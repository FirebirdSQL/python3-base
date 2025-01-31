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

from __future__ import annotations

import pytest

from firebird.base import config
from firebird.base.types import MIME, Error

DEFAULT_S = "DEFAULT"
PRESENT_S = "present"
ABSENT_S = "absent"
BAD_S = "bad_value"
EMPTY_S = "empty"

PRESENT_VAL = MIME("text/plain;charset=utf-8")
PRESENT_TYPE = "text/plain"
PRESENT_PARS = {"charset": "utf-8"}
DEFAULT_VAL = MIME("application/octet-stream")
DEFAULT_TYPE = "application/octet-stream"
DEFAULT_PARS = {}
DEFAULT_OPT_VAL = MIME("text/plain;charset=win1250")
DEFAULT_OPT_TYPE = "text/plain"
DEFAULT_OPT_PARS = {"charset": "win1250"}
NEW_VAL = MIME("application/x.fb.proto;type=firebird.butler.fbsd.ErrorDescription")
NEW_TYPE = "application/x.fb.proto"
NEW_PARS = {"type": "firebird.butler.fbsd.ErrorDescription"}

@pytest.fixture
def conf(base_conf):
    """Returns configparser initialized with data.
    """
    conf_str = """[%(DEFAULT)s]
option_name = application/octet-stream
[%(PRESENT)s]
option_name = text/plain;charset=utf-8
[%(ABSENT)s]
[%(BAD)s]
option_name = wrong mime specification
[unsupported_mime_type]
option_name = model/vml
[bad_mime_parameters]
option_name = text/plain;charset/utf-8
"""
    base_conf.read_string(conf_str % {"DEFAULT": DEFAULT_S, "PRESENT": PRESENT_S,
                                      "ABSENT": ABSENT_S, "BAD": BAD_S, "EMPTY": EMPTY_S,})
    return base_conf

def test_simple(conf):
    opt: config.MIMEOption = config.MIMEOption("option_name", "description")
    assert opt.name == "option_name"
    assert opt.datatype == MIME
    assert opt.description == "description"
    assert not opt.required
    assert opt.default is None
    assert opt.value is None
    opt.validate()
    opt.load_config(conf, PRESENT_S)
    assert opt.value == PRESENT_VAL
    assert opt.value == "text/plain;charset=utf-8"
    assert opt.get_as_str() == PRESENT_VAL
    assert isinstance(opt.value, opt.datatype)
    assert opt.value.mime_type == PRESENT_TYPE
    assert opt.value.params == PRESENT_PARS
    assert opt.value.params.get("charset") == "utf-8"
    opt.clear()
    assert opt.value is None
    opt.load_config(conf, DEFAULT_S)
    assert opt.value == DEFAULT_VAL
    assert isinstance(opt.value, opt.datatype)
    assert opt.value.mime_type == DEFAULT_TYPE
    assert opt.value.params == DEFAULT_PARS
    opt.set_value(None)
    assert opt.value is None
    opt.load_config(conf, ABSENT_S)
    assert opt.value == DEFAULT_VAL
    assert isinstance(opt.value, opt.datatype)
    assert opt.value.mime_type == DEFAULT_TYPE
    assert opt.value.params == DEFAULT_PARS
    opt.set_value(NEW_VAL)
    assert opt.value == NEW_VAL
    assert isinstance(opt.value, opt.datatype)
    assert opt.value.mime_type == NEW_TYPE
    assert opt.value.params == NEW_PARS

def test_required(conf):
    opt = config.MIMEOption("option_name", "description", required=True)
    assert opt.name == "option_name"
    assert opt.datatype == MIME
    assert opt.description == "description"
    assert opt.required
    assert opt.default is None
    assert opt.value is None
    with pytest.raises(Error) as cm:
        opt.validate()
    assert cm.value.args == ("Missing value for required option 'option_name'",)
    opt.load_config(conf, PRESENT_S)
    assert opt.value == PRESENT_VAL
    assert opt.value.mime_type == PRESENT_TYPE
    assert opt.value.params == PRESENT_PARS
    opt.validate()
    opt.clear()
    assert opt.value is None
    opt.load_config(conf, DEFAULT_S)
    assert opt.value == DEFAULT_VAL
    assert opt.value.mime_type == DEFAULT_TYPE
    assert opt.value.params == DEFAULT_PARS
    with pytest.raises(ValueError) as cm:
        opt.set_value(None)
    assert cm.value.args == ("Value is required for option 'option_name'.",)
    opt.load_config(conf, ABSENT_S)
    assert opt.value == DEFAULT_VAL
    assert opt.value.mime_type == DEFAULT_TYPE
    assert opt.value.params == DEFAULT_PARS
    opt.set_value(NEW_VAL)
    assert opt.value == NEW_VAL
    assert opt.value.mime_type == NEW_TYPE
    assert opt.value.params == NEW_PARS

