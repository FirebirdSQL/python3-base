# SPDX-FileCopyrightText: 2019-present The Firebird Projects <www.firebirdsql.org>
#
# SPDX-License-Identifier: MIT
#
# PROGRAM/MODULE: firebird-base
# FILE:           firebird/base/protobuf.py
# DESCRIPTION:    Registry for Google Protocol Buffer messages and enums
# CREATED:        27.12.2019
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


"""Firebird Base - Registry for Google Protocol Buffer messages and enums

This module provides a central registry for Google Protocol Buffer message types
and enum types generated from `.proto` files. It allows creating message instances
and accessing enum information using their fully qualified names (e.g.,
"my.package.MyMessage", "my.package.MyEnum") without needing to directly import
the corresponding generated `_pb2.py` modules throughout the codebase.

Benefits:
*   Decouples code using protobuf messages from the specific generated modules.
*   Provides a single point for managing and discovering available message/enum types.
*   Facilitates dynamic loading of protobuf definitions via entry points.

Core Features:
*   Register message/enum types using their file DESCRIPTOR object.
*   Create new message instances by name using `create_message()`.
*   Access enum descriptors and values by name using `get_enum_type()`.
*   Load protobuf definitions registered by other installed packages via entry points
    using `load_registered()`.
*   Helpers for common types like `google.protobuf.Struct`.

Example:
    # Assume you have my_proto_pb2.py generated from my_proto.proto
    # containing:
    # message Sample { required string name = 1; }
    # enum Status { UNKNOWN = 0; OK = 1; ERROR = 2; }

    from firebird.base.protobuf import (
        register_descriptor, create_message, get_enum_type, is_msg_registered
    )
    # Import the generated descriptor (only needed once, e.g., at startup)
    try:
        from . import my_proto_pb2 # Replace with actual import path
        HAS_MY_PROTO = True
    except ImportError:
        HAS_MY_PROTO = False

    # 1. Register the types from the descriptor
    if HAS_MY_PROTO:
        register_descriptor(my_proto_pb2.DESCRIPTOR)
        print(f"Is 'my_proto.Sample' registered? {is_msg_registered('my_proto.Sample')}")

    # 2. Create a message instance by name
    if HAS_MY_PROTO:
        try:
            msg = create_message('my_proto.Sample')
            msg.name = "Example"
            print(f"Created message: {msg}")

            # 3. Access enum type and values by name
            status_enum = get_enum_type('my_proto.Status')
            print(f"Status enum name: {status_enum.name}")
            print(f"OK value: {status_enum.OK}") # Access like attribute
            print(f"Name for value 2: {status_enum.get_value_name(2)}") # Access via method
            print(f"Available status keys: {status_enum.keys()}")

        except KeyError as e:
            print(f"Error accessing registered proto type: {e}")

"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from importlib.metadata import entry_points
from typing import Any, cast

from google.protobuf import any_pb2, duration_pb2, empty_pb2, field_mask_pb2, json_format, struct_pb2, timestamp_pb2
from google.protobuf.descriptor import EnumDescriptor
from google.protobuf.message import Message as ProtoMessage
from google.protobuf.struct_pb2 import Struct as StructProto

from .collections import Registry
from .types import Distinct

#: Name of well-known EMPTY protobuf message (for use with `.create_message()`)
PROTO_EMPTY: str = 'google.protobuf.Empty'
#: Name of well-known ANY protobuf message (for use with `.create_message()`)
PROTO_ANY: str = 'google.protobuf.Any'
#: Name of well-known DURATION protobuf message (for use with `.create_message()`)
PROTO_DURATION: str = 'google.protobuf.Duration'
#: Name of well-known TIMESTAMP protobuf message (for use with `.create_message()`)
PROTO_TIMESTAMP: str = 'google.protobuf.Timestamp'
#: Name of well-known STRUCT protobuf message (for use with `.create_message()`)
PROTO_STRUCT: str = 'google.protobuf.Struct'
#: Name of well-known VALUE protobuf message (for use with `.create_message()`)
PROTO_VALUE: str = 'google.protobuf.Value'
#: Name of well-known LISTVALUE protobuf message (for use with `.create_message()`)
PROTO_LISTVALUE: str = 'google.protobuf.ListValue'
#: Name of well-known FIELDMASK protobuf message (for use with `.create_message()`)
PROTO_FIELDMASK: str = 'google.protobuf.FieldMask'

# Classes
@dataclass(eq=True, order=True, frozen=True)
class ProtoMessageType(Distinct):
    """Registry entry representing a registered Protocol Buffer message type.

    Stores the fully qualified name and the constructor (the generated class)
    for a message type, allowing instantiation via the registry.

    Arguments:
        name: Fully qualified message type name (e.g., "package.Message").
        constructor: The callable (generated message class) used to create instances.
    """
    #: Fully qualified message type name (e.g., "package.Message").
    name: str
    #: The callable (generated message class) used to create instances.
    constructor: Callable
    def get_key(self) -> str:
        """Returns the message name, used as the key in the registry."""
        return self.name

@dataclass(eq=True, order=True, frozen=True)
class ProtoEnumType(Distinct):
    """Registry entry providing access to a registered Protocol Buffer enum type.

    Wraps the `EnumDescriptor` and provides an API similar to generated enum
    types, allowing access to names and values without direct import of the
    generated `_pb2` module.

    Arguments:
        descriptor: The `google.protobuf.descriptor.EnumDescriptor` for the enum type.

    Example::

        # Assuming 'my_proto.Status' enum (UNKNOWN=0, OK=1) is registered
        status_enum = get_enum_type('my_proto.Status')

        print(status_enum.OK)              # Output: 1 (Access value by name)
        print(status_enum.get_value_name(1)) # Output: 'OK' (Get name by value)
        print(status_enum.keys())          # Output: ['UNKNOWN', 'OK']
        print(status_enum.values())        # Output: [0, 1]
        print(status_enum.items())         # Output: [('UNKNOWN', 0), ('OK', 1)]

        try:
            print(status_enum.NONEXISTENT)
        except AttributeError as e:
            print(e) # Output: Enum my_proto.Status has no value with name 'NONEXISTENT'

        try:
            print(status_enum.get_value_name(99))
        except KeyError as e:
            print(e) # Output: "Enum my_proto.Status has no name defined for value 99"
    """
    #: The `google.protobuf.descriptor.EnumDescriptor` for the enum type.
    descriptor: EnumDescriptor
    def get_key(self) -> str:
        """Returns the full enum name, used as the key in the registry."""
        return self.name
    def __getattr__(self, name: str):
        """Return the integer value corresponding to the enum member name `name`.

        Arguments:
            name: The string name of the enum member.

        Returns:
            The integer value of the enum member.

        Raises:
            AttributeError: If `name` is not a valid member name for this enum.
        """
        if name in self.descriptor.values_by_name:
            return self.descriptor.values_by_name[name].number
        raise AttributeError(f"Enum {self.name} has no value with name '{name}'")
    def keys(self) -> list[str]:
        """Return a list of the string names in the enum.

        These are returned in the order they were defined in the .proto file.
        """
        return [value_descriptor.name for value_descriptor in self.descriptor.values]
    def values(self) -> list[int]:
        """Return a list of the integer values in the enum.

        These are returned in the order they were defined in the .proto file.
        """
        return [value_descriptor.number for value_descriptor in self.descriptor.values]
    def items(self) -> list[tuple[str, int]]:
        """Return a list of the (name, value) pairs of the enum.

        These are returned in the order they were defined in the .proto file.
        """
        return [(value_descriptor.name, value_descriptor.number)
                for value_descriptor in self.descriptor.values]
    def get_value_name(self, number: int) -> str:
        """Return the string name corresponding to the enum member value `number`.

        Arguments:
            number: The integer value of the enum member.

        Returns:
            The string name of the enum member.

        Raises:
            KeyError: If there is no value for specified name.
        """
        if number in self.descriptor.values_by_number:
            return self.descriptor.values_by_number[number].name
        raise KeyError(f"Enum {self.name} has no name defined for value {number}")
    @property
    def name(self) -> str:
        """The fully qualified name of the enum type (e.g., "package.MyEnum")."""
        return self.descriptor.full_name

#: Internal registry storing ProtoMessageType instances.
_msgreg: Registry = Registry()
#: Internal registry storing ProtoEnumType instances.
_enumreg: Registry = Registry()

def struct2dict(struct: StructProto) -> dict[str, Any]:
    """Unpack a `google.protobuf.Struct` message into a Python dictionary.

    Uses `google.protobuf.json_format.MessageToDict`.

    Arguments:
        struct: The `Struct` message instance.

    Returns:
        A Python dictionary representing the struct's content.
    """
    return json_format.MessageToDict(struct)

def dict2struct(value: dict[str, Any]) -> StructProto:
    """Pack a Python dictionary into a `google.protobuf.Struct` message.

    Arguments:
        value: The Python dictionary.

    Returns:
        A `Struct` message instance containing the dictionary's data.
    """
    struct = StructProto()
    struct.update(value)
    return struct

def create_message(name: str, serialized: bytes | None=None) -> ProtoMessage:
    """Create a new instance of a registered protobuf message type by name.

    Optionally initializes the message by parsing serialized data.

    Arguments:
        name: Fully qualified name of the registered protobuf message type.
        serialized: Optional bytes containing the serialized message data.

    Returns:
        An instance of the requested protobuf message class.

    Raises:
        KeyError: If `name` does not correspond to a registered message type.
        google.protobuf.message.DecodeError: If `serialized` data is provided
            but cannot be parsed correctly for the message type.
    """
    if (msg := _msgreg.get(name)) is None:
        raise KeyError(f"Unregistered protobuf message '{name}'")
    result = cast(ProtoMessageType, msg).constructor()
    if serialized is not None:
        result.ParseFromString(serialized)
    return result

def get_message_factory(name: str) -> Callable:
    """Return the constructor (factory callable) for a registered message type.

    Allows creating multiple instances without repeated registry lookups.

    Arguments:
        name: Fully qualified name of the registered protobuf message type.

    Returns:
        The callable (message class) used to construct instances.

    Raises:
        KeyError: If `name` does not correspond to a registered message type.
    """
    if (msg := _msgreg.get(name)) is None:
        raise KeyError(f"Unregistered protobuf message '{name}'")
    return cast(ProtoMessageType, msg).constructor

def is_msg_registered(name: str) -> bool:
    """Check if a protobuf message type with the given name is registered.

    Arguments:
        name: Fully qualified message type name.

    Returns:
        True if registered, False otherwise.
    """
    return name in _msgreg

def is_enum_registered(name: str) -> bool:
    """Check if a protobuf enum type with the given name is registered.

    Arguments:
        name: Fully qualified enum type name.

    Returns:
        True if registered, False otherwise.
    """
    return name in _enumreg

def get_enum_type(name: str) -> ProtoEnumType:
    """Return the `ProtoEnumType` wrapper for a registered enum type by name.

    Provides access to enum members and values via the wrapper object.

    Arguments:
        Fully qualified name of the registered protobuf enum type.

    Returns:
        The `ProtoEnumType` instance for the requested enum.

    Raises:
        KeyError: If `name` does not correspond to a registered enum type.
    """
    if (e := _enumreg.get(name)) is None:
        raise KeyError(f"Unregistered protobuf enum type '{name}'")
    return e

def get_enum_field_type(msg, field_name: str) -> str:
    """Return the fully qualified name of the enum type for a message field.

    Arguments:
        msg: An *instance* of a protobuf message.
        field_name: The string name of the field within the message.

    Returns:
        The fully qualified name of the enum type used by the field.

    Raises:
        KeyError: If `msg` does not have a field named `field_name`.
        TypeError: If the specified field is not an enum field.
    """
    if (fdesc := msg.DESCRIPTOR.fields_by_name.get(field_name)) is None:
        raise KeyError(f"Message does not have field '{field_name}'")
    if fdesc.enum_type is None:
        raise TypeError(f"Field '{field_name}' in message type '{msg.DESCRIPTOR.full_name}' is not an enum field.")
    return fdesc.enum_type.full_name

def get_enum_value_name(enum_type_name: str, value: int) -> str:
    """Return the string name corresponding to a value within a registered enum type.

    Convenience function equivalent to `get_enum_type(enum_type_name).get_value_name(value)`.

    Arguments:
        enum_type_name: Fully qualified name of the registered enum type.
        value: The integer value of the enum member.

    Returns:
        The string name of the enum member.

    Raises:
        KeyError: If `enum_type_name` is not registered, or if `value` is not
                      defined within that enum.
    """
    return get_enum_type(enum_type_name).get_value_name(value)

def register_decriptor(file_descriptor) -> None:
    """Register all message and enum types defined within a protobuf file descriptor.

    This is the primary mechanism for adding types to the registry. The descriptor
    object is typically accessed as `DESCRIPTOR` from a generated `_pb2.py` module.

    Arguments:
        file_descriptor: The `google.protobuf.descriptor.FileDescriptor` object
                         (e.g., `my_proto_pb2.DESCRIPTOR`).
    """
    for msg_desc in file_descriptor.message_types_by_name.values():
        if msg_desc.full_name not in _msgreg:
            _msgreg.store(ProtoMessageType(msg_desc.full_name, msg_desc._concrete_class))
    for enum_desc in file_descriptor.enum_types_by_name.values():
        if enum_desc.full_name not in _enumreg:
            _enumreg.store(ProtoEnumType(enum_desc))

def load_registered(group: str) -> None: # pragma: no cover
    """Load and register protobuf types defined via package entry points.

    Searches for installed packages that register entry points under the specified
    `group`. Each entry point should load a `FileDescriptor` object. This allows
    packages to automatically make their protobuf types available to the registry
    upon installation.

    This function is typically called once during application initialization.

    Arguments:
        group: The name of the entry-point group to scan (e.g., 'firebird.base.protobuf').

    Example:
        ::

           # setup.cfg:

           [options.entry_points]
           firebird.base.protobuf =
               firebird.base.lib_a = firebird.base.lib_a_pb2:DESCRIPTOR
               firebird.base.lib_b = firebird.base.lib_b_pb2:DESCRIPTOR
               firebird.base.lib_c = firebird.base.lib_c_pb2:DESCRIPTOR

           # pyproject.toml

           [project.entry-points."firebird.base.protobuf"]
           "firebird.base.lib_a" = "firebird.base.lib_a_pb2:DESCRIPTOR"
           "firebird.base.lib_b" = "firebird.base.lib_b_pb2:DESCRIPTOR"
           "firebird.base.lib_c" = "firebird.base.lib_c_pb2:DESCRIPTOR"

    Usage::

         # In your application's startup code:
         load_registered('firebird.base.protobuf')
         # Now messages/enums registered via entry points are available
    """
    for desc in (entry.load() for entry in entry_points().get(group, [])):
        register_decriptor(desc)

for well_known in [any_pb2, struct_pb2, duration_pb2, empty_pb2, timestamp_pb2, field_mask_pb2]:
    register_decriptor(well_known.DESCRIPTOR)
del any_pb2, struct_pb2, duration_pb2, empty_pb2, timestamp_pb2, field_mask_pb2
