#!/usr/bin/python
#coding:utf-8
#
# PROGRAM/MODULE: firebird-base
# FILE:           test/test_config.py
# DESCRIPTION:    Unit tests for firebird.base.config
# CREATED:        20.9.2019
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
# Copyright (c) 2019 Firebird Project (www.firebirdsql.org)
# All Rights Reserved.
#
# Contributor(s): Pavel Císař (original code)
#                 ______________________________________.

"Firebird Base - Unit tests for firebird.base.config."

from __future__ import annotations
from unittest import TestCase, mock, main as unittest_main
from uuid import UUID
from decimal import Decimal
import io
import os
import platform
from pathlib import Path
from enum import IntEnum, IntFlag, Flag, auto
from dataclasses import dataclass
from inspect import signature
from configparser import ConfigParser, ExtendedInterpolation
from firebird.base.types import Error, ZMQAddress, MIME, PyExpr, PyCode, PyCallable
from firebird.base.strconv import convert_to_str
from firebird.base import config

DEFAULT_S = 'DEFAULT'
PRESENT_S = 'present'
ABSENT_S = 'absent'
BAD_S = 'bad_value'
EMPTY_S = 'empty'

class SimpleEnum(IntEnum):
    "Enum for testing"
    UNKNOWN    = 0
    READY      = 1
    RUNNING    = 2
    WAITING    = 3
    SUSPENDED  = 4
    FINISHED   = 5
    ABORTED    = 6
    # Aliases
    CREATED    = 1
    BLOCKED    = 3
    STOPPED    = 4
    TERMINATED = 6

class SimpleIntFlag(IntFlag):
    "Flag for testing"
    ONE = auto()
    TWO = auto()
    THREE = auto()
    FOUR = auto()
    FIVE = auto()

class SimpleFlag(Flag):
    "Flag for testing"
    ONE = auto()
    TWO = auto()
    THREE = auto()
    FOUR = auto()
    FIVE = auto()

@dataclass
class SimpleDataclass:
    name: str
    priority: int = 1
    state: SimpleEnum = SimpleEnum.READY

class ValueHolder:
    "Simple values holding object"

def foo_func(value: int) -> int:
    ...

def store_opt(d, o):
    d[o.name] = o

class BaseConfigTest(TestCase):
    "Base class for firebird.base.config unit tests"
    def setUp(self):
        self.proto: config.ConfigProto = config.ConfigProto()
        self.conf: ConfigParser = ConfigParser(interpolation=ExtendedInterpolation())
    def tearDown(self):
        pass
    def setConf(self, conf_str):
        self.conf.read_string(conf_str % {'DEFAULT': DEFAULT_S, 'PRESENT': PRESENT_S,
                                          'ABSENT': ABSENT_S, 'BAD': BAD_S, 'EMPTY': EMPTY_S,})

class TestStrOption(BaseConfigTest):
    "Unit tests for firebird.base.config.StrOption"
    PRESENT_VAL = 'present_value\ncan be multiline'
    DEFAULT_VAL = 'DEFAULT_value'
    DEFAULT_OPT_VAL = 'DEFAULT'
    NEW_VAL = 'new_value'
    def setUp(self):
        super().setUp()
        self.setConf("""[%(DEFAULT)s]
option_name = DEFAULT_value
[%(PRESENT)s]
option_name = present_value
   can be multiline
[%(ABSENT)s]
[%(BAD)s]
option_name =
""")
    def test_simple(self):
        opt = config.StrOption('option_name', 'description')
        self.assertEqual(opt.name, 'option_name')
        self.assertEqual(opt.datatype, str)
        self.assertEqual(opt.description, 'description')
        self.assertFalse(opt.required)
        self.assertIsNone(opt.default)
        self.assertIsNone(opt.value)
        opt.validate()
        opt.load_config(self.conf, PRESENT_S)
        self.assertEqual(opt.value, self.PRESENT_VAL)
        self.assertEqual(opt.get_formatted(), 'present_value\n   can be multiline')
        self.assertIsInstance(opt.value, opt.datatype)
        opt.clear()
        self.assertIsNone(opt.value)
        opt.load_config(self.conf, DEFAULT_S)
        self.assertEqual(opt.value, self.DEFAULT_VAL)
        self.assertIsInstance(opt.value, opt.datatype)
        opt.set_value(None)
        self.assertIsNone(opt.value)
        opt.load_config(self.conf, ABSENT_S)
        self.assertEqual(opt.value, self.DEFAULT_VAL)
        self.assertIsInstance(opt.value, opt.datatype)
        opt.set_value(self.NEW_VAL)
        self.assertEqual(opt.value, self.NEW_VAL)
        self.assertIsInstance(opt.value, opt.datatype)
    def test_required(self):
        opt = config.StrOption('option_name', 'description', required=True)
        self.assertEqual(opt.name, 'option_name')
        self.assertEqual(opt.datatype, str)
        self.assertEqual(opt.description, 'description')
        self.assertTrue(opt.required)
        self.assertIsNone(opt.default)
        self.assertIsNone(opt.value)
        with self.assertRaises(Error) as cm:
            opt.validate()
        self.assertEqual(cm.exception.args, ("Missing value for required option 'option_name'",))
        opt.load_config(self.conf, PRESENT_S)
        self.assertEqual(opt.value, self.PRESENT_VAL)
        opt.validate()
        opt.clear()
        self.assertIsNone(opt.value)
        opt.load_config(self.conf, DEFAULT_S)
        self.assertEqual(opt.value, self.DEFAULT_VAL)
        with self.assertRaises(ValueError) as cm:
            opt.set_value(None)
        self.assertEqual(cm.exception.args, ("Value is required for option 'option_name'.",))
        opt.load_config(self.conf, ABSENT_S)
        self.assertEqual(opt.value, self.DEFAULT_VAL)
        opt.set_value(self.NEW_VAL)
        self.assertEqual(opt.value, self.NEW_VAL)
    def test_bad_value(self):
        opt = config.StrOption('option_name', 'description')
        opt.load_config(self.conf, BAD_S)
        self.assertEqual(opt.value, '')
        with self.assertRaises(TypeError) as cm:
            opt.set_value(10.0)
        self.assertEqual(cm.exception.args, ("Option 'option_name' value must be a 'str', not 'float'",))
    def test_default(self):
        opt = config.StrOption('option_name', 'description', default=self.DEFAULT_OPT_VAL)
        self.assertEqual(opt.name, 'option_name')
        self.assertEqual(opt.datatype, str)
        self.assertEqual(opt.description, 'description')
        self.assertFalse(opt.required)
        self.assertEqual(opt.default, self.DEFAULT_OPT_VAL)
        self.assertIsInstance(opt.default, opt.datatype)
        self.assertEqual(opt.value, self.DEFAULT_OPT_VAL)
        self.assertIsInstance(opt.value, opt.datatype)
        opt.validate()
        opt.load_config(self.conf, PRESENT_S)
        self.assertEqual(opt.value, self.PRESENT_VAL)
        opt.clear()
        self.assertEqual(opt.value, opt.default)
        opt.load_config(self.conf, DEFAULT_S)
        self.assertEqual(opt.value, self.DEFAULT_VAL)
        opt.set_value(None)
        self.assertIsNone(opt.value)
        opt.load_config(self.conf, ABSENT_S)
        self.assertEqual(opt.value, self.DEFAULT_VAL)
        opt.set_value(self.NEW_VAL)
        self.assertEqual(opt.value, self.NEW_VAL)
    def test_proto(self):
        opt = config.StrOption('option_name', 'description', default=self.DEFAULT_OPT_VAL)
        proto_value = 'proto_value'
        opt.set_value(proto_value)
        self.proto.options['option_name'].as_string = proto_value
        proto_dump = str(self.proto)
        opt.load_proto(self.proto)
        self.assertEqual(opt.value, proto_value)
        self.assertIsInstance(opt.value, opt.datatype)
        self.proto.Clear()
        self.assertFalse('option_name' in self.proto.options)
        opt.save_proto(self.proto)
        self.assertTrue('option_name' in self.proto.options)
        self.assertEqual(str(self.proto), proto_dump)
        # empty proto
        opt.clear(to_default=False)
        self.proto.Clear()
        opt.load_proto(self.proto)
        self.assertIsNone(opt.value)
        # bad proto value
        self.proto.options['option_name'].as_uint64 = 1000
        with self.assertRaises(TypeError) as cm:
            opt.load_proto(self.proto)
        self.assertEqual(cm.exception.args, ('Wrong value type: uint64',))
        self.proto.Clear()
        opt.clear(to_default=False)
        opt.save_proto(self.proto)
        self.assertFalse('option_name' in self.proto.options)
    def test_get_config(self):
        opt = config.StrOption('option_name', 'description', default=self.DEFAULT_OPT_VAL)
        lines = """; option_name
; -----------
;
; data type: str
;
; [optional] description
;
;option_name = DEFAULT
"""
        self.assertEqual(opt.get_config(), lines)
        lines = """; option_name
; -----------
;
; data type: str
;
; [optional] description
;
option_name = Multiline
   value
"""
        opt.set_value("Multiline\nvalue")
        self.assertEqual(opt.get_config(), lines)
        lines = """; option_name
; -----------
;
; data type: str
;
; [optional] description
;
option_name = <UNDEFINED>
"""
        opt.set_value(None)
        self.assertEqual(opt.get_config(), lines)

class TestIntOption(BaseConfigTest):
    "Unit tests for firebird.base.config.IntOption"
    PRESENT_VAL = 500
    DEFAULT_VAL = 10
    DEFAULT_OPT_VAL = 3000
    NEW_VAL = 0
    def setUp(self):
        super().setUp()
        self.setConf("""[%(DEFAULT)s]
option_name = 10
[%(PRESENT)s]
option_name = 500
[%(ABSENT)s]
[%(BAD)s]
option_name = bad_value
""")
    def test_simple(self):
        opt = config.IntOption('option_name', 'description')
        self.assertEqual(opt.name, 'option_name')
        self.assertEqual(opt.datatype, int)
        self.assertEqual(opt.description, 'description')
        self.assertFalse(opt.required)
        self.assertIsNone(opt.default)
        self.assertIsNone(opt.value)
        opt.validate()
        opt.load_config(self.conf, PRESENT_S)
        self.assertEqual(opt.value, self.PRESENT_VAL)
        self.assertEqual(opt.get_as_str(), '500')
        self.assertIsInstance(opt.value, opt.datatype)
        opt.clear()
        self.assertIsNone(opt.value)
        opt.load_config(self.conf, DEFAULT_S)
        self.assertEqual(opt.value, self.DEFAULT_VAL)
        self.assertIsInstance(opt.value, opt.datatype)
        opt.set_value(None)
        self.assertIsNone(opt.value)
        opt.load_config(self.conf, ABSENT_S)
        self.assertEqual(opt.value, self.DEFAULT_VAL)
        self.assertIsInstance(opt.value, opt.datatype)
        opt.set_value(self.NEW_VAL)
        self.assertEqual(opt.value, self.NEW_VAL)
        self.assertIsInstance(opt.value, opt.datatype)
    def test_required(self):
        opt = config.IntOption('option_name', 'description', required=True)
        self.assertEqual(opt.name, 'option_name')
        self.assertEqual(opt.datatype, int)
        self.assertEqual(opt.description, 'description')
        self.assertTrue(opt.required)
        self.assertIsNone(opt.default)
        self.assertIsNone(opt.value)
        with self.assertRaises(Error) as cm:
            opt.validate()
        self.assertEqual(cm.exception.args, ("Missing value for required option 'option_name'",))
        opt.load_config(self.conf, PRESENT_S)
        self.assertEqual(opt.value, self.PRESENT_VAL)
        opt.validate()
        opt.clear()
        self.assertIsNone(opt.value)
        opt.load_config(self.conf, DEFAULT_S)
        self.assertEqual(opt.value, self.DEFAULT_VAL)
        with self.assertRaises(ValueError) as cm:
            opt.set_value(None)
        self.assertEqual(cm.exception.args, ("Value is required for option 'option_name'.",))
        opt.load_config(self.conf, ABSENT_S)
        self.assertEqual(opt.value, self.DEFAULT_VAL)
        opt.set_value(self.NEW_VAL)
        self.assertEqual(opt.value, self.NEW_VAL)
    def test_bad_value(self):
        opt = config.IntOption('option_name', 'description')
        with self.assertRaises(ValueError) as cm:
            opt.load_config(self.conf, BAD_S)
        self.assertEqual(cm.exception.args, ("invalid literal for int() with base 10: 'bad_value'",))
        with self.assertRaises(TypeError) as cm:
            opt.set_value(10.0)
        self.assertEqual(cm.exception.args, ("Option 'option_name' value must be a 'int', not 'float'",))
    def test_default(self):
        opt = config.IntOption('option_name', 'description', default=self.DEFAULT_OPT_VAL)
        self.assertEqual(opt.name, 'option_name')
        self.assertEqual(opt.datatype, int)
        self.assertEqual(opt.description, 'description')
        self.assertFalse(opt.required)
        self.assertEqual(opt.default, self.DEFAULT_OPT_VAL)
        self.assertIsInstance(opt.default, opt.datatype)
        self.assertEqual(opt.value, self.DEFAULT_OPT_VAL)
        self.assertIsInstance(opt.value, opt.datatype)
        opt.validate()
        opt.load_config(self.conf, PRESENT_S)
        self.assertEqual(opt.value, self.PRESENT_VAL)
        opt.clear()
        self.assertEqual(opt.value, opt.default)
        opt.load_config(self.conf, DEFAULT_S)
        self.assertEqual(opt.value, self.DEFAULT_VAL)
        opt.set_value(None)
        self.assertIsNone(opt.value)
        opt.load_config(self.conf, ABSENT_S)
        self.assertEqual(opt.value, self.DEFAULT_VAL)
        opt.set_value(self.NEW_VAL)
        self.assertEqual(opt.value, self.NEW_VAL)
    def test_proto(self):
        opt = config.IntOption('option_name', 'description', default=self.DEFAULT_OPT_VAL)
        proto_value = 800000
        opt.set_value(proto_value)
        self.proto.options['option_name'].as_uint64 = proto_value
        proto_dump = str(self.proto)
        opt.load_proto(self.proto)
        self.assertEqual(opt.value, proto_value)
        self.assertIsInstance(opt.value, opt.datatype)
        self.proto.Clear()
        self.assertFalse('option_name' in self.proto.options)
        opt.save_proto(self.proto)
        self.assertTrue('option_name' in self.proto.options)
        self.assertEqual(str(self.proto), proto_dump)
        # empty proto
        opt.clear(False)
        self.proto.Clear()
        opt.load_proto(self.proto)
        self.assertIsNone(opt.value)
        # bad proto value
        self.proto.options['option_name'].as_string = 'BAD VALUE'
        with self.assertRaises(ValueError) as cm:
            opt.load_proto(self.proto)
        self.assertEqual(cm.exception.args, ("invalid literal for int() with base 10: 'BAD VALUE'",))
        self.proto.options['option_name'].as_bytes = b'BAD VALUE'
        with self.assertRaises(TypeError) as cm:
            opt.load_proto(self.proto)
        self.assertEqual(cm.exception.args, ('Wrong value type: bytes',))
        self.proto.Clear()
        opt.clear(False)
        opt.save_proto(self.proto)
        self.assertFalse('option_name' in self.proto.options)
    def test_get_config(self):
        opt = config.IntOption('option_name', 'description', default=self.DEFAULT_OPT_VAL)
        lines = """; option_name
; -----------
;
; data type: int
;
; [optional] description
;
;option_name = 3000
"""
        self.assertEqual(opt.get_config(), lines)
        lines = """; option_name
; -----------
;
; data type: int
;
; [optional] description
;
option_name = 500
"""
        opt.set_value(500)
        self.assertEqual(opt.get_config(), lines)
        lines = """; option_name
; -----------
;
; data type: int
;
; [optional] description
;
option_name = <UNDEFINED>
"""
        opt.set_value(None)
        self.assertEqual(opt.get_config(), lines)

