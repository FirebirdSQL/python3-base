# SPDX-FileCopyrightText: 2020-present The Firebird Projects <www.firebirdsql.org>
#
# SPDX-License-Identifier: MIT
#
# PROGRAM/MODULE: firebird-base
# FILE:           test/test_trace.py
# DESCRIPTION:    Tests for firebird.base.trace
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

from __future__ import annotations

import os
from logging import Formatter, LogRecord, getLogger, lastResort

import pytest

from firebird.base.logging import LogLevel, get_agent_name, logging_manager
from firebird.base.strconv import convert_from_str
from firebird.base.trace import TracedMixin, TraceFlag, add_trace, trace_manager, traced
from firebird.base.types import *

## TODO:
#
# - TraceManager.trace_active (get/set)
# - Trace Config
# - TraceManager.trace_object
# - TraceManager.remove_trace
# - TraceManager.is_registered
# - traced: set_before_msg without args
# - __debug__ False: traced, TraceManager

class Namespace:
    "Simple Namespace"

DECORATED = Namespace()
DECORATED.name = "DECORATED"

class Traced(TracedMixin):
    "traceable callables"
    def __init__(self, logging_id: str=None):
        if logging_id is not None:
            self._agent_name_ = logging_id
    def traced_noparam_noresult(self) -> None:
        getLogger().info("<traced_noparam_noresult>")
    def traced_noparam_result(self) -> str:
        getLogger().info("<traced_noparam_result>")
        return "OK"
    def traced_param_noresult(self, pos_only, / , pos, kw="KW", *, kw_only="KW_ONLY") -> None:
        getLogger().info("<traced_param_noresult>")
    def traced_param_result(self, pos_only, / , pos, kw="KW", *, kw_only="KW_ONLY") -> str:
        getLogger().info("<traced_param_result>")
        return "OK"
    def traced_long_result(self) -> str:
        getLogger().info("<traced_long_result>")
        return "0123456789" * 10
    def traced_raises(self) -> None:
        getLogger().info("<traced_raises>")
        raise Error("No cookies left")

class DecoratedTraced:
    "traceable callables"
    def __init__(self, logging_id: str=None):
        if logging_id is not None:
            self._agent_name_ = logging_id
    @traced()
    def traced_noparam_noresult(self) -> None:
        getLogger().info("<traced_noparam_noresult>")
    @traced()
    def traced_noparam_result(self) -> str:
        getLogger().info("<traced_noparam_result>")
        return "OK"
    @traced()
    def traced_param_noresult(self, pos_only, / , pos, kw="KW", *, kw_only="KW_ONLY") -> None:
        getLogger().info("<traced_param_noresult>")
    @traced()
    def traced_param_result(self, pos_only, / , pos, kw="KW", *, kw_only="KW_ONLY") -> str:
        getLogger().info("<traced_param_result>")
        return "OK"
    @traced()
    def traced_raises(self) -> None:
        getLogger().info("<traced_raises>")
        raise Error("No cookies left")


@pytest.fixture(autouse=True)
def ensure_trace(monkeypatch):
    if not __debug__:
        monkeypatch.setenv("FBASE_TRACE", "on")
    logging_manager.logger_fmt = ["trace"]
    #
    trace_manager.clear()
    trace_manager.decorator = traced
    trace_manager._traced.clear()
    trace_manager._flags = TraceFlag.NONE
    trace_manager.trace_active = convert_from_str(bool, os.getenv("FBASE_TRACE", str(__debug__)))
    if convert_from_str(bool, os.getenv("FBASE_TRACE_BEFORE", "no")): # pragma: no cover
        trace_manager.set_flag(TraceFlag.BEFORE)
    if convert_from_str(bool, os.getenv("FBASE_TRACE_AFTER", "no")): # pragma: no cover
        trace_manager.set_flag(TraceFlag.AFTER)
    if convert_from_str(bool, os.getenv("FBASE_TRACE_FAIL", "yes")):
        trace_manager.set_flag(TraceFlag.FAIL)
    #
    trace_manager.register(Traced)

def verify_func(records, func_name: str, only: bool=False) -> None:
    if only:
        assert len(records) == 1
    else:
        assert len(records) >= 1
    assert records.pop(0).message == f"<{func_name}>"

