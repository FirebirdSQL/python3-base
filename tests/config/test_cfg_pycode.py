# SPDX-FileCopyrightText: 2019-present The Firebird Projects <www.firebirdsql.org>
#
# SPDX-License-Identifier: MIT
#
# PROGRAM/MODULE: firebird-base
# FILE:           tests/config/test_cfg_pycode.py
# DESCRIPTION:    Tests for firebird.base.config PyCodeOption
# CREATED:        28.1.2025
#
# The contents of this file are subject to the MIT License
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#
# Copyright (c) 2025 Firebird Project (www.firebirdsql.org)
# All Rights Reserved.
#
# Contributor(s): Pavel Císař (original code)
#                 ______________________________________.

"""Unit tests for the PyCodeOption configuration option class."""

from __future__ import annotations

import io # For capturing output during code execution test
import pytest
from configparser import ConfigParser # Import for type hinting

from firebird.base import config
from firebird.base.config_pb2 import ConfigProto # Import for proto tests
from firebird.base.types import Error, PyCode

# --- Constants for Test Sections ---
DEFAULT_S = "DEFAULT"
PRESENT_S = "present"
ABSENT_S = "absent"
BAD_S = "bad_value" # Invalid Python syntax
EMPTY_S = "empty"

# --- Constants for Test Values ---
DEFAULT_VAL_STR = 'print("Default value")'
DEFAULT_VAL = PyCode(DEFAULT_VAL_STR)
PRESENT_VAL_STR = '\ndef pp(value):\n    print("Value:",value,file=output)\n\nfor i in [1,2,3]:\n    pp(i)'
PRESENT_VAL = PyCode(PRESENT_VAL_STR)
DEFAULT_OPT_VAL_STR = "print('Option Default')"
DEFAULT_OPT_VAL = PyCode(DEFAULT_OPT_VAL_STR) # Default for the option itself
NEW_VAL_STR = 'print("NEW value")'
NEW_VAL = PyCode(NEW_VAL_STR)

# --- Fixtures ---

@pytest.fixture
def conf(base_conf: ConfigParser) -> ConfigParser:
    """Provides a ConfigParser instance initialized with PyCode test data."""
    conf_str = """
[%(DEFAULT)s]
# Simple code block in DEFAULT section
option_name = print("Default value")
[%(PRESENT)s]
# Multiline code block using vertical bar indentation
option_name =
    | def pp(value):
    |     print("Value:",value,file=output)
    |
    | for i in [1,2,3]:
    |     pp(i)
[%(ABSENT)s]
# Section exists, but option is absent (will inherit from DEFAULT)
[%(BAD)s]
# Invalid Python syntax
option_name = This is not a valid Python code block
[%(EMPTY)s]
# Option present but empty
option_name =
"""
    # Format the string with section names and read into the config parser
    base_conf.read_string(conf_str % {"DEFAULT": DEFAULT_S, "PRESENT": PRESENT_S,
                                      "ABSENT": ABSENT_S, "BAD": BAD_S, "EMPTY": EMPTY_S})
    return base_conf

# --- Test Cases ---

def test_simple(conf: ConfigParser):
    """Tests basic PyCodeOption: init, load, value access, clear, default handling, execution."""
    opt = config.PyCodeOption("option_name", "description")

    # Verify initial state
    assert opt.name == "option_name"
    assert opt.datatype == PyCode
    assert opt.description == "description"
    assert not opt.required
    assert opt.default is None
    assert opt.value is None # Initial value without default is None
    opt.validate() # Should pass as not required

    # Load value from [present] section (multiline with verticals)
    opt.load_config(conf, PRESENT_S)
    # Equality check compares the source code string
    assert opt.value == PRESENT_VAL
    # get_as_str returns the source code string
    assert opt.get_as_str() == PRESENT_VAL_STR
    assert isinstance(opt.value, opt.datatype)
    # get_formatted should add back the vertical bars for config output
    assert opt.get_formatted().strip().endswith("|     pp(i)")

    # Check the loaded code executes correctly
    out = io.StringIO()
    exec_namespace = {"output": out}
    exec(opt.value.code, exec_namespace) # Use the compiled code object
    assert out.getvalue() == "Value: 1\nValue: 2\nValue: 3\n"

    # Clear value (should reset to None as no default)
    opt.clear(to_default=False)
    assert opt.value is None

    # Clear value to default (should still be None)
    opt.clear(to_default=True)
    assert opt.value is None

    # Load value from [DEFAULT] section
    opt.load_config(conf, DEFAULT_S)
    assert opt.value == DEFAULT_VAL
    assert isinstance(opt.value, opt.datatype)
    # Check default code execution
    out = io.StringIO()
    exec(opt.value.code, {"print": lambda *a, **kw: print(*a, file=out, **kw)}) # Capture print
    assert out.getvalue() == "Default value\n"

    # Set value manually to None
    opt.set_value(None)
    assert opt.value is None

    # Load from section where option is absent (should inherit from DEFAULT)
    opt.load_config(conf, ABSENT_S)
    assert opt.value == DEFAULT_VAL
    assert isinstance(opt.value, opt.datatype)

    # Set value manually using PyCode instance
    opt.set_value(NEW_VAL)
    assert opt.value == NEW_VAL
    assert isinstance(opt.value, opt.datatype)
    # Check new code execution
    out = io.StringIO()
    exec(opt.value.code, {"print": lambda *a, **kw: print(*a, file=out, **kw)})
    assert out.getvalue() == "NEW value\n"

