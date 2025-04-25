# SPDX-FileCopyrightText: 2020-present The Firebird Projects <www.firebirdsql.org>
#
# SPDX-License-Identifier: MIT
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
#                 Tom Bulled (new Sentinels)
#                 ______________________________________

"""Firebird Base - Core Types and Utilities

This module provides fundamental building blocks used across the `firebird-base`
package and potentially other Firebird Python projects. It includes:

- A custom base exception class (`Error`).
- Utilities for creating Singletons (`Singleton`).
- A robust implementation for Sentinel objects (`Sentinel`) and common predefined sentinels.
- Base classes for objects with distinct identities based on keys (`Distinct`, `CachedDistinct`).
- Enumerations for specific concepts (`ByteOrder`, `ZMQTransport`, `ZMQDomain`).
- Enhanced string types with validation and added functionality (`ZMQAddress`, `MIME`,
  `PyExpr`, `PyCode`, `PyCallable`).
- Metaclass utilities (`conjunctive`).
- Helper functions (`load`).
"""

from __future__ import annotations

import sys
import types
from abc import ABC, ABCMeta, abstractmethod
from collections.abc import Callable, Hashable
from enum import Enum, IntEnum
from importlib import import_module
from typing import Any, AnyStr, ClassVar, Self, cast
from weakref import WeakValueDictionary

# Exceptions

