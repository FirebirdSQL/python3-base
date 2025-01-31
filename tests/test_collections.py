# SPDX-FileCopyrightText: 2019-present The Firebird Projects <www.firebirdsql.org>
#
# SPDX-License-Identifier: MIT
#
# PROGRAM/MODULE: firebird-base
# FILE:           test/test_collections.py
# DESCRIPTION:    Tests for firebird.base.collections
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

from dataclasses import dataclass
from types import GeneratorType

import pytest

from firebird.base.collections import DataList, Registry
from firebird.base.types import UNDEFINED, Distinct, Error

KEY_ITEM = "item.key"
KEY_SPEC = "item.key"

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

@pytest.fixture
def data_items():
    return [Item(1, "Item 01"), Item(2, "Item 02"), Item(3, "Item 03"), Item(4, "Item 04"),
            Item(5, "Item 05"), Item(6, "Item 06"), Item(7, "Item 07"), Item(8, "Item 08"),
            Item(9, "Item 09"), Item(10, "Item 10")]

@pytest.fixture
def data_desc(data_items):
    return [Desc(item.key, item, f"This is item '{item.name}'") for item in data_items]

@pytest.fixture
def dict_items(data_items):
    return {i.key: i for i in data_items}

@pytest.fixture
def dict_desc(data_desc):
    return {i.key: i for i in data_desc}

def test_datalist_create():
    l = DataList()
    assert l == []
    assert not l.frozen
    assert l.key_expr is None
    assert l.type_spec is UNDEFINED

def test_datalist_create_from_items(data_items):
    with pytest.raises(TypeError):
        DataList(object)
    l = DataList(data_items)
    assert l == data_items
    assert not l.frozen
    assert l.key_expr is None
    assert l.type_spec is UNDEFINED

def test_datalist_create_with_typespec(data_items):
    # With type spec (Non-Distinct)
    l = DataList(type_spec=int)
    assert not l.frozen
    assert l.key_expr is None
    # With type spec (Distinct)
    l = DataList(type_spec=Item)
    assert not l.frozen
    assert l.key_expr == "item.get_key()"
    assert l.type_spec == Item
    l = DataList(type_spec=(Item, Desc))
    assert l.key_expr == "item.get_key()"
    assert l.type_spec == (Item, Desc)
    # With key expr
    if __debug__:
        with pytest.raises(AssertionError):
            DataList(key_expr=object)
        with pytest.raises(SyntaxError):
            DataList(key_expr="wrong key expression")
    l = DataList(key_expr=KEY_ITEM)
    assert not l.frozen
    assert l.key_expr == KEY_ITEM
    assert l.type_spec is UNDEFINED
    # With frozen
    l = DataList(frozen=True)
    assert l.frozen
    # With all
    l = DataList(data_items, Item, KEY_ITEM)
    assert l == data_items

def test_datalist_insert(data_items):
    i1, i2, i3 = data_items[:3]
    l = DataList()
    # Simple
    l.insert(0, i1)
    assert l == [i1]
    l.insert(0, i2)
    assert l == [i2, i1]
    l.insert(1, i3)
    assert l == [i2, i3, i1]
    l.insert(5, i3)
    assert l == [i2, i3, i1, i3]

def test_datalist_insert_with_typespec(data_items, data_desc):
    i1, i2, i3 = data_items[:3]
    # With type_spec
    l = DataList(type_spec=Item)
    l.insert(0, i1)
    with pytest.raises(TypeError):
        l.insert(0, data_desc[0])
    # With key expr
    l = DataList(key_expr=KEY_ITEM)
    l.insert(0, i1)
    assert l == [i1]

def test_datalist_insert_to_frozen(data_items):
    l = DataList(data_items)
    with pytest.raises(TypeError):
        l.freeze()
        l.insert(0, data_items[0])

def test_datalist_append(data_items):
    i1, i2 = data_items[:2]
    l = DataList()
    l.append(i1)
    assert l == [i1]
    l.append(i2)
    assert l == [i1, i2]

def test_datalist_append_with_typespec(data_items, data_desc):
    i1 = data_items[0]
    # With type_spec
    l = DataList(type_spec=Item)
    l.append(i1)
    with pytest.raises(TypeError):
        l.insert(0, data_desc[0])
    # With key expr
    l = DataList(key_expr=KEY_ITEM)
    l.append(i1)
    assert l == [i1]

