# SPDX-FileCopyrightText: 2020-present The Firebird Projects <www.firebirdsql.org>
#
# SPDX-License-Identifier: MIT
#
# PROGRAM/MODULE: firebird-base
# FILE:           test/test_logging.py
# DESCRIPTION:    Tests for firebird.base.logging
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

import logging
from contextlib import contextmanager

import pytest

import firebird.base.logging as fblog

from firebird.base.types import *

class Namespace:
    "Simple Namespace"

class NaiveAgent:
    "Naive agent"
    @property
    def name(self):
        return fblog.get_agent_name(self)

class AwareAgentAttr:
    "Aware agent with _agent_name_ as attribute"
    _agent_name_ = "_agent_name_attr"
    @property
    def name(self):
        return fblog.get_agent_name(self)

class AwareAgentProperty:
    "Aware agent with _agent_name_ as dynamic property"
    def __init__(self, agent_name: Any):
        self._int_agent_name = agent_name
    @property
    def _agent_name_(self) -> Any:
        return self._int_agent_name
    @property
    def name(self):
        return fblog.get_agent_name(self)


@contextmanager
def context_filter(to):
    ctxfilter = fblog.ContextFilter()
    to.addFilter(ctxfilter)
    yield
    to.removeFilter(ctxfilter)

def test_fstr_message():
    ns = Namespace()
    ns.nested = Namespace()
    ns.nested.item = "item!"
    ns.attr = "attr"
    ns.number = 5
    #
    msg = fblog.FStrMessage("-> Message <-")
    assert str(msg) == "-> Message <-"
    msg = fblog.FStrMessage("Let's see {ns.number=} * 5 = {ns.number * 5}, [{ns.nested.item}] or {ns.attr!r}", {"ns": ns})
    assert str(msg) == "Let's see ns.number=5 * 5 = 25, [item!] or 'attr'"
    msg = fblog.FStrMessage("Let's see {ns.number=} * 5 = {ns.number * 5}, [{ns.nested.item}] or {ns.attr!r}", ns=ns)
    assert str(msg) == "Let's see ns.number=5 * 5 = 25, [item!] or 'attr'"
    msg = fblog.FStrMessage("Let's see {args[0]=} * 5 = {args[0] * 5}, {ns.attr!r}", 5, ns=ns)
    assert str(msg) == "Let's see args[0]=5 * 5 = 25, 'attr'"

def test_brace_message():
    point = Namespace()
    point.x = 0.5
    point.y = 0.5
    msg = fblog.BraceMessage("Message with {0} {1}", 2, "placeholders")
    assert str(msg) == "Message with 2 placeholders"
    msg = fblog.BraceMessage("Message with coordinates: ({point.x:.2f}, {point.y:.2f})", point=point)
    assert str(msg) == "Message with coordinates: (0.50, 0.50)"

def test_dollar_message():
    point = Namespace()
    point.x = 0.5
    point.y = 0.5
    msg = fblog.DollarMessage("Message with $num $what", num=2, what="placeholders")
    assert str(msg) == "Message with 2 placeholders"

def test_context_filter(caplog):
    caplog.set_level(logging.INFO)
    log = logging.getLogger()
    log.info("Message")
    for rec in caplog.records:
        assert not hasattr(rec, "domain")
        assert not hasattr(rec, "topic")
        assert not hasattr(rec, "agent")
        assert not hasattr(rec, "context")
    caplog.clear()
    with context_filter(log):
        log.info("Message")
        for rec in caplog.records:
            assert rec.domain is None
            assert rec.topic is None
            assert rec.agent is None
            assert rec.context is None

def test_context_adapter(caplog):
    caplog.set_level(logging.INFO)
    log = fblog.ContextLoggerAdapter(logging.getLogger(), "domain", "topic", "agent", "agent_name")
    log.info("Message")
    for rec in caplog.records:
        assert rec.domain == "domain"
        assert rec.topic == "topic"
        assert rec.agent == "agent_name"
        assert rec.context is None

def test_context_adapter_filter(caplog):
    caplog.set_level(logging.INFO)
    log = fblog.ContextLoggerAdapter(logging.getLogger(), "domain", "topic", "agent", "agent_name")
    with context_filter(log.logger):
        log.info("Message")
        for rec in caplog.records:
            assert rec.domain == "domain"
            assert rec.topic == "topic"
            assert rec.agent == "agent_name"
            assert rec.context is None

def test_mngr_default_domain():
    manager = fblog.LoggingManager()
    assert manager.default_domain is None
    manager.default_domain = "default_domain"
    assert manager.default_domain == "default_domain"

