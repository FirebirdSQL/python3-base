#coding:utf-8
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

* configuration options of various data type, including lists and other complex types
* validation
* direct manipulation of configuration values
* reading from (and writing into) configuration in `configparser` format
* exchanging configuration (for example between processes) using Google protobuf messages
"""

from __future__ import annotations
from typing import Generic, Type, Any, List, Dict, Union, Sequence, Optional, TypeVar, cast, get_type_hints
from abc import ABC, abstractmethod
from uuid import UUID
from decimal import Decimal, DecimalException
from configparser import ConfigParser
from inspect import signature, Signature, Parameter
from enum import Enum, Flag, _decompose
from .config_pb2 import ConfigProto
from .types import Error, MIME, ZMQAddress, PyExpr, PyCode, PyCallable
from .strconv import get_convertor, convert_to_str, Convertor

# Functions

def unindent_verticals(value: str) -> str:
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

def create_config(_cls: Type[Config], name: str, description: str) -> Config: # pragma: no cover
    """Return newly created `Config` instance. Intended to be used with `functools.partial`.
"""
    return _cls(name, description)



# Base classes

T = TypeVar('T')

class Option(Generic[T], ABC):
    """Generic abstract base class for configuration options.

Arguments:
    name: Option name.
    datatype: Option datatype.
    description: Option description. Can span multiple lines.
    required: True if option must have a value.
    default: Default option value.

Attributes:
    name (str): Option name.
    datatype (type): Option datatype.
    description (str): Option description. Can span multiple lines.
    required (bool): True if option must have a value.
    default (instance of [T]): Default option value.
"""
    def __init__(self, name: str, datatype: T, description: str, required: bool=False,
                 default: T=None):
        assert name and isinstance(name, str), "name required"
        assert datatype and isinstance(datatype, type), "datatype required"
        assert description and isinstance(description, str), "description required"
        assert default is None or isinstance(default, datatype), "default has wrong data type"
        self.name: str = name
        self.datatype: T = datatype
        self.description: str = description
        self.required: bool = required
        self.default: T = default
        if default is not None:
            self.set_value(default)
    def _check_value(self, value: T) -> None:
        if value is None and self.required:
            raise ValueError(f"Value is required for option '{self.name}'.")
        if value is not None and not isinstance(value, self.datatype):
            raise TypeError(f"Option '{self.name}' value must be a "
                            f"'{self.datatype.__name__}',"
                            f" not '{type(value).__name__}'")
    def _get_config_lines(self) -> List[str]:
        """Returns list of strings containing text lines suitable for use in configuration
file processed with `~configparser.ConfigParser`.

Text lines with configuration start with comment marker `;` and end with newline.

Note:
   This function is intended for internal use. To get string describing current
   configuration that is suitable for configuration files, use `get_config` method.
"""
        lines = [f"; {self.name}\n",
                 f"; {'-' * len(self.name)}\n",
                 ";\n",
                 f"; data type: {self.datatype.__name__}\n",
                 ";\n"]
        if self.required:
            description = '[REQUIRED] ' + self.description
        else:
            description = '[optional] ' + self.description
        for line in description.split('\n'):
            lines.append(f"; {line}\n")
        lines.append(';\n')
        value = self.get_value()
        nodef = ';' if value == self.default else ''
        value = '<UNDEFINED>' if value is None else self.get_formatted()
        if '\n' in value:
            chunks = value.splitlines(keepends=True)
            new_value = [chunks[0]]
            new_value.extend(f'{nodef}{x}' for x in chunks[1:])
            value = ''.join(new_value)
        lines.append(f"{nodef}{self.name} = {value}\n")
        return lines
    def load_config(self, config: ConfigParser, section: str) -> None:
        """Update option value from `~configparser.ConfigParser` instance.

Arguments:
    config:  ConfigParser instance.
    section: Name of ConfigParser section that should be used to get new option value.

Raises:
    ValueError: When the argument is not a valid option value.
"""
        if self.name in config[section]:
            self.set_as_str(config[section][self.name])
    def validate(self) -> None:
        """Validates option state.

Raises:
    Error: When required option does not have a value.
"""
        if self.required and self.get_value() is None:
            raise Error(f"Missing value for required option '{self.name}'")
    def get_config(self) -> str:
        """Returns string containing text lines suitable for use in configuration file
processed with `~configparser.ConfigParser`.

Text lines with configuration start with comment marker ; and end with newline.
"""
        return ''.join(self._get_config_lines())
    @abstractmethod
    def clear(self, to_default: bool=True) -> None:
        """Clears the option value.

