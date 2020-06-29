#coding:utf-8
#
# PROGRAM/MODULE: firebird-base
# FILE:           firebird/base/buffer.py
# DESCRIPTION:    Memory buffer manager
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
# Copyright (c) 2020 Firebird Project (www.firebirdsql.org)
# All Rights Reserved.
#
# Contributor(s): Pavel Císař (original code)
#                 ______________________________________

"""Firebird Base - Memory buffer manager

This module provides a raw memory buffer manager with convenient methods to read/write
data of various data type.
"""

from __future__ import annotations
from typing import runtime_checkable, Protocol, Type, Union, Any
from ctypes import memset, create_string_buffer
from .types import Sentinel, UNLIMITED, ByteOrder

@runtime_checkable
class BufferFactory(Protocol): # pragma: no cover
    "BufferFactory Protocol definition"
    def create(self, init_or_size: Union[int, bytes], size: int = None) -> Any:
        """This function must create and return a mutable character buffer.

Arguments:
    init_or_size: Must be an integer which specifies the size of the array, or a bytes
        object which will be used to initialize the array items.
    size: Size of the array.
"""
    def clear(self, buffer: Any) -> None:
        """Fills the buffer with zero.

Argument:
    buffer: A memory buffer previously created by `BufferFactory.create()` method.
"""

class BytesBufferFactory:
    """Buffer factory for `bytearray` buffers."""
    def create(self, init_or_size: Union[int, bytes], size: int = None) -> bytearray:
        """This function creates a mutable character buffer. The returned object is a `bytearray`.

    Arguments:
        init_or_size: Must be an integer which specifies the size of the array, or a bytes
            object which will be used to initialize the array items.
        size: Size of the array.

    Important:
        Although arguments are the same as for `ctypes.create_string_buffer`, the behavior
        is different when new buffer is initialized from bytes:

        1. If there are more bytes than specified `size`, this function copies only `size`
           bytes into new buffer. The `~ctypes.create_string_buffer` raises an excpetion.
        2. Unlike `~ctypes.create_string_buffer` when `size` is NOT specified, the buffer
           is NOT made one item larger than its length so that the last element in the array
           is a NUL termination character.
    """
        if isinstance(init_or_size, int):
            return bytearray(init_or_size)
        size = len(init_or_size) if size is None else size
        buffer = bytearray(size)
        limit = min(len(init_or_size), size)
        buffer[:limit] = init_or_size[:limit]
        return buffer
    def clear(self, buffer: bytearray) -> None:
        "Fills the buffer with zero"
        buffer[:] = b'\x00' * len(buffer)

class CTypesBufferFactory:
    """Buffer factory for `ctypes` array of `~ctypes.c_char` buffers."""
    def create(self, init_or_size: Union[int, bytes], size: int = None) -> bytearray:
        """This function creates a `ctypes` mutable character buffer. The returned object
is an array of `ctypes.c_char`.

Arguments:
    init_or_size: Must be an integer which specifies the size of the array, or a bytes
        object which will be used to initialize the array items.
    size: Size of the array.

Important:
    Although arguments are the same as for `ctypes.create_string_buffer`, the behavior
    is different when new buffer is initialized from bytes:

    1. If there are more bytes than specified `size`, this function copies only `size`
       bytes into new buffer. The `~ctypes.create_string_buffer` raises an excpetion.
    2. Unlike `~ctypes.create_string_buffer` when `size` is NOT specified, the buffer is NOT
       made one item larger than its length so that the last element in the array is a
       NUL termination character.
"""
        if isinstance(init_or_size, int):
            return create_string_buffer(init_or_size)
        size = len(init_or_size) if size is None else size
        buffer = create_string_buffer(size)
        limit = min(len(init_or_size), size)
        buffer[:limit] = init_or_size[:limit]
        return buffer
    def clear(self, buffer: bytearray, init: int=0) -> None:
        "Fills the buffer with specified value (default)"
        memset(buffer, init, len(buffer))

def safe_ord(byte: Union[bytes, int]) -> int:
    """If `byte` argument is byte character, returns ord(byte), otherwise returns argument."""
    return byte if isinstance(byte, int) else ord(byte)