class TestFloatOption(BaseConfigTest):
    "Unit tests for firebird.base.config.FloatOption"
    PRESENT_VAL = 500.0
    DEFAULT_VAL = 10.5
    DEFAULT_OPT_VAL = 3000.0
    NEW_VAL = 0.0
    def setUp(self):
        super().setUp()
        self.setConf("""[%(DEFAULT)s]
option_name = 10.5
[%(PRESENT)s]
option_name = 500
[%(ABSENT)s]
[%(BAD)s]
option_name = bad_value
""")
    def test_simple(self):
        opt = config.FloatOption('option_name', 'description')
        self.assertEqual(opt.name, 'option_name')
        self.assertEqual(opt.datatype, float)
        self.assertEqual(opt.description, 'description')
        self.assertFalse(opt.required)
        self.assertIsNone(opt.default)
        self.assertIsNone(opt.value)
        opt.validate()
        opt.load_config(self.conf, PRESENT_S)
        self.assertEqual(opt.value, self.PRESENT_VAL)
        self.assertEqual(opt.get_as_str(), '500.0')
        self.assertIsInstance(opt.value, opt.datatype)
        opt.clear()
        self.assertIsNone(opt.value)
        opt.load_config(self.conf, DEFAULT_S)
        self.assertEqual(opt.value, self.DEFAULT_VAL)
        self.assertIsInstance(opt.value, opt.datatype)
        opt.set_value(None)
        self.assertIsNone(opt.value)
        opt.load_config(self.conf, ABSENT_S)
        self.assertEqual(opt.value, self.DEFAULT_VAL)
        self.assertIsInstance(opt.value, opt.datatype)
        opt.set_value(self.NEW_VAL)
        self.assertEqual(opt.value, self.NEW_VAL)
        self.assertIsInstance(opt.value, opt.datatype)
    def test_required(self):
        opt = config.FloatOption('option_name', 'description', required=True)
        self.assertEqual(opt.name, 'option_name')
        self.assertEqual(opt.datatype, float)
        self.assertEqual(opt.description, 'description')
        self.assertTrue(opt.required)
        self.assertIsNone(opt.default)
        self.assertIsNone(opt.value)
        with self.assertRaises(Error) as cm:
            opt.validate()
        self.assertEqual(cm.exception.args, ("Missing value for required option 'option_name'",))
        opt.load_config(self.conf, PRESENT_S)
        self.assertEqual(opt.value, self.PRESENT_VAL)
        opt.validate()
        opt.clear()
        self.assertIsNone(opt.value)
        opt.load_config(self.conf, DEFAULT_S)
        self.assertEqual(opt.value, self.DEFAULT_VAL)
        with self.assertRaises(ValueError) as cm:
            opt.set_value(None)
        self.assertEqual(cm.exception.args, ("Value is required for option 'option_name'.",))
        opt.load_config(self.conf, ABSENT_S)
        self.assertEqual(opt.value, self.DEFAULT_VAL)
        opt.set_value(self.NEW_VAL)
        self.assertEqual(opt.value, self.NEW_VAL)
    def test_bad_value(self):
        opt = config.FloatOption('option_name', 'description')
        with self.assertRaises(ValueError) as cm:
            opt.load_config(self.conf, BAD_S)
        self.assertEqual(cm.exception.args, ("could not convert string to float: 'bad_value'",))
        with self.assertRaises(TypeError) as cm:
            opt.set_value(10)
        self.assertEqual(cm.exception.args, ("Option 'option_name' value must be a 'float', not 'int'",))
        with self.assertRaises(TypeError) as cm:
            opt.set_value(0)
        self.assertEqual(cm.exception.args, ("Option 'option_name' value must be a 'float', not 'int'",))
    def test_default(self):
        opt = config.FloatOption('option_name', 'description', default=self.DEFAULT_OPT_VAL)
        self.assertEqual(opt.name, 'option_name')
        self.assertEqual(opt.datatype, float)
        self.assertEqual(opt.description, 'description')
        self.assertFalse(opt.required)
        self.assertEqual(opt.default, self.DEFAULT_OPT_VAL)
        self.assertIsInstance(opt.value, opt.datatype)
        self.assertEqual(opt.value, self.DEFAULT_OPT_VAL)
        self.assertIsInstance(opt.value, opt.datatype)
        opt.validate()
        opt.load_config(self.conf, PRESENT_S)
        self.assertEqual(opt.value, self.PRESENT_VAL)
        opt.clear()
        self.assertEqual(opt.value, opt.default)
        opt.load_config(self.conf, DEFAULT_S)
        self.assertEqual(opt.value, self.DEFAULT_VAL)
        opt.set_value(None)
        self.assertIsNone(opt.value)
        opt.load_config(self.conf, ABSENT_S)
        self.assertEqual(opt.value, self.DEFAULT_VAL)
        opt.set_value(self.NEW_VAL)
        self.assertEqual(opt.value, self.NEW_VAL)
    def test_proto(self):
        opt = config.FloatOption('option_name', 'description', default=self.DEFAULT_OPT_VAL)
        proto_value = 800000.0
        opt.set_value(proto_value)
        self.proto.options['option_name'].as_double = proto_value
        proto_dump = str(self.proto)
        opt.load_proto(self.proto)
        self.assertEqual(opt.value, proto_value)
        self.assertIsInstance(opt.value, opt.datatype)
        self.proto.Clear()
        self.assertFalse('option_name' in self.proto.options)
        opt.save_proto(self.proto)
        self.assertTrue('option_name' in self.proto.options)
        self.assertEqual(str(self.proto), proto_dump)
        # empty proto
        opt.clear(to_default=False)
        self.proto.Clear()
        opt.load_proto(self.proto)
        self.assertIsNone(opt.value)
        # bad proto value
        self.proto.options['option_name'].as_string = 'BAD VALUE'
        with self.assertRaises(ValueError) as cm:
            opt.load_proto(self.proto)
        self.assertEqual(cm.exception.args, ("could not convert string to float: 'BAD VALUE'",))
        self.proto.options['option_name'].as_bytes = b'BAD VALUE'
        with self.assertRaises(TypeError) as cm:
            opt.load_proto(self.proto)
        self.assertEqual(cm.exception.args, ('Wrong value type: bytes',))
        self.proto.Clear()
        opt.clear(to_default=False)
        opt.save_proto(self.proto)
        self.assertFalse('option_name' in self.proto.options)
    def test_get_config(self):
        opt = config.FloatOption('option_name', 'description', default=self.DEFAULT_OPT_VAL)
        lines = """; option_name
; -----------
;
; data type: float
;
; [optional] description
;
;option_name = 3000.0
"""
        self.assertEqual(opt.get_config(), lines)
        lines = """; option_name
; -----------
;
; data type: float
;
; [optional] description
;
option_name = 500.0
"""
        opt.set_value(500.0)
        self.assertEqual(opt.get_config(), lines)
        lines = """; option_name
; -----------
;
; data type: float
;
; [optional] description
;
option_name = <UNDEFINED>
"""
        opt.set_value(None)
        self.assertEqual(opt.get_config(), lines)

class TestDecimalOption(BaseConfigTest):
    "Unit tests for firebird.base.config.DecimalOption"
    PRESENT_VAL = Decimal('500.0')
    DEFAULT_VAL = Decimal('10.5')
    DEFAULT_OPT_VAL = Decimal('3000.0')
    NEW_VAL = Decimal('0.0')
    def setUp(self):
        super().setUp()
        self.setConf("""[%(DEFAULT)s]
option_name = 10.5
[%(PRESENT)s]
option_name = 500
[%(ABSENT)s]
[%(BAD)s]
option_name = bad_value
""")
    def test_simple(self):
        opt = config.DecimalOption('option_name', 'description')
        self.assertEqual(opt.name, 'option_name')
        self.assertEqual(opt.datatype, Decimal)
        self.assertEqual(opt.description, 'description')
        self.assertFalse(opt.required)
        self.assertIsNone(opt.default)
        self.assertIsNone(opt.value)
        opt.validate()
        opt.load_config(self.conf, PRESENT_S)
        self.assertEqual(opt.value, self.PRESENT_VAL)
        self.assertEqual(opt.get_as_str(), '500')
        self.assertIsInstance(opt.value, opt.datatype)
        opt.clear()
        self.assertIsNone(opt.value)
        opt.load_config(self.conf, DEFAULT_S)
        self.assertEqual(opt.value, self.DEFAULT_VAL)
        self.assertIsInstance(opt.value, opt.datatype)
        opt.set_value(None)
        self.assertIsNone(opt.value)
        opt.load_config(self.conf, ABSENT_S)
        self.assertEqual(opt.value, self.DEFAULT_VAL)
        self.assertIsInstance(opt.value, opt.datatype)
        opt.set_value(self.NEW_VAL)
        self.assertEqual(opt.value, self.NEW_VAL)
        self.assertIsInstance(opt.value, opt.datatype)
    def test_required(self):
        opt = config.DecimalOption('option_name', 'description', required=True)
        self.assertEqual(opt.name, 'option_name')
        self.assertEqual(opt.datatype, Decimal)
        self.assertEqual(opt.description, 'description')
        self.assertTrue(opt.required)
        self.assertIsNone(opt.default)
        self.assertIsNone(opt.value)
        with self.assertRaises(Error) as cm:
            opt.validate()
        self.assertEqual(cm.exception.args, ("Missing value for required option 'option_name'",))
        opt.load_config(self.conf, PRESENT_S)
        self.assertEqual(opt.value, self.PRESENT_VAL)
        opt.validate()
        opt.clear()
        self.assertIsNone(opt.value)
        opt.load_config(self.conf, DEFAULT_S)
        self.assertEqual(opt.value, self.DEFAULT_VAL)
        with self.assertRaises(ValueError) as cm:
            opt.set_value(None)
        self.assertEqual(cm.exception.args, ("Value is required for option 'option_name'.",))
        opt.load_config(self.conf, ABSENT_S)
        self.assertEqual(opt.value, self.DEFAULT_VAL)
        opt.set_value(self.NEW_VAL)
        self.assertEqual(opt.value, self.NEW_VAL)
    def test_bad_value(self):
        opt = config.DecimalOption('option_name', 'description')
        with self.assertRaises(ValueError) as cm:
            opt.load_config(self.conf, BAD_S)
        self.assertEqual(cm.exception.args, ("[<class 'decimal.ConversionSyntax'>]",))
        with self.assertRaises(TypeError) as cm:
            opt.set_value(10.0)
        self.assertEqual(cm.exception.args, ("Option 'option_name' value must be a 'Decimal', not 'float'",))
    def test_default(self):
        opt = config.DecimalOption('option_name', 'description', default=self.DEFAULT_OPT_VAL)
        self.assertEqual(opt.name, 'option_name')
        self.assertEqual(opt.datatype, Decimal)
        self.assertEqual(opt.description, 'description')
        self.assertFalse(opt.required)
        self.assertEqual(opt.default, self.DEFAULT_OPT_VAL)
        self.assertIsInstance(opt.value, opt.datatype)
        self.assertEqual(opt.value, self.DEFAULT_OPT_VAL)
        self.assertIsInstance(opt.value, opt.datatype)
        opt.validate()
        opt.load_config(self.conf, PRESENT_S)
        self.assertEqual(opt.value, self.PRESENT_VAL)
        opt.clear()
        self.assertEqual(opt.value, opt.default)
        opt.load_config(self.conf, DEFAULT_S)
        self.assertEqual(opt.value, self.DEFAULT_VAL)
        opt.set_value(None)
        self.assertIsNone(opt.value)
        opt.load_config(self.conf, ABSENT_S)
        self.assertEqual(opt.value, self.DEFAULT_VAL)
        opt.set_value(self.NEW_VAL)
        self.assertEqual(opt.value, self.NEW_VAL)
    def test_proto(self):
        opt = config.DecimalOption('option_name', 'description', default=self.DEFAULT_OPT_VAL)
        proto_value = Decimal('800000.0')
        opt.set_value(proto_value)
        self.proto.options['option_name'].as_string = str(proto_value)
        proto_dump = str(self.proto)
        opt.load_proto(self.proto)
        self.assertEqual(opt.value, proto_value)
        self.assertIsInstance(opt.value, opt.datatype)
        self.proto.Clear()
        self.assertFalse('option_name' in self.proto.options)
        opt.save_proto(self.proto)
        self.assertTrue('option_name' in self.proto.options)
        self.assertEqual(str(self.proto), proto_dump)
        #
        self.proto.options['option_name'].as_uint64 = 10
        opt.load_proto(self.proto)
        self.assertEqual(opt.value, Decimal('10'))
        # empty proto
        opt.clear(to_default=False)
        self.proto.Clear()
        opt.load_proto(self.proto)
        self.assertIsNone(opt.value)
        # bad proto value
        self.proto.options['option_name'].as_string = 'BAD VALUE'
        with self.assertRaises(ValueError) as cm:
            opt.load_proto(self.proto)
        self.assertEqual(cm.exception.args, ("[<class 'decimal.ConversionSyntax'>]",))
        self.proto.options['option_name'].as_float = 10.01
        with self.assertRaises(TypeError) as cm:
            opt.load_proto(self.proto)
        self.assertEqual(cm.exception.args, ('Wrong value type: float',))
        self.proto.Clear()
        opt.clear(to_default=False)
        opt.save_proto(self.proto)
        self.assertFalse('option_name' in self.proto.options)
    def test_get_config(self):
        opt = config.DecimalOption('option_name', 'description', default=self.DEFAULT_OPT_VAL)
        lines = """; option_name
; -----------
;
; data type: Decimal
;
; [optional] description
;
;option_name = 3000.0
"""
        self.assertEqual(opt.get_config(), lines)
        lines = """; option_name
; -----------
;
; data type: Decimal
;
; [optional] description
;
option_name = 500.120
"""
        opt.set_as_str('500.120')
        self.assertEqual(opt.get_config(), lines)
        lines = """; option_name
; -----------
;
; data type: Decimal
;
; [optional] description
;
option_name = <UNDEFINED>
"""
        opt.set_value(None)
        self.assertEqual(opt.get_config(), lines)

class TestBoolOption(BaseConfigTest):
    "Unit tests for firebird.base.config.BoolOption"
    YES = True
    NO = False
    PRESENT_VAL = YES
    DEFAULT_VAL = NO
    DEFAULT_OPT_VAL = NO
    NEW_VAL = YES
    def setUp(self):
        super().setUp()
        self.setConf("""[%(DEFAULT)s]
option_name = no
[%(PRESENT)s]
option_name = yes
[%(ABSENT)s]
[%(BAD)s]
option_name = bad_value
""")
    def test_simple(self):
        opt = config.BoolOption('option_name', 'description')
        self.assertEqual(opt.name, 'option_name')
        self.assertEqual(opt.datatype, bool)
        self.assertEqual(opt.description, 'description')
        self.assertFalse(opt.required)
        self.assertIsNone(opt.default)
        self.assertIsNone(opt.value)
        opt.validate()
        opt.load_config(self.conf, PRESENT_S)
        self.assertEqual(opt.value, self.PRESENT_VAL)
        self.assertEqual(opt.get_as_str(), 'True')
        self.assertIsInstance(opt.value, opt.datatype)
        opt.clear()
        self.assertIsNone(opt.value)
        opt.load_config(self.conf, DEFAULT_S)
        self.assertEqual(opt.value, self.DEFAULT_VAL)
        self.assertIsInstance(opt.value, opt.datatype)
        opt.set_value(None)
        self.assertIsNone(opt.value)
        opt.load_config(self.conf, ABSENT_S)
        self.assertEqual(opt.value, self.DEFAULT_VAL)
        self.assertIsInstance(opt.value, opt.datatype)
        opt.set_value(self.NEW_VAL)
        self.assertEqual(opt.value, self.NEW_VAL)
        self.assertIsInstance(opt.value, opt.datatype)
    def test_required(self):
        opt = config.BoolOption('option_name', 'description', required=True)
        self.assertEqual(opt.name, 'option_name')
        self.assertEqual(opt.datatype, bool)
        self.assertEqual(opt.description, 'description')
        self.assertTrue(opt.required)
        self.assertIsNone(opt.default)
        self.assertIsNone(opt.value)
        with self.assertRaises(Error) as cm:
            opt.validate()
        self.assertEqual(cm.exception.args, ("Missing value for required option 'option_name'",))
        opt.load_config(self.conf, PRESENT_S)
        self.assertEqual(opt.value, self.PRESENT_VAL)
        opt.validate()
        opt.clear()
        self.assertIsNone(opt.value)
        opt.load_config(self.conf, DEFAULT_S)
        self.assertEqual(opt.value, self.DEFAULT_VAL)
        with self.assertRaises(ValueError) as cm:
            opt.set_value(None)
        self.assertEqual(cm.exception.args, ("Value is required for option 'option_name'.",))
        opt.load_config(self.conf, ABSENT_S)
        self.assertEqual(opt.value, self.DEFAULT_VAL)
        opt.set_value(self.NEW_VAL)
        self.assertEqual(opt.value, self.NEW_VAL)
    def test_bad_value(self):
        opt = config.BoolOption('option_name', 'description')
        with self.assertRaises(ValueError) as cm:
            opt.load_config(self.conf, BAD_S)
        self.assertEqual(cm.exception.args, ('Value is not a valid bool string constant',))
        with self.assertRaises(TypeError) as cm:
            opt.set_value(10.0)
        self.assertEqual(cm.exception.args, ("Option 'option_name' value must be a 'bool', not 'float'",))
        with self.assertRaises(ValueError) as cm:
            opt.set_as_str('nope')
        self.assertEqual(cm.exception.args, ('Value is not a valid bool string constant',))
    def test_default(self):
        opt = config.BoolOption('option_name', 'description', default=self.DEFAULT_OPT_VAL)
        self.assertEqual(opt.name, 'option_name')
        self.assertEqual(opt.datatype, bool)
        self.assertEqual(opt.description, 'description')
        self.assertFalse(opt.required)
        self.assertEqual(opt.default, self.DEFAULT_OPT_VAL)
        self.assertIsInstance(opt.default, opt.datatype)
        self.assertEqual(opt.value, self.DEFAULT_OPT_VAL)
        self.assertIsInstance(opt.value, opt.datatype)
        opt.validate()
        opt.load_config(self.conf, PRESENT_S)
        self.assertEqual(opt.value, self.PRESENT_VAL)
        opt.clear()
        self.assertEqual(opt.value, opt.default)
        opt.load_config(self.conf, DEFAULT_S)
        self.assertEqual(opt.value, self.DEFAULT_VAL)
        opt.set_value(None)
        self.assertIsNone(opt.value)
        opt.load_config(self.conf, ABSENT_S)
        self.assertEqual(opt.value, self.DEFAULT_VAL)
        opt.set_value(self.NEW_VAL)
        self.assertEqual(opt.value, self.NEW_VAL)
    def test_proto(self):
        opt = config.BoolOption('option_name', 'description', default=self.DEFAULT_OPT_VAL)
        proto_value = self.YES
        opt.set_value(proto_value)
        self.proto.options['option_name'].as_bool = proto_value
        proto_dump = str(self.proto)
        opt.load_proto(self.proto)
        self.assertEqual(opt.value, proto_value)
        self.assertIsInstance(opt.value, opt.datatype)
        self.proto.Clear()
        self.assertFalse('option_name' in self.proto.options)
        opt.save_proto(self.proto)
        self.assertTrue('option_name' in self.proto.options)
        self.assertEqual(str(self.proto), proto_dump)
        # empty proto
        opt.clear(to_default=False)
        self.proto.Clear()
        opt.load_proto(self.proto)
        self.assertIsNone(opt.value)
        # bad proto value
        self.proto.options['option_name'].as_string = 'BAD VALUE'
        with self.assertRaises(ValueError) as cm:
            opt.load_proto(self.proto)
        self.assertEqual(cm.exception.args, ('Value is not a valid bool string constant',))
        self.proto.Clear()
        opt.clear(to_default=False)
        opt.save_proto(self.proto)
        self.assertFalse('option_name' in self.proto.options)
    def test_get_config(self):
        opt = config.BoolOption('option_name', 'description', default=self.DEFAULT_OPT_VAL)
        lines = """; option_name
; -----------
;
; data type: bool
;
; [optional] description
;
;option_name = no
"""
        self.assertEqual(opt.get_config(), lines)
        lines = """; option_name
; -----------
;
; data type: bool
;
; [optional] description
;
option_name = yes
"""
        opt.set_value(True)
        self.assertEqual(opt.get_config(), lines)
        lines = """; option_name
; -----------
;
; data type: bool
;
; [optional] description
;
option_name = <UNDEFINED>
"""
        opt.set_value(None)
        self.assertEqual(opt.get_config(), lines)

