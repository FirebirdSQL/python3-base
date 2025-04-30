# SPDX-FileCopyrightText: 2025-present The Firebird Projects <www.firebirdsql.org>
#
# SPDX-License-Identifier: MIT
#
# PROGRAM/MODULE: firebird-base
# FILE:           tests/config/test_cfg_list.py
# DESCRIPTION:    Tests for firebird.base.config ListOption
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

"""Unit tests for the ListOption configuration option class."""

from __future__ import annotations

from decimal import Decimal
from enum import IntEnum
from uuid import UUID
import pytest
from configparser import ConfigParser # Import for type hinting
from collections.abc import Sequence

from firebird.base import config
from firebird.base.config_pb2 import ConfigProto # Import for proto tests
from firebird.base.strconv import convert_to_str, register_class # For multi-type test setup
from firebird.base.types import MIME, Error, ZMQAddress # For multi-type test setup

# --- Constants for Test Sections ---
DEFAULT_S = "DEFAULT"
PRESENT_S = "present"
ABSENT_S = "absent"
BAD_S = "bad_value"
EMPTY_S = "empty"

# --- Test Helper Classes ---

class SimpleEnum(IntEnum):
    """Enum used for testing within lists."""
    UNKNOWN    = 0
    READY      = 1
    RUNNING    = 2

class ParamBase:
    """Base class for test parameter sets."""
    # Values used in tests
    DEFAULT_VAL = []
    PRESENT_VAL = []
    DEFAULT_OPT_VAL = []
    NEW_VAL = []
    PROTO_VALUE = []
    LONG_VAL = [] # For testing multiline formatting

    # String representations expected/used
    DEFAULT_PRINT = "" # How DEFAULT_OPT_VAL prints in get_config comment
    PRESENT_AS_STR = "" # How PRESENT_VAL serializes to string
    NEW_PRINT = "" # How NEW_VAL prints in get_config non-commented
    PROTO_VALUE_STR = "" # How PROTO_VALUE serializes to string for proto

    # Config option parameters
    ITEM_TYPE: type | tuple[type, ...] = None # type: ignore
    TYPE_NAMES: str = "" # Generated string like "int, str"
    SEPARATOR: str | None = None # Separator override for ListOption

    # Expected error message for bad conversion from config string
    BAD_MSG: tuple | None = None

    # Raw config string template for this type
    conf_str: str = ""

    # Derived value used in tests
    LONG_PRINT: str = "" # Generated multiline string from LONG_VAL

    def __init__(self):
        """Initializes derived values after subclass defines bases."""
        self.conf: ConfigParser = None
        self.prepare() # Allow subclasses to modify values before generating strings
        # Generate TYPE_NAMES string
        type_tuple = (self.ITEM_TYPE, ) if isinstance(self.ITEM_TYPE, type) else self.ITEM_TYPE
        self.TYPE_NAMES = ", ".join(t.__name__ for t in type_tuple)
        # Generate LONG_PRINT (multiline format)
        x = "\n   "
        self.LONG_PRINT = f"\n   {x.join(self._format_item(item) for item in self.LONG_VAL)}"

    def prepare(self):
        """Placeholder for subclass modifications before string generation."""
        pass

    def _format_item(self, item) -> str:
        """Helper to format list items, handling multi-type."""
        result = convert_to_str(item)
        if not isinstance(self.ITEM_TYPE, type): # Multi-type case
            result = f"{item.__class__.__name__}:{result}"
        return result

# --- Parameter Sets for Different List Item Types ---

class StrParams(ParamBase):
    """Parameters for ListOption[str]."""
    DEFAULT_VAL = ["DEFAULT_value"]
    PRESENT_VAL = ["present_value_1", "present_value_2"]
    DEFAULT_OPT_VAL = ["DEFAULT_1", "DEFAULT_2", "DEFAULT_3"]
    NEW_VAL = ["NEW"]
    PROTO_VALUE = ["proto_value_1", "proto_value_2"]
    LONG_VAL = ["long" * 3, "verylong" * 3, "veryverylong" * 5]

    DEFAULT_PRINT = "DEFAULT_1, DEFAULT_2, DEFAULT_3"
    PRESENT_AS_STR = "present_value_1,present_value_2" # Loaded multiline
    NEW_PRINT = "NEW"
    PROTO_VALUE_STR = "proto_value_1,proto_value_2" # Default comma for short proto

    ITEM_TYPE = str
    BAD_MSG = None # No conversion error expected for string

    conf_str = """
[%(DEFAULT)s]
[%(PRESENT)s]
option_name =
  present_value_1
  present_value_2
[%(ABSENT)s]
[%(BAD)s]
# Bad value test not applicable for str, use EMPTY instead
[%(EMPTY)s]
option_name =
"""

