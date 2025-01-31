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

from __future__ import annotations

import inspect
from functools import partial

import pytest

from firebird.base.signal import Signal, _EventSocket, eventsocket, signal

ns = {}

def nopar_signal():
    pass

nopar_signature = inspect.Signature.from_callable(nopar_signal)

def value_signal(value) -> None:
    ns["checkval"]= value
    ns["call_count"] += 1

def value_event(value: int) -> None:
    ns["checkval"]= value
    ns["call_count"] += 1

slot_signature = inspect.Signature.from_callable(value_signal)

def _func(test, value) -> None:
    """A test standalone function for signals/events to attach onto"""
    test.checkval = value
    test.func_call_count += 1

def _func_int(test, value: int) -> None:
    """A test standalone function for signals/events to attach onto"""
    test.checkval = value
    test.func_call_count += 1

testFunc_signature = inspect.Signature.from_callable(_func)

def _func_with_kw_deafult(test, value, kiwi=None):
    """A test standalone function with excess default keyword argument for signals to attach onto"""
    test.checkval = value
    test.func_call_count += 1

def _func_with_kw(test, value, *, kiwi):
    """A test standalone function with excess keyword argument for signals to attach onto"""
    test.checkval = value
    test.func_call_count += 1

def _local_emit(signal_instance):
    """A test standalone function for signals to emit at local level"""
    exec("signal_instance.emit()")

def _module_emit(signal_instance):
    """A test standalone function for signals to emit at module level"""
    signal_instance.emit()

class DummySignalClass:
    """A dummy class to check for instance handling of signals"""
    @signal
    def c_signal(self, value):
        "cSignal"
    @signal
    def c_signal2(self, value):
        "cSignal2"
    def __init__(self):
        self.signal = Signal(slot_signature)
    def trigger_signal(self):
        self.signal.emit()
    def trigger_class_signal(self):
        self.c_signal.emit(1)

class DummyEventClass:
    """A dummy class to check for eventsockets"""
    @eventsocket
    def event(self, value: int) -> None:
        "event"
    @eventsocket
    def event2(self, value: int) -> int:
        "event2"
    @eventsocket
    def event3(self, value):
        "event2 without annotations for lambdas"
    @eventsocket
    def event_nopar(self) -> None:
        "event without parameters"

class DummySlotClass:
    """A dummy class to check for slot handling"""
    checkval = None
    setVal_call_count = 0

    def set_val(self, value):
        """A method to test slot calls with"""
        self.checkval = value
        self.setVal_call_count += 1
    @classmethod
    def cls_set_val(cls, value):
        """A method to test slot calls with"""
        cls.checkval = value
        cls.setVal_call_count += 1

class DummyEventSlotClass:
    """A dummy class to check for eventsocket slot handling"""
    checkval = None

    def set_val(self, value):
        """A method to test slot calls with"""
        self.checkval = value
    def set_val_kw(self, value, extra=None):
        """A method to test slot calls with"""
        self.checkval = value
    def set_val_extra(self, value, extra):
        """A method to test slot calls with"""
        self.checkval = value
    def set_val_int(self, value: int) -> None:
        """A method to test slot calls with"""
        self.checkval = value
    def set_val_int_ret_int(self, value: int) -> int:
        """A method to test slot calls with"""
        self.checkval = value
        return value * 2

class SignalTestMixin:
    """Mixin class with common helpers for signal tests
    """
    def __init__(self):
        self.checkval = None  # A state check for the tests
        self.checkval2 = None  # A state check for the tests
        self.setVal_call_count = 0  # A state check for the test method
        self.setVal2_call_count = 0  # A state check for the test method
        self.func_call_count = 0  # A state check for test function
        self.reset()
    def reset(self):
        self.checkval = None
        self.checkval2 = None
        self.setVal_call_count = 0
        self.setVal2_call_count = 0
        self.func_call_count = 0
        ns.clear() # Clear global namespace
        ns["checkval"] = None
        ns["call_count"] = 0
    # Helper methods
    def set_val(self, value):
        """A method to test instance settings with"""
        self.checkval = value
        self.setVal_call_count += 1
    @classmethod
    def set_val2(cls, value):
        """Another method to test instance settings with"""
        ns["checkval"]= value
        ns["call_count"] += 1
    def set_val_int(self, value: int) -> None:
        """A method to test slot calls with"""
        self.checkval = value
        self.setVal_call_count += 1
    def set_val_int_ret_int(self, value: int) -> int:
        """A method to test slot calls with"""
        self.checkval = value
        self.setVal_call_count += 1
        return value * 2
    def throwaway(self, value):
        """A method to throw redundant data into"""
    def throwaway_int(self, value: int) -> None:
        """A method to throw redundant data into"""
    def throwaway_int_ret_int(self, value: int) -> int:
        """A method to throw redundant data into"""
        return value * 2

