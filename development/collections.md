# `firebird.base.collections`

Source: `src/firebird/base/collections.py`. Tests: `tests/test_collections.py`.

`BaseObjectCollection` supplies `filter`, `filterfalse`, `find`, `contains`, `report`, `occurrence`,
`all`, and `any`. Predicates can be callables or string expressions. `make_lambda()` compiles
the latter using `eval`, so expressions must come from trusted input.

`DataList` extends `list` with optional element `type_spec`, a key expression, keyed `get()`,
sort, split, extract, and a frozen state. Freezing prevents supported mutations and builds
a lookup map when a key expression exists. A `Distinct` element type supplies `item.get_key()`
as the default key expression. Keep ordinary list behavior, type checking, frozen behavior,
and the lookup map aligned when changing mutation or retrieval logic.

`Registry` stores `Distinct` objects by their `get_key()` values and exposes mapping style
lookup alongside collection query methods. Its iteration yields stored objects, so inspect
its API before substituting a plain `dict`. Other modules use it for convertors, protobuf
types, hooks, and trace metadata.
