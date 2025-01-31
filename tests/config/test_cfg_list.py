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

from __future__ import annotations

from decimal import Decimal
from enum import IntEnum
from uuid import UUID

import pytest

from firebird.base import config
from firebird.base.strconv import convert_to_str
from firebird.base.types import MIME, Error, ZMQAddress

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

class StrParams:
    DEFAULT_VAL = ["DEFAULT_value"]
    DEFAULT_PRINT = "DEFAULT_1, DEFAULT_2, DEFAULT_3"
    PRESENT_VAL = ["present_value_1", "present_value_2"]
    PRESENT_AS_STR = "present_value_1,present_value_2"
    DEFAULT_OPT_VAL = ["DEFAULT_1", "DEFAULT_2", "DEFAULT_3"]
    NEW_VAL = ["NEW"]
    NEW_PRINT = "NEW"
    ITEM_TYPE = str
    PROTO_VALUE = ["proto_value_1", "proto_value_2"]
    PROTO_VALUE_STR = "proto_value_1,proto_value_2"
    LONG_VAL = ["long" * 3, "verylong" * 3, "veryverylong" * 5]
    BAD_MSG = None
    def __init__(self):
        self.prepare()
        x = (self.ITEM_TYPE, ) if isinstance(self.ITEM_TYPE, type) else self.ITEM_TYPE
        self.TYPE_NAMES = ", ".join(t.__name__ for t in x)
    def prepare(self):
        x = "\n   "
        self.LONG_PRINT = f"\n   {x.join(self.LONG_VAL)}"
        self.conf_str = """[%(DEFAULT)s]
option_name = DEFAULT_value
[%(PRESENT)s]
option_name =
  present_value_1
  present_value_2
[%(ABSENT)s]
[%(BAD)s]
option_name =
"""

class IntParams(StrParams):
    DEFAULT_VAL = [0]
    PRESENT_VAL = [10, 20]
    DEFAULT_OPT_VAL = [1, 2, 3]
    NEW_VAL = [100]
    DEFAULT_PRINT = "1, 2, 3"
    PRESENT_AS_STR = "10,20"
    NEW_PRINT = "100"
    ITEM_TYPE = int
    PROTO_VALUE = [30, 40, 50]
    PROTO_VALUE_STR = "30,40,50"
    LONG_VAL = [x for x in range(50)]
    def prepare(self):
        x = "\n   "
        self.LONG_PRINT = f"\n   {x.join(str(x) for x in self.LONG_VAL)}"
        self.BAD_MSG = ("invalid literal for int() with base 10: 'this is not an integer'",)
        self.conf_str = """[%(DEFAULT)s]
option_name = 0
[%(PRESENT)s]
option_name = 10, 20
[%(ABSENT)s]
[%(BAD)s]
option_name = this is not an integer
"""

class FloatParams(StrParams):
    DEFAULT_VAL = [0.0]
    PRESENT_VAL = [10.1, 20.2]
    DEFAULT_OPT_VAL = [1.11, 2.22, 3.33]
    NEW_VAL = [100.101]
    DEFAULT_PRINT = "1.11, 2.22, 3.33"
    PRESENT_AS_STR = "10.1,20.2"
    NEW_PRINT = "100.101"
    ITEM_TYPE = float
    PROTO_VALUE = [30.3, 40.4, 50.5]
    PROTO_VALUE_STR = "30.3,40.4,50.5"
    LONG_VAL = [x / 1.5 for x in range(50)]
    def prepare(self):
        x = "\n   "
        self.LONG_PRINT = f"\n   {x.join(str(x) for x in self.LONG_VAL)}"
        self.BAD_MSG = ("could not convert string to float: 'this is not a float'",)
        self.conf_str = """[%(DEFAULT)s]
option_name = 0.0
[%(PRESENT)s]
option_name = 10.1, 20.2
[%(ABSENT)s]
[%(BAD)s]
option_name = this is not a float
"""

