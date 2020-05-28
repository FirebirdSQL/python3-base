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
import os
from logging import getLogger, Formatter, lastResort, LogRecord
from firebird.base.types import *
from firebird.base.logging import LoggingManager, get_manager, get_logger, bind_logger, \
     traced, LogLevel, TraceFlag, BindFlag, LoggingIdMixin, install_null_logger, add_traced

class Namespace:
    "Simple Namespace"

DECORATED = Namespace()
DECORATED.name = 'DECORATED'

class BaseLoggingTest(unittest.TestCase):
    "Base class for logging unit tests"
    def __init__(self, methodName='runTest'):
        super().__init__(methodName)
        self._saved_trace: TraceFlag = None
        self.logger = getLogger()
        self.logger.setLevel(LogLevel.NOTSET)
        self.mngr: LoggingManager = get_manager()
        self.fmt: Formatter = Formatter("%(levelname)10s: [%(name)s] topic='%(topic)s' agent=%(agent)s context=%(context)s %(message)s")
        lastResort.setLevel(LogLevel.NOTSET)
    def setUp(self) -> None:
        self._saved_trace = self.mngr.trace
        self.mngr.clear()
        self.logger.handlers.clear()
        #lastResort.setFormatter(self.fmt)
        #self.logger.addHandler(lastResort)
    def tearDown(self):
        self.mngr.trace = self._saved_trace
        if 'FBASE_TRACE' in os.environ:
            del os.environ['FBASE_TRACE']
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
    def test_manager(self):
        self.assertEqual(__debug__, TraceFlag.ACTIVE in self.mngr.trace)
        self.mngr.trace ^= TraceFlag.ACTIVE
        self.assertEqual(__debug__, TraceFlag.ACTIVE not in self.mngr.trace)
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
        self.mngr.bind_logger(agent, ctx, LOG_AC)
        self.mngr.bind_logger(agent, ANY, LOG_AX)
        self.mngr.bind_logger(ANY, ctx, LOG_XC)
        # root logger unmasked
        with self.assertLogs(level='DEBUG') as log:
            get_logger(agent_B, ctx_B).debug('General:B-Agent:B-context')
        rec: LogRecord = log.records.pop(0)
        self.assertEqual(rec.name, 'root')
        # this will mask the root logger, we also test the `bind_logger()`
        bind_logger(ANY, ANY, LOG_XX)
        #
        self.assertTrue(BindFlag.ANY_AGENT in self.mngr.bindings)
        self.assertTrue(BindFlag.ANY_CTX in self.mngr.bindings)
        self.assertTrue(BindFlag.ANY_ANY in self.mngr.bindings)
        self.assertTrue(BindFlag.DIRECT in self.mngr.bindings)
        self.assertEqual(len(self.mngr.loggers), 4)
        self.assertEqual(len(self.mngr.topics), 1)
        self.assertEqual(self.mngr.topics[''], 4)
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
        self.mngr.bind_logger(agent, ctx, LOG_AC)
        self.mngr.bind_logger(agent, ANY, LOG_AX)
        self.mngr.bind_logger(ANY, ctx, LOG_XC)
        self.mngr.bind_logger(ANY, ANY, LOG_XX)
        #
        self.assertTrue(BindFlag.ANY_AGENT in self.mngr.bindings)
        self.assertTrue(BindFlag.ANY_CTX in self.mngr.bindings)
        self.assertTrue(BindFlag.ANY_ANY in self.mngr.bindings)
        self.assertTrue(BindFlag.DIRECT in self.mngr.bindings)
        self.assertEqual(len(self.mngr.loggers), 4)
        self.assertEqual(len(self.mngr.topics), 1)
        # Clear
        self.mngr.clear()
        self.assertFalse(BindFlag.ANY_AGENT in self.mngr.bindings)
        self.assertFalse(BindFlag.ANY_CTX in self.mngr.bindings)
        self.assertFalse(BindFlag.ANY_ANY in self.mngr.bindings)
        self.assertFalse(BindFlag.DIRECT in self.mngr.bindings)
        self.assertEqual(len(self.mngr.loggers), 0)
        self.assertEqual(len(self.mngr.topics), 0)
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
        self.mngr.bind_logger(agent, ctx, LOG_AC)
        self.mngr.bind_logger(agent, ANY, LOG_AX)
        self.mngr.bind_logger(ANY, ctx, LOG_XC)
        self.mngr.bind_logger(ANY, ANY, LOG_XX)
        #
        self.assertTrue(BindFlag.ANY_AGENT in self.mngr.bindings)
        self.assertTrue(BindFlag.ANY_CTX in self.mngr.bindings)
        self.assertTrue(BindFlag.ANY_ANY in self.mngr.bindings)
        self.assertTrue(BindFlag.DIRECT in self.mngr.bindings)
        self.assertEqual(len(self.mngr.loggers), 4)
        self.assertEqual(len(self.mngr.topics), 1)
        self.assertEqual(self.mngr.topics[''], 4)
        # Unbind
        # nothing to remove
        self.assertEqual(0, self.mngr.unbind(agent, ctx, 'trace'))
        self.assertEqual(0, self.mngr.unbind(agent, ctx_B))
        self.assertEqual(0, self.mngr.unbind(agent_B, ctx))
        # targeted
        self.assertEqual(1, self.mngr.unbind(ANY, ANY))
        self.assertTrue(BindFlag.ANY_AGENT in self.mngr.bindings)
        self.assertTrue(BindFlag.ANY_CTX in self.mngr.bindings)
        self.assertFalse(BindFlag.ANY_ANY in self.mngr.bindings)
        self.assertTrue(BindFlag.DIRECT in self.mngr.bindings)
        self.assertEqual(len(self.mngr.loggers), 3)
        self.assertEqual(self.mngr.topics[''], 3)
        # group (all agents for context)
        self.assertEqual(2, self.mngr.unbind(ALL, ctx))
        self.assertFalse(BindFlag.ANY_AGENT in self.mngr.bindings)
        self.assertTrue(BindFlag.ANY_CTX in self.mngr.bindings)
        self.assertFalse(BindFlag.ANY_ANY in self.mngr.bindings)
        self.assertFalse(BindFlag.DIRECT in self.mngr.bindings)
        self.assertEqual(len(self.mngr.loggers), 1)
        self.assertEqual(self.mngr.topics[''], 1)
        # rebind
        self.mngr.bind_logger(agent, ctx, LOG_AC)
        self.mngr.bind_logger(agent, ANY, LOG_AX)
        self.mngr.bind_logger(ANY, ctx, LOG_XC)
        self.mngr.bind_logger(ANY, ANY, LOG_XX)
        # group (all contexts for agent)
        self.assertEqual(2, self.mngr.unbind(agent, ALL))
        self.assertTrue(BindFlag.ANY_AGENT in self.mngr.bindings)
        self.assertTrue(BindFlag.ANY_CTX in self.mngr.bindings)
        self.assertTrue(BindFlag.ANY_ANY in self.mngr.bindings)
        self.assertFalse(BindFlag.DIRECT in self.mngr.bindings)
        self.assertEqual(len(self.mngr.loggers), 2)
        self.assertEqual(self.mngr.topics[''], 2)
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