class Error(Exception):
    """Exception intended as a base for application-related errors.

    Unlike the standard `Exception`, this class accepts arbitrary keyword
    arguments during initialization. These keyword arguments are stored as
    attributes on the exception instance.

    Attribute lookup on instances of `Error` (or its subclasses) will return
    `None` for any attribute that was not explicitly set via keyword arguments
    during `__init__`, preventing `AttributeError` for common checks.

    Important:
        Attribute lookup on this class never fails, as all attributes that are not actually
        set, have `None` value. The special attribute `__notes__` (used by `add_note`
        since Python 3.11) is explicitly excluded from this behavior to ensure
        compatibility.

    Example::

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
        Warnings are not errors and should typically derive from `Warning`,
        not this class.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args)
        for name, value in kwargs.items():
            setattr(self, name, value)
    def __getattr__(self, name) -> Any | None:
        # Prevent AttributeError for unset attributes, default to None.
        # Explicitly raise AttributeError for __notes__ to allow standard
        # exception note handling to work correctly.
        if name == '__notes__':
            raise AttributeError
        return None # Default value for attributes not set in __init__

# Singletons

_singletons_ = {}

class SingletonMeta(type):
    """Metaclass for `Singleton` classes.

    Manages internal cache of class instances. If instance for a class is in cache, it's
    returned without calling the constructor, otherwise the instance is created normally
    and stored in cache for later use.
    """
    def __call__(cls: type[Singleton], *args, **kwargs) -> Singleton:
        name = f"{cls.__module__}.{cls.__qualname__}"
        obj = _singletons_.get(name)
        if obj is None:
            obj = super().__call__(*args, **kwargs)
            _singletons_[name] = obj
        return obj

class Singleton(metaclass=SingletonMeta):
    """Base class for singletons.

    Ensures that only one instance of a class derived from `Singleton` exists.
    Subsequent attempts to 'create' an instance will return the existing one.

    Important:
        If a descendant class's `__init__` method accepts arguments, these
        arguments are only used the *first* time the instance is created.
        Subsequent calls that retrieve the cached instance will *not* invoke
        `__init__` again.

    Example::

        class MyService(Singleton):
            def __init__(self, config_param=None):
                if hasattr(self, '_initialized'): # Prevent re-init
                    return
                print("Initializing MyService...")
                self.config = config_param
                self._initialized = True

            def do_something(self):
                print(f"Doing something with config: {self.config}")

        service1 = MyService("config1") # Prints "Initializing MyService..."
        service2 = MyService("config2") # Does *not* print, returns existing instance

        print(service1 is service2) # Output: True
        service2.do_something()     # Output: Doing something with config: config1
    """

# Sentinels

class _SentinelMeta(type):
    """Metaclass for Sentinel objects.

    This metaclass ensures that classes defined using it behave as
    proper sentinels:

    - They cannot be instantiated directly (e.g., `MySentinel()`).
    - They cannot be subclassed after initial definition.
    - Provides a basic `__repr__` and `__str__` based on the class name.
    - Allows defining sentinels via class definition (`class NAME(Sentinel): ...`)
      or potentially a functional call (though class definition is preferred).
    - Neuters `__call__` inherited from `type` to prevent unintended behavior.
    """

    def __new__(metaclass, name, bases, namespace): # noqa: N804
        def __new__(cls, *args, **kwargs): # noqa: N807, ARG001
            raise TypeError(f'Cannot initialise or subclass sentinel {cls.__name__!r}')
        cls = super().__new__(metaclass, name, bases, namespace)
        # We are creating a sentinel, neuter it appropriately
        if type(metaclass) is metaclass:
            cls_call = getattr(cls, '__call__', None) # noqa B004
            metaclass_call = getattr(metaclass, '__call__', None) # noqa B004
            # If the class did not provide it's own `__call__`
            # and therefore inherited the `__call__` belongining
            # to it's metaclass, get rid of it.
            # This prevents sentinels inheriting the Functional API.
            if cls_call is not None and cls_call is metaclass_call:
                cls.__call__ = super().__call__
            # Neuter the sentinel's `__new__` to prevent it
            # from being initialised or subclassed
            cls.__new__ = __new__
        # Sentinel classes must derive from their metaclass,
        # otherwise the object layout will differ
        if not issubclass(cls, metaclass):
            raise TypeError(f'{metaclass.__name__!r} must also be derived from when provided as a metaclass')
        cls.__class__ = cls
        return cls
    def __call__(cls, name, bases=None, namespace=None, /, *, repr=None) -> type[Sentinel]: # noqa: A002
        # Attempts to subclass/initialise derived classes will end up
        # arriving here.
        # In these cases, we simply redirect to `__new__`
        if bases is not None:
            return cls.__new__(cls, name, bases, namespace)
        bases = (cls,)
        namespace = {}
        # If a custom `repr` was provided, create an appropriate
        # `__repr__` method to be added to the sentinel class
        if repr is not None:
            def __repr__(cls): # noqa: ARG001, N807
                return repr
            namespace['__repr__'] =__repr__
        return cls.__new__(cls, name, bases, namespace)
    def __str__(cls):
        return cls.__name__
    def __repr__(cls):
        return cls.__name__
    @property
    def name(cls):
        return cls.__name__

class Sentinel(_SentinelMeta, metaclass=_SentinelMeta):
    """Base class for creating unique sentinel objects.

    Sentinels are special singleton objects used to signal unique states or
    conditions, particularly useful when `None` might be a valid data value.
    They offer a more explicit and readable alternative to magic constants
    or using `object()`.

    You can define specific sentinels in two primary ways:

    1.  **By Subclassing:** Inherit directly from `Sentinel`. The name of the
        subclass becomes the sentinel's identity.

        .. code-block:: python

            class DEFAULT(Sentinel):
                "Represents a default value placeholder."

            class ALL(Sentinel):
                "Represents all possible values."

        This creates classes `DEFAULT` and `ALL`, each acting as a unique
        sentinel object.

    2.  **Using the Functional Call:** Use the `Sentinel` base class itself
        as a factory function.

        .. code-block:: python

            # Signature: Sentinel(name: str, *, repr: str | None = None) -> Sentinel
            NOT_FOUND = Sentinel("NOT_FOUND", repr="<Value Not Found>")
            UNKNOWN = Sentinel("UNKNOWN")

        - The required `name` argument (e.g., `"NOT_FOUND"`) specifies the
          `__name__` of the dynamically created sentinel class.
        - The optional `repr` keyword argument provides a custom string
          to be returned by `repr()` for this specific sentinel. If omitted,
          `repr()` defaults to the sentinel's name.

        This dynamically creates new classes derived from `Sentinel`, assigns
        them to the variables (`NOT_FOUND`, `UNKNOWN`), and sets a custom
        `__repr__` if provided.

    **Behavior:**

    Regardless of the creation method:

    - Each sentinel is a unique object (a class behaving as a singleton).
    - Sentinels are identified using the `is` operator.
    - They cannot be instantiated (e.g., `DEFAULT()` raises `TypeError`).
    - They cannot be subclassed further after their initial definition.
    - `str(MySentinel)` returns the sentinel's name (`MySentinel.__name__`).
    - `repr(MySentinel)` returns the custom `repr` if provided via the
      functional call, otherwise it defaults to the sentinel's name.

    **Example Usage:**

    .. code-block:: python

        # Define using subclassing
        class DEFAULT_SETTING(Sentinel):
            "Indicates a setting should use its compiled-in default."

        # Define using functional call with custom repr
        NOT_APPLICABLE = Sentinel("NOT_APPLICABLE", repr="<N/A>")

        def get_config(key, user_override=NOT_APPLICABLE):
            if user_override is NOT_APPLICABLE:
                # User did not provide an override, check stored config
                value = read_stored_config(key, default=DEFAULT_SETTING)
                if value is DEFAULT_SETTING:
                    return get_hardcoded_default(key)
                return value
            else:
                # User provided an override (which could be None)
                return user_override

        config1 = get_config("timeout") # Uses stored or hardcoded default
        config2 = get_config("retries", user_override=None) # Explicitly set to None
        config3 = get_config("feature_flag", user_override=NOT_APPLICABLE) # Same as providing nothing

        print(repr(DEFAULT_SETTING)) # Output: DEFAULT_SETTING
        print(repr(NOT_APPLICABLE))  # Output: <N/A>

    """
    # Note: The actual implementation relies on _SentinelMeta for the behaviors described.
    # The methods like __str__, __repr__, name property are defined on the metaclass.

# Useful sentinel objects

class DEFAULT(Sentinel):
    "Sentinel that denotes default value"

class INFINITY(Sentinel):
    "Sentinel that denotes infinity value"

class UNLIMITED(Sentinel):
    "Sentinel that denotes unlimited value"

class UNKNOWN(Sentinel):
    "Sentinel that denotes unknown value"

class NOT_FOUND(Sentinel): # noqa: N801
    "Sentinel that denotes a condition when value was not found"

class UNDEFINED(Sentinel):
    "Sentinel that denotes explicitly undefined value"

class ANY(Sentinel):
    "Sentinel that denotes any value"

class ALL(Sentinel):
    "Sentinel that denotes all possible values"

class SUSPEND(Sentinel):
    "Sentinel that denotes suspend request (in message queue)"

class RESUME(Sentinel):
    "Sentinel that denotes resume request (in message queue)"

class STOP(Sentinel):
    "Sentinel that denotes stop request (in message queue)"

# Distinct objects
class Distinct(ABC):
    """Abstract base class for objects with distinct instances based on a key.

    Instances are considered equal (`==`) if their keys, returned by
    `get_key()`, are equal. The hash of an instance is derived from the
    hash of its key by default.

    .. important::

       If used with `@dataclass`, it must be defined with `eq=False`
       to prevent overriding the custom `__eq__` and `__hash__` methods:

       .. code-block:: python

           from dataclasses import dataclass

           @dataclass(eq=False)
           class MyDistinctData(Distinct):
               id: int
               name: str

               def get_key(self) -> Hashable:
                   return self.id

    """
    @abstractmethod
    def get_key(self) -> Hashable:
        """Return the unique key identifying this instance.

        The key must be hashable. It determines equality and hashing
        behavior unless `__eq__` or `__hash__` are explicitly overridden.
        """
    def __hash(self) -> int:
        return hash(self.get_key())
    def __eq__(self, other) -> bool:
        if isinstance(other, Distinct):
            return self.get_key() == other.get_key()
        return False
    __hash__ = __hash

class CachedDistinctMeta(ABCMeta):
    """Metaclass for `CachedDistinct`.

    Intercepts class instantiation (`__call__`) to implement the instance
    caching mechanism based on the key extracted by `cls.extract_key()`.
    Ensures that only one instance exists per unique key.
    """
    def __call__(cls: type[CachedDistinct], *args, **kwargs) -> CachedDistinct:
        key = cls.extract_key(*args, **kwargs)
        obj = cls._instances_.get(key)
        if obj is None:
            obj = super().__call__(*args, **kwargs)
            cls._instances_[key] = obj
        return obj

class CachedDistinct(Distinct, metaclass=CachedDistinctMeta):
    """Abstract `Distinct` descendant that caches instances.

    Behaves like `Distinct`, but ensures only one instance is created per
    unique key. Subsequent attempts to create an instance with the same key
    (as determined by `extract_key` from the constructor arguments) will
    return the cached instance instead of creating a new one.

    Instances are stored in a class-level `~weakref.WeakValueDictionary`,
    allowing them to be garbage-collected if no longer referenced elsewhere.

    Requires implementation of both `get_key()` (for instance equality/hashing)
    and `extract_key()` (for retrieving the key from constructor arguments
    *before* instance creation). These two methods should conceptually return
    the same identifier for a given object identity.

    .. important::
        Like `Distinct`, if used with `@dataclass`, define with `eq=False`.

    Example::

        from dataclasses import dataclass

        @dataclass(eq=False) # Important!
        class User(CachedDistinct):
            user_id: int
            name: str

            def get_key(self) -> int:
                return self.user_id

            @classmethod
            def extract_key(cls, user_id: int, name: str) -> int:
                # Extracts the key from __init__ args
                return user_id

        user1 = User(1, "Alice")
        user2 = User(2, "Bob")
        user3 = User(1, "Alice") # Name might be different here, but key is the same

        print(user1 is user3)  # Output: True (cached instance returned)
        print(user1 == user3)  # Output: True (equality based on get_key)
        print(user1 is user2)  # Output: False
    """
    def __init_subclass__(cls: type, /, **kwargs) -> None:
        super().__init_subclass__(**kwargs)
        cls._instances_ = WeakValueDictionary()
    @classmethod
    @abstractmethod
    def extract_key(cls: type[CachedDistinct], *args, **kwargs) -> Hashable:
        """Returns key from arguments passed to `__init__()`.

        Important:
            The key is used to store instance in cache. It should be the same as key
            returned by instance `Distinct.get_key()`!
        """

# Enums
class ByteOrder(Enum):
    """Byte order for storing numbers in binary `.MemoryBuffer`.
    """
    LITTLE = 'little'
    BIG = 'big'
    NETWORK = BIG

class ZMQTransport(IntEnum):
    """ZeroMQ transport protocol.
    """
    UNKNOWN = 0 # Not a valid option, defined only to handle undefined values
    INPROC = 1
    IPC = 2
    TCP = 3
    PGM = 4
    EPGM = 5
    VMCI = 6

class ZMQDomain(IntEnum):
    """ZeroMQ address domain.
    """
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

    Example::

        addr_str = "tcp://127.0.0.1:5555"
        zmq_addr = ZMQAddress(addr_str)

        print(zmq_addr)                 # Output: tcp://127.0.0.1:5555
        print(repr(zmq_addr))           # Output: ZMQAddress('tcp://127.0.0.1:5555')
        print(zmq_addr.protocol)        # Output: ZMQTransport.TCP
        print(zmq_addr.address)         # Output: 127.0.0.1:5555
        print(zmq_addr.domain)          # Output: ZMQDomain.NODE

        try:
            invalid = ZMQAddress("myfile.txt")
        except ValueError as e:
            print(e)                    # Output: Protocol specification required
    """
    def __new__(cls, value: AnyStr, encoding: str = 'utf8') -> Self:
        if isinstance(value, bytes):
            value = cast(bytes, value).decode(encoding)
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
        """Transport protocol (e.g., TCP, IPC, INPROC)."""
        protocol, _ = self.split('://', 1)
        return ZMQTransport._member_map_[protocol.upper()]
    @property
    def address(self) -> str:
        """Endpoint address part (following '://')."""
        _, address = self.split('://', 1)
        return address
    @property
    def domain(self) -> ZMQDomain:
        """Endpoint address domain (LOCAL, NODE, NETWORK)."""
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
    """MIME type specification string (e.g., 'text/plain; charset=utf-8').

    Behaves like `str`, but validates the input format (`type/subtype[;params]`)
    upon creation and provides convenient read-only properties to access parts
    of the specification.

    Raises:
        ValueError: If the input string is not a valid MIME type specification
                    (missing '/', unsupported type, invalid parameters).

    Example::

        mime1_str = "application/json"
        mime1 = MIME(mime1_str)
        print(mime1)            # Output: application/json
        print(repr(mime1))      # Output: MIME('application/json')
        print(mime1.type)       # Output: application
        print(mime1.subtype)    # Output: json
        print(mime1.params)     # Output: {}

        mime2_str = "text/html; charset=UTF-8"
        mime2 = MIME(mime2_str)
        print(mime2.mime_type)  # Output: text/html
        print(mime2.params)     # Output: {'charset': 'UTF-8'}

        try:
            invalid_mime = MIME("application")
        except ValueError as e:
            print(e) # Output: MIME type specification must be 'type/subtype[;param=value;...]'

        try:
            invalid_mime = MIME("myapp/data") # 'myapp' is not a standard type
        except ValueError as e:
            print(e) # Output: MIME type 'myapp' not supported

    """
    #: Supported base MIME types
    MIME_TYPES: ClassVar[list[str]] = ['text', 'image', 'audio', 'video', 'application', 'multipart', 'message']
    def __new__(cls, value: str) -> Self:
        dfm = list(value.split(';'))
        mime_type: str = dfm.pop(0).strip()
        if (i := mime_type.find('/')) == -1:
            raise ValueError("MIME type specification must be 'type/subtype[;param=value;...]'")
        if mime_type[:i] not in cls.MIME_TYPES:
            raise ValueError(f"MIME type '{mime_type[:i]}' not supported")
        if [i for i in dfm if '=' not in i]:
            raise ValueError("Wrong specification of MIME type parameters")
        # Check parameters format
        if any('=' not in p for p in dfm if p.strip()): # Check non-empty params
            raise ValueError("Wrong specification of MIME type parameters (should be key=value)")
        obj = str.__new__(cls, value)
        # Store indices after validation and potential stripping
        obj._bs_: int = obj.find('/')
        obj._fp_: int = obj.find(';')
        return obj
    def __repr__(self):
        return f"MIME('{self}')"
    @property
    def mime_type(self) -> str:
        """The base MIME type specification: '<type>/<subtype>'."""
        if self._fp_ != -1:
            return self[:self._fp_]
        return self
    @property
    def type(self) -> str:
        """The main MIME type (e.g., 'text', 'application')."""
        return self[:self._bs_]
    @property
    def subtype(self) -> str:
        """The MIME subtype (e.g., 'plain', 'json')."""
        if self._fp_ != -1:
            return self[self._bs_ + 1:self._fp_]
        return self[self._bs_ + 1:]
    @property
    def params(self) -> dict[str, str]:
        """MIME parameters as a dictionary (e.g., {'charset': 'utf-8'})."""
        if self._fp_ != -1:
            # Split parameters, then split each into key/value, stripping whitespace
            return {k.strip(): v.strip() for k, v
                    in (x.split('=') for x in self[self._fp_+1:].split(';'))}
        return {}