class IntParams(ParamBase):
    """Parameters for ListOption[int]."""
    DEFAULT_VAL = [0]
    PRESENT_VAL = [10, 20]
    DEFAULT_OPT_VAL = [1, 2, 3]
    NEW_VAL = [100]
    PROTO_VALUE = [30, 40, 50]
    LONG_VAL = [x for x in range(50)]

    DEFAULT_PRINT = "1, 2, 3"
    PRESENT_AS_STR = "10,20" # Loaded comma-separated
    NEW_PRINT = "100"
    PROTO_VALUE_STR = "30,40,50"

    ITEM_TYPE = int
    BAD_MSG = ("invalid literal for int() with base 10: 'invalid'",)

    conf_str = """
[%(DEFAULT)s]
option_name = 0
[%(PRESENT)s]
option_name = 10, 20
[%(ABSENT)s]
[%(BAD)s]
option_name = invalid
[%(EMPTY)s]
option_name =
"""

class FloatParams(ParamBase):
    """Parameters for ListOption[float]."""
    DEFAULT_VAL = [0.0]
    PRESENT_VAL = [10.1, 20.2]
    DEFAULT_OPT_VAL = [1.11, 2.22, 3.33]
    NEW_VAL = [100.101]
    PROTO_VALUE = [30.3, 40.4, 50.5]
    LONG_VAL = [x / 1.5 for x in range(50)]

    DEFAULT_PRINT = "1.11, 2.22, 3.33"
    PRESENT_AS_STR = "10.1,20.2"
    NEW_PRINT = "100.101"
    PROTO_VALUE_STR = "30.3,40.4,50.5"

    ITEM_TYPE = float
    BAD_MSG = ("could not convert string to float: 'invalid'",)

    conf_str = """
[%(DEFAULT)s]
option_name = 0.0
[%(PRESENT)s]
option_name = 10.1, 20.2
[%(ABSENT)s]
[%(BAD)s]
option_name = invalid
[%(EMPTY)s]
option_name =
"""

class DecimalParams(ParamBase):
    """Parameters for ListOption[Decimal]."""
    DEFAULT_VAL = [Decimal("0.0")]
    PRESENT_VAL = [Decimal("10.1"), Decimal("20.2")]
    DEFAULT_OPT_VAL = [Decimal("1.11"), Decimal("2.22"), Decimal("3.33")]
    NEW_VAL = [Decimal("100.101")]
    PROTO_VALUE = [Decimal("30.3"), Decimal("40.4"), Decimal("50.5")]
    LONG_VAL = [Decimal(str(x / 1.5)) for x in range(50)]

    DEFAULT_PRINT = "1.11, 2.22, 3.33"
    PRESENT_AS_STR = "10.1,20.2"
    NEW_PRINT = "100.101"
    PROTO_VALUE_STR = "30.3,40.4,50.5"

    ITEM_TYPE = Decimal
    BAD_MSG = ("could not convert string to Decimal: 'invalid'",)

    conf_str = """
[%(DEFAULT)s]
option_name = 0.0
[%(PRESENT)s]
option_name = 10.1, 20.2
[%(ABSENT)s]
[%(BAD)s]
option_name = invalid
[%(EMPTY)s]
option_name =
"""

class BoolParams(ParamBase):
    """Parameters for ListOption[bool]."""
    DEFAULT_VAL = [False] # From "0"
    PRESENT_VAL = [True, False]
    DEFAULT_OPT_VAL = [True, False, True]
    NEW_VAL = [True]
    PROTO_VALUE = [False, True, False]
    LONG_VAL = [bool(x % 2) for x in range(40)] # Alternating True/False

    DEFAULT_PRINT = "yes, no, yes"
    PRESENT_AS_STR = "yes,no"
    NEW_PRINT = "yes"
    PROTO_VALUE_STR = "no,yes,no"

    ITEM_TYPE = bool
    BAD_MSG = ("Value is not a valid bool string constant",)

    conf_str = """
[%(DEFAULT)s]
option_name = 0
[%(PRESENT)s]
option_name = yes, no
[%(ABSENT)s]
[%(BAD)s]
option_name = this is not a bool
[%(EMPTY)s]
option_name =
"""

