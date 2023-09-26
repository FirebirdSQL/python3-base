#!/usr/bin/python
#coding:utf-8
#
#   PROGRAM/MODULE: firebird-base
#   FILE:           test/test_hooks.py
#   DESCRIPTION:    Unit tests for firebird.base.hooks
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

"Firebird Base - Unit tests for firebird.base.hooks."

from __future__ import annotations
from typing import Protocol, List, cast
import unittest
from enum import Enum, auto
from firebird.base.hooks import hook_manager, HookFlag
from firebird.base.types import ANY

class MyEvents(Enum):
    CREATE = auto()
    ACTION = auto()

class with_print(Protocol):
    def print(self, msg: str) -> None:
        ...

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
        for hook in hook_manager.get_callbacks('super-action', self):
            try:
                hook(self, 'super-action')
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
        if not (isinstance(value, property) or callable(value)) and not varname.startswith('_'):
            yield varname


class TestHooks(unittest.TestCase):
    """Unit tests for firebird.base.hooks.HookManager"""
    def __init__(self, methodName='runTest'):
        super().__init__(methodName)
        self.output: List = []
    def setUp(self) -> None:
        self.output.clear()
        hook_manager.reset()
    def tearDown(self):
        pass
    def print(self, msg: str) -> None:
        self.output.append(msg)
    def test_aaa_hooks(self):
        # register hookables
        hook_manager.register_class(MyHookable, MyEvents)
        self.assertTupleEqual(tuple(hook_manager.hookables.keys()), (MyHookable, ))
        self.assertSetEqual(hook_manager.hookables[MyHookable],
                            set(x for x in cast(Enum, MyEvents).__members__.values()))
        # Optimizations
        self.assertNotIn(HookFlag.CLASS, hook_manager.flags)
        self.assertNotIn(HookFlag.INSTANCE, hook_manager.flags)
        self.assertNotIn(HookFlag.ANY_EVENT, hook_manager.flags)
        self.assertNotIn(HookFlag.NAME, hook_manager.flags)
        # Install hooks
        hook_A: MyHook = MyHook(self, 'Hook-A')
        hook_B: MyHook = MyHook(self, 'Hook-B')
        hook_C: MyHook = MyHook(self, 'Hook-C')
        hook_N: MyHook = MyHook(self, 'Hook-N')
        #
        hook_manager.add_hook(MyEvents.CREATE, MyHookable, hook_A.callback)
        self.assertIn(HookFlag.CLASS, hook_manager.flags)
        hook_manager.add_hook(MyEvents.CREATE, MyHookable, hook_B.err_callback)
        hook_manager.add_hook(MyEvents.ACTION, MyHookable, hook_C.callback)
        hook_manager.add_hook(MyEvents.ACTION, 'Source-A', hook_N.callback)
        self.assertIn(HookFlag.NAME, hook_manager.flags)
        #
        key = (MyEvents.CREATE, MyHookable, ANY)
        self.assertTrue(key in hook_manager.hooks)
        self.assertIn(hook_A.callback, hook_manager.hooks[key].callbacks)
        self.assertIn(hook_B.err_callback, hook_manager.hooks[key].callbacks)
        key = (MyEvents.ACTION, MyHookable, ANY)
        self.assertTrue(key in hook_manager.hooks)
        self.assertIn(hook_C.callback, hook_manager.hooks[key].callbacks)
        # Create event sources, emits CREATE
        self.output.clear()
        src_A: MyHookable = MyHookable(self, 'Source-A', register=True)
        self.assertListEqual(self.output,
                             ['Hook Hook-A event CREATE called by Source-A',
                              'Source-A.CREATE hook call outcome: OK',
                              'Hook Hook-B event CREATE called by Source-A',
                              'Source-A.CREATE hook call outcome: ERROR (Error in hook)'])
        self.output.clear()
        src_B: MyHookable = MyHookable(self, 'Source-B', register=True)
        self.assertListEqual(self.output,
                             ['Hook Hook-A event CREATE called by Source-B',
                              'Source-B.CREATE hook call outcome: OK',
                              'Hook Hook-B event CREATE called by Source-B',
                              'Source-B.CREATE hook call outcome: ERROR (Error in hook)'])
        # Install instance hooks
        hook_manager.add_hook(MyEvents.ACTION, src_A, hook_A.callback)
        self.assertIn(HookFlag.INSTANCE, hook_manager.flags)
        hook_manager.add_hook(MyEvents.ACTION, src_B, hook_B.callback)
        #
        key = (MyEvents.ACTION, ANY, src_A)
        self.assertTrue(key in hook_manager.hooks)
        self.assertIn(hook_A.callback, hook_manager.hooks[key].callbacks)
        key = (MyEvents.ACTION, ANY, src_B)
        self.assertTrue(key in hook_manager.hooks)
        self.assertIn(hook_B.callback, hook_manager.hooks[key].callbacks)
        # And action!
        self.output.clear()
        src_A.action()
        self.assertListEqual(self.output,
                             ['Source-A.ACTION!',
                              'Hook Hook-A event ACTION called by Source-A',
                              'Source-A.ACTION hook call outcome: OK',
                              'Hook Hook-N event ACTION called by Source-A',
                              'Source-A.ACTION hook call outcome: OK',
                              'Hook Hook-C event ACTION called by Source-A',
                              'Source-A.ACTION hook call outcome: OK'])
        #
        self.output.clear()
        src_B.action()
        self.assertListEqual(self.output,
                             ['Source-B.ACTION!',
                              'Hook Hook-B event ACTION called by Source-B',
                              'Source-B.ACTION hook call outcome: OK',
                              'Hook Hook-C event ACTION called by Source-B',
                              'Source-B.ACTION hook call outcome: OK'])
        # Optimizations
        self.assertIn(HookFlag.CLASS, hook_manager.flags)
        self.assertIn(HookFlag.INSTANCE, hook_manager.flags)
        self.assertNotIn(HookFlag.ANY_EVENT, hook_manager.flags)
        self.assertIn(HookFlag.NAME, hook_manager.flags)
        # Remove hooks
        hook_manager.remove_hook(MyEvents.CREATE, MyHookable, hook_A.callback)
        key = (MyEvents.CREATE, MyHookable, ANY)
        self.assertTrue(key in hook_manager.hooks)
        self.assertNotIn(hook_A.callback, hook_manager.hooks[key].callbacks)
        hook_manager.remove_hook(MyEvents.CREATE, MyHookable, hook_B.err_callback)
        self.assertFalse(key in hook_manager.hooks)
        #
        hook_manager.remove_hook(MyEvents.ACTION, src_A, hook_A.callback)
        key = (MyEvents.ACTION, ANY, src_A)
        self.assertFalse(key in hook_manager.hooks)
        #
        hook_manager.remove_all_hooks()
        self.assertEqual(len(hook_manager.hooks), 0)
        #
        hook_manager.add_hook(MyEvents.ACTION, MyHookable, hook_C.callback)
        hook_manager.reset()
        self.assertEqual(len(hook_manager.hookables), 0)
        self.assertEqual(len(hook_manager.hooks), 0)
    def test_inherited_hookable(self):
        # register hookables
        hook_manager.register_class(MyHookable, MyEvents)
        self.assertTupleEqual(tuple(hook_manager.hookables.keys()), (MyHookable, ))
        self.assertSetEqual(hook_manager.hookables[MyHookable],
                            set(x for x in cast(Enum, MyEvents).__members__.values()))
        # Install hooks
        hook_A: MyHook = MyHook(self, 'Hook-A')
        hook_B: MyHook = MyHook(self, 'Hook-B')
        hook_C: MyHook = MyHook(self, 'Hook-C')
        #
        hook_manager.add_hook(MyEvents.CREATE, MyHookable, hook_A.callback)
        hook_manager.add_hook(MyEvents.CREATE, MyHookable, hook_B.err_callback)
        hook_manager.add_hook(MyEvents.ACTION, MyHookable, hook_C.callback)
        #
        key = (MyEvents.CREATE, MyHookable, ANY)
        self.assertTrue(key in hook_manager.hooks)
        self.assertIn(hook_A.callback, hook_manager.hooks[key].callbacks)
        self.assertIn(hook_B.err_callback, hook_manager.hooks[key].callbacks)
        key = (MyEvents.ACTION, MyHookable, ANY)
        self.assertTrue(key in hook_manager.hooks)
        self.assertIn(hook_C.callback, hook_manager.hooks[key].callbacks)
        # Create event sources, emits CREATE
        self.output.clear()
        src_A: MySuperHookable = MySuperHookable(self, 'SuperSource-A')
        self.assertListEqual(self.output,
                             ['Hook Hook-A event CREATE called by SuperSource-A',
                              'SuperSource-A.CREATE hook call outcome: OK',
                              'Hook Hook-B event CREATE called by SuperSource-A',
                              'SuperSource-A.CREATE hook call outcome: ERROR (Error in hook)'])
        self.output.clear()
        src_B: MySuperHookable = MySuperHookable(self, 'SuperSource-B')
        self.assertListEqual(self.output,
                             ['Hook Hook-A event CREATE called by SuperSource-B',
                              'SuperSource-B.CREATE hook call outcome: OK',
                              'Hook Hook-B event CREATE called by SuperSource-B',
                              'SuperSource-B.CREATE hook call outcome: ERROR (Error in hook)'])
        # Install instance hooks
        hook_manager.add_hook(MyEvents.ACTION, src_A, hook_A.callback)
        hook_manager.add_hook(MyEvents.ACTION, src_B, hook_B.callback)
        #
        key = (MyEvents.ACTION, ANY, src_A)
        self.assertTrue(key in hook_manager.hooks)
        self.assertIn(hook_A.callback, hook_manager.hooks[key].callbacks)
        key = (MyEvents.ACTION, ANY, src_B)
        self.assertTrue(key in hook_manager.hooks)
        self.assertIn(hook_B.callback, hook_manager.hooks[key].callbacks)
        # And action!
        self.output.clear()
        src_A.action()
        self.assertListEqual(self.output,
                             ['SuperSource-A.ACTION!',
                              'Hook Hook-A event ACTION called by SuperSource-A',
                              'SuperSource-A.ACTION hook call outcome: OK',
                              'Hook Hook-C event ACTION called by SuperSource-A',
                              'SuperSource-A.ACTION hook call outcome: OK'])
        #
        self.output.clear()
        src_B.action()
        self.assertListEqual(self.output,
                             ['SuperSource-B.ACTION!',
                              'Hook Hook-B event ACTION called by SuperSource-B',
                              'SuperSource-B.ACTION hook call outcome: OK',
                              'Hook Hook-C event ACTION called by SuperSource-B',
                              'SuperSource-B.ACTION hook call outcome: OK'])
    def test_inheritance(self):
        # register hookables
        hook_manager.register_class(MyHookable, MyEvents)
        hook_manager.register_class(MySuperHookable, ('super-action', ))
        self.assertTupleEqual(tuple(hook_manager.hookables.keys()), (MyHookable, MySuperHookable))
        self.assertSetEqual(hook_manager.hookables[MyHookable],
                            set(x for x in cast(Enum, MyEvents).__members__.values()))
        self.assertTupleEqual(hook_manager.hookables[MySuperHookable], ('super-action', ))
        # Install hooks
        hook_A: MyHook = MyHook(self, 'Hook-A')
        hook_B: MyHook = MyHook(self, 'Hook-B')
        hook_C: MyHook = MyHook(self, 'Hook-C')
        hook_S: MyHook = MyHook(self, 'Hook-S')
        #
        hook_manager.add_hook(MyEvents.CREATE, MyHookable, hook_A.callback)
        hook_manager.add_hook(MyEvents.CREATE, MySuperHookable, hook_B.err_callback)
        hook_manager.add_hook(MyEvents.ACTION, MyHookable, hook_C.callback)
        hook_manager.add_hook('super-action', MySuperHookable, hook_S.callback)
        #
        key = (MyEvents.CREATE, MyHookable, ANY)
        self.assertTrue(key in hook_manager.hooks)
        self.assertIn(hook_A.callback, hook_manager.hooks[key].callbacks)
        key = (MyEvents.CREATE, MySuperHookable, ANY)
        self.assertTrue(key in hook_manager.hooks)
        self.assertIn(hook_B.err_callback, hook_manager.hooks[key].callbacks)
        key = (MyEvents.ACTION, MyHookable, ANY)
        self.assertTrue(key in hook_manager.hooks)
        self.assertIn(hook_C.callback, hook_manager.hooks[key].callbacks)
        # Create event sources, emits CREATE
        self.output.clear()
        src_A: MySuperHookable = MySuperHookable(self, 'SuperSource-A')
        self.assertListEqual(self.output,
                             ['Hook Hook-A event CREATE called by SuperSource-A',
                              'SuperSource-A.CREATE hook call outcome: OK',
                              'Hook Hook-B event CREATE called by SuperSource-A',
                              'SuperSource-A.CREATE hook call outcome: ERROR (Error in hook)'])
        self.output.clear()
        src_B: MySuperHookable = MySuperHookable(self, 'SuperSource-B')
        self.assertListEqual(self.output,
                             ['Hook Hook-A event CREATE called by SuperSource-B',
                              'SuperSource-B.CREATE hook call outcome: OK',
                              'Hook Hook-B event CREATE called by SuperSource-B',
                              'SuperSource-B.CREATE hook call outcome: ERROR (Error in hook)'])
        # Install instance hooks
        hook_manager.add_hook(MyEvents.ACTION, src_A, hook_A.callback)
        hook_manager.add_hook(MyEvents.ACTION, src_B, hook_B.callback)
        #
        key = (MyEvents.ACTION, ANY, src_A)
        self.assertTrue(key in hook_manager.hooks)
        self.assertIn(hook_A.callback, hook_manager.hooks[key].callbacks)
        key = (MyEvents.ACTION, ANY, src_B)
        self.assertTrue(key in hook_manager.hooks)
        self.assertIn(hook_B.callback, hook_manager.hooks[key].callbacks)
        # And action!
        self.output.clear()
        src_A.action()
        self.assertListEqual(self.output,
                             ['SuperSource-A.ACTION!',
                              'Hook Hook-A event ACTION called by SuperSource-A',
                              'SuperSource-A.ACTION hook call outcome: OK',
                              'Hook Hook-C event ACTION called by SuperSource-A',
                              'SuperSource-A.ACTION hook call outcome: OK'])
        #
        self.output.clear()
        src_B.action()
        self.assertListEqual(self.output,
                             ['SuperSource-B.ACTION!',
                              'Hook Hook-B event ACTION called by SuperSource-B',
                              'SuperSource-B.ACTION hook call outcome: OK',
                              'Hook Hook-C event ACTION called by SuperSource-B',
                              'SuperSource-B.ACTION hook call outcome: OK'])
        #
        self.output.clear()
        src_B.super_action()
        self.assertListEqual(self.output,
                             ['SuperSource-B.SUPER-ACTION!',
                              'Hook Hook-S event super-action called by SuperSource-B',
                              'SuperSource-B.SUPER-ACTION hook call outcome: OK'])
    def test_bad_hooks(self):
        # register hookables
        hook_manager.register_class(MyHookable, MyEvents)
        hook_manager.register_class(MySuperHookable, ('super-action', ))
        src_A: MyHookable = MyHookable(self, 'Source-A')
        src_B: MySuperHookable = MySuperHookable(self, 'SuperSource-B')
        # Install hooks
        bad_hook: MyHook = MyHook(self, 'BAD-Hook')
        # Wrong hookables
        with self.assertRaises(TypeError) as cm:
            hook_manager.add_hook(MyEvents.CREATE, ANY, bad_hook.callback) # hook object
        self.assertEqual(cm.exception.args, ("Subject must be hookable class or instance, or name",))
        with self.assertRaises(TypeError) as cm:
            hook_manager.add_hook(MyEvents.CREATE, Enum, bad_hook.callback) # hook class
        self.assertEqual(cm.exception.args, ('The type is not registered as hookable',))
        self.assertDictEqual(hook_manager.hooks._reg, {})
        # Wrong events
        with self.assertRaises(ValueError) as cm:
            hook_manager.add_hook('BAD EVENT', MyHookable, bad_hook.callback)
        self.assertEqual(cm.exception.args, ("Event 'BAD EVENT' is not supported by 'MyHookable'",))
        with self.assertRaises(ValueError) as cm:
            hook_manager.add_hook('BAD EVENT', MySuperHookable, bad_hook.callback)
        self.assertEqual(cm.exception.args, ("Event 'BAD EVENT' is not supported by 'MySuperHookable'",))
        #
        with self.assertRaises(ValueError) as cm:
            hook_manager.add_hook('BAD EVENT', src_A, bad_hook.callback)
        self.assertEqual(cm.exception.args, ("Event 'BAD EVENT' is not supported by 'MyHookable'",))
        with self.assertRaises(ValueError) as cm:
            hook_manager.add_hook('BAD EVENT', src_B, bad_hook.callback)
        self.assertEqual(cm.exception.args, ("Event 'BAD EVENT' is not supported by 'MySuperHookable'",))
        # Bad hookable instances
        with self.assertRaises(TypeError) as cm:
            hook_manager.register_name(self, 'BAD_CLASS')
        self.assertEqual(cm.exception.args, ("The instance is not of hookable type",))
    def test_any_event(self):
        # register hookables
        hook_manager.register_class(MyHookable, MyEvents)
        # Install hooks
        hook_A: MyHook = MyHook(self, 'Hook-A')
        hook_B: MyHook = MyHook(self, 'Hook-B')
        hook_C: MyHook = MyHook(self, 'Hook-C')
        hook_D: MyHook = MyHook(self, 'Hook-D')
        hook_manager.add_hook(ANY, MyHookable, hook_A.callback)
        hook_manager.add_hook(ANY, MyHookable, hook_B.err_callback)
        # Create event sources, emits CREATE
        self.output.clear()
        src_A: MyHookable = MyHookable(self, 'Source-A', register=True)
        self.assertListEqual(self.output,
                             ['Hook Hook-A event CREATE called by Source-A',
                              'Source-A.CREATE hook call outcome: OK',
                              'Hook Hook-B event CREATE called by Source-A',
                              'Source-A.CREATE hook call outcome: ERROR (Error in hook)'])
        # Install instance hooks
        hook_manager.add_hook(ANY, src_A, hook_C.callback)
        hook_manager.add_hook(ANY, 'Source-A', hook_D.callback)
        # And action!
        self.output.clear()
        src_A.action()
        self.assertListEqual(self.output,
                             ['Source-A.ACTION!',
                              'Hook Hook-C event ACTION called by Source-A',
                              'Source-A.ACTION hook call outcome: OK',
                              'Hook Hook-D event ACTION called by Source-A',
                              'Source-A.ACTION hook call outcome: OK',
                              'Hook Hook-A event ACTION called by Source-A',
                              'Source-A.ACTION hook call outcome: OK',
                              'Hook Hook-B event ACTION called by Source-A',
                              'Source-A.ACTION hook call outcome: ERROR (Error in hook)'])
        # Optimizations
        self.assertIn(HookFlag.CLASS, hook_manager.flags)
        self.assertIn(HookFlag.INSTANCE, hook_manager.flags)
        self.assertIn(HookFlag.ANY_EVENT, hook_manager.flags)
        self.assertIn(HookFlag.NAME, hook_manager.flags)
    def test_class_hooks(self):
        # register hookables
        hook_manager.register_class(MyHookable, MyEvents)
        # Install hooks
        hook_A: MyHook = MyHook(self, 'Hook-A')
        hook_B: MyHook = MyHook(self, 'Hook-B')
        hook_C: MyHook = MyHook(self, 'Hook-C')
        hook_D: MyHook = MyHook(self, 'Hook-D')
        hook_manager.add_hook(MyEvents.CREATE, MyHookable, hook_A.callback)
        hook_manager.add_hook(ANY, MyHookable, hook_B.err_callback)
        hook_manager.add_hook(MyEvents.CREATE, 'Source-A', hook_C.callback)
        hook_manager.add_hook(ANY, 'Source-A', hook_D.callback)
        # Create event sources, emits CREATE
        self.output.clear()
        MyHookable(self, 'Source-A', use_class=True)
        self.assertListEqual(self.output,
                             ['Hook Hook-A event CREATE called by Source-A',
                              'Source-A.CREATE hook call outcome: OK',
                              'Hook Hook-B event CREATE called by Source-A',
                              'Source-A.CREATE hook call outcome: ERROR (Error in hook)'])
    def test_name_hooks(self):
        # register hookables
        hook_manager.register_class(MyHookable, MyEvents)
        # Install hooks
        hook_A: MyHook = MyHook(self, 'Hook-A')
        hook_B: MyHook = MyHook(self, 'Hook-B')
        hook_C: MyHook = MyHook(self, 'Hook-C')
        hook_D: MyHook = MyHook(self, 'Hook-D')
        hook_manager.add_hook(MyEvents.CREATE, MyHookable, hook_A.callback)
        hook_manager.add_hook(ANY, MyHookable, hook_B.err_callback)
        hook_manager.add_hook(MyEvents.CREATE, 'Source-A', hook_C.callback)
        hook_manager.add_hook(ANY, 'Source-A', hook_D.err_callback)
        # Create event sources, emits CREATE
        self.output.clear()
        MyHookable(self, 'Source-A', use_name=True)
        self.assertListEqual(self.output,
                             ['Hook Hook-C event CREATE called by Source-A',
                              'Source-A.CREATE hook call outcome: OK',
                              'Hook Hook-D event CREATE called by Source-A',
                              'Source-A.CREATE hook call outcome: ERROR (Error in hook)'])



if __name__ == '__main__':
    unittest.main()