Arguments:
    to_default: If True, sets the option value to default value, else to None.
"""
    @abstractmethod
    def get_formatted(self) -> str:
        """Return value formatted for use in config file."""
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
        """Return value as string."""
    @abstractmethod
    def get_value(self) -> T:
        "Return current option value"
    @abstractmethod
    def set_value(self, value: T) -> None:
        """Set new option value.

Arguments:
    value: New option value.

Raises:
    TypeError: When the new value is of the wrong type.
    ValueError: When the argument is not a valid option value.
"""
    @abstractmethod
    def load_proto(self, proto: ConfigProto) -> None:
        """Deserialize value from `.ConfigProto` message.

Arguments:
    proto: Protobuf message that may contains options value.

Raises:
    TypeError: When the new value is of the wrong type.
    ValueError: When the argument is not a valid option value.
"""
    @abstractmethod
    def save_proto(self, proto: ConfigProto) -> None:
        """Serialize value into `.ConfigProto` message.

Arguments:
    proto: Protobuf message where option value should be stored.
"""

class Config:
    """Collection of configuration options.

Arguments:
    name: Name associated with Config (default section name).

Important:
    Descendants must define individual options and sub configs as instance attributes.
"""
    def __init__(self, name: str):
        self._name: str = name
    def validate(self) -> None:
        """Checks whether:
    - all required options have value other than None.
    - all options are defined as config attribute with the same name as option name

Raises exception when any constraint required by configuration is violated.
"""
        for option in self.options:
            option.validate()
            if not hasattr(self, option.name):
                raise Error(f"Option '{option.name}' is not defined as "
                            f"attribute with the same name")
    def clear(self, to_default: bool=True) -> None:
        """Clears all owned options and options in owned sub-configs.

Arguments:
    to_default: If True, sets the option values to defaults, else to None.
"""
        for option in self.options:
            option.clear(to_default)
        for config in self.configs:
            config.clear(to_default)
    def get_description(self) -> str:
        """Configuration description. Can span multiple lines.

Note:  Default implementation returns class doc string.
"""
        return self.__doc__
    def get_config(self) -> str:
        """Returns string containing text lines suitable for use in configuration file
processed with `~configparser.ConfigParser`.

Text lines with configuration start with comment marker ; and end with newline.
"""
        lines = [f'[{self.name}]\n', ';\n']
        for line in self.get_description().splitlines():
            lines.append(f"; {line}\n")
        lines.append(';\n')
        for option in self.options:
            lines.append('\n')
            lines.append(option.get_config())
        for config in self.configs:
            lines.append('\n')
            lines.append(config.get_config())
        return ''.join(lines)
    def load_config(self, config: ConfigParser, section: str=None) -> None:
        """Update configuration.

Arguments:
    config:  ConfigParser instance with configuration values.
    section: Name of ConfigParser section that should be used to get new configuration
             values. If not provided, uses `name`.
"""
        if section is None:
            section = self.name
        try:
            for option in self.options:
                option.load_config(config, section)
            for subcfg in self.configs:
                subcfg.load_config(config)
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
        "Name associated with Config (default section name)."
        return self._name
    @property
    def options(self) -> List[Option]:
        "List of options defined for this Config instance."
        return [v for v in vars(self).values() if isinstance(v, Option)]
    @property
    def configs(self) -> List[Config]:
        """List of sub-Configs defined for this Config instance. It includes all instance
attributes of `Config` type, and `Config` values of owned `ConfigOption` and `ConfigListOption`
instances.
"""
        result = [v if isinstance(v, Config) else v.value
                  for v in vars(self).values() if isinstance(v, (Config, ConfigOption))]
        for opt in (v for v in vars(self).values() if isinstance(v, ConfigListOption)):
            result.extend(opt.value)
        return result

# Options

class StrOption(Option[str]):
    """Configuration option with string value.

Arguments:
    name: Option name.
    description: Option description. Can span multiple lines.
    required: True if option must have a value.
    default: Default option value.
"""
    def __init__(self, name: str, description: str, *, required: bool=False, default: str=None):
        self._value: str = None
        super().__init__(name, str, description, required, default)
    def clear(self, to_default: bool=True) -> None:
        """Clears the option value.

Arguments:
    to_default: If True, sets the option value to default value, else to None.
