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
from typing import Protocol, cast

import pytest

from firebird.base.hooks import HookFlag, hook_manager
from firebird.base.types import ANY


class MyEvents(Enum):
    CREATE = auto()
    ACTION = auto()

class with_print(Protocol):
    def print(self, msg: str) -> None:
        ...

class Output:
    def __init__(self):
        self.output: list[str] = []
    def print(self, msg: str) -> None:
        self.output.append(msg)
    def clear(self) -> None:
        self.output.clear()

class MyHookable:
    def __init__(self, owner: with_print, name: str, *, register: bool=False,
                 use_class: bool=False, use_name: bool=False):
        self.owner = owner
        self.name: str = name
        if register:
            hook_manager.register_name(self, name)
        subj = self
        if use_class:
            subj = MyHookable
        elif use_name:
            subj = name
        for hook in hook_manager.get_callbacks(MyEvents.CREATE, subj):
            try:
                hook(self, MyEvents.CREATE)
            except Exception as e:
                self.owner.print(f"{self.name}.CREATE hook call outcome: ERROR ({e.args[0]})")
            else:
                self.owner.print(f"{self.name}.CREATE hook call outcome: OK")
    def action(self):
        self.owner.print(f"{self.name}.ACTION!")
        for hook in hook_manager.get_callbacks(MyEvents.ACTION, self):
            try:
                hook(self, MyEvents.ACTION)
            except Exception as e:
                self.owner.print(f"{self.name}.ACTION hook call outcome: ERROR ({e.args[0]})")
            else:
                self.owner.print(f"{self.name}.ACTION hook call outcome: OK")

class MySuperHookable(MyHookable):
    def super_action(self):
        self.owner.print(f"{self.name}.SUPER-ACTION!")
        for hook in hook_manager.get_callbacks("super-action", self):
            try:
                hook(self, "super-action")
            except Exception as e:
                self.owner.print(f"{self.name}.SUPER-ACTION hook call outcome: ERROR ({e.args[0]})")
            else:
                self.owner.print(f"{self.name}.SUPER-ACTION hook call outcome: OK")

class MyHook:
    def __init__(self, owner: with_print, name: str):
        self.owner = owner
        self.name: str = name
    def callback(self, subject: MyHookable, event: MyEvents):
        self.owner.print(f"Hook {self.name} event {event.name if isinstance(event, Enum) else event} called by {subject.name}")
    def err_callback(self, subject: MyHookable, event: MyEvents):
        self.callback(subject, event)
        raise Exception("Error in hook")

def iter_class_properties(cls):
    """Iterator function.

    Args:
        cls (class): Class object.

    Yields:
        `name', 'property` pairs for all properties in class.
"""
    for varname in vars(cls):
        value = getattr(cls, varname)
        if isinstance(value, property):
            yield varname, value

def iter_class_variables(cls):
    """Iterator function.

    Args:
        cls (class): Class object.

    Yields:
        Names of all non-callable attributes in class.
"""
    for varname in vars(cls):
        value = getattr(cls, varname)
        if not (isinstance(value, property) or callable(value)) and not varname.startswith("_"):
            yield varname

@pytest.fixture
def output():
    return Output()

@pytest.fixture(autouse=True)
def manager():
    hook_manager.reset()
    return hook_manager