def test_required(conf: ConfigParser):
    """Tests PyCodeOption with the 'required' flag."""
    opt = config.PyCodeOption("option_name", "description", required=True)

    # Verify initial state (required, no default)
    assert opt.required
    assert opt.default is None
    assert opt.value is None
    # Validation should fail when value is None
    with pytest.raises(Error, match="Missing value for required option 'option_name'"):
        opt.validate()

    # Load value, validation should pass
    opt.load_config(conf, PRESENT_S)
    assert opt.value == PRESENT_VAL
    opt.validate()

    # Clear to default (which is None), validation should fail again
    opt.clear(to_default=True)
    assert opt.value is None
    with pytest.raises(Error, match="Missing value for required option 'option_name'"):
        opt.validate()

    # Load from DEFAULT section
    opt.load_config(conf, DEFAULT_S)
    assert opt.value == DEFAULT_VAL
    opt.validate() # Should pass

    # Setting value to None should raise ValueError for required option
    with pytest.raises(ValueError, match="Value is required for option 'option_name'"):
        opt.set_value(None)

    # Load from absent section (inherits from DEFAULT)
    opt.load_config(conf, ABSENT_S)
    assert opt.value == DEFAULT_VAL
    opt.validate()

    # Set value manually
    opt.set_value(NEW_VAL)
    assert opt.value == NEW_VAL
    opt.validate()

def test_bad_value(conf: ConfigParser):
    """Tests loading invalid Python code strings."""
    opt = config.PyCodeOption("option_name", "description")

    # Load from section with bad syntax
    with pytest.raises(SyntaxError, match="invalid syntax"):
        opt.load_config(conf, BAD_S)
    # Verify error details if possible (line/offset might vary slightly)
    # assert cm.value.args == ("invalid syntax", ("PyCode", 1, 15, "This is not a valid Python code block\n", 1, 20))
    assert opt.value is None # Value should remain unchanged (None)

    # Load from section with empty value (should be valid empty code)
    opt.load_config(conf, EMPTY_S)
    assert opt.value == PyCode("")
    exec(opt.value.code) # Empty code should execute without error

    # Test assigning invalid type via set_value
    with pytest.raises(TypeError, match="Option 'option_name' value must be a 'PyCode', not 'float'"):
        opt.set_value(10.0) # type: ignore

    # Test setting invalid syntax string via set_as_str
    with pytest.raises(SyntaxError):
        opt.set_as_str("def foo(:")


def test_default(conf: ConfigParser):
    """Tests PyCodeOption with a defined default PyCode value."""
    opt = config.PyCodeOption("option_name", "description", default=DEFAULT_OPT_VAL)

    # Verify initial state (default value should be set)
    assert not opt.required
    assert opt.default == DEFAULT_OPT_VAL
    assert isinstance(opt.default, opt.datatype)
    assert opt.value == DEFAULT_OPT_VAL # Initial value is the default
    assert isinstance(opt.value, opt.datatype)
    # Check default code execution
    out = io.StringIO()
    exec(opt.value.code, {"print": lambda *a, **kw: print(*a, file=out, **kw)})
    assert out.getvalue() == "Option Default\n"
    opt.validate() # Should pass

    # Load value from [present] section (overrides default)
    opt.load_config(conf, PRESENT_S)
    assert opt.value == PRESENT_VAL

    # Clear to default
    opt.clear(to_default=True)
    assert opt.value == opt.default

    # Clear to None
    opt.clear(to_default=False)
    assert opt.value is None

    # Load from [DEFAULT] section (overrides option default)
    opt.load_config(conf, DEFAULT_S)
    assert opt.value == DEFAULT_VAL

    # Set value manually to None
    opt.set_value(None)
    assert opt.value is None

    # Load from absent section (inherits from DEFAULT, overrides option default)
    opt.load_config(conf, ABSENT_S)
    assert opt.value == DEFAULT_VAL

    # Set value manually
    opt.set_value(NEW_VAL)
    assert opt.value == NEW_VAL