class PyExpr(str):
    """Source code string representing a single Python expression.

    Behaves like `str`, but validates that the content is a syntactically
    valid Python expression during initialization by attempting to compile it
    in 'eval' mode. Provides access to the compiled code object and a helper
    to create a callable function from the expression.

    Raises:
        SyntaxError: If the string value is not a valid Python expression.

    Example::

        expr_str = "a + b * 2"
        py_expr = PyExpr(expr_str)

        print(py_expr)           # Output: a + b * 2
        print(repr(py_expr))     # Output: PyExpr('a + b * 2')

        # Get the compiled code object
        code_obj = py_expr.expr
        print(eval(code_obj, {'a': 10, 'b': 5})) # Output: 20

        # Get a callable function
        func = py_expr.get_callable(arguments='a, b')
        print(func(a=3, b=4))    # Output: 11

        # Using a namespace
        import math
        log_expr = PyExpr("math.log10(x)")
        log_func = log_expr.get_callable(arguments='x', namespace={'math': math})
        print(log_func(x=100))   # Output: 2.0

        try:
            invalid_expr = PyExpr("a = 5") # Assignment is not an expression
        except SyntaxError as e:
            print(e)              # Output: invalid syntax (<string>, line 1) or similar

    """
    _expr_: types.CodeType = None # Compiled code object
    def __new__(cls, value: str) -> Self:
        new = str.__new__(cls, value)
        # Validate by compiling in 'eval' mode
        new._expr_ = compile(value, '<PyExpr>', 'eval')
        return new
    def __repr__(self):
        return f"PyExpr('{self}')"
    def get_callable(self, arguments: str='', namespace: dict[str, Any] | None=None) -> Callable:
        """Returns the expression wrapped in a callable function.

        Arguments:
            arguments: Comma-separated string of argument names for the function signature.
            namespace: Optional dictionary providing the execution namespace for the expression.
                       Can be used to provide access to modules or specific values.

        Returns:
            A callable function that takes the specified arguments and returns
            the result of evaluating the expression.
        """
        ns = {}
        if namespace:
            ns.update(namespace)
        # Create function definition string dynamically
        func_def = f"def expr({arguments}):\n    return {self}"
        # Compile the function definition in 'exec' mode
        code = compile(func_def, '<PyExpr Function>', 'exec')
        # Execute the compiled code to define the function in the namespace 'ns'
        eval(code, ns) # noqa: S307 Using eval safely with controlled input
        # Return the defined function
        return ns['expr']
    @property
    def expr(self) -> types.CodeType:
        """The compiled expression code object, ready for `eval()`."""
        return self._expr_

