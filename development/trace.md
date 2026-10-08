# `firebird.base.trace`

Source: `src/firebird/base/trace.py`. Tests: `tests/test_trace.py`.

The `traced` decorator logs before, after, or failed calls through `firebird.base.logging`;
it can include parameters, return values, elapsed time, and exceptions. `TraceFlag` controls
whether and when logging occurs. `TracedMixin` and `TracedMeta` support automatic class
participation. `TraceManager` registers classes and method trace definitions, can wrap an
object with `trace_object()`, and loads INI settings through the `Config` subclasses `TraceConfig`,
`TracedClassConfig`, and `TracedMethodConfig`.

The module-level `trace_manager` and aliases `add_trace`, `remove_trace`, and `trace_object`
share state. Trace definitions use `Registry`, and configuration may resolve names through
`types.load()` and values through `strconv`. When changing wrapper behavior, verify return
values, exceptions, signature-sensitive call paths, flags, message contents, and runtime
configuration. Clear manager state between tests.