"""
        self._value = self.default if to_default else None
    def get_formatted(self) -> str:
        """Return value formatted for use in config file."""
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
        self._value = value
    def get_as_str(self) -> str:
        """Return value as string."""
        return self._value
    def get_value(self) -> str:
        "Return current option value"
        return self._value
    def set_value(self, value: str) -> None:
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
    value: str = property(get_value, set_value)

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
                 default: int=None, signed: bool=False):
        self._value: int = None
        self.__signed: bool = signed
        super().__init__(name, int, description, required, default)
    def clear(self, to_default: bool=True) -> None:
        """Clears the option value.

Arguments:
    to_default: If True, sets the option value to default value, else to None.
"""
        self._value = self.default if to_default else None
    def get_formatted(self) -> str:
        """Return value formatted for use in config file."""
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
        """Return value as string."""
        return str(self._value)
    def get_value(self) -> int:
        "Return current option value"
        return self._value
    def set_value(self, value: int) -> None:
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
    value: int = property(get_value, set_value)

class FloatOption(Option[float]):
    """Configuration option with float value.

Arguments:
    name: Option name.
    description: Option description. Can span multiple lines.
    required: True if option must have a value.
    default: Default option value.
"""
    def __init__(self, name: str, description: str, *, required: bool=False, default: float=None):
        self._value: float = None
        super().__init__(name, float, description, required, default)
    def clear(self, to_default: bool=True) -> None:
        """Clears the option value.

Arguments:
    to_default: If True, sets the option value to default value, else to None.
"""
        self._value = self.default if to_default else None
    def get_formatted(self) -> str:
        """Return value formatted for use in config file."""
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
        """Return value as string."""
        return str(self._value)
    def get_value(self) -> float:
        "Return current option value"
        return self._value
    def set_value(self, value: float) -> None:
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
    value: float = property(get_value, set_value)

class DecimalOption(Option[Decimal]):
    """Configuration option with decimal.Decimal value.

Arguments:
    name: Option name.
    description: Option description. Can span multiple lines.
    required: True if option must have a value.
    default: Default option value.
"""
    def __init__(self, name: str, description: str, *, required: bool=False, default: Decimal=None):
        self._value: Decimal = None
        super().__init__(name, Decimal, description, required, default)
    def clear(self, to_default: bool=True) -> None:
        """Clears the option value.

Arguments:
    to_default: If True, sets the option value to default value, else to None.
"""
        self._value = self.default if to_default else None
    def get_formatted(self) -> str:
        """Return value formatted for use in config file."""
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
            raise ValueError(str(exc))
    def get_as_str(self) -> str:
        """Return value as string."""
        return str(self._value)
    def get_value(self) -> Decimal:
        "Return current option value"
        return self._value
    def set_value(self, value: Decimal) -> None:
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
    value: Decimal = property(get_value, set_value)

class BoolOption(Option[bool]):
    """Configuration option with boolean value.

Arguments:
    name: Option name.
    description: Option description. Can span multiple lines.
    required: True if option must have a value.
    default: Default option value.
"""
    def __init__(self, name: str, description: str, *, required: bool=False, default: bool=None):
        self._value: bool = None
        self.from_str = get_convertor(bool).from_str
        super().__init__(name, bool, description, required, default)
    def clear(self, to_default: bool=True) -> None:
        """Clears the option value.

Arguments:
    to_default: If True, sets the option value to default value, else to None.
"""
        self._value = self.default if to_default else None
    def get_formatted(self) -> str:
        """Return value formatted for use in config file."""
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
        """Return value as string."""
        return str(self._value)
    def get_value(self) -> bool:
        "Return current option value"
        return self._value
    def set_value(self, value: bool) -> None:
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
    value: bool = property(get_value, set_value)

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
        self._value: ZMQAddress = None
        super().__init__(name, ZMQAddress, description, required, default)
    def clear(self, to_default: bool=True) -> None:
        """Clears the option value.

Arguments:
    to_default: If True, sets the option value to default value, else to None.
"""
        self._value = self.default if to_default else None
    def get_formatted(self) -> str:
        """Return value formatted for use in config file."""
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
        """Return value as string."""
        return self._value
    def get_value(self) -> ZMQAddress:
        "Return current option value"
        return self._value
    def set_value(self, value: ZMQAddress) -> None:
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
    value: ZMQAddress = property(get_value, set_value)

class EnumOption(Option[Enum]):
    """Configuration option with enum value.

Arguments:
    name: Option name.
    description: Option description. Can span multiple lines.
    required: True if option must have a value.
    default: Default option value.
    allowed: List of allowed Enum members. When not defined, all members of enum type are
             allowed.

Attributes:
    allowed: List of allowed enum values.
