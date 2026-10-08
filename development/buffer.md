# `firebird.base.buffer`

Source: `src/firebird/base/buffer.py`. Tests: `tests/test_buffer.py`.

`MemoryBuffer` is a cursor over mutable raw storage. `BufferFactory` defines allocation,
clearing, and raw access; `BytesBufferFactory` uses `bytearray`, and `CTypesBufferFactory`
uses a ctypes buffer. Call `get_raw()` for factory-independent access. `pos`, `byteorder`,
`max_size`, and optional `eof_marker` control reads and writes.

The API handles raw bytes, fixed width integers, strings, Pascal strings, and sized strings;
reads and writes advance `pos`. Writes may resize the buffer unless `max_size` forbids it.
Reads check available space; `is_eof()` also honors the marker. When changing encoding or
length prefixes, test both factories, both byte orders where relevant, position movement,
truncation, and size limits. `ByteOrder` and `UNLIMITED` come from `types`.
