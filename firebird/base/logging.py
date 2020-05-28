#coding:utf-8
#
# PROGRAM/MODULE: firebird-base
# FILE:           firebird/base/logging.py
# DESCRIPTION:    Context-based logging and trace/audit
# CREATED:        14.5.2020
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

"""firebird-base - Context-based logging and trace/audit

"""

from __future__ import annotations
from typing import Any, Dict, Tuple, Sequence, Union, Hashable, Callable
import os
from time import monotonic
from enum import IntEnum, Flag, IntFlag, auto
from decimal import Decimal
from collections.abc import Mapping
from dataclasses import dataclass
from inspect import signature
from functools import wraps
from logging import Logger, LoggerAdapter, getLogger, lastResort, Formatter
from firebird.base.types import UNDEFINED, UNLIMITED, DEFAULT, ANY, ALL, Distinct, \
     CachedDistinct, Sentinel, str2bool
from firebird.base.collections import Registry

class LogLevel(IntEnum):
    "Shadow enumeration for logging levels"
    NOTSET = 0
    DEBUG = 10
    INFO = 20
    WARNING = 30
    ERROR = 40
    CRITICAL = 50
    FATAL = CRITICAL
    WARN = WARNING

class TraceFlag(IntFlag):
    "`LoggingManager` trace/audit flags"
    DISABLED = 0
    ACTIVE = auto()
    BEFORE = auto()
    AFTER = auto()
    FAIL = auto()

class BindFlag(Flag):
    "Internal flags used by `LoggingManager`."
    DIRECT = auto()
    ANY_AGENT = auto()
    ANY_CTX = auto()
    ANY_ANY = auto()

class FBLoggerAdapter(LoggerAdapter, CachedDistinct):
    """`~logging.LoggerAdapter` that injects information about context, agent and topic
into `extra` and with **f-string** log message support.

Attributes:
    logger (Logger): Adapted Logger instance.
    agent (str): Agent for logger
    context (str): Context for logger
    topic (str): Topic for logger.
"""
    def __init__(self, logger: Logger, agent: Any=UNDEFINED, context: Any=UNDEFINED, topic: str=''):
        """
Arguments:
    logger: Adapted Logger instance.
    agent: Agent for logger
    context: Context for logger
    topic: Topic of recorded information.
"""
        self.logger: Logger = logger
        self.agent: Any = agent
        self.context: Any = context
        self.topic: str = topic
    @classmethod
    def extract_key(cls, *args, **kwargs) -> Hashable:
        "Returns instance key extracted from constructor arguments."
        return (args[1], args[2])
    def get_key(self) -> Hashable: # pragma: no cover
        "Returns instance key."
        return (self.topic, self.agent, self.context)
    def process(self, msg, kwargs) -> Tuple[str, Dict]:
        """Process the logging message and keyword arguments passed in to
        a logging call to insert contextual information. You can either
        manipulate the message itself, the keyword args or both. Return
        the message and kwargs modified (or not) to suit your needs.
        """
        return msg, kwargs
    def log(self, level, msg, *args, **kwargs):
        """Delegate a log call to the underlying logger after processing.

        Interpolates the message as **f-string** using either `kwargs` or dict passed as
        only one positional argument. If sole positional argument is not dictionary or
        `args` has more than one item, adds `args` into namespace for interpolation.

        Moves 'context', 'agent' and 'topic' keyword arguments into `extra`.

        Strips out all keyword arguments not expected by `logging.Logger`.
        """
        if self.isEnabledFor(level):
            msg, kwargs = self.process(msg, kwargs)
            if (args and len(args) == 1 and isinstance(args[0], Mapping) and args[0]):
                ns = args[0]
            else:
                ns = kwargs
                if args:
                    ns['args'] = args
            msg = eval(f'f"""{msg}"""', globals(), ns)
            args = ()
            if 'stacklevel' not in kwargs:
                kwargs['stacklevel'] = 3
            kwargs.setdefault('extra', {}).update(topic=self.topic, agent=self.agent,
                                                  context=self.context)
            self.logger.log(level, msg, *args, **{k: v for k, v in kwargs.items()
                                                  if k in ['exc_info', 'stack_info',
                                                           'stacklevel', 'extra']})