def test_aaa(caplog):
    "Default settings only, events: FAIL"

    def verify(records, func_name, params: str="", result: str=None,
               outcome: str=("log_failed", "<--")) -> None:
        assert len(records) >= 2
        verify_func(records, func_name)
        rec = records.pop(0)
        assert rec.name == "trace"
        assert rec.levelno == LogLevel.DEBUG
        assert rec.args == ()
        assert rec.filename == "trace.py"
        assert rec.module == "trace"
        assert rec.funcName == outcome[0]
        assert rec.topic == "trace"
        assert rec.agent == get_agent_name(ctx)
        assert rec.context is None
        assert rec.message.startswith(f"{outcome[1]} {func_name}")
        assert rec.message.endswith(f"{result}")

    assert trace_manager.flags == TraceFlag.ACTIVE | TraceFlag.FAIL
    ctx = Traced()
    # traced_noparam_noresult
    with caplog.at_level(level="DEBUG"):
        traced()(ctx.traced_noparam_noresult)()
    verify_func(caplog.records, "traced_noparam_noresult", True)
    # traced_noparam_result
    with caplog.at_level(level="DEBUG"):
        traced()(ctx.traced_noparam_result)()
    verify_func(caplog.records, "traced_noparam_result", True)
    # traced_param_noresult
    with caplog.at_level(level="DEBUG"):
        traced()(ctx.traced_param_noresult)(1, 2, kw_only="NO-DEFAULT")
    verify_func(caplog.records, "traced_param_noresult", True)
    # traced_param_noresult
    with caplog.at_level(level="DEBUG"):
        traced()(ctx.traced_param_result)(1, 2, kw_only="NO-DEFAULT")
    verify_func(caplog.records, "traced_param_result", True)
    # traced_raises
    with caplog.at_level(level="DEBUG"):
        with pytest.raises(Error):
            traced()(ctx.traced_raises)()
    verify(caplog.records, "traced_raises", result="Error: No cookies left")

def test_aab(caplog):
    "Default decorator settings, all events"
    def verify(records, func_name: str, params: str="", result: str="",
               outcome: str=("log_after", "<<<")) -> None:
        assert len(records) == 3
        rec: LogRecord = records.pop(0)
        assert rec.name == "trace"
        assert rec.levelno == LogLevel.DEBUG
        assert rec.args == ()
        assert rec.filename == "trace.py"
        assert rec.module == "trace"
        assert rec.funcName == "log_before"
        assert rec.topic == "trace"
        assert rec.agent == get_agent_name(ctx)
        assert rec.context is None
        assert rec.message == f">>> {func_name}({params})"
        #
        verify_func(records, func_name)
        #
        rec = records.pop(0)
        assert rec.name == "trace"
        assert rec.levelno == LogLevel.DEBUG
        assert rec.args == ()
        assert rec.filename == "trace.py"
        assert rec.module == "trace"
        assert rec.funcName == outcome[0]
        assert rec.topic == "trace"
        assert rec.agent == get_agent_name(ctx)
        assert rec.context is None
        assert rec.message.startswith(f"{outcome[1]} {func_name}")
        assert rec.message.endswith(f"{result}")

    ctx = Traced()
    trace_manager.flags |= (TraceFlag.FAIL | TraceFlag.BEFORE | TraceFlag.AFTER)

    # traced_noparam_noresult
    with caplog.at_level(level="DEBUG"):
        traced()(ctx.traced_noparam_noresult)()
    verify(caplog.records, "traced_noparam_noresult")
    # traced_noparam_result
    with caplog.at_level(level="DEBUG"):
        traced()(ctx.traced_noparam_result)()
    verify(caplog.records, "traced_noparam_result", result="'OK'")
    # traced_param_noresult
    with caplog.at_level(level="DEBUG"):
        traced()(ctx.traced_param_noresult)(1, 2, kw_only="NO-DEFAULT")
    verify(caplog.records, "traced_param_noresult", "pos_only=1, pos=2, kw='KW', kw_only='NO-DEFAULT'")
    # traced_param_noresult
    with caplog.at_level(level="DEBUG"):
        traced()(ctx.traced_param_result)(1, 2, kw_only="NO-DEFAULT")
    verify(caplog.records, "traced_param_result", "pos_only=1, pos=2, kw='KW', kw_only='NO-DEFAULT'", "'OK'")
    # traced_raises
    with caplog.at_level(level="DEBUG"):
        with pytest.raises(Error):
            traced()(ctx.traced_raises)()
    verify(caplog.records, "traced_raises", result="Error: No cookies left", outcome=("log_failed", "<--"))

