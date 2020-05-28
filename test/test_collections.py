#!/usr/bin/python
#coding:utf-8
#
# PROGRAM/MODULE: firebird-base
# FILE:           test/test_collections.py
# DESCRIPTION:    Unit tests for firebird.base.collections
# CREATED:        20.9.2019
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

"""Firebird Base - Unit tests for firebird.base.collections."""

from __future__ import annotations
from types import GeneratorType
import unittest
from dataclasses import dataclass
from firebird.base.types import Error, Distinct, UNDEFINED
from firebird.base.collections import DataList, Registry

@dataclass
class Item(Distinct):
    key: int
    name: str
    def get_key(self):
        return self.key

@dataclass
class Desc(Distinct):
    key: int
    item: Item
    description: str
    def get_key(self):
        return self.key

class MyRegistry(Registry):
    pass

class TestDataList(unittest.TestCase):
    """Unit tests for firebird.base.collection.DataList"""
    def setUp(self):
        self.data_items = [Item(1, 'Item 01'), Item(2, 'Item 02'), Item(3, 'Item 03'),
                           Item(4, 'Item 04'), Item(5, 'Item 05'), Item(6, 'Item 06'),
                           Item(7, 'Item 07'), Item(8, 'Item 08'), Item(9, 'Item 09'),
                           Item(10, 'Item 10')]
        self.data_desc = [Desc(item.key, item, f"This is item '{item.name}'") for item
                          in self.data_items]
        self.key_item = 'item.key'
        self.key_spec = 'item.key'
    def tearDown(self):
        pass
    def test_create(self):
        l = DataList()
        # Simple
        self.assertListEqual(l, [], "Simple")
        self.assertFalse(l.frozen, "Simple")
        self.assertIsNone(l.key_expr, "Simple")
        self.assertIs(l.type_spec, UNDEFINED, "Simple")
        # From items
        with self.assertRaises(TypeError):
            DataList(object)
        l = DataList(self.data_items)
        self.assertListEqual(l, self.data_items, "From items")
        self.assertFalse(l.frozen, "From items")
        self.assertIsNone(l.key_expr, "From items")
        self.assertIs(l.type_spec, UNDEFINED, "From items")
        # With type spec (Non-Distinct)
        l = DataList(type_spec=int)
        self.assertFalse(l.frozen, "With type spec (Non-Distinct)")
        self.assertIsNone(l.key_expr, "With type spec (Non-Distinct)")
        # With type spec (Distinct)
        l = DataList(type_spec=Item)
        self.assertFalse(l.frozen, "With type spec (Distinct)")
        self.assertEqual(l.key_expr, 'item.get_key()', "With type spec (Distinct)")
        self.assertEqual(l.type_spec, Item, "With type spec (Distinct)")
        l = DataList(type_spec=(Item, Desc))
        self.assertEqual(l.key_expr, 'item.get_key()', "With type spec (Distinct)")
        self.assertEqual(l.type_spec, (Item, Desc), "With type spec (Distinct)")
        # With key expr
        if __debug__:
            with self.assertRaises(AssertionError, msg="With key expr"):
                DataList(key_expr=object)
            with self.assertRaises(SyntaxError, msg="With key expr"):
                DataList(key_expr='wrong key expression')
        l = DataList(key_expr=self.key_item)
        self.assertFalse(l.frozen, "With key expr")
        self.assertEqual(l.key_expr, self.key_item, "With key expr")
        self.assertIs(l.type_spec, UNDEFINED, "With key expr")
        # With frozen
        l = DataList(frozen=True)
        self.assertTrue(l.frozen, "With frozen")
        # With all
        l = DataList(self.data_items, Item, self.key_item)
        self.assertEqual(l, self.data_items, "With all")
    def test_insert(self):
        i1, i2, i3 = self.data_items[:3]
        l = DataList()
        # Simple
        l.insert(0, i1)
        self.assertListEqual(l, [i1], "Simple")
        l.insert(0, i2)
        self.assertListEqual(l, [i2, i1], "Simple")
        l.insert(1, i3)
        self.assertListEqual(l, [i2, i3, i1], "Simple")
        l.insert(5, i3)
        self.assertListEqual(l, [i2, i3, i1, i3], "Simple")
        # With type_spec
        l = DataList(type_spec=Item)
        l.insert(0, i1)
        with self.assertRaises(TypeError, msg="With type_spec"):
            l.insert(0, self.data_desc[0])
        # With key expr
        l = DataList(key_expr=self.key_item)
        l.insert(0, i1)
        self.assertListEqual(l, [i1], "With key expr")
        # Frozen
        with self.assertRaises(TypeError):
            l.freeze()
            l.insert(0, i1)
    def test_append(self):
        i1, i2 = self.data_items[:2]
        l = DataList()
        # Simple
        l.append(i1)
        self.assertListEqual(l, [i1], "Simple")
        l.append(i2)
        self.assertListEqual(l, [i1, i2], "Simple")
        # With type_spec
        l = DataList(type_spec=Item)
        l.append(i1)
        with self.assertRaises(TypeError, msg="With type_spec"):
            l.insert(0, self.data_desc[0])
        # With key expr
        l = DataList(key_expr=self.key_item)
        l.append(i1)
        self.assertListEqual(l, [i1], "With key expr")
        # Frozen
        with self.assertRaises(TypeError):
            l.freeze()
            l.append(i1)
    def test_extend(self):
        l = DataList()
        # Simple
        l.extend(self.data_items)
        self.assertListEqual(l, self.data_items)
        # With type_spec
        l = DataList(type_spec=Item)
        l.extend(self.data_items)
        self.assertListEqual(l, self.data_items)
        with self.assertRaises(TypeError, msg="With type_spec"):
            l.extend(self.data_desc)
        # With key expr
        l = DataList(key_expr=self.key_item)
        l.extend(self.data_items)
        self.assertListEqual(l, self.data_items, "With key expr")
        # Frozen
        with self.assertRaises(TypeError):
            l.freeze()
            l.extend(self.data_items[0])
    def test_list_acess(self):
        l = DataList(self.data_items)
        # Simple
        self.assertEqual(l[2], self.data_items[2])
        with self.assertRaises(IndexError):
            l[20]
        # With type_spec
        l = DataList(self.data_items, type_spec=Item)
        self.assertEqual(l[2], self.data_items[2])
        # With key expr
        l = DataList(self.data_items, key_expr=self.key_item)
        self.assertEqual(l[2], self.data_items[2])
    def test_list_update(self):
        i1 = self.data_items[0]
        l = DataList(self.data_items)
        # Simple
        l[3] = i1
        self.assertEqual(l[3], i1)
        l = DataList(self.data_items, type_spec=Item)
        # With type_spec
        l[3] = i1
        self.assertEqual(l[3], i1)
        with self.assertRaises(TypeError, msg="With type_spec"):
            l[3] = self.data_desc[0]
        # With key expr
        l = DataList(self.data_items, key_expr=self.key_item)
        l[3] = i1
        self.assertEqual(l[3], i1)
        # Frozen
        with self.assertRaises(TypeError):
            l.freeze()
            l[3] = i1
    def test_list_delete(self):
        i1, i2, i3 = self.data_items[:3]
        l = DataList(self.data_items[:3])
        #
        del l[1]
        self.assertListEqual(l, [i1, i3])
        # Frozen
        with self.assertRaises(TypeError):
            l.freeze()
            del l[1]
    def test_remove(self):
        i1, i2, i3 = self.data_items[:3]
        l = DataList(self.data_items[:3])
        #
        l.remove(i2)
        self.assertListEqual(l, [i1, i3])
        # Frozen
        with self.assertRaises(TypeError):
            l.freeze()
            l.remove(i1)
    def test_slice(self):
        i1 = self.data_items[0]
        expect = self.data_items.copy()
        expect[5:6] = [i1]
        l = DataList(self.data_items)
        # Slice read
        self.assertListEqual(l[:], self.data_items[:])
        self.assertListEqual(l[:1],self.data_items[:1])
        self.assertListEqual(l[1:], self.data_items[1:])
        self.assertListEqual(l[2:2], self.data_items[2:2])
        self.assertListEqual(l[2:3], self.data_items[2:3])
        self.assertListEqual(l[2:4], self.data_items[2:4])
        self.assertListEqual(l[-1:], self.data_items[-1:])
        self.assertListEqual(l[:-1], self.data_items[:-1])
        # Slice set
        l[5:6] = [i1]
        self.assertListEqual(l, expect)
        # With type_spec
        l = DataList(self.data_items, Item)
        with self.assertRaises(TypeError):
            l[5:6] = [self.data_desc[0]]
        l[5:6] = [i1]
        self.assertListEqual(l, expect)
        # Slice remove
        l = DataList(self.data_items)
        del l[:]
        self.assertListEqual(l, [])
        # Frozen
        l = DataList(self.data_items)
        with self.assertRaises(TypeError):
            l.freeze()
            del l[:]
    def test_sort(self):
        i1, i2, i3 = self.data_items[:3]
        unsorted = [i3, i1, i2]
        l = DataList(unsorted)
        # Simple
        with self.assertRaises(TypeError):
            l.sort()
        if __debug__:
            with self.assertRaises(AssertionError):
                l.sort(attrs= 'key')
        l.sort(attrs=['key'])
        self.assertListEqual(l, [i1, i2, i3])
        l.sort(attrs=['key'], reverse=True)
        self.assertListEqual(l, [i3, i2, i1])

        l = DataList(unsorted)
        l.sort(expr=lambda x: x.key)
        self.assertListEqual(l, [i1, i2, i3])
        l.sort(expr=lambda x: x.key, reverse=True)
        self.assertListEqual(l, [i3, i2, i1])

        l = DataList(unsorted)
        l.sort(expr='item.key')
        self.assertListEqual(l, [i1, i2, i3])
        l.sort(expr='item.key', reverse=True)
        self.assertListEqual(l, [i3, i2, i1])
        # With key expr
        l = DataList(unsorted, key_expr=self.key_item)
        l.sort()
        self.assertListEqual(l, [i1, i2, i3])
        l.sort(reverse=True)
        self.assertListEqual(l, [i3, i2, i1])
    def test_reverse(self):
        revers = list(reversed(self.data_items))
        l = DataList(self.data_items)
        #
        l.reverse()
        self.assertListEqual(l, revers)
    def test_clear(self):
        l = DataList(self.data_items)
        #
        l.clear()
        self.assertListEqual(l, [])
    def test_freeze(self):
        l = DataList(self.data_items)
        #
        l.freeze()
        self.assertTrue(l.frozen)
        with self.assertRaises(TypeError):
            l[0] = self.data_items[0]
    def test_filter(self):
        l = DataList(self.data_items)
        #
        result = l.filter(lambda x: x.key > 5)
        self.assertIsInstance(result, GeneratorType)
        self.assertListEqual(list(result), self.data_items[5:])
        #
        result = l.filter('item.key > 5')
        self.assertListEqual(list(result), self.data_items[5:])
    def test_filterfalse(self):
        l = DataList(self.data_items)
        #
        result = l.filterfalse(lambda x: x.key > 5)
        self.assertIsInstance(result, GeneratorType)
        self.assertListEqual(list(result), self.data_items[:5])
        #
        result = l.filterfalse('item.key > 5')
        self.assertListEqual(list(result), self.data_items[:5])
    def test_report(self):
        l = DataList(self.data_desc[:2])
        expect = [(1, 'Item 01', "This is item 'Item 01'"),
                  (2, 'Item 02', "This is item 'Item 02'")]
        #
        rpt = l.report(lambda x: (x.key, x.item.name, x.description))
        self.assertIsInstance(rpt, GeneratorType)
        self.assertListEqual(list(rpt), expect)
        #
        rpt = list(l.report('item.key', 'item.item.name', 'item.description'))
        self.assertListEqual(rpt, expect)
    def test_occurrence(self):
        l = DataList(self.data_items)
        expect = sum(1 for x in l if x.key > 5)
        #
        result = l.occurrence(lambda x: x.key > 5)
        self.assertIsInstance(result, int)
        self.assertEqual(result, expect)
        #
        result = l.occurrence('item.key > 5')
        self.assertEqual(result, expect)
    def test_split(self):
        exp_left = [x for x in self.data_items if x.key > 5]
        exp_right = [x for x in self.data_items if not x.key > 5]
        l = DataList(self.data_items)
        #
        res_left, res_right = l.split(lambda x: x.key > 5)
        self.assertIsInstance(res_left, DataList)
        self.assertIsInstance(res_right, DataList)
        self.assertListEqual(res_left, exp_left)
        self.assertListEqual(res_right, exp_right)
        self.assertEqual(len(res_left) + len(res_right), len(l))
        #
        res_left, res_right = l.split('item.key > 5')
        self.assertIsInstance(res_left, DataList)
        self.assertIsInstance(res_right, DataList)
        self.assertListEqual(res_left, exp_left)
        self.assertListEqual(res_right, exp_right)
        self.assertEqual(len(res_left) + len(res_right), len(l))
    def test_extract(self):
        exp_return = [x for x in self.data_items if x.key > 5]
        exp_remains = [x for x in self.data_items if not x.key > 5]
        l = DataList(self.data_items)
        #
        result = l.extract(lambda x: x.key > 5)
        self.assertIsInstance(result, DataList)
        self.assertListEqual(result, exp_return)
        self.assertListEqual(l, exp_remains)
        self.assertEqual(len(result) + len(l), len(self.data_items))
        #
        l = DataList(self.data_items)
        result = l.extract('item.key > 5')
        self.assertListEqual(result, exp_return)
        self.assertListEqual(l, exp_remains)
        self.assertEqual(len(result) + len(l), len(self.data_items))
        # frozen
        with self.assertRaises(TypeError):
            l.freeze()
            l.extract('item.key > 5')
    def test_get(self):
        i5 = self.data_items[4]
        # Simple
        l = DataList(self.data_items)
        with self.assertRaises(Error):
            l.get(i5.key)
        # Distinct type
        l = DataList(self.data_items, type_spec=Item)
        self.assertEqual(l.get(i5.key), i5)
        self.assertIsNone(l.get('NOT IN LIST'))
        self.assertEqual(l.get('NOT IN LIST', 'DEFAULT'), 'DEFAULT')
        # Key spec
        l = DataList(self.data_items, key_expr=self.key_item)
        self.assertEqual(l.get(i5.key), i5)
        self.assertIsNone(l.get('NOT IN LIST'))
        self.assertEqual(l.get('NOT IN LIST', 'DEFAULT'), 'DEFAULT')
        # Frozen (fast-path)
        #   with Distinct
        l = DataList(self.data_items, type_spec=Item, frozen=True)
        self.assertEqual(l.get(i5.key), i5)
        self.assertIsNone(l.get('NOT IN LIST'))
        self.assertEqual(l.get('NOT IN LIST', 'DEFAULT'), 'DEFAULT')
        #   with key_expr
        l = DataList(self.data_items, key_expr='item.key', frozen=True)
        self.assertEqual(l.get(i5.key), i5)
        self.assertIsNone(l.get('NOT IN LIST'))
        self.assertEqual(l.get('NOT IN LIST', 'DEFAULT'), 'DEFAULT')
    def test_find(self):
        i5 = self.data_items[4]
        l = DataList(self.data_items)
        result = l.find(lambda x: x.key >= 5)
        self.assertIsInstance(result, Item)
        self.assertEqual(result, i5)
        self.assertIsNone(l.find(lambda x: x.key > 100))
        self.assertEqual(l.find(lambda x: x.key > 100, 'DEFAULT'), 'DEFAULT')

        self.assertEqual(l.find('item.key >= 5'), i5)
        self.assertIsNone(l.find('item.key > 100'))
        self.assertEqual(l.find('item.key > 100', 'DEFAULT'), 'DEFAULT')
    def test_contains(self):
        # Simple
        l = DataList(self.data_items)
        self.assertTrue(l.contains('item.key >= 5'))
        self.assertTrue(l.contains(lambda x: x.key >= 5))
        self.assertFalse(l.contains('item.key > 100'))
        self.assertFalse(l.contains(lambda x: x.key > 100))
    def test_in(self):
        # Simple
        l = DataList(self.data_items)
        self.assertTrue(self.data_items[0] in l)
        self.assertTrue(self.data_items[-1] in l)
        # Frozen
        l.freeze()
        self.assertTrue(self.data_items[0] in l)
        self.assertTrue(self.data_items[-1] in l)
        # Typed
        l = DataList(self.data_items, Item)
        self.assertTrue(self.data_items[0] in l)
        self.assertTrue(self.data_items[-1] in l)
        # Frozen
        l.freeze()
        self.assertTrue(self.data_items[0] in l)
        self.assertTrue(self.data_items[-1] in l)
        # Keyed
        l = DataList(self.data_items, key_expr='item.key')
        self.assertTrue(self.data_items[0] in l)
        self.assertTrue(self.data_items[-1] in l)
        # Frozen
        l.freeze()
        self.assertTrue(self.data_items[0] in l)
        self.assertTrue(self.data_items[-1] in l)
        nil = Item(100, "NOT IN LISTS")
        i5 = self.data_items[4]
        # Simple
        l = DataList(self.data_items)
        self.assertIn(i5, l)
        self.assertNotIn(nil, l)
        # Frozen distincts
        l = DataList(self.data_items, type_spec=Item, frozen=True)
        self.assertIn(i5, l)
        self.assertNotIn(nil, l)
        # Frozen key_expr
        l = DataList(self.data_items, key_expr=self.key_item, frozen=True)
        self.assertIn(i5, l)
        self.assertNotIn(nil, l)
    def test_all(self):
        l = DataList(self.data_items)
        self.assertTrue(l.all(lambda x: x.name.startswith('Item')))
        self.assertFalse(l.all(lambda x: '1' in x.name))
        self.assertTrue(l.all("item.name.startswith('Item')"))
        self.assertFalse(l.all("'1' in item.name"))
    def test_any(self):
        l = DataList(self.data_items)
        self.assertTrue(l.any(lambda x: '05' in x.name))
        self.assertFalse(l.any(lambda x: x.name.startswith('XXX')))
        self.assertTrue(l.any("'05' in item.name"))
        self.assertFalse(l.any("item.name.startswith('XXX')"))