class Traced(LoggingIdMixin):
    "traceable callables"
    def __init__(self, owner: BaseLoggingTest, logging_id: str=None):
        self.owner = owner
        if logging_id is not None:
            self._logging_id_ = logging_id
    def traced_noparam_noresult(self) -> None:
        getLogger().info('<traced_noparam_noresult>')
    def traced_noparam_result(self) -> str:
        getLogger().info('<traced_noparam_result>')
        return 'OK'
    def traced_param_noresult(self, pos_only, / , pos, kw='KW', *, kw_only='KW_ONLY') -> None:
        getLogger().info('<traced_param_noresult>')
    def traced_param_result(self, pos_only, / , pos, kw='KW', *, kw_only='KW_ONLY') -> str:
        getLogger().info('<traced_param_result>')
        return 'OK'
    def traced_long_result(self) -> str:
        getLogger().info('<traced_long_result>')
        return '0123456789' * 10
    def traced_raises(self) -> None:
        getLogger().info('<traced_raises>')
        raise Error("No cookies left")

class DecoratedTraced(LoggingIdMixin):
    "traceable callables"
    def __init__(self, owner: BaseLoggingTest, logging_id: str=None):
        self.owner = owner
        if logging_id is not None:
            self._logging_id_ = logging_id
    @traced()
    def traced_noparam_noresult(self) -> None:
        getLogger().info('<traced_noparam_noresult>')
    @traced()
    def traced_noparam_result(self) -> str:
        getLogger().info('<traced_noparam_result>')
        return 'OK'
    @traced()
    def traced_param_noresult(self, pos_only, / , pos, kw='KW', *, kw_only='KW_ONLY') -> None:
        getLogger().info('<traced_param_noresult>')
    @traced()
    def traced_param_result(self, pos_only, / , pos, kw='KW', *, kw_only='KW_ONLY') -> str:
        getLogger().info('<traced_param_result>')
        return 'OK'
    @traced()
    def traced_raises(self) -> None:
        getLogger().info('<traced_raises>')
        raise Error("No cookies left")


