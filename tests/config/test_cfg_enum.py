# SPDX-FileCopyrightText: 2025-present The Firebird Projects <www.firebirdsql.org>
#
# SPDX-License-Identifier: MIT
#
# PROGRAM/MODULE: firebird-base
# FILE:           tests/config/test_cfg_enum.py
# DESCRIPTION:    Tests for firebird.base.config EnumOption
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

"""Unit tests for the EnumOption configuration option class."""

from __future__ import annotations

from enum import IntEnum
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
ILLEGAL_VAL_S = "illegal" # Section for testing loading an integer string

# --- Test Helper Classes ---

class SimpleEnum(IntEnum):
    """Enum for testing EnumOption."""
    UNKNOWN    = 0
    READY      = 1
    RUNNING    = 2
    WAITING    = 3
    SUSPENDED  = 4
    FINISHED   = 5
    ABORTED    = 6
    # Aliases
    CREATED    = 1
    BLOCKED    = 3
    STOPPED    = 4 # Alias for SUSPENDED
    TERMINATED = 6 # Alias for ABORTED

# --- Constants for Test Values ---
DEFAULT_VAL = SimpleEnum.UNKNOWN
PRESENT_VAL = SimpleEnum.RUNNING
DEFAULT_OPT_VAL = SimpleEnum.READY # Default for the option itself
NEW_VAL = SimpleEnum.SUSPENDED # Will test setting via STOPPED alias too

# --- Fixtures ---

@pytest.fixture
def conf(base_conf: ConfigParser) -> ConfigParser:
    """Provides a ConfigParser instance initialized with Enum test data."""
    conf_str = """
[%(DEFAULT)s]
# Enum is defined by name in DEFAULT section
option_name = UNKNOWN
[%(PRESENT)s]
# Enum defined by name in specific section (case-insensitive load)
option_name = RuNnInG
[%(ABSENT)s]
# Section exists, but option is absent (will inherit from DEFAULT)
[%(BAD)s]
# Option present but with a name not in the Enum
option_name = bad_value
[%(EMPTY)s]
# Option present but empty
option_name =
[%(ILLEGAL)s]
# Tries to load an integer string, which is invalid for EnumOption
option_name = 3
"""
    # Format the string with section names and read into the config parser
    base_conf.read_string(conf_str % {"DEFAULT": DEFAULT_S, "PRESENT": PRESENT_S,
                                      "ABSENT": ABSENT_S, "BAD": BAD_S, "EMPTY": EMPTY_S,
                                      "ILLEGAL": ILLEGAL_VAL_S})
    return base_conf

# --- Test Cases ---

def test_simple(conf: ConfigParser):
    """Tests basic EnumOption functionality: init, load, value access, clear, default handling."""
    opt = config.EnumOption("option_name", SimpleEnum, "description")

    # Verify initial state
    assert opt.name == "option_name"
    assert opt.datatype == SimpleEnum
    assert opt.description == "description"
    assert not opt.required
    assert opt.default is None
    assert opt.value is None # Initial value without default is None
    assert opt.allowed == SimpleEnum # Allowed should default to the enum type
    opt.validate() # Should pass as not required

    # Load value from [present] section (case-insensitive)
    opt.load_config(conf, PRESENT_S)
    assert opt.value == PRESENT_VAL # SimpleEnum.RUNNING
    assert opt.get_as_str() == "RUNNING" # String representation is the member name
    assert isinstance(opt.value, opt.datatype)
    assert opt.get_formatted() == "running" # Config file format uses lowercase

    # Clear value (should reset to None as no default)
    opt.clear(to_default=False)
    assert opt.value is None

    # Clear value to default (should still be None)
    opt.clear(to_default=True)
    assert opt.value is None

    # Load value from [DEFAULT] section
    opt.load_config(conf, DEFAULT_S)
    assert opt.value == DEFAULT_VAL # SimpleEnum.UNKNOWN
    assert isinstance(opt.value, opt.datatype)
    assert opt.get_formatted() == "unknown"

    # Set value manually to None
    opt.set_value(None)
    assert opt.value is None

    # Load from section where option is absent (should inherit from DEFAULT)
    opt.load_config(conf, ABSENT_S)
    assert opt.value == DEFAULT_VAL
    assert isinstance(opt.value, opt.datatype)

    # Set value manually using member
    opt.set_value(NEW_VAL) # SimpleEnum.SUSPENDED
    assert opt.value == NEW_VAL
    assert isinstance(opt.value, opt.datatype)
    assert opt.get_formatted() == "suspended"

    # Set value manually using alias member (STOPPED -> SUSPENDED)
    opt.set_value(SimpleEnum.STOPPED)
    assert opt.value == NEW_VAL # Should resolve to the primary member SUSPENDED
    assert opt.get_formatted() == "suspended" # Output uses primary member name