"""
    def __init__(self, name: str, enum_class: Enum, description: str, *, required: bool=False,
                 default: Enum=None, allowed: List=None):
        self._value: Enum = None
        self.allowed: Sequence = enum_class if allowed is None else allowed
        self._members: Dict = {i.name.lower(): i for i in self.allowed}
        super().__init__(name, enum_class, description, required, default)
    def get_config(self) -> str:
        """Returns string containing text lines suitable for use in configuration file
processed with `~configparser.ConfigParser`.

Text lines with configuration start with comment marker ; and end with newline.
"""
        lines: List = super()._get_config_lines()
        lines.insert(4, f"; values: {', '.join(x.name.lower() for x in self.allowed)}\n")
        return ''.join(lines)
    def clear(self, to_default: bool=True) -> None:
        """Clears the option value.

Arguments:
    to_default: If True, sets the option value to default value, else to None.
"""
        self._value = self.default if to_default else None
    def get_formatted(self) -> str:
        """Return value formatted for use in config file."""
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
        """Return value as string."""
        return self._value.name
    def get_value(self) -> Enum:
        "Return current option value"
        return self._value
    def set_value(self, value: Enum) -> None:
        """Set new option value.

Arguments:
    value: New option value.

Raises:
    TypeError: When the new value is of the wrong type.
    ValueError: When the argument is not a valid option value.
"""
        self._check_value(value)
        if value is not None and value not in self.allowed:
            raise ValueError(f"Value '{value}' not allowed")
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
    value: Enum = property(get_value, set_value)

class FlagOption(Option[Flag]):
    """Configuration option with flag value.

Arguments:
    name: Option name.
    description: Option description. Can span multiple lines.
    required: True if option must have a value.
    default: Default option value.
    allowed: List of allowed Flag members. When not defined, all members of flag type are
             allowed.

Attributes:
    allowed: List of allowed flag values.
"""
    def __init__(self, name: str, flag_class: Flag, description: str, *, required: bool=False,
                 default: Flag=None, allowed: List=None):
        self._value: Flag = None
        self.allowed: Sequence = flag_class if allowed is None else allowed
        self._members: Dict = {i.name.lower(): i for i in self.allowed}
        super().__init__(name, flag_class, description, required, default)
    def get_config(self) -> str:
        """Returns string containing text lines suitable for use in configuration file
processed with `~configparser.ConfigParser`.

Text lines with configuration start with comment marker ; and end with newline.
"""
        lines: List = super()._get_config_lines()
        lines.insert(4, f"; values: {', '.join(x.name.lower() for x in self.allowed)}\n")
        return ''.join(lines)
    def clear(self, to_default: bool=True) -> None:
        """Clears the option value.

Arguments:
    to_default: If True, sets the option value to default value, else to None.
"""
        self._value = self.default if to_default else None
    def get_formatted(self) -> str:
        """Return value formatted for use in config file."""
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
        """Return value as string."""
        if self._value._name_ is not None:
            return self._value.name
        members, uncovered = _decompose(self.datatype, self._value)
        if len(members) == 1 and members[0]._name_ is None:
            return f'{members[0]._value_}'
        return ' | '.join([str(m._name_ or m._value_) for m in members])
    def get_value(self) -> Flag:
        "Return current option value"
        return self._value
    def set_value(self, value: Flag) -> None:
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
    value: Flag = property(get_value, set_value)

class UUIDOption(Option[UUID]):
    """Configuration option with UUID value.

Arguments:
    name: Option name.
    description: Option description. Can span multiple lines.
    required: True if option must have a value.
    default: Default option value.
"""
    def __init__(self, name: str, description: str, *, required: bool=False, default: UUID=None):
        self._value: UUID = None
        super().__init__(name, UUID, description, required, default)
    def clear(self, to_default: bool=True) -> None:
        """Clears the option value.

Arguments:
    to_default: If True, sets the option value to default value, else to None.
"""
        self._value = self.default if to_default else None
    def get_formatted(self) -> str:
        """Return value formatted for use in config file."""
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
        """Return value as string."""
        return 'None' if self._value is None else self._value.hex
    def get_value(self) -> UUID:
        "Return current option value"
        return self._value
    def set_value(self, value: UUID) -> None:
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
    value: UUID = property(get_value, set_value)

class MIMEOption(Option[MIME]):
    """Configuration option with MIME type specification value.

Arguments:
    name: Option name.
    description: Option description. Can span multiple lines.
    required: True if option must have a value.
    default: Default option value.
