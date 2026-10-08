# `firebird.base.config`

[Published API](https://firebird-base.readthedocs.io/config/index.md)

Define a `Config` subclass and assign each `Option` to an attribute with the same name as
the option. Read and write values through `option.value`. Use `Config.get_config()` for an
INI template, `Config.load_config()` with `ConfigParser` to load it, and
`Config.save_proto()` / `Config.load_proto()` to exchange state. `ConfigOption` references
one nested section; `ConfigListOption` references several sections. Use `get_directory_scheme()`
for platform conventions. Register `strconv` convertors before using custom values in list
or dataclass options.

Avoid assigning an option under a different attribute name: discovery depends on the match.
Do not serialize a nested option in isolation; use its owning `Config`, which may need
surrounding sections. Do not treat commented defaults in `get_config()` output as active
settings. `EnvExtendedInterpolation` supports `${env:VAR}` but an absent variable yields
an empty string, so validate required secrets. Construct `PyExprOption`, `PyCodeOption`,
and `PyCallableOption` only from trusted configuration. For registry lookup of `ConfigProto`,
call `load_registered('firebird.base.protobuf')` first; direct import of `ConfigProto` needs
no registry.