@pytest.fixture
def receiver():
    return SignalTestMixin()

def test_signal_get():
    """Test signal decorator get method"""
    sig = DummySignalClass()
    assert isinstance(sig.c_signal, Signal)
    assert isinstance(DummySignalClass.c_signal, signal)

def test_signal_set():
    """Test signal decorator get method"""
    sig = DummySignalClass()
    with pytest.raises(AttributeError) as cm:
        sig.c_signal = _func
    assert cm.value.args == ("Can't assign to signal", )

def test_signal_del():
    """Test signal decorator get method"""
    sig = DummySignalClass()
    with pytest.raises(AttributeError) as cm:
        del sig.c_signal
    assert cm.value.args == ("Can't delete signal", )

def test_signal_partial_connect(receiver):
    """Tests connecting signals to partials"""
    partialSignal = Signal(nopar_signature)
    partialSignal.connect(partial(_func, receiver, "Partial"))
    assert len(partialSignal._slots) == 1

def test_signal_partial_connect_kw_differ_ok(receiver):
    """Tests connecting signals to partials"""
    partialSignal = Signal(nopar_signature)
    partialSignal.connect(partial(_func_with_kw_deafult, receiver, "Partial"))
    assert len(partialSignal._slots) == 1

def test_signal_partial_connect_kw_differ_bad(receiver):
    """Tests connecting signals to partials"""
    partialSignal = Signal(nopar_signature)
    with pytest.raises(ValueError):
        partialSignal.connect(partial(_func_with_kw, receiver, "Partial"))
    assert len(partialSignal._slots) == 0

def test_signal_partial_connect_duplicate(receiver):
    """Tests connecting signals to partials"""
    partialSignal = Signal(nopar_signature)
    func = partial(_func, receiver, "Partial")
    partialSignal.connect(func)
    partialSignal.connect(func)
    assert len(partialSignal._slots) == 1

def test_signal_lambda_connect(receiver):
    """Tests connecting signals to lambdas"""
    lambdaSignal = Signal(slot_signature)
    lambdaSignal.connect(lambda value: _func(receiver, value))
    assert len(lambdaSignal._slots) == 1

def test_signal_lambda_connect_duplicate(receiver):
    """Tests connecting signals to duplicate lambdas"""
    lambdaSignal = Signal(slot_signature)
    func = lambda value: _func(receiver, value)
    lambdaSignal.connect(func)
    lambdaSignal.connect(func)
    assert len(lambdaSignal._slots) == 1

def test_signal_method_connect(receiver):
    """Test connecting signals to methods on class instances"""
    methodSignal = Signal(slot_signature)
    methodSignal.connect(receiver.set_val)
    assert len(methodSignal._islots) == 1
    assert len(methodSignal._slots) == 0

def test_signal_class_method_connect(receiver):
    """Test connecting signals to methods on class instances"""
    methodSignal = Signal(slot_signature)
    methodSignal.connect(receiver.set_val2)
    assert len(methodSignal._islots) == 1
    assert len(methodSignal._slots) == 0

def test_signal_method_connect_duplicate(receiver):
    """Test that each method connection is unique"""
    methodSignal = Signal(slot_signature)
    methodSignal.connect(receiver.set_val)
    methodSignal.connect(receiver.set_val)
    assert len(methodSignal._islots) == 1
    assert len(methodSignal._slots) == 0

def test_signal_method_connect_different_instances():
    """Test connecting the same method from different instances"""
    methodSignal = Signal(slot_signature)
    dummy1 = DummySlotClass()
    dummy2 = DummySlotClass()
    methodSignal.connect(dummy1.set_val)
    methodSignal.connect(dummy2.set_val)
    assert len(methodSignal._islots) == 2
    assert len(methodSignal._slots) == 0

def test_signal_function_connect():
    """Test connecting signals to standalone functions"""
    funcSignal = Signal(testFunc_signature)
    funcSignal.connect(_func)
    assert len(funcSignal._slots) == 1

def test_signal_function_connect_duplicate():
    """Test that each function connection is unique"""
    funcSignal = Signal(testFunc_signature)
    funcSignal.connect(_func)
    funcSignal.connect(_func)
    assert len(funcSignal._slots) == 1

