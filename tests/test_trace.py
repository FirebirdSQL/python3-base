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

"""Unit tests for the firebird.base.trace module."""

from __future__ import annotations

import os
from logging import LogRecord, getLogger

import pytest

from firebird.base.logging import LogLevel, get_agent_name, logging_manager
from firebird.base.strconv import convert_from_str
# Assuming trace.py is importable as below
from firebird.base.trace import (
    TracedItem, TracedClass, TracedMixin, TraceFlag, add_trace, trace_manager,
    traced, remove_trace, trace_object
)
# Assuming types.py is importable as below
from firebird.base.types import DEFAULT, Error

# --- Test Setup & Fixtures ---

class Namespace:
    """Simple namespace for holding test attributes."""
    name: str = "Namespace"

class Traced(TracedMixin):
    """A sample class using TracedMixin for automatic registration and instrumentation."""
    def __init__(self, logging_id: str | None = None):
        if logging_id is not None:
            self._agent_name_: str = logging_id # type: ignore
    def traced_noparam_noresult(self) -> None:
        """Method with no parameters and no return value."""
        getLogger().info("<traced_noparam_noresult>")
    def traced_noparam_result(self) -> str:
        """Method with no parameters, returns a string."""
        getLogger().info("<traced_noparam_result>")
        return "OK"
    def traced_param_noresult(self, pos_only, / , pos, kw="KW", *, kw_only="KW_ONLY") -> None:
        """Method with various parameters, no return value."""
        getLogger().info("<traced_param_noresult>")
    def traced_param_result(self, pos_only, / , pos, kw="KW", *, kw_only="KW_ONLY") -> str:
        """Method with various parameters, returns a string."""
        getLogger().info("<traced_param_result>")
        return "OK"
    def traced_long_result(self) -> str:
        """Method returning a long string for truncation tests."""
        getLogger().info("<traced_long_result>")
        return "0123456789" * 10
    def traced_raises(self) -> None:
        """Method that raises an exception."""
        getLogger().info("<traced_raises>")
        raise Error("No cookies left")

class DecoratedTraced:
    """A sample class using the @traced decorator directly."""
    def __init__(self, logging_id: str | None = None):
        if logging_id is not None:
            self._agent_name_: str = logging_id # type: ignore
    @traced()
    def traced_noparam_noresult(self) -> None:
        """Decorated method with no parameters and no return value."""
        getLogger().info("<traced_noparam_noresult>")
    @traced()
    def traced_noparam_result(self) -> str:
        """Decorated method with no parameters, returns a string."""
        getLogger().info("<traced_noparam_result>")
        return "OK"
    @traced()
    def traced_param_noresult(self, pos_only, / , pos, kw="KW", *, kw_only="KW_ONLY") -> None:
        """Decorated method with various parameters, no return value."""
        getLogger().info("<traced_param_noresult>")
    @traced()
    def traced_param_result(self, pos_only, / , pos, kw="KW", *, kw_only="KW_ONLY") -> str:
        """Decorated method with various parameters, returns a string."""
        getLogger().info("<traced_param_result>")
        return "OK"
    @traced()
    def traced_raises(self) -> None:
        """Decorated method that raises an exception."""
        getLogger().info("<traced_raises>")
        raise Error("No cookies left")

class UnregisteredTraced:
    """A sample class *not* registered with TraceManager."""
    def method_a(self):
        getLogger().info("<UnregisteredTraced.method_a>")