"""
    def __init__(self, name: str, description: str, *, required: bool=False, default: MIME=None):
        self._value: MIME = None
        super().__init__(name, MIME, description, required, default)
    def clear(self, to_default: bool=True) -> None:
        """Clears the option value.

Arguments:
    to_default: If True, sets the option value to default value, else to None.
"""
        self._value = self.default if to_default else None
    def get_formatted(self) -> str:
        """Return value formatted for use in config file."""
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
        """Return value as string."""
        return 'None' if self._value is None else self._value
    def get_value(self) -> MIME:
        "Return current option value"
        return self._value
    def set_value(self, value: MIME) -> None:
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
    value: MIME = property(get_value, set_value)

class ListOption(Option[List]):
    """Configuration option with list of values.

Arguments:
    name:        Option name.
    item_type:   Datatype of list items. It could be a type or sequence of types. If multiple
                 types are provided, each value in config file must have format:
                 `type_name:value_as_str`.
    description: Option description. Can span multiple lines.
    required:    True if option must have a value.
    default:     Default option value.
    separator:   String that separates list item values when options value is read from
                 `ConfigParser`. It's possible to use a line break as separator.
                 If separator is `None` [default] and the value contains line breaks, it uses
                 the line break as separator, otherwise it uses comma as separator.

Attributes:
    item_types:  Datatypes of list items. If there is more than one type, each value in
                 config file must have format: `type_name:value_as_str`.
    separator:   String that separates list item values when options value is read from
                 `ConfigParser`. Default separator is None. It's possible to use a line
                 break as separator. If separator is `None` and the value contains line
                 breaks, it uses the line break as separator, otherwise it uses comma as
                 separator.

Important:
    When option is read from `ConfigParser`, empty values are ignored.
"""
    def __init__(self, name: str, item_type: Union[Type, Sequence[Type]], description: str,
                 *, required: bool=False, default: List=None, separator: str=None):
        self._value: List = None
        self.item_types: Sequence[Type] = (item_type, ) if isinstance(item_type, type) else item_type
        self.separator: Optional[str] = separator
        self._convertor: Convertor = get_convertor(item_type) if isinstance(item_type, type) else None
        super().__init__(name, list, description, required, default)
    def _get_as_typed_str(self, value: Any) -> str:
        result = convert_to_str(value)
        if len(self.item_types) > 1:
            result = f'{value.__class__.__name__}:{result}'
        return result
    def clear(self, to_default: bool=True) -> None:
        """Clears the option value.

Arguments:
    to_default: If True, sets the option value to default value, else to None.
"""
        self._value = self.default if to_default else None
    def get_formatted(self) -> str:
        """Return value formatted for use in config file."""
        if self._value is None:
            return '<UNDEFINED>'
        result = [convert_to_str(i) for i in self._value]
        sep = self.separator
        if sep is None:
            sep = '\n' if sum(len(i) for i in result) > 80 else ','
        if sep == '\n':
            x = '\n   '
            return f"\n   {x.join(result)}"
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
                    itype_name, item = item.split(':', 1)
                    itype_name = itype_name.strip()
                    itype = fullname_map.get(itype_name) if '.' in itype_name else name_map.get(itype_name)
                    if itype is None:
                        raise ValueError(f"Item type '{itype_name}' not supported")
                    convertor = get_convertor(itype)
                new.append(convertor.from_str(itype, item.strip()))
            self._value = new
    def get_as_str(self) -> str:
        """Return value as string."""
        result = [convert_to_str(i) for i in self._value]
        sep = self.separator
        if sep is None:
            sep = '\n' if sum(len(i) for i in result) > 80 else ','
        return sep.join(result)
    def get_value(self) -> List:
        "Return current option value"
        return self._value
    def set_value(self, value: List) -> None:
        """Set new option value.

Arguments:
    value: New option value.

Raises:
    TypeError: When the new value is of the wrong type.
    ValueError: When the argument is not a valid option value.
"""
        self._check_value(value)
        if value is not None:
            i = 0
            for item in value:
                if item.__class__ not in self.item_types:
                    raise ValueError(f"List item[{i}] has wrong type")
                i += 1
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
            result = [self._get_as_typed_str(i) for i in self._value]
            sep = self.separator
            if sep is None:
                sep = '\n' if sum(len(i) for i in result) > 80 else ','
            proto.options[self.name].as_string = sep.join(result)
    value: List = property(get_value, set_value)

class PyExprOption(Option[PyExpr]):
    """String configuration option with Python expression value.