class UUIDParams(ParamBase):
    """Parameters for ListOption[UUID]."""
    DEFAULT_VAL = [UUID("eeb7f94a-256d-11ea-ad1d-5404a6a1fd6e")]
    PRESENT_VAL = [UUID("0a7fd53a-256e-11ea-ad1d-5404a6a1fd6e"),
                   UUID("0551feb2-256e-11ea-ad1d-5404a6a1fd6e")]
    DEFAULT_OPT_VAL = [UUID("2f02868c-256e-11ea-ad1d-5404a6a1fd6e"),
                       UUID("3521db30-256e-11ea-ad1d-5404a6a1fd6e"),
                       UUID("3a3e68cc-256e-11ea-ad1d-5404a6a1fd6e")]
    NEW_VAL = [UUID("3e8a4ce8-256e-11ea-ad1d-5404a6a1fd6e")]
    PROTO_VALUE = [UUID("3a3e68cc-256e-11ea-ad1d-5404a6a1fd6e"), UUID("3521db30-256e-11ea-ad1d-5404a6a1fd6e")]
    LONG_VAL = [UUID("2f02868c-256e-11ea-ad1d-5404a6a1fd6e") for x in range(10)]

    DEFAULT_PRINT = "\n;   2f02868c-256e-11ea-ad1d-5404a6a1fd6e\n;   3521db30-256e-11ea-ad1d-5404a6a1fd6e\n;   3a3e68cc-256e-11ea-ad1d-5404a6a1fd6e" # Multiline default
    PRESENT_AS_STR = "0a7fd53a-256e-11ea-ad1d-5404a6a1fd6e,0551feb2-256e-11ea-ad1d-5404a6a1fd6e"
    NEW_PRINT = "3e8a4ce8-256e-11ea-ad1d-5404a6a1fd6e"
    PROTO_VALUE_STR = "3a3e68cc-256e-11ea-ad1d-5404a6a1fd6e,3521db30-256e-11ea-ad1d-5404a6a1fd6e"

    ITEM_TYPE = UUID
    BAD_MSG = ("badly formed hexadecimal UUID string",)

    conf_str = """
[%(DEFAULT)s]
option_name = eeb7f94a-256d-11ea-ad1d-5404a6a1fd6e
[%(PRESENT)s]
# Mixed formats allowed by UUID constructor
option_name = 0a7fd53a256e11eaad1d5404a6a1fd6e, 0551feb2-256e-11ea-ad1d-5404a6a1fd6e
[%(ABSENT)s]
[%(BAD)s]
option_name = this is not an uuid
[%(EMPTY)s]
option_name =
"""

class MIMEParams(ParamBase):
    """Parameters for ListOption[MIME]."""
    DEFAULT_VAL = [MIME("application/octet-stream")]
    PRESENT_VAL = [MIME("text/plain;charset=utf-8"), MIME("text/csv")]
    DEFAULT_OPT_VAL = [MIME("text/html;charset=utf-8"), MIME("video/mp4"), MIME("image/png")]
    NEW_VAL = [MIME("audio/mpeg")]
    PROTO_VALUE = [MIME("application/octet-stream"), MIME("video/mp4")]
    LONG_VAL = [MIME("text/html;charset=win1250") for x in range(10)]

    DEFAULT_PRINT = "text/html;charset=utf-8, video/mp4, image/png"
    PRESENT_AS_STR = "text/plain;charset=utf-8,text/csv" # Loaded multiline
    NEW_PRINT = "audio/mpeg"
    PROTO_VALUE_STR = "application/octet-stream,video/mp4"

    ITEM_TYPE = MIME
    BAD_MSG = ("MIME type specification must be 'type/subtype[;param=value;...]'",)

    conf_str = """
[%(DEFAULT)s]
option_name = application/octet-stream
[%(PRESENT)s]
option_name =
    text/plain;charset=utf-8
    text/csv
[%(ABSENT)s]
[%(BAD)s]
option_name = wrong mime specification
[%(EMPTY)s]
option_name =
"""

