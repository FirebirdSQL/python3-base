# SPDX-FileCopyrightText: 2019-present The Firebird Projects <www.firebirdsql.org>
#
# SPDX-License-Identifier: MIT
#
# PROGRAM/MODULE: firebird-base
# FILE:           tests/config/test_cfg_pycall.py
# DESCRIPTION:    Tests for firebird.base.config PyCallableOption
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

"""Unit tests for the PyCallableOption configuration option class."""

from __future__ import annotations

from inspect import signature, Signature # Import Signature for type hint
import pytest
from configparser import ConfigParser # Import for type hinting

from firebird.base import config
from firebird.base.config_pb2 import ConfigProto # Import for proto tests
from firebird.base.types import Error, PyCallable

# --- Constants for Test Sections ---
DEFAULT_S = "DEFAULT"
PRESENT_S = "present"
ABSENT_S = "absent"
BAD_S = "bad_value" # Invalid Python code / structure
BAD_SIGNATURE_S = "bad_signature" # Valid code, wrong signature
EMPTY_S = "empty"

# --- Test Helper Classes / Functions ---

def foo_func(value: int) -> int:
    """Target signature for testing PyCallableOption."""
    # The body is irrelevant, only the signature matters
    return 0 # pragma: no cover

# --- Constants for Test Values ---
DEFAULT_VAL = PyCallable("\ndef foo(value: int) -> int:\n    return value * 2")
PRESENT_VAL = PyCallable("\n# Some comment\ndef foo(value: int) -> int:\n    # Some comment\n    return value * 5")
DEFAULT_OPT_VAL = PyCallable("\ndef foo(value: int) -> int:\n    return value") # Default for the option itself
NEW_VAL = PyCallable("\ndef foo(value: int) -> int:\n    return value * 3")

# --- Fixtures ---

@pytest.fixture
def conf(base_conf: ConfigParser) -> ConfigParser:
    """Provides a ConfigParser instance initialized with PyCallable test data."""
    conf_str = """
[%(DEFAULT)s]
# Callable definition in DEFAULT section
option_name =
    | def foo(value: int) -> int:
    |     return value * 2
[%(PRESENT)s]
# Callable definition in specific section
option_name =
    | # Some comment
    | def foo(value: int) -> int:
    |     # Some comment
    |     return value * 5
[%(ABSENT)s]
# Section exists, but option is absent (will inherit from DEFAULT)
[%(BAD)s]
# Not a valid function/class definition
option_name = This is not a valid Python function/procedure definition
[%(BAD_SIGNATURE)s]
# Valid Python, but wrong signature (different param name, extra param)
option_name =
    | def foo(val: str, extra: bool = False) -> int:
    |     return int(len(val))
[%(EMPTY)s]
# Option present but empty
option_name =
"""
    # Format the string with section names and read into the config parser
    base_conf.read_string(conf_str % {"DEFAULT": DEFAULT_S, "PRESENT": PRESENT_S,
                                      "ABSENT": ABSENT_S, "BAD": BAD_S, "EMPTY": EMPTY_S,
                                      "BAD_SIGNATURE": BAD_SIGNATURE_S})
    return base_conf

# --- Test Cases ---

