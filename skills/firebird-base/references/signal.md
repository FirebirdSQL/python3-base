# `firebird.base.signal`

[Published API](https://firebird-base.readthedocs.io/signal/index.md)

Use `Signal` or the `@signal` descriptor for one to many notifications. Define the expected
signature and connect compatible slots; slot return values are ignored. A decorated signal
belongs to each instance. Use `@eventsocket` for one optional handler whose return value
matters; assign a compatible callable, inspect `is_set()` if needed, and assign `None` to
disconnect it.

Avoid using a signal to collect callback results. Do not connect a callback with an incompatible
signature. Regular functions and bound methods are weakly referenced; keep their owners
alive while connected. Lambdas and partials are retained directly, so manage their lifetime
and disconnect when appropriate.
