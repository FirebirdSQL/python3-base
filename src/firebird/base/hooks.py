# SPDX-FileCopyrightText: 2020-present The Firebird Projects <www.firebirdsql.org>
#
# SPDX-License-Identifier: MIT
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

This module provides a general framework for callbacks and "hookable" events,
implementing a variation of the publish-subscribe pattern. It allows different
parts of an application to register interest in events triggered by specific
objects or classes and execute custom code (callbacks) when those events occur.

Architecture
------------

The callback extension mechanism is based on the following:

* The `Event source` provides one or more "hookable events" that work like connection points.
  The event source represents "origin of event" and is always identified by class, class
  instance or name. Event sources that are identified by classes (or their instances) must
  be registered along with events they provide.
* `Event` is typically linked to particular event source, but it's not mandatory and it's
  possible to define global events. Event is represented as value of any type, that must
  be unique in used context (particular event source or global).

  Each event should be properly documented along with required signature for callback
  function.
* `Event provider` is a class or function that implements the event for event source, and
  asks the `.hook_manager` for list of event consumers (callbacks) registered for particular
  event and source.
* `Event consumer` is a function or class method that implements the callback for particular
  event. The callback must be registered in `.hook_manager` before it could be called by
  event providers.


The architecture supports multiple usage strategies:

* If event provider uses class instance to identify the event source, it's possible to
  register callbacks to all instances (by registering to class), or particular instance(s).
* It's possible to register callback to particular instance by name, if instance is associated
  with name by `register_name()` function.
* It's possible to register callback to `.ANY` event from particular source, or particular
  event from `.ANY` source, or even to `.ANY` event from `.ANY` source.

Example
-------

.. code-block:: python

   from __future__ import annotations
   from enum import Enum, auto
   from firebird.base.types import *
   from firebird.base.hooks import hook_manager

   class MyEvents(Enum):
       "Sample definition of events"
       CREATE = auto()
       ACTION = auto()

   class MyHookable:
       "Example of hookable class, i.e. a class that calls hooks registered for events."
       def __init__(self, name: str):
           self.name: str = name
           for hook in hook_manager.get_callbacks(MyEvents.CREATE, self):
               try:
                   hook(self, MyEvents.CREATE)
               except Exception as e:
                   print(f"{self.name}.CREATE hook call outcome: ERROR ({e.args[0]})")
               else:
                   print(f"{self.name}.CREATE hook call outcome: OK")
       def action(self):
           print(f"{self.name}.ACTION!")
           for hook in hook_manager.get_callbacks(MyEvents.ACTION, self):
               try:
                   hook(self, MyEvents.ACTION)
               except Exception as e:
                   print(f"{self.name}.ACTION hook call outcome: ERROR ({e.args[0]})")
               else:
                   print(f"{self.name}.ACTION hook call outcome: OK")

   class MyHook:
       "Example of hook implementation"
       def __init__(self, name: str):
           self.name: str = name
       def callback(self, subject: MyHookable, event: MyEvents):
           print(f"Hook {self.name} event {event.name} called by {subject.name}")
       def err_callback(self, subject: MyHookable, event: MyEvents):
           self.callback(subject, event)
           raise Exception("Error in hook")


   # Example code that installs and uses hooks

   hook_manager.register_class(MyHookable, MyEvents)
   hook_A: MyHook = MyHook('Hook-A')
   hook_B: MyHook = MyHook('Hook-B')
   hook_C: MyHook = MyHook('Hook-C')

   print("Install hooks")
   hook_manager.add_hook(MyEvents.CREATE, MyHookable, hook_A.callback)
   hook_manager.add_hook(MyEvents.CREATE, MyHookable, hook_B.err_callback)
   hook_manager.add_hook(MyEvents.ACTION, MyHookable, hook_C.callback)

   print("Create event sources, emits CREATE")
   src_A: MyHookable = MyHookable('Source-A')
   src_B: MyHookable = MyHookable('Source-B')

   print("Install instance hooks")
   hook_manager.add_hook(MyEvents.ACTION, src_A, hook_A.callback)
   hook_manager.add_hook(MyEvents.ACTION, src_B, hook_B.callback)

   print("And action!")
   src_A.action()
   src_B.action()

