# SPDX-FileCopyrightText: 2025-present The Firebird Projects <www.firebirdsql.org>
#
# SPDX-License-Identifier: MIT
#
# PROGRAM/MODULE: firebird-base
# FILE:           tests/config/test_cfg_flag.py
# DESCRIPTION:    Tests for firebird.base.config FlagOption
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

"""Unit tests for the FlagOption configuration option class."""

from __future__ import annotations

# Use STRICT boundary behavior for IntFlag tests to catch invalid integer values.
from enum import STRICT, Flag, IntFlag, auto
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
ILLEGAL_INT_S = "illegal_int" # Section for testing loading an integer string
MIXED_SEP_S = "mixed_sep" # Section for testing mixed separators

# --- Test Helper Classes ---

class SimpleIntFlag(IntFlag, boundary=STRICT):
    """IntFlag for testing, using STRICT boundary."""
    NONE = 0 # Explicit zero member often useful
    ONE = auto()
    TWO = auto()
    THREE = auto()
    FOUR = auto()
    FIVE = auto()

class SimpleFlag(Flag):
    """Standard Flag for comparison."""
    ONE = auto()
    TWO = auto()
    THREE = auto()

# --- Constants for Test Values ---
DEFAULT_VAL = SimpleIntFlag.ONE
PRESENT_VAL = SimpleIntFlag.TWO | SimpleIntFlag.THREE
DEFAULT_OPT_VAL = SimpleIntFlag.THREE | SimpleIntFlag.FOUR # Default for the option itself
NEW_VAL = SimpleIntFlag.FIVE

# --- Fixtures ---

@pytest.fixture
def conf(base_conf: ConfigParser) -> ConfigParser:
    """Provides a ConfigParser instance initialized with Flag test data."""
    conf_str = """
[%(DEFAULT)s]
# Flag is defined by single name in DEFAULT section
option_name = ONE
[%(PRESENT)s]
# Flag defined by multiple names (comma separated, case-insensitive load)
option_name = TwO, tHrEe
[%(ABSENT)s]
# Section exists, but option is absent (will inherit from DEFAULT)
[%(BAD)s]
# Option present but with a name not in the Flag
option_name = bad_value
[%(EMPTY)s]
# Option present but empty (should result in Flag(0))
option_name =
[%(ILLEGAL_INT)s]
# Tries to load an integer string (invalid for FlagOption string parsing)
option_name = 8
[%(MIXED_SEP)s]
# Uses mixed separators (pipe and comma)
option_name = ONE | two, THREE
"""
    # Format the string with section names and read into the config parser
    base_conf.read_string(conf_str % {"DEFAULT": DEFAULT_S, "PRESENT": PRESENT_S,
                                      "ABSENT": ABSENT_S, "BAD": BAD_S, "EMPTY": EMPTY_S,
                                      "ILLEGAL_INT": ILLEGAL_INT_S,
                                      "MIXED_SEP": MIXED_SEP_S})
    return base_conf

# --- Test Cases ---

def test_simple(conf: ConfigParser):
    """Tests basic FlagOption: init, load, value access, clear, default handling."""
    opt = config.FlagOption("option_name", SimpleIntFlag, "description")

    # Verify initial state
    assert opt.name == "option_name"
    assert opt.datatype == SimpleIntFlag
    assert opt.description == "description"
    assert not opt.required
    assert opt.default is None
    assert opt.value is None # Initial value without default is None
    assert opt.allowed == SimpleIntFlag # Allowed defaults to the enum type
    opt.validate() # Should pass as not required

    # Load value from [present] section (comma separated, case-insensitive)
    opt.load_config(conf, PRESENT_S)
    assert opt.value == PRESENT_VAL # SimpleIntFlag.TWO | SimpleIntFlag.THREE
    # get_as_str() should produce pipe-separated canonical names
    assert opt.get_as_str() == "TWO|THREE"
    assert isinstance(opt.value, opt.datatype)
    # get_formatted() uses lowercase names
    assert opt.get_formatted() == "two|three"

    # Clear value (should reset to None as no default)
    opt.clear(to_default=False)
    assert opt.value is None

    # Clear value to default (should still be None)
    opt.clear(to_default=True)
    assert opt.value is None

    # Load value from [DEFAULT] section
    opt.load_config(conf, DEFAULT_S)
    assert opt.value == DEFAULT_VAL # SimpleIntFlag.ONE
    assert isinstance(opt.value, opt.datatype)
    assert opt.get_formatted() == "one"

    # Set value manually to None
    opt.set_value(None)
    assert opt.value is None

    # Load from section where option is absent (should inherit from DEFAULT)
    opt.load_config(conf, ABSENT_S)
    assert opt.value == DEFAULT_VAL
    assert isinstance(opt.value, opt.datatype)

    # Set value manually using member
    opt.set_value(NEW_VAL) # SimpleIntFlag.FIVE
    assert opt.value == NEW_VAL
    assert isinstance(opt.value, opt.datatype)
    assert opt.get_formatted() == "five"

    # Test loading mixed separators
    with pytest.raises(ValueError, match="Illegal value 'two, three' for flag option"):
        opt.load_config(conf, MIXED_SEP_S)

    # Test loading empty value
    with pytest.raises(ValueError, match="Illegal value '' for flag option"):
        opt.load_config(conf, EMPTY_S)

