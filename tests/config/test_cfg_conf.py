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

"""Unit tests for the Config, ConfigOption, and ConfigListOption classes
in firebird.base.config."""

from __future__ import annotations

from enum import IntEnum
from configparser import ConfigParser # Import for type hinting

import pytest

from firebird.base import config
from firebird.base.types import Error
from firebird.base.config_pb2 import ConfigProto # Import for proto tests

# --- Constants ---
DEFAULT_S = "DEFAULT"
PRESENT_S = "present"
ABSENT_S = "absent"
BAD_S = "bad_value"
EMPTY_S = "empty"

# --- Test Helper Classes ---

class SimpleEnum(IntEnum):
    """Enum for testing ListOption inside Config."""
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
    """Simple database configuration structure for testing nested configs."""
    def __init__(self, name: str, *, optional: bool = False, description: str | None = None):
        """Initializes DbConfig."""
        super().__init__(name, optional=optional, description=description)
        self.database: config.StrOption = config.StrOption("database", "Database connection string",
                                                           required=True) # Made required for validation test
        self.user: config.StrOption = config.StrOption("user", "User name", required=True,
                                                       default="SYSDBA")
        self.password: config.StrOption = config.StrOption("password", "User password")

class SimpleConfig(config.Config):
    """Main configuration structure for testing hierarchical configs.

    Includes various option types and nested Config instances.
    """
    def __init__(self, *, optional: bool = False):
        """Initializes SimpleConfig."""
        super().__init__("simple-config", optional=optional)
        # Options
        self.opt_str: config.StrOption = config.StrOption("opt_str", "Simple string option")
        # Corrected opt_int type
        self.opt_int: config.IntOption = config.IntOption("opt_int", "Simple int option")
        self.enum_list: config.ListOption = config.ListOption("enum_list", SimpleEnum, "List of enum values")
        # ConfigOption for dynamically named sub-config
        self.main_db: config.ConfigOption = config.ConfigOption("main_db", DbConfig(""), "Main database config section name")
        # ConfigListOption for list of dynamically named sub-configs
        self.opt_cfgs: config.ConfigListOption = config.ConfigListOption("opt_cfgs", DbConfig, "List of optional database sections")
        # Fixed-name sub-configs as direct attributes
        self.master_db: DbConfig = DbConfig("master-db")
        self.backup_db: DbConfig = DbConfig("backup-db")

class ConfigWithDocstring(config.Config):
    """Config class with docstring but no explicit description."""
    def __init__(self, name: str):
        # Note: super().__init__ does *not* get description here
        super().__init__(name)
        self.option1: config.StrOption = config.StrOption("option1", "Option 1")


# --- Fixtures ---

@pytest.fixture
def base_conf_data() -> str:
    """Provides the raw string data for the base ConfigParser fixture."""
    # Added password to DEFAULT section for testing default inheritance
    # Added section for missing required value test
    return """
[%(DEFAULT)s]
password = masterkey

[%(PRESENT)s]
opt_str = Lorem ipsum
opt_int = 123
enum_list = ready, finished, aborted
main_db = my-main-db
opt_cfgs = db-one, db-two

[master-db]
database = primary:/path/master.fdb
user = tester
password = lockpick

[backup-db]
database = secondary:/path/backup.fdb
# user uses DEFAULT (SYSDBA)
# password uses DEFAULT (masterkey)

[my-main-db]
database = main:/path/main.fdb
# user uses DEFAULT (SYSDBA)
# password uses DEFAULT (masterkey)

[db-one]
database = /path/db1.fdb
user = user1

[db-two]
database = /path/db2.fdb
# user uses DEFAULT (SYSDBA)

[%(ABSENT)s]
# Section exists but is empty

[%(BAD)s]
# Used for option-specific bad value tests

[missing_req_sub]
opt_str = Subconfig present but required value missing
opt_int = 456
main_db = sub-config-missing-db-req

[sub-config-missing-db-req]
# Missing the required 'database' option
user = bad_user
"""