class TestTraced(BaseLoggingTest):
    """Unit tests for firebird.base.logging"""
    def setUp(self) -> None:
        super().setUp()
        if not __debug__:
            os.environ['FBASE_TRACE'] = 'on'
        self.mngr.trace |= TraceFlag.ACTIVE
    def verify_func(self, records, func_name: str, only: bool=False) -> None:
        if only:
            self.assertEqual(len(records), 1)
        else:
            self.assertGreaterEqual(len(records), 1)
        self.assertEqual(records.pop(0).message, f'<{func_name}>')
    def test_aaa(self):
        "Default settings only, events: FAIL"

        def verify(records, func_name, params: str='', result: str=None,
                   outcome: str=('log_failed', '<--')) -> None:
            self.assertGreaterEqual(len(records), 2)
            self.verify_func(records, func_name)
            rec = records.pop(0)
            self.assertEqual(rec.name, 'trace')
            self.assertEqual(rec.levelno, LogLevel.DEBUG)
            self.assertEqual(rec.args, ())
            self.assertEqual(rec.filename, 'logging.py')
            self.assertEqual(rec.module, 'logging')
            self.assertEqual(rec.funcName, outcome[0])
            self.assertEqual(rec.topic, 'trace')
            self.assertEqual(rec.agent, 'Traced')
            self.assertEqual(rec.context, UNDEFINED)
            self.assertTrue(rec.message.startswith(f'{outcome[1]} {func_name}'))
            self.assertTrue(rec.message.endswith(f'{result}'))

        self.assertEqual(self.mngr.trace, TraceFlag.ACTIVE | TraceFlag.FAIL)
        ctx = Traced(self)
        # traced_noparam_noresult
        with self.assertLogs(level='DEBUG') as log:
            traced()(ctx.traced_noparam_noresult)()
        self.verify_func(log.records, 'traced_noparam_noresult', True)
        # traced_noparam_result
        with self.assertLogs(level='DEBUG') as log:
            traced()(ctx.traced_noparam_result)()
        self.verify_func(log.records, 'traced_noparam_result', True)
        # traced_param_noresult
        with self.assertLogs(level='DEBUG') as log:
            traced()(ctx.traced_param_noresult)(1, 2, kw_only='NO-DEFAULT')
        self.verify_func(log.records, 'traced_param_noresult', True)
        # traced_param_noresult
        with self.assertLogs(level='DEBUG') as log:
            traced()(ctx.traced_param_result)(1, 2, kw_only='NO-DEFAULT')
        self.verify_func(log.records, 'traced_param_result', True)
        # traced_raises
        with self.assertLogs(level='DEBUG') as log:
            with self.assertRaises(Error):
                traced()(ctx.traced_raises)()
        verify(log.records, 'traced_raises', result='Error: No cookies left')
    def test_aab(self):
        "Default decorator settings, all events"
        def verify(records, func_name: str, params: str='', result: str='Result: None',
                   outcome: str=('log_after', '<<<')) -> None:
            self.assertEqual(len(records), 3)
            rec: LogRecord = records.pop(0)
            self.assertEqual(rec.name, 'trace')
            self.assertEqual(rec.levelno, LogLevel.DEBUG)
            self.assertEqual(rec.args, ())
            self.assertEqual(rec.filename, 'logging.py')
            self.assertEqual(rec.module, 'logging')
            self.assertEqual(rec.funcName, 'log_before')
            self.assertEqual(rec.topic, 'trace')
            self.assertEqual(rec.agent, 'Traced')
            self.assertEqual(rec.context, UNDEFINED)
            self.assertEqual(rec.message, f'>>> {func_name}({params})')
            #
            self.verify_func(records, func_name)
            #
            rec = records.pop(0)
            self.assertEqual(rec.name, 'trace')
            self.assertEqual(rec.levelno, LogLevel.DEBUG)
            self.assertEqual(rec.args, ())
            self.assertEqual(rec.filename, 'logging.py')
            self.assertEqual(rec.module, 'logging')
            self.assertEqual(rec.funcName, outcome[0])
            self.assertEqual(rec.topic, 'trace')
            self.assertEqual(rec.agent, 'Traced')
            self.assertEqual(rec.context, UNDEFINED)
            self.assertTrue(rec.message.startswith(f'{outcome[1]} {func_name}'))
            self.assertTrue(rec.message.endswith(f'{result}'))

        ctx = Traced(self)
        self.mngr.trace |= (TraceFlag.FAIL | TraceFlag.BEFORE | TraceFlag.AFTER)

        # traced_noparam_noresult
        with self.assertLogs(level='DEBUG') as log:
            traced()(ctx.traced_noparam_noresult)()
        verify(log.records, 'traced_noparam_noresult')
        # traced_noparam_result
        with self.assertLogs(level='DEBUG') as log:
            traced()(ctx.traced_noparam_result)()
        verify(log.records, 'traced_noparam_result', result='OK')
        # traced_param_noresult
        with self.assertLogs(level='DEBUG') as log:
            traced()(ctx.traced_param_noresult)(1, 2, kw_only='NO-DEFAULT')
        verify(log.records, 'traced_param_noresult', "pos_only=1, pos=2, kw='KW', kw_only='NO-DEFAULT'")
        # traced_param_noresult
        with self.assertLogs(level='DEBUG') as log:
            traced()(ctx.traced_param_result)(1, 2, kw_only='NO-DEFAULT')
        verify(log.records, 'traced_param_result', "pos_only=1, pos=2, kw='KW', kw_only='NO-DEFAULT'", 'OK')
        # traced_raises
        with self.assertLogs(level='DEBUG') as log:
            with self.assertRaises(Error):
                traced()(ctx.traced_raises)()
        verify(log.records, 'traced_raises', result='Error: No cookies left', outcome=('log_failed', '<--'))
    def test_custom_msg(self):
        def verify(records, msg_before: str, msg_after_start: str, msg_after_end: str='Result: None') -> None:
            self.assertEqual(len(records), 3)
            rec = records.pop(0)
            self.assertEqual(rec.message, msg_before)
            records.pop(0)
            rec = records.pop(0)
            self.assertTrue(rec.message.startswith(msg_after_start))
            self.assertTrue(rec.message.endswith(msg_after_end))

        ctx = Traced(self)
        self.mngr.trace |= (TraceFlag.FAIL | TraceFlag.BEFORE | TraceFlag.AFTER)
        #
        with self.assertLogs(level='DEBUG') as log:
            d = traced(msg_before='ENTER {_fname_} ({pos_only}, {pos}, {kw}, {kw_only})')
            d(ctx.traced_param_noresult)(1, 2, kw_only='NO-DEFAULT')
        verify(log.records, 'ENTER traced_param_noresult (1, 2, KW, NO-DEFAULT)', '<<< traced_param_noresult')
        with self.assertLogs(level='DEBUG') as log:
            d = traced(msg_after='EXIT {_fname_}: {_result_}')
            d(ctx.traced_param_noresult)(1, 2, kw_only='NO-DEFAULT')
        verify(log.records, ">>> traced_param_noresult(pos_only=1, pos=2, kw='KW', kw_only='NO-DEFAULT')",
               'EXIT traced_param_noresult: None', '')
        d = traced(msg_before='ENTER {_fname_} ({pos_only}, {pos}, {kw}, {kw_only})',
                   msg_after='EXIT {_fname_}: {_result_}')
        with self.assertLogs(level='DEBUG') as log:
            d(ctx.traced_param_noresult)(1, 2, kw_only='NO-DEFAULT')
        verify(log.records, 'ENTER traced_param_noresult (1, 2, KW, NO-DEFAULT)',
               'EXIT traced_param_noresult: None', '')
        with self.assertLogs(level='DEBUG') as log:
            d = traced(msg_before='ENTER {_fname_} ()',
                       msg_after='EXIT {_fname_}: {_result_}',
                       msg_failed='!!! {_fname_}: {_result_}')
            with self.assertRaises(Error):
                d(ctx.traced_raises)()
        verify(log.records, 'ENTER traced_raises ()',
               '!!! traced_raises: Error: No cookies left', '')
    def test_extra(self):
        def foo(bar=''):
            return f'Foo{bar}!'

        def verify(records, msg_before: str, msg_after: str) -> None:
            self.assertEqual(len(records), 3)
            self.assertEqual(records.pop(0).message, msg_before)
            records.pop(0)
            self.assertEqual(records.pop(0).message, msg_after)

        ctx = Traced(self)
        self.mngr.trace |= (TraceFlag.FAIL | TraceFlag.BEFORE | TraceFlag.AFTER)
        #
        with self.assertLogs(level='DEBUG') as log:
            d = traced(msg_before='>>> {_fname_} ({foo()}, {foo(kw)}, {foo(kw_only)})',
                       msg_after='<<< {_fname_}: {foo(_result_)}', extra={'foo': foo})
            d(ctx.traced_param_noresult)(1, 2, kw_only='bar')
        verify(log.records, '>>> traced_param_noresult (Foo!, FooKW!, Foobar!)',
               '<<< traced_param_noresult: FooNone!')
    def test_topic(self):
        def verify(records, topic: str) -> None:
            self.assertEqual(len(records), 3)
            self.assertEqual(records.pop(0).topic, topic)
            records.pop(0)
            self.assertEqual(records.pop(0).topic, topic)

        ctx = Traced(self)
        self.mngr.trace |= (TraceFlag.FAIL | TraceFlag.BEFORE | TraceFlag.AFTER)
        #
        with self.assertLogs(level='DEBUG') as log:
            traced(topic='fun')(ctx.traced_noparam_noresult)()
        verify(log.records, 'fun')
    def test_max_param_length(self):
        def verify(records, message: str, result: str='Result: OK') -> None:
            self.assertEqual(len(records), 3)
            self.assertEqual(records.pop(0).message, message)
            records.pop(0)
            self.assertTrue(records.pop(0).message.endswith(result))

        ctx = Traced(self)
        self.mngr.trace |= (TraceFlag.FAIL | TraceFlag.BEFORE | TraceFlag.AFTER)
        #
        with self.assertLogs(level='DEBUG') as log:
            traced(max_param_length=10)(ctx.traced_param_result)('123456789', '0123456789' * 10)
        verify(log.records, ">>> traced_param_result(pos_only='123456789', pos='0123456789..[90]', kw='KW', kw_only='KW_ONLY')")
        #
        with self.assertLogs(level='DEBUG') as log:
            traced(max_param_length=10)(ctx.traced_long_result)()
        verify(log.records, '>>> traced_long_result()', 'Result: 0123456789..[90]')
    def test_agent_ctx(self):
        def verify(records, agent, ctx) -> None:
            self.assertEqual(len(records), 3)
            rec = records.pop(0)
            self.assertEqual(rec.agent, agent)
            self.assertEqual(rec.context, ctx)
            records.pop(0)
            rec = records.pop(0)
            self.assertEqual(rec.agent, agent)
            self.assertEqual(rec.context, ctx)

        ctx = Traced(self)
        self.mngr.trace |= (TraceFlag.FAIL | TraceFlag.BEFORE | TraceFlag.AFTER)
        #
        with self.assertLogs(level='DEBUG') as log:
            traced(agent=UNDEFINED, context=UNDEFINED)(ctx.traced_noparam_noresult)()
        verify(log.records, UNDEFINED, UNDEFINED)
        ctx.log_context = '<CONTEXT>'
        ctx._logging_id_ = '<AGENT>'
        with self.assertLogs(level='DEBUG') as log:
            traced()(ctx.traced_noparam_noresult)()
        verify(log.records, '<AGENT>', '<CONTEXT>')
    def test_level(self):
        def verify(records, level) -> None:
            self.assertEqual(len(records), 3)
            self.assertEqual(records.pop(0).levelno, level)
            records.pop(0)
            self.assertEqual(records.pop(0).levelno, level)

        ctx = Traced(self)
        self.mngr.trace |= (TraceFlag.FAIL | TraceFlag.BEFORE | TraceFlag.AFTER)
        #
        with self.assertLogs(level='DEBUG') as log:
            traced(level=LogLevel.INFO)(ctx.traced_noparam_noresult)()
        verify(log.records, LogLevel.INFO)
    def test_forced(self):
        def verify(records, msg_before: str, msg_after_start: str, msg_after_end: str='Result: None') -> None:
            self.assertEqual(len(records), 3)
            rec = records.pop(0)
            self.assertEqual(rec.message, msg_before)
            records.pop(0)
            rec = records.pop(0)
            self.assertTrue(rec.message.startswith(msg_after_start))
            self.assertTrue(rec.message.endswith(msg_after_end))

        ctx = Traced(self)
        self.mngr.trace = (TraceFlag.FAIL | TraceFlag.BEFORE | TraceFlag.AFTER)
        with self.assertLogs(level='DEBUG') as log:
            traced()(ctx.traced_noparam_noresult)()
        self.verify_func(log.records, 'traced_noparam_noresult', True)
        #
        with self.assertLogs(level='DEBUG') as log:
            traced(flags=TraceFlag.ACTIVE)(ctx.traced_noparam_noresult)()
        verify(log.records, '>>> traced_noparam_noresult()', '<<< traced_noparam_noresult')
    def test_env(self):
        ctx = Traced(self)
        self.mngr.trace = (TraceFlag.ACTIVE | TraceFlag.FAIL | TraceFlag.BEFORE | TraceFlag.AFTER)
        with self.assertLogs(level='DEBUG') as log:
            traced()(ctx.traced_noparam_noresult)()
        self.assertEqual(len(log.records), 3)
        os.environ['FBASE_TRACE'] = 'off'
        with self.assertLogs(level='DEBUG') as log:
            traced()(ctx.traced_noparam_noresult)()
        self.verify_func(log.records, 'traced_noparam_noresult', True)
        del os.environ['FBASE_TRACE']
    def test_debug(self):
        if __debug__:
            self.skipTest("__debug__ is True")
        if 'FBASE_TRACE' in os.environ:
            del os.environ['FBASE_TRACE']
        ctx = Traced(self)
        self.mngr.trace = (TraceFlag.ACTIVE | TraceFlag.FAIL | TraceFlag.BEFORE | TraceFlag.AFTER)
        with self.assertLogs(level='DEBUG') as log:
            traced()(ctx.traced_noparam_noresult)()
        self.verify_func(log.records, 'traced_noparam_noresult', True)
    def test_decorated(self):
        "Default settings only, events: FAIL"

        def verify(records, func_name, params: str='', result: str=None,
                   outcome: str=('log_failed', '<--')) -> None:
            self.assertGreaterEqual(len(records), 2 if __debug__ else 1)
            self.verify_func(records, func_name)
            if __debug__:
                rec = records.pop(0)
                self.assertEqual(rec.name, 'trace')
                self.assertEqual(rec.levelno, LogLevel.DEBUG)
                self.assertEqual(rec.args, ())
                self.assertEqual(rec.filename, 'logging.py')
                self.assertEqual(rec.module, 'logging')
                self.assertEqual(rec.funcName, outcome[0])
                self.assertEqual(rec.topic, 'trace')
                self.assertEqual(rec.agent, 'DecoratedTraced')
                self.assertEqual(rec.context, UNDEFINED)
                self.assertTrue(rec.message.startswith(f'{outcome[1]} {func_name}'))
                self.assertTrue(rec.message.endswith(f'{result}'))

        self.assertEqual(self.mngr.trace, TraceFlag.ACTIVE | TraceFlag.FAIL)
        ctx = DecoratedTraced(self)
        # traced_noparam_noresult
        with self.assertLogs(level='DEBUG') as log:
            ctx.traced_noparam_noresult()
        self.verify_func(log.records, 'traced_noparam_noresult', True)
        # traced_noparam_result
        with self.assertLogs(level='DEBUG') as log:
            ctx.traced_noparam_result()
        self.verify_func(log.records, 'traced_noparam_result', True)
        # traced_param_noresult
        with self.assertLogs(level='DEBUG') as log:
            ctx.traced_param_noresult(1, 2, kw_only='NO-DEFAULT')
        self.verify_func(log.records, 'traced_param_noresult', True)
        # traced_param_noresult
        with self.assertLogs(level='DEBUG') as log:
            ctx.traced_param_result(1, 2, kw_only='NO-DEFAULT')
        self.verify_func(log.records, 'traced_param_result', True)
        # traced_raises
        with self.assertLogs(level='DEBUG') as log:
            with self.assertRaises(Error):
                ctx.traced_raises()
        verify(log.records, 'traced_raises', result='Error: No cookies left')
    def test_add_traced(self):
        "Default settings only, events: FAIL"

        def verify(records, func_name, params: str='', result: str=None,
                   outcome: str=('log_failed', '<--')) -> None:
            self.assertGreaterEqual(len(records), 2)
            self.verify_func(records, func_name)
            rec = records.pop(0)
            self.assertEqual(rec.name, 'trace')
            self.assertEqual(rec.levelno, LogLevel.DEBUG)
            self.assertEqual(rec.args, ())
            self.assertEqual(rec.filename, 'logging.py')
            self.assertEqual(rec.module, 'logging')
            self.assertEqual(rec.funcName, outcome[0])
            self.assertEqual(rec.topic, 'trace')
            self.assertEqual(rec.agent, 'Traced')
            self.assertEqual(rec.context, UNDEFINED)
            self.assertTrue(rec.message.startswith(f'{outcome[1]} {func_name}'))
            self.assertTrue(rec.message.endswith(f'{result}'))

        self.assertEqual(self.mngr.trace, TraceFlag.ACTIVE | TraceFlag.FAIL)
        ctx = Traced(self)
        add_traced(ctx, 'traced_noparam_noresult')
        add_traced(ctx, 'traced_noparam_result')
        add_traced(ctx, 'traced_param_noresult')
        add_traced(ctx, 'traced_param_result')
        add_traced(ctx, 'traced_raises')
        # traced_noparam_noresult
        with self.assertLogs(level='DEBUG') as log:
            ctx.traced_noparam_noresult()
        self.verify_func(log.records, 'traced_noparam_noresult', True)
        # traced_noparam_result
        with self.assertLogs(level='DEBUG') as log:
            ctx.traced_noparam_result()
        self.verify_func(log.records, 'traced_noparam_result', True)
        # traced_param_noresult
        with self.assertLogs(level='DEBUG') as log:
            ctx.traced_param_noresult(1, 2, kw_only='NO-DEFAULT')
        self.verify_func(log.records, 'traced_param_noresult', True)
        # traced_param_result
        with self.assertLogs(level='DEBUG') as log:
            ctx.traced_param_result(1, 2, kw_only='NO-DEFAULT')
        self.verify_func(log.records, 'traced_param_result', True)
        # traced_raises
        with self.assertLogs(level='DEBUG') as log:
            with self.assertRaises(Error):
                traced()(ctx.traced_raises)()
        verify(log.records, 'traced_raises', result='Error: No cookies left')


if __name__ == '__main__':
    unittest.main()
