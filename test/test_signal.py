#coding:utf-8
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

"""firebird-base - Tests for firebird.base.signal module


"""

from __future__ import annotations
import typing as t
from firebird.base.signal import signal, Signal, eventsocket
from functools import partial
import inspect

try:
    import unittest2 as unittest
except ImportError:
    import unittest

def nopar_signal():
    pass

nopar_signature = inspect.Signature.from_callable(nopar_signal)

def value_signal(value):
    pass

slot_signature = inspect.Signature.from_callable(value_signal)

def testFunc(test, value):
    """A test standalone function for signals to attach onto"""
    test.checkval = value
    test.func_call_count += 1

testFunc_signature = inspect.Signature.from_callable(testFunc)

def testFuncWithKWDeafult(test, value, kiwi=None):
    """A test standalone function with excess default keyword argument for signals to attach onto"""
    test.checkval = value
    test.func_call_count += 1

def testFuncWithKW(test, value, *, kiwi):
    """A test standalone function with excess keyword argument for signals to attach onto"""
    test.checkval = value
    test.func_call_count += 1

def testLocalEmit(signal_instance):
    """A test standalone function for signals to emit at local level"""
    exec('signal_instance.emit()')


def testModuleEmit(signal_instance):
    """A test standalone function for signals to emit at module level"""
    signal_instance.emit()


class DummySignalClass:
    """A dummy class to check for instance handling of signals"""
    @signal
    def cSignal(self, value):
        "cSignal"
        pass

    @signal
    def cSignal2(self, value):
        "cSignal2"
        pass

    def __init__(self):
        self.signal = Signal(slot_signature)

    def triggerSignal(self):
        self.signal.emit()

    def triggerClassSignal(self):
        self.cSignal.emit(1)


class DummyEventClass:
    """A dummy class to check for eventsockets"""
    @eventsocket
    def event(self, value: int) -> None:
        "event"
        pass

    @eventsocket
    def event2(self, value: int) -> int:
        "event2"
        pass

class DummySlotClass:
    """A dummy class to check for slot handling"""
    checkval = None

    def setVal(self, value):
        """A method to test slot calls with"""
        self.checkval = val

class DummyEventSlotClass:
    """A dummy class to check for eventsocket slot handling"""
    checkval = None

    def setVal(self, value):
        """A method to test slot calls with"""
        self.checkval = value

    def setValInt(self, value: int) -> None:
        """A method to test slot calls with"""
        self.checkval = value

    def setValIntRetInt(self, value: int) -> int:
        """A method to test slot calls with"""
        self.checkval = value
        return value * 2

class SignalTestMixin:
    """Mixin class with common helpers for signal tests"""

    def __init__(self):
        self.checkval = None  # A state check for the tests
        self.checkval2 = None  # A state check for the tests
        self.setVal_call_count = 0  # A state check for the test method
        self.setVal2_call_count = 0  # A state check for the test method
        self.func_call_count = 0  # A state check for test function

    def reset(self):
        self.checkval = None
        self.checkval2 = None
        self.setVal_call_count = 0
        self.setVal2_call_count = 0
        self.func_call_count = 0

    # Helper methods
    def setVal(self, value):
        """A method to test instance settings with"""
        self.checkval = value
        self.setVal_call_count += 1

    def setVal2(self, value):
        """Another method to test instance settings with"""
        self.checkval2 = value
        self.setVal2_call_count += 1

    def setValInt(self, value: int) -> None:
        """A method to test slot calls with"""
        self.checkval = value
        self.setVal_call_count += 1

    def setValIntRetInt(self, value: int) -> int:
        """A method to test slot calls with"""
        self.checkval = value
        self.setVal_call_count += 1
        return value * 2

    def throwaway(self, value):
        """A method to throw redundant data into"""
        pass

    def throwawayInt(self, value: int) -> None:
        """A method to throw redundant data into"""
        pass

    def throwawayIntRetInt(self, value: int) -> int:
        """A method to throw redundant data into"""
        return value * 2

