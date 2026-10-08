# `firebird.base.buffer`

[Published API](https://firebird-base.readthedocs.io/buffer/index.md)

Use `MemoryBuffer` for cursor based binary I/O. Choose `ByteOrder` explicitly for a wire
format and pair each read with the corresponding write and string encoding. Reads and writes
advance `pos`; reset it before rereading written bytes. Use `get_raw()` for factory independent
storage access. Account for `max_size`, automatic growth, and `eof_marker` when parsing a protocol.

Avoid assuming buffer capacity equals the amount written; track the cursor or protocol length.
Avoid relying on the default byte order or default ASCII encoding for a specified external
format. Do not read past available data or expect a fixed size buffer to grow beyond `max_size`.