#
def test_01_general_tests(output):
    # register hookables
    hook_manager.register_class(MyHookable, MyEvents)
    assert tuple(hook_manager.hookables.keys()) == (MyHookable, )
    assert hook_manager.hookables[MyHookable] == set(x for x in cast(Enum, MyEvents).__members__.values())
    # Optimizations
    assert HookFlag.CLASS not in hook_manager.flags
    assert HookFlag.INSTANCE not in hook_manager.flags
    assert HookFlag.ANY_EVENT not in hook_manager.flags
    assert HookFlag.NAME not in hook_manager.flags
    # Install hooks
    hook_A: MyHook = MyHook(output, "Hook-A")
    hook_B: MyHook = MyHook(output, "Hook-B")
    hook_C: MyHook = MyHook(output, "Hook-C")
    hook_N: MyHook = MyHook(output, "Hook-N")
    #
    hook_manager.add_hook(MyEvents.CREATE, MyHookable, hook_A.callback)
    assert HookFlag.CLASS in hook_manager.flags
    hook_manager.add_hook(MyEvents.CREATE, MyHookable, hook_B.err_callback)
    hook_manager.add_hook(MyEvents.ACTION, MyHookable, hook_C.callback)
    hook_manager.add_hook(MyEvents.ACTION, "Source-A", hook_N.callback)
    assert HookFlag.NAME in hook_manager.flags
    #
    key = (MyEvents.CREATE, MyHookable, ANY)
    assert key in hook_manager.hooks
    assert hook_A.callback in hook_manager.hooks[key].callbacks
    assert hook_B.err_callback in hook_manager.hooks[key].callbacks
    key = (MyEvents.ACTION, MyHookable, ANY)
    assert key in hook_manager.hooks
    assert hook_C.callback in hook_manager.hooks[key].callbacks
    # Create event sources, emits CREATE
    output.clear()
    src_A: MyHookable = MyHookable(output, "Source-A", register=True)
    assert output.output == ["Hook Hook-A event CREATE called by Source-A",
                             "Source-A.CREATE hook call outcome: OK",
                             "Hook Hook-B event CREATE called by Source-A",
                             "Source-A.CREATE hook call outcome: ERROR (Error in hook)"]
    output.clear()
    src_B: MyHookable = MyHookable(output, "Source-B", register=True)
    assert output.output ==  ["Hook Hook-A event CREATE called by Source-B",
                              "Source-B.CREATE hook call outcome: OK",
                              "Hook Hook-B event CREATE called by Source-B",
                              "Source-B.CREATE hook call outcome: ERROR (Error in hook)"]
    # Install instance hooks
    hook_manager.add_hook(MyEvents.ACTION, src_A, hook_A.callback)
    assert HookFlag.INSTANCE in hook_manager.flags
    hook_manager.add_hook(MyEvents.ACTION, src_B, hook_B.callback)
    #
    key = (MyEvents.ACTION, ANY, src_A)
    assert key in hook_manager.hooks
    assert hook_A.callback in hook_manager.hooks[key].callbacks
    key = (MyEvents.ACTION, ANY, src_B)
    assert key in hook_manager.hooks
    assert hook_B.callback in hook_manager.hooks[key].callbacks
    # And action!
    output.clear()
    src_A.action()
    assert output.output == ["Source-A.ACTION!",
                             "Hook Hook-A event ACTION called by Source-A",
                             "Source-A.ACTION hook call outcome: OK",
                             "Hook Hook-N event ACTION called by Source-A",
                             "Source-A.ACTION hook call outcome: OK",
                             "Hook Hook-C event ACTION called by Source-A",
                             "Source-A.ACTION hook call outcome: OK"]
    #
    output.clear()
    src_B.action()
    assert output.output == ["Source-B.ACTION!",
                             "Hook Hook-B event ACTION called by Source-B",
                             "Source-B.ACTION hook call outcome: OK",
                             "Hook Hook-C event ACTION called by Source-B",
                             "Source-B.ACTION hook call outcome: OK"]
    # Optimizations
    assert HookFlag.CLASS in hook_manager.flags
    assert HookFlag.INSTANCE in hook_manager.flags
    assert HookFlag.ANY_EVENT not in hook_manager.flags
    assert HookFlag.NAME in hook_manager.flags
    # Remove hooks
    hook_manager.remove_hook(MyEvents.CREATE, MyHookable, hook_A.callback)
    key = (MyEvents.CREATE, MyHookable, ANY)
    assert key in hook_manager.hooks
    assert hook_A.callback not in hook_manager.hooks[key].callbacks
    hook_manager.remove_hook(MyEvents.CREATE, MyHookable, hook_B.err_callback)
    assert key not in hook_manager.hooks
    #
    hook_manager.remove_hook(MyEvents.ACTION, src_A, hook_A.callback)
    key = (MyEvents.ACTION, ANY, src_A)
    assert key not in hook_manager.hooks
    #
    hook_manager.remove_all_hooks()
    assert len(hook_manager.hooks) == 0
    #
    hook_manager.add_hook(MyEvents.ACTION, MyHookable, hook_C.callback)
    hook_manager.reset()
    assert len(hook_manager.hookables) == 0
    assert len(hook_manager.hooks) == 0