class TestEnumOption(BaseConfigTest):
    "Unit tests for firebird.base.config.EnumOption"
    DEFAULT_VAL = SimpleEnum.UNKNOWN
    PRESENT_VAL = SimpleEnum.RUNNING
    DEFAULT_OPT_VAL = SimpleEnum.READY
    NEW_VAL = SimpleEnum.STOPPED
    def setUp(self):
        super().setUp()
        self.setConf("""[%(DEFAULT)s]
; Enum is defined by name
option_name = UNKNOWN
[%(PRESENT)s]
; case does not matter
option_name = RuNnInG
[%(ABSENT)s]
[%(BAD)s]
option_name = bad_value
[illegal]
option_name = 1000
""")
    def test_simple(self):
        opt = config.EnumOption('option_name', SimpleEnum, 'description')
        self.assertEqual(opt.name, 'option_name')
        self.assertEqual(opt.datatype, SimpleEnum)
        self.assertEqual(opt.description, 'description')
        self.assertFalse(opt.required)
        self.assertIsNone(opt.default)
        self.assertIsNone(opt.value)
        self.assertSequenceEqual(opt.allowed, SimpleEnum)
        opt.validate()
        opt.load_config(self.conf, PRESENT_S)
        self.assertEqual(opt.value, self.PRESENT_VAL)
        self.assertEqual(opt.get_as_str(), 'RUNNING')
        self.assertIsInstance(opt.value, opt.datatype)
        opt.clear()
        self.assertIsNone(opt.value)
        opt.load_config(self.conf, DEFAULT_S)
        self.assertEqual(opt.value, self.DEFAULT_VAL)
        self.assertIsInstance(opt.value, opt.datatype)
        opt.set_value(None)
        self.assertIsNone(opt.value)
        opt.load_config(self.conf, ABSENT_S)
        self.assertEqual(opt.value, self.DEFAULT_VAL)
        self.assertIsInstance(opt.value, opt.datatype)
        opt.set_value(self.NEW_VAL)
        self.assertEqual(opt.value, self.NEW_VAL)
        self.assertIsInstance(opt.value, opt.datatype)
    def test_required(self):
        opt = config.EnumOption('option_name', SimpleEnum, 'description', required=True)
        self.assertEqual(opt.name, 'option_name')
        self.assertEqual(opt.datatype, SimpleEnum)
        self.assertEqual(opt.description, 'description')
        self.assertTrue(opt.required)
        self.assertIsNone(opt.default)
        self.assertIsNone(opt.value)
        with self.assertRaises(Error) as cm:
            opt.validate()
        self.assertEqual(cm.exception.args, ("Missing value for required option 'option_name'",))
        opt.load_config(self.conf, PRESENT_S)
        self.assertEqual(opt.value, self.PRESENT_VAL)
        opt.validate()
        opt.clear()
        self.assertIsNone(opt.value)
        opt.load_config(self.conf, DEFAULT_S)
        self.assertEqual(opt.value, self.DEFAULT_VAL)
        with self.assertRaises(ValueError) as cm:
            opt.set_value(None)
        self.assertEqual(cm.exception.args, ("Value is required for option 'option_name'.",))
        opt.load_config(self.conf, ABSENT_S)
        self.assertEqual(opt.value, self.DEFAULT_VAL)
        opt.set_value(self.NEW_VAL)
        self.assertEqual(opt.value, self.NEW_VAL)
    def test_bad_value(self):
        opt = config.EnumOption('option_name', SimpleEnum, 'description')
        with self.assertRaises(ValueError) as cm:
            opt.load_config(self.conf, BAD_S)
        self.assertEqual(cm.exception.args, ("Illegal value 'bad_value' for enum type 'SimpleEnum'",))
        with self.assertRaises(ValueError) as cm:
            opt.load_config(self.conf, 'illegal')
        self.assertEqual(cm.exception.args, ("Illegal value '1000' for enum type 'SimpleEnum'",))
        with self.assertRaises(TypeError) as cm:
            opt.set_value(10.0)
        self.assertEqual(cm.exception.args, ("Option 'option_name' value must be a 'SimpleEnum', not 'float'",))
    def test_allowed_values(self):
        opt = config.EnumOption('option_name', SimpleEnum, 'description',
                                allowed=[SimpleEnum.UNKNOWN, SimpleEnum.RUNNING])
        self.assertEqual(opt.name, 'option_name')
        self.assertEqual(opt.datatype, SimpleEnum)
        self.assertEqual(opt.description, 'description')
        self.assertFalse(opt.required)
        self.assertIsNone(opt.default)
        self.assertIsNone(opt.value)
        opt.load_config(self.conf, PRESENT_S)
        self.assertEqual(opt.value, self.PRESENT_VAL)
        opt.validate()
        opt.clear()
        self.assertIsNone(opt.value)
        opt.load_config(self.conf, DEFAULT_S)
        self.assertEqual(opt.value, self.DEFAULT_VAL)
        opt.set_value(None)
        self.assertIsNone(opt.value)
        opt.load_config(self.conf, ABSENT_S)
        self.assertEqual(opt.value, self.DEFAULT_VAL)
        with self.assertRaises(ValueError) as cm:
            opt.set_value(self.NEW_VAL)
        self.assertEqual(cm.exception.args, ("Value '4' not allowed",))
    def test_default(self):
        opt = config.EnumOption('option_name', SimpleEnum, 'description', default=self.DEFAULT_OPT_VAL)
        self.assertEqual(opt.name, 'option_name')
        self.assertEqual(opt.datatype, SimpleEnum)
        self.assertEqual(opt.description, 'description')
        self.assertFalse(opt.required)
        self.assertEqual(opt.default, self.DEFAULT_OPT_VAL)
        self.assertIsInstance(opt.default, opt.datatype)
        self.assertEqual(opt.value, self.DEFAULT_OPT_VAL)
        self.assertIsInstance(opt.value, opt.datatype)
        opt.validate()
        opt.load_config(self.conf, PRESENT_S)
        self.assertEqual(opt.value, self.PRESENT_VAL)
        opt.clear()
        self.assertEqual(opt.value, opt.default)
        opt.load_config(self.conf, DEFAULT_S)
        self.assertEqual(opt.value, self.DEFAULT_VAL)
        opt.set_value(None)
        self.assertIsNone(opt.value)
        opt.load_config(self.conf, ABSENT_S)
        self.assertEqual(opt.value, self.DEFAULT_VAL)
        opt.set_value(self.NEW_VAL)
        self.assertEqual(opt.value, self.NEW_VAL)
    def test_proto(self):
        opt = config.EnumOption('option_name', SimpleEnum, 'description', default=self.DEFAULT_OPT_VAL)
        proto_value = SimpleEnum.READY
        opt.set_value(proto_value)
        self.proto.options['option_name'].as_string = proto_value.name
        proto_dump = str(self.proto)
        opt.load_proto(self.proto)
        self.assertEqual(opt.value, proto_value)
        self.assertIsInstance(opt.value, opt.datatype)
        opt.set_value(None)
        self.proto.options['option_name'].as_string = 'READY'
        opt.load_proto(self.proto)
        self.assertEqual(opt.value, proto_value)
        self.proto.Clear()
        self.assertFalse('option_name' in self.proto.options)
        opt.save_proto(self.proto)
        self.assertTrue('option_name' in self.proto.options)
        self.assertEqual(str(self.proto), proto_dump)
        # empty proto
        opt.clear(to_default=False)
        self.proto.Clear()
        opt.load_proto(self.proto)
        self.assertIsNone(opt.value)
        # bad proto value
        self.proto.options['option_name'].as_uint32 = 1000
        with self.assertRaises(TypeError) as cm:
            opt.load_proto(self.proto)
        self.assertEqual(cm.exception.args, ('Wrong value type: uint32',))
        self.proto.Clear()
        opt.clear(to_default=False)
        opt.save_proto(self.proto)
        self.assertFalse('option_name' in self.proto.options)
    def test_get_config(self):
        opt = config.EnumOption('option_name', SimpleEnum, 'description', default=self.DEFAULT_OPT_VAL)
        lines = """; option_name
; -----------
;
; data type: SimpleEnum
; values: unknown, ready, running, waiting, suspended, finished, aborted
;
; [optional] description
;
;option_name = ready
"""
        self.assertEqual(opt.get_config(), lines)
        lines = """; option_name
; -----------
;
; data type: SimpleEnum
; values: unknown, ready, running, waiting, suspended, finished, aborted
;
; [optional] description
;
option_name = suspended
"""
        # Although NEW_VAL is STOPPED, the printout is SUSPENDED because STOPPED is an alias
        opt.set_value(self.NEW_VAL)
        self.assertEqual(opt.get_config(), lines)
        lines = """; option_name
; -----------
;
; data type: SimpleEnum
; values: unknown, ready, running, waiting, suspended, finished, aborted
;
; [optional] description
;
option_name = <UNDEFINED>
"""
        opt.set_value(None)
        self.assertEqual(opt.get_config(), lines)
        # Reduced option list
        opt = config.EnumOption('option_name', SimpleEnum, 'description',
                                allowed=[SimpleEnum.UNKNOWN, SimpleEnum.RUNNING])
        lines = """; option_name
; -----------
;
; data type: SimpleEnum
; values: unknown, running
;
; [optional] description
;
;option_name = <UNDEFINED>
"""
        self.assertEqual(opt.get_config(), lines)

class TestFlagOption(BaseConfigTest):
    "Unit tests for firebird.base.config.FlagOption"
    DEFAULT_VAL = SimpleIntFlag.ONE
    PRESENT_VAL = SimpleIntFlag.TWO | SimpleIntFlag.THREE
    DEFAULT_OPT_VAL = SimpleIntFlag.THREE | SimpleIntFlag.FOUR
    NEW_VAL = SimpleIntFlag.FIVE
    def setUp(self):
        super().setUp()
        self.setConf("""[%(DEFAULT)s]
; Flag is defined by name(s)
option_name = ONE
[%(PRESENT)s]
; case does not matter
option_name = TwO, tHrEe
[%(ABSENT)s]
[%(BAD)s]
option_name = bad_value
[illegal]
option_name = 1000
""")
    def test_simple(self):
        opt = config.FlagOption('option_name', SimpleIntFlag, 'description')
        self.assertEqual(opt.name, 'option_name')
        self.assertEqual(opt.datatype, SimpleIntFlag)
        self.assertEqual(opt.description, 'description')
        self.assertFalse(opt.required)
        self.assertIsNone(opt.default)
        self.assertIsNone(opt.value)
        self.assertSequenceEqual(opt.allowed, SimpleIntFlag)
        opt.validate()
        opt.load_config(self.conf, PRESENT_S)
        self.assertEqual(opt.value, self.PRESENT_VAL)
        self.assertEqual(opt.get_as_str(), 'THREE | TWO')
        self.assertIsInstance(opt.value, opt.datatype)
        opt.clear()
        self.assertIsNone(opt.value)
        opt.load_config(self.conf, DEFAULT_S)
        self.assertEqual(opt.value, self.DEFAULT_VAL)
        self.assertIsInstance(opt.value, opt.datatype)
        opt.set_value(None)
        self.assertIsNone(opt.value)
        opt.load_config(self.conf, ABSENT_S)
        self.assertEqual(opt.value, self.DEFAULT_VAL)
        self.assertIsInstance(opt.value, opt.datatype)
        opt.set_value(self.NEW_VAL)
        self.assertEqual(opt.value, self.NEW_VAL)
        self.assertIsInstance(opt.value, opt.datatype)
    def test_required(self):
        opt = config.FlagOption('option_name', SimpleIntFlag, 'description', required=True)
        self.assertEqual(opt.name, 'option_name')
        self.assertEqual(opt.datatype, SimpleIntFlag)
        self.assertEqual(opt.description, 'description')
        self.assertTrue(opt.required)
        self.assertIsNone(opt.default)
        self.assertIsNone(opt.value)
        with self.assertRaises(Error) as cm:
            opt.validate()
        self.assertEqual(cm.exception.args, ("Missing value for required option 'option_name'",))
        opt.load_config(self.conf, PRESENT_S)
        self.assertEqual(opt.value, self.PRESENT_VAL)
        opt.validate()
        opt.clear()
        self.assertIsNone(opt.value)
        opt.load_config(self.conf, DEFAULT_S)
        self.assertEqual(opt.value, self.DEFAULT_VAL)
        with self.assertRaises(ValueError) as cm:
            opt.set_value(None)
        self.assertEqual(cm.exception.args, ("Value is required for option 'option_name'.",))
        opt.load_config(self.conf, ABSENT_S)
        self.assertEqual(opt.value, self.DEFAULT_VAL)
        opt.set_value(self.NEW_VAL)
        self.assertEqual(opt.value, self.NEW_VAL)
    def test_bad_value(self):
        opt = config.FlagOption('option_name', SimpleIntFlag, 'description')
        with self.assertRaises(ValueError) as cm:
            opt.load_config(self.conf, BAD_S)
        self.assertEqual(cm.exception.args, ("Illegal value 'bad_value' for flag option 'option_name'",))
        with self.assertRaises(ValueError) as cm:
            opt.load_config(self.conf, 'illegal')
        self.assertEqual(cm.exception.args, ("Illegal value '1000' for flag option 'option_name'",))
        with self.assertRaises(TypeError) as cm:
            opt.set_value(SimpleFlag.ONE)
        self.assertEqual(cm.exception.args, ("Option 'option_name' value must be a 'SimpleIntFlag', not 'SimpleFlag'",))
        with self.assertRaises(ValueError) as cm:
            opt.set_as_str('one, two ,three, illegal,four')
        self.assertEqual(cm.exception.args, ("Illegal value 'illegal' for flag option 'option_name'",))
    def test_allowed_values(self):
        opt = config.FlagOption('option_name', SimpleIntFlag, 'description',
                                allowed=[SimpleIntFlag.ONE, SimpleIntFlag.TWO])
        self.assertEqual(opt.name, 'option_name')
        self.assertEqual(opt.datatype, SimpleIntFlag)
        self.assertEqual(opt.description, 'description')
        self.assertFalse(opt.required)
        self.assertIsNone(opt.default)
        self.assertIsNone(opt.value)
        with self.assertRaises(ValueError) as cm:
            opt.load_config(self.conf, PRESENT_S)
        self.assertEqual(cm.exception.args, ("Illegal value 'three' for flag option 'option_name'",))
        self.assertIsNone(opt.value)
        opt.validate()
        opt.clear()
        self.assertIsNone(opt.value)
        opt.load_config(self.conf, DEFAULT_S)
        self.assertEqual(opt.value, self.DEFAULT_VAL)
        opt.set_value(None)
        self.assertIsNone(opt.value)
        opt.load_config(self.conf, ABSENT_S)
        self.assertEqual(opt.value, self.DEFAULT_VAL)
        with self.assertRaises(ValueError) as cm:
            opt.set_value(self.NEW_VAL)
        self.assertEqual(cm.exception.args, ("Illegal value 'SimpleIntFlag.FIVE' for flag option 'option_name'",))
    def test_default(self):
        opt = config.FlagOption('option_name', SimpleIntFlag, 'description', default=self.DEFAULT_OPT_VAL)
        self.assertEqual(opt.name, 'option_name')
        self.assertEqual(opt.datatype, SimpleIntFlag)
        self.assertEqual(opt.description, 'description')
        self.assertFalse(opt.required)
        self.assertEqual(opt.default, self.DEFAULT_OPT_VAL)
        self.assertIsInstance(opt.default, opt.datatype)
        self.assertEqual(opt.value, self.DEFAULT_OPT_VAL)
        self.assertIsInstance(opt.value, opt.datatype)
        opt.validate()
        opt.load_config(self.conf, PRESENT_S)
        self.assertEqual(opt.value, self.PRESENT_VAL)
        opt.clear()
        self.assertEqual(opt.value, opt.default)
        opt.load_config(self.conf, DEFAULT_S)
        self.assertEqual(opt.value, self.DEFAULT_VAL)
        opt.set_value(None)
        self.assertIsNone(opt.value)
        opt.load_config(self.conf, ABSENT_S)
        self.assertEqual(opt.value, self.DEFAULT_VAL)
        opt.set_value(self.NEW_VAL)
        self.assertEqual(opt.value, self.NEW_VAL)
    def test_proto(self):
        opt = config.FlagOption('option_name', SimpleIntFlag, 'description', default=self.DEFAULT_OPT_VAL)
        proto_value = SimpleIntFlag.FIVE
        opt.set_value(proto_value)
        self.proto.options['option_name'].as_uint64 = proto_value.value
        proto_dump = str(self.proto)
        opt.load_proto(self.proto)
        self.assertEqual(opt.value, proto_value)
        self.assertIsInstance(opt.value, opt.datatype)
        opt.set_value(None)
        self.proto.options['option_name'].as_string = 'five'
        opt.load_proto(self.proto)
        self.assertEqual(opt.value, proto_value)
        self.proto.Clear()
        self.assertFalse('option_name' in self.proto.options)
        opt.save_proto(self.proto)
        self.assertTrue('option_name' in self.proto.options)
        self.assertEqual(str(self.proto), proto_dump)
        # empty proto
        opt.clear(to_default=False)
        self.proto.Clear()
        opt.load_proto(self.proto)
        self.assertIsNone(opt.value)
        # bad proto value
        self.proto.options['option_name'].as_uint32 = 1000
        with self.assertRaises(TypeError) as cm:
            opt.load_proto(self.proto)
        self.assertEqual(cm.exception.args, ('Wrong value type: uint32',))
        self.proto.Clear()
        self.proto.options['option_name'].as_uint64 = 1000
        with self.assertRaises(ValueError) as cm:
            opt.load_proto(self.proto)
        self.assertEqual(cm.exception.args, ("Illegal value 'SimpleIntFlag.512|256|128|64|32|FOUR' for flag option 'option_name'",))
        self.proto.Clear()
        opt.clear(to_default=False)
        opt.save_proto(self.proto)
        self.assertFalse('option_name' in self.proto.options)
    def test_get_config(self):
        opt = config.FlagOption('option_name', SimpleIntFlag, 'description', default=self.DEFAULT_OPT_VAL)
        lines = """; option_name
; -----------
;
; data type: SimpleIntFlag
; values: one, two, three, four, five
;
; [optional] description
;
;option_name = four | three
"""
        self.assertEqual(opt.get_config(), lines)
        lines = """; option_name
; -----------
;
; data type: SimpleIntFlag
; values: one, two, three, four, five
;
; [optional] description
;
option_name = five
"""
        opt.set_value(self.NEW_VAL)
        self.assertEqual(opt.get_config(), lines)
        lines = """; option_name
; -----------
;
; data type: SimpleIntFlag
; values: one, two, three, four, five
;
; [optional] description
;
option_name = <UNDEFINED>
"""
        opt.set_value(None)
        self.assertEqual(opt.get_config(), lines)
        # Reduced flag list
        opt = config.EnumOption('option_name', SimpleIntFlag, 'description',
                                allowed=[SimpleIntFlag.ONE, SimpleIntFlag.FOUR])
        lines = """; option_name
; -----------
;
; data type: SimpleIntFlag
; values: one, four
;
; [optional] description
;
;option_name = <UNDEFINED>
"""
        self.assertEqual(opt.get_config(), lines)

