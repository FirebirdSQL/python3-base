#!/usr/bin/python
#coding:utf-8
#
#   PROGRAM/MODULE: firebird-base
#   FILE:           test/test_buffer.py
#   DESCRIPTION:    Unit tests for firebird.base.buffer
#   CREATED:        14.5.2020
#
#  Software distributed under the License is distributed AS IS,
#  WITHOUT WARRANTY OF ANY KIND, either express or implied.
#  See the License for the specific language governing rights
#  and limitations under the License.
#
#  The Original Code was created by Pavel Cisar
#
#  Copyright (c) Pavel Cisar <pcisar@users.sourceforge.net>
#  and all contributors signed below.
#
#  All Rights Reserved.
#  Contributor(s): Pavel Císař (original code)
#                  ______________________________________.
#
# See LICENSE.TXT for details.

from __future__ import annotations
import unittest
from firebird.base.buffer import *

class TestBuffer(unittest.TestCase):
    """Unit tests for firebird.base.buffer with BytesBufferFactory"""
    def __init__(self, methodName='runTest'):
        super().__init__(methodName)
        self.factory = BytesBufferFactory
    def setUp(self) -> None:
        pass
    def tearDown(self):
        pass
    def assertBuffer(self, buffer, content):
        self.assertEqual(buffer.raw, content)
    def test_create(self):
        # Empty buffer
        buf = MemoryBuffer(0, factory=self.factory)
        self.assertEqual(buf.pos, 0)
        self.assertEqual(len(buf.raw), 0)
        self.assertIsNone(buf.eof_marker)
        self.assertIs(buf.max_size, UNLIMITED)
        self.assertIs(buf.byteorder, ByteOrder.LITTLE)
        self.assertTrue(buf.is_eof())
        self.assertEqual(buf.buffer_size, 0)
        self.assertEqual(buf.last_data, -1)
        # Sized
        buf = MemoryBuffer(10, factory=self.factory)
        self.assertEqual(buf.pos, 0)
        self.assertEqual(len(buf.raw), 10)
        self.assertBuffer(buf, b'\x00' * 10)
        #self.assertEqual(buf.raw, b'\x00' * 10)
        self.assertIsNone(buf.eof_marker)
        self.assertIs(buf.max_size, UNLIMITED)
        self.assertIs(buf.byteorder, ByteOrder.LITTLE)
        self.assertFalse(buf.is_eof())
        self.assertEqual(buf.buffer_size, 10)
        self.assertEqual(buf.last_data, -1)
        # Initialized
        buf = MemoryBuffer(b'\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09\x00\x00', factory=self.factory)
        self.assertEqual(buf.pos, 0)
        self.assertEqual(len(buf.raw), 12)
        self.assertBuffer(buf, b'\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09\x00\x00')
        self.assertIsNone(buf.eof_marker)
        self.assertIs(buf.max_size, UNLIMITED)
        self.assertIs(buf.byteorder, ByteOrder.LITTLE)
        self.assertFalse(buf.is_eof())
        self.assertEqual(buf.buffer_size, 12)
        self.assertEqual(buf.last_data, 9)
        # Max. Size
        buf = MemoryBuffer(10, max_size=20, factory=self.factory)
        self.assertEqual(buf.buffer_size, 10)
        self.assertIs(buf.max_size, 20)
        # Byte order
        buf = MemoryBuffer(10, byteorder=ByteOrder.BIG, factory=self.factory)
        self.assertIs(buf.byteorder, ByteOrder.BIG)
    def test_clear(self):
        # Empty
        buf = MemoryBuffer(0, factory=self.factory)
        buf.write(b'0123456789')
        buf.clear()
        self.assertEqual(buf.pos, 0)
        self.assertEqual(len(buf.raw), 10)
        self.assertBuffer(buf, b'\x00' * 10)
        self.assertFalse(buf.is_eof())
        self.assertEqual(buf.buffer_size, 10)
        self.assertEqual(buf.last_data, -1)
        # Sized
        buf = MemoryBuffer(10, factory=self.factory)
        for i in range(buf.buffer_size):
            buf.raw[i] = 255
        self.assertBuffer(buf, b'\xff' * 10)
        buf.clear()
        self.assertEqual(buf.pos, 0)
        self.assertEqual(len(buf.raw), 10)
        self.assertBuffer(buf, b'\x00' * 10)
        self.assertFalse(buf.is_eof())
        self.assertEqual(buf.buffer_size, 10)
        self.assertEqual(buf.last_data, -1)
    def test_write(self):
        buf = MemoryBuffer(0, factory=self.factory)
        buf.write(b'ABCDE')
        self.assertEqual(buf.pos, 5)
        self.assertBuffer(buf, b'ABCDE')
        self.assertTrue(buf.is_eof())
    def test_write_byte(self):
        buf = MemoryBuffer(0, factory=self.factory)
        buf.write_byte(1)
        self.assertEqual(buf.pos, 1)
        self.assertBuffer(buf, b'\x01')
        self.assertTrue(buf.is_eof())
    def test_write_short(self):
        buf = MemoryBuffer(0, factory=self.factory)
        buf.write_short(2)
        self.assertEqual(buf.pos, 2)
        self.assertBuffer(buf, b'\x02\x00')
        self.assertTrue(buf.is_eof())
    def test_write_int(self):
        buf = MemoryBuffer(0, factory=self.factory)
        buf.write_int(3)
        self.assertEqual(buf.pos, 4)
        self.assertBuffer(buf, b'\x03\x00\x00\x00')
        self.assertTrue(buf.is_eof())
    def test_write_bigint(self):
        buf = MemoryBuffer(0, factory=self.factory)
        buf.write_bigint(4)
        self.assertEqual(buf.pos, 8)
        self.assertBuffer(buf, b'\x04\x00\x00\x00\x00\x00\x00\x00')
        self.assertTrue(buf.is_eof())
    def test_write_number(self):
        buf = MemoryBuffer(0, factory=self.factory)
        buf.write_number(255, 1)
        self.assertEqual(buf.pos, 1)
        self.assertBuffer(buf, b'\xff')
        self.assertTrue(buf.is_eof())
        #
        buf = MemoryBuffer(0, factory=self.factory)
        buf.write_number(255, 2)
        self.assertEqual(buf.pos, 2)
        self.assertBuffer(buf, b'\xff\x00')
        self.assertTrue(buf.is_eof())
        #
        buf = MemoryBuffer(0, factory=self.factory)
        buf.write_number(255, 4)
        self.assertEqual(buf.pos, 4)
        self.assertBuffer(buf, b'\xff\x00\x00\x00')
        self.assertTrue(buf.is_eof())
        #
        buf = MemoryBuffer(0, factory=self.factory)
        buf.write_number(255, 8)
        self.assertEqual(buf.pos, 8)
        self.assertBuffer(buf, b'\xff\x00\x00\x00\x00\x00\x00\x00')
        self.assertTrue(buf.is_eof())
        # Atypical sizes
        buf = MemoryBuffer(0, factory=self.factory)
        buf.write_number(255, 3)
        self.assertEqual(buf.pos, 3)
        self.assertBuffer(buf, b'\xff\x00\x00')
        self.assertTrue(buf.is_eof())
        buf = MemoryBuffer(0, factory=self.factory)
        buf.write_number(255, 12)
        self.assertEqual(buf.pos, 12)
        self.assertBuffer(buf, b'\xff\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00')
        self.assertTrue(buf.is_eof())
    def test_write_string(self):
        buf = MemoryBuffer(0, factory=self.factory)
        buf.write_string('string')
        self.assertEqual(buf.pos, 7)
        self.assertBuffer(buf, b'string\x00')
        self.assertTrue(buf.is_eof())
    def test_write_pascal_string(self):
        buf = MemoryBuffer(0, factory=self.factory)
        buf.write_pascal_string('string')
        self.assertEqual(buf.pos, 7)
        self.assertBuffer(buf, b'\x06string')
        self.assertTrue(buf.is_eof())
    def test_write_past_size(self):
        buf = MemoryBuffer(0, max_size=5, factory=self.factory)
        buf.write(b'ABCDE')
        with self.assertRaises(IOError) as cm:
            buf.write(b'exceeds size')
        self.assertEqual(cm.exception.args, ("Cannot resize buffer past max. size 5 bytes",))
    def test_read(self):
        buf = MemoryBuffer(b'ABCDE', factory=self.factory)
        self.assertEqual(buf.read(3), b'ABC')
        self.assertEqual(buf.pos, 3)
        self.assertFalse(buf.is_eof())
        self.assertEqual(buf.read(), b'DE')
        self.assertEqual(buf.pos, 5)
        self.assertTrue(buf.is_eof())
    def test_read_byte(self):
        buf = MemoryBuffer(b'\x01', factory=self.factory)
        self.assertEqual(buf.read_byte(), 1)
        self.assertEqual(buf.pos, 1)
        self.assertTrue(buf.is_eof())
    def test_read_short(self):
        buf = MemoryBuffer(b'\x02\x00', factory=self.factory)
        self.assertEqual(buf.read_short(), 2)
        self.assertEqual(buf.pos, 2)
        self.assertTrue(buf.is_eof())
    def test_read_int(self):
        buf = MemoryBuffer(b'\x03\x00\x00\x00', factory=self.factory)
        self.assertEqual(buf.read_int(), 3)
        self.assertEqual(buf.pos, 4)
        self.assertTrue(buf.is_eof())
    def test_read_bigint(self):
        buf = MemoryBuffer(b'\x04\x00\x00\x00\x00\x00\x00\x00', factory=self.factory)
        self.assertEqual(buf.read_bigint(), 4)
        self.assertEqual(buf.pos, 8)
        self.assertBuffer(buf, b'\x04\x00\x00\x00\x00\x00\x00\x00')
        self.assertTrue(buf.is_eof())
    def test_read_number(self):
        buf = MemoryBuffer(b'\xff', factory=self.factory)
        self.assertEqual(buf.read_number(1), 255)
        self.assertEqual(buf.pos, 1)
        self.assertTrue(buf.is_eof())
        #
        buf = MemoryBuffer(b'\xff\x00', factory=self.factory)
        self.assertEqual(buf.read_number(2), 255)
        self.assertEqual(buf.pos, 2)
        self.assertTrue(buf.is_eof())
        #
        buf = MemoryBuffer(b'\xff\x00\x00\x00', factory=self.factory)
        self.assertEqual(buf.read_number(4), 255)
        self.assertEqual(buf.pos, 4)
        self.assertTrue(buf.is_eof())
        #
        buf = MemoryBuffer(b'\xff\x00\x00\x00\x00\x00\x00\x00', factory=self.factory)
        self.assertEqual(buf.read_number(8), 255)
        self.assertEqual(buf.pos, 8)
        self.assertTrue(buf.is_eof())
        # Atypical sizes
        buf = MemoryBuffer(b'\xff\x00\x00', factory=self.factory)
        self.assertEqual(buf.read_number(3), 255)
        self.assertEqual(buf.pos, 3)
        self.assertTrue(buf.is_eof())
        buf = MemoryBuffer(b'\xff\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00', factory=self.factory)
        self.assertEqual(buf.read_number(12), 255)
        self.assertEqual(buf.pos, 12)
        self.assertTrue(buf.is_eof())
    def test_read_sized_int(self):
        buf = MemoryBuffer(b'\x04\x00\x03\x00\x00\x00', factory=self.factory)
        self.assertEqual(buf.read_sized_int(), 3)
        self.assertEqual(buf.pos, 6)
        self.assertTrue(buf.is_eof())
    def test_read_string(self):
        buf = MemoryBuffer(b'string 1\x00string 2\x00', factory=self.factory)
        self.assertEqual(buf.read_string(), 'string 1')
        self.assertEqual(buf.pos, 9)
        self.assertFalse(buf.is_eof())
        #  No zero-terminator
        buf = MemoryBuffer(b'string', factory=self.factory)
        self.assertEqual(buf.read_string(), 'string')
        self.assertEqual(buf.pos, 7)
        self.assertTrue(buf.is_eof())
    def test_read_pascal_string(self):
        buf = MemoryBuffer(b'\x06string', factory=self.factory)
        self.assertEqual(buf.read_pascal_string(), 'string')
        self.assertEqual(buf.pos, 7)
        self.assertTrue(buf.is_eof())
    def test_read_sized_string(self):
        buf = MemoryBuffer(b'\x08\x00string 1\x08\x00string 2', factory=self.factory)
        self.assertEqual(buf.read_sized_string(), 'string 1')
        self.assertEqual(buf.pos, 10)
        self.assertFalse(buf.is_eof())
    def test_read_bytes(self):
        buf = MemoryBuffer(b'\x08\x00ABCDEFGH\x08\x00string 2', factory=self.factory)
        self.assertEqual(buf.read_bytes(), b'ABCDEFGH')
        self.assertEqual(buf.pos, 10)
        self.assertFalse(buf.is_eof())
    def test_read_past_size(self):
        buf = MemoryBuffer(b'ABCDE', factory=self.factory)
        with self.assertRaises(IOError) as cm:
            buf.read_bigint()
        self.assertEqual(cm.exception.args, ("Insufficient buffer size",))
    def test_eof_marker(self):
        buf = MemoryBuffer(b'\x08\x00ABCDEFGH\xFF\x00\x00\x00\x00\x00\x00', eof_marker=255,
                           factory=self.factory)
        while not buf.is_eof():
            buf.pos += 1
        self.assertLess(buf.pos, buf.buffer_size)
        self.assertEqual(buf.pos, 10)
        self.assertEqual(safe_ord(buf.raw[buf.pos]), buf.eof_marker)

class TestCBuffer(TestBuffer):
    """Unit tests for firebird.base.buffer with CTypesBufferFactory"""
    def __init__(self, methodName='runTest'):
        super().__init__(methodName)
        self.factory = CTypesBufferFactory
    def assertBuffer(self, buffer, content):
        self.assertEqual(buffer.raw.raw, content)

if __name__ == '__main__':
    unittest.main()