class ZMQAddressParams(ParamBase):
    """Parameters for ListOption[ZMQAddress]."""
    DEFAULT_VAL = [ZMQAddress("tcp://127.0.0.1:*")]
    PRESENT_VAL = [ZMQAddress("ipc://@my-address"), ZMQAddress("inproc://my-address"), ZMQAddress("tcp://127.0.0.1:9001")]
    DEFAULT_OPT_VAL = [ZMQAddress("tcp://127.0.0.1:8001")]
    NEW_VAL = [ZMQAddress("inproc://my-address")]
    PROTO_VALUE = [ZMQAddress("tcp://www.firebirdsql.org:8001"), ZMQAddress("tcp://www.firebirdsql.org:9001")]
    LONG_VAL = [ZMQAddress("tcp://www.firebirdsql.org:500") for x in range(10)]

    DEFAULT_PRINT = "tcp://127.0.0.1:8001"
    PRESENT_AS_STR = "ipc://@my-address,inproc://my-address,tcp://127.0.0.1:9001"
    NEW_PRINT = "inproc://my-address"
    PROTO_VALUE_STR = "tcp://www.firebirdsql.org:8001,tcp://www.firebirdsql.org:9001"

    ITEM_TYPE = ZMQAddress
    BAD_MSG = ("Protocol specification required",)

    conf_str = """
[%(DEFAULT)s]
option_name = tcp://127.0.0.1:*
[%(PRESENT)s]
option_name = ipc://@my-address, inproc://my-address, tcp://127.0.0.1:9001
[%(ABSENT)s]
[%(BAD)s]
option_name = bad_value
[%(EMPTY)s]
option_name =
"""

class MultiTypeParams(ParamBase):
    """Parameters for ListOption with multiple item types."""
    DEFAULT_VAL = ["DEFAULT_value"] # From str:DEFAULT_value
    PRESENT_VAL = [1, 1.1, Decimal("1.01"), True,
                   UUID("eeb7f94a-256d-11ea-ad1d-5404a6a1fd6e"),
                   MIME("application/octet-stream"),
                   ZMQAddress("tcp://127.0.0.1:*"),
                   SimpleEnum.RUNNING]
    DEFAULT_OPT_VAL = ["DEFAULT_1", 1, False]
    NEW_VAL = [MIME("text/plain;charset=utf-8")]
    PROTO_VALUE = [UUID("2f02868c-256e-11ea-ad1d-5404a6a1fd6e"), MIME("application/octet-stream")]
    LONG_VAL = [ZMQAddress("tcp://www.firebirdsql.org:500"),
                UUID("2f02868c-256e-11ea-ad1d-5404a6a1fd6e"),
                MIME("application/octet-stream"),
                "=" * 30, 1, True, 10.1, Decimal("20.20")]

    DEFAULT_PRINT = "str:DEFAULT_1, int:1, bool:no" # Needs type prefix
    # Config is multiline, so default separator is newline for get_as_str
    PRESENT_AS_STR = "int:1\nfloat:1.1\nDecimal:1.01\nbool:yes\nUUID:eeb7f94a-256d-11ea-ad1d-5404a6a1fd6e\nMIME:application/octet-stream\nZMQAddress:tcp://127.0.0.1:*\nSimpleEnum:RUNNING"
    NEW_PRINT = "MIME:text/plain;charset=utf-8" # Needs type prefix
    PROTO_VALUE_STR = "UUID:2f02868c-256e-11ea-ad1d-5404a6a1fd6e,MIME:application/octet-stream"

    ITEM_TYPE = (str, int, float, Decimal, bool, UUID, MIME, ZMQAddress, SimpleEnum)
    # Register classes used in multi-type list if not built-in or already registered
    register_class(SimpleEnum)

    BAD_MSG = ("Item type 'bin' not supported",) # From the bad config string below

    conf_str = """
[%(DEFAULT)s]
option_name = str:DEFAULT_value
[%(PRESENT)s]
option_name =
    int: 1
    float: 1.1
    Decimal: 1.01
    bool: yes
    UUID: eeb7f94a-256d-11ea-ad1d-5404a6a1fd6e
    # Test using full name lookup
    firebird.base.types.MIME: application/octet-stream
    # Test simple name lookup (requires prior register_class)
    ZMQAddress: tcp://127.0.0.1:*
    SimpleEnum:RUNNING
[%(ABSENT)s]
[%(BAD)s]
# Contains an unsupported type prefix 'bin'
option_name = str:this is string, int:20, bin:100110111
[%(EMPTY)s]
option_name =
"""

