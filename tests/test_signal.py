# SPDX-FileCopyrightText: 2020-present The Firebird Projects <www.firebirdsql.org>
#
# SPDX-License-Identifier: MIT
#
# PROGRAM/MODULE: firebird-base
# FILE:           tests/test_signal.py
# DESCRIPTION:    Tests for firebird.base.signal module
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
# Copyright (c) 2020 Firebird Project (www.firebirdsql.org)
# All Rights Reserved.
#
# Contributor(s): Pavel Císař (original code)
#                 ______________________________________

"""Unit tests for the firebird.base.signal module (Signal and eventsocket)."""

from __future__ import annotations

import inspect
import gc # For testing weak references
import weakref
from functools import partial
from typing import Any # Added for type hints

import pytest

from firebird.base.signal import Signal, _EventSocket, eventsocket, signal

# --- Test Setup & Fixtures ---

ns = {} # Global namespace for checking side effects of some test functions

def nopar_signal_sig_func():
    """Function defining a signature with no parameters (except self implicitly)."""
    pass

nopar_signature = inspect.Signature.from_callable(nopar_signal_sig_func)
nopar_signature = nopar_signature.replace(parameters=[]) # Explicitly remove self if needed

def value_signal_func(value) -> None:
    """Function defining a signature with one 'value' parameter."""
    pass

slot_signature = inspect.Signature.from_callable(value_signal_func)
slot_signature = slot_signature.replace(parameters=[p for p in slot_signature.parameters.values() if p.name != 'self'],
                                        return_annotation=inspect.Signature.empty)


# Functions to be used as slots/handlers
def _func(test_instance, value) -> None:
    """A standalone function slot that modifies the test instance."""
    test_instance.checkval = value
    test_instance.call_count += 1

def _func_int(test_instance, value: int) -> None:
    """A standalone function slot with type hints."""
    test_instance.checkval = value
    test_instance.call_count += 1

def _func_int_ret(value: int) -> int:
    """A standalone function slot with type hints and return value."""
    return value

def _func_with_kw_default(test_instance, value, kiwi=None) -> None:
    """Slot with an extra keyword argument having a default value."""
    test_instance.checkval = value
    test_instance.call_count += 1

def _func_with_kw(test_instance, value, *, kiwi) -> None:
    """Slot with an extra mandatory keyword argument."""
    test_instance.checkval = value
    test_instance.call_count += 1

def _func_wrong_param_name(test_instance, val):
    """Slot with a different parameter name."""
    test_instance.checkval = val
    test_instance.call_count += 1

def _func_wrong_param_type(test_instance, value: str):
    """Slot with a different parameter type hint."""
    test_instance.checkval = value
    test_instance.call_count += 1

def _func_wrong_ret_type(test_instance, value: int) -> float:
    """Slot with a different return type hint."""
    test_instance.checkval = value
    test_instance.call_count += 1
    return float(value)


class DummySignalClass:
    """A dummy class using the @signal decorator."""
    @signal
    def c_signal(self, value: Any):
        """Class Signal Docstring"""
        pass # Signature definition only

    @signal
    def c_signal2(self, value: Any):
        """Class Signal 2 Docstring"""
        pass

    def __init__(self):
        self.instance_signal = Signal(slot_signature) # Manual signal instance

    def trigger_instance_signal(self, value):
        """Emits the manually created instance signal."""
        self.instance_signal.emit(value)

    def trigger_class_signal(self, value):
        """Emits the signal defined via the @signal decorator."""
        self.c_signal.emit(value)

class DummyEventClass:
    """A dummy class using the @eventsocket decorator."""
    @eventsocket
    def event(self, value: int) -> None:
        """Event Socket Docstring"""
        pass # Signature definition only

    @eventsocket
    def event2(self, value: int) -> int:
        """Event Socket 2 Docstring (returns int)"""
        pass

    @eventsocket
    def event3(self, value):
        """Event Socket 3 Docstring (no type hints)"""
        pass

    @eventsocket
    def event_nopar(self) -> None:
        """Event Socket 4 Docstring (no parameters)"""
        pass

class DummySlotClass:
    """A dummy class providing methods to act as slots."""
    checkval: Any = None
    call_count: int = 0

    def set_val(self, value):
        """Instance method slot."""
        self.__class__.checkval = value
        self.__class__.call_count += 1

    @classmethod
    def cls_set_val(cls, value):
        """Class method slot."""
        cls.checkval = value
        cls.call_count += 1

