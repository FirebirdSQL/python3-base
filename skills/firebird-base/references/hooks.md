# `firebird.base.hooks`

[Published API](https://firebird-base.readthedocs.io/hooks/index.md)

Use hooks when callbacks must be selected by event and source class, instance, or registered
instance name. Register the source class and its supported events before adding its hooks.
An event provider calls `get_callbacks(event, source)` and invokes the returned callbacks
using a documented signature. Use `ANY` deliberately for wildcard event or source registrations.
Remove hooks or reset the manager during teardown in tests and short lived integrations.

Avoid expecting `HookManager` to invoke callbacks or validate their signatures: the event
provider owns both. Avoid registering hooks repeatedly inside event dispatch; the manager
is shared process state. Do not use a source name until `register_name()` associates it with
an instance.
