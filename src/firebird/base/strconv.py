# SPDX-FileCopyrightText: 2020-present The Firebird Projects <www.firebirdsql.org>
#
# SPDX-License-Identifier: MIT
#
# PROGRAM/MODULE: firebird-base
# FILE:           firebird/base/strconv.py
# DESCRIPTION:    Data conversion from/to string
# CREATED:        4.6.2020
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
#                 ______________________________________

"""firebird-base - Data conversion from/to string

This module provides a centralized mechanism for converting various Python data types
to and from their string representations. It allows registering custom conversion
functions for specific types, making the conversion process extensible and
decoupled from the types themselves.

Core features include:
- Registration of type-specific string conversion functions.
- Lookup of convertors based on type or type name (simple or full).
- Helper functions (`convert_to_str`, `convert_from_str`) for easy conversion.
- Built-in support for common types (str, int, float, bool, Decimal, UUID, Enum, etc.).

Example::

    from firebird.base.strconv import convert_to_str, convert_from_str
    from decimal import Decimal

    # Convert Decimal to string
    s = convert_to_str(Decimal('123.45'))
    print(s)  # Output: 123.45

    # Convert string back to Decimal
    d = convert_from_str(Decimal, '123.45')
    print(d)  # Output: Decimal('123.45')

    # Boolean conversion
    b = convert_from_str(bool, 'yes')
    print(b) # Output: True
    s = convert_to_str(False)
    print(s) # Output: no
"""

from __future__ import annotations

from collections.abc import Callable, Hashable
from dataclasses import dataclass
from decimal import Decimal, DecimalException
from enum import Enum, IntEnum, IntFlag
from typing import Any, TypeAlias
from uuid import UUID

from .collections import Registry
from .types import MIME, Distinct, ZMQAddress

#: Function that converts typed value to its string representation.
TConvertToStr: TypeAlias = Callable[[Any], str]
#: Function that converts string representation of typed value to typed value.
TConvertFromStr: TypeAlias = Callable[[type, str], Any]

@dataclass
class Convertor(Distinct):
    """Data convertor registry entry.

    Holds the functions responsible for converting a specific data type
    to and from its string representation. Instances of this class are
    stored in the internal registry.

    Arguments:
        cls: The data type (class) this convertor handles.
        to_str: The function converting an instance of `cls` to a string.
        from_str: The function converting a string back to an instance of `cls`.
    """
    #: The data type (class) this convertor handles.
    cls: type
    #: The function converting an instance of `cls` to a string.
    to_str: TConvertToStr
    #: The function converting a string back to an instance of `cls`.
    from_str: TConvertFromStr
    def get_key(self) -> Hashable:
        """Returns instance key (the class itself), used by the Registry."""
        return self.cls
    @property
    def name(self) -> str:
        """Simple type name (e.g., 'int', 'Decimal')."""
        return self.cls.__name__
    @property
    def full_name(self) -> str:
        """Type name including source module (e.g., 'decimal.Decimal')."""
        return f'{self.cls.__module__}.{self.cls.__name__}'

_convertors: Registry = Registry()
_classes: dict[str, type] = {}

# Convertors

#: Valid string literals for True value.
TRUE_STR: list[str] = ['yes', 'true', 'on', 'y', '1']
#: Valid string literals for False value.
FALSE_STR: list[str] = ['no', 'false', 'off', 'n', '0']

def any2str(value: Any) -> str:
    """Converts value to string using `str(value)`.

    This is the default `to_str` convertor function.

    Arguments:
       value: The value to convert.

    :return: The string representation of the value.
    """
    return str(value)

def str2any(cls: type, value: str) -> Any:
    """Converts string to data type value using `type(value)`.

    This is the default `from_str` convertor function. It assumes the
    type's constructor can handle a single string argument.

    Arguments:
      cls: The target data type.
      value: The string representation to convert.

    :return: An instance of `cls` created from the string value.
    """
    return cls(value)