def test_mngr_logger_fmt():
    manager = fblog.LoggingManager()
    assert manager.logger_fmt == []
    value = ["app"]
    manager.logger_fmt = value
    assert manager.logger_fmt == value
    value[0] = "xxx"
    assert manager.logger_fmt == ["app"]
    manager.logger_fmt = ["app", "", "module"]
    assert manager.logger_fmt == ["app", "module"]
    with pytest.raises(ValueError) as cm:
        manager.logger_fmt = ["app", None, "module"]
    assert cm.value.args == ("Unsupported item type <class 'NoneType'>",)
    with pytest.raises(ValueError) as cm:
        manager.logger_fmt = [1]
    assert cm.value.args == ("Unsupported item type <class 'int'>",)
    with pytest.raises(ValueError) as cm:
        manager.logger_fmt = ["app", fblog.TOPIC, "x", fblog.TOPIC]
    assert cm.value.args == ("Only one occurence of sentinel TOPIC allowed",)
    with pytest.raises(ValueError) as cm:
        manager.logger_fmt = ["app", fblog.DOMAIN, "x", fblog.DOMAIN]
    assert cm.value.args == ("Only one occurence of sentinel DOMAIN allowed",)
    value = ["app", fblog.DOMAIN, fblog.TOPIC]
    manager.logger_fmt = value
    assert manager.logger_fmt == value

def test_mngr_get_logger_name():
    manager = fblog.LoggingManager()
    assert manager._get_logger_name("domain", "topic") == ""
    manager.logger_fmt = ["app"]
    assert manager._get_logger_name("domain", "topic") == "app"
    manager.logger_fmt = ["app", "module"]
    assert manager._get_logger_name("domain", "topic") == "app.module"
    manager.logger_fmt = ["app", fblog.DOMAIN]
    assert manager._get_logger_name("domain", "topic") == "app.domain"
    manager.logger_fmt = ["app", fblog.TOPIC]
    assert manager._get_logger_name("domain", "topic") == "app.topic"
    manager.logger_fmt = ["app", fblog.TOPIC, "", fblog.DOMAIN]
    assert manager._get_logger_name("domain", "topic") == "app.topic.domain"

def test_mngr_set_get_topic_mapping():
    topic = "topic"
    new_topic = "topic-X"
    manager = fblog.LoggingManager()
    assert len(manager._topic_map) == 0
    assert manager.get_topic_mapping(topic) is None
    #
    manager.set_topic_mapping(topic, new_topic)
    assert len(manager._topic_map) == 1
    assert manager.get_topic_mapping(topic) == new_topic
    #
    manager.set_topic_mapping(topic, None)
    assert len(manager._topic_map) == 0
    assert manager.get_topic_mapping(topic) is None
    #
    manager.set_topic_mapping(topic, DEFAULT)
    assert manager.get_topic_mapping(topic) == str(DEFAULT)
    assert len(manager._topic_map) == 1
    #
    manager.set_topic_mapping(new_topic, DEFAULT)
    assert len(manager._topic_map) == 2

def test_mngr_topic_domain_to_logger_name():
    agent = NaiveAgent()
    manager = fblog.LoggingManager()
    manager.logger_fmt = ["app", fblog.TOPIC, fblog.DOMAIN]
    #
    log = manager.get_logger(agent, "topic")
    assert log.logger.name == "app.topic"
    #
    manager.logger_fmt = ["app"]
    assert manager._get_logger_name("domain", "topic") == "app"
    #
    manager.logger_fmt = ["app", "module"]
    assert manager._get_logger_name("domain", "topic") == "app.module"
    #
    manager.logger_fmt = ["app", fblog.DOMAIN]
    assert manager._get_logger_name("domain", "topic") == "app.domain"
    #
    manager.logger_fmt = ["app", fblog.TOPIC]
    assert manager._get_logger_name("domain", "topic") == "app.topic"
    #
    manager.logger_fmt = ["app", fblog.TOPIC, "", fblog.DOMAIN]
    assert manager._get_logger_name("domain", "topic") == "app.topic.domain"

def test_mngr_get_agent_name_str():
    agent = "agent"
    manager = fblog.LoggingManager()
    assert manager.get_agent_name(agent) == agent

def test_mngr_get_agent_name_naive_obj():
    agent = NaiveAgent()
    manager = fblog.LoggingManager()
    assert manager.get_agent_name(agent) == "tests.test_logging.NaiveAgent"

def test_mngr_get_agent_name_aware_obj_attr():
    agent = AwareAgentAttr()
    manager = fblog.LoggingManager()
    assert manager.get_agent_name(agent) == "_agent_name_attr"

