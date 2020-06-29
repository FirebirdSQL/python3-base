#coding:utf-8
#
# PROGRAM/MODULE: firebird-base
# FILE:           firebird/base/trace.py
# DESCRIPTION:    Trace/audit for class instances
# CREATED:        5.6.2020
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

"""firebird-base - Trace/audit for class instances
"""

from __future__ import annotations
from typing import Any, Type, Hashable, List, Dict, Callable
import os
from inspect import signature, Signature
from dataclasses import dataclass, field
from enum import IntFlag, auto
from functools import wraps
from time import monotonic
from decimal import Decimal
from .types import Distinct, DEFAULT, UNLIMITED
from .collections import Registry
from .strconv import convert_from_str
from .logging import LogLevel, FBLoggerAdapter, get_logger

class TraceFlag(IntFlag):
    "`LoggingManager` trace/audit flags"
    DISABLED = 0
    ACTIVE = auto()
    BEFORE = auto()
    AFTER = auto()
    FAIL = auto()

@dataclass
class TracedItem(Distinct):
    "Class method trace specification"
    method: str
    decorator: Callable
    args: List = field(default_factory=list)
    kwargs: Dict = field(default_factory=dict)
    def get_key(self) -> Hashable:
        return self.method

@dataclass
class TracedClass(Distinct):
    "Traced class registry entry"
    cls: Type
    traced: Registry = field(default_factory=Registry)
    def get_key(self) -> Hashable:
        return self.cls

_traced: Registry = Registry()

class TracedMeta(type):
    "Metaclass that instruments instances on creation."
    def __call__(cls: Type, *args, **kwargs):
        return trace_object(super().__call__(*args, **kwargs), strict=True)

class TracedMixin(metaclass=TracedMeta):
    """Mixin class that automatically registers descendants for trace and instruments
instances on creation.
"""
    def __init_subclass__(cls: Type, /, **kwargs) -> None:
        super().__init_subclass__(**kwargs)
        trace_manager.register(cls)


class traced:
    """Base decorator for logging of callables, suitable for trace/audit.

It's not applied on decorated function/method if `FBASE_TRACE` environment variable is
set to False, or if `FBASE_TRACE` is not defined and `__debug__` is False (optimized
Python code).

Both positional and keyword arguments of decorated callable are available by name for
f-string type message interpolation as `dict` passed to logger as positional argument.
"""
    def __init__(self, *, agent: Any=DEFAULT, context: Any=DEFAULT, topic: str='trace',
                 msg_before: str=DEFAULT, msg_after: str=DEFAULT, msg_failed: str=DEFAULT,
                 flags: TraceFlag=TraceFlag(0), level: LogLevel=LogLevel.DEBUG,
                 max_param_length: int=UNLIMITED, extra: Dict=None,
                 callback: Callable[[Any], bool]=None, has_result: bool=DEFAULT,
                 with_args: bool=True):
        """
        Arguments:
            agent: Agent identification
            context: Context identification
            topic: Trace/audit logging topic
            msg_before: Trace/audit message logged before decorated function
            msg_after: Trace/audit message logged after decorated function
            msg_failed: Trace/audit message logged when decorated function raises an exception
            flags: Trace flags override
            level: Logging level for trace/audit messages
            max_param_length: Max. length of parameters (longer will be trimmed)
            extra: Extra data for `LogRecord`
        """
        self.msg_before: str = msg_before
        self.msg_after: str = msg_after
        self.msg_failed: str = msg_failed
        self.agent: Any = agent
        self.context: Any = context
        self.topic: str = topic
        self.flags: TraceFlag = flags
        self.level: LogLevel = level
        self.max_len: int = max_param_length
        self.extra: Dict = extra
        self.callback: Callable[[Any], bool] = self.__callback if callback is None else callback
        self.has_result: bool = has_result
        self.with_args: bool = with_args
    def __callback(self, agent: Any) -> bool:
        "Default callback, does nothing"
        return True
    def set_before_msg(self, fn: Callable, sig: Signature) -> None:
        "Sets the DEFAULT before message f-string template."
        if self.with_args:
            self.msg_before = f">>> {fn.__name__}({', '.join(f'{{{x}=}}' for x in sig.parameters if x != 'self')})"
        else:
            self.msg_before = f">>> {fn.__name__}"
    def set_after_msg(self, fn: Callable, sig: Signature) -> None:
        "Sets the DEFAULT after message f-string template."
        self.msg_after = f"<<< {fn.__name__}[{{_etime_}}] Result: {{_result_}}" \
            if self.has_result else f"<<< {fn.__name__}[{{_etime_}}]"
    def set_fail_msg(self, fn: Callable, sig: Signature) -> None:
        "Sets the DEFAULT fail message f-string template."
        self.msg_failed = f"<-- {fn.__name__}[{{_etime_}}] {{_exc_}}"
    def log_before(self, logger: FBLoggerAdapter, params: Dict) -> None:
        "Executed before decorated callable"
        logger.log(self.level, self.msg_before, params, stacklevel=2)
    def log_after(self, logger: FBLoggerAdapter, params: Dict) -> None:
        "Executed after decorated callable"
        logger.log(self.level, self.msg_after, params, stacklevel=2)
    def log_failed(self, logger: FBLoggerAdapter, params: Dict) -> None:
        "Executed when decorated callable raises an exception"
        logger.log(self.level, self.msg_failed, params, stacklevel=2)
    def __call__(self, fn: Callable):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            flags = trace_manager.trace | self.flags
            if enabled := ((TraceFlag.ACTIVE in flags) and int(flags) > 1):
                params = {}
                bound = sig.bind_partial(*args, **kwargs)
                # If it's not a bound method, look for 'self'
                log = get_logger(bound.arguments.get('self', 'function') if self.agent is None
                                 else self.agent, self.context, self.topic)
                if enabled := (log.isEnabledFor(self.level) and self.callback(self.agent)):
                    if self.with_args:
                        bound.apply_defaults()
                        params.update(bound.arguments)
                        if self.max_len is not UNLIMITED:
                            for k, v in params.items():
                                s = str(v)
                                if (i := len(s)) > self.max_len:
                                    params[k] = f'{s[:self.max_len]}..[{i - self.max_len}]'
                    if self.extra is not None:
                        params.update(self.extra)
                    params['_fname_'] = fn.__name__
                    params['_result_'] = None
                    #
                    if TraceFlag.BEFORE in flags:
                        self.log_before(log, params)
            try:
                result = None
                start = monotonic()
                result = fn(*args, **kwargs)
            except Exception as exc:
                if enabled and TraceFlag.FAIL | TraceFlag.ACTIVE in flags:
                    e = str(Decimal(monotonic() - start))
                    params['_etime_'] = e[:e.find('.')+6]
                    params['_exc_'] = f'{exc.__class__.__qualname__}: {exc}'
                    self.log_failed(log, params)
                raise
            else:
                if enabled and TraceFlag.AFTER | TraceFlag.ACTIVE in flags:
                    e = str(Decimal(monotonic() - start))
                    params['_etime_'] = e[:e.find('.')+6]
                    if self.has_result:
                        params['_result_'] = result
                        if self.max_len is not UNLIMITED:
                            s = str(result)
                            if (i := len(s)) > self.max_len:
                                params['_result_'] = f'{s[:self.max_len]}..[{i - self.max_len}]'
                    self.log_after(log, params)
            return result

        if (trace := os.getenv('FBASE_TRACE')) is not None:
            if not convert_from_str(bool, trace):
                return fn
        elif not __debug__:
            return fn
        if self.agent is DEFAULT:
            self.agent = getattr(fn, '__self__', None)
        sig = signature(fn)
        if self.has_result is DEFAULT:
            self.has_result = sig.return_annotation != 'None'
        if self.msg_before is DEFAULT:
            self.set_before_msg(fn, sig)
        if self.msg_after is DEFAULT:
            self.set_after_msg(fn, sig)
        if self.msg_failed is DEFAULT:
            self.set_fail_msg(fn, sig)
        return wrapper

