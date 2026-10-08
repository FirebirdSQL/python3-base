# `firebird.base.logging`

[Published API](https://firebird-base.readthedocs.io/logging/index.md)

Use `get_logger(agent, topic=...)` when records need agent, context, domain, or topic.
An object agent uses `_agent_name_` if present, otherwise its qualified class name.
Configure standard `logging` handlers and formatters; add `ContextFilter` to a handler
when its formatter expects context fields from both ordinary and context loggers.
Set `logging_manager.logger_fmt` and mappings when separate logger names are needed; its
default empty format maps to the root logger. Use message wrappers when deferred
interpolation is useful.

Avoid assuming `agent.log_context` refreshes automatically on a retained adapter: the first
value is cached in `adapter.extra['context']`; update or delete that key for a new context.
Do not use `%(agent)s` and related fields with ordinary records unless the handler supplies
`ContextFilter`. Avoid changing global mappings per request; they affect all agents in the process.