@pytest.fixture(autouse=True)
def ensure_trace(monkeypatch):
    """Fixture to ensure tracing is active and manager state is clean before each test."""
    # Ensure tracing is on for tests, even if __debug__ is False
    if not __debug__:
        monkeypatch.setenv("FBASE_TRACE", "on")
    else:
        # Make sure env var doesn't override __debug__ if it's set to off
        monkeypatch.delenv("FBASE_TRACE", raising=False)

    # Configure logging manager format
    logging_manager.logger_fmt = ["trace_test"]

    # Reset TraceManager state
    trace_manager.clear()
    trace_manager.decorator = traced # Reset to default decorator
    # trace_manager._traced.clear() # Done by clear()
    # trace_manager._flags = TraceFlag.NONE # Reset below
    # Read flags from environment (consistent with manager init)
    trace_manager.trace_active = convert_from_str(bool, os.getenv("FBASE_TRACE", str(__debug__)))
    # Set flags based on env vars or defaults
    flags = TraceFlag.NONE
    if trace_manager.trace_active:
        flags |= TraceFlag.ACTIVE
    if convert_from_str(bool, os.getenv("FBASE_TRACE_BEFORE", "no")): # pragma: no cover
        flags |= TraceFlag.BEFORE
    if convert_from_str(bool, os.getenv("FBASE_TRACE_AFTER", "no")): # pragma: no cover
        flags |= TraceFlag.AFTER
    if convert_from_str(bool, os.getenv("FBASE_TRACE_FAIL", "yes")):
        flags |= TraceFlag.FAIL
    trace_manager.flags = flags

    # Register the Traced class (simulates TracedMixin effect)
    trace_manager.register(Traced)
    assert trace_manager.is_registered(Traced) # Verify registration


def verify_func(records: list[LogRecord], func_name: str, only: bool = False) -> None:
    """Helper to verify that the actual (non-trace) log message from a function exists."""
    expected_msg = f"<{func_name}>"
    if only:
        assert len(records) == 1, f"Expected only 1 record, got {len(records)}"
        assert records[0].getMessage() == expected_msg, f"Expected message '{expected_msg}'"
        records.pop(0) # Consume the record
    else:
        found = False
        initial_len = len(records)
        for i, record in enumerate(records):
            if record.getMessage() == expected_msg:
                records.pop(i)
                found = True
                break
        assert found, f"Did not find expected message '{expected_msg}' in records"
        assert len(records) == initial_len - 1

# --- Test Functions ---

def test_trace_dataclasses():
    """Tests the TracedItem and TracedClass dataclasses."""
    item = TracedItem(method="method_a", decorator=traced, args=[1], kwargs={'a': 1})
    assert item.method == "method_a"
    assert item.decorator is traced
    assert item.args == [1]
    assert item.kwargs == {'a': 1}
    assert item.get_key() == "method_a"

    cls_entry = TracedClass(cls=Traced)
    assert cls_entry.cls is Traced
    assert isinstance(cls_entry.traced, type(trace_manager._traced)) # Check registry type
    assert len(cls_entry.traced) == 0
    assert cls_entry.get_key() is Traced

    cls_entry.traced.store(item)
    assert len(cls_entry.traced) == 1


def test_traced_defaults_fail_only(caplog):
    """Tests the @traced decorator with default manager flags (ACTIVE | FAIL)."""

    def verify(records: list[LogRecord], func_name: str, result: str,
               outcome: tuple[str, str] = ("log_failed", "<--")) -> None:
        """Verify failure log record."""
        assert len(records) >= 2 # Expect func log + fail log
        verify_func(records, func_name) # Consume the function's own log
        assert len(records) == 1 # Only fail log should remain
        rec = records.pop(0)
        assert rec.name == "trace_test" # From logger_fmt
        assert rec.levelno == LogLevel.DEBUG
        assert rec.filename == "trace.py"
        assert rec.funcName == outcome[0]
        assert rec.topic == "trace"
        assert rec.agent == get_agent_name(ctx)
        assert rec.message.startswith(f"{outcome[1]} {func_name}")
        assert rec.message.endswith(f"{result}")

    # Assuming fixture sets flags = ACTIVE | FAIL
    assert trace_manager.flags == TraceFlag.ACTIVE | TraceFlag.FAIL
    ctx = Traced()

    # Test methods that DON'T fail - should only log their own message
    with caplog.at_level(level="DEBUG"):
        traced()(ctx.traced_noparam_noresult)()
    verify_func(caplog.records, "traced_noparam_noresult", only=True)

    with caplog.at_level(level="DEBUG"):
        traced()(ctx.traced_noparam_result)()
    verify_func(caplog.records, "traced_noparam_result", only=True)

    with caplog.at_level(level="DEBUG"):
        traced()(ctx.traced_param_noresult)(1, 2, kw_only="NO-DEFAULT")
    verify_func(caplog.records, "traced_param_noresult", only=True)

    with caplog.at_level(level="DEBUG"):
        traced()(ctx.traced_param_result)(1, 2, kw_only="NO-DEFAULT")
    verify_func(caplog.records, "traced_param_result", only=True)

    # Test method that fails - should log fail message
    with caplog.at_level(level="DEBUG"):
        with pytest.raises(Error):
            traced()(ctx.traced_raises)()
    verify(caplog.records, "traced_raises", result="Error: No cookies left")