def test_datalist_append_to_frozen(data_items):
    l = DataList()
    with pytest.raises(TypeError):
        l.freeze()
        l.append(data_items[0])

def test_datalist_extend(data_items):
    l = DataList()
    l.extend(data_items)
    assert l == data_items

def test_datalist_extend_with_typespec(data_items, data_desc):
    l = DataList(type_spec=Item)
    l.extend(data_items)
    assert l == data_items
    with pytest.raises(TypeError):
        l.extend(data_desc)
    # With key expr
    l = DataList(key_expr=KEY_ITEM)
    l.extend(data_items)
    assert l == data_items

def test_datalist_extend_frozen(data_items):
    l = DataList()
    with pytest.raises(TypeError):
        l.freeze()
        l.extend(data_items[0])

def test_datalist_list_access(data_items):
    l = DataList(data_items)
    # Simple
    assert l[2] == data_items[2]
    with pytest.raises(IndexError):
        l[20]
    # With type_spec
    l = DataList(data_items, type_spec=Item)
    assert l[2] == data_items[2]
    # With key expr
    l = DataList(data_items, key_expr=KEY_ITEM)
    assert l[2] == data_items[2]

def test_datalist_list_update(data_items):
    i1 = data_items[0]
    l = DataList(data_items)
    l[3] = i1
    assert l[3] == i1

def test_datalist_list_update_with_typespec(data_items, data_desc):
    i1 = data_items[0]
    l = DataList(data_items, type_spec=Item)
    l[3] = i1
    assert l[3] == i1
    with pytest.raises(TypeError):
        l[3] = data_desc[0]
    # With key expr
    l = DataList(data_items, key_expr=KEY_ITEM)
    l[3] = i1
    assert l[3] == i1

def test_datalist_list_update_frozen(data_items):
    i1 = data_items[0]
    l = DataList(data_items)
    with pytest.raises(TypeError):
        l.freeze()
        l[3] = i1

def test_datalist_list_delete(data_items):
    i1, i2, i3 = data_items[:3]
    l = DataList(data_items[:3])
    #
    del l[1]
    assert l == [i1, i3]
    # Frozen
    with pytest.raises(TypeError):
        l.freeze()
        del l[1]

def test_datalist_remove(data_items):
    i1, i2, i3 = data_items[:3]
    l = DataList(data_items[:3])
    #
    l.remove(i2)
    assert l == [i1, i3]
    # Frozen
    with pytest.raises(TypeError):
        l.freeze()
        l.remove(i1)

def test_datalist_slice(data_items):
    i1 = data_items[0]
    expect = data_items.copy()
    expect[5:6] = [i1]
    l = DataList(data_items)
    # Slice read
    assert l[:] == data_items[:]
    assert l[:1] == data_items[:1]
    assert l[1:] == data_items[1:]
    assert l[2:2] == data_items[2:2]
    assert l[2:3] == data_items[2:3]
    assert l[2:4] == data_items[2:4]
    assert l[-1:] == data_items[-1:]
    assert l[:-1] == data_items[:-1]
    # Slice set
    l[5:6] = [i1]
    assert l == expect

def test_datalist_slice_with_typespec(data_items, data_desc):
    i1 = data_items[0]
    expect = data_items.copy()
    expect[5:6] = [i1]
    l = DataList(data_items, Item)
    with pytest.raises(TypeError):
        l[5:6] = [data_desc[0]]
    l[5:6] = [i1]
    assert l == expect
    # Slice remove
    l = DataList(data_items)
    del l[:]
    assert l == []

def test_datalist_slice_update_frozen(data_items):
    l = DataList(data_items)
    with pytest.raises(TypeError):
        l.freeze()
        del l[:]