def test_signal_connect_non_callable(receiver):
    """Test connecting non-callable object"""
    nonCallableSignal = Signal(slot_signature)
    with pytest.raises(ValueError):
        nonCallableSignal.connect(receiver.checkval)

def test_signal_emit_no_slots(receiver):
    """Test emit with signal without slots.
    """
    sig = Signal(slot_signature)
    sig(1)
    assert ns["checkval"] is None

def test_signal_emit_to_partial(receiver):
    """Test emitting signals to partial"""
    partialSignal = Signal(nopar_signature)
    partialSignal.connect(partial(_func, receiver, "Partial"))
    partialSignal.emit()
    assert receiver.checkval == "Partial"
    assert receiver.func_call_count == 1

def test_signal_emit_to_lambda(receiver):
    """Test emitting signal to lambda"""
    lambdaSignal = Signal(slot_signature)
    lambdaSignal.connect(lambda value: _func(receiver, value))
    lambdaSignal.emit("Lambda")
    assert receiver.checkval == "Lambda"
    assert receiver.func_call_count == 1

def test_signal_emit_to_method(receiver):
    """Test emitting signal to method"""
    toSucceed = DummySignalClass()
    toSucceed.signal.connect(receiver.set_val)
    toSucceed.signal.emit("Method")
    assert receiver.checkval == "Method"
    assert receiver.setVal_call_count == 1

def test_signal_emit_to_class_method(receiver):
    """Test delivery to class methods.
    """
    sig = Signal(slot_signature)
    sig.connect(receiver.set_val2)
    sig(1)
    assert ns["checkval"] == 1

def test_signal_emit_to_method_on_deleted_instance(receiver):
    """Test emitting signal to deleted instance method"""
    toDelete = DummySlotClass()
    toCall = Signal(slot_signature)
    toCall.connect(toDelete.set_val)
    toCall.connect(receiver.set_val)
    assert len(toCall._islots) == 2
    toCall.emit(1)
    assert receiver.checkval == 1
    assert receiver.setVal_call_count == 1
    assert toDelete.checkval == 1
    assert toDelete.setVal_call_count == 1
    del toDelete
    assert len(toCall._islots) == 1
    toCall.emit(2)
    assert receiver.checkval == 2
    assert receiver.setVal_call_count == 2

def test_signal_emit_to_function(receiver):
    """Test emitting signal to standalone function"""
    funcSignal = Signal(testFunc_signature)
    funcSignal.connect(_func)
    funcSignal.emit(receiver, "Function")
    assert receiver.checkval == "Function"
    assert receiver.func_call_count == 1

def test_signal_emit_to_deleted_function(receiver):
    """Test emitting signal to deleted instance method"""
    def ToDelete(test, value):
        test.checkval = value
        test.func_call_count += 1
    funcSignal = Signal(inspect.Signature.from_callable(ToDelete))
    funcSignal.connect(ToDelete)
    funcSignal.emit(receiver, "Function")
    assert receiver.checkval == "Function"
    assert receiver.func_call_count == 1
    receiver.reset()
    del ToDelete
    funcSignal.emit(receiver, 1)
    assert receiver.checkval == None
    assert receiver.func_call_count == 0

def test_signal_emit_block(receiver):
    """Test blocked signals.
    """
    sig = Signal(slot_signature)
    sig.connect(receiver.set_val)
    sig.emit(1)
    assert receiver.checkval == 1
    sig.block = True
    sig.emit(2)
    assert receiver.checkval == 1
    sig.block = False
    sig.emit(3)
    assert receiver.checkval == 3

def test_signal_emit_direct_call(receiver):
    """Test blocked signals.
    """
    sig = Signal(slot_signature)
    sig.connect(receiver.set_val)
    sig(1)
    assert receiver.checkval == 1

def test_signal_partial_disconnect(receiver):
    """Test disconnecting partial function"""
    partialSignal = Signal(nopar_signature)
    part = partial(_func, receiver, "Partial")
    assert len(partialSignal._slots) == 0
    partialSignal.connect(part)
    assert len(partialSignal._slots) == 1
    partialSignal.disconnect(part)
    assert len(partialSignal._slots) == 0
    assert receiver.checkval == None

def test_signal_partial_disconnect_unconnected(receiver):
    """Test disconnecting unconnected partial function"""
    partialSignal = Signal(slot_signature)
    part = partial(_func, receiver, "Partial")
    try:
        partialSignal.disconnect(part)
    except:
        pytest.fail("Disonnecting unconnected partial should not raise")

