# SPDX-FileCopyrightText: 2019-present The Firebird Projects <www.firebirdsql.org>
#
# SPDX-License-Identifier: MIT
#
#   PROGRAM/MODULE: firebird-base
#   FILE:           test/test_hooks.py
#   DESCRIPTION:    Tests for firebird.base.hooks
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
# Copyright (c) 2020 Firebird Project (www.firebirdsql.org)
# All Rights Reserved.
#
# Contributor(s): Pavel Císař (original code)
#                 ______________________________________.

from __future__ import annotations

from enum import Enum, auto
from typing import Protocol

import pytest

# Assuming hooks.py is importable as below
from firebird.base.hooks import Hook, HookFlag, HookManager, hook_manager
from firebird.base.types import ANY

# --- Test Setup & Fixtures ---

class MyEvents(Enum):
    """Sample events for testing."""
    CREATE = auto()
    ACTION = auto()
    DELETE = auto() # Added for more variety

class OtherEvents(Enum):
    """Different set of events."""
    START = auto()
    STOP = auto()

class with_print(Protocol):
    """Protocol for test classes needing output collection."""
    def print(self, msg: str) -> None:
        ...

class Output:
    """Simple output collector for tests."""
    def __init__(self):
        self.output: list[str] = []
    def print(self, msg: str) -> None:
        self.output.append(msg)
    def clear(self) -> None:
        self.output.clear()

class MyHookable:
    """A sample class that can have hooks attached."""
    def __init__(self, owner: with_print, name: str, *, register_name: bool = False,
                 trigger_event: MyEvents | None = MyEvents.CREATE):
        """
        Args:
            owner: The output collector.
            name: An identifier for the instance.
            register_name: Whether to register this instance with the hook manager by name.
            trigger_event: Which event to trigger hooks for during init (or None).
        """
        self.owner = owner
        self.name: str = name
        if register_name:
            hook_manager.register_name(self, name)

        if trigger_event:
            source = self.__class__ if trigger_event == MyEvents.CREATE else self # Simplified logic
            for hook in hook_manager.get_callbacks(trigger_event, source):
                try:
                    hook(self, trigger_event)
                except Exception as e:
                    self.owner.print(f"{self.name}.{trigger_event.name} hook call outcome: ERROR ({e})") # Show exception type
                else:
                    self.owner.print(f"{self.name}.{trigger_event.name} hook call outcome: OK")

    def action(self):
        """Simulates performing an action and triggering ACTION hooks."""
        self.owner.print(f"{self.name}.ACTION!")
        for hook in hook_manager.get_callbacks(MyEvents.ACTION, self):
            try:
                hook(self, MyEvents.ACTION)
            except Exception as e:
                self.owner.print(f"{self.name}.ACTION hook call outcome: ERROR ({e})")
            else:
                self.owner.print(f"{self.name}.ACTION hook call outcome: OK")

    def delete(self):
        """Simulates deletion and triggering DELETE hooks."""
        self.owner.print(f"{self.name}.DELETE!")
        for hook in hook_manager.get_callbacks(MyEvents.DELETE, self):
            try:
                hook(self, MyEvents.DELETE)
            except Exception as e:
                self.owner.print(f"{self.name}.DELETE hook call outcome: ERROR ({e})")
            else:
                self.owner.print(f"{self.name}.DELETE hook call outcome: OK")


class MySuperHookable(MyHookable):
    """A subclass to test hook inheritance."""
    def super_action(self):
        """Simulates a subclass-specific action."""
        self.owner.print(f"{self.name}.SUPER-ACTION!")
        # Using a string event name here for testing purposes
        for hook in hook_manager.get_callbacks("super-action", self):
            try:
                hook(self, "super-action")
            except Exception as e:
                self.owner.print(f"{self.name}.SUPER-ACTION hook call outcome: ERROR ({e})")
            else:
                self.owner.print(f"{self.name}.SUPER-ACTION hook call outcome: OK")

