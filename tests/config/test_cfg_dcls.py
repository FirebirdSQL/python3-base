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

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum

import pytest

from firebird.base import config
from firebird.base.types import Error, PyCallable

DEFAULT_S = "DEFAULT"
PRESENT_S = "present"
ABSENT_S = "absent"
BAD_S = "bad_value"
EMPTY_S = "empty"

class SimpleEnum(IntEnum):
    "Enum for testing"
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
    STOPPED    = 4
    TERMINATED = 6

@dataclass
class SimpleDataclass:
    name: str
    priority: int = 1
    state: SimpleEnum = SimpleEnum.READY

DEFAULT_VAL = SimpleDataclass("main")
PRESENT_VAL = SimpleDataclass("master", 3, SimpleEnum.RUNNING)
DEFAULT_OPT_VAL = SimpleDataclass("default")
NEW_VAL = SimpleDataclass("master", 3, SimpleEnum.STOPPED)

@pytest.fixture
def conf(base_conf):
    """Returns configparser initialized with data.
    """
    conf_str = """[%(DEFAULT)s]
; Enum is defined by name
option_name = name:main
[%(PRESENT)s]
; case does not matter
option_name =
   name:master
   priority:3
   state:RUNNING
[%(ABSENT)s]
[%(BAD)s]
option_name = bad_value
[illegal]
option_name = 1000
"""
    base_conf.read_string(conf_str % {"DEFAULT": DEFAULT_S, "PRESENT": PRESENT_S,
                                      "ABSENT": ABSENT_S, "BAD": BAD_S, "EMPTY": EMPTY_S,})
    return base_conf

def test_simple(conf):
    opt = config.DataclassOption("option_name", SimpleDataclass, "description")
    assert opt.name == "option_name"
    assert opt.datatype == SimpleDataclass
    assert opt.description == "description"
    assert not opt.required
    assert opt.default is None
    assert opt.value is None
    opt.validate()
    opt.load_config(conf, PRESENT_S)
    assert opt.value == PRESENT_VAL
    assert opt.get_as_str() == "name:master,priority:3,state:RUNNING"
    assert isinstance(opt.value, opt.datatype)
    opt.clear()
    assert opt.value is None
    opt.load_config(conf, DEFAULT_S)
    assert opt.value == DEFAULT_VAL
    assert isinstance(opt.value, opt.datatype)
    opt.set_value(None)
    assert opt.value is None
    opt.load_config(conf, ABSENT_S)
    assert opt.value == DEFAULT_VAL
    assert isinstance(opt.value, opt.datatype)
    opt.set_value(NEW_VAL)
    assert opt.value == NEW_VAL
    assert isinstance(opt.value, opt.datatype)

def test_required(conf):
    opt = config.DataclassOption("option_name", SimpleDataclass, "description", required=True)
    assert opt.name == "option_name"
    assert opt.datatype == SimpleDataclass
    assert opt.description == "description"
    assert opt.required
    assert opt.default is None
    assert opt.value is None
    with pytest.raises(Error) as cm:
        opt.validate()
    assert cm.value.args == ("Missing value for required option 'option_name'",)
    opt.load_config(conf, PRESENT_S)
    assert opt.value == PRESENT_VAL
    opt.validate()
    opt.clear()
    assert opt.value is None
    opt.load_config(conf, DEFAULT_S)
    assert opt.value == DEFAULT_VAL
    with pytest.raises(ValueError) as cm:
        opt.set_value(None)
    assert cm.value.args == ("Value is required for option 'option_name'.",)
    opt.load_config(conf, ABSENT_S)
    assert opt.value == DEFAULT_VAL
    opt.set_value(NEW_VAL)
    assert opt.value == NEW_VAL

def test_bad_value(conf):
    opt = config.DataclassOption("option_name", SimpleDataclass, "description")
    with pytest.raises(ValueError) as cm:
        opt.load_config(conf, BAD_S)
    assert cm.value.args == ("Illegal value 'bad_value' for option 'option_name'",)
    with pytest.raises(ValueError) as cm:
        opt.load_config(conf, "illegal")
    assert cm.value.args == ("Illegal value '1000' for option 'option_name'",)
    with pytest.raises(TypeError) as cm:
        opt.set_value(10.0)
    assert cm.value.args == ("Option 'option_name' value must be a 'SimpleDataclass', not 'float'",)

def test_default(conf):
    opt = config.DataclassOption("option_name", SimpleDataclass, "description", default=DEFAULT_OPT_VAL)
    assert opt.name == "option_name"
    assert opt.datatype == SimpleDataclass
    assert opt.description == "description"
    assert not opt.required
    assert opt.default == DEFAULT_OPT_VAL
    assert isinstance(opt.default, opt.datatype)
    assert opt.default == DEFAULT_OPT_VAL
    assert isinstance(opt.value, opt.datatype)
    opt.validate()
    opt.load_config(conf, PRESENT_S)
    assert opt.value == PRESENT_VAL
    opt.clear()
    assert opt.value == opt.default
    opt.load_config(conf, DEFAULT_S)
    assert opt.value == DEFAULT_VAL
    opt.set_value(None)
    assert opt.value is None
    opt.load_config(conf, ABSENT_S)
    assert opt.value == DEFAULT_VAL
    opt.set_value(NEW_VAL)
    assert opt.value == NEW_VAL

def test_proto(conf, proto):
    opt = config.DataclassOption("option_name", SimpleDataclass, "description", default=DEFAULT_OPT_VAL)
    proto_value = SimpleDataclass("backup", 2, SimpleEnum.FINISHED)
    opt.set_value(proto_value)
    proto.options["option_name"].as_string = "name:backup,priority:2,state:FINISHED"
    proto_dump = str(proto)
    opt.load_proto(proto)
    assert opt.value == proto_value
    assert isinstance(opt.value, opt.datatype)
    opt.set_value(None)
    proto.options["option_name"].as_string = "name:backup,priority:2,state:FINISHED"
    opt.load_proto(proto)
    assert opt.value == proto_value
    proto.Clear()
    assert "option_name" not in proto.options
    opt.save_proto(proto)
    assert "option_name" in proto.options
    assert str(proto) == proto_dump
    # empty proto
    opt.clear(to_default=False)
    proto.Clear()
    opt.load_proto(proto)
    assert opt.value is None
    # bad proto value
    proto.options["option_name"].as_uint32 = 1000
    with pytest.raises(TypeError) as cm:
        opt.load_proto(proto)
    assert cm.value.args == ("Wrong value type: uint32",)
    proto.Clear()
    opt.clear(to_default=False)
    opt.save_proto(proto)
    assert "option_name" not in proto.options

def test_get_config(conf):
    opt = config.DataclassOption("option_name", SimpleDataclass, "description", default=DEFAULT_OPT_VAL)
    lines = """; description
; Type: list of values, where each list item defines value for a dataclass field.
; Item format: field_name:value_as_str
;option_name = name:default, priority:1, state:READY
"""
    assert opt.get_config() == lines
    lines = """; description
; Type: list of values, where each list item defines value for a dataclass field.
; Item format: field_name:value_as_str
option_name = name:master, priority:3, state:SUSPENDED
"""
    opt.set_value(NEW_VAL)
    assert opt.get_config() == lines
    lines = """; description
; Type: list of values, where each list item defines value for a dataclass field.
; Item format: field_name:value_as_str
option_name = <UNDEFINED>
"""
    opt.set_value(None)
    assert opt.get_config() == lines
