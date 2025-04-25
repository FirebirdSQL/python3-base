# SPDX-FileCopyrightText: 2020-present The Firebird Projects <www.firebirdsql.org>
#
# SPDX-License-Identifier: MIT
#
# PROGRAM/MODULE: firebird-base
# FILE:           firebird/base/config.py
# DESCRIPTION:    Classes for configuration definitions
# CREATED:        14.5.2020
#
# The contents of this file are subject to the MIT License
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#
# Copyright (c) 2019 Firebird Project (www.firebirdsql.org)
# All Rights Reserved.
#
# Contributor(s): Pavel Císař (original code)
#                 ______________________________________.


"""Firebird Base - Classes for configuration definitions

Complex applications (and some library modules like `logging`) could be often parametrized
via configuration. This module provides a framework for unified structured configuration
that supports:

*   Configuration options of various data types (int, str, bool, list, Enum, Path, etc.).
*   Nested configuration structures (`Config` containing other `Config` instances).
*   Type checking and validation for option values.
*   Default values and marking options as required.
*   Reading from (and writing to) configuration files in `configparser` format,
    with extended interpolation support (including environment variables via `${env:VAR}`).
*   Serialization/deserialization using Google protobuf messages (`ConfigProto`).
*   Platform-specific application directory schemes (`DirectoryScheme`).

Example::

    from firebird.base.config import Config, StrOption, IntOption, load_config
    from configparser import ConfigParser
    import io

    class ServerConfig(Config):
        '''Configuration for a server application.'''
        def __init__(self):
            super().__init__('server') # Section name in config file
            self.host = StrOption('host', 'Server hostname or IP address', default='localhost')
            self.port = IntOption('port', 'Server port number', required=True, default=8080)

    # Instantiate
    my_config = ServerConfig()

    # Load from a string (simulating a file)
    config_string = '''
    [server]
    host = 192.168.1.100
    port = 9000
    '''
    parser = ConfigParser()
    parser.read_string(config_string)
    my_config.load_config(parser)

    # Access values
    print(f"Host: {my_config.host.value}") # Output: Host: 192.168.1.100
    print(f"Port: {my_config.port.value}") # Output: Port: 9000

    # Get config file representation
    print(my_config.get_config())
"""

from __future__ import annotations

import os
import platform
from abc import ABC, abstractmethod
from collections.abc import Callable, Sequence
from configparser import (
    DEFAULTSECT,
    MAX_INTERPOLATION_DEPTH,
    ConfigParser,
    ExtendedInterpolation,
    InterpolationDepthError,
    InterpolationMissingOptionError,
    InterpolationSyntaxError,
    NoOptionError,
    NoSectionError,
)
from decimal import Decimal, DecimalException
from enum import Enum, Flag
from inspect import Parameter, Signature, signature
from pathlib import Path
from typing import Any, Generic, TypeVar, cast, get_type_hints
from uuid import UUID

from .config_pb2 import ConfigProto
from .strconv import Convertor, convert_to_str, get_convertor
from .types import MIME, Error, PyCallable, PyCode, PyExpr, ZMQAddress

PROTO_CONFIG = 'firebird.base.ConfigProto'

def has_verticals(value: str) -> bool:
    """Returns True if lines in multiline string contains leading '|' character.
    Used to detect if special vertical bar indentation was used.
    """
    return any(1 for line in value.split('\n') if line.startswith('|'))

def has_leading_spaces(value: str) -> bool:
    """Returns True if any line in multiline string starts with space(s).
    Used to determine if vertical bar notation is needed for preservation.
    """
    return any(1 for line in value.split('\n') if line.startswith(' '))

def unindent_verticals(value: str) -> str:
    """Removes leading '|' character and calculated indent from each relevant line.

    This reverses the vertical bar notation used to preserve leading whitespace
    in multiline string options when read by `ConfigParser`, which normally strips
    leading whitespace from continuation lines.
    """
    lines = []
    indent = None
    for line in value.split('\n'):
        if line.startswith('|'):
            if indent is None:
                indent = (len(line[1:]) - len(line[1:].strip())) + 1
            lines.append(line[indent:])
        else:
            lines.append(line)
    return '\n'.join(lines)

def _eq(a: Any, b: Any) -> bool:
    return str(a) == str(b)

# --- Internal helpers for FlagOption copied from stdlib enum (pre-Python 3.11) ---
def _decompose(flag, value):
    "Extract all members from the value (internal helper for FlagOption)."
    # _decompose is only called if the value is not named
    not_covered = value
    negative = value < 0
    # issue29167: wrap accesses to _value2member_map_ in a list to avoid race
    #             conditions between iterating over it and having more pseudo-
    #             members added to it
    if negative:
        # only check for named flags
        flags_to_check = [
                (m, v)
                for v, m in list(flag._value2member_map_.items())
                if m.name is not None
                ]
    else:
        # check for named flags and powers-of-two flags
        flags_to_check = [
                (m, v)
                for v, m in list(flag._value2member_map_.items())
                if m.name is not None or _power_of_two(v)
                ]
    members = []
    for member, member_value in flags_to_check:
        if member_value and member_value & value == member_value:
            members.append(member)
            not_covered &= ~member_value
    if not members and value in flag._value2member_map_:
        members.append(flag._value2member_map_[value])
    members.sort(key=lambda m: m._value_, reverse=True)
    if len(members) > 1 and members[0].value == value:
        # we have the breakdown, don't need the value member itself
        members.pop(0)
    return members, not_covered

def _power_of_two(value):
    "Check if value is a power of two (internal helper for FlagOption)."
    if value < 1:
        return False
    return value == 2 ** (value.bit_length() - 1)

class EnvExtendedInterpolation(ExtendedInterpolation):
    """.. versionadded:: 1.8.0

    Modified version of `configparser.ExtendedInterpolation` class that adds special
    handling for "env" section that returns value of specified environment variable,
    or empty string if such variable is not defined.

    Example::

       ${env:path} is reference to PATH environment variable.
    """
    def _interpolate_some(self, parser, option, accum, rest, section, map, # noqa: A002
                          depth):
        rawval = parser.get(section, option, raw=True, fallback=rest)
        if depth > MAX_INTERPOLATION_DEPTH:
            raise InterpolationDepthError(option, section, rawval)
        while rest:
            p = rest.find('$')
            if p < 0:
                accum.append(rest)
                return
            if p > 0:
                accum.append(rest[:p])
                rest = rest[p:]
            # p is no longer used
            c = rest[1:2]
            if c == '$':
                accum.append('$')
                rest = rest[2:]
            elif c == '{':
                m = self._KEYCRE.match(rest)
                if m is None:
                    raise InterpolationSyntaxError(option, section,
                        f"bad interpolation variable reference {rest!r}")
                path = m.group(1).split(':')
                rest = rest[m.end():]
                sect = section
                opt = option
                try:
                    if len(path) == 1:
                        opt = parser.optionxform(path[0])
                        v = map[opt]
                    elif len(path) == 2:# noqa: PLR2004
                        sect = path[0]
                        opt = parser.optionxform(path[1])
                        if sect == 'env':
                            v = os.getenv(opt.upper(), '')
                        else:
                            v = parser.get(sect, opt, raw=True)
                    else:
                        raise InterpolationSyntaxError(
                            option, section,
                            f"More than one ':' found: {rest!r}")
                except (KeyError, NoSectionError, NoOptionError):
                    raise InterpolationMissingOptionError(
                        option, section, rawval, ':'.join(path)) from None
                if '$' in v:
                    self._interpolate_some(parser, opt, accum, v, sect,
                                           dict(parser.items(sect, raw=True)),
                                           depth + 1)
                else:
                    accum.append(v)
            else:
                raise InterpolationSyntaxError(
                    option, section,
                    f"'$' must be followed by '$' or '{{', found: {rest!r}")

class DirectoryScheme:
    """Class that provide paths to typically used application directories.

    Default scheme uses HOME directory as root for other directories. The HOME is
    determined as follows:

    1. If environment variable `<app_name>_HOME` exists, its value is used as HOME directory.
    2. HOME directory is set to current working directory.

    Note:
        All paths are set when the instance is created and can be changed later.

    Arguments:
        name: Appplication name.
        version: Application version.
        force_home: When True, general directories (i.e. all except user-specific and
            TMP) would be always based on HOME directory.

    Example::

        scheme = get_directory_scheme("MyApp", "1.0")
        config_path = scheme.config / "settings.ini"
        log_file = scheme.logs / "app.log"
        user_cache_dir = scheme.user_cache
        print(f"Config dir: {scheme.config}")
        print(f"User cache: {user_cache_dir}")
    """
    def __init__(self, name: str, version: str | None=None, *, force_home: bool=False):
        self.name: str = name
        self.version: str = version
        self.force_home: bool = force_home
        _h = os.getenv(f"{self.name.upper()}_HOME")
        self.__home: Path = Path(_h) if _h is not None else Path.cwd()
        home: Path = self.home
        self.dir_map: dict[str, Path] = {'config': home / 'config',
                                         'run_data': home / 'run_data',
                                         'logs': home / 'logs',
                                         'data': home / 'data',
                                         'tmp': home / 'tmp',
                                         'cache': home / 'cache',
                                         'srv': home / 'srv',
                                         'user_config': home / 'user_config',
                                         'user_data': home / 'user_data',
                                         'user_sync': home / 'user_sync',
                                         'user_cache': home / 'user_cache',
                                      }
    def has_home_env(self) -> bool:
        """Returns True if HOME directory is set by "<app_name>_HOME" environment variable.
        """
        return os.getenv(f'{self.name.upper()}_HOME') is not None
    @property
    def home(self) -> Path:
        """HOME directory. Initial value is path set by `<app_name>_HOME` environment
        variable, or to current working directory when variable is not defined.

        Important:
            When new value is assigned, the general directories (i.e. all except user-specific
            and TMP) are redefined as subdirectories of new home path ONLY when HOME was
            initially defined using `<app_name>_HOME` environment variable, or instance
            was created with `force_home` = True.

            However, all paths could be still changed individually to any value.
        """
        return self.__home
    @home.setter
    def home(self, value: Path | str) -> None:
        self.__home = value if isinstance(value, Path) else Path(value)
        if self.has_home_env() or self.force_home:
            self.dir_map.update({'config': self.__home / 'config',
                                 'run_data': self.__home / 'run_data',
                                 'logs': self.__home / 'logs',
                                 'data': self.__home / 'data',
                                 'cache': self.__home / 'cache',
                                 'srv': self.__home / 'srv'})
    @property
    def config(self) -> Path:
        """Directory for host-specific system-wide configuration files.
        """
        return self.dir_map['config']
    @config.setter
    def config(self, path: Path) -> None:
        self.dir_map['config'] = path
    @property
    def run_data(self) -> Path:
        """Directory for run-time variable data that may not persist over boot.
        """
        return self.dir_map['run_data']
    @run_data.setter
    def run_data(self, path: Path) -> None:
        self.dir_map['run_data'] = path
    @property
    def logs(self) -> Path:
        """Directory for log files.
        """
        return self.dir_map['logs']
    @logs.setter
    def logs(self, path: Path) -> None:
        self.dir_map['logs'] = path
    @property
    def data(self) -> Path:
        """Directory for state information / persistent data modified by application as
        it runs.
        """
        return self.dir_map['data']
    @data.setter
    def data(self, path: Path) -> None:
        self.dir_map['data'] = path
    @property
    def tmp(self) -> Path:
        """Directory for temporary files to be preserved between reboots.
        """
        return self.dir_map['tmp']
    @tmp.setter
    def tmp(self, path: Path) -> None:
        self.dir_map['tmp'] = path
    @property
    def cache(self) -> Path:
        """Directory for application cache data.

        Such data are locally generated as a result of time-consuming I/O or calculation.
        The application must be able to regenerate or restore the data. The cached files
        can be deleted without loss of data.
        """
        return self.dir_map['cache']
    @cache.setter
    def cache(self, path: Path) -> None:
        self.dir_map['cache'] = path
    @property
    def srv(self) -> Path:
        """Directory for site-specific data served by this system, such as data and
        scripts for web servers, data offered by FTP servers, and repositories for
        version control systems etc.
        """
        return self.dir_map['srv']
    @srv.setter
    def srv(self, path: Path) -> None:
        self.dir_map['srv'] = path
    @property
    def user_config(self) -> Path:
        """Directory for user-specific configuration.
        """
        return self.dir_map['user_config']
    @user_config.setter
    def user_config(self, path: Path) -> None:
        self.dir_map['user_config'] = path
    @property
    def user_data(self) -> Path:
        """Directory for User local data.
        """
        return self.dir_map['user_data']
    @user_data.setter
    def user_data(self, path: Path) -> None:
        self.dir_map['user_data'] = path
    @property
    def user_sync(self) -> Path:
        """Directory for user data synced accross systems (roaming).
        """
        return self.dir_map['user_sync']
    @user_sync.setter
    def user_sync(self, path: Path) -> None:
        self.dir_map['user_sync'] = path
    @property
    def user_cache(self) -> Path:
        """Directory for user-specific application cache data.
        """
        return self.dir_map['user_cache']
    @user_cache.setter
    def user_cache(self, path: Path) -> None:
        self.dir_map['user_cache'] = path


