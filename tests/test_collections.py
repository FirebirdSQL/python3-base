# SPDX-FileCopyrightText: 2019-present The Firebird Projects <www.firebirdsql.org>
#
# SPDX-License-Identifier: MIT
#
# PROGRAM/MODULE: firebird-base
# FILE:           tests/test_collections.py
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

# Assuming collections.py is importable as below
from firebird.base.collections import DataList, Registry, make_lambda
from firebird.base.types import UNDEFINED, Distinct, Error

# --- Test Setup & Fixtures ---

KEY_ITEM = "item.key"
KEY_SPEC = "item.key" # Seems redundant with KEY_ITEM, maybe intended for different tests?

@dataclass(eq=False)
class Item(Distinct):
    """Simple Distinct item for testing collections."""
    key: int
    name: str
    # Make items mutable for shallow copy tests
    mutable_list: list = None # type: ignore

    def __post_init__(self):
        if self.mutable_list is None:
            self.mutable_list = []

    def get_key(self):
        """Returns the key for the Distinct item."""
        return self.key

@dataclass(eq=False)
class Desc(Distinct):
    """Another Distinct item type for testing collections."""
    key: int
    item: Item
    description: str
    def get_key(self):
        """Returns the key for the Distinct item."""
        return self.key

class NonDistinctItem:
    """A class that does not inherit from Distinct."""
    def __init__(self, key, name):
        self.key = key
        self.name = name
    # No get_key method

class MyRegistry(Registry):
    """Subclass of Registry for testing copy behavior."""
    pass

@pytest.fixture
def data_items():
    """Provides a list of Item instances for tests."""
    return [Item(1, "Item 01"), Item(2, "Item 02"), Item(3, "Item 03"), Item(4, "Item 04"),
            Item(5, "Item 05"), Item(6, "Item 06"), Item(7, "Item 07"), Item(8, "Item 08"),
            Item(9, "Item 09"), Item(10, "Item 10")]

@pytest.fixture
def data_desc(data_items):
    """Provides a list of Desc instances linked to data_items."""
    return [Desc(item.key, item, f"This is item '{item.name}'") for item in data_items]

@pytest.fixture
def dict_items(data_items):
    """Provides a dictionary mapping keys to Item instances."""
    return {i.key: i for i in data_items}

@pytest.fixture
def dict_desc(data_desc):
    """Provides a dictionary mapping keys to Desc instances."""
    return {i.key: i for i in data_desc}

# --- Test Functions ---

def test_make_lambda():
    """Tests the make_lambda helper function."""
    # Simple case
    f1 = make_lambda("item + 1")
    assert f1(5) == 6
    # With parameters
    f2 = make_lambda("x * y", params="x, y")
    assert f2(3, 4) == 12
    # With context
    ctx = {"multiplier": 10}
    f3 = make_lambda("val * multiplier", params="val", context=ctx)
    assert f3(7) == 70
    # Syntax Error
    with pytest.raises(SyntaxError):
        make_lambda("item +")

def test_datalist_create():
    """Tests DataList initialization variations."""
    l = DataList()
    assert l == []
    assert not l.frozen
    assert l.key_expr is None
    assert l.type_spec is UNDEFINED

def test_datalist_create_from_items(data_items):
    """Tests DataList initialization with an iterable."""
    # Should not accept non-iterable
    with pytest.raises(TypeError):
        DataList(object) # type: ignore
    # Initialize with list
    l = DataList(data_items)
    assert l == data_items
    assert not l.frozen
    assert l.key_expr is None # No type_spec, so no default key_expr
    assert l.type_spec is UNDEFINED

def test_datalist_create_with_typespec(data_items):
    """Tests DataList initialization with type_spec."""
    # With type spec (Non-Distinct) - key_expr should remain None
    l_int = DataList(type_spec=int)
    assert not l_int.frozen
    assert l_int.key_expr is None
    assert l_int.type_spec == int

    # With type spec (Single Distinct) - key_expr should default
    l_item = DataList(type_spec=Item)
    assert not l_item.frozen
    assert l_item.key_expr == "item.get_key()"
    assert l_item.type_spec == Item

    # With type spec (Tuple of Distinct) - key_expr should default
    l_multi = DataList(type_spec=(Item, Desc))
    assert l_multi.key_expr == "item.get_key()"
    assert l_multi.type_spec == (Item, Desc)

    # With type spec (Tuple mixed Distinct/Non-Distinct) - key_expr should be None
    l_mixed = DataList(type_spec=(Item, int))
    assert l_mixed.key_expr is None
    assert l_mixed.type_spec == (Item, int)


def test_datalist_create_with_keyexpr():
    """Tests DataList initialization with an explicit key_expr."""
    # Invalid key_expr type
    with pytest.raises(AssertionError):
        DataList(key_expr=object) # type: ignore
    # Invalid key_expr syntax
    with pytest.raises(SyntaxError):
        DataList(key_expr="item.")
    # Valid key_expr
    l = DataList(key_expr=KEY_ITEM)
    assert not l.frozen
    assert l.key_expr == KEY_ITEM
    assert l.type_spec is UNDEFINED

def test_datalist_create_frozen():
    """Tests DataList initialization with frozen=True."""
    l = DataList(frozen=True)
    assert l.frozen

