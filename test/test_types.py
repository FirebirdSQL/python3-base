#!/usr/bin/python
#coding:utf-8
#
#   PROGRAM/MODULE: firebird-base
#   FILE:           test/test_types.py
#   DESCRIPTION:    Unit tests for firebird.base.types
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
from typing import List
import unittest
from dataclasses import dataclass
from firebird.base.types import *

class TestTypes(unittest.TestCase):
    """Unit tests for firebird.base.types"""
    def __init__(self, methodName='runTest'):
        super().__init__(methodName)
        self.output: List = []
    def setUp(self) -> None:
        self.output.clear()
    def tearDown(self):
        pass
    def test_exceptions(self):
        "Test exceptions"
        e = Error("Message", code=1, subject=self)
        self.assertTupleEqual(e.args, ("Message",))
        self.assertEqual(e.code, 1)
        self.assertEqual(e.subject, self)
        self.assertIsNone(e.other_attr)
    def test_singletons(self):
        "Test Singletons"
        class MySingleton(Singleton):
            pass

        class MyOtherSingleton(MySingleton):
            pass
        #
        s = MySingleton()
        self.assertIs(s, MySingleton())
        os = MyOtherSingleton()
        self.assertIs(os, MyOtherSingleton())
        self.assertIsNot(s, os)
    def test_sentinel(self):
        "Test Sentinel"
        self.assertEqual(UNKNOWN.name, 'UNKNOWN')
        self.assertEqual(str(UNKNOWN), 'UNKNOWN')
        self.assertEqual(repr(UNKNOWN), "Sentinel('UNKNOWN')")
        self.assertDictEqual(UNKNOWN.instances, {'DEFAULT': DEFAULT,
                                                 'INFINITY': INFINITY,
                                                 'UNLIMITED': UNLIMITED,
                                                 'UNKNOWN': UNKNOWN,
                                                 'NOT_FOUND': NOT_FOUND,
                                                 'UNDEFINED': UNDEFINED,
                                                 'ANY': ANY,
                                                 'ALL': ALL,
                                                 'SUSPEND': SUSPEND,
                                                 'RESUME': RESUME,
                                                 'STOP': STOP,
                                                 })
        for name, sentinel in Sentinel.instances.items():
            self.assertEqual(sentinel, Sentinel(name))
        self.assertNotIn('TEST-SENTINEL', Sentinel.instances)
        Sentinel('TEST-SENTINEL')
        self.assertIn('TEST-SENTINEL', Sentinel.instances)
    def test_distinct(self):
        "Test Distinct"
        @dataclass
        class MyDistinct(Distinct):
            key_1: int
            key_2: str
            payload: str
            def get_key(self):
                if not hasattr(self, '__key__'):
                    self.__key__ = (self.key_1, self.key_2)
                return self.__key__

        d = MyDistinct(1, 'A', '1A')
        self.assertFalse(hasattr(d, '__key__'))
        self.assertEqual(d.get_key(), (1, 'A'))
        self.assertTrue(hasattr(d, '__key__'))
        d.key_2 = 'B'
        self.assertEqual(d.get_key(), (1, 'A'))
    def test_cached_distinct(self):
        "Test CachedDistinct"
        class MyCachedDistinct(CachedDistinct):
            def __init__(self, key_1, key_2, payload):
                self.key_1 = key_1
                self.key_2 = key_2
                self.payload = payload
            @classmethod
            def extract_key(cls, *args, **kwargs) -> t.Hashable:
                return (args[0], args[1])
            def get_key(self) -> t.Hashable:
                return (self.key_1, self.key_2)
        #
        self.assertTrue(hasattr(MyCachedDistinct, '_instances_'))
        cd_1 = MyCachedDistinct(1, ANY, 'type 1A')
        self.assertIs(cd_1, MyCachedDistinct(1, ANY, 'type 1A'))
        self.assertIsNot(cd_1, MyCachedDistinct(2, ANY, 'type 2A'))
        self.assertTrue(hasattr(MyCachedDistinct, '_instances_'))
        self.assertEqual(len(getattr(MyCachedDistinct, '_instances_')), 1)
        cd_2 = MyCachedDistinct(2, ANY, 'type 2A')
        self.assertEqual(len(getattr(MyCachedDistinct, '_instances_')), 2)
        temp = MyCachedDistinct(2, ANY, 'type 2A')
        self.assertEqual(len(getattr(MyCachedDistinct, '_instances_')), 2)
        del cd_1, cd_2, temp
        self.assertEqual(len(getattr(MyCachedDistinct, '_instances_')), 0)
    def test_zmqaddress(self):
        "Test ZMQAddress"
        addr = ZMQAddress('ipc://@my-address')
        self.assertEqual(addr.address, '@my-address')
        self.assertEqual(addr.protocol, ZMQTransport.IPC)
        self.assertEqual(addr.domain, ZMQDomain.NODE)
        #
        addr = ZMQAddress('inproc://my-address')
        self.assertEqual(addr.address, 'my-address')
        self.assertEqual(addr.protocol, ZMQTransport.INPROC)
        self.assertEqual(addr.domain, ZMQDomain.LOCAL)
        #
        addr = ZMQAddress('tcp://127.0.0.1:*')
        self.assertEqual(addr.address, '127.0.0.1:*')
        self.assertEqual(addr.protocol, ZMQTransport.TCP)
        self.assertEqual(addr.domain, ZMQDomain.NODE)
        #
        addr = ZMQAddress('tcp://192.168.0.1:8001')
        self.assertEqual(addr.address, '192.168.0.1:8001')
        self.assertEqual(addr.protocol, ZMQTransport.TCP)
        self.assertEqual(addr.domain, ZMQDomain.NETWORK)
        #
        addr = ZMQAddress('pgm://192.168.0.1:8001')
        self.assertEqual(addr.address, '192.168.0.1:8001')
        self.assertEqual(addr.protocol, ZMQTransport.PGM)
        self.assertEqual(addr.domain, ZMQDomain.NETWORK)
        # Bytes
        addr = ZMQAddress(b'ipc://@my-address')
        self.assertEqual(addr.address, '@my-address')
        self.assertEqual(addr.protocol, ZMQTransport.IPC)
        self.assertEqual(addr.domain, ZMQDomain.NODE)
        # Bad ZMQ address
        with self.assertRaises(ValueError) as cm:
            addr = ZMQAddress('onion://@my-address')
        self.assertEqual(cm.exception.args, ("Unknown protocol 'onion'",))
        with self.assertRaises(ValueError) as cm:
            addr = ZMQAddress('192.168.0.1:8001')
        self.assertEqual(cm.exception.args, ("Protocol specification required",))
        with self.assertRaises(ValueError) as cm:
            addr = ZMQAddress('unknown://192.168.0.1:8001')
        self.assertEqual(cm.exception.args, ("Invalid protocol",))
    def test_MIME(self):
        "Test MIME"
        mime = MIME('text/plain;charset=utf-8')
        self.assertEqual(mime.mime_type, 'text/plain')
        self.assertEqual(mime.type, 'text')
        self.assertEqual(mime.subtype, 'plain')
        self.assertDictEqual(mime.params, {'charset': 'utf-8',})
        #
        mime = MIME('text/plain')
        self.assertEqual(mime.mime_type, 'text/plain')
        self.assertEqual(mime.type, 'text')
        self.assertEqual(mime.subtype, 'plain')
        self.assertDictEqual(mime.params, {})
        #
        # Bad MIME type
        with self.assertRaises(ValueError) as cm:
            mime = MIME('')
        self.assertEqual(cm.exception.args, ("MIME type specification must be 'type/subtype[;param=value;...]'",))
        with self.assertRaises(ValueError) as cm:
            mime = MIME('model/airplane')
        self.assertEqual(cm.exception.args, ("MIME type 'model' not supported",))
        with self.assertRaises(ValueError) as cm:
            mime = MIME('text/plain;charset:utf-8')
        self.assertEqual(cm.exception.args, ("Wrong specification of MIME type parameters",))


if __name__ == '__main__':
    unittest.main()