def test_bad_value(conf):
    opt: config.MIMEOption = config.MIMEOption("option_name", "description")
    with pytest.raises(ValueError) as cm:
        opt.load_config(conf, BAD_S)
    assert cm.value.args == ("MIME type specification must be 'type/subtype[;param=value;...]'",)
    with pytest.raises(ValueError) as cm:
        opt.load_config(conf, "unsupported_mime_type")
    assert cm.value.args == ("MIME type 'model' not supported",)
    with pytest.raises(ValueError) as cm:
        opt.load_config(conf, "bad_mime_parameters")
    assert cm.value.args == ("Wrong specification of MIME type parameters",)
    with pytest.raises(TypeError) as cm:
        opt.set_value(10.0)
    assert cm.value.args == ("Option 'option_name' value must be a 'MIME', not 'float'",)

def test_default(conf):
    opt = config.MIMEOption("option_name", "description", default=DEFAULT_OPT_VAL)
    assert opt.name == "option_name"
    assert opt.datatype == MIME
    assert opt.description == "description"
    assert not opt.required
    assert str(opt.default) == str(DEFAULT_OPT_VAL)
    assert isinstance(opt.default, opt.datatype)
    assert str(opt.value) == str(DEFAULT_OPT_VAL)
    assert isinstance(opt.value, opt.datatype)
    assert opt.value.mime_type == DEFAULT_OPT_TYPE
    assert opt.value.params == DEFAULT_OPT_PARS
    opt.validate()
    opt.load_config(conf, PRESENT_S)
    assert opt.get_as_str() == str(PRESENT_VAL)
    assert opt.value.mime_type == PRESENT_TYPE
    assert opt.value.params == PRESENT_PARS
    opt.clear()
    assert opt.value == opt.default
    opt.load_config(conf, DEFAULT_S)
    assert opt.value == DEFAULT_VAL
    assert opt.value.mime_type == DEFAULT_TYPE
    assert opt.value.params == DEFAULT_PARS
    opt.set_value(None)
    assert opt.value is None
    opt.load_config(conf, ABSENT_S)
    assert opt.value == DEFAULT_VAL
    assert opt.value.mime_type == DEFAULT_TYPE
    assert opt.value.params == DEFAULT_PARS
    opt.set_value(NEW_VAL)
    assert opt.value == NEW_VAL
    assert opt.value.mime_type == NEW_TYPE
    assert opt.value.params == NEW_PARS

def test_proto(conf, proto):
    opt = config.MIMEOption("option_name", "description", default=DEFAULT_OPT_VAL)
    proto_value = NEW_VAL
    opt.set_value(proto_value)
    proto.options["option_name"].as_string = proto_value
    proto_dump = str(proto)
    opt.load_proto(proto)
    assert opt.value == proto_value
    assert opt.value.mime_type == NEW_TYPE
    assert opt.value.params == NEW_PARS
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

def test_get_config(conf):
    opt = config.MIMEOption("option_name", "description", default=DEFAULT_OPT_VAL)
    lines = """; description
; Type: MIME
;option_name = text/plain;charset=win1250
"""
    assert opt.get_config() == lines
    lines = """; description
; Type: MIME
option_name = application/x.fb.proto;type=firebird.butler.fbsd.ErrorDescription
"""
    opt.set_value(NEW_VAL)
    assert opt.get_config() == lines
    lines = """; description
; Type: MIME
option_name = <UNDEFINED>
"""
    opt.set_value(None)
    assert opt.get_config() == lines