class TestUUIDOption(BaseConfigTest):
    "Unit tests for firebird.base.config.UUIDOption"
    PRESENT_VAL = UUID('fbcdd0ac-de0d-11e9-9b5b-5404a6a1fd6e')
    DEFAULT_VAL = UUID('e3a57070-de0d-11e9-9b5b-5404a6a1fd6e')
    DEFAULT_OPT_VAL = UUID('ede5cc42-de0d-11e9-9b5b-5404a6a1fd6e')
    NEW_VAL = UUID('92ef5c08-de0e-11e9-9b5b-5404a6a1fd6e')
    def setUp(self):
        super().setUp()
        self.setConf("""[%(DEFAULT)s]
option_name = e3a57070-de0d-11e9-9b5b-5404a6a1fd6e
[%(PRESENT)s]
; as hex
option_name = fbcdd0acde0d11e99b5b5404a6a1fd6e
[%(ABSENT)s]
[%(BAD)s]
option_name = BAD_UID
""")
    def test_simple(self):
        opt = config.UUIDOption('option_name', 'description')
        self.assertEqual(opt.name, 'option_name')
        self.assertEqual(opt.datatype, UUID)
        self.assertEqual(opt.description, 'description')
        self.assertFalse(opt.required)
        self.assertIsNone(opt.default)
        self.assertIsNone(opt.value)
        opt.validate()
        opt.load_config(self.conf, PRESENT_S)
        self.assertEqual(opt.value, self.PRESENT_VAL)
        self.assertEqual(opt.get_as_str(), 'fbcdd0acde0d11e99b5b5404a6a1fd6e')
        self.assertIsInstance(opt.value, opt.datatype)
        opt.clear()
        self.assertIsNone(opt.value)
        opt.load_config(self.conf, DEFAULT_S)
        self.assertEqual(opt.value, self.DEFAULT_VAL)
        self.assertIsInstance(opt.value, opt.datatype)
        opt.set_value(None)
        self.assertIsNone(opt.value)
        opt.load_config(self.conf, ABSENT_S)
        self.assertEqual(opt.value, self.DEFAULT_VAL)
        self.assertIsInstance(opt.value, opt.datatype)
        opt.set_value(self.NEW_VAL)
        self.assertEqual(opt.value, self.NEW_VAL)
        self.assertIsInstance(opt.value, opt.datatype)
    def test_required(self):
        opt = config.UUIDOption('option_name', 'description', required=True)
        self.assertEqual(opt.name, 'option_name')
        self.assertEqual(opt.datatype, UUID)
        self.assertEqual(opt.description, 'description')
        self.assertTrue(opt.required)
        self.assertIsNone(opt.default)
        self.assertIsNone(opt.value)
        with self.assertRaises(Error) as cm:
            opt.validate()
        self.assertEqual(cm.exception.args, ("Missing value for required option 'option_name'",))
        opt.load_config(self.conf, PRESENT_S)
        self.assertEqual(opt.value, self.PRESENT_VAL)
        opt.validate()
        opt.clear()
        self.assertIsNone(opt.value)
        opt.load_config(self.conf, DEFAULT_S)
        self.assertEqual(opt.value, self.DEFAULT_VAL)
        with self.assertRaises(ValueError) as cm:
            opt.set_value(None)
        self.assertEqual(cm.exception.args, ("Value is required for option 'option_name'.",))
        opt.load_config(self.conf, ABSENT_S)
        self.assertEqual(opt.value, self.DEFAULT_VAL)
        opt.set_value(self.NEW_VAL)
        self.assertEqual(opt.value, self.NEW_VAL)
    def test_bad_value(self):
        opt = config.UUIDOption('option_name', 'description')
        with self.assertRaises(ValueError) as cm:
            opt.load_config(self.conf, BAD_S)
        self.assertEqual(cm.exception.args, ('badly formed hexadecimal UUID string',))
        with self.assertRaises(TypeError) as cm:
            opt.set_value(10.0)
        self.assertEqual(cm.exception.args, ("Option 'option_name' value must be a 'UUID', not 'float'",))
    def test_default(self):
        opt = config.UUIDOption('option_name', 'description', default=self.DEFAULT_OPT_VAL)
        self.assertEqual(opt.name, 'option_name')
        self.assertEqual(opt.datatype, UUID)
        self.assertEqual(opt.description, 'description')
        self.assertFalse(opt.required)
        self.assertEqual(opt.default, self.DEFAULT_OPT_VAL)
        self.assertIsInstance(opt.default, opt.datatype)
        self.assertEqual(opt.value, self.DEFAULT_OPT_VAL)
        self.assertIsInstance(opt.value, opt.datatype)
        opt.validate()
        opt.load_config(self.conf, PRESENT_S)
        self.assertEqual(opt.value, self.PRESENT_VAL)
        opt.clear()
        self.assertEqual(opt.value, opt.default)
        opt.load_config(self.conf, DEFAULT_S)
        self.assertEqual(opt.value, self.DEFAULT_VAL)
        opt.set_value(None)
        self.assertIsNone(opt.value)
        opt.load_config(self.conf, ABSENT_S)
        self.assertEqual(opt.value, self.DEFAULT_VAL)
        opt.set_value(self.NEW_VAL)
        self.assertEqual(opt.value, self.NEW_VAL)
    def test_proto(self):
        opt = config.UUIDOption('option_name', 'description', default=self.DEFAULT_OPT_VAL)
        proto_value = UUID('bcd80916-de0e-11e9-9b5b-5404a6a1fd6e')
        opt.set_value(proto_value)
        # as_bytes (default)
        self.proto.options['option_name'].as_bytes = proto_value.bytes
        proto_dump = str(self.proto)
        opt.load_proto(self.proto)
        self.assertEqual(opt.value, proto_value)
        self.assertIsInstance(opt.value, opt.datatype)
        # as_string
        self.proto.Clear()
        self.proto.options['option_name'].as_string = proto_value.hex
        opt.load_proto(self.proto)
        self.assertEqual(opt.value, proto_value)
        self.assertIsInstance(opt.value, opt.datatype)
        #
        self.proto.Clear()
        self.assertFalse('option_name' in self.proto.options)
        opt.save_proto(self.proto)
        self.assertTrue('option_name' in self.proto.options)
        self.assertEqual(str(self.proto), proto_dump)
        # empty proto
        opt.clear(to_default=False)
        self.proto.Clear()
        opt.load_proto(self.proto)
        self.assertIsNone(opt.value)
        # bad proto value
        self.proto.options['option_name'].as_uint32 = 1000
        with self.assertRaises(TypeError) as cm:
            opt.load_proto(self.proto)
        self.assertEqual(cm.exception.args, ('Wrong value type: uint32',))
        self.proto.Clear()
        opt.clear(to_default=False)
        opt.save_proto(self.proto)
        self.assertFalse('option_name' in self.proto.options)
    def test_get_config(self):
        opt = config.UUIDOption('option_name', 'description', default=self.DEFAULT_OPT_VAL)
        lines = """; option_name
; -----------
;
; data type: UUID
;
; [optional] description
;
;option_name = ede5cc42-de0d-11e9-9b5b-5404a6a1fd6e
"""
        self.assertEqual(opt.get_config(), lines)
        lines = """; option_name
; -----------
;
; data type: UUID
;
; [optional] description
;
option_name = 92ef5c08-de0e-11e9-9b5b-5404a6a1fd6e
"""
        opt.set_value(self.NEW_VAL)
        self.assertEqual(opt.get_config(), lines)
        lines = """; option_name
; -----------
;
; data type: UUID
;
; [optional] description
;
option_name = <UNDEFINED>
"""
        opt.set_value(None)
        self.assertEqual(opt.get_config(), lines)

class TestMIMEOption(BaseConfigTest):
    "Unit tests for firebird.base.config.MIMEOption"
    PRESENT_VAL = MIME('text/plain;charset=utf-8')
    PRESENT_TYPE = 'text/plain'
    PRESENT_PARS = {'charset': 'utf-8'}
    DEFAULT_VAL = MIME('application/octet-stream')
    DEFAULT_TYPE = 'application/octet-stream'
    DEFAULT_PARS = {}
    DEFAULT_OPT_VAL = MIME('text/plain;charset=win1250')
    DEFAULT_OPT_TYPE = 'text/plain'
    DEFAULT_OPT_PARS = {'charset': 'win1250'}
    NEW_VAL = MIME('application/x.fb.proto;type=firebird.butler.fbsd.ErrorDescription')
    NEW_TYPE = 'application/x.fb.proto'
    NEW_PARS = {'type': 'firebird.butler.fbsd.ErrorDescription'}
    def setUp(self):
        super().setUp()
        self.setConf("""[%(DEFAULT)s]
option_name = application/octet-stream
[%(PRESENT)s]
option_name = text/plain;charset=utf-8
[%(ABSENT)s]
[%(BAD)s]
option_name = wrong mime specification
[unsupported_mime_type]
option_name = model/vml
[bad_mime_parameters]
option_name = text/plain;charset/utf-8
""")
    def test_simple(self):
        opt: config.MIMEOption = config.MIMEOption('option_name', 'description')
        self.assertEqual(opt.name, 'option_name')
        self.assertEqual(opt.datatype, MIME)
        self.assertEqual(opt.description, 'description')
        self.assertFalse(opt.required)
        self.assertIsNone(opt.default)
        self.assertIsNone(opt.value)
        opt.validate()
        opt.load_config(self.conf, PRESENT_S)
        self.assertEqual(opt.value, self.PRESENT_VAL)
        self.assertEqual(opt.value, 'text/plain;charset=utf-8')
        self.assertEqual(opt.get_as_str(), self.PRESENT_VAL)
        self.assertIsInstance(opt.value, opt.datatype)
        self.assertEqual(opt.value.mime_type, self.PRESENT_TYPE)
        self.assertDictEqual(opt.value.params, self.PRESENT_PARS)
        self.assertEqual(opt.value.params.get('charset'), 'utf-8')
        opt.clear()
        self.assertIsNone(opt.value)
        opt.load_config(self.conf, DEFAULT_S)
        self.assertEqual(opt.value, self.DEFAULT_VAL)
        self.assertIsInstance(opt.value, opt.datatype)
        self.assertEqual(opt.value.mime_type, self.DEFAULT_TYPE)
        self.assertDictEqual(opt.value.params, self.DEFAULT_PARS)
        opt.set_value(None)
        self.assertIsNone(opt.value)
        opt.load_config(self.conf, ABSENT_S)
        self.assertEqual(opt.value, self.DEFAULT_VAL)
        self.assertIsInstance(opt.value, opt.datatype)
        self.assertEqual(opt.value.mime_type, self.DEFAULT_TYPE)
        self.assertDictEqual(opt.value.params, self.DEFAULT_PARS)
        opt.set_value(self.NEW_VAL)
        self.assertEqual(opt.value, self.NEW_VAL)
        self.assertIsInstance(opt.value, opt.datatype)
        self.assertEqual(opt.value.mime_type, self.NEW_TYPE)
        self.assertDictEqual(opt.value.params, self.NEW_PARS)
    def test_required(self):
        opt = config.MIMEOption('option_name', 'description', required=True)
        self.assertEqual(opt.name, 'option_name')
        self.assertEqual(opt.datatype, MIME)
        self.assertEqual(opt.description, 'description')
        self.assertTrue(opt.required)
        self.assertIsNone(opt.default)
        self.assertIsNone(opt.value)
        with self.assertRaises(Error) as cm:
            opt.validate()
        self.assertEqual(cm.exception.args, ("Missing value for required option 'option_name'",))
        opt.load_config(self.conf, PRESENT_S)
        self.assertEqual(opt.value, self.PRESENT_VAL)
        self.assertEqual(opt.value.mime_type, self.PRESENT_TYPE)
        self.assertDictEqual(opt.value.params, self.PRESENT_PARS)
        opt.validate()
        opt.clear()
        self.assertIsNone(opt.value)
        opt.load_config(self.conf, DEFAULT_S)
        self.assertEqual(opt.value, self.DEFAULT_VAL)
        self.assertEqual(opt.value.mime_type, self.DEFAULT_TYPE)
        self.assertDictEqual(opt.value.params, self.DEFAULT_PARS)
        with self.assertRaises(ValueError) as cm:
            opt.set_value(None)
        self.assertEqual(cm.exception.args, ("Value is required for option 'option_name'.",))
        opt.load_config(self.conf, ABSENT_S)
        self.assertEqual(opt.value, self.DEFAULT_VAL)
        self.assertEqual(opt.value.mime_type, self.DEFAULT_TYPE)
        self.assertDictEqual(opt.value.params, self.DEFAULT_PARS)
        opt.set_value(self.NEW_VAL)
        self.assertEqual(opt.value, self.NEW_VAL)
        self.assertEqual(opt.value.mime_type, self.NEW_TYPE)
        self.assertDictEqual(opt.value.params, self.NEW_PARS)
    def test_bad_value(self):
        opt: config.MIMEOption = config.MIMEOption('option_name', 'description')
        with self.assertRaises(ValueError) as cm:
            opt.load_config(self.conf, BAD_S)
        self.assertEqual(cm.exception.args, ("MIME type specification must be 'type/subtype[;param=value;...]'",))
        with self.assertRaises(ValueError) as cm:
            opt.load_config(self.conf, 'unsupported_mime_type')
        self.assertEqual(cm.exception.args, ("MIME type 'model' not supported",))
        with self.assertRaises(ValueError) as cm:
            opt.load_config(self.conf, 'bad_mime_parameters')
        self.assertEqual(cm.exception.args, ('Wrong specification of MIME type parameters',))
        with self.assertRaises(TypeError) as cm:
            opt.set_value(10.0)
        self.assertEqual(cm.exception.args, ("Option 'option_name' value must be a 'MIME', not 'float'",))
    def test_default(self):
        opt = config.MIMEOption('option_name', 'description', default=self.DEFAULT_OPT_VAL)
        self.assertEqual(opt.name, 'option_name')
        self.assertEqual(opt.datatype, MIME)
        self.assertEqual(opt.description, 'description')
        self.assertFalse(opt.required)
        self.assertEqual(str(opt.default), str(self.DEFAULT_OPT_VAL))
        self.assertIsInstance(opt.default, opt.datatype)
        self.assertEqual(str(opt.value), str(self.DEFAULT_OPT_VAL))
        self.assertIsInstance(opt.value, opt.datatype)
        self.assertEqual(opt.value.mime_type, self.DEFAULT_OPT_TYPE)
        self.assertDictEqual(opt.value.params, self.DEFAULT_OPT_PARS)
        opt.validate()
        opt.load_config(self.conf, PRESENT_S)
        self.assertEqual(opt.get_as_str(), str(self.PRESENT_VAL))
        self.assertEqual(opt.value.mime_type, self.PRESENT_TYPE)
        self.assertDictEqual(opt.value.params, self.PRESENT_PARS)
        opt.clear()
        self.assertEqual(opt.value, opt.default)
        opt.load_config(self.conf, DEFAULT_S)
        self.assertEqual(opt.value, self.DEFAULT_VAL)
        self.assertEqual(opt.value.mime_type, self.DEFAULT_TYPE)
        self.assertDictEqual(opt.value.params, self.DEFAULT_PARS)
        opt.set_value(None)
        self.assertIsNone(opt.value)
        opt.load_config(self.conf, ABSENT_S)
        self.assertEqual(opt.value, self.DEFAULT_VAL)
        self.assertEqual(opt.value.mime_type, self.DEFAULT_TYPE)
        self.assertDictEqual(opt.value.params, self.DEFAULT_PARS)
        opt.set_value(self.NEW_VAL)
        self.assertEqual(opt.value, self.NEW_VAL)
        self.assertEqual(opt.value.mime_type, self.NEW_TYPE)
        self.assertDictEqual(opt.value.params, self.NEW_PARS)
    def test_proto(self):
        opt = config.MIMEOption('option_name', 'description', default=self.DEFAULT_OPT_VAL)
        proto_value = self.NEW_VAL
        opt.set_value(proto_value)
        self.proto.options['option_name'].as_string = proto_value
        proto_dump = str(self.proto)
        opt.load_proto(self.proto)
        self.assertEqual(opt.value, proto_value)
        self.assertEqual(opt.value.mime_type, self.NEW_TYPE)
        self.assertDictEqual(opt.value.params, self.NEW_PARS)
        self.assertIsInstance(opt.value, opt.datatype)
        self.proto.Clear()
        self.assertFalse('option_name' in self.proto.options)
        opt.save_proto(self.proto)
        self.assertTrue('option_name' in self.proto.options)
        self.assertEqual(str(self.proto), proto_dump)
        # empty proto
        opt.clear(to_default=False)
        self.proto.Clear()
        opt.load_proto(self.proto)
        self.assertIsNone(opt.value)
        # bad proto value
        self.proto.options['option_name'].as_uint32 = 1000
        with self.assertRaises(TypeError) as cm:
            opt.load_proto(self.proto)
        self.assertEqual(cm.exception.args, ('Wrong value type: uint32',))
        self.proto.Clear()
        opt.clear(to_default=False)
        opt.save_proto(self.proto)
        self.assertFalse('option_name' in self.proto.options)
    def test_get_config(self):
        opt = config.MIMEOption('option_name', 'description', default=self.DEFAULT_OPT_VAL)
        lines = """; option_name
; -----------
;
; data type: MIME
;
; [optional] description
;
;option_name = text/plain;charset=win1250
"""
        self.assertEqual(opt.get_config(), lines)
        lines = """; option_name
; -----------
;
; data type: MIME
;
; [optional] description
;
option_name = application/x.fb.proto;type=firebird.butler.fbsd.ErrorDescription
"""
        opt.set_value(self.NEW_VAL)
        self.assertEqual(opt.get_config(), lines)
        lines = """; option_name
; -----------
;
; data type: MIME
;
; [optional] description
;
option_name = <UNDEFINED>
"""
        opt.set_value(None)
        self.assertEqual(opt.get_config(), lines)

