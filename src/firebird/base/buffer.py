# SPDX-FileCopyrightText: 2020-present The Firebird Projects <www.firebirdsql.org>
#
# SPDX-License-Identifier: MIT
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

This module provides a `MemoryBuffer` class for managing raw memory buffers,
offering a convenient and consistent API for reading and writing various data types
(integers of different sizes, strings with different termination/prefixing styles, raw bytes).
It's particularly useful for tasks involving binary data serialization/deserialization,
such as implementing network protocols or handling custom file formats.

The underlying memory storage can be customized via a `BufferFactory`. Two factories
are provided:
- `BytesBufferFactory`: Uses Python's built-in `bytearray`.
- `CTypesBufferFactory`: Uses `ctypes.create_string_buffer` for potentially different
  memory characteristics or C-level interoperability.

Example::

    from firebird.base.buffer import MemoryBuffer, ByteOrder

    # Create a buffer (default uses bytearray)
    buf = MemoryBuffer(10) # Initial size 10 bytes

    # Write data
    buf.write_short(258)       # Write 2 bytes (0x0102 in little-endian)
    buf.write_pascal_string("Hi") # Write 1 byte length (2) + "Hi"
    buf.write(b'\\x0A\\x0B')     # Write raw bytes

    # Reset position to read
    buf.pos = 0

    # Read data
    num = buf.read_short()
    s = buf.read_pascal_string()
    extra = buf.read(2)

    print(f"Number: {num}")      # Output: Number: 258
    print(f"String: '{s}'")      # Output: String: 'Hi'
    print(f"Extra bytes: {extra}") # Output: Extra bytes: b'\\n\\x0b'
    print(f"Final position: {buf.pos}") # Output: Final position: 7
    print(f"Raw buffer: {buf.get_raw()}") # Output: Raw buffer: bytearray(b'\\x02\\x01\\x02Hi\\n\\x0b\\x00\\x00\\x00')
"""



from __future__ import annotations

from ctypes import create_string_buffer, memset
from typing import Any, Protocol, runtime_checkable

from .types import UNLIMITED, ByteOrder, Sentinel


@runtime_checkable
class BufferFactory(Protocol): # pragma: no cover
    """Protocol defining the interface for creating and managing memory buffers.

    Allows `MemoryBuffer` to work with different underlying buffer types
    (like `bytearray` or `ctypes` arrays).
    """
    def create(self, init_or_size: int | bytes, size: int | None=None) -> Any:
        """Create and return a mutable byte buffer object.

        Arguments:
            init_or_size: An integer specifying the buffer size, or a bytes
                          object for initializing the buffer content.
            size: Optional integer size, primarily used when `init_or_size`
                  is bytes to specify a potentially different final size.

        Returns:
            The created mutable buffer object (e.g., `bytearray`, `ctypes.c_char_Array`).
        """
    def clear(self, buffer: Any) -> None:
        """Fill the buffer entirely with null bytes (zeros).

        Argument:
            buffer: A memory buffer previously created by this factory's `create()` method.
        """
    def get_raw(self, buffer: Any) -> bytes | bytearray:
        """Return the buffer's content as a standard `bytes` or `bytearray`.

        This method is necessary to provide a consistent way to access the raw
        byte sequence, as the buffer object returned by `create` might be of a
        different type (e.g., `ctypes` arrays have a `.raw` attribute).

        Argument:
            buffer: A memory buffer previously created by this factory's `create()` method.

        Returns:
            The raw byte content of the buffer.
        """

class BytesBufferFactory:
    """Buffer factory using Python's `bytearray` for storage."""
    def create(self, init_or_size: int | bytes, size: int | None=None) -> bytearray:
        """This function creates a mutable character buffer. The returned object is a
        `bytearray`.

        Arguments:
            init_or_size: Must be an integer which specifies the size of the array,
                or a bytes object which will be used to initialize the array items.
            size: Size of the array.

        Important:
            Although arguments are the same as for `ctypes.create_string_buffer`,
            the behavior is different when new buffer is initialized from bytes:

            1. If there are more bytes than specified `size`, this function copies only
               `size` bytes into new buffer. The `~ctypes.create_string_buffer` raises
               an excpetion.
            2. Unlike `~ctypes.create_string_buffer` when `size` is NOT specified,
               the buffer is NOT made one item larger than its length so that the last
               element in the array is a NUL termination character.
        """
        if isinstance(init_or_size, int):
            return bytearray(init_or_size)
        size = len(init_or_size) if size is None else size
        buffer = bytearray(size)
        limit = min(len(init_or_size), size)
        buffer[:limit] = init_or_size[:limit]
        return buffer
    def clear(self, buffer: bytearray) -> None:
        """Fills the bytearray buffer with zero bytes."""
        buffer[:] = b'\x00' * len(buffer)
    def get_raw(self, buffer: Any) -> bytes | bytearray:
        """Returns the `bytearray` buffer itself."""
        return buffer

