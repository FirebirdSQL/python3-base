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
from typing import Any, Dict, Hashable, Callable, AnyStr, cast
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
            obj = super().__call__(*args, **kwargs)
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
            obj = super().__call__(*args, **kwargs)
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
    def get_key(self) -> Hashable:
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
        obj = cls._instances_.get(key)
        if obj is None:
            obj = super().__call__(*args, **kwargs)
            cls._instances_[key] = obj
        return obj

class CachedDistinct(Distinct, metaclass=CachedDistinctMeta):
    """Abstract `Distinct` descendant that caches instances.

All created instances are cached in `~weakref.WeakValueDictionary`.
"""
    def __init_subclass__(cls: Type, /, **kwargs) -> None:
        super().__init_subclass__(**kwargs)
        setattr(cls, '_instances_', WeakValueDictionary())
    @classmethod
    @abstractmethod
    def extract_key(cls, *args, **kwargs) -> Hashable:
        """Returns key from arguments passed to `__init__()`.

Important:
    The key is used to store instance in cache. It should be the same as key returned by
    instance `Distinct.get_key()`!
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

# Enhanced string types

class ZMQAddress(str):
    """ZeroMQ endpoint address.

It behaves like `str`, but checks that value is valid ZMQ endpoint address, has
additional R/O properties and meaningful `repr()`.

Raises:
    ValueError: When string value passed to constructor is not a valid ZMQ endpoint address.
"""
    def __new__(cls, value: AnyStr):
        if isinstance(value, bytes):
            value = cast(bytes, value).decode('utf8')
        if '://' in value:
            protocol, _ = value.split('://', 1)
            if protocol.upper() not in ZMQTransport._member_map_:
                raise ValueError(f"Unknown protocol '{protocol}'")
            if protocol.upper() == 'UNKNOWN':
                raise ValueError("Invalid protocol")
        else:
            raise ValueError("Protocol specification required")
        return str.__new__(cls, value.lower())
    def __repr__(self):
        return f"ZMQAddress('{self}')"
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

class MIME(str):
    """MIME type specification.

It behaves like `str`, but checks that value is valid MIME type specification, has
additional R/O properties and meaningful `repr()`.

"""
    #: Supported MIME types
    MIME_TYPES = ['text', 'image', 'audio', 'video', 'application', 'multipart', 'message']
    def __new__(cls, value: AnyStr):
        dfm = [x for x in value.split(';')]
        mime_type: str = dfm.pop(0)
        if (i := mime_type.find('/')) == -1:
            raise ValueError("MIME type specification must be 'type/subtype[;param=value;...]'")
        if mime_type[:i] not in cls.MIME_TYPES:
            raise ValueError(f"MIME type '{mime_type[:i]}' not supported")
        if [i for i in dfm if '=' not in i]:
            raise ValueError("Wrong specification of MIME type parameters")
        return str.__new__(cls, value)
    def __repr__(self):
        return f"MIME('{self}')"
    @property
    def mime_type(self) -> str:
        "MIME type specification: <type>/<subtype>"
        if ';' in self:
            return self[:self.find(';')]
        return self
    @property
    def type(self) -> str:
        "MIME type"
        return self[:self.find('/')]
    @property
    def subtype(self) -> str:
        "MIME subtype"
        if ';' in self:
            return self[self.find('/')+1:self.find(';')]
        return self[self.find('/')+1]
    @property
    def params(self) -> Dict[str, str]:
        "MIME parameters"
        if ';' in self:
            return {k.strip(): v.strip() for k, v in (x.split('=') for x in self[self.find(';')+1:].split(';'))}
        return {}

class PyExpr(str):
    """Source code for Python expression.

It behaves like `str`, but checks that value is a valid Python expression, and provides
direct access to compiled code.

Raises:
    SyntaxError: When string value is not a valid Python expression.
"""
    _expr_ = None
    def __new__(cls, value: str):
        expr = compile(value, "PyExpr", 'eval')
        new = str.__new__(cls, value)
        new._expr_ = expr
        return new
    def __repr__(self):
        return f"PyExpr('{self}')"
    def get_callable(self, arguments: str='', namespace: Dict[str, Any]=None) -> Callable:
        """Returns expression as callable function ready for execution.

Arguments:
    arguments: String with arguments (names separated by coma) for returned function.
"""
        ns = {}
        if namespace:
            ns.update(namespace)
        code = compile(f"def expr({arguments}):\n    return {self}",
                       "PyExpr", 'exec')
        eval(code, ns)
        return ns['expr']
    @property
    def expr(self):
        "Expression code ready to be appased to `eval`."
        return self._expr_

class PyCode(str):
    """Python source code.

It behaves like `str`, but checks that value is a valid Python code block, and provides
direct access to compiled code.

Raises:
    SyntaxError: When string value is not a valid Python code block.
"""
    _code_ = None
    def __new__(cls, value: str):
        code = compile(value, "PyCode", 'exec')
        new = str.__new__(cls, value)
        new._code_ = code
        return new
    @property
    def code(self):
        "Python code ready to be appased to `exec`."
        return self._code_

class PyCallable(str):
    """Source code for Python callable.

It behaves like `str`, but checks that value is a valid Python callable (function of class
definition), and acts like a callable (i.e. you can directly call the PyCallable value).

Raises:
    ValueError: When string value does not contains the function or class definition.
    SyntaxError: When string value is not a valid Python callable.
"""
    _callable_ = None
    def __new__(cls, value: str):
        callable_name = None
        for line in value.split('\n'):
            if line.lower().startswith('def '):
                callable_name = line[4:line.find('(')].strip()
                break
        if callable_name is None:
            for line in value.split('\n'):
                if line.lower().startswith('class '):
                    callable_name = line[6:line.find('(')].strip()
                    break
        if callable_name is None:
            raise ValueError("Python function or class definition not found")
        ns = {}
        eval(compile(value, "PyCallable", 'exec'), ns)
        new = str.__new__(cls, value)
        new._callable_ = ns[callable_name]
        new.name = callable_name
        return new
    def __call__(self, *args, **kwargs):
        return self._callable_(*args, **kwargs)

# Metaclasses

def Conjunctive(name, bases, attrs):
    """Returns a metaclass that is conjunctive descendant of all metaclasses used by parent
classes.

Example:

    class A(type): pass

    class B(type): pass

    class AA(metaclass=A):pass

    class BB(metaclass=B):pass

    class CC(AA, BB, metaclass=Conjunctive): pass
"""
    basemetaclasses = []
    for base in bases:
        metacls = type(base)
        if isinstance(metacls, type) and metacls is not type and not metacls in basemetaclasses:
            basemetaclasses.append(metacls)
    dynamic = type(''.join(b.__name__ for b in basemetaclasses), tuple(basemetaclasses), {})
    return dynamic(name, bases, attrs)
