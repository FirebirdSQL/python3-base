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
from typing import Any # Added for type hints

import pytest

import firebird.base.logging as fblog
# Assuming types.py is importable for DEFAULT sentinel if used
from firebird.base.types import DEFAULT

# --- Test Setup & Fixtures ---

class Namespace:
    """Simple class acting as a namespace for holding attributes."""
    pass

class NaiveAgent:
    """A test agent class without specific logging awareness."""
    @property
    def name(self):
        """Returns the agent name determined by the logging manager."""
        return fblog.get_agent_name(self)

class AwareAgentAttr:
    """A test agent class with a static _agent_name_ attribute."""
    _agent_name_: str = "_agent_name_attr"
    log_context: Any = None # Add for testing context propagation
    @property
    def name(self):
        """Returns the agent name determined by the logging manager."""
        return fblog.get_agent_name(self)

class AwareAgentProperty:
    """A test agent class with a dynamic _agent_name_ property."""
    def __init__(self, agent_name: Any):
        self._int_agent_name = agent_name
    @property
    def _agent_name_(self) -> Any:
        """Dynamically returns the configured agent name."""
        return self._int_agent_name
    @property
    def name(self):
        """Returns the agent name determined by the logging manager."""
        return fblog.get_agent_name(self)


@contextmanager
def context_filter(target_logger: logging.Logger):
    """Context manager to temporarily add the ContextFilter to a logger."""
    ctx_filter = fblog.ContextFilter()
    target_logger.addFilter(ctx_filter)
    try:
        yield
    finally:
        target_logger.removeFilter(ctx_filter)

# --- Test Functions ---

def test_fstr_message():
    """Tests the FStrMessage formatter for f-string style log messages."""
    ns = Namespace()
    ns.nested = Namespace()
    ns.nested.item = "item!"
    ns.attr = "attr"
    ns.number = 5
    # Simple message
    msg = fblog.FStrMessage("-> Message <-")
    assert str(msg) == "-> Message <-"
    # Message with nested attributes, expressions, repr, initialized via dict
    msg = fblog.FStrMessage("Let's see {ns.number=} * 5 = {ns.number * 5}, [{ns.nested.item}] or {ns.attr!r}", {"ns": ns})
    assert str(msg) == "Let's see ns.number=5 * 5 = 25, [item!] or 'attr'"
    # Same, initialized via kwargs
    msg = fblog.FStrMessage("Let's see {ns.number=} * 5 = {ns.number * 5}, [{ns.nested.item}] or {ns.attr!r}", ns=ns)
    assert str(msg) == "Let's see ns.number=5 * 5 = 25, [item!] or 'attr'"
    # Message with positional args treated as 'args' list
    msg = fblog.FStrMessage("Let's see {args[0]=} * 5 = {args[0] * 5}, {ns.attr!r}", 5, ns=ns)
    assert str(msg) == "Let's see args[0]=5 * 5 = 25, 'attr'"

def test_brace_message():
    """Tests the BraceMessage formatter for str.format() style log messages."""
    point = Namespace()
    point.x = 0.5
    point.y = 0.5
    # Positional placeholders
    msg = fblog.BraceMessage("Message with {0} {1}", 2, "placeholders")
    assert str(msg) == "Message with 2 placeholders"
    # Keyword placeholders with formatting
    msg = fblog.BraceMessage("Message with coordinates: ({point.x:.2f}, {point.y:.2f})", point=point)
    assert str(msg) == "Message with coordinates: (0.50, 0.50)"

def test_dollar_message():
    """Tests the DollarMessage formatter for string.Template style log messages."""
    point = Namespace()
    point.x = 0.5
    point.y = 0.5
    # Keyword substitution
    msg = fblog.DollarMessage("Message with $num $what", num=2, what="placeholders")
    assert str(msg) == "Message with 2 placeholders"
    # Note: DollarMessage doesn't support attribute access like {point.x} directly