# List of parameter classes to use with pytest.mark.parametrize
params = [StrParams, IntParams, FloatParams, DecimalParams, BoolParams, UUIDParams,
          MIMEParams, ZMQAddressParams, MultiTypeParams]

@pytest.fixture(params=params)
def test_params(base_conf: ConfigParser, request) -> ParamBase:
    """Fixture providing parameterized test data for ListOption tests."""
    param_class = request.param
    data = param_class()
    data.conf = base_conf # Attach the base config parser
    # Read the specific config string for this parameter set
    data.conf.read_string(data.conf_str % {"DEFAULT": DEFAULT_S, "PRESENT": PRESENT_S,
                                           "ABSENT": ABSENT_S, "BAD": BAD_S, "EMPTY": EMPTY_S})
    return data

# --- Test Cases ---

def test_simple(test_params: ParamBase):
    """Tests basic ListOption: init, load, value access, clear, default handling."""
    opt = config.ListOption("option_name", test_params.ITEM_TYPE, "description")

    # Verify initial state
    assert opt.name == "option_name"
    assert opt.datatype == list
    assert opt.description == "description"
    assert not opt.required
    assert opt.default is None
    assert opt.value is None # Initial value without default is None
    assert opt.item_types == test_params.ITEM_TYPE if isinstance(test_params.ITEM_TYPE, Sequence) else (test_params.ITEM_TYPE, )
    opt.validate() # Should pass as not required

    # Load value from [present] section
    opt.load_config(test_params.conf, PRESENT_S)
    assert opt.value == test_params.PRESENT_VAL
    # get_as_str() depends on default separator logic (newline if loaded multiline)
    assert opt.get_as_str() == test_params.PRESENT_AS_STR
    assert isinstance(opt.value, opt.datatype)
    # get_formatted() depends on default separator logic
    if '\n' in test_params.PRESENT_AS_STR: # Check if it was multiline
        expected_format = f"\n   {test_params.PRESENT_AS_STR.replace(chr(10), chr(10) + '   ')}"
        assert opt.get_formatted() == expected_format
    else:
        assert opt.get_formatted() == ", ".join(opt._get_as_typed_str(i) for i in test_params.PRESENT_VAL)


    # Clear value (should reset to None as no default)
    opt.clear(to_default=False)
    assert opt.value is None

    # Clear value to default (should still be None)
    opt.clear(to_default=True)
    assert opt.value is None

    # Set value manually to None
    opt.set_value(None)
    assert opt.value is None

    # Set value manually
    opt.set_value(test_params.NEW_VAL)
    assert opt.value == test_params.NEW_VAL
    assert isinstance(opt.value, opt.datatype)

    # Test assigning list with wrong item type (only if ITEM_TYPE is single)
    if isinstance(test_params.ITEM_TYPE, type) and test_params.ITEM_TYPE is not str:
        with pytest.raises(ValueError, match="List item\\[1\\] has wrong type"):
            opt.value = [test_params.NEW_VAL[0], "a_string"]
    elif isinstance(test_params.ITEM_TYPE, type) and test_params.ITEM_TYPE is str:
        with pytest.raises(ValueError, match="List item\\[1\\] has wrong type"):
            opt.value = [test_params.NEW_VAL[0], 123] # Assign int to str list


def test_required(test_params: ParamBase):
    """Tests ListOption with the 'required' flag."""
    opt = config.ListOption("option_name", test_params.ITEM_TYPE, "description", required=True)

    # Verify initial state (required, no default)
    assert opt.required
    assert opt.default is None
    assert opt.value is None
    # Validation should fail when value is None
    with pytest.raises(Error, match="Missing value for required option 'option_name'"):
        opt.validate()

    # Load value, validation should pass
    opt.load_config(test_params.conf, PRESENT_S)
    assert opt.value == test_params.PRESENT_VAL
    opt.validate()

    # Clear to default (which is None), validation should fail again
    opt.clear(to_default=True)
    assert opt.value is None
    with pytest.raises(Error, match="Missing value for required option 'option_name'"):
        opt.validate()

    # Setting value to None should raise ValueError for required option
    with pytest.raises(ValueError, match="Value is required for option 'option_name'"):
        opt.set_value(None)

    # Set value manually
    opt.set_value(test_params.NEW_VAL)
    assert opt.value == test_params.NEW_VAL
    opt.validate()

