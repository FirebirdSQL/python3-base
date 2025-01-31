# SPDX-FileCopyrightText: 2020-present The Firebird Projects <www.firebirdsql.org>
#
# SPDX-License-Identifier: MIT
#
#   PROGRAM/MODULE: firebird-base
#   FILE:           tests/test_types.py
#   DESCRIPTION:    Unit tests for firebird.base.types
#   CREATED:        14.5.2020
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
# Copyright (c) 2020 Firebird Project (www.firebirdsql.org)
# All Rights Reserved.
#
# Contributor(s): Pavel Císař (original code)
#                 ______________________________________.

from __future__ import annotations

import io
from dataclasses import dataclass

import pytest

from firebird.base.types import *

ns = {}

class A(type):
    """Test metaclass
    """
    attr_a: int = "A"
    def __call__(cls: Type, *args, **kwargs):
        ns["A"] = cls.attr_a
        return super().__call__(*args, **kwargs)

class B(type):
    """Test metaclass
    """
    attr_b: int = "B"
    def __call__(cls: Type, *args, **kwargs):
        ns["B"] = cls.attr_b
        return super().__call__(*args, **kwargs)

class AA(metaclass=A):pass

class BB(metaclass=B):pass

class CC(AA, BB, metaclass=conjunctive): pass

class ValueHolder:
    "Simple values holding object"

def func(): pass

def test_exceptions():
    "Test exceptions"
    e = Error("Message", code=1, subject=ns)
    assert e.args == ("Message",)
    assert e.code == 1
    assert e.subject is ns
    assert e.other_attr is None
    with pytest.raises(AttributeError):
        _ = e.__notes__

def test_conjunctive():
    "Test Conjunctive metaclass"
    _ = AA()
    assert ns == {"A": "A"}
    ns.clear()
    _ = BB()
    assert ns == {"B": "B"}
    ns.clear()
    _ = CC()
    assert ns == {"A": "A", "B": "B"}

def test_singletons():
    "Test Singletons"
    class MySingleton(Singleton):
        pass

    class MyOtherSingleton(MySingleton):
        pass
    #
    s = MySingleton()
    assert s is MySingleton()
    os = MyOtherSingleton()
    assert os is MyOtherSingleton()
    assert s is not os

def test_sentinel():
    "Test Sentinel"
    assert UNKNOWN.name == "UNKNOWN"
    assert str(UNKNOWN) == "UNKNOWN"
    assert repr(UNKNOWN) == "Sentinel('UNKNOWN')"
    assert UNKNOWN.instances == {"DEFAULT": DEFAULT,
                                 "INFINITY": INFINITY,
                                 "UNLIMITED": UNLIMITED,
                                 "UNKNOWN": UNKNOWN,
                                 "NOT_FOUND": NOT_FOUND,
                                 "UNDEFINED": UNDEFINED,
                                 "ANY": ANY,
                                 "ALL": ALL,
                                 "SUSPEND": SUSPEND,
                                 "RESUME": RESUME,
                                 "STOP": STOP,
                                 }
    for name, sentinel in Sentinel.instances.items():
        assert sentinel == Sentinel(name)
    assert "TEST-SENTINEL" not in Sentinel.instances
    Sentinel("TEST-SENTINEL")
    assert "TEST-SENTINEL" in Sentinel.instances

def test_distinct():
    "Test Distinct"
    @dataclass
    class MyDistinct(Distinct):
        key_1: int
        key_2: str
        payload: str
        def get_key(self):
            if not hasattr(self, "__key__"):
                self.__key__ = (self.key_1, self.key_2)
            return self.__key__

    d = MyDistinct(1, "A", "1A")
    assert not hasattr(d, "__key__")
    assert d.get_key() == (1, "A")
    assert hasattr(d, "__key__")
    d.key_2 = "B"
    assert d.get_key() == (1, "A")

def test_cached_distinct():
    "Test CachedDistinct"
    class MyCachedDistinct(CachedDistinct):
        def __init__(self, key_1, key_2, payload):
            self.key_1 = key_1
            self.key_2 = key_2
            self.payload = payload
        @classmethod
        def extract_key(cls, *args, **kwargs) -> t.Hashable:
            return (args[0], args[1])
        def get_key(self) -> t.Hashable:
            return (self.key_1, self.key_2)
    #
    assert hasattr(MyCachedDistinct, "_instances_")
    cd_1 = MyCachedDistinct(1, ANY, "type 1A")
    assert cd_1 is MyCachedDistinct(1, ANY, "type 1A")
    assert cd_1 is not MyCachedDistinct(2, ANY, "type 2A")
    assert hasattr(MyCachedDistinct, "_instances_")
    assert len(MyCachedDistinct._instances_) == 1
    cd_2 = MyCachedDistinct(2, ANY, "type 2A")
    assert len(MyCachedDistinct._instances_) == 2
    temp = MyCachedDistinct(2, ANY, "type 2A")
    assert len(MyCachedDistinct._instances_) == 2
    del cd_1, cd_2, temp
    assert len(MyCachedDistinct._instances_) == 0

