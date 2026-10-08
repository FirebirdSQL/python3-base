# `firebird.base.types`

Source: `src/firebird/base/types.py`. Tests: `tests/test_types.py`.

This is the shared foundation for several other modules. `Error` accepts keyword attributes
and returns `None` for unknown attributes, except special cases needed by Python exceptions.
`SingletonMeta` and `Singleton` cache one instance per subclass. `Sentinel` is a metaclass-based
named value system; predefined sentinels such as `DEFAULT`, `UNDEFINED`, `ANY`, `UNLIMITED`,
and `NOT_FOUND` are used as control values in other modules. Preserve sentinel identity comparisons.

`Distinct` defines equality and hashing through `get_key()`; `CachedDistinct` adds a weak-value
instance cache keyed by `extract_key()`. Changes to either affect `Registry`, hooks, protobuf
descriptors, and trace registrations. `ByteOrder` is consumed by `MemoryBuffer`. The module
also defines `ZMQTransport`, `ZMQDomain`, `ZMQAddress`, `MIME`, and executable string forms
`PyExpr`, `PyCode`, and `PyCallable`; these are used by typed configuration options.
`conjunctive()` combines metaclasses, while `load()` resolves a Python object from a dotted specification.

When changing a value type, check its matching option in `config.py` and any built-in convertor
in `strconv.py`. Executable string types can evaluate Python code, so keep trust assumptions
explicit in any new caller.