class DecimalParams(StrParams):
    DEFAULT_VAL = [Decimal("0.0")]
    PRESENT_VAL = [Decimal("10.1"), Decimal("20.2")]
    DEFAULT_OPT_VAL = [Decimal("1.11"), Decimal("2.22"), Decimal("3.33")]
    NEW_VAL = [Decimal("100.101")]
    DEFAULT_PRINT = "1.11, 2.22, 3.33"
    PRESENT_AS_STR = "10.1,20.2"
    NEW_PRINT = "100.101"
    ITEM_TYPE = Decimal
    PROTO_VALUE = [Decimal("30.3"), Decimal("40.4"), Decimal("50.5")]
    PROTO_VALUE_STR = "30.3,40.4,50.5"
    LONG_VAL = [Decimal(str(x / 1.5)) for x in range(50)]
    def prepare(self):
        x = "\n   "
        self.LONG_PRINT = f"\n   {x.join(str(x) for x in self.LONG_VAL)}"
        self.BAD_MSG = ("could not convert string to Decimal: 'this is not a decimal'",)
        self.conf_str = """[%(DEFAULT)s]
option_name = 0.0
[%(PRESENT)s]
option_name = 10.1, 20.2
[%(ABSENT)s]
[%(BAD)s]
option_name = this is not a decimal
"""

class BoolParams(StrParams):
    DEFAULT_VAL = [0]
    PRESENT_VAL = [True, False]
    DEFAULT_OPT_VAL = [True, False, True]
    NEW_VAL = [True]
    DEFAULT_PRINT = "yes, no, yes"
    PRESENT_AS_STR = "yes,no"
    NEW_PRINT = "yes"
    ITEM_TYPE = bool
    PROTO_VALUE = [False, True, False]
    PROTO_VALUE_STR = "no,yes,no"
    LONG_VAL = [bool(x % 2) for x in range(40)]
    def prepare(self):
        x = "\n   "
        self.LONG_PRINT = f"\n   {x.join(convert_to_str(x) for x in self.LONG_VAL)}"
        self.BAD_MSG = ("Value is not a valid bool string constant",)
        self.conf_str = """[%(DEFAULT)s]
option_name = 0
[%(PRESENT)s]
option_name = yes, no
[%(ABSENT)s]
[%(BAD)s]
option_name = this is not a bool
"""

class UUIDParams(StrParams):
    DEFAULT_VAL = [UUID("eeb7f94a-256d-11ea-ad1d-5404a6a1fd6e")]
    PRESENT_VAL = [UUID("0a7fd53a-256e-11ea-ad1d-5404a6a1fd6e"),
                   UUID("0551feb2-256e-11ea-ad1d-5404a6a1fd6e")]
    DEFAULT_OPT_VAL = [UUID("2f02868c-256e-11ea-ad1d-5404a6a1fd6e"),
                       UUID("3521db30-256e-11ea-ad1d-5404a6a1fd6e"),
                       UUID("3a3e68cc-256e-11ea-ad1d-5404a6a1fd6e")]
    NEW_VAL = [UUID("3e8a4ce8-256e-11ea-ad1d-5404a6a1fd6e")]
    DEFAULT_PRINT = "\n;   2f02868c-256e-11ea-ad1d-5404a6a1fd6e\n;   3521db30-256e-11ea-ad1d-5404a6a1fd6e\n;   3a3e68cc-256e-11ea-ad1d-5404a6a1fd6e"
    PRESENT_AS_STR = "0a7fd53a-256e-11ea-ad1d-5404a6a1fd6e,0551feb2-256e-11ea-ad1d-5404a6a1fd6e"
    NEW_PRINT = "3e8a4ce8-256e-11ea-ad1d-5404a6a1fd6e"
    ITEM_TYPE = UUID
    PROTO_VALUE = [UUID("3a3e68cc-256e-11ea-ad1d-5404a6a1fd6e"), UUID("3521db30-256e-11ea-ad1d-5404a6a1fd6e")]
    PROTO_VALUE_STR = "3a3e68cc-256e-11ea-ad1d-5404a6a1fd6e,3521db30-256e-11ea-ad1d-5404a6a1fd6e"
    LONG_VAL = [UUID("2f02868c-256e-11ea-ad1d-5404a6a1fd6e") for x in range(10)]
    def prepare(self):
        x = "\n   "
        self.LONG_PRINT = f"\n   {x.join(str(x) for x in self.LONG_VAL)}"
        self.BAD_MSG = ("badly formed hexadecimal UUID string",)
        self.conf_str = """[%(DEFAULT)s]
option_name = eeb7f94a-256d-11ea-ad1d-5404a6a1fd6e
[%(PRESENT)s]
option_name = 0a7fd53a256e11eaad1d5404a6a1fd6e, 0551feb2-256e-11ea-ad1d-5404a6a1fd6e
[%(ABSENT)s]
[%(BAD)s]
option_name = this is not an uuid
"""