def test_context_filter_alone(caplog):
    """Tests the ContextFilter when applied directly to a standard logger.

    Ensures it adds the required attributes (domain, topic, agent, context)
    with None values if they are not already present on the LogRecord.
    """
    caplog.set_level(logging.INFO)
    log = logging.getLogger("test_context_filter_logger")
    log.propagate = False # Prevent interference from root logger if handlers exist
    handler = caplog.handler # Use pytest's handler
    log.addHandler(handler)

    # Log without the filter
    log.info("Message 1")
    assert len(caplog.records) == 1
    rec1 = caplog.records[0]
    assert not hasattr(rec1, "domain")
    assert not hasattr(rec1, "topic")
    assert not hasattr(rec1, "agent")
    assert not hasattr(rec1, "context")
    caplog.clear()

    # Log with the filter applied
    with context_filter(log):
        log.info("Message 2")
        assert len(caplog.records) == 1
        rec2 = caplog.records[0]
        # Filter should have added attributes with None values
        assert hasattr(rec2, "domain") and rec2.domain is None
        assert hasattr(rec2, "topic") and rec2.topic is None
        assert hasattr(rec2, "agent") and rec2.agent is None
        assert hasattr(rec2, "context") and rec2.context is None

    log.removeHandler(handler) # Clean up handler


def test_context_adapter_basic(caplog):
    """Tests the basic functionality of ContextLoggerAdapter.

    Verifies that it correctly adds domain, topic, agent name, and context (from agent)
    to the LogRecord's dictionary via the 'extra' mechanism.
    """
    caplog.set_level(logging.INFO)
    agent_obj = AwareAgentAttr()
    agent_obj.log_context = "Agent Context Data"
    adapter = fblog.ContextLoggerAdapter(logging.getLogger("adapter_test"),
                                         domain="domain1", topic="topic1",
                                         agent=agent_obj, agent_name="agent_name1")
    adapter.logger.propagate = False # Isolate logger
    adapter.logger.addHandler(caplog.handler)

    adapter.info("Adapter message")

    assert len(caplog.records) == 1
    rec = caplog.records[0]
    assert rec.domain == "domain1"
    assert rec.topic == "topic1"
    assert rec.agent == "agent_name1"
    assert rec.context == "Agent Context Data"

    # Test overriding context via extra dict
    caplog.clear()
    adapter.info("Override context", extra={'context': 'OVERRIDE'})
    assert len(caplog.records) == 1
    rec_override = caplog.records[0]
    assert rec_override.context == 'OVERRIDE' # Should use value from 'extra'

    adapter.logger.removeHandler(caplog.handler)


def test_context_adapter_with_filter(caplog):
    """Tests ContextLoggerAdapter used in conjunction with ContextFilter.

    This combination is typical. The adapter adds the data, and the filter
    ensures the attributes exist even if the adapter somehow didn't add them
    (though that shouldn't happen with the adapter). Mainly verifies they don't conflict.
    """
    caplog.set_level(logging.INFO)
    adapter = fblog.ContextLoggerAdapter(logging.getLogger("adapter_filter_test"),
                                         "domain", "topic", "agent", "agent_name")
    adapter.logger.propagate = False
    adapter.logger.addHandler(caplog.handler)

    with context_filter(adapter.logger):
        adapter.info("Adapter+Filter message")
        assert len(caplog.records) == 1
        rec = caplog.records[0]
        assert rec.domain == "domain"
        assert rec.topic == "topic"
        assert rec.agent == "agent_name"
        assert rec.context is None # Agent provided was string, no log_context

    adapter.logger.removeHandler(caplog.handler)


def test_mngr_default_domain():
    """Tests setting and getting the default_domain on the LoggingManager."""
    manager = fblog.LoggingManager()
    assert manager.default_domain is None
    manager.default_domain = "default_domain_test"
    assert manager.default_domain == "default_domain_test"
    manager.default_domain = None
    assert manager.default_domain is None
    manager.default_domain = 123 # Should convert to string
    assert manager.default_domain == "123"


