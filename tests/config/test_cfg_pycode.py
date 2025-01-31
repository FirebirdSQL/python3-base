# SPDX-FileCopyrightText: 2019-present The Firebird Projects <www.firebirdsql.org>
#
# SPDX-License-Identifier: MIT
#
# PROGRAM/MODULE: firebird-base
# FILE:           tests/config/test_cfg_pycode.py
# DESCRIPTION:    Tests for firebird.base.config PyCodeOption
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

import io

import pytest

from firebird.base import config
from firebird.base.types import Error, PyCode

DEFAULT_S = "DEFAULT"
PRESENT_S = "present"
ABSENT_S = "absent"
BAD_S = "bad_value"
EMPTY_S = "empty"

DEFAULT_VAL = PyCode('print("Default value")')
PRESENT_VAL = PyCode('\ndef pp(value):\n    print("Value:",value,file=output)\n\nfor i in [1,2,3]:\n    pp(i)')
DEFAULT_OPT_VAL = PyCode("DEFAULT")
NEW_VAL = PyCode('print("NEW value")')

@pytest.fixture
def conf(base_conf):
    """Returns configparser initialized with data.
    """
    conf_str = """[%(DEFAULT)s]
option_name = print("Default value")
[%(PRESENT)s]
option_name =
    | def pp(value):
    |     print("Value:",value,file=output)
    |
    | for i in [1,2,3]:
    |     pp(i)
[%(ABSENT)s]
[%(BAD)s]
option_name = This is not a valid Python code block
"""
    base_conf.read_string(conf_str % {"DEFAULT": DEFAULT_S, "PRESENT": PRESENT_S,
                                      "ABSENT": ABSENT_S, "BAD": BAD_S, "EMPTY": EMPTY_S,})
    return base_conf

def test_simple(conf):
    opt = config.PyCodeOption("option_name", "description")
    assert opt.name == "option_name"
    assert opt.datatype == PyCode
    assert opt.description == "description"
    assert not opt.required
    assert opt.default is None
    assert opt.value is None
    opt.validate()
    opt.load_config(conf, PRESENT_S)
    assert opt.value == PRESENT_VAL
    assert opt.get_as_str() == '\ndef pp(value):\n    print("Value:",value,file=output)\n\nfor i in [1,2,3]:\n    pp(i)'
    assert isinstance(opt.value, opt.datatype)
    # Check expression code
    out = io.StringIO()
    exec(opt.value.code, {"output": out})
    assert out.getvalue() == "Value: 1\nValue: 2\nValue: 3\n"
    #
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
    opt = config.PyCodeOption("option_name", "description", required=True)
    assert opt.name == "option_name"
    assert opt.datatype == PyCode
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
    opt = config.PyCodeOption("option_name", "description")
    with pytest.raises(SyntaxError) as cm:
        opt.load_config(conf, BAD_S)
    assert cm.value.args == ("invalid syntax", ("PyCode", 1, 15, "This is not a valid Python code block\n", 1, 20))
    with pytest.raises(TypeError) as cm:
        opt.set_value(10.0)
    assert cm.value.args == ("Option 'option_name' value must be a 'PyCode', not 'float'",)

def test_default(conf):
    opt = config.PyCodeOption("option_name", "description", default=DEFAULT_OPT_VAL)
    assert opt.name == "option_name"
    assert opt.datatype == PyCode
    assert opt.description == "description"
    assert not opt.required
    assert opt.default == DEFAULT_OPT_VAL
    assert isinstance(opt.default, opt.datatype)
    assert opt.value == DEFAULT_OPT_VAL
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
    opt = config.PyCodeOption("option_name", "description")
    proto_value = PyCode("proto_value")
    opt.set_value(proto_value)
    proto.options["option_name"].as_string = proto_value
    proto_dump = str(proto)
    opt.load_proto(proto)
    assert opt.value == proto_value
    assert isinstance(opt.value, opt.datatype)
    proto.Clear()
    assert "option_name" not in proto.options
    opt.save_proto(proto)
    assert "option_name" in proto.options
    assert str(proto) == proto_dump
    proto.Clear()
    opt.clear()
    opt.save_proto(proto)
    assert "option_name" not in proto.options

def test_get_config(conf):
    opt = config.PyCodeOption("option_name", "description", default=DEFAULT_OPT_VAL)
    lines = """; description
; Type: PyCode
;option_name = DEFAULT
"""
    assert opt.get_config() == lines
    lines = """; description
; Type: PyCode
option_name =
   | def pp(value):
   |     print("Value:",value,file=output)
   |
   | for i in [1,2,3]:
   |     pp(i)"""
    opt.set_value(PRESENT_VAL)
    assert "\n".join(x.rstrip() for x in opt.get_config().splitlines()) == lines
    lines = """; description
; Type: PyCode
option_name = <UNDEFINED>
"""
    opt.set_value(None)
    assert opt.get_config() == lines
    assert opt.get_formatted() == "<UNDEFINED>"
