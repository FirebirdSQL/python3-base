# SPDX-FileCopyrightText: 2019-present The Firebird Projects <www.firebirdsql.org>
#
# SPDX-License-Identifier: MIT
#
# PROGRAM/MODULE: firebird-base
# FILE:           tests/config/test_cfg_dcls.py
# DESCRIPTION:    Tests for firebird.base.config DataclassOption
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

"""Unit tests for the DataclassOption configuration option class."""

from __future__ import annotations

from dataclasses import dataclass, field # Added field for testing defaults
from enum import IntEnum
from typing import Optional # For testing complex type hints

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
PARTIAL_S = "partial"
BAD_FIELD_NAME_S = "bad_field_name"
BAD_FIELD_VALUE_S = "bad_field_value"

# --- Test Helper Classes ---

class SimpleEnum(IntEnum):
    """Enum used within the test dataclass."""
    UNKNOWN    = 0
    READY      = 1
    RUNNING    = 2
    # ... (other members as needed) ...

@dataclass
class SimpleDataclass:
    """Dataclass used for testing DataclassOption."""
    name: str # Required field
    priority: int = 1 # Field with default
    state: SimpleEnum = SimpleEnum.READY # Field with enum default

@dataclass
class ComplexHintDataclass:
    """Dataclass with more complex type hints for testing 'fields' override."""
    label: str
    count: Optional[int] = None
    status: SimpleEnum = SimpleEnum.UNKNOWN

# --- Constants for Test Values ---
DEFAULT_VAL = SimpleDataclass("main") # name required, others default
PRESENT_VAL = SimpleDataclass("master", 3, SimpleEnum.RUNNING)
DEFAULT_OPT_VAL = SimpleDataclass("default_obj", 5) # Uses default state=READY
NEW_VAL = SimpleDataclass("master", 99, SimpleEnum.UNKNOWN)

# --- Fixtures ---

@pytest.fixture
def conf(base_conf: ConfigParser) -> ConfigParser:
    """Provides a ConfigParser instance initialized with dataclass test data."""
    conf_str = """
[%(DEFAULT)s]
# Defines a default object using only the required field
option_name = name:main
[%(PRESENT)s]
# Defines a complete object, multiline format
option_name =
   name:master
   priority:3
   state:RUNNING
[%(ABSENT)s]
# Section exists, but option is absent (will inherit from DEFAULT)
[%(BAD)s]
# Invalid format - missing colon
option_name = bad_value
[%(PARTIAL)s]
# Only defines one field, relies on defaults for others
option_name = name:partial_obj
[%(BAD_FIELD_NAME)s]
# Includes a field name not present in the dataclass
option_name = name:badfield, non_existent_field:abc
[%(BAD_FIELD_VALUE)s]
# Includes a value that cannot be converted to the field's type
option_name = name:badvalue, priority:not_an_int
[%(EMPTY)s]
# Option present but empty
option_name =
"""
    # Format the string with section names and read into the config parser
    base_conf.read_string(conf_str % {"DEFAULT": DEFAULT_S, "PRESENT": PRESENT_S,
                                      "ABSENT": ABSENT_S, "BAD": BAD_S, "EMPTY": EMPTY_S,
                                      "PARTIAL": PARTIAL_S,
                                      "BAD_FIELD_NAME": BAD_FIELD_NAME_S,
                                      "BAD_FIELD_VALUE": BAD_FIELD_VALUE_S})
    return base_conf

# --- Test Cases ---