class CTypesBufferFactory:
    """Buffer factory using `ctypes.create_string_buffer` (array of c_char)."""
    def create(self, init_or_size: int | bytes, size: int | None=None) -> bytearray:
        """This function creates a `ctypes` mutable character buffer. The returned object
        is an array of `ctypes.c_char`.

        Arguments:
            init_or_size: Must be an integer which specifies the size of the array,
                or a bytes object which will be used to initialize the array items.
            size: Size of the array.

        Important:
            Although arguments are the same as for `ctypes.create_string_buffer`,
            the behavior is different when new buffer is initialized from bytes:

            1. If there are more bytes than specified `size`, this function copies only
               `size` bytes into new buffer. The `~ctypes.create_string_buffer` raises
               an excpetion.
            2. Unlike `~ctypes.create_string_buffer` when `size` is NOT specified,
               the buffer is NOT made one item larger than its length so that the last
               element in the array is a NUL termination character.
        """
        if isinstance(init_or_size, int):
            return create_string_buffer(init_or_size)
        size = len(init_or_size) if size is None else size
        buffer = create_string_buffer(size)
        limit = min(len(init_or_size), size)
        buffer[:limit] = init_or_size[:limit]
        return buffer
    def clear(self, buffer: bytearray, init: int=0) -> None:
        """Fills the ctypes buffer with a specified byte value using `memset`.

        Arguments:
            buffer: The ctypes buffer.
            init: The byte value to fill with (default 0).
        """
        memset(buffer, init, len(buffer))
    def get_raw(self, buffer: Any) -> bytes | bytearray:
        """Returns the raw byte content via the buffer's `.raw` attribute."""
        return buffer.raw