def test_datalist_sort(data_items):
    i1, i2, i3 = data_items[:3]
    unsorted = [i3, i1, i2]
    l = DataList(unsorted)
    # Simple
    with pytest.raises(TypeError):
        l.sort()
    if __debug__:
        with pytest.raises(AssertionError):
            l.sort(attrs= "key")
    l.sort(attrs=["key"])
    assert l == [i1, i2, i3]
    l.sort(attrs=["key"], reverse=True)
    assert l == [i3, i2, i1]

    l = DataList(unsorted)
    l.sort(expr=lambda x: x.key)
    assert l == [i1, i2, i3]
    l.sort(expr=lambda x: x.key, reverse=True)
    assert l == [i3, i2, i1]

    l = DataList(unsorted)
    l.sort(expr="item.key")
    assert l == [i1, i2, i3]
    l.sort(expr="item.key", reverse=True)
    assert l == [i3, i2, i1]
    # With key expr
    l = DataList(unsorted, key_expr=KEY_ITEM)
    l.sort()
    assert l == [i1, i2, i3]
    l.sort(reverse=True)
    assert l == [i3, i2, i1]

def test_datalist_reverse(data_items):
    revers = list(reversed(data_items))
    l = DataList(data_items)
    l.reverse()
    assert l == revers

def test_datalist_clear(data_items):
    l = DataList(data_items)
    l.clear()
    assert l == []

def test_datalist_freeze(data_items):
    l = DataList(data_items)
    assert not l.frozen
    l.freeze()
    assert l.frozen
    with pytest.raises(TypeError):
        l[0] = data_items[0]

def test_datalist_filter(data_items):
    l = DataList(data_items)
    #
    result = l.filter(lambda x: x.key > 5)
    assert isinstance(result, GeneratorType)
    assert list(result) == data_items[5:]
    #
    result = l.filter("item.key > 5")
    assert list(result) == data_items[5:]

def test_datalist_filterfalse(data_items):
    l = DataList(data_items)
    #
    result = l.filterfalse(lambda x: x.key > 5)
    assert isinstance(result, GeneratorType)
    assert list(result) == data_items[:5]
    #
    result = l.filterfalse("item.key > 5")
    assert list(result) == data_items[:5]

def test_datalist_report(data_desc):
    l = DataList(data_desc[:2])
    expect = [(1, "Item 01", "This is item 'Item 01'"),
              (2, "Item 02", "This is item 'Item 02'")]
    #
    rpt = l.report(lambda x: (x.key, x.item.name, x.description))
    assert isinstance(rpt, GeneratorType)
    assert list(rpt) == expect
    #
    rpt = list(l.report("item.key", "item.item.name", "item.description"))
    assert rpt == expect

def test_datalist_occurrence(data_items):
    l = DataList(data_items)
    expect = sum(1 for x in l if x.key > 5)
    #
    result = l.occurrence(lambda x: x.key > 5)
    assert isinstance(result, int)
    assert result == expect
    #
    result = l.occurrence("item.key > 5")
    assert result == expect

def test_datalist_split_lambda(data_items):
    exp_left = [x for x in data_items if x.key > 5]
    exp_right = [x for x in data_items if not x.key > 5]
    l = DataList(data_items)
    #
    res_left, res_right = l.split(lambda x: x.key > 5)
    assert isinstance(res_left, DataList)
    assert isinstance(res_right, DataList)
    assert res_left == exp_left
    assert res_right == exp_right
    assert len(res_left) + len(res_right) == len(l)

def test_datalist_split_expr(data_items):
    exp_left = [x for x in data_items if x.key > 5]
    exp_right = [x for x in data_items if not x.key > 5]
    l = DataList(data_items)
    #
    res_left, res_right = l.split("item.key > 5")
    assert isinstance(res_left, DataList)
    assert isinstance(res_right, DataList)
    assert res_left == exp_left
    assert res_right == exp_right
    assert len(res_left) + len(res_right) == len(l)

def test_datalist_extract_lambda(data_items):
    exp_return = [x for x in data_items if x.key > 5]
    exp_remains = [x for x in data_items if not x.key > 5]
    l = DataList(data_items)
    #
    result = l.extract(lambda x: x.key > 5)
    assert isinstance(result, DataList)
    assert result == exp_return
    assert l == exp_remains
    assert len(result) + len(l) == len(data_items)

def test_datalist_extract_exprS(data_items):
    exp_return = [x for x in data_items if x.key > 5]
    exp_remains = [x for x in data_items if not x.key > 5]
    l = DataList(data_items)
    #
    result = l.extract("item.key > 5")
    assert isinstance(result, DataList)
    assert result == exp_return
    assert l == exp_remains
    assert len(result) + len(l) == len(data_items)