Output from sample code::

   Install hooks
   Create event sources, emits CREATE
   Hook Hook-A event CREATE called by Source-A
   Source-A.CREATE hook call outcome: OK
   Hook Hook-B event CREATE called by Source-A
   Source-A.CREATE hook call outcome: ERROR (Error in hook)
   Hook Hook-A event CREATE called by Source-B
   Source-B.CREATE hook call outcome: OK
   Hook Hook-B event CREATE called by Source-B
   Source-B.CREATE hook call outcome: ERROR (Error in hook)
   Install instance hooks
   And action!
   Source-A.ACTION!
   Hook Hook-A event ACTION called by Source-A
   Source-A.ACTION hook call outcome: OK
   Hook Hook-C event ACTION called by Source-A
   Source-A.ACTION hook call outcome: OK
   Source-B.ACTION!
   Hook Hook-B event ACTION called by Source-B
   Source-B.ACTION hook call outcome: OK
   Hook Hook-C event ACTION called by Source-B
   Source-B.ACTION hook call outcome: OK
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum, Flag, auto
from typing import Any, cast
from weakref import WeakKeyDictionary

from .collections import Registry
from .types import ANY, Distinct, Singleton


@dataclass(order=True, frozen=True)
class Hook(Distinct):
    """Represents a registered hook subscription.

    Instances of this class store the details of a callback registered
    for a specific event and source combination within the `HookManager`.

    Arguments:
        event: The specific event this hook subscribes to (can be `ANY`).
        cls: The specific class this hook targets. `ANY` if targeting an instance/name directly or globally.
        instance: The specific instance or instance name this hook targets. `ANY` if targeting a class or globally.
        callbacks: A list of callable functions to be executed when the specified event occurs for the specified source.
    """
    #: The specific event this hook subscribes to (can be `ANY`).
    event: Any
    #: The specific class this hook targets. `ANY` if targeting an instance/name directly or globally.
    cls: type = ANY
    #: The specific instance or instance name this hook targets. `ANY` if targeting a class or globally.
    instance: Any = ANY
    #: A list of callable functions to be executed when the specified event occurs for the specified source.
    callbacks: list[Callable] = field(default_factory=list)
    def get_key(self) -> Any:
        """Returns the unique key for this hook registration used by the Registry.

        The key is a tuple of (event, class, instance/name).
        """
        return (self.event, self.cls, self.instance)

class HookFlag(Flag):
    """Internal flags used by HookManager to optimize callback lookups.

    These flags track the *types* of registrations present (e.g., if any
    instance hooks, class hooks, or ANY_EVENT hooks exist) to potentially
    speed up `get_callbacks` by avoiding unnecessary checks.
    """
    NONE = 0
    INSTANCE = auto()   # A hook targets a specific object instance
    CLASS = auto()      # A hook targets a class (applies to all instances)
    NAME = auto()       # A hook targets a registered instance name
    ANY_EVENT = auto()  # A hook targets ANY event