def test_datalist_create_all_args(data_items):
    """Tests DataList initialization with items, type_spec, and key_expr."""
    l = DataList(data_items, Item, KEY_ITEM)
    assert l == data_items
    assert l.type_spec == Item
    assert l.key_expr == KEY_ITEM

# --- DataList Modification Tests ---

def test_datalist_insert(data_items):
    """Tests the insert method."""
    i1, i2, i3 = data_items[:3]
    l = DataList()
    l.insert(0, i1)
    assert l == [i1]
    l.insert(0, i2)
    assert l == [i2, i1]
    l.insert(1, i3)
    assert l == [i2, i3, i1]
    # Insert past end behaves like append
    l.insert(5, i3)
    assert l == [i2, i3, i1, i3]

def test_datalist_insert_with_typespec(data_items, data_desc):
    """Tests insert with type specification enforcement."""
    i1 = data_items[0]
    l = DataList(type_spec=Item)
    l.insert(0, i1)
    # Should fail with wrong type
    with pytest.raises(TypeError, match="Value is not an instance of allowed class"):
        l.insert(0, data_desc[0])
    # Should succeed with correct type
    l.insert(0, Item(0, "New Item"))
    assert len(l) == 2

def test_datalist_insert_to_frozen(data_items):
    """Tests that insert raises TypeError on a frozen list."""
    l = DataList(data_items)
    l.freeze()
    with pytest.raises(TypeError, match="Cannot modify frozen DataList"):
        l.insert(0, data_items[0])

def test_datalist_append(data_items):
    """Tests the append method."""
    i1, i2 = data_items[:2]
    l = DataList()
    l.append(i1)
    assert l == [i1]
    l.append(i2)
    assert l == [i1, i2]

def test_datalist_append_with_typespec(data_items, data_desc):
    """Tests append with type specification enforcement."""
    i1 = data_items[0]
    l = DataList(type_spec=Item)
    l.append(i1)
    # Should fail with wrong type
    with pytest.raises(TypeError, match="Value is not an instance of allowed class"):
        l.append(data_desc[0])
    # Should succeed with correct type
    l.append(Item(0, "New Item"))
    assert len(l) == 2

def test_datalist_append_to_frozen(data_items):
    """Tests that append raises TypeError on a frozen list."""
    l = DataList()
    l.freeze()
    with pytest.raises(TypeError, match="Cannot modify frozen DataList"):
        l.append(data_items[0])

def test_datalist_extend(data_items):
    """Tests the extend method."""
    l = DataList()
    l.extend(data_items[:5])
    assert l == data_items[:5]
    l.extend(data_items[5:])
    assert l == data_items

def test_datalist_extend_with_typespec(data_items, data_desc):
    """Tests extend with type specification enforcement."""
    l = DataList(type_spec=Item)
    l.extend(data_items)
    assert l == data_items
    # Should fail if any item in iterable is wrong type
    with pytest.raises(TypeError, match="Value is not an instance of allowed class"):
        l.extend([data_items[0], data_desc[0]]) # Only second item is wrong

def test_datalist_extend_frozen(data_items):
    """Tests that extend raises TypeError on a frozen list."""
    l = DataList()
    l.freeze()
    with pytest.raises(TypeError, match="Cannot modify frozen DataList"):
        l.extend(data_items)

def test_datalist_list_access(data_items):
    """Tests accessing items by index (__getitem__)."""
    l = DataList(data_items)
    assert l[2] is data_items[2]
    assert l[-1] is data_items[-1]
    with pytest.raises(IndexError):
        l[len(data_items)] # Index out of range

def test_datalist_list_update(data_items):
    """Tests updating items by index (__setitem__)."""
    i1 = data_items[0]
    l = DataList(data_items)
    original_item = l[3]
    l[3] = i1
    assert l[3] is i1
    assert l[3] is not original_item

def test_datalist_list_update_with_typespec(data_items, data_desc):
    """Tests __setitem__ with type specification enforcement."""
    i1 = data_items[0]
    l = DataList(data_items, type_spec=Item)
    l[3] = i1 # OK
    assert l[3] is i1
    # Should fail with wrong type
    with pytest.raises(TypeError, match="Value is not an instance of allowed class"):
        l[3] = data_desc[0]

def test_datalist_list_update_frozen(data_items):
    """Tests that __setitem__ raises TypeError on a frozen list."""
    i1 = data_items[0]
    l = DataList(data_items)
    l.freeze()
    with pytest.raises(TypeError, match="Cannot modify frozen DataList"):
        l[3] = i1

def test_datalist_list_delete(data_items):
    """Tests deleting items by index (__delitem__)."""
    i1, i2, i3 = data_items[:3]
    l = DataList(data_items[:3])
    del l[1] # Delete i2
    assert l == [i1, i3]

def test_datalist_list_delete_frozen(data_items):
    """Tests that __delitem__ raises TypeError on a frozen list."""
    l = DataList(data_items)
    l.freeze()
    with pytest.raises(TypeError, match="Cannot modify frozen DataList"):
        del l[1]

def test_datalist_remove(data_items):
    """Tests the remove method."""
    i1, i2, i3 = data_items[:3]
    l = DataList(data_items[:3])
    l.remove(i2) # Remove by value
    assert l == [i1, i3]
    # Test removing item not present
    with pytest.raises(ValueError):
        l.remove(i2)

