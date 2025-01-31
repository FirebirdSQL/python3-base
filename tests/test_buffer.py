# SPDX-FileCopyrightText: 2019-present The Firebird Projects <www.firebirdsql.org>
#
# SPDX-License-Identifier: MIT
#
#   PROGRAM/MODULE: firebird-base
#   FILE:           tests/test_buffer.py
#   DESCRIPTION:    Tests for firebird.base.buffer
#   CREATED:        14.5.2020
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

from __future__ import annotations

import pytest

from firebird.base.buffer import *

factories = [BytesBufferFactory, CTypesBufferFactory]

@pytest.fixture(params=factories)
def factory(request):
    return request.param

def test_create_empty(factory):
    buf = MemoryBuffer(0, factory=factory)
    assert buf.pos == 0
    assert len(buf.raw) == 0
    assert buf.eof_marker is None
    assert buf.max_size is UNLIMITED
    assert buf.byteorder is ByteOrder.LITTLE
    assert buf.is_eof()
    assert buf.buffer_size == 0
    assert buf.last_data == -1

def test_create_sized(factory):
    buf = MemoryBuffer(10, factory=factory)
    assert buf.pos == 0
    assert len(buf.raw) == 10
    assert buf.get_raw() == b"\x00" * 10
    assert buf.eof_marker is None
    assert buf.max_size is UNLIMITED
    assert buf.byteorder is ByteOrder.LITTLE
    assert not buf.is_eof()
    assert buf.buffer_size == 10
    assert buf.last_data == -1

def test_create_initialized(factory):
    buf = MemoryBuffer(b"\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09\x00\x00", factory=factory)
    assert buf.pos == 0
    assert len(buf.raw) == 12
    assert buf.get_raw() == b"\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09\x00\x00"
    assert buf.eof_marker is None
    assert buf.max_size is UNLIMITED
    assert buf.byteorder is ByteOrder.LITTLE
    assert not buf.is_eof()
    assert buf.buffer_size == 12
    assert buf.last_data == 9

def test_create_max_size(factory):
    buf = MemoryBuffer(10, max_size=20, factory=factory)
    assert buf.buffer_size == 10
    assert buf.max_size == 20

def test_create_byte_order(factory):
    buf = MemoryBuffer(10, byteorder=ByteOrder.BIG, factory=factory)
    assert buf.byteorder == ByteOrder.BIG

def test_clear_empty(factory):
    buf = MemoryBuffer(0, factory=factory)
    buf.write(b"0123456789")
    buf.clear()
    assert buf.pos == 0
    assert len(buf.raw) == 10
    assert buf.get_raw() == b"\x00" * 10
    assert not buf.is_eof()
    assert buf.buffer_size == 10
    assert buf.last_data == -1

def test_clear_sized(factory):
    buf = MemoryBuffer(10, factory=factory)
    for i in range(buf.buffer_size):
        buf.raw[i] = 255
    assert buf.get_raw() == b"\xff" * 10
    buf.clear()
    assert buf.pos == 0
    assert len(buf.raw) == 10
    assert buf.get_raw() == b"\x00" * 10
    assert not buf.is_eof()
    assert buf.buffer_size == 10
    assert buf.last_data == -1

def test_write(factory):
    buf = MemoryBuffer(0, factory=factory)
    buf.write(b"ABCDE")
    assert buf.pos == 5
    assert buf.get_raw() == b"ABCDE"
    assert buf.is_eof()

def test_write_byte(factory):
    buf = MemoryBuffer(0, factory=factory)
    buf.write_byte(1)
    assert buf.pos == 1
    assert buf.get_raw() == b"\x01"
    assert buf.is_eof()

def test_write_short(factory):
    buf = MemoryBuffer(0, factory=factory)
    buf.write_short(2)
    assert buf.pos == 2
    assert buf.get_raw() == b"\x02\x00"
    assert buf.is_eof()

def test_write_int(factory):
    buf = MemoryBuffer(0, factory=factory)
    buf.write_int(3)
    assert buf.pos == 4
    assert buf.get_raw() == b"\x03\x00\x00\x00"
    assert buf.is_eof()

def test_write_bigint(factory):
    buf = MemoryBuffer(0, factory=factory)
    buf.write_bigint(4)
    assert buf.pos == 8
    assert buf.get_raw() == b"\x04\x00\x00\x00\x00\x00\x00\x00"
    assert buf.is_eof()

