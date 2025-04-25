# SPDX-FileCopyrightText: 2020-present The Firebird Projects <www.firebirdsql.org>
#
# SPDX-License-Identifier: MIT
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

This module provides trace/audit logging for functions or object methods through context-based
logging provided by logging module.

The trace logging is performed by traced decorator. You can use this decorator directly,
or use TracedMixin class to automatically decorate methods of class instances on creation.
Each decorated callable could log messages before execution, after successful execution or
on failed execution (when unhandled execption is raised by callable). The trace decorator
can automatically add agent and context information, and include parameters passed to callable,
execution time, return value, information about raised exception etc. to log messages.

The trace logging is managed by TraceManager, that allows dynamic configuration of traced
callables at runtime.
"""

from __future__ import annotations

import os
from collections.abc import Callable, Hashable
from configparser import ConfigParser
from dataclasses import dataclass, field
from decimal import Decimal
from enum import IntFlag, auto
from functools import partial, wraps
from inspect import Signature, isfunction, signature
from time import monotonic
from typing import Any

from firebird.base.collections import Registry
from firebird.base.config import (
    BoolOption,
    Config,
    ConfigListOption,
    EnumOption,
    FlagOption,
    IntOption,
    ListOption,
    StrOption,
)
from firebird.base.logging import ContextLoggerAdapter, FStrMessage, LogLevel, get_logger
from firebird.base.strconv import convert_from_str
from firebird.base.types import DEFAULT, UNLIMITED, Distinct, Error, load


class TraceFlag(IntFlag):
    """Flags controlling the behavior of the `traced` decorator and `TraceManager`.

    These flags determine whether tracing is active and which parts of a call
    (before, after success, after failure) should be logged.
    """
    #: No tracing enabled by default flags.
    NONE = 0
    #: Master switch; tracing is performed only if ACTIVE is set.
    ACTIVE = auto()
    #: Log message before the decorated callable executes.
    BEFORE = auto()
    #: Log message after the decorated callable successfully returns.
    AFTER = auto()
    #: Log message if the decorated callable raises an exception.
    FAIL = auto()

@dataclass
class TracedItem(Distinct):
    """Holds the trace specification for a single method within a registered class.

    Stored by `TraceManager` for each method configured via `add_trace` or
    `load_config`. Applied by `trace_object`.

    Arguments:
        method: The name of the method to be traced.
        decorator: The decorator callable (usually `traced` or a custom one) to apply.
        args: Positional arguments to pass to the decorator factory.
        kwargs: Keyword arguments to pass to the decorator factory.
    """
    #: The name of the method to be traced.
    method: str
    #: The decorator callable (usually `traced` or a custom one) to apply.
    decorator: Callable
    #: Positional arguments to pass to the decorator factory.
    args: list[Any] = field(default_factory=list)
    #: Keyword arguments to pass to the decorator factory.
    kwargs: dict[str, Any] = field(default_factory=dict)
    def get_key(self) -> Hashable:
        """Returns Distinct key for traced item [method]."""
        return self.method

@dataclass
class TracedClass(Distinct):
    """Represents a class registered for tracing within the `TraceManager`.

    Holds a registry (`Registry[TracedItem]`) of trace specifications for
    methods belonging to this class.

    Arguments:
        cls: The class type registered for tracing.
        traced: A registry mapping method names to `TracedItem` specifications.
    """
    #: The class type registered for tracing.
    cls: type
    #: A registry mapping method names to `TracedItem` specifications.
    traced: Registry = field(default_factory=Registry)
    def get_key(self) -> Hashable:
        """Returns Distinct key for traced item [cls]."""
        return self.cls


class TracedMeta(type):
    """Metaclass that instruments instances on creation.
    """
    def __call__(cls: type, *args, **kwargs):
        return trace_object(super().__call__(*args, **kwargs), strict=True)

class TracedMixin(metaclass=TracedMeta):
    """Mixin class to automatically enable tracing for descendants.

    Subclasses inheriting from `TracedMixin` are automatically registered with the
    `trace_manager` upon definition. When instances of these subclasses are created,
    their methods are automatically instrumented by `trace_object` according to the
    currently active trace specifications in the `trace_manager`.
    """
    def __init_subclass__(cls: type, /, **kwargs) -> None:
        super().__init_subclass__(**kwargs)
        trace_manager.register(cls)

class traced: # noqa: N801
    """Decorator factory for adding trace/audit logging to callables.

    Creates a decorator that wraps a function or method to log messages
    before execution, after successful execution, and/or upon failure,
    based on configured flags and messages. Integrates with the
    `firebird.base.logging` context logger.

    Note:
        The decorator is *only applied* if tracing is globally enabled via
        the `FBASE_TRACE` environment variable or if `__debug__` is true
        (i.e., Python is not run with -O). If disabled globally, the original
        un-decorated function is returned. Runtime behavior (whether logs
        are actually emitted) is further controlled by `TraceManager.flags`.

    Arguments:
        agent: Agent identifier for logging context (object or string).
               If `DEFAULT`, uses `self` for methods or `'function'` otherwise.
        topic: Logging topic (default: 'trace').
        msg_before: Format string (f-string style) for log message before execution.
                    If `DEFAULT`, a standard message is generated.
        msg_after: Format string for log message after successful execution. Available
                   context includes `_etime_` (execution time string) and `_result_`
                   (return value, if `has_result` is true). If `DEFAULT`, a standard
                   message is generated.
        msg_failed: Format string for log message on exception. Available context includes
                    `_etime_` and `_exc_` (exception string). If `DEFAULT`, a standard
                    message is generated.
        flags: `TraceFlag` values to override `TraceManager.flags` for this specific
               decorator instance. Allows fine-grained control per traced callable.
        level: `LogLevel` for trace messages (default: `LogLevel.DEBUG`).
        max_param_length: Max length for string representation of parameters/result
                          in logs. Longer values are truncated (default: `UNLIMITED`).
        extra: Dictionary of extra data to add to the `LogRecord`.
        callback: Optional callable `func(agent) -> bool`. If provided, it's called
                  before logging to check if tracing is permitted for this specific call.
        has_result: Boolean or `DEFAULT`. If True, include result in `msg_after`.
                    If `DEFAULT`, inferred from function's return type annotation
                    (considered True unless annotation is `None`).
        with_args: If True (default), make function arguments available by name for
                   interpolation in `msg_before`.
    """
    def __init__(self, *, agent: Any | DEFAULT=DEFAULT, topic: str='trace',
                 msg_before: str | DEFAULT=DEFAULT, msg_after: str | DEFAULT=DEFAULT,
                 msg_failed: str | DEFAULT=DEFAULT, flags: TraceFlag=TraceFlag.NONE,
                 level: LogLevel=LogLevel.DEBUG, max_param_length: int | UNLIMITED=UNLIMITED,
                 extra: dict | None=None, callback: Callable[[Any], bool] | None=None,
                 has_result: bool | DEFAULT=DEFAULT, with_args: bool=True):
        #: Trace/audit message logged before decorated function
        self.msg_before: str | DEFAULT = msg_before
        #: Trace/audit message logged after decorated function
        self.msg_after: str | DEFAULT = msg_after
        #: Trace/audit message logged when decorated function raises an exception
        self.msg_failed: str | DEFAULT = msg_failed
        #: Agent identification
        self.agent: Any | DEFAULT = agent
        #: Trace/audit logging topic
        self.topic: str = topic
        #: Trace flags override
        self.flags: TraceFlag = flags
        #: Logging level for trace/audit messages
        self.level: LogLevel = level
        #: Max. length of parameters (longer will be trimmed)
        self.max_len: int | UNLIMITED = max_param_length
        #: Extra data for `LogRecord`
        self.extra: dict[str, Any] = extra
        #: Callback function that gets the agent identification as argument,
        #: and must return True/False indicating whether trace is allowed.
        self.callback: Callable[[Any], bool] = self.__callback if callback is None else callback
        #: Indicator whether function has result value. If True, `_result_` is available
        #: for interpolation in `msg_after`.
        self.has_result: bool | DEFAULT= has_result
        #: If True, function arguments are available for interpolation in `msg_before`
        self.with_args: bool = with_args
    def __callback(self, agent: Any) -> bool: # noqa: ARG002
        """Default callback, does nothing.
        """
        return True
    def set_before_msg(self, fn: Callable, sig: Signature) -> None:
        """Generate the default log message template for before execution."""
        if self.with_args:
            self.msg_before = f">>> {fn.__name__}({', '.join(f'{{{x}=}}' for x in sig.parameters if x != 'self')})"
        else:
            self.msg_before = f">>> {fn.__name__}"
    def set_after_msg(self, fn: Callable, sig: Signature) -> None: # noqa: ARG002
        """Generate the default log message template for successful execution."""
        self.msg_after = f"<<< {fn.__name__}[{{_etime_}}] Result: {{_result_!r}}" \
            if self.has_result else f"<<< {fn.__name__}[{{_etime_}}]"
    def set_fail_msg(self, fn: Callable, sig: Signature) -> None: # noqa: ARG002
        """Generate the default log message template for failed execution."""
        self.msg_failed = f"<-- {fn.__name__}[{{_etime_}}] {{_exc_}}"
    def log_before(self, logger: ContextLoggerAdapter, params: dict) -> None:
        """Log the 'before' message using the configured template and logger."""
        logger.log(self.level, FStrMessage(self.msg_before, params))
    def log_after(self, logger: ContextLoggerAdapter, params: dict) -> None:
        """Log the 'after' message using the configured template and logger."""
        logger.log(self.level, FStrMessage(self.msg_after, params))
    def log_failed(self, logger: ContextLoggerAdapter, params: dict) -> None:
        """Log the 'failed' message using the configured template and logger."""
        logger.log(self.level, FStrMessage(self.msg_failed, params))
    def __call__(self, fn: Callable) -> Callable:
        @wraps(fn)
        def wrapper(*args, **kwargs) -> Any:
            """The actual wrapper function applied to the decorated callable.

            Checks runtime flags, prepares parameters, logs messages according
            to flags (before/after/fail), measures execution time, and handles
            exceptions for logging purposes before re-raising them.
            """
            # Combine global flags with decorator-specific overrides
            flags = trace_manager.flags | self.flags
            # Check if ACTIVE flag is set AND at least one logging flag (BEFORE/AFTER/FAIL) is set
            if enabled := ((TraceFlag.ACTIVE in flags) and int(flags) > 1):
                params = {}
                bound = sig.bind_partial(*args, **kwargs)
                # If it's not a bound method, look for 'self'
                log = get_logger(bound.arguments.get('self', 'function') if self.agent is None
                                 else self.agent, self.topic)
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
            result = None
            start = monotonic()
            try:
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

class BaseTraceConfig(Config):
    """Base class defining common configuration options for trace settings.

    Used as a base for global trace config, per-class config, and per-method config.
    Corresponds typically to settings within a section of a configuration file.
    """
    def __init__(self, name: str):
        super().__init__(name)
        #: Agent identification
        self.agent: StrOption = \
            StrOption('agent', "Agent identification")
        #: Trace/audit logging topic
        self.topic: StrOption = \
            StrOption('topic', "Trace/audit logging topic")
        #: Trace/audit message logged before decorated function
        self.msg_before: StrOption = \
            StrOption('msg_before', "Trace/audit message logged before decorated function")
        #: Trace/audit message logged after decorated function
        self.msg_after: StrOption = \
            StrOption('msg_after', "Trace/audit message logged after decorated function")
        #: Trace/audit message logged when decorated function raises an exception
        self.msg_failed: StrOption = \
            StrOption('msg_failed', "Trace/audit message logged when decorated function raises an exception")
        #: Trace flags override
        self.flags: FlagOption = \
            FlagOption('flags', TraceFlag, "Trace flags override")
        #: Logging level for trace/audit messages
        self.level: EnumOption = \
            EnumOption('level', LogLevel, "Logging level for trace/audit messages")
        #: Max. length of parameters (longer will be trimmed)
        self.max_param_length: IntOption = \
            IntOption('max_param_length', "Max. length of parameters (longer will be trimmed)")
        #: Indicator whether function has result value
        self.has_result: BoolOption = \
            BoolOption('has_result', "Indicator whether function has result value")
        #: If True, function arguments are available for interpolation in `msg_before`
        self.with_args: BoolOption = \
            BoolOption('with_args',
                       "If True, function arguments are available for interpolation in `msg_before`")

class TracedMethodConfig(BaseTraceConfig):
    """Defines the structure for a configuration section specifying trace
    settings specific to a single class method.

    Used within `TracedClassConfig.special` list. The section name itself is
    referenced in the parent `TracedClassConfig` section.
    """
    def __init__(self, name: str):
        super().__init__(name)
        #: Class method name [required]
        self.method: StrOption = \
            StrOption('method', "Class method name", required=True)

class TracedClassConfig(BaseTraceConfig):
    """Defines the structure for a configuration section specifying trace
    settings for a Python class and its methods.

    The section name itself is referenced in the main `TraceConfig` section.
    See the module documentation for an example INI structure.
    """
    def __init__(self, name: str):
        super().__init__(name)
        #: Fully qualified class name [required]
        self.source: StrOption = \
            StrOption('source', "Fully qualified class name", required=True)
        #: Names of traced class methods
        self.methods: ListOption = \
            ListOption('methods', str, "Names of traced class methods")
        #: Configuration sections with extended config of traced class methods
        self.special: ConfigListOption = \
            ConfigListOption('special',
                             "Configuration sections with extended config of traced class methods",
                             TracedMethodConfig)
        #: Wherher configuration should be applied also to all registered descendant classes [default: True].
        self.apply_to_descendants: BoolOption = \
            BoolOption('apply_to_descendants',
                       "Configuration should be applied also to all registered descendant classes",
                       default=True)

class TraceConfig(BaseTraceConfig):
    """Defines the structure for the main trace configuration section (typically '[trace]').

    Holds global default trace settings and lists the sections defining specific
    traced classes. See the module documentation for an example INI structure.
    """
    def __init__(self, name: str):
        super().__init__(name)
        #: When True, unregistered classes are registered automatically [default: True].
        self.autoregister: BoolOption = \
            BoolOption('autoregister',
                       "When True, unregistered classes are registered automatically",
                       default=True)
        #: Configuration sections with traced Python classes [required].
        self.classes: ConfigListOption = \
            ConfigListOption('classes',
                             "Configuration sections with traced Python classes",
                             TracedClassConfig, required=True)

class TraceManager:
    """Trace manager.
    """
    def __init__(self):
        #: Decorator factory used by `add_trace` (default: `traced`). Can be replaced.
        self.decorator: Callable = traced
        #: Internal registry storing `TracedClass` specifications.
        self._traced: Registry = Registry()
        #: Current runtime trace flags, controlling overall behavior.
        self._flags: TraceFlag = TraceFlag.NONE
        # Initialize flags based on environment variables (FBASE_TRACE_*) and __debug__
        # Active flag
        self.trace_active: bool = convert_from_str(bool, os.getenv('FBASE_TRACE', str(__debug__)))
        # Specific logging flags
        if convert_from_str(bool, os.getenv('FBASE_TRACE_BEFORE', 'no')): # pragma: no cover
            self.set_flag(TraceFlag.BEFORE)
        if convert_from_str(bool, os.getenv('FBASE_TRACE_AFTER', 'no')): # pragma: no cover
            self.set_flag(TraceFlag.AFTER)
        # Note: FAIL is enabled by default unless FBASE_TRACE_FAIL is explicitly 'no'
        if convert_from_str(bool, os.getenv('FBASE_TRACE_FAIL', 'yes')):
            self.set_flag(TraceFlag.FAIL)
    def is_registered(self, cls: type) -> bool:
        """Return True if class is registered.
        """
        return cls in self._traced
    def clear(self) -> None:
        """Removes all trace specifications.
        """
        for cls in self._traced:
            cls.traced.clear()
    def register(self, cls: type) -> None:
        """Register class for trace.

        Arguments:
            cls: Class to be registered.

        Does nothing if class is already registered.
        """
        if cls not in self._traced:
            self._traced.store(TracedClass(cls))
    def add_trace(self, cls: type, method: str, / , *args, **kwargs) -> None:
        """Store or update the trace specification for a specific class method.

        Registers how a method should be decorated (using `self.decorator`) when
        `trace_object` is called on an instance of `cls` or its registered descendants.
        This specification can be overridden or augmented by settings loaded via
        `load_config`.

        Arguments:
            cls: Registered traced class type.
            method: The name of the method within `cls` to trace.
            *args: Positional arguments for the decorator factory (`self.decorator`).
            **kwargs: Keyword arguments for the decorator factory (`self.decorator`).
        """
        self._traced[cls].traced.update(TracedItem(method, self.decorator, args, kwargs))
    def remove_trace(self, cls: type, method: str) -> None:
        """Remove trace specification for class method.

        Arguments:
            cls: Registered traced class
            method: Name of class method
        """
        del self._traced[cls].traced[method]
    def trace_object(self, obj: Any, *, strict: bool=False) -> Any:
        """Apply registered trace decorators to the methods of an object instance.

        Iterates through the trace specifications (`TracedItem`) registered for the
        object's class (via `add_trace` or `load_config`). For each specification,
        it wraps the corresponding method on the `obj` instance using the specified
        decorator and arguments. Modifies the object *in place*.

        Arguments:
            obj: The object instance whose methods should be instrumented.
            strict: If True, raise TypeError if `obj`'s class is not registered.
                    If False (default), return `obj` unmodified if not registered.

        Returns:
            The (potentially modified) object instance `obj`.

        Raises:
            TypeError: If `obj`'s class is not registered and `strict` is True.
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
            return obj
        for item in entry.traced:
            setattr(obj, item.method, item.decorator(*item.args, **item.kwargs)(getattr(obj, item.method)))
        return obj
    def load_config(self, config: ConfigParser, section: str='trace') -> None:
        """Load and apply trace configurations from a `ConfigParser` instance.

        Parses the specified `section` (and referenced sub-sections) using the
        `TraceConfig`, `TracedClassConfig`, and `TracedMethodConfig` structures.
        Updates the `TraceManager`'s flags and trace specifications (`add_trace`).

        Arguments:
            config:  `ConfigParser` instance containing the trace configuration.
            section: Name of the main trace configuration section (default: 'trace').

        Note:
            This method *adds to or updates* existing trace specifications. It does
            not clear previous configurations unless the loaded configuration explicitly
            overwrites specific settings.

        Raises:
            Error: If configuration references a class that is not registered and
                   `autoregister` is False, or if the class cannot be loaded via `load()`.
            KeyError, ValueError: If the configuration file structure is invalid or
                                  contains invalid values according to the `Option` types.
        """
        def build_kwargs(from_cfg: BaseTraceConfig) -> dict[str, Any]:
            result = {}
            for item in ['agent', 'topic', 'msg_before', 'msg_after',
                         'msg_failed', 'flags', 'level', 'max_param_length',
                         'has_result', 'with_args']:
                if (value := getattr(from_cfg, item).value) is not None:
                    result[item] = value
            return result

        def apply_on(cls):
            if (items := cls_cfg.methods.value) is not None:
                if (len(items) == 1) and (items[0] == '*'):
                    items = [i for i in dir(cls) if not i.startswith('_') and isfunction(getattr(cls, i))]
                for item in items:
                    self.add_trace(cls, item, *[], **cls_kwargs)
            if (items := cls_cfg.special.value) is not None:
                for mcfg in items:
                    method = mcfg.method.value
                    kwargs = {}
                    kwargs.update(cls_kwargs)
                    kwargs.update(build_kwargs(mcfg))
                    self.add_trace(cls, method, *[], **kwargs)
        def with_name(name: str, obj: Any) -> bool:
            return f'{obj.cls.__module__}.{obj.cls.__name__}' == name

        cfg = TraceConfig('trace')
        cfg.load_config(config, section)
        self.flags = cfg.flags.value
        global_kwargs = build_kwargs(cfg)
        for cls_cfg in cfg.classes.value:
            cls_name = cls_cfg.source.value
            cls_kwargs = {}
            cls_kwargs.update(global_kwargs)
            cls_kwargs.update(build_kwargs(cls_cfg))
            if (cls_desc := self._traced.find(partial(with_name, cls_name))) is None:
                if cfg.autoregister.value:
                    cls = load(':'.join(cls_name.rsplit('.', 1)))
                    self.register(cls)
                else:
                    raise Error(f"Class '{cls_name}' is not registered for trace.")
            else:
                cls = cls_desc.cls
            apply_on(cls)
            if cls_cfg.apply_to_descendants.value:
                for cls_desc in self._traced.values():
                    if (cls_desc.cls is not cls) and issubclass(cls_desc.cls, cls):
                        apply_on(cls_desc.cls)
    def set_flag(self, flag: TraceFlag) -> None:
        """Set flag specified by `flag` mask.
        """
        self._flags |= flag
    def clear_flag(self, flag: TraceFlag) -> None:
        """Clear flag specified by `flag` mask.
        """
        self._flags &= ~flag
    @property
    def flags(self) -> TraceFlag:
        """Trace flags.
        """
        return self._flags
    @flags.setter
    def flags(self, value: TraceFlag) -> None:
        self._flags = value if isinstance(value, TraceFlag) else TraceFlag(value)
    @property
    def trace_active(self) -> bool:
        """True if trace is active.
        """
        return TraceFlag.ACTIVE in self._flags
    @trace_active.setter
    def trace_active(self, value: bool) -> None:
        if value:
            self._flags |= TraceFlag.ACTIVE
        else:
            self._flags &= ~TraceFlag.ACTIVE

#: Trace manager singleton instance.
trace_manager: TraceManager = TraceManager()

#: Shortcut for `trace_manager.add_trace()`
add_trace = trace_manager.add_trace
#: Shortcut for `trace_manager.remove_trace()`
remove_trace = trace_manager.remove_trace
#: Shortcut for `trace_manager.trace_object()`
trace_object = trace_manager.trace_object