class WindowsDirectoryScheme(DirectoryScheme):
    """Directory scheme conforming to Windows standards (e.g., APPDATA, PROGRAMDATA).

    If HOME is defined using "<app_name>_HOME" environment variable, or `force_home` parameter
    is True, only user-specific directories and TMP are set according to platform standars,
    while general directories remain as defined by base `DirectoryScheme`.

    Arguments:
        name: Appplication name.
        version: Application version.
        force_home: When True, general directories (i.e. all except user-specific and
            TMP) would be always based on HOME directory.
    """
    def __init__(self, name: str, version: str | None=None, *, force_home: bool=False):
        super().__init__(name, version, force_home=force_home)
        app_dir = Path(self.name)
        if self.version is not None:
            app_dir /= self.version
        pd = Path(os.path.expandvars('%PROGRAMDATA%'))
        lad = Path(os.path.expandvars('%LOCALAPPDATA%'))
        ad = Path(os.path.expandvars('%APPDATA%'))
        # Set general directories only when HOME is not forced by environment variable.
        if not self.has_home_env() and not force_home:
            self.dir_map.update({'config': pd / app_dir / 'config',
                                 'run_data': pd / app_dir / 'run',
                                 'logs': pd / app_dir / 'log',
                                 'data': pd / app_dir / 'data',
                                 'cache': pd / app_dir / 'cache',
                                 'srv': pd / app_dir / 'srv',
                                 })
        # Always set user-specific directories and TMP
        self.dir_map.update({'tmp': lad / app_dir / 'tmp',
                             'user_config': lad / app_dir / 'config',
                             'user_data': lad / app_dir / 'data',
                             'user_sync': ad / app_dir,
                             'user_cache': lad / app_dir / 'cache',
                             })

class LinuxDirectoryScheme(DirectoryScheme):
    """Directory scheme that conforms to Linux standards.

    If HOME is defined using "<app_name>_HOME" environment variable, or `force_home` parameter
    is True, only user-specific directories and TMP are set according to platform standars,
    while general directories remain as defined by base `DirectoryScheme`.

    Arguments:
        name: Appplication name.
        version: Application version.
        force_home: When True, general directories (i.e. all except user-specific and
            TMP) would be always based on HOME directory.
    """
    def __init__(self, name: str, version: str | None=None, *, force_home: bool=False):
        super().__init__(name, version, force_home=force_home)
        app_dir = Path(self.name)
        if self.version is not None:
            app_dir /= self.version
        # Set general directories only when HOME is not forced by environment variable.
        if not self.has_home_env() and not force_home:
            self.dir_map.update({'config': Path('/etc') / app_dir,
                                 'run_data': Path('/run') / app_dir,
                                 'logs': Path('/var/log') / app_dir,
                                 'data': Path('/var/lib') / app_dir,
                                 'cache': Path('/var/cache') / app_dir,
                                 'srv': Path('/srv') / app_dir,
                                 })
        # Always set user-specific directories and TMP
        self.dir_map.update({'tmp': Path('/var/tmp') / app_dir, # noqa S108
                             'user_config': Path('~/.config').expanduser() / app_dir,
                             'user_data': Path('~/.local/share').expanduser() / app_dir,
                             'user_sync': Path('~/.local/sync').expanduser() / app_dir,
                             'user_cache': Path('~/.cache').expanduser() / app_dir,
                             })

class MacOSDirectoryScheme(DirectoryScheme):
    """Directory scheme that conforms to MacOS standards.

    If HOME is defined using "<app_name>_HOME" environment variable, only user-specific
    directories and TMP are set according to platform standars, while general directories
    remain as defined by base `DirectoryScheme`.

    Arguments:
        name: Appplication name.
        version: Application version.
    """
    def __init__(self, name: str, version: str | None=None, *, force_home: bool=False):
        super().__init__(name, version, force_home=force_home)
        app_dir = Path(self.name)
        if self.version is not None:
            app_dir /= self.version
        pd = Path('/Library/Application Support')
        lad = Path('~/Library/Application Support').expanduser()
        # Set general directories only when HOME is not forced by environment variable.
        if not self.has_home_env() and not force_home:
            self.dir_map.update({'config': pd / app_dir / 'config',
                                 'run_data': pd / app_dir / 'run',
                                 'logs': pd / app_dir / 'log',
                                 'data': pd / app_dir / 'data',
                                 'cache': pd / app_dir / 'cache',
                                 'srv': pd / app_dir / 'srv',
                                 })
        # Always set user-specific directories and TMP
        self.dir_map.update({'tmp': Path(os.getenv('TMPDIR')) / app_dir,
                             'user_config': lad / app_dir / 'config',
                             'user_data': lad / app_dir / 'data',
                             'user_sync': lad / app_dir,
                             'user_cache': Path('~/Library/Caches').expanduser() / app_dir / 'cache',
                             })

def get_directory_scheme(app_name: str, version: str | None=None, *, force_home: bool=False) -> DirectoryScheme:
    """Returns directory scheme for current platform.

    Arguments:
        app_name: Application name
        version: Application version string
        force_home: When True, the general directies are always set to subdirectories of
                    `DirectoryScheme.home` directory. When False, then home is used ONLY
                    when it's set by "<app_name>_HOME" environment variable.
    """
    return {'Windows': WindowsDirectoryScheme,
            'Linux':LinuxDirectoryScheme,
            'Darwin': MacOSDirectoryScheme}.get(platform.system(),
                                                DirectoryScheme)(app_name, version,
                                                                 force_home=force_home)

T = TypeVar("T")
E = TypeVar("E", bound=Enum)
F = TypeVar("F", bound=Flag)

class Option(Generic[T], ABC):
    """Generic abstract base class for configuration options.

    Arguments:
        name: Option name.
        datatype: Option datatype.
        description: Option description. Can span multiple lines.
        required: True if option must have a value.
        default: Default option value.
    """
    def __init__(self, name: str, datatype: type[T], description: str, *, required: bool=False,
                 default: T | None =None):
        assert name and isinstance(name, str), "name required" # noqa: S101
        assert datatype and isinstance(datatype, type), "datatype required" # noqa: S101
        assert description and isinstance(description, str), "description required" # noqa: S101
        assert default is None or isinstance(default, datatype), "default has wrong data type" # noqa: S101
        #: Option name.
        self.name: str = name
        #: Option datatype.
        self.datatype: type[T] = datatype
        #: Option description. Can span multiple lines.
        self.description: str = description
        #: True if option must have a value.
        self.required: bool = required
        #: Default option value.
        self.default: T = default
        if default is not None:
            self.set_value(default)
    def _check_value(self, value: T | None) -> None:
        if value is None and self.required:
            raise ValueError(f"Value is required for option '{self.name}'.")
        if value is not None and not isinstance(value, self.datatype):
            raise TypeError(f"Option '{self.name}' value must be a "
                            f"'{self.datatype.__name__}',"
                            f" not '{type(value).__name__}'")
    def _get_value_description(self) -> str:
        return f'{self.datatype.__name__}\n'
    def _get_config_lines(self, *, plain: bool=False) -> list[str]:
        """Returns list of strings containing text lines suitable for use in configuration
        file processed with `~configparser.ConfigParser`.

        Text lines with configuration start with comment marker `;` and end with newline.

        Arguments:
          plain: When True, it outputs only the option value. When False, it includes also
                 option description and other helpful information.

        Note:
           This function is intended for internal use. To get string describing current
           configuration that is suitable for configuration files, use `get_config` method.
        """
        lines = []
        if not plain:
            if self.required:
                lines.append("; REQUIRED option.\n")
            for line in self.description.strip().splitlines():
                lines.append(f"; {line}\n")
            first = True
            for line in self._get_value_description().splitlines():
                lines.append(f"; {'Type: ' if first else ''}{line}\n")
                first = False
        value = self.get_value()
        nodef = ';' if value == self.default else ''
        value = '<UNDEFINED>' if value is None else self.get_formatted()
        if '\n' in value:
            chunks = value.splitlines(keepends=True)
            new_value = [chunks[0]]
            new_value.extend(f'{nodef}{x}' for x in chunks[1:])
            value = ''.join(new_value)
        lines.append(f'{nodef}{self.name} = {value}\n')
        return lines
    def load_config(self, config: ConfigParser, section: str) -> None:
        """Update option value from `~configparser.ConfigParser` instance.

        Arguments:
            config:  ConfigParser instance.
            section: Name of ConfigParser section that should be used to get new option
               value.

        Raises:
            ValueError: When option value cannot be loadded.
            KeyError: If section does not exists, and it's not `configparser.DEFAULTSECT`.
        """
        if not config.has_section(section) and section != DEFAULTSECT:
            raise KeyError(f"Configuration error: section '{section}' not found!")
        if config.has_option(section, self.name):
            self.set_as_str(config[section][self.name])
    def validate(self) -> None:
        """Validates option state.

        Raises:
            Error: When required option does not have a value.
        """
        if self.required and self.get_value() is None:
            raise Error(f"Missing value for required option '{self.name}'")
    def get_config(self, *, plain: bool=False) -> str:
        """Returns string containing text lines suitable for use in configuration file
        processed with `~configparser.ConfigParser`.

        Arguments:
          plain: When True, it outputs only the option value. When False, it includes also
                 option description and other helpful information.
        """
        return ''.join(self._get_config_lines(plain=plain))
    def has_value(self) -> bool:
        """Returns True if option value is not None.
        """
        return self.get_value() is not None
    @abstractmethod
    def clear(self, *, to_default: bool=True) -> None:
        """Clears the option value.

        Arguments:
            to_default: If True, sets the option value to default value, else to None.
        """
    @abstractmethod
    def get_formatted(self) -> str:
        """Returns value formatted for use in config file.
        """
    @abstractmethod
    def set_as_str(self, value: str) -> None:
        """Set new option value from string.

        Arguments:
            value: New option value.

        Raises:
            ValueError: When the argument is not a valid option value.
        """
    @abstractmethod
    def get_as_str(self) -> str:
        """Returns value as string.
        """
    @abstractmethod
    def get_value(self) -> T | None:
        """Returns current option value.
        """
    @abstractmethod
    def set_value(self, value: T | None) -> None:
        """Set new option value.

        Arguments:
            value: New option value.

        Raises:
            TypeError: When the new value is not of the expected `datatype`.
            ValueError: When the `value` content is invalid for the specific option type
                        (e.g., disallowed enum member, negative for unsigned int).
        """
    @abstractmethod
    def load_proto(self, proto: ConfigProto) -> None:
        """Deserialize value from `.ConfigProto` message.

        Arguments:
            proto: Protobuf message that may contain this option's value under `proto.options[self.name]`.

        Raises:
            TypeError: If the protobuf field type is incompatible with the option.
            ValueError: If the deserialized value content is invalid for the option.
        """
    @abstractmethod
    def save_proto(self, proto: ConfigProto) -> None:
        """Serialize the current value into `.ConfigProto` message.

        The value is stored in `proto.options[self.name]` using an appropriate
        protobuf field type (e.g., `as_string`, `as_sint64`). If the current
        value is `None`, nothing is saved for this option.

        Arguments:
            proto: Protobuf message where the option value should be stored.
        """

