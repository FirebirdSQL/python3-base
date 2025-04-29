# SPDX-FileCopyrightText: 2019-present The Firebird Projects <www.firebirdsql.org>
#
# SPDX-License-Identifier: MIT
#
#   PROGRAM/MODULE: firebird-base
#   FILE:           tests/test_strconv.py
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

from decimal import Decimal # Import specific exception
from enum import Enum, IntEnum, IntFlag, auto # Added auto
from uuid import NAMESPACE_OID, UUID, uuid5

import pytest

# Assuming strconv.py is importable as below
from firebird.base.strconv import *
# Assuming necessary types are available
from firebird.base.types import MIME, ByteOrder, Distinct, PyExpr, ZMQAddress, ZMQDomain # Added Distinct

# --- Test Setup ---

class MyCustomType:
    """Dummy class for testing custom convertor registration."""
    def __init__(self, value):
        self.value = value
    def __eq__(self, other):
        return isinstance(other, MyCustomType) and self.value == other.value

class UnregisteredType:
    """Dummy class guaranteed not to have a convertor."""
    pass

class AnotherFlag(IntFlag):
    """Another flag type for testing."""
    A = auto()
    B = auto()
    C = auto()

# --- Test Functions ---

def test_any2str():
    """Tests the default 'any to string' convertor function."""
    assert any2str(1) == "1"
    assert any2str(True) == "True" # Note: Different from bool2str used by default
    assert any2str(1.5) == "1.5"
    assert any2str(None) == "None"

def test_str2any():
    """Tests the default 'string to any' convertor function."""
    assert str2any(int, "1") == 1
    assert str2any(float, "1.5") == 1.5
    assert str2any(str, "hello") == "hello"
    with pytest.raises(ValueError):
        str2any(int, "not-a-number")

def test_convertor_dataclass():
    """Tests the Convertor dataclass itself."""
    c1 = Convertor(int, any2str, str2any)
    c2 = Convertor(int, lambda x: f"int:{x}", lambda c, v: int(v[4:]))
    c3 = Convertor(str, any2str, str2any)

    # get_key
    assert c1.get_key() is int
    assert c3.get_key() is str

    # Equality (based on key/cls)
    assert c1.get_key() == c2.get_key() # Same class key
    assert c1.get_key() != c3.get_key() # Different class key

    # Check attributes
    assert c1.cls is int
    assert c1.to_str is any2str
    assert c1.from_str is str2any
    assert c1.name == "int"
    assert c1.full_name == "builtins.int" # Check builtins module


def test_register_custom_convertor():
    """Tests registering, using, and getting a convertor for a new custom type."""
    custom_to_str = lambda x: f"CUSTOM<{x.value}>"
    custom_from_str = lambda c, v: c(v[7:-1]) # Assumes MyCustomType("...")

    assert not has_convertor(MyCustomType)
    with pytest.raises(TypeError, match="Type 'MyCustomType' has no Convertor"):
        get_convertor(MyCustomType)

    # Register
    register_convertor(MyCustomType, to_str=custom_to_str, from_str=custom_from_str)

    # Check presence and retrieval
    assert has_convertor(MyCustomType)
    conv = get_convertor(MyCustomType)
    assert isinstance(conv, Convertor)
    assert conv.cls is MyCustomType
    assert conv.to_str is custom_to_str
    assert conv.from_str is custom_from_str
    assert conv == get_convertor("MyCustomType")

    # Test conversion
    instance = MyCustomType("hello")
    instance_str = "CUSTOM<hello>"
    assert convert_to_str(instance) == instance_str
    assert convert_from_str(MyCustomType, instance_str) == instance

    # Cleanup (optional, but good practice if tests interfere)
    # This requires access to the internal registry, which might not be ideal.
    # If cleanup is essential, strconv might need a 'unregister' function.
    # For now, assume tests run sufficiently isolated or later tests overwrite.


def test_builtin_convertors_registered():
    """Checks that convertors for common built-in types are registered by default."""
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
    assert has_convertor(ByteOrder) # Test a specific Enum subclass
    assert has_convertor(AnotherFlag) # Test a specific IntFlag subclass

def test_has_convertor_logic():
    """Tests various scenarios for has_convertor, including MRO and unregistered."""
    # Unregistered base class
    assert not has_convertor(Distinct)
    # Registered descendant (str is registered)
    assert has_convertor(PyExpr)
    # Explicitly unregistered type
    assert not has_convertor(UnregisteredType)
    # Unresolvable string name
    assert not has_convertor("NoSuchClassAnywhere")

def test_core_function_errors():
    """Tests TypeErrors when attempting operations on types without convertors."""
    # get_convertor
    with pytest.raises(TypeError, match="Type 'UnregisteredType' has no Convertor"):
        get_convertor(UnregisteredType)
    # convert_to_str
    with pytest.raises(TypeError, match="Type 'UnregisteredType' has no Convertor"):
        convert_to_str(UnregisteredType())
    # convert_from_str
    with pytest.raises(TypeError, match="Type 'UnregisteredType' has no Convertor"):
        convert_from_str(UnregisteredType, "some string")