def test_required(conf: ConfigParser):
    """Tests FlagOption with the 'required' flag."""
    opt = config.FlagOption("option_name", SimpleIntFlag, "description", required=True)

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
    """Tests loading invalid flag string values or invalid types."""
    opt = config.FlagOption("option_name", SimpleIntFlag, "description")

    # Load from section with bad value (not a flag member name)
    with pytest.raises(ValueError, match="'bad_value'"): # Internal lookup fails
        opt.load_config(conf, BAD_S)
    assert opt.value is None # Value should remain unchanged (None)

    # Load from section with integer string (invalid for string parsing)
    with pytest.raises(ValueError, match="'8'"):
        opt.load_config(conf, ILLEGAL_INT_S)
    assert opt.value is None

    # Test assigning invalid type via set_value
    with pytest.raises(TypeError, match="Option 'option_name' value must be a 'SimpleIntFlag', not 'SimpleFlag'"):
        opt.set_value(SimpleFlag.ONE) # Type mismatch

    # Test setting invalid string via set_as_str
    with pytest.raises(ValueError, match="'invalid_name'"):
        opt.set_as_str("one | invalid_name")


def test_allowed_values(conf: ConfigParser):
    """Tests FlagOption with the 'allowed' parameter restricting valid members."""
    allowed_members = [SimpleIntFlag.ONE, SimpleIntFlag.TWO, SimpleIntFlag.FOUR]
    opt = config.FlagOption("option_name", SimpleIntFlag, "description",
                            allowed=allowed_members)

    # Verify allowed list is set
    assert opt.allowed == allowed_members

    # Load value where all members are allowed
    opt.load_config(conf, DEFAULT_S) # Value is ONE
    assert opt.value == SimpleIntFlag.ONE

    # Load value where some members are *not* allowed
    with pytest.raises(ValueError, match="'three'"): # PRESENT_S contains TWO and THREE
        opt.load_config(conf, PRESENT_S)
    assert opt.value == SimpleIntFlag.ONE # Should remain unchanged

    # Try setting a value containing disallowed members manually
    disallowed_val = SimpleIntFlag.ONE | SimpleIntFlag.THREE # THREE is not allowed
    with pytest.raises(ValueError, match="Illegal value.*for flag option 'option_name'"):
        opt.set_value(disallowed_val)

    # Try setting a value that is completely disallowed
    with pytest.raises(ValueError, match="Illegal value.*for flag option 'option_name'"):
        opt.set_value(SimpleIntFlag.FIVE)

    # Test get_config shows only allowed members in description
    expected_config_desc = """; description
; Type: flag [one, two, four]
;option_name = <UNDEFINED>
"""
    opt.value = None # Reset value
    assert opt.get_config() == expected_config_desc


def test_default(conf: ConfigParser):
    """Tests FlagOption with a defined default value."""
    opt = config.FlagOption("option_name", SimpleIntFlag, "description", default=DEFAULT_OPT_VAL)

    # Verify initial state (default value should be set)
    assert not opt.required
    assert opt.default == DEFAULT_OPT_VAL # SimpleIntFlag.THREE | SimpleIntFlag.FOUR
    assert isinstance(opt.default, opt.datatype)
    assert opt.value == DEFAULT_OPT_VAL # Initial value is the default
    assert isinstance(opt.value, opt.datatype)
    opt.validate() # Should pass

    # Load value from [present] section (overrides default)
    opt.load_config(conf, PRESENT_S)
    assert opt.value == PRESENT_VAL # SimpleIntFlag.TWO | SimpleIntFlag.THREE

    # Clear to default
    opt.clear(to_default=True)
    assert opt.value == opt.default # Should be THREE | FOUR

    # Clear to None
    opt.clear(to_default=False)
    assert opt.value is None

    # Load from [DEFAULT] section (overrides option default)
    opt.load_config(conf, DEFAULT_S)
    assert opt.value == DEFAULT_VAL # SimpleIntFlag.ONE

    # Set value manually to None
    opt.set_value(None)
    assert opt.value is None

    # Load from absent section (inherits from DEFAULT, overrides option default)
    opt.load_config(conf, ABSENT_S)
    assert opt.value == DEFAULT_VAL # SimpleIntFlag.ONE

    # Set value manually
    opt.set_value(NEW_VAL) # SimpleIntFlag.FIVE
    assert opt.value == NEW_VAL