@dataclass(order=True, frozen=True)
class BindInfo(Distinct):
    """Information about Logger binding"""
    topic: str
    agent: str
    context: str
    logger: FBLoggerAdapter
    def get_key(self) -> Any:
        return (self.topic, self.agent, self.context)

def get_logging_id(obj: Any) -> Any:
    """Returns logging ID for object.

Arguments:
    obj: Any object

Returns:
    1. `logging_id` attribute if `obj` does have it, or..
    2. `__name__` attribute if `obj` does have it, or..
    3. `str(obj)`
"""
    return getattr(obj, 'logging_id', getattr(obj, '__name__', str(obj)))

class LoggingIdMixin:
    "Mixin class that adds `logging_id` property and `__str__`."
    def __str__(self):
        "Returns `logging_id`"
        return self.logging_id
    @property
    def logging_id(self) -> str:
        "Returns `_logging_id_` attribute if defined, else returns qualified class name"
        return getattr(self, '_logging_id_', self.__class__.__qualname__)

class LoggingManager:
    """Logger manager.
"""
    def __init__(self):
        self.loggers: Registry = Registry()
        self.topics: Dict = {}
        self.bindings: BindFlag = BindFlag(0)
        self._trace: TraceFlag = TraceFlag.DISABLED
        if str2bool(os.getenv('FBASE_TRACE', str(__debug__))):
            self.trace |= TraceFlag.ACTIVE
        if str2bool(os.getenv('FBASE_TRACE_BEFORE', 'no')): # pragma: no cover
            self.trace |= TraceFlag.BEFORE
        if str2bool(os.getenv('FBASE_TRACE_AFTER', 'no')): # pragma: no cover
            self.trace |= TraceFlag.AFTER
        if str2bool(os.getenv('FBASE_TRACE_FAIL', 'yes')):
            self.trace |= TraceFlag.FAIL
    def _update_bindings(self, agent: Any, context: Any) -> None:
        if agent is ANY:
            self.bindings |= BindFlag.ANY_AGENT
        if context is ANY:
            self.bindings |= BindFlag.ANY_CTX
        if (agent is ANY) and (context is ANY):
            self.bindings |= BindFlag.ANY_ANY
        if (agent is not ANY) and (context is not ANY):
            self.bindings |= BindFlag.DIRECT
    def _update_topics(self, topic: str) -> None:
        if topic in self.topics:
            self.topics[topic] += 1
        else:
            self.topics[topic] = 1
    def bind_logger(self, agent: Any, context: Any, logger: Union[str, Logger], topic: str='') -> None:
        """Bind agent and context to specific logger.

Arguments:
    agent: Agent identification
    context: Context identification
    logger: Loger (instance or name)
    topic: Topic of recorded information

The identification of agent and context could be:

    1. String
    2. Object instance. Uses `get_logging_id()` to retrieve its logging ID.
    3. Sentinel. The ANY sentinel matches any particular agent or context. You can use
       sentinel `.UNDEFINED` to register a logger for cases when agent or context are not
       specified in logger lookup.

Important:
   You SHOULD NOT use sentinel `.ALL` for `agent` or `context` identification! This
   sentinel is used by `.unbind`, so binding that uses ALL could not be removed by `.unbind`.

"""
        if isinstance(logger, str):
            logger = getLogger(logger)
        if not isinstance(agent, (str, Sentinel)):
            agent = get_logging_id(agent)
        if not isinstance(context, (str, Sentinel)):
            context = get_logging_id(context)
        if agent is not ANY and context is not ANY:
            logger = FBLoggerAdapter(logger, agent, context)
        self._update_bindings(agent, context)
        self._update_topics(topic)
        self.loggers.update(BindInfo(topic, agent, context, logger))
    def unbind(self, agent: Any, context: Any, topic: str='') -> int:
        """Drops logger bindings.
"""
        if not isinstance(agent, (str, Sentinel)):
            agent = get_logging_id(agent)
        if not isinstance(context, (str, Sentinel)):
            context = get_logging_id(context)
        if topic in self.topics:
            rm = [i for i in self.loggers
                  if i.topic == topic and ((i.agent == agent) or agent is ALL)
                  and ((i.context == context) or context is ALL)]
            for item in rm:
                self.loggers.remove(item)
            # recalculate optimizations
            self.topics.clear()
            self.bindings = BindFlag(0)
            for item in self.loggers:
                self._update_bindings(item.agent, item.context)
                self._update_topics(item.topic)
            return len(rm)
        return 0
    def clear(self) -> None:
        """Remove all logger bindings"""
        self.loggers.clear()
        self.topics.clear()
        self.bindings = BindFlag(0)
    def get_logger(self, agent: Any=UNDEFINED, context: Any=DEFAULT, topic: str='') -> FBLoggerAdapter:
        """Return a logger for the specified agent and context combination.

Arguments:
    agent: Agent identification.
    context: Context identification.
    topic: Topic of recorded information.

The identification of agent and context could be:

    1. String
    2. Object instance. Uses `get_logging_id()` to retrieve its logging ID.
    3. Sentinel `.UNDEFINED`
    4. When `context` is sentinel `.DEFAULT`, uses `agent` attribute `log_context` (if defined)
       or sentinel `.UNDEFINED` otherwise.

The search for a suitable topic logger proceeds as follows:

    1. Return logger registered for specified agent and context, or...
    2. Return logger registered for ANY agent and specified context, or...
    3. Return logger registered for specified agent and ANY context, or...
    4. Return logger registered for ANY agent and ANY context, or...
    5. Return the root logger.
"""
        if context is DEFAULT:
            context = getattr(agent, 'log_context', UNDEFINED)
        if agent is not UNDEFINED and not isinstance(agent, str):
            agent = get_logging_id(agent)
        if context is not UNDEFINED and not isinstance(context, str):
            context = get_logging_id(context)
        result: BindInfo = None
        if topic in self.topics:
            if BindFlag.DIRECT in self.bindings and \
               (result := self.loggers.get((topic, agent, context))) is not None:
                result = result.logger
            elif BindFlag.ANY_AGENT in self.bindings and \
                 (result := self.loggers.get((topic, ANY, context))) is not None:
                result = result.logger
            elif BindFlag.ANY_CTX in self.bindings and \
                 (result := self.loggers.get((topic, agent, ANY))) is not None:
                result = result.logger
            elif BindFlag.ANY_ANY in self.bindings and \
                 (result := self.loggers.get((topic, ANY, ANY))) is not None:
                result = result.logger
            else:
                result = getLogger(topic)
        else:
            result = getLogger(topic)
        return result if isinstance(result, FBLoggerAdapter) \
               else FBLoggerAdapter(result, agent, context, topic)
    #
    @property
    def trace(self) -> TraceFlag:
        "Trace flags"
        return self._trace
    @trace.setter
    def trace(self, value: TraceFlag) -> None:
        self._trace = value if isinstance(value, TraceFlag) else TraceFlag(value)

