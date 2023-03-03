================================
Firebird base modules for Python
================================

The firebird-base package is a set of Python 3 modules commonly used by `Firebird Project`_
in various development projects (for example the firebird-driver or Saturnin). However, these
modules have general applicability outside the scope of development for Firebird_.

Common data types
=================

The `types` module provides collection of classes and other types that are often used by
other library modules or applications.

* Exception `Error` that is intended to be used as a base class of all application-related
  errors. The important difference from `Exception` class is that `Error` accepts keyword
  arguments, that are stored into instance attributes with the same name.
* `Singleton` base class for singletons.
* `Sentinel` base class for named sentinel objects that provide meaningful `str` and `repr`,
  along with collection of predefined sentinels.
* `Distinct` abstract base class for classes (incl. dataclasses) with distinct instances.
* Collection of `Enums` and `custom string types`.

Various collection types
========================

The `collections` module provides data structures that behave much like builtin `list` and
`dict` types, but with direct support of operations that can use structured data stored in
container, and which would normally require utilization of `operator`, `functools` or other
means.

All containers provide next operations:

* `filter` and `filterfalse` that return generator that yields items for which expr is
  evaluated as True (or False).
* `find` that returns first item for which expr is evaluated as True, or default.
* `contains` that returns True if there is any item for which expr is evaluated as True.
* `occurrence` that returns number of items for which expr is evaluated as True.
* `all` and `any` that return True if expr is evaluated as True for all or any collection element(s).
* `report` that returns generator that yields data produced by expression(s) evaluated on collection items.

Individual collection types provide additional operations like splitting and extracting
based on expression etc.

Expressions used by these methods could be strings that contain Python expression referencing
the collection item(s), or lambda functions.

Data conversion from/to string
==============================

While Python types typically support conversion to string via builtin `str()` function (and
custom `__str__` methods), there is no symetric operation that converts string created by
`str()` back to typed value. Module `strconv` provides support for such symetric conversion
from/to string for any data type.

Symetric string conversion is used by `firebird.base.config` module, notably by
`firebird.base.config.ListOption` and `firebird.base.config.DataclassOption`. You can
extend the range of data types supported by these options by registering convertors for
required data types.

Configuration definitions
=========================

Complex applications (and some library modules like `logging`) could be often parametrized
via configuration. Module `firebird.base.config` provides a framework for unified structured
configuration that supports:

* configuration options of various data type, including lists and other complex types
* validation
* direct manipulation of configuration values
* reading from (and writing into) configuration in `configparser` format
* exchanging configuration (for example between processes) using Google protobuf messages

Additionally, the `ApplicationDirectoryScheme` abstract base class defines set of mostly
used application directories. The function `get_directory_scheme()` could be then used
to obtain instance that implements platform-specific standards for file-system location
for these directories. Currently, only "Windows", "Linux" and "MacOS" directory schemes
are supported.

Memory buffer manager
=====================

Module `buffer` provides a raw memory buffer manager with convenient methods to read/write
data of various data types.

Hook manager
============

Module `hooks` provides a general framework for callbacks and “hookable” events, that
supports multiple usage strategies.

Context-based logging
=====================

Module `logging` provides context-based logging system built on top of standard `logging`
module.

The context-based logging:

* Adds context information (defined as combination of topic, agent and context string values)
  into `logging.LogRecord`, that could be used in logging message.
* Adds support for f-string message format.
* Allows assignment of loggers to specific contexts. The `LoggingManager` class maintains
  a set of bindings between `Logger` objects and combination of `agent`, `context` and `topic`
  specifications. It’s possible to bind loggers to exact combination of values, or whole
  sets of values using `ANY` sentinel. It means that is possible to assign specific Logger
  to log messages for particular agent in any context, or any agent operating in specific
  context etc.

Trace/audit for class instances
===============================

Module `trace` provides trace/audit logging for functions or object methods through
context-based logging provided by `logging` module.

The trace logging is performed by `traced` decorator. You can use this decorator directly,
or use `TracedMixin` class to automatically decorate methods of class instances on creation.
Each decorated callable could log messages before execution, after successful execution or
on failed execution (when unhandled exception is raised by callable). The trace decorator
can automatically add `agent` and `context` information, and include parameters passed to
callable, execution time, return value, information about raised exception etc. to log messages.

The trace logging is managed by `TraceManager`, that allows dynamic configuration of traced
callables at runtime.

Trace supports configuration based on `firebird.base.config`.

Registry for Google Protocol Buffer messages and enums
======================================================

Module `protobuf` provides central registry for Google Protocol Buffer messages and enums.
The generated `*_pb2.py protobuf` files could be registered using `register_decriptor` or
`load_registered` function. The registry could be then used to obtain information about
protobuf messages or enum types, or to create message instances or enum values.

Callback systems
================

Module `firebird.base.signal` provides two callback mechanisms: one based on signals and
slots similar to Qt signal/slot, and second based on optional method delegation similar to
events in Delphi.

In both cases, the callback callables could be functions, instance or class methods,
partials and lambda functions. The `inspect` module is used to define the signature for
callbacks, and to validate that only compatible callables are assigned.

|donate|

.. _Firebird: http://www.firebirdsql.org
.. _Firebird Project: https://github.com/FirebirdSQL

.. |donate| image:: https://www.firebirdsql.org/img/donate/donate_to_firebird.gif
    :alt: Contribute to the development
    :scale: 100%
    :target: https://www.firebirdsql.org/en/donate/