def test_mngr_get_agent_name_aware_obj_dynamic():
    agent = AwareAgentProperty("_agent_name_property")
    manager = fblog.LoggingManager()
    assert manager.get_agent_name(agent) == "_agent_name_property"
    agent._int_agent_name = DEFAULT
    assert manager.get_agent_name(agent) == "DEFAULT"

def test_mngr_set_get_agent_mapping():
    agent = "agent"
    new_agent = "agent-X"
    manager = fblog.LoggingManager()
    assert len(manager._agent_map) == 0
    assert manager.get_agent_mapping(agent) is None
    #
    manager.set_agent_mapping(agent, new_agent)
    assert len(manager._agent_map) == 1
    assert manager.get_agent_mapping(agent) == new_agent
    #
    manager.set_agent_mapping(agent, None)
    assert len(manager._agent_map) == 0
    assert manager.get_agent_mapping(agent) is None
    #
    manager.set_agent_mapping(agent, DEFAULT)
    assert len(manager._agent_map) == 1
    assert manager.get_agent_mapping(agent) == str(DEFAULT)
    #
    manager.set_agent_mapping(new_agent, DEFAULT)
    assert len(manager._agent_map) == 2

def test_mngr_set_get_domain_mapping():
    domain = "domain"
    agent_naive = NaiveAgent()
    agent_aware_attr = AwareAgentAttr()
    agent_aware_prop_1 = AwareAgentProperty("agent_aware_prop_1")
    agent_aware_prop_2 = AwareAgentProperty("agent_aware_prop_2")
    manager = fblog.LoggingManager()
    assert len(manager._agent_domain_map) == 0
    assert len(manager._domain_agent_map) == 0
    assert manager.get_agent_domain(agent_naive.name) is None
    assert manager.get_agent_domain(agent_aware_attr.name) is None
    assert manager.get_agent_domain(agent_aware_prop_1.name) is None
    assert manager.get_agent_domain(agent_aware_prop_2.name) is None
    assert manager.get_domain_mapping(domain) is None
    # Set
    manager.set_domain_mapping(domain, [agent_naive.name, agent_aware_attr.name])
    assert len(manager._agent_domain_map) == 2
    assert len(manager._domain_agent_map) == 1
    assert manager.get_domain_mapping(domain) == set([agent_naive.name, agent_aware_attr.name])
    assert manager.get_agent_domain(agent_naive.name) == domain
    assert manager.get_agent_domain(agent_aware_attr.name) == domain
    assert manager.get_agent_domain(agent_aware_prop_1.name) is None
    assert manager.get_agent_domain(agent_aware_prop_2.name) is None
    # Update
    manager.set_domain_mapping(domain, [agent_naive.name, agent_aware_prop_1.name])
    assert len(manager._agent_domain_map) == 3
    assert len(manager._domain_agent_map) == 1
    assert manager.get_domain_mapping(domain) == set([agent_naive.name, agent_aware_attr.name,
                                                      agent_aware_prop_1.name])
    assert manager.get_agent_domain(agent_naive.name) == domain
    assert manager.get_agent_domain(agent_aware_attr.name) == domain
    assert manager.get_agent_domain(agent_aware_prop_1.name) == domain
    assert manager.get_agent_domain(agent_aware_prop_2.name) is None
    # Replace + single name
    manager.set_domain_mapping(domain, agent_naive.name, replace=True)
    assert len(manager._agent_domain_map) == 1
    assert len(manager._domain_agent_map) == 1
    assert manager.get_domain_mapping(domain) == set([agent_naive.name])
    assert manager.get_agent_domain(agent_naive.name) == domain
    assert manager.get_agent_domain(agent_aware_attr.name) is None
    assert manager.get_agent_domain(agent_aware_prop_1.name) is None
    assert manager.get_agent_domain(agent_aware_prop_2.name) is None
    # Remove
    manager.set_domain_mapping(domain, None)
    assert len(manager._agent_domain_map) == 0
    assert len(manager._domain_agent_map) == 0
    assert manager.get_agent_domain(agent_naive.name) is None
    assert manager.get_agent_domain(agent_aware_attr.name) is None
    assert manager.get_agent_domain(agent_aware_prop_1.name) is None
    assert manager.get_agent_domain(agent_aware_prop_2.name) is None
    assert manager.get_domain_mapping(domain) is None

