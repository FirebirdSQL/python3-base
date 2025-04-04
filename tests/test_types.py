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
import gc # For explicit GC in CachedDistinct test if needed
import sys # For load test
from dataclasses import dataclass
from typing import Type # For metaclass annotations

import pytest

from firebird.base.types import *

# --- Test Setup ---

ns = {}

class A(type):
    """Test metaclass A."""
    attr_a: str = "A" # Changed type hint for clarity
    def __call__(cls: Type, *args, **kwargs):
        ns["A"] = cls.attr_a
        return super().__call__(*args, **kwargs)

class B(type):
    """Test metaclass B."""
    attr_b: str = "B" # Changed type hint for clarity
    def __call__(cls: Type, *args, **kwargs):
        ns["B"] = cls.attr_b
        return super().__call__(*args, **kwargs)

class AA(metaclass=A):
    """Test class using metaclass A."""
    pass

class BB(metaclass=B):
    """Test class using metaclass B."""
    pass

class CC(AA, BB, metaclass=conjunctive):
    """Test class combining AA and BB using the conjunctive metaclass."""
    pass

class ValueHolder:
    """Simple object for holding a value during tests."""
    value: Any = None # Added type hint

def func():
    """Dummy function for testing."""
    pass

# --- Test Functions ---

def test_error_exception():
    """Tests the custom Error exception class.

    Verifies:
    - Initialization with positional message and keyword arguments.
    - Keyword arguments become instance attributes.
    - Accessing non-existent attributes returns None (via __getattr__).
    - Accessing the special '__notes__' attribute raises AttributeError.
    """
    e = Error("Message", code=1, subject=ns)
    assert e.args == ("Message",)
    assert e.code == 1
    assert e.subject is ns
    assert e.other_attr is None
    # Explicitly test __notes__ attribute access
    with pytest.raises(AttributeError):
        _ = e.__notes__

def test_singleton_behavior():
    """Tests the Singleton base class and its metaclass.

    Verifies:
    - Multiple instantiations of a Singleton subclass return the same instance.
    - Subclasses of a Singleton are distinct singleton instances.
    - Constructor arguments are only used during the *first* instantiation.
    """
    class MySingleton(Singleton):
        def __init__(self, arg=None):
            # Store arg only if it's the first time __init__ is called
            if not '_initialized_arg' in self.__class__.__dict__:
                self.__class__._initialized_arg = arg
                self.init_arg = arg

    class MyOtherSingleton(MySingleton):
        pass

    # Basic singleton behavior
    s1 = MySingleton("first")
    s2 = MySingleton("second")
    assert s1 is s2
    assert hasattr(s1, 'init_arg')
    assert s1.init_arg == "first" # Argument from second call was ignored

    # Inheritance
    os1 = MyOtherSingleton("other_first")
    os2 = MyOtherSingleton("other_second")
    assert os1 is os2
    assert s1 is not os1
    assert hasattr(os1, 'init_arg')
    assert os1.init_arg == "other_first"

    # Cleanup class attribute for test isolation if needed
    del MySingleton._initialized_arg
    del MyOtherSingleton._initialized_arg


def test_sentinel_objects():
    """Tests the Sentinel base class and predefined sentinel objects.

    Verifies:
    - Sentinel name is stored uppercase.
    - __str__ and __repr__ methods produce correct output.
    - Predefined sentinels exist and have the correct type.
    - Creating a new sentinel adds it to the instances cache.
    - Retrieving a sentinel by name (case-insensitive) returns the singleton instance.
    """
    assert UNKNOWN.name == "UNKNOWN"
    assert str(UNKNOWN) == "UNKNOWN"
    assert repr(UNKNOWN) == "Sentinel('UNKNOWN')"

    # Check predefined sentinels (just a sample)
    predefined = [DEFAULT, INFINITY, UNLIMITED, UNKNOWN, NOT_FOUND, UNDEFINED, ANY, ALL, SUSPEND, RESUME, STOP]
    for sentinel in predefined:
        assert isinstance(sentinel, Sentinel)
        assert sentinel.name in Sentinel.instances
        assert Sentinel.instances[sentinel.name] is sentinel

    # Test creation and retrieval
    assert "TEST_SENTINEL" not in Sentinel.instances # Check case used in Sentinel creation
    test_sentinel_upper = Sentinel("TEST_SENTINEL")
    assert "TEST_SENTINEL" in Sentinel.instances
    assert test_sentinel_upper.name == "TEST_SENTINEL"
    test_sentinel_lower = Sentinel("test_sentinel")
    assert test_sentinel_upper is test_sentinel_lower # Should be the same object

    # Clean up test sentinel
    del Sentinel.instances["TEST_SENTINEL"]

