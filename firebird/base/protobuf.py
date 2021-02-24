#coding:utf-8
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
"""

from __future__ import annotations
from typing import Dict, Any, Callable, cast
from dataclasses import dataclass
from pkg_resources import iter_entry_points
from google.protobuf.message import Message as ProtoMessage
from google.protobuf.descriptor import EnumDescriptor
from google.protobuf.struct_pb2 import Struct as StructProto
from google.protobuf import json_format, struct_pb2, any_pb2, duration_pb2, empty_pb2, \
     timestamp_pb2, field_mask_pb2
from .types import Distinct
from .collections import Registry

PROTO_EMPTY = 'google.protobuf.Empty'
PROTO_ANY = 'google.protobuf.Any'
PROTO_DURATION = 'google.protobuf.Duration'
PROTO_TIMESTAMP = 'google.protobuf.Timestamp'
PROTO_STRUCT = 'google.protobuf.Struct'
PROTO_VALUE = 'google.protobuf.Value'
PROTO_LISTVALUE = 'google.protobuf.ListValue'
PROTO_FIELDMASK = 'google.protobuf.FieldMask'

# Classes
@dataclass(eq=True, order=True, frozen=True)
class ProtoMessageType(Distinct):
    """Google protobuf message type.
    """
    name: str
    constructor: Callable
    def get_key(self) -> Any:
        """Returns `name`.
        """
        return self.name

@dataclass(eq=True, order=True, frozen=True)
class ProtoEnumType(Distinct):
    """Google protobuf enum type
    """
    descriptor: EnumDescriptor
    def get_key(self) -> Any:
        """Returns `name`.
        """
        return self.name
    def __getattr__(self, name):
        """Returns the value corresponding to the given enum name."""
        if name in self.descriptor.values_by_name:
            return self.descriptor.values_by_name[name].number
        raise AttributeError(f"Enum {self.name} has no value with name '{name}'")
    def keys(self):
        """Return a list of the string names in the enum.

        These are returned in the order they were defined in the .proto file.
        """
        return [value_descriptor.name for value_descriptor in self.descriptor.values]
    def values(self):
        """Return a list of the integer values in the enum.

        These are returned in the order they were defined in the .proto file.
        """
        return [value_descriptor.number for value_descriptor in self.descriptor.values]
    def items(self):
        """Return a list of the (name, value) pairs of the enum.

        These are returned in the order they were defined in the .proto file.
        """
        return [(value_descriptor.name, value_descriptor.number)
                for value_descriptor in self.descriptor.values]
    def get_value_name(self, number: int) -> str:
        """Returns a string containing the name of an enum value.

        Raises:
            KeyError: If there is no value for specified name.
        """
        if number in self.descriptor.values_by_number:
            return self.descriptor.values_by_number[number].name
        raise KeyError(f"Enum {self.name} has no name defined for value {number}")
    @property
    def name(self) -> str:
        """Full enum type name.
        """
        return self.descriptor.full_name

_msgreg: Registry = Registry()
_enumreg: Registry = Registry()

def struct2dict(struct: StructProto) -> Dict:
    """Unpacks `google.protobuf.Struct` message to Python dict value.
    """
    return json_format.MessageToDict(struct)

def dict2struct(value: Dict) -> StructProto:
    """Returns dict packed into `google.protobuf.Struct` message.
    """
    struct = StructProto()
    struct.update(value)
    return struct

def create_message(name: str, serialized: bytes = None) -> ProtoMessage:
    """Returns new protobuf message instance.

    Arguments:
        name: Fully qualified protobuf message name.
        serialized: Serialized message.

    Raises:
        KeyError: When message type is not registered.
        google.protobuf.message.DecodeError: When deserializations fails.
    """
    if (msg := _msgreg.get(name)) is None:
        raise KeyError(f"Unregistered protobuf message '{name}'")
    result = cast(ProtoMessageType, msg).constructor()
    if serialized is not None:
        result.ParseFromString(serialized)
    return result

def get_message_factory(name: str) -> Callable:
    """Returns callable that creates new protobuf messages of specified name.

    Arguments:
        name: Fully qualified protobuf message name.

    Raises:
        KeyError: When message type is not registered.
    """
    if (msg := _msgreg.get(name)) is None:
        raise KeyError(f"Unregistered protobuf message '{name}'")
    return cast(ProtoMessageType, msg).constructor

def is_msg_registered(name: str) -> bool:
    """Returns True if specified `name` refers to registered protobuf message type.
    """
    return name in _msgreg

def is_enum_registered(name: str) -> bool:
    """Returns True if specified `name` refers to registered protobuf enum type.
    """
    return name in _enumreg

def get_enum_type(name: str) -> ProtoEnumType:
    """Returns wrapper instance for protobuf enum type with specified `name`.

    Raises:
        KeyError: When enum type is not registered.
    """
    if (e := _enumreg.get(name)) is None:
        raise KeyError(f"Unregistered protobuf enum type '{name}'")
    return e

def get_enum_field_type(msg, field_name: str) -> str:
    """Returns name of enum type for message enum field.

    Raises:
        KeyError: When message does not have specified field.
    """
    if (fdesc := msg.DESCRIPTOR.fields_by_name.get(field_name)) is None:
        raise KeyError(f"Message does not have field '{field_name}'")
    return fdesc.enum_type.full_name

def get_enum_value_name(enum_type_name: str, value: int) -> str:
    """Returns name for the enum value.
    """
    return get_enum_type(enum_type_name).get_value_name(value)


def register_decriptor(file_descriptor) -> None:
    """Registers enums and messages defined by protobuf file DESCRIPTOR.
    """
    for msg_desc in file_descriptor.message_types_by_name.values():
        _msgreg.store(ProtoMessageType(msg_desc.full_name, msg_desc._concrete_class))
    for enum_desc in file_descriptor.enum_types_by_name.values():
        _enumreg.store(ProtoEnumType(enum_desc))

def load_registered(group: str) -> None: # pragma: no cover
    """Load registered protobuf packages.

    Protobuf packages must register the pb2-file DESCRIPTOR in `entry_points` section of
    `setup.cfg` file.

    Arguments:
        group: Entry-point group name.

    Example:
        ::

           # setup.cfg:

           [options.entry_points]
           firebird.base.protobuf =
               firebird.base.lib_a = firebird.base.lib_a_pb2:DESCRIPTOR
               firebird.base.lib_b = firebird.base.lib_b_pb2:DESCRIPTOR
               firebird.base.lib_c = firebird.base.lib_c_pb2:DESCRIPTOR

           # will be loaded with:

           load_registered('firebird.base.protobuf')
    """
    for desc in (entry.load() for entry in iter_entry_points(group)):
        register_decriptor(desc)


for well_known in [any_pb2, struct_pb2, duration_pb2, empty_pb2, timestamp_pb2, field_mask_pb2]:
    register_decriptor(well_known.DESCRIPTOR)
del any_pb2, struct_pb2, duration_pb2, empty_pb2, timestamp_pb2, field_mask_pb2