def test_datalist_extract_from_frozen(data_items):
    l = DataList(data_items)
    # frozen
    with pytest.raises(TypeError):
        l.freeze()
        l.extract("item.key > 5")

def test_datalist_extract_copy(data_items):
    exp_return = [x for x in data_items if x.key > 5]
    exp_remains = [x for x in data_items]
    l = DataList(data_items)
    #
    result = l.extract(lambda x: x.key > 5, copy=True)
    assert isinstance(result, DataList)
    assert result == exp_return
    assert l == exp_remains
    assert len(l) == len(data_items)

def test_datalist_get(data_items):
    i5 = data_items[4]
    # Simple
    l = DataList(data_items)
    with pytest.raises(Error):
        l.get(i5.key)
    # Distinct type
    l = DataList(data_items, type_spec=Item)
    assert l.get(i5.key) == i5
    assert l.get("NOT IN LIST") is None
    assert l.get("NOT IN LIST", "DEFAULT") == "DEFAULT"
    # Key spec
    l = DataList(data_items, key_expr=KEY_ITEM)
    assert l.get(i5.key) == i5
    assert l.get("NOT IN LIST") is None
    assert l.get("NOT IN LIST", "DEFAULT") == "DEFAULT"
    # Frozen (fast-path)
    #   with Distinct
    l = DataList(data_items, type_spec=Item, frozen=True)
    assert l.get(i5.key) == i5
    assert l.get("NOT IN LIST") is None
    assert l.get("NOT IN LIST", "DEFAULT") == "DEFAULT"
    #   with key_expr
    l = DataList(data_items, key_expr="item.key", frozen=True)
    assert l.get(i5.key) == i5
    assert l.get("NOT IN LIST") is None
    assert l.get("NOT IN LIST", "DEFAULT") == "DEFAULT"

def test_datalist_find(data_items):
    i5 = data_items[4]
    l = DataList(data_items)
    result = l.find(lambda x: x.key >= 5)
    assert isinstance(result, Item)
    assert result == i5
    assert l.find(lambda x: x.key > 100) is None
    assert l.find(lambda x: x.key > 100, "DEFAULT") == "DEFAULT"

    assert l.find("item.key >= 5") == i5
    assert l.find("item.key > 100") is None
    assert l.find("item.key > 100", "DEFAULT") == "DEFAULT"

def test_datalist_contains(data_items):
    # Simple
    l = DataList(data_items)
    assert l.contains("item.key >= 5")
    assert l.contains(lambda x: x.key >= 5)
    assert not l.contains("item.key > 100")
    assert not l.contains(lambda x: x.key > 100)

def test_datalist_in(data_items):
    # Simple
    l = DataList(data_items)
    assert data_items[0] in l
    assert data_items[-1] in l
    # Frozen
    l.freeze()
    assert data_items[0] in l
    assert data_items[-1] in l
    # Typed
    l = DataList(data_items, Item)
    assert data_items[0] in l
    assert data_items[-1] in l
    # Frozen
    l.freeze()
    assert data_items[0] in l
    assert data_items[-1] in l
    # Keyed
    l = DataList(data_items, key_expr="item.key")
    assert data_items[0] in l
    assert data_items[-1] in l
    # Frozen
    l.freeze()
    assert data_items[0] in l
    assert data_items[-1] in l
    #
    nil = Item(100, "NOT IN LISTS")
    i5 = data_items[4]
    # Simple
    l = DataList(data_items)
    assert i5 in l
    assert nil not in l
    # Frozen distincts
    l = DataList(data_items, type_spec=Item, frozen=True)
    assert i5 in l
    assert nil not in l
    # Frozen key_expr
    l = DataList(data_items, key_expr=KEY_ITEM, frozen=True)
    assert i5 in l
    assert nil not in l

def test_datalist_all(data_items):
    l = DataList(data_items)
    assert l.all(lambda x: x.name.startswith("Item"))
    assert not l.all(lambda x: "1" in x.name)
    assert l.all("item.name.startswith('Item')")
    assert not l.all("'1' in item.name")

