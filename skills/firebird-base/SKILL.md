---
name: firebird-base
description: Use the firebird-base Python library in application code, including its configuration, collections, conversion, callbacks, logging, tracing, buffers, protobuf registry, and value types. Load only the reference for the module involved.
---

# Firebird Base application use

`firebird-base` is a collection of independent modules. Import the needed module from `firebird.base.<module>`;
the package root does not reexport its APIs. Do not add other modules to a solution unless their features are needed.

Choose the relevant reference below and read only that file. If a task crosses module boundaries,
read those references too. Each reference records practical use, likely mistakes, and a link
to its published API documentation.

| Need | Reference |
| --- | --- |
| Errors, sentinels, identities, validated string types | [types](references/types.md) |
| Queryable lists or keyed object registries | [collections](references/collections.md) |
| Bidirectional value/string conversion | [strconv](references/strconv.md) |
| Typed application settings, INI, directories, config protobuf | [config](references/config.md) |
| Binary reads and writes with a cursor | [buffer](references/buffer.md) |
| Source/event callback registry | [hooks](references/hooks.md) |
| Agent/context based standard logging | [logging](references/logging.md) |
| Decorator or runtime method tracing | [trace](references/trace.md) |
| Named protobuf message and enum lookup | [protobuf](references/protobuf.md) |
| Signature checked signals or optional event handlers | [signal](references/signal.md) |

## Documentation and version checks

The published [llms.txt](https://firebird-base.rtfd.io/llms.txt) is the current documentation
index. It links to separate Markdown pages for library modules; use the relevant page for
exact signatures and detailed API behavior. Check the version named in that index against
the installed library before copying examples, especially when working with older releases.

String expressions in collections and executable values in `types`/`config` execute Python
code. Use them only with trusted input. Global registries and managers in `strconv`, `hooks`,
`logging`, `trace`, and `protobuf` affect other users in the same process; isolate changes
in tests and avoid repeated registration during ordinary calls.