@pytest.fixture
def conf(base_conf: ConfigParser, base_conf_data: str) -> ConfigParser:
    """Returns a ConfigParser initialized with test data."""
    conf_str = base_conf_data % {"DEFAULT": DEFAULT_S, "PRESENT": PRESENT_S,
                                 "ABSENT": ABSENT_S, "BAD": BAD_S, "EMPTY": EMPTY_S}
    base_conf.read_string(conf_str)
    return base_conf

# --- Test Cases ---

def test_basics(conf: ConfigParser):
    """Tests basic Config initialization, structure, and attribute access."""
    cfg = SimpleConfig()

    # Test basic attributes
    assert cfg.name == "simple-config"
    assert not cfg.optional

    # Test discovery of options and configs
    assert len(cfg.options) == 5, "Should find 5 direct Option attributes"
    assert cfg.opt_str in cfg.options
    assert cfg.opt_int in cfg.options
    assert cfg.enum_list in cfg.options
    assert cfg.main_db in cfg.options # ConfigOption counts as an option
    assert cfg.opt_cfgs in cfg.options # ConfigListOption counts as an option

    # Initial state: main_db points to empty-named config, opt_cfgs is empty list
    assert len(cfg.configs) == 3, "Should find 2 direct Config attributes + 1 empty from main_db"
    assert cfg.master_db in cfg.configs
    assert cfg.backup_db in cfg.configs
    assert cfg.main_db.value in cfg.configs # The actual DbConfig instance from ConfigOption

    # Check initial values (before loading)
    assert cfg.opt_str.value is None
    assert cfg.opt_int.value is None
    assert cfg.enum_list.value is None
    assert isinstance(cfg.master_db, DbConfig)
    assert isinstance(cfg.backup_db, DbConfig)
    assert isinstance(cfg.main_db.value, DbConfig)
    assert isinstance(cfg.opt_cfgs.value, list) and not cfg.opt_cfgs.value

    # Check sub-config initial state (defaults should apply)
    assert cfg.main_db.value.database.value is None # Required, no default
    assert cfg.main_db.value.user.value == "SYSDBA" # Has default
    assert cfg.main_db.value.password.value is None # Optional, no default
    assert cfg.master_db.database.value is None
    assert cfg.master_db.user.value == "SYSDBA"
    assert cfg.master_db.password.value is None

    # Test ConfigOption specific methods
    assert cfg.main_db.get_value() is cfg.main_db._value # get_value returns the Config instance
    assert cfg.main_db.get_as_str() == "" # Initial name is empty

    # Test ConfigListOption specific methods
    assert cfg.opt_cfgs.get_value() == []
    assert cfg.opt_cfgs.get_formatted() == "<UNDEFINED>" # Representation of empty list

    # Test direct assignment prevention
    with pytest.raises(ValueError, match="Cannot assign values to option itself"):
        cfg.opt_str = "value" # type: ignore

    # Test changing ConfigListOption value and reflected configs
    test_db_instance = DbConfig("test-db")
    cfg.opt_cfgs.value = [test_db_instance]
    assert len(cfg.configs) == 4, "configs should now include the one from opt_cfgs"
    assert len(cfg.opt_cfgs.value) == 1
    assert cfg.opt_cfgs.value[0].name == "test-db"
    assert test_db_instance in cfg.configs

    # Test assigning invalid type to ConfigListOption
    with pytest.raises(ValueError, match="List item\\[0\\] has wrong type: Expected 'DbConfig', got 'list'"):
        cfg.opt_cfgs.value = [list()] # type: ignore


