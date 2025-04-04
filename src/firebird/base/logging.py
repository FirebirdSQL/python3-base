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

"""

from __future__ import annotations

import logging
from collections.abc import Iterable, Mapping
from enum import Enum, IntEnum
from typing import Any


class FormatElement(Enum):
    DOMAIN = 1
    TOPIC = 2

DOMAIN = FormatElement.DOMAIN
TOPIC = FormatElement.TOPIC

class LogLevel(IntEnum):
    """Shadow enumeration for logging levels.
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
    """Log message that uses `f-string` format.
    """
    def __init__(self, fmt, /, *args, **kwargs):
        self.fmt = fmt
        self.args = args
        self.kwargs = kwargs
        if (args and len(args) == 1 and isinstance(args[0], Mapping) and args[0]):
            self.kwargs = args[0]
        else:
            self.kwargs = kwargs
            if args:
                self.kwargs['args'] = args
    def __str__(self):
        return eval(f'f"""{self.fmt}"""', globals(), self.kwargs) # noqa: S307
        #return self.fmt.format(*self.args, **self.kwargs)

class BraceMessage:
    """Log message that uses brace (`str.format`) format.
    """
    def __init__(self, fmt, /, *args, **kwargs):
        self.fmt = fmt
        self.args = args
        self.kwargs = kwargs
    def __str__(self):
        return self.fmt.format(*self.args, **self.kwargs)

class DollarMessage:
    """Log message that uses dollar (`string.Template`) format.
    """
    def __init__(self, fmt, /, **kwargs):
        self.fmt = fmt
        self.kwargs = kwargs
    def __str__(self):
        from string import Template
        return Template(self.fmt).substitute(**self.kwargs)

class ContextFilter(logging.Filter):
    """Filter that adds `domain`, `topic`, `agent` and `context` fields to `logging.LogRecord`
    if they are not already present.
    """
    def filter(self, record):
        for attr in ('domain', 'topic', 'agent', 'context'):
            if not hasattr(record, attr):
                setattr(record, attr, None)
        return True

class ContextLoggerAdapter(logging.LoggerAdapter):
    """A logger adapter that adds `domain`, `topic`, `agent` and `context` items to `extra`
    dictionary which is used to populate the `__dict__` of the `logging.LogRecord` created for the
    logging event.

    Parameters:
        logger: Adapted Logger instance.
        domain: Context Domain name.
        topic: Context Topic name.
        agent: Agent identification (object or string)
        agent_name: Agent name
    """
    def __init__(self, logger, domain: str, topic: str, agent: Any, agent_name: str):
        self.agent = agent
        super().__init__(logger,
                         {'domain': domain,
                          'topic': topic,
                          'agent': agent_name}
                         )
    def process(self, msg, kwargs):
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
        self._logger_factory = logging.getLogger
    def get_logger_factory(self):
        """Return a callable which is used to create a Logger.
        """
        return self._logger_factory
    def set_logger_factory(self, factory):
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
    def _get_logger_name(self, domain: str, topic: str | None) -> str:
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
        """Returns agent name.

        Parameters:
            agent: Agent name or object that identifies the agent (typically an instance
                   of agent class).

        Returns:
            Agent name. If `agent` value is a string, is returned as is. If it's an object,
            it returns value of its `_agent_name_` attribute if defined, otherwise it returns
            name in "MODULE_NAME.CLASS_QUALNAME" format. If `_agent_name_` value is not a string,
            it's converted to string.

        Important:
            This method does apply agent name mapping to returned value.

        Example::

            > from firebird.base.logging import manager
            > manager.get_agent_name(manager)
            'firebird.base.logging.LoggingManager'
        """
        agent_name = agent
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
        """Returns `.ContextLoggerAdapter` for specified `agent` and optional `topic`.

        Arguments:
            agent: Agent specification. Calls `.get_agent_name` to determine agent's name.
            topic: Optional topic.

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
