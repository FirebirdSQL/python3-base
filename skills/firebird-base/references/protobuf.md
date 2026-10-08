# `firebird.base.protobuf`

[Published API](https://firebird-base.readthedocs.io/protobuf/index.md)

Use `register_descriptor()` for a generated module's file descriptor, or `load_registered(group)`
for descriptors advertised by installed entry points. The package uses the `firebird.base.protobuf`
group for its own config descriptor. After registration, use fully qualified names with
`create_message()`, `get_message_factory()`, and enum helpers. `struct2dict()` and `dict2struct()`
exchange values with `google.protobuf.Struct`.

Avoid calling registry lookup before descriptor registration. Do not use the deprecated
misspelling `register_decriptor()` in new code. Avoid relying on registration order or
treating the registry as local to one caller; names and registrations are process wide.