class MIMEParams(StrParams):
    DEFAULT_VAL = [MIME("application/octet-stream")]
    PRESENT_VAL = [MIME("text/plain;charset=utf-8"),
                   MIME("text/csv")]
    DEFAULT_OPT_VAL = [MIME("text/html;charset=utf-8"),
                       MIME("video/mp4"),
                       MIME("image/png")]
    NEW_VAL = [MIME("audio/mpeg")]
    DEFAULT_PRINT = "text/html;charset=utf-8, video/mp4, image/png"
    PRESENT_AS_STR = "text/plain;charset=utf-8,text/csv"
    NEW_PRINT = "audio/mpeg"
    ITEM_TYPE = MIME
    PROTO_VALUE = [MIME("application/octet-stream"), MIME("video/mp4")]
    PROTO_VALUE_STR = "application/octet-stream,video/mp4"
    LONG_VAL = [MIME("text/html;charset=win1250") for x in range(10)]
    def prepare(self):
        x = "\n   "
        self.LONG_PRINT = f"\n   {x.join(x for x in self.LONG_VAL)}"
        self.BAD_MSG = ("MIME type specification must be 'type/subtype[;param=value;...]'",)
        self.conf_str = """[%(DEFAULT)s]
option_name = application/octet-stream
[%(PRESENT)s]
option_name =
    text/plain;charset=utf-8
    text/csv
[%(ABSENT)s]
[%(BAD)s]
option_name = wrong mime specification
"""

class ZMQAddressParams(StrParams):
    DEFAULT_VAL = [ZMQAddress("tcp://127.0.0.1:*")]
    PRESENT_VAL = [ZMQAddress("ipc://@my-address"),
                   ZMQAddress("inproc://my-address"),
                   ZMQAddress("tcp://127.0.0.1:9001")]
    DEFAULT_OPT_VAL = [ZMQAddress("tcp://127.0.0.1:8001")]
    NEW_VAL = [ZMQAddress("inproc://my-address")]
    DEFAULT_PRINT = "tcp://127.0.0.1:8001"
    PRESENT_AS_STR = "ipc://@my-address,inproc://my-address,tcp://127.0.0.1:9001"
    NEW_PRINT = "inproc://my-address"
    ITEM_TYPE = ZMQAddress
    PROTO_VALUE = [ZMQAddress("tcp://www.firebirdsql.org:8001"), ZMQAddress("tcp://www.firebirdsql.org:9001")]
    PROTO_VALUE_STR = "tcp://www.firebirdsql.org:8001,tcp://www.firebirdsql.org:9001"
    LONG_VAL = [ZMQAddress("tcp://www.firebirdsql.org:500") for x in range(10)]
    def prepare(self):
        x = "\n   "
        self.LONG_PRINT = f"\n   {x.join(x for x in self.LONG_VAL)}"
        self.BAD_MSG = ("Protocol specification required",)
        self.conf_str = """[%(DEFAULT)s]
option_name = tcp://127.0.0.1:*
[%(PRESENT)s]
option_name = ipc://@my-address, inproc://my-address, tcp://127.0.0.1:9001
[%(ABSENT)s]
[%(BAD)s]
option_name = bad_value
"""

