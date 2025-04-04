# SPDX-FileCopyrightText: 2025-present The Firebird Projects <www.firebirdsql.org>
#
# SPDX-License-Identifier: MIT
#
# PROGRAM/MODULE: firebird-base
# FILE:           tests/config/test_cfg_mime.py
# DESCRIPTION:    Tests for firebird.base.config MIMEOption
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

"""Unit tests for the MIMEOption configuration option class."""

from __future__ import annotations

import pytest
from configparser import ConfigParser # Import for type hinting

from firebird.base import config
from firebird.base.config_pb2 import ConfigProto # Import for proto tests
from firebird.base.types import MIME, Error

# --- Constants for Test Sections ---
DEFAULT_S = "DEFAULT"
PRESENT_S = "present"
ABSENT_S = "absent"
BAD_FORMAT_S = "bad_format"
BAD_TYPE_S = "unsupported_mime_type"
BAD_PARAMS_S = "bad_mime_parameters"
EMPTY_S = "empty"

# --- Constants for Test Values ---
PRESENT_VAL = MIME("text/plain;charset=utf-8")
PRESENT_TYPE = "text/plain"
PRESENT_PARS = {"charset": "utf-8"}
DEFAULT_VAL = MIME("application/octet-stream")
DEFAULT_TYPE = "application/octet-stream"
DEFAULT_PARS = {}
DEFAULT_OPT_VAL = MIME("text/plain;charset=win1250") # Default for the option itself
DEFAULT_OPT_TYPE = "text/plain"
DEFAULT_OPT_PARS = {"charset": "win1250"}
NEW_VAL = MIME("application/x.fb.proto;type=firebird.butler.fbsd.ErrorDescription")
NEW_TYPE = "application/x.fb.proto"
NEW_PARS = {"type": "firebird.butler.fbsd.ErrorDescription"}

# --- Fixtures ---

@pytest.fixture
def conf(base_conf: ConfigParser) -> ConfigParser:
    """Provides a ConfigParser instance initialized with MIME test data."""
    conf_str = """
[%(DEFAULT)s]
# Option defined in DEFAULT section
option_name = application/octet-stream
[%(PRESENT)s]
# Option present in its own section
option_name = text/plain;charset=utf-8
[%(ABSENT)s]
# Section exists, but option is absent (will inherit from DEFAULT)
[%(BAD_FORMAT)s]
# Invalid format (missing slash)
option_name = wrong mime specification
[%(BAD_TYPE)s]
# Unsupported MIME primary type
option_name = model/vml
[%(BAD_PARAMS)s]
# Invalid parameter format (should be key=value)
option_name = text/plain;charset/utf-8
[%(EMPTY)s]
# Option present but empty
option_name =
"""
    # Format the string with section names and read into the config parser
    base_conf.read_string(conf_str % {"DEFAULT": DEFAULT_S, "PRESENT": PRESENT_S,
                                      "ABSENT": ABSENT_S, "BAD_FORMAT": BAD_FORMAT_S,
                                      "BAD_TYPE": BAD_TYPE_S, "BAD_PARAMS": BAD_PARAMS_S,
                                      "EMPTY": EMPTY_S})
    return base_conf

# --- Test Cases ---

def test_simple(conf: ConfigParser):
    """Tests basic MIMEOption functionality: init, load, value access, clear, default handling."""
    opt: config.MIMEOption = config.MIMEOption("option_name", "description")

    # Verify initial state
    assert opt.name == "option_name"
    assert opt.datatype == MIME
    assert opt.description == "description"
    assert not opt.required
    assert opt.default is None
    assert opt.value is None # Initial value without default is None
    opt.validate() # Should pass as not required

    # Load value from [present] section
    opt.load_config(conf, PRESENT_S)
    assert opt.value == PRESENT_VAL
    assert str(opt.value) == "text/plain;charset=utf-8" # Check string value
    assert opt.get_as_str() == str(PRESENT_VAL) # Should be the same
    assert isinstance(opt.value, opt.datatype)
    assert opt.value.mime_type == PRESENT_TYPE
    assert opt.value.params == PRESENT_PARS
    assert opt.value.params.get("charset") == "utf-8"
    assert opt.get_formatted() == str(PRESENT_VAL) # Config format is same as string

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
    assert opt.value.mime_type == DEFAULT_TYPE
    assert opt.value.params == DEFAULT_PARS

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
    assert opt.value.mime_type == NEW_TYPE
    assert opt.value.params == NEW_PARS

