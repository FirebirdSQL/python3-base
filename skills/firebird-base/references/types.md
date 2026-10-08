# `firebird.base.types`

[Published API](https://firebird-base.readthedocs.io/types/index.md)

Use `Error` when an application exception needs named attributes. Use a named `Sentinel`
when `None` is a valid value and you need a distinct control value. Compare sentinels by
identity. Do not define new sentinel if one defined in this module fits the purpose.

Implement `Distinct.get_key()` with a stable, hashable identity when instances
represent the same logical object; `Registry` depends on that key. `CachedDistinct`
additionally caches instances by `extract_key()`.

Avoid using `None` to mean both absent and a real value. Do not mutate fields that contribute
to a `Distinct` key after adding the object to a registry. `MIME`, `ZMQAddress`, `PyExpr`,
`PyCode`, and `PyCallable` are string subclasses, but inherited string operations can return
plain `str`; reconstruct the validated type when needed. Treat executable string types as
code and construct them only from trusted text.
