# strconv - Data conversion from/to string

## Overview

::: firebird.base.strconv
    options:
        members: false

While Python types typically support conversion to string via builtin `str()` function
(and custom `__str__` methods), there is no symetric operation that converts string created
by `str()` back to typed value. This module provides support for such symetric conversion
from/to string for any data type.

!!! note
    Symetric string conversion is used by [firebird.base.config][] module, notably by
    [ListOption][firebird.base.config.ListOption] and [DataclassOption][firebird.base.config.DataclassOption].
    You can extend the range of data types supported by these options by registering convertors
    for required data types.

### Architecture

Module maintains a global registry of convertors associated with a data type. These
convertor functions may support conversion for multiple data types, and must have signatures:

```python
# Conversion to string

def value2str(value: Any) -> str:
    ...

# Conversion from string

def str2value(cls: Type, value: str) -> Any:
    ...
```

Convertors should raise [ValueError][] when conversion fails.

Convertors must be registered using [register_convertor][firebird.base.strconv.register_convertor]
function, or reassigned using [update_convertor][firebird.base.strconv.update_convertor].

There are two methods for use of registered convertors:

1. By using functions [convert_to_str][firebird.base.strconv.convert_to_str] and
   [convert_from_str][firebird.base.strconv.convert_from_str]. These functions use
   convertor that is registered for particular data type. If there is no such convertor,
   they use first convertor registered for any base class. The lookup is performed in Method
   Resolution Order. This method is preferred when you will work with various data types.
2. Using [get_convertor][firebird.base.strconv.get_convertor] function to obtain registry
   entry with convertors.

   This method is preferred when you will work with single data type repeatedly.

!!! important
    The convertor registry lookup could be done either for a class, or class name.

    Lookup for a class is first performed for specified class. If there is no such entry,
    all base classes in Method Resolution Order are used for lookup, and the first entry
    found is returned.

    Lookup for a class name could be performed only for a specified class. Because some types
    could be converted using convertors registered for their base class, such lookup will
    not find the required convertor entry. To circumvent this issue, it's necessary to
    register a class for name lookup using [register_class][firebird.base.strconv.register_class]
    function. The registry lookup uses this class registry to use the actual type instead type name.

### Registered data types

Module registers convertor functions for next data types:

* `str`
* `int`
* `float`
* `complex`
* `bool`. Uses `TRUE_STR` and `FALSE_STR` list for conversion from string (the case is NOT
  significant). Conversion to string always uses first item in these lists.
* `decimal.Decimal`
* `uuid.UUID`
* `MIME`
* `ZMQAddress`
* `enum.Enum` and `enum.Flag`. Supports conversion for all descendants of `Enum`,
  `IntEnum`, `Flag` and `IntFlag`.

!!! tip
    Functions [any2str][firebird.base.strconv.any2str] and [str2any][firebird.base.strconv.str2any]
    could be used to register conversion for data types that support symetric conversion via
    `__str__()` method and class constructor (`__init__()` must accept one positional argument
    that could be a string and all other arguments must be keyword arguments with default values).

## Types for annotations

::: firebird.base.strconv.TConvertToStr

::: firebird.base.strconv.TConvertFromStr

## Globals

::: firebird.base.strconv.TRUE_STR

::: firebird.base.strconv.FALSE_STR

## Functions

::: firebird.base.strconv.convert_to_str

::: firebird.base.strconv.convert_from_str

::: firebird.base.strconv.register_convertor

::: firebird.base.strconv.update_convertor

::: firebird.base.strconv.register_class

::: firebird.base.strconv.has_convertor

::: firebird.base.strconv.get_convertor

::: firebird.base.strconv.any2str

::: firebird.base.strconv.str2any

## Dataclasses

::: firebird.base.strconv.Convertor
