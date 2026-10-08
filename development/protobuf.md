# `firebird.base.protobuf`

Source: `src/firebird/base/protobuf.py`. Tests: `tests/test_protobuf.py`; test schema: `tests/base_test.proto`.

`ProtoMessageType` and `ProtoEnumType` wrap Google protobuf descriptors and live in process-wide
`Registry` instances keyed by fully qualified protobuf names. `create_message()`,
`get_message_factory()`, `get_enum_type()`, and enum helpers provide name-based access.
`struct2dict()` and `dict2struct()` handle `google.protobuf.Struct` conversion.

The public registration function is `register_descriptor()`.
`load_registered(group)` loads descriptor entry points, normally from `firebird.base.protobuf`.
The package's own `firebird.base.config` descriptor is registered in `pyproject.toml` through
that group. Descriptor registration affects global state; tests should avoid relying on
registration order and cover message and enum lookups.