def test_required(conf: ConfigParser):
    """Tests EnumOption with the 'required' flag."""
    opt = config.EnumOption("option_name", SimpleEnum, "description", required=True)

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
    """Tests loading invalid enum string values."""
    opt = config.EnumOption("option_name", SimpleEnum, "description")

    # Load from section with bad value (not an enum member name)
    with pytest.raises(ValueError, match="Illegal value 'bad_value' for enum type 'SimpleEnum'"):
        opt.load_config(conf, BAD_S)
    assert opt.value is None # Value should remain unchanged (None)

    # Load from section with empty value (should also be illegal)
    with pytest.raises(ValueError, match="Illegal value '' for enum type 'SimpleEnum'"):
        opt.load_config(conf, EMPTY_S)
    assert opt.value is None

    # Load from section with integer string (illegal for EnumOption)
    with pytest.raises(ValueError, match="Illegal value '3' for enum type 'SimpleEnum'"):
        opt.load_config(conf, ILLEGAL_VAL_S)
    assert opt.value is None

    # Test assigning invalid type via set_value
    with pytest.raises(TypeError, match="Option 'option_name' value must be a 'SimpleEnum', not 'float'"):
        opt.set_value(10.0) # type: ignore

    # Test setting invalid string via set_as_str
    with pytest.raises(ValueError, match="Illegal value 'invalid_name' for enum type 'SimpleEnum'"):
        opt.set_as_str("invalid_name")


def test_allowed_values(conf: ConfigParser):
    """Tests EnumOption with the 'allowed' parameter restricting valid members."""
    allowed_members = [SimpleEnum.READY, SimpleEnum.RUNNING, SimpleEnum.FINISHED]
    opt = config.EnumOption("option_name", SimpleEnum, "description",
                            allowed=allowed_members)

    # Verify allowed list is set
    assert opt.allowed == allowed_members

    # Load a value that *is* allowed
    opt.load_config(conf, PRESENT_S) # Value is RUNNING
    assert opt.value == SimpleEnum.RUNNING

    # Load a value that is *not* allowed (UNKNOWN from DEFAULT section)
    opt.value = None # Reset before loading
    with pytest.raises(ValueError, match="Illegal value 'UNKNOWN' for enum type 'SimpleEnum'"):
        # Note: set_as_str raises the error internally during load_config
        opt.load_config(conf, DEFAULT_S)
    assert opt.value is None # Should remain None

    # Try setting a disallowed value manually
    with pytest.raises(ValueError, match="Value '<SimpleEnum.SUSPENDED: 4>' not allowed"):
        opt.set_value(SimpleEnum.SUSPENDED)

    # Test get_config shows only allowed members in description
    expected_config_desc = """; description
; Type: enum [ready, running, finished]
;option_name = <UNDEFINED>
"""
    opt.value = None # Reset value
    assert opt.get_config() == expected_config_desc