def test_bad_value(test_params: ParamBase):
    """Tests loading invalid list string values."""
    opt = config.ListOption("option_name", test_params.ITEM_TYPE, "description")

    # Load from section with bad value
    if test_params.BAD_MSG:
        with pytest.raises(ValueError) as excinfo:
            opt.load_config(test_params.conf, BAD_S)
        # Check if the specific underlying error matches
        if isinstance(excinfo.value, Exception):
            assert excinfo.value.args == test_params.BAD_MSG
        else:
            # For multi-type error which isn't from cause
            assert excinfo.value.args == test_params.BAD_MSG

        assert opt.value is None # Value should remain unchanged (None)
    else:
        # For string list, BAD_S might be empty or contain convertible strings
        opt.load_config(test_params.conf, BAD_S)
        # Depending on conf_str for StrParams, value might be None or ['']
        assert opt.value is None or opt.value == ['']


    # Load from section with empty value (should result in None or empty list)
    opt.load_config(test_params.conf, EMPTY_S)
    assert opt.value is None # Empty config value results in None

    # Test assigning invalid type via set_value
    with pytest.raises(TypeError, match="Option 'option_name' value must be a 'list', not 'float'"):
        opt.set_value(10.0) # type: ignore

    # Test setting invalid string via set_as_str
    if test_params.BAD_MSG:
        with pytest.raises(ValueError) as excinfo:
            opt.set_as_str("invalid" if not isinstance(test_params.ITEM_TYPE, Sequence) else "bin:invalid")
        if isinstance(excinfo.value, Exception):
            assert excinfo.value.args == test_params.BAD_MSG
        elif test_params.ITEM_TYPE is bool: # Bool error isn't nested
            assert excinfo.value.args == test_params.BAD_MSG


def test_default(test_params: ParamBase):
    """Tests ListOption with a defined default list value."""
    opt = config.ListOption("option_name", test_params.ITEM_TYPE, "description",
                            default=test_params.DEFAULT_OPT_VAL)

    # Verify initial state (default value should be set)
    assert not opt.required
    assert opt.default == test_params.DEFAULT_OPT_VAL
    assert isinstance(opt.default, opt.datatype)
    assert opt.value == test_params.DEFAULT_OPT_VAL # Initial value is the default
    assert isinstance(opt.value, opt.datatype)
    opt.validate() # Should pass

    # Load value from [present] section (overrides default)
    opt.load_config(test_params.conf, PRESENT_S)
    assert opt.value == test_params.PRESENT_VAL

    # Clear to default
    opt.clear(to_default=True)
    # Default is copied, should be equal but not the same instance
    assert opt.value == opt.default
    assert opt.value is not opt.default

    # Clear to None
    opt.clear(to_default=False)
    assert opt.value is None

    # Set value manually to None
    opt.set_value(None)
    assert opt.value is None

    # Set value manually
    opt.set_value(test_params.NEW_VAL)
    assert opt.value == test_params.NEW_VAL

    # Ensure default list wasn't modified if value was appended to
    opt.value.append(test_params.DEFAULT_VAL[0]) # Modify the current value list
    assert opt.default == test_params.DEFAULT_OPT_VAL # Original default should be unchanged

