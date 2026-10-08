# firebird-base

## Firebird base modules for Python

[![PyPI - Version](https://img.shields.io/pypi/v/firebird-base.svg)](https://pypi.org/project/firebird-base)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/firebird-base.svg)](https://pypi.org/project/firebird-base)
[![Hatch project](https://img.shields.io/badge/%F0%9F%A5%9A-Hatch-4051b5.svg)](https://github.com/pypa/hatch)
[![PyPI - Downloads](https://img.shields.io/pypi/dm/firebird-base)](https://pypi.org/project/firebird-base)
[![Libraries.io SourceRank](https://img.shields.io/librariesio/sourcerank/pypi/firebird-base)](https://libraries.io/pypi/firebird-base)
[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/FirebirdSQL/python3-base)

`firebird-base` provides reusable Python modules used by the [Firebird Project](https://github.com/FirebirdSQL)
and other applications. The modules can be used independently of the Firebird database.

## Installation

Requires Python `>=3.11,<4`.

```console
pip install firebird-base
```

Import the submodules you need, for example `import firebird.base.config`.

## Documentation

For module guides and API details, see the [firebird-base documentation](https://firebird-base.rtfd.io/).

## Agent skill

The [firebird-base skill](skills/firebird-base/SKILL.md) provides guidance for using individual
modules. Copy or link its entire `skills/firebird-base` directory from this repository into
the skill directory used by your coding agent:

| Agent | User skill directory |
| --- | --- |
| [Codex](https://learn.chatgpt.com/docs/build-skills) | `~/.codex/skills/` |
| [Claude Code](https://code.claude.com/docs/en/skills) | `~/.claude/skills/` |
| [Gemini CLI](https://geminicli.com/docs/cli/using-agent-skills/) | `~/.agents/skills/` (also supports `~/.gemini/skills/`) |

## Development

For the package map, dependencies, build and test workflow, and module maintenance notes,
see [development/README.md](development/README.md) and the other files in [`development/`](development/).

## License

`firebird-base` is distributed under the terms of the [MIT](https://spdx.org/licenses/MIT.html) license.