def test_custom_msg(caplog):
    def verify(records, msg_before: str, msg_after_start: str, msg_after_end: str="") -> None:
        assert len(records) == 3
        rec = records.pop(0)
        assert rec.message == msg_before
        records.pop(0)
        rec = records.pop(0)
        assert rec.message.startswith(msg_after_start)
        assert rec.message.endswith(msg_after_end)

    ctx = Traced()
    trace_manager.flags |= (TraceFlag.FAIL | TraceFlag.BEFORE | TraceFlag.AFTER)
    #
    with caplog.at_level(level="DEBUG"):
        d = traced(msg_before="ENTER {_fname_} ({pos_only}, {pos}, {kw}, {kw_only})")
        d(ctx.traced_param_noresult)(1, 2, kw_only="NO-DEFAULT")
    verify(caplog.records, "ENTER traced_param_noresult (1, 2, KW, NO-DEFAULT)", "<<< traced_param_noresult")
    with caplog.at_level(level="DEBUG"):
        d = traced(msg_after="EXIT {_fname_}: {_result_}")
        d(ctx.traced_param_noresult)(1, 2, kw_only="NO-DEFAULT")
    verify(caplog.records, ">>> traced_param_noresult(pos_only=1, pos=2, kw='KW', kw_only='NO-DEFAULT')",
           "EXIT traced_param_noresult: None", "")
    d = traced(msg_before="ENTER {_fname_} ({pos_only}, {pos}, {kw}, {kw_only})",
               msg_after="EXIT {_fname_}: {_result_}")
    with caplog.at_level(level="DEBUG"):
        d(ctx.traced_param_noresult)(1, 2, kw_only="NO-DEFAULT")
    verify(caplog.records, "ENTER traced_param_noresult (1, 2, KW, NO-DEFAULT)",
           "EXIT traced_param_noresult: None", "")
    with caplog.at_level(level="DEBUG"):
        d = traced(msg_before="ENTER {_fname_} ()",
                   msg_after="EXIT {_fname_}: {_result_}",
                   msg_failed="!!! {_fname_}: {_exc_}")
        with pytest.raises(Error):
            d(ctx.traced_raises)()
    verify(caplog.records, "ENTER traced_raises ()",
           "!!! traced_raises: Error: No cookies left", "")

def test_extra(caplog):
    def foo(bar=""):
        return f"Foo{bar}!"

    def verify(records, msg_before: str, msg_after: str) -> None:
        assert len(records) == 3
        assert records.pop(0).message == msg_before
        records.pop(0)
        assert records.pop(0).message == msg_after

    ctx = Traced()
    trace_manager.flags |= (TraceFlag.FAIL | TraceFlag.BEFORE | TraceFlag.AFTER)
    #
    with caplog.at_level(level="DEBUG"):
        d = traced(msg_before=">>> {_fname_} ({foo()}, {foo(kw)}, {foo(kw_only)})",
                   msg_after="<<< {_fname_}: {foo(_result_)}", extra={"foo": foo})
        d(ctx.traced_param_noresult)(1, 2, kw_only="bar")
    verify(caplog.records, ">>> traced_param_noresult (Foo!, FooKW!, Foobar!)",
           "<<< traced_param_noresult: FooNone!")

def test_topic(caplog):
    def verify(records, topic: str) -> None:
        assert len(records) == 3
        assert records.pop(0).topic == topic
        records.pop(0)
        assert records.pop(0).topic == topic

    ctx = Traced()
    trace_manager.flags |= (TraceFlag.FAIL | TraceFlag.BEFORE | TraceFlag.AFTER)
    #
    with caplog.at_level(level="DEBUG"):
        traced(topic="fun")(ctx.traced_noparam_noresult)()
    verify(caplog.records, "fun")

