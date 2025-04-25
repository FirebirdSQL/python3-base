# SPDX-FileCopyrightText: 2020-present The Firebird Projects <www.firebirdsql.org>
#
# SPDX-License-Identifier: MIT
#
# PROGRAM/MODULE: firebird-base
# FILE:           firebird/base/logging.py
# DESCRIPTION:    Context-based logging
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

"""firebird-base - Context-based logging

This module provides context-based logging system built on top of standard `logging` module.
It also solves the common logging management problem when various modules use hard-coded
separate loggers, and provides several types of message wrappers that allow lazy message
interpolation using f-string, brace (`str.format`) or dollar (`string.Template`) formats.

The context-based logging:

1. Adds context information into `logging.LogRecord`, that could be used in logging entry formats.
2. Allows assignment of loggers to specific contexts.

This module also provides message wrapper classes (`FStrMessage`, `BraceMessage`,
`DollarMessage`) that defer string formatting until the log record is actually
processed by a handler. This avoids the performance cost of formatting messages
that might be filtered out due to log levels.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterable, Mapping
from enum import Enum, IntEnum
from typing import Any


class FormatElement(Enum):
    """Sentinels used within `LoggingManager.logger_fmt` list."""
    DOMAIN = 1
    TOPIC = 2

#: Sentinel representing the domain element in `LoggingManager.logger_fmt`.
DOMAIN: FormatElement = FormatElement.DOMAIN
#: Sentinel representing the topic element in `LoggingManager.logger_fmt`.
TOPIC: FormatElement = FormatElement.TOPIC

class LogLevel(IntEnum):
    """Mirrors standard `logging` levels for convenience and type hinting.

    Provides symbolic names (e.g., `LogLevel.DEBUG`) corresponding to the
    integer values used by the standard `logging` module (`logging.DEBUG`).
    """
    NOTSET = 0
    DEBUG = 10
    INFO = 20
    WARNING = 30
    ERROR = 40
    CRITICAL = 50
    FATAL = CRITICAL
    WARN = WARNING

class FStrMessage:
    """Lazy logging message wrapper using f-string semantics via `eval`.

    Defers the evaluation of the f-string until the message is actually
    formatted by a handler, improving performance if the message might be
    filtered out by log level settings.

    Note:
        Uses `eval()` internally. Ensure the format string and arguments
        do not contain untrusted user input.

    Example::

        logger.debug(FStrMessage("Processing item {item_id} for user {user!r}",
                                item_id=123, user="Alice"))
        # Formatting only happens if DEBUG level is enabled for the logger/handler.
    """
    def __init__(self, fmt: str, /, *args, **kwargs):
        self.fmt: str = fmt
        self.args: tuple[Any, ...] = args
        self.kwargs: dict[str, Any] = kwargs
        if (args and len(args) == 1 and isinstance(args[0], Mapping) and args[0]):
            self.kwargs = args[0]
        else:
            self.kwargs = kwargs
            if args:
                self.kwargs['args'] = args
    def __str__(self) -> str:
        return eval(f'f"""{self.fmt}"""', globals(), self.kwargs) # noqa: S307

class BraceMessage:
    """Lazy logging message wrapper using brace (`str.format`) style formatting.

    Defers the call to `str.format()` until the message is actually formatted
    by a handler, improving performance for potentially filtered messages.

    Example::

        logger.warning(BraceMessage("Connection failed: host={0}, port={1}",
                                    'server.com', 8080))
        logger.warning(BraceMessage(("Message with coordinates: ({point.x:.2f}, {point.y:.2f})",
                                     point=point))
    """
    def __init__(self, fmt: str, /, *args, **kwargs):
        self.fmt: str = fmt
        self.args: tuple[Any, ...] = args
        self.kwargs: dict[str, Any] = kwargs
    def __str__(self) -> str:
        return self.fmt.format(*self.args, **self.kwargs)

class DollarMessage:
    """Lazy logging message wrapper using dollar (`string.Template`) style formatting.

    Defers the substitution using `string.Template` until the message is actually
    formatted by a handler, improving performance for potentially filtered messages.

    Example::

        from string import Template # Not strictly needed for caller
        logger.info(DollarMessage("Task $name completed with status $status",
                                  name='Cleanup', status='Success'))
    """
    def __init__(self, fmt: str, /, **kwargs):
        self.fmt: str = fmt
        self.kwargs: dict[str, Any] = kwargs
    def __str__(self) -> str:
        from string import Template
        return Template(self.fmt).substitute(**self.kwargs)

class ContextFilter(logging.Filter):
    """Logging filter ensuring context fields exist on `LogRecord` instances.

    Checks for `domain`, `topic`, `agent`, and `context` attributes on each
    log record. If any are missing (e.g., for records from standard loggers
    not using `ContextLoggerAdapter`), it adds them with a value of `None`.

    Usage:
        Attach an instance of this filter to `logging.Handler` objects to ensure
        formatters expecting these fields do not raise `AttributeError`.

    Example::

        handler = logging.StreamHandler()
        handler.addFilter(ContextFilter())
        # ... add handler to logger ...
    """
    def filter(self, record) -> bool:
        for attr in ('domain', 'topic', 'agent', 'context'):
            if not hasattr(record, attr):
                setattr(record, attr, None)
        return True

class ContextLoggerAdapter(logging.LoggerAdapter):
    """Logger adapter injecting context (`domain`, `topic`, `agent`, `context`) info.

    Wraps a standard `logging.Logger`. When a logging method (e.g., `info`, `debug`)
    is called, it adds the context information into the `extra` dictionary, making
    it available as attributes on the resulting `logging.LogRecord`.

    Parameters:
        logger: The standard `logging.Logger` instance to wrap.
        domain: Context Domain name (or None).
        topic: Context Topic name (or None).
        agent: The original agent object or string passed to `get_logger`.
        agent_name: The resolved string name for the agent.
    """
    def __init__(self, logger, domain: str | None, topic: str | None, agent: Any, agent_name: str):
        self.agent = agent
        super().__init__(logger,
                         {'domain': domain,
                          'topic': topic,
                          'agent': agent_name}
                         )
    def process(self, msg: Any, kwargs: dict[str, Any]) -> tuple[Any, dict[str, Any]]:
        """Process the logging message and keyword arguments passed in to
        a logging call to insert contextual information.

        - Ensures `self.extra` contains `domain`, `topic`, and `agent` (from init).
        - Adds `context` to `self.extra`, taking it from `self.agent.log_context`
          if available, otherwise `None`.
        - Merges the adapter's `extra` dictionary with any `extra` dictionary
          passed in `kwargs`, giving precedence to keys in `kwargs['extra']`.
        - Stores the final merged `extra` dictionary into `kwargs['extra']`.

        Returns:
            The possibly modified `msg` and `kwargs`.
        """
        if 'context' not in self.extra:
            self.extra['context'] = getattr(self.agent, 'log_context', None)
        #if "stacklevel" not in kwargs:
            #kwargs["stacklevel"] = 1
        kwargs['extra'] = dict(self.extra, **kwargs['extra']) if 'extra' in kwargs else self.extra
        return msg, kwargs

class LoggingManager:
    """Logging manager.
    """
    def __init__(self):
        self._agent_domain_map: dict[str, str] = {}
        self._domain_agent_map: dict[str, set] = {}
        self._topic_map: dict[str, str] = {}
        self._agent_map: dict[str, str] = {}
        self.__logger_fmt: list[str | FormatElement] = []
        self.__default_domain: str | None = None
        self._logger_factory: Callable = logging.getLogger
    def get_logger_factory(self) -> Callable:
        """Return a callable which is used to create a Logger.
        """
        return self._logger_factory
    def set_logger_factory(self, factory) -> None:
        """Set a callable which is used to create a Logger.

        Parameters:
            factory: The factory callable to be used to instantiate a logger.

        The factory has the following signature: `factory(name, *args, **kwargs)`
        """
        self._logger_factory = factory
    def reset(self) -> None:
        """Resets manager to "factory defaults": no mappings, no `logger_fmt` and undefined
        `default_domain`.
        """
        self._agent_domain_map.clear()
        self._domain_agent_map.clear()
        self._topic_map.clear()
        self._agent_map.clear()
        self.__logger_fmt.clear()
        self.__default_domain = None
    @property
    def logger_fmt(self) -> list[str | FormatElement]:
        """Logger format.

        The list can contain any number of string values and at most one occurrence of `DOMAIN`
        or `TOPIC` enum values. Empty strings are removed.

        The final `logging.Logger` name is constructed by joining elements of this list with
        dots, and with sentinels replaced with `domain` and `topic` names.

        Example::

           logger_fmt = ['app', DOMAIN, TOPIC]
           domain = 'database'
           topic = 'trace'

           Logger name will be: "app.database.trace"
        """
        return self.__logger_fmt
    @logger_fmt.setter
    def logger_fmt(self, value: list[str | FormatElement]) -> None:
        """Sets the logger name format list.

        Validates the list to ensure it contains only non-empty strings and
        at most one `DOMAIN` and one `TOPIC` sentinel.

        :param value: The list defining the logger name format.
        :raises ValueError: If the format list is invalid (e.g., multiple DOMAINs).
        """
        def validated(seq):
            domain_found = False
            topic_found = False
            for item in seq:
                match item:
                    case x if isinstance(x, str):
                        if x:
                            yield item
                    case FormatElement.DOMAIN:
                        if domain_found:
                            raise ValueError("Only one occurence of sentinel DOMAIN allowed")
                        domain_found = True
                        yield item
                    case FormatElement.TOPIC:
                        if topic_found:
                            raise ValueError("Only one occurence of sentinel TOPIC allowed")
                        topic_found = True
                        yield item
                    case _:
                        raise ValueError(f"Unsupported item type {type(item)}")

        self.__logger_fmt = list(validated(value))
    @property
    def default_domain(self) -> str | None:
        """Default domain. Could be either a string or `None`.

        Important:
            When assigned, it does not validate the value type, but converts it to string.
        """
        return self.__default_domain
    @default_domain.setter
    def default_domain(self, value: str | None) -> None:
        self.__default_domain = None if value is None else str(value)
    def _get_logger_name(self, domain: str | None, topic: str | None) -> str:
        """Returns `logging.Logger` name.
        """
        result = []
        for item in self.logger_fmt:
            match item:
                case x if isinstance(x, str):
                    result.append(item)
                case x if x is DOMAIN:
                    if domain:
                        result.append(domain)
                case x if x is TOPIC:
                    if topic:
                        result.append(topic)
        return '.'.join(result)
    def set_topic_mapping(self, topic: str, new_topic: str | None) -> None:
        """Sets or removes the mapping of an topic name to another name.

        Arguments:
            topic: Topic name.
            new_topic: Either `None` or new topic name.

        - When `new_topic` is a string, it maps `topic` to `new_topic`. Empty string is
          like `None`.
        - When `new_topic` is `None`, it removes any mapping.

        Important:
            Does not validate the `new_topic` value type, instead it's converted to string.
        """
        if new_topic:
            self._topic_map[topic] = str(new_topic)
        else:
            self._topic_map.pop(topic, None)
    def get_topic_mapping(self, topic: str) -> str | None:
        """Returns current name mapping for topic.

        Arguments:
            topic: Topic name.

        Returns:
            Reassigned topic name or `None`.
        """
        return self._topic_map.get(topic)
    def get_agent_name(self, agent: Any) -> str:
        """Determine the canonical string name for a given agent identifier.

        Parameters:
            agent: Agent identifier (string, or object).

        Returns:
            The resolved agent name (string).

        Logic:

        1. If `agent` is a string, it's used directly.
        2. If `agent` is an object:
           - Uses `agent._agent_name_` if defined (converting to string if needed).
           - Otherwise, constructs name as `module.ClassQualname`.
        3. Applies any agent name mapping defined via `set_agent_mapping` to the
           name determined in steps 1 or 2.
        4. Ensures the final result is a string.

        Example::

            > from firebird.base.logging import logging_manager
            > logging_manager.get_agent_name(logging_manager)
            'firebird.base.logging.LoggingManager'
        """
        agent_name: Any = agent
        if not isinstance(agent, str):
            if not (agent_name := getattr(agent, '_agent_name_', None)):
                agent_name = f'{agent.__class__.__module__}.{agent.__class__.__qualname__}'
        agent_name = self._agent_map.get(agent_name, agent_name)
        return str(agent_name)
    def set_agent_mapping(self, agent: str, new_agent: str | None) -> None:
        """Sets or removes the mapping of an agent name to another name.

        Parameters:
            agent: Agent name.
            new_agent: New agent name or `None` to remove the mapping. Empty string is like `None`.

        Important:
            Does not validate the `new_agent` value type, instead it's converted to string.
        """
        if new_agent:
            self._agent_map[agent] = str(new_agent)
        else:
            self._agent_map.pop(agent, None)
    def get_agent_mapping(self, agent: str) -> str | None:
        """Returns current name mapping for agent.

        Arguments:
            agent: Agent name.

        Returns:
            Reassigned agent name or `None`.
        """
        return self._agent_map.get(agent)
    def get_agent_domain(self, agent: str) -> str | None:
        """Returns domain name assigned to agent.

        Arguments:
            agent: Agent name.

        Returns:
            Domain assigned to agent or `None`.
        """
        return self._agent_domain_map.get(agent)
    def set_domain_mapping(self, domain: str, agents: Iterable[str] | str | None, *,
                           replace: bool=False) -> None:
        """Sets, updates, or removes agent name mappings to a domain.

        Parameters:
            domain:  Domain name.
            agents:  Iterable with agent names, single agent name, or `None`.
            replace: When True, the new mapping replaces the current one, otherwise the mapping is updated.

        Important:
            Passing `None` to `agents` removes all agent mappings for specified domain,
            regardless of `replace` value.
        """
        # Remove agents that are already mapped
        if agents is not None:
            for agent in set([agents] if isinstance(agents, str) else agents):
                current_domain = self._agent_domain_map.pop(agent, None)
                if current_domain:
                    self._domain_agent_map[current_domain].discard(agent)
                    if not self._domain_agent_map[current_domain]:
                        del self._domain_agent_map[current_domain]
        if (replace or agents is None) and domain in self._domain_agent_map:
            for agent in self._domain_agent_map[domain]:
                del self._agent_domain_map[agent]
            if agents is None:
                del self._domain_agent_map[domain]
                return
        if replace or domain not in self._domain_agent_map:
            self._domain_agent_map[domain] = set()
        agents = set([agents] if isinstance(agents, str) else agents)
        self._domain_agent_map[domain].update(agents)
        for agent in agents:
            self._agent_domain_map[agent] = domain
    def get_domain_mapping(self, domain: str) -> set[str] | None:
        """Returns current agent mapping for domain.

        Arguments:
            domain: Domain name.

        Returns:
            Set of agent names assigned to domain or `None`.
        """
        return self._domain_agent_map.get(domain)
    def get_logger(self, agent: Any, topic: str | None=None) -> ContextLoggerAdapter:
        """Get a ContextLoggerAdapter configured for the specified agent and topic.

        This is the primary function for obtaining a logger in the context logging system.
        It determines the appropriate underlying `logging.Logger` based on the agent's
        domain and the topic, then wraps it in a `ContextLoggerAdapter` to inject
        context information.

        Arguments:
            agent: The agent identifier (object or string). Used to determine the
                   `agent_name` and `domain`.
            topic: Optional topic string for the logging stream (e.g., 'network', 'db').

        Returns:
            A `ContextLoggerAdapter` instance ready for logging.

        Process Flow:

        1. Determine `agent_name` using `get_agent_name(agent)`.
        2. Determine `domain` by looking up `agent_name` in the domain mapping,
           falling back to `self.default_domain`.
        3. Apply topic mapping to the input `topic` (if any).
        4. Construct the final underlying `logging.Logger` name using `self.logger_fmt`,
           substituting the determined `domain` and mapped `topic`.
        5. Get/create the `logging.Logger` instance using `self._logger_factory`
           with the constructed name.
        6. Create and return a `ContextLoggerAdapter` wrapping the logger and
           carrying the `domain`, mapped `topic`, original `agent`, and `agent_name`.
        """
        agent_name = self.get_agent_name(agent)
        agent_name = self._agent_map.get(agent_name, agent_name)
        domain = self._agent_domain_map.get(agent_name, self.default_domain)
        topic = self._topic_map.get(topic, topic)
        # Get logger
        logger = self._logger_factory(self._get_logger_name(domain, topic))
        return ContextLoggerAdapter(logger, domain, topic, agent, agent_name)

#: Context logging manager.
logging_manager: LoggingManager = LoggingManager()
#: Shortcut to global `.LoggingManager.get_logger` function.
get_logger = logging_manager.get_logger
#: Shortcut to global `.LoggingManager.get_agent_name` function.
get_agent_name = logging_manager.get_agent_name
#: Shortcut to global `.LoggingManager.set_domain_mapping` function.
set_domain_mapping = logging_manager.set_domain_mapping
#: Shortcut to global `.LoggingManager.set_agent_mapping` function.
set_agent_mapping = logging_manager.set_agent_mapping