Arguments:
    name: Option name.
    description: Option description. Can span multiple lines.
    required: True if option must have a value.
    default: Default option value.
"""
    def __init__(self, name: str, description: str, *, required: bool=False, default: PyExpr=None):
        self._value: PyExpr = None
        super().__init__(name, PyExpr, description, required, default)
    def clear(self, to_default: bool=True) -> None:
        """Clears the option value.

Arguments:
    to_default: If True, sets the option value to default value, else to None.
"""
        self._value = self.default if to_default else None
    def get_formatted(self) -> str:
        """Return value formatted for use in config file."""
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
        """Return value as string."""
        return self._value
    def get_value(self) -> PyExpr:
        "Return current option value"
        return self._value
    def set_value(self, value: PyExpr) -> None:
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
    value: PyExpr = property(get_value, set_value)

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
    def __init__(self, name: str, description: str, *, required: bool=False, default: PyCode=None):
        self._value: PyCode = None
        super().__init__(name, PyCode, description, required, default)
    def clear(self, to_default: bool=True) -> None:
        """Clears the option value.

Arguments:
    to_default: If True, sets the option value to default value, else to None.
"""
        self._value = self.default if to_default else None
    def get_formatted(self) -> str:
        """Return value formatted for use in config file."""
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
        """Return value as string."""
        return self._value
    def get_value(self) -> PyCode:
        "Return current option value"
        return self._value
    def set_value(self, value: PyCode) -> None:
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
    value: PyCode = property(get_value, set_value)

class PyCallableOption(Option[PyCallable]):
    """String configuration option with Python callable value.

Arguments:
    name: Option name.
    description: Option description. Can span multiple lines.
    signature: Callable signature.
    required: True if option must have a value.
    default: Default option value.

Attributes:
    signature (inspect.Signature): Callable signature.

Important:
    Python code must be properly indented, but `ConfigParser` multiline string values have
    leading whitespace removed. To circumvent this, the `PyCodeOption` supports assignment
    of text values where lines start with `|` character. This character is removed, along
    with any number of subsequent whitespace characters that are between `|` and first
    non-whitespace character on first line starting with `|`.
"""
    def __init__(self, name: str, description: str, signature: Signature, * ,
                 required: bool=False, default: PyCallable=None):
        self._value: PyCallable = None
        self.signature: Signature = signature
        super().__init__(name, PyCallable, description, required=required, default=default)
    def clear(self, to_default: bool=True) -> None:
        """Clears the option value.

Arguments:
    to_default: If True, sets the option value to default value, else to None.
"""
        self._value = self.default if to_default else None
    def get_formatted(self) -> str:
        """Return value formatted for use in config file."""
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
        """Return value as string."""
        return self._value
    def get_value(self) -> PyCallable:
        "Return current option value"
        return self._value
    def set_value(self, value: PyCallable) -> None:
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
    value: PyCallable = property(get_value, set_value)

class ConfigOption(Option[str]):
    """Configuration option with `Config` value.

Important:
    This option is intended for sub-configs that should have *configurable* name (i.e. the
    section name that holds sub-config values). To create sub-configs with fixed section
    names, simply assign them to instance attributes of `Config` instance that owns them
    (preferably in constructor).

    While the `value` attribute for this option is an instance of any class inherited from
    `Config`, in other ways it behaves like `StrOption` that loads/saves only name of its
    `Config` value (i.e. the section name). The actual I/O for sub-config's options is
    delegated to `Config` instance that owns this option.

    The "empty" value for this option is not `None` (because the `Config` instance always
    exists), but an empty string for `Config.name` attribute.

Arguments:
    name: Option name.
    description: Option description. Can span multiple lines.
    config: Option's value.
    required: True if option must have a value.
    default: Default `Config.name` value.
"""
    def __init__(self, name: str, description: str, config: Config, *, required: bool=False,
                 default: str=None):
        assert isinstance(config, Config)
        self._value: Config = config
        super().__init__(name, str, description, required, default)
    def validate(self) -> None:
        """Validates option state.

Raises:
    Error: When required option does not have a value.
"""
        if self.required and self.get_value().name == '':
            raise Error(f"Missing value for required option '{self.name}'")
    def clear(self, to_default: bool=True) -> None:
        """Clears the option value.

Note:
   This method calls `~Config.clear(to_default)`.

Arguments:
    to_default: If True, sets the `Config.name` to default value, else to empty string.
"""
        self._value.clear(to_default)
        self._value.name = self.default if to_default else ''
    def get_formatted(self) -> str:
        """Return value formatted for use in config file.