def test_max_param_length(caplog):
    def verify(records, message: str, result: str="Result: 'OK'") -> None:
        assert len(records) == 3
        assert records.pop(0).message == message
        records.pop(0)
        assert records.pop(0).message.endswith(result)

    ctx = Traced()
    trace_manager.flags |= (TraceFlag.FAIL | TraceFlag.BEFORE | TraceFlag.AFTER)
    #
    with caplog.at_level(level="DEBUG"):
        traced(max_param_length=10)(ctx.traced_param_result)("123456789", "0123456789" * 10)
    verify(caplog.records, ">>> traced_param_result(pos_only='123456789', pos='0123456789..[90]', kw='KW', kw_only='KW_ONLY')")
    #
    with caplog.at_level(level="DEBUG"):
        traced(max_param_length=10)(ctx.traced_long_result)()
    verify(caplog.records, ">>> traced_long_result()", "Result: '0123456789..[90]'")

def test_agent_ctx(caplog):
    def verify(records, agent) -> None:
        assert len(records) == 3
        rec = records.pop(0)
        assert rec.agent == get_agent_name(agent)
        assert rec.context is None
        records.pop(0)
        rec = records.pop(0)
        assert rec.agent == get_agent_name(agent)
        assert rec.context is None

    ctx = Traced()
    trace_manager.flags |= (TraceFlag.FAIL | TraceFlag.BEFORE | TraceFlag.AFTER)
    #
    with caplog.at_level(level="DEBUG"):
        traced(agent=UNDEFINED)(ctx.traced_noparam_noresult)()
    verify(caplog.records, UNDEFINED)
    #ctx.log_context = "<CONTEXT>"
    ctx._agent_name_ = "<AGENT>"
    with caplog.at_level(level="DEBUG"):
        traced()(ctx.traced_noparam_noresult)()
    verify(caplog.records, "<AGENT>")

def test_level(caplog):
    def verify(records, level) -> None:
        assert len(records) == 3
        assert records.pop(0).levelno == level
        records.pop(0)
        assert records.pop(0).levelno == level

    ctx = Traced()
    trace_manager.flags |= (TraceFlag.FAIL | TraceFlag.BEFORE | TraceFlag.AFTER)
    #
    with caplog.at_level(level="INFO"):
        traced(level=LogLevel.INFO)(ctx.traced_noparam_noresult)()
    verify(caplog.records, LogLevel.INFO)

def test_forced(caplog):
    def verify(records, msg_before: str, msg_after_start: str, msg_after_end: str="") -> None:
        assert len(records) == 3
        rec = records.pop(0)
        assert rec.message == msg_before
        records.pop(0)
        rec = records.pop(0)
        assert rec.message.startswith(msg_after_start)
        assert rec.message.endswith(msg_after_end)

    ctx = Traced()
    trace_manager.flags = (TraceFlag.FAIL | TraceFlag.BEFORE | TraceFlag.AFTER)
    with caplog.at_level(level="DEBUG"):
        traced()(ctx.traced_noparam_noresult)()
    verify_func(caplog.records, "traced_noparam_noresult", True)
    #
    with caplog.at_level(level="DEBUG"):
        traced(flags=TraceFlag.ACTIVE)(ctx.traced_noparam_noresult)()
    verify(caplog.records, ">>> traced_noparam_noresult()", "<<< traced_noparam_noresult")

def test_env(caplog, monkeypatch):
    ctx = Traced()
    trace_manager.flags = (TraceFlag.ACTIVE | TraceFlag.FAIL | TraceFlag.BEFORE | TraceFlag.AFTER)
    with caplog.at_level(level="DEBUG"):
        traced()(ctx.traced_noparam_noresult)()
    assert len(caplog.records) == 3
    caplog.clear()
    with monkeypatch.context() as m:
        m.setenv("FBASE_TRACE", "off")
        with caplog.at_level(level="DEBUG"):
            traced()(ctx.traced_noparam_noresult)()
        verify_func(caplog.records, "traced_noparam_noresult", True)

@pytest.mark.skipif(__debug__, reason="__debug__ is True")
def test_debug(caplog, monkeypatch):
    with monkeypatch.context() as m:
        m.delenv("FBASE_TRACE")
    ctx = Traced()
    trace_manager.flags = (TraceFlag.ACTIVE | TraceFlag.FAIL | TraceFlag.BEFORE | TraceFlag.AFTER)
    with caplog.at_level(level="DEBUG"):
        traced()(ctx.traced_noparam_noresult)()
    verify_func(caplog.records, "traced_noparam_noresult", True)

