#!/usr/bin/python
#coding:utf-8
#
# PROGRAM/MODULE: firebird-base
# FILE:           test/test_logging.py
# DESCRIPTION:    Unit tests for firebird.base.logging
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

"""firebird-base - Unit tests for firebird.base.logging
"""

from __future__ import annotations
import unittest
from logging import getLogger, Formatter, lastResort, LogRecord
from firebird.base.types import *
from firebird.base.logging import logging_manager, get_logger, bind_logger, \
     LogLevel, BindFlag, install_null_logger

class Namespace:
    "Simple Namespace"

DECORATED = Namespace()
DECORATED.name = 'DECORATED'

class BaseLoggingTest(unittest.TestCase):
    "Base class for logging unit tests"
    def __init__(self, methodName='runTest'):
        super().__init__(methodName)
        self.logger = getLogger()
        self.logger.setLevel(LogLevel.NOTSET)
        self.fmt: Formatter = Formatter("%(levelname)10s: [%(name)s] topic='%(topic)s' agent=%(agent)s context=%(context)s %(message)s")
        lastResort.setLevel(LogLevel.NOTSET)
    def setUp(self) -> None:
        logging_manager.clear()
        self.logger.handlers.clear()
        #lastResort.setFormatter(self.fmt)
        #self.logger.addHandler(lastResort)
    def tearDown(self):
        pass
    def show(self, records, attrs=None):
        while records:
            item = records.pop(0)
            try:
                print({k: v for k, v in vars(item).items() if attrs is None or k in attrs})
            except:
                print(item)