def test_update_convertor_logic():
    """Tests the update_convertor function, including error cases."""
    # Test update works (reusing test_update_convertor from original)
    conv = get_convertor(int)
    original_to_str = conv.to_str
    original_from_str = conv.from_str
    try:
        update_convertor(int, to_str=lambda x: "foo", from_str=lambda c, v: "baz")
        assert convert_to_str(42) == "foo"
        assert convert_from_str(int, "bar") == "baz"

        # Update only one function
        update_convertor(int, to_str=lambda x: "updated_foo")
        assert convert_to_str(42) == "updated_foo"
        assert convert_from_str(int, "bar") == "baz" # from_str should be unchanged

        update_convertor(int, from_str=lambda c, v: "updated_baz")
        assert convert_to_str(42) == "updated_foo" # to_str should be unchanged
        assert convert_from_str(int, "bar") == "updated_baz"

    finally:
        # Restore original convertors
        update_convertor(int, to_str=original_to_str, from_str=original_from_str)

    # Test update on unregistered type
    with pytest.raises(TypeError, match="Type 'UnregisteredType' has no Convertor"):
        # Note: It raises TypeError because get_convertor fails first
        update_convertor(UnregisteredType, to_str=lambda x: "")

# --- Built-in Type Conversion Tests ---

def test_builtin_str():
    """Tests string conversion (should be identity)."""
    value = "test value"
    assert convert_to_str(value) == value
    assert convert_from_str(str, value) == value

def test_builtin_int():
    """Tests integer conversion."""
    value = 42
    value_str = "42"
    assert convert_to_str(value) == value_str
    assert convert_from_str(int, value_str) == value
    with pytest.raises(ValueError):
        convert_from_str(int, "not-an-int")

def test_builtin_bool():
    """Tests boolean conversion, including case-insensitivity and error handling."""
    # To string
    assert convert_to_str(True) == "yes"
    assert convert_to_str(False) == "no"
    # From string (True cases)
    for true_val in TRUE_STR + [s.upper() for s in TRUE_STR] + ["On", "YES", "True", "Y"]:
        assert convert_from_str(bool, true_val) is True, f"Failed for '{true_val}'"
    # From string (False cases)
    for false_val in FALSE_STR + [s.upper() for s in FALSE_STR] + ["Off", "NO", "False", "N"]:
        assert convert_from_str(bool, false_val) is False, f"Failed for '{false_val}'"
    # From string (Error cases)
    with pytest.raises(ValueError, match="Value is not a valid bool string constant"):
        convert_from_str(bool, "maybe")
    with pytest.raises(ValueError, match="Value is not a valid bool string constant"):
        convert_from_str(bool, "") # Empty string

def test_builtin_float():
    """Tests float conversion."""
    value = 42.5
    value_str = "42.5"
    assert convert_to_str(value) == value_str
    assert convert_from_str(float, value_str) == value
    with pytest.raises(ValueError):
        convert_from_str(float, "not-a-float")

def test_builtin_complex():
    """Tests complex number conversion."""
    value = complex(42.5, -1.0)
    value_str = "(42.5-1j)" # Default complex repr
    assert convert_to_str(value) == value_str
    assert convert_from_str(complex, value_str) == value
    assert convert_from_str(complex, "42.5-1j") == value # Also handles without parens
    with pytest.raises(ValueError):
        convert_from_str(complex, "not-a-complex")

def test_builtin_decimal():
    """Tests Decimal conversion, including error handling."""
    value = Decimal("42.123456789")
    value_str = "42.123456789"
    assert convert_to_str(value) == value_str
    assert convert_from_str(Decimal, value_str) == value
    # Test error case from str2decimal
    with pytest.raises(ValueError, match="could not convert string to Decimal"):
        convert_from_str(Decimal, "not-a-decimal")

def test_builtin_uuid():
    """Tests UUID conversion."""
    value = uuid5(NAMESPACE_OID, "firebird.base.strconv")
    value_str = str(value) #"2ff58c2e-5cfd-50f1-8767-c9e405d7d62e"
    assert convert_to_str(value) == value_str
    assert convert_from_str(UUID, value_str) == value
    with pytest.raises(ValueError): # Invalid hex uuid
        convert_from_str(UUID, "not-a-valid-uuid-string")

def test_builtin_mime():
    """Tests MIME type conversion."""
    value = MIME("text/plain;charset=utf-8")
    value_str = "text/plain;charset=utf-8"
    assert convert_to_str(value) == value_str
    assert convert_from_str(MIME, value_str) == value
    with pytest.raises(ValueError): # Invalid MIME format
        convert_from_str(MIME, "textplain")

