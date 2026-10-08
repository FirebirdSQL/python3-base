# `firebird.base.logging`

Source: `src/firebird/base/logging.py`. Tests: `tests/test_logging.py`.

`LoggingManager` builds standard-library loggers from an agent and optional topic. Its domain,
topic, and agent mappings, `default_domain`, and `logger_fmt` determine the underlying logger
name. `get_logger()` returns a `ContextLoggerAdapter`; the adapter and `ContextFilter` add
agent/domain/topic context to log records. Module-level `logging_manager`, `get_logger()`,
`get_agent_name()`, `set_domain_mapping()`, and `set_agent_mapping()` are shared entry points.

`FStrMessage`, `BraceMessage`, and `DollarMessage` defer interpolation until a message is
rendered. `FormatElement` and `LogLevel` define formatting elements and levels. Trace uses
this module to obtain loggers, so changes to record context or naming also require trace checks.
Tests should reset manager mappings/factory and standard logging handlers they modify.