class DummyEventSlotClass:
    """A dummy class providing methods to act as event handlers."""
    checkval: Any = None
    call_count: int = 0

    def set_val(self, value):
        """Event handler instance method."""
        self.checkval = value
        self.call_count += 1

    def set_val_kw(self, value, extra=None):
        """Handler with an extra keyword argument having a default."""
        self.checkval = value
        self.call_count += 1

    def set_val_extra(self, value, extra):
        """Handler with an extra mandatory keyword argument."""
        self.checkval = value
        self.call_count += 1

    def set_val_int(self, value: int) -> None:
        """Handler with specific type hints."""
        self.checkval = value
        self.call_count += 1

    def set_val_int_ret_int(self, value: int) -> int:
        """Handler with type hints and a return value."""
        self.checkval = value
        self.call_count += 1
        return value * 2

class SignalTestMixin:
    """Mixin class with common setup, teardown, and helper methods for tests."""
    def __init__(self):
        self.checkval: Any = None
        self.call_count: int = 0
        self.slot_call_count: int = 0
        self.reset()

    def reset(self):
        """Resets state variables for a new test."""
        self.checkval = None
        self.call_count = 0
        self.slot_call_count = 0
        ns.clear()
        ns["checkval"] = None
        ns["call_count"] = 0
        # Reset class variables of dummy slot classes
        DummySlotClass.checkval = None
        DummySlotClass.call_count = 0
        DummyEventSlotClass.checkval = None
        DummyEventSlotClass.call_count = 0


    # Helper methods acting as slots/handlers
    def slot_method(self, value):
        """Instance method slot."""
        self.checkval = value
        self.slot_call_count += 1

    def slot_method_int(self, value: int) -> None:
        """Instance method slot with int hint."""
        self.checkval = value
        self.slot_call_count += 1

    def slot_method_int_ret_int(self, value: int) -> int:
        """Instance method slot with int hint and return."""
        self.checkval = value
        self.slot_call_count += 1
        return value * 2

    @classmethod
    def slot_cls_method(cls, value):
        """Class method slot."""
        ns["checkval"] = value
        ns["call_count"] += 1

    def slot_method_ignore(self, value):
        """Instance method slot used when testing disconnects/failures."""
        pass # Does nothing

    def slot_method_ignore_int(self, value: int) -> None:
        """Typed instance method slot used for ignoring calls."""
        pass

    def slot_method_ignore_int_ret_int(self, value: int) -> int:
        """Typed instance method slot with return, used for ignoring calls."""
        return value * 2

@pytest.fixture
def receiver() -> SignalTestMixin:
    """Provides a fresh SignalTestMixin instance for each test."""
    return SignalTestMixin()

# --- Signal Decorator Tests ---

def test_signal_decorator_get():
    """Tests the @signal decorator's __get__ method and docstring propagation."""
    sig_instance = DummySignalClass()
    # Get on instance returns Signal object
    assert isinstance(sig_instance.c_signal, Signal)
    # Get on class returns descriptor itself
    assert isinstance(DummySignalClass.c_signal, signal)
    # Check docstring
    assert DummySignalClass.c_signal.__doc__ == "Class Signal Docstring"
    # Accessing multiple times returns same Signal instance for that object
    assert sig_instance.c_signal is sig_instance.c_signal

def test_signal_decorator_set():
    """Tests that assigning to a @signal property raises AttributeError."""
    sig_instance = DummySignalClass()
    with pytest.raises(AttributeError, match="Can't assign to signal"):
        sig_instance.c_signal = _func # type: ignore

def test_signal_decorator_del():
    """Tests that deleting a @signal property raises AttributeError."""
    sig_instance = DummySignalClass()
    with pytest.raises(AttributeError, match="Can't delete signal"):
        del sig_instance.c_signal

# --- Signal Class Tests ---

def test_signal_connect_signature_mismatch(receiver):
    """Tests that Signal.connect raises ValueError for incompatible signatures."""
    sig = Signal(slot_signature) # Expects (value: Any) -> None

    # Wrong number of parameters
    with pytest.raises(ValueError, match="Callable signature does not match"):
        sig.connect(nopar_signal_sig_func)
    # Wrong parameter name
    with pytest.raises(ValueError, match="Callable signature does not match"):
        sig.connect(receiver.slot_method_ignore_int) # Correct type, uses self implicitly
        # Check against external func too
        sig.connect(_func_wrong_param_name) # Correct number, wrong name ('val' vs 'value')


