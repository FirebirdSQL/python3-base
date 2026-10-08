# `firebird.base.trace`

[Published API](https://firebird-base.readthedocs.io/trace/index.md)

Use `traced` for a specific callable. Use `TracedMixin` and `TraceManager` when methods
need registration or runtime control. Trace output uses `firebird.base.logging`; configure
logging before expecting records. Choose `TraceFlag` phases deliberately and limit argument
or result detail where values may be large or sensitive. With INI configuration, list class
sections in `[trace] classes`; only referenced class and `special` sections are loaded.

Avoid assuming a decorated callable is automatically active under every flag or logging level.
Avoid logging secrets through `with_args` or return values. Do not expect an unreferenced
INI section to configure tracing. Treat manager registration and flags as shared state and
clear them in isolated tests.