class Config:
    """Collection of configuration options, potentially nested.

    Arguments:
        name: Name associated with Config (default section name).
        optional: Whether config is optional (True) or mandatory (False) for
                  configuration file (see `.load_config()` for details).
        description: Optional configuration description. Can span multiple lines.

    Important:
        Descendants must define individual options and sub configs as instance attributes.

        Attributes defined as instances of `Option` subclasses represent individual
        configuration settings. Attributes defined as instances of `Config` subclasses
        represent nested configuration sections with fixed names. Attributes defined as
        `ConfigOption` or `ConfigListOption` allow for referring to nested sections
        whose names (section headers) are themselves configurable.
    """
    def __init__(self, name: str, *, optional: bool=False, description: str | None=None):
        self._name: str = name
        self._optional: bool = optional
        self._description: str | None = description if description is not None else self.__doc__
    def __setattr__(self, name, value) -> None:
        for attr in vars(self).values():
            if isinstance(attr, Option) and attr.name == name:
                raise ValueError("Cannot assign values to option itself, use 'option.value' instead")
        super().__setattr__(name, value)
    def validate(self) -> None:
        """Recursively validates all directly owned options and sub-configs.

        Checks whether:
            - all required options have a non-`None` value.
            - required `ConfigOption` values have a non-empty section name.
            - required `ConfigListOption` values have a non-empty list.
            - all options are defined as instance attributes with the same name as `option.name`.
            - calls `validate()` on all nested `Config` instances (direct attributes,
              values of `ConfigOption`, and items in `ConfigListOption`).

        Raises:
            Error: When any validation constraint is violated.
        """
        for option in self.options:
            option.validate()
            if not hasattr(self, option.name):
                raise Error(f"Option '{option.name}' is not defined as attribute with the same name")
    def clear(self, *, to_default: bool=True) -> None:
        """Clears all owned options and options in owned sub-configs.

        Arguments:
            to_default: If True, sets the option values to defaults, else to None.
        """
        for option in self.options:
            option.clear(to_default=to_default)
        for config in self.configs:
            config.clear(to_default=to_default)
    def get_description(self) -> str:
        """Configuration description. Can span multiple lines.

        Note:  If description is not provided on instance creation, class doc string.
        """
        return '' if self._description is None else self._description
    def get_config(self, *, plain: bool=False) -> str:
        """Returns string containing text lines suitable for use in configuration file
        processed with `~configparser.ConfigParser`.

        Important:
            When config is optional and the name is an empty string, it returns empty string.

        Arguments:
          plain: When True, it outputs only the option values. When False, it includes also
                 option descriptions and other helpful information.
        """
        if self.optional and not self.name:
            return ''
        lines = [f"[{self.name}]\n"]
        if not plain:
            lines.append(';\n')
            for line in self.get_description().strip().splitlines():
                lines.append(f"; {line}\n")
        for option in self.options:
            if not plain:
                lines.append('\n')
            lines.append(option.get_config(plain=plain))
        for config in self.configs:
            if subcfg := config.get_config(plain=plain):
                if not plain:
                    lines.append('\n')
                lines.append(subcfg)
        return ''.join(lines)
    def load_config(self, config: ConfigParser, section: str | None=None) -> None:
        """Update configuration values from a `ConfigParser` instance.

        Arguments:
            config:  `ConfigParser` instance containing configuration values.
            section: Name of the `ConfigParser` section corresponding to this `Config`
                     instance. If `None`, uses `self.name`.

        Behavior:
            - Reads values for directly owned `Option` instances from the specified `section`.
            - Recursively calls `load_config` on directly owned `Config` instances using
              their respective `name` attribute as the section name.
            - Recursively calls `load_config` on `Config` instances referenced by owned
              `ConfigOption` and `ConfigListOption` values, using the section names
              stored within those options.

        Raises:
            Error: If `section` does not exist in `config` and `self.optional` is `False`
                   (unless `section` is `DEFAULTSECT`). Also wraps underlying `ValueError`
                   or `KeyError` from option parsing.
            KeyError: Propagated if an invalid section name is used for a nested config.
            ValueError: Propagated if an option string cannot be parsed correctly.
        """
        if section is None:
            section = self.name
        if not config.has_section(section):
            if self._optional:
                return
            if section != DEFAULTSECT:
                raise Error(f"Configuration error: section '{section}' not found!")
        try:
            for option in self.options:
                option.load_config(config, section)
            for subcfg in self.configs:
                subcfg.load_config(config)
        except Error:
            raise
        except Exception as exc: # pragma: no cover
            raise Error(f"Configuration error: {exc}") from exc
    def load_proto(self, proto: ConfigProto) -> None:
        """Deserialize value from `.ConfigProto` message.

        Arguments:
            proto: Protobuf message that may contains option values and sub-configs.
        """
        for option in self.options:
            option.load_proto(proto)
        for subcfg in self.configs:
            if subcfg.name in proto.configs:
                subcfg.load_proto(proto.configs[subcfg.name])
    def save_proto(self, proto: ConfigProto) -> None:
        """Serialize value into `.ConfigProto` message.

        Arguments:
            proto: Protobuf message where option values and sub-configs should be stored.
        """
        for option in self.options:
            option.save_proto(proto)
        for subcfg in self.configs:
            subcfg.save_proto(proto.configs.get_or_create(subcfg.name))
    @property
    def name(self) -> str:
        """Name associated with Config (default section name).
        """
        return self._name
    @property
    def optional(self) -> bool:
        """Whether config is optional (False) or mandatory (True) for configuration file
        (see `.load_config()` for details).
        """
        return self._optional
    @property
    def options(self) -> list[Option]:
        """List of `Option` instances directly defined as attributes of this `Config` instance."""
        return [v for v in vars(self).values() if isinstance(v, Option)]
    @property
    def configs(self) -> list[Config]:
        """List of nested `Config` instances associated with this instance.

        Includes:

        - `Config` instances directly assigned as attributes.
        - The `Config` instance held by any `ConfigOption` attribute.
        - All `Config` instances within the list held by any `ConfigListOption` attribute.
        """
        result = [v if isinstance(v, Config) else v.value
                  for v in vars(self).values() if isinstance(v, Config | ConfigOption)]
        for opt in (v for v in vars(self).values() if isinstance(v, ConfigListOption)):
            result.extend(opt.value)
        return result

# Options
class StrOption(Option[str]):
    """Configuration option with string value.

    .. versionadded:: 1.6.1
       Support for verticals to preserve leading whitespace.

    Arguments:
        name: Option name.
        description: Option description. Can span multiple lines.
        required: True if option must have a value.
        default: Default option value.

    Important:
        Multiline string values could contain significant leading whitespace, but
        ConfigParser multiline string values have leading whitespace removed. To circumvent
        this, the `StrOption` supports assignment of text values where lines start with `|`
        character. This character is removed, along with any number of subsequent whitespace
        characters that are between `|` and first non-whitespace character on first line
        starting with `|`.
    """
    def __init__(self, name: str, description: str, *, required: bool=False, default: str | None=None):
        self._value: str | None = None
        super().__init__(name, str, description, required=required, default=default)
    def clear(self, *, to_default: bool=True) -> None:
        """Clears the option value.

        Arguments:
            to_default: If True, sets the option value to default value, else to None.
        """
        self._value = self.default if to_default else None
    def get_formatted(self) -> str:
        """Returns value formatted for use in config file.
        """
        if self._value is None:
            return '<UNDEFINED>'
        result = self._value
        if '\n' in result:
            lines = []
            indent = '   | ' if has_leading_spaces(result) else '   '
            for line in result.splitlines(True):
                if lines:
                    lines.append(indent + line)
                else:
                    lines.append(line)
            result = ''.join(lines)
        return result
    def set_as_str(self, value: str) -> None:
        """Set new option value from string.

        Arguments:
            value: New option value.

        Raises:
            ValueError: When the argument is not a valid option value.
        """
        value = unindent_verticals(value)
        self._value = value
    def get_as_str(self) -> str:
        """Returns value as string.
        """
        return self._value
    def get_value(self) -> str | None:
        """Returns current option value.
        """
        return self._value
    def set_value(self, value: str | None) -> None:
        """Set new option value.

        Arguments:
            value: New option value.

        Raises:
            TypeError: When the new value is of the wrong type.
            ValueError: When the argument is not a valid option value.
        """
        self._check_value(value)
        self._value = value
    def load_proto(self, proto: ConfigProto) -> None:
        """Deserialize value from `.ConfigProto` message.

        Arguments:
            proto: Protobuf message that may contains options value.

        Raises:
            TypeError: When the new value is of the wrong type.
            ValueError: When the argument is not a valid option value.
        """
        if self.name in proto.options:
            opt = proto.options[self.name]
            if opt.HasField('as_string'):
                self.set_value(opt.as_string)
            else:
                raise TypeError(f"Wrong value type: {opt.WhichOneof('kind')[3:]}")
    def save_proto(self, proto: ConfigProto) -> None:
        """Serialize value into `.ConfigProto` message.

        Arguments:
            proto: Protobuf message where option value should be stored.
        """
        if self._value is not None:
            proto.options[self.name].as_string = self._value
    value: str | None = property(get_value, set_value, doc="Current option value")