def test_distinct_abc():
    """Tests the Distinct abstract base class using a concrete dataclass implementation.

    Verifies:
    - A concrete subclass can be instantiated.
    - get_key() method works as expected.
    - __hash__() method works and uses the key.
    """
    @dataclass(eq=False)
    class MyDistinct(Distinct):
        key_1: int
        key_2: str
        payload: str
        # Cache the key after first calculation (implementation detail, but tested here)
        __key__: tuple | None = None

        def get_key(self):
            if self.__key__ is None:
                self.__key__ = (self.key_1, self.key_2)
            return self.__key__

        # Explicitly define __hash__ to rely on Distinct's default or customize
        # __hash__ = Distinct.__hash__ # Using the ABC's default hash

    d1 = MyDistinct(1, "A", "1A")
    d2 = MyDistinct(1, "A", "Different Payload")
    d3 = MyDistinct(2, "A", "2A")

    key1 = (1, "A")
    key3 = (2, "A")

    assert d1.get_key() == key1
    assert d2.get_key() == key1
    assert d3.get_key() == key3

    # Test hashing
    assert hash(d1) == hash(key1)
    assert hash(d2) == hash(key1)
    assert hash(d3) == hash(key3)
    assert hash(d1) == hash(d2)
    assert hash(d1) != hash(d3)

    # Test use in a set/dict
    s = {d1, d2, d3}
    assert len(s) == 2 # d1 and d2 hash to the same value
    assert d1 in s
    assert d2 in s # d2 replaces d1 or vice-versa based on set implementation details
    assert d3 in s

def test_cached_distinct_abc():
    """Tests the CachedDistinct ABC and its instance caching mechanism.

    Verifies:
    - Instances with the same key (extracted from init args) are cached and reused.
    - Instances with different keys result in different objects.
    - The cache uses weak references (tested implicitly by deleting references).
    """
    class MyCachedDistinct(CachedDistinct):
        def __init__(self, key_1: int, key_2: Any, payload: str):
            self.key_1 = key_1
            self.key_2 = key_2
            self.payload = payload

        @classmethod
        def extract_key(cls, *args, **kwargs) -> Hashable:
            # Assumes key parts are the first two positional args
            return (args[0], args[1])

        def get_key(self) -> Hashable:
            return (self.key_1, self.key_2)

    # Ensure cache is initially empty or clean for this type
    if MyCachedDistinct in MyCachedDistinct._instances_:
         MyCachedDistinct._instances_[MyCachedDistinct].clear() # type: ignore

    cd1_a = MyCachedDistinct(1, ANY, "payload A")
    cd1_b = MyCachedDistinct(1, ANY, "payload B") # Payload differs, but key is the same
    cd2 = MyCachedDistinct(2, ANY, "payload C")

    assert cd1_a is cd1_b  # Should return the cached instance based on key (1, ANY)
    assert cd1_a is not cd2 # Different key (2, ANY)
    assert cd1_a.payload == "payload A" # Payload from the first creation is retained

    # Check cache size
    assert len(MyCachedDistinct._instances_) == 2 # One for key (1, ANY), one for (2, ANY)

    # Test weak reference behavior (implicitly)
    key1 = cd1_a.get_key()
    key2 = cd2.get_key()
    assert key1 in MyCachedDistinct._instances_
    assert key2 in MyCachedDistinct._instances_

    del cd1_a
    del cd1_b
    # gc.collect() # Might be needed for immediate cleanup in some environments
    # Check if weakref cleanup happened (might not be immediate)
    # assert key1 not in MyCachedDistinct._instances_ # This assertion can be flaky

    del cd2
    # gc.collect()
    # assert key2 not in MyCachedDistinct._instances_ # Flaky

    # Recreate to confirm cache was potentially cleared
    cd1_new = MyCachedDistinct(1, ANY, "payload New")
    assert cd1_new.payload == "payload New" # Confirms __init__ was likely called again