def safe_ord(byte: bytes | int) -> int:
    """Return the integer ordinal of a byte, or the integer itself.

    Handles inputs that might already be integers (e.g., from iterating
    over a `bytes` object) or single-character `bytes` objects.

    Arguments:
        byte: A single-character bytes object or an integer.

    Returns:
        The integer value.
    """
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
    """
    def __init__(self, init: int | bytes, size: int | None=None, *,
                 factory: type[BufferFactory]=BytesBufferFactory, eof_marker: int | None=None,
                 max_size: int | Sentinel=UNLIMITED, byteorder: ByteOrder=ByteOrder.LITTLE):
        #: Buffer factory instance used by manager [default: `BytesBufferFactory`].
        self.factory: BufferFactory = factory()
        #: The memory buffer. The actual data type of buffer depends on `buffer factory`,
        #: but it must provide direct acces to cells, slices and length like `bytearray`.
        self.raw: bytearray = self.factory.create(init, size)
        #: Current position in buffer, i.e. the next read/writen byte would be at this position.
        self.pos: int = 0
        #: Value that indicates the end of data. Could be None.
        self.eof_marker: int = eof_marker
        #: The buffer couldn't grow beyond specified number of bytes [default: `.UNLIMITED`].
        self.max_size: int | Sentinel = max_size
        #: The byte order used to read/write numbers [default: `.LITTLE`].
        self.byteorder: ByteOrder = byteorder
    def _ensure_space(self, size: int) -> None:
        if len(self.raw) < self.pos + size:
            self.resize(self.pos + size)
    def _check_space(self, size: int) -> None:
        if len(self.raw) < self.pos + size:
            raise BufferError("Insufficient buffer size")
    def clear(self) -> None:
        """Fills the buffer with zeros and resets the position in buffer to zero.
        """
        self.factory.clear(self.raw)
        self.pos = 0
    def resize(self, size: int) -> None:
        """Resize buffer to the specified length. Content is preserved up to the minimum
        of the old and new sizes. New space is uninitialized (depends on factory).

        Arguments:
            size: The new size in bytes.

        Raises:
            BufferError: On attempt to resize beyond `self.max_size`.
        """
        if self.max_size is not UNLIMITED and self.max_size < size:
            raise BufferError(f"Cannot resize buffer past max. size {self.max_size} bytes")
        self.raw = self.factory.create(self.raw, size)
    def is_eof(self) -> bool:
        """Check if the current position is at or past the end of data.

        End of data is defined as being beyond the buffer's current length,
        or positioned exactly on a byte matching `self.eof_marker` (if defined).

        Returns:
            True if at end-of-data, False otherwise.
        """
        if self.pos >= len(self.raw):
            return True
        if self.eof_marker is not None and safe_ord(self.raw[self.pos]) == self.eof_marker:
            return True
        return False
    def get_raw(self) -> bytes | bytearray:
        """Return the underlying buffer's content as `bytes` or `bytearray`.

        Use this method for generic access to the raw buffer content instead of
        accessing the `raw` attribute directly, as the type of `raw` can vary
        depending on the buffer factory used.

        Returns:
            The raw content of the buffer.
        """
        return self.factory.get_raw(self.raw)
    def write(self, data: bytes) -> None:
        """Write raw bytes at the current position and advance position.

        Ensures buffer has enough space, resizing if necessary and allowed.

        Arguments:
            data: The bytes to write.

        Raises:
            BufferError: If resizing is needed but exceeds `max_size`.
        """
        size = len(data)
        self._ensure_space(size)
        self.raw[self.pos:self.pos + size] = data
        self.pos += size
    def write_byte(self, byte: int) -> None:
        """Write one byte.
        """
        self._ensure_space(1)
        self.raw[self.pos] = byte
        self.pos += 1
    def write_number(self, value: int, size: int, *, signed: bool=False) -> None:
        """Write number with specified size (in bytes).

        Arguments:
            value: The integer value to write.
            size: Value size in bytes.
            signed: Write as signed or unsigned integer.

        Raise:
            BufferError: If resizing is needed but exceeds `max_size`.
        """
        self.write(value.to_bytes(size, self.byteorder.value, signed=signed))
    def write_short(self, value: int) -> None:
        """Write 2 byte number (c_ushort).

        Arguments:
            value: The integer value to write.

        Raise:
            BufferError: If resizing is needed but exceeds `max_size`.
        """
        self.write_number(value, 2)
    def write_int(self, value: int) -> None:
        """Write 4 byte number (c_uint).

        Arguments:
            value: The integer value to write.

        Raise:
            BufferError: If resizing is needed but exceeds `max_size`.
        """
        self.write_number(value, 4)
    def write_bigint(self, value: int) -> None:
        """Write 8 byte number (c_ulonglong).

        Arguments:
            value: The integer value to write.

        Raise:
            BufferError: If resizing is needed but exceeds `max_size`.
        """
        self.write_number(value, 8)
    def write_string(self, value: str, *, encoding: str='ascii', errors: str='strict') -> None:
        """Encode string, write bytes followed by a null terminator (0x00).

        Arguments:
            value: The string to write.
            encoding: Encoding to use (default: 'ascii').
            errors: Encoding error handling scheme (default: 'strict').

        Raise:
            BufferError: If resizing is needed but exceeds `max_size`.
            UnicodeEncodeError: If `value` cannot be encoded using `encoding`.
        """
        self.write(value.encode(encoding, errors))
        self.write_byte(0)
    def write_pascal_string(self, value: str, *, encoding: str='ascii', errors: str='strict') -> None:
        """Write Pascal string (2 byte length followed by data).

        Arguments:
            value: The string to write.
            encoding: Encoding to use (default: 'ascii').
            errors: Encoding error handling scheme (default: 'strict').

        Raise:
            BufferError: If resizing is needed but exceeds `max_size`.
        """
        value = value.encode(encoding, errors)
        self.write_byte(len(value))
        self.write(value)
    def write_sized_string(self, value: str, *, encoding: str='ascii', errors: str='strict') -> None:
        """Write sized string (2 byte length followed by data).

        Arguments:
            value: The string to write.
            encoding: Encoding to use (default: 'ascii').
            errors: Encoding error handling scheme (default: 'strict').

        Raise:
            BufferError: If resizing is needed but exceeds `max_size`.
        """
        value = value.encode(encoding, errors)
        self.write_short(len(value))
        self.write(value)
    def read(self, size: int=-1) -> bytes:
        """Read specified number of bytes from current position, or all remaining data.

        Advances the position by the number of bytes read.

        Arguments:
            size: Number of bytes to read. If negative, reads all data from the
                  current position to the end of the buffer (default: -1).
        Returns:
           The bytes read.

        Raises:
            BufferError: If `size` requests more bytes than available from the current position.
        """
        if size < 0:
            size = self.buffer_size - self.pos
        self._check_space(size)
        result = self.raw[self.pos: self.pos + size]
        self.pos += size
        return result
    def read_number(self, size: int, *, signed=False) -> int:
        """Read a number of `size` bytes from current position using `self.byteorder`.

        Advances the position by `size`.

        Arguments:
            size: The number of bytes representing the number.
            signed: Whether to interpret the bytes as a signed integer (default: False).

        Returns:
           The integer value read.

        Raises:
            BufferError: When `size` is specified, but there is not enough bytes to read.
        """
        self._check_space(size)
        result = (0).from_bytes(self.raw[self.pos: self.pos + size], self.byteorder.value, signed=signed)
        self.pos += size
        return result
    def read_byte(self, *, signed: bool=False) -> int:
        """Read 1 byte number (c_ubyte).
        """
        return self.read_number(1, signed=signed)
    def read_short(self, *, signed: bool=False) -> int:
        """Read 2 byte number (c_ushort).
        """
        return self.read_number(2, signed=signed)
    def read_int(self, *, signed: bool=False) -> int:
        """Read 4 byte number (c_uint).
        """
        return self.read_number(4, signed=signed)
    def read_bigint(self, *, signed: bool=False) -> int:
        """Read 8 byte number (c_ulonglong).
        """
        return self.read_number(8, signed=signed)
    def read_sized_int(self, *, signed: bool=False) -> int:
        """Read number cluster (2 byte length followed by data).
        """
        return self.read_number(self.read_short(), signed=signed)
    def read_string(self, *, encoding: str='ascii', errors: str='strict') -> str:
        """Read bytes until a null terminator (0x00) is found, decode, and return string.

        Advances the position past the null terminator.

        Arguments:
            encoding: Encoding to use for decoding (default: 'ascii').
            errors: Decoding error handling scheme (default: 'strict').

        Returns:
            The decoded string (excluding the null terminator).

        Raises:
            BufferError: If the end of the buffer is reached before a null terminator.
            UnicodeDecodeError: If the read bytes cannot be decoded using `encoding`.
        """
        i = self.pos
        while i < self.buffer_size and safe_ord(self.raw[i]) != 0:
            i += 1
        result = self.read(i - self.pos).decode(encoding, errors)
        self.pos += 1
        return result
    def read_pascal_string(self, *, encoding: str='ascii', errors: str='strict') -> str:
        """Read Pascal string (1 byte length followed by string data).

        Arguments:
            encoding: Encoding to use for decoding (default: 'ascii').
            errors: Decoding error handling scheme (default: 'strict').

        Returns:
            The decoded string.

        Raises:
            BufferError: If the end of the buffer is reached before end of string.
            UnicodeDecodeError: If the read bytes cannot be decoded using `encoding`.
        """
        return self.read(self.read_byte()).decode(encoding, errors)
    def read_sized_string(self, *, encoding: str='ascii', errors: str='strict') -> str:
        """Read sized string (2 byte length followed by data).

        Arguments:
            encoding: Encoding to use for decoding (default: 'ascii').
            errors: Decoding error handling scheme (default: 'strict').

        Returns:
            The decoded string.

        Raises:
            BufferError: If the end of the buffer is reached before end of string.
            UnicodeDecodeError: If the read bytes cannot be decoded using `encoding`.
        """
        return self.read(self.read_short()).decode(encoding, errors)
    def read_bytes(self) -> bytes | bytearray:
        """Read content of binary cluster (2 bytes data length followed by data).


        Returns:
            The bytes read.

        Raises:
            BufferError: If the end of the buffer is reached before end of data.
        """
        return self.read(self.read_short())
    # Properties
    @property
    def buffer_size(self) -> int:
        """Current allocated buffer size in bytes."""
        return len(self.raw)
    @property
    def last_data(self) -> int:
        """Index of the last non-zero byte in the buffer (-1 if all zeros).
        """
        i = len(self.raw) - 1
        while i >= 0:
            if safe_ord(self.raw[i]) != 0:
                break
            i -= 1
        return i