def test_datalist_remove_frozen(data_items):
    """Tests that remove raises TypeError on a frozen list."""
    l = DataList(data_items)
    l.freeze()
    with pytest.raises(TypeError, match="Cannot modify frozen DataList"):
        l.remove(data_items[0])

def test_datalist_slice_read(data_items):
    """Tests reading slices."""
    l = DataList(data_items)
    assert l[:] == data_items[:]
    assert l[:3] == data_items[:3]
    assert l[5:] == data_items[5:]
    assert l[2:5] == data_items[2:5]
    assert l[-3:] == data_items[-3:]
    assert l[:-2] == data_items[:-2]
    assert l[::2] == data_items[::2]
    assert l[::-1] == data_items[::-1]

def test_datalist_slice_set(data_items):
    """Tests setting slices (__setitem__ with slice)."""
    i1 = data_items[0]
    l = DataList(data_items)
    original_len = len(l)
    # Replace slice
    l[2:5] = [i1, i1]
    assert len(l) == original_len - 1 # 3 removed, 2 added
    assert l[2] is i1
    assert l[3] is i1
    # Insert slice
    l[1:1] = [data_items[5], data_items[6]]
    assert len(l) == original_len + 1 # 2 added
    assert l[1] is data_items[5]
    assert l[2] is data_items[6]

def test_datalist_slice_set_with_typespec(data_items, data_desc):
    """Tests __setitem__ with slice and type checking."""
    i1 = data_items[0]
    l = DataList(data_items, Item)
    # OK
    l[2:4] = [i1]
    assert l[2] is i1
    # Fail with wrong type in iterable
    with pytest.raises(TypeError, match="Value is not an instance of allowed class"):
        l[5:6] = [data_desc[0]]

def test_datalist_slice_set_frozen(data_items):
    """Tests that setting a slice raises TypeError on a frozen list."""
    l = DataList(data_items)
    l.freeze()
    with pytest.raises(TypeError, match="Cannot modify frozen DataList"):
        l[1:3] = [data_items[0]]

def test_datalist_slice_delete(data_items):
    """Tests deleting slices (__delitem__ with slice)."""
    l = DataList(data_items)
    expected = data_items[:2] + data_items[5:]
    del l[2:5]
    assert l == expected

def test_datalist_slice_delete_frozen(data_items):
    """Tests that deleting a slice raises TypeError on a frozen list."""
    l = DataList(data_items)
    l.freeze()
    with pytest.raises(TypeError, match="Cannot modify frozen DataList"):
        del l[2:5]

def test_datalist_sort(data_items):
    """Tests the sort method with various key types."""
    i1, i2, i3 = data_items[:3]
    # Unsortable items without a key
    class Unsortable: pass
    l_unsortable = DataList([Unsortable(), Unsortable()])
    with pytest.raises(TypeError):
        l_unsortable.sort() # Should fail

    unsorted = [i3, i1, i2]
    l = DataList(unsorted)

    # Sort by attributes
    l.sort(attrs=["key"])
    assert l == [i1, i2, i3]
    l.sort(attrs=["key"], reverse=True)
    assert l == [i3, i2, i1]

    # Sort by lambda expression
    l = DataList(unsorted) # Reset
    l.sort(expr=lambda x: x.key)
    assert l == [i1, i2, i3]
    l.sort(expr=lambda x: x.key, reverse=True)
    assert l == [i3, i2, i1]

    # Sort by string expression
    l = DataList(unsorted) # Reset
    l.sort(expr="item.key")
    assert l == [i1, i2, i3]
    l.sort(expr="item.key", reverse=True)
    assert l == [i3, i2, i1]

    # Sort using default key expression
    l = DataList(unsorted, key_expr=KEY_ITEM)
    l.sort()
    assert l == [i1, i2, i3]
    l.sort(reverse=True)
    assert l == [i3, i2, i1]

def test_datalist_reverse(data_items):
    """Tests the reverse method."""
    revers = list(reversed(data_items))
    l = DataList(data_items)
    l.reverse()
    assert l == revers

def test_datalist_clear(data_items):
    """Tests the clear method."""
    l = DataList(data_items)
    l.clear()
    assert l == []

def test_datalist_clear_frozen(data_items):
    """Tests that clear raises TypeError on a frozen list."""
    l = DataList(data_items)
    l.freeze()
    with pytest.raises(TypeError, match="Cannot modify frozen DataList"):
        l.clear()

def test_datalist_freeze(data_items):
    """Tests the freeze method and its effects."""
    l = DataList(data_items, type_spec=Item) # Need key_expr for map
    assert not l.frozen
    assert l._DataList__map is None # Check internal map state

    l.freeze()
    assert l.frozen
    assert isinstance(l._DataList__map, dict) # Map should be created
    assert len(l._DataList__map) == len(data_items)

    # Verify write protection
    with pytest.raises(TypeError, match="Cannot modify frozen DataList"):
        l[0] = data_items[0]
    with pytest.raises(TypeError, match="Cannot modify frozen DataList"):
        l.append(data_items[0])
    with pytest.raises(TypeError, match="Cannot modify frozen DataList"):
        del l[0]
    with pytest.raises(TypeError, match="Cannot modify frozen DataList"):
        l.clear()

# --- BaseObjectCollection Method Tests (via DataList) ---