# noinspection PyProtectedMember
class SignalTest(unittest.TestCase, SignalTestMixin):
    """Unit tests for Signal class"""

    def setUp(self):
        self.reset()

    def __init__(self, methodName='runTest'):
        unittest.TestCase.__init__(self, methodName)
        SignalTestMixin.__init__(self)

    def test_PartialConnect(self):
        """Tests connecting signals to partials"""
        partialSignal = Signal(nopar_signature)
        partialSignal.connect(partial(testFunc, self, 'Partial'))
        self.assertEqual(len(partialSignal._slots), 1, "Expected single connected slot")

    def test_PartialConnectKWDifferOk(self):
        """Tests connecting signals to partials"""
        partialSignal = Signal(nopar_signature)
        partialSignal.connect(partial(testFuncWithKWDeafult, self, 'Partial'))
        self.assertEqual(len(partialSignal._slots), 1, "Expected single connected slot")

    def test_PartialConnectKWDifferBad(self):
        """Tests connecting signals to partials"""
        partialSignal = Signal(nopar_signature)
        with self.assertRaises(ValueError):
            partialSignal.connect(partial(testFuncWithKW, self, 'Partial'))
        self.assertEqual(len(partialSignal._slots), 0, "Expected single connected slot")

    def test_PartialConnectDuplicate(self):
        """Tests connecting signals to partials"""
        partialSignal = Signal(nopar_signature)
        func = partial(testFunc, self, 'Partial')
        partialSignal.connect(func)
        partialSignal.connect(func)
        self.assertEqual(len(partialSignal._slots), 1, "Expected single connected slot")

    def test_LambdaConnect(self):
        """Tests connecting signals to lambdas"""
        lambdaSignal = Signal(slot_signature)
        lambdaSignal.connect(lambda value: testFunc(self, value))
        self.assertEqual(len(lambdaSignal._slots), 1, "Expected single connected slot")

    def test_LambdaConnectDuplicate(self):
        """Tests connecting signals to duplicate lambdas"""
        lambdaSignal = Signal(slot_signature)
        func = lambda value: testFunc(self, value)
        lambdaSignal.connect(func)
        lambdaSignal.connect(func)
        self.assertEqual(len(lambdaSignal._slots), 1, "Expected single connected slot")

    def test_MethodConnect(self):
        """Test connecting signals to methods on class instances"""
        methodSignal = Signal(slot_signature)
        methodSignal.connect(self.setVal)
        self.assertEqual(len(methodSignal._islots), 1, "Expected single connected slot")
        self.assertEqual(len(methodSignal._slots), 0, "Expected single connected slot")

    def test_MethodConnectDuplicate(self):
        """Test that each method connection is unique"""
        methodSignal = Signal(slot_signature)
        methodSignal.connect(self.setVal)
        methodSignal.connect(self.setVal)
        self.assertEqual(len(methodSignal._islots), 1, "Expected single connected slot")
        self.assertEqual(len(methodSignal._slots), 0, "Expected single connected slot")

    def test_MethodConnectDifferentInstances(self):
        """Test connecting the same method from different instances"""
        methodSignal = Signal(slot_signature)
        dummy1 = DummySlotClass()
        dummy2 = DummySlotClass()
        methodSignal.connect(dummy1.setVal)
        methodSignal.connect(dummy2.setVal)
        self.assertEqual(len(methodSignal._islots), 2, "Expected two connected slots")
        self.assertEqual(len(methodSignal._slots), 0, "Expected single connected slot")

    def test_FunctionConnect(self):
        """Test connecting signals to standalone functions"""
        funcSignal = Signal(testFunc_signature)
        funcSignal.connect(testFunc)
        self.assertEqual(len(funcSignal._slots), 1, "Expected single connected slot")

    def test_FunctionConnectDuplicate(self):
        """Test that each function connection is unique"""
        funcSignal = Signal(testFunc_signature)
        funcSignal.connect(testFunc)
        funcSignal.connect(testFunc)
        self.assertEqual(len(funcSignal._slots), 1, "Expected single connected slot")

    def test_ConnectNonCallable(self):
        """Test connecting non-callable object"""
        nonCallableSignal = Signal(slot_signature)
        with self.assertRaises(ValueError):
            nonCallableSignal.connect(self.checkval)

    def test_EmitToPartial(self):
        """Test emitting signals to partial"""
        partialSignal = Signal(nopar_signature)
        partialSignal.connect(partial(testFunc, self, 'Partial'))
        partialSignal.emit()
        self.assertEqual(self.checkval, 'Partial')
        self.assertEqual(self.func_call_count, 1, "Expected function to be called once")

    def test_EmitToLambda(self):
        """Test emitting signal to lambda"""
        lambdaSignal = Signal(slot_signature)
        lambdaSignal.connect(lambda value: testFunc(self, value))
        lambdaSignal.emit('Lambda')
        self.assertEqual(self.checkval, 'Lambda')
        self.assertEqual(self.func_call_count, 1, "Expected function to be called once")

    def test_EmitToMethod(self):
        """Test emitting signal to method"""
        toSucceed = DummySignalClass()
        toSucceed.signal.connect(self.setVal)
        toSucceed.signal.emit('Method')
        self.assertEqual(self.checkval, 'Method')
        self.assertEqual(self.setVal_call_count, 1, "Expected function to be called once")

    def test_EmitToMethodOnDeletedInstance(self):
        """Test emitting signal to deleted instance method"""
        toDelete = DummySlotClass()
        toCall = Signal(slot_signature)
        toCall.connect(toDelete.setVal)
        toCall.connect(self.setVal)
        del toDelete
        toCall.emit(1)
        self.assertEqual(self.checkval, 1)

    def test_EmitToFunction(self):
        """Test emitting signal to standalone function"""
        funcSignal = Signal(testFunc_signature)
        funcSignal.connect(testFunc)
        funcSignal.emit(self, 'Function')
        self.assertEqual(self.checkval, 'Function')
        self.assertEqual(self.func_call_count, 1, "Expected function to be called once")

    def test_EmitToDeletedFunction(self):
        """Test emitting signal to deleted instance method"""
        def ToDelete(test, value):
            test.checkVal = value
            test.func_call_count += 1
        funcSignal = Signal(inspect.Signature.from_callable(ToDelete))
        funcSignal.connect(ToDelete)
        del ToDelete
        funcSignal.emit(self, 1)
        self.assertEqual(self.checkval, None)
        self.assertEqual(self.func_call_count, 0)

    def test_PartialDisconnect(self):
        """Test disconnecting partial function"""
        partialSignal = Signal(nopar_signature)
        part = partial(testFunc, self, 'Partial')
        partialSignal.connect(part)
        partialSignal.disconnect(part)
        self.assertEqual(self.checkval, None, "Slot was not removed from signal")

    def test_PartialDisconnectUnconnected(self):
        """Test disconnecting unconnected partial function"""
        partialSignal = Signal(slot_signature)
        part = partial(testFunc, self, 'Partial')
        try:
            partialSignal.disconnect(part)
        except:
            self.fail("Disonnecting unconnected partial should not raise")

    def test_LambdaDisconnect(self):
        """Test disconnecting lambda function"""
        lambdaSignal = Signal(slot_signature)
        func = lambda value: testFunc(self, value)
        lambdaSignal.connect(func)
        lambdaSignal.disconnect(func)
        self.assertEqual(len(lambdaSignal._slots), 0, "Slot was not removed from signal")

    def test_LambdaDisconnectUnconnected(self):
        """Test disconnecting unconnected lambda function"""
        lambdaSignal = Signal(slot_signature)
        func = lambda value: testFunc(self, value)
        try:
            lambdaSignal.disconnect(func)
        except:
            self.fail("Disconnecting unconnected lambda should not raise")

    def test_MethodDisconnect(self):
        """Test disconnecting method"""
        toCall = Signal(slot_signature)
        toCall.connect(self.setVal)
        toCall.disconnect(self.setVal)
        toCall.emit(1)
        self.assertEqual(len(toCall._islots), 0, "Expected 1 connected after disconnect, found %d" % len(toCall._slots))
        self.assertEqual(self.setVal_call_count, 0, "Expected function to be called once")

    def test_MethodDisconnectUnconnected(self):
        """Test disconnecting unconnected method"""
        toCall = Signal(slot_signature)
        try:
            toCall.disconnect(self.setVal)
        except:
            self.fail("Disconnecting unconnected method should not raise")

    def test_FunctionDisconnect(self):
        """Test disconnecting function"""
        funcSignal = Signal(testFunc_signature)
        funcSignal.connect(testFunc)
        funcSignal.disconnect(testFunc)
        self.assertEqual(len(funcSignal._slots), 0, "Slot was not removed from signal")

    def test_FunctionDisconnectUnconnected(self):
        """Test disconnecting unconnected function"""
        funcSignal = Signal(slot_signature)
        try:
            funcSignal.disconnect(testFunc)
        except:
            self.fail("Disconnecting unconnected function should not raise")

    def test_DisconnectNonCallable(self):
        """Test disconnecting non-callable object"""
        signal = Signal(slot_signature)
        try:
            signal.disconnect(self.checkval)
        except:
            self.fail("Disconnecting invalid object should not raise")

    def test_ClearSlots(self):
        """Test clearing all slots"""
        multiSignal = Signal(slot_signature)
        func = lambda value: self.setVal(value)
        multiSignal.connect(partial(testFunc, self))
        multiSignal.connect(self.setVal)
        multiSignal.clear()
        self.assertEqual(len(multiSignal._slots), 0, "Not all slots were removed from signal")


