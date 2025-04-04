# SPDX-FileCopyrightText: 2019-present The Firebird Projects <www.firebirdsql.org>
#
# SPDX-License-Identifier: MIT
#
# PROGRAM/MODULE: firebird-base
# FILE:           tests/config/test_cfg_pyexpr.py
# DESCRIPTION:    Tests for firebird.base.config PyExprOption
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

"""Unit tests for the PyExprOption configuration option class."""

from __future__ import annotations

import pytest
from configparser import ConfigParser # Import for type hinting

from firebird.base import config
from firebird.base.config_pb2 import ConfigProto # Import for proto tests
from firebird.base.types import Error, PyExpr

# --- Constants for Test Sections ---
DEFAULT_S = "DEFAULT"
PRESENT_S = "present"
ABSENT_S = "absent"
BAD_S = "bad_value" # Invalid Python syntax
EMPTY_S = "empty"

# --- Constants for Test Values ---
PRESENT_VAL_STR = "this.value in [1, 2, 3]"
PRESENT_VAL = PyExpr(PRESENT_VAL_STR)
DEFAULT_VAL_STR = "this.value is None"
DEFAULT_VAL = PyExpr(DEFAULT_VAL_STR)
DEFAULT_OPT_VAL_STR = "True" # Simple default expression
DEFAULT_OPT_VAL = PyExpr(DEFAULT_OPT_VAL_STR) # Default for the option itself
NEW_VAL_STR = 'this.value == "VALUE"'
NEW_VAL = PyExpr(NEW_VAL_STR)
MULTI_VAL_STR = """this.value in [
    1,
    2,
    3
]"""
MULTI_VAL = PyExpr(MULTI_VAL_STR) # Multiline expression
# Expected format for multiline in get_formatted()
MULTIFMT_VAL_STR = """this.value in [
       1,
       2,
       3
   ]"""

# --- Test Helper Classes ---

class ValueHolder:
    """Simple object used for evaluating test expressions."""
    value: int | str | None = None
    x: int = 100

# --- Fixtures ---

@pytest.fixture
def conf(base_conf: ConfigParser) -> ConfigParser:
    """Provides a ConfigParser instance initialized with PyExpr test data."""
    conf_str = """
[%(DEFAULT)s]
# Expression defined in DEFAULT section
option_name = this.value is None
[%(PRESENT)s]
# Expression defined in specific section
option_name = this.value in [1, 2, 3]
[%(ABSENT)s]
# Section exists, but option is absent (will inherit from DEFAULT)
[%(BAD)s]
# Invalid Python syntax
option_name = This is not a valid Python expression
[%(EMPTY)s]
# Option present but empty (invalid expression)
option_name =
"""
    # Format the string with section names and read into the config parser
    base_conf.read_string(conf_str % {"DEFAULT": DEFAULT_S, "PRESENT": PRESENT_S,
                                      "ABSENT": ABSENT_S, "BAD": BAD_S, "EMPTY": EMPTY_S})
    return base_conf

# --- Test Cases ---

def test_simple(conf: ConfigParser):
    """Tests basic PyExprOption: init, load, value access, clear, default handling, evaluation."""
    opt = config.PyExprOption("option_name", "description")

    # Verify initial state
    assert opt.name == "option_name"
    assert opt.datatype == PyExpr
    assert opt.description == "description"
    assert not opt.required
    assert opt.default is None
    assert opt.value is None # Initial value without default is None
    opt.validate() # Should pass as not required

    # Load value from [present] section
    opt.load_config(conf, PRESENT_S)
    assert opt.value == PRESENT_VAL # String equality check
    assert opt.get_as_str() == PRESENT_VAL_STR # String representation
    assert isinstance(opt.value, opt.datatype)
    assert opt.get_formatted() == PRESENT_VAL_STR # Config format for single line

    # Check the loaded expression evaluates correctly
    obj = ValueHolder()
    obj.value = 2
    assert eval(opt.value.expr, {"this": obj}) is True # Use compiled .expr
    fce = opt.value.get_callable("this")
    assert fce(obj) is True
    obj.value = 4
    assert eval(opt.value.expr, {"this": obj}) is False
    assert fce(obj) is False

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
    # Check default expression evaluation
    obj.value = None
    assert eval(opt.value.expr, {"this": obj}) is True
    obj.value = 1
    assert eval(opt.value.expr, {"this": obj}) is False

    # Set value manually to None
    opt.set_value(None)
    assert opt.value is None

    # Load from section where option is absent (should inherit from DEFAULT)
    opt.load_config(conf, ABSENT_S)
    assert opt.value == DEFAULT_VAL
    assert isinstance(opt.value, opt.datatype)

    # Set value manually using PyExpr instance
    opt.set_value(NEW_VAL)
    assert opt.value == NEW_VAL
    assert isinstance(opt.value, opt.datatype)
    # Check new expression evaluation
    obj.value = "VALUE"
    assert eval(opt.value.expr, {"this": obj}) is True
    obj.value = "OTHER"
    assert eval(opt.value.expr, {"this": obj}) is False

    # Test multiline expression formatting
    opt.value = MULTI_VAL
    assert opt.value == MULTI_VAL_STR
    assert opt.get_as_str() == MULTI_VAL_STR
    # get_formatted adds indentation for multiline
    assert opt.get_formatted() == MULTIFMT_VAL_STR