def register_convertor(cls: type, *, to_str: TConvertToStr=any2str,
                       from_str: TConvertFromStr=str2any) -> None:
    """Registers convertor function(s) for a specific data type.

    If `to_str` or `from_str` are not provided, default convertors (`any2str`,
    `str2any`) based on `str()` and `cls()` are used.

    Arguments:
        cls:      Class to register convertor for.
        to_str:   Optional function that converts an instance of `cls` to `str`.
                  Defaults to `any2str`.
        from_str: Optional function that converts `str` to value of `cls` data type.
                  Defaults to `str2any`.

    Example:
        .. code-block:: python

            from datetime import date
            from firebird.base.strconv import register_convertor, convert_to_str, convert_from_str

            # Register custom convertors for date
            def date_to_iso(value: date) -> str:
                return value.isoformat()

            def iso_to_date(cls: type, value: str) -> date:
                return cls.fromisoformat(value)

            register_convertor(date, to_str=date_to_iso, from_str=iso_to_date)

            d = date(2023, 10, 27)
            s = convert_to_str(d) # Uses date_to_iso -> '2023-10-27'
            d2 = convert_from_str(date, s) # Uses iso_to_date -> date(2023, 10, 27)
    """
    _convertors.store(Convertor(cls, to_str, from_str))

def register_class(cls: type) -> None:
    """Registers a class name for lookup, primarily for string-based conversions.

    This allows functions like `has_convertor`, `get_convertor`, and `convert_from_str`
    to find the correct convertor when given a simple class name (e.g., "MyClass")
    as a string, instead of the class object itself. Registration is particularly
    useful when:

    1. Performing lookups based on class names stored as strings.
    2. Resolving potential ambiguity if multiple classes with the same simple name
       exist in different modules (though using full names like 'module.MyClass'
       is generally safer in such cases).
    3. Enabling MRO (Method Resolution Order) lookup for base class convertors
       when the lookup starts with a string name.

    .. seealso:: `has_convertor()`, `get_convertor()`, `convert_from_str()`

    Arguments:
        cls: Class to be registered.

    Raises:
        TypeError: When the simple class name (`cls.__name__`) is already registered.
    """
    if cls.__name__ in _classes:
        raise TypeError(f"Class '{cls.__name__}' already registered as '{_classes[cls.__name__]!r}'")
    _classes[cls.__name__] = cls

def _get_convertor(cls: type | str) -> Convertor | None:
    if isinstance(cls, str):
        cls = _classes.get(cls, cls)
    if isinstance(cls, str):
        conv = list(_convertors.filter(f"item.{'full_name' if '.' in cls else 'name'} == '{cls}'"))
        conv = conv.pop(0) if conv else None
    elif (conv := _convertors.get(cls)) is None:
        for base in cls.__mro__:
            conv = _convertors.get(base)
            if conv is not None:
                break
    return conv

def has_convertor(cls: type | str) -> bool:
    """Returns True if a convertor is registered for the class or its bases.

    Arguments:
        cls: Type object or type name. The name could be a simple class name
             (e.g., "MyClass") or a full name including the module
             (e.g., "my_module.MyClass").

    Note:

        When `cls` is a name:

        1. If the class name is NOT registered via `register_class()`, it's not
           possible to perform MRO lookup for base class convertors. Only an exact
           match on the name (simple or full) will work.
        2. If a simple class name is provided and multiple classes of the same
           name but from different modules have registered convertors (or been
           registered via `register_class`), the lookup might be ambiguous. Using
           full names is recommended in such scenarios.

    Example:

        .. code-block:: python

            from decimal import Decimal
            from firebird.base.strconv import register_convertor, has_convertor, register_class

            print(has_convertor(Decimal))  # Output: True (built-in)
            print(has_convertor('Decimal')) # Output: True (built-in, simple name works)
            print(has_convertor('decimal.Decimal')) # Output: True (full name)

            class MyData: pass
            class MySubData(MyData): pass

            register_convertor(MyData)
            register_class(MySubData) # Register subclass name

            print(has_convertor(MySubData))   # Output: True (finds MyData via MRO)
            print(has_convertor('MySubData')) # Output: True (finds MyData via MRO because name is registered)
            print(has_convertor('NonExistent')) # Output: False
    """
    return _get_convertor(cls) is not None