_manager: LoggingManager = LoggingManager()

def get_manager() -> LoggingManager:
    "Returns main `LoggingManager`."
    return _manager

def bind_logger(agent: Any, context: Any, logger: Union[str, Logger], topic: str='') -> None:
    "Calls `~LoggingManager.bind_logger()` on main LoggingManager."
    _manager.bind_logger(agent, context, logger, topic)

def get_logger(agent: Any=UNDEFINED, context: Any=DEFAULT, topic: str='') -> FBLoggerAdapter:
    "Calls `~LoggingManager.get_logger()` on main LoggingManager."
    return _manager.get_logger(agent, context, topic)

# Trace logging decorator

class traced:
    """Base decorator for logging of callables, suitable for trace/audit.

It's not applied on decorated function/method if `FBASE_TRACE` environment variable is
set to False, or ff `FBASE_TRACE` is not defined and `__debug__` is False (optimized
Python code).

Both positional and keyword arguments of decorated callable are available by name for
f-string type message interpolation as `dict` passed to logger as positional argument.
"""
    def __init__(self, *, agent: Any=DEFAULT, context: Any=DEFAULT, topic: str='trace',
                 msg_before: str=DEFAULT, msg_after: str=DEFAULT, msg_failed: str=DEFAULT,
                 flags: TraceFlag=TraceFlag(0), level: LogLevel=LogLevel.DEBUG,
                 max_param_length: int=UNLIMITED, extra: Dict=None,
                 callback: Callable[[Any], bool]=None):
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
    def __callback(self, agent: Any) -> bool:
        "Default callback, does nothing"
        return True
    def log_before(self, logger: FBLoggerAdapter, params: Dict) -> None:
        "Executed before decorated callable"
        logger.log(self.level, self.msg_before, params, stacklevel=2)
    def log_after(self, logger: FBLoggerAdapter, params: Dict) -> None:
        "Executed after decorated callable"
        logger.log(self.level, self.msg_after, params, stacklevel=2)
    def log_failed(self, logger: FBLoggerAdapter, params: Dict) -> None:
        "Executed when decorated callable raises an exception"
        logger.log(self.level, self.msg_failed, params, stacklevel=2)
    def __call__(self, fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            flags = _manager.trace | self.flags
            if enabled := ((TraceFlag.ACTIVE in flags) and int(flags) > 1):
                params = sig.bind_partial(*args, **kwargs).arguments
                # If it's not a bound method, look for 'self'
                log = _manager.get_logger(params.get('self', 'function') if self.agent is None
                                          else self.agent, self.context, self.topic)
                if enabled := (log.isEnabledFor(self.level) and self.callback(self.agent)):
                    for name, value in sig.parameters.items():
                        if value.default is not sig.empty and name not in params:
                            params[name] = value.default
                    if self.max_len is not UNLIMITED:
                        for k, v in params.items():
                            s = str(v)
                            if (i := len(s)) > self.max_len:
                                params[k] = f'{s[:self.max_len]}..[{i - self.max_len}]'
                    if self.extra is not None:
                        params.update(self.extra)
                    params['_fname_'] = fname
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
                    params['_result_'] = f'{exc.__class__.__qualname__}: {exc}'
                    self.log_failed(log, params)
                raise
            else:
                if enabled and TraceFlag.AFTER | TraceFlag.ACTIVE in flags:
                    e = str(Decimal(monotonic() - start))
                    params['_etime_'] = e[:e.find('.')+6]
                    params['_result_'] = result
                    if self.max_len is not UNLIMITED:
                        s = str(result)
                        if (i := len(s)) > self.max_len:
                            params['_result_'] = f'{s[:self.max_len]}..[{i - self.max_len}]'
                    self.log_after(log, params)
            return result

        if (trace := os.getenv('FBASE_TRACE')) is not None:
            if not str2bool(trace):
                return fn
        elif not __debug__:
            return fn
        if self.agent is DEFAULT:
            self.agent = getattr(fn, '__self__', None)
        sig = signature(fn)
        fname = fn.__name__
        if self.msg_before is DEFAULT:
            self.msg_before = f">>> {fname}({', '.join(f'{{{x}=}}' for x in sig.parameters if x != 'self')})"
        if self.msg_after is DEFAULT:
            self.msg_after = f"<<< {fname}[{{_etime_}}] Result: {{_result_}}"
        if self.msg_failed is DEFAULT:
            self.msg_failed = f"<-- {fname}[{{_etime_}}] {{_result_}}"
        return wrapper
    #def wrap(self, obj: Any, attrs: Union[str, Sequence]) -> None:
        #for attr in (attrs, ) if isinstance(attrs, str) else attrs:
            #setattr(obj, attr, self(getattr(obj, attr)))

def add_traced(obj: Any, attrs: Union[str, Sequence[str]], **kwargs) -> None:
    """Decorates attributes in object with `traced`.

Arguments:
    obj: Object to be decorated.
    attrs: Object attribute name or sequence of names.
    **kwargs: Keyword arguments to be passed to `traced`.

Hint:
    To remove the `traced` decorator, use `inspect.unwrap`.
"""
    names = (attrs, ) if isinstance(attrs, str) else attrs
    for attr in names:
        setattr(obj, attr, traced(**kwargs)(getattr(obj, attr)))

# Install simple formatter for lastResort handler
if lastResort is not None and lastResort.formatter is None:
    lastResort.setFormatter(Formatter('%(levelname)s: %(message)s'))

def install_null_logger():
    "Installs 'null' logger."
    log = getLogger('null')
    log.propagate = False
    log.disabled = True