The string contains section name that will be used to store the `Config` values.
"""
        return self._value.name
    def set_as_str(self, value: str) -> None:
        """Set new option value from string.

Important:
    Because the actual value is a `Config` instance, the string must contain the
    `Config.name` value (which is the section name used to store `Config` options).
    Beware that multiple Config instances with the same (section) name may cause
    collision when configuration is written to protobuf message or configuration file.

Arguments:
    value: New `Config.name` value.
"""
        self._value.name = value
    def get_as_str(self) -> str:
        """Return value as string.

Important:
    Because the actual value is a `Config` instance, the returned string is the section
    name used to store `Config` options.
"""
        return self._value.name
    def get_value(self) -> Config:
        "Return current option value."
        return self._value
    def set_value(self, value: str) -> None:
        """Set new option value.

This option type does not support direct assignment of `Config` value. Because this method
is also used to assign default value (which is a `Config.name`), it accepts None or string
argument that is interpreted as new Config name. `None` value is translated to empty string.

Arguments:
    value: New `Config` name.

Raises:
    TypeError: When the new value is of the wrong type.
    ValueError: When None or empty string is passed and option value is required.
"""
        if value is None:
            value = ''
        if value == '' and self.required:
            raise ValueError(f"Value is required for option '{self.name}'.")
        self._value.name = value
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
            proto.options[self.name].as_string = self._value.name
    value: Config = property(get_value, set_value)

class ConfigListOption(Option[List]):
    """Configuration option with list of `Config` values.

Important:
    This option is intended for configurable set of sub-configs of fixed type.

    While the `value` attribute for this option is a list of instances of single class
    inherited from `Config`, in other ways it behaves like `ListOption` with `str` items
    that loads/saves only names of its `Config` items (i.e. the section names). The actual
    I/O for sub-config options is delegated to `Config` instance that owns this option.

Arguments:
    name:        Option name.
    description: Option description. Can span multiple lines.
    item_type:   Datatype of list items. Must be subclass of `Config`.
    required:    True if option must have a value.
    separator:   String that separates values when options value is read from `ConfigParser`.
                 It's possible to use a line break as separator.
                 If separator is `None` [default] and the value contains line breaks, it uses
                 the line break as separator, otherwise it uses comma as separator.

Attributes:
    item_type:   Datatype of list items.
    separator:   String that separates values when options value is read from `ConfigParser`.
                 Default separator is None. It's possible to use a line break as separator.
                 If separator is `None` and the value contains line breaks, it uses
                 the line break as separator, otherwise it uses comma as separator.

Important:
    When option is read from `ConfigParser`, empty values are ignored.
"""
    def __init__(self, name: str, description: str, item_type: Type[Config], *,
                 required: bool=False, separator: str=None):
        assert issubclass(item_type, Config)
        self._value: List = []
        self.item_type: Type[Config] = item_type
        self.separator: Optional[str] = separator
        super().__init__(name, list, description, required, [])
    def clear(self, to_default: bool=True) -> None:
        """Clears the option value.

Arguments:
    to_default: If True, sets the option value to default value, else to None.
"""
        self._value = []
    def get_formatted(self) -> str:
        """Return value formatted for use in config file."""
        if self._value is None:
            return '<UNDEFINED>'
        result = [i.name for i in self._value]
        sep = self.separator
        if sep is None:
            sep = '\n' if sum(len(i) for i in result) > 80 else ','
        if sep == '\n':
            x = '\n   '
            return f"\n   {x.join(result)}"
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
            for item in (i for i in value.split(separator) if i.strip()):
                new.append(self.item_type(item.strip()))
            self._value = new
    def get_as_str(self) -> str:
        """Return value as string."""
        result = [i.name for i in self._value]
        sep = self.separator
        if sep is None:
            sep = '\n' if sum(len(i) for i in result) > 80 else ','
        return sep.join(result)
    def get_value(self) -> List:
        "Return current option value"
        return self._value
    def set_value(self, value: List) -> None:
        """Set new option value.

Arguments:
    value: New option value.

Raises:
    TypeError: When the new value is of the wrong type.
    ValueError: When the argument is not a valid option value.
"""
        self._check_value(value)
        if value is not None:
            i = 0
            for item in value:
                if item.__class__ is not self.item_type:
                    raise ValueError(f"List item[{i}] has wrong type")
                i += 1
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
        result = [i.name for i in self._value]
        sep = self.separator
        if sep is None:
            sep = '\n' if sum(len(i) for i in result) > 80 else ','
        proto.options[self.name].as_string = sep.join(result)
    value: List = property(get_value, set_value)

class DataclassOption(Option[Any]):
    """Configuration option with a dataclass value.