class TestRegistry(unittest.TestCase):
    """Unit tests for firebird.base.collection.Registry"""
    def setUp(self):
        self.data_items = [Item(1, 'Item 01'), Item(2, 'Item 02'), Item(3, 'Item 03'),
                           Item(4, 'Item 04'), Item(5, 'Item 05'), Item(6, 'Item 06'),
                           Item(7, 'Item 07'), Item(8, 'Item 08'), Item(9, 'Item 09'),
                           Item(10, 'Item 10')]
        self.data_desc = [Desc(item.key, item, "This is item '%s'" % item.name) for item
                          in self.data_items]
        self.key_item = 'item.key'
        self.key_spec = 'item.key'
        self.dict_items = dict((i.key, i) for i in self.data_items)
        self.dict_desc = dict((i.key, i) for i in self.data_desc)
    def tearDown(self):
        pass
    def test_create(self):
        r = Registry()
        # Simple
        self.assertDictEqual(r._reg, {})
        # From items
        with self.assertRaises(TypeError):
            Registry(object)
        r = Registry(self.data_items)
        self.assertSequenceEqual(r._reg.keys(), self.dict_items.keys())
        self.assertListEqual(list(r._reg.values()), list(self.dict_items.values()))
    def test_store(self):
        i1 = self.data_items[0]
        d2 = self.data_desc[1]
        r = Registry()
        r.store(i1)
        self.assertDictEqual(r._reg, {i1.key: i1})
        r.store(d2)
        self.assertDictEqual(r._reg, {i1.key: i1, d2.key: d2,})
        with self.assertRaises(ValueError):
            r.store(i1)
    def test_len(self):
        r = Registry(self.data_items)
        self.assertEqual(len(r), len(self.data_items))
    def test_dict_access(self):
        i5 = self.data_items[4]
        r = Registry(self.data_items)
        self.assertEqual(r[i5], i5)
        self.assertEqual(r[i5.key], i5)
        with self.assertRaises(KeyError):
            r['NOT IN REGISTRY']
    def test_dict_update(self):
        i1 = self.data_items[0]
        d1 = self.data_desc[0]
        r = Registry(self.data_items)
        self.assertEqual(r[i1.key], i1)
        r[i1] = d1
        self.assertEqual(r[i1.key], d1)
    def test_dict_delete(self):
        i1 = self.data_items[0]
        r = Registry(self.data_items)
        self.assertIn(i1, r)
        del r[i1]
        self.assertNotIn(i1, r)
        r.store(i1)
        self.assertIn(i1, r)
        del r[i1.key]
        self.assertNotIn(i1, r)
    def test_dict_iter(self):
        r = Registry(self.data_items)
        self.assertListEqual(list(r), list(self.dict_items.values()))
    def test_remove(self):
        i1 = self.data_items[0]
        r = Registry(self.data_items)
        self.assertIn(i1, r)
        r.remove(i1)
        self.assertNotIn(i1, r)
    def test_in(self):
        nil = Item(100, "NOT IN REGISTRY")
        i1 = self.data_items[0]
        r = Registry(self.data_items)
        self.assertIn(i1, r)
        self.assertIn(i1.key, r)
        self.assertNotIn('NOT IN REGISTRY', r)
        self.assertNotIn(nil, r)
    def test_clear(self):
        r = Registry(self.data_items)
        r.clear()
        self.assertListEqual(list(r), [])
        self.assertEqual(len(r), 0)
    def test_get(self):
        i5 = self.data_items[4]
        r = Registry(self.data_items)
        self.assertEqual(r.get(i5), i5)
        self.assertEqual(r.get(i5.key), i5)
        self.assertIsNone(r.get('NOT IN REGISTRY'))
        self.assertEqual(r.get('NOT IN REGISTRY', i5), i5)
    def test_update(self):
        i1 = self.data_items[0]
        d1 = self.data_desc[0]
        r = Registry(self.data_items)
        # Single item
        self.assertEqual(r[i1.key], i1)
        r.update(d1)
        self.assertEqual(r[i1.key], d1)
        # From list
        r = Registry(self.data_items)
        r.update(self.data_desc)
        self.assertListEqual(list(r), list(self.dict_desc.values()))
        # From dict
        r = Registry(self.data_items)
        r.update(self.dict_desc)
        self.assertListEqual(list(r), list(self.dict_desc.values()))
        # From registry
        r = Registry(self.data_items)
        r_other = Registry(self.data_desc)
        r.update(r_other)
        self.assertListEqual(list(r), list(self.dict_desc.values()))
    def test_extend(self):
        i1 = self.data_items[0]
        # Single item
        r = Registry()
        r.extend(i1)
        self.assertListEqual(list(r), [i1])
        # From list
        r = Registry(self.data_items[:5])
        r.extend(self.data_items[5:])
        self.assertListEqual(list(r), list(self.dict_items.values()))
        # From dict
        r = Registry()
        r.extend(self.dict_items)
        self.assertListEqual(list(r), list(self.dict_items.values()))
        # From registry
        r = Registry()
        r_other = Registry(self.data_items)
        r.extend(r_other)
        self.assertListEqual(list(r), list(self.dict_items.values()))
    def test_copy(self):
        r = Registry(self.data_items)
        r_other = r.copy()
        self.assertListEqual(list(r_other), list(r))
        # Registry descendants
        r = MyRegistry(self.data_items)
        r_other = r.copy()
        self.assertIsInstance(r_other, MyRegistry)
        self.assertListEqual(list(r_other), list(r))
    def test_pop(self):
        icopy = self.data_items.copy()
        i5 = icopy.pop(4)
        r = Registry(self.data_items)
        result = r.pop(i5.key)
        self.assertEqual(result, i5)
        self.assertListEqual(list(r), icopy)

        self.assertIsNone(r.pop('NOT IN REGISTRY'))
        self.assertListEqual(list(r), icopy)

        r = Registry(self.data_items)
        result = r.pop(i5)
        self.assertEqual(result, i5)
        self.assertListEqual(list(r), icopy)
    def test_popitem(self):
        icopy = self.data_items.copy()
        r = Registry(self.data_items)
        self.assertListEqual(list(r), icopy)
        #
        last = icopy.pop()
        result = r.popitem()
        self.assertEqual(result, last)
        self.assertListEqual(list(r), icopy)

        first = icopy.pop(0)
        result = r.popitem(False)
        self.assertEqual(result, first)
        self.assertListEqual(list(r), icopy)
    def test_filter(self):
        r = Registry(self.data_items)
        #
        result = r.filter(lambda x: x.key > 5)
        self.assertIsInstance(result, GeneratorType)
        self.assertListEqual(list(result), self.data_items[5:])
        #
        result = r.filter('item.key > 5')
        self.assertListEqual(list(result), self.data_items[5:])
    def test_filterfalse(self):
        r = Registry(self.data_items)
        #
        result = r.filterfalse(lambda x: x.key > 5)
        self.assertIsInstance(result, GeneratorType)
        self.assertListEqual(list(result), self.data_items[:5])
        #
        result = r.filterfalse('item.key > 5')
        self.assertListEqual(list(result), self.data_items[:5])
    def test_find(self):
        i5 = self.data_items[4]
        r = Registry(self.data_items)
        result = r.find(lambda x: x.key >= 5)
        self.assertIsInstance(result, Item)
        self.assertEqual(result, i5)
        self.assertIsNone(r.find(lambda x: x.key > 100))
        self.assertEqual(r.find(lambda x: x.key > 100, 'DEFAULT'), 'DEFAULT')

        self.assertEqual(r.find('item.key >= 5'), i5)
        self.assertIsNone(r.find('item.key > 100'))
        self.assertEqual(r.find('item.key > 100', 'DEFAULT'), 'DEFAULT')
    def test_contains(self):
        # Simple
        r = Registry(self.data_items)
        self.assertTrue(r.contains('item.key >= 5'))
        self.assertTrue(r.contains(lambda x: x.key >= 5))
        self.assertFalse(r.contains('item.key > 100'))
        self.assertFalse(r.contains(lambda x: x.key > 100))
    def test_report(self):
        r = Registry(self.data_desc[:2])
        expect = [(1, 'Item 01', "This is item 'Item 01'"),
                  (2, 'Item 02', "This is item 'Item 02'")]
        #
        rpt = r.report(lambda x: (x.key, x.item.name, x.description))
        self.assertIsInstance(rpt, GeneratorType)
        self.assertListEqual(list(rpt), expect)
        #
        rpt = list(r.report('item.key', 'item.item.name', 'item.description'))
        self.assertListEqual(rpt, expect)
    def test_occurrence(self):
        r = Registry(self.data_items)
        expect = sum(1 for x in r if x.key > 5)
        #
        result = r.occurrence(lambda x: x.key > 5)
        self.assertIsInstance(result, int)
        self.assertEqual(result, expect)
        #
        result = r.occurrence('item.key > 5')
        self.assertEqual(result, expect)
    def test_all(self):
        r = Registry(self.data_items)
        self.assertTrue(r.all(lambda x: x.name.startswith('Item')))
        self.assertFalse(r.all(lambda x: '1' in x.name))
        self.assertTrue(r.all("item.name.startswith('Item')"))
        self.assertFalse(r.all("'1' in item.name"))
    def test_any(self):
        r = Registry(self.data_items)
        self.assertTrue(r.any(lambda x: '05' in x.name))
        self.assertFalse(r.any(lambda x: x.name.startswith('XXX')))
        self.assertTrue(r.any("'05' in item.name"))
        self.assertFalse(r.any("item.name.startswith('XXX')"))
    def test_repr(self):
        r = Registry(self.data_items)
        self.assertEqual(repr(r), """Registry([Item(key=1, name='Item 01'), Item(key=2, name='Item 02'), Item(key=3, name='Item 03'), Item(key=4, name='Item 04'), Item(key=5, name='Item 05'), Item(key=6, name='Item 06'), Item(key=7, name='Item 07'), Item(key=8, name='Item 08'), Item(key=9, name='Item 09'), Item(key=10, name='Item 10')])""")

if __name__=='__main__':
    unittest.main()
