# Agent guidance

This repository is the `firebird-base` Python library, a collection of modules under `src/firebird/base/`.
Work from the repository root when using the paths and commands below.

Read [development/README.md](development/README.md) for the package map, dependencies,
build and test workflow. Before changing a module, read its matching `development/<module>.md`
file and update that file when its architecture or maintenance contract changes. The module
files are the development reference; `docs/docs/` contains published user documentation.

## Working rules

- Keep changes scoped to the affected module and its tests. This library is shared by other
  Firebird Python projects, so preserve public signatures and serialization formats unless
  the task explicitly changes them.
- Add or adjust tests in `tests/test_<module>.py`; configuration option tests belong in
  `tests/config/`. Exercise both normal behavior and relevant failure paths.
- Do not hand edit generated `src/firebird/base/config_pb2.py`, `src/firebird/base/config_pb2.pyi`,
  or `tests/base_test_pb2.*`. Update the corresponding `.proto` source and regenerate the artifacts
  if the schema changes.
- Run focused tests first, then `hatch test` for the configured Python matrix when available.
  Run `hatch run ruff check src/firebird/base` and `git diff --check` for code changes.
  Report any unavailable environment or pre-existing failure separately.
- Follow `pyproject.toml` for Python support, dependency versions, Ruff settings, and Hatch
  environments. Preserve the existing module style and license headers.

## Module references

- [types](development/types.md)
- [collections](development/collections.md)
- [strconv](development/strconv.md)
- [config](development/config.md)
- [buffer](development/buffer.md)
- [hooks](development/hooks.md)
- [logging](development/logging.md)
- [trace](development/trace.md)
- [protobuf](development/protobuf.md)
- [signal](development/signal.md)
