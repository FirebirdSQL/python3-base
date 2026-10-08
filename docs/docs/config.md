# config - Configuration definitions

## Overview

::: firebird.base.config
    options:
        members: false

### Architecture

The framework is based around two classes:

* [Config][firebird.base.config.Config] - Collection of configuration options and sub-collections.
  Particular configuration is then realized as descendant from this class, that defines configuration
  options in constructor, and customize the validation when required.
* [Option][firebird.base.config.Option] - Abstract base class for configuration options,
  where descendants implement handling of particular data type. This module provides
  implementation for next data types: [str][], [int][], [float][], [bool][], [decimal.Decimal][],
  [enum.Enum][], [enum.Flag][], [uuid.UUID][], [pathlib.Path][], [MIME][firebird.base.types.MIME],
  [ZMQAddress][firebird.base.types.ZMQAddress], [list][], [dataclasses.dataclass][],
  [PyExpr][firebird.base.types.PyExpr], [PyCode][firebird.base.types.PyCode] and
  [PyCallable][firebird.base.types.PyCallable].
  It also provides special options [ConfigOption][firebird.base.config.ConfigOption] and
  [ConfigListOption][firebird.base.config.ConfigListOption].

Use `ConfigOption` for one nested `Config` object whose section name is stored in an
option. Use `ConfigListOption` for a list of nested `Config` objects: its option value
contains their section names, separated by commas or by lines. When loading an INI
file, `Config` loads the options from those referenced sections as well.

Additionally, the [DirectoryScheme][firebird.base.config.DirectoryScheme] abstract base class
defines set of mostly used application directories. The function
[get_directory_scheme()][firebird.base.config.get_directory_scheme] could be then used
to obtain instance that implements platform-specific standards for file-system location
for these directories. Currently, only "Windows", "Linux" and "MacOS" directory schemes
are supported.

!!! tip
    You may use `get_directory_scheme()` function to get the scheme suitable for platform
    where your application is running.

!!! tip
    If your configurations contain secrets like passwords or access tokens, that would be
    read from files via [configparser][], you should consider to use
    [EnvExtendedInterpolation][firebird.base.config.EnvExtendedInterpolation]
    that has support for option values defined via environment variables.

### Usage
First, you need to define your own configuration.

```python
from enum import IntEnum
from firebird.base.config import Config, StrOption, IntOption, ListOption

class SampleEnum(IntEnum):
    "Enum for testing"
    UNKNOWN    = 0
    READY      = 1
    RUNNING    = 2
    WAITING    = 3
    SUSPENDED  = 4
    FINISHED   = 5
    ABORTED    = 6

class DbConfig(Config):
    "Simple database config"
    def __init__(self, name: str):
        super().__init__(name)
        # options
        self.database: StrOption = StrOption('database', 'Database connection string',
                                             required=True)
        self.user: StrOption = StrOption('user', 'User name', required=True,
                                         default='SYSDBA')
        self.password: StrOption = StrOption('password', 'User password')

class SampleConfig(Config):
    """Sample Config.

Has three options and two sub-configs.
"""
    def __init__(self):
        super().__init__('sample-config')
        # options
        self.opt_str: StrOption = StrOption('opt_str', "Sample string option")
        self.opt_int: IntOption = IntOption('opt_int', "Sample int option")
        self.enum_list: ListOption = ListOption('enum_list', SampleEnum, "List of enum values")
        # sub configs
        self.master_db: DbConfig = DbConfig('master-db')
        self.backup_db: DbConfig = DbConfig('backup-db')
```

!!! important
    Option must be assigned to `Config` attributes with the same name as option name.

Typically you need only one instance of your configuration class in application.

```python
app_config: SampleConfig = SampleConfig()

```
Typically, your application is configured using file(s) in `configparser` format. You may
create initial one using `Config.get_config()` method.

!!! note
    [Config.get_config][firebird.base.config.Config.get_config] works with current configuration
    values. When called on "empty" instance it returns "default" configuration. Option values
    that match the default are returned as commented out.

```ini
>>> print(app_config.get_config())

[sample-config]
;
; Sample Config.
;
; Has three options and two sub-configs.

; Sample string option
; Type: str
;opt_str = <UNDEFINED>

; Sample int option
; Type: int
;opt_int = <UNDEFINED>

; List of enum values
; Type: list [SampleEnum]
;enum_list = <UNDEFINED>

[master-db]
;
; Simple database config

; REQUIRED option.
; Database connection string
; Type: str
;database = <UNDEFINED>

; REQUIRED option.
; User name
; Type: str
;user = SYSDBA

; User password
; Type: str
;password = <UNDEFINED>

[backup-db]
;
; Simple database config

; REQUIRED option.
; Database connection string
; Type: str
;database = <UNDEFINED>

; REQUIRED option.
; User name
; Type: str
;user = SYSDBA

; User password
; Type: str
;password = <UNDEFINED>
```
To read the configuration from file, use the [configparser.ConfigParser][] and pass it
to [Config.load_config()][firebird.base.config.Config.load_config] method.