class ClassSignalTest(unittest.TestCase, SignalTestMixin):
    """Unit tests for ClassSignal class"""

    def setUp(self):
        self.reset()

    def __init__(self, methodName='runTest'):
        unittest.TestCase.__init__(self, methodName)
        SignalTestMixin.__init__(self)

    def test_AssignToProperty(self):
        """Test assigning to a ClassSignal property"""
        dummy = DummySignalClass()
        with self.assertRaises(AttributeError):
            dummy.cSignal = None

    # noinspection PyUnresolvedReferences
    def test_Emit(self):
        """Test emitting signals from class signal and that instances of the class are unique"""
        toSucceed = DummySignalClass()
        toSucceed.name = 'toSucceed'
        toSucceed.cSignal.connect(self.setVal)
        toSucceed.cSignal2.connect(self.setVal)
        toFail = DummySignalClass()
        toFail.name = 'toFail'
        toFail.cSignal.connect(self.throwaway)
        toFail.cSignal2.connect(self.throwaway)
        toSucceed.cSignal.emit(1)
        self.assertEqual(self.checkval, 1)
        toSucceed.cSignal2.emit(2)
        self.assertEqual(self.checkval, 2)
        toFail.cSignal.emit(3)
        toFail.cSignal2.emit(3)
        self.assertEqual(self.checkval, 2)
        self.assertEqual(self.setVal_call_count, 2)

