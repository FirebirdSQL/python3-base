# SPDX-FileCopyrightText: 2025-present The Firebird Projects <www.firebirdsql.org>
#
# SPDX-License-Identifier: MIT
#
# PROGRAM/MODULE: firebird-base
# FILE:           tests/config/test_cfg_uuid.py
# DESCRIPTION:    Tests for firebird.base.config UUIDOption
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

"""Unit tests for the UUIDOption configuration option class."""

from __future__ import annotations

from uuid import UUID
import pytest
from configparser import ConfigParser # Import for type hinting

from firebird.base import config
from firebird.base.config_pb2 import ConfigProto # Import for proto tests
from firebird.base.types import Error

# --- Constants for Test Sections ---
DEFAULT_S = "DEFAULT"
PRESENT_S = "present"
ABSENT_S = "absent"
BAD_S = "bad_value" # Invalid UUID format
EMPTY_S = "empty"

# --- Constants for Test Values ---
PRESENT_VAL_STR_HEX = "fbcdd0acde0d11e99b5b5404a6a1fd6e"
PRESENT_VAL = UUID(PRESENT_VAL_STR_HEX)
DEFAULT_VAL_STR = "e3a57070-de0d-11e9-9b5b-5404a6a1fd6e"
DEFAULT_VAL = UUID(DEFAULT_VAL_STR)
DEFAULT_OPT_VAL_STR = "ede5cc42-de0d-11e9-9b5b-5404a6a1fd6e"
DEFAULT_OPT_VAL = UUID(DEFAULT_OPT_VAL_STR) # Default for the option itself
NEW_VAL_STR = "92ef5c08-de0e-11e9-9b5b-5404a6a1fd6e"
NEW_VAL = UUID(NEW_VAL_STR)

# --- Fixtures ---