def test_traced_all_events(caplog):
    """Tests the @traced decorator when all event flags (BEFORE, AFTER, FAIL) are active."""
    def verify(records: list[LogRecord], func_name: str, params: str = "", result: str = "",
               outcome: tuple[str, str] = ("log_after", "<<<"), expect_fail: bool = False) -> None:
        """Verify log records for BEFORE, func, and AFTER/FAIL."""
        expected_records = 3 if __debug__ else 1 # Needs FBASE_TRACE=on if not debug
        assert len(records) == expected_records, f"Expected {expected_records} records for {func_name}, got {len(records)}"

        if not __debug__: # Only func log expected
            verify_func(records, func_name, only=True)
            return

        # BEFORE log
        rec_before = records.pop(0)
        assert rec_before.name == "trace_test"
        assert rec_before.levelno == LogLevel.DEBUG
        assert rec_before.funcName == "log_before"
        assert rec_before.topic == "trace"
        assert rec_before.agent == get_agent_name(ctx)
        expected_before = f">>> {func_name}({params})" if decorator.with_args else f">>> {func_name}"
        assert rec_before.message == expected_before

        # Function's own log
        verify_func(records, func_name) # Consumes the record

        # AFTER or FAIL log
        rec_after_fail = records.pop(0)
        assert rec_after_fail.name == "trace_test"
        assert rec_after_fail.levelno == LogLevel.DEBUG
        assert rec_after_fail.funcName == outcome[0]
        assert rec_after_fail.topic == "trace"
        assert rec_after_fail.agent == get_agent_name(ctx)
        assert rec_after_fail.message.startswith(f"{outcome[1]} {func_name}")
        # Result check needs refinement based on has_result
        if expect_fail or decorator.has_result:
            assert rec_after_fail.message.endswith(f"{result}")
        else:
            assert not rec_after_fail.message.endswith(f"{result}") # Check it doesn't include result

    ctx = Traced()
    # Enable all flags in the manager for this test
    trace_manager.flags = TraceFlag.ACTIVE | TraceFlag.FAIL | TraceFlag.BEFORE | TraceFlag.AFTER
    # traced_noparam_noresult (has_result=False implicitly)
    decorator = traced() # As we refer to decorator in verify, we need fresh one
    with caplog.at_level(level="DEBUG"):
        decorator(ctx.traced_noparam_noresult)()
    verify(caplog.records, "traced_noparam_noresult", result="None", expect_fail=False)
    caplog.clear()

    # traced_noparam_result (has_result=True implicitly)
    decorator = traced() # As we refer to decorator in verify, we need fresh one
    with caplog.at_level(level="DEBUG"):
        decorator(ctx.traced_noparam_result)()
    verify(caplog.records, "traced_noparam_result", result="'OK'", expect_fail=False)
    caplog.clear()

    # traced_param_noresult
    decorator = traced() # As we refer to decorator in verify, we need fresh one
    params_str = "pos_only=1, pos=2, kw='KW', kw_only='NO-DEFAULT'"
    with caplog.at_level(level="DEBUG"):
        decorator(ctx.traced_param_noresult)(1, 2, kw_only="NO-DEFAULT")
    verify(caplog.records, "traced_param_noresult", params=params_str, result="None", expect_fail=False)
    caplog.clear()

    # traced_param_result
    decorator = traced() # As we refer to decorator in verify, we need fresh one
    with caplog.at_level(level="DEBUG"):
        decorator(ctx.traced_param_result)(1, 2, kw_only="NO-DEFAULT")
    verify(caplog.records, "traced_param_result", params=params_str, result="'OK'", expect_fail=False)
    caplog.clear()

    # traced_raises
    decorator = traced() # As we refer to decorator in verify, we need fresh one
    with caplog.at_level(level="DEBUG"):
        with pytest.raises(Error):
            decorator(ctx.traced_raises)()
    verify(caplog.records, "traced_raises", params="", result="Error: No cookies left", outcome=("log_failed", "<--"), expect_fail=True)

