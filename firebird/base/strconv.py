#coding:utf-8
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
"""

from __future__ import annotations
from typing import Hashable, Callable, Any, Type, Union
from dataclasses import dataclass
from decimal import Decimal, DecimalException
from enum import Enum, IntEnum, IntFlag
from uuid import UUID
from .types import Distinct, MIME, ZMQAddress
from .collections import Registry

#: Function that converts typed value to its string representation.
TConvertToStr = Callable[[Any], str]
#: Function that converts string representation of typed value to typed value.
TConvertFromStr = Callable[[Type, str], Any]

@dataclass
class Convertor(Distinct):
    "Data convertor registry entry."
    cls: Type
    to_str: TConvertToStr
    from_str: TConvertFromStr
    def get_key(self) -> Hashable:
        """Returns instance key."""
        return self.cls
    @property
    def name(self) -> str:
        "Type name"
        return self.cls.__name__
    @property
    def full_name(self) -> str:
        "Type name incl. source module"
        return f'{self.cls.__module__}.{self.cls.__name__}'

_convertors: Registry = Registry()
_classes = {}

# Convertors

#: Valid string literals for True value.
TRUE_STR = ['yes', 'true', 'on', 'y', '1']
#: Valid string literals for False value.
FALSE_STR = ['no', 'false', 'off', 'n', '0']

def any2str(value: Any) -> str:
    "Converts value to string using `str(value)`."
    return str(value)

def str2any(cls: Type, value: str) -> Any:
    "Converts string to data type value using `type(value)`."
    return cls(value)

def register_convertor(cls: Type, *,
                       to_str: TConvertToStr=any2str,
                       from_str: TConvertFromStr=str2any):
    """Registers convertor function(s).

Arguments:
    cls:      Class or class name
    to_str:   Function that converts `cls` value to `str`
    from_str: Function that converts `str` to value of `cls` data type
"""
    _convertors.store(Convertor(cls, to_str, from_str))

def register_class(cls: Type) -> None:
    """Registers class for name lookup.

.. seealso:: `has_convertor()`, `get_convertor()`

Raises:
    TypeError: When class name is already registered.
"""
    if cls.__name__ in _classes:
        raise TypeError(f"Class '{cls.__name__}' already registered as '{_classes[cls.__name__]!r}'")
    _classes[cls.__name__] = cls

def _get_convertor(cls: Union[Type, str]) -> Convertor:
    if isinstance(cls, str):
        if cls in _classes:
            cls = _classes[cls]
    if isinstance(cls, str):
        conv = list(_convertors.filter(f"item.{'full_name' if '.' in cls else 'name'} == '{cls}'"))
        conv = conv.pop(0) if conv else None
    else:
        if (conv := _convertors.get(cls)) is None:
            for base in cls.__mro__:
                conv = _convertors.get(base)
                if conv is not None:
                    break
    return conv

def has_convertor(cls: Union[Type, str]) -> bool:
    """Returns True if class has a convertor.

Arguments:
    cls: Type or type name. The name could be simple class name, or full name that includes
         the module name.

Note:
    When `cls` is a name:

    1. If class name is NOT registered via `register_class()`, it's not possible to perform
       lookup for bases classes.
    2. If simple class name is provided and multiple classes of the same name but from
       different modules have registered convertors, the first one found is used. If you
       want to avoid this situation, use full names.
"""
    return _get_convertor(cls) is not None

def update_convertor(cls: Union[Type, str], *,
                     to_str: TConvertToStr=None,
                     from_str: TConvertFromStr=None):
    """Update convertor function(s).

Arguments:
    cls:      Class or class name
    to_str:   Function that converts `cls` value to `str`
    from_str: Function that converts `str` to value of `cls` data type

Raises:
    KeyError: If data type has not registered convertor.
"""
    conv = get_convertor(cls)
    if to_str:
        conv.to_str = to_str
    if from_str:
        conv.from_str = from_str

def convert_to_str(value: Any) -> str:
    """Converts value to string using registered convertor.

Arguments:
    value:  Value to be converted.

If there is no convertor for value's class, uses MRO to locate alternative convertor.

Raises:
    TypeError: If there is no convertor for value's class or any from its bases classes.
"""
    return get_convertor(value.__class__).to_str(value)


def convert_from_str(cls: Union[Type, str], value: str) -> Any:
    """Converts value from string to data type using registered convertor.

Arguments:
    cls:   Type or type name. The name could be simple class name, or full name that includes
           the module name.
    value: String value to be converted

Note:
    When `cls` is a type name:

    1. If class name is NOT registered via `register_class()`, it's not possible to perform
       lookup for bases classes.
    2. If simple class name is provided and multiple classes of the same name but from
       different modules have registered convertors, the first one found is used. If you
       want to avoid this situation, use full names.

Raises:
    TypeError: If there is no convertor for `cls` or any from its bases classes.
"""
    return get_convertor(cls).from_str(cls, value)

def get_convertor(cls: Union[Type, str]) -> Convertor:
    """Returns Convertor for data type.

Arguments:
    cls: Type or type name. The name could be simple class name, or full name that includes
         the module name.

Note:
    When `cls` is a type name:

    1. If class name is NOT registered via `register_class()`, it's not possible to perform
       lookup for bases classes.
    2. If simple class name is provided and multiple classes of the same name but from
       different modules have registered convertors, the first one found is used. If you
       want to avoid this situation, use full names.

Raises:
    TypeError: If there is no convertor for `cls` or any from its bases classes.
"""
    if (conv := _get_convertor(cls)) is None:
        raise TypeError(f"Type '{cls.__name__ if isinstance(cls, type) else cls}' has no Convertor")
    return conv

def register():

    def bool2str(value: bool) -> str:
        return TRUE_STR[0] if value else FALSE_STR[0]
    def str2bool(type_: Type, value: str) -> bool:
        if (v := value.lower()) in TRUE_STR:
            return True
        if v not in FALSE_STR:
            raise ValueError("Value is not a valid bool string constant")
        return False
    def str2decimal(type_: Type, value: str) -> Decimal:
        try:
            return type_(value)
        except DecimalException:
            raise ValueError(f"could not convert string to {type_.__name__}: '{value}'")
    def enum2str(value: Enum) -> str:
        "Converts any Enum/Flag value to string"
        return value.name
    def str2enum(cls: Type, value: str) -> Enum:
        "Converts string to Enum/Flag value"
        return {k.lower(): v for k, v in cls.__members__.items()}[value.lower()]

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
    register_convertor(IntFlag, to_str=enum2str, from_str=str2enum)

register()
del register