def test_mngr_logger_fmt():
    """Tests setting, getting, and validation of logger_fmt on the LoggingManager."""
    manager = fblog.LoggingManager()
    assert manager.logger_fmt == [] # Default is empty list

    # Set valid format
    value = ["app", fblog.DOMAIN, "module"]
    manager.logger_fmt = value
    assert manager.logger_fmt == value
    # Ensure internal list is a copy
    value[0] = "xxx_changed"
    assert manager.logger_fmt == ["app", fblog.DOMAIN, "module"] # Should not have changed

    # Test empty string removal
    manager.logger_fmt = ["app", "", fblog.TOPIC]
    assert manager.logger_fmt == ["app", fblog.TOPIC]

    # Test invalid item types
    with pytest.raises(ValueError, match="Unsupported item type"):
        manager.logger_fmt = ["app", None, "module"]
    with pytest.raises(ValueError, match="Unsupported item type"):
        manager.logger_fmt = [1]

    # Test duplicate sentinels
    with pytest.raises(ValueError, match="Only one occurence of sentinel TOPIC allowed"):
        manager.logger_fmt = ["app", fblog.TOPIC, "x", fblog.TOPIC]
    with pytest.raises(ValueError, match="Only one occurence of sentinel DOMAIN allowed"):
        manager.logger_fmt = ["app", fblog.DOMAIN, "x", fblog.DOMAIN]

    # Test valid combination
    value = ["app", fblog.DOMAIN, fblog.TOPIC, "suffix"]
    manager.logger_fmt = value
    assert manager.logger_fmt == value


def test_mngr_get_logger_name_generation():
    """Tests the internal _get_logger_name method for various formats and inputs."""
    manager = fblog.LoggingManager()

    # Default format (empty)
    assert manager._get_logger_name("domain", "topic") == ""

    # Simple formats
    manager.logger_fmt = ["app"]
    assert manager._get_logger_name("domain", "topic") == "app"
    manager.logger_fmt = ["app", "module"]
    assert manager._get_logger_name("domain", "topic") == "app.module"

    # Format with DOMAIN
    manager.logger_fmt = ["app", fblog.DOMAIN]
    assert manager._get_logger_name("domain", "topic") == "app.domain"
    assert manager._get_logger_name(None, "topic") == "app" # Domain None ignored

    # Format with TOPIC
    manager.logger_fmt = ["app", fblog.TOPIC]
    assert manager._get_logger_name("domain", "topic") == "app.topic"
    assert manager._get_logger_name("domain", None) == "app" # Topic None ignored

    # Format with DOMAIN and TOPIC
    manager.logger_fmt = ["app", fblog.DOMAIN, fblog.TOPIC]
    assert manager._get_logger_name("domain", "topic") == "app.domain.topic"
    assert manager._get_logger_name(None, "topic") == "app.topic" # Domain None ignored
    assert manager._get_logger_name("domain", None) == "app.domain" # Topic None ignored
    assert manager._get_logger_name(None, None) == "app" # Both None ignored

    # Format with empty strings and sentinels
    manager.logger_fmt = ["prefix", "", fblog.TOPIC, "", fblog.DOMAIN, "suffix"]
    assert manager._get_logger_name("domain", "topic") == "prefix.topic.domain.suffix"


def test_mngr_set_get_topic_mapping():
    """Tests setting, getting, and removing topic mappings."""
    topic_orig = "original_topic"
    topic_mapped = "mapped_topic"
    manager = fblog.LoggingManager()

    assert len(manager._topic_map) == 0
    assert manager.get_topic_mapping(topic_orig) is None

    # Set mapping
    manager.set_topic_mapping(topic_orig, topic_mapped)
    assert len(manager._topic_map) == 1
    assert manager.get_topic_mapping(topic_orig) == topic_mapped
    assert manager.get_topic_mapping(topic_mapped) is None # Mapping is one-way

    # Remove mapping using None
    manager.set_topic_mapping(topic_orig, None)
    assert len(manager._topic_map) == 0
    assert manager.get_topic_mapping(topic_orig) is None

    # Remove mapping using empty string
    manager.set_topic_mapping(topic_orig, topic_mapped)
    manager.set_topic_mapping(topic_orig, "")
    assert len(manager._topic_map) == 0
    assert manager.get_topic_mapping(topic_orig) is None

    # Test setting non-string (should be converted)
    manager.set_topic_mapping(topic_orig, DEFAULT)
    assert manager.get_topic_mapping(topic_orig) == str(DEFAULT)
    assert len(manager._topic_map) == 1


