# buffer - Memory buffer manager

## Overview

::: firebird.base.buffer
    options:
        members: false

`MemoryBuffer` starts with a capacity and a position of zero. Writes advance `pos`;
set it back to zero before reading the data you wrote. Number reads and writes use
the selected byte order:

```python
from firebird.base.buffer import MemoryBuffer
from firebird.base.types import ByteOrder

buffer = MemoryBuffer(4, byteorder=ByteOrder.BIG)
buffer.write_short(0x1234)
buffer.write(b"OK")
assert buffer.pos == 4
assert bytes(buffer.get_raw()) == b"\x12\x34OK"

buffer.pos = 0
assert buffer.read_short() == 0x1234
assert bytes(buffer.read(2)) == b"OK"
assert buffer.pos == 4
```

`get_raw()` returns the storage content as bytes or a bytearray regardless of the
chosen buffer factory. A buffer's capacity may exceed the amount of data written,
so use `pos` to track where the next read or write takes place.

## MemoryBuffer

::: firebird.base.buffer.MemoryBuffer

## Buffer factories

::: firebird.base.buffer.BufferFactory

::: firebird.base.buffer.BytesBufferFactory

::: firebird.base.buffer.CTypesBufferFactory

## Functions

::: firebird.base.buffer.safe_ord
