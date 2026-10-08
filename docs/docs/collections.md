# collections - Various collection types

## Overview

::: firebird.base.collections
    options:
        members: false

Methods such as `filter()` accept either a Python callable or a string expression.
String expressions are evaluated as Python code, so use them only when the expression
comes from a trusted source. For input from users or other untrusted sources, choose a
callable defined by your application:

```python
from firebird.base.collections import DataList

names = DataList(["Ada", "Bob", "Alex"])
selected = list(names.filter(lambda name: name.startswith("A")))
assert selected == ["Ada", "Alex"]
```

## Types for type hints & annotations

::: firebird.base.collections.Item

::: firebird.base.collections.TypeSpec

::: firebird.base.collections.ItemExpr

::: firebird.base.collections.FilterExpr

::: firebird.base.collections.CheckExpr

## Collections

::: firebird.base.collections.BaseObjectCollection

::: firebird.base.collections.DataList

::: firebird.base.collections.Registry

## Functions

::: firebird.base.collections.make_lambda