def test_proto(conf: ConfigParser, proto: ConfigProto):
    """Tests serialization to and deserialization from Protobuf messages."""
    opt = config.PyCodeOption("option_name", "description", default=DEFAULT_OPT_VAL)
    proto_value_str = "for i in range(3): print(i)"
    proto_value = PyCode(proto_value_str)

    # Set value and serialize (saves as string)
    opt.set_value(proto_value)
    opt.save_proto(proto)
    assert "option_name" in proto.options
    assert proto.options["option_name"].HasField('as_string')
    assert proto.options["option_name"].as_string == proto_value_str
    proto_dump = proto.SerializeToString() # Save serialized state

    # Clear option and deserialize from string
    opt.clear(to_default=False)
    assert opt.value is None
    proto_read = ConfigProto()
    proto_read.ParseFromString(proto_dump)
    opt.load_proto(proto_read)
    assert opt.value == proto_value # String equality
    # Check loaded code works
    out = io.StringIO()
    exec(opt.value.code, {"print": lambda *a, **kw: print(*a, file=out, **kw)})
    assert out.getvalue() == "0\n1\n2\n"
    assert isinstance(opt.value, opt.datatype)

    # Test saving None value (should not add option to proto)
    proto.Clear()
    opt.set_value(None)
    opt.save_proto(proto)
    assert "option_name" not in proto.options

    # Test loading from empty proto (value should remain unchanged)
    opt.set_value(DEFAULT_OPT_VAL) # Set a known value
    proto.Clear()
    opt.load_proto(proto)
    assert opt.value is DEFAULT_OPT_VAL # Should not change to None

    # Test loading bad proto value (wrong type)
    proto.Clear()
    proto.options["option_name"].as_uint32 = 1000 # Invalid type for PyCodeOption
    with pytest.raises(TypeError, match="Wrong value type: uint32"):
        opt.load_proto(proto)

    # Test loading bad proto value (invalid string syntax)
    proto.Clear()
    proto.options["option_name"].as_string = "def foo(:"
    with pytest.raises(SyntaxError):
        opt.load_proto(proto)


def test_get_config(conf: ConfigParser):
    """Tests the get_config method for generating config file string representation."""
    opt = config.PyCodeOption("option_name", "description", default=DEFAULT_OPT_VAL)

    # Test output with default value (should be commented out, no verticals needed for simple string)
    expected_lines_default = """; description
; Type: PyCode
;option_name = print('Option Default')
"""
    assert opt.get_config() == expected_lines_default

    # Test output with multiline value (PRESENT_VAL, should have verticals)
    opt.set_value(PRESENT_VAL)
    expected_lines_present = """; description
; Type: PyCode
option_name =
   | def pp(value):
   |     print("Value:",value,file=output)
   |
   | for i in [1,2,3]:
   |     pp(i)"""
    # Compare stripped lines due to potential trailing whitespace differences
    assert "\n".join(x.rstrip() for x in opt.get_config().splitlines()) == expected_lines_present

    # Test output when value is None (should show <UNDEFINED>)
    opt.set_value(None)
    expected_lines_none = """; description
; Type: PyCode
option_name = <UNDEFINED>
"""
    assert opt.get_config() == expected_lines_none
    # Check get_formatted directly for None case
    assert opt.get_formatted() == "<UNDEFINED>"

    # Test plain output
    opt.set_value(NEW_VAL)
    # Plain output shouldn't have vertical bars or comments
    expected_plain_new = "option_name = print(\"NEW value\")\n"
    assert opt.get_config(plain=True) == expected_plain_new

    opt.set_value(None)
    assert opt.get_config(plain=True) == "option_name = <UNDEFINED>\n"
