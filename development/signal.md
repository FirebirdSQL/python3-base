# `firebird.base.signal`

Source: `src/firebird/base/signal.py`. Tests: `tests/test_signal.py`.

The module provides two callback models. `Signal` validates connected slot signatures against
an `inspect.Signature`, then emits to connected functions, methods, lambdas, or partials.
The `signal` descriptor creates a separate signal for each object instance from a decorated
method signature. `eventsocket` is an optional single-callback descriptor with signature
checking; callers can inspect whether a callback is set.

Storage deliberately differs by callable type: regular functions use weak references, bound
methods use a weak-key map, while lambdas and partials are retained directly. Changes to
connection logic must check signature compatibility, duplicate connection and disconnection,
garbage collection behavior, and per-instance isolation. Tests should cover both descriptor
models as well as direct `Signal` use.