# Parameterize to test different ways of providing the signature
@pytest.mark.parametrize("sig_arg", [signature(foo_func), foo_func, "foo_func(value: int) -> int"])
def test_simple(conf: ConfigParser, sig_arg: Signature | callable | str):
    """Tests basic PyCallableOption: init (with various signature inputs), load, value access, clear."""
    opt = config.PyCallableOption("option_name", "description", signature=sig_arg)

    # Verify initial state
    assert opt.name == "option_name"
    assert opt.datatype == PyCallable
    assert opt.description == "description"
    assert not opt.required
    assert opt.default is None
    assert opt.value is None # Initial value without default is None
    assert isinstance(opt.signature, Signature) # Ensure signature was processed
    assert str(opt.signature) == "(value: 'int') -> 'int'" # Verify processed signature
    opt.validate() # Should pass as not required

    # Load value from [present] section
    opt.load_config(conf, PRESENT_S)
    # Note: Equality check compares the string source code
    assert opt.value == PRESENT_VAL
    assert opt.get_as_str() == str(PRESENT_VAL) # String representation
    assert isinstance(opt.value, opt.datatype)
    assert opt.value.name == "foo" # Check callable name extraction
    assert opt.get_formatted().strip().endswith("|     return value * 5") # Check config format with verticals

    # Check the loaded callable works as expected
    assert opt.value(1) == 5 # Call the loaded function
    assert opt.value(10) == 50

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
    assert opt.value(10) == 20 # Check default callable works

    # Set value manually to None
    opt.set_value(None)
    assert opt.value is None

    # Load from section where option is absent (should inherit from DEFAULT)
    opt.load_config(conf, ABSENT_S)
    assert opt.value == DEFAULT_VAL
    assert isinstance(opt.value, opt.datatype)

    # Set value manually using PyCallable instance
    opt.set_value(NEW_VAL)
    assert opt.value == NEW_VAL
    assert isinstance(opt.value, opt.datatype)
    assert opt.value(10) == 30 # Check new callable works

def test_required(conf: ConfigParser):
    """Tests PyCallableOption with the 'required' flag."""
    opt = config.PyCallableOption("option_name", "description", signature=signature(foo_func),
                                  required=True)

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
    """Tests loading invalid callable definitions or code with wrong signatures."""
    opt = config.PyCallableOption("option_name", "description", signature=signature(foo_func))

    # Load from section with bad value (not function/class def)
    with pytest.raises(ValueError, match="Python function or class definition not found"):
        opt.load_config(conf, BAD_S)
    assert opt.value is None # Value should remain unchanged (None)

    # Load from section with empty value
    with pytest.raises(ValueError, match="Python function or class definition not found"):
        opt.load_config(conf, EMPTY_S)
    assert opt.value is None

    # Load from section with syntactically valid code but wrong signature
    with pytest.raises(ValueError, match="Wrong number of parameters"):
        opt.load_config(conf, BAD_SIGNATURE_S)
    assert opt.value is None

    # Test assigning invalid type via set_value
    with pytest.raises(TypeError, match="Option 'option_name' value must be a 'PyCallable', not 'float'"):
        opt.set_value(10.0) # type: ignore

    # Test setting invalid string via set_as_str (bad Python syntax)
    with pytest.raises(SyntaxError):
        opt.set_as_str("def foo(:")

    # Test setting invalid string via set_as_str (not function/class def)
    with pytest.raises(ValueError, match="Python function or class definition not found"):
        opt.set_as_str("a = 1")

    # Test setting string with wrong signature via set_as_str
    with pytest.raises(ValueError, match="Wrong type, parameter 'value'"):
        opt.set_as_str("\ndef foo(value: str) -> int:\n    return 1")
    with pytest.raises(ValueError, match="Wrong callable return type"):
        opt.set_as_str("\ndef foo(value: int) -> str:\n    return 'a'")
    with pytest.raises(ValueError, match="Wrong number of parameters"):
        opt.set_as_str("\ndef foo(value: int, extra: int) -> int:\n    return 1")


