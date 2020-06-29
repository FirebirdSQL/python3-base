================================
Firebird base modules for Python
================================

The `firebird-base` package provides common Python 3 modules used by `Firebird Project`_
in various development projects. However, these modules have general applicability outside
the scope of development for `Firebird`_ ® RDBMS.

Topic covered by `firebird-base` package:

* General data types like `singletons`, `sentinels` and objects with identity.
* Unified system for data conversion from/to string.
* `DataList` and `Registry` collection types with advanced data-processing cappabilities.
* Work with structured binary buffers.
* Global registry of Google `protobuf` messages and enumerations.
* Extended configuration system based on `ConfigParser`.
* Context-based logging.
* Trace/audit for class instances.
* General "hook" mechanism.


|donate|

.. _Firebird: http://www.firebirdsql.org
.. _Firebird Project: https://github.com/FirebirdSQL

.. |donate| image:: https://www.firebirdsql.org/img/donate/donate_to_firebird.gif
    :alt: Contribute to the development
    :scale: 100%
    :target: https://www.firebirdsql.org/en/donate/
