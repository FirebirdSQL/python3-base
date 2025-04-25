# SPDX-FileCopyrightText: 2020-present The Firebird Projects <www.firebirdsql.org>
#
# SPDX-License-Identifier: MIT
#
# PROGRAM/MODULE: firebird-base
# FILE:           firebird/base/signal.py
# DESCRIPTION:    Callback system based on Signals and Slots, and "Delphi events"
# CREATED:        22.11.2020
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
# Copyright (c) 2016 Dhruv Govil, PySignal 1.1.4, original code
# fork source: https://github.com/dgovil/PySignal
# Copyright (c) 2020 Firebird Project (www.firebirdsql.org), after fork
# All Rights Reserved.
#
# Contributor(s): Based on PySignal 1.1.4 contributors: John Hood, Jason Viloria,
#                 Adric Worley, Alex Widener
#                 Pavel Císař - fork and reduction & adaptation for firebird-base and
#                               Python 3.8, added Delphi events
#                 ______________________________________

"""firebird-base - Callback system based on Signals and Slots, and "Delphi events"

TThis module provides two callback mechanisms:

1.  **Signals and Slots (`Signal`, `signal` decorator):** Inspired by Qt, a signal
    can be connected to multiple slots (callbacks). When the signal is emitted,
    all connected slots are called. Return values from slots are ignored.
2.  **Eventsockets (`eventsocket` decorator):** Similar to Delphi events, an
    eventsocket holds a reference to a *single* slot (callback). Assigning a new
    slot replaces the previous one. Calling the eventsocket delegates the call
    directly to the connected slot. Return values are passed back from the slot.

In both cases, slots can be functions, instance/class methods, `functools.partial`
objects, or lambda functions. The `inspect` module is used to enforce signature
matching between the signal/eventsocket definition and the connected slots.
"""

from __future__ import annotations

from collections.abc import Callable
from functools import partial
from inspect import Signature, ismethod
from typing import Any
from weakref import ReferenceType, WeakKeyDictionary, ref


