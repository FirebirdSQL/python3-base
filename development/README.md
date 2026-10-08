# Development map

All paths and commands here are relative to the repository root. `firebird-base` is a set
of reusable Python modules, not an application with a central startup path. The package
lives in `src/firebird/base/`; `src/firebird/base/__init__.py` has no public reexports.
Import the needed submodule directly. `__about__.py` holds the version read by Hatch.

## Module relationships

| Module | Role | Main dependencies within this package |
| --- | --- | --- |
| [types](types.md) | Errors, sentinels, identity bases, validated value types | Foundation |
| [collections](collections.md) | Queryable `DataList` and keyed `Registry` | `types` |
| [strconv](strconv.md) | Registry of bidirectional string convertors | `types`, `collections` |
| [protobuf](protobuf.md) | Descriptor and enum registry | `types`, `collections`, Google protobuf |
| [config](config.md) | Typed options, nested configurations, paths, INI and protobuf exchange | `types`, `strconv`, `config_pb2` |
| [buffer](buffer.md) | Binary buffer reads and writes | `types` |
| [hooks](hooks.md) | Event/source callback registry | `types`, `collections` |
| [logging](logging.md) | Context aware standard logging adapters | Standard library logging |
| [trace](trace.md) | Trace decorators, runtime trace configuration | `types`, `collections`, `strconv`, `config`, `logging` |
| [signal](signal.md) | Signature checked signals and event sockets | Standard library inspect and weakref |

The package's runtime dependency is `protobuf~=5.29`. `proto/config.proto` defines the configuration
wire format; its Python module and stub generated using `hatch run build-config-proto` are
in `src/firebird/base/`. The protobuf registry also accepts installed descriptors through
the `firebird.base.protobuf` entry point group. `tests/base_test.proto` and files generated
using `hatch run build-test-proto` provide test fixtures.

## Development workflow

- `pyproject.toml` is the source for Python support (`>=3.11,<4`), Hatch build settings,
  the test matrix (3.11 through 3.14), and Ruff rules. The wheel packages `src/firebird`;
  the sdist includes `src`.
- Use `hatch test` from the repository root for the configured matrix, or `hatch run hatch-test.py3.11:pytest tests/test_buffer.py`
  for a focused module run when that environment exists. Run `hatch run ruff check src/firebird/base`
  for production code and `git diff --check` before finishing.
- Published user documentation is in `docs/docs/`, configured by `docs/zensical.toml`;
  `hatch run doc:build` builds it. Command `hatch run doc:docset` generates Dash/Zeal docset
  distribution in `dist/` directory. `development/` is for architecture, module boundaries,
  and maintenance information.
- Tests mirror modules under `tests/test_*.py`; `config` has one file per option or feature
  under `tests/config/`. Some modules hold global registries or managers, so tests that mutate
  them must reset their state.
- Treat `proto/config.proto` and its generated outputs as one change. Preserve protobuf
  field numbers and meanings when evolving the format. Regenerate bindings with a compatible
  protobuf compiler rather than editing generated output by hand.

The module documents below describe implementation boundaries and change points. For public
API usage, consult the source docstrings and `docs/docs/<module>.md`.