def test_02_inherited_hookable(output):
    # register hookables
    hook_manager.register_class(MyHookable, MyEvents)
    assert tuple(hook_manager.hookables.keys()) == (MyHookable, )
    assert hook_manager.hookables[MyHookable] ==  set(x for x in cast(Enum, MyEvents).__members__.values())
    # Install hooks
    hook_A: MyHook = MyHook(output, "Hook-A")
    hook_B: MyHook = MyHook(output, "Hook-B")
    hook_C: MyHook = MyHook(output, "Hook-C")
    #
    hook_manager.add_hook(MyEvents.CREATE, MyHookable, hook_A.callback)
    hook_manager.add_hook(MyEvents.CREATE, MyHookable, hook_B.err_callback)
    hook_manager.add_hook(MyEvents.ACTION, MyHookable, hook_C.callback)
    #
    key = (MyEvents.CREATE, MyHookable, ANY)
    assert key in hook_manager.hooks
    assert hook_A.callback in hook_manager.hooks[key].callbacks
    assert hook_B.err_callback in hook_manager.hooks[key].callbacks
    key = (MyEvents.ACTION, MyHookable, ANY)
    assert key in hook_manager.hooks
    assert hook_C.callback in hook_manager.hooks[key].callbacks
    # Create event sources, emits CREATE
    output.clear()
    src_A: MySuperHookable = MySuperHookable(output, "SuperSource-A")
    assert output.output ==  ["Hook Hook-A event CREATE called by SuperSource-A",
                              "SuperSource-A.CREATE hook call outcome: OK",
                              "Hook Hook-B event CREATE called by SuperSource-A",
                              "SuperSource-A.CREATE hook call outcome: ERROR (Error in hook)"]
    output.clear()
    src_B: MySuperHookable = MySuperHookable(output, "SuperSource-B")
    assert output.output == ["Hook Hook-A event CREATE called by SuperSource-B",
                             "SuperSource-B.CREATE hook call outcome: OK",
                             "Hook Hook-B event CREATE called by SuperSource-B",
                             "SuperSource-B.CREATE hook call outcome: ERROR (Error in hook)"]
    # Install instance hooks
    hook_manager.add_hook(MyEvents.ACTION, src_A, hook_A.callback)
    hook_manager.add_hook(MyEvents.ACTION, src_B, hook_B.callback)
    #
    key = (MyEvents.ACTION, ANY, src_A)
    assert key in hook_manager.hooks
    assert hook_A.callback in hook_manager.hooks[key].callbacks
    key = (MyEvents.ACTION, ANY, src_B)
    assert key in hook_manager.hooks
    assert hook_B.callback in hook_manager.hooks[key].callbacks
    # And action!
    output.clear()
    src_A.action()
    assert output.output ==  ["SuperSource-A.ACTION!",
                              "Hook Hook-A event ACTION called by SuperSource-A",
                              "SuperSource-A.ACTION hook call outcome: OK",
                              "Hook Hook-C event ACTION called by SuperSource-A",
                              "SuperSource-A.ACTION hook call outcome: OK"]
    #
    output.clear()
    src_B.action()
    assert output.output == ["SuperSource-B.ACTION!",
                             "Hook Hook-B event ACTION called by SuperSource-B",
                             "SuperSource-B.ACTION hook call outcome: OK",
                             "Hook Hook-C event ACTION called by SuperSource-B",
                             "SuperSource-B.ACTION hook call outcome: OK"]