class HookManager(Singleton):
    """Manages the registration and retrieval of hooks (callbacks).

    This singleton class acts as the central registry for hookable classes,
    named instances, and the hooks themselves. It provides methods to add,
    remove, and retrieve callbacks based on event and source specifications.
    """
    def __init__(self):
        self.obj_map: WeakKeyDictionary[Any, str] = WeakKeyDictionary()
        self.hookables: dict[type, set[Any]] = {}
        self.hooks: Registry = Registry()
        self.flags: HookFlag = HookFlag.NONE
    def _update_flags(self, event: Any, cls: type, obj: Any) -> None:
        if event is ANY:
            self.flags |= HookFlag.ANY_EVENT
        if cls is not ANY:
            self.flags |= HookFlag.CLASS
        if obj is not ANY:
            self.flags |= HookFlag.NAME if isinstance(obj, str) else HookFlag.INSTANCE
    def register_class(self, cls: type, events: type[Enum] | set | None=None) -> None:
        """Register a class as being capable of generating hookable events.

        Registration is necessary for validation when adding hooks and potentially
        for optimizing callback lookups.

        Arguments:
            cls: The class that acts as an event source.
            events: The set of events this class (and its instances) can trigger.
                    Can be specified using an `~enum.Enum` type (recommended),
                    a `set` of event identifiers, or `None` if events are not
                    statically known or validated at registration time.

        Raises:
            TypeError: If `events` is provided but is not an Enum type or a set.
        """
        event_set = set()
        if events is not None:
            if isinstance(events, type) and issubclass(events, Enum):
                event_set = set(events.__members__.values())
            elif isinstance(events, set):
                event_set = events
            else:
                raise TypeError("`events` must be an Enum type or a set")
        self.hookables[cls] = event_set # Store the processed set
    def register_name(self, instance: Any, name: str) -> None:
        """Associate a unique string name with an instance of a hookable class.

        This allows registering hooks specifically for this named instance using
        the name string as the `source`.

        Arguments:
            instance: An instance of a class previously registered via `register_class`.
            name:     A unique string name to assign to the instance.

        Raises:
            TypeError: If `instance` is not an instance of any registered hookable class.
        """
        if not isinstance(instance, tuple(self.hookables.keys())):
            raise TypeError("The instance is not of hookable type")
        self.obj_map[instance] = name
    def add_hook(self, event: Any, source: Any, callback: Callable) -> None:
        """Register a callback function (hook) for a specific event and source.

        Arguments:
            event:    The event identifier the callback subscribes to. Can be `ANY`
                      to subscribe to all events from the specified source.
            source:   The source of the event. Can be:

                      - A hookable class (registered via `register_class`): The callback
                        will trigger for this event from *any* instance of this class.
                      - An instance of a hookable class: The callback will trigger
                        only for this event from *this specific* instance.
                      - A string name (registered via `register_name`): The callback
                        will trigger only for this event from the instance associated
                        with this name.
                      - `ANY`: The callback will trigger for this event from *any* source.
            callback: The function or method to be called when the event occurs.

        Important:
            The signature of the `callback` function must match the signature expected
            by the code that *triggers* the event (the event provider). This framework
            does not enforce signature matching; it's the responsibility of the event
            provider and consumer documentation.

        Raises:
            TypeError: If `source` is a class/instance type not registered as hookable,
                       or if `source` is not a class, instance, name, or `ANY`.
            ValueError: If `event` is not `ANY` and is not declared as a supported event
                        by the specified `source` class (during `register_class`).
        """
        cls: type = ANY
        obj: Any = ANY
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
        """Remove a previously registered hook callback.

        Arguments:
            event:    The event identifier used when registering the hook.
            source:   The hookable class, instance, name, or `ANY` used when registering.
            callback: The specific callback function instance that was registered.

        Important:
            To successfully remove a hook, all arguments (`event`, `source`, `callback`)
            must *exactly* match the values used in the original `add_hook()` call.
            Comparing function objects requires using the *same* function object.

            This method does nothing if no matching hook registration is found.
        """
        cls: type = ANY
        obj: Any = ANY
        if isinstance(source, type):
            cls = source
        else:
            obj = source
        key = (event, cls, obj)
        hook: Hook | None = self.hooks.get(key)
        if hook is not None:
            hook.callbacks.remove(callback)
            if not hook.callbacks:
                self.hooks.remove(hook)
                self.flags = HookFlag.NONE
                for h in self.hooks:
                    self._update_flags(h.event, h.cls, h.instance)
    def remove_all_hooks(self) -> None:
        """Removes all installed hooks.
        """
        self.hooks.clear()
        self.flags = HookFlag.NONE
    def reset(self) -> None:
        """Removes all installed hooks and unregisters all hookable classes and instances.
        """
        self.remove_all_hooks()
        self.hookables.clear()
        self.obj_map.clear()
    def get_callbacks(self, event: Any, source: Any) -> list:
        """Return a list of all callbacks applicable to the specified event and source.

        The method searches for matching hook registrations based on the provided
        `event` and `source`, considering class hierarchy, registered names, and
        the `ANY` sentinel for broader matches.

        Arguments:
            event:  The specific event identifier being triggered.
            source: The source triggering the event. Can be:

                    - An instance of a hookable class.
                    - A hookable class itself (e.g., for class-level events).
                    - A registered string name.

                    Note:
                       Using `ANY` as the `source` here is generally not meaningful,
                       as event triggers typically originate from a specific source.

        Returns:
            A list of `Callable` objects. The order reflects the lookup process but
            is not guaranteed between different calls or manager states.

        Lookup Logic:
            The returned list aggregates callbacks from registrations matching:

            1. Specific Instance: Hooks registered for (`event`, `ANY`, `source` instance).
            2. Specific Name: Hooks for (`event`, `ANY`, `source` name) if `source` instance
               has a registered name.
            3. Specific Class: Hooks for (`event`, `cls`, `ANY`) for every class `cls` in
               the `source` instance's Method Resolution Order (MRO) that is registered.
            4. ANY Event on Instance: Hooks for (`ANY`, `ANY`, `source` instance).
            5. ANY Event on Name: Hooks for (`ANY`, `ANY`, `source` name`) if applicable.
            6. ANY Event on Class: Hooks for (`ANY`, `cls`, `ANY`) for applicable classes `cls`
               in the MRO.

        Note:
           If `source` is a class or name directly, only relevant parts of the
           above logic apply.
        """
        result: list[Callable] = []
        hook: Hook | None
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

#: Hook manager singleton instance.
hook_manager: HookManager = HookManager()

#: Shortcut for `hook_manager.register_class()`
register_class = hook_manager.register_class
#: shortcut for `hook_manager.register_name()`
register_name = hook_manager.register_name
#: shortcut for `hook_manager.add_hook()`
add_hook = hook_manager.add_hook
#: shortcut for `hook_manager.get_callbacks()`
get_callbacks = hook_manager.get_callbacks