class Signal:
    """Handles connections between a signal and multiple slots (callbacks).

    When the signal is emitted, all connected slots are called with the
    provided arguments. Return values from slots are ignored.

    Arguments:
        signature: The `inspect.Signature` object defining the expected parameters for
                   connected slots.

    Important:
        Only slots that match the signature could be connected to signal. The check is
        performed only on parameters, and not on return value type (as signals does
        not have/ignore return values).

        The match must be exact, including type annotations, parameter names, order,
        parameter type etc. The sole exception to this rule are excess slot keyword
        arguments with default values.

    Note:
        Signal functions with signatures different from signal could be adapted using
        `functools.partial`. However, you can "mask" only keyword arguments (without
        default) and leading positional arguments (as any positional argument binded
        by name will not mask-out parameter from signature introspection).
    """
    def __init__(self, signature: Signature):
        self._sig: Signature = signature.replace(parameters=[p for p in signature.parameters.values()
                                                             if p.name != 'self'],
                                                 return_annotation=Signature.empty)
        #: Toggle to block / unblock signal transmission
        self.block: bool = False
        self._slots: list[Callable | ReferenceType[Callable]] = []
        self._islots: WeakKeyDictionary = WeakKeyDictionary()
    def __call__(self, *args, **kwargs):
        """Shortcut for `emit(*args, **kwargs)`."""
        self.emit(*args, **kwargs)
    def _kw_test(self, sig: Signature) -> bool:
        """Internal helper to check if the only difference between `sig` and `self._sig`
        is the presence of extra keyword arguments with default values in `sig`.
        """
        p = sig.parameters
        result = False
        for k in set(p).difference(set(self._sig.parameters)):
            result = True
            if p[k].default is Signature.empty:
                return False
        return result
    def emit(self, *args, **kwargs) -> None:
        """Emit the signal, calling all connected slots with the given arguments.

        Does nothing if `self.block` is True. Handles different storage types
        (functions, methods, lambdas, partials) correctly.

        Arguments:
            *args: Positional arguments to pass to the slots.
            **kwargs: Keyword arguments to pass to the slots.
        """
        if self.block:
            return
        for slot in self._slots:
            if isinstance(slot, partial):
                slot(*args, **kwargs)
            elif isinstance(slot, ref):
                # If it's a weakref, call the ref to get the instance and then call the func
                # Don't wrap in try/except so we don't risk masking exceptions from the actual func call
                if (t_slot := slot()) is not None:
                    t_slot(*args, **kwargs)
            else:
                # Else call it in a standard way. Should be just lambdas at this point
                slot(*args, **kwargs)
        for obj, method in self._islots.items():
            method(obj, *args, **kwargs)
    def connect(self, slot: Callable) -> None:
        """Connect a callable slot to this signal.

        The slot will be called whenever the signal is emitted.

        Arguments:
            slot: The callable (function, method, lambda, partial) to connect.
                  Its signature must match the signal's signature (see class docs).

        Raises:
            ValueError: If `slot` is not callable or if its signature does not match
                    the signal's signature (parameters and their types/names/kinds,
                    excluding return type and allowing extra keyword args with defaults).

        Storage Note:

        - Regular functions are stored using `weakref.ref` to avoid preventing
          garbage collection if the signal outlives the function's scope.
        - Instance methods are stored using a `WeakKeyDictionary` mapping the
          instance (weakly) to the unbound function.
        - Lambdas and `functools.partial` objects are stored directly, as weak
          references to them are often problematic.
        """
        if not callable(slot):
            raise ValueError(f"Connection to non-callable '{slot.__class__.__name__}' object failed")
        # Verify signatures
        sig = Signature.from_callable(slot).replace(return_annotation=Signature.empty)
        if str(sig) != str(self._sig):
            # Check if the difference is only in keyword arguments with defaults.
            if not self._kw_test(sig):
                raise ValueError("Callable signature does not match the signal signature")
        if isinstance(slot, partial) or slot.__name__ == '<lambda>':
            # If it's a partial or a lambda.
            if slot not in self._slots:
                self._slots.append(slot)
        elif ismethod(slot):
            # Check if it's an instance method and store it with the instance as the key
            self._islots[slot.__self__] = slot.__func__
        else:
            # If it's just a function then just store it as a weakref.
            new_slot_ref = ref(slot)
            if new_slot_ref not in self._slots:
                self._slots.append(new_slot_ref)
    def disconnect(self, slot: Callable) -> None:
        """Disconnect a previously connected slot from the signal.

        Attempts to remove the specified slot. Does nothing if the slot
        is not currently connected or not callable.

        Arguments:
            slot: The callable that was previously passed to `connect()`.
        """
        if not callable(slot):
            return

        if ismethod(slot):
            # If it's a method, then find it by its instance
            self._islots.pop(slot.__self__, None)
        elif isinstance(slot, partial) or slot.__name__ == '<lambda>':
            # If it's a partial, a Signal or lambda, try to remove directly
            try:
                self._slots.remove(slot)
            except ValueError:
                pass
        else:
            # It's probably a function, so try to remove by weakref
            try:
                self._slots.remove(ref(slot))
            except ValueError:
                pass
    def clear(self) -> None:
        """Clears the signal of all connected slots.
        """
        self._slots.clear()
        self._islots.clear()


class signal: # noqa: N801
    """Decorator to define a `Signal` instance as a read-only property on a class.

    The decorated function's signature (excluding 'self') defines the required
    signature for slots connecting to this signal. The body of the decorated
    function is never executed.

    A unique `Signal` instance is lazily created for each object instance the
    first time the signal property is accessed.

    Example::

        class MyClass:
            @signal
            def value_changed(self, new_value: int):
                # This signature dictates slots must accept (new_value: int)
                pass # Body is ignored

        instance = MyClass()
        instance.value_changed.connect(my_slot_function)
        instance.value_changed.emit(10)
    """
    def __init__(self, fget, doc=None):
        self._sig_ = Signature.from_callable(fget)
        self._map: WeakKeyDictionary[Any, Signal] = WeakKeyDictionary()
        if doc is None and fget is not None:
            doc = fget.__doc__
        self.__doc__ = doc
    def __get__(self, obj, objtype):
        if obj is None:
            return self
        if obj not in self._map:
            self._map[obj] = Signal(self._sig_)
        return self._map[obj]
    def __set__(self, obj, val):
        raise AttributeError("Can't assign to signal")
    def __delete__(self, obj):
        raise AttributeError("Can't delete signal")