def test_write_number(factory):
    buf = MemoryBuffer(0, factory=factory)
    buf.write_number(255, 1)
    assert buf.pos == 1
    assert buf.get_raw() == b"\xff"
    assert buf.is_eof()
    #
    buf = MemoryBuffer(0, factory=factory)
    buf.write_number(255, 2)
    assert buf.pos == 2
    assert buf.get_raw() == b"\xff\x00"
    assert buf.is_eof()
    #
    buf = MemoryBuffer(0, factory=factory)
    buf.write_number(255, 4)
    assert buf.pos == 4
    assert buf.get_raw() == b"\xff\x00\x00\x00"
    assert buf.is_eof()
    #
    buf = MemoryBuffer(0, factory=factory)
    buf.write_number(255, 8)
    assert buf.pos == 8
    assert buf.get_raw() == b"\xff\x00\x00\x00\x00\x00\x00\x00"
    assert buf.is_eof()
    # Atypical sizes
    buf = MemoryBuffer(0, factory=factory)
    buf.write_number(255, 3)
    assert buf.pos == 3
    assert buf.get_raw() == b"\xff\x00\x00"
    assert buf.is_eof()
    buf = MemoryBuffer(0, factory=factory)
    buf.write_number(255, 12)
    assert buf.pos == 12
    assert buf.get_raw() == b"\xff\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
    assert buf.is_eof()

def test_write_number_big_endian(factory):
    buf = MemoryBuffer(0, factory=factory, byteorder=ByteOrder.BIG)
    buf.write_number(255, 1)
    assert buf.pos == 1
    assert buf.get_raw() == b"\xff"
    assert buf.is_eof()
    #
    buf = MemoryBuffer(0, factory=factory, byteorder=ByteOrder.BIG)
    buf.write_number(255, 2)
    assert buf.pos == 2
    assert buf.get_raw() == b"\x00\xff"
    assert buf.is_eof()
    #
    buf = MemoryBuffer(0, factory=factory, byteorder=ByteOrder.BIG)
    buf.write_number(255, 4)
    assert buf.pos == 4
    assert buf.get_raw() == b"\x00\x00\x00\xff"
    assert buf.is_eof()
    #
    buf = MemoryBuffer(0, factory=factory, byteorder=ByteOrder.BIG)
    buf.write_number(255, 8)
    assert buf.pos == 8
    assert buf.get_raw() == b"\x00\x00\x00\x00\x00\x00\x00\xff"
    assert buf.is_eof()
    # Atypical sizes
    buf = MemoryBuffer(0, factory=factory, byteorder=ByteOrder.BIG)
    buf.write_number(255, 3)
    assert buf.pos == 3
    assert buf.get_raw() == b"\x00\x00\xff"
    assert buf.is_eof()
    buf = MemoryBuffer(0, factory=factory, byteorder=ByteOrder.BIG)
    buf.write_number(255, 12)
    assert buf.pos == 12
    assert buf.get_raw() == b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xff"
    assert buf.is_eof()

def test_write_string(factory):
    buf = MemoryBuffer(0, factory=factory)
    buf.write_string("string")
    assert buf.pos == 7
    assert buf.get_raw() == b"string\x00"
    assert buf.is_eof()

def test_write_pascal_string(factory):
    buf = MemoryBuffer(0, factory=factory)
    buf.write_pascal_string("string")
    assert buf.pos == 7
    assert buf.get_raw() == b"\x06string"
    assert buf.is_eof()

def test_write_sized_string(factory):
    buf = MemoryBuffer(0, factory=factory)
    buf.write_sized_string("string")
    assert buf.pos == 8
    assert buf.get_raw() == b"\x06\x00string"
    assert buf.is_eof()

def test_write_past_size(factory):
    buf = MemoryBuffer(0, max_size=5, factory=factory)
    buf.write(b"ABCDE")
    with pytest.raises(BufferError) as cm:
        buf.write(b"exceeds size")
    assert cm.value.args == ("Cannot resize buffer past max. size 5 bytes",)

def test_read(factory):
    buf = MemoryBuffer(b"ABCDE", factory=factory)
    assert buf.read(3) == b"ABC"
    assert buf.pos == 3
    assert not buf.is_eof()
    assert buf.read() == b"DE"
    assert buf.pos == 5
    assert buf.is_eof()

def test_read_byte(factory):
    buf = MemoryBuffer(b"\x01", factory=factory)
    assert buf.read_byte() == 1
    assert buf.pos == 1
    assert buf.is_eof()

def test_read_short(factory):
    buf = MemoryBuffer(b"\x02\x00", factory=factory)
    assert buf.read_short() == 2
    assert buf.pos == 2
    assert buf.is_eof()

def test_read_int(factory):
    buf = MemoryBuffer(b"\x03\x00\x00\x00", factory=factory)
    assert buf.read_int() == 3
    assert buf.pos == 4
    assert buf.is_eof()

def test_read_bigint(factory):
    buf = MemoryBuffer(b"\x04\x00\x00\x00\x00\x00\x00\x00", factory=factory)
    assert buf.read_bigint() == 4
    assert buf.pos == 8
    assert buf.get_raw() == b"\x04\x00\x00\x00\x00\x00\x00\x00"
    assert buf.is_eof()