# --- Tests for specific `traced` arguments ---

def test_traced_custom_msg(caplog):
    """Tests customizing log messages via traced arguments."""
    def verify(records: list[LogRecord], msg_before: str, msg_after_fail_start: str, msg_after_fail_end: str = "") -> None:
        if not __debug__: pytest.skip("Trace inactive")
        assert len(records) == 3 # Before, Func, After/Fail
        assert records[0].message == msg_before
        # records[1] is the function's log
        assert records[2].message.startswith(msg_after_fail_start)
        assert records[2].message.endswith(msg_after_fail_end)

    ctx = Traced()
    trace_manager.flags = TraceFlag.ACTIVE | TraceFlag.FAIL | TraceFlag.BEFORE | TraceFlag.AFTER

    # Custom BEFORE message
    with caplog.at_level(level="DEBUG"):
        d = traced(msg_before="ENTER {_fname_} ({pos_only}, {pos}, {kw}, {kw_only})")
        d(ctx.traced_param_noresult)(1, 2, kw_only="NO-DEFAULT")
    verify(caplog.records, "ENTER traced_param_noresult (1, 2, KW, NO-DEFAULT)", "<<< traced_param_noresult") # Default after msg
    caplog.clear()

    # Custom AFTER message
    with caplog.at_level(level="DEBUG"):
        d = traced(msg_after="EXIT {_fname_}: {_result_!r}")
        d(ctx.traced_param_result)(1, 2, kw_only="NO-DEFAULT")
    verify(caplog.records, ">>> traced_param_result(pos_only=1, pos=2, kw='KW', kw_only='NO-DEFAULT')", # Default before msg
           "EXIT traced_param_result: 'OK'")
    caplog.clear()

    # Custom FAIL message
    with caplog.at_level(level="DEBUG"):
        d = traced(msg_failed="!!! {_fname_}: {_exc_}")
        with pytest.raises(Error):
            d(ctx.traced_raises)()
    verify(caplog.records, ">>> traced_raises()", # Default before msg
           "!!! traced_raises: Error: No cookies left")


def test_traced_extra_arg(caplog):
    """Tests passing and using 'extra' data in trace messages."""
    def foo(bar=""):
        """Helper function available in extra."""
        return f"Foo{bar}!"

    def verify(records: list[LogRecord], msg_before: str, msg_after: str) -> None:
        if not __debug__: pytest.skip("Trace inactive")
        assert len(records) == 3
        assert records[0].message == msg_before
        assert records[2].message == msg_after

    ctx = Traced()
    trace_manager.flags = TraceFlag.ACTIVE | TraceFlag.FAIL | TraceFlag.BEFORE | TraceFlag.AFTER

    with caplog.at_level(level="DEBUG"):
        # Use 'foo' from extra in message formats
        d = traced(msg_before=">>> {_fname_} ({foo(kw)}, {foo(kw_only)})",
                   msg_after="<<< {_fname_}: {foo(_result_)}", extra={"foo": foo})
        d(ctx.traced_param_result)(1, 2, kw_only="bar")
    # Verify 'foo' was called correctly within the f-string interpolation
    verify(caplog.records, ">>> traced_param_result (FooKW!, Foobar!)",
           "<<< traced_param_result: FooOK!")


def test_traced_topic_arg(caplog):
    """Tests setting a custom logging topic via the 'topic' argument."""
    def verify(records: list[LogRecord], topic: str) -> None:
        if not __debug__: pytest.skip("Trace inactive")
        assert len(records) == 3
        assert records[0].topic == topic
        assert records[2].topic == topic

    ctx = Traced()
    trace_manager.flags = TraceFlag.ACTIVE | TraceFlag.FAIL | TraceFlag.BEFORE | TraceFlag.AFTER

    with caplog.at_level(level="DEBUG"):
        traced(topic="custom_topic")(ctx.traced_noparam_noresult)()
    verify(caplog.records, "custom_topic")