def test_load_config(conf: ConfigParser):
    """Tests loading hierarchical configuration using Config.load_config.

    Verifies that options in the main config and nested Config instances (both
    direct attributes and via ConfigOption/ConfigListOption) are correctly populated
    from the ConfigParser object, including handling of defaults from DEFAULTSECT.
    """
    ocfg = SimpleConfig(optional=True)
    # Loading optional config from non-existent section should do nothing
    ocfg.load_config(conf, "no-such-section")
    assert ocfg.optional
    assert ocfg.opt_str.value is None

    cfg = SimpleConfig()
    # Loading mandatory config from non-existent section should fail
    with pytest.raises(Error, match="Configuration error: section 'no-such-section' not found!"):
        cfg.load_config(conf, "no-such-section")

    # Load from the PRESENT section
    cfg.load_config(conf, PRESENT_S)
    cfg.validate() # Should pass now

    # Check main config options
    assert cfg.opt_str.value == "Lorem ipsum"
    assert cfg.opt_int.value == 123
    assert cfg.enum_list.value == [SimpleEnum.READY, SimpleEnum.FINISHED, SimpleEnum.ABORTED]

    # Check ConfigOption (main_db) - name loaded, sub-config loaded
    assert cfg.main_db.value.name == "my-main-db"
    assert cfg.main_db.value.database.value == "main:/path/main.fdb"
    assert cfg.main_db.value.user.value == "SYSDBA" # Default
    assert cfg.main_db.value.password.value == "masterkey" # From DEFAULTSECT

    # Check fixed sub-configs (master_db, backup_db)
    assert cfg.master_db.database.value == "primary:/path/master.fdb"
    assert cfg.master_db.user.value == "tester"
    assert cfg.master_db.password.value == "lockpick"

    assert cfg.backup_db.database.value == "secondary:/path/backup.fdb"
    assert cfg.backup_db.user.value == "SYSDBA" # Default
    assert cfg.backup_db.password.value == "masterkey" # From DEFAULTSECT

    # Check ConfigListOption (opt_cfgs) - list of names loaded, sub-configs loaded
    assert cfg.opt_cfgs.get_as_str() == "db-one, db-two"
    assert len(cfg.opt_cfgs.value) == 2
    assert cfg.opt_cfgs.value[0].name == "db-one"
    assert cfg.opt_cfgs.value[0].database.value == "/path/db1.fdb"
    assert cfg.opt_cfgs.value[0].user.value == "user1"
    assert cfg.opt_cfgs.value[0].password.value == "masterkey" # From DEFAULTSECT

    assert cfg.opt_cfgs.value[1].name == "db-two"
    assert cfg.opt_cfgs.value[1].database.value == "/path/db2.fdb"
    assert cfg.opt_cfgs.value[1].user.value == "SYSDBA" # Default
    assert cfg.opt_cfgs.value[1].password.value == "masterkey" # From DEFAULTSECT

    # Check total number of discovered Config instances after loading
    assert len(cfg.configs) == 5 # master, backup, main_db's target, opt_cfg[0], opt_cfg[1]


def test_clear(conf: ConfigParser):
    """Tests the clear method, ensuring it resets options and nested configs."""
    cfg = SimpleConfig()
    cfg.load_config(conf, PRESENT_S)

    # Verify some values are set before clear
    assert cfg.opt_str.value is not None
    assert cfg.master_db.user.value == "tester"
    assert len(cfg.opt_cfgs.value) > 0
    assert cfg.main_db.value.name == "my-main-db"

    # Clear to None/Defaults
    cfg.clear(to_default=True)

    # Check main options reset
    assert cfg.opt_str.value is None # No default defined
    assert cfg.opt_int.value is None # No default defined
    assert cfg.enum_list.value is None # No default defined

    # Check ConfigOption reset (sub-config values cleared to defaults)
    assert cfg.main_db.value.database.value is None # No default
    assert cfg.main_db.value.user.value == "SYSDBA" # Reset to default
    assert cfg.main_db.value.password.value is None # No default

    # Check ConfigListOption reset (list cleared)
    assert len(cfg.opt_cfgs.value) == 0

    # Check fixed sub-configs reset to defaults
    assert cfg.master_db.database.value is None
    assert cfg.master_db.user.value == "SYSDBA"
    assert cfg.master_db.password.value is None

    assert cfg.backup_db.database.value is None
    assert cfg.backup_db.user.value == "SYSDBA"
    assert cfg.backup_db.password.value is None