class IntOption(Option[int]):
    """Configuration option with integer value.

    Arguments:
        name: Option name.
        description: Option description. Can span multiple lines.
        required: True if option must have a value.
        default: Default option value.
        signed: When False, the option value cannot be negative.
    """
    def __init__(self, name: str, description: str, *, required: bool=False,
                 default: int | None=None, signed: bool=False):
        self._value: int | None = None
        self.__signed: bool = signed
        super().__init__(name, int, description, required=required, default=default)
    def clear(self, *, to_default: bool=True) -> None:
        """Clears the option value.

        Arguments:
            to_default: If True, sets the option value to default value, else to None.
        """
        self._value = self.default if to_default else None
    def get_formatted(self) -> str:
        """Returns value formatted for use in config file.
        """
        return '<UNDEFINED>' if self._value is None else str(self._value)
    def set_as_str(self, value: str) -> None:
        """Set new option value from string.

        Arguments:
            value: New option value.

        Raises:
            ValueError: When the argument is not a valid option value.
        """
        new = int(value)
        if not self.__signed and new < 0:
            raise ValueError("Negative numbers not allowed")
        self._value = new
    def get_as_str(self) -> str:
        """Returns value as string.
        """
        return str(self._value)
    def get_value(self) -> int | None:
        """Returns current option value.
        """
        return self._value
    def set_value(self, value: int | None) -> None:
        """Set new option value.

        Arguments:
            value: New option value.

        Raises:
            TypeError: When the new value is of the wrong type.
            ValueError: When the argument is not a valid option value.
        """
        self._check_value(value)
        if value is not None and (not self.__signed and value < 0):
            raise ValueError("Negative numbers not allowed")
        self._value = value
    def load_proto(self, proto: ConfigProto) -> None:
        """Deserialize value from `.ConfigProto` message.

        Arguments:
            proto: Protobuf message that may contains options value.

        Raises:
            TypeError: When the new value is of the wrong type.
            ValueError: When the argument is not a valid option value.
        """
        if self.name in proto.options:
            opt = proto.options[self.name]
            oneof = opt.WhichOneof('kind')
            if oneof not in ['as_sint32', 'as_sint64', 'as_uint32', 'as_uint64', 'as_string']:
                raise TypeError(f"Wrong value type: {oneof[3:]}")
            if oneof == 'as_string':
                self.set_as_str(opt.as_string)
            else:
                self.set_value(getattr(opt, oneof))
    def save_proto(self, proto: ConfigProto) -> None:
        """Serialize value into `.ConfigProto` message.

        Arguments:
            proto: Protobuf message where option value should be stored.
        """
        if self._value is not None:
            opt = proto.options[self.name]
            if self.__signed:
                opt.as_sint64 = self._value
            else:
                opt.as_uint64 = self._value
    value: int | None = property(get_value, set_value, doc="Current option value")

class FloatOption(Option[float]):
    """Configuration option with float value.

    Arguments:
        name: Option name.
        description: Option description. Can span multiple lines.
        required: True if option must have a value.
        default: Default option value.
    """
    def __init__(self, name: str, description: str, *, required: bool=False,
                 default: float | None=None):
        self._value: float | None = None
        super().__init__(name, float, description, required=required, default=default)
    def clear(self, *, to_default: bool=True) -> None:
        """Clears the option value.

        Arguments:
            to_default: If True, sets the option value to default value, else to None.
        """
        self._value = self.default if to_default else None
    def get_formatted(self) -> str:
        """Returns value formatted for use in config file.
        """
        return '<UNDEFINED>' if self._value is None else str(self._value)
    def set_as_str(self, value: str) -> None:
        """Set new option value from string.

        Arguments:
            value: New option value.

        Raises:
            ValueError: When the argument is not a valid option value.
        """
        self._value = float(value)
    def get_as_str(self) -> str:
        """Returns value as string.
        """
        return str(self._value)
    def get_value(self) -> float | None:
        """Returns current option value.
        """
        return self._value
    def set_value(self, value: float | None) -> None:
        """Set new option value.

        Arguments:
            value: New option value.

        Raises:
            TypeError: When the new value is of the wrong type.
            ValueError: When the argument is not a valid option value.
        """
        self._check_value(value)
        self._value = value
    def load_proto(self, proto: ConfigProto) -> None:
        """Deserialize value from `.ConfigProto` message.

        Arguments:
            proto: Protobuf message that may contains options value.

        Raises:
            TypeError: When the new value is of the wrong type.
            ValueError: When the argument is not a valid option value.
        """
        if self.name in proto.options:
            opt = proto.options[self.name]
            oneof = opt.WhichOneof('kind')
            if oneof not in ['as_float', 'as_double', 'as_string']:
                raise TypeError(f"Wrong value type: {oneof[3:]}")
            if oneof == 'as_string':
                self.set_as_str(opt.as_string)
            else:
                self.set_value(getattr(opt, oneof))
    def save_proto(self, proto: ConfigProto) -> None:
        """Serialize value into `.ConfigProto` message.

        Arguments:
            proto: Protobuf message where option value should be stored.
        """
        if self._value is not None:
            proto.options[self.name].as_double = self._value
    value: float | None = property(get_value, set_value, doc="Current option value")

class DecimalOption(Option[Decimal]):
    """Configuration option with decimal.Decimal value.

    Arguments:
        name: Option name.
        description: Option description. Can span multiple lines.
        required: True if option must have a value.
        default: Default option value.
    """
    def __init__(self, name: str, description: str, *, required: bool=False,
                 default: Decimal | None=None):
        self._value: Decimal | None = None
        super().__init__(name, Decimal, description, required=required, default=default)
    def clear(self, *, to_default: bool=True) -> None:
        """Clears the option value.

        Arguments:
            to_default: If True, sets the option value to default value, else to None.
        """
        self._value = self.default if to_default else None
    def get_formatted(self) -> str:
        """Returns value formatted for use in config file.
        """
        return '<UNDEFINED>' if self._value is None else str(self._value)
    def set_as_str(self, value: str) -> None:
        """Set new option value from string.

        Arguments:
            value: New option value.

        Raises:
            ValueError: When the argument is not a valid option value.
        """
        try:
            self._value = Decimal(value)
        except DecimalException as exc:
            raise ValueError("Cannot convert string to Decimal") from exc
    def get_as_str(self) -> str:
        """Returns value as string.
        """
        return str(self._value)
    def get_value(self) -> Decimal | None:
        """Returns current option value.
        """
        return self._value
    def set_value(self, value: Decimal | None) -> None:
        """Set new option value.

        Arguments:
            value: New option value.

        Raises:
            TypeError: When the new value is of the wrong type.
            ValueError: When the argument is not a valid option value.
        """
        self._check_value(value)
        self._value = value
    def load_proto(self, proto: ConfigProto):
        """Deserialize value from `.ConfigProto` message.

        Arguments:
            proto: Protobuf message that may contains options value.

        Raises:
            TypeError: When the new value is of the wrong type.
            ValueError: When the argument is not a valid option value.
        """
        if self.name in proto.options:
            opt = proto.options[self.name]
            oneof = opt.WhichOneof('kind')
            if oneof not in ['as_sint32', 'as_sint64', 'as_uint32', 'as_uint64', 'as_string']:
                raise TypeError(f"Wrong value type: {oneof[3:]}")
            if oneof == 'as_string':
                self.set_as_str(opt.as_string)
            else:
                self.set_value(Decimal(getattr(opt, oneof)))
    def save_proto(self, proto: ConfigProto):
        """Serialize value into `.ConfigProto` message.

        Arguments:
            proto: Protobuf message where option value should be stored.
        """
        if self._value is not None:
            proto.options[self.name].as_string = str(self._value)
    value: Decimal | None = property(get_value, set_value, doc="Current option value")

class BoolOption(Option[bool]):
    """Configuration option with boolean value.

    Arguments:
        name: Option name.
        description: Option description. Can span multiple lines.
        required: True if option must have a value.
        default: Default option value.
    """
    def __init__(self, name: str, description: str, *, required: bool=False,
                 default: bool | None=None):
        self._value: bool | None = None
        self.from_str = get_convertor(bool).from_str
        super().__init__(name, bool, description, required=required, default=default)
    def clear(self, *, to_default: bool=True) -> None:
        """Clears the option value.

        Arguments:
            to_default: If True, sets the option value to default value, else to None.
        """
        self._value = self.default if to_default else None
    def get_formatted(self) -> str:
        """Returns value formatted for use in config file.
        """
        if self._value is None:
            return '<UNDEFINED>'
        return 'yes' if self._value else 'no'
    def set_as_str(self, value: str) -> None:
        """Set new option value from string.

        Arguments:
            value: New option value.

        Raises:
            ValueError: When the argument is not a valid option value.
        """
        self._value = self.from_str(bool, value)
    def get_as_str(self) -> str:
        """Returns value as string.
        """
        return str(self._value)
    def get_value(self) -> bool | None:
        """Returns current option value.
        """
        return self._value
    def set_value(self, value: bool | None) -> None:
        """Set new option value.

        Arguments:
            value: New option value.

        Raises:
            TypeError: When the new value is of the wrong type.
            ValueError: When the argument is not a valid option value.
        """
        self._check_value(value)
        self._value = value
    def load_proto(self, proto: ConfigProto) -> None:
        """Deserialize value from `.ConfigProto` message.

        Arguments:
            proto: Protobuf message that may contains options value.

        Raises:
            TypeError: When the new value is of the wrong type.
            ValueError: When the argument is not a valid option value.
        """
        if self.name in proto.options:
            opt = proto.options[self.name]
            oneof = opt.WhichOneof('kind')
            if oneof not in ['as_bool', 'as_string']:
                raise TypeError(f"Wrong value type: {oneof[3:]}")
            if oneof == 'as_string':
                self.set_as_str(opt.as_string)
            else:
                self.set_value(opt.as_bool)
    def save_proto(self, proto: ConfigProto) -> None:
        """Serialize value into `.ConfigProto` message.

        Arguments:
            proto: Protobuf message where option value should be stored.
        """
        if self._value is not None:
            proto.options[self.name].as_bool = self._value
    value: bool | None = property(get_value, set_value, doc="Current option value")

class ZMQAddressOption(Option[ZMQAddress]):
    """Configuration option with `.ZMQAddress` value.

    Arguments:
        name: Option name.
        description: Option description. Can span multiple lines.
        required: True if option must have a value.
        default: Default option value.
    """
    def __init__(self, name: str, description: str, *, required: bool=False,
                 default: ZMQAddress=None):
        self._value: ZMQAddress | None = None
        super().__init__(name, ZMQAddress, description, required=required, default=default)
    def clear(self, *, to_default: bool=True) -> None:
        """Clears the option value.

        Arguments:
            to_default: If True, sets the option value to default value, else to None.
        """
        self._value = self.default if to_default else None
    def get_formatted(self) -> str:
        """Returns value formatted for use in config file.
        """
        return '<UNDEFINED>' if self._value is None else self._value
    def set_as_str(self, value: str) -> None:
        """Set new option value from string.

        Arguments:
            value: New option value.

        Raises:
            ValueError: When the argument is not a valid option value.
        """
        self._value = ZMQAddress(value)
    def get_as_str(self) -> str:
        """Returns value as string.
        """
        return self._value
    def get_value(self) -> ZMQAddress | None:
        """Returns current option value.
        """
        return self._value
    def set_value(self, value: ZMQAddress | None) -> None:
        """Set new option value.

        Arguments:
            value: New option value.

        Raises:
            TypeError: When the new value is of the wrong type.
            ValueError: When the argument is not a valid option value.
        """
        self._check_value(value)
        self._value = value
    def load_proto(self, proto: ConfigProto) -> None:
        """Deserialize value from `.ConfigProto` message.

        Arguments:
            proto: Protobuf message that may contains options value.

        Raises:
            TypeError: When the new value is of the wrong type.
            ValueError: When the argument is not a valid option value.
        """
        if self.name in proto.options:
            opt = proto.options[self.name]
            if opt.HasField('as_string'):
                self.set_as_str(opt.as_string)
            else:
                raise TypeError(f"Wrong value type: {opt.WhichOneof('kind')[3:]}")
    def save_proto(self, proto: ConfigProto) -> None:
        """Serialize value into `.ConfigProto` message.

        Arguments:
            proto: Protobuf message where option value should be stored.
        """
        if self._value is not None:
            proto.options[self.name].as_string = self._value
    value: ZMQAddress | None = property(get_value, set_value, doc="Current option value")

