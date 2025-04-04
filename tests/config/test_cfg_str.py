# SPDX-FileCopyrightText: 2025-present The Firebird Projects <www.firebirdsql.org>
#
# SPDX-License-Identifier: MIT
#
# PROGRAM/MODULE: firebird-base
# FILE:           tests/config/test_cfg_str.py
# DESCRIPTION:    Tests for firebird.base.config StrOption
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

"""Unit tests for the StrOption configuration option class."""

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
BAD_S = "bad_value" # Not applicable for StrOption, use EMPTY
EMPTY_S = "empty"
VERTICALS_S = "VERTICALS" # Section with vertical bar indentation

# --- Constants for Test Values ---
PRESENT_VAL_STR = "present_value\ncan be multiline" # Loaded from multiline config
PRESENT_VAL = PRESENT_VAL_STR # For StrOption, loaded value is the string
DEFAULT_VAL = "DEFAULT_value"
DEFAULT_OPT_VAL = "DEFAULT_OPTION_VALUE" # Default for the option itself
NEW_VAL = "new_value"
VERTICALS_VAL_STR = '\ndef pp(value):\n    print("Value:",value,file=output)\n\nfor i in [1,2,3]:\n    pp(i)' # Code intended for PyCode test, used here to test verticals
VERTICALS_VAL = VERTICALS_VAL_STR # StrOption just stores the string after unindenting

# --- Fixtures ---

@pytest.fixture
def conf(base_conf: ConfigParser) -> ConfigParser:
    """Provides a ConfigParser instance initialized with string test data."""
    conf_str = """
[%(DEFAULT)s]
# Option defined in DEFAULT section
option_name = DEFAULT_value
[%(PRESENT)s]
# Option present in its own section (multiline)
option_name = present_value
   can be multiline
[%(ABSENT)s]
# Section exists, but option is absent (will inherit from DEFAULT)
[%(BAD)s]
# Not applicable, use EMPTY
[%(EMPTY)s]
# Option present but empty
option_name =
[%(VERTICALS)s]
# Option with vertical bars for preserving leading whitespace
option_name =
    | def pp(value):
    |     print("Value:",value,file=output)
    |
    | for i in [1,2,3]:
    |     pp(i)
"""
    # Format the string with section names and read into the config parser
    base_conf.read_string(conf_str % {"DEFAULT": DEFAULT_S, "PRESENT": PRESENT_S,
                                      "ABSENT": ABSENT_S, "BAD": BAD_S, "EMPTY": EMPTY_S,
                                      "VERTICALS": VERTICALS_S})
    return base_conf

# --- Test Cases ---

def test_simple(conf: ConfigParser):
    """Tests basic StrOption functionality: init, load, value access, clear, default handling."""
    opt = config.StrOption("option_name", "description")

    # Verify initial state
    assert opt.name == "option_name"
    assert opt.datatype == str
    assert opt.description == "description"
    assert not opt.required
    assert opt.default is None
    assert opt.value is None # Initial value without default is None
    opt.validate() # Should pass as not required

    # Load value from [present] section (multiline)
    opt.load_config(conf, PRESENT_S)
    assert opt.value == PRESENT_VAL
    assert opt.get_as_str() == PRESENT_VAL_STR # String representation
    assert isinstance(opt.value, opt.datatype)
    # get_formatted adds indentation for multiline output
    assert opt.get_formatted() == "present_value\n   can be multiline"

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
    assert opt.get_formatted() == DEFAULT_VAL # Single line format

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

    # Test loading value with vertical bars (should unindent)
    opt.load_config(conf, VERTICALS_S)
    assert opt.value == VERTICALS_VAL
    assert opt.get_as_str() == VERTICALS_VAL_STR
    # Check formatted output adds vertical bars back if needed (due to leading space)
    assert opt.get_formatted().strip().startswith("| def pp(value):")

def test_required(conf: ConfigParser):
    """Tests StrOption with the 'required' flag."""
    opt = config.StrOption("option_name", "description", required=True)

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

    # Set value to empty string (should pass validation even if required)
    opt.set_value("")
    assert opt.value == ""
    opt.validate() # Empty string is considered a value

def test_bad_value(conf: ConfigParser):
    """Tests loading edge cases like empty values."""
    opt = config.StrOption("option_name", "description")

    # Load from section with empty value
    opt.load_config(conf, EMPTY_S)
    assert opt.value == "" # Empty value in config results in empty string
    assert opt.value is not None

    # Test assigning invalid type via set_value
    with pytest.raises(TypeError, match="Option 'option_name' value must be a 'str', not 'float'"):
        opt.set_value(10.0) # type: ignore
    with pytest.raises(TypeError, match="Option 'option_name' value must be a 'str', not 'int'"):
        opt.set_value(123) # type: ignore


def test_default(conf: ConfigParser):
    """Tests StrOption with a defined default string value."""
    opt = config.StrOption("option_name", "description", default=DEFAULT_OPT_VAL)

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
    opt = config.StrOption("option_name", "description", default=DEFAULT_OPT_VAL)
    proto_value = "value from proto test"

    # Set value and serialize (saves as string)
    opt.set_value(proto_value)
    opt.save_proto(proto)
    assert "option_name" in proto.options
    assert proto.options["option_name"].HasField('as_string')
    assert proto.options["option_name"].as_string == proto_value
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
    proto.options["option_name"].as_uint64 = 1000 # Invalid type for StrOption
    with pytest.raises(TypeError, match="Wrong value type: uint64"):
        opt.load_proto(proto)


def test_get_config(conf: ConfigParser):
    """Tests the get_config method for generating config file string representation."""
    opt = config.StrOption("option_name", "description", default=DEFAULT_OPT_VAL)

    # Test output with default value (should be commented out)
    expected_lines_default = f"""; description
; Type: str
;option_name = {DEFAULT_OPT_VAL}
"""
    assert opt.get_config() == expected_lines_default

    # Test output with explicitly set single-line value
    opt.set_value(NEW_VAL)
    expected_lines_new = f"""; description
; Type: str
option_name = {NEW_VAL}
"""
    assert opt.get_config() == expected_lines_new

    # Test output with explicitly set multi-line value (no leading spaces)
    opt.set_value(PRESENT_VAL)
    expected_lines_multi = """; description
; Type: str
option_name = present_value
   can be multiline
"""
    assert opt.get_config() == expected_lines_multi

    # Test output with multi-line value needing vertical bars
    opt.set_value(VERTICALS_VAL)
    expected_lines_verticals = """; description
; Type: str
option_name =
   | def pp(value):
   |     print("Value:",value,file=output)
   |
   | for i in [1,2,3]:
   |     pp(i)"""
    # Compare stripped lines due to potential trailing whitespace differences
    assert "\n".join(x.rstrip() for x in opt.get_config().splitlines()) == expected_lines_verticals


    # Test output when value is None (should show <UNDEFINED>)
    opt.set_value(None)
    expected_lines_none = """; description
; Type: str
option_name = <UNDEFINED>
"""
    assert opt.get_config() == expected_lines_none
    # Check get_formatted directly for None case
    assert opt.get_formatted() == "<UNDEFINED>"

    # Test plain output
    opt.set_value(NEW_VAL)
    assert opt.get_config(plain=True) == f"option_name = {NEW_VAL}\n"
    # Plain output for multiline shouldn't have leading indent on first line
    opt.set_value(PRESENT_VAL)
    expected_plain_multi = """option_name = present_value
   can be multiline
"""
    assert opt.get_config(plain=True) == expected_plain_multi
    opt.set_value(None)
    assert opt.get_config(plain=True) == "option_name = <UNDEFINED>\n"