def test_simple(conf: ConfigParser):
    """Tests basic DataclassOption: init, load, value access, clear, default handling."""
    opt = config.DataclassOption("option_name", SimpleDataclass, "description")

    # Verify initial state
    assert opt.name == "option_name"
    assert opt.datatype == SimpleDataclass
    assert opt.description == "description"
    assert not opt.required
    assert opt.default is None
    assert opt.value is None # Initial value without default is None
    opt.validate() # Should pass as not required

    # Load value from [present] section (multiline format)
    opt.load_config(conf, PRESENT_S)
    assert opt.value == PRESENT_VAL
    # Test get_as_str (uses comma separator by default if value short enough)
    assert opt.get_as_str() == "name:master,priority:3,state:RUNNING"
    assert isinstance(opt.value, opt.datatype)
    assert opt.get_formatted() == "name:master, priority:3, state:RUNNING" # Config file format (adds space)

    # Clear value (should reset to None as no default)
    opt.clear(to_default=False)
    assert opt.value is None

    # Clear value to default (should still be None)
    opt.clear(to_default=True)
    assert opt.value is None

    # Load value from [DEFAULT] section
    opt.load_config(conf, DEFAULT_S)
    assert opt.value == DEFAULT_VAL # name=main, priority=1, state=READY
    assert isinstance(opt.value, opt.datatype)
    assert opt.get_formatted() == "name:main, priority:1, state:READY"

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

    # Load partial definition (should use dataclass defaults)
    opt.load_config(conf, PARTIAL_S)
    expected_partial = SimpleDataclass("partial_obj") # Uses defaults for priority/state
    assert opt.value == expected_partial
    assert opt.get_formatted() == "name:partial_obj, priority:1, state:READY"

def test_required(conf: ConfigParser):
    """Tests DataclassOption with the 'required' flag."""
    opt = config.DataclassOption("option_name", SimpleDataclass, "description", required=True)

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
    """Tests loading invalid string values or invalid types."""
    opt = config.DataclassOption("option_name", SimpleDataclass, "description")

    # Load from section with bad format (missing colon)
    with pytest.raises(ValueError, match="Illegal value 'bad_value' for option 'option_name'"):
        opt.load_config(conf, BAD_S)
    assert opt.value is None # Value should remain unchanged (None)

    # Load from section with unknown field name
    with pytest.raises(ValueError, match="Unknown data field 'non_existent_field'"):
        opt.load_config(conf, BAD_FIELD_NAME_S)
    assert opt.value is None

    # Load from section with bad field value (cannot convert)
    with pytest.raises(ValueError) as excinfo: # Check underlying error
        opt.load_config(conf, BAD_FIELD_VALUE_S)
    assert isinstance(excinfo.value, ValueError) # Check conversion error
    assert "invalid literal for int()" in str(excinfo.value)
    assert opt.value is None

    # Test assigning invalid type via set_value
    with pytest.raises(TypeError, match="Option 'option_name' value must be a 'SimpleDataclass', not 'float'"):
        opt.set_value(10.0) # type: ignore

    # Test setting invalid string via set_as_str
    with pytest.raises(ValueError, match="Illegal value 'invalid-format' for option 'option_name'"):
        opt.set_as_str("invalid-format")

    with pytest.raises(ValueError, match="Unknown data field 'badfield'"):
        opt.set_as_str("badfield:value")

    with pytest.raises(ValueError) as excinfo:
        opt.set_as_str("name:test, priority:invalid")
    assert isinstance(excinfo.value, ValueError)
    assert "invalid literal for int()" in str(excinfo.value)


def test_default(conf: ConfigParser):
    """Tests DataclassOption with a defined default value."""
    opt = config.DataclassOption("option_name", SimpleDataclass, "description", default=DEFAULT_OPT_VAL)

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
    opt = config.DataclassOption("option_name", SimpleDataclass, "description", default=DEFAULT_OPT_VAL)
    proto_value = SimpleDataclass("backup", 2, SimpleEnum.UNKNOWN)
    proto_value_str = "name:backup,priority:2,state:UNKNOWN" # Expected string format

    # Set value and serialize
    opt.set_value(proto_value)
    opt.save_proto(proto)
    assert "option_name" in proto.options
    assert proto.options["option_name"].HasField('as_string')
    # Serialized string might use different separator based on length, reconstruct for check
    assert proto.options["option_name"].as_string == opt.get_as_str()
    proto_dump = proto.SerializeToString() # Save serialized state

    # Clear option and deserialize
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
    proto.options["option_name"].as_uint64 = 1 # Invalid type for DataclassOption
    with pytest.raises(TypeError, match="Wrong value type: uint64"):
        opt.load_proto(proto)

    # Test loading bad proto value (invalid string format)
    proto.Clear()
    proto.options["option_name"].as_string = "name:bad, priority:invalid_int"
    with pytest.raises(ValueError) as excinfo:
        opt.load_proto(proto)
    assert isinstance(excinfo.value, ValueError)
    assert "invalid literal for int()" in str(excinfo.value)