def update_convertor(cls: type | str, *,
                     to_str: TConvertToStr | None=None,
                     from_str: TConvertFromStr | None=None) -> None:
    """Update the `to_str` and/or `from_str` functions for an existing convertor.

    Arguments:
        cls:      Class or class name whose convertor needs updating.
        to_str:   Optional new function that converts `cls` value to `str`.
        from_str: Optional new function that converts `str` to value of `cls` data type.

    Raises:
        TypeError: If the data type (or its name) has no registered convertor.

    Example:
        .. code-block:: python

           from firebird.base.strconv import update_convertor, convert_to_str

           # Assume BoolConvertor exists and uses 'yes'/'no'
           # Change bool to output 'TRUE'/'FALSE'
           update_convertor(bool, to_str=lambda v: 'TRUE' if v else 'FALSE')
           print(convert_to_str(True)) # Output: TRUE
    """
    conv: Convertor = get_convertor(cls)
    if to_str:
        conv.to_str = to_str
    if from_str:
        conv.from_str = from_str

def convert_to_str(value: Any) -> str:
    """Converts a value to its string representation using its registered convertor.

    Looks up the convertor based on the value's class (`value.__class__`).
    If there is no direct convertor registered for the value's specific class,
    it searches the Method Resolution Order (MRO) for a convertor registered
    for a base class.

    Arguments:
        value: The value to be converted to a string.

    Raises:
        TypeError: If no convertor is found for the value's class or any of
                   its base classes in the MRO.

    Example:
        .. code-block:: python

            from decimal import Decimal
            from uuid import uuid4
            from firebird.base.strconv import convert_to_str, register_convertor

            print(convert_to_str(123))           # Output: '123'
            print(convert_to_str(Decimal('1.2'))) # Output: '1.2'
            print(convert_to_str(True))          # Output: 'yes'
            my_uuid = uuid4()
            print(convert_to_str(my_uuid))       # Output: UUID string representation

            class MyBase: pass
            class MyDerived(MyBase): pass
            register_convertor(MyBase, to_str=lambda v: "BaseStr")
            instance = MyDerived()
            print(convert_to_str(instance))      # Output: 'BaseStr' (uses MyBase convertor)
    """
    return get_convertor(value.__class__).to_str(value)

def convert_from_str(cls: type | str, value: str) -> Any:
    """Converts a string representation back to a typed value using a registered convertor.

    Arguments:
        cls:   The target type object or type name (simple or full) to convert to.
        value: The string value to be converted.

    Note:
        When `cls` is a type name:

        1. If the class name is NOT registered via `register_class()`, MRO lookup for
           base class convertors is not possible if an exact name match isn't found.
        2. If a simple class name is provided and is ambiguous (multiple registered
           classes with the same name), the first match found is used. Use full names
           ('module.ClassName') for clarity in such cases.

    Raises:
        TypeError: If no convertor is found for `cls` or any of its base classes (when MRO lookup is possible).
        ValueError: Often raised by the underlying `from_str` function if the string
                    `value` is not in the expected format for the target type (e.g.,
                    converting 'abc' to int).

    Example:
        .. code-block:: python

            from decimal import Decimal
            from uuid import UUID
            from firebird.base.strconv import convert_from_str

            num = convert_from_str(int, '123')        # Output: 123 (int)
            dec = convert_from_str(Decimal, '1.2')    # Output: Decimal('1.2')
            flag = convert_from_str(bool, 'off')      # Output: False (bool)
            uid = convert_from_str(UUID, '...')       # Output: UUID object
            # Using string name
            dec_from_name = convert_from_str('Decimal', '3.14') # Output: Decimal('3.14')

            try:
               convert_from_str(int, 'not-a-number')
            except ValueError as e:
               print(e) # Example: invalid literal for int() with base 10: 'not-a-number'
    """
    return get_convertor(cls).from_str(cls, value)