class TestZMQAddressOption(BaseConfigTest):
    "Unit tests for firebird.base.config.ZMQAddressOption"
    PRESENT_VAL = ZMQAddress('ipc://@my-address')
    DEFAULT_VAL = ZMQAddress('tcp://127.0.0.1:*')
    DEFAULT_OPT_VAL = ZMQAddress('tcp://127.0.0.1:8001')
    NEW_VAL = ZMQAddress('inproc://my-address')
    def setUp(self):
        super().setUp()
        self.setConf("""[%(DEFAULT)s]
option_name = tcp://127.0.0.1:*
[%(PRESENT)s]
option_name = ipc://@my-address
[%(ABSENT)s]
[%(BAD)s]
option_name = bad_value
""")
    def test_simple(self):
        opt = config.ZMQAddressOption('option_name', 'description')
        self.assertEqual(opt.name, 'option_name')
        self.assertEqual(opt.datatype, ZMQAddress)
        self.assertEqual(opt.description, 'description')
        self.assertFalse(opt.required)
        self.assertIsNone(opt.default)
        self.assertIsNone(opt.value)
        opt.validate()
        opt.load_config(self.conf, PRESENT_S)
        self.assertEqual(opt.value, self.PRESENT_VAL)
        self.assertEqual(opt.get_as_str(), 'ipc://@my-address')
        self.assertIsInstance(opt.value, opt.datatype)
        opt.clear()
        self.assertIsNone(opt.value)
        opt.load_config(self.conf, DEFAULT_S)
        self.assertEqual(opt.value, self.DEFAULT_VAL)
        self.assertIsInstance(opt.value, opt.datatype)
        opt.set_value(None)
        self.assertIsNone(opt.value)
        opt.load_config(self.conf, ABSENT_S)
        self.assertEqual(opt.value, self.DEFAULT_VAL)
        self.assertIsInstance(opt.value, opt.datatype)
        opt.set_value(self.NEW_VAL)
        self.assertEqual(opt.value, self.NEW_VAL)
        self.assertIsInstance(opt.value, opt.datatype)
    def test_required(self):
        opt = config.ZMQAddressOption('option_name', 'description', required=True)
        self.assertEqual(opt.name, 'option_name')
        self.assertEqual(opt.datatype, ZMQAddress)
        self.assertEqual(opt.description, 'description')
        self.assertTrue(opt.required)
        self.assertIsNone(opt.default)
        self.assertIsNone(opt.value)
        with self.assertRaises(Error) as cm:
            opt.validate()
        self.assertEqual(cm.exception.args, ("Missing value for required option 'option_name'",))
        opt.load_config(self.conf, PRESENT_S)
        self.assertEqual(opt.value, self.PRESENT_VAL)
        opt.validate()
        opt.clear()
        self.assertIsNone(opt.value)
        opt.load_config(self.conf, DEFAULT_S)
        self.assertEqual(opt.value, self.DEFAULT_VAL)
        with self.assertRaises(ValueError) as cm:
            opt.set_value(None)
        self.assertEqual(cm.exception.args, ("Value is required for option 'option_name'.",))
        opt.load_config(self.conf, ABSENT_S)
        self.assertEqual(opt.value, self.DEFAULT_VAL)
        opt.set_value(self.NEW_VAL)
        self.assertEqual(opt.value, self.NEW_VAL)
    def test_bad_value(self):
        opt = config.ZMQAddressOption('option_name', 'description')
        with self.assertRaises(ValueError) as cm:
            opt.load_config(self.conf, BAD_S)
        self.assertEqual(cm.exception.args, ('Protocol specification required',))
        with self.assertRaises(TypeError) as cm:
            opt.set_value(10.0)
        self.assertEqual(cm.exception.args, ("Option 'option_name' value must be a 'ZMQAddress', not 'float'",))
    def test_default(self):
        opt = config.ZMQAddressOption('option_name', 'description', default=self.DEFAULT_OPT_VAL)
        self.assertEqual(opt.name, 'option_name')
        self.assertEqual(opt.datatype, ZMQAddress)
        self.assertEqual(opt.description, 'description')
        self.assertFalse(opt.required)
        self.assertEqual(opt.default, self.DEFAULT_OPT_VAL)
        self.assertIsInstance(opt.default, opt.datatype)
        self.assertEqual(opt.value, self.DEFAULT_OPT_VAL)
        self.assertIsInstance(opt.value, opt.datatype)
        opt.validate()
        opt.load_config(self.conf, PRESENT_S)
        self.assertEqual(opt.value, self.PRESENT_VAL)
        opt.clear()
        self.assertEqual(opt.value, opt.default)
        opt.load_config(self.conf, DEFAULT_S)
        self.assertEqual(opt.value, self.DEFAULT_VAL)
        opt.set_value(None)
        self.assertIsNone(opt.value)
        opt.load_config(self.conf, ABSENT_S)
        self.assertEqual(opt.value, self.DEFAULT_VAL)
        opt.set_value(self.NEW_VAL)
        self.assertEqual(opt.value, self.NEW_VAL)
    def test_proto(self):
        opt = config.ZMQAddressOption('option_name', 'description', default=self.DEFAULT_OPT_VAL)
        proto_value = ZMQAddress('inproc://proto-address')
        opt.set_value(proto_value)
        self.proto.options['option_name'].as_string = proto_value
        proto_dump = str(self.proto)
        opt.load_proto(self.proto)
        self.assertEqual(opt.value, proto_value)
        self.assertIsInstance(opt.value, opt.datatype)
        self.proto.Clear()
        self.assertFalse('option_name' in self.proto.options)
        opt.save_proto(self.proto)
        self.assertTrue('option_name' in self.proto.options)
        self.assertEqual(str(self.proto), proto_dump)
        # empty proto
        opt.clear(to_default=False)
        self.proto.Clear()
        opt.load_proto(self.proto)
        self.assertIsNone(opt.value)
        # bad proto value
        self.proto.options['option_name'].as_string = 'BAD VALUE'
        with self.assertRaises(ValueError) as cm:
            opt.load_proto(self.proto)
        self.assertEqual(cm.exception.args, ('Protocol specification required',))
        self.proto.options['option_name'].as_uint64 = 1000
        with self.assertRaises(TypeError) as cm:
            opt.load_proto(self.proto)
        self.assertEqual(cm.exception.args, ('Wrong value type: uint64',))
        self.proto.Clear()
        opt.clear(to_default=False)
        opt.save_proto(self.proto)
        self.assertFalse('option_name' in self.proto.options)
    def test_get_config(self):
        opt = config.ZMQAddressOption('option_name', 'description', default=self.DEFAULT_OPT_VAL)
        lines = """; option_name
; -----------
;
; data type: ZMQAddress
;
; [optional] description
;
;option_name = tcp://127.0.0.1:8001
"""
        self.assertEqual(opt.get_config(), lines)
        lines = """; option_name
; -----------
;
; data type: ZMQAddress
;
; [optional] description
;
option_name = inproc://my-address
"""
        opt.set_value(self.NEW_VAL)
        self.assertEqual(opt.get_config(), lines)
        lines = """; option_name
; -----------
;
; data type: ZMQAddress
;
; [optional] description
;
option_name = <UNDEFINED>
"""
        opt.set_value(None)
        self.assertEqual(opt.get_config(), lines)

class TestListOption(BaseConfigTest):
    "Unit tests for firebird.base.config.ListOption"
    DEFAULT_VAL = ['DEFAULT_value']
    DEFAULT_PRINT = "DEFAULT_1, DEFAULT_2, DEFAULT_3"
    PRESENT_VAL = ['present_value_1', 'present_value_2']
    PRESENT_AS_STR = 'present_value_1,present_value_2'
    DEFAULT_OPT_VAL = ['DEFAULT_1', 'DEFAULT_2', 'DEFAULT_3']
    NEW_VAL = ['NEW']
    NEW_PRINT = 'NEW'
    ITEM_TYPE = str
    PROTO_VALUE = ['proto_value_1', 'proto_value_2']
    PROTO_VALUE_STR = 'proto_value_1,proto_value_2'
    LONG_VAL = ['long' * 3, 'verylong' * 3, 'veryverylong' * 5]
    BAD_MSG = None
    def setUp(self):
        super().setUp()
        self.prepare()
    def prepare(self):
        x = '\n   '
        self.LONG_PRINT = f"\n   {x.join(self.LONG_VAL)}"
        self.setConf("""[%(DEFAULT)s]
option_name = DEFAULT_value
[%(PRESENT)s]
option_name =
  present_value_1
  present_value_2
[%(ABSENT)s]
[%(BAD)s]
option_name =
""")
    def test_simple(self):
        opt = config.ListOption('option_name', self.ITEM_TYPE, 'description')
        self.assertEqual(opt.name, 'option_name')
        self.assertEqual(opt.datatype, list)
        self.assertEqual(opt.description, 'description')
        self.assertFalse(opt.required)
        self.assertIsNone(opt.default)
        self.assertIsNone(opt.value)
        opt.validate()
        opt.load_config(self.conf, PRESENT_S)
        self.assertEqual(opt.value, self.PRESENT_VAL)
        self.assertEqual(opt.get_as_str(), self.PRESENT_AS_STR)
        self.assertIsInstance(opt.value, opt.datatype)
        opt.clear()
        self.assertIsNone(opt.value)
        opt.load_config(self.conf, DEFAULT_S)
        self.assertEqual(opt.value, self.DEFAULT_VAL)
        self.assertIsInstance(opt.value, opt.datatype)
        opt.set_value(None)
        self.assertIsNone(opt.value)
        opt.load_config(self.conf, ABSENT_S)
        self.assertEqual(opt.value, self.DEFAULT_VAL)
        self.assertIsInstance(opt.value, opt.datatype)
        opt.set_value(self.NEW_VAL)
        self.assertEqual(opt.value, self.NEW_VAL)
        self.assertIsInstance(opt.value, opt.datatype)
    def test_required(self):
        opt = config.ListOption('option_name', self.ITEM_TYPE, 'description', required=True)
        self.assertEqual(opt.name, 'option_name')
        self.assertEqual(opt.datatype, list)
        self.assertEqual(opt.description, 'description')
        self.assertTrue(opt.required)
        self.assertIsNone(opt.default)
        self.assertIsNone(opt.value)
        with self.assertRaises(Error) as cm:
            opt.validate()
        self.assertEqual(cm.exception.args, ("Missing value for required option 'option_name'",))
        opt.load_config(self.conf, PRESENT_S)
        self.assertEqual(opt.value, self.PRESENT_VAL)
        opt.validate()
        opt.clear()
        self.assertIsNone(opt.value)
        opt.load_config(self.conf, DEFAULT_S)
        self.assertEqual(opt.value, self.DEFAULT_VAL)
        with self.assertRaises(ValueError) as cm:
            opt.set_value(None)
        self.assertEqual(cm.exception.args, ("Value is required for option 'option_name'.",))
        opt.load_config(self.conf, ABSENT_S)
        self.assertEqual(opt.value, self.DEFAULT_VAL)
        opt.set_value(self.NEW_VAL)
        self.assertEqual(opt.value, self.NEW_VAL)
    def test_bad_value(self):
        opt = config.ListOption('option_name', self.ITEM_TYPE, 'description')
        if self.ITEM_TYPE is str:
            opt.load_config(self.conf, BAD_S)
            self.assertIsNone(opt.value)
        else:
            with self.assertRaises(ValueError) as cm:
                opt.load_config(self.conf, BAD_S)
            #print(f'{cm.exception.args}\n')
            self.assertEqual(cm.exception.args, self.BAD_MSG)
            self.assertIsNone(opt.value)
        with self.assertRaises(TypeError) as cm:
            opt.set_value(10.0)
        self.assertEqual(cm.exception.args, ("Option 'option_name' value must be a 'list', not 'float'",))
    def test_default(self):
        opt = config.ListOption('option_name', self.ITEM_TYPE, 'description',
                                default=self.DEFAULT_OPT_VAL)
        self.assertEqual(opt.name, 'option_name')
        self.assertEqual(opt.datatype, list)
        self.assertEqual(opt.description, 'description')
        self.assertFalse(opt.required)
        self.assertEqual(opt.default, self.DEFAULT_OPT_VAL)
        self.assertIsInstance(opt.default, opt.datatype)
        self.assertEqual(opt.value, self.DEFAULT_OPT_VAL)
        self.assertIsInstance(opt.value, opt.datatype)
        opt.validate()
        opt.load_config(self.conf, PRESENT_S)
        self.assertEqual(opt.value, self.PRESENT_VAL)
        opt.clear()
        self.assertEqual(opt.value, opt.default)
        opt.load_config(self.conf, DEFAULT_S)
        self.assertEqual(opt.value, self.DEFAULT_VAL)
        opt.set_value(None)
        self.assertIsNone(opt.value)
        opt.load_config(self.conf, ABSENT_S)
        self.assertEqual(opt.value, self.DEFAULT_VAL)
        opt.set_value(self.NEW_VAL)
        self.assertEqual(opt.value, self.NEW_VAL)
    def test_proto(self):
        opt = config.ListOption('option_name', self.ITEM_TYPE, 'description',
                                default=self.DEFAULT_OPT_VAL)
        proto_value = self.PROTO_VALUE
        opt.set_value(proto_value)
        self.proto.options['option_name'].as_string = self.PROTO_VALUE_STR
        proto_dump = str(self.proto)
        opt.load_proto(self.proto)
        self.assertEqual(opt.value, proto_value)
        self.assertIsInstance(opt.value, opt.datatype)
        self.proto.Clear()
        self.assertFalse('option_name' in self.proto.options)
        opt.save_proto(self.proto)
        self.assertTrue('option_name' in self.proto.options)
        self.assertEqual(str(self.proto), proto_dump)
        # empty proto
        opt.clear(to_default=False)
        self.proto.Clear()
        opt.load_proto(self.proto)
        self.assertIsNone(opt.value)
        # bad proto value
        self.proto.options['option_name'].as_uint32 = 1000
        with self.assertRaises(TypeError) as cm:
            opt.load_proto(self.proto)
        self.assertEqual(cm.exception.args, ('Wrong value type: uint32',))
        self.proto.Clear()
        opt.clear(to_default=False)
        opt.save_proto(self.proto)
        self.assertFalse('option_name' in self.proto.options)
    def test_get_config(self):
        opt = config.ListOption('option_name', self.ITEM_TYPE, 'description',
                                default=self.DEFAULT_OPT_VAL)
        lines = f"""; option_name
; -----------
;
; data type: list
;
; [optional] description
;
;option_name = {self.DEFAULT_PRINT}
"""
        #print(f"\n{opt.get_config()}")
        self.assertEqual(opt.get_config(), lines)
        lines = f"""; option_name
; -----------
;
; data type: list
;
; [optional] description
;
option_name = {self.NEW_PRINT}
"""
        opt.set_value(self.NEW_VAL)
        self.assertEqual(opt.get_config(), lines)
        lines = """; option_name
; -----------
;
; data type: list
;
; [optional] description
;
option_name = <UNDEFINED>
"""
        opt.set_value(None)
        self.assertEqual(opt.get_config(), lines)
        lines = f"""; option_name
; -----------
;
; data type: list
;
; [optional] description
;
option_name = {self.LONG_PRINT}
"""
        opt.set_value(self.LONG_VAL)
        #print(f'\n{opt.get_config()}')
        self.assertEqual(opt.get_config(), lines)

class TestListOptionInt(TestListOption):
    "Unit tests for firebird.base.config.ListOption with int items"
    DEFAULT_VAL = [0]
    PRESENT_VAL = [10, 20]
    DEFAULT_OPT_VAL = [1, 2, 3]
    NEW_VAL = [100]

    DEFAULT_PRINT = '1, 2, 3'
    PRESENT_AS_STR = '10,20'
    NEW_PRINT = '100'
    ITEM_TYPE = int
    PROTO_VALUE = [30, 40, 50]
    PROTO_VALUE_STR = '30,40,50'
    LONG_VAL = [x for x in range(50)]
    def prepare(self):
        x = '\n   '
        self.LONG_PRINT = f"\n   {x.join(str(x) for x in self.LONG_VAL)}"
        self.BAD_MSG = ("invalid literal for int() with base 10: 'this is not an integer'",)
        self.setConf("""[%(DEFAULT)s]
option_name = 0
[%(PRESENT)s]
option_name = 10, 20
[%(ABSENT)s]
[%(BAD)s]
option_name = this is not an integer
""")

class TestListOptionFloat(TestListOption):
    "Unit tests for firebird.base.config.ListOption with float items"
    DEFAULT_VAL = [0.0]
    PRESENT_VAL = [10.1, 20.2]
    DEFAULT_OPT_VAL = [1.11, 2.22, 3.33]
    NEW_VAL = [100.101]

    DEFAULT_PRINT = '1.11, 2.22, 3.33'
    PRESENT_AS_STR = '10.1,20.2'
    NEW_PRINT = '100.101'
    ITEM_TYPE = float
    PROTO_VALUE = [30.3, 40.4, 50.5]
    PROTO_VALUE_STR = '30.3,40.4,50.5'
    LONG_VAL = [x / 1.5 for x in range(50)]
    def prepare(self):
        x = '\n   '
        self.LONG_PRINT = f"\n   {x.join(str(x) for x in self.LONG_VAL)}"
        self.BAD_MSG = ("could not convert string to float: 'this is not a float'",)
        self.setConf("""[%(DEFAULT)s]
option_name = 0.0
[%(PRESENT)s]
option_name = 10.1, 20.2
[%(ABSENT)s]
[%(BAD)s]
option_name = this is not a float
""")

class TestListOptionDecimal(TestListOption):
    "Unit tests for firebird.base.config.ListOption with Decimal items"
    DEFAULT_VAL = [Decimal('0.0')]
    PRESENT_VAL = [Decimal('10.1'), Decimal('20.2')]
    DEFAULT_OPT_VAL = [Decimal('1.11'), Decimal('2.22'), Decimal('3.33')]
    NEW_VAL = [Decimal('100.101')]

    DEFAULT_PRINT = '1.11, 2.22, 3.33'
    PRESENT_AS_STR = '10.1,20.2'
    NEW_PRINT = '100.101'
    ITEM_TYPE = Decimal
    PROTO_VALUE = [Decimal('30.3'), Decimal('40.4'), Decimal('50.5')]
    PROTO_VALUE_STR = '30.3,40.4,50.5'
    LONG_VAL = [Decimal(str(x / 1.5)) for x in range(50)]
    def prepare(self):
        x = '\n   '
        self.LONG_PRINT = f"\n   {x.join(str(x) for x in self.LONG_VAL)}"
        self.BAD_MSG = ("could not convert string to Decimal: 'this is not a decimal'",)
        self.setConf("""[%(DEFAULT)s]
option_name = 0.0
[%(PRESENT)s]
option_name = 10.1, 20.2
[%(ABSENT)s]
[%(BAD)s]
option_name = this is not a decimal
""")

class TestListOptionBool(TestListOption):
    "Unit tests for firebird.base.config.ListOption with bool items"
    DEFAULT_VAL = [0]
    PRESENT_VAL = [True, False]
    DEFAULT_OPT_VAL = [True, False, True]
    NEW_VAL = [True]

    DEFAULT_PRINT = 'yes, no, yes'
    PRESENT_AS_STR = 'yes,no'
    NEW_PRINT = 'yes'
    ITEM_TYPE = bool
    PROTO_VALUE = [False, True, False]
    PROTO_VALUE_STR = 'no,yes,no'
    LONG_VAL = [bool(x % 2) for x in range(40)]
    def prepare(self):
        x = '\n   '
        self.LONG_PRINT = f"\n   {x.join(convert_to_str(x) for x in self.LONG_VAL)}"
        self.BAD_MSG = ('Value is not a valid bool string constant',)
        self.setConf("""[%(DEFAULT)s]
option_name = 0
[%(PRESENT)s]
option_name = yes, no
[%(ABSENT)s]
[%(BAD)s]
option_name = this is not a bool
""")