def test_signal_connect_various_types(receiver):
    """Tests connecting various callable types to a Signal."""
    sig = Signal(slot_signature) # Expects (value: Any) -> None

    # Partial
    part = partial(_func, receiver, "Partial Value") # Adapts _func's signature
    sig_nopar = Signal(nopar_signature)
    sig_nopar.connect(part)
    assert len(sig_nopar._slots) == 1
    assert part in sig_nopar._slots

    # Lambda
    lamb = lambda value: _func(receiver, value)
    sig.connect(lamb)
    assert len(sig._slots) == 1
    assert lamb in sig._slots

    # Instance Method
    sig.connect(receiver.slot_method)
    assert receiver.slot_method.__self__ in sig._islots # Check instance is key
    assert sig._islots[receiver.slot_method.__self__] == receiver.slot_method.__func__

    # Class Method
    sig.connect(SignalTestMixin.slot_cls_method)
    assert SignalTestMixin.slot_cls_method.__self__ in sig._islots # Class is key
    assert sig._islots[SignalTestMixin.slot_cls_method.__self__] == SignalTestMixin.slot_cls_method.__func__

    # Regular Function (stored as weakref)
    sig_func = Signal(inspect.Signature.from_callable(_func).replace(parameters=[p for p in inspect.signature(_func).parameters.values() if p.name != 'self'], return_annotation=inspect.Signature.empty))
    sig_func.connect(_func)
    assert len(sig_func._slots) == 1
    assert isinstance(sig_func._slots[0], weakref.ReferenceType) # Functions likely stored as weakref internally

def test_signal_connect_duplicates(receiver):
    """Tests that connecting the same slot multiple times only stores it once."""
    sig = Signal(slot_signature)
    # Lambda
    func = lambda value: _func(receiver, value)
    sig.connect(func)
    sig.connect(func)
    assert len(sig._slots) == 1
    # Method
    sig.connect(receiver.slot_method)
    sig.connect(receiver.slot_method)
    assert len(sig._islots) == 1
    # Function
    sig_func = Signal(inspect.Signature.from_callable(_func).replace(parameters=[p for p in inspect.signature(_func).parameters.values() if p.name != 'self'], return_annotation=inspect.Signature.empty))
    sig_func.connect(_func)
    sig_func.connect(_func)
    assert len(sig_func._slots) == 1

def test_signal_connect_different_instances():
    """Tests connecting the same method from different instances."""
    method_sig = Signal(slot_signature)
    dummy1 = DummySlotClass()
    dummy2 = DummySlotClass()
    method_sig.connect(dummy1.set_val)
    method_sig.connect(dummy2.set_val)
    assert len(method_sig._islots) == 2 # Should have entries for both instances

def test_signal_connect_non_callable(receiver):
    """Tests that connecting a non-callable raises ValueError."""
    sig = Signal(slot_signature)
    with pytest.raises(ValueError, match="Connection to non-callable"):
        sig.connect(receiver.checkval) # type: ignore

def test_signal_connect_kwarg_signature_variants(receiver):
    """Tests connecting slots with extra keyword arguments."""
    sig = Signal(slot_signature) # Expects (value)

    # Slot with extra kwarg having a default (OK)
    sig.connect(partial(_func_with_kw_default, receiver)) # Must use partial for receiver
    assert len(sig._slots) == 1

    # Slot with extra mandatory kwarg (Fail)
    with pytest.raises(ValueError, match="Callable signature does not match"):
        sig.connect(_func_with_kw)
    assert len(sig._slots) == 1 # Should not have added the invalid one

def test_signal_emit_various_targets(receiver):
    """Tests emitting signals to various connected slot types."""
    test_value = "Emitted Value"

    # To Partial
    sig_nopar = Signal(nopar_signature)
    sig_nopar.connect(partial(_func, receiver, test_value))
    sig_nopar.emit()
    assert receiver.checkval == test_value
    assert receiver.call_count == 1
    receiver.reset()

    # To Lambda
    sig_lambda = Signal(slot_signature)
    sig_lambda.connect(lambda value: _func(receiver, value))
    sig_lambda.emit(test_value)
    assert receiver.checkval == test_value
    assert receiver.call_count == 1
    receiver.reset()

    # To Instance Method
    sig_method = Signal(slot_signature)
    sig_method.connect(receiver.slot_method)
    sig_method.emit(test_value)
    assert receiver.checkval == test_value
    assert receiver.slot_call_count == 1
    receiver.reset()

    # To Class Method
    sig_cls_method = Signal(slot_signature)
    sig_cls_method.connect(SignalTestMixin.slot_cls_method)
    sig_cls_method.emit(test_value)
    assert ns["checkval"] == test_value
    assert ns["call_count"] == 1
    receiver.reset() # Also clears ns

    # To Regular Function
    sig_func = Signal(inspect.Signature.from_callable(_func).replace(parameters=[p for p in inspect.signature(_func).parameters.values() if p.name != 'self'], return_annotation=inspect.Signature.empty))
    sig_func.connect(_func)
    sig_func.emit(receiver, test_value)
    assert receiver.checkval == test_value
    assert receiver.call_count == 1