class MultiTypeParams(StrParams):
    DEFAULT_VAL = ["DEFAULT_value"]
    PRESENT_VAL = [1, 1.1, Decimal("1.01"), True,
                   UUID("eeb7f94a-256d-11ea-ad1d-5404a6a1fd6e"),
                   MIME("application/octet-stream"),
                   ZMQAddress("tcp://127.0.0.1:*"),
                   SimpleEnum.RUNNING]
    DEFAULT_OPT_VAL = ["DEFAULT_1", 1, False]
    NEW_VAL = [MIME("text/plain;charset=utf-8")]
    DEFAULT_PRINT = "DEFAULT_1, 1, no"
    PRESENT_AS_STR = "1\n1.1\n1.01\nyes\neeb7f94a-256d-11ea-ad1d-5404a6a1fd6e\napplication/octet-stream\ntcp://127.0.0.1:*\nRUNNING"
    NEW_PRINT = "text/plain;charset=utf-8"
    ITEM_TYPE = (str, int, float, Decimal, bool, UUID, MIME, ZMQAddress, SimpleEnum)
    PROTO_VALUE = [UUID("2f02868c-256e-11ea-ad1d-5404a6a1fd6e"), MIME("application/octet-stream")]
    PROTO_VALUE_STR = "UUID:2f02868c-256e-11ea-ad1d-5404a6a1fd6e,MIME:application/octet-stream"
    LONG_VAL = [ZMQAddress("tcp://www.firebirdsql.org:500"),
                UUID("2f02868c-256e-11ea-ad1d-5404a6a1fd6e"),
                MIME("application/octet-stream"),
                "=" * 30, 1, True, 10.1, Decimal("20.20")]
    def prepare(self):
        x = "\n   "
        self.LONG_PRINT = f"\n   {x.join(convert_to_str(x) for x in self.LONG_VAL)}"
        self.BAD_MSG = ("Item type 'bin' not supported",)
        self.conf_str = """[%(DEFAULT)s]
option_name = str:DEFAULT_value
[%(PRESENT)s]
option_name =
    int: 1
    float: 1.1
    Decimal: 1.01
    bool: yes
    UUID: eeb7f94a-256d-11ea-ad1d-5404a6a1fd6e
    firebird.base.types.MIME: application/octet-stream
    ZMQAddress: tcp://127.0.0.1:*
    SimpleEnum:RUNNING
[%(ABSENT)s]
[%(BAD)s]
option_name = str:this is string, int:20, bin:100110111
"""

params = [StrParams, IntParams, FloatParams, DecimalParams, BoolParams, UUIDParams,
          MIMEParams, ZMQAddressParams, MultiTypeParams]

@pytest.fixture
def conf(base_conf):
    """Returns configparser initialized with data.
    """
    conf_str = """[%(DEFAULT)s]
option_name = DEFAULT_value
[%(PRESENT)s]
option_name =
  present_value_1
  present_value_2
[%(ABSENT)s]
[%(BAD)s]
option_name =
"""
    base_conf.read_string(conf_str % {"DEFAULT": DEFAULT_S, "PRESENT": PRESENT_S,
                                      "ABSENT": ABSENT_S, "BAD": BAD_S, "EMPTY": EMPTY_S,})
    return base_conf

@pytest.fixture(params=params)
def xx(base_conf, request):
    """Parameters for List tests.
    """
    data = request.param()
    data.conf = base_conf
    conf_str = """[%(DEFAULT)s]
option_name = DEFAULT_value
[%(PRESENT)s]
option_name =
  present_value_1
  present_value_2
[%(ABSENT)s]
[%(BAD)s]
option_name =
"""
    base_conf.read_string(data.conf_str % {"DEFAULT": DEFAULT_S, "PRESENT": PRESENT_S,
                                      "ABSENT": ABSENT_S, "BAD": BAD_S, "EMPTY": EMPTY_S,})
    return data

def test_simple(xx):
    opt = config.ListOption("option_name", xx.ITEM_TYPE, "description")
    assert opt.name == "option_name"
    assert opt.datatype == list
    assert opt.description == "description"
    assert not opt.required
    assert opt.default is None
    assert opt.value is None
    opt.validate()
    opt.load_config(xx.conf, PRESENT_S)
    assert opt.value == xx.PRESENT_VAL
    assert opt.get_as_str() == xx.PRESENT_AS_STR
    assert isinstance(opt.value, opt.datatype)
    opt.clear()
    assert opt.value is None
    opt.load_config(xx.conf, DEFAULT_S)
    assert opt.value == xx.DEFAULT_VAL
    assert isinstance(opt.value, opt.datatype)
    opt.set_value(None)
    assert opt.value is None
    opt.load_config(xx.conf, ABSENT_S)
    assert opt.value == xx.DEFAULT_VAL
    assert isinstance(opt.value, opt.datatype)
    opt.set_value(xx.NEW_VAL)
    assert opt.value == xx.NEW_VAL
    assert isinstance(opt.value, opt.datatype)
    # Wrong item type in list
    if xx.ITEM_TYPE is str:
        with pytest.raises(ValueError) as cm:
            opt.value = ["ok", 1]
        assert cm.value.args == ("List item[1] has wrong type",)