def test_default(conf: ConfigParser):
    """Tests PyCallableOption with a defined default PyCallable value."""
    opt = config.PyCallableOption("option_name", "description", signature=signature(foo_func),
                                  default=DEFAULT_OPT_VAL)

    # Verify initial state (default value should be set)
    assert not opt.required
    assert opt.default == DEFAULT_OPT_VAL
    assert isinstance(opt.default, opt.datatype)
    assert opt.value == DEFAULT_OPT_VAL # Initial value is the default
    assert isinstance(opt.value, opt.datatype)
    assert opt.value(10) == 10 # Default function returns input
    opt.validate() # Should pass

    # Load value from [present] section (overrides default)
    opt.load_config(conf, PRESENT_S)
    assert opt.value == PRESENT_VAL
    assert opt.value(10) == 50

    # Clear to default
    opt.clear(to_default=True)
    assert opt.value == opt.default
    assert opt.value(10) == 10

    # Clear to None
    opt.clear(to_default=False)
    assert opt.value is None

    # Load from [DEFAULT] section (overrides option default)
    opt.load_config(conf, DEFAULT_S)
    assert opt.value == DEFAULT_VAL
    assert opt.value(10) == 20

    # Set value manually to None
    opt.set_value(None)
    assert opt.value is None

    # Load from absent section (inherits from DEFAULT, overrides option default)
    opt.load_config(conf, ABSENT_S)
    assert opt.value == DEFAULT_VAL

    # Set value manually
    opt.set_value(NEW_VAL)
    assert opt.value == NEW_VAL
    assert opt.value(10) == 30


def test_proto(conf: ConfigParser, proto: ConfigProto):
    """Tests serialization to and deserialization from Protobuf messages."""
    opt = config.PyCallableOption("option_name", "description", signature=signature(foo_func),
                                  default=DEFAULT_OPT_VAL)
    proto_value_str = "\ndef foo(value: int) -> int:\n    return value * 100"
    proto_value = PyCallable(proto_value_str)

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
    assert opt.value(10) == 1000 # Functional equality
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
    proto.options["option_name"].as_uint32 = 1000 # Invalid type for PyCallableOption
    with pytest.raises(TypeError, match="Wrong value type: uint32"):
        opt.load_proto(proto)

    # Test loading bad proto value (invalid string for callable)
    proto.Clear()
    proto.options["option_name"].as_string = "def foo(:" # Syntax error
    with pytest.raises(SyntaxError):
        opt.load_proto(proto)

    proto.Clear()
    proto.options["option_name"].as_string = "a = 1" # Not def/class
    with pytest.raises(ValueError, match="Python function or class definition not found"):
        opt.load_proto(proto)


def test_get_config(conf: ConfigParser):
    """Tests the get_config method for generating config file string representation."""
    opt = config.PyCallableOption("option_name", "description", signature=signature(foo_func),
                                  default=DEFAULT_OPT_VAL)

    # Test output with default value (should be commented out, with vertical bars)
    expected_lines_default = """; description
; Type: PyCallable
;option_name =
;   | def foo(value: int) -> int:
;   |     return value"""
    # Need to strip trailing whitespace for comparison as get_config adds it
    assert "\n".join(x.rstrip() for x in opt.get_config().splitlines()) == expected_lines_default

    # Test output with explicitly set value (PRESENT_VAL)
    opt.set_value(PRESENT_VAL)
    expected_lines_present = """; description
; Type: PyCallable
option_name =
   | # Some comment
   | def foo(value: int) -> int:
   |     # Some comment
   |     return value * 5"""
    assert "\n".join(x.rstrip() for x in opt.get_config().splitlines()) == expected_lines_present

    # Test output when value is None (should show <UNDEFINED>)
    opt.set_value(None)
    expected_lines_none = """; description
; Type: PyCallable
option_name = <UNDEFINED>
"""
    assert opt.get_config() == expected_lines_none
    # Check get_formatted directly for None case
    assert opt.get_formatted() == "<UNDEFINED>"

    # Test plain output
    opt.set_value(NEW_VAL)
    # Plain output shouldn't have vertical bars or comments
    expected_plain_new = """option_name =
   | def foo(value: int) -> int:
   |     return value * 3
""".replace("option_name =", "option_name = ") # Fix editor trailing white cleanup
    # Normalize whitespace for comparison as plain output might have different leading space
    assert opt.get_config(plain=True).strip() == expected_plain_new.strip()

    opt.set_value(None)
    assert opt.get_config(plain=True) == "option_name = <UNDEFINED>\n"
