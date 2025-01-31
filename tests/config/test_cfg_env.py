# SPDX-FileCopyrightText: 2019-present The Firebird Projects <www.firebirdsql.org>
#
# SPDX-License-Identifier: MIT
#
# PROGRAM/MODULE: firebird-base
# FILE:           tests/config/test_cfg_env.py
# DESCRIPTION:    Tests for firebird.base.config EnvExtendedInterpolation
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

import pytest

from firebird.base import config
from firebird.base.types import Error


@pytest.fixture
def conf(base_conf):
    """Returns configparser initialized with data.
    """
    conf_str = """[base]
base_value = BASE

[my-config]
value_str = VALUE
value_int = 1
base_value = ${base:base_value}
value_env_1 = ${env:mysecret}
value_env_2 = ${env:not-present}
value_env_path = ${env:path}
"""
    base_conf.read_string(conf_str)
    return base_conf

def test_01(conf, monkeypatch):
    monkeypatch.setenv("MYSECRET", "secret")
    assert conf["my-config"]["value_str"] == "VALUE"
    assert conf["my-config"]["value_int"] == "1"
    assert conf["my-config"]["base_value"] == "BASE"
    assert conf["my-config"]["value_env_1"] == "secret"
    assert conf["my-config"]["value_env_2"] == ""
    assert conf["my-config"]["value_env_path"] == os.getenv("PATH")
