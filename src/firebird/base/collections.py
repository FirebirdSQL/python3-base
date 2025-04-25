# SPDX-FileCopyrightText: 2020-present The Firebird Projects <www.firebirdsql.org>
#
# SPDX-License-Identifier: MIT
#
# PROGRAM/MODULE: firebird-base
# FILE:           firebird/base/collections.py
# DESCRIPTION:    Various collection types
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
# Copyright (c) 2019 Firebird Project (www.firebirdsql.org)
# All Rights Reserved.
#
# Contributor(s): Pavel Císař (original code)
#                 ______________________________________.

"""Firebird Base - Various collection types

This module provides data structures like `DataList` and `Registry` that behave
much like builtin `list` and `dict` types, respectively, but with direct support
of operations that can use structured data stored in container, and which would
normally require utilization of `operator`, `functools` or other means.

All containers provide next operations:

* `filter` and `filterfalse` that return generator that yields items for which `expr` is
  evaluated as True (or False).
* `find` that returns first item for which `expr` is evaluated as True, or default.
* `contains` that returns True if there is any item for which `expr` is evaluated as True.
* `occurrence` that returns number of items for which `expr` is evaluated as True.
* `all` and `any` that return True if `expr` is evaluated as True for all or any list element(s).
* `report` that returns generator that yields data produced by expression(s) evaluated on
  collection items.

Individual collection types provide additional operations like splitting and extracting
based on expression etc.

Expressions used by these methods could be strings that contain Python expression
referencing the collection item(s), or lambda functions.
"""

from __future__ import annotations

from collections.abc import Callable, Generator, Iterable, Iterator, Mapping, Sequence
from operator import attrgetter
from typing import Any, TypeAlias, TypeVar, cast

from .types import UNDEFINED, Distinct, Error, Sentinel

_T = TypeVar("_T")

def make_lambda(expr: str, params: str='item', context: dict[str, Any] | None=None) -> Callable[..., Any]:
    """Makes lambda function from expression.

    Arguments:
        expr: Python expression as string.
        params: Comma-separated list of names that should be used as lambda parameters
        context: Dictionary passed as `context` to `eval`.

    Note:
        Uses `eval`. Ensure that the `expr` string comes from a trusted source
        if used in security-sensitive contexts.
    """
    return eval(f"lambda {params}:{expr}", context) if context \
           else eval(f"lambda {params}:{expr}") # noqa: S307


#: Collection Item
Item = Any
#: Collection Item type specification
TypeSpec: TypeAlias = type | tuple[type, ...]
#: Collection Item sort expression
ItemExpr: TypeAlias = str | Callable[[Item], Any]
#: Filter expression
FilterExpr: TypeAlias = str | Callable[[Item], bool]
#: Check expression
CheckExpr: TypeAlias = str | Callable[[Item, Any], bool]