class EnumOption(Option[E], Generic[E]):
    """Configuration option with enum value.

    Arguments:
        name: Option name.
        description: Option description. Can span multiple lines.
        required: True if option must have a value.
        default: Default option value.
        allowed: List of allowed Enum members. When not defined, all members of enum type are
                 allowed.
    """
    def __init__(self, name: str, enum_class: type[E], description: str, *, required: bool=False,
                 default: E | None=None, allowed: list | None=None):
        self._value: E | None = None
        #: List of allowed enum values.
        self.allowed: Sequence[E] = enum_class if allowed is None else allowed
        self._members: dict = {i.name.lower(): i for i in self.allowed}
        super().__init__(name, enum_class, description, required=required, default=default)
    def _get_value_description(self) -> str:
        return f"enum [{', '.join(x.name.lower() for x in self.allowed)}]\n"
    def clear(self, *, to_default: bool=True) -> None:
        """Clears the option value.

        Arguments:
            to_default: If True, sets the option value to default value, else to None.
        """
        self._value = self.default if to_default else None
    def get_formatted(self) -> str:
        """Returns value formatted for use in config file.
        """
        return '<UNDEFINED>' if self._value is None else self._value.name.lower()
    def set_as_str(self, value: str) -> None:
        """Set new option value from string.

        Arguments:
            value: New option value.

        Raises:
            ValueError: When the argument is not a valid option value.
        """
        name = value.lower()
        if name in self._members:
            self.set_value(self._members[name])
        else:
            raise ValueError(f"Illegal value '{value}' for enum type "
                             f"'{self.datatype.__name__}'")
    def get_as_str(self) -> str:
        """Returns value as string.
        """
        return self._value.name
    def get_value(self) -> E | None:
        """Returns current option value.
        """
        return self._value
    def set_value(self, value: E | None) -> None:
        """Set new option value.

        Arguments:
            value: New option value.

        Raises:
            TypeError: When the new value is of the wrong type.
            ValueError: When the argument is not a valid option value.
        """
        self._check_value(value)
        if value is not None and value not in self.allowed:
            raise ValueError(f"Value '{value!r}' not allowed")
        self._value = value
    def load_proto(self, proto: ConfigProto) -> None:
        """Deserialize value from `.ConfigProto` message.

        Arguments:
            proto: Protobuf message that may contains option value.

        Raises:
            TypeError: When the new value is of the wrong type.
            ValueError: When the argument is not a valid option value.
        """
        if self.name in proto.options:
            opt = proto.options[self.name]
            if opt.HasField('as_string'):
                self.set_as_str(opt.as_string)
            else:
                raise TypeError(f"Wrong value type: {opt.WhichOneof('kind')[3:]}")
    def save_proto(self, proto: ConfigProto) -> None:
        """Serialize value into `.ConfigProto` message.

        Arguments:
            proto: Protobuf message where option value should be stored.
        """
        if self._value is not None:
            proto.options[self.name].as_string = self._value.name
    value: E | None = property(get_value, set_value, doc="Current option value")

class FlagOption(Option[F], Generic[F]):
    """Configuration option with flag value.

    Arguments:
        name: Option name.
        description: Option description. Can span multiple lines.
        required: True if option must have a value.
        default: Default option value.
        allowed: List of allowed Flag members. When not defined, all members of flag type are
                 allowed.
    """
    def __init__(self, name: str, flag_class: type[F], description: str, *, required: bool=False,
                 default: F | None=None, allowed: list | None=None):
        self._value: F | None = None
        #: List of allowed flag values.
        self.allowed: Sequence[F] = flag_class if allowed is None else allowed
        self._members: dict = {i.name.lower(): i for i in self.allowed}
        super().__init__(name, flag_class, description, required=required, default=default)
    def _get_value_description(self) -> str:
        return f"flag [{', '.join(x.name.lower() for x in self.allowed)}]\n"
    def clear(self, *, to_default: bool=True) -> None:
        """Clears the option value.

        Arguments:
            to_default: If True, sets the option value to default value, else to None.
        """
        self._value = self.default if to_default else None
    def get_formatted(self) -> str:
        """Returns value formatted for use in config file.
        """
        return '<UNDEFINED>' if self._value is None else self.get_as_str().lower()
    def set_as_str(self, value: str) -> None:
        """Set new option value from string.

        Arguments:
            value: New option value.

        Raises:
            ValueError: When the argument is not a valid option value.
        """
        result = self.datatype(0)
        for name in (x.strip().lower() for x in value.split('|' if '|' in value else ',')):
            if name in self._members:
                result |= self._members[name]
            else:
                raise ValueError(f"Illegal value '{name}' for flag option '{self.name}'")
        self.set_value(result)
    def get_as_str(self) -> str:
        """Returns value as string.
        """
        if self._value._name_ is not None:
            return self._value.name
        members, uncovered = _decompose(self.datatype, self._value)
        if len(members) == 1 and members[0]._name_ is None:
            return f'{members[0]._value_}'
        return ' | '.join([str(m._name_ or m._value_) for m in members])
    def get_value(self) -> F | None:
        """Returns current option value.
        """
        return self._value
    def set_value(self, value: F | None) -> None:
        """Set new option value.

        Arguments:
            value: New option value.

        Raises:
            TypeError: When the new value is of the wrong type.
            ValueError: When the argument is not a valid option value.
        """
        self._check_value(value)
        if value is not None:
            members, uncovered = _decompose(self.datatype, value.value)
            if uncovered or [i for i in members if i.name is None or i.name.lower() not in self._members]:
                raise ValueError(f"Illegal value '{value!s}' for flag option '{self.name}'")
        self._value = value
    def load_proto(self, proto: ConfigProto) -> None:
        """Deserialize value from `.ConfigProto` message.

        Arguments:
            proto: Protobuf message that may contains option value.

        Raises:
            TypeError: When the new value is of the wrong type.
            ValueError: When the argument is not a valid option value.
        """
        if self.name in proto.options:
            opt = proto.options[self.name]
            oneof = opt.WhichOneof('kind')
            if oneof not in ['as_uint64', 'as_string']:
                raise TypeError(f"Wrong value type: {oneof[3:]}")
            if oneof == 'as_uint64':
                self.set_value(self.datatype(opt.as_uint64))
            else:
                self.set_as_str(opt.as_string)
    def save_proto(self, proto: ConfigProto) -> None:
        """Serialize value into `.ConfigProto` message.

        Arguments:
            proto: Protobuf message where option value should be stored.
        """
        if self._value is not None:
            proto.options[self.name].as_uint64 = self._value.value
    value: F | None = property(get_value, set_value, doc="Current option value")

class UUIDOption(Option[UUID]):
    """Configuration option with UUID value.

    Arguments:
        name: Option name.
        description: Option description. Can span multiple lines.
        required: True if option must have a value.
        default: Default option value.
    """
    def __init__(self, name: str, description: str, *, required: bool=False,
                 default: UUID | None=None):
        self._value: UUID | None = None
        super().__init__(name, UUID, description, required=required, default=default)
    def clear(self, *, to_default: bool=True) -> None:
        """Clears the option value.

        Arguments:
            to_default: If True, sets the option value to default value, else to None.
        """
        self._value = self.default if to_default else None
    def get_formatted(self) -> str:
        """Returns value formatted for use in config file.
        """
        return '<UNDEFINED>' if self._value is None else str(self._value)
    def set_as_str(self, value: str) -> None:
        """Set new option value from string.

        Arguments:
            value: New option value.

        Raises:
            ValueError: When the argument is not a valid option value.
        """
        self._value = UUID(value)
    def get_as_str(self) -> str:
        """Returns value as string.
        """
        return 'None' if self._value is None else self._value.hex
    def get_value(self) -> UUID | None:
        """Returns current option value.
        """
        return self._value
    def set_value(self, value: UUID | None) -> None:
        """Set new option value.

        Arguments:
            value: New option value.

        Raises:
            TypeError: When the new value is of the wrong type.
            ValueError: When the argument is not a valid option value.
        """
        self._check_value(value)
        self._value = value
    def load_proto(self, proto: ConfigProto) -> None:
        """Deserialize value from `.ConfigProto` message.

        Arguments:
            proto: Protobuf message that may contains options value.
        """
        if self.name in proto.options:
            opt = proto.options[self.name]
            oneof = opt.WhichOneof('kind')
            if oneof not in ['as_bytes', 'as_string']:
                raise TypeError(f"Wrong value type: {oneof[3:]}")
            if oneof == 'as_bytes':
                self.set_value(UUID(bytes=opt.as_bytes))
            else:
                self.set_value(UUID(opt.as_string))
    def save_proto(self, proto: ConfigProto) -> None:
        """Serialize value into `.ConfigProto` message.

        Arguments:
            proto: Protobuf message where option value should be stored.
        """
        if self._value is not None:
            proto.options[self.name].as_bytes = self._value.bytes
    value: UUID | None = property(get_value, set_value, doc="Current option value")

class MIMEOption(Option[MIME]):
    """Configuration option with MIME type specification value.

    Arguments:
        name: Option name.
        description: Option description. Can span multiple lines.
        required: True if option must have a value.
        default: Default option value.
    """
    def __init__(self, name: str, description: str, *, required: bool=False, default: MIME=None):
        self._value: MIME | None = None
        super().__init__(name, MIME, description, required=required, default=default)
    def clear(self, *, to_default: bool=True) -> None:
        """Clears the option value.

        Arguments:
            to_default: If True, sets the option value to default value, else to None.
        """
        self._value = self.default if to_default else None
    def get_formatted(self) -> str:
        """Returns value formatted for use in config file.
        """
        return '<UNDEFINED>' if self._value is None else self._value
    def set_as_str(self, value: str) -> None:
        """Set new option value from string.

        Arguments:
            value: New option value.

        Raises:
            ValueError: When the argument is not a valid option value.
        """
        self._value = MIME(value)
    def get_as_str(self) -> str:
        """Returns value as string.
        """
        return 'None' if self._value is None else self._value
    def get_value(self) -> MIME | None:
        """Returns current option value.
        """
        return self._value
    def set_value(self, value: MIME | None) -> None:
        """Set new option value.

        Arguments:
            value: New option value.

        Raises:
            TypeError: When the new value is of the wrong type.
            ValueError: When the argument is not a valid option value.
        """
        self._check_value(value)
        self._value = value
    def load_proto(self, proto: ConfigProto) -> None:
        """Deserialize value from `.ConfigProto` message.

        Arguments:
            proto: Protobuf message that may contains options value.
        """
        if self.name in proto.options:
            opt = proto.options[self.name]
            if opt.HasField('as_string'):
                self.set_as_str(opt.as_string)
            else:
                raise TypeError(f"Wrong value type: {opt.WhichOneof('kind')[3:]}")
    def save_proto(self, proto: ConfigProto) -> None:
        """Serialize value into `.ConfigProto` message.

        Arguments:
            proto: Protobuf message where option value should be stored.
        """
        if self._value is not None:
            proto.options[self.name].as_string = self._value
    value: MIME | None = property(get_value, set_value, doc="Current option value")