def test_proto(test_params: ParamBase, proto: ConfigProto):
    """Tests serialization to and deserialization from Protobuf messages."""
    opt = config.ListOption("option_name", test_params.ITEM_TYPE, "description",
                            default=test_params.DEFAULT_OPT_VAL)
    proto_value = test_params.PROTO_VALUE
    proto_value_str = test_params.PROTO_VALUE_STR

    # Set value and serialize (saves as string)
    opt.set_value(proto_value)
    opt.save_proto(proto)
    assert "option_name" in proto.options
    assert proto.options["option_name"].HasField('as_string')
    # Serialized string uses default separator logic (comma unless long)
    assert proto.options["option_name"].as_string == proto_value_str
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
    opt.set_value(test_params.DEFAULT_OPT_VAL) # Set a known value
    proto.Clear()
    opt.load_proto(proto)
    assert opt.value == test_params.DEFAULT_OPT_VAL # Should not change to None

    # Test loading bad proto value (wrong type)
    proto.Clear()
    proto.options["option_name"].as_uint64 = 1 # Invalid type for ListOption (expects string)
    with pytest.raises(TypeError, match="Wrong value type: uint64"):
        opt.load_proto(proto)

    # Test loading bad proto value (invalid string format for item type)
    if test_params.BAD_MSG:
        proto.Clear()
        # Construct a bad string based on expected error
        bad_item_str = "invalid"
        proto.options["option_name"].as_string = bad_item_str if len(opt.item_types) == 1 \
                                                else f"bin:{bad_item_str}" # Need prefix for multi
        with pytest.raises(ValueError) as excinfo:
            opt.load_proto(proto)
        if isinstance(excinfo.value, Exception):
            assert excinfo.value.args == test_params.BAD_MSG
        # Handle multi-type case where error isn't nested
        elif test_params is MultiTypeParams and test_params.BAD_MSG[0].startswith("Item type"):
            assert excinfo.value.args == test_params.BAD_MSG


def test_get_config(test_params: ParamBase):
    """Tests the get_config method for generating config file string representation."""
    opt = config.ListOption("option_name", test_params.ITEM_TYPE, "description",
                            default=test_params.DEFAULT_OPT_VAL)

    # Test output with default value (should be commented out)
    expected_lines_default = f"""; description
; Type: list [{test_params.TYPE_NAMES}]
;option_name = {test_params.DEFAULT_PRINT}
"""
    assert opt.get_config() == expected_lines_default

    # Test output with explicitly set value
    opt.set_value(test_params.NEW_VAL)
    expected_lines_set = f"""; description
; Type: list [{test_params.TYPE_NAMES}]
option_name = {test_params.NEW_PRINT}
"""
    assert opt.get_config() == expected_lines_set

    # Test output when value is None (should show <UNDEFINED>)
    opt.set_value(None)
    expected_lines_none = f"""; description
; Type: list [{test_params.TYPE_NAMES}]
option_name = <UNDEFINED>
"""
    assert opt.get_config() == expected_lines_none
    # Check get_formatted directly for None case
    assert opt.get_formatted() == "<UNDEFINED>"

    # Test multiline formatting for long values
    opt.set_value(test_params.LONG_VAL)
    expected_lines_long = f"""; description
; Type: list [{test_params.TYPE_NAMES}]
option_name = {test_params.LONG_PRINT}
"""
    assert opt.get_config() == expected_lines_long

    # Test plain output
    opt.set_value(test_params.NEW_VAL)
    assert opt.get_config(plain=True) == f"option_name = {test_params.NEW_PRINT}\n"
    opt.set_value(None)
    assert opt.get_config(plain=True) == "option_name = <UNDEFINED>\n"

def test_separator_override(test_params: ParamBase):
    """Tests ListOption with an explicit separator."""
    # Use semicolon as separator
    opt = config.ListOption("option_name", test_params.ITEM_TYPE, "description",
                            separator='|')
    assert opt.separator == '|'

    # Set value
    opt.set_value(test_params.PRESENT_VAL)

    # Check get_formatted uses the specified separator
    expected_format = "| ".join(opt._get_as_typed_str(i) for i in test_params.PRESENT_VAL)
    assert opt.get_formatted() == expected_format

    # Check get_as_str uses the specified separator
    expected_str = "|".join(opt._get_as_typed_str(i) for i in test_params.PRESENT_VAL)
    assert opt.get_as_str() == expected_str

    # Test set_as_str with the specified separator
    opt.set_value(None) # Clear first
    opt.set_as_str(expected_str)
    assert opt.value == test_params.PRESENT_VAL

    # Test set_as_str with a *different* separator (should likely fail or parse incorrectly)
    opt.set_value(None)
    if test_params.BAD_MSG: # Expect parsing error if items are not simple strings
        with pytest.raises(ValueError):
            opt.set_as_str("item1, item2") # Using comma instead of semicolon
    else: # For string list, it will just parse as one item
        opt.set_as_str("item1, item2")
        assert opt.value == ["item1, item2"]
