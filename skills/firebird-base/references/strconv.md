# `firebird.base.strconv`

[Published API](https://firebird-base.readthedocs.io/strconv/index.md)

Use `convert_to_str()` and `convert_from_str()` for supported types; lookups for a class
follow its MRO. Use `get_convertor()` when repeatedly converting one type. For a custom
type, register a pair of functions that round trip its values and raise `ValueError` for
invalid input. Register the class with `register_class()` if it must be resolved by name,
as in some configuration uses. Built-in support includes scalars, decimals, UUIDs, enums
and flags, `MIME`, and `ZMQAddress`.

Avoid assuming a name lookup inherits a base class convertor automatically. Avoid `str(value)`
as a substitute for a reversible representation, especially for `ListOption` or `DataclassOption`.
Registry updates are process wide: register deliberately and use `update_convertor()` for
an intentional replacement rather than repeating `register_convertor()`.