def test_required(conf: ConfigParser):
    """Tests PyExprOption with the 'required' flag."""
    opt = config.PyExprOption("option_name", "description", required=True)

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
    """Tests loading invalid Python expression strings."""
    opt = config.PyExprOption("option_name", "description")

    # Load from section with bad syntax
    with pytest.raises(SyntaxError, match="invalid syntax"):
        opt.load_config(conf, BAD_S)
    # Verify error details if possible (line/offset might vary slightly)
    # assert cm.value.args == ("invalid syntax", ("PyExpr", 1, 15, "This is not a valid Python expression", 1, 20))
    assert opt.value is None # Value should remain unchanged (None)

    # Load from section with empty value (invalid expression)
    with pytest.raises(SyntaxError):
        opt.load_config(conf, EMPTY_S)
    assert opt.value is None

    # Test assigning invalid type via set_value
    with pytest.raises(TypeError, match="Option 'option_name' value must be a 'PyExpr', not 'float'"):
        opt.set_value(10.0) # type: ignore

    # Test setting invalid syntax string via set_as_str
    with pytest.raises(SyntaxError):
        opt.set_as_str("a +")


def test_default(conf: ConfigParser):
    """Tests PyExprOption with a defined default PyExpr value."""
    opt = config.PyExprOption("option_name", "description", default=DEFAULT_OPT_VAL)

    # Verify initial state (default value should be set)
    assert not opt.required
    assert opt.default == DEFAULT_OPT_VAL # PyExpr("True")
    assert isinstance(opt.default, opt.datatype)
    assert opt.value == DEFAULT_OPT_VAL # Initial value is the default
    assert isinstance(opt.value, opt.datatype)
    assert eval(opt.value.expr) is True # Check default expression evaluates
    opt.validate() # Should pass

    # Load value from [present] section (overrides default)
    opt.load_config(conf, PRESENT_S)
    assert opt.value == PRESENT_VAL

    # Clear to default
    opt.clear(to_default=True)
    assert opt.value == opt.default
    assert eval(opt.value.expr) is True

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
    opt = config.PyExprOption("option_name", "description", default=DEFAULT_OPT_VAL)

    # Test with single-line expression
    proto_value_single = PyExpr("item.x > 10")
    proto_value_single_str = "item.x > 10"
    opt.set_value(proto_value_single)

    # Serialize (saves as string)
    opt.save_proto(proto)
    assert "option_name" in proto.options
    assert proto.options["option_name"].HasField('as_string')
    assert proto.options["option_name"].as_string == proto_value_single_str
    proto_dump_single = proto.SerializeToString()

    # Clear option and deserialize from string
    opt.clear(to_default=False)
    proto_read = ConfigProto()
    proto_read.ParseFromString(proto_dump_single)
    opt.load_proto(proto_read)
    assert opt.value == proto_value_single # String equality
    assert isinstance(opt.value, opt.datatype)
    # Check evaluation
    assert eval(opt.value.expr, {"item": ValueHolder()}) # Assumes item.x access doesn't fail

    # Test with multi-line expression
    proto.Clear()
    proto_value_multi = MULTI_VAL
    proto_value_multi_str = MULTI_VAL_STR
    opt.set_value(proto_value_multi)
    opt.save_proto(proto)
    assert proto.options["option_name"].as_string == proto_value_multi_str
    proto_dump_multi = proto.SerializeToString()

    opt.clear(to_default=False)
    proto_read = ConfigProto()
    proto_read.ParseFromString(proto_dump_multi)
    opt.load_proto(proto_read)
    assert opt.value == proto_value_multi


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
    proto.options["option_name"].as_uint32 = 1000 # Invalid type for PyExprOption
    with pytest.raises(TypeError, match="Wrong value type: uint32"):
        opt.load_proto(proto)

    # Test loading bad proto value (invalid string syntax)
    proto.Clear()
    proto.options["option_name"].as_string = "a +"
    with pytest.raises(SyntaxError):
        opt.load_proto(proto)


def test_get_config(conf: ConfigParser):
    """Tests the get_config method for generating config file string representation."""
    opt = config.PyExprOption("option_name", "description", default=DEFAULT_OPT_VAL)

    # Test output with default value (should be commented out)
    expected_lines_default = """; description
; Type: PyExpr
;option_name = True
"""
    assert opt.get_config() == expected_lines_default

    # Test output with explicitly set single-line value
    opt.set_value(NEW_VAL) # 'this.value == "VALUE"'
    expected_lines_new = """; description
; Type: PyExpr
option_name = this.value == "VALUE"
"""
    assert opt.get_config() == expected_lines_new

    # Test output with explicitly set multi-line value
    opt.set_value(MULTI_VAL)
    # Expected format includes indentation for subsequent lines
    expected_lines_multi = """; description
; Type: PyExpr
option_name = this.value in [
       1,
       2,
       3
   ]\n"""
    assert opt.get_config() == expected_lines_multi


    # Test output when value is None (should show <UNDEFINED>)
    opt.set_value(None)
    expected_lines_none = """; description
; Type: PyExpr
option_name = <UNDEFINED>
"""
    assert opt.get_config() == expected_lines_none
    # Check get_formatted directly for None case
    assert opt.get_formatted() == "<UNDEFINED>"

    # Test plain output
    opt.set_value(NEW_VAL)
    assert opt.get_config(plain=True) == f"option_name = {NEW_VAL_STR}\n"
    opt.set_value(MULTI_VAL)
    # Plain output for multiline shouldn't have leading indent on first line
    expected_plain_multi = f"""option_name = this.value in [
       1,
       2,
       3
   ]
"""
    assert opt.get_config(plain=True) == expected_plain_multi

    opt.set_value(None)
    assert opt.get_config(plain=True) == "option_name = <UNDEFINED>\n"