class MemoryBuffer:
    """Generic memory buffer manager.

Arguments:
    init: Must be an integer which specifies the size of the array, or a `bytes` object
          which will be used to initialize the array items.
    size: Size of the array. The argument value is used only when `init` is a `bytes` object.
    factory: Factory object used to create/resize the internal memory buffer.
    eof_marker: Value that indicates the end of data. Could be None.
    max_size: If specified, the buffer couldn't grow beyond specified number of bytes.
    byteorder: The byte order used to read/write numbers.

Attributes:
    raw: The memory buffer. The actual data type of buffer depends on `buffer factory`, but
         it must provide direct acces to cells, slices and length like `bytearray`.
    pos (int): Current position in buffer, i.e. the next read/writen byte would be at this position.
    factory (BufferFactory): Buffer factory instance used by manager [default: `BytesBufferFactory`].
    eof_marker (int): Value that indicates the end of data. Could be None.
    max_size (int or `.UNLIMITED`): The buffer couldn't grow beyond specified number of bytes
      [default: `.UNLIMITED`].
    byteorder (ByteOrder): The byte order used to read/write numbers [default: `.LITTLE`].
"""
    def __init__(self, init: Union[int, bytes], size: int = None, *,
                 factory: Type[BufferFactory]=BytesBufferFactory, eof_marker: int=None,
                 max_size: Union[int, Sentinel]=UNLIMITED, byteorder: ByteOrder=ByteOrder.LITTLE):
        self.factory: BufferFactory = factory()
        self.raw: bytearray = self.factory.create(init, size)
        self.pos: int = 0
        self.eof_marker: int = eof_marker
        self.max_size: Union[int, Sentinel] = max_size
        self.byteorder: ByteOrder = byteorder
    def _ensure_space(self, size: int) -> None:
        if len(self.raw) < self.pos + size:
            self.resize(self.pos + size)
    def _check_space(self, size: int):
        if len(self.raw) < self.pos + size:
            raise IOError("Insufficient buffer size")
    def clear(self) -> None:
        "Fills the buffer with zeros and resets the position in buffer to zero."
        self.factory.clear(self.raw)
        self.pos = 0
    def resize(self, size: int) -> None:
        "Resize buffer to specified length."
        if self.max_size is not UNLIMITED and self.max_size < size:
            raise IOError(f"Cannot resize buffer past max. size {self.max_size} bytes")
        self.raw = self.factory.create(self.raw, size)
    def is_eof(self) -> bool:
        "Return True when positioned past the end of buffer or on `.eof_marker` (if defined)"
        if self.pos >= len(self.raw):
            return True
        if self.eof_marker is not None and safe_ord(self.raw[self.pos]) == self.eof_marker:
            return True
        return False
    def write(self, data: bytes) -> None:
        "Write bytes"
        size = len(data)
        self._ensure_space(size)
        self.raw[self.pos:self.pos + size] = data
        self.pos += size
    def write_byte(self, byte: int) -> None:
        "Write byte"
        self._ensure_space(1)
        self.raw[self.pos] = byte
        self.pos += 1
    def write_number(self, value: int, size: int, *, signed: bool=False) -> None:
        "Write number with specified size in bytes"
        self.write(value.to_bytes(size, self.byteorder.value, signed=signed))
    def write_short(self, value: int) -> None:
        "Write 2 byte number (c_ushort)"
        self.write_number(value, 2)
    def write_int(self, value: int) -> None:
        "Write 4 byte number (c_uint)"
        self.write_number(value, 4)
    def write_bigint(self, value: int) -> None:
        "Write tagged 8 byte number (c_ulonglong)"
        self.write_number(value, 8)
    def write_string(self, value: str, *, encoding='ascii') -> None:
        "Write zero-terminated string"
        self.write(value.encode(encoding))
        self.write_byte(0)
    def write_pascal_string(self, value: str, *, encoding='ascii') -> None:
        "Write tagged Pascal string (2 byte length followed by data)"
        value = value.encode(encoding)
        size = len(value)
        self.write_byte(size)
        self.write(value)
    def read(self, size: int=-1) -> bytes:
        "Reads specified number of bytes, or all remaining data."
        if size < 0:
            size = self.buffer_size - self.pos
        self._check_space(size)
        result = self.raw[self.pos: self.pos + size]
        self.pos += size
        return result
    def read_number(self, size: int, *, signed=False) -> int:
        "Read number with specified size in bytes"
        self._check_space(size)
        result = (0).from_bytes(self.raw[self.pos: self.pos + size], self.byteorder.value, signed=signed)
        self.pos += size
        return result
    def read_byte(self, *, signed=False) -> int:
        "Read 1 byte number (c_ubyte)"
        return self.read_number(1, signed=signed)
    def read_short(self, *, signed=False) -> int:
        "Read 2 byte number (c_ushort)"
        return self.read_number(2, signed=signed)
    def read_int(self, *, signed=False) -> int:
        "Read 4 byte number (c_uint)"
        return self.read_number(4, signed=signed)
    def read_bigint(self, *, signed=False) -> int:
        "Read 8 byte number (c_ulonglong)"
        return self.read_number(8, signed=signed)
    def read_sized_int(self, *, signed=False) -> int:
        "Read number cluster (2 byte length followed by data)"
        return self.read_number(self.read_short(), signed=signed)
    def read_string(self, *, encoding='ascii') -> str:
        "Read null-terminated string"
        i = self.pos
        while i < self.buffer_size and safe_ord(self.raw[i]) != 0:
            i += 1
        result = self.read(i - self.pos).decode(encoding)
        self.pos += 1
        return result
    def read_pascal_string(self, *, encoding='ascii') -> str:
        "Read Pascal string (1 byte length followed by string data)"
        return self.read(self.read_byte()).decode(encoding)
    def read_sized_string(self, *, encoding='ascii') -> str:
        "Read string (2 byte length followed by data)"
        return self.read(self.read_short()).decode(encoding)
    def read_bytes(self) -> bytes:
        "Read content of binary cluster (2 bytes data length followed by data)"
        return self.read(self.read_short())
    # Properties
    @property
    def buffer_size(self) -> int:
        "Current buffer size in bytes."
        return len(self.raw)
    @property
    def last_data(self) -> int:
        "Index of first non-zero byte when searched from the end of buffer."
        i = len(self.raw) - 1
        while i >= 0:
            if safe_ord(self.raw[i]) != 0:
                break
            i -= 1
        return i