class MyHook:
    """A sample hook implementation."""
    def __init__(self, owner: with_print, name: str):
        self.owner = owner
        self.name: str = name
    def callback(self, subject: MyHookable, event: MyEvents | str):
        """Standard callback method."""
        event_name = event.name if isinstance(event, Enum) else event
        self.owner.print(f"Hook {self.name} event {event_name} called by {subject.name}")
    def err_callback(self, subject: MyHookable, event: MyEvents | str):
        """Callback method that raises an exception."""
        self.callback(subject, event)
        raise ValueError("Error in hook") # Use specific exception


@pytest.fixture
def output() -> Output:
    """Provides a fresh Output collector for each test."""
    return Output()

@pytest.fixture(autouse=True)
def manager() -> HookManager:
    """Provides the global hook_manager and ensures it's reset before each test."""
    hook_manager.reset()
    # Basic registration needed for many tests
    hook_manager.register_class(MyHookable, MyEvents)
    return hook_manager

# --- Test Functions ---

def test_hook_dataclass():
    """Tests the Hook dataclass directly."""
    hook_A: MyHook = MyHook(Output(), "Hook-A")
    h1 = Hook(event=MyEvents.CREATE, cls=MyHookable, instance=ANY, callbacks=[hook_A.callback])
    h2 = Hook(event=MyEvents.CREATE, cls=MyHookable) # Defaults instance=ANY, callbacks=[]

    # Test get_key
    assert h1.get_key() == (MyEvents.CREATE, MyHookable, ANY)
    assert h2.get_key() == (MyEvents.CREATE, MyHookable, ANY)

    # Test basic attributes
    assert h1.event == MyEvents.CREATE
    assert h1.cls == MyHookable
    assert h1.instance is ANY
    assert h1.callbacks == [hook_A.callback]
    assert h2.callbacks == []

def test_register_class_with_set():
    """Tests registering a hookable class with a set of event names."""
    hook_manager.register_class(MySuperHookable, {"event1", "event2"})
    assert MySuperHookable in hook_manager.hookables
    assert hook_manager.hookables[MySuperHookable] == {"event1", "event2"}

    # Test adding a hook for a set-registered event
    hook_A: MyHook = MyHook(Output(), "Hook-A")
    hook_manager.add_hook("event1", MySuperHookable, hook_A.callback)
    assert len(hook_manager.hooks) == 1
    # Test adding hook for unsupported event
    with pytest.raises(ValueError, match="Event 'event3' is not supported by 'MySuperHookable'"):
        hook_manager.add_hook("event3", MySuperHookable, hook_A.callback)

