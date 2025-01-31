from collections.abc import Mapping as _Mapping
from typing import ClassVar as _ClassVar
from typing import Optional as _Optional
from typing import Union as _Union

from google.protobuf import any_pb2 as _any_pb2
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from google.protobuf import struct_pb2 as _struct_pb2
from google.protobuf.internal import containers as _containers

DESCRIPTOR: _descriptor.FileDescriptor

class Value(_message.Message):
    __slots__ = ("as_string", "as_bytes", "as_bool", "as_double", "as_float", "as_sint32", "as_sint64", "as_uint32", "as_uint64", "as_msg")
    AS_STRING_FIELD_NUMBER: _ClassVar[int]
    AS_BYTES_FIELD_NUMBER: _ClassVar[int]
    AS_BOOL_FIELD_NUMBER: _ClassVar[int]
    AS_DOUBLE_FIELD_NUMBER: _ClassVar[int]
    AS_FLOAT_FIELD_NUMBER: _ClassVar[int]
    AS_SINT32_FIELD_NUMBER: _ClassVar[int]
    AS_SINT64_FIELD_NUMBER: _ClassVar[int]
    AS_UINT32_FIELD_NUMBER: _ClassVar[int]
    AS_UINT64_FIELD_NUMBER: _ClassVar[int]
    AS_MSG_FIELD_NUMBER: _ClassVar[int]
    as_string: str
    as_bytes: bytes
    as_bool: bool
    as_double: float
    as_float: float
    as_sint32: int
    as_sint64: int
    as_uint32: int
    as_uint64: int
    as_msg: _any_pb2.Any
    def __init__(self, as_string: str | None = ..., as_bytes: bytes | None = ..., as_bool: bool = ..., as_double: float | None = ..., as_float: float | None = ..., as_sint32: int | None = ..., as_sint64: int | None = ..., as_uint32: int | None = ..., as_uint64: int | None = ..., as_msg: _any_pb2.Any | _Mapping | None = ...) -> None: ...

class ConfigProto(_message.Message):
    __slots__ = ("options", "configs")
    class OptionsEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: str
        value: Value
        def __init__(self, key: str | None = ..., value: Value | _Mapping | None = ...) -> None: ...
    class ConfigsEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: str
        value: ConfigProto
        def __init__(self, key: str | None = ..., value: ConfigProto | _Mapping | None = ...) -> None: ...
    OPTIONS_FIELD_NUMBER: _ClassVar[int]
    CONFIGS_FIELD_NUMBER: _ClassVar[int]
    options: _containers.MessageMap[str, Value]
    configs: _containers.MessageMap[str, ConfigProto]
    def __init__(self, options: _Mapping[str, Value] | None = ..., configs: _Mapping[str, ConfigProto] | None = ...) -> None: ...
