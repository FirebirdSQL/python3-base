#coding:utf-8
#
# PROGRAM/MODULE: firebird-base
# FILE:           firebird/base/hooks.py
# DESCRIPTION:    Hook manager
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

"""Firebird Base - Hook manager

This module provides a general framework for callbacks and "hookable" events.
"""

from __future__ import annotations
from typing import Union, Any, Type, Dict, List, Set, Callable, cast
from enum import Enum, Flag, auto
from weakref import WeakKeyDictionary
from dataclasses import dataclass, field
from .types import Distinct, ANY, Singleton
from .collections import Registry

@dataclass(order=True, frozen=True)
class Hook(Distinct):
    "Hook registration info"
    event: Any
    cls: type = ANY
    instance: Any = ANY
    callbacks: List = field(default_factory=list)
    def get_key(self) -> Any:
        "Returns hook key"
        return (self.event, self.cls, self.instance)

class HookFlag(Flag):
    "Internally used flags"
    NONE = 0
    INSTANCE = auto()
    CLASS = auto()
    NAME = auto()
    ANY_EVENT = auto()

class HookManager(Singleton):
    """Hook manager."""
    def __init__(self):
        self.obj_map: WeakKeyDictionary = WeakKeyDictionary()
        self.hookables: Dict[Type, Set[Any]] = {}
        self.hooks: Registry = Registry()
        self.flags: HookFlag = HookFlag.NONE
    def _update_flags(self, event: Any, cls: Any, obj: Any) -> None:
        if event is ANY:
            self.flags |= HookFlag.ANY_EVENT
        if cls is not ANY:
            self.flags |= HookFlag.CLASS
        if obj is not ANY:
            if isinstance(obj, str):
                self.flags |= HookFlag.NAME
            else:
                self.flags |= HookFlag.INSTANCE
    def register_class(self, cls: Type, events: Union[Type[Enum], Set]=None) -> None:
        """Register hookable class.

Arguments:
    cls: Class that supports hooks.
    events: Supported events.

Events could be specified using an `~enum.Enum` type or set of event identificators.
When Enum is used (recommended), all enum values are registered as hookable events.
"""
        if isinstance(events, type) and issubclass(events, Enum):
            events = set(events.__members__.values())
        self.hookables[cls] = events
    def register_name(self, instance: Any, name: str) -> None:
        """Associate name with hookable instance.

Arguments:
    instance: Instance of registered hookable class.
    name:     Unique name assigned to instance.
"""
        if not isinstance(instance, tuple(self.hookables.keys())):
            raise TypeError("The instance is not of hookable type")
        self.obj_map[instance] = name
    def add_hook(self, event: Any, source: Any, callback: Callable) -> None:
        """Add new hook.

Arguments:
    event:    Event identificator.
    source:   Hookable class or instance, or instance name.
    callback: Callback function.

Important:
    The signature of `callback` must conform to requirements for particular hookable event.

Raises:
    TypeError: When `subject` is not registered as hookable.
    ValueError: When `event` is not supported by specified `subject`.
"""
        cls = obj = ANY
        if isinstance(source, type):
            if source in self.hookables:
                cls = source
                if event is not ANY:
                    found = False
                    for cls_ in (c for c in self.hookables if issubclass(cls, c)):
                        if event in self.hookables[cls_]:
                            found = True
                            break
                    if not found:
                        raise ValueError(f"Event '{event}' is not supported by '{cls.__name__}'")
            else:
                raise TypeError("The type is not registered as hookable")
        elif isinstance(source, tuple(self.hookables)):
            obj = source
            if event is not ANY:
                found = False
                for cls_ in (c for c in self.hookables if isinstance(obj, c)):
                    if event in self.hookables[cls_]:
                        found = True
                        break
                if not found:
                    raise ValueError(f"Event '{event}' is not supported by '{obj.__class__.__name__}'")
        elif isinstance(source, str):
            obj = source
        else:
            raise TypeError("Subject must be hookable class or instance, or name")
        self._update_flags(event, cls, obj)
        key = (event, cls, obj)
        hook: Hook = self.hooks[key] if key in self.hooks else self.hooks.store(Hook(*key))
        hook.callbacks.append(callback)
    def remove_hook(self, event: Any, source: Any, callback: Callable) -> None:
        """Remove hook callback installed by `add_hook()`.

Arguments:
    event:    Event identificator.
    source:   Hookable class or instance.
    callback: Callback function.

Important:
    For successful removal, the argument values must be exactly the same as used in
    `add_hook()` call.

    The method does nothing if described hook is not installed.
"""
        cls = obj = ANY
        if isinstance(source, type):
            cls = source
        else:
            obj = source
        key = (event, cls, obj)
        hook: Hook = self.hooks.get(key)
        if hook is not None:
            hook.callbacks.remove(callback)
            if not hook.callbacks:
                self.hooks.remove(hook)
                self.flags = HookFlag.NONE
                for h in self.hooks:
                    self._update_flags(h.event, h.cls, h.instance)
    def remove_all_hooks(self) -> None:
        "Removes all installed hooks."
        self.hooks.clear()
        self.flags = HookFlag.NONE
    def reset(self) -> None:
        """Removes all installed hooks and unregisters all hookable classes and instances."""
        self.remove_all_hooks()
        self.hookables.clear()
        self.obj_map.clear()
    def get_callbacks(self, event: Any, source: Any) -> List:
        """Returns list of all callbacks installed for specified event and hookable subject.

Arguments:
    event:  Event identificator.
    source: Hookable class or instance, or name.
"""
        result = []
        if isinstance(source, type):
            if HookFlag.CLASS in self.flags:
                if (hook := self.hooks.get((event, source, ANY))) is not None:
                    result.extend(cast(Hook, hook).callbacks)
                if HookFlag.ANY_EVENT in self.flags and (hook := self.hooks.get((ANY, source, ANY))) is not None:
                    result.extend(cast(Hook, hook).callbacks)
        elif isinstance(source, str):
            if HookFlag.NAME in self.flags:
                if (hook := self.hooks.get((event, ANY, source))) is not None:
                    result.extend(cast(Hook, hook).callbacks)
                if HookFlag.ANY_EVENT in self.flags and (hook := self.hooks.get((ANY, ANY, source))) is not None:
                    result.extend(cast(Hook, hook).callbacks)
        else:
            if HookFlag.INSTANCE in self.flags:
                if (hook := self.hooks.get((event, ANY, source))) is not None:
                    result.extend(cast(Hook, hook).callbacks)
                if HookFlag.ANY_EVENT in self.flags and (hook := self.hooks.get((ANY, ANY, source))) is not None:
                    result.extend(cast(Hook, hook).callbacks)
            if HookFlag.NAME in self.flags and (name := self.obj_map.get(source)) is not None:
                if (hook := self.hooks.get((event, ANY, name))) is not None:
                    result.extend(cast(Hook, hook).callbacks)
                if HookFlag.ANY_EVENT in self.flags and (hook := self.hooks.get((ANY, ANY, name))) is not None:
                    result.extend(cast(Hook, hook).callbacks)
            if HookFlag.CLASS in self.flags:
                for cls in (c for c in self.hookables if isinstance(source, c)):
                    if (hook := self.hooks.get((event, cls, ANY))) is not None:
                        result.extend(cast(Hook, hook).callbacks)
                    if HookFlag.ANY_EVENT in self.flags and (hook := self.hooks.get((ANY, cls, ANY))) is not None:
                        result.extend(cast(Hook, hook).callbacks)
        return result

#: Hook manager
hook_manager: HookManager = HookManager()

register_class = hook_manager.register_class
register_name = hook_manager.register_name
add_hook = hook_manager.add_hook
get_callbacks = hook_manager.get_callbacks
