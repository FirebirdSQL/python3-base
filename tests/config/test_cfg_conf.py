# SPDX-FileCopyrightText: 2019-present The Firebird Projects <www.firebirdsql.org>
#
# SPDX-License-Identifier: MIT
#
# PROGRAM/MODULE: firebird-base
# FILE:           tests/config/test_cfg_conf.py
# DESCRIPTION:    Tests for firebird.base.config Config, ConfigOption and ConfigListOption
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

from enum import IntEnum

import pytest

from firebird.base import config
from firebird.base.types import Error

DEFAULT_S = "DEFAULT"
PRESENT_S = "present"
ABSENT_S = "absent"
BAD_S = "bad_value"
EMPTY_S = "empty"

class SimpleEnum(IntEnum):
    "Enum for testing"
    UNKNOWN    = 0
    READY      = 1
    RUNNING    = 2
    WAITING    = 3
    SUSPENDED  = 4
    FINISHED   = 5
    ABORTED    = 6
    # Aliases
    CREATED    = 1
    BLOCKED    = 3
    STOPPED    = 4
    TERMINATED = 6

class DbConfig(config.Config):
    "Simple DB config for testing"
    def __init__(self, name: str):
        super().__init__(name)
        # options
        self.database: config.StrOption = config.StrOption("database", "Database connection string",
                                                           required=True)
        self.user: config.StrOption = config.StrOption("user", "User name", required=True,
                                                       default="SYSDBA")
        self.password: config.StrOption = config.StrOption("password", "User password")

class SimpleConfig(config.Config):
    """Simple Config for testing.

Has three options and two sub-configs.
"""
    def __init__(self, *, optional: bool=False):
        super().__init__("simple-config", optional=optional)
        # options
        self.opt_str: config.StrOption = config.StrOption("opt_str", "Simple string option")
        self.opt_int: config.IntOption = config.StrOption("opt_int", "Simple int option")
        self.enum_list: config.ListOption = config.ListOption("enum_list", SimpleEnum, "List of enum values")
        self.main_db: config.ConfigOption = config.ConfigOption("main_db", DbConfig(""), "Main database")
        self.opt_cfgs: config.ConfigListOption = config.ConfigListOption("opt_cfgs", DbConfig, "List of databases")
        # sub configs
        self.master_db: DbConfig = DbConfig("master-db")
        self.backup_db: DbConfig = DbConfig("backup-db")

@pytest.fixture
def conf(base_conf):
    """Returns configparser initialized with data.
    """
    conf_str = """[%(DEFAULT)s]
password = masterkey
[%(PRESENT)s]
opt_str = Lorem ipsum
enum_list = ready, finished, aborted
main_db = my-main-db
opt_cfgs = db-one, db-two

[master-db]
database = primary
user = tester
password = lockpick

[backup-db]
database = secondary

[my-main-db]
database = main

[db-one]
database = one
[db-two]
database = two
[%(ABSENT)s]
[%(BAD)s]
"""
    base_conf.read_string(conf_str % {"DEFAULT": DEFAULT_S, "PRESENT": PRESENT_S,
                                      "ABSENT": ABSENT_S, "BAD": BAD_S, "EMPTY": EMPTY_S,})
    return base_conf

def test_basics(conf):
    cfg = SimpleConfig()
    assert cfg.name == "simple-config"
    assert len(cfg.options) == 5
    assert cfg.opt_str in cfg.options
    assert cfg.opt_int in cfg.options
    assert cfg.enum_list in cfg.options
    assert len(cfg.configs) == 3
    assert cfg.master_db in cfg.configs
    assert cfg.backup_db in cfg.configs
    #
    assert cfg.opt_str.value is None
    assert cfg.opt_int.value is None
    assert cfg.enum_list.value is None
    assert isinstance(cfg.master_db, DbConfig)
    assert isinstance(cfg.backup_db, DbConfig)
    assert isinstance(cfg.main_db.value, DbConfig)
    assert isinstance(cfg.opt_cfgs.value, list)
    assert cfg.main_db.value.database.value is None
    assert cfg.main_db.value.user.value == "SYSDBA"
    assert cfg.main_db.value.password.value is None
    assert cfg.master_db.database.value is None
    assert cfg.master_db.user.value == "SYSDBA"
    assert cfg.master_db.password.value is None
    assert cfg.backup_db.database.value is None
    assert cfg.backup_db.user.value == "SYSDBA"
    assert cfg.backup_db.password.value is None
    assert cfg.main_db.value.name == cfg.main_db.get_as_str()
    assert cfg.opt_cfgs.get_formatted() == "<UNDEFINED>"
    #
    with pytest.raises(ValueError) as cm:
        cfg.opt_str = "value"
    assert cm.value.args == ("Cannot assign values to option itself, use 'option.value' instead",)
    #
    cfg.opt_cfgs.value = [DbConfig("test-db")]
    assert len(cfg.configs) == 4
    assert len(cfg.opt_cfgs.value) == 1
    assert cfg.opt_cfgs.value[0].name == "test-db"
    #
    with pytest.raises(ValueError) as cm:
        cfg.opt_cfgs.value = [list()]
    assert cm.value.args == ("List item[0] has wrong type",)