def test_zmqaddress():
    "Test ZMQAddress"
    addr = ZMQAddress("ipc://@my-address")
    assert addr.address == "@my-address"
    assert addr.protocol == ZMQTransport.IPC
    assert addr.domain == ZMQDomain.NODE
    assert repr(addr) == "ZMQAddress('ipc://@my-address')"
    #
    addr = ZMQAddress("inproc://my-address")
    assert addr.address == "my-address"
    assert addr.protocol == ZMQTransport.INPROC
    assert addr.domain == ZMQDomain.LOCAL
    #
    addr = ZMQAddress("tcp://127.0.0.1:*")
    assert addr.address == "127.0.0.1:*"
    assert addr.protocol == ZMQTransport.TCP
    assert addr.domain == ZMQDomain.NODE
    #
    addr = ZMQAddress("tcp://192.168.0.1:8001")
    assert addr.address == "192.168.0.1:8001"
    assert addr.protocol == ZMQTransport.TCP
    assert addr.domain == ZMQDomain.NETWORK
    #
    addr = ZMQAddress("pgm://192.168.0.1:8001")
    assert addr.address == "192.168.0.1:8001"
    assert addr.protocol == ZMQTransport.PGM
    assert addr.domain == ZMQDomain.NETWORK
    # Bytes
    addr = ZMQAddress(b"ipc://@my-address")
    assert addr.address == "@my-address"
    assert addr.protocol == ZMQTransport.IPC
    assert addr.domain == ZMQDomain.NODE
    # Bad ZMQ address
    with pytest.raises(ValueError) as cm:
        addr = ZMQAddress("onion://@my-address")
    assert cm.value.args == ("Unknown protocol 'onion'",)
    with pytest.raises(ValueError) as cm:
        addr = ZMQAddress("192.168.0.1:8001")
    assert cm.value.args == ("Protocol specification required",)
    with pytest.raises(ValueError) as cm:
        addr = ZMQAddress("unknown://192.168.0.1:8001")
    assert cm.value.args == ("Invalid protocol",)

def test_MIME():
    "Test MIME"
    mime = MIME("text/plain;charset=utf-8")
    assert mime.mime_type == "text/plain"
    assert mime.type == "text"
    assert mime.subtype == "plain"
    assert mime.params == {"charset": "utf-8",}
    assert repr(mime) == "MIME('text/plain;charset=utf-8')"
    #
    mime = MIME("text/plain")
    assert mime.mime_type == "text/plain"
    assert mime.type == "text"
    assert mime.subtype == "plain"
    assert mime.params == {}
    #
    # Bad MIME type
    with pytest.raises(ValueError) as cm:
        mime = MIME("")
    assert cm.value.args == ("MIME type specification must be 'type/subtype[;param=value;...]'",)
    with pytest.raises(ValueError) as cm:
        mime = MIME("model/airplane")
    assert cm.value.args == ("MIME type 'model' not supported",)
    with pytest.raises(ValueError) as cm:
        mime = MIME("text/plain;charset:utf-8")
    assert cm.value.args == ("Wrong specification of MIME type parameters",)

def test_PyExpr():
    "Test PyExpr"
    code_type = type(compile("1+1", "none", "eval"))
    expr_str = "this.value in [1, 2, 3]"
    expr = PyExpr(expr_str)
    assert expr == expr_str
    assert repr(expr) == f"PyExpr('{expr_str}')"
    obj = ValueHolder()
    obj.value = 1
    assert type(expr) == PyExpr
    assert type(expr.expr) == code_type
    assert type(expr.get_callable()) == type(func)
    # Evaluation
    fce = expr.get_callable("this", {"some_name": "value"})
    assert eval(expr, None, {"this": obj})
    assert eval(expr.expr, None, {"this": obj})
    assert fce(obj)
    obj.value = 4
    assert not eval(expr, None, {"this": obj})
    assert not eval(expr.expr, None, {"this": obj})
    assert not fce(obj)

def test_PyCode():
    "Test PyCode"
    code_str = """def pp(value):
    print("Value:",value,file=output)

for i in [1,2,3]:
    pp(i)
"""
    code = PyCode(code_str)
    assert code == code_str
    out = io.StringIO()
    exec(code.code, {"output": out})
    assert out.getvalue() == "Value: 1\nValue: 2\nValue: 3\n"

def test_PyCallable():
    "Test PyCode"
    func_str = """
def foo(value: int) -> int:
    return value * 5
"""
    class_str = """
class Bar():
    def __init__(self, value: int):
        self.value = value
"""
    with pytest.raises(ValueError) as cm:
        _ = PyCallable("some text")
    #
    code = PyCallable(func_str)
    assert code == func_str
    assert code.name == "foo"
    assert code(1) == 5
    #
    cls = PyCallable(class_str)
    assert cls == class_str
    assert cls.name == "Bar"
    obj = cls(1)
    assert obj.__class__.__name__ == "Bar"
    assert obj.value == 1

def test_load():
    "Test load function"
    obj = load("firebird.base.types:conjunctive")
    assert obj is conjunctive
    fce = load("colorsys:rgb_to_hsv")
    assert fce(0.2, 0.4, 0.4) == (0.5, 0.5, 0.4)