def test_datalist_filter(data_items):
    """Tests the filter method (inherited from BaseObjectCollection)."""
    l = DataList(data_items)
    # Filter with lambda
    result_lambda = l.filter(lambda x: x.key > 5)
    assert isinstance(result_lambda, GeneratorType)
    assert list(result_lambda) == data_items[5:]
    # Filter with string expression
    result_str = l.filter("item.key > 5")
    assert isinstance(result_str, GeneratorType)
    assert list(result_str) == data_items[5:]

def test_datalist_filterfalse(data_items):
    """Tests the filterfalse method (inherited from BaseObjectCollection)."""
    l = DataList(data_items)
    # Filterfalse with lambda
    result_lambda = l.filterfalse(lambda x: x.key > 5)
    assert isinstance(result_lambda, GeneratorType)
    assert list(result_lambda) == data_items[:5]
    # Filterfalse with string expression
    result_str = l.filterfalse("item.key > 5")
    assert isinstance(result_str, GeneratorType)
    assert list(result_str) == data_items[:5]

def test_datalist_report(data_desc):
    """Tests the report method (inherited from BaseObjectCollection)."""
    l = DataList(data_desc[:2])
    expect = [(1, "Item 01", "This is item 'Item 01'"),
              (2, "Item 02", "This is item 'Item 02'")]
    # Report with lambda
    rpt_lambda = l.report(lambda x: (x.key, x.item.name, x.description))
    assert isinstance(rpt_lambda, GeneratorType)
    assert list(rpt_lambda) == expect
    # Report with string expressions
    rpt_str = l.report("item.key", "item.item.name", "item.description")
    assert isinstance(rpt_str, GeneratorType)
    assert list(rpt_str) == expect
    # Report with single string expression
    rpt_single_str = l.report("item.key")
    assert isinstance(rpt_single_str, GeneratorType)
    assert list(rpt_single_str) == [1, 2]


def test_datalist_occurrence(data_items):
    """Tests the occurrence method (inherited from BaseObjectCollection)."""
    l = DataList(data_items)
    expect = 5 # Items with key > 5
    # Occurrence with lambda
    result_lambda = l.occurrence(lambda x: x.key > 5)
    assert isinstance(result_lambda, int)
    assert result_lambda == expect
    # Occurrence with string expression
    result_str = l.occurrence("item.key > 5")
    assert result_str == expect

def test_datalist_split(data_items):
    """Tests the split method."""
    exp_true = [x for x in data_items if x.key > 5]
    exp_false = [x for x in data_items if not x.key > 5]
    l = DataList(data_items, type_spec=Item, key_expr=KEY_ITEM) # Ensure spec/key propagate

    # Split with lambda
    res_true_l, res_false_l = l.split(lambda x: x.key > 5)
    assert isinstance(res_true_l, DataList)
    assert isinstance(res_false_l, DataList)
    assert res_true_l == exp_true
    assert res_false_l == exp_false
    assert res_true_l.key_expr == KEY_ITEM # Check propagation
    assert res_false_l.type_spec == Item

    # Split with string expression
    res_true_s, res_false_s = l.split("item.key > 5")
    assert isinstance(res_true_s, DataList)
    assert isinstance(res_false_s, DataList)
    assert res_true_s == exp_true
    assert res_false_s == exp_false
    assert res_true_s.key_expr == KEY_ITEM
    assert res_false_s.type_spec == Item

    # Split frozen
    res_true_f, res_false_f = l.split("item.key > 5", frozen=True)
    assert res_true_f.frozen
    assert res_false_f.frozen

def test_datalist_extract(data_items):
    """Tests the extract method."""
    exp_extracted = [x for x in data_items if x.key > 5]
    exp_remaining = [x for x in data_items if not x.key > 5]
    original_len = len(data_items)

    # Extract with lambda (move)
    l = DataList(data_items, type_spec=Item, key_expr=KEY_ITEM) # Ensure spec/key propagate
    result_lambda = l.extract(lambda x: x.key > 5)
    assert isinstance(result_lambda, DataList)
    assert result_lambda == exp_extracted
    assert l == exp_remaining
    assert len(result_lambda) + len(l) == original_len
    assert result_lambda.key_expr == KEY_ITEM # Check propagation
    assert result_lambda.type_spec == Item

    # Extract with string expression (move)
    l = DataList(data_items, type_spec=Item, key_expr=KEY_ITEM) # Reset
    result_str = l.extract("item.key > 5")
    assert isinstance(result_str, DataList)
    assert result_str == exp_extracted
    assert l == exp_remaining
    assert len(result_str) + len(l) == original_len
    assert result_str.key_expr == KEY_ITEM
    assert result_str.type_spec == Item

def test_datalist_extract_copy(data_items):
    """Tests the extract method with copy=True."""
    exp_extracted = [x for x in data_items if x.key > 5]
    original_len = len(data_items)
    l = DataList(data_items, type_spec=Item, key_expr=KEY_ITEM)

    result = l.extract(lambda x: x.key > 5, copy=True)
    assert isinstance(result, DataList)
    assert result == exp_extracted
    assert l == data_items # Original list unchanged
    assert len(l) == original_len
    assert result.key_expr == KEY_ITEM # Check propagation
    assert result.type_spec == Item