def test_mngr_get_logger():
    manager = fblog.LoggingManager()
    agent = "agent"
    agent_naive = NaiveAgent()
    domain = "domain"
    topic = "topic"
    new_topic = "new_topic"
    root_logger = "root"
    app_logger = "app"
    # No mappings
    logger = manager.get_logger(agent)
    assert isinstance(logger, fblog.ContextLoggerAdapter)
    assert logger.name == root_logger
    assert logger.extra == {"domain": None, "topic": None, "agent": agent}
    # Domain mapped
    manager.set_domain_mapping(domain, agent)
    manager.set_domain_mapping(domain, agent_naive.name)
    logger = manager.get_logger(agent)
    assert isinstance(logger, fblog.ContextLoggerAdapter)
    assert logger.name == root_logger
    assert logger.extra == {"domain": domain, "topic": None, "agent": agent}
    # With topic
    logger = manager.get_logger(agent, topic)
    assert isinstance(logger, fblog.ContextLoggerAdapter)
    assert logger.name == root_logger
    assert logger.extra == {"domain": domain, "topic": topic, "agent": agent}
    # Simple logger fmt
    manager.logger_fmt = ["app"]
    logger = manager.get_logger(agent, topic)
    assert isinstance(logger, fblog.ContextLoggerAdapter)
    assert logger.name == app_logger
    assert logger.extra == {"domain": domain, "topic": topic, "agent": agent}
    #
    manager.logger_fmt = ["app", fblog.DOMAIN]
    # Logger fmt with DOMAIN, no topic
    logger = manager.get_logger(agent)
    assert isinstance(logger, fblog.ContextLoggerAdapter)
    assert logger.name == app_logger + "." + domain
    assert logger.extra == {"domain": domain, "topic": None, "agent": agent}
    # Logger fmt with DOMAIN, with topic
    logger = manager.get_logger(agent, topic)
    assert isinstance(logger, fblog.ContextLoggerAdapter)
    assert logger.name == app_logger + "." + domain
    assert logger.extra == {"domain": domain, "topic": topic, "agent": agent}
    # Logger fmt with DOMAIN, no topic, with NaiveAgent
    logger = manager.get_logger(agent_naive)
    assert isinstance(logger, fblog.ContextLoggerAdapter)
    assert logger.name == app_logger + "." + domain
    assert logger.extra == {"domain": domain, "topic": None, "agent": agent_naive.name}
    #
    manager.logger_fmt = ["app", fblog.TOPIC]
    # Logger fmt with TOPIC, no topic
    logger = manager.get_logger(agent)
    assert isinstance(logger, fblog.ContextLoggerAdapter)
    assert logger.name == app_logger
    assert logger.extra == {"domain": domain, "topic": None, "agent": agent}
    # Logger fmt with TOPIC, with topic
    logger = manager.get_logger(agent, topic)
    assert isinstance(logger, fblog.ContextLoggerAdapter)
    assert logger.name == app_logger + "." + topic
    assert logger.extra == {"domain": domain, "topic": topic, "agent": agent}
    # Logger fmt with TOPIC, with mapped topic
    manager.set_topic_mapping(topic, new_topic)
    logger = manager.get_logger(agent, topic)
    assert isinstance(logger, fblog.ContextLoggerAdapter)
    assert logger.name == app_logger + "." + new_topic
    assert logger.extra == {"domain": domain, "topic": new_topic, "agent": agent}
    manager.set_topic_mapping(topic, None)
    #
    manager.logger_fmt = ["app", fblog.DOMAIN, fblog.TOPIC]
    # Logger fmt with DOMAIN and TOPIC, no topic
    logger = manager.get_logger(agent)
    assert isinstance(logger, fblog.ContextLoggerAdapter)
    assert logger.name == app_logger + "." + domain
    assert logger.extra == {"domain": domain, "topic": None, "agent": agent}
    # Logger fmt with DOMAIN and TOPIC, with topic
    logger = manager.get_logger(agent, topic)
    assert isinstance(logger, fblog.ContextLoggerAdapter)
    assert logger.name == app_logger + "." + domain + "." + topic
    assert logger.extra == {"domain": domain, "topic": topic, "agent": agent}
    #
    manager.set_domain_mapping(domain, None)
    # Logger fmt with DOMAIN and TOPIC, no topic, no domain
    logger = manager.get_logger(agent)
    assert isinstance(logger, fblog.ContextLoggerAdapter)
    assert logger.name == app_logger
    assert logger.extra == {"domain": None, "topic": None, "agent": agent}
    # Logger fmt with DOMAIN and TOPIC, with topic, no domain
    logger = manager.get_logger(agent, topic)
    assert isinstance(logger, fblog.ContextLoggerAdapter)
    assert logger.name == app_logger + "." + topic
    assert logger.extra == {"domain": None, "topic": topic, "agent": agent}
    # Logger fmt with DOMAIN and TOPIC, no topic, default domain
    manager.default_domain = "default_domain"
    logger = manager.get_logger(agent)
    assert isinstance(logger, fblog.ContextLoggerAdapter)
    assert logger.name == app_logger + ".default_domain"
    assert logger.extra == {"domain": "default_domain", "topic": None, "agent": agent}