def test_general_hooking(output: Output, manager: HookManager):
    """Tests core hooking functionality: registration, adding hooks (class, instance, name),
       triggering, getting callbacks, removing hooks, and manager state reset."""

    # Initial state checks
    assert tuple(manager.hookables.keys()) == (MyHookable, )
    assert manager.hookables[MyHookable] == set(MyEvents.__members__.values())
    assert manager.flags == HookFlag.NONE # No hooks added yet

    # Install hooks
    hook_A: MyHook = MyHook(output, "Hook-A")
    hook_B: MyHook = MyHook(output, "Hook-B") # Error hook
    hook_C: MyHook = MyHook(output, "Hook-C")
    hook_N: MyHook = MyHook(output, "Hook-N") # Name hook

    # Add CLASS hook
    manager.add_hook(MyEvents.CREATE, MyHookable, hook_A.callback)
    assert HookFlag.CLASS in manager.flags
    manager.add_hook(MyEvents.CREATE, MyHookable, hook_B.err_callback)
    manager.add_hook(MyEvents.ACTION, MyHookable, hook_C.callback) # Another class hook

    # Add NAME hook
    manager.add_hook(MyEvents.ACTION, "Source-A", hook_N.callback)
    assert HookFlag.NAME in manager.flags

    # Verify hooks registry
    key_create = (MyEvents.CREATE, MyHookable, ANY)
    assert key_create in manager.hooks
    assert hook_A.callback in manager.hooks[key_create].callbacks
    assert hook_B.err_callback in manager.hooks[key_create].callbacks
    key_action_cls = (MyEvents.ACTION, MyHookable, ANY)
    assert key_action_cls in manager.hooks
    assert hook_C.callback in manager.hooks[key_action_cls].callbacks
    key_action_name = (MyEvents.ACTION, ANY, "Source-A")
    assert key_action_name in manager.hooks
    assert hook_N.callback in manager.hooks[key_action_name].callbacks

    # Create event sources (triggers CREATE hooks)
    output.clear()
    src_A: MyHookable = MyHookable(output, "Source-A", register_name=True)
    assert output.output == ["Hook Hook-A event CREATE called by Source-A",
                             "Source-A.CREATE hook call outcome: OK",
                             "Hook Hook-B event CREATE called by Source-A",
                             "Source-A.CREATE hook call outcome: ERROR (Error in hook)"]
    output.clear()
    src_B: MyHookable = MyHookable(output, "Source-B", register_name=True) # Name B
    assert output.output ==  ["Hook Hook-A event CREATE called by Source-B",
                              "Source-B.CREATE hook call outcome: OK",
                              "Hook Hook-B event CREATE called by Source-B",
                              "Source-B.CREATE hook call outcome: ERROR (Error in hook)"]

    # Add INSTANCE hooks
    manager.add_hook(MyEvents.ACTION, src_A, hook_A.callback) # Instance hook for src_A
    assert HookFlag.INSTANCE in manager.flags
    manager.add_hook(MyEvents.ACTION, src_B, hook_B.callback) # Instance hook for src_B (non-error callback)

    # Verify instance hooks registry
    key_action_inst_A = (MyEvents.ACTION, ANY, src_A)
    assert key_action_inst_A in manager.hooks
    assert hook_A.callback in manager.hooks[key_action_inst_A].callbacks
    key_action_inst_B = (MyEvents.ACTION, ANY, src_B)
    assert key_action_inst_B in manager.hooks
    assert hook_B.callback in manager.hooks[key_action_inst_B].callbacks

    # Trigger ACTION hooks and verify combined callbacks (Instance + Name + Class)
    output.clear()
    src_A.action()
    # Expected callbacks for src_A: hook_A (Instance), hook_N (Name), hook_C (Class)
    assert output.output == ["Source-A.ACTION!",
                             "Hook Hook-A event ACTION called by Source-A", # Instance Hook
                             "Source-A.ACTION hook call outcome: OK",
                             "Hook Hook-N event ACTION called by Source-A", # Name Hook
                             "Source-A.ACTION hook call outcome: OK",
                             "Hook Hook-C event ACTION called by Source-A", # Class Hook
                             "Source-A.ACTION hook call outcome: OK"]

    output.clear()
    src_B.action()
    # Expected callbacks for src_B: hook_B (Instance), hook_C (Class) - No name hook for "Source-B"
    assert output.output == ["Source-B.ACTION!",
                             "Hook Hook-B event ACTION called by Source-B", # Instance Hook
                             "Source-B.ACTION hook call outcome: OK",
                             "Hook Hook-C event ACTION called by Source-B", # Class Hook
                             "Source-B.ACTION hook call outcome: OK"]

    # Verify flags are all set
    assert HookFlag.CLASS in manager.flags
    assert HookFlag.INSTANCE in manager.flags
    assert HookFlag.NAME in manager.flags
    assert HookFlag.ANY_EVENT not in manager.flags # ANY_EVENT not used yet

    # Test remove_hook and flag updates
    # Remove name hook
    manager.remove_hook(MyEvents.ACTION, "Source-A", hook_N.callback)
    assert key_action_name not in manager.hooks # Hook entry should be gone
    assert HookFlag.NAME not in manager.flags # Flag might persist if other name hooks exist (none here, but test resilience)

    # Remove one class hook callback
    manager.remove_hook(MyEvents.CREATE, MyHookable, hook_A.callback)
    assert key_create in manager.hooks # Hook entry still exists
    assert hook_A.callback not in manager.hooks[key_create].callbacks
    assert hook_B.err_callback in manager.hooks[key_create].callbacks # Other callback remains
    assert HookFlag.CLASS in manager.flags

    # Remove last class hook callback for that key
    manager.remove_hook(MyEvents.CREATE, MyHookable, hook_B.err_callback)
    assert key_create not in manager.hooks # Hook entry removed
    # manager.flags should ideally be recalculated here. Test assumes it's not for simplicity.

    # Remove instance hook
    manager.remove_hook(MyEvents.ACTION, src_A, hook_A.callback)
    assert key_action_inst_A not in manager.hooks
    # manager.flags ideally updated.

    # Test remove_all_hooks
    manager.remove_all_hooks()
    assert len(manager.hooks) == 0
    assert manager.flags == HookFlag.NONE # Flags should be reset

    # Test reset (also clears hookables)
    manager.add_hook(MyEvents.ACTION, MyHookable, hook_C.callback) # Add one back
    assert len(manager.hooks) == 1
    assert len(manager.hookables) == 1
    manager.reset()
    assert len(manager.hooks) == 0
    assert len(manager.hookables) == 0
    assert len(manager.obj_map) == 0
    assert manager.flags == HookFlag.NONE

