# SPDX-FileCopyrightText: 2025-present The Firebird Projects <www.firebirdsql.org>
#
# SPDX-License-Identifier: MIT
#
# PROGRAM/MODULE: firebird-base
# FILE:           tests/config/test_cfg_int.py
# DESCRIPTION:    Tests for firebird.base.config IntOption
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

"""Unit tests for the IntOption configuration option class."""

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
NEGATIVE_S = "negative" # Section for testing signed values

# --- Constants for Test Values ---
PRESENT_VAL = 500
DEFAULT_VAL = 10
DEFAULT_OPT_VAL = 3000 # Default for the option itself
NEW_VAL = 0
NEGATIVE_VAL = -99

# --- Fixtures ---

@pytest.fixture
def conf(base_conf: ConfigParser) -> ConfigParser:
    """Provides a ConfigParser instance initialized with integer test data."""
    conf_str = """
[%(DEFAULT)s]
# Option defined in DEFAULT section
option_name = 10
[%(PRESENT)s]
# Option present in its own section
option_name = 500
[%(ABSENT)s]
# Section exists, but option is absent (will inherit from DEFAULT)
[%(BAD)s]
# Option present but with an invalid integer string
option_name = bad_value
[%(EMPTY)s]
# Option present but empty
option_name =
[%(NEGATIVE)s]
# Option with a negative value
option_name = -99
"""
    # Format the string with section names and read into the config parser
    base_conf.read_string(conf_str % {"DEFAULT": DEFAULT_S, "PRESENT": PRESENT_S,
                                      "ABSENT": ABSENT_S, "BAD": BAD_S, "EMPTY": EMPTY_S,
                                      "NEGATIVE": NEGATIVE_S})
    return base_conf

# --- Test Cases ---

def test_simple_unsigned(conf: ConfigParser):
    """Tests basic *unsigned* IntOption: init, load, value access, clear, default handling."""
    # Default is unsigned (signed=False)
    opt = config.IntOption("option_name", "description")

    # Verify initial state
    assert opt.name == "option_name"
    assert opt.datatype == int
    assert opt.description == "description"
    assert not opt.required
    assert opt.default is None
    assert opt.value is None # Initial value without default is None
    opt.validate() # Should pass as not required

    # Load value from [present] section
    opt.load_config(conf, PRESENT_S)
    assert opt.value == PRESENT_VAL
    assert opt.get_as_str() == "500" # String representation
    assert isinstance(opt.value, opt.datatype)
    assert opt.get_formatted() == "500" # Config file format

    # Clear value (should reset to None as no default)
    opt.clear(to_default=False)
    assert opt.value is None

    # Clear value to default (should still be None)
    opt.clear(to_default=True)
    assert opt.value is None

    # Load value from [DEFAULT] section
    opt.load_config(conf, DEFAULT_S)
    assert opt.value == DEFAULT_VAL # 10
    assert isinstance(opt.value, opt.datatype)
    assert opt.get_formatted() == "10"

    # Set value manually to None
    opt.set_value(None)
    assert opt.value is None

    # Load from section where option is absent (should inherit from DEFAULT)
    opt.load_config(conf, ABSENT_S)
    assert opt.value == DEFAULT_VAL
    assert isinstance(opt.value, opt.datatype)

    # Set value manually
    opt.set_value(NEW_VAL)
    assert opt.value == NEW_VAL # 0
    assert isinstance(opt.value, opt.datatype)

    # Test setting negative value (should fail for unsigned)
    with pytest.raises(ValueError, match="Negative numbers not allowed"):
        opt.set_value(-1)
    with pytest.raises(ValueError, match="Negative numbers not allowed"):
        opt.value = -1 # type: ignore
    with pytest.raises(ValueError, match="Negative numbers not allowed"):
        opt.set_as_str("-1")
    # Loading negative value from config should also fail
    with pytest.raises(ValueError, match="Negative numbers not allowed"):
        opt.load_config(conf, NEGATIVE_S)


def test_signed(conf: ConfigParser):
    """Tests IntOption with signed=True."""
    opt = config.IntOption("option_name", "description", signed=True)

    # Verify initial state
    assert opt.value is None

    # Load positive value
    opt.load_config(conf, PRESENT_S)
    assert opt.value == PRESENT_VAL

    # Load negative value
    opt.load_config(conf, NEGATIVE_S)
    assert opt.value == NEGATIVE_VAL
    assert opt.get_formatted() == "-99"

    # Set negative value manually
    opt.set_value(-123)
    assert opt.value == -123

    # Set negative value via string
    opt.set_as_str("-456")
    assert opt.value == -456


