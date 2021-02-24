#coding:utf-8
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
# Contributor(s): PySignal 1.1.4 contributors: John Hood, Jason Viloria, Adric Worley,
#                 Alex Widener
#                 Pavel Císař - fork and reduction & adaptation for firebird-base and Python 3.8
#                 ______________________________________

"""firebird-base - Callback system based on Signals and Slots, and "Delphi events"


"""

from __future__ import annotations
from typing import Callable, List
from inspect import Signature, ismethod
from weakref import ref, WeakKeyDictionary
from functools import partial

class Signal:
    """The Signal is the core object that handles connection with slots and emission.

    Slots are callables that are called when signal is emitted (the return value is ignored).
    They could be functions, instance or class methods, partials and lambda functions.
    """
    def __init__(self, signature: Signature):
        """
        Arguments:
            signature: Signature for slots.

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
        self._sig: Signature = signature.replace(parameters=[p for p in signature.parameters.values()
                                                             if p.name != 'self'],
                                                 return_annotation=Signature.empty)
        #: Toggle to block / unblock signal transmission
        self.block: bool = False
        self._slots: List[Callable] = []
        self._islots: WeakKeyDictionary = WeakKeyDictionary()
    def __call__(self, *args, **kwargs):
        self.emit(*args, **kwargs)
    def _kw_test(self, sig: Signature) -> bool:
        p = sig.parameters
        result = False
        for k in set(p).difference(set(self._sig.parameters)):
            result = True
            if p[k].default is Signature.empty:
                return False
        return result
    def emit(self, *args, **kwargs) -> None:
        """Calls all the connected slots with the provided args and kwargs unless block
        is activated.
        """
        if self.block:
            return
        for slot in self._slots:
            if not slot:
                continue
            elif isinstance(slot, partial):
                slot(*args, **kwargs)
            elif isinstance(slot, WeakKeyDictionary):
                # For class methods, get the class object and call the method accordingly.
                for obj, method in slot.items():
                    method(obj, *args, **kwargs)
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
        """Connects the signal to callable that will receive the signal when emitted.

        Arguments:
            slot: Callable with signature that match the signature defined for signal.

        Raises:
            ValueError: When callable signature does not match the signature of signal.
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
            # If it's a partial, a Signal or a lambda.
            if slot not in self._slots:
                self._slots.append(slot)
        elif ismethod(slot):
            # Check if it's an instance method and store it with the instance as the key
            self._islots[slot.__self__] = slot.__func__
        else:
            # If it's just a function then just store it as a weakref.
            newSlotRef = ref(slot)
            if newSlotRef not in self._slots:
                self._slots.append(newSlotRef)
    def disconnect(self, slot) -> None:
        """Disconnects the slot from the signal.
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


class signal:
    """Decorator that defines signal as read-only property. The decorated function/method
    is used to define the signature required for slots to successfuly register to signal,
    and does not need to have a body as it's never executed.

    The usage is similar to builtin `property`, except that it does not support custom
    setter and deleter.
    """
    def __init__(self, fget, doc=None):
        self._sig_ = Signature.from_callable(fget)
        self._map = WeakKeyDictionary()
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
        raise AttributeError("can't set signal")
    def __delete__(self, obj):
        raise AttributeError("can't delete signal")

class _EventSocket:
    """Internal EventSocket handler.
    """
    def __init__(self, slot: Callable=None):
        self._slot: Callable = None
        self._weak = False
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
        elif self._weak:
            return self._slot() is not None
        return self._slot is not None

class eventsocket:
    """The `eventsocket` is like read/write property that handles connection and call
    delegation to single slot. It basically works like Delphi event.

    The Slot could be function, instance or class method, partial and lambda function.

    Important:
        Only slot that match the signature could be connected to eventsocket. The check is
        performed on parameters and return value type (as events may have return values).

        The match must be exact, including type annotations, parameter names, order,
        parameter type etc. The sole exception to this rule are excess slot keyword
        arguments with default values.

    Note:
        Eventsocket functions with signatures different from event could be adapted
        using `functools.partial`. However, you can "mask" only keyword arguments
        (without default) and leading positional arguments (as any positional argument
        binded by name will not mask-out parameter from signature introspection).

    To call the event, simply call the eventsocket property with required parameters.
    To check whether slot is assigned to eventsocket, use `is_set()` bool function
    defined on property.
    """
    _empty = _EventSocket()
    def __init__(self, fget, doc=None):
        s = Signature.from_callable(fget)
        # Remove 'self' from list of parameters
        self._sig: Signature = s.replace(parameters=[v for k,v in s.parameters.items() if k.lower() != 'self'])
        # Key: instance of class where this eventsocket instance is used to define a property
        # Value: _EventSocket
        self._map = WeakKeyDictionary()
        if doc is None and fget is not None:
            doc = fget.__doc__
        self.__doc__ = doc
    def _kw_test(self, sig: Signature) -> bool:
        set_p = set(sig.parameters)
        set_t = set(self._sig.parameters)
        for k in set_p.difference(set_t):
            if sig.parameters[k].default is Signature.empty:
                return False
        for k in set_t.difference(set_p):
            if self._sig.parameters[k].default is Signature.empty:
                return False
        return sig.return_annotation == self._sig.return_annotation
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
        raise AttributeError("can't delete eventsocket")