def test_03_inheritance(output):
    # register hookables
    hook_manager.register_class(MyHookable, MyEvents)
    hook_manager.register_class(MySuperHookable, ("super-action", ))
    assert tuple(hook_manager.hookables.keys()) == (MyHookable, MySuperHookable)
    assert hook_manager.hookables[MyHookable] == set(x for x in cast(Enum, MyEvents).__members__.values())
    assert hook_manager.hookables[MySuperHookable] == ("super-action", )
    # Install hooks
    hook_A: MyHook = MyHook(output, "Hook-A")
    hook_B: MyHook = MyHook(output, "Hook-B")
    hook_C: MyHook = MyHook(output, "Hook-C")
    hook_S: MyHook = MyHook(output, "Hook-S")
    #
    hook_manager.add_hook(MyEvents.CREATE, MyHookable, hook_A.callback)
    hook_manager.add_hook(MyEvents.CREATE, MySuperHookable, hook_B.err_callback)
    hook_manager.add_hook(MyEvents.ACTION, MyHookable, hook_C.callback)
    hook_manager.add_hook("super-action", MySuperHookable, hook_S.callback)
    #
    key = (MyEvents.CREATE, MyHookable, ANY)
    assert key in hook_manager.hooks
    assert hook_A.callback in hook_manager.hooks[key].callbacks
    key = (MyEvents.CREATE, MySuperHookable, ANY)
    assert key in hook_manager.hooks
    assert hook_B.err_callback in hook_manager.hooks[key].callbacks
    key = (MyEvents.ACTION, MyHookable, ANY)
    assert key in hook_manager.hooks
    assert hook_C.callback in hook_manager.hooks[key].callbacks
    # Create event sources, emits CREATE
    output.clear()
    src_A: MySuperHookable = MySuperHookable(output, "SuperSource-A")
    assert output.output == ["Hook Hook-A event CREATE called by SuperSource-A",
                            "SuperSource-A.CREATE hook call outcome: OK",
                            "Hook Hook-B event CREATE called by SuperSource-A",
                            "SuperSource-A.CREATE hook call outcome: ERROR (Error in hook)"]
    output.clear()
    src_B: MySuperHookable = MySuperHookable(output, "SuperSource-B")
    assert output.output == ["Hook Hook-A event CREATE called by SuperSource-B",
                            "SuperSource-B.CREATE hook call outcome: OK",
                            "Hook Hook-B event CREATE called by SuperSource-B",
                            "SuperSource-B.CREATE hook call outcome: ERROR (Error in hook)"]
    # Install instance hooks
    hook_manager.add_hook(MyEvents.ACTION, src_A, hook_A.callback)
    hook_manager.add_hook(MyEvents.ACTION, src_B, hook_B.callback)
    #
    key = (MyEvents.ACTION, ANY, src_A)
    assert key in hook_manager.hooks
    assert hook_A.callback in hook_manager.hooks[key].callbacks
    key = (MyEvents.ACTION, ANY, src_B)
    assert key in hook_manager.hooks
    assert hook_B.callback in hook_manager.hooks[key].callbacks
    # And action!
    output.clear()
    src_A.action()
    assert output.output == ["SuperSource-A.ACTION!",
                            "Hook Hook-A event ACTION called by SuperSource-A",
                            "SuperSource-A.ACTION hook call outcome: OK",
                            "Hook Hook-C event ACTION called by SuperSource-A",
                            "SuperSource-A.ACTION hook call outcome: OK"]
    #
    output.clear()
    src_B.action()
    assert output.output == ["SuperSource-B.ACTION!",
                            "Hook Hook-B event ACTION called by SuperSource-B",
                            "SuperSource-B.ACTION hook call outcome: OK",
                            "Hook Hook-C event ACTION called by SuperSource-B",
                            "SuperSource-B.ACTION hook call outcome: OK"]
    #
    output.clear()
    src_B.super_action()
    assert output.output == ["SuperSource-B.SUPER-ACTION!",
                            "Hook Hook-S event super-action called by SuperSource-B",
                            "SuperSource-B.SUPER-ACTION hook call outcome: OK"]

def test_04_bad_hooks(output):
    # register hookables
    hook_manager.register_class(MyHookable, MyEvents)
    hook_manager.register_class(MySuperHookable, ("super-action", ))
    src_A: MyHookable = MyHookable(output, "Source-A")
    src_B: MySuperHookable = MySuperHookable(output, "SuperSource-B")
    # Install hooks
    bad_hook: MyHook = MyHook(output, "BAD-Hook")
    # Wrong hookables
    with pytest.raises(TypeError) as cm:
        hook_manager.add_hook(MyEvents.CREATE, ANY, bad_hook.callback) # hook object
    assert cm.value.args == ("Subject must be hookable class or instance, or name",)
    with pytest.raises(TypeError) as cm:
        hook_manager.add_hook(MyEvents.CREATE, Enum, bad_hook.callback) # hook class
    assert cm.value.args == ("The type is not registered as hookable",)
    assert hook_manager.hooks._reg == {}
    # Wrong events
    with pytest.raises(ValueError) as cm:
        hook_manager.add_hook("BAD EVENT", MyHookable, bad_hook.callback)
    assert cm.value.args == ("Event 'BAD EVENT' is not supported by 'MyHookable'",)
    with pytest.raises(ValueError) as cm:
        hook_manager.add_hook("BAD EVENT", MySuperHookable, bad_hook.callback)
    assert cm.value.args == ("Event 'BAD EVENT' is not supported by 'MySuperHookable'",)
    #
    with pytest.raises(ValueError) as cm:
        hook_manager.add_hook("BAD EVENT", src_A, bad_hook.callback)
    assert cm.value.args == ("Event 'BAD EVENT' is not supported by 'MyHookable'",)
    with pytest.raises(ValueError) as cm:
        hook_manager.add_hook("BAD EVENT", src_B, bad_hook.callback)
    assert cm.value.args == ("Event 'BAD EVENT' is not supported by 'MySuperHookable'",)
    # Bad hookable instances
    with pytest.raises(TypeError) as cm:
        hook_manager.register_name(output, "BAD_CLASS")
    assert cm.value.args == ("The instance is not of hookable type",)