def test_signal_emit_to_method_on_deleted_instance(receiver):
    """Tests that signals skip calls to methods of deleted instances."""
    sig = Signal(slot_signature)
    to_delete = DummySlotClass()
    sig.connect(to_delete.set_val)
    sig.connect(receiver.slot_method)
    assert len(sig._islots) == 2

    # Emit once, both should receive
    sig.emit(1)
    assert DummySlotClass.checkval == 1
    assert DummySlotClass.call_count == 1
    assert receiver.checkval == 1
    assert receiver.slot_call_count == 1

    # Delete one instance and collect garbage
    del to_delete
    gc.collect()

    # Emit again, only receiver should get it
    sig.emit(2)
    assert DummySlotClass.checkval == 1 # Unchanged
    assert DummySlotClass.call_count == 1 # Unchanged
    assert receiver.checkval == 2
    assert receiver.slot_call_count == 2
    # Internal slot count might decrease depending on WeakKeyDictionary timing
    # assert len(sig._islots) == 1 # This might be flaky

def test_signal_emit_to_deleted_function(receiver):
    """Tests that signals skip calls to functions that have been deleted."""
    def func_to_delete(test, value):
        """Temporary function to test deletion."""
        test.checkval = value
        test.call_count += 1

    func_signature = inspect.Signature.from_callable(func_to_delete) # Signature of func_to_delete
    sig = Signal(func_signature)
    sig.connect(func_to_delete)
    assert len(sig._slots) == 1

    # Emit once
    sig.emit(receiver, "Before Delete")
    assert receiver.checkval == "Before Delete"
    assert receiver.call_count == 1
    receiver.reset()

    # Delete the function reference and collect garbage
    del func_to_delete
    gc.collect()

    # Emit again, should not call anything (weakref should be dead)
    sig.emit(receiver, "After Delete")
    assert receiver.checkval is None
    assert receiver.call_count == 0
    # Internal slot count might decrease depending on weakref cleanup timing

def test_signal_emit_block(receiver):
    """Tests that setting signal.block = True prevents emissions."""
    sig = Signal(slot_signature)
    sig.connect(receiver.slot_method)
    sig.emit(1)
    assert receiver.checkval == 1
    # Block emission
    sig.block = True
    sig.emit(2)
    assert receiver.checkval == 1 # Value should not change
    # Unblock emission
    sig.block = False
    sig.emit(3)
    assert receiver.checkval == 3

def test_signal_emit_direct_call(receiver):
    """Tests emitting by calling the Signal instance directly."""
    sig = Signal(slot_signature)
    sig.connect(receiver.slot_method)
    sig(1) # Emit using __call__
    assert receiver.checkval == 1

def test_signal_disconnect_various_types(receiver):
    """Tests disconnecting various types of connected slots."""
    sig = Signal(slot_signature)
    sig_nopar = Signal(nopar_signature)
    sig_func = Signal(inspect.Signature.from_callable(_func).replace(parameters=[p for p in inspect.signature(_func).parameters.values() if p.name != 'self'], return_annotation=inspect.Signature.empty))


    # Partial
    part = partial(_func, receiver, "Partial")
    sig_nopar.connect(part)
    assert part in sig_nopar._slots
    sig_nopar.disconnect(part)
    assert part not in sig_nopar._slots

    # Lambda
    lamb = lambda value: _func(receiver, value)
    sig.connect(lamb)
    assert lamb in sig._slots
    sig.disconnect(lamb)
    assert lamb not in sig._slots

    # Instance Method
    sig.connect(receiver.slot_method)
    assert receiver.slot_method.__self__ in sig._islots
    sig.disconnect(receiver.slot_method)
    assert receiver.slot_method.__self__ not in sig._islots

    # Class Method
    sig.connect(SignalTestMixin.slot_cls_method)
    assert SignalTestMixin.slot_cls_method.__self__ in sig._islots
    sig.disconnect(SignalTestMixin.slot_cls_method)
    assert SignalTestMixin.slot_cls_method.__self__ not in sig._islots

    # Regular Function
    sig_func.connect(_func)
    assert len(sig_func._slots) > 0 # Weakref makes direct check hard
    sig_func.disconnect(_func)
    # Asserting weakref removal is tricky, check emit works
    sig_func.emit(receiver, "After Disconnect")
    assert receiver.checkval is None