def test_datalist_any(data_items):
    l = DataList(data_items)
    assert l.any(lambda x: "05" in x.name)
    assert not l.any(lambda x: x.name.startswith("XXX"))
    assert l.any("'05' in item.name")
    assert not l.any("item.name.startswith('XXX')")

def test_registry_create(data_items, dict_items):
    r = Registry()
    # Simple
    assert r._reg == {}
    # From items
    with pytest.raises(TypeError):
        Registry(object)
    r = Registry(data_items)
    assert r._reg.keys() == dict_items.keys()
    assert list(r._reg.values()) == list(dict_items.values())

def test_registry_store(data_items, data_desc):
    i1 = data_items[0]
    d2 = data_desc[1]
    r = Registry()
    r.store(i1)
    assert r._reg == {i1.key: i1}
    r.store(d2)
    assert r._reg == {i1.key: i1, d2.key: d2,}
    with pytest.raises(ValueError):
        r.store(i1)

def test_registry_len(data_items):
    r = Registry(data_items)
    assert len(r) == len(data_items)

def test_registry_dict_access(data_items):
    i5 = data_items[4]
    r = Registry(data_items)
    assert r[i5] == i5
    assert r[i5.key] == i5
    with pytest.raises(KeyError):
        r["NOT IN REGISTRY"]

def test_registry_dict_update(data_items, data_desc):
    i1 = data_items[0]
    d1 = data_desc[0]
    r = Registry(data_items)
    assert r[i1.key] == i1
    r[i1] = d1
    assert r[i1.key] == d1

def test_registry_dict_delete(data_items):
    i1 = data_items[0]
    r = Registry(data_items)
    assert i1 in r
    del r[i1]
    assert i1 not in r
    r.store(i1)
    assert i1 in r
    del r[i1.key]
    assert i1 not in r

def test_registry_dict_iter(data_items, dict_items):
    r = Registry(data_items)
    assert list(r) == list(dict_items.values())

def test_registry_remove(data_items):
    i1 = data_items[0]
    r = Registry(data_items)
    assert i1 in r
    r.remove(i1)
    assert i1 not in r

def test_registry_in(data_items):
    nil = Item(100, "NOT IN REGISTRY")
    i1 = data_items[0]
    r = Registry(data_items)
    assert i1 in r
    assert i1.key in r
    assert "NOT IN REGISTRY" not in r
    assert nil not in r

def test_registry_clear(data_items):
    r = Registry(data_items)
    r.clear()
    assert list(r) == []
    assert len(r) == 0

def test_registry_get(data_items):
    i5 = data_items[4]
    r = Registry(data_items)
    assert r.get(i5) == i5
    assert r.get(i5.key) == i5
    assert r.get("NOT IN REGISTRY") is None
    assert r.get("NOT IN REGISTRY", i5) == i5

def test_registry_update(data_items, data_desc, dict_desc):
    i1 = data_items[0]
    d1 = data_desc[0]
    r = Registry(data_items)
    # Single item
    assert r[i1.key] == i1
    r.update(d1)
    assert r[i1.key] == d1
    # From list
    r = Registry(data_items)
    r.update(data_desc)
    assert list(r) == list(dict_desc.values())
    # From dict
    r = Registry(data_items)
    r.update(dict_desc)
    assert list(r) == list(dict_desc.values())
    # From registry
    r = Registry(data_items)
    r_other = Registry(data_desc)
    r.update(r_other)
    assert list(r) == list(dict_desc.values())

def test_registry_extend(data_items, dict_items):
    i1 = data_items[0]
    # Single item
    r = Registry()
    r.extend(i1)
    assert list(r) == [i1]
    # From list
    r = Registry(data_items[:5])
    r.extend(data_items[5:])
    assert list(r) == list(dict_items.values())
    # From dict
    r = Registry()
    r.extend(dict_items)
    assert list(r) == list(dict_items.values())
    # From registry
    r = Registry()
    r_other = Registry(data_items)
    r.extend(r_other)
    assert list(r) == list(dict_items.values())

def test_registry_copy(data_items):
    r = Registry(data_items)
    r_other = r.copy()
    assert list(r_other) == list(r)
    # Registry descendants
    r = MyRegistry(data_items)
    r_other = r.copy()
    assert isinstance(r_other, MyRegistry)
    assert list(r_other) == list(r)

