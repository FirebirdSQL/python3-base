# Change Log
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](http://keepachangelog.com/)
and this project adheres to [Semantic Versioning](http://semver.org/).

## [2.0.0] - Unreleased

### Added

- `firebird.base.buffer.MemoryBuffer.get_raw` method.
- `get_raw` method to `BufferFactory`, `BytesBufferFactory` and `CTypesBufferFactory`.
- `__repr__` method for `PyCode` and `PyCallable` that will limit output to 50 characters.
- Optional `encoding` parameter for `ZMQAddress` constructor.

### Changed

- Tests changed from `unittest` to `pytest`, 96% code coverage.
- Minimal Python version raised to 3.11.
- The `firebird.base.logging` module was completelly reworked.
- Function `firebird.base.types.Conjunctive` renamed to `conjunctive`.
- `firebird.base.collections.DataList.__init__` parameter `frozen` is now keyword-only.
- `firebird.base.collections.DataList.extract` parameter `copy` is now keyword-only.
- `firebird.base.collections.DataList.sort` parameter `reverse` is now keyword-only.
- `firebird.base.collections.DataList.split` parameter `frozen` is now keyword-only.
- `firebird.base.collections.Registry.popitem` parameter `last` is now keyword-only.
- `firebird.base.collections.BaseObjectCollection.contains` parameter `expr` now does not have default value.
- Deprecated `firebird.base.config.create_config` function was removed.
- `firebird.base.config.DirectoryScheme` parameter `force_home` is now keyword only.
- `firebird.base.config.Option` parameters `required` and `default` are now keyword only.
- Parameter `context` was removed from `firebird.base.trace.traced` decorator.
- Option `context` was removed from `firebird.base.trace.BaseTraceConfig`.
- Log function return value as `repr` rather than `str`.
- Sentinel objects completely reworked. Individual sentinels are now classes derived from `Sentinel`.

### Fixed

- Broken `firebird.base.types.Distinct` support for dataclasses and hash function.
- Raise `BufferError` istead `IOError` in `firebird.base.buffer.MemoryBuffer` methods `resize`,
  `read` and `read_number`
- Problem with `firebird.base.collections.Registry.pop` that did not raised `KeyError` when
  `default` was not specified.
- Bug in `firebird.base.collections.Registry.popitem` with `last` = True.
- Problem with name handling in `firebird.base.config.ConfigOption.clear` and `set_value`.
- Problem with `firebird.base.config.WindowsDirectoryScheme` and `firebird.base.config.MacOSDirectoryScheme` constructors.
- Problem with `firebird.base.config.ListOption.item_types` value.
- Problem with internal `.Convertor` initialization in `firebird.base.config.ListOption`.
- Use copy of `default` list stead direct use in `firebird.base.config.ListOption`.
- `firebird.base.config.ListOption.get_formatted` and `firebird.base.config.ListOption.get_as_str`
  should return typed values for multitype lists.
- `firebird.base.config.ConfigOption.validate` should validate the `Config` as well if defined.
- `firebird.base.config.ConfigListOption.validate` should report error for empty list when `required`.
- Problem with conversion of flags from string in `firebird.base.strconv`.

## [1.8.0] - 2024-05-03

### Added

- New `EnvExtendedInterpolation` class in `cnfig` module that extends `configparser.ExtendedInterpolation`
  with special handling for "env" section that returns value of specified environment
  variable, or empty string if such variable is not defined.

## [1.7.2] - 2024-02-20

### Fixed

- `Error.getattr()` should not mask the absence of `__notes__` attribute.

## [1.7.1] - 2023-10-08

### Fixed

- Log record values `module` and `filename` were not assigned properly under Python 3.11
- Failed tests due to subtle changes in Python 3.11

### Changed

- Downgrade dependency to protobuf>=4.23.4

## [1.7.0] - 2023-10-03

### Changed

- Update dependency to protobuf >=4.24.3
- Build system changed from setuptools to hatch
- Package version is now defined in firebird.base.__about__.py (__version__)

### Added

- .pyi file for config protobuf

## [1.6.1] - 2023-03-03

### Fixed

- Bug with Config.get_config() and `plain` bool argument.

### Changed

- firebird.base.config.StrOption now supports preservation of significant leading whitespace
  for multiline values (like PyCodeOption).

## [1.6.0] - 2023-02-15

### Fixed

- Bug in TraceManager.load_config().

### Changed

- Registration of already registered protobuf objects is now ignored instead
  raising exception.
- Module firebird.base.config:

  - Config.get_config() and Option.get_config() now provides  `plain` bool argument to
    return configuration text without comments. Deafult is False.
  - create_config is now deprecated, will be removed in version 2.0.

## [1.5.0] - 2022-11-14

### Changed

- Move away from setup.cfg to pyproject.toml, new source tree layout.

## [1.4.3] - 2022-10-27

### Added

- Added internal functions firebird.base.types._decompose and firebird.base.types._power_of_two
  from stdlib enum module, because they were removed in Python 3.11.

### Changed

- Module firebird.base.protobuf now uses importlib.metadata.entry_points <entry-points>
  instead pkg_resources.iter_entry_points.
- Improved documentation.

## [1.4.2] - 2022-10-05

### Fixed

- Signature in firebird.base.config.IntOption.clear().
- Signature in firebird.base.trace.TraceManager.add_trace(). Keyword argument `decorator`
  (with default) could not be used with args/kwargs, so it was removed. New
  firebird.base.trace.TraceManager.decorator attribute was added to
  firebird.base.trace.TraceManager that could be used to change trace decorator used
  for intrumentation.

### Changed

- Optimizations.
- Cleanup of pylint warnings.
- Updated documentation.

## [1.4.1] - 2022-09-28

### Added

- Documentation is now also provided as Dash / Zeal docset, downloadable from releases
  at github.

### Fixed

- Uregistered bug in trace.TraceConfig - redundant `flags` definition.

## [1.4.0] - 2022-06-13

### Changed

- Upgrade to protobuf 4.21.1. As this upgrade has consequences, please read
  https://developers.google.com/protocol-buffers/docs/news/2022-05-06#python-updates

## [1.3.1] - 2022-01-11

### Added

* `~firebird.base.buffer` module:

- Added firebird.base.buffer.MemoryBuffer.write_sized_string() for symetry with read_sized_string().
- Now firebird.base.buffer.MemoryBuffer string functions has also `errors` parameter in
  addition to `encoding`.

### Changed

- Direct assignment to firebird.base.config.Config option raises a `ValueError` exception
  with message "Cannot assign values to option itself, use `option.value` instead".

## [1.3.0] - 2021-06-03

### Added

- firebird.base.config.Config has new constructor keyword-only argument `description`.

### Fixed

- Uregistered bug in config.ListOption - value and default was the same instance

### Changed

- Layout produced by firebird.base.config.get_config() was changed.

## [1.2.0] - 2021-03-04

### Added

- New function firebird.base.protobuf.get_message_factory.
- Module firebird.base.trace: Added: `apply_to_descendants` boolean configuration option to
  apply configuration also to all registered descendant classes. The default value is `True`.

### Fixed

- Bug in firebird.base.signal.eventsocket signature handling.

### Changed

- Build scheme changed to `PEP 517`.
- Various changes to documentation and type hint adjustments.
- firebird.base.config module:

  - **BREAKING CHANGE**: ApplicationDirectoryScheme was replaced by
    DirectoryScheme class, and get_directory_scheme() has changed signature.
  - Directory scheme was reworked and now also supports concept of HOME directory.
  - New MacOS directory scheme support. As I don't have access to MacOS, this support
    should be considered EXPERIMENTAL. Any feedback about it's correctness is welcome.
  - Added: New Config constructor keyword-only `bool` argument `optional` and
    associated Config.optional read-only property.
  - Added: Config.has_value() function.
  - New class: PathOption for Configuration options with `pathlib.Path` value.

## [1.1.0] - 2020-11-30

### Added

- New module: signal - Callback system based on Signals and Slots, and "Delphi events"
- New class: firebird.base.config.ApplicationDirectoryScheme
- Introduced firebird.base.config.PROTO_CONFIG constant with fully qualified name for
  ConfigProto protobuf.
- Module firebird.base.protobuf: Added direct support for key well-known data types
  `Empty`, `Any`, `Duration`, `Timestamp`, `Struct`, `Value`, `ListValue` and `FieldMask`.
  They are automatically registered. New constants 'PROTO_<type>' with fully qualified names.
- firebird.base.protobuf.create_message()` has new optional `serialized` argument with
  `bytes` that should be parsed into newly created message instance.
- New functions firebird.base.protobuf.struct2dict() and firebird.base.protobuf.dict2struct()
- Modules firebird.base.trace: Added support for trace configuration based on firebird.base.config,
  using new classes BaseTraceConfig, TracedMethodConfig, TracedClassConfig and TraceConfig.
- New methods in firebird.base.trace.TraceManager:

  - load_config() to update trace from configuration.
  - set_flag() and clear_flag().
- New function firebird.base.types.load().

### Changed

- firebird.base.types.load() function now supports `object_name[.object_name...]`
  specifications instead single `object_name`.
- firebird.base.config.Config.load_config(): raises error when section is missing,
  better error handling when exception is raised while loading options
- firebird.base.config.PyCallableOption signature argument could be inspect.Signature
  or Callable
- Optional argument `to_default` in `~firebird.base.config.Option.clear()` is now keyword-only.
- firebird.base.logging.get_logging_id() uses __qualname__ instead __name__
- firebird.base.trace.TraceFlag value `DISABLED` was renamed to `NONE`.
- firebird.base.types.MIME now handles access to properties more efficiently and faster.
- Changes in documentation.

## [1.0.0] - 2020-10-13

### Added

- Documentation: new examples for trace, logging and hooks
- Documentation: adjustments to css

### Changed

- DataList is now generic class.
- DataList.extract() has new 'copy' argument.

## [0.6.1] - 2020-09-15

- Promoted to stable
- More documentation

## [0.6.0] - 2020-06-30

### Added

- New module: firebird.base.strconv - Data conversion from/to string
- New module: firebird.base.trace - Trace/audit for class instances

### Changed

- Changed module: firebird.base.types, New classes: MIME - MIME type specification,
  PyExpr - Source code for Python expression, PyCode - Python source code and PyCallable -
  Source code for Python callable. Removed function: str2bool
- Reworked module: firebird.base.config - Classes for configuration definitions
  with new classes: ConfigOption - Configuration option with Config value,
  ConfigListOption - Configuration option with list of Config values, and
  DataclassOption - Configuration option with a dataclass value.
- Changed module: firebird.base.logging - Trace/audit functionality removed (into new
  module firebird.base.trace)

## [0.5.0] - 2020-05-28

Initial release.