def test_proto(conf: ConfigParser, proto: ConfigProto):
    """Tests serialization to and deserialization from Protobuf messages."""
    cfg_write = SimpleConfig()
    cfg_write.load_config(conf, PRESENT_S)

    # Serialize to proto
    cfg_write.save_proto(proto)

    # Deserialize into a new, empty config instance
    cfg_read = SimpleConfig()
    cfg_read.load_proto(proto)

    # Verify values match the originally loaded config
    assert cfg_read.opt_str.value == "Lorem ipsum"
    assert cfg_read.opt_int.value == 123
    assert cfg_read.enum_list.value == [SimpleEnum.READY, SimpleEnum.FINISHED, SimpleEnum.ABORTED]

    assert cfg_read.main_db.value.name == "my-main-db"
    assert cfg_read.main_db.value.database.value == "main:/path/main.fdb"
    assert cfg_read.main_db.value.user.value == "SYSDBA"
    assert cfg_read.main_db.value.password.value == "masterkey"

    assert cfg_read.master_db.database.value == "primary:/path/master.fdb"
    assert cfg_read.master_db.user.value == "tester"
    assert cfg_read.master_db.password.value == "lockpick"

    assert cfg_read.backup_db.database.value == "secondary:/path/backup.fdb"
    assert cfg_read.backup_db.user.value == "SYSDBA"
    assert cfg_read.backup_db.password.value == "masterkey"

    assert cfg_read.opt_cfgs.get_as_str() == "db-one, db-two"
    assert len(cfg_read.opt_cfgs.value) == 2
    assert cfg_read.opt_cfgs.value[0].name == "db-one"
    assert cfg_read.opt_cfgs.value[0].database.value == "/path/db1.fdb"
    assert cfg_read.opt_cfgs.value[0].user.value == "user1"
    assert cfg_read.opt_cfgs.value[0].password.value == "masterkey"

    assert cfg_read.opt_cfgs.value[1].name == "db-two"
    assert cfg_read.opt_cfgs.value[1].database.value == "/path/db2.fdb"
    assert cfg_read.opt_cfgs.value[1].user.value == "SYSDBA"
    assert cfg_read.opt_cfgs.value[1].password.value == "masterkey"

    # Test loading from incomplete proto (e.g., missing sub-config)
    proto_incomplete = ConfigProto()
    cfg_write.save_proto(proto_incomplete)
    del proto_incomplete.configs["master-db"] # Remove one sub-config

    cfg_read_incomplete = SimpleConfig()
    cfg_read_incomplete.load_proto(proto_incomplete)
    # Check that the loaded config reflects the missing part (values should be default/None)
    assert cfg_read_incomplete.master_db.database.value is None
    assert cfg_read_incomplete.master_db.user.value == "SYSDBA"
    # Other parts should still be loaded
    assert cfg_read_incomplete.opt_str.value == "Lorem ipsum"
    assert cfg_read_incomplete.backup_db.database.value == "secondary:/path/backup.fdb"


def test_get_config(conf: ConfigParser):
    """Tests the get_config method for generating config file string representation."""
    cfg = SimpleConfig()
    # Get config for default, empty instance
    default_config_str = cfg.get_config()
    assert "[simple-config]" in default_config_str
    assert "; Main configuration structure for testing hierarchical configs." in default_config_str # Description
    assert ";opt_str = <UNDEFINED>" in default_config_str # Option default indication
    assert "main_db =" in default_config_str and "my-main-db" not in default_config_str
    assert ";opt_cfgs = <UNDEFINED>" in default_config_str
    assert "[master-db]" in default_config_str
    assert ";user = SYSDBA" in default_config_str # Default in sub-config

    # Load data and get config again
    cfg.load_config(conf, PRESENT_S)
    loaded_config_str = cfg.get_config()
    assert "[simple-config]" in loaded_config_str
    assert "opt_str = Lorem ipsum" in loaded_config_str
    assert "opt_int = 123" in loaded_config_str # Check corrected type
    assert "enum_list = READY, FINISHED, ABORTED" in loaded_config_str # Check comma default separator
    assert "main_db = my-main-db" in loaded_config_str
    assert "opt_cfgs = db-one, db-two" in loaded_config_str
    assert "[my-main-db]" in loaded_config_str # Section for ConfigOption target
    assert "database = main:/path/main.fdb" in loaded_config_str
    assert ";user = SYSDBA" in loaded_config_str # Still shows default in target section
    assert "password = masterkey" in loaded_config_str
    assert "[master-db]" in loaded_config_str
    assert "user = tester" in loaded_config_str # Overridden default
    assert "password = lockpick" in loaded_config_str
    assert "[backup-db]" in loaded_config_str
    assert ";user = SYSDBA" in loaded_config_str # Shows default
    assert "password = masterkey" in loaded_config_str # Shows inherited default
    assert "[db-one]" in loaded_config_str # Section for ConfigListOption item
    assert "[db-two]" in loaded_config_str # Section for ConfigListOption item

    # Test get_config(plain=True)
    plain_config_str = cfg.get_config(plain=True)
    # Check no comments/descriptions (adjust for default value)
    assert ";" not in plain_config_str.replace(";user = SYSDBA", "user = SYSDBA")
    # Check options are present
    assert "opt_str = Lorem ipsum" in plain_config_str
    assert "opt_int = 123" in plain_config_str
    assert "enum_list = READY, FINISHED, ABORTED" in plain_config_str
    assert "main_db = my-main-db" in plain_config_str
    assert "opt_cfgs = db-one, db-two" in plain_config_str
    # Check sections for sub-configs are included
    assert "[my-main-db]" in plain_config_str
    assert "database = main:/path/main.fdb" in plain_config_str
    assert ";user = SYSDBA" in plain_config_str # Defaults shown plainly
    assert "password = masterkey" in plain_config_str
    assert "[master-db]" in plain_config_str
    assert "[backup-db]" in plain_config_str
    assert "[db-one]" in plain_config_str
    assert "[db-two]" in plain_config_str