class BaseObjectCollection:
    """Base class for collection of objects.
    """
    def filter(self, expr: FilterExpr) -> Generator[Item, None, None]:
        """Returns generator that yields items for which `expr` is evaluated as True.

        Arguments:
            expr: Bool expression, a callable accepting one parameter and returning bool or
                  bool expression as string referencing list item as `item`.

        Example:
            .. code-block:: python

               L.filter(lambda x: x.name.startswith("ABC"))
               L.filter('item.name.startswith("ABC")')
        """
        fce = expr if callable(expr) else make_lambda(expr)
        return (item for item in self if fce(item))
    def filterfalse(self, expr: FilterExpr) -> Generator[Item, None, None]:
        """Returns generator that yields items for which `expr` is evaluated as False.

        Arguments:
            expr: Bool expression, a callable accepting one parameter and returning bool or
                  bool expression as string referencing list item as `item`.

        Example:
            .. code-block:: python

               L.filterfalse(lambda x: x.name.startswith("ABC"))
               L.filterfalse('item.name.startswith("ABC")')
        """
        fce = expr if callable(expr) else make_lambda(expr)
        return (item for item in self if not fce(item))
    def find(self, expr: FilterExpr, default: _T=None) -> Item | _T:
        """Returns first item for which `expr` is evaluated as True, or default.

        Arguments:
            expr:    Bool expression, a callable accepting one parameter and returning bool or
                     bool expression as string referencing list item as `item`.
            default: Default value returned when Items is not found.

        Example:
            .. code-block:: python

               L.find(lambda x: x.name.startswith("ABC"))
               L.find('item.name.startswith("ABC")')
        """
        for item in self.filter(expr):
            return item
        return default
    def contains(self, expr: FilterExpr) -> bool:
        """Returns True if there is any item for which `expr` is evaluated as True.

        Arguments:
            expr: Bool expression, a callable accepting one parameter and returning bool or
                  bool expression as string referencing list item as `item`.

        Example:
            .. code-block:: python

               if L.contains(lambda x: x.name.startswith("ABC")):
                   ...
               if L.contains('item.name.startswith("ABC")'):
                   ...
        """
        fce = expr if callable(expr) else make_lambda(expr)
        for item in self:
            if fce(item):
                return True
        return False
    def report(self, *args) -> Generator[Any, None, None]:
        """Returns generator that yields data produced by expression(s) evaluated on list items.

        Arguments:
            args: Parameter(s) could be one from:

                - A callable accepting one parameter and returning data for output
                - One or more expressions as string referencing item as `item`.

        Example:
            .. code-block:: python

               # generator of tuples with item.name and item.size

               L.report(lambda x: (x.name, x.size))
               L.report('item.name','item.size')

               # generator of item names

               L.report(lambda x: x.name)
               L.report('item.name')
        """
        if len(args) == 1 and callable(args[0]):
            fce = args[0]
        else:
            attrs = f'({",".join(args) if len(args) > 1 else args[0]})'
            fce = make_lambda(attrs)
        return (fce(item) for item in self)
    def occurrence(self, expr: FilterExpr) -> int:
        """Return number of items for which `expr` is evaluated as True.

        Arguments:
            expr: Bool expression, a callable accepting one parameter and returning bool or
                  bool expression as string referencing list item as `item`.

        Example:
            .. code-block:: python

               L.occurrence(lambda x: x.name.startswith("ABC"))
               L.occurrence('item.name.startswith("ABC")')
        """
        return sum(1 for item in self.filter(expr))
    def all(self, expr: FilterExpr) -> bool:
        """Return True if `expr` is evaluated as True for all list elements.

        Arguments:
            expr: Bool expression, a callable accepting one parameter and returning bool or
                  bool expression as string referencing list item as `item`.

        Example:
            .. code-block:: python

               L.all(lambda x: x.name.startswith("ABC"))
               L.all('item.name.startswith("ABC")')
        """
        fce = expr if callable(expr) else make_lambda(expr)
        for item in self:
            if not fce(item):
                return False
        return True
    def any(self, expr: FilterExpr) -> bool:
        """Return True if `expr` is evaluated as True for any list element.

        Arguments:
            expr: Bool expression, a callable accepting one parameter and returnin bool or
                  bool expression as string referencing list item as `item`.

        Note:
            Functionally equivalent to the `contains` method in this class.

        Example:
            .. code-block:: python

               L.any(lambda x: x.name.startswith("ABC"))
               L.any('item.name.startswith("ABC")')
        """
        fce = expr if callable(expr) else make_lambda(expr)
        for item in self:
            if fce(item):
                return True
        return False