def test_mngr_get_agent_name_various():
    """Tests get_agent_name with different agent types and mappings."""
    manager = fblog.LoggingManager()
    agent_str = "agent_string_id"
    agent_naive = NaiveAgent()
    agent_aware_attr = AwareAgentAttr()
    agent_aware_prop = AwareAgentProperty("_agent_name_property")
    agent_aware_nonstr = AwareAgentProperty(123) # Property returns int

    # String agent
    assert manager.get_agent_name(agent_str) == agent_str

    # Naive object agent (uses class path)
    expected_naive_name = "tests.test_logging.NaiveAgent" # Adjust if file location changes
    assert manager.get_agent_name(agent_naive) == expected_naive_name

    # Aware object agent (attribute)
    assert manager.get_agent_name(agent_aware_attr) == "_agent_name_attr"

    # Aware object agent (property)
    assert manager.get_agent_name(agent_aware_prop) == "_agent_name_property"

    # Aware object agent (property returning non-string)
    assert manager.get_agent_name(agent_aware_nonstr) == "123" # Should be converted to str

    # Test with agent mapping
    mapped_name = "mapped_agent_id"
    manager.set_agent_mapping(agent_str, mapped_name)
    assert manager.get_agent_name(agent_str) == mapped_name # Should return mapped name

    manager.set_agent_mapping(expected_naive_name, mapped_name)
    assert manager.get_agent_name(agent_naive) == mapped_name # Should map the derived name

    manager.set_agent_mapping("_agent_name_attr", mapped_name)
    assert manager.get_agent_name(agent_aware_attr) == mapped_name


def test_mngr_set_get_agent_mapping():
    """Tests setting, getting, and removing agent name mappings."""
    agent_orig = "original_agent"
    agent_mapped = "mapped_agent"
    manager = fblog.LoggingManager()

    assert len(manager._agent_map) == 0
    assert manager.get_agent_mapping(agent_orig) is None

    # Set mapping
    manager.set_agent_mapping(agent_orig, agent_mapped)
    assert len(manager._agent_map) == 1
    assert manager.get_agent_mapping(agent_orig) == agent_mapped

    # Remove mapping using None
    manager.set_agent_mapping(agent_orig, None)
    assert len(manager._agent_map) == 0
    assert manager.get_agent_mapping(agent_orig) is None

    # Remove mapping using empty string
    manager.set_agent_mapping(agent_orig, agent_mapped)
    manager.set_agent_mapping(agent_orig, "")
    assert len(manager._agent_map) == 0
    assert manager.get_agent_mapping(agent_orig) is None

    # Test setting non-string (should be converted)
    manager.set_agent_mapping(agent_orig, DEFAULT)
    assert manager.get_agent_mapping(agent_orig) == str(DEFAULT)
    assert len(manager._agent_map) == 1