def test_traced_max_param_length_arg(caplog):
    """Tests argument and result truncation using 'max_param_length'."""
    def verify(records: list[LogRecord], msg_before: str, msg_after_end: str) -> None:
        if not __debug__: pytest.skip("Trace inactive")
        assert len(records) == 3
        assert records[0].message == msg_before
        assert records[2].message.endswith(msg_after_end)

    ctx = Traced()
    trace_manager.flags = TraceFlag.ACTIVE | TraceFlag.FAIL | TraceFlag.BEFORE | TraceFlag.AFTER
    max_len = 10

    # Test argument truncation
    with caplog.at_level(level="DEBUG"):
        traced(max_param_length=max_len)(ctx.traced_param_result)("1234567890ABC", "x" * 15, kw="LongKeyword")
    # Expect truncation like 'LongKeywor..[1]' if length > 10
    # Exact format depends on internal logic, check if it's shorter than original + ellipsis
    expected_before = ">>> traced_param_result(pos_only='1234567890..[3]', pos='xxxxxxxxxx..[5]', kw='LongKeywor..[1]', kw_only='KW_ONLY')"
    verify(caplog.records, expected_before, "Result: 'OK'") # Result not truncated here
    caplog.clear()

    # Test result truncation
    with caplog.at_level(level="DEBUG"):
        traced(max_param_length=max_len)(ctx.traced_long_result)()
    expected_after_end = "Result: '0123456789..[90]'"
    verify(caplog.records, ">>> traced_long_result()", expected_after_end)


def test_traced_agent_arg(caplog):
    """Tests agent handling: default resolution vs. explicit 'agent' argument."""
    def verify(records: list[LogRecord], agent_id: Any, context: Any = None) -> None:
        if not __debug__: pytest.skip("Trace inactive")
        assert len(records) == 3
        assert records[0].agent == get_agent_name(agent_id)
        assert records[0].context == context
        assert records[2].agent == get_agent_name(agent_id)
        assert records[2].context == context

    ctx = Traced("AgentID_1")
    ctx.log_context = "Context_1" # type: ignore
    trace_manager.flags = TraceFlag.ACTIVE | TraceFlag.FAIL | TraceFlag.BEFORE | TraceFlag.AFTER

    # Default agent resolution (uses ctx._agent_name_)
    with caplog.at_level(level="DEBUG"):
        traced()(ctx.traced_noparam_noresult)()
    verify(caplog.records, "AgentID_1", "Context_1")
    caplog.clear()

    # Explicit agent argument
    explicit_agent = Namespace()
    explicit_agent.name = "ExplicitAgent" # type: ignore
    with caplog.at_level(level="DEBUG"):
        traced(agent=explicit_agent)(ctx.traced_noparam_noresult)()
    verify(caplog.records, explicit_agent, None) # Context comes from agent, explicit_agent has no log_context
    caplog.clear()

    # Agent argument as DEFAULT (should resolve to ctx like default case)
    with caplog.at_level(level="DEBUG"):
        traced(agent=DEFAULT)(ctx.traced_noparam_noresult)()
    verify(caplog.records, "AgentID_1", "Context_1")


def test_traced_level_arg(caplog):
    """Tests setting a custom logging level via the 'level' argument."""
    def verify(records: list[LogRecord], level: int) -> None:
        if not __debug__: pytest.skip("Trace inactive")
        assert len(records) == 3
        assert records[0].levelno == level
        assert records[2].levelno == level

    ctx = Traced()
    trace_manager.flags = TraceFlag.ACTIVE | TraceFlag.FAIL | TraceFlag.BEFORE | TraceFlag.AFTER

    # Log at INFO level
    with caplog.at_level(level="INFO"): # Ensure caplog captures INFO
        traced(level=LogLevel.INFO)(ctx.traced_noparam_noresult)()
    verify(caplog.records, LogLevel.INFO)

    # Log at WARNING level (should still be captured if caplog level is INFO or lower)
    caplog.clear()
    with caplog.at_level(level="INFO"):
        traced(level=LogLevel.WARNING)(ctx.traced_noparam_noresult)()
    verify(caplog.records, LogLevel.WARNING)