Example configuration file:

```ini
; myapp.cfg

[DEFAULT]
password = masterkey

[sample-config]
opt_str = Lorem ipsum
enum_list = ready, finished, aborted

[master-db]
database = primary
user = tester
password = lockpick

[backup-db]
database = secondary
```

```python
from configparser import ConfigParser

cfg = ConfigParser()
cfg.read('myapp.cfg')
app_config.load_config(cfg)

```
Access to configuration values is through attributes on your `Config` instance, and
their `value` attribute.

```python
>>> app_config.opt_str.value
Lorem ipsum
>>> app_config.opt_int.value
>>> app_config.enum_list.value
[READY, FINISHED, ABORTED]
>>> app_config.master_db.database.value
primary
>>> app_config.master_db.user.value
tester
>>> app_config.master_db.password.value
lockpick
>>> app_config.backup_db.database.value
secondary
>>> app_config.backup_db.user.value
SYSDBA
>>> app_config.backup_db.password.value
masterkey

```
## ConfigProto

You can transfer configuration (state) between instances of your `Config` classes using
Google Protocol Buffer message `firebird.base.ConfigProto` and methods
[Config.save_proto()][firebird.base.config.Config.save_proto] and
[Config.load_proto()][firebird.base.config.Config.load_proto].

The protobuf message is defined in `/proto/config.proto`.

```proto
syntax = "proto3";

package firebird.base;

import "google/protobuf/any.proto";
import "google/protobuf/struct.proto";

message Value {
  oneof kind {
    string as_string = 2 ;
    bytes  as_bytes  = 3 ;
    bool   as_bool   = 4 ;
    double as_double = 5 ;
    float  as_float  = 6 ;
    sint32 as_sint32 = 7 ;
    sint64 as_sint64 = 8 ;
    uint32 as_uint32 = 9 ;
    uint64 as_uint64 = 10 ;
    google.protobuf.Any as_msg = 11 ;
  }
}

message ConfigProto {
  map<string, Value>  options = 1 ;
  map<string, ConfigProto> configs = 2 ;
}
```

!!! note
    You can use it directly or via [firebird.base.protobuf][] registry.

    ```python
    # Direct use
    from firebird.base.config import ConfigProto
    cfg_msg = ConfigProto()
    ```

    Because the proto file is NOT registered in `protobuf` registry, you must register
    it manually. The proto file is listed in `pyproject.toml` under **"firebird.base.protobuf"**
    entrypoint, so use `load_registered('firebird.base.protobuf')` for its registration.

    ```python
    from firebird.base.protobuf import load_registered, create_message
    load_registered('firebird.base.protobuf')
    cfg_msg = create_message('firebird.base.ConfigProto')
    ```

!!! important
    Although `Option` also provides methods `Config.save_proto()` and `Config.load_proto()`
    to transfer option value in/out ConfigProto message, you should always use methods
    on `Config` instance because option's serialization may relly on `Config` instance that
    owns them.

    See Also:
        [ConfigOption][firebird.base.config.ConfigOption], [ConfigListOption][firebird.base.config.ConfigListOption]

## Constants

::: firebird.base.config.PROTO_CONFIG

!!! tip
    To address `ConfigProto` in functions like `firebird.base.protobuf.create_message()`,
    use `PROTO_CONFIG` constant.


## Application Directory Scheme

::: firebird.base.config.DirectoryScheme

::: firebird.base.config.WindowsDirectoryScheme

::: firebird.base.config.LinuxDirectoryScheme

::: firebird.base.config.MacOSDirectoryScheme

::: firebird.base.config.get_directory_scheme

## Configparser interpolation

::: firebird.base.config.EnvExtendedInterpolation

## Config

::: firebird.base.config.Config

## Options

::: firebird.base.config.Option

::: firebird.base.config.StrOption

::: firebird.base.config.IntOption

::: firebird.base.config.FloatOption

::: firebird.base.config.DecimalOption

::: firebird.base.config.BoolOption

::: firebird.base.config.ZMQAddressOption

::: firebird.base.config.EnumOption

::: firebird.base.config.FlagOption

::: firebird.base.config.UUIDOption

::: firebird.base.config.MIMEOption

::: firebird.base.config.ListOption

::: firebird.base.config.DataclassOption

::: firebird.base.config.PathOption

::: firebird.base.config.PyExprOption

::: firebird.base.config.PyCodeOption

::: firebird.base.config.PyCallableOption

::: firebird.base.config.ConfigOption

::: firebird.base.config.ConfigListOption

## Functions

::: firebird.base.config.has_verticals

::: firebird.base.config.has_leading_spaces