class DataList(list[Item], BaseObjectCollection):
    """List of data (objects) with additional functionality.

    Arguments:
        items:     Sequence to initialize the collection.
        type_spec: Reject instances that are not instances of specified types.
        key_expr:  Key expression. Must contain item referrence as `item`, for example
                   `item.attribute_name`. If **all** classes specified in `type_spec`
                   are descendants of `.Distinct`, the default value is `item.get_key()`,
                   otherwise the default is `None`.
        frozen:    Create frozen list.

    Raises:
        ValueError: When initialization sequence contains invalid instance.
    """
    def __init__(self, items: Iterable | None=None, type_spec: TypeSpec=UNDEFINED,
                 key_expr: str | None=None, *, frozen: bool=False):
        assert key_expr is None or isinstance(key_expr, str) # noqa: S101
        assert key_expr is None or make_lambda(key_expr) is not None # noqa: S101
        if items is not None:
            super().__init__(items)
        else:
            super().__init__()
        if type_spec is not UNDEFINED and key_expr is None:
            all_distinct = True
            if isinstance(type_spec, tuple):
                for ts in type_spec:
                    all_distinct = all_distinct and issubclass(ts, Distinct)
            else:
                all_distinct = all_distinct and issubclass(type_spec, Distinct)
            if all_distinct:
                key_expr = 'item.get_key()'
        self.__key_expr: str = key_expr
        self.__frozen: bool = False
        self._type_spec: TypeSpec = type_spec
        self.__map: dict = None
        if frozen:
            self.freeze()
    def __valchk(self, value: Item) -> None:
        if self._type_spec is not UNDEFINED and not isinstance(value, self._type_spec):
            raise TypeError("Value is not an instance of allowed class")
    def __updchk(self) -> None:
        if self.__frozen:
            raise TypeError("Cannot modify frozen DataList")
    def __setitem__(self, index: int | slice, value: Item | Iterable[Item]) -> None:
        """Set item[index] = value. Performs type check and frozen check."""
        self.__updchk()
        if isinstance(index, slice):
            for val in value:
                self.__valchk(val)
        else:
            self.__valchk(value)
        super().__setitem__(index, value)
    def __delitem__(self, index: int | slice) -> None:
        """Delete item[index]. Performs frozen check."""
        self.__updchk()
        super().__delitem__(index)
    def __contains__(self, o) -> bool:
        """Return key in self. Optimized for frozen lists with a key_expr.

        If the list is frozen and has a key_expr, uses an internal map for
        O(1) average time complexity. Otherwise, falls back to standard
        list iteration (O(n)). Handles Distinct instances specifically if
        key_expr matches 'item.get_key()'.
        """
        if self.__map is not None:
            if isinstance(o, Distinct) and self.__key_expr == 'item.get_key()':
                return o.get_key() in self.__map
            return make_lambda(self.__key_expr)(o) in self.__map
        return super().__contains__(o)
    def insert(self, index: int, item: Item) -> None:
        """Insert item before index.

        Raises:
            TypeError: When `item` is not an instance of the allowed `type_spec`,
                       or if the list is frozen.
        """
        self.__updchk()
        self.__valchk(item)
        super().insert(index, item)
    def remove(self, item: Item) -> None:
        """Remove first occurrence of item.

        Raises:
            ValueError: When `item` is not present, or list is frozen
        """
        self.__updchk()
        super().remove(item)
    def append(self, item: Item) -> None:
        """Add an item to the end of the list.

        Raises:
            TypeError: When `item` is not an instance of the allowed `type_spec`,
                       or if the list is frozen.
        """
        self.__updchk()
        self.__valchk(item)
        super().append(item)
    def extend(self, iterable: Iterable[Item]) -> None:
        """Extend the list by appending all the items in the given iterable.

        Raises:
            TypeError: When any `item` in `iterable` is not an instance of the allowed
                       `type_spec`, or if the list is frozen.
        """
        for item in iterable:
            self.append(item)
    def sort(self, attrs: list[str] | tuple[str, ...] | None=None,
             expr: ItemExpr | None=None, *, reverse: bool=False) -> None:
        """Sort items in-place, optionaly using attribute values as key or key expression.

        Arguments:
            attrs: List of attribute names.
            expr: Key expression, a callable accepting one parameter or expression
                   as string referencing list item as `item`.

            Important:
                Only one parameter (`attrs` or `expr`) could be specified.
                If none is present then uses default list sorting rule.

        Example:
            .. code-block:: python

               L.sort(attrs=['name','degree'])       # Sort by item.name, item.degree
               L.sort(expr=lambda x: x.name.upper()) # Sort by upper item.name
               L.sort(expr='item.name.upper()')      # Sort by upper item.name
        """
        assert attrs is None or isinstance(attrs, list | tuple) # noqa: S101
        if attrs:
            super().sort(key=attrgetter(*attrs), reverse=reverse)
        elif expr:
            super().sort(key=expr if callable(expr) else make_lambda(expr), reverse=reverse)
        elif self.__key_expr:
            super().sort(key=make_lambda(self.__key_expr), reverse=reverse)
        else:
            super().sort(reverse=reverse)
    def clear(self) -> None:
        """Remove all items from the list.

        Raises:
            TypeError: When list is frozen.
        """
        self.__updchk()
        super().clear()
    def freeze(self) -> None:
        """Set list to immutable (frozen) state.

        Freezing list makes internal map from `key_expr` to item index that significantly
        speeds up retrieval by key using the `get()` method.

        It's not possible to `add`, `delete` or `change` items in frozen list, but `.sort`
        is allowed.
        """
        self.__frozen = True
        if self.__key_expr:
            fce = make_lambda(self.__key_expr)
            self.__map = {key: index for index, key in enumerate(fce(item) for item in self)}
    def split(self, expr: FilterExpr, *, frozen: bool=False) -> tuple[DataList, DataList]:
        """Return two new `DataList` instances, first with items for which `expr` is
        evaluated as True and second for `expr` evaluated as False.

        Arguments:
            expr: A callable accepting one parameter or expression as string referencing
                  list item as `item`.
            frozen: Create frozen lists.

        Example:
            .. code-block:: python

               below, above = L.split(lambda x: x.size > 100)
               below, above = L.split('item.size > 100')
        """
        return DataList(self.filter(expr), self._type_spec, self.__key_expr, frozen=frozen), \
               DataList(self.filterfalse(expr), self._type_spec, self.__key_expr, frozen=frozen)
    def extract(self, expr: FilterExpr, *, copy: bool=False) -> DataList:
        """Move/copy items for which `expr` is evaluated as True into new `DataList`.

        Arguments:
            expr: A callable accepting one parameter or expression as string referencing list item
                  as `item`.
            copy: When True, items are not removed from source DataList.

        Raises:
            TypeError: When list is frozen and `copy` is False.

        Example:
            .. code-block:: python

               L.extract(lambda x: x.name.startswith("ABC"))
               L.extract('item.name.startswith("ABC")')
        """
        if not copy:
            self.__updchk()
        fce = expr if callable(expr) else make_lambda(expr)
        l = DataList(type_spec=self._type_spec, key_expr=self.__key_expr)
        i = 0
        while len(self) > i:
            item = self[i]
            if fce(item):
                l.append(item)
                if not copy:
                    del self[i]
                else:
                    i += 1
            else:
                i += 1
        return l
    def get(self, key: Any, default: _T=None) -> Item | _T:
        """Returns item with given key using default key expression. Returns `default`
        value if item is not found.

        Uses very fast method to look up value of default key expression in `frozen` list,
        otherwise it uses slower list traversal.

        Arguments:
            key:     Searched value.
            default: Default value.

        Raises:
            Error: If key expression is not defined.

        Example:
            .. code-block:: python

               # Search using default key expression (fast for frozen list)
               L.get('ITEM_NAME')
        """
        if not self.__key_expr:
            raise Error("Key expression required")
        if self.__map:
            i = self.__map.get(key)
            return default if i is None else self[i]
        fce = make_lambda(f'{self.__key_expr} == key', 'item, key')
        for item in self:
            if fce(item, key):
                return item
        return default
    @property
    def frozen(self) -> bool:
        """True if list items couldn't be changed.
        """
        return self.__frozen
    @property
    def key_expr(self) -> Item | None:
        """Key expression.
        """
        return self.__key_expr
    @property
    def type_spec(self) -> TypeSpec | Sentinel:
        """Specification of valid type(s) for list values, or `.UNDEFINED` if there is
        no such constraint.
        """
        return self._type_spec

