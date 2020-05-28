#coding:utf-8
#
# PROGRAM/MODULE: firebird-base
# FILE:           firebird/base/types.py
# DESCRIPTION:    Types
# CREATED:        14.5.2020
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

"""Firebird Base - Types
"""

from __future__ import annotations
import typing as t
from abc import ABC, ABCMeta, abstractmethod
from enum import Enum, IntEnum
from weakref import WeakValueDictionary

# Exceptions

class Error(Exception):
    """Exception that is intended to be used as a base class of all **application-related**
errors. The important difference from `Exception` class is that `Error` accepts keyword
arguments, that are stored into instance attributes with the same name.

Important:
    Attribute lookup on this class never fails, as all attributes that are not actually set,
    have `None` value.

Example:
    .. code-block:: python

        try:
            if condition:
                raise Error("Error message", err_code=1)
            else:
                raise Error("Unknown error")
        except Error as e:
            if e.err_code is None:
                ...
            elif e.err_code == 1:
                ...

Note:
    Warnings are not considered errors and thus should not use this class as base.
"""
    def __init__(self, *args, **kwargs):
        super().__init__(*args)
        for name, value in kwargs.items():
            setattr(self, name, value)
    def __getattr__(self, name):
        return None

# Singletons

_singletons_ = {}

class SingletonMeta(type):
    """Metaclass for `Singleton` classes.

Manages internal cache of class instances. If instance for a class is in cache, it's returned
without calling the constructor, otherwise the instance is created normally and stored in
cache for later use.
"""
    def __call__(cls: Singleton, *args, **kwargs):
        name = f"{cls.__module__}.{cls.__qualname__}"
        obj = _singletons_.get(name)
        if obj is None:
            obj = super(SingletonMeta, cls).__call__(*args, **kwargs)
            _singletons_[name] = obj
        return obj

class Singleton(metaclass=SingletonMeta):
    """Base class for singletons.

Important:
    If you create a descendant class that uses constructor arguments, these arguments are
    meaningful ONLY on first call, because all subsequent calls simply return an instance
    stored in cache without calling the constructor.
"""

# Sentinels

class SentinelMeta(type):
    "Metaclass for `Sentinel`."
    def __call__(cls: Sentinel, *args, **kwargs):
        name = args[0].upper()
        obj = cls.instances.get(name)
        if obj is None:
            obj = super(SentinelMeta, cls).__call__(*args, **kwargs)
            cls.instances[name] = obj
        return obj

class Sentinel(metaclass=SentinelMeta):
    """Simple sentinel object.

Important:
  All sentinels have name, that is **always in capital letters**. Sentinels with the same
  name are singletons.

Attributes:
    name (str): Sentinel name.
"""
    #: Class attribute with defined sentinels. There is no need to access or manipulate it.
    instances = {}
    def __init__(self, name: str):
        self.name = name.upper()
    def __str__(self):
        "Returns name"
        return self.name
    def __repr__(self):
        "Returns Sentinel('name')"
        return f"Sentinel('{self.name}')"

# Useful sentinel objects

#: Sentinel that denotes default value
DEFAULT: Sentinel = Sentinel('DEFAULT')
#: Sentinel that denotes infinity value
INFINITY: Sentinel = Sentinel('INFINITY')
#: Sentinel that denotes unlimited value
UNLIMITED: Sentinel = Sentinel('UNLIMITED')
#: Sentinel that denotes unknown value
UNKNOWN: Sentinel = Sentinel('UNKNOWN')
#: Sentinel that denotes a condition when value was not found
NOT_FOUND: Sentinel = Sentinel('NOT_FOUND')
#: Sentinel that denotes explicitly undefined value
UNDEFINED: Sentinel = Sentinel('UNDEFINED')
#: Sentinel that denotes any value
ANY: Sentinel = Sentinel('ANY')
#: Sentinel that denotes all possible values
ALL: Sentinel = Sentinel('ALL')
#: Sentinel that denotes suspend request (in message queue)
SUSPEND: Sentinel = Sentinel('SUSPEND')
#: Sentinel that denotes resume request (in message queue)
RESUME: Sentinel = Sentinel('RESUME')
#: Sentinel that denotes stop request (in message queue)
STOP: Sentinel = Sentinel('STOP')

# Distinct objects

class Distinct(ABC):
    """Abstract base class for classes (incl. dataclasses) with distinct instances.
"""
    @abstractmethod
    def get_key(self) -> t.Hashable:
        """Returns instance key.

Important:
    The key is used for instance hash computation that by default uses the `hash`
    function. If the key is not suitable argument for `hash`, you must provide your
    own `__hash__` implementation as well!
"""
    __hash__ = lambda self: hash(self.get_key())