class TestListOptionUUID(TestListOption):
    "Unit tests for firebird.base.config.ListOption with UUID items"
    DEFAULT_VAL = [UUID('eeb7f94a-256d-11ea-ad1d-5404a6a1fd6e')]
    PRESENT_VAL = [UUID('0a7fd53a-256e-11ea-ad1d-5404a6a1fd6e'),
                   UUID('0551feb2-256e-11ea-ad1d-5404a6a1fd6e')]
    DEFAULT_OPT_VAL = [UUID('2f02868c-256e-11ea-ad1d-5404a6a1fd6e'),
                       UUID('3521db30-256e-11ea-ad1d-5404a6a1fd6e'),
                       UUID('3a3e68cc-256e-11ea-ad1d-5404a6a1fd6e')]
    NEW_VAL = [UUID('3e8a4ce8-256e-11ea-ad1d-5404a6a1fd6e')]

    DEFAULT_PRINT = '\n;   2f02868c-256e-11ea-ad1d-5404a6a1fd6e\n;   3521db30-256e-11ea-ad1d-5404a6a1fd6e\n;   3a3e68cc-256e-11ea-ad1d-5404a6a1fd6e'
    PRESENT_AS_STR = '0a7fd53a-256e-11ea-ad1d-5404a6a1fd6e,0551feb2-256e-11ea-ad1d-5404a6a1fd6e'
    NEW_PRINT = '3e8a4ce8-256e-11ea-ad1d-5404a6a1fd6e'
    ITEM_TYPE = UUID
    PROTO_VALUE = [UUID('3a3e68cc-256e-11ea-ad1d-5404a6a1fd6e'), UUID('3521db30-256e-11ea-ad1d-5404a6a1fd6e')]
    PROTO_VALUE_STR = '3a3e68cc-256e-11ea-ad1d-5404a6a1fd6e,3521db30-256e-11ea-ad1d-5404a6a1fd6e'
    LONG_VAL = [UUID('2f02868c-256e-11ea-ad1d-5404a6a1fd6e') for x in range(10)]
    def prepare(self):
        x = '\n   '
        self.LONG_PRINT = f"\n   {x.join(str(x) for x in self.LONG_VAL)}"
        self.BAD_MSG = ('badly formed hexadecimal UUID string',)
        self.setConf("""[%(DEFAULT)s]
option_name = eeb7f94a-256d-11ea-ad1d-5404a6a1fd6e
[%(PRESENT)s]
option_name = 0a7fd53a256e11eaad1d5404a6a1fd6e, 0551feb2-256e-11ea-ad1d-5404a6a1fd6e
[%(ABSENT)s]
[%(BAD)s]
option_name = this is not an uuid
""")

class TestListOptionMIME(TestListOption):
    "Unit tests for firebird.base.config.ListOption with MIME items"
    DEFAULT_VAL = [MIME('application/octet-stream')]
    PRESENT_VAL = [MIME('text/plain;charset=utf-8'),
                   MIME('text/csv')]
    DEFAULT_OPT_VAL = [MIME('text/html;charset=utf-8'),
                       MIME('video/mp4'),
                       MIME('image/png')]
    NEW_VAL = [MIME('audio/mpeg')]

    DEFAULT_PRINT = 'text/html;charset=utf-8, video/mp4, image/png'
    PRESENT_AS_STR = 'text/plain;charset=utf-8,text/csv'
    NEW_PRINT = 'audio/mpeg'
    ITEM_TYPE = MIME
    PROTO_VALUE = [MIME('application/octet-stream'), MIME('video/mp4')]
    PROTO_VALUE_STR = 'application/octet-stream,video/mp4'
    LONG_VAL = [MIME('text/html;charset=win1250') for x in range(10)]
    def prepare(self):
        x = '\n   '
        self.LONG_PRINT = f"\n   {x.join(x for x in self.LONG_VAL)}"
        self.BAD_MSG = ("MIME type specification must be 'type/subtype[;param=value;...]'",)
        self.setConf("""[%(DEFAULT)s]
option_name = application/octet-stream
[%(PRESENT)s]
option_name =
    text/plain;charset=utf-8
    text/csv
[%(ABSENT)s]
[%(BAD)s]
option_name = wrong mime specification
""")

class TestListOptionZMQAddress(TestListOption):
    "Unit tests for firebird.base.config.ListOption with ZMQAddress items"
    DEFAULT_VAL = [ZMQAddress('tcp://127.0.0.1:*')]
    PRESENT_VAL = [ZMQAddress('ipc://@my-address'),
                   ZMQAddress('inproc://my-address'),
                   ZMQAddress('tcp://127.0.0.1:9001')]
    DEFAULT_OPT_VAL = [ZMQAddress('tcp://127.0.0.1:8001')]
    NEW_VAL = [ZMQAddress('inproc://my-address')]

    DEFAULT_PRINT = 'tcp://127.0.0.1:8001'
    PRESENT_AS_STR = 'ipc://@my-address,inproc://my-address,tcp://127.0.0.1:9001'
    NEW_PRINT = 'inproc://my-address'
    ITEM_TYPE = ZMQAddress
    PROTO_VALUE = [ZMQAddress('tcp://www.firebirdsql.org:8001'), ZMQAddress('tcp://www.firebirdsql.org:9001')]
    PROTO_VALUE_STR = 'tcp://www.firebirdsql.org:8001,tcp://www.firebirdsql.org:9001'
    LONG_VAL = [ZMQAddress('tcp://www.firebirdsql.org:500') for x in range(10)]
    def prepare(self):
        x = '\n   '
        self.LONG_PRINT = f"\n   {x.join(x for x in self.LONG_VAL)}"
        self.BAD_MSG = ('Protocol specification required',)
        self.setConf("""[%(DEFAULT)s]
option_name = tcp://127.0.0.1:*
[%(PRESENT)s]
option_name = ipc://@my-address, inproc://my-address, tcp://127.0.0.1:9001
[%(ABSENT)s]
[%(BAD)s]
option_name = bad_value
""")

class TestListOptionMultiType(TestListOption):
    "Unit tests for firebird.base.config.ListOption with items of various types"
    DEFAULT_VAL = ['DEFAULT_value']
    PRESENT_VAL = [1, 1.1, Decimal('1.01'), True,
                   UUID('eeb7f94a-256d-11ea-ad1d-5404a6a1fd6e'),
                   MIME('application/octet-stream'),
                   ZMQAddress('tcp://127.0.0.1:*'),
                   SimpleEnum.RUNNING]
    DEFAULT_OPT_VAL = ['DEFAULT_1', 1, False]
    NEW_VAL = [MIME('text/plain;charset=utf-8')]

    DEFAULT_PRINT = 'DEFAULT_1, 1, no'
    PRESENT_AS_STR = '1\n1.1\n1.01\nyes\neeb7f94a-256d-11ea-ad1d-5404a6a1fd6e\napplication/octet-stream\ntcp://127.0.0.1:*\nRUNNING'
    NEW_PRINT = 'text/plain;charset=utf-8'
    ITEM_TYPE = (str, int, float, Decimal, bool, UUID, MIME, ZMQAddress, SimpleEnum)
    PROTO_VALUE = [UUID('2f02868c-256e-11ea-ad1d-5404a6a1fd6e'), MIME('application/octet-stream')]
    PROTO_VALUE_STR = 'UUID:2f02868c-256e-11ea-ad1d-5404a6a1fd6e,MIME:application/octet-stream'
    LONG_VAL = [ZMQAddress('tcp://www.firebirdsql.org:500'),
                UUID('2f02868c-256e-11ea-ad1d-5404a6a1fd6e'),
                MIME('application/octet-stream'),
                '=' * 30, 1, True, 10.1, Decimal('20.20')]
    def prepare(self):
        x = '\n   '
        self.LONG_PRINT = f"\n   {x.join(convert_to_str(x) for x in self.LONG_VAL)}"
        self.BAD_MSG = ("Item type 'bin' not supported",)
        self.setConf("""[%(DEFAULT)s]
option_name = str:DEFAULT_value
[%(PRESENT)s]
option_name =
    int: 1
    float: 1.1
    Decimal: 1.01
    bool: yes
    UUID: eeb7f94a-256d-11ea-ad1d-5404a6a1fd6e
    firebird.base.types.MIME: application/octet-stream
    ZMQAddress: tcp://127.0.0.1:*
    SimpleEnum:RUNNING
[%(ABSENT)s]
[%(BAD)s]
option_name = str:this is string, int:20, bin:100110111
""")

class TestPyExprOption(BaseConfigTest):
    "Unit tests for firebird.base.config.PyExprOption"
    PRESENT_VAL = PyExpr('this.value in [1, 2, 3]')
    DEFAULT_VAL = PyExpr('this.value is None')
    DEFAULT_OPT_VAL = PyExpr('DEFAULT')
    NEW_VAL = PyExpr('this.value == "VALUE"')
    def setUp(self):
        super().setUp()
        self.setConf("""[%(DEFAULT)s]
option_name = this.value is None
[%(PRESENT)s]
option_name = this.value in [1, 2, 3]
[%(ABSENT)s]
[%(BAD)s]
option_name = This is not a valid Python expression
""")
    def test_simple(self):
        opt = config.PyExprOption('option_name', 'description')
        self.assertEqual(opt.name, 'option_name')
        self.assertEqual(opt.datatype, PyExpr)
        self.assertEqual(opt.description, 'description')
        self.assertFalse(opt.required)
        self.assertIsNone(opt.default)
        self.assertIsNone(opt.value)
        opt.validate()
        opt.load_config(self.conf, PRESENT_S)
        self.assertEqual(opt.value, self.PRESENT_VAL)
        self.assertEqual(opt.get_as_str(), 'this.value in [1, 2, 3]')
        self.assertIsInstance(opt.value, opt.datatype)
        opt.clear()
        self.assertIsNone(opt.value)
        opt.load_config(self.conf, DEFAULT_S)
        self.assertEqual(opt.value, self.DEFAULT_VAL)
        self.assertIsInstance(opt.value, opt.datatype)
        opt.set_value(None)
        self.assertIsNone(opt.value)
        opt.load_config(self.conf, ABSENT_S)
        self.assertEqual(opt.value, self.DEFAULT_VAL)
        self.assertIsInstance(opt.value, opt.datatype)
        opt.set_value(self.NEW_VAL)
        self.assertEqual(opt.value, self.NEW_VAL)
        self.assertIsInstance(opt.value, opt.datatype)
        # Check expression code
        obj = ValueHolder()
        obj.value = "VALUE"
        self.assertTrue(eval(opt.value, {'this': obj}))
        fce = opt.value.get_callable('this')
        self.assertTrue(fce(obj))
        obj.value = "OTHER VALUE"
        self.assertFalse(eval(opt.value, {'this': obj}))
        self.assertFalse(fce(obj))
    def test_required(self):
        opt = config.PyExprOption('option_name', 'description', required=True)
        self.assertEqual(opt.name, 'option_name')
        self.assertEqual(opt.datatype, PyExpr)
        self.assertEqual(opt.description, 'description')
        self.assertTrue(opt.required)
        self.assertIsNone(opt.default)
        self.assertIsNone(opt.value)
        with self.assertRaises(Error) as cm:
            opt.validate()
        self.assertEqual(cm.exception.args, ("Missing value for required option 'option_name'",))
        opt.load_config(self.conf, PRESENT_S)
        self.assertEqual(opt.value, self.PRESENT_VAL)
        opt.validate()
        opt.clear()
        self.assertIsNone(opt.value)
        opt.load_config(self.conf, DEFAULT_S)
        self.assertEqual(opt.value, self.DEFAULT_VAL)
        with self.assertRaises(ValueError) as cm:
            opt.set_value(None)
        self.assertEqual(cm.exception.args, ("Value is required for option 'option_name'.",))
        opt.load_config(self.conf, ABSENT_S)
        self.assertEqual(opt.value, self.DEFAULT_VAL)
        opt.set_value(self.NEW_VAL)
        self.assertEqual(opt.value, self.NEW_VAL)
    def test_bad_value(self):
        opt = config.PyExprOption('option_name', 'description')
        with self.assertRaises(SyntaxError) as cm:
            opt.load_config(self.conf, BAD_S)
        self.assertEqual(cm.exception.args, ('invalid syntax', ('PyExpr', 1, 15, 'This is not a valid Python expression')))
        with self.assertRaises(TypeError) as cm:
            opt.set_value(10.0)
        self.assertEqual(cm.exception.args, ("Option 'option_name' value must be a 'PyExpr', not 'float'",))
    def test_default(self):
        opt = config.PyExprOption('option_name', 'description', default=self.DEFAULT_OPT_VAL)
        self.assertEqual(opt.name, 'option_name')
        self.assertEqual(opt.datatype, PyExpr)
        self.assertEqual(opt.description, 'description')
        self.assertFalse(opt.required)
        self.assertEqual(opt.default, self.DEFAULT_OPT_VAL)
        self.assertIsInstance(opt.default, opt.datatype)
        self.assertEqual(opt.value, self.DEFAULT_OPT_VAL)
        self.assertIsInstance(opt.value, opt.datatype)
        opt.validate()
        opt.load_config(self.conf, PRESENT_S)
        self.assertEqual(opt.value, self.PRESENT_VAL)
        opt.clear()
        self.assertEqual(opt.value, opt.default)
        opt.load_config(self.conf, DEFAULT_S)
        self.assertEqual(opt.value, self.DEFAULT_VAL)
        opt.set_value(None)
        self.assertIsNone(opt.value)
        opt.load_config(self.conf, ABSENT_S)
        self.assertEqual(opt.value, self.DEFAULT_VAL)
        opt.set_value(self.NEW_VAL)
        self.assertEqual(opt.value, self.NEW_VAL)
    def test_proto(self):
        opt = config.PyExprOption('option_name', 'description', default=self.DEFAULT_OPT_VAL)
        proto_value = PyExpr('proto_value')
        opt.set_value(proto_value)
        self.proto.options['option_name'].as_string = proto_value
        proto_dump = str(self.proto)
        opt.load_proto(self.proto)
        self.assertEqual(opt.value, proto_value)
        self.assertIsInstance(opt.value, opt.datatype)
        self.proto.Clear()
        self.assertFalse('option_name' in self.proto.options)
        opt.save_proto(self.proto)
        self.assertTrue('option_name' in self.proto.options)
        self.assertEqual(str(self.proto), proto_dump)
        # empty proto
        opt.clear(to_default=False)
        self.proto.Clear()
        opt.load_proto(self.proto)
        self.assertIsNone(opt.value)
        # bad proto value
        self.proto.options['option_name'].as_uint32 = 1000
        with self.assertRaises(TypeError) as cm:
            opt.load_proto(self.proto)
        self.assertEqual(cm.exception.args, ('Wrong value type: uint32',))
        self.proto.Clear()
        opt.clear(to_default=False)
        opt.save_proto(self.proto)
        self.assertFalse('option_name' in self.proto.options)
    def test_get_config(self):
        opt = config.PyExprOption('option_name', 'description', default=self.DEFAULT_OPT_VAL)
        lines = """; option_name
; -----------
;
; data type: PyExpr
;
; [optional] description
;
;option_name = DEFAULT
"""
        self.assertEqual(opt.get_config(), lines)
        lines = """; option_name
; -----------
;
; data type: PyExpr
;
; [optional] description
;
option_name = this.value == "VALUE"
"""
        opt.set_value(self.NEW_VAL)
        self.assertEqual(opt.get_config(), lines)
        lines = """; option_name
; -----------
;
; data type: PyExpr
;
; [optional] description
;
option_name = <UNDEFINED>
"""
        opt.set_value(None)
        self.assertEqual(opt.get_config(), lines)

class TestPyCodeOption(BaseConfigTest):
    "Unit tests for firebird.base.config.PyCodeOption"
    DEFAULT_VAL = PyCode('print("Default value")')
    PRESENT_VAL = PyCode('\ndef pp(value):\n    print("Value:",value,file=output)\n\nfor i in [1,2,3]:\n    pp(i)')
    DEFAULT_OPT_VAL = PyCode('DEFAULT')
    NEW_VAL = PyCode('print("NEW value")')
    def setUp(self):
        super().setUp()
        self.setConf("""[%(DEFAULT)s]
option_name = print("Default value")
[%(PRESENT)s]
option_name =
    | def pp(value):
    |     print("Value:",value,file=output)
    |
    | for i in [1,2,3]:
    |     pp(i)
[%(ABSENT)s]
[%(BAD)s]
option_name = This is not a valid Python code block
""")
    def test_simple(self):
        opt = config.PyCodeOption('option_name', 'description')
        self.assertEqual(opt.name, 'option_name')
        self.assertEqual(opt.datatype, PyCode)
        self.assertEqual(opt.description, 'description')
        self.assertFalse(opt.required)
        self.assertIsNone(opt.default)
        self.assertIsNone(opt.value)
        opt.validate()
        opt.load_config(self.conf, PRESENT_S)
        self.assertEqual(opt.value, self.PRESENT_VAL)
        self.assertEqual(opt.get_as_str(), '\ndef pp(value):\n    print("Value:",value,file=output)\n\nfor i in [1,2,3]:\n    pp(i)')
        self.assertIsInstance(opt.value, opt.datatype)
        # Check expression code
        out = io.StringIO()
        exec(opt.value.code, {'output': out})
        self.assertEqual(out.getvalue(), 'Value: 1\nValue: 2\nValue: 3\n')
        #
        opt.clear()
        self.assertIsNone(opt.value)
        opt.load_config(self.conf, DEFAULT_S)
        self.assertEqual(opt.value, self.DEFAULT_VAL)
        self.assertIsInstance(opt.value, opt.datatype)
        opt.set_value(None)
        self.assertIsNone(opt.value)
        opt.load_config(self.conf, ABSENT_S)
        self.assertEqual(opt.value, self.DEFAULT_VAL)
        self.assertIsInstance(opt.value, opt.datatype)
        opt.set_value(self.NEW_VAL)
        self.assertEqual(opt.value, self.NEW_VAL)
        self.assertIsInstance(opt.value, opt.datatype)
    def test_required(self):
        opt = config.PyCodeOption('option_name', 'description', required=True)
        self.assertEqual(opt.name, 'option_name')
        self.assertEqual(opt.datatype, PyCode)
        self.assertEqual(opt.description, 'description')
        self.assertTrue(opt.required)
        self.assertIsNone(opt.default)
        self.assertIsNone(opt.value)
        with self.assertRaises(Error) as cm:
            opt.validate()
        self.assertEqual(cm.exception.args, ("Missing value for required option 'option_name'",))
        opt.load_config(self.conf, PRESENT_S)
        self.assertEqual(opt.value, self.PRESENT_VAL)
        opt.validate()
        opt.clear()
        self.assertIsNone(opt.value)
        opt.load_config(self.conf, DEFAULT_S)
        self.assertEqual(opt.value, self.DEFAULT_VAL)
        with self.assertRaises(ValueError) as cm:
            opt.set_value(None)
        self.assertEqual(cm.exception.args, ("Value is required for option 'option_name'.",))
        opt.load_config(self.conf, ABSENT_S)
        self.assertEqual(opt.value, self.DEFAULT_VAL)
        opt.set_value(self.NEW_VAL)
        self.assertEqual(opt.value, self.NEW_VAL)
    def test_bad_value(self):
        opt = config.PyCodeOption('option_name', 'description')
        with self.assertRaises(SyntaxError) as cm:
            opt.load_config(self.conf, BAD_S)
        self.assertEqual(cm.exception.args, ('invalid syntax', ('PyCode', 1, 15, 'This is not a valid Python code block\n')))
        with self.assertRaises(TypeError) as cm:
            opt.set_value(10.0)
        self.assertEqual(cm.exception.args, ("Option 'option_name' value must be a 'PyCode', not 'float'",))
    def test_default(self):
        opt = config.PyCodeOption('option_name', 'description', default=self.DEFAULT_OPT_VAL)
        self.assertEqual(opt.name, 'option_name')
        self.assertEqual(opt.datatype, PyCode)
        self.assertEqual(opt.description, 'description')
        self.assertFalse(opt.required)
        self.assertEqual(opt.default, self.DEFAULT_OPT_VAL)
        self.assertIsInstance(opt.default, opt.datatype)
        self.assertEqual(opt.value, self.DEFAULT_OPT_VAL)
        opt.validate()
        opt.load_config(self.conf, PRESENT_S)
        self.assertEqual(opt.value, self.PRESENT_VAL)
        opt.clear()
        self.assertEqual(opt.value, opt.default)
        opt.load_config(self.conf, DEFAULT_S)
        self.assertEqual(opt.value, self.DEFAULT_VAL)
        opt.set_value(None)
        self.assertIsNone(opt.value)
        opt.load_config(self.conf, ABSENT_S)
        self.assertEqual(opt.value, self.DEFAULT_VAL)
        opt.set_value(self.NEW_VAL)
        self.assertEqual(opt.value, self.NEW_VAL)
    def test_proto(self):
        opt = config.PyCodeOption('option_name', 'description')
        proto_value = PyCode('proto_value')
        opt.set_value(proto_value)
        self.proto.options['option_name'].as_string = proto_value
        proto_dump = str(self.proto)
        opt.load_proto(self.proto)
        self.assertEqual(opt.value, proto_value)
        self.assertIsInstance(opt.value, opt.datatype)
        self.proto.Clear()
        self.assertFalse('option_name' in self.proto.options)
        opt.save_proto(self.proto)
        self.assertTrue('option_name' in self.proto.options)
        self.assertEqual(str(self.proto), proto_dump)
        self.proto.Clear()
        opt.clear()
        opt.save_proto(self.proto)
        self.assertFalse('option_name' in self.proto.options)
    def test_get_config(self):
        opt = config.PyCodeOption('option_name', 'description', default=self.DEFAULT_OPT_VAL)
        lines = """; option_name
; -----------
;
; data type: PyCode
;
; [optional] description
;
;option_name = DEFAULT
"""
        self.assertEqual(opt.get_config(), lines)
        lines = """; option_name
; -----------
;
; data type: PyCode
;
; [optional] description
;
option_name =
   | def pp(value):
   |     print("Value:",value,file=output)
   |
   | for i in [1,2,3]:
   |     pp(i)"""
        opt.set_value(self.PRESENT_VAL)
        self.assertEqual('\n'.join(x.rstrip() for x in opt.get_config().splitlines()), lines)
        lines = """; option_name
; -----------
;
; data type: PyCode
;
; [optional] description
;
option_name = <UNDEFINED>
"""
        opt.set_value(None)
        self.assertEqual(opt.get_config(), lines)