def test_load_config(conf):
    ocfg = SimpleConfig(optional=True)
    #
    ocfg.load_config(conf, "(no-section)")
    assert ocfg.optional
    assert ocfg.opt_str.value is None
    #
    cfg = SimpleConfig()
    #
    with pytest.raises(Error):
        cfg.load_config(conf)
    #
    cfg.load_config(conf, PRESENT_S)
    cfg.validate()
    assert len(cfg.configs) == 5
    assert cfg.opt_str.value == "Lorem ipsum"
    assert cfg.opt_int.value is None
    assert cfg.enum_list.value == [SimpleEnum.READY, SimpleEnum.FINISHED, SimpleEnum.ABORTED]
    #
    assert cfg.main_db.value.database.value == "main"
    assert cfg.main_db.value.user.value == "SYSDBA"
    assert cfg.main_db.value.password.value == "masterkey"
    #
    assert cfg.master_db.database.value == "primary"
    assert cfg.master_db.user.value == "tester"
    assert cfg.master_db.password.value == "lockpick"
    #
    assert cfg.backup_db.database.value == "secondary"
    assert cfg.backup_db.user.value == "SYSDBA"
    assert cfg.backup_db.password.value == "masterkey"
    #
    assert cfg.opt_cfgs.get_as_str() == "db-one, db-two"
    assert cfg.opt_cfgs.value[0].database.value == "one"
    assert cfg.opt_cfgs.value[1].database.value == "two"

def test_clear(conf):
    cfg = SimpleConfig()
    cfg.load_config(conf, PRESENT_S)
    cfg.clear()
    #
    assert cfg.opt_str.value is None
    assert cfg.opt_int.value is None
    assert cfg.enum_list.value is None
    assert len(cfg.opt_cfgs.value) == 0
    assert cfg.master_db.database.value is None
    assert cfg.master_db.user.value == "SYSDBA"
    assert cfg.master_db.password.value is None
    assert cfg.backup_db.database.value is None
    assert cfg.backup_db.user.value == "SYSDBA"
    assert cfg.backup_db.password.value is None

def test_4_proto(conf, proto):
    cfg = SimpleConfig()
    cfg.load_config(conf, PRESENT_S)
    #
    cfg.save_proto(proto)
    cfg.clear()
    cfg.load_proto(proto)
    #
    assert cfg.opt_str.value == "Lorem ipsum"
    assert cfg.opt_int.value is None
    assert cfg.enum_list.value == [SimpleEnum.READY, SimpleEnum.FINISHED, SimpleEnum.ABORTED]
    #
    assert cfg.main_db.value.database.value == "main"
    assert cfg.main_db.value.user.value == "SYSDBA"
    assert cfg.main_db.value.password.value == "masterkey"
    #
    assert cfg.master_db.database.value == "primary"
    assert cfg.master_db.user.value == "tester"
    assert cfg.master_db.password.value == "lockpick"
    #
    assert cfg.backup_db.database.value == "secondary"
    assert cfg.backup_db.user.value == "SYSDBA"
    assert cfg.backup_db.password.value == "masterkey"
    #
    assert cfg.opt_cfgs.get_as_str() == "db-one, db-two"
    assert cfg.opt_cfgs.value[0].database.value == "one"
    assert cfg.opt_cfgs.value[1].database.value == "two"

def test_5_get_config(conf):
    cfg = SimpleConfig()
    lines = """[simple-config]
;
; Simple Config for testing.
;
; Has three options and two sub-configs.

; Simple string option
; Type: str
;opt_str = <UNDEFINED>

; Simple int option
; Type: str
;opt_int = <UNDEFINED>

; List of enum values
; Type: list [SimpleEnum]
;enum_list = <UNDEFINED>

; Main database
; Type: configuration section name
main_db =

; List of databases
; Type: list of configuration section names
;opt_cfgs = <UNDEFINED>

[master-db]
;
; Simple DB config for testing

; REQUIRED option.
; Database connection string
; Type: str
;database = <UNDEFINED>

; REQUIRED option.
; User name
; Type: str
;user = SYSDBA

; User password
; Type: str
;password = <UNDEFINED>

[backup-db]
;
; Simple DB config for testing

; REQUIRED option.
; Database connection string
; Type: str
;database = <UNDEFINED>

; REQUIRED option.
; User name
; Type: str
;user = SYSDBA

; User password
; Type: str
;password = <UNDEFINED>"""
    assert "\n".join(x.strip() for x in cfg.get_config().splitlines()) == lines
    #
    cfg.load_config(conf, PRESENT_S)
    lines = """[simple-config]
;
; Simple Config for testing.
;
; Has three options and two sub-configs.

; Simple string option
; Type: str
opt_str = Lorem ipsum

; Simple int option
; Type: str
;opt_int = <UNDEFINED>

; List of enum values
; Type: list [SimpleEnum]
enum_list = READY, FINISHED, ABORTED

; Main database
; Type: configuration section name
main_db = my-main-db

; List of databases
; Type: list of configuration section names
opt_cfgs = db-one, db-two

[my-main-db]
;
; Simple DB config for testing

; REQUIRED option.
; Database connection string
; Type: str
database = main

; REQUIRED option.
; User name
; Type: str
;user = SYSDBA

; User password
; Type: str
password = masterkey

[master-db]
;
; Simple DB config for testing

; REQUIRED option.
; Database connection string
; Type: str
database = primary

; REQUIRED option.
; User name
; Type: str
user = tester

; User password
; Type: str
password = lockpick

[backup-db]
;
; Simple DB config for testing

; REQUIRED option.
; Database connection string
; Type: str
database = secondary

; REQUIRED option.
; User name
; Type: str
;user = SYSDBA

; User password
; Type: str
password = masterkey

[db-one]
;
; Simple DB config for testing

; REQUIRED option.
; Database connection string
; Type: str
database = one

; REQUIRED option.
; User name
; Type: str
;user = SYSDBA

; User password
; Type: str
password = masterkey

[db-two]
;
; Simple DB config for testing

; REQUIRED option.
; Database connection string
; Type: str
database = two

; REQUIRED option.
; User name
; Type: str
;user = SYSDBA

; User password
; Type: str
password = masterkey"""
    assert "\n".join(x.strip() for x in cfg.get_config().splitlines()) == lines