class Registry(BaseObjectCollection, Mapping[Any, Distinct]):
    """Mapping container for `.Distinct` objects.

    Any method that expects a `key` also acepts `.Distinct` instance.

    To store items into registry with existence check, use:
        - R.store(item)
        - R.extend(items) or R.extend(item)

    To update items in registry (added if not present), use:
        - R[key] = item
        - R.update(items) or R.update(item)

    To check presence of item or key in registry, use:
        - key in R

    To retrieve items from registry, use:
        - R.get(key, default=None)
        - R[key]
        - R.pop(key, default=None)
        - R.popitem(last=True)

    To delete items from registry, use:
        - R.remove(item)
        - del R[key]

    Whenever a `key` is required, you can use either a `.Distinct` instance, or any value
    that represens a key value for instances of stored type.

    Arguments:
        data: Either a `.Distinct` instance, or sequence or mapping of `.Distinct`
              instances.
    """
    def __init__(self, data: Mapping[Any, Distinct] | Sequence[Distinct] | Registry=None):
        self._reg: dict[Any, Distinct] = {}
        if data:
            self.update(data)
    def __len__(self):
        return len(self._reg)
    def __getitem__(self, key: Any) -> Distinct:
        """Return self[key]. Accepts a key value or a `.Distinct` instance."""
        return self._reg[key.get_key() if isinstance(key, Distinct) else key]
    def __setitem__(self, key: Any, value: Distinct) -> None:
        assert isinstance(value, Distinct) # noqa: S101
        self._reg[key.get_key() if isinstance(key, Distinct) else key] = value
    def __delitem__(self, key: Any) -> None:
        del self._reg[key.get_key() if isinstance(key, Distinct) else key]
    def __iter__(self) -> Iterator[Distinct]:
        return iter(self._reg.values())
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}([{', '.join(repr(x) for x in self)}])"
    def __contains__(self, item: Any) -> bool:
        """Return key in self. Accepts a key value or a `.Distinct` instance."""
        if isinstance(item, Distinct):
            item = item.get_key()
        return item in self._reg
    def clear(self) -> None:
        """Remove all items from registry.
        """
        self._reg.clear()
    def get(self, key: Any, default: _T=None) -> Distinct | _T:
        """ D.get(key[,d]) -> D[key] if key in D else d. d defaults to None.

        Arguments:
            key: The key to retrieve (can be the key value or a `.Distinct` instance).
            default: Value to return if key is not found.
        """
        return self._reg.get(key.get_key() if isinstance(key, Distinct) else key, default)
    def store(self, item: Distinct) -> Distinct:
        """Register an item.

        Raises:
            ValueError: When item is already registered.
        """
        assert isinstance(item, Distinct), f"Item is not of type '{Distinct.__name__}'" # noqa: S101
        key = item.get_key()
        if key in self._reg:
            raise ValueError(f"Item already registered, key: '{key}'")
        self._reg[key] = item
        return item
    def remove(self, item: Distinct) -> None:
        """Removes item from registry (same as: del R[item]).
        """
        del self._reg[item.get_key()]
    def update(self, _from: Distinct | Mapping[Any, Distinct] | Sequence[Distinct]) -> None:
        """Update items in the registry.

        Arguments:
            _from: Either a `.Distinct` instance, or sequence or mapping of `.Distinct`
                   instances.
        """
        if isinstance(_from, Distinct):
            self[_from] = _from
        else:
            for item in cast(Mapping, _from).values() if hasattr(_from, 'values') else _from:
                self[item] = item
    def extend(self, _from: Distinct | Mapping[Any, Distinct] | Sequence[Distinct]) -> None:
        """Store one or more items to the registry.

        Unlike `update`, this method requires that the items (or their keys)
        do not already exist in the registry.

        Arguments:
            _from: Either a `.Distinct` instance, or sequence or mapping of `.Distinct`
                   instances.

        Raises:
            ValueError: If an item with the same key is already registered.
        """
        if isinstance(_from, Distinct):
            self.store(_from)
        else:
            for item in cast(Mapping, _from).values() if hasattr(_from, 'values') else _from:
                self.store(item)
    def copy(self) -> Registry:
        """Shalow copy of the registry.
        """
        return self.__class__(self)
    def pop(self, key: Any, default: _T=...) -> Distinct | _T:
        """Remove specified `key` and return the corresponding `.Distinct` object.

        If `key` is not found, the `default` is returned if given, otherwise
        `KeyError` is raised.

        Arguments:
            key: The key to remove (can be the key value or a `.Distinct` instance).
            default: Value to return if key is not found (if not provided, raises `KeyError`).
        """
        if default is ...:
            return self._reg.pop(key.get_key() if isinstance(key, Distinct) else key)
        else:
            return self._reg.pop(key.get_key() if isinstance(key, Distinct) else key, default)
    def popitem(self, *, last: bool=True) -> Distinct:
        """Returns and removes a `.Distinct` object. The objects are returned in LIFO order
        if `last` is true or FIFO order if false.
        """
        if last:
            _, item = self._reg.popitem()
            return item
        try:
            item = next(iter(self))
            self.remove(item)
            return item
        except StopIteration:
            raise KeyError() # noqa: B904
