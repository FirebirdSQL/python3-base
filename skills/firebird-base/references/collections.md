# `firebird.base.collections`

[Published API](https://firebird-base.readthedocs.io/collections/index.md)

Use `DataList` when list behavior plus filtering, reporting, type checks, keyed lookup, or
freezing helps. Supply a stable key expression for keyed `get()`; `Distinct` items can use
their `get_key()` by default. Use `Registry` for `Distinct` objects keyed by identity. Its
iteration yields objects, so check mapping behavior before treating it like a plain `dict`.
`filter()`, `filterfalse()`, and `report()` return generators; consume them when a concrete
result is needed.

Avoid string predicates or key expressions derived from untrusted input: `make_lambda()`
evaluates them as Python code. Prefer callables for external criteria. Do not mutate a frozen
`DataList`, or change an item's key while it is indexed. Do not assume `Registry` iteration
yields keys.