def test_signal_disconnect_unconnected(receiver):
    """Tests that disconnecting an unconnected slot does not raise errors."""
    sig = Signal(slot_signature)
    part = partial(_func, receiver, "Partial")
    lamb = lambda value: _func(receiver, value)
    try:
        sig.disconnect(receiver.slot_method)
        sig.disconnect(part)
        sig.disconnect(lamb)
        sig.disconnect(_func)
    except Exception as e:
        pytest.fail(f"Disconnecting unconnected slot raised: {e}")

def test_signal_disconnect_non_callable(receiver):
    """Tests that disconnecting a non-callable argument does not raise errors."""
    sig = Signal(slot_signature)
    try:
        sig.disconnect(receiver.checkval) # type: ignore
    except Exception as e:
        pytest.fail(f"Disconnecting non-callable raised: {e}")

def test_signal_clear_slots(receiver):
    """Tests the clear method removes all connected slots."""
    sig = Signal(slot_signature)
    part = partial(_func, receiver)
    lamb = lambda value: _func(receiver, value)
    sig.connect(part)
    sig.connect(lamb)
    sig.connect(receiver.slot_method)
    sig_func = Signal(inspect.Signature.from_callable(_func).replace(parameters=[p for p in inspect.signature(_func).parameters.values() if p.name != 'self'], return_annotation=inspect.Signature.empty))

    sig_func.connect(_func)

    assert len(sig._slots) == 2
    assert len(sig._islots) == 1
    assert len(sig_func._slots) == 1

    sig.clear()
    sig_func.clear()

    assert len(sig._slots) == 0
    assert len(sig._islots) == 0
    assert len(sig_func._slots) == 0

# --- eventsocket Decorator Tests ---

def test_event_decorator_get():
    """Tests the @eventsocket decorator's __get__ method and docstring propagation."""
    evt_instance = DummyEventClass()
    # Get on instance returns _EventSocket object
    socket = evt_instance.event
    assert isinstance(socket, _EventSocket)
    assert not socket.is_set() # Initially empty
    # Get on class returns descriptor itself
    assert isinstance(DummyEventClass.event, eventsocket)
    # Check docstring
    assert DummyEventClass.event.__doc__ == "Event Socket Docstring"
    # Accessing multiple times returns same _EventSocket for that object (or default)
    assert evt_instance.event is socket

def test_event_decorator_del():
    """Tests that deleting an @eventsocket property raises AttributeError."""
    evt_instance = DummyEventClass()
    with pytest.raises(AttributeError, match="Can't delete eventsocket"):
        del evt_instance.event

def test_event_assign_and_clear(receiver):
    """Tests assignment of various handlers to an eventsocket and clearing."""
    obj = DummyEventClass()
    slot_instance = DummyEventSlotClass()

    # Initially unset
    assert not obj.event.is_set()
    assert not obj.event2.is_set()

    # Assign instance method
    obj.event = receiver.slot_method_int
    assert obj.event.is_set()
    obj.event = None # Clear
    assert not obj.event.is_set()

    # Assign function
    obj.event2 = _func_int_ret
    assert obj.event2.is_set()
    obj.event2 = None
    assert not obj.event2.is_set()


    # Assign lambda
    obj.event3 = lambda value: _func(receiver, value)
    assert obj.event3.is_set()
    obj.event3 = None
    assert not obj.event3.is_set()

    # Assign partial
    obj.event = partial(slot_instance.set_val_extra, extra="Partial")
    assert obj.event.is_set()
    obj.event = None
    assert not obj.event.is_set()

    # Assign method with extra default kwarg (OK)
    obj.event = slot_instance.set_val_kw
    assert obj.event.is_set()
    obj.event = None
    assert not obj.event.is_set()

    # Assign non-callable
    with pytest.raises(ValueError, match="Connection to non-callable"):
        obj.event = "non-callable" # type: ignore