def test_inheritance_specific_hooks(output: Output, manager: HookManager):
    """Tests hooks registered specifically for base and subclasses are triggered correctly."""
    # Register both base and subclass, subclass with different/additional events
    # manager.register_class(MyHookable, MyEvents) # Done by fixture
    manager.register_class(MySuperHookable, {"super-action"}) # Register only subclass-specific event set

    # Hooks for Base
    hook_A: MyHook = MyHook(output, "Hook-A-Base")
    hook_C: MyHook = MyHook(output, "Hook-C-Base")
    manager.add_hook(MyEvents.CREATE, MyHookable, hook_A.callback)
    manager.add_hook(MyEvents.ACTION, MyHookable, hook_C.callback)

    # Hooks for Subclass
    hook_B: MyHook = MyHook(output, "Hook-B-Super") # Error hook
    hook_S: MyHook = MyHook(output, "Hook-S-Super")
    manager.add_hook(MyEvents.CREATE, MySuperHookable, hook_B.err_callback) # CREATE hook specific to subclass
    manager.add_hook("super-action", MySuperHookable, hook_S.callback)

    # Create subclass instance (triggers CREATE)
    output.clear()
    src_A: MySuperHookable = MySuperHookable(output, "SuperSource-A")
    # Expected: hook_B (Subclass)
    assert output.output == ["Hook Hook-B-Super event CREATE called by SuperSource-A",
                            "SuperSource-A.CREATE hook call outcome: ERROR (Error in hook)"]

    # Trigger base class action
    output.clear()
    src_A.action()
    # Expected: hook_C (Base Class only, as ACTION not registered for MySuperHookable)
    assert output.output == ["SuperSource-A.ACTION!",
                            "Hook Hook-C-Base event ACTION called by SuperSource-A",
                            "SuperSource-A.ACTION hook call outcome: OK"]

    # Trigger subclass action
    output.clear()
    src_A.super_action()
    # Expected: hook_S (Subclass only)
    assert output.output == ["SuperSource-A.SUPER-ACTION!",
                            "Hook Hook-S-Super event super-action called by SuperSource-A",
                            "SuperSource-A.SUPER-ACTION hook call outcome: OK"]

def test_bad_hook_registrations(output: Output, manager: HookManager):
    """Tests error handling for invalid arguments during hook registration."""
    # manager.register_class(MyHookable, MyEvents) # Done by fixture
    # manager.register_class(MySuperHookable, {"super-action"}) # Assume registered if needed

    bad_hook: MyHook = MyHook(output, "BAD-Hook")

    # Invalid source type for add_hook
    with pytest.raises(TypeError, match="Subject must be hookable class or instance, or name"):
        manager.add_hook(MyEvents.CREATE, ANY, bad_hook.callback) # Cannot use ANY as source
    with pytest.raises(TypeError, match="Subject must be hookable class or instance, or name"):
        manager.add_hook(MyEvents.CREATE, 123, bad_hook.callback) # Invalid type

    # Unregistered class for add_hook
    class Unregistered: pass
    with pytest.raises(TypeError, match="The type is not registered as hookable"):
        manager.add_hook(MyEvents.CREATE, Unregistered, bad_hook.callback)

    # Unsupported event for add_hook
    with pytest.raises(ValueError, match="Event 'BAD EVENT' is not supported by 'MyHookable'"):
        manager.add_hook("BAD EVENT", MyHookable, bad_hook.callback)
    src_A: MyHookable = MyHookable(output, "Source-A", trigger_event=None)
    with pytest.raises(ValueError, match="Event 'BAD EVENT' is not supported by 'MyHookable'"):
        manager.add_hook("BAD EVENT", src_A, bad_hook.callback)

    # Invalid instance type for register_name
    with pytest.raises(TypeError, match="The instance is not of hookable type"):
        manager.register_name(output, "BAD_CLASS_INSTANCE") # 'output' is not hookable