def test_datalist_extract_from_frozen(data_items):
    """Tests that extract (move) raises TypeError on a frozen list."""
    l = DataList(data_items)
    l.freeze()
    # Extract copy should work
    extracted_copy = l.extract("item.key > 5", copy=True)
    assert len(extracted_copy) > 0
    assert l == data_items # Original unchanged
    # Extract move should fail
    with pytest.raises(TypeError, match="Cannot modify frozen DataList"):
        l.extract("item.key > 5") # copy=False is default

def test_datalist_get(data_items):
    """Tests the get method for retrieving items by key."""
    i5 = data_items[4]
    # Without key_expr defined
    l_nokey = DataList(data_items)
    with pytest.raises(Error, match="Key expression required"):
        l_nokey.get(i5.key)

    # With key_expr (unfrozen)
    l_key = DataList(data_items, key_expr=KEY_ITEM)
    assert l_key.get(i5.key) is i5
    assert l_key.get(999) is None # Not found
    assert l_key.get(999, "DEFAULT") == "DEFAULT" # Not found with default

    # With key_expr (frozen) - uses fast path
    l_key.freeze()
    assert l_key.get(i5.key) is i5
    assert l_key.get(999) is None # Not found
    assert l_key.get(999, "DEFAULT") == "DEFAULT" # Not found with default

    # With default key_expr via Distinct type_spec (frozen)
    l_distinct = DataList(data_items, type_spec=Item, frozen=True)
    assert l_distinct.get(i5.key) is i5
    assert l_distinct.get(999) is None
    assert l_distinct.get(999, "DEFAULT") == "DEFAULT"

def test_datalist_find(data_items):
    """Tests the find method (inherited from BaseObjectCollection)."""
    i5 = data_items[4]
    l = DataList(data_items)
    # Find with lambda
    result_lambda = l.find(lambda x: x.key >= 5)
    assert isinstance(result_lambda, Item)
    assert result_lambda is i5 # Should be the first match
    assert l.find(lambda x: x.key > 100) is None # Not found
    assert l.find(lambda x: x.key > 100, "DEFAULT") == "DEFAULT" # Not found with default

    # Find with string expression
    result_str = l.find("item.key >= 5")
    assert result_str is i5
    assert l.find("item.key > 100") is None
    assert l.find("item.key > 100", "DEFAULT") == "DEFAULT"

def test_datalist_contains(data_items):
    """Tests the contains method (inherited from BaseObjectCollection)."""
    l = DataList(data_items)
    # Contains with lambda
    assert l.contains(lambda x: x.key == 5)
    assert not l.contains(lambda x: x.key == 999)
    # Contains with string expression
    assert l.contains("item.key == 5")
    assert not l.contains("item.key == 999")

def test_datalist_in(data_items):
    """Tests the `in` operator (__contains__) for DataList."""
    nil = Item(100, "NOT IN LISTS")
    i5 = data_items[4]

    # Simple DataList (uses standard list __contains__)
    l_simple = DataList(data_items)
    assert i5 in l_simple
    assert nil not in l_simple

    # Frozen distincts (uses fast map lookup via key)
    l_frozen_distinct = DataList(data_items, type_spec=Item, frozen=True)
    assert i5 in l_frozen_distinct # Looks up i5.get_key() in map
    assert nil not in l_frozen_distinct

    # Frozen with key_expr (uses fast map lookup via key)
    l_frozen_keyexpr = DataList(data_items, key_expr=KEY_ITEM, frozen=True)
    assert i5 in l_frozen_keyexpr # Evaluates key_expr(i5) and looks up in map
    assert nil not in l_frozen_keyexpr

def test_datalist_all(data_items):
    """Tests the all method (inherited from BaseObjectCollection)."""
    l = DataList(data_items)
    # All with lambda
    assert l.all(lambda x: x.key > 0)
    assert not l.all(lambda x: x.key < 5)
    # All with string expression
    assert l.all("item.key > 0")
    assert not l.all("item.key < 5")
    # Test on empty list
    assert DataList().all("item.key > 0") # Should be True for empty list

def test_datalist_any(data_items):
    """Tests the any method (inherited from BaseObjectCollection)."""
    l = DataList(data_items)
    # Any with lambda
    assert l.any(lambda x: x.key == 5)
    assert not l.any(lambda x: x.key == 999)
    # Any with string expression
    assert l.any("item.key == 5")
    assert not l.any("item.key == 999")
    # Test on empty list
    assert not DataList().any("item.key > 0") # Should be False for empty list


# --- Registry Tests ---

def test_registry_create(data_items, dict_items):
    """Tests Registry initialization."""
    # Empty
    r_empty = Registry()
    assert r_empty._reg == {}

    # From sequence of Distinct items
    r_seq = Registry(data_items)
    assert list(r_seq._reg.keys()) == list(dict_items.keys()) # Check keys
    assert list(r_seq._reg.values()) == list(dict_items.values()) # Check values

    # From mapping (dict) of Distinct items
    r_map = Registry(dict_items)
    assert list(r_map._reg.keys()) == list(dict_items.keys())
    assert list(r_map._reg.values()) == list(dict_items.values())

    # From another Registry
    r_other = Registry(r_seq)
    assert list(r_other._reg.keys()) == list(dict_items.keys())
    assert list(r_other._reg.values()) == list(dict_items.values())

    # From non-iterable (should fail)
    with pytest.raises(TypeError):
        Registry(object()) # type: ignore