class _EventSocket:
    """Internal EventSocket handler.
    """
    def __init__(self, slot: Callable | None=None):
        self._slot: Callable | None = None
        self._weak: bool | ReferenceType[Callable] = False
        if slot is not None:
            if isinstance(slot, partial) or slot.__name__ == '<lambda>':
                self._slot = slot
                self._weak = False
            elif ismethod(slot):
                self._slot = slot.__func__
                self._weak = ref(slot.__self__)
            else:
                self._slot = ref(slot)
                self._weak = True
    def __call__(self, *args, **kwargs):
        if self._slot is not None:
            if isinstance(self._weak, ref):
                if (obj := self._weak()):
                    return self._slot(obj, *args, **kwargs)
            elif self._weak and (slot := self._slot()):
                return slot(*args, **kwargs)
            else:
                return self._slot(*args, **kwargs)
    def is_set(self) -> bool:
        """Returns True if slot is assigned to eventsocket.
        """
        if isinstance(self._weak, ref):
            return self._weak() is not None
        if self._weak:
            return self._slot() is not None
        return self._slot is not None

class eventsocket: # noqa: N801
    """Decorator defining a property that holds a single callable slot (like a Delphi event).

    Assigning a callable (function, method, lambda, partial) to the property connects it
    as the event handler. Assigning `None` disconnects the current handler. Calling the
    property like a method invokes the currently connected handler, passing through
    arguments and returning its result.

    The decorated function's signature (excluding 'self' but including the return
    type annotation) defines the required signature for the assigned slot.

    Use the `.is_set()` method on the property access to check if a handler is assigned.

    Example::

        class MyComponent:
            @eventsocket
            def on_update(self, data: dict) -> None:
                # Slots must match (data: dict) -> None
                pass

            def do_update(self):
                data = {'value': 1}
                if self.on_update.is_set():
                    self.on_update(data) # Call the assigned handler

        def my_handler(data: dict):
            print(f"Handler received: {data}")

        comp = MyComponent()
        comp.on_update = my_handler # Connect handler
        comp.do_update()            # Calls my_handler
        comp.on_update = None       # Disconnect handler

    Important:
        Signature matching includes parameter names, types, kinds, order, *and* the
        return type annotation. The only exception is that the assigned slot may have
        extra keyword arguments if they have default values.

    Storage Note:
        Similar to `Signal`, functions and methods are stored using weak references
        where appropriate to prevent memory leaks. Lambdas/partials are stored directly.
    """
    _empty: _EventSocket = _EventSocket()
    def __init__(self, fget: Callable, doc: str | None=None):
        s = Signature.from_callable(fget)
        # Remove 'self' from list of parameters
        self._sig: Signature = s.replace(parameters=[v for k,v in s.parameters.items()
                                                     if k.lower() != 'self'])
        # Key: instance of class where this eventsocket instance is used to define a property
        # Value: _EventSocket
        self._map = WeakKeyDictionary()
        if doc is None and fget is not None:
            doc = fget.__doc__
        self.__doc__ = doc
    def _kw_test(self, sig: Signature) -> bool:
        p = sig.parameters
        result = False
        for k in set(p).difference(set(self._sig.parameters)):
            result = True
            if p[k].default is Signature.empty:
                return False
        return result
    def __get__(self, obj, objtype):
        if obj is None:
            return self
        return self._map.get(obj, eventsocket._empty)
    def __set__(self, obj, value):
        if value is None:
            if obj in self._map:
                del self._map[obj]
            return
        if not callable(value):
            raise ValueError(f"Connection to non-callable '{value.__class__.__name__}' object failed")
        # Verify signatures
        sig = Signature.from_callable(value)
        if str(sig) != str(self._sig):
            # Check if the difference is only in keyword arguments with defaults.
            if not self._kw_test(sig):
                raise ValueError("Callable signature does not match the event signature")
        self._map[obj] = _EventSocket(value)
    def __delete__(self, obj):
        raise AttributeError("Can't delete eventsocket")
