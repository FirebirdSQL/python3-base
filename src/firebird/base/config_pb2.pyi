from google.protobuf import any_pb2 as _any_pb2
from google.protobuf import struct_pb2 as _struct_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Mapping as _Mapping, Optional as _Optional, Union as _Union

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
    def __init__(self, as_string: _Optional[str] = ..., as_bytes: _Optional[bytes] = ..., as_bool: bool = ..., as_double: _Optional[float] = ..., as_float: _Optional[float] = ..., as_sint32: _Optional[int] = ..., as_sint64: _Optional[int] = ..., as_uint32: _Optional[int] = ..., as_uint64: _Optional[int] = ..., as_msg: _Optional[_Union[_any_pb2.Any, _Mapping]] = ...) -> None: ...

class ConfigProto(_message.Message):
    __slots__ = ("options", "configs")
    class OptionsEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: str
        value: Value
        def __init__(self, key: _Optional[str] = ..., value: _Optional[_Union[Value, _Mapping]] = ...) -> None: ...
    class ConfigsEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: str
        value: ConfigProto
        def __init__(self, key: _Optional[str] = ..., value: _Optional[_Union[ConfigProto, _Mapping]] = ...) -> None: ...
    OPTIONS_FIELD_NUMBER: _ClassVar[int]
    CONFIGS_FIELD_NUMBER: _ClassVar[int]
    options: _containers.MessageMap[str, Value]
    configs: _containers.MessageMap[str, ConfigProto]
    def __init__(self, options: _Optional[_Mapping[str, Value]] = ..., configs: _Optional[_Mapping[str, ConfigProto]] = ...) -> None: ...