def test_registry_pop(data_items):
    icopy = data_items.copy()
    i5 = icopy.pop(4)
    r = Registry(data_items)
    result = r.pop(i5.key)
    assert result == i5
    assert list(r) == icopy

    assert r.pop("NOT IN REGISTRY") is None
    assert list(r) == icopy

    r = Registry(data_items)
    result = r.pop(i5)
    assert result == i5
    assert list(r) == icopy

def test_registry_popitem(data_items):
    icopy = data_items.copy()
    r = Registry(data_items)
    assert list(r) == icopy
    #
    last = icopy.pop()
    result = r.popitem()
    assert result == last
    assert list(r) == icopy

    first = icopy.pop(0)
    result = r.popitem(last=False)
    assert result == first
    assert list(r) == icopy

def test_registry_filter(data_items):
    r = Registry(data_items)
    #
    result = r.filter(lambda x: x.key > 5)
    assert isinstance(result, GeneratorType)
    assert list(result) == data_items[5:]
    #
    result = r.filter("item.key > 5")
    assert list(result) == data_items[5:]

def test_registry_filterfalse(data_items):
    r = Registry(data_items)
    #
    result = r.filterfalse(lambda x: x.key > 5)
    assert isinstance(result, GeneratorType)
    assert list(result) == data_items[:5]
    #
    result = r.filterfalse("item.key > 5")
    assert list(result) == data_items[:5]

def test_registry_find(data_items):
    i5 = data_items[4]
    r = Registry(data_items)
    result = r.find(lambda x: x.key >= 5)
    assert isinstance(result, Item)
    assert result == i5
    assert r.find(lambda x: x.key > 100) is None
    assert r.find(lambda x: x.key > 100, "DEFAULT") == "DEFAULT"

    assert r.find("item.key >= 5") == i5
    assert r.find("item.key > 100") is None
    assert r.find("item.key > 100", "DEFAULT") == "DEFAULT"

def test_registry_contains(data_items):
    # Simple
    r = Registry(data_items)
    assert r.contains("item.key >= 5")
    assert r.contains(lambda x: x.key >= 5)
    assert not r.contains("item.key > 100")
    assert not r.contains(lambda x: x.key > 100)

def test_registry_report(data_desc):
    r = Registry(data_desc[:2])
    expect = [(1, "Item 01", "This is item 'Item 01'"),
              (2, "Item 02", "This is item 'Item 02'")]
    #
    rpt = r.report(lambda x: (x.key, x.item.name, x.description))
    assert isinstance(rpt, GeneratorType)
    assert list(rpt) == expect
    #
    rpt = list(r.report("item.key", "item.item.name", "item.description"))
    assert rpt == expect

def test_registry_occurrence(data_items):
    r = Registry(data_items)
    expect = sum(1 for x in r if x.key > 5)
    #
    result = r.occurrence(lambda x: x.key > 5)
    assert isinstance(result, int)
    assert result == expect
    #
    result = r.occurrence("item.key > 5")
    assert result == expect

def test_registry_all(data_items):
    r = Registry(data_items)
    assert r.all(lambda x: x.name.startswith("Item"))
    assert not r.all(lambda x: "1" in x.name)
    assert r.all("item.name.startswith('Item')")
    assert not r.all("'1' in item.name")
    with pytest.raises(AttributeError):
        assert r.all("'1' in item.x")

def test_registry_any(data_items):
    r = Registry(data_items)
    assert r.any(lambda x: "05" in x.name)
    assert not r.any(lambda x: x.name.startswith("XXX"))
    assert r.any("'05' in item.name")
    assert not r.any("item.name.startswith('XXX')")
    with pytest.raises(AttributeError):
        assert r.any("'1' in item.x")

def test_registry_repr(data_items):
    r = Registry(data_items)
    assert repr(r) == """Registry([Item(key=1, name='Item 01'), Item(key=2, name='Item 02'), Item(key=3, name='Item 03'), Item(key=4, name='Item 04'), Item(key=5, name='Item 05'), Item(key=6, name='Item 06'), Item(key=7, name='Item 07'), Item(key=8, name='Item 08'), Item(key=9, name='Item 09'), Item(key=10, name='Item 10')])"""