def test_required(conf: ConfigParser):
    """Tests IntOption with the 'required' flag."""
    opt = config.IntOption("option_name", "description", required=True)

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
    """Tests loading invalid integer string values."""
    opt = config.IntOption("option_name", "description") # Unsigned

    # Load from section with bad value
    with pytest.raises(ValueError, match="invalid literal for int\\(\\) with base 10: 'bad_value'"):
        opt.load_config(conf, BAD_S)
    assert opt.value is None # Value should remain unchanged (None)

    # Load from section with empty value
    with pytest.raises(ValueError, match="invalid literal for int\\(\\) with base 10: ''"):
        opt.load_config(conf, EMPTY_S)
    assert opt.value is None

    # Test assigning invalid type via set_value
    with pytest.raises(TypeError, match="Option 'option_name' value must be a 'int', not 'float'"):
        opt.set_value(10.0) # type: ignore
    with pytest.raises(TypeError, match="Option 'option_name' value must be a 'int', not 'str'"):
        opt.set_value("10") # type: ignore

    # Test setting invalid string via set_as_str
    with pytest.raises(ValueError, match="invalid literal for int\\(\\) with base 10: 'not-an-int'"):
        opt.set_as_str("not-an-int")


def test_default(conf: ConfigParser):
    """Tests IntOption with a defined default value."""
    opt = config.IntOption("option_name", "description", default=DEFAULT_OPT_VAL)

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
    """Tests serialization to and deserialization from Protobuf messages for IntOption."""
    # --- Unsigned ---
    opt_unsigned = config.IntOption("option_name", "description", default=DEFAULT_OPT_VAL)
    proto_value_unsigned = 800000
    opt_unsigned.set_value(proto_value_unsigned)

    # Serialize (saves as uint64)
    opt_unsigned.save_proto(proto)
    assert "option_name" in proto.options
    assert proto.options["option_name"].HasField('as_uint64')
    assert proto.options["option_name"].as_uint64 == proto_value_unsigned
    proto_dump_unsigned = proto.SerializeToString()

    # Clear option and deserialize from uint64
    opt_unsigned.clear(to_default=False)
    proto_read = ConfigProto()
    proto_read.ParseFromString(proto_dump_unsigned)
    opt_unsigned.load_proto(proto_read)
    assert opt_unsigned.value == proto_value_unsigned
    assert isinstance(opt_unsigned.value, opt_unsigned.datatype)

    # --- Signed ---
    opt_signed = config.IntOption("option_name", "description signed", signed=True)
    proto_value_signed = -500000
    opt_signed.set_value(proto_value_signed)
    proto.Clear() # Clear proto for signed test

    # Serialize (saves as sint64)
    opt_signed.save_proto(proto)
    assert "option_name" in proto.options
    assert proto.options["option_name"].HasField('as_sint64')
    assert proto.options["option_name"].as_sint64 == proto_value_signed
    proto_dump_signed = proto.SerializeToString()

    # Clear option and deserialize from sint64
    opt_signed.clear(to_default=False)
    proto_read = ConfigProto()
    proto_read.ParseFromString(proto_dump_signed)
    opt_signed.load_proto(proto_read)
    assert opt_signed.value == proto_value_signed
    assert isinstance(opt_signed.value, opt_signed.datatype)

    # --- Common Tests ---
    opt = opt_unsigned # Use one instance for remaining tests

    # Test deserializing from various compatible proto int types
    proto.Clear()
    proto.options["option_name"].as_sint32 = 123 # Load sint32 into unsigned int option
    opt.load_proto(proto)
    assert opt.value == 123

    proto.Clear()
    proto.options["option_name"].as_uint32 = 456 # Load uint32 into unsigned int option
    opt.load_proto(proto)
    assert opt.value == 456

    # Test deserializing from string representation in proto
    proto.Clear()
    proto.options["option_name"].as_string = "789"
    opt.load_proto(proto)
    assert opt.value == 789

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
    proto.options["option_name"].as_bytes = b'abc' # Invalid type for IntOption
    with pytest.raises(TypeError, match="Wrong value type: bytes"):
        opt.load_proto(proto)

    # Test loading bad proto value (invalid string for int)
    proto.Clear()
    proto.options["option_name"].as_string = "not-an-int"
    with pytest.raises(ValueError, match="invalid literal for int\\(\\) with base 10: 'not-an-int'"):
        opt.load_proto(proto)


def test_get_config(conf: ConfigParser):
    """Tests the get_config method for generating config file string representation."""
    opt = config.IntOption("option_name", "description", default=DEFAULT_OPT_VAL)

    # Test output with default value (should be commented out)
    expected_lines_default = """; description
; Type: int
;option_name = 3000
"""
    assert opt.get_config() == expected_lines_default

    # Test output with explicitly set value
    opt.set_value(500)
    expected_lines_set = """; description
; Type: int
option_name = 500
"""
    assert opt.get_config() == expected_lines_set

    # Test output when value is None (should show <UNDEFINED>)
    opt.set_value(None)
    expected_lines_none = """; description
; Type: int
option_name = <UNDEFINED>
"""
    assert opt.get_config() == expected_lines_none
    # Check get_formatted directly for None case
    assert opt.get_formatted() == "<UNDEFINED>"

    # Test plain output
    opt.set_value(12345)
    assert opt.get_config(plain=True) == "option_name = 12345\n"
    opt.set_value(None)
    assert opt.get_config(plain=True) == "option_name = <UNDEFINED>\n"