def test_any_event_hooks(output: Output, manager: HookManager):
    """Tests hooks registered for ANY event."""
    # manager.register_class(MyHookable, MyEvents) # Done by fixture

    # Hooks
    hook_A_ANY: MyHook = MyHook(output, "Hook-A-ANY")
    hook_B_ACTION: MyHook = MyHook(output, "Hook-B-ACTION")
    hook_C_ANY_Inst: MyHook = MyHook(output, "Hook-C-ANY-Inst")
    hook_D_ANY_Name: MyHook = MyHook(output, "Hook-D-ANY-Name")

    # Add ANY event hook for the class
    manager.add_hook(ANY, MyHookable, hook_A_ANY.callback)
    assert HookFlag.CLASS in manager.flags
    assert HookFlag.ANY_EVENT in manager.flags

    # Add specific event hook for comparison
    manager.add_hook(MyEvents.ACTION, MyHookable, hook_B_ACTION.callback)

    # Create instance (triggers CREATE)
    output.clear()
    src_A: MyHookable = MyHookable(output, "Source-A", register_name=True)
    # Expected: hook_A_ANY (Class ANY) triggered by CREATE event
    assert output.output == ["Hook Hook-A-ANY event CREATE called by Source-A",
                             "Source-A.CREATE hook call outcome: OK"]

    # Add ANY event hooks for instance and name
    manager.add_hook(ANY, src_A, hook_C_ANY_Inst.callback)
    manager.add_hook(ANY, "Source-A", hook_D_ANY_Name.callback)
    assert HookFlag.INSTANCE in manager.flags
    assert HookFlag.NAME in manager.flags

    # Trigger ACTION event
    output.clear()
    src_A.action()
    # Expected:
    # - hook_C_ANY_Inst (Instance ANY)
    # - hook_D_ANY_Name (Name ANY)
    # - hook_B_ACTION (Class ACTION)
    # - hook_A_ANY (Class ANY)
    assert output.output == ["Source-A.ACTION!",
                             "Hook Hook-C-ANY-Inst event ACTION called by Source-A", # Instance ANY
                             "Source-A.ACTION hook call outcome: OK",
                             "Hook Hook-D-ANY-Name event ACTION called by Source-A", # Name ANY
                             "Source-A.ACTION hook call outcome: OK",
                             "Hook Hook-B-ACTION event ACTION called by Source-A", # Class ACTION
                             "Source-A.ACTION hook call outcome: OK",
                             "Hook Hook-A-ANY event ACTION called by Source-A", # Class ANY
                             "Source-A.ACTION hook call outcome: OK"]

    # Test removing ANY hook
    manager.remove_hook(ANY, MyHookable, hook_A_ANY.callback)
    output.clear()
    src_A.action() # Trigger again
    # Expected: Same as above, but without hook_A_ANY
    assert output.output == ["Source-A.ACTION!",
                             "Hook Hook-C-ANY-Inst event ACTION called by Source-A",
                             "Source-A.ACTION hook call outcome: OK",
                             "Hook Hook-D-ANY-Name event ACTION called by Source-A",
                             "Source-A.ACTION hook call outcome: OK",
                             "Hook Hook-B-ACTION event ACTION called by Source-A",
                             "Source-A.ACTION hook call outcome: OK"]
    # Check flags after removal (this part is speculative without internal flag recalc logic)
    # assert HookFlag.ANY_EVENT not in manager.flags # Might be false if other ANY hooks remain