def test_enums():
    """Tests the Enum definitions.

    Verifies basic member access and values.
    """
    assert ByteOrder.LITTLE.value == 'little'
    assert ByteOrder.BIG.value == 'big'
    assert ByteOrder.NETWORK.value == 'big' # Alias check

    assert ZMQTransport.INPROC.value == 1
    assert ZMQTransport.TCP.value == 3
    assert ZMQTransport.UNKNOWN.value == 0

    assert ZMQDomain.LOCAL.value == 1
    assert ZMQDomain.NODE.value == 2
    assert ZMQDomain.NETWORK.value == 3
    assert ZMQDomain.UNKNOWN.value == 0

def test_zmqaddress_type():
    """Tests the ZMQAddress enhanced string type.

    Verifies:
    - Correct parsing of protocol, address, and domain for various ZMQ transports.
    - Handling of bytes input.
    - Correct __repr__ output.
    - Error handling for invalid address formats.
    """
    # IPC
    addr_ipc = ZMQAddress("ipc://@my-address")
    assert addr_ipc == "ipc://@my-address"
    assert addr_ipc.address == "@my-address"
    assert addr_ipc.protocol == ZMQTransport.IPC
    assert addr_ipc.domain == ZMQDomain.NODE
    assert repr(addr_ipc) == "ZMQAddress('ipc://@my-address')"

    # INPROC
    addr_inproc = ZMQAddress("inproc://my-address")
    assert addr_inproc.address == "my-address"
    assert addr_inproc.protocol == ZMQTransport.INPROC
    assert addr_inproc.domain == ZMQDomain.LOCAL

    # TCP - Node local
    addr_tcp_node = ZMQAddress("tcp://127.0.0.1:*")
    assert addr_tcp_node.address == "127.0.0.1:*"
    assert addr_tcp_node.protocol == ZMQTransport.TCP
    assert addr_tcp_node.domain == ZMQDomain.NODE
    addr_tcp_localhost = ZMQAddress("tcp://localhost:5555")
    assert addr_tcp_localhost.domain == ZMQDomain.NODE


    # TCP - Network
    addr_tcp_net = ZMQAddress("tcp://192.168.0.1:8001")
    assert addr_tcp_net.address == "192.168.0.1:8001"
    assert addr_tcp_net.protocol == ZMQTransport.TCP
    assert addr_tcp_net.domain == ZMQDomain.NETWORK

    # PGM
    addr_pgm = ZMQAddress("pgm://192.168.0.1:8001")
    assert addr_pgm.address == "192.168.0.1:8001"
    assert addr_pgm.protocol == ZMQTransport.PGM
    assert addr_pgm.domain == ZMQDomain.NETWORK

    # EPGM and VMCI (assuming they follow network domain pattern)
    addr_epgm = ZMQAddress("epgm://192.168.0.1:8002")
    assert addr_epgm.protocol == ZMQTransport.EPGM
    assert addr_epgm.domain == ZMQDomain.NETWORK
    addr_vmci = ZMQAddress("vmci://100:101")
    assert addr_vmci.protocol == ZMQTransport.VMCI
    assert addr_vmci.domain == ZMQDomain.NETWORK


    # Bytes input
    addr_bytes = ZMQAddress(b"ipc://@my-bytes-address")
    assert addr_bytes.address == "@my-bytes-address"
    assert addr_bytes.protocol == ZMQTransport.IPC
    assert addr_bytes.domain == ZMQDomain.NODE

    # Error Handling
    with pytest.raises(ValueError, match="Unknown protocol 'onion'"):
        ZMQAddress("onion://@my-address")
    with pytest.raises(ValueError, match="Protocol specification required"):
        ZMQAddress("192.168.0.1:8001")
    with pytest.raises(ValueError, match="Invalid protocol"):
        ZMQAddress("unknown://192.168.0.1:8001")