class TestPyCallableOption(BaseConfigTest):
    "Unit tests for firebird.base.config.PyCallableOption"
    DEFAULT_VAL = PyCallable('\ndef foo(value: int) -> int:\n    return value * 2')
    PRESENT_VAL = PyCallable('\ndef foo(value: int) -> int:\n    return value * 5')
    DEFAULT_OPT_VAL = PyCallable('\ndef foo(value: int) -> int:\n    return value')
    NEW_VAL = PyCallable('\ndef foo(value: int) -> int:\n    return value * 3')
    def setUp(self):
        super().setUp()
        self.setConf("""[%(DEFAULT)s]
option_name =
    | def foo(value: int) -> int:
    |     return value * 2
[%(PRESENT)s]
option_name =
    | def foo(value: int) -> int:
    |     return value * 5
[%(ABSENT)s]
[%(BAD)s]
option_name = This is not a valid Python function/procedure definition
[bad_signature]
option_name =
    | def bad_foo(value, value_2)->int:
    |     return value * value_2
""")
    def test_simple(self):
        opt = config.PyCallableOption('option_name', 'description', signature=signature(foo_func))
        self.assertEqual(opt.name, 'option_name')
        self.assertEqual(opt.datatype, PyCallable)
        self.assertEqual(opt.description, 'description')
        self.assertFalse(opt.required)
        self.assertIsNone(opt.default)
        self.assertIsNone(opt.value)
        opt.validate()
        opt.load_config(self.conf, PRESENT_S)
        self.assertEqual(opt.value, self.PRESENT_VAL)
        self.assertEqual(opt.get_as_str(), self.PRESENT_VAL)
        self.assertIsInstance(opt.value, opt.datatype)
        self.assertEqual(opt.value.name, 'foo')
        # Check expression code
        self.assertEqual(opt.value(1), 5)
        #
        opt.clear()
        self.assertIsNone(opt.value)
        opt.load_config(self.conf, DEFAULT_S)
        self.assertEqual(opt.value, self.DEFAULT_VAL)
        self.assertIsInstance(opt.value, opt.datatype)
        opt.set_value(None)
        self.assertIsNone(opt.value)
        opt.load_config(self.conf, ABSENT_S)
        self.assertEqual(opt.value, self.DEFAULT_VAL)
        self.assertIsInstance(opt.value, opt.datatype)
        opt.set_value(self.NEW_VAL)
        self.assertEqual(opt.value, self.NEW_VAL)
        self.assertIsInstance(opt.value, opt.datatype)
    def test_required(self):
        opt = config.PyCallableOption('option_name', 'description', signature=signature(foo_func),
                                      required=True)
        self.assertEqual(opt.name, 'option_name')
        self.assertEqual(opt.datatype, PyCallable)
        self.assertEqual(opt.description, 'description')
        self.assertTrue(opt.required)
        self.assertIsNone(opt.default)
        self.assertIsNone(opt.value)
        with self.assertRaises(Error) as cm:
            opt.validate()
        self.assertEqual(cm.exception.args, ("Missing value for required option 'option_name'",))
        opt.load_config(self.conf, PRESENT_S)
        self.assertEqual(opt.value, self.PRESENT_VAL)
        opt.validate()
        opt.clear()
        self.assertIsNone(opt.value)
        opt.load_config(self.conf, DEFAULT_S)
        self.assertEqual(opt.value, self.DEFAULT_VAL)
        with self.assertRaises(ValueError) as cm:
            opt.set_value(None)
        self.assertEqual(cm.exception.args, ("Value is required for option 'option_name'.",))
        opt.load_config(self.conf, ABSENT_S)
        self.assertEqual(opt.value, self.DEFAULT_VAL)
        opt.set_value(self.NEW_VAL)
        self.assertEqual(opt.value, self.NEW_VAL)
    def test_bad_value(self):
        opt = config.PyCallableOption('option_name', 'description', signature=signature(foo_func))
        with self.assertRaises(ValueError) as cm:
            opt.load_config(self.conf, BAD_S)
        self.assertEqual(cm.exception.args, ('Python function or class definition not found',))
        with self.assertRaises(ValueError) as cm:
            opt.load_config(self.conf, 'bad_signature')
        self.assertEqual(cm.exception.args, ('Wrong number of parameters',))
        with self.assertRaises(ValueError) as cm:
            opt.set_as_str('\ndef foo(value: int) -> float:\n    return value * 3')
        self.assertEqual(cm.exception.args, ('Wrong callable return type',))
        with self.assertRaises(ValueError) as cm:
            opt.set_as_str('\ndef foo(value: float) -> int:\n    return value * 3')
        self.assertEqual(cm.exception.args, ("Wrong type, parameter 'value'",))
        with self.assertRaises(TypeError) as cm:
            opt.set_value(10.0)
        self.assertEqual(cm.exception.args, ("Option 'option_name' value must be a 'PyCallable', not 'float'",))
    def test_default(self):
        opt = config.PyCallableOption('option_name', 'description', signature=signature(foo_func),
                                      default=self.DEFAULT_OPT_VAL)
        self.assertEqual(opt.name, 'option_name')
        self.assertEqual(opt.datatype, PyCallable)
        self.assertEqual(opt.description, 'description')
        self.assertFalse(opt.required)
        self.assertEqual(opt.default, self.DEFAULT_OPT_VAL)
        self.assertIsInstance(opt.default, opt.datatype)
        self.assertEqual(opt.value, self.DEFAULT_OPT_VAL)
        self.assertIsInstance(opt.value, opt.datatype)
        opt.validate()
        opt.load_config(self.conf, PRESENT_S)
        self.assertEqual(opt.value, self.PRESENT_VAL)
        opt.clear()
        self.assertEqual(opt.value, opt.default)
        opt.load_config(self.conf, DEFAULT_S)
        self.assertEqual(opt.value, self.DEFAULT_VAL)
        opt.set_value(None)
        self.assertIsNone(opt.value)
        opt.load_config(self.conf, ABSENT_S)
        self.assertEqual(opt.value, self.DEFAULT_VAL)
        opt.set_value(self.NEW_VAL)
        self.assertEqual(opt.value, self.NEW_VAL)
    def test_proto(self):
        opt = config.PyCallableOption('option_name', 'description', signature=signature(foo_func),
                                      default=self.DEFAULT_OPT_VAL)
        proto_value = '\ndef foo(value: int) -> int:\n    return value * 100'
        opt.set_value(PyCallable(proto_value))
        self.proto.options['option_name'].as_string = proto_value
        proto_dump = str(self.proto)
        opt.load_proto(self.proto)
        self.assertEqual(opt.value, proto_value)
        self.assertIsInstance(opt.value, opt.datatype)
        self.proto.Clear()
        self.assertFalse('option_name' in self.proto.options)
        opt.save_proto(self.proto)
        self.assertTrue('option_name' in self.proto.options)
        self.assertEqual(str(self.proto), proto_dump)
        # empty proto
        opt.clear(to_default=False)
        self.proto.Clear()
        opt.load_proto(self.proto)
        self.assertIsNone(opt.value)
        # bad proto value
        self.proto.options['option_name'].as_uint32 = 1000
        with self.assertRaises(TypeError):
            opt.load_proto(self.proto)
        self.proto.Clear()
        opt.clear(to_default=False)
        opt.save_proto(self.proto)
        self.assertFalse('option_name' in self.proto.options)
    def test_get_config(self):
        opt = config.PyCallableOption('option_name', 'description', signature=signature(foo_func),
                                      default=self.DEFAULT_OPT_VAL)
        lines = """; option_name
; -----------
;
; data type: PyCallable
;
; [optional] description
;
;option_name =
;   | def foo(value: int) -> int:
;   |     return value"""
        self.assertEqual('\n'.join(x.rstrip() for x in opt.get_config().splitlines()), lines)
        lines = """; option_name
; -----------
;
; data type: PyCallable
;
; [optional] description
;
option_name =
   | def foo(value: int) -> int:
   |     return value * 5"""
        opt.set_value(self.PRESENT_VAL)
        self.assertEqual('\n'.join(x.rstrip() for x in opt.get_config().splitlines()), lines)
        lines = """; option_name
; -----------
;
; data type: PyCallable
;
; [optional] description
;
option_name = <UNDEFINED>
"""
        opt.set_value(None)
        self.assertEqual(opt.get_config(), lines)

class TestDataclassOption(BaseConfigTest):
    "Unit tests for firebird.base.config.EnumOption"
    DEFAULT_VAL = SimpleDataclass('main')
    PRESENT_VAL = SimpleDataclass('master', 3, SimpleEnum.RUNNING)
    DEFAULT_OPT_VAL = SimpleDataclass('default')
    NEW_VAL = SimpleDataclass('master', 3, SimpleEnum.STOPPED)
    def setUp(self):
        super().setUp()
        self.setConf("""[%(DEFAULT)s]
; Enum is defined by name
option_name = name:main
[%(PRESENT)s]
; case does not matter
option_name =
   name:master
   priority:3
   state:RUNNING
[%(ABSENT)s]
[%(BAD)s]
option_name = bad_value
[illegal]
option_name = 1000
""")
    def _dc_equal(self, first, second):
        for fld in first.__dataclass_fields__.values():
            if getattr(first, fld.name) != getattr(second, fld.name):
                return False
        return True
    def test_simple(self):
        opt = config.DataclassOption('option_name', SimpleDataclass, 'description')
        self.assertEqual(opt.name, 'option_name')
        self.assertEqual(opt.datatype, SimpleDataclass)
        self.assertEqual(opt.description, 'description')
        self.assertFalse(opt.required)
        self.assertIsNone(opt.default)
        self.assertIsNone(opt.value)
        opt.validate()
        opt.load_config(self.conf, PRESENT_S)
        self.assertTrue(self._dc_equal(opt.value, self.PRESENT_VAL))
        self.assertEqual(opt.get_as_str(), 'name:master,priority:3,state:RUNNING')
        self.assertIsInstance(opt.value, opt.datatype)
        opt.clear()
        self.assertIsNone(opt.value)
        opt.load_config(self.conf, DEFAULT_S)
        self.assertTrue(self._dc_equal(opt.value, self.DEFAULT_VAL))
        self.assertIsInstance(opt.value, opt.datatype)
        opt.set_value(None)
        self.assertIsNone(opt.value)
        opt.load_config(self.conf, ABSENT_S)
        self.assertTrue(self._dc_equal(opt.value, self.DEFAULT_VAL))
        self.assertIsInstance(opt.value, opt.datatype)
        opt.set_value(self.NEW_VAL)
        self.assertTrue(self._dc_equal(opt.value, self.NEW_VAL))
        self.assertIsInstance(opt.value, opt.datatype)
    def test_required(self):
        opt = config.DataclassOption('option_name', SimpleDataclass, 'description', required=True)
        self.assertEqual(opt.name, 'option_name')
        self.assertEqual(opt.datatype, SimpleDataclass)
        self.assertEqual(opt.description, 'description')
        self.assertTrue(opt.required)
        self.assertIsNone(opt.default)
        self.assertIsNone(opt.value)
        with self.assertRaises(Error) as cm:
            opt.validate()
        self.assertEqual(cm.exception.args, ("Missing value for required option 'option_name'",))
        opt.load_config(self.conf, PRESENT_S)
        self.assertTrue(self._dc_equal(opt.value, self.PRESENT_VAL))
        opt.validate()
        opt.clear()
        self.assertIsNone(opt.value)
        opt.load_config(self.conf, DEFAULT_S)
        self.assertTrue(self._dc_equal(opt.value, self.DEFAULT_VAL))
        with self.assertRaises(ValueError) as cm:
            opt.set_value(None)
        self.assertEqual(cm.exception.args, ("Value is required for option 'option_name'.",))
        opt.load_config(self.conf, ABSENT_S)
        self.assertTrue(self._dc_equal(opt.value, self.DEFAULT_VAL))
        opt.set_value(self.NEW_VAL)
        self.assertTrue(self._dc_equal(opt.value, self.NEW_VAL))
    def test_bad_value(self):
        opt = config.DataclassOption('option_name', SimpleDataclass, 'description')
        with self.assertRaises(ValueError) as cm:
            opt.load_config(self.conf, BAD_S)
        self.assertEqual(cm.exception.args, ("Illegal value 'bad_value' for option 'option_name'",))
        with self.assertRaises(ValueError) as cm:
            opt.load_config(self.conf, 'illegal')
        self.assertEqual(cm.exception.args, ("Illegal value '1000' for option 'option_name'",))
        with self.assertRaises(TypeError) as cm:
            opt.set_value(10.0)
        self.assertEqual(cm.exception.args, ("Option 'option_name' value must be a 'SimpleDataclass', not 'float'",))
    def test_default(self):
        opt = config.DataclassOption('option_name', SimpleDataclass, 'description', default=self.DEFAULT_OPT_VAL)
        self.assertEqual(opt.name, 'option_name')
        self.assertEqual(opt.datatype, SimpleDataclass)
        self.assertEqual(opt.description, 'description')
        self.assertFalse(opt.required)
        self.assertTrue(self._dc_equal(opt.default, self.DEFAULT_OPT_VAL))
        self.assertIsInstance(opt.default, opt.datatype)
        self.assertTrue(self._dc_equal(opt.default, self.DEFAULT_OPT_VAL))
        self.assertIsInstance(opt.value, opt.datatype)
        opt.validate()
        opt.load_config(self.conf, PRESENT_S)
        self.assertTrue(self._dc_equal(opt.value, self.PRESENT_VAL))
        opt.clear()
        self.assertTrue(self._dc_equal(opt.value, opt.default))
        opt.load_config(self.conf, DEFAULT_S)
        self.assertTrue(self._dc_equal(opt.value, self.DEFAULT_VAL))
        opt.set_value(None)
        self.assertIsNone(opt.value)
        opt.load_config(self.conf, ABSENT_S)
        self.assertTrue(self._dc_equal(opt.value, self.DEFAULT_VAL))
        opt.set_value(self.NEW_VAL)
        self.assertTrue(self._dc_equal(opt.value, self.NEW_VAL))
    def test_proto(self):
        opt = config.DataclassOption('option_name', SimpleDataclass, 'description', default=self.DEFAULT_OPT_VAL)
        proto_value = SimpleDataclass('backup', 2, SimpleEnum.FINISHED)
        opt.set_value(proto_value)
        self.proto.options['option_name'].as_string = 'name:backup,priority:2,state:FINISHED'
        proto_dump = str(self.proto)
        opt.load_proto(self.proto)
        self.assertTrue(self._dc_equal(opt.value, proto_value))
        self.assertIsInstance(opt.value, opt.datatype)
        opt.set_value(None)
        self.proto.options['option_name'].as_string = 'name:backup,priority:2,state:FINISHED'
        opt.load_proto(self.proto)
        self.assertTrue(self._dc_equal(opt.value, proto_value))
        self.proto.Clear()
        self.assertFalse('option_name' in self.proto.options)
        opt.save_proto(self.proto)
        self.assertTrue('option_name' in self.proto.options)
        self.assertEqual(str(self.proto), proto_dump)
        # empty proto
        opt.clear(to_default=False)
        self.proto.Clear()
        opt.load_proto(self.proto)
        self.assertIsNone(opt.value)
        # bad proto value
        self.proto.options['option_name'].as_uint32 = 1000
        with self.assertRaises(TypeError) as cm:
            opt.load_proto(self.proto)
        self.assertEqual(cm.exception.args, ('Wrong value type: uint32',))
        self.proto.Clear()
        opt.clear(to_default=False)
        opt.save_proto(self.proto)
        self.assertFalse('option_name' in self.proto.options)
    def test_get_config(self):
        opt = config.DataclassOption('option_name', SimpleDataclass, 'description', default=self.DEFAULT_OPT_VAL)
        lines = """; option_name
; -----------
;
; data type: SimpleDataclass
;
; [optional] description
;
;option_name = name:default, priority:1, state:READY
"""
        self.assertEqual(opt.get_config(), lines)
        lines = """; option_name
; -----------
;
; data type: SimpleDataclass
;
; [optional] description
;
option_name = name:master, priority:3, state:SUSPENDED
"""
        opt.set_value(self.NEW_VAL)
        self.assertEqual(opt.get_config(), lines)
        lines = """; option_name
; -----------
;
; data type: SimpleDataclass
;
; [optional] description
;
option_name = <UNDEFINED>
"""
        opt.set_value(None)
        self.assertEqual(opt.get_config(), lines)