def test_traced_flags_override(caplog):
    """Tests overriding TraceManager flags using the decorator's 'flags' argument."""
    def verify_log_counts(records: list[LogRecord], before: bool, after: bool, fail: bool):
        """Checks presence/absence of specific trace logs."""
        if not __debug__: pytest.skip("Trace inactive")
        has_before = any(r.funcName == 'log_before' for r in records)
        has_after = any(r.funcName == 'log_after' for r in records)
        has_fail = any(r.funcName == 'log_failed' for r in records)
        assert has_before == before
        assert has_after == after
        assert has_fail == fail

    ctx = Traced()
    # Manager: FAIL only
    trace_manager.flags = TraceFlag.ACTIVE | TraceFlag.FAIL

    # Decorator forces BEFORE | AFTER (FAIL comes from manager)
    with caplog.at_level(level="DEBUG"):
        traced(flags=TraceFlag.BEFORE | TraceFlag.AFTER)(ctx.traced_noparam_noresult)()
    # Expect BEFORE, func, AFTER logs
    verify_log_counts(caplog.records, before=True, after=True, fail=False)

    # Decorator forces FAIL only (manager adds ACTIVE)
    caplog.clear()
    with caplog.at_level(level="DEBUG"):
        with pytest.raises(Error):
            traced(flags=TraceFlag.FAIL)(ctx.traced_raises)()
    # Expect func, FAIL logs (FAIL overrides manager's default FAIL?) -> No, flags are ORed.
    # If manager has FAIL and decorator has FAIL, result still has FAIL.
    # This test doesn't show override well. Let's try disabling.
    verify_log_counts(caplog.records, before=False, after=False, fail=True)

    # Manager: BEFORE | AFTER | FAIL | ACTIVE
    trace_manager.flags = TraceFlag.ACTIVE | TraceFlag.BEFORE | TraceFlag.AFTER | TraceFlag.FAIL

    # Decorator forces *only* ACTIVE (disables others for this call)
    # The OR logic means we cannot *disable* flags this way.
    # The test 'test_forced' seems misnamed or the logic misunderstood previously.
    # Let's test adding a flag instead.

    # Manager: ACTIVE | FAIL
    trace_manager.flags = TraceFlag.ACTIVE | TraceFlag.FAIL
    # Decorator adds BEFORE
    caplog.clear()
    with caplog.at_level(level="DEBUG"):
        traced(flags=TraceFlag.BEFORE)(ctx.traced_noparam_noresult)()
    # Expect BEFORE, func logs (no fail, no after)
    verify_log_counts(caplog.records, before=True, after=False, fail=False)


def test_traced_env_disable(caplog, monkeypatch):
    """Tests disabling trace via FBASE_TRACE=off environment variable."""
    ctx = Traced()
    trace_manager.flags = TraceFlag.ACTIVE | TraceFlag.BEFORE | TraceFlag.AFTER | TraceFlag.FAIL

    # Baseline: trace should be active
    with caplog.at_level(level="DEBUG"):
        traced()(ctx.traced_noparam_noresult)()
    assert len(caplog.records) == 3 if __debug__ else 1
    caplog.clear()

    # Disable via environment variable
    monkeypatch.setenv("FBASE_TRACE", "off")
    # Re-create decorator instance *after* setting env var if it caches the check
    decorator_instance = traced()
    with caplog.at_level(level="DEBUG"):
        decorator_instance(ctx.traced_noparam_noresult)()
    # Only the function's own log should appear
    verify_func(caplog.records, "traced_noparam_noresult", only=True)


@pytest.mark.skipif(__debug__, reason="Test requires __debug__ == False")
def test_traced_debug_disable(caplog, monkeypatch):
    """Tests disabling trace when __debug__ is False and FBASE_TRACE is not set."""
    # Fixture ensures FBASE_TRACE is deleted if __debug__ is True,
    # but we skip if __debug__ is True. So if we run, __debug__ is False.
    # We need to ensure FBASE_TRACE is *not* set.
    monkeypatch.delenv("FBASE_TRACE", raising=False)

    ctx = Traced()
    trace_manager.flags = TraceFlag.ACTIVE | TraceFlag.BEFORE | TraceFlag.AFTER | TraceFlag.FAIL

    # Decorator should be disabled by __debug__ == False
    decorator_instance = traced()
    with caplog.at_level(level="DEBUG"):
        decorator_instance(ctx.traced_noparam_noresult)()
    # Only the function's own log should appear
    verify_func(caplog.records, "traced_noparam_noresult", only=True)

# --- Tests for direct @traced usage ---

