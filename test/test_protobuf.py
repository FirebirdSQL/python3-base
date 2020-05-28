#coding:utf-8
#
# PROGRAM/MODULE: firebird-base
# FILE:           test/test_protobuf.py
# DESCRIPTION:    Unit tests for firebird.base.protobuf
# CREATED:        21.5.2020
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

"""firebird-base - Unit tests for firebird.base.protobuf

"""

from __future__ import annotations
import unittest
from enum import IntEnum
from firebird.base.types import Error
from firebird.base.protobuf import register_decriptor, get_enum_type, get_enum_field_type, \
     get_enum_value_name, is_enum_registered, is_msg_registered, create_message, \
     ProtoEnumType, _enumreg, _msgreg
from base_test_pb2 import DESCRIPTOR

ENUM_TYPE_NAME: str = 'firebird.base.TestEnum'
STATE_MSG_TYPE_NAME: str = 'firebird.base.TestState'
COLLECTION_MSG_TYPE_NAME: str = 'firebird.base.TestCollection'


class TestProtobuf(unittest.TestCase):
    """Unit tests for firebird.base.types"""
    def __init__(self, methodName='runTest'):
        super().__init__(methodName)
    def setUp(self) -> None:
        _enumreg.clear()
        _msgreg.clear()
    def tearDown(self):
        pass
    def test_aaa_register(self):
        self.assertEqual(len(_msgreg), 0)
        self.assertEqual(len(_enumreg), 0)
        #
        self.assertFalse(is_enum_registered(ENUM_TYPE_NAME))
        self.assertFalse(is_msg_registered(STATE_MSG_TYPE_NAME))
        self.assertFalse(is_msg_registered(COLLECTION_MSG_TYPE_NAME))
        #
        register_decriptor(DESCRIPTOR)
        #
        self.assertTrue(is_enum_registered(ENUM_TYPE_NAME))
        self.assertTrue(is_msg_registered(STATE_MSG_TYPE_NAME))
        self.assertTrue(is_msg_registered(COLLECTION_MSG_TYPE_NAME))
        #
        self.assertEqual(len(_msgreg), 2)
        self.assertEqual(len(_enumreg), 1)
        self.assertIn(ENUM_TYPE_NAME, _enumreg)
        self.assertIn(STATE_MSG_TYPE_NAME, _msgreg)
        self.assertIn(COLLECTION_MSG_TYPE_NAME, _msgreg)
    def test_enums(self):
        class TestEnum(IntEnum):
            UNKNOWN = 0
            READY = 1
            RUNNING = 2
            WAITING = 3
            SUSPENDED = 4
            FINISHED = 5
            ABORTED = 6
            # Aliases
            CREATED = 1
            BLOCKED = 3
            STOPPED = 4
            TERMINATED = 6

        enum_spec = [('TEST_UNKNOWN', 0),
                     ('TEST_READY', 1),
                     ('TEST_RUNNING', 2),
                     ('TEST_WAITING', 3),
                     ('TEST_SUSPENDED', 4),
                     ('TEST_FINISHED', 5),
                     ('TEST_ABORTED', 6),
                     ('TEST_CREATED', 1),
                     ('TEST_BLOCKED', 3),
                     ('TEST_STOPPED', 4),
                     ('TEST_TERMINATED', 6),
                     ]
        register_decriptor(DESCRIPTOR)
        # Value name
        self.assertEqual(get_enum_value_name(ENUM_TYPE_NAME, TestEnum.SUSPENDED),
                         f'TEST_{TestEnum.SUSPENDED.name}')
        # Errors
        with self.assertRaises(KeyError) as cm:
            get_enum_value_name('BAD.TYPE', TestEnum.SUSPENDED)
        self.assertEqual(cm.exception.args, ("Unregistered protobuf enum type 'BAD.TYPE'",))
        with self.assertRaises(KeyError) as cm:
            get_enum_value_name(ENUM_TYPE_NAME, 9999)
        self.assertEqual(cm.exception.args, (f"Enum {ENUM_TYPE_NAME} has no name defined for value 9999",))
        # Type specification
        enum: ProtoEnumType = get_enum_type(ENUM_TYPE_NAME)
        self.assertEqual(enum.name, ENUM_TYPE_NAME)
        self.assertEqual(enum.get_value_name(TestEnum.SUSPENDED),
                         f'TEST_{TestEnum.SUSPENDED.name}')
        self.assertListEqual(enum.items(), enum_spec)
        self.assertListEqual(enum.keys(), [k for k, v in enum_spec])
        self.assertListEqual(enum.values(), [v for k, v in enum_spec])
        # attribute access to enum values
        for name, value in enum_spec:
            self.assertEqual(getattr(enum, name), value)
        with self.assertRaises(AttributeError) as cm:
            enum.TEST_BAD_VALUE
        self.assertEqual(cm.exception.args, (f"Enum {ENUM_TYPE_NAME} has no value with name 'TEST_BAD_VALUE'",))
    def test_messages(self):
        register_decriptor(DESCRIPTOR)
        #
        msg = create_message(STATE_MSG_TYPE_NAME)
        self.assertIsNotNone(msg)
        self.assertEqual(get_enum_field_type(msg, 'test'), ENUM_TYPE_NAME)
        #
        msg.name = 'State.NAME'
        msg.test = 1
        # Errors
        with self.assertRaises(KeyError) as cm:
            create_message('NOT_REGISTERED')
        self.assertEqual(cm.exception.args, ("Unregistered protobuf message 'NOT_REGISTERED'",))
        with self.assertRaises(KeyError) as cm:
            get_enum_field_type(msg, 'BAD_FIELD')
        self.assertEqual(cm.exception.args, ("Message does not have field 'BAD_FIELD'",))