def test_validate_subconfig_failure(conf: ConfigParser):
    """Tests that Config.validate fails if a nested config fails validation."""
    cfg = SimpleConfig()
    # Load config where the 'sub-config-missing-db-req' section is missing 'database'
    cfg.load_config(conf, "missing_req_sub")

    # main_db now points to 'sub-config-missing-db-req' which is invalid
    assert cfg.main_db.value.name == "sub-config-missing-db-req"
    assert cfg.main_db.value.database.value is None # Missing required value

    with pytest.raises(Error, match="Missing value for required option 'database'"):
        cfg.validate() # Should fail because main_db.value fails validation


def test_get_description_fallback():
    """Tests that Config.get_description falls back to the class docstring."""
    cfg = ConfigWithDocstring("test_doc")
    assert cfg.get_description() == "Config class with docstring but no explicit description."

def test_load_config_missing_required_section(conf: ConfigParser):
    """Tests Error when load_config points a required ConfigOption to a missing section."""
    # main_db ConfigOption *itself* is required (as it's not optional)
    cfg = SimpleConfig()
    cfg.load_config(conf, PRESENT_S)

    # Load from a config that specifies a section name, but that section doesn't exist
    with pytest.raises(Error, match="Configuration error: section 'missing_req_section_cfg' not found!"):
        # The error occurs when SimpleConfig tries to load the *target* section 'non-existent-section'
        cfg.load_config(conf, "missing_req_section_cfg")


def test_config_option_required(conf: ConfigParser):
    """Tests the 'required' flag on ConfigOption."""
    cfg = SimpleConfig()
    # Make the ConfigOption itself required
    cfg.main_db.required = True

    # Validation should fail if value is empty after init/clear
    cfg.main_db.clear(to_default=False)
    with pytest.raises(Error, match="Missing value for required option 'main_db'"):
        cfg.validate()

    # Should pass after loading a value
    cfg.main_db.clear() # Necessary to restore default values
    cfg.load_config(conf, PRESENT_S)
    assert cfg.main_db.value.name == "my-main-db"
    cfg.validate()

def test_config_list_option_required(conf: ConfigParser):
    """Tests the 'required' flag on ConfigListOption."""
    cfg = SimpleConfig()
    cfg.load_config(conf, ABSENT_S)
    # Make the ConfigListOption itself required
    cfg.opt_cfgs.required = True

    # Validation should fail if list is empty after init/clear
    #cfg.opt_cfgs.clear()
    assert cfg.opt_cfgs.value == []
    with pytest.raises(Error, match="Missing value for required option 'opt_cfgs'"):
        cfg.validate()

    # Should pass after loading a value
    cfg.load_config(conf, PRESENT_S)
    assert len(cfg.opt_cfgs.value) > 0
    cfg.validate()