class eventsocketTest(unittest.TestCase, SignalTestMixin):
    """Unit tests for ClassSignal class"""

    def setUp(self):
        self.reset()

    def __init__(self, methodName='runTest'):
        unittest.TestCase.__init__(self, methodName)
        SignalTestMixin.__init__(self)

    def test_01_assign(self):
        """Test slot assignment to eventsocket."""
        obj = DummyEventClass()
        #
        self.assertFalse(obj.event.is_set())
        self.assertFalse(obj.event2.is_set())
        #
        obj.event = self.setValInt
        self.assertTrue(obj.event.is_set())
        #
        obj.event2 = self.setValIntRetInt

    def test_02_clear(self):
        """Test slot assignment to eventsocket."""
        obj = DummyEventClass()
        #
        obj.event = self.setValInt
        self.assertTrue(obj.event.is_set())
        #
        obj.event = None
        self.assertFalse(obj.event.is_set())
        obj.event = None

    # noinspection PyUnresolvedReferences
    def test_03_call(self):
        """Test emitting events and that instances of the class are unique"""
        toSucceed = DummyEventClass()
        toSucceed.name = 'toSucceed'
        toSucceed.event = self.setValInt
        toSucceed.event2 = self.setValIntRetInt
        #
        toFail = DummyEventClass()
        toFail.name = 'toFail'
        toFail.event = self.throwawayInt
        toFail.event2 = self.throwawayIntRetInt
        #
        result = toSucceed.event(1)
        self.assertEqual(self.checkval, 1)
        self.assertIsNone(result)
        result = toSucceed.event2(2)
        self.assertEqual(result, 2 * 2)
        self.assertEqual(self.checkval, 2)
        toFail.event(3)
        result = toFail.event2(3)
        self.assertEqual(result, 3 * 2)
        self.assertEqual(self.checkval, 2)
        self.assertEqual(self.setVal_call_count, 2)

    def test_04_instance_slot(self):
        """Test that instance slots will automatically go away with instance."""
        obj = DummyEventClass()
        slot = DummyEventSlotClass()
        #
        obj.event = slot.setValInt
        self.assertTrue(obj.event.is_set())
        #
        del slot
        self.assertFalse(obj.event.is_set())