def test_registry_store(data_items, data_desc):
    """Tests the store method for adding new items."""
    i1 = data_items[0]
    d2 = data_desc[1]
    r = Registry()

    # Store new items
    r.store(i1)
    assert r._reg == {i1.key: i1}
    r.store(d2)
    assert r._reg == {i1.key: i1, d2.key: d2}

    # Store item with existing key (should fail)
    i1_again = Item(i1.key, "Different Name")
    with pytest.raises(ValueError, match=f"Item already registered, key: '{i1.key}'"):
        r.store(i1_again)

    # Store non-Distinct item (should fail)
    with pytest.raises(AssertionError, match="Item is not of type 'Distinct'"):
        r.store(NonDistinctItem(99, "Fail")) # type: ignore

def test_registry_len(data_items):
    """Tests the __len__ method."""
    r = Registry(data_items)
    assert len(r) == len(data_items)
    r_empty = Registry()
    assert len(r_empty) == 0

def test_registry_dict_access(data_items):
    """Tests accessing items by key or Distinct instance (__getitem__)."""
    i5 = data_items[4]
    r = Registry(data_items)
    # Access by Distinct instance
    assert r[i5] is i5
    # Access by key
    assert r[i5.key] is i5
    # Access non-existent key
    with pytest.raises(KeyError):
        r[999]
    with pytest.raises(KeyError):
        r[Item(999, "Not There")]

def test_registry_dict_update(data_items, data_desc):
    """Tests updating/adding items via __setitem__."""
    i1 = data_items[0]
    d1 = data_desc[0] # Same key as i1
    d_new = data_desc[1] # New key
    r = Registry(data_items)

    # Update existing item using Distinct instance as key
    assert r[i1.key] is i1
    r[i1] = d1 # Replace item at key i1.key with d1
    assert r[i1.key] is d1
    assert len(r) == len(data_items) # Length should be unchanged

    # Update existing item using key
    r[i1.key] = i1 # Change back
    assert r[i1.key] is i1

    # Add new item using key
    r[d_new.key] = d_new
    assert r[d_new.key] is d_new
    assert len(r) == len(data_items) # Length increased if key was new

    # Add new item using Distinct instance as key
    d_newer = data_desc[2]
    r[d_newer] = d_newer
    assert r[d_newer.key] is d_newer

    # Add non-Distinct item (should fail)
    non_distinct = NonDistinctItem(99, "Fail")
    with pytest.raises(AssertionError):
        r[99] = non_distinct # type: ignore

def test_registry_dict_delete(data_items):
    """Tests deleting items by key or Distinct instance (__delitem__)."""
    i1 = data_items[0]
    i2_key = data_items[1].key
    r = Registry(data_items)
    original_len = len(r)

    # Delete by Distinct instance
    assert i1 in r
    del r[i1]
    assert i1 not in r
    assert len(r) == original_len - 1

    # Delete by key
    assert i2_key in r
    del r[i2_key]
    assert i2_key not in r
    assert len(r) == original_len - 2

    # Delete non-existent key
    with pytest.raises(KeyError):
        del r[999]
    with pytest.raises(KeyError):
        del r[Item(999, "Not There")]


def test_registry_dict_iter(data_items, dict_items):
    """Tests iterating over the registry (should yield values)."""
    r = Registry(data_items)
    # Order isn't guaranteed, but content should match
    assert set(r) == set(dict_items.values())
    assert len(list(r)) == len(data_items)

def test_registry_remove(data_items):
    """Tests the remove method (removes by Distinct instance)."""
    i1 = data_items[0]
    r = Registry(data_items)
    assert i1 in r
    r.remove(i1)
    assert i1 not in r
    # Test removing item not present (should raise KeyError via __delitem__)
    with pytest.raises(KeyError):
        r.remove(i1)

def test_registry_in(data_items):
    """Tests the `in` operator (__contains__)."""
    nil = Item(100, "NOT IN REGISTRY")
    i1 = data_items[0]
    r = Registry(data_items)
    # Check by Distinct instance
    assert i1 in r
    assert nil not in r
    # Check by key
    assert i1.key in r
    assert nil.key not in r
    # Check by other type (should be False)
    assert "random string" not in r

def test_registry_clear(data_items):
    """Tests the clear method."""
    r = Registry(data_items)
    assert len(r) > 0
    r.clear()
    assert len(r) == 0
    assert r._reg == {}

def test_registry_get(data_items):
    """Tests the get method."""
    i5 = data_items[4]
    r = Registry(data_items)
    # Get by Distinct instance
    assert r.get(i5) is i5
    # Get by key
    assert r.get(i5.key) is i5
    # Get non-existent key (no default)
    assert r.get(999) is None
    # Get non-existent key (with default)
    assert r.get(999, "DEFAULT") == "DEFAULT"
    # Get non-existent Distinct instance (with default)
    assert r.get(Item(999, "Not There"), "DEFAULT") == "DEFAULT"