def test_context_adapter(caplog):
    manager = fblog.LoggingManager()
    agent = "agent"
    agent_naive = NaiveAgent()
    agent_aware = AwareAgentAttr()
    domain = "domain"
    topic = "topic"
    message = "Log message"
    manager.set_domain_mapping(domain, [agent, agent_naive.name, agent_aware.name])
    caplog.set_level(logging.NOTSET)
    # Agent name
    log = manager.get_logger(agent)
    log.info(message)
    assert len(caplog.records) == 1
    rec = caplog.records.pop(0)
    assert rec.name == "root"
    assert rec.funcName == "test_context_adapter"
    assert rec.filename == "test_logging.py"
    assert rec.message == message
    assert rec.domain == domain
    assert rec.agent == agent
    assert rec.topic is None
    assert rec.context is None
    # Naive agent, no log_context
    log = manager.get_logger(agent_naive)
    log.info(message)
    assert len(caplog.records) == 1
    rec = caplog.records.pop(0)
    assert rec.name == "root"
    assert rec.funcName == "test_context_adapter"
    assert rec.filename == "test_logging.py"
    assert rec.message == message
    assert rec.domain == domain
    assert rec.agent == agent_naive.name
    assert rec.topic is None
    assert rec.context is None
    # Naive agent, with log_context
    agent_naive.log_context = "Context data"
    log = manager.get_logger(agent_naive)
    log.info(message)
    assert len(caplog.records) == 1
    rec = caplog.records.pop(0)
    assert rec.name == "root"
    assert rec.funcName == "test_context_adapter"
    assert rec.filename == "test_logging.py"
    assert rec.message == message
    assert rec.domain == domain
    assert rec.agent == agent_naive.name
    assert rec.topic is None
    assert rec.context == "Context data"

def test_context_filter(caplog):
    manager = fblog.LoggingManager()
    caplog.set_level(logging.NOTSET)
    # No filter
    logging.getLogger().info("Message")
    assert len(caplog.records) == 1
    rec = caplog.records.pop(0)
    assert not hasattr(rec, "domain")
    assert not hasattr(rec, "topic")
    assert not hasattr(rec, "agent")
    assert not hasattr(rec, "context")
    # Filter, no attrs in record
    with caplog.filtering(fblog.ContextFilter()):
        logging.getLogger().info("Message")
    assert len(caplog.records) == 1
    rec = caplog.records.pop(0)
    assert rec.domain is None
    assert rec.topic is None
    assert rec.agent is None
    assert rec.context is None
    # Filter, attrs in record
    agent = AwareAgentAttr()
    agent.log_context = "Context data"
    domain = "domain"
    topic = "topic"
    manager.set_domain_mapping(domain, agent.name)
    log = manager.get_logger(agent, topic)
    with caplog.filtering(fblog.ContextFilter()):
        log.info("Message")
    assert len(caplog.records) == 1
    rec = caplog.records.pop(0)
    assert rec.domain == domain
    assert rec.topic == topic
    assert rec.agent == agent.name
    assert rec.context == "Context data"

def test_logger_factory():
    manager = fblog.LoggingManager()
    assert manager.get_logger_factory() == manager._logger_factory
    manager.set_logger_factory(None)
    assert manager._logger_factory is None

def test_mngr_reset():
    manager = fblog.LoggingManager()
    assert len(manager._agent_domain_map) == 0
    assert len(manager._domain_agent_map) == 0
    assert len(manager._topic_map) == 0
    assert len(manager._agent_map) == 0
    assert len(manager.logger_fmt) == 0
    assert manager.default_domain is None
    # Setup
    manager.set_agent_mapping("agent", "new_agent")
    manager.set_domain_mapping("domain", "agent")
    manager.set_topic_mapping("topic", "new_topic")
    manager.logger_fmt = ["app"]
    manager.default_domain = "app"
    assert len(manager._agent_domain_map) == 1
    assert len(manager._domain_agent_map) == 1
    assert len(manager._topic_map) == 1
    assert len(manager._agent_map) == 1
    assert manager.logger_fmt == ["app"]
    assert manager.default_domain == "app"
    # Reset
    manager.reset()
    assert len(manager._agent_domain_map) == 0
    assert len(manager._domain_agent_map) == 0
    assert len(manager._topic_map) == 0
    assert len(manager._agent_map) == 0
    assert len(manager.logger_fmt) == 0
    assert manager.default_domain is None
