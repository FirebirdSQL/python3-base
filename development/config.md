# `firebird.base.config`

Source: `src/firebird/base/config.py`; wire schema: `proto/config.proto`; generated binding:
`src/firebird/base/config_pb2.py` and stub. Tests: `tests/config/`.

This module has two related parts. `DirectoryScheme` and its Windows, Linux, and macOS
implementations choose application directories through `get_directory_scheme()`. The configuration
framework uses `Config` as a nested container and `Option[T]` as the base for typed values.
`Config` discovers child options and child configurations assigned as attributes. Options
carry defaults, required status, validation, string conversion, and serialization behavior.

Concrete options cover strings, integers, floats, decimals, booleans, ZMQ addresses, enums,
flags, UUIDs, MIME types, lists, Python expressions/code/callables, nested configurations
(`ConfigOption`, `ConfigListOption`), dataclasses, and paths. New options must implement
the same value, text, and protobuf paths as comparable options. `ListOption` and `DataclassOption`
rely on `strconv` convertors.

`load_config()` reads `configparser` sections. `EnvExtendedInterpolation` adds `${env:VAR}`
interpolation. Multiline text has special vertical-bar handling to preserve indentation.
`get_config()` writes an INI representation. `load_proto()` and `save_proto()` exchange values
via `ConfigProto`; `proto/config.proto` defines its `Value` oneof and nested configuration
maps. Preserve field numbering and existing value meanings when changing this format.

Tests are split by option type and feature, with common parser/protobuf fixtures in
`tests/config/conftest.py`. For a change to an option, verify defaults, required/invalid
values, string/INI round trips, and protobuf round trips where applicable. Directory behavior
varies by platform and environment, so keep tests isolated from the host's real directories.