def test_registry_update(data_items, data_desc, dict_items, dict_desc):
    """Tests the update method with various sources."""
    i1 = data_items[0]
    d1 = data_desc[0] # Same key as i1
    d_new = data_desc[1] # New key

    # Update with single Distinct instance (adds or replaces)
    r = Registry(data_items)
    assert r[i1.key] is i1
    r.update(d1) # Replace i1 with d1
    assert r[i1.key] is d1
    r.update(d_new) # Add d_new
    assert r[d_new.key] is d_new

    # Update from sequence
    r = Registry(data_items[:5])
    r.update(data_desc[5:]) # Add remaining items as Desc
    assert len(r) == len(data_items)
    assert isinstance(r[data_items[6].key], Desc)

    # Update from dict
    r = Registry(data_items)
    r.update(dict_desc) # Replace all items with Desc versions
    assert len(r) == len(data_items)
    assert isinstance(r[i1.key], Desc)

    # Update from registry
    r = Registry(data_items)
    r_other = Registry(data_desc)
    r.update(r_other) # Replace all items with Desc versions
    assert len(r) == len(data_items)
    assert isinstance(r[i1.key], Desc)

    # Update with non-Distinct item (should fail)
    non_distinct = NonDistinctItem(99, "Fail")
    with pytest.raises(AssertionError):
        r.update([non_distinct]) # type: ignore


def test_registry_extend(data_items, data_desc, dict_items):
    """Tests the extend method (only adds new items)."""
    i1 = data_items[0]
    d1 = data_desc[0] # Same key as i1
    d_new = data_desc[1] # New key

    # Extend with single Distinct instance
    r = Registry()
    r.extend(i1)
    assert r[i1.key] is i1
    # Extend with existing key (should fail)
    with pytest.raises(ValueError, match=f"Item already registered, key: '{d1.key}'"):
        r.extend(d1)

    # Extend from sequence
    r = Registry(data_items[:5])
    with pytest.raises(ValueError, match="Item already registered"):
        r.extend(data_items[3:7]) # Fails when trying to add items with keys 3, 4, 5
    # Let's try extending only with new items
    r = Registry(data_items[:5])
    r.extend(data_items[5:]) # Add 6 through 10
    assert len(r) == len(data_items)

    # Extend from dict
    r = Registry()
    r.extend(dict_items)
    assert len(r) == len(dict_items)

    # Extend from registry
    r = Registry()
    r_other = Registry(data_items)
    r.extend(r_other)
    assert len(r) == len(data_items)

    # Extend with non-Distinct item (should fail)
    non_distinct = NonDistinctItem(99, "Fail")
    with pytest.raises(AssertionError):
        r.extend([non_distinct]) # type: ignore

def test_registry_copy(data_items):
    """Tests the copy method, including subclass and shallow copy behavior."""
    r = Registry(data_items)
    r_copy = r.copy()

    # Check type and content
    assert isinstance(r_copy, Registry)
    assert not isinstance(r_copy, MyRegistry) # Ensure it's not the subclass
    assert r_copy is not r # Different objects
    assert r_copy._reg is not r._reg # Different underlying dicts
    assert list(r_copy) == list(r) # Same values (references)
    assert r_copy[data_items[0].key] is r[data_items[0].key] # Items are the same reference

    # Test shallow copy behavior
    key_to_modify = data_items[0].key
    r_copy[key_to_modify].name = "Modified Name"
    assert r[key_to_modify].name == "Modified Name" # Original is affected
    r[key_to_modify].mutable_list.append("Modified in Original")
    assert "Modified in Original" in r_copy[key_to_modify].mutable_list # Copy is affected

    # Test copy for subclass
    r_sub = MyRegistry(data_items)
    r_sub_copy = r_sub.copy()
    assert isinstance(r_sub_copy, MyRegistry) # Copy is instance of subclass
    assert list(r_sub_copy) == list(r_sub)

def test_registry_pop(data_items):
    """Tests the pop method."""
    i5 = data_items[4]
    r = Registry(data_items)
    original_len = len(r)

    # Pop by key
    popped_item = r.pop(i5.key)
    assert popped_item is i5
    assert len(r) == original_len - 1
    assert i5.key not in r

    # Pop by Distinct instance
    i1 = data_items[0]
    popped_item_2 = r.pop(i1)
    assert popped_item_2 is i1
    assert len(r) == original_len - 2
    assert i1 not in r

    # Pop non-existent key (with default)
    assert r.pop(999, "DEFAULT") == "DEFAULT"
    assert len(r) == original_len - 2 # Length unchanged

    # Pop non-existent key (without default - raises KeyError)
    with pytest.raises(KeyError):
        r.pop(999)

def test_registry_popitem(data_items):
    """Tests the popitem method."""
    r = Registry(data_items)
    original_len = len(r)
    popped_items = set()

    # Pop last (LIFO) until empty
    for _ in range(original_len):
        key, item = r._reg.popitem() # Use internal dict popitem LIFO behavior
        r._reg[key] = item # Put back temporarily to simulate Registry.popitem
        popped = r.popitem() # Default is last=True
        assert isinstance(popped, Item)
        popped_items.add(popped.key)
        assert len(r) == original_len - len(popped_items)

    assert len(r) == 0
    assert popped_items == set(item.key for item in data_items)

    # Pop first (FIFO) until empty
    r.update(data_items) # Refill registry
    popped_items.clear()
    # Need to know the insertion order for FIFO test, dicts preserve it >= 3.7
    ordered_keys = [item.key for item in data_items]

    for i in range(original_len):
        popped = r.popitem(last=False)
        assert popped.key == ordered_keys[i] # Check FIFO order
        popped_items.add(popped.key)
        assert len(r) == original_len - len(popped_items)

    assert len(r) == 0
    assert popped_items == set(item.key for item in data_items)

    # Popitem on empty registry
    with pytest.raises(KeyError):
        r.popitem()
    with pytest.raises(KeyError):
        r.popitem(last=False)