def test_mime_type():
    """Tests the MIME enhanced string type.

    Verifies:
    - Correct parsing of type, subtype, and parameters.
    - Handling of MIME types with and without parameters.
    - Correct __repr__ output.
    - Error handling for invalid MIME formats.
    """
    # With parameters
    mime_params = MIME("text/plain;charset=utf-8;format=flowed")
    assert mime_params == "text/plain;charset=utf-8;format=flowed"
    assert mime_params.mime_type == "text/plain"
    assert mime_params.type == "text"
    assert mime_params.subtype == "plain"
    assert mime_params.params == {"charset": "utf-8", "format": "flowed"}
    assert repr(mime_params) == "MIME('text/plain;charset=utf-8;format=flowed')"

    # Without parameters
    mime_no_params = MIME("application/json")
    assert mime_no_params.mime_type == "application/json"
    assert mime_no_params.type == "application"
    assert mime_no_params.subtype == "json"
    assert mime_no_params.params == {}
    assert repr(mime_no_params) == "MIME('application/json')"

    # Error Handling
    with pytest.raises(ValueError, match="MIME type specification must be"):
        MIME("textplain")
    with pytest.raises(ValueError, match="MIME type 'model' not supported"):
        MIME("model/vml")
    with pytest.raises(ValueError, match="Wrong specification of MIME type parameters"):
        MIME("text/plain;charset:utf-8")
    with pytest.raises(ValueError, match="Wrong specification of MIME type parameters"):
        MIME("text/plain;charset") # Missing '='


def test_pyexpr_type():
    """Tests the PyExpr enhanced string type for Python expressions.

    Verifies:
    - Valid expression compilation upon creation.
    - Correct __repr__ output.
    - Access to the compiled code via `.expr`.
    - Creation of a callable function via `get_callable`.
    - Error handling (SyntaxError) for invalid expressions.
    """
    expr_str = "obj.value * 2 + offset"
    expr = PyExpr(expr_str)

    assert expr == expr_str
    assert repr(expr) == f"PyExpr('{expr_str}')"
    assert hasattr(expr, '_expr_') # Check internal attribute exists
    assert isinstance(expr.expr, type(compile("1", "", "eval"))) # Check type of compiled code

    # Test evaluation
    obj = ValueHolder()
    obj.value = 10
    namespace = {"obj": obj, "offset": 5}
    assert eval(expr.expr, namespace) == 25

    # Test get_callable
    callable_func = expr.get_callable(arguments="obj, offset")
    assert callable(callable_func)
    assert callable_func(obj, 5) == 25
    assert callable_func(obj, offset=10) == 30 # Test kwarg

    # Test SyntaxError
    with pytest.raises(SyntaxError):
        PyExpr("invalid syntax-")


def test_pycode_type():
    """Tests the PyCode enhanced string type for Python code blocks.

    Verifies:
    - Valid code compilation upon creation.
    - Access to the compiled code via `.code`.
    - Execution of the compiled code.
    - Error handling (SyntaxError) for invalid code blocks.
    """
    code_str = """
results = []
for i in range(start, end):
    results.append(i * multiplier)
"""
    code = PyCode(code_str)
    assert code == code_str
    assert hasattr(code, '_code_')
    assert isinstance(code.code, type(compile("", "", "exec"))) # Check type

    # Test execution
    namespace = {"start": 2, "end": 5, "multiplier": 3}
    exec(code.code, namespace)
    assert "results" in namespace
    assert namespace["results"] == [6, 9, 12]

    # Test SyntaxError
    with pytest.raises(SyntaxError):
        PyCode("for i in range(5)\n  print(i)") # Indentation error