class CachedDistinctMeta(ABCMeta):
    "Metaclass for CachedDistinct."
    def __call__(cls: CachedDistinct, *args, **kwargs):
        key = cls.extract_key(*args, **kwargs)
        if not hasattr(cls, '_instances_'):
            setattr(cls, '_instances_', WeakValueDictionary())
        obj = cls._instances_.get(key)
        if obj is None:
            obj = super(CachedDistinctMeta, cls).__call__(*args, **kwargs)
            cls._instances_[key] = obj
        return obj

class CachedDistinct(Distinct, metaclass=CachedDistinctMeta):
    """Abstract `Distinct` descendant that caches instances.

All created instances are cached in `~weakref.WeakValueDictionary`.
"""
    @classmethod
    @abstractmethod
    def extract_key(cls, *args, **kwargs) -> t.Hashable:
        """Returns key from arguments passed to `__init__()`.

Important:
    The key is used to store instance in cache. It should be the same as key returned by
    instance `.get_key()`!
"""

# Enums

class ByteOrder(Enum):
    "Byte order for storing numbers in binary `.MemoryBuffer`."
    LITTLE = 'little'
    BIG = 'big'
    NETWORK = BIG

class ZMQTransport(IntEnum):
    """ZeroMQ transport protocol"""
    UNKNOWN = 0 # Not a valid option, defined only to handle undefined values
    INPROC = 1
    IPC = 2
    TCP = 3
    PGM = 4
    EPGM = 5
    VMCI = 6

class ZMQDomain(IntEnum):
    """ZeroMQ address domain"""
    UNKNOWN = 0  # Not a valid option, defined only to handle undefined values
    LOCAL = 1    # Within process (inproc)
    NODE = 2     # On single node (ipc or tcp loopback)
    NETWORK = 3  # Network-wide (ip address or domain name)

# Zero MQ

class ZMQAddress(str):
    """ZeroMQ endpoint address.

It behaves like `str`, but checks that value is valid ZMQ endpoint address, and has
additional R/O properties.

Raises:
    ValueError: When string value passed to constructor is not a valid ZMQ endpoint address.
"""
    def __new__(cls, value: t.AnyStr):
        if isinstance(value, bytes):
            value = t.cast(bytes, value).decode('utf8')
        if '://' in value:
            protocol, _ = value.split('://', 1)
            if protocol.upper() not in ZMQTransport._member_map_:
                raise ValueError(f"Unknown protocol '{protocol}'")
            if protocol.upper() == 'UNKNOWN':
                raise ValueError("Invalid protocol")
        else:
            raise ValueError("Protocol specification required")
        return str.__new__(cls, value.lower())
    @property
    def protocol(self) -> ZMQTransport:
        "Transport protocol"
        protocol, _ = self.split('://', 1)
        return ZMQTransport._member_map_[protocol.upper()]
    @property
    def address(self) -> str:
        "Address"
        _, address = self.split('://', 1)
        return address
    @property
    def domain(self) -> ZMQDomain:
        "Address domain"
        if self.protocol == ZMQTransport.INPROC:
            return ZMQDomain.LOCAL
        if self.protocol == ZMQTransport.IPC:
            return ZMQDomain.NODE
        if self.protocol == ZMQTransport.TCP:
            if self.address.startswith('127.0.0.1') or self.address.lower().startswith('localhost'):
                return ZMQDomain.NODE
            return ZMQDomain.NETWORK
        # PGM, EPGM and VMCI
        return ZMQDomain.NETWORK

# Types for type hints / annotations

#: List of ZeroMQ endpoints
ZMQAddressList = t.List[ZMQAddress]

# Type conversions

#: [True] bool string constants for `str2bool`. All values must be in lower case.
true_str = ['yes', 'true', 'on', 'y', '1']

#: [False] bool string constants for `str2bool`. All values must be in lower case.
false_str = ['no', 'false', 'off', 'n', '0']

def str2bool(value: str, *, type_check: bool=True) -> bool:
    """Converts bool string constants to boolean.

Arguments:
    value: Bool string constant (case is not significant).
    type_check: When True [default], only values defined in `true_str` and `false_str` are
        allowed. When False, all values that does not match these defined by `true_str` are
        considered as False value.

Raises:
    ValueError: When `type_check` is True and value does not match any string defined in
                `true_str` or `false_str` lists.
"""
    if (v := value.lower()) in true_str:
        return True
    if type_check and v not in false_str:
        raise ValueError("Value is not a valid bool string constant")
    return False
