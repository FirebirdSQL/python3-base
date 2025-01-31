# SPDX-FileCopyrightText: 2019-present The Firebird Projects <www.firebirdsql.org>
#
# SPDX-License-Identifier: MIT
#
# PROGRAM/MODULE: firebird-base
# FILE:           tests/config/test_cfg_scheme.py
# DESCRIPTION:    Tests for firebird.base.config ApplicationDirectoryScheme
# CREATED:        28.1.2025
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
# Copyright (c) 2025 Firebird Project (www.firebirdsql.org)
# All Rights Reserved.
#
# Contributor(s): Pavel Císař (original code)
#                 ______________________________________.

from __future__ import annotations

import os
import platform
from pathlib import Path

import pytest

from firebird.base import config
from firebird.base.types import Error

_pd = "c:\\ProgramData"
_ap = "C:\\Users\\username\\AppData"
_lap = "C:\\Users\\username\\AppData\\Local"
app_name = "test_app"

@pytest.mark.skipif(platform.system() != "Linux", reason="Only for Linux")
def test_linux_default():
    # Without version
    scheme = config.get_directory_scheme(app_name)
    assert scheme.config == Path("/etc/test_app")
    assert scheme.run_data == Path("/run/test_app")
    assert scheme.logs == Path("/var/log/test_app")
    assert scheme.data == Path("/var/lib/test_app")
    assert scheme.tmp == Path("/var/tmp/test_app")
    assert scheme.cache == Path("/var/cache/test_app")
    assert scheme.srv == Path("/srv/test_app")
    assert scheme.user_config == Path("~/.config/test_app").expanduser()
    assert scheme.user_data == Path("~/.local/share/test_app").expanduser()
    assert scheme.user_sync == Path("~/.local/sync/test_app").expanduser()
    assert scheme.user_cache == Path("~/.cache/test_app").expanduser()
    # With version
    scheme = config.get_directory_scheme(app_name, "1.0")
    assert scheme.config == Path("/etc/test_app/1.0")
    assert scheme.run_data == Path("/run/test_app/1.0")
    assert scheme.logs == Path("/var/log/test_app/1.0")
    assert scheme.data == Path("/var/lib/test_app/1.0")
    assert scheme.tmp == Path("/var/tmp/test_app/1.0")
    assert scheme.cache == Path("/var/cache/test_app/1.0")
    assert scheme.srv == Path("/srv/test_app/1.0")
    assert scheme.user_config == Path("~/.config/test_app/1.0").expanduser()
    assert scheme.user_data == Path("~/.local/share/test_app/1.0").expanduser()
    assert scheme.user_sync == Path("~/.local/sync/test_app/1.0").expanduser()
    assert scheme.user_cache == Path("~/.cache/test_app/1.0").expanduser()

@pytest.mark.skipif(platform.system() != "Linux", reason="Only for Linux")
def test_linux_home_env(monkeypatch):
    monkeypatch.setenv(f"{app_name.upper()}_HOME", "/mydir/apphome/")
    scheme = config.get_directory_scheme(app_name)
    assert scheme.config == Path("/mydir/apphome/config")
    assert scheme.run_data == Path("/mydir/apphome/run_data")
    assert scheme.logs == Path("/mydir/apphome/logs")
    assert scheme.data == Path("/mydir/apphome/data")
    assert scheme.tmp == Path("/var/tmp/test_app")
    assert scheme.cache == Path("/mydir/apphome/cache")
    assert scheme.srv == Path("/mydir/apphome/srv")
    assert scheme.user_config == Path("~/.config/test_app").expanduser()
    assert scheme.user_data == Path("~/.local/share/test_app").expanduser()
    assert scheme.user_sync == Path("~/.local/sync/test_app").expanduser()
    assert scheme.user_cache == Path("~/.cache/test_app").expanduser()

@pytest.mark.skipif(platform.system() != "Linux", reason="Only for Linux")
def test_linux_home_forced(monkeypatch):
    def fake_cwd():
        return "/mydir/apphome/"
    monkeypatch.setattr(os, "getcwd", fake_cwd)
    scheme = config.get_directory_scheme(app_name, force_home=True)
    assert scheme.config == Path("/mydir/apphome/config")
    assert scheme.run_data == Path("/mydir/apphome/run_data")
    assert scheme.logs == Path("/mydir/apphome/logs")
    assert scheme.data == Path("/mydir/apphome/data")
    assert scheme.tmp == Path("/var/tmp/test_app")
    assert scheme.cache == Path("/mydir/apphome/cache")
    assert scheme.srv == Path("/mydir/apphome/srv")
    assert scheme.user_config == Path("~/.config/test_app").expanduser()
    assert scheme.user_data == Path("~/.local/share/test_app").expanduser()
    assert scheme.user_sync == Path("~/.local/sync/test_app").expanduser()
    assert scheme.user_cache == Path("~/.cache/test_app").expanduser()

@pytest.mark.skipif(platform.system() != "Linux", reason="Only for Linux")
def test_linux_home_change():
    scheme = config.get_directory_scheme(app_name, force_home=True)
    scheme.home = "/mydir/apphome/"
    assert scheme.config == Path("/mydir/apphome/config")
    assert scheme.run_data == Path("/mydir/apphome/run_data")
    assert scheme.logs == Path("/mydir/apphome/logs")
    assert scheme.data == Path("/mydir/apphome/data")
    assert scheme.tmp == Path("/var/tmp/test_app")
    assert scheme.cache == Path("/mydir/apphome/cache")
    assert scheme.srv == Path("/mydir/apphome/srv")
    assert scheme.user_config == Path("~/.config/test_app").expanduser()
    assert scheme.user_data == Path("~/.local/share/test_app").expanduser()
    assert scheme.user_sync == Path("~/.local/sync/test_app").expanduser()
    assert scheme.user_cache == Path("~/.cache/test_app").expanduser()