def test_signal_lambda_disconnect(receiver):
    """Test disconnecting lambda function"""
    lambdaSignal = Signal(slot_signature)
    func = lambda value: _func(receiver, value)
    lambdaSignal.connect(func)
    assert len(lambdaSignal._slots) == 1
    lambdaSignal.disconnect(func)
    assert len(lambdaSignal._slots) == 0

def test_signal_lambda_disconnect_unconnected(receiver):
    """Test disconnecting unconnected lambda function"""
    lambdaSignal = Signal(slot_signature)
    func = lambda value: _func(receiver, value)
    try:
        lambdaSignal.disconnect(func)
    except:
        pytest.fail("Disconnecting unconnected lambda should not raise")

def test_signal_method_disconnect(receiver):
    """Test disconnecting method"""
    toCall = Signal(slot_signature)
    toCall.connect(receiver.set_val)
    assert len(toCall._islots) == 1
    toCall.disconnect(receiver.set_val)
    toCall.emit(1)
    assert len(toCall._islots) == 0
    assert receiver.setVal_call_count == 0

def test_signal_method_disconnect_unconnected(receiver):
    """Test disconnecting unconnected method"""
    toCall = Signal(slot_signature)
    try:
        toCall.disconnect(receiver.set_val)
    except:
        pytest.fail("Disconnecting unconnected method should not raise")

def test_signal_function_disconnect():
    """Test disconnecting function"""
    funcSignal = Signal(testFunc_signature)
    funcSignal.connect(_func)
    assert len(funcSignal._slots) == 1
    funcSignal.disconnect(_func)
    assert len(funcSignal._slots) == 0

def test_signal_function_disconnect_unconnected():
    """Test disconnecting unconnected function"""
    funcSignal = Signal(slot_signature)
    try:
        funcSignal.disconnect(_func)
    except:
        pytest.fail("Disconnecting unconnected function should not raise")

def test_signal_disconnect_non_callable(receiver):
    """Test disconnecting non-callable object"""
    signal = Signal(slot_signature)
    try:
        signal.disconnect(receiver.checkval)
    except:
        pytest.fail("Disconnecting invalid object should not raise")

def test_signal_clear_slots(receiver):
    """Test clearing all slots"""
    multiSignal = Signal(slot_signature)
    multiSignal.connect(partial(_func, receiver))
    multiSignal.connect(receiver.set_val)
    assert len(multiSignal._slots) == 1
    assert len(multiSignal._islots) == 1
    multiSignal.clear()
    assert len(multiSignal._slots) == 0
    assert len(multiSignal._islots) == 0

def test_signalcls_assign_to_property():
    """Test assigning to a ClassSignal property
    """
    dummy = DummySignalClass()
    with pytest.raises(AttributeError):
        dummy.c_signal = None

def test_signalcls_emit(receiver):
    """Test emitting signals from class signal and that instances of the class are unique
    """
    toSucceed = DummySignalClass()
    toSucceed.name = "toSucceed"
    toSucceed.c_signal.connect(receiver.set_val)
    toSucceed.c_signal2.connect(receiver.set_val)
    toFail = DummySignalClass()
    toFail.name = "toFail"
    toFail.c_signal.connect(receiver.throwaway)
    toFail.c_signal2.connect(receiver.throwaway)
    toSucceed.c_signal.emit(1)
    assert receiver.checkval == 1
    toSucceed.c_signal2.emit(2)
    assert receiver.checkval == 2
    toFail.c_signal.emit(3)
    toFail.c_signal2.emit(3)
    assert receiver.checkval == 2
    assert receiver.setVal_call_count == 2

def test_event_get():
    """Test event decorator get method"""
    obj = DummyEventClass()
    assert isinstance(obj.event, _EventSocket)
    assert isinstance(DummyEventClass.event, eventsocket)

def test_event_del():
    """Test event decorator get method"""
    obj = DummyEventClass()
    with pytest.raises(AttributeError) as cm:
        del obj.event
    assert cm.value.args == ("Can't delete eventsocket", )

