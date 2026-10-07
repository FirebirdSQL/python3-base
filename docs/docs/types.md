
# types - Common data types

## Overview

::: firebird.base.types
    options:
        members: false

## Exceptions

::: firebird.base.types.Error
## Singletons

Singleton is a pattern that restricts the instantiation of a class to one "single" instance.
This is useful when exactly one object is needed to coordinate actions across the system.

Common uses:

- The abstract factory, factory method, builder, and prototype patterns can use singletons
  in their implementation.
- Facade objects are often singletons because only one facade object is required.
- State objects are often singletons.
- Singletons are often preferred to global variables because:

  - They do not pollute the global namespace with unnecessary variables.
  - They permit lazy allocation and initialization.

To create your own singletons, use [Singleton][firebird.base.types.Singleton] as the base class.

!!! example
    ```python
    >>> class MySingleton(Singleton):
    ...     "Description"
    ...     ...
    ...
    >>> obj1 = MySingleton()
    >>> obj2 = MySingleton()
    >>> obj1 is obj2
    True
    ```

::: firebird.base.types.Singleton

## Sentinels

The Sentinel Object pattern is a standard Pythonic approach that’s used both in the
Standard Library and beyond. The pattern most often uses Python’s built-in `None` object,
but in situations where None might be a useful value, a unique sentinel `object()` can be
used instead to indicate missing or unspecified data, or other specific condition.

However, the plain `object()` sentinel has not very useful `str` and `repr` values.
The [Sentinel][firebird.base.types.Sentinel] class provides named sentinels, with meaningful `str` and `repr`.

::: firebird.base.types.Sentinel

### Predefined sentinels

::: firebird.base.types.DEFAULT

::: firebird.base.types.INFINITY

::: firebird.base.types.UNLIMITED

::: firebird.base.types.UNKNOWN

::: firebird.base.types.NOT_FOUND

::: firebird.base.types.UNDEFINED

::: firebird.base.types.ANY

::: firebird.base.types.ALL

::: firebird.base.types.SUSPEND

::: firebird.base.types.RESUME

::: firebird.base.types.STOP

## Distinct objects

Some complex data structures or data processing algorithms require unique object
identification (ie object identity). In Python, an object identity is defined internally
as unique instance identity that is not suitable for complex objects whose identity is
derived from content.

The [Distinct][firebird.base.types.Distinct] abstract base class is intended as a unified solution to these needs.

!!! seealso
    module [firebird.base.collections][]

::: firebird.base.types.Distinct

::: firebird.base.types.CachedDistinct

## Enums

::: firebird.base.types.ByteOrder

::: firebird.base.types.ZMQTransport

::: firebird.base.types.ZMQDomain

## Custom string types

Some string values have unified structure and carry specific information (like network
address or database connection string). Typical repeating operation with these values
are validation and parsing. It makes sense to put these operations under one roof.
One such approach uses custom descendants of builtin `str` type.

!!! caution
    Custom string types have an inherent weakness. They support all inherited string methods,
    but any method that returns string value return a base `str` type, not the descendant class
    type. That same apply when you assign strings to variables that should be of custom
    string type.

    !!! tip
        Module [firebird.base.strconv][] could help you to safely translate strings stored
        externally to typed strings.

::: firebird.base.types.ZMQAddress

::: firebird.base.types.MIME

::: firebird.base.types.PyExpr

::: firebird.base.types.PyCode

::: firebird.base.types.PyCallable

## Meta classes

::: firebird.base.types.SingletonMeta

::: firebird.base.types._SentinelMeta

::: firebird.base.types.CachedDistinctMeta

::: firebird.base.types.conjunctive

## Functions

::: firebird.base.types.load