class PyCode(str):
    """Source code string representing a block of Python statements.

    Behaves like `str`, but validates that the content is a syntactically
    valid Python code block (potentially multiple statements) during
    initialization by attempting to compile it in 'exec' mode. Provides access
    to the compiled code object.

    Raises:
        SyntaxError: If the string value is not a valid Python code block.

    Example::

        code_str = '''
        import math
        result = math.sqrt(x * y)
        print(f"Result: {result}")
        '''
        py_code = PyCode(code_str)

        print(py_code[:20])      # Output: import math\\nresult
        print(repr(py_code))     # Output: PyCode('import math\\nresult = ...')

        # Get the compiled code object
        code_obj = py_code.code

        # Execute the code block
        exec_namespace = {'x': 4, 'y': 9}
        exec(code_obj, exec_namespace) # Output: Result: 6.0
        print(exec_namespace['result']) # Output: 6.0

        try:
            # Invalid syntax (e.g., unmatched parenthesis)
            invalid_code = PyCode("print('Hello'")
        except SyntaxError as e:
            print(e)             # Output: unexpected EOF while parsing (<string>, line 1) or similar
    """
    _code_: types.CodeType = None # Compiled code object
    def __new__(cls, value: str) -> Self:
        # Validate by compiling in 'exec' mode
        code = compile(value, '<PyCode>', 'exec')
        new = str.__new__(cls, value)
        new._code_ = code
        return new
    def __repr__(self) -> str:
        # Truncate long strings in repr for readability
        limit = 50
        ellipsis = "..." if len(self) > limit else ""
        return f"PyCode('{self[:limit]}{ellipsis}')"
    @property
    def code(self) -> types.CodeType:
        """The compiled Python code object, ready for `exec()`."""
        return self._code_