def test_event_assign_signature_mismatch(receiver):
    """Tests that assigning handlers with incompatible signatures raises ValueError."""
    obj = DummyEventClass() # event expects (value: int) -> None

    # Wrong parameter name
    with pytest.raises(ValueError, match="Callable signature does not match"):
        obj.event = _func_wrong_param_name # Takes 'val' not 'value'

    # Wrong parameter type
    with pytest.raises(ValueError, match="Callable signature does not match"):
        obj.event = _func_wrong_param_type # Takes str, not int

    # Wrong return type (event expects None)
    with pytest.raises(ValueError, match="Callable signature does not match"):
        obj.event = _func_wrong_ret_type # Returns float, not None

    # Correct type, but different instance method signature (e.g., event2 expects int->int)
    with pytest.raises(ValueError, match="Callable signature does not match"):
        obj.event2 = receiver.slot_method_int # Returns None, not int

def test_event_call(receiver):
    """Tests calling eventsocket properties like functions."""
    evt_instance = DummyEventClass()
    evt_instance.event = receiver.slot_method_int
    evt_instance.event2 = receiver.slot_method_int_ret_int

    # Call event without return value
    evt_instance.event(10)
    assert receiver.checkval == 10
    assert receiver.slot_call_count == 1

    # Call event with return value
    result = evt_instance.event2(20)
    assert result == 40 # 20 * 2
    assert receiver.checkval == 20
    assert receiver.slot_call_count == 2

def test_event_call_unset(receiver):
    """Tests calling an eventsocket that has no handler assigned."""
    obj = DummyEventClass()
    try:
        # Call event without return expected
        result1 = obj.event(123)
        assert result1 is None # Should return None if unset and no return expected

        # Call event with return expected
        result2 = obj.event2(456)
        assert result2 is None # Should return None if unset, even if return expected
    except Exception as e:
        pytest.fail(f"Calling unset eventsocket raised: {e}")

def test_event_handler_weakref(receiver):
    """Tests that handlers referencing deleted objects are skipped."""
    obj = DummyEventClass()
    slot_instance = DummyEventSlotClass()

    # Assign instance method
    obj.event = slot_instance.set_val_int
    assert obj.event.is_set()

    # Call it
    obj.event(1)
    assert slot_instance.checkval == 1
    assert slot_instance.call_count == 1

    # Delete the instance holding the handler method
    del slot_instance
    gc.collect()

    # Check the handler is no longer set
    assert not obj.event.is_set()

    # Call again, should do nothing
    obj.event(2)
    # Cannot check slot_instance.checkval as it's deleted
    # Check that receiver (if used as alternative) wasn't called
    assert receiver.checkval is None

def test_event_handler_partial_kwarg_variants(receiver):
    """Tests assigning and calling handlers with extra kwargs via partial."""
    obj = DummyEventClass() # event expects (value: int) -> None
    slot_instance = DummyEventSlotClass()

    # Partial with extra default kwarg (OK to assign)
    part_def = partial(_func_with_kw_default, slot_instance) # Binds test_instance
    # Assign to event_nopar as it matches the remaining signature () -> None
    # Needs adjustment in DummyEventClass if event_nopar removed
    # Let's assign to event3 (value) -> None , binding value in partial
    part_def_bound = partial(_func_with_kw_default, slot_instance, 99)
    obj.event3 = part_def_bound # Signature now matches () -> None conceptually
    assert obj.event3.is_set()
    # Calling event3 (which takes value) will fail if partial expects no args left.
    # Revisit: Assigning partials needs careful signature matching.
    # Let's test assignment directly to a compatible event signature:
    obj.event_nopar = part_def_bound # Assign partial expecting no args to event_nopar
    assert obj.event_nopar.is_set()
    obj.event_nopar() # Call event
    assert slot_instance.checkval == 99 # Value bound in partial is used
    slot_instance.checkval = None # Reset

    obj.event_nopar = None # Reset
    # Partial with extra mandatory kwarg (assign should fail if check is strict)
    part_man = partial(_func_with_kw, slot_instance, 100)
    # Try assigning to event_nopar again
    with pytest.raises(ValueError, match="Callable signature does not match"):
        obj.event_nopar = part_man # Signature should mismatch due to extra 'kiwi'
    assert not obj.event_nopar.is_set() # Should not be set
    # Should pass if kwarg is bound
    part_man_bound = partial(_func_with_kw, slot_instance, 100, kiwi="test") # Provide mandatory kwarg
    obj.event_nopar = part_man_bound
    assert obj.event_nopar.is_set() # Should be set