# --- BaseObjectCollection Method Tests (via Registry) ---
# These tests verify that filter, find etc. work on the *values* of the Registry

def test_registry_filter(data_items):
    """Tests the filter method for Registry."""
    r = Registry(data_items)
    # Filter with lambda
    result_lambda = r.filter(lambda item: item.key > 5)
    assert isinstance(result_lambda, GeneratorType)
    assert list(result_lambda) == data_items[5:]
    # Filter with string expression
    result_str = r.filter("item.key > 5")
    assert isinstance(result_str, GeneratorType)
    assert list(result_str) == data_items[5:]

def test_registry_filterfalse(data_items):
    """Tests the filterfalse method for Registry."""
    r = Registry(data_items)
    # Filterfalse with lambda
    result_lambda = r.filterfalse(lambda item: item.key > 5)
    assert isinstance(result_lambda, GeneratorType)
    assert list(result_lambda) == data_items[:5]
    # Filterfalse with string expression
    result_str = r.filterfalse("item.key > 5")
    assert isinstance(result_str, GeneratorType)
    assert list(result_str) == data_items[:5]

def test_registry_find(data_items):
    """Tests the find method for Registry."""
    # Need predictable order for find 'first' - use data_items directly
    i5 = data_items[4] # Key=5
    i6 = data_items[5] # Key=6
    r = Registry(data_items)

    # Find with lambda
    result_lambda = r.find(lambda item: item.key >= 5)
    # Order isn't guaranteed by find on dict values, assert presence instead of exact item
    assert isinstance(result_lambda, Item)
    assert result_lambda.key >= 5
    # Find not found
    assert r.find(lambda item: item.key > 100) is None
    assert r.find(lambda item: item.key > 100, "DEFAULT") == "DEFAULT" # Not found with default

    # Find with string expression
    result_str = r.find("item.key >= 5")
    assert isinstance(result_str, Item)
    assert result_str.key >= 5
    # Find not found
    assert r.find("item.key > 100") is None
    assert r.find("item.key > 100", "DEFAULT") == "DEFAULT"

def test_registry_contains(data_items):
    """Tests the contains method for Registry."""
    r = Registry(data_items)
    # Contains with lambda
    assert r.contains(lambda item: item.key == 5)
    assert not r.contains(lambda item: item.key == 999)
    # Contains with string expression
    assert r.contains("item.key == 5")
    assert not r.contains("item.key == 999")

def test_registry_report(data_desc):
    """Tests the report method for Registry."""
    r = Registry(data_desc[:2]) # Items with keys 1, 2
    expect = [(1, "Item 01", "This is item 'Item 01'"),
              (2, "Item 02", "This is item 'Item 02'")]
    # Report with lambda
    rpt_lambda = r.report(lambda x: (x.key, x.item.name, x.description))
    assert isinstance(rpt_lambda, GeneratorType)
    # Order isn't guaranteed, sort results for comparison
    assert sorted(list(rpt_lambda)) == sorted(expect)
    # Report with string expressions
    rpt_str = r.report("item.key", "item.item.name", "item.description")
    assert isinstance(rpt_str, GeneratorType)
    assert sorted(list(rpt_str)) == sorted(expect)
    # Report with single string expression
    rpt_single_str = r.report("item.key")
    assert isinstance(rpt_single_str, GeneratorType)
    assert sorted(list(rpt_single_str)) == sorted([1, 2])


def test_registry_occurrence(data_items):
    """Tests the occurrence method for Registry."""
    r = Registry(data_items)
    expect = 5 # Items with key > 5
    # Occurrence with lambda
    result_lambda = r.occurrence(lambda item: item.key > 5)
    assert isinstance(result_lambda, int)
    assert result_lambda == expect
    # Occurrence with string expression
    result_str = r.occurrence("item.key > 5")
    assert result_str == expect

def test_registry_all(data_items):
    """Tests the all method for Registry."""
    r = Registry(data_items)
    # All with lambda
    assert r.all(lambda item: item.key > 0)
    assert not r.all(lambda item: item.key < 5)
    # All with string expression
    assert r.all("item.key > 0")
    assert not r.all("item.key < 5")
    # Test on empty registry
    assert Registry().all("item.key > 0") # Should be True

def test_registry_any(data_items):
    """Tests the any method for Registry."""
    r = Registry(data_items)
    # Any with lambda
    assert r.any(lambda item: item.key == 5)
    assert not r.any(lambda item: item.key == 999)
    # Any with string expression
    assert r.any("item.key == 5")
    assert not r.any("item.key == 999")
    # Test on empty registry
    assert not Registry().any("item.key > 0") # Should be False

def test_registry_repr(data_items):
    """Tests the __repr__ method for Registry."""
    r = Registry(data_items[:2]) # Use fewer items for readability
    # Representation depends on the order items are iterated from the dict
    # We can check the basic format and the presence of items
    repr_str = repr(r)
    assert repr_str.startswith("Registry([")
    assert repr_str.endswith("])")
    assert repr(data_items[0]) in repr_str
    assert repr(data_items[1]) in repr_str
    assert ", " in repr_str # Separator between items