def test_05_any_event(output):
    # register hookables
    hook_manager.register_class(MyHookable, MyEvents)
    # Install hooks
    hook_A: MyHook = MyHook(output, "Hook-A")
    hook_B: MyHook = MyHook(output, "Hook-B")
    hook_C: MyHook = MyHook(output, "Hook-C")
    hook_D: MyHook = MyHook(output, "Hook-D")
    hook_manager.add_hook(ANY, MyHookable, hook_A.callback)
    hook_manager.add_hook(ANY, MyHookable, hook_B.err_callback)
    # Create event sources, emits CREATE
    output.clear()
    src_A: MyHookable = MyHookable(output, "Source-A", register=True)
    assert output.output == ["Hook Hook-A event CREATE called by Source-A",
                             "Source-A.CREATE hook call outcome: OK",
                             "Hook Hook-B event CREATE called by Source-A",
                             "Source-A.CREATE hook call outcome: ERROR (Error in hook)"]
    # Install instance hooks
    hook_manager.add_hook(ANY, src_A, hook_C.callback)
    hook_manager.add_hook(ANY, "Source-A", hook_D.callback)
    # And action!
    output.clear()
    src_A.action()
    assert output.output == ["Source-A.ACTION!",
                             "Hook Hook-C event ACTION called by Source-A",
                             "Source-A.ACTION hook call outcome: OK",
                             "Hook Hook-D event ACTION called by Source-A",
                             "Source-A.ACTION hook call outcome: OK",
                             "Hook Hook-A event ACTION called by Source-A",
                             "Source-A.ACTION hook call outcome: OK",
                             "Hook Hook-B event ACTION called by Source-A",
                             "Source-A.ACTION hook call outcome: ERROR (Error in hook)"]
    # Optimizations
    assert HookFlag.CLASS in hook_manager.flags
    assert HookFlag.INSTANCE in hook_manager.flags
    assert HookFlag.ANY_EVENT in hook_manager.flags
    assert HookFlag.NAME in hook_manager.flags

def test_06_class_hooks(output):
    # register hookables
    hook_manager.register_class(MyHookable, MyEvents)
    # Install hooks
    hook_A: MyHook = MyHook(output, "Hook-A")
    hook_B: MyHook = MyHook(output, "Hook-B")
    hook_C: MyHook = MyHook(output, "Hook-C")
    hook_D: MyHook = MyHook(output, "Hook-D")
    hook_manager.add_hook(MyEvents.CREATE, MyHookable, hook_A.callback)
    hook_manager.add_hook(ANY, MyHookable, hook_B.err_callback)
    hook_manager.add_hook(MyEvents.CREATE, "Source-A", hook_C.callback)
    hook_manager.add_hook(ANY, "Source-A", hook_D.callback)
    # Create event sources, emits CREATE
    output.clear()
    MyHookable(output, "Source-A", use_class=True)
    assert output.output == ["Hook Hook-A event CREATE called by Source-A",
                             "Source-A.CREATE hook call outcome: OK",
                             "Hook Hook-B event CREATE called by Source-A",
                             "Source-A.CREATE hook call outcome: ERROR (Error in hook)"]

def test_07_name_hooks(output):
    # register hookables
    hook_manager.register_class(MyHookable, MyEvents)
    # Install hooks
    hook_A: MyHook = MyHook(output, "Hook-A")
    hook_B: MyHook = MyHook(output, "Hook-B")
    hook_C: MyHook = MyHook(output, "Hook-C")
    hook_D: MyHook = MyHook(output, "Hook-D")
    hook_manager.add_hook(MyEvents.CREATE, MyHookable, hook_A.callback)
    hook_manager.add_hook(ANY, MyHookable, hook_B.err_callback)
    hook_manager.add_hook(MyEvents.CREATE, "Source-A", hook_C.callback)
    hook_manager.add_hook(ANY, "Source-A", hook_D.err_callback)
    # Create event sources, emits CREATE
    output.clear()
    MyHookable(output, "Source-A", use_name=True)
    assert output.output == ["Hook Hook-C event CREATE called by Source-A",
                             "Source-A.CREATE hook call outcome: OK",
                             "Hook Hook-D event CREATE called by Source-A",
                             "Source-A.CREATE hook call outcome: ERROR (Error in hook)"]