class PyCallable(str):
    """Source code string representing a Python callable (function or class definition).

    Behaves like `str`, but validates that the content is a syntactically
    valid Python function or class definition during initialization. It compiles
    and executes the definition to capture the resulting callable object.

    Instances of `PyCallable` are themselves callable, acting as a proxy to the
    defined function or class.

    Raises:
        ValueError: If the string does not contain a recognizable 'def ' or 'class '
                    definition at the top level.
        SyntaxError: If the string contains syntactically invalid Python code.
        NameError: If the definition relies on names not available during its execution.

    Example::

        func_str = '''
        def greet(name):
            "Greets the person."
            return f"Hello, {name}!"
        '''
        py_func = PyCallable(func_str)

        print(py_func.name)      # Output: greet
        print(py_func.__doc__)   # Output: Greets the person.
        print(repr(py_func))     # Output: PyCallable('def greet(name):\\n    ...')

        # Call the instance directly
        message = py_func(name="World")
        print(message)           # Output: Hello, World!

        class_str = '''
        class MyNumber:
            def __init__(self, value):
                self.value = value
            def double(self):
                return self.value * 2
        '''
        py_class = PyCallable(class_str)

        print(py_class.name)     # Output: MyNumber
        instance = py_class(value=10) # Instantiate the class via the PyCallable object
        print(instance.double()) # Output: 20

        try:
            # Missing 'def' or 'class'
            invalid = PyCallable("print('Hello')")
        except ValueError as e:
            print(e)             # Output: Python function or class definition not found

        try:
            # Syntax error in definition
            invalid = PyCallable("def my_func(x:")
        except SyntaxError as e:
            print(e)             # Output: invalid syntax (<string>, line 1) or similar
    """
    _callable_: Callable | type = None
    #: Name of the defined function or class.
    name: str = None
    def __new__(cls, value: str) -> Self:
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
        # Compile and execute the code to define the callable in a temporary namespace
        ns = {}
        try:
            code_obj = compile(value, '<PyCallable>', 'exec')
            eval(code_obj, ns) # noqa: S307 Use eval cautiously; input should be trusted/validated
        except SyntaxError as e:
            raise SyntaxError(f"Invalid syntax in callable definition: {e}") from e
        except Exception as e: # Catch other potential errors during definition execution (e.g., NameError)
            raise RuntimeError(f"Error executing callable definition: {e}") from e

        if callable_name not in ns:
            # This might happen if the parsed name doesn't match the actual definition
            raise ValueError(f"Could not find defined callable named '{callable_name}' after execution. Check definition.") # noqa: E501

        new = str.__new__(cls, value)
        new._callable_ = ns[callable_name]
        new.name = callable_name
        # Copy docstring if present
        new.__doc__ = getattr(new._callable_, '__doc__', None)
        return new
    def __call__(self, *args, **kwargs) -> Any:
        """Calls the wrapped function or instantiates the wrapped class."""
        return self._callable_(*args, **kwargs)
    def __repr__(self) -> str:
        limit = 50
        ellipsis = "..." if len(self) > limit else ""
        # Show the beginning of the code string
        string = self[:limit].replace('\\n', '\\\\n')
        return f"PyCallable('{string}{ellipsis}')"