class TestPathOption(BaseConfigTest):
    "Unit tests for firebird.base.config.PathOption"
    PRESENT_VAL = Path('c:\\home\\present' if platform.system == 'Windows' else '/home/present')
    DEFAULT_VAL = Path('c:\\home\\default' if platform.system == 'Windows' else '/home/default')
    DEFAULT_OPT_VAL = Path('c:\\home\\default-opt' if platform.system == 'Windows' else '/home/default-opt')
    NEW_VAL = Path('c:\\home\\new' if platform.system == 'Windows' else '/home/new')
    def setUp(self):
        super().setUp()
        self.setConf(f"""[%(DEFAULT)s]
option_name = {self.DEFAULT_VAL}
[%(PRESENT)s]
option_name = {self.PRESENT_VAL}
[%(ABSENT)s]
[%(BAD)s]
option_name =
""")
    def test_simple(self):
        opt = config.PathOption('option_name', 'description')
        self.assertEqual(opt.name, 'option_name')
        self.assertEqual(opt.datatype, Path)
        self.assertEqual(opt.description, 'description')
        self.assertFalse(opt.required)
        self.assertIsNone(opt.default)
        self.assertIsNone(opt.value)
        opt.validate()
        opt.load_config(self.conf, PRESENT_S)
        self.assertEqual(opt.value, self.PRESENT_VAL)
        self.assertEqual(opt.get_formatted(), str(self.PRESENT_VAL))
        self.assertIsInstance(opt.value, opt.datatype)
        opt.clear()
        self.assertIsNone(opt.value)
        opt.load_config(self.conf, DEFAULT_S)
        self.assertEqual(opt.value, self.DEFAULT_VAL)
        self.assertIsInstance(opt.value, opt.datatype)
        opt.set_value(None)
        self.assertIsNone(opt.value)
        opt.load_config(self.conf, ABSENT_S)
        self.assertEqual(opt.value, self.DEFAULT_VAL)
        self.assertIsInstance(opt.value, opt.datatype)
        opt.set_value(self.NEW_VAL)
        self.assertEqual(opt.value, self.NEW_VAL)
        self.assertIsInstance(opt.value, opt.datatype)
    def test_required(self):
        opt = config.PathOption('option_name', 'description', required=True)
        self.assertEqual(opt.name, 'option_name')
        self.assertEqual(opt.datatype, Path)
        self.assertEqual(opt.description, 'description')
        self.assertTrue(opt.required)
        self.assertIsNone(opt.default)
        self.assertIsNone(opt.value)
        with self.assertRaises(Error) as cm:
            opt.validate()
        self.assertEqual(cm.exception.args, ("Missing value for required option 'option_name'",))
        opt.load_config(self.conf, PRESENT_S)
        self.assertEqual(opt.value, self.PRESENT_VAL)
        opt.validate()
        opt.clear()
        self.assertIsNone(opt.value)
        opt.load_config(self.conf, DEFAULT_S)
        self.assertEqual(opt.value, self.DEFAULT_VAL)
        with self.assertRaises(ValueError) as cm:
            opt.set_value(None)
        self.assertEqual(cm.exception.args, ("Value is required for option 'option_name'.",))
        opt.load_config(self.conf, ABSENT_S)
        self.assertEqual(opt.value, self.DEFAULT_VAL)
        opt.set_value(self.NEW_VAL)
        self.assertEqual(opt.value, self.NEW_VAL)
    def test_bad_value(self):
        opt = config.PathOption('option_name', 'description')
        opt.load_config(self.conf, BAD_S)
        self.assertEqual(opt.value, Path(''))
        with self.assertRaises(TypeError) as cm:
            opt.set_value(10.0)
        self.assertEqual(cm.exception.args, ("Option 'option_name' value must be a 'Path', not 'float'",))
    def test_default(self):
        opt = config.PathOption('option_name', 'description', default=self.DEFAULT_OPT_VAL)
        self.assertEqual(opt.name, 'option_name')
        self.assertEqual(opt.datatype, Path)
        self.assertEqual(opt.description, 'description')
        self.assertFalse(opt.required)
        self.assertEqual(opt.default, self.DEFAULT_OPT_VAL)
        self.assertIsInstance(opt.default, opt.datatype)
        self.assertEqual(opt.value, self.DEFAULT_OPT_VAL)
        self.assertIsInstance(opt.value, opt.datatype)
        opt.validate()
        opt.load_config(self.conf, PRESENT_S)
        self.assertEqual(opt.value, self.PRESENT_VAL)
        opt.clear()
        self.assertEqual(opt.value, opt.default)
        opt.load_config(self.conf, DEFAULT_S)
        self.assertEqual(opt.value, self.DEFAULT_VAL)
        opt.set_value(None)
        self.assertIsNone(opt.value)
        opt.load_config(self.conf, ABSENT_S)
        self.assertEqual(opt.value, self.DEFAULT_VAL)
        opt.set_value(self.NEW_VAL)
        self.assertEqual(opt.value, self.NEW_VAL)
    def test_proto(self):
        opt = config.PathOption('option_name', 'description', default=self.DEFAULT_OPT_VAL)
        proto_value = Path('c:\\home\\proto' if platform.system == 'Windows' else '/home/proto')
        opt.set_value(proto_value)
        self.proto.options['option_name'].as_string = str(proto_value)
        proto_dump = str(self.proto)
        opt.load_proto(self.proto)
        self.assertEqual(opt.value, proto_value)
        self.assertIsInstance(opt.value, opt.datatype)
        self.proto.Clear()
        self.assertFalse('option_name' in self.proto.options)
        opt.save_proto(self.proto)
        self.assertTrue('option_name' in self.proto.options)
        self.assertEqual(str(self.proto), proto_dump)
        # empty proto
        opt.clear(to_default=False)
        self.proto.Clear()
        opt.load_proto(self.proto)
        self.assertIsNone(opt.value)
        # bad proto value
        self.proto.options['option_name'].as_uint64 = 1000
        with self.assertRaises(TypeError) as cm:
            opt.load_proto(self.proto)
        self.assertEqual(cm.exception.args, ('Wrong value type: uint64',))
        self.proto.Clear()
        opt.clear(to_default=False)
        opt.save_proto(self.proto)
        self.assertFalse('option_name' in self.proto.options)
    def test_get_config(self):
        opt = config.PathOption('option_name', 'description', default=self.DEFAULT_OPT_VAL)
        lines = f"""; option_name
; -----------
;
; data type: Path
;
; [optional] description
;
;option_name = {self.DEFAULT_OPT_VAL}
"""
        self.assertEqual(opt.get_config(), lines)
        lines = f"""; option_name
; -----------
;
; data type: Path
;
; [optional] description
;
option_name = {self.NEW_VAL}
"""
        opt.set_value(self.NEW_VAL)
        self.assertEqual(opt.get_config(), lines)
        lines = """; option_name
; -----------
;
; data type: Path
;
; [optional] description
;
option_name = <UNDEFINED>
"""
        opt.set_value(None)
        self.assertEqual(opt.get_config(), lines)

class DbConfig(config.Config):
    "Simple DB config for testing"
    def __init__(self, name: str):
        super().__init__(name)
        # options
        self.database: config.StrOption = config.StrOption('database', 'Database connection string',
                                                           required=True)
        self.user: config.StrOption = config.StrOption('user', 'User name', required=True,
                                                       default='SYSDBA')
        self.password: config.StrOption = config.StrOption('password', 'User password')

class SimpleConfig(config.Config):
    """Simple Config for testing.

Has three options and two sub-configs.
"""
    def __init__(self):
        super().__init__('simple-config')
        # options
        self.opt_str: config.StrOption = config.StrOption('opt_str', "Simple string option")
        self.opt_int: config.IntOption = config.StrOption('opt_int', "Simple int option")
        self.enum_list: config.ListOption = config.ListOption('enum_list', SimpleEnum, "List of enum values")
        # sub configs
        self.master_db: DbConfig = DbConfig('master-db')
        self.backup_db: DbConfig = DbConfig('backup-db')

class TestConfig(BaseConfigTest):
    "Unit tests for firebird.base.config.Config"
    def setUp(self):
        super().setUp()
        self.setConf("""[%(DEFAULT)s]
password = masterkey
[%(PRESENT)s]
opt_str = Lorem ipsum
enum_list = ready, finished, aborted
[%(ABSENT)s]
[%(BAD)s]

[master-db]
database = primary
user = tester
password = lockpick

[backup-db]
database = secondary
""")
    def test_1_basics(self):
        cfg = SimpleConfig()
        self.assertEqual(cfg.name, 'simple-config')
        self.assertEqual(len(cfg.options), 3)
        self.assertIn(cfg.opt_str, cfg.options)
        self.assertIn(cfg.opt_int, cfg.options)
        self.assertIn(cfg.enum_list, cfg.options)
        self.assertEqual(len(cfg.configs), 2)
        self.assertIn(cfg.master_db, cfg.configs)
        self.assertIn(cfg.backup_db, cfg.configs)
        #
        self.assertIsNone(cfg.opt_str.value)
        self.assertIsNone(cfg.opt_int.value)
        self.assertIsNone(cfg.enum_list.value)
        self.assertIsNone(cfg.master_db.database.value)
        self.assertEqual(cfg.master_db.user.value, 'SYSDBA')
        self.assertIsNone(cfg.master_db.password.value)
        self.assertIsNone(cfg.backup_db.database.value)
        self.assertEqual(cfg.backup_db.user.value, 'SYSDBA')
        self.assertIsNone(cfg.backup_db.password.value)
    def test_2_load_config(self):
        cfg = SimpleConfig()
        #
        with self.assertRaises(Error):
            cfg.load_config(self.conf)
        #
        cfg.load_config(self.conf, PRESENT_S)
        self.assertEqual(cfg.opt_str.value, 'Lorem ipsum')
        self.assertIsNone(cfg.opt_int.value)
        self.assertListEqual(cfg.enum_list.value, [SimpleEnum.READY,
                                                   SimpleEnum.FINISHED,
                                                   SimpleEnum.ABORTED])
        #
        self.assertEqual(cfg.master_db.database.value, 'primary')
        self.assertEqual(cfg.master_db.user.value, 'tester')
        self.assertEqual(cfg.master_db.password.value, 'lockpick')
        #
        self.assertEqual(cfg.backup_db.database.value, 'secondary')
        self.assertEqual(cfg.backup_db.user.value, 'SYSDBA')
        self.assertEqual(cfg.backup_db.password.value, 'masterkey')
    def test_3_clear(self):
        cfg = SimpleConfig()
        cfg.load_config(self.conf, PRESENT_S)
        cfg.clear()
        #
        self.assertIsNone(cfg.opt_str.value)
        self.assertIsNone(cfg.opt_int.value)
        self.assertIsNone(cfg.enum_list.value)
        self.assertIsNone(cfg.master_db.database.value)
        self.assertEqual(cfg.master_db.user.value, 'SYSDBA')
        self.assertIsNone(cfg.master_db.password.value)
        self.assertIsNone(cfg.backup_db.database.value)
        self.assertEqual(cfg.backup_db.user.value, 'SYSDBA')
        self.assertIsNone(cfg.backup_db.password.value)
    def test_4_proto(self):
        cfg = SimpleConfig()
        cfg.load_config(self.conf, PRESENT_S)
        #
        cfg.save_proto(self.proto)
        cfg.clear()
        cfg.load_proto(self.proto)
        #
        self.assertEqual(cfg.opt_str.value, 'Lorem ipsum')
        self.assertIsNone(cfg.opt_int.value)
        self.assertListEqual(cfg.enum_list.value, [SimpleEnum.READY,
                                                   SimpleEnum.FINISHED,
                                                   SimpleEnum.ABORTED])
        #
        self.assertEqual(cfg.master_db.database.value, 'primary')
        self.assertEqual(cfg.master_db.user.value, 'tester')
        self.assertEqual(cfg.master_db.password.value, 'lockpick')
        #
        self.assertEqual(cfg.backup_db.database.value, 'secondary')
        self.assertEqual(cfg.backup_db.user.value, 'SYSDBA')
        self.assertEqual(cfg.backup_db.password.value, 'masterkey')
    def test_5_get_config(self):
        cfg = SimpleConfig()
        lines = """[simple-config]
;
; Simple Config for testing.
;
; Has three options and two sub-configs.
;

; opt_str
; -------
;
; data type: str
;
; [optional] Simple string option
;
;opt_str = <UNDEFINED>

; opt_int
; -------
;
; data type: str
;
; [optional] Simple int option
;
;opt_int = <UNDEFINED>

; enum_list
; ---------
;
; data type: list
;
; [optional] List of enum values
;
;enum_list = <UNDEFINED>

[master-db]
;
; Simple DB config for testing
;

; database
; --------
;
; data type: str
;
; [REQUIRED] Database connection string
;
;database = <UNDEFINED>

; user
; ----
;
; data type: str
;
; [REQUIRED] User name
;
;user = SYSDBA

; password
; --------
;
; data type: str
;
; [optional] User password
;
;password = <UNDEFINED>

[backup-db]
;
; Simple DB config for testing
;

; database
; --------
;
; data type: str
;
; [REQUIRED] Database connection string
;
;database = <UNDEFINED>

; user
; ----
;
; data type: str
;
; [REQUIRED] User name
;
;user = SYSDBA

; password
; --------
;
; data type: str
;
; [optional] User password
;
;password = <UNDEFINED>"""
        self.maxDiff = None
        self.assertEqual('\n'.join(x.strip() for x in cfg.get_config().splitlines()), lines)
        #
        cfg.load_config(self.conf, PRESENT_S)
        lines = """[simple-config]
;
; Simple Config for testing.
;
; Has three options and two sub-configs.
;

; opt_str
; -------
;
; data type: str
;
; [optional] Simple string option
;
opt_str = Lorem ipsum

; opt_int
; -------
;
; data type: str
;
; [optional] Simple int option
;
;opt_int = <UNDEFINED>

; enum_list
; ---------
;
; data type: list
;
; [optional] List of enum values
;
enum_list = READY, FINISHED, ABORTED

[master-db]
;
; Simple DB config for testing
;

; database
; --------
;
; data type: str
;
; [REQUIRED] Database connection string
;
database = primary

; user
; ----
;
; data type: str
;
; [REQUIRED] User name
;
user = tester

; password
; --------
;
; data type: str
;
; [optional] User password
;
password = lockpick

[backup-db]
;
; Simple DB config for testing
;

; database
; --------
;
; data type: str
;
; [REQUIRED] Database connection string
;
database = secondary

; user
; ----
;
; data type: str
;
; [REQUIRED] User name
;
;user = SYSDBA

; password
; --------
;
; data type: str
;
; [optional] User password
;
password = masterkey"""
        self.assertEqual('\n'.join(x.strip() for x in cfg.get_config().splitlines()), lines)

class TestApplicationDirScheme(BaseConfigTest):
    "Unit tests for firebird.base.config.ApplicationDirectoryScheme"
    _pd = 'c:\\ProgramData'
    _ap = 'C:\\Users\\username\\AppData'
    _lap = 'C:\\Users\\username\\AppData\\Local'
    app_name = 'test_app'
    def setUp(self):
        super().setUp()
    @mock.patch.dict(os.environ, {'%PROGRAMDATA%': _pd,
                                  '%LOCALAPPDATA%': _lap,
                                  '%APPDATA%': _ap})
    def test_01_widnows(self):
        if platform.system() != 'Windows':
            self.skipTest("Only for Windows")
        scheme = config.get_directory_scheme(self.app_name)
        # 'C:/Users/pavel/AppData/Local/test_app/tmp'
        self.assertEqual(scheme.config, Path('c:/ProgramData/test_app/config'))
        self.assertEqual(scheme.run_data, Path('c:/ProgramData/test_app/run'))
        self.assertEqual(scheme.logs, Path('c:/ProgramData/test_app/log'))
        self.assertEqual(scheme.data, Path('c:/ProgramData/test_app/data'))
        self.assertEqual(scheme.tmp, Path('~/AppData/Local/test_app/tmp').expanduser())
        self.assertEqual(scheme.cache, Path('c:/ProgramData/test_app/cache'))
        self.assertEqual(scheme.srv, Path('c:/ProgramData/test_app/srv'))
        self.assertEqual(scheme.user_config, Path('~/AppData/Local/test_app/config').expanduser())
        self.assertEqual(scheme.user_data, Path('~/AppData/Local/test_app/data').expanduser())
        self.assertEqual(scheme.user_sync, Path('~/AppData/Roaming/test_app').expanduser())
        self.assertEqual(scheme.user_cache, Path('~/AppData/Local/test_app/cache').expanduser())
    def test_02_linux(self):
        if platform.system() != 'Linux':
            self.skipTest("Only for Linux")
        scheme = config.get_directory_scheme(self.app_name)
        self.assertEqual(scheme.config, Path('/etc/test_app'))
        self.assertEqual(scheme.run_data, Path('/run/test_app'))
        self.assertEqual(scheme.logs, Path('/var/log/test_app'))
        self.assertEqual(scheme.data, Path('/var/lib/test_app'))
        self.assertEqual(scheme.tmp, Path('/var/tmp/test_app'))
        self.assertEqual(scheme.cache, Path('/var/cache/test_app'))
        self.assertEqual(scheme.srv, Path('/srv/test_app'))
        self.assertEqual(scheme.user_config, Path('~/.config/test_app').expanduser())
        self.assertEqual(scheme.user_data, Path('~/.local/share/test_app').expanduser())
        self.assertEqual(scheme.user_sync, Path('~/.local/sync/test_app').expanduser())
        self.assertEqual(scheme.user_cache, Path('~/.cache/test_app').expanduser())

if __name__ == '__main__':
    unittest_main()

#class TestFloatOption(BaseConfigTest):
    #"Unit tests for firebird.base.config.FloatOption"
    #def setUp(self):
        #super().setUp()
    #def test_simple(self):
        #pass
    #def test_required(self):
        #pass
    #def test_bad_value(self):
        #pass
    #def test_default(self):
        #pass
    #def test_proto(self):
        #pass
    #def test_get_config(self):
        #pass


    #print(f'{cm.exception.args}\n')
    #self.assertEqual(cm.exception.args, None)