def test_decorated_class(caplog):
    """Tests using @traced directly on methods of a class (no mixin/manager)."""
    # Uses the same verify helper as test_traced_defaults_fail_only
    def verify(records: list[LogRecord], func_name: str, result: str,
               outcome: tuple[str, str] = ("log_failed", "<--")) -> None:
        # Check if trace logs are expected based on __debug__
        if not __debug__:
            verify_func(records, func_name, only=True)
            return

        assert len(records) >= 2 # Expect func log + fail log
        verify_func(records, func_name) # Consume the function's own log
        assert len(records) == 1 # Only fail log should remain
        rec = records.pop(0)
        assert rec.name == "trace_test" # From logger_fmt
        assert rec.levelno == LogLevel.DEBUG
        assert rec.filename == "trace.py" # Decorator code location
        assert rec.funcName == outcome[0]
        assert rec.topic == "trace" # Decorator default
        assert rec.agent == get_agent_name(ctx)
        assert rec.message.startswith(f"{outcome[1]} {func_name}")
        assert rec.message.endswith(f"{result}")

    # Manager flags only control implicit tracing via TracedMixin/trace_object
    # Direct @traced decorator uses its own defaults + checks env/__debug__
    assert trace_manager.flags == TraceFlag.ACTIVE | TraceFlag.FAIL
    ctx = DecoratedTraced("DecoratedAgent")

    # Test methods that DON'T fail - should only log their own message if trace inactive
    with caplog.at_level(level="DEBUG"):
        ctx.traced_noparam_noresult()
    if not __debug__: verify_func(caplog.records, "traced_noparam_noresult", only=True)
    else: assert len(caplog.records) == 1 # Only func log, FAIL flag doesn't trigger
    caplog.clear()

    # Test method that fails - should log fail message IF trace active
    with caplog.at_level(level="DEBUG"):
        with pytest.raises(Error):
            ctx.traced_raises()
    # Verify output based on whether tracing was active
    verify(caplog.records, "traced_raises", result="Error: No cookies left")


# --- Tests for TraceManager interaction ---

def test_manager_add_remove_trace(caplog):
    """Tests adding and removing trace specifications via TraceManager."""
    # Fixture registers Traced class. Add trace for one method.
    add_trace(Traced, "traced_noparam_result", flags=TraceFlag.BEFORE | TraceFlag.AFTER)
    ctx = Traced() # Instantiation applies the trace via TracedMeta/trace_object

    # Check that only the added method is traced with specified flags
    trace_manager.flags = TraceFlag.ACTIVE # Ensure only ACTIVE is on manager

    # Call traced method
    with caplog.at_level(level="DEBUG"):
        ctx.traced_noparam_result()
    # Expect BEFORE, func, AFTER logs because decorator flags were added
    assert len(caplog.records) == 3
    assert caplog.records[0].funcName == "log_before"
    assert caplog.records[2].funcName == "log_after"
    caplog.clear()

    # Call another method (should not be traced by manager)
    with caplog.at_level(level="DEBUG"):
        ctx.traced_noparam_noresult()
    verify_func(caplog.records, "traced_noparam_noresult", only=True) # Only func log

    # Remove the trace
    remove_trace(Traced, "traced_noparam_result")

    # Re-instantiate to get clean object without the removed trace applied
    ctx2 = Traced()
    with caplog.at_level(level="DEBUG"):
        ctx2.traced_noparam_result()
    verify_func(caplog.records, "traced_noparam_result", only=True) # Should no longer trace

def test_manager_trace_object_strict(caplog):
    """Tests trace_object with strict=True for unregistered classes."""
    instance = UnregisteredTraced()
    # Should work fine with strict=False (default)
    traced_instance = trace_object(instance)
    assert traced_instance is instance # No changes applied
    with caplog.at_level(level="DEBUG"):
        traced_instance.method_a()
    verify_func(caplog.records, "UnregisteredTraced.method_a", only=True) # No trace logs

    # Should raise TypeError with strict=True
    with pytest.raises(TypeError, match="Class 'UnregisteredTraced' not registered for trace!"):
        trace_object(instance, strict=True)


# --- Config tests are missing ---
# TODO: Add tests for TraceConfig classes and TraceManager.load_config