def test_decorated(caplog):
    "Default settings only, events: FAIL"

    def verify(records, func_name, params: str="", result: str=None,
               outcome: str=("log_failed", "<--")) -> None:
        assert len(records) >= 2 if __debug__ else 1
        verify_func(records, func_name)
        if __debug__:
            rec = records.pop(0)
            assert rec.name == "trace"
            assert rec.levelno == LogLevel.DEBUG
            assert rec.args == ()
            assert rec.filename == "trace.py"
            assert rec.module == "trace"
            assert rec.funcName == outcome[0]
            assert rec.topic == "trace"
            assert rec.agent == get_agent_name(ctx)
            assert rec.context is None
            assert rec.message.startswith(f"{outcome[1]} {func_name}")
            assert rec.message.endswith(f"{result}")

    assert trace_manager.flags == TraceFlag.ACTIVE | TraceFlag.FAIL
    ctx = DecoratedTraced()
    # traced_noparam_noresult
    with caplog.at_level(level="DEBUG"):
        ctx.traced_noparam_noresult()
    verify_func(caplog.records, "traced_noparam_noresult", True)
    # traced_noparam_result
    with caplog.at_level(level="DEBUG"):
        ctx.traced_noparam_result()
    verify_func(caplog.records, "traced_noparam_result", True)
    # traced_param_noresult
    with caplog.at_level(level="DEBUG"):
        ctx.traced_param_noresult(1, 2, kw_only="NO-DEFAULT")
    verify_func(caplog.records, "traced_param_noresult", True)
    # traced_param_noresult
    with caplog.at_level(level="DEBUG"):
        ctx.traced_param_result(1, 2, kw_only="NO-DEFAULT")
    verify_func(caplog.records, "traced_param_result", True)
    # traced_raises
    with caplog.at_level(level="DEBUG"):
        with pytest.raises(Error):
            ctx.traced_raises()
    verify(caplog.records, "traced_raises", result="Error: No cookies left")

def test_add_traced(caplog):
    "Default settings only, events: FAIL"

    def verify(records, func_name, params: str="", result: str=None,
               outcome: str=("log_failed", "<--")) -> None:
        assert len(records) >= 2
        verify_func(records, func_name)
        rec = records.pop(0)
        assert rec.name == "trace"
        assert rec.levelno == LogLevel.DEBUG
        assert rec.args == ()
        assert rec.filename == "trace.py"
        assert rec.module == "trace"
        assert rec.funcName == outcome[0]
        assert rec.topic == "trace"
        assert rec.agent == get_agent_name(ctx)
        assert rec.context is None
        assert rec.message.startswith(f"{outcome[1]} {func_name}")
        assert rec.message.endswith(f"{result}")

    assert trace_manager.flags == TraceFlag.ACTIVE | TraceFlag.FAIL
    add_trace(Traced, "traced_noparam_noresult")
    add_trace(Traced, "traced_noparam_result")
    add_trace(Traced, "traced_param_noresult")
    add_trace(Traced, "traced_param_result")
    add_trace(Traced, "traced_raises")
    ctx = Traced()
    # traced_noparam_noresult
    with caplog.at_level(level="DEBUG"):
        ctx.traced_noparam_noresult()
    verify_func(caplog.records, "traced_noparam_noresult", True)
    # traced_noparam_result
    with caplog.at_level(level="DEBUG"):
        ctx.traced_noparam_result()
    verify_func(caplog.records, "traced_noparam_result", True)
    # traced_param_noresult
    with caplog.at_level(level="DEBUG"):
        ctx.traced_param_noresult(1, 2, kw_only="NO-DEFAULT")
    verify_func(caplog.records, "traced_param_noresult", True)
    # traced_param_result
    with caplog.at_level(level="DEBUG"):
        ctx.traced_param_result(1, 2, kw_only="NO-DEFAULT")
    verify_func(caplog.records, "traced_param_result", True)
    # traced_raises
    with caplog.at_level(level="DEBUG"):
        with pytest.raises(Error):
            traced()(ctx.traced_raises)()
    verify(caplog.records, "traced_raises", result="Error: No cookies left")