@pytest.fixture
def conf(base_conf: ConfigParser) -> ConfigParser:
    """Provides a ConfigParser instance initialized with UUID test data."""
    conf_str = """
[%(DEFAULT)s]
# Option defined in DEFAULT section (standard format)
option_name = e3a57070-de0d-11e9-9b5b-5404a6a1fd6e
[%(PRESENT)s]
# Option present (hex format without dashes)
option_name = fbcdd0acde0d11e99b5b5404a6a1fd6e
[%(ABSENT)s]
# Section exists, but option is absent (will inherit from DEFAULT)
[%(BAD)s]
# Option present but with an invalid UUID string
option_name = BAD_UID-string-not-hex
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
    """Tests basic UUIDOption functionality: init, load, value access, clear, default handling."""
    opt = config.UUIDOption("option_name", "description")

    # Verify initial state
    assert opt.name == "option_name"
    assert opt.datatype == UUID
    assert opt.description == "description"
    assert not opt.required
    assert opt.default is None
    assert opt.value is None # Initial value without default is None
    opt.validate() # Should pass as not required

    # Load value from [present] section (hex format)
    opt.load_config(conf, PRESENT_S)
    assert opt.value == PRESENT_VAL
    assert opt.get_as_str() == PRESENT_VAL_STR_HEX # String representation is hex
    assert isinstance(opt.value, opt.datatype)
    # get_formatted uses standard hyphenated format
    assert opt.get_formatted() == "fbcdd0ac-de0d-11e9-9b5b-5404a6a1fd6e"

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
    assert opt.get_formatted() == DEFAULT_VAL_STR

    # Set value manually to None
    opt.set_value(None)
    assert opt.value is None

    # Load from section where option is absent (should inherit from DEFAULT)
    opt.load_config(conf, ABSENT_S)
    assert opt.value == DEFAULT_VAL
    assert isinstance(opt.value, opt.datatype)

    # Set value manually
    opt.set_value(NEW_VAL)
    assert opt.value == NEW_VAL
    assert isinstance(opt.value, opt.datatype)

def test_required(conf: ConfigParser):
    """Tests UUIDOption with the 'required' flag."""
    opt = config.UUIDOption("option_name", "description", required=True)

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
    """Tests loading invalid UUID string values."""
    opt = config.UUIDOption("option_name", "description")

    # Load from section with bad value
    with pytest.raises(ValueError, match="badly formed hexadecimal UUID string"):
        opt.load_config(conf, BAD_S)
    assert opt.value is None # Value should remain unchanged (None)

    # Load from section with empty value
    with pytest.raises(ValueError, match="badly formed hexadecimal UUID string"):
        opt.load_config(conf, EMPTY_S)
    assert opt.value is None

    # Test assigning invalid type via set_value
    with pytest.raises(TypeError, match="Option 'option_name' value must be a 'UUID', not 'float'"):
        opt.set_value(10.0) # type: ignore
    with pytest.raises(TypeError, match="Option 'option_name' value must be a 'UUID', not 'str'"):
        # Requires UUID object, not string
        opt.set_value("fbcdd0ac-de0d-11e9-9b5b-5404a6a1fd6e") # type: ignore

    # Test setting invalid string via set_as_str
    with pytest.raises(ValueError, match="badly formed hexadecimal UUID string"):
        opt.set_as_str("not-a-uuid")


def test_default(conf: ConfigParser):
    """Tests UUIDOption with a defined default UUID value."""
    opt = config.UUIDOption("option_name", "description", default=DEFAULT_OPT_VAL)

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
    opt = config.UUIDOption("option_name", "description", default=DEFAULT_OPT_VAL)
    proto_value = UUID("bcd80916-de0e-11e9-9b5b-5404a6a1fd6e")
    proto_value_bytes = proto_value.bytes
    proto_value_hex = proto_value.hex

    # Set value and serialize (saves as bytes)
    opt.set_value(proto_value)
    opt.save_proto(proto)
    assert "option_name" in proto.options
    assert proto.options["option_name"].HasField('as_bytes')
    assert proto.options["option_name"].as_bytes == proto_value_bytes
    proto_dump = proto.SerializeToString() # Save serialized state

    # Clear option and deserialize from bytes
    opt.clear(to_default=False)
    assert opt.value is None
    proto_read = ConfigProto()
    proto_read.ParseFromString(proto_dump)
    opt.load_proto(proto_read)
    assert opt.value == proto_value
    assert isinstance(opt.value, opt.datatype)

    # Test deserializing from string representation in proto
    proto.Clear()
    proto.options["option_name"].as_string = proto_value_hex # Use hex string
    opt.load_proto(proto)
    assert opt.value == proto_value

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
    proto.options["option_name"].as_uint32 = 1000 # Invalid type for UUIDOption
    with pytest.raises(TypeError, match="Wrong value type: uint32"):
        opt.load_proto(proto)

    # Test loading bad proto value (invalid string for UUID)
    proto.Clear()
    proto.options["option_name"].as_string = "not-a-uuid"
    with pytest.raises(ValueError, match="badly formed hexadecimal UUID string"):
        opt.load_proto(proto)

    # Test loading bad proto value (invalid bytes length for UUID)
    proto.Clear()
    proto.options["option_name"].as_bytes = b'\x01\x02\x03' # Too short
    with pytest.raises(ValueError, match="bytes is not a 16-char string"):
        opt.load_proto(proto)


def test_get_config(conf: ConfigParser):
    """Tests the get_config method for generating config file string representation."""
    opt = config.UUIDOption("option_name", "description", default=DEFAULT_OPT_VAL)

    # Test output with default value (should be commented out, standard format)
    expected_lines_default = f"""; description
; Type: UUID
;option_name = {DEFAULT_OPT_VAL_STR}
"""
    assert opt.get_config() == expected_lines_default

    # Test output with explicitly set value
    opt.set_value(NEW_VAL)
    expected_lines_new = f"""; description
; Type: UUID
option_name = {NEW_VAL_STR}
"""
    assert opt.get_config() == expected_lines_new

    # Test output when value is None (should show <UNDEFINED>)
    opt.set_value(None)
    expected_lines_none = """; description
; Type: UUID
option_name = <UNDEFINED>
"""
    assert opt.get_config() == expected_lines_none
    # Check get_formatted directly for None case
    assert opt.get_formatted() == "<UNDEFINED>"

    # Test plain output
    opt.set_value(NEW_VAL)
    assert opt.get_config(plain=True) == f"option_name = {NEW_VAL_STR}\n"
    opt.set_value(None)
    assert opt.get_config(plain=True) == "option_name = <UNDEFINED>\n"
