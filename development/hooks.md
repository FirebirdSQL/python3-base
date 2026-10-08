# `firebird.base.hooks`

Source: `src/firebird/base/hooks.py`. Tests: `tests/test_hooks.py`.

`HookManager` is a `Singleton` that registers hookable classes and their supported events,
optional names for instances, and callbacks. `Hook` objects are stored in a `Registry` keyed
by event, class, and object/name. `ANY` can be used for either the event or the source,
including both together. The manager also uses it internally for the unused parts of a
class or instance key.
`HookFlag` records which lookup forms are in use; `get_callbacks()` resolves callbacks for
a raised event and source.

`register_class()` establishes supported events before class or instance hooks are added.
`register_name()` uses a weak key map for instances. The module exposes shortcuts such as
`add_hook()` and `get_callbacks()` bound to the global `hook_manager`. Callback signatures
are a caller contract rather than validated by this manager. Tests that register hooks should
reset manager state and cover class, instance, name, and wildcard matching.