def test_read_number(factory):
    buf = MemoryBuffer(b"\xff", factory=factory)
    assert buf.read_number(1) == 255
    assert buf.pos == 1
    assert buf.is_eof()
    #
    buf = MemoryBuffer(b"\xff\x00", factory=factory)
    assert buf.read_number(2) == 255
    assert buf.pos == 2
    assert buf.is_eof()
    #
    buf = MemoryBuffer(b"\xff\x00\x00\x00", factory=factory)
    assert buf.read_number(4) == 255
    assert buf.pos == 4
    assert buf.is_eof()
    #
    buf = MemoryBuffer(b"\xff\x00\x00\x00\x00\x00\x00\x00", factory=factory)
    assert buf.read_number(8) == 255
    assert buf.pos == 8
    assert buf.is_eof()
    # Atypical sizes
    buf = MemoryBuffer(b"\xff\x00\x00", factory=factory)
    assert buf.read_number(3) == 255
    assert buf.pos == 3
    assert buf.is_eof()
    #
    buf = MemoryBuffer(b"\xff\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00", factory=factory)
    assert buf.read_number(12) == 255
    assert buf.pos == 12
    assert buf.is_eof()

def test_read_number_big_endian(factory):
    buf = MemoryBuffer(b"\xff", factory=factory, byteorder=ByteOrder.BIG)
    assert buf.read_number(1) == 255
    assert buf.pos == 1
    assert buf.is_eof()
    #
    buf = MemoryBuffer(b"\x00\xff", factory=factory, byteorder=ByteOrder.BIG)
    assert buf.read_number(2) == 255
    assert buf.pos == 2
    assert buf.is_eof()
    #
    buf = MemoryBuffer(b"\x00\x00\x00\xff", factory=factory, byteorder=ByteOrder.BIG)
    assert buf.read_number(4) == 255
    assert buf.pos == 4
    assert buf.is_eof()
    #
    buf = MemoryBuffer(b"\x00\x00\x00\x00\x00\x00\x00\xff", factory=factory,
                       byteorder=ByteOrder.BIG)
    assert buf.read_number(8) == 255
    assert buf.pos == 8
    assert buf.is_eof()
    # Atypical sizes
    buf = MemoryBuffer(b"\x00\x00\xff", factory=factory, byteorder=ByteOrder.BIG)
    assert buf.read_number(3) == 255
    assert buf.pos == 3
    assert buf.is_eof()
    #
    buf = MemoryBuffer(b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xff", factory=factory,
                       byteorder=ByteOrder.BIG)
    assert buf.read_number(12) == 255
    assert buf.pos == 12
    assert buf.is_eof()

def test_read_sized_int(factory):
    buf = MemoryBuffer(b"\x04\x00\x03\x00\x00\x00", factory=factory)
    assert buf.read_sized_int() == 3
    assert buf.pos == 6
    assert buf.is_eof()

def test_read_string(factory):
    buf = MemoryBuffer(b"string 1\x00string 2\x00", factory=factory)
    assert buf.read_string() == "string 1"
    assert buf.pos == 9
    assert not buf.is_eof()
    #  No zero-terminator
    buf = MemoryBuffer(b"string", factory=factory)
    assert buf.read_string() == "string"
    assert buf.pos == 7
    assert buf.is_eof()

def test_read_pascal_string(factory):
    buf = MemoryBuffer(b"\x06stringand another data", factory=factory)
    assert buf.read_pascal_string() == "string"
    assert buf.pos == 7
    assert not buf.is_eof()

def test_read_sized_string(factory):
    buf = MemoryBuffer(b"\x08\x00string 1\x08\x00string 2", factory=factory)
    assert buf.read_sized_string() == "string 1"
    assert buf.pos == 10
    assert not buf.is_eof()

def test_read_bytes(factory):
    buf = MemoryBuffer(b"\x08\x00ABCDEFGH\x08\x00string 2", factory=factory)
    assert buf.read_bytes() == b"ABCDEFGH"
    assert buf.pos == 10
    assert not buf.is_eof()

def test_read_past_size(factory):
    buf = MemoryBuffer(b"ABCDE", factory=factory)
    with pytest.raises(BufferError) as cm:
        buf.read_bigint()
    assert cm.value.args == ("Insufficient buffer size",)

def test_eof_marker(factory):
    buf = MemoryBuffer(b"\x08\x00ABCDEFGH\xFF\x00\x00\x00\x00\x00\x00", eof_marker=255,
                       factory=factory)
    while not buf.is_eof():
        buf.pos += 1
    assert buf.pos < buf.buffer_size
    assert buf.pos == 10
    assert safe_ord(buf.raw[buf.pos]) == buf.eof_marker