def test_required(conf: ConfigParser):
    """Tests MIMEOption with the 'required' flag."""
    opt = config.MIMEOption("option_name", "description", required=True)

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
    """Tests loading invalid MIME string values or invalid types."""
    opt: config.MIMEOption = config.MIMEOption("option_name", "description")

    # Load from section with bad format (missing slash)
    with pytest.raises(ValueError, match="MIME type specification must be"):
        opt.load_config(conf, BAD_FORMAT_S)
    assert opt.value is None # Value should remain unchanged (None)

    # Load from section with unsupported type
    with pytest.raises(ValueError, match="MIME type 'model' not supported"):
        opt.load_config(conf, BAD_TYPE_S)
    assert opt.value is None

    # Load from section with bad parameters
    with pytest.raises(ValueError, match="Wrong specification of MIME type parameters"):
        opt.load_config(conf, BAD_PARAMS_S)
    assert opt.value is None

    # Load from section with empty value
    with pytest.raises(ValueError, match="MIME type specification must be"):
        opt.load_config(conf, EMPTY_S)
    assert opt.value is None

    # Test assigning invalid type via set_value
    with pytest.raises(TypeError, match="Option 'option_name' value must be a 'MIME', not 'float'"):
        opt.set_value(10.0) # type: ignore

    # Test setting invalid string via set_as_str
    with pytest.raises(ValueError, match="MIME type specification must be"):
        opt.set_as_str("invalid-mime-string")


def test_default(conf: ConfigParser):
    """Tests MIMEOption with a defined default value."""
    opt = config.MIMEOption("option_name", "description", default=DEFAULT_OPT_VAL)

    # Verify initial state (default value should be set)
    assert not opt.required
    assert opt.default == DEFAULT_OPT_VAL
    assert isinstance(opt.default, opt.datatype)
    assert opt.value == DEFAULT_OPT_VAL # Initial value is the default
    assert isinstance(opt.value, opt.datatype)
    assert opt.value.mime_type == DEFAULT_OPT_TYPE
    assert opt.value.params == DEFAULT_OPT_PARS
    opt.validate() # Should pass

    # Load value from [present] section (overrides default)
    opt.load_config(conf, PRESENT_S)
    assert opt.value == PRESENT_VAL
    assert opt.value.mime_type == PRESENT_TYPE
    assert opt.value.params == PRESENT_PARS

    # Clear to default
    opt.clear(to_default=True)
    assert opt.value == opt.default

    # Clear to None
    opt.clear(to_default=False)
    assert opt.value is None

    # Load from [DEFAULT] section (overrides option default)
    opt.load_config(conf, DEFAULT_S)
    assert opt.value == DEFAULT_VAL
    assert opt.value.mime_type == DEFAULT_TYPE
    assert opt.value.params == DEFAULT_PARS

    # Set value manually to None
    opt.set_value(None)
    assert opt.value is None

    # Load from absent section (inherits from DEFAULT, overrides option default)
    opt.load_config(conf, ABSENT_S)
    assert opt.value == DEFAULT_VAL

    # Set value manually
    opt.set_value(NEW_VAL)
    assert opt.value == NEW_VAL
    assert opt.value.mime_type == NEW_TYPE
    assert opt.value.params == NEW_PARS

def test_proto(conf: ConfigParser, proto: ConfigProto):
    """Tests serialization to and deserialization from Protobuf messages."""
    opt = config.MIMEOption("option_name", "description", default=DEFAULT_OPT_VAL)
    proto_value = NEW_VAL # application/x.fb.proto;type=...
    proto_value_str = str(proto_value)

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
    assert opt.value == proto_value
    assert opt.value.mime_type == NEW_TYPE
    assert opt.value.params == NEW_PARS
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
    proto.options["option_name"].as_uint32 = 1000 # Invalid type for MIMEOption
    with pytest.raises(TypeError, match="Wrong value type: uint32"):
        opt.load_proto(proto)

    # Test loading bad proto value (invalid string for MIME)
    proto.Clear()
    proto.options["option_name"].as_string = "invalid mime"
    with pytest.raises(ValueError, match="MIME type specification must be"):
        opt.load_proto(proto)


def test_get_config(conf: ConfigParser):
    """Tests the get_config method for generating config file string representation."""
    opt = config.MIMEOption("option_name", "description", default=DEFAULT_OPT_VAL)

    # Test output with default value (should be commented out)
    expected_lines_default = """; description
; Type: MIME
;option_name = text/plain;charset=win1250
"""
    assert opt.get_config() == expected_lines_default

    # Test output with explicitly set value
    opt.set_value(NEW_VAL)
    expected_lines_new = """; description
; Type: MIME
option_name = application/x.fb.proto;type=firebird.butler.fbsd.ErrorDescription
"""
    assert opt.get_config() == expected_lines_new

    # Test output when value is None (should show <UNDEFINED>)
    opt.set_value(None)
    expected_lines_none = """; description
; Type: MIME
option_name = <UNDEFINED>
"""
    assert opt.get_config() == expected_lines_none
    # Check get_formatted directly for None case
    assert opt.get_formatted() == "<UNDEFINED>"

    # Test plain output
    opt.set_value(NEW_VAL)
    assert opt.get_config(plain=True) == f"option_name = {str(NEW_VAL)}\n"
    opt.set_value(None)
    assert opt.get_config(plain=True) == "option_name = <UNDEFINED>\n"