def test_default(conf: ConfigParser):
    """Tests EnumOption with a defined default value."""
    opt = config.EnumOption("option_name", SimpleEnum, "description", default=DEFAULT_OPT_VAL)

    # Verify initial state (default value should be set)
    assert not opt.required
    assert opt.default == DEFAULT_OPT_VAL # SimpleEnum.READY
    assert isinstance(opt.default, opt.datatype)
    assert opt.value == DEFAULT_OPT_VAL # Initial value is the default
    assert isinstance(opt.value, opt.datatype)
    opt.validate() # Should pass

    # Load value from [present] section (overrides default)
    opt.load_config(conf, PRESENT_S)
    assert opt.value == PRESENT_VAL # SimpleEnum.RUNNING

    # Clear to default
    opt.clear(to_default=True)
    assert opt.value == opt.default # Should be SimpleEnum.READY

    # Clear to None
    opt.clear(to_default=False)
    assert opt.value is None

    # Load from [DEFAULT] section (overrides option default)
    opt.load_config(conf, DEFAULT_S)
    assert opt.value == DEFAULT_VAL # SimpleEnum.UNKNOWN

    # Set value manually to None
    opt.set_value(None)
    assert opt.value is None

    # Load from absent section (inherits from DEFAULT, overrides option default)
    opt.load_config(conf, ABSENT_S)
    assert opt.value == DEFAULT_VAL # SimpleEnum.UNKNOWN

    # Set value manually
    opt.set_value(NEW_VAL) # SimpleEnum.SUSPENDED
    assert opt.value == NEW_VAL


def test_proto(conf: ConfigParser, proto: ConfigProto):
    """Tests serialization to and deserialization from Protobuf messages."""
    opt = config.EnumOption("option_name", SimpleEnum, "description", default=DEFAULT_OPT_VAL)
    proto_value = SimpleEnum.FINISHED # Use a specific value for testing

    # Set value and serialize (saves as string name)
    opt.set_value(proto_value)
    opt.save_proto(proto)
    assert "option_name" in proto.options
    assert proto.options["option_name"].HasField('as_string')
    assert proto.options["option_name"].as_string == "FINISHED"
    proto_dump = proto.SerializeToString() # Save serialized state

    # Clear option and deserialize from string
    opt.clear(to_default=False)
    assert opt.value is None
    proto_read = ConfigProto()
    proto_read.ParseFromString(proto_dump)
    opt.load_proto(proto_read)
    assert opt.value == proto_value
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
    proto.options["option_name"].as_uint32 = 1 # Invalid type for EnumOption (expects string)
    with pytest.raises(TypeError, match="Wrong value type: uint32"):
        opt.load_proto(proto)

    # Test loading bad proto value (invalid string for enum)
    proto.Clear()
    proto.options["option_name"].as_string = "not_a_member"
    with pytest.raises(ValueError, match="Illegal value 'not_a_member' for enum type 'SimpleEnum'"):
        opt.load_proto(proto)


def test_get_config(conf: ConfigParser):
    """Tests the get_config method for generating config file string representation."""
    opt = config.EnumOption("option_name", SimpleEnum, "description", default=DEFAULT_OPT_VAL)

    # Test output with default value (READY, should be commented out)
    expected_lines_default = """; description
; Type: enum [unknown, ready, running, waiting, suspended, finished, aborted]
;option_name = ready
"""
    assert opt.get_config() == expected_lines_default

    # Test output with explicitly set value (SUSPENDED)
    opt.set_value(SimpleEnum.SUSPENDED)
    expected_lines_set = """; description
; Type: enum [unknown, ready, running, waiting, suspended, finished, aborted]
option_name = suspended
"""
    assert opt.get_config() == expected_lines_set

    # Test output with alias value (STOPPED -> SUSPENDED)
    opt.set_value(SimpleEnum.STOPPED)
    assert opt.get_config() == expected_lines_set # Should still output primary name

    # Test output when value is None (should show <UNDEFINED>)
    opt.set_value(None)
    expected_lines_none = """; description
; Type: enum [unknown, ready, running, waiting, suspended, finished, aborted]
option_name = <UNDEFINED>
"""
    assert opt.get_config() == expected_lines_none
    # Check get_formatted directly for None case
    assert opt.get_formatted() == "<UNDEFINED>"

    # Test plain output
    opt.set_value(SimpleEnum.RUNNING)
    assert opt.get_config(plain=True) == "option_name = running\n"
    opt.set_value(None)
    assert opt.get_config(plain=True) == "option_name = <UNDEFINED>\n"

    # Test with 'allowed' restriction
    opt_allowed = config.EnumOption("option_name", SimpleEnum, "description",
                                    allowed=[SimpleEnum.READY, SimpleEnum.RUNNING])
    opt_allowed.set_value(SimpleEnum.RUNNING)
    expected_lines_allowed = """; description
; Type: enum [ready, running]
option_name = running
"""
    assert opt_allowed.get_config() == expected_lines_allowed