The `ConfigParser` format for this option is a list of values, where each list items
defines value for dataclass field in `field_name:value_as_str` format. The configuration
must contain values for all fields for the dataclass that does not have default value.

Important:
    This option uses type annotation for dataclass to determine the actual data type for
    conversion from string. It means that:

    1. If type annotation contains "typing" types, it's necessary to specify "real" types
       for all dataclass fields using the `fields` argument.
    2. All used data types must have string convertors registered in `strconv` module.

Arguments:
    name:        Option name.
    dataclass:   Dataclass type.
    description: Option description. Can span multiple lines.
    required:    True if option must have a value.
    default:     Default option value.
    separator:   String that separates dataclass field values when options value is read
                 from `ConfigParser`. It's possible to use a line break as separator.
                 If separator is `None` [default] and the value contains line breaks, it
                 uses the line break as separator, otherwise it uses comma as separator.
    fields:      Dictionary that maps dataclass field names to data types.

Attributes:
    dataclass:   Dataclass type.
    separator:   String that separates dataclass field values when options value is read
                 from `ConfigParser`. Default separator is None. It's possible to use a line
                 break as separator. If separator is `None` and the value contains line
                 breaks, it uses the line break as separator, otherwise it uses comma as
                 separator.

Important:
    When option is read from `ConfigParser`, empty values are ignored.
"""
    def __init__(self, name: str, dataclass: Type, description: str, *, required: bool=False,
                 default: Any=None, separator: str=None, fields: Dict[str, Type]=None):
        assert hasattr(dataclass, '__dataclass_fields__')
        self._fields: Dict[str, Type] = get_type_hints(dataclass) if fields is None else fields
        if __debug__:
            for ftype in self._fields.values():
                assert get_convertor(ftype) is not None
        self._value: Any = None
        self.dataclass: Type = dataclass
        self.separator: Optional[str] = separator
        super().__init__(name, dataclass, description, required, default)
    def _get_str_fields(self) -> List[str]:
        result = []
        if self._value is not None:
            for fname in self._fields:
                result.append(f'{fname}:{convert_to_str(getattr(self._value, fname))}')
        return result
    def clear(self, to_default: bool=True) -> None:
        """Clears the option value.

Arguments:
    to_default: If True, sets the option value to default value, else to None.
"""
        self._value = self.default if to_default else None
    def get_formatted(self) -> str:
        """Return value formatted for use in config file."""
        if self._value is None:
            return '<UNDEFINED>'
        result = self._get_str_fields()
        sep = self.separator
        if sep is None:
            sep = '\n' if sum(len(i) for i in result) > 80 else ','
        if sep == '\n':
            x = '\n   '
            return f"\n   {x.join(result)}"
        return f'{sep} '.join(result)
    def set_as_str(self, value: str) -> None:
        """Set new option value from string.

Arguments:
    value: New option value.

Raises:
    ValueError: When the argument is not a valid option value.
"""
        new = {}
        if value.strip():
            separator = ('\n' if '\n' in value else ',') if self.separator is None else self.separator
            for item in (i for i in value.split(separator) if i.strip()):
                try:
                    field_name, field_value = item.split(':', 1)
                except Exception:
                    raise ValueError(f"Illegal value '{value}' for option '{self.name}'")
                field_name = field_name.strip()
                ftype = self._fields.get(field_name)
                if ftype is None:
                    raise ValueError(f"Unknown data field '{field_name}' for option '{self.name}'")
                convertor = get_convertor(ftype)
                new[field_name] = convertor.from_str(ftype, field_value.strip())
                try:
                    new_val = self.dataclass(**new)
                except Exception:
                    raise ValueError(f"Illegal value '{value}' for option '{self.name}'")
            self._value = new_val
    def get_as_str(self) -> str:
        """Return value as string."""
        result = self._get_str_fields()
        sep = self.separator
        if sep is None:
            sep = '\n' if sum(len(i) for i in result) > 80 else ','
        return sep.join(result)
    def get_value(self) -> Any:
        "Return current option value"
        return self._value
    def set_value(self, value: Any) -> None:
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
            result = self._get_str_fields()
            sep = self.separator
            if sep is None:
                sep = '\n' if sum(len(i) for i in result) > 80 else ','
            proto.options[self.name].as_string = sep.join(result)
    value: Any = property(get_value, set_value)

