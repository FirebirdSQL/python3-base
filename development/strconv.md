# `firebird.base.strconv`

Source: `src/firebird/base/strconv.py`. Tests: `tests/test_strconv.py`.

The module provides symmetric conversion between Python values and strings. A `Convertor`
is keyed by type; `register_convertor()`, `register_class()`, and `update_convertor()` manage
the registry. `convert_to_str()` and `convert_from_str()` are the main operations; `has_convertor()`
and `get_convertor()` expose registration state. Resolution considers type inheritance, so
built-ins include separate registrations for `IntEnum` and `IntFlag` in addition to `Enum` and `int`.

Built-in convertors are registered during module import for scalar, decimal, UUID, MIME,
ZMQ address, boolean, and enum types. `config.ListOption` and `config.DataclassOption` depend
on this registry for nested values. When adding a supported type, test both directions,
invalid input, and interaction with the configuration options that consume it. Registry
changes affect process-wide behavior.