def test_mngr_set_get_domain_mapping():
    """Tests setting, getting, updating, replacing, and removing domain mappings for agents."""
    domain1 = "domain1"
    domain2 = "domain2"
    agent1_name = "agent1"
    agent2_name = "agent2"
    agent3_name = "agent3"
    manager = fblog.LoggingManager()

    # Initial state
    assert len(manager._agent_domain_map) == 0
    assert len(manager._domain_agent_map) == 0
    assert manager.get_agent_domain(agent1_name) is None
    assert manager.get_domain_mapping(domain1) is None

    # Set initial mapping (list)
    manager.set_domain_mapping(domain1, [agent1_name, agent2_name])
    assert len(manager._agent_domain_map) == 2
    assert len(manager._domain_agent_map) == 1
    assert manager.get_domain_mapping(domain1) == {agent1_name, agent2_name}
    assert manager.get_agent_domain(agent1_name) == domain1
    assert manager.get_agent_domain(agent2_name) == domain1
    assert manager.get_agent_domain(agent3_name) is None

    # Update mapping (add agent3, agent1 is duplicate but ok)
    manager.set_domain_mapping(domain1, [agent1_name, agent3_name])
    assert len(manager._agent_domain_map) == 3
    assert len(manager._domain_agent_map) == 1
    assert manager.get_domain_mapping(domain1) == {agent1_name, agent2_name, agent3_name}
    assert manager.get_agent_domain(agent1_name) == domain1
    assert manager.get_agent_domain(agent2_name) == domain1
    assert manager.get_agent_domain(agent3_name) == domain1

    # Set mapping for a different domain (single agent name)
    manager.set_domain_mapping(domain2, agent1_name) # Agent1 now maps to domain2
    assert len(manager._agent_domain_map) == 3 # Still 3 agents mapped
    assert len(manager._domain_agent_map) == 2 # Now 2 domains
    assert manager.get_domain_mapping(domain1) == {agent2_name, agent3_name} # agent1 removed from domain1
    assert manager.get_domain_mapping(domain2) == {agent1_name}
    assert manager.get_agent_domain(agent1_name) == domain2 # agent1 updated
    assert manager.get_agent_domain(agent2_name) == domain1
    assert manager.get_agent_domain(agent3_name) == domain1

    # Replace mapping for domain1
    manager.set_domain_mapping(domain1, agent1_name, replace=True) # Should remove agent2, agent3 first
    assert len(manager._agent_domain_map) == 1 # Only agent1 mapped now
    assert len(manager._domain_agent_map) == 1 # Only domain1 remains
    assert manager.get_domain_mapping(domain1) == {agent1_name}
    assert manager.get_domain_mapping(domain2) is None # domain2 mapping removed
    assert manager.get_agent_domain(agent1_name) == domain1 # agent1 updated again
    assert manager.get_agent_domain(agent2_name) is None
    assert manager.get_agent_domain(agent3_name) is None

    # Remove mapping for domain1 using None
    manager.set_domain_mapping(domain1, None)
    assert len(manager._agent_domain_map) == 0
    assert len(manager._domain_agent_map) == 0
    assert manager.get_agent_domain(agent1_name) is None
    assert manager.get_domain_mapping(domain1) is None


def test_mngr_get_logger_scenarios():
    """Tests get_logger under various manager configurations."""
    manager = fblog.LoggingManager()
    agent = "test_agent"
    agent_mapped = "mapped_agent_name"
    domain_specific = "specific_domain"
    domain_default = "default_domain"
    topic_orig = "original_topic"
    topic_mapped = "mapped_topic"
    app_name = "my_app"

    # Scenario 1: No mappings, no format, no defaults
    logger = manager.get_logger(agent)
    assert isinstance(logger, fblog.ContextLoggerAdapter)
    assert logger.logger.name == "root" # Default logger name
    assert logger.extra == {"domain": None, "topic": None, "agent": agent}

    # Setup for subsequent tests
    manager.logger_fmt = [app_name, fblog.DOMAIN, fblog.TOPIC]
    manager.default_domain = domain_default
    manager.set_topic_mapping(topic_orig, topic_mapped)
    manager.set_agent_mapping(agent, agent_mapped)
    manager.set_domain_mapping(domain_specific, agent_mapped) # Map the *mapped* agent name

    # Scenario 2: All mappings active
    logger = manager.get_logger(agent, topic_orig)
    # Expected: Agent name mapped, domain from specific mapping, topic mapped, full logger name format
    assert logger.logger.name == f"{app_name}.{domain_specific}.{topic_mapped}"
    assert logger.extra['agent'] == agent_mapped
    assert logger.extra['domain'] == domain_specific
    assert logger.extra['topic'] == topic_mapped

    # Scenario 3: Agent mapped, but no specific domain mapping for mapped name, uses default domain
    manager.set_domain_mapping(domain_specific, None) # Remove specific mapping
    logger = manager.get_logger(agent, topic_orig)
    assert logger.logger.name == f"{app_name}.{domain_default}.{topic_mapped}"
    assert logger.extra['agent'] == agent_mapped
    assert logger.extra['domain'] == domain_default # Falls back to default
    assert logger.extra['topic'] == topic_mapped
    manager.set_domain_mapping(domain_specific, agent_mapped) # Restore mapping for next test

    # Scenario 4: No topic provided
    logger = manager.get_logger(agent) # Topic is None
    assert logger.logger.name == f"{app_name}.{domain_specific}" # Topic omitted from name
    assert logger.extra['agent'] == agent_mapped
    assert logger.extra['domain'] == domain_specific
    assert logger.extra['topic'] is None

    # Scenario 5: No domain mapping and no default domain
    manager.set_domain_mapping(domain_specific, None)
    manager.default_domain = None
    logger = manager.get_logger(agent, topic_orig)
    assert logger.logger.name == f"{app_name}.{topic_mapped}" # Domain omitted from name
    assert logger.extra['agent'] == agent_mapped
    assert logger.extra['domain'] is None
    assert logger.extra['topic'] == topic_mapped