class ListOption(Option[list]):
    """Configuration option with list of values.

    Arguments:
        name:        Option name.
        item_type:   Datatype of list items. It could be a type or sequence of types.
                     If multiple types are provided, each value in config file must
                     have format: `type_name:value_as_str`.
        description: Option description. Can span multiple lines.
        required:    True if option must have a value.
        default:     Default option value.
        separator:   String that separates list item values when options value is read
                     from `ConfigParser`. It's possible to use a line break as separator.
                     If separator is `None` [default] and the value contains line breaks,
                     it uses the line break as separator, otherwise it uses comma as
                     separator.

    Important:
        When option is read from `ConfigParser`, empty values are ignored.
    """
    def __init__(self, name: str, item_type: type | Sequence[type], description: str,
                 *, required: bool=False, default: list | None=None, separator: str | None=None):
        self._value: list | None = None
        #: Datatypes of list items. If there is more than one type, each value in
        #: config file must have format: `type_name:value_as_str`.
        self.item_types: Sequence[type] = item_type if isinstance(item_type, Sequence) else (item_type, )
        #: String that separates list item values when options value is read from
        #: `ConfigParser`. Default separator is None. It's possible to use a line break as
        #: separator. If separator is `None` and the value contains line breaks, it uses
        #: the line break as separator, otherwise it uses comma as separator.
        self.separator: str | None = separator
        self._convertor: Convertor = get_convertor(item_type) if not isinstance(item_type, Sequence) else None
        super().__init__(name, list, description, required=required, default=default)
        # Value fixup, store copy of default list instead direct assignment
        if default is not None:
            self.set_value(list(default))
    def _get_value_description(self) -> str:
        return f"list [{', '.join(x.__name__ for x in self.item_types)}]\n"
    def _check_value(self, value: list) -> None:
        super()._check_value(value)
        if value is not None:
            i = 0
            for item in value:
                if item.__class__ not in self.item_types:
                    raise ValueError(f"List item[{i}] has wrong type")
                i += 1
    def _get_as_typed_str(self, value: Any) -> str:
        result = convert_to_str(value)
        if len(self.item_types) > 1:
            result = f'{value.__class__.__name__}:{result}'
        return result
    def clear(self, *, to_default: bool=True) -> None:
        """Clears the option value.

        Arguments:
            to_default: If True, sets the option value to default value, else to None.
        """
        self._value = list(self.default) if to_default and self.default is not None else None
    def get_formatted(self) -> str:
        """Returns value formatted for use in config file.
        """
        if self._value is None:
            return '<UNDEFINED>'
        result = [self._get_as_typed_str(i) for i in self._value]
        sep = self.separator
        if sep is None:
            sep = '\n' if sum(len(i) for i in result) > 80 else ',' # noqa: PLR2004
        if sep == '\n':
            x = '\n   '
            return f'\n   {x.join(result)}'
        return f'{sep} '.join(result)
    def set_as_str(self, value: str) -> None:
        """Set new option value from string.

        Arguments:
            value: New option value.

        Raises:
            ValueError: When the argument is not a valid option value.
        """
        new = []
        if value.strip():
            separator = ('\n' if '\n' in value else ',') if self.separator is None else self.separator
            itype = self.item_types[0]
            convertor = self._convertor
            name_map = {}
            if len(self.item_types) > 1:
                name_map = {cls.__name__: cls for cls in self.item_types}
                fullname_map = {f'{cls.__module__}.{cls.__name__}': cls for cls in self.item_types}
            for item in (i for i in value.split(separator) if i.strip()):
                if name_map:
                    itype_name, item = item.split(':', 1) # noqa: PLW2901
                    itype_name = itype_name.strip()
                    itype = fullname_map.get(itype_name) if '.' in itype_name else name_map.get(itype_name)
                    if itype is None:
                        raise ValueError(f"Item type '{itype_name}' not supported")
                    convertor = get_convertor(itype)
                new.append(convertor.from_str(itype, item.strip()))
            self._value = new
    def get_as_str(self) -> str:
        """Returns value as string.
        """
        result = [self._get_as_typed_str(i) for i in self._value]
        sep = self.separator
        if sep is None:
            sep = '\n' if sum(len(i) for i in result) > 80 else ',' # noqa: PLR2004
        return sep.join(result)
    def get_value(self) -> list | None:
        """Returns current option value.
        """
        return self._value
    def set_value(self, value: list | None) -> None:
        """Set new option value.

        Arguments:
            value: New option value.

        Raises:
            TypeError: When the new value is of the wrong type.
            ValueError: When the argument is not a valid option value.
        """
        self._check_value(value)
        self._value = None if value is None else list(value)
    def load_proto(self, proto: ConfigProto) -> None:
        """Deserialize value from `.ConfigProto` message.

        Arguments:
            proto: Protobuf message that may contains options value.

        Raises:
            TypeError: When the new value is of the wrong type.
            ValueError: When the argument is not a valid option value.
        """
        if self.name in proto.options:
            opt = proto.options[self.name]
            if opt.HasField('as_string'):
                self.set_as_str(opt.as_string)
            else:
                raise TypeError(f"Wrong value type: {opt.WhichOneof('kind')[3:]}")
    def save_proto(self, proto: ConfigProto) -> None:
        """Serialize value into `.ConfigProto` message.

        Arguments:
            proto: Protobuf message where option value should be stored.
        """
        if self._value is not None:
            result = [self._get_as_typed_str(i) for i in self._value]
            sep = self.separator
            if sep is None:
                sep = '\n' if sum(len(i) for i in result) > 80 else ',' # noqa: PLR2004
            proto.options[self.name].as_string = sep.join(result)
    value: list = property(get_value, set_value, doc="Current option value")

class PyExprOption(Option[PyExpr]):
    """String configuration option with Python expression value.

    Arguments:
        name: Option name.
        description: Option description. Can span multiple lines.
        required: True if option must have a value.
        default: Default option value.
    """
    def __init__(self, name: str, description: str, *, required: bool=False,
                 default: PyExpr | None=None):
        self._value: PyExpr | None = None
        super().__init__(name, PyExpr, description, required=required, default=default)
    def clear(self, *, to_default: bool=True) -> None:
        """Clears the option value.

        Arguments:
            to_default: If True, sets the option value to default value, else to None.
        """
        self._value = self.default if to_default else None
    def get_formatted(self) -> str:
        """Returns value formatted for use in config file.
        """
        if self._value is None:
            return '<UNDEFINED>'
        result = self._value
        if '\n' in result:
            lines = []
            for line in result.splitlines(True):
                if lines:
                    lines.append('   ' + line)
                else:
                    lines.append(line)
            result = ''.join(lines)
        return result
    def set_as_str(self, value: str) -> None:
        """Set new option value from string.

        Arguments:
            value: New option value.

        Raises:
            ValueError: When the argument is not a valid option value.
        """
        self._value = PyExpr(value)
    def get_as_str(self) -> str:
        """Returns value as string.
        """
        return self._value
    def get_value(self) -> PyExpr | None:
        """Returns current option value.
        """
        return self._value
    def set_value(self, value: PyExpr | None) -> None:
        """Set new option value.

        Arguments:
            value: New option value.

        Raises:
            TypeError: When the new value is of the wrong type.
            ValueError: When the argument is not a valid option value.
        """
        self._check_value(value)
        self._value = value
    def load_proto(self, proto: ConfigProto) -> None:
        """Deserialize value from `.ConfigProto` message.

        Arguments:
            proto: Protobuf message that may contains options value.

        Raises:
            TypeError: When the new value is of the wrong type.
            ValueError: When the argument is not a valid option value.
        """
        if self.name in proto.options:
            opt = proto.options[self.name]
            if opt.HasField('as_string'):
                self.set_as_str(opt.as_string)
            else:
                raise TypeError(f"Wrong value type: {opt.WhichOneof('kind')[3:]}")
    def save_proto(self, proto: ConfigProto) -> None:
        """Serialize value into `.ConfigProto` message.

        Arguments:
            proto: Protobuf message where option value should be stored.
        """
        if self._value is not None:
            proto.options[self.name].as_string = self._value
    value: PyExpr | None = property(get_value, set_value, doc="Current option value")

class PyCodeOption(Option[PyCode]):
    """String configuration option with Python code value.

    Arguments:
        name: Option name.
        description: Option description. Can span multiple lines.
        required: True if option must have a value.
        default: Default option value.

    Important:
        Python code must be properly indented, but ConfigParser multiline string values have
        leading whitespace removed. To circumvent this, the `PyCodeOption` supports assignment
        of text values where lines start with `|` character. This character is removed, along
        with any number of subsequent whitespace characters that are between `|` and first
        non-whitespace character on first line starting with `|`.
    """
    def __init__(self, name: str, description: str, *, required: bool=False,
                 default: PyCode | None=None):
        self._value: PyCode | None = None
        super().__init__(name, PyCode, description, required=required, default=default)
    def clear(self, *, to_default: bool=True) -> None:
        """Clears the option value.

        Arguments:
            to_default: If True, sets the option value to default value, else to None.
        """
        self._value = self.default if to_default else None
    def get_formatted(self) -> str:
        """Returns value formatted for use in config file.
        """
        if self._value is None:
            return '<UNDEFINED>'
        result = self._value
        if '\n' in result:
            lines = []
            for line in result.splitlines(True):
                if lines:
                    lines.append('   | ' + line)
                else:
                    lines.append(line)
            result = ''.join(lines)
        return result
    def set_as_str(self, value: str) -> None:
        """Set new option value from string.

        Arguments:
            value: New option value.

        Raises:
            ValueError: When the argument is not a valid option value.
        """
        value = unindent_verticals(value)
        self._value = PyCode(value)
    def get_as_str(self) -> str:
        """Returns value as string.
        """
        return self._value
    def get_value(self) -> PyCode | None:
        """Returns current option value.
        """
        return self._value
    def set_value(self, value: PyCode | None) -> None:
        """Set new option value.

        Arguments:
            value: New option value.

        Raises:
            TypeError: When the new value is of the wrong type.
            ValueError: When the argument is not a valid option value.
        """
        self._check_value(value)
        self._value = value
    def load_proto(self, proto: ConfigProto) -> None:
        """Deserialize value from `.ConfigProto` message.

        Arguments:
            proto: Protobuf message that may contains options value.

        Raises:
            TypeError: When the new value is of the wrong type.
            ValueError: When the argument is not a valid option value.
        """
        if self.name in proto.options:
            opt = proto.options[self.name]
            if opt.HasField('as_string'):
                self.set_as_str(opt.as_string)
            else:
                raise TypeError(f"Wrong value type: {opt.WhichOneof('kind')[3:]}")
    def save_proto(self, proto: ConfigProto) -> None:
        """Serialize value into `.ConfigProto` message.

        Arguments:
            proto: Protobuf message where option value should be stored.
        """
        if self._value is not None:
            proto.options[self.name].as_string = self._value
    value: PyCode | None = property(get_value, set_value, doc="Current option value")