class TraceManager:
    """Trace manager."""
    def __init__(self):
        self._traced: Registry = Registry()
        self._flags: TraceFlag = TraceFlag.DISABLED
        if convert_from_str(bool, os.getenv('FBASE_TRACE', str(__debug__))):
            self.trace |= TraceFlag.ACTIVE
        if convert_from_str(bool, os.getenv('FBASE_TRACE_BEFORE', 'no')): # pragma: no cover
            self.trace |= TraceFlag.BEFORE
        if convert_from_str(bool, os.getenv('FBASE_TRACE_AFTER', 'no')): # pragma: no cover
            self.trace |= TraceFlag.AFTER
        if convert_from_str(bool, os.getenv('FBASE_TRACE_FAIL', 'yes')):
            self.trace |= TraceFlag.FAIL
    def is_registered(self, cls: Type) -> bool:
        "Return True if class is registered"
        return cls in self._traced
    def clear(self) -> None:
        "Removes all trace specifications."
        for cls in self._traced:
            cls.traced.clear()
    def register(self, cls: Type) -> None:
        "Register class for trace. Does nothing if class is already registered."
        if cls not in self._traced:
            self._traced.store(TracedClass(cls))
    def add_trace(self, cls: Type, method: str, decorator: Callable=traced, / , *args, **kwargs) -> None:
        "Add/update trace specification for class method."
        self._traced[cls].traced.update(TracedItem(method, decorator, args, kwargs))
    def remove_trace(self, cls: Type, method: str) -> None:
        "Remove trace specification for class method."
        del self._traced[cls].traced[method]
    def trace_object(self, obj: Any, *, strict: bool=False) -> Any:
        """Instruments object's methods with decorator according to trace configuration.

Arguments:
    strict: Determines the response if the object class is not registered for trace.
            Raises exception when True, or return the instance as is when False [default].

Returns:
    Decorated instance.

Raises:
    TypeError: When object class is not registered and `strict` is True.
"""
        if (trace := os.getenv('FBASE_TRACE')) is not None:
            if not convert_from_str(bool, trace):
                return obj
        elif not __debug__:
            return obj
        entry: TracedClass = self._traced.get(obj.__class__)
        if entry is None:
            if strict:
                raise TypeError(f"Class '{obj.__class__.__name__}' not registered for trace!")
            else:
                return obj
        for item in entry.traced:
            setattr(obj, item.method, item.decorator(*item.args, **item.kwargs)(getattr(obj, item.method)))
        return obj
    @property
    def trace(self) -> TraceFlag:
        "Trace flags"
        return self._flags
    @trace.setter
    def trace(self, value: TraceFlag) -> None:
        self._flags = value if isinstance(value, TraceFlag) else TraceFlag(value)

#: Trace manager
trace_manager: TraceManager = TraceManager()

add_trace = trace_manager.add_trace
remove_trace = trace_manager.remove_trace
trace_object = trace_manager.trace_object