def test_event_assign_and_clear(receiver):
    """Test slot assignment to eventsocket."""
    obj = DummyEventClass()
    slot = DummyEventSlotClass()
    #
    assert not obj.event.is_set()
    assert not obj.event2.is_set()
    #
    obj.event = receiver.set_val_int
    assert obj.event.is_set()
    obj.event = None
    assert not obj.event.is_set()
    #
    obj.event2 = receiver.set_val_int_ret_int
    assert obj.event2.is_set()
    obj.event2 = None
    assert not obj.event2.is_set()
    # Non-callable
    with pytest.raises(ValueError) as cm:
        obj.event = "non-callable"
    assert cm.value.args == ("Connection to non-callable 'str' object failed", )
    # Lambda
    obj.event3 = lambda value: _func(receiver, value)
    assert obj.event3.is_set()
    obj.event3 = None
    assert not obj.event3.is_set()
    # Function
    obj.event = value_event
    assert obj.event.is_set()
    obj.event = None
    assert not obj.event.is_set()
    # Partial
    obj.event = partial(slot.set_val_extra, extra="Partial")
    assert obj.event.is_set()
    obj.event = None
    assert not obj.event.is_set()
    # KW
    obj.event = slot.set_val_kw
    assert obj.event.is_set()
    obj.event = None
    assert not obj.event.is_set()

def test_event_call(receiver):
    """Test emitting events and that instances of the class are unique"""
    toSucceed = DummyEventClass()
    toSucceed.name = "toSucceed"
    toSucceed.event = receiver.set_val_int
    toSucceed.event2 = receiver.set_val_int_ret_int
    #
    toFail = DummyEventClass()
    toFail.name = "toFail"
    toFail.event = receiver.throwaway_int
    toFail.event2 = receiver.throwaway_int_ret_int
    #
    result = toSucceed.event(1)
    assert receiver.checkval == 1
    assert result is None
    #
    result = toSucceed.event2(2)
    assert result == 2 * 2
    assert receiver.checkval == 2
    #
    toFail.event(3)
    result = toFail.event2(3)
    assert result == 3 * 2
    assert receiver.checkval == 2
    assert receiver.setVal_call_count == 2

def test_event_method_event_handler_connect():
    """Test that instance slots will automatically go away with instance."""
    obj = DummyEventClass()
    slot = DummyEventSlotClass()
    #
    obj.event = slot.set_val_int
    assert obj.event.is_set()
    #
    del slot
    assert not obj.event.is_set()

def test_event_partial_event_handler_connect(receiver):
    """Tests connecting event to partial"""
    obj = DummyEventClass()
    p = partial(_func, receiver, "Partial")
    obj.event_nopar = p
    assert obj.event_nopar._slot == p

def test_event_partial_event_handler_connect_kw_differ_ok(receiver):
    """Tests connecting event to partial"""
    obj = DummyEventClass()
    p = partial(_func_with_kw_deafult, receiver, "Partial")
    obj.event_nopar = p
    assert obj.event_nopar._slot == p

def test_event_partial_event_handler_connect_kw_differ_bad(receiver):
    """Tests connecting event to partial"""
    obj = DummyEventClass()
    p = partial(_func_with_kw, receiver, "Partial")
    with pytest.raises(ValueError):
        obj.event_nopar = p
    assert obj.event_nopar._slot is None
    assert not obj.event_nopar.is_set()

def test_event_lambda_event_handler_connect(receiver):
    """Tests connecting event to lambda"""
    obj = DummyEventClass()
    l = lambda value: _func(receiver, value)
    obj.event3 = l
    assert obj.event3._slot == l

def test_event_method_event_handler_call():
    """Test that instance slots will automatically go away with instance."""
    obj = DummyEventClass()
    slot = DummyEventSlotClass()
    #
    obj.event = slot.set_val_int
    obj.event(1)
    assert slot.checkval == 1

def test_event_func_event_handler_call(receiver):
    """Tests calling event to function"""
    obj = DummyEventClass()
    #
    obj.event = value_event
    obj.event(1)
    assert ns["checkval"] == 1

def test_event_partial_event_handler_call():
    """Tests calling event to partial"""
    obj = DummyEventClass()
    slot = DummyEventSlotClass()
    obj.event3 = partial(slot.set_val_extra, extra="Partial")
    obj.event3(2)
    assert slot.checkval == 2

def test_event_partial_event_handler_call_kw():
    """Tests calling event to method with extra KW"""
    obj = DummyEventClass()
    slot = DummyEventSlotClass()
    obj.event = slot.set_val_kw
    obj.event(3)
    assert slot.checkval == 3

def test_event_lambda_event_handler_call(receiver):
    """Tests calling event to lambda"""
    obj = DummyEventClass()
    l = lambda value: _func(receiver, value)
    obj.event3 = l
    obj.event3(4)
    assert receiver.checkval == 4