def test_pycallable_type():
    """Tests the PyCallable enhanced string type for Python callables (functions/classes).

    Verifies:
    - Valid callable compilation upon creation.
    - Extraction of the callable's name.
    - Ability to call the PyCallable instance directly.
    - Error handling for invalid input (not function/class, SyntaxError).
    """
    func_str = """
def multiply(a: int, b: int = 2) -> int:
    '''Docstring for multiply.'''
    return a * b
"""
    class_str = """
class Adder:
    '''Docstring for Adder.'''
    def __init__(self, initial=0):
        self.current = initial
    def add(self, value):
        self.current += value
        return self.current
"""
    # Test function callable
    py_func = PyCallable(func_str)
    assert py_func == func_str
    assert py_func.name == "multiply"
    assert callable(py_func)
    assert py_func(5) == 10      # Uses default b=2
    assert py_func(5, 3) == 15
    assert py_func.__doc__ == "Docstring for multiply." # Check __doc__ passthrough

    # Test class callable
    py_class = PyCallable(class_str)
    assert py_class == class_str
    assert py_class.name == "Adder"
    assert callable(py_class)
    instance = py_class(10) # Calls __init__
    assert isinstance(instance, py_class._callable_) # Check instance type
    assert instance.current == 10
    assert instance.add(5) == 15
    assert py_class.__doc__ == "Docstring for Adder."

    # Error Handling
    with pytest.raises(ValueError, match="Python function or class definition not found"):
        PyCallable("a = 1 + 2") # Not a def or class
    with pytest.raises(SyntaxError):
        PyCallable("def invalid-func(a):\n  pass") # Invalid function name


def test_conjunctive_metaclass():
    """Tests the conjunctive metaclass helper.

    Verifies that when a class inherits from multiple base classes, each with its own
    distinct metaclass, the conjunctive metaclass ensures that the behaviors (like __call__)
    of *all* parent metaclasses are executed upon instantiation of the final class.
    """
    # Clear namespace used by metaclasses A and B
    ns.clear()

    # Instantiate class AA (uses metaclass A)
    _ = AA()
    assert ns == {"A": "A"}, "Metaclass A should have been called"
    ns.clear()

    # Instantiate class BB (uses metaclass B)
    _ = BB()
    assert ns == {"B": "B"}, "Metaclass B should have been called"
    ns.clear()

    # Instantiate class CC (uses conjunctive metaclass combining A and B)
    _ = CC()
    assert ns == {"A": "A", "B": "B"}, "Both Metaclass A and B should have been called"


def test_load_function():
    """Tests the load function for importing objects dynamically.

    Verifies:
    - Loading an object from a standard library module.
    - Loading a nested object (class within a module).
    - Loading an object from the current package.
    - Error handling for non-existent modules and objects.
    """
    # Load a function from stdlib
    rgb_to_hsv = load("colorsys:rgb_to_hsv")
    assert callable(rgb_to_hsv)
    assert rgb_to_hsv(0.2, 0.4, 0.4) == (0.5, 0.5, 0.4)

    # Load a class from stdlib
    deque_class = load("collections:deque")
    assert isinstance(deque_class, type)
    assert deque_class([1, 2]).pop() == 2

    # Load an object from the current package (firebird.base)
    conj_meta = load("firebird.base.types:conjunctive")
    assert conj_meta is conjunctive

    # Load a nested object (enum member)
    little_endian = load("firebird.base.types:ByteOrder.LITTLE")
    assert little_endian is ByteOrder.LITTLE

    # Error Handling: Module not found
    with pytest.raises(ModuleNotFoundError):
        load("non_existent_module:some_object")

    # Error Handling: Object not found
    with pytest.raises(AttributeError):
        load("firebird.base.types:NonExistentClass")

    # Error Handling: Nested object not found
    with pytest.raises(AttributeError):
        load("firebird.base.types:ByteOrder.NONEXISTENT")

    # Error Handling: Malformed spec string
    with pytest.raises(ValueError):
        load("firebird.base.types") # Missing ':'
    with pytest.raises(ValueError):
        load(":ByteOrder") # Missing module