@pytest.mark.skipif(platform.system() != "Windows", reason="Only for Windows")
def test_widnows_default():
    # Without version
    scheme = config.get_directory_scheme(app_name)
    assert scheme.config == Path("c:/ProgramData/test_app/config")
    assert scheme.run_data == Path("c:/ProgramData/test_app/run")
    assert scheme.logs == Path("c:/ProgramData/test_app/log")
    assert scheme.data == Path("c:/ProgramData/test_app/data")
    assert scheme.tmp == Path("~/AppData/Local/test_app/tmp").expanduser()
    assert scheme.cache == Path("c:/ProgramData/test_app/cache")
    assert scheme.srv == Path("c:/ProgramData/test_app/srv")
    assert scheme.user_config == Path("~/AppData/Local/test_app/config").expanduser()
    assert scheme.user_data == Path("~/AppData/Local/test_app/data").expanduser()
    assert scheme.user_sync == Path("~/AppData/Roaming/test_app").expanduser()
    assert scheme.user_cache == Path("~/AppData/Local/test_app/cache").expanduser()
    # With version
    assert scheme.config == Path("c:/ProgramData/test_app/1.0/config")
    assert scheme.run_data == Path("c:/ProgramData/test_app/1.0/run")
    assert scheme.logs == Path("c:/ProgramData/test_app/1.0/log")
    assert scheme.data == Path("c:/ProgramData/test_app/1.0/data")
    assert scheme.tmp == Path("~/AppData/Local/test_app/1.0/tmp").expanduser()
    assert scheme.cache == Path("c:/ProgramData/test_app/1.0/cache")
    assert scheme.srv == Path("c:/ProgramData/test_app/1.0/srv")
    assert scheme.user_config == Path("~/AppData/Local/test_app/1.0/config").expanduser()
    assert scheme.user_data == Path("~/AppData/Local/test_app/1.0/data").expanduser()
    assert scheme.user_sync == Path("~/AppData/Roaming/test_app/1.0").expanduser()
    assert scheme.user_cache == Path("~/AppData/Local/test_app/1.0/cache").expanduser()

@pytest.mark.skipif(platform.system() != "Windows", reason="Only for Windows")
def test_widnows_home_env(monkeypatch):
    monkeypatch.setenv(f"{app_name.upper()}_HOME", "c:/mydir/apphome/")
    scheme = config.get_directory_scheme(app_name)
    assert scheme.config == Path("c:/mydir/apphome/config")
    assert scheme.run_data == Path("c:/mydir/apphome/run_data")
    assert scheme.logs == Path("c:/mydir/apphome/logs")
    assert scheme.data == Path("c:/mydir/apphome/data")
    assert scheme.tmp == Path("~/AppData/Local/test_app/tmp").expanduser()
    assert scheme.cache == Path("c:/mydir/apphome/cache")
    assert scheme.srv == Path("c:/mydir/apphome/srv")
    assert scheme.user_config == Path("~/AppData/Local/test_app/config").expanduser()
    assert scheme.user_data == Path("~/AppData/Local/test_app/data").expanduser()
    assert scheme.user_sync == Path("~/AppData/Roaming/test_app").expanduser()
    assert scheme.user_cache == Path("~/AppData/Local/test_app/cache").expanduser()

@pytest.mark.skipif(platform.system() != "Windows", reason="Only for Windows")
def test_widnows_home_forced(monkeypatch):
    def fake_cwd():
        return "c:/mydir/apphome/"
    monkeypatch.setattr(os, "getcwd", fake_cwd)
    scheme = config.get_directory_scheme(app_name)
    assert scheme.config == Path("c:/mydir/apphome/config")
    assert scheme.run_data == Path("c:/mydir/apphome/run_data")
    assert scheme.logs == Path("c:/mydir/apphome/logs")
    assert scheme.data == Path("c:/mydir/apphome/data")
    assert scheme.tmp == Path("~/AppData/Local/test_app/tmp").expanduser()
    assert scheme.cache == Path("c:/mydir/apphome/cache")
    assert scheme.srv == Path("c:/mydir/apphome/srv")
    assert scheme.user_config == Path("~/AppData/Local/test_app/config").expanduser()
    assert scheme.user_data == Path("~/AppData/Local/test_app/data").expanduser()
    assert scheme.user_sync == Path("~/AppData/Roaming/test_app").expanduser()
    assert scheme.user_cache == Path("~/AppData/Local/test_app/cache").expanduser()

@pytest.mark.skipif(platform.system() != "Windows", reason="Only for Windows")
def test_04_widnows_home_change():
    scheme = config.get_directory_scheme(app_name)
    scheme.home = "c:/mydir/apphome/"
    assert scheme.config == Path("c:/mydir/apphome/config")
    assert scheme.run_data == Path("c:/mydir/apphome/run_data")
    assert scheme.logs == Path("c:/mydir/apphome/logs")
    assert scheme.data == Path("c:/mydir/apphome/data")
    assert scheme.tmp == Path("~/AppData/Local/test_app/tmp").expanduser()
    assert scheme.cache == Path("c:/mydir/apphome/cache")
    assert scheme.srv == Path("c:/mydir/apphome/srv")
    assert scheme.user_config == Path("~/AppData/Local/test_app/config").expanduser()
    assert scheme.user_data == Path("~/AppData/Local/test_app/data").expanduser()
    assert scheme.user_sync == Path("~/AppData/Roaming/test_app").expanduser()
    assert scheme.user_cache == Path("~/AppData/Local/test_app/cache").expanduser()
