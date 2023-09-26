from google.protobuf import any_pb2 as _any_pb2
from google.protobuf import struct_pb2 as _struct_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Iterable as _Iterable, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class TestEnum(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = []
    TEST_UNKNOWN: _ClassVar[TestEnum]
    TEST_READY: _ClassVar[TestEnum]
    TEST_RUNNING: _ClassVar[TestEnum]
    TEST_WAITING: _ClassVar[TestEnum]
    TEST_SUSPENDED: _ClassVar[TestEnum]
    TEST_FINISHED: _ClassVar[TestEnum]
    TEST_ABORTED: _ClassVar[TestEnum]
    TEST_CREATED: _ClassVar[TestEnum]
    TEST_BLOCKED: _ClassVar[TestEnum]
    TEST_STOPPED: _ClassVar[TestEnum]
    TEST_TERMINATED: _ClassVar[TestEnum]
TEST_UNKNOWN: TestEnum
TEST_READY: TestEnum
TEST_RUNNING: TestEnum
TEST_WAITING: TestEnum
TEST_SUSPENDED: TestEnum
TEST_FINISHED: TestEnum
TEST_ABORTED: TestEnum
TEST_CREATED: TestEnum
TEST_BLOCKED: TestEnum
TEST_STOPPED: TestEnum
TEST_TERMINATED: TestEnum

class TestState(_message.Message):
    __slots__ = ["name", "test"]
    NAME_FIELD_NUMBER: _ClassVar[int]
    TEST_FIELD_NUMBER: _ClassVar[int]
    name: str
    test: TestEnum
    def __init__(self, name: _Optional[str] = ..., test: _Optional[_Union[TestEnum, str]] = ...) -> None: ...

class TestCollection(_message.Message):
    __slots__ = ["name", "tests", "context", "annotation", "supplement"]
    NAME_FIELD_NUMBER: _ClassVar[int]
    TESTS_FIELD_NUMBER: _ClassVar[int]
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    ANNOTATION_FIELD_NUMBER: _ClassVar[int]
    SUPPLEMENT_FIELD_NUMBER: _ClassVar[int]
    name: str
    tests: _containers.RepeatedCompositeFieldContainer[TestState]
    context: _struct_pb2.Struct
    annotation: _struct_pb2.Struct
    supplement: _containers.RepeatedCompositeFieldContainer[_any_pb2.Any]
    def __init__(self, name: _Optional[str] = ..., tests: _Optional[_Iterable[_Union[TestState, _Mapping]]] = ..., context: _Optional[_Union[_struct_pb2.Struct, _Mapping]] = ..., annotation: _Optional[_Union[_struct_pb2.Struct, _Mapping]] = ..., supplement: _Optional[_Iterable[_Union[_any_pb2.Any, _Mapping]]] = ...) -> None: ...