class PyCallableOption(Option[PyCallable]):
    """String configuration option with Python callable value.

    Arguments:
        name: Option name.
        description: Option description. Can span multiple lines.
        signature: Callable signature, callable or string with callable signature (function header).
        required: True if option must have a value.
        default: Default option value.

    Important:
        Python code must be properly indented, but `ConfigParser` multiline string values have
        leading whitespace removed. To circumvent this, the `PyCallableOption` supports assignment
        of text values where lines start with `|` character. This character is removed, along
        with any number of subsequent whitespace characters that are between `|` and first
        non-whitespace character on first line starting with `|`.
    """
    def __init__(self, name: str, description: str, signature: Signature | Callable | str,
                 * , required: bool=False, default: PyCallable | None=None):
        self._value: PyCallable | None = None
        #: Callable signature.
        if isinstance(signature, str):
            if not signature.startswith('def'):
                signature = 'def ' + signature
            signature += ': pass' if not signature.endswith(':') else ' pass'
            signature = Signature.from_callable(PyCallable(signature)._callable_)
        elif not isinstance(signature, Signature):
            signature = Signature.from_callable(signature)
        self.signature: Signature = signature
        super().__init__(name, PyCallable, description, required=required, default=default)
    def clear(self, *, to_default: bool=True) -> None:
        """Clears the option value.

        Arguments:
            to_default: If True, sets the option value to default value, else to None.
        """
        self._value = self.default if to_default else None
    def get_formatted(self) -> str:
        """Returns value formatted for use in config file.
        """
        if self._value is None:
            return '<UNDEFINED>'
        result = self._value
        if '\n' in result:
            lines = []
            for line in result.splitlines(True):
                if lines:
                    lines.append('   | ' + line)
                else:
                    lines.append(line)
            result = ''.join(lines)
        return result
    def set_as_str(self, value: str) -> None:
        """Set new option value from string.

        Arguments:
            value: New option value.

        Raises:
            ValueError: When the argument is not a valid option value.
        """
        value = unindent_verticals(value)
        self.set_value(PyCallable(value))
    def get_as_str(self) -> str:
        """Returns value as string.
        """
        return self._value
    def get_value(self) -> PyCallable | None:
        """Returns current option value.
        """
        return self._value
    def set_value(self, value: PyCallable | None) -> None:
        """Set new option value.

        Arguments:
            value: New option value.

        Raises:
            TypeError: When the new value is of the wrong type.
            ValueError: When the callable has wrong signature.
        """
        self._check_value(value)
        if value is not None:
            val_sig = signature(value._callable_)
            if not _eq(val_sig.return_annotation, self.signature.return_annotation):
                raise ValueError("Wrong callable return type")
            if len(val_sig.parameters) != len(self.signature.parameters):
                raise ValueError("Wrong number of parameters")
            for par in self.signature.parameters.values():
                val_par: Parameter = val_sig.parameters[cast(Signature, par).name]
                if not _eq(val_par.annotation, cast(Signature, par).annotation):
                    raise ValueError(f"Wrong type, parameter '{val_par.name}'")
                if not _eq(val_par.default, cast(Signature, par).default):
                    raise ValueError(f"Wrong default, parameter '{val_par.name}'")
                if not _eq(val_par.kind, cast(Signature, par).kind):
                    raise ValueError(f"Wrong parameter kind, parameter '{val_par.name}'")
        self._value = value
    def load_proto(self, proto: ConfigProto) -> None:
        """Deserialize value from `.ConfigProto` message.

        Arguments:
            proto: Protobuf message that may contains options value.

        Raises:
            TypeError: When the new value is of the wrong type.
            ValueError: When the argument is not a valid option value.
        """
        if self.name in proto.options:
            opt = proto.options[self.name]
            if opt.HasField('as_string'):
                self.set_as_str(opt.as_string)
            else:
                raise TypeError(f"Wrong value type: {opt.WhichOneof('kind')[3:]}")
    def save_proto(self, proto: ConfigProto) -> None:
        """Serialize value into `.ConfigProto` message.

        Arguments:
            proto: Protobuf message where option value should be stored.
        """
        if self._value is not None:
            proto.options[self.name].as_string = self._value
    value: PyCallable = property(get_value, set_value, doc="Current option value")

class ConfigOption(Option[str]):
    """Option whose 'value' is a Config instance, but stores/parses its section name.

    This allows having nested configuration sections where the section *name*
    itself is configurable. The actual `Config` object must be passed during
    initialization. The `value` property returns this `Config` object, while
    methods like `set_as_str`, `get_as_str`, `get_formatted`, `load_proto`,
    `save_proto` operate on the `Config` object's *name* (the section name).

    Loading/saving the *contents* of the referenced `Config` object is handled
    by the parent `Config`'s `load_config`/`save_proto` methods.

    Arguments:
        name: Option name.
        description: Option description. Can span multiple lines.
        config: Option's value.
        required: True if option must have a value.
        default: Default `Config.name` value.

    Important:
        Assigning directly to the `value` property is not supported like other
        options; use `set_as_str` or assign to the `Config` object's `.name`
        attribute indirectly if needed (though typically done via `load_config`).

    Note:
        The "empty" value for this option is not `None` (because the `Config` instance always
        exists), but an empty string for `Config.name` attribute.
    """
    def __init__(self, name: str, config: Config, description: str, *, required: bool=False,
                 default: str | None=None):
        assert isinstance(config, Config) # noqa: S101
        self._value: Config = config
        config._optional = not required
        super().__init__(name, str, description, required=required, default=default)
    def _get_value_description(self) -> str:
        return "configuration section name\n"
    def validate(self) -> None:
        """Validates option state.

        Raises:
            Error: When required option does not have a value.
        """
        if self.required and self.get_value().name == '':
            raise Error(f"Missing value for required option '{self.name}'")
        if self.get_value().name != '':
            self.value.validate()
    def clear(self, *, to_default: bool=True) -> None:
        """Clears the option value.

        Note:
           This method calls `~Config.clear(to_default)`.

        Arguments:
            to_default: If True, sets the `Config.name` to default value, else to empty string.
        """
        self._value.clear(to_default=to_default)
        self._value._name = self.default if to_default else ''
    def get_formatted(self) -> str:
        """Return value formatted for use in config file.

        The string contains section name that will be used to store the `Config` values.
        """
        return self._value.name
    def set_as_str(self, value: str) -> None:
        """Sets the section name for the associated `Config` instance.

        Arguments:
            value: The new section name (string).
        """
        self._value._name = value
    def get_as_str(self) -> str:
        """Returns the current section name of the associated `Config` instance."""
        return self._value.name
    def get_value(self) -> Config:
        """Returns the associated `Config` instance itself."""
        return self._value
    def set_value(self, value: str | None) -> None:
        """Sets the section name (indirectly). **Does not accept a Config object.**

        This method primarily handles setting the default section name during init.
        Setting the name post-init is typically done via `load_config` or `set_as_str`.
        Passing `None` sets the name to empty string (if not required).

        Arguments:
            value: The new section name (string) or None.

        Raises:
            ValueError: If `value` is None or empty string and the option is required.
        """
        if value is None:
            value = ''
        if value == '' and self.required:
            raise ValueError(f"Value is required for option '{self.name}'.")
        self._value._name = value
    def load_proto(self, proto: ConfigProto) -> None:
        """Deserialize section name from `proto.options[self.name].as_string`."""
        if self.name in proto.options:
            opt = proto.options[self.name]
            if opt.HasField('as_string'):
                self.set_as_str(opt.as_string)
            else:
                raise TypeError(f"Wrong value type: {opt.WhichOneof('kind')[3:]}")
    def save_proto(self, proto: ConfigProto) -> None:
        """Serialize section name into `proto.options[self.name].as_string`."""
        if self._value is not None:
            proto.options[self.name].as_string = self._value.name
    value: Config = property(get_value, set_value, doc="Current option value")

class ConfigListOption(Option[list]):
    """Option holding a list of Config instances, parsing/storing their section names.

    This option manages a list of `Config` objects, all of the *same* specified
    `item_type`. However, in configuration files (`ConfigParser`) and Protobuf
    messages, it stores and parses a *list of strings*, where each string is the
    section name corresponding to one of the `Config` instances in the list.

    Loading/saving the *contents* (options) of each referenced `Config` section
    is handled by the parent `Config`'s `load_config`/`save_proto` methods when
    they iterate through the main configuration structure. This option itself
    only deals with the list of *names* that identify which sections belong here.

    When `set_as_str` or `load_config` processes the string list of names, it
    creates new instances of `item_type` (the specified `Config` subclass)
    for each name found.

    Important:
        When read from `ConfigParser`, empty values in the list of names are ignored.

    Arguments:
        name: Option name identifying where the *list of section names* is stored.
        item_type: The specific `Config` subclass for items in the list. All items
                   will be instances of this type.
        description: Option description. Can span multiple lines.
        required: If True, the list of section names cannot be empty.
        separator: String separating section names in the config file value.
                   Handles line breaks automatically if `None`. See class docs.

    Example::

        from firebird.base.config import Config, StrOption, ConfigListOption
        from configparser import ConfigParser
        import io

        class WorkerConfig(Config):
            '''Configuration for a worker process.'''
            def __init__(self, name: str):
                super().__init__(name)
                self.task_type = StrOption('task_type', 'Type of task', default='generic')

        class MainAppConfig(Config):
            '''Main application configuration.'''
            def __init__(self):
                super().__init__('main_app')
                self.workers = ConfigListOption('workers', WorkerConfig,
                                                'List of worker configurations (section names)')

        # --- Configuration File Content ---
        config_data = '''
        [main_app]
        workers = worker_alpha, worker_beta  ; List of section names

        [worker_alpha]
        task_type = processing

        [worker_beta]
        task_type = reporting
        '''

        # --- Loading ---
        app_config = MainAppConfig()
        parser = ConfigParser()
        parser.read_string(config_data)
        app_config.load_config(parser) # Loads 'workers' list and worker sections

        # --- Accessing ---
        print(f"Worker section names: {app_config.workers.get_as_str()}")
        # Output: Worker section names: worker_alpha, worker_beta

        worker_list = app_config.workers.value
        print(f"Number of workers: {len(worker_list)}") # Output: 2
        print(f"First worker name: {worker_list[0].name}") # Output: worker_alpha
        print(f"First worker task: {worker_list[0].task_type.value}") # Output: processing
        print(f"Second worker task: {worker_list[1].task_type.value}") # Output: reporting

        # --- Getting Config String ---
        # print(app_config.get_config()) would regenerate the structure
    """
    def __init__(self, name: str, item_type: type[Config], description: str, *,
                 required: bool=False, separator: str | None=None):
        assert issubclass(item_type, Config) # noqa: S101
        self._value: list = []
        #: Datatype of list items.
        self.item_type: type[Config] = item_type
        #: String that separates values when options value is read from `ConfigParser`.
        #: Default separator is None. It's possible to use a line break as separator.
        #: If separator is `None` and the value contains line breaks, it uses the line
        #: break as separator, otherwise it uses comma as separator.
        self.separator: str | None = separator
        super().__init__(name, list, description, required=required, default=[])
    def _get_value_description(self) -> str:
        return f"list of configuration section names (for sections of type '{self.item_type.__name__}')\n"
    def _check_value(self, value: list) -> None:
        # Checks if 'value' is a list and all items are instances of self.item_type
        super()._check_value(value) # Checks if it's a list (and None if required)
        if value is not None:
            for i, item in enumerate(value):
                if not isinstance(item, self.item_type):
                    raise ValueError(f"List item[{i}] has wrong type: "
                                    f"Expected '{self.item_type.__name__}', "
                                    f"got '{type(item).__name__}'")
    def clear(self, *, to_default: bool=True) -> None: # noqa: ARG002
        """Clears the list of `Config` instances.

        Arguments:
            to_default: This parameter is ignored as there's no default list content.
                        The list is simply emptied.
        """
        self._value.clear()
    def validate(self) -> None:
        """Validates the option state.

        Checks if the list is non-empty if required. Calls `validate()` on each
        `Config` instance currently in the list.

        Raises:
            Error: When required and the list is empty, or if any contained
                   `Config` instance fails its own validation.
        """
        if self.required and not self._value:
            raise Error(f"Missing value for required option '{self.name}'")
        for item in self._value:
            item.validate()
    def get_formatted(self) -> str:
        """Returns the list of section names formatted for use in a config file."""
        if not self._value:
            return '<UNDEFINED>'
        result = [i.name for i in self._value]
        sep = self.separator
        if sep is None:
            sep = '\n' if sum(len(i) for i in result) > 80 else ',' # noqa: PLR2004
        if sep == '\n':
            x = '\n   '
            return f'\n   {x.join(result)}'
        return f'{sep} '.join(result)
    def set_as_str(self, value: str) -> None:
        """Populates the list with new `Config` instances based on section names in string.

        Parses the input string `value` (using the defined `separator` logic)
        to get a list of section names. For each non-empty name, creates a new
        instance of `self.item_type` with that name and adds it to the internal list,
        replacing any previous list content.

        Arguments:
            value: String containing separator-defined list of section names.

        Raises:
            ValueError: If the string parsing encounters issues (though typically just
                        results in fewer items if format is odd).
        """
        new = []
        if value.strip():
            separator = ('\n' if '\n' in value else ',') if self.separator is None else self.separator
            for item in (i for i in value.split(separator) if i.strip()):
                new.append(self.item_type(item.strip()))
            self._value = new
    def get_as_str(self) -> str:
        """Returns the list of contained section names as a separator-joined string."""
        result = [i.name for i in self._value]
        sep = self.separator
        if sep is None:
            sep = '\n' if sum(len(i) for i in result) > 80 else ', ' # noqa: PLR2004
        return sep.join(result)
    def get_value(self) -> list:
        """Returns the current list of `Config` instances."""
        return self._value
    def set_value(self, value: list | None) -> None:
        """Sets the list of `Config` instances.

        Replaces the current list with the provided one. Ensures all items in the
        new list are of the correct `item_type`. Passing `None` clears the list.

        Arguments:
            value: A new list of `Config` instances (must be of `self.item_type`), or `None`.

        Raises:
            TypeError: If `value` is not a list or contains items of the wrong type.
            ValueError: If `value` is None or empty and the option is required.
        """
        self._check_value(value)
        if value is None:
            self.clear()
        else:
            self._value = list(value)
    def load_proto(self, proto: ConfigProto) -> None:
        """Deserialize list of section names from `proto.options[self.name].as_string`."""
        if self.name in proto.options:
            opt = proto.options[self.name]
            if opt.HasField('as_string'):
                self.set_as_str(opt.as_string)
            else:
                raise TypeError(f"Wrong value type: {opt.WhichOneof('kind')[3:]}")
    def save_proto(self, proto: ConfigProto) -> None:
        """Serialize list of section names into `proto.options[self.name].as_string`."""
        result = [i.name for i in self._value]
        sep = self.separator
        if sep is None:
            sep = '\n' if sum(len(i) for i in result) > 80 else ',' # noqa: PLR2004
        proto.options[self.name].as_string = sep.join(result)
    value: list = property(get_value, set_value, doc="Current option value")

