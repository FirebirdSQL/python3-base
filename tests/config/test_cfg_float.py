# SPDX-FileCopyrightText: 2025-present The Firebird Projects <www.firebirdsql.org>
#
# SPDX-License-Identifier: MIT
#
# PROGRAM/MODULE: firebird-base
# FILE:           tests/config/test_cfg_float.py
# DESCRIPTION:    Tests for firebird.base.config FloatOption
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

"""Unit tests for the FloatOption configuration option class."""

from __future__ import annotations

import pytest
from configparser import ConfigParser # Import for type hinting

from firebird.base import config
from firebird.base.config_pb2 import ConfigProto # Import for proto tests
from firebird.base.types import Error

# --- Constants for Test Sections ---
DEFAULT_S = "DEFAULT"
PRESENT_S = "present"
ABSENT_S = "absent"
BAD_S = "bad_value"
EMPTY_S = "empty"

# --- Constants for Test Values ---
PRESENT_VAL = 500.0 # Loaded from "500"
DEFAULT_VAL = 10.5
DEFAULT_OPT_VAL = 3000.0 # Default for the option itself
NEW_VAL = 0.0

# --- Fixtures ---

@pytest.fixture
def conf(base_conf: ConfigParser) -> ConfigParser:
    """Provides a ConfigParser instance initialized with float test data."""
    conf_str = """
[%(DEFAULT)s]
# Option defined in DEFAULT section
option_name = 10.5
[%(PRESENT)s]
# Option present (as integer string, should convert to float)
option_name = 500
[%(ABSENT)s]
# Section exists, but option is absent (will inherit from DEFAULT)
[%(BAD)s]
# Option present but with an invalid float string
option_name = bad_value
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
    """Tests basic FloatOption functionality: init, load, value access, clear, default handling."""
    opt = config.FloatOption("option_name", "description")

    # Verify initial state
    assert opt.name == "option_name"
    assert opt.datatype == float
    assert opt.description == "description"
    assert not opt.required
    assert opt.default is None
    assert opt.value is None # Initial value without default is None
    opt.validate() # Should pass as not required

    # Load value from [present] section (was "500", converts to 500.0)
    opt.load_config(conf, PRESENT_S)
    assert opt.value == PRESENT_VAL
    assert opt.get_as_str() == "500.0" # String representation of float
    assert isinstance(opt.value, opt.datatype)
    assert opt.get_formatted() == "500.0" # Config file format

    # Clear value (should reset to None as no default)
    opt.clear(to_default=False)
    assert opt.value is None

    # Clear value to default (should still be None)
    opt.clear(to_default=True)
    assert opt.value is None

    # Load value from [DEFAULT] section
    opt.load_config(conf, DEFAULT_S)
    assert opt.value == DEFAULT_VAL # 10.5
    assert isinstance(opt.value, opt.datatype)
    assert opt.get_formatted() == "10.5"

    # Set value manually to None
    opt.set_value(None)
    assert opt.value is None

    # Load from section where option is absent (should inherit from DEFAULT)
    opt.load_config(conf, ABSENT_S)
    assert opt.value == DEFAULT_VAL
    assert isinstance(opt.value, opt.datatype)

    # Set value manually
    opt.set_value(NEW_VAL)
    assert opt.value == NEW_VAL # 0.0
    assert isinstance(opt.value, opt.datatype)

def test_required(conf: ConfigParser):
    """Tests FloatOption with the 'required' flag."""
    opt = config.FloatOption("option_name", "description", required=True)

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
    """Tests loading invalid float string values."""
    opt = config.FloatOption("option_name", "description")

    # Load from section with bad value
    with pytest.raises(ValueError, match="could not convert string to float: 'bad_value'"):
        opt.load_config(conf, BAD_S)
    assert opt.value is None # Value should remain unchanged (None)

    # Load from section with empty value
    with pytest.raises(ValueError, match="could not convert string to float: ''"):
        opt.load_config(conf, EMPTY_S)
    assert opt.value is None

    # Test assigning invalid type via set_value
    with pytest.raises(TypeError, match="Option 'option_name' value must be a 'float', not 'int'"):
        opt.set_value(10) # type: ignore
    with pytest.raises(TypeError, match="Option 'option_name' value must be a 'float', not 'bool'"):
        opt.set_value(True) # type: ignore

    # Test setting invalid string via set_as_str
    with pytest.raises(ValueError, match="could not convert string to float: 'not-a-float'"):
        opt.set_as_str("not-a-float")

def test_default(conf: ConfigParser):
    """Tests FloatOption with a defined default value."""
    opt = config.FloatOption("option_name", "description", default=DEFAULT_OPT_VAL)

    # Verify initial state (default value should be set)
    assert not opt.required
    assert opt.default == DEFAULT_OPT_VAL
    assert isinstance(opt.default, opt.datatype)
    assert opt.value == DEFAULT_OPT_VAL # Initial value is the default
    assert isinstance(opt.value, opt.datatype)
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
    opt = config.FloatOption("option_name", "description", default=DEFAULT_OPT_VAL)
    proto_value = 800000.125 # Use a float value for testing
    opt.set_value(proto_value)

    # Serialize (saves as double)
    opt.save_proto(proto)
    assert "option_name" in proto.options
    assert proto.options["option_name"].HasField('as_double')
    assert proto.options["option_name"].as_double == proto_value
    proto_dump = proto.SerializeToString() # Save serialized state

    # Clear option and deserialize from double
    opt.clear(to_default=False)
    assert opt.value is None
    proto_read = ConfigProto()
    proto_read.ParseFromString(proto_dump)
    opt.load_proto(proto_read)
    assert opt.value == proto_value
    assert isinstance(opt.value, opt.datatype)

    # Test deserializing from float field in proto
    proto.Clear()
    proto.options["option_name"].as_float = -123.5 # Use as_float field
    opt.load_proto(proto)
    # pytest.approx needed due to potential float precision issues
    assert opt.value == pytest.approx(-123.5)

    # Test deserializing from string representation in proto
    proto.Clear()
    proto.options["option_name"].as_string = "987.654"
    opt.load_proto(proto)
    assert opt.value == pytest.approx(987.654)

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
    proto.options["option_name"].as_bytes = b'abc' # Invalid type for FloatOption
    with pytest.raises(TypeError, match="Wrong value type: bytes"):
        opt.load_proto(proto)

    # Test loading bad proto value (invalid string for float)
    proto.Clear()
    proto.options["option_name"].as_string = "not-a-float"
    with pytest.raises(ValueError, match="could not convert string to float: 'not-a-float'"):
        opt.load_proto(proto)


def test_get_config(conf: ConfigParser):
    """Tests the get_config method for generating config file string representation."""
    opt = config.FloatOption("option_name", "description", default=DEFAULT_OPT_VAL)

    # Test output with default value (should be commented out)
    expected_lines_default = """; description
; Type: float
;option_name = 3000.0
"""
    assert opt.get_config() == expected_lines_default

    # Test output with explicitly set value
    opt.set_value(500.75)
    expected_lines_set = """; description
; Type: float
option_name = 500.75
"""
    assert opt.get_config() == expected_lines_set

    # Test output when value is None (should show <UNDEFINED>)
    opt.set_value(None)
    expected_lines_none = """; description
; Type: float
option_name = <UNDEFINED>
"""
    assert opt.get_config() == expected_lines_none
    # Check get_formatted directly for None case
    assert opt.get_formatted() == "<UNDEFINED>"

    # Test plain output
    opt.set_value(123.45)
    assert opt.get_config(plain=True) == "option_name = 123.45\n"
    opt.set_value(None)
    assert opt.get_config(plain=True) == "option_name = <UNDEFINED>\n"