def test_get_config(conf: ConfigParser):
    """Tests the get_config method for generating config file string representation."""
    opt = config.DataclassOption("option_name", SimpleDataclass, "description", default=DEFAULT_OPT_VAL)

    # Test output with default value (should be commented out)
    expected_lines_default = """; description
; Type: list of values, where each list item defines value for a dataclass field.
; Item format: field_name:value_as_str
;option_name = name:default_obj, priority:5, state:READY
"""
    assert opt.get_config() == expected_lines_default

    # Test output with explicitly set value
    opt.set_value(NEW_VAL) # name=master, priority=99, state=UNKNOWN
    expected_lines_new = """; description
; Type: list of values, where each list item defines value for a dataclass field.
; Item format: field_name:value_as_str
option_name = name:master, priority:99, state:UNKNOWN
"""
    assert opt.get_config() == expected_lines_new

    # Test output when value is None (should show <UNDEFINED>)
    opt.set_value(None)
    expected_lines_none = """; description
; Type: list of values, where each list item defines value for a dataclass field.
; Item format: field_name:value_as_str
option_name = <UNDEFINED>
"""
    assert opt.get_config() == expected_lines_none
    # Check get_formatted directly for None case
    assert opt.get_formatted() == "<UNDEFINED>"

    # Test multiline formatting for long values
    long_name = "a_very_long_dataclass_instance_name_that_should_cause_wrapping"
    long_val = SimpleDataclass(long_name, 123456789, SimpleEnum.UNKNOWN)
    opt.set_value(long_val)
    expected_lines_long = f"""; description
; Type: list of values, where each list item defines value for a dataclass field.
; Item format: field_name:value_as_str
option_name =
   name:{long_name}
   priority:123456789
   state:UNKNOWN
""".replace("option_name =", "option_name = ") # Necessary due to editor trailing white cleanup
    assert opt.get_config() == expected_lines_long

    # Test plain output
    opt.set_value(NEW_VAL)
    assert opt.get_config(plain=True) == "option_name = name:master, priority:99, state:UNKNOWN\n"
    opt.set_value(None)
    assert opt.get_config(plain=True) == "option_name = <UNDEFINED>\n"


def test_fields_override():
    """Tests using the 'fields' parameter to override type hints."""
    # Dataclass has Optional[int], but we want to treat it just as 'int' for config
    opt = config.DataclassOption(
        "complex_option",
        ComplexHintDataclass,
        "description",
        fields={'label': str, 'count': int, 'status': SimpleEnum} # Override 'count'
    )

    # Test setting string value that needs conversion based on overridden type
    opt.set_as_str("label:Test, count:123, status:RUNNING")
    assert opt.value == ComplexHintDataclass("Test", 123, SimpleEnum.RUNNING)
    assert isinstance(opt.value.count, int) # Should be int, not Optional[int] internally

    # Test get_config reflects the actual value's type
    assert opt.get_config() == """; description
; Type: list of values, where each list item defines value for a dataclass field.
; Item format: field_name:value_as_str
complex_option = label:Test, count:123, status:RUNNING
"""

    # Test case where config string is missing an optional field defined in 'fields'
    # The dataclass __init__ should handle the default if the field is omitted
    opt.set_as_str("label:OnlyLabel")
    assert opt.value == ComplexHintDataclass("OnlyLabel", None, SimpleEnum.UNKNOWN) # Dataclass defaults used

    # Test case where config provides 'None' or empty for the overridden optional field
    # This depends on how the base type's str->value convertor handles None/empty
    # For int, it would likely raise an error.
    with pytest.raises(ValueError) as excinfo:
        opt.set_as_str("label:LabelNone, count:") # Empty string for int
    assert isinstance(excinfo.value, ValueError)

    # Test error if 'fields' dict doesn't cover all dataclass fields (unlikely use case)
    # Or if 'fields' dict refers to a field not in the dataclass
    with pytest.raises(ValueError, match="Unknown data field 'non_field'"):
        opt.set_as_str("label:X, non_field:Y")