class DataclassOption(Option[Any]):
    """Configuration option holding an instance of a Python dataclass.

    Parses configuration from a string representation where each field of the
    dataclass is defined on its own line or separated by a defined `separator`.
    The format for each field within the string is `field_name: value_as_str`.

    Relies on the `firebird.base.strconv` module to convert the `value_as_str`
    part for each field into the appropriate Python type based on the dataclass's
    type hints or the explicitly provided `fields` mapping.

    Important:
        - Ensure type hints in the dataclass are concrete types (or provide the
          `fields` mapping) and that `strconv` has registered convertors for all
          field types used.
        - When read from `ConfigParser`, empty field definitions in the value string
          might be ignored or cause errors depending on parsing.

    Arguments:
        name: Option name.
        dataclass: The dataclass type this option holds an instance of.
        description: Option description.
        required: If True, the option must have a value (cannot be None).
        default: Default instance of the dataclass.
        separator: String separating `field:value` pairs in the config file string.
                   Handles line breaks automatically if `None`. See class docs.
        fields: Optional override mapping field names to types. Useful if type hints
                are complex or need overriding. If None, uses `get_type_hints`.

    Example::

        from dataclasses import dataclass, field
        from firebird.base.config import Config, DataclassOption
        from firebird.base.strconv import register_convertor # If custom types needed
        from configparser import ConfigParser
        import io

        @dataclass
        class DBInfo:
            host: str
            port: int = 5432 # Field with default
            user: str
            ssl_mode: bool = field(default=False)

        class AppSettings(Config):
            def __init__(self):
                super().__init__('app')
                self.database = DataclassOption('database', DBInfo,
                                               'Database connection details')

        # --- Configuration File Content ---
        config_data = '''
        [app]
        database =
            host: db.example.com
            user: app_user
            port: 15432
        '''
        # Note: ssl_mode uses its default (False) as it's not specified.

        # --- Loading ---
        app_config = AppSettings()
        parser = ConfigParser()
        parser.read_string(config_data)
        app_config.load_config(parser)

        # --- Accessing ---
        db_info = app_config.database.value
        print(f"Is DBInfo instance: {isinstance(db_info, DBInfo)}") # Output: True
        print(f"DB Host: {db_info.host}")       # Output: db.example.com
        print(f"DB Port: {db_info.port}")       # Output: 15432 (overrode default)
        print(f"DB User: {db_info.user}")       # Output: app_user
        print(f"DB SSL: {db_info.ssl_mode}")    # Output: False (used default)

        # --- Getting Config String ---
        # print(app_config.get_config()) would regenerate the structure
    """
    def __init__(self, name: str, dataclass: type, description: str, *, required: bool=False,
                 default: Any | None=None, separator: str | None=None, fields: dict[str, type] | None=None):
        assert hasattr(dataclass, '__dataclass_fields__') # noqa: S101
        self._fields: dict[str, type] = get_type_hints(dataclass) if fields is None else fields
        if __debug__:
            for ftype in self._fields.values():
                assert get_convertor(ftype) is not None # noqa: S101
        self._value: Any = None
        #: Dataclass type.
        self.dataclass: type = dataclass
        #: String that separates dataclass field values when options value is read from
        #: `ConfigParser`. Default separator is None. It's possible to use a line break
        #: as separator. If separator is `None` and the value contains line breaks, it
        #: uses the line break as separator, otherwise it uses comma as separator.
        self.separator: str | None = separator
        super().__init__(name, dataclass, description, required=required, default=default)
    def _get_value_description(self) -> str:
        return """list of values, where each list item defines value for a dataclass field.
Item format: field_name:value_as_str
"""
    def _get_str_fields(self) -> list[str]:
        result = []
        if self._value is not None:
            for fname in self._fields:
                result.append(f'{fname}:{convert_to_str(getattr(self._value, fname))}')
        return result
    def clear(self, *, to_default: bool=True) -> None:
        """Clears the option value.

        Arguments:
            to_default: If True, sets the option value to default value, else to None.
        """
        self._value = self.default if to_default else None
    def get_formatted(self) -> str:
        """Returns value formatted for use in config file.
        """
        if self._value is None:
            return '<UNDEFINED>'
        result = self._get_str_fields()
        sep = self.separator
        if sep is None:
            sep = '\n' if sum(len(i) for i in result) > 80 else ',' # noqa: PLR2004
        if sep == '\n':
            x = '\n   '
            return f'\n   {x.join(result)}'
        return f'{sep} '.join(result)
    def set_as_str(self, value: str) -> None:
        """Creates and sets the dataclass instance from its string representation.

        Parses the `value` string expecting `field_name: value_as_str` items,
        separated according to the `separator` logic. Uses `strconv` to convert
        each `value_as_str` to the required field type. Finally, instantiates
        the dataclass using the parsed field values.

        Arguments:
            value: String containing the dataclass representation.

        Raises:
            ValueError: If the string format is invalid, a field name is unknown,
                        a value cannot be converted by `strconv`, or the resulting
                        dictionary of values cannot instantiate the dataclass
                        (e.g., missing required fields without defaults).
            TypeError: If `strconv` conversion fails with a type error.
        """
        new = {}
        if value.strip():
            separator = ('\n' if '\n' in value else ',') if self.separator is None else self.separator
            for item in (i for i in value.split(separator) if i.strip()):
                try:
                    field_name, field_value = item.split(':', 1)
                except Exception as exc:
                    raise ValueError(f"Illegal value '{value}' for option '{self.name}'") from exc
                field_name = field_name.strip()
                ftype = self._fields.get(field_name)
                if ftype is None:
                    raise ValueError(f"Unknown data field '{field_name}' for option '{self.name}'")
                convertor = get_convertor(ftype)
                new[field_name] = convertor.from_str(ftype, field_value.strip())
            try:
                new_val = self.dataclass(**new)
            except Exception as exc:
                raise ValueError(f"Illegal value '{value}' for option '{self.name}'") from exc
            self._value = new_val
    def get_as_str(self) -> str:
        """Returns the string representation of the current dataclass value."""
        result = self._get_str_fields()
        sep = self.separator
        if sep is None:
            sep = '\n' if sum(len(i) for i in result) > 80 else ',' # noqa: PLR2004
        return sep.join(result)
    def get_value(self) -> Any:
        """Returns the current dataclass instance (or None)."""
        return self._value
    def set_value(self, value: Any) -> None:
        """Sets the option value to the provided dataclass instance.

        Arguments:
            value: An instance of the option's `dataclass` type, or `None`.

        Raises:
            TypeError: If `value` is not None and not an instance of the expected `dataclass`.
            ValueError: If `value` is None and the option is required.
        """
        self._check_value(value)
        self._value = value
    def load_proto(self, proto: ConfigProto) -> None:
        """Deserialize dataclass from `proto.options[self.name].as_string`."""
        if self.name in proto.options:
            opt = proto.options[self.name]
            if opt.HasField('as_string'):
                self.set_as_str(opt.as_string)
            else:
                raise TypeError(f"Wrong value type: {opt.WhichOneof('kind')[3:]}")
    def save_proto(self, proto: ConfigProto) -> None:
        """Serialize dataclass into `proto.options[self.name].as_string`."""
        if self._value is not None:
            result = self._get_str_fields()
            sep = self.separator
            if sep is None:
                sep = '\n' if sum(len(i) for i in result) > 80 else ',' # noqa: PLR2004
            proto.options[self.name].as_string = sep.join(result)
    value: Any = property(get_value, set_value, doc="Current option value")

class PathOption(Option[str]):
    """Configuration option with `pathlib.Path` value.

        Arguments:
            name: Option name.
            description: Option description. Can span multiple lines.
            required: True if option must have a value.
            default: Default option value.
    """
    def __init__(self, name: str, description: str, *, required: bool=False,
                 default: Path | None=None):
        self._value: Path | None = None
        super().__init__(name, Path, description, required=required, default=default)
    def clear(self, *, to_default: bool=True) -> None:
        """Clears the option value.

        Arguments:
            to_default: If True, sets the option value to default value, else to None.
        """
        self._value = self.default if to_default else None
    def get_formatted(self) -> str:
        """Returns value formatted for use in config file.
        """
        return '<UNDEFINED>' if self._value is None else str(self._value)
    def set_as_str(self, value: str) -> None:
        """Set new option value from string.

        Arguments:
            value: New option value.

        Raises:
            ValueError: When the argument is not a valid option value.
        """
        self._value = Path(value)
    def get_as_str(self) -> str:
        """Returns value as string.
        """
        return str(self._value)
    def get_value(self) -> Path | None:
        """Returns current option value.
        """
        return self._value
    def set_value(self, value: Path | None) -> None:
        """Set new option value.

        Arguments:
            value: New option value.

        Raises:
            TypeError: When the new value is of the wrong type.
            ValueError: When the argument is not a valid option value.
        """
        self._check_value(value)
        self._value = value
    def load_proto(self, proto: ConfigProto) -> None:
        """Deserialize value from `.ConfigProto` message.

        Arguments:
            proto: Protobuf message that may contains options value.

        Raises:
            TypeError: When the new value is of the wrong type.
            ValueError: When the argument is not a valid option value.
        """
        if self.name in proto.options:
            opt = proto.options[self.name]
            if opt.HasField('as_string'):
                self.set_as_str(opt.as_string)
            else:
                raise TypeError(f"Wrong value type: {opt.WhichOneof('kind')[3:]}")
    def save_proto(self, proto: ConfigProto) -> None:
        """Serialize value into `.ConfigProto` message.

        Arguments:
            proto: Protobuf message where option value should be stored.
        """
        if self._value is not None:
            proto.options[self.name].as_string = self.get_as_str()
    value: Path = property(get_value, set_value, doc="Current option value")