class TestLogging(BaseLoggingTest):
    """Unit tests for firebird.base.logging"""
    def test_module(self):
        self.assertIsNotNone(lastResort)
        self.assertIsNotNone(lastResort.formatter)
    def test_aaa(self):
        # root
        with self.assertLogs() as log:
            get_logger(self).info('Message')
        rec: LogRecord = log.records.pop(0)
        self.assertEqual(rec.name, 'root')
        self.assertEqual(rec.levelno, LogLevel.INFO)
        self.assertEqual(rec.args, ())
        self.assertEqual(rec.module, 'test_logging')
        self.assertEqual(rec.filename, 'test_logging.py')
        self.assertEqual(rec.funcName, 'test_aaa')
        self.assertEqual(rec.topic, '')
        self.assertEqual(rec.agent, 'test_aaa (test_logging.TestLogging)')
        self.assertEqual(rec.context, UNDEFINED)
        self.assertEqual(rec.message, 'Message')
        # trace
        with self.assertLogs() as log:
            get_logger(self, topic='trace').info('Message')
        rec = log.records.pop(0)
        self.assertEqual(rec.name, 'trace')
        self.assertEqual(rec.levelno, LogLevel.INFO)
        self.assertEqual(rec.args, ())
        self.assertEqual(rec.module, 'test_logging')
        self.assertEqual(rec.filename, 'test_logging.py')
        self.assertEqual(rec.funcName, 'test_aaa')
        self.assertEqual(rec.topic, 'trace')
        self.assertEqual(rec.agent, 'test_aaa (test_logging.TestLogging)')
        self.assertEqual(rec.context, UNDEFINED)
        self.assertEqual(rec.message, 'Message')
    def test_interpolation(self):
        data = ['interpolation', 'breakdown', 'overflow']
        # Using keyword arguments
        with self.assertLogs() as log:
            get_logger(self).info('Information {data}', data=data[0])
        rec: LogRecord = log.records.pop(0)
        self.assertEqual(rec.message, 'Information interpolation')
        # Using positional dictionary
        with self.assertLogs() as log:
            get_logger(self).info('Information {data}', {'data': data[1]})
        rec = log.records.pop(0)
        self.assertEqual(rec.message, 'Information breakdown')
        # Using positional args
        with self.assertLogs() as log:
            get_logger(self).info('Information {args[0][2]}', data)
        rec = log.records.pop(0)
        self.assertEqual(rec.message, 'Information overflow')
    def test_bind(self):
        LOG_AC = 'test.agent.ctx'
        LOG_AX = 'test.agent.ANY'
        LOG_XC = 'test.ANY.ctx'
        LOG_XX = 'test.ANY.ANY'
        ctx = Namespace()
        ctx.logging_id = 'CONTEXT'
        ctx_B = Namespace()
        ctx_B.logging_id = 'B-CONTEXT'
        agent = Namespace()
        agent.logging_id = 'AGENT'
        agent_B = Namespace()
        agent_B.logging_id = 'B-AGENT'
        #
        logging_manager.bind_logger(agent, ctx, LOG_AC)
        logging_manager.bind_logger(agent, ANY, LOG_AX)
        logging_manager.bind_logger(ANY, ctx, LOG_XC)
        # root logger unmasked
        with self.assertLogs(level='DEBUG') as log:
            get_logger(agent_B, ctx_B).debug('General:B-Agent:B-context')
        rec: LogRecord = log.records.pop(0)
        self.assertEqual(rec.name, 'root')
        # this will mask the root logger, we also test the `bind_logger()`
        bind_logger(ANY, ANY, LOG_XX)
        #
        self.assertTrue(BindFlag.ANY_AGENT in logging_manager.bindings)
        self.assertTrue(BindFlag.ANY_CTX in logging_manager.bindings)
        self.assertTrue(BindFlag.ANY_ANY in logging_manager.bindings)
        self.assertTrue(BindFlag.DIRECT in logging_manager.bindings)
        self.assertEqual(len(logging_manager.loggers), 4)
        self.assertEqual(len(logging_manager.topics), 1)
        self.assertEqual(logging_manager.topics[''], 4)
        #
        with self.assertLogs(level='DEBUG') as log:
            get_logger(agent, ctx).debug('General:Agent:Context')
        rec = log.records.pop(0)
        self.assertEqual(rec.name, LOG_AC)
        #
        with self.assertLogs(level='DEBUG') as log:
            get_logger(agent, ctx_B).debug('General:Agent:B-context')
        rec = log.records.pop(0)
        self.assertEqual(rec.name, LOG_AX)
        #
        with self.assertLogs(level='DEBUG') as log:
            get_logger(agent, ANY).debug('General:Agent:ANY')
        rec = log.records.pop(0)
        self.assertEqual(rec.name, LOG_AX)
        #
        with self.assertLogs(level='DEBUG') as log:
            get_logger(agent).debug('General:Agent:UNDEFINED')
        rec = log.records.pop(0)
        self.assertEqual(rec.name, LOG_AX)
        #
        with self.assertLogs(level='DEBUG') as log:
            get_logger(agent_B, ctx).debug('General:B-Agent:Context')
        rec = log.records.pop(0)
        self.assertEqual(rec.name, LOG_XC)
        #
        with self.assertLogs(level='DEBUG') as log:
            get_logger(context=ctx).debug('General:UNDEFINED:Context')
        rec = log.records.pop(0)
        self.assertEqual(rec.name, LOG_XC)
        #
        with self.assertLogs(level='DEBUG') as log:
            get_logger(agent_B, ctx_B).debug('General:B-Agent:B-context')
        rec = log.records.pop(0)
        self.assertEqual(rec.name, LOG_XX)
        #
        with self.assertLogs(level='DEBUG') as log:
            get_logger().debug('General:UNDEFINED:UNDEFINED')
        rec = log.records.pop(0)
        self.assertEqual(rec.name, LOG_XX)
    def test_clear(self):
        LOG_AC = 'test.agent.ctx'
        LOG_AX = 'test.agent.ANY'
        LOG_XC = 'test.ANY.ctx'
        LOG_XX = 'test.ANY.ANY'
        ctx = Namespace()
        ctx.logging_id = 'CONTEXT'
        agent = Namespace()
        agent.logging_id = 'AGENT'
        #
        logging_manager.bind_logger(agent, ctx, LOG_AC)
        logging_manager.bind_logger(agent, ANY, LOG_AX)
        logging_manager.bind_logger(ANY, ctx, LOG_XC)
        logging_manager.bind_logger(ANY, ANY, LOG_XX)
        #
        self.assertTrue(BindFlag.ANY_AGENT in logging_manager.bindings)
        self.assertTrue(BindFlag.ANY_CTX in logging_manager.bindings)
        self.assertTrue(BindFlag.ANY_ANY in logging_manager.bindings)
        self.assertTrue(BindFlag.DIRECT in logging_manager.bindings)
        self.assertEqual(len(logging_manager.loggers), 4)
        self.assertEqual(len(logging_manager.topics), 1)
        # Clear
        logging_manager.clear()
        self.assertFalse(BindFlag.ANY_AGENT in logging_manager.bindings)
        self.assertFalse(BindFlag.ANY_CTX in logging_manager.bindings)
        self.assertFalse(BindFlag.ANY_ANY in logging_manager.bindings)
        self.assertFalse(BindFlag.DIRECT in logging_manager.bindings)
        self.assertEqual(len(logging_manager.loggers), 0)
        self.assertEqual(len(logging_manager.topics), 0)
    def test_unbind(self):
        LOG_AC = 'test.agent.ctx'
        LOG_AX = 'test.agent.ANY'
        LOG_XC = 'test.ANY.ctx'
        LOG_XX = 'test.ANY.ANY'
        ctx = Namespace()
        ctx.logging_id = 'CONTEXT'
        ctx_B = Namespace()
        ctx_B.logging_id = 'B-CONTEXT'
        agent = Namespace()
        agent.logging_id = 'AGENT'
        agent_B = Namespace()
        agent_B.logging_id = 'B-AGENT'
        #
        logging_manager.bind_logger(agent, ctx, LOG_AC)
        logging_manager.bind_logger(agent, ANY, LOG_AX)
        logging_manager.bind_logger(ANY, ctx, LOG_XC)
        logging_manager.bind_logger(ANY, ANY, LOG_XX)
        #
        self.assertTrue(BindFlag.ANY_AGENT in logging_manager.bindings)
        self.assertTrue(BindFlag.ANY_CTX in logging_manager.bindings)
        self.assertTrue(BindFlag.ANY_ANY in logging_manager.bindings)
        self.assertTrue(BindFlag.DIRECT in logging_manager.bindings)
        self.assertEqual(len(logging_manager.loggers), 4)
        self.assertEqual(len(logging_manager.topics), 1)
        self.assertEqual(logging_manager.topics[''], 4)
        # Unbind
        # nothing to remove
        self.assertEqual(0, logging_manager.unbind(agent, ctx, 'trace'))
        self.assertEqual(0, logging_manager.unbind(agent, ctx_B))
        self.assertEqual(0, logging_manager.unbind(agent_B, ctx))
        # targeted
        self.assertEqual(1, logging_manager.unbind(ANY, ANY))
        self.assertTrue(BindFlag.ANY_AGENT in logging_manager.bindings)
        self.assertTrue(BindFlag.ANY_CTX in logging_manager.bindings)
        self.assertFalse(BindFlag.ANY_ANY in logging_manager.bindings)
        self.assertTrue(BindFlag.DIRECT in logging_manager.bindings)
        self.assertEqual(len(logging_manager.loggers), 3)
        self.assertEqual(logging_manager.topics[''], 3)
        # group (all agents for context)
        self.assertEqual(2, logging_manager.unbind(ALL, ctx))
        self.assertFalse(BindFlag.ANY_AGENT in logging_manager.bindings)
        self.assertTrue(BindFlag.ANY_CTX in logging_manager.bindings)
        self.assertFalse(BindFlag.ANY_ANY in logging_manager.bindings)
        self.assertFalse(BindFlag.DIRECT in logging_manager.bindings)
        self.assertEqual(len(logging_manager.loggers), 1)
        self.assertEqual(logging_manager.topics[''], 1)
        # rebind
        logging_manager.bind_logger(agent, ctx, LOG_AC)
        logging_manager.bind_logger(agent, ANY, LOG_AX)
        logging_manager.bind_logger(ANY, ctx, LOG_XC)
        logging_manager.bind_logger(ANY, ANY, LOG_XX)
        # group (all contexts for agent)
        self.assertEqual(2, logging_manager.unbind(agent, ALL))
        self.assertTrue(BindFlag.ANY_AGENT in logging_manager.bindings)
        self.assertTrue(BindFlag.ANY_CTX in logging_manager.bindings)
        self.assertTrue(BindFlag.ANY_ANY in logging_manager.bindings)
        self.assertFalse(BindFlag.DIRECT in logging_manager.bindings)
        self.assertEqual(len(logging_manager.loggers), 2)
        self.assertEqual(logging_manager.topics[''], 2)
    def test_null_logger(self):
        with self.assertLogs() as log:
            get_logger(self).info('Message')
        rec: LogRecord = log.records.pop(0)
        self.assertEqual(rec.message, 'Message')
        install_null_logger()
        bind_logger(ANY, ANY, 'null')
        with self.assertRaises(AssertionError) as cm:
            with self.assertLogs() as log:
                get_logger(self).info('Message')
        self.assertEqual(cm.exception.args, ("no logs of level INFO or higher triggered on root",))

if __name__ == '__main__':
    unittest.main()