def test_builtin_zmqaddress():
    """Tests ZMQAddress conversion."""
    value = ZMQAddress("tcp://192.168.0.1:8080")
    value_str = "tcp://192.168.0.1:8080"
    assert convert_to_str(value) == value_str
    assert convert_from_str(ZMQAddress, value_str) == value
    with pytest.raises(ValueError): # Invalid ZMQ address format
        convert_from_str(ZMQAddress, "192.168.0.1:8080")

def test_builtin_enum():
    """Tests Enum conversion, including case-insensitivity and errors."""
    value = ByteOrder.BIG
    value_str = "BIG"
    assert convert_to_str(value) == value_str
    assert convert_from_str(ByteOrder, value_str) == value
    assert convert_from_str(ByteOrder, "little") == ByteOrder.LITTLE # Case test
    assert convert_from_str(ByteOrder, "NeTwOrK") == ByteOrder.NETWORK # Case test
    with pytest.raises(ValueError, match="'invalid_member'"): # Specific error
        convert_from_str(ByteOrder, "invalid_member")

def test_builtin_intenum():
    """Tests IntEnum conversion (should behave like Enum)."""
    value = ZMQDomain.LOCAL
    value_str = "LOCAL"
    assert convert_to_str(value) == value_str
    assert convert_from_str(ZMQDomain, value_str) == value
    assert convert_from_str(ZMQDomain, "nOdE") == ZMQDomain.NODE # Case test
    with pytest.raises(ValueError, match="'invalid_domain'"):
        convert_from_str(ZMQDomain, "invalid_domain")

def test_builtin_intflag():
    """Tests IntFlag conversion, including combinations, case, separators, and errors."""
    # Single flag
    assert convert_to_str(AnotherFlag.A) == "A"
    assert convert_from_str(AnotherFlag, "a") == AnotherFlag.A
    assert convert_from_str(AnotherFlag, "B") == AnotherFlag.B

    # Combined flags
    value_comb = AnotherFlag.A | AnotherFlag.C
    value_str_comb = "A|C"
    assert convert_to_str(value_comb) == value_str_comb
    # From string (various separators and cases)
    assert convert_from_str(AnotherFlag, "a|c") == value_comb
    assert convert_from_str(AnotherFlag, "C | a") == value_comb # Spaces, order

    # Empty string
    with pytest.raises(KeyError, match="''"):
        assert convert_from_str(AnotherFlag, "")

    # Invalid flag name
    with pytest.raises(KeyError, match="'invalid_flag'"):
        convert_from_str(AnotherFlag, "a|invalid_flag")
    with pytest.raises(KeyError, match="'d'"):
        convert_from_str(AnotherFlag, "a|d")

# --- Remaining Function Tests ---

def test_get_convertor_lookup():
    """Tests get_convertor with different lookup methods (type, name, fullname, MRO)."""
    # By type
    assert get_convertor(int).cls is int
    # By simple name (requires prior registration if not built-in/imported)
    # tested in test_register_custom_convertor
    # By full name
    assert get_convertor("firebird.base.types.MIME").cls is MIME
    # By MRO lookup
    assert get_convertor(PyExpr).cls is str # PyExpr -> str, str has convertor

def test_update_convertor_restoration():
    """Ensures update_convertor changes are correctly restored."""
    conv = get_convertor(int)
    original_to_str = conv.to_str
    original_from_str = conv.from_str
    try:
        update_convertor(int, to_str=lambda x: "foo", from_str=lambda c, v: "baz")
        assert get_convertor(int).to_str is not original_to_str
    finally:
        # Restore original convertors
        update_convertor(int, to_str=original_to_str, from_str=original_from_str)
    # Verify restoration
    assert get_convertor(int).to_str is original_to_str
    assert get_convertor(int).from_str is original_from_str


def test_convertor_names_property():
    """Tests the .name and .full_name properties of a Convertor."""
    c = get_convertor(MIME)
    assert c.name == "MIME"
    assert c.full_name == "firebird.base.types.MIME"

    c_int = get_convertor(int)
    assert c_int.name == "int"
    assert c_int.full_name == "builtins.int"


def test_register_class_logic():
    """Tests register_class functionality and duplicate handling."""
    class TempClassForRegister: pass

    assert not has_convertor("TempClassForRegister") # Check lookup by name fails
    register_class(TempClassForRegister)
    assert not has_convertor("TempClassForRegister") # Still no *convertor*, just class known
    assert not has_convertor(TempClassForRegister)

    # Register a convertor for it now
    register_convertor(TempClassForRegister)
    assert has_convertor("TempClassForRegister") # Now name lookup finds convertor
    assert has_convertor(TempClassForRegister)
    assert get_convertor("TempClassForRegister").cls is TempClassForRegister

    # Test duplicate registration
    with pytest.raises(TypeError, match="Class 'TempClassForRegister' already registered"):
        register_class(TempClassForRegister)

    # Cleanup (optional, requires internal access or unregister function)
    # del _classes["TempClassForRegister"]
    # del _convertors[TempClassForRegister]
