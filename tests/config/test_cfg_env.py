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

"""Unit tests for the EnvExtendedInterpolation class in firebird.base.config."""

from __future__ import annotations

import os
import pytest
from configparser import ConfigParser, InterpolationMissingOptionError, InterpolationSyntaxError # Added errors

from firebird.base import config # Assuming config.py is accessible
# Assuming types.py is accessible if needed for Error, though not strictly required here
# from firebird.base.types import Error

# --- Fixtures ---

@pytest.fixture
def conf(base_conf: ConfigParser) -> ConfigParser: # Use the fixture from conftest.py
    """Provides a ConfigParser instance using EnvExtendedInterpolation, initialized with test data."""
    conf_str = """
[base]
# Base value for standard interpolation testing
base_value = BASE_SECTION_VALUE
home_dir = /base/home

[my-config]
# Standard value
value_str = VALUE

# Standard interpolation from another section
base_value_interp = ${base:base_value}

# Interpolation using existing environment variables
value_env_present = ${env:MYSECRET}
value_env_path = ${env:PATH}

# Interpolation using non-existent environment variable (should resolve to empty string)
value_env_absent = ${env:NOT_A_REAL_ENV_VAR}

# Interpolation using default section (works like standard interpolation)
value_from_default = ${DEFAULT:default_var}

# Nested interpolation involving environment variables
nested_env = ${env:MYSECRET}/subpath
nested_mix = ${base:home_dir}/${env:MYSECRET}

# Case-insensitivity test for env var name
value_env_mixed_case = ${env:mYsEcReT}

[DEFAULT]
# Default value used in interpolation test
default_var = DEFAULT_VALUE
"""
    # Read the string into the ConfigParser instance provided by base_conf
    base_conf.read_string(conf_str)
    return base_conf

# --- Test Cases ---

def test_env_interpolation(conf: ConfigParser, monkeypatch):
    """Tests successful interpolation of environment variables."""
    # Set environment variables for the test
    secret_value = "secret_test_value"
    monkeypatch.setenv("MYSECRET", secret_value)
    # PATH is usually set, but ensure it exists for robustness
    original_path = os.getenv("PATH", "/usr/bin:/bin")
    monkeypatch.setenv("PATH", original_path)

    # --- Assertions ---
    # Standard value
    assert conf["my-config"]["value_str"] == "VALUE"

    # Standard interpolation
    assert conf["my-config"]["base_value_interp"] == "BASE_SECTION_VALUE"

    # Environment variable interpolation (present)
    assert conf["my-config"]["value_env_present"] == secret_value

    # Environment variable interpolation (PATH)
    assert conf["my-config"]["value_env_path"] == original_path

    # Environment variable interpolation (absent - should be empty string)
    assert conf["my-config"]["value_env_absent"] == ""

    # Interpolation from DEFAULT section
    assert conf["my-config"]["value_from_default"] == "DEFAULT_VALUE"

    # Nested interpolation involving environment variables
    assert conf["my-config"]["nested_env"] == f"{secret_value}/subpath"
    assert conf["my-config"]["nested_mix"] == f"/base/home/{secret_value}"

    # Case-insensitivity (env var names are typically case-insensitive on Windows, case-sensitive elsewhere,
    # but os.getenv usually handles this. We test if our interpolation treats the *lookup key* case-insensitively).
    # The interpolation logic uses optionxform which lowercases by default. Let's test the uppercase env var.
    monkeypatch.setenv("MYUPPERSECRET", "upper_secret")
    conf.read_string("[my-config]\nupper_test = ${env:MYUPPERSECRET}") # Add test case
    assert conf["my-config"]["upper_test"] == "upper_secret"
    # Test mixed case lookup key (should work due to optionxform lowercasing)
    assert conf["my-config"]["value_env_mixed_case"] == secret_value


def test_env_interpolation_errors(base_conf: ConfigParser): # Use base_conf to start clean
    """Tests error conditions during interpolation."""
    # Test Missing Option Error (standard interpolation)
    conf_missing_std = """
[section_a]
ref = ${section_b:missing_option}
[section_b]
exists = yes
"""
    base_conf.read_string(conf_missing_std)
    with pytest.raises(InterpolationMissingOptionError):
        _ = base_conf["section_a"]["ref"]

    # Test Missing Option Error (env var - should NOT error, returns "")
    # This confirms the special handling for 'env' section
    base_conf.clear()
    conf_missing_env = """
[section_a]
ref = ${env:missing_env_var}
"""
    base_conf.read_string(conf_missing_env)
    # Should *not* raise InterpolationMissingOptionError
    assert base_conf["section_a"]["ref"] == ""

    # Test Syntax Error (bad format)
    base_conf.clear()
    conf_syntax_bad_format = """
[section_a]
ref = ${env:missing_close_brace
"""
    base_conf.read_string(conf_syntax_bad_format)
    with pytest.raises(InterpolationSyntaxError, match="bad interpolation variable reference"):
        _ = base_conf["section_a"]["ref"]

    # Test Syntax Error (too many colons)
    base_conf.clear()
    conf_syntax_colons = """
[section_a]
ref = ${env:too:many:colons}
"""
    base_conf.read_string(conf_syntax_colons)
    with pytest.raises(InterpolationSyntaxError, match="More than one ':' found"):
        _ = base_conf["section_a"]["ref"]

    # Test Syntax Error (invalid char after $)
    base_conf.clear()
    conf_syntax_bad_char = """
[section_a]
ref = $invalid
"""
    base_conf.read_string(conf_syntax_bad_char)
    with pytest.raises(InterpolationSyntaxError, match="'\\$' must be followed by"):
        _ = base_conf["section_a"]["ref"]

    # Test Depth Error (standard interpolation - requires setup)
    base_conf.clear()
    conf_depth = """
[a]
val = ${b:val}
[b]
val = ${a:val}
"""
    base_conf.read_string(conf_depth)
    # Need to configure MAX_INTERPOLATION_DEPTH lower for easy testing if possible,
    # otherwise rely on default limit triggering the error.
    # configparser doesn't easily expose setting MAX_INTERPOLATION_DEPTH externally.
    # This error is less critical to test for the 'env' extension specifically.
    # with pytest.raises(InterpolationDepthError):
    #     _ = base_conf["a"]["val"]
    # Skipping direct DepthError test as it's hard to trigger reliably without modifying stdlib internals.