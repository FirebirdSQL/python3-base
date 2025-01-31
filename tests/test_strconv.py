# SPDX-FileCopyrightText: 2019-present The Firebird Projects <www.firebirdsql.org>
#
# SPDX-License-Identifier: MIT
#
#   PROGRAM/MODULE: firebird-base
#   FILE:           test/test_strconv.py
#   DESCRIPTION:    Tests for firebird.base.strconv
#   CREATED:        21.1.2025
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
from enum import Enum, IntEnum, IntFlag
from uuid import NAMESPACE_OID, UUID, uuid5

import pytest

from firebird.base.strconv import *
from firebird.base.trace import Distinct, TraceFlag
from firebird.base.types import MIME, ByteOrder, PyExpr, ZMQAddress, ZMQDomain

## TODO:
#
# - register_convertor
# - register_class
# - update_convertor

def test_any2str():
    assert any2str(1) == "1"

def test_str2any():
    assert str2any(int, "1") == 1

def test_builtin_convertors():
    assert has_convertor(str)
    assert has_convertor(int)
    assert has_convertor(float)
    assert has_convertor(complex)
    assert has_convertor(bool)
    assert has_convertor(Decimal)
    assert has_convertor(UUID)
    assert has_convertor(MIME)
    assert has_convertor(ZMQAddress)
    assert has_convertor(Enum)
    assert has_convertor(IntEnum)
    assert has_convertor(IntFlag)

def test_has_convertor():
    assert not has_convertor(Distinct)
    assert has_convertor(PyExpr) # It's descendant from 'str'

def test_builtin_str():
    value = "test value"
    assert convert_to_str(value) == value
    assert convert_from_str(str, value) == value

def test_builtin_int():
    value = 42
    value_str = "42"
    assert convert_to_str(value) == value_str
    assert convert_from_str(int, value_str) == value

def test_builtin_bool():
    assert convert_to_str(True) == "yes"
    assert convert_to_str(False) == "no"
    assert convert_from_str(bool, "yes")
    assert convert_from_str(bool, "True")
    assert convert_from_str(bool, "y")
    assert convert_from_str(bool, "on")
    assert convert_from_str(bool, "1")
    assert not convert_from_str(bool, "no")
    assert not convert_from_str(bool, "False")
    assert not convert_from_str(bool, "n")
    assert not convert_from_str(bool, "off")
    assert not convert_from_str(bool, "0")

def test_builtin_float():
    value = 42.5
    value_str = "42.5"
    assert convert_to_str(value) == value_str
    assert convert_from_str(float, value_str) == value

def test_builtin_complex():
    value = complex(42.5)
    value_str = "(42.5+0j)"
    assert convert_to_str(value) == value_str
    assert convert_from_str(complex, value_str) == value

def test_builtin_decimal():
    value = Decimal("42.123456789")
    value_str = "42.123456789"
    assert convert_to_str(value) == value_str
    assert convert_from_str(Decimal, value_str) == value

def test_builtin_uuid():
    value = uuid5(NAMESPACE_OID, "firebird.base.strconv")
    value_str = "2ff58c2e-5cfd-50f1-8767-c9e405d7d62e"
    assert convert_to_str(value) == value_str
    assert convert_from_str(UUID, value_str) == value

def test_builtin_mime():
    value = MIME("text/plain")
    value_str = "text/plain"
    assert convert_to_str(value) == value_str
    assert convert_from_str(MIME, value_str) == value

def test_builtin_zmqaddress():
    value = ZMQAddress("tcp://192.168.0.1:8080")
    value_str = "tcp://192.168.0.1:8080"
    assert convert_to_str(value) == value_str
    assert convert_from_str(ZMQAddress, value_str) == value

def test_builtin_enum():
    value = ByteOrder.BIG
    value_str = "BIG"
    assert convert_to_str(value) == value_str
    assert convert_from_str(ByteOrder, value_str) == value

def test_builtin_intenum():
    value = ZMQDomain.LOCAL
    value_str = "LOCAL"
    assert convert_to_str(value) == value_str
    assert convert_from_str(ZMQDomain, value_str) == value

def test_builtin_intflag():
    data = [(TraceFlag.ACTIVE, "ACTIVE"), (TraceFlag.ACTIVE | TraceFlag.FAIL, "ACTIVE|FAIL")]
    for value, value_str in data:
        assert convert_to_str(value) == value_str
        assert convert_from_str(TraceFlag, value_str) == value

def test_get_convertor():
    assert isinstance(get_convertor(int), Convertor)
    # Not registered
    with pytest.raises(TypeError) as cm:
        get_convertor(Distinct)
    assert cm.value.args == ("Type 'Distinct' has no Convertor",)
    # Descendant from registered
    assert get_convertor(PyExpr).cls == str
    # Type by name
    assert get_convertor("MIME").cls == MIME
    # Type by full name
    assert get_convertor("firebird.base.types.MIME").cls == MIME

def test_update_convertor():
    conv = get_convertor(int)
    to_str = conv.to_str
    from_str = conv.from_str
    try:
        update_convertor(int, to_str=lambda x: "foo", from_str=lambda c, v: "baz")
        assert convert_to_str(42) == "foo"
        assert convert_from_str(int, "bar") == "baz"
    finally:
        update_convertor(int, to_str=to_str, from_str=from_str)

def test_convertor_names():
    c = get_convertor(MIME)
    assert c.name == "MIME"
    assert c.full_name == "firebird.base.types.MIME"

def test_register_class():
    assert not has_convertor("PyExpr")
    register_class(PyExpr)
    assert has_convertor("PyExpr")
    assert get_convertor("PyExpr").cls == str
    with pytest.raises(TypeError) as cm:
        register_class(PyExpr)
    assert cm.value.args == ("Class 'PyExpr' already registered as '<class 'firebird.base.types.PyExpr'>'",)