def test_logger_factory_integration():
    """Tests using a custom logger factory with the manager."""
    manager = fblog.LoggingManager()
    custom_loggers_created = {}

    def my_logger_factory(name):
        """Custom factory that tracks created loggers."""
        logger = logging.getLogger(name) # Still use standard mechanism internally
        custom_loggers_created[name] = logger
        return logger

    manager.set_logger_factory(my_logger_factory)
    assert manager.get_logger_factory() is my_logger_factory

    # Get a logger via the manager
    manager.logger_fmt = ["factory_test", fblog.DOMAIN]
    manager.set_domain_mapping("domainX", "agentX")
    logger_name = "factory_test.domainX"

    assert logger_name not in custom_loggers_created
    adapter = manager.get_logger("agentX")

    # Check if factory was called and logger was retrieved
    assert adapter.logger.name == logger_name
    assert logger_name in custom_loggers_created
    assert custom_loggers_created[logger_name] is adapter.logger

    # Restore default factory
    manager.set_logger_factory(logging.getLogger)
    assert manager.get_logger_factory() is logging.getLogger


def test_mngr_reset():
    """Tests that reset clears all manager configurations."""
    manager = fblog.LoggingManager()
    # Setup some state
    manager.set_agent_mapping("agent", "new_agent")
    manager.set_domain_mapping("domain", "agent")
    manager.set_topic_mapping("topic", "new_topic")
    manager.logger_fmt = ["app"]
    manager.default_domain = "app_default"
    assert len(manager._agent_map) > 0
    assert len(manager._domain_agent_map) > 0
    assert len(manager._topic_map) > 0
    assert manager.logger_fmt != []
    assert manager.default_domain is not None

    # Reset
    manager.reset()

    # Check state is cleared
    assert len(manager._agent_map) == 0
    assert len(manager._domain_agent_map) == 0
    assert len(manager._agent_domain_map) == 0 # Check reverse map too
    assert len(manager._topic_map) == 0
    assert manager.logger_fmt == []
    assert manager.default_domain is None


# Note: Tests for log record content (filename, funcName etc.) are kept from original
# as they verify standard logging behavior interaction.
def test_log_record_standard_attributes(caplog):
    """Verifies standard LogRecord attributes like name, funcName, filename."""
    manager = fblog.LoggingManager()
    agent_aware = AwareAgentAttr()
    agent_aware.log_context = "Context data"
    domain = "domain_rec_test"
    topic = "topic_rec_test"
    message = "Log message for record test"
    manager.set_domain_mapping(domain, agent_aware.name)
    manager.logger_fmt = ['record_test', fblog.DOMAIN] # Example format

    log = manager.get_logger(agent_aware, topic)
    log.logger.propagate = False
    log.logger.addHandler(caplog.handler)
    caplog.set_level(logging.NOTSET)

    log.info(message)
    assert len(caplog.records) == 1
    rec = caplog.records[0]

    # Check standard logging attributes
    assert rec.name == "record_test.domain_rec_test"
    assert rec.levelname == "INFO"
    assert rec.levelno == logging.INFO
    assert rec.getMessage() == message
    # These depend on the exact location and execution context
    assert rec.funcName.startswith("test_log_record_standard_attributes") # Check prefix
    assert rec.filename == "test_logging.py"
    assert rec.module == "test_logging"
    # Check custom attributes
    assert rec.domain == domain
    assert rec.agent == agent_aware.name
    assert rec.topic == topic
    assert rec.context == "Context data"

    log.logger.removeHandler(caplog.handler)