def test_proto(conf: ConfigParser, proto: ConfigProto):
    """Tests serialization to and deserialization from Protobuf messages."""
    opt = config.FlagOption("option_name", SimpleIntFlag, "description", default=DEFAULT_OPT_VAL)
    proto_value_flag = SimpleIntFlag.ONE | SimpleIntFlag.FIVE
    proto_value_int = proto_value_flag.value # Integer representation
    proto_value_str = "ONE | FIVE" # String representation

    # Set value and serialize (saves as uint64)
    opt.set_value(proto_value_flag)
    opt.save_proto(proto)
    assert "option_name" in proto.options
    assert proto.options["option_name"].HasField('as_uint64')
    assert proto.options["option_name"].as_uint64 == proto_value_int
    proto_dump = proto.SerializeToString() # Save serialized state

    # Clear option and deserialize from uint64
    opt.clear(to_default=False)
    assert opt.value is None
    proto_read = ConfigProto()
    proto_read.ParseFromString(proto_dump)
    opt.load_proto(proto_read)
    assert opt.value == proto_value_flag
    assert isinstance(opt.value, opt.datatype)

    # Test deserializing from string representation in proto
    proto.Clear()
    proto.options["option_name"].as_string = proto_value_str
    opt.load_proto(proto)
    assert opt.value == proto_value_flag

    proto.Clear()
    proto.options["option_name"].as_string = "two, FOUR" # Mixed case, comma sep
    opt.load_proto(proto)
    assert opt.value == (SimpleIntFlag.TWO | SimpleIntFlag.FOUR)


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
    proto.options["option_name"].as_float = 1.23 # Invalid type for FlagOption
    with pytest.raises(TypeError, match="Wrong value type: float"):
        opt.load_proto(proto)

    # Test loading bad proto value (invalid integer value for STRICT flag)
    proto.Clear()
    proto.options["option_name"].as_uint64 = 1000 # Not a valid flag combination
    with pytest.raises(ValueError, match="invalid value 1000"):
        opt.load_proto(proto)

    # Test loading bad proto value (invalid string for flag)
    proto.Clear()
    proto.options["option_name"].as_string = "one | non_member"
    with pytest.raises(ValueError, match="'non_member'"):
        opt.load_proto(proto)


def test_get_config(conf: ConfigParser):
    """Tests the get_config method for generating config file string representation."""
    opt = config.FlagOption("option_name", SimpleIntFlag, "description", default=DEFAULT_OPT_VAL)
    all_members_str = "one, two, three, four, five" # Assuming NONE=0 exists

    # Test output with default value (THREE | FOUR, should be commented out)
    expected_lines_default = f"""; description
; Type: flag [{all_members_str}]
;option_name = three|four
"""
    assert opt.get_config() == expected_lines_default

    # Test output with explicitly set value (FIVE)
    opt.set_value(SimpleIntFlag.FIVE)
    expected_lines_set = f"""; description
; Type: flag [{all_members_str}]
option_name = five
"""
    assert opt.get_config() == expected_lines_set

    # Test output with combined value (ONE | TWO)
    opt.set_value(SimpleIntFlag.ONE | SimpleIntFlag.TWO)
    expected_lines_comb = f"""; description
; Type: flag [{all_members_str}]
option_name = one|two
"""
    assert opt.get_config() == expected_lines_comb


    # Test output when value is None (should show <UNDEFINED>)
    opt.set_value(None)
    expected_lines_none = f"""; description
; Type: flag [{all_members_str}]
option_name = <UNDEFINED>
"""
    assert opt.get_config() == expected_lines_none
    # Check get_formatted directly for None case
    assert opt.get_formatted() == "<UNDEFINED>"

    # Test plain output
    opt.set_value(SimpleIntFlag.ONE | SimpleIntFlag.THREE)
    assert opt.get_config(plain=True) == "option_name = one|three\n"
    opt.set_value(None)
    assert opt.get_config(plain=True) == "option_name = <UNDEFINED>\n"

    # Test with 'allowed' restriction
    opt_allowed = config.FlagOption("option_name", SimpleIntFlag, "description",
                                    allowed=[SimpleIntFlag.ONE, SimpleIntFlag.TWO])
    opt_allowed.set_value(SimpleIntFlag.TWO)
    expected_lines_allowed = """; description
; Type: flag [one, two]
option_name = two
"""
    assert opt_allowed.get_config() == expected_lines_allowed
