"""Analyze structure of a Netscape 4 .snm mailbox (index + raw RFC822 messages)."""
import sys
from pathlib import Path

path = Path(sys.argv[1])
data = path.read_bytes()

# Message text bytes we consider part of a stored message.
def is_text_byte(b):
    return b in (0x09, 0x0a, 0x0d) or 0x20 <= b <= 0x7e or b >= 0x80

pos = 0
starts = []
while True:
    i = data.find(b"Return-Path:", pos)
    if i < 0:
        break
    starts.append(i)
    pos = i + 1

print(f"size={len(data)} Return-Path count={len(starts)}")

for n, s in enumerate(starts[:5] + starts[-2:]):
    # walk to end of text region
    e = s
    while e < len(data) and is_text_byte(data[e]):
        e += 1
    tail = data[e:e + 32]
    head = data[max(0, s - 16):s]
    print(f"msg@{s} end@{e} len={e - s}")
    print(f"  before: {head!r}")
    print(f"  after : {tail!r}")

# Gap analysis between consecutive messages
print("\ngaps between text regions:")
for a, b in zip(starts, starts[1:]):
    ea = a
    while ea < len(data) and is_text_byte(data[ea]):
        ea += 1
    print(f"  {ea} -> {b}  gap={b - ea}  first16={data[ea:ea + 16]!r}")

# First bytes of file
print(f"\nfile head: {data[:64]!r}")