def test_required(xx):
    opt = config.ListOption("option_name", xx.ITEM_TYPE, "description", required=True)
    assert opt.name == "option_name"
    assert opt.datatype == list
    assert opt.description == "description"
    assert opt.required
    assert opt.default is None
    assert opt.value is None
    with pytest.raises(Error) as cm:
        opt.validate()
    assert cm.value.args == ("Missing value for required option 'option_name'",)
    opt.load_config(xx.conf, PRESENT_S)
    assert opt.value == xx.PRESENT_VAL
    opt.validate()
    opt.clear()
    assert opt.value is None
    opt.load_config(xx.conf, DEFAULT_S)
    assert opt.value == xx.DEFAULT_VAL
    with pytest.raises(ValueError) as cm:
        opt.set_value(None)
    assert cm.value.args == ("Value is required for option 'option_name'.",)
    opt.load_config(xx.conf, ABSENT_S)
    assert opt.value == xx.DEFAULT_VAL
    opt.set_value(xx.NEW_VAL)
    assert opt.value == xx.NEW_VAL

def test_bad_value(xx):
    opt = config.ListOption("option_name", xx.ITEM_TYPE, "description")
    if xx.ITEM_TYPE is str:
        opt.load_config(xx.conf, BAD_S)
        assert opt.value is None
    else:
        with pytest.raises(ValueError) as cm:
            opt.load_config(xx.conf, BAD_S)
        #print(f'{cm.exception.args}\n')
        assert cm.value.args == xx.BAD_MSG
        assert opt.value is None
    with pytest.raises(TypeError) as cm:
        opt.set_value(10.0)
    assert cm.value.args == ("Option 'option_name' value must be a 'list', not 'float'",)

def test_default(xx):
    opt = config.ListOption("option_name", xx.ITEM_TYPE, "description",
                            default=xx.DEFAULT_OPT_VAL)
    assert opt.name == "option_name"
    assert opt.datatype == list
    assert opt.description == "description"
    assert not opt.required
    assert opt.default == xx.DEFAULT_OPT_VAL
    assert isinstance(opt.default, opt.datatype)
    assert opt.value == xx.DEFAULT_OPT_VAL
    assert isinstance(opt.value, opt.datatype)
    opt.validate()
    opt.load_config(xx.conf, PRESENT_S)
    assert opt.value == xx.PRESENT_VAL
    opt.clear()
    assert opt.value == opt.default
    opt.load_config(xx.conf, DEFAULT_S)
    assert opt.value == xx.DEFAULT_VAL
    opt.set_value(None)
    assert opt.value is None
    opt.load_config(xx.conf, ABSENT_S)
    assert opt.value == xx.DEFAULT_VAL
    opt.set_value(xx.NEW_VAL)
    assert opt.value == xx.NEW_VAL

def test_proto(xx, proto):
    opt = config.ListOption("option_name", xx.ITEM_TYPE, "description",
                            default=xx.DEFAULT_OPT_VAL)
    proto_value = xx.PROTO_VALUE
    opt.set_value(proto_value)
    proto.options["option_name"].as_string = xx.PROTO_VALUE_STR
    proto_dump = str(proto)
    opt.load_proto(proto)
    assert opt.value == proto_value
    assert isinstance(opt.value, opt.datatype)
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

def test_get_config(xx):
    opt = config.ListOption("option_name", xx.ITEM_TYPE, "description",
                            default=xx.DEFAULT_OPT_VAL)
    lines = f"""; description
; Type: list [{xx.TYPE_NAMES}]
;option_name = {xx.DEFAULT_PRINT}
"""
    assert opt.get_config() == lines
    lines = f"""; description
; Type: list [{xx.TYPE_NAMES}]
option_name = {xx.NEW_PRINT}
"""
    opt.set_value(xx.NEW_VAL)
    assert opt.get_config() == lines
    lines = f"""; description
; Type: list [{xx.TYPE_NAMES}]
option_name = <UNDEFINED>
"""
    opt.set_value(None)
    assert opt.get_config() == lines
    assert opt.get_formatted() == "<UNDEFINED>"
    lines = f"""; description
; Type: list [{xx.TYPE_NAMES}]
option_name = {xx.LONG_PRINT}
"""
    opt.set_value(xx.LONG_VAL)
    assert opt.get_config() == lines