def get_convertor(cls: type | str) -> Convertor:
    """"Returns the Convertor object registered for a data type or its bases.

    This function performs the lookup based on the type or type name, including
    MRO search for base classes if necessary and possible. It is used internally
    by `convert_to_str` and `convert_from_str`, but can be called directly
    if you need access to the `Convertor` instance itself, for example,
    for introspection or direct access to the `to_str`/`from_str` functions.

    Arguments:
        cls: Type object or type name. The name could be a simple class name
             (e.g., "MyClass") or a full name including the module
             (e.g., "my_module.MyClass").

    Note:
        When `cls` is a name:

        1. If the class name is NOT registered via `register_class()`, MRO lookup for
           base class convertors is not possible if an exact name match isn't found.
        2. If a simple class name is provided and is ambiguous (multiple registered
           classes with the same name), the first match found is used. Use full names
           for clarity.

    Raises:
        TypeError: If no convertor is found for `cls` or any of its base classes.

    Example:
        .. code-block:: python

            from decimal import Decimal
            from firebird.base.strconv import get_convertor

            decimal_conv = get_convertor(Decimal)
            print(decimal_conv.name) # Output: Decimal
            print(decimal_conv.to_str(Decimal('9.87'))) # Output: 9.87

            bool_conv = get_convertor('bool') # Lookup by name
            print(bool_conv.from_str(bool, 'TRUE')) # Output: True
    """
    if (conv := _get_convertor(cls)) is None:
        raise TypeError(f"Type '{cls.__name__ if isinstance(cls, type) else cls}' has no Convertor")
    return conv

def _register() -> None:
    """Internal function for registration of builtin converters."""

    def bool2str(value: bool) -> str: # noqa: FBT001
        return TRUE_STR[0] if value else FALSE_STR[0]
    def str2bool(type_: type, value: str) -> bool: # noqa: ARG001
        if (v := value.lower()) in TRUE_STR:
            return True
        if v not in FALSE_STR:
            raise ValueError("Value is not a valid bool string constant")
        return False
    def str2decimal(type_: type, value: str) -> Decimal:
        try:
            return type_(value)
        except DecimalException as exc:
            raise ValueError(f"could not convert string to {type_.__name__}: '{value}'") from exc
    def enum2str(value: Enum) -> str:
        "Converts any Enum/Flag value to string"
        return value.name
    def str2enum(cls: type, value: str) -> Enum:
        "Converts string to Enum/Flag value (case-insensitive)."
        # Use get for better error message if key not found
        members_lower = {k.lower(): v for k, v in cls.__members__.items()}
        member = members_lower.get(value.lower())
        if member is None:
            raise ValueError(f"'{value}' is not a valid member of enum {cls.__name__}")
        return member
    def str2flag(cls: type, value: str) -> Enum:
        "Converts pipe-separated string to IntFlag value (case-insensitive)."
        result = None
        for item in value.lower().split('|'):
            value = {k.lower(): v for k, v in cls.__members__.items()}[item.strip()]
            if result:
                result |= value
            else:
                result = value
        return result

    register_convertor(str)
    register_convertor(int)
    register_convertor(float)
    register_convertor(complex)
    register_convertor(Decimal, from_str=str2decimal)
    register_convertor(UUID)
    register_convertor(MIME)
    register_convertor(ZMQAddress)
    register_convertor(bool, to_str=bool2str, from_str=str2bool)
    register_convertor(Enum, to_str=enum2str, from_str=str2enum)
    # We must register IntEnum and IntFlag because 'int' is before Enum in MRO
    register_convertor(IntEnum, to_str=enum2str, from_str=str2enum)
    register_convertor(IntFlag, to_str=enum2str, from_str=str2flag)

_register()
del _register