# Metaclasses
def conjunctive(name, bases, attrs) -> type:
    """Returns a metaclass that is conjunctive descendant of all metaclasses used by parent
    classes. It's necessary to create a class with multiple inheritance, where multiple
    parent classes use different metaclasses.

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
        if isinstance(metacls, type) and metacls is not type and metacls not in basemetaclasses:
            basemetaclasses.append(metacls)
    dynamic = type(''.join(b.__name__ for b in basemetaclasses), tuple(basemetaclasses), {})
    return dynamic(name, bases, attrs)

# Functions
def load(spec: str) -> Any:
    """Dynamically load an object (class, function, variable) from a module.

    The module is imported automatically if it hasn't been already.

    Arguments:
        spec: Object specification string in the format
              `'module[.submodule...]:object_name[.attribute...]'`.

    Returns:
        The loaded object.

    Raises:
        ImportError: If the module cannot be imported.
        AttributeError: If the specified object cannot be found within the module.

    Example::

        # Assuming 'my_package/my_module.py' contains: class MyClass: pass
        MyClassRef = load("my_package.my_module:MyClass")
        instance = MyClassRef()

        # Load a function
        pprint_func = load("pprint:pprint")
        pprint_func({"a": 1})
    """
    module_spec, name = spec.split(':')
    if module_spec in sys.modules:
        module = sys.modules[module_spec]
    else:
        module = import_module(module_spec)
    result = module
    for item in name.split('.'):
        result = getattr(result, item)
    return result

