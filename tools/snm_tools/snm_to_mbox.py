"""Convert a Netscape 4 .snm mailbox to mbox.

.snm layout: binary index, then raw RFC822 messages separated by
short runs of NUL bytes (plus one larger index block). Messages may
quote "Return-Path:" inside bodies, so nested hits are skipped.
"""
import re
import sys
from email.utils import parsedate_to_datetime
from pathlib import Path


def is_text_byte(b: int) -> bool:
    return b in (0x09, 0x0A, 0x0D) or 0x20 <= b <= 0x7E or b >= 0x80


def extract_messages(data: bytes) -> list[bytes]:
    starts = []
    pos = 0
    while True:
        i = data.find(b"Return-Path:", pos)
        if i < 0:
            break
        starts.append(i)
        pos = i + 1

    messages = []
    covered_until = 0
    for s in starts:
        if s < covered_until:  # Return-Path quoted inside a previous body
            continue
        e = s
        while e < len(data) and is_text_byte(data[e]):
            e += 1
        # trim trailing NULs / stray CR
        block = data[s:e].rstrip(b"\x00\r\n\t ")
        if block:
            messages.append(block + b"\n")
        covered_until = e
    return messages


def to_mbox_message(raw: bytes) -> bytes:
    # normalize line endings to LF
    raw = raw.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    if not raw.endswith(b"\n"):
        raw += b"\n"
    # mboxrd-escape body lines that begin with "From "
    out_lines = []
    for line in raw.split(b"\n")[:-1]:
        if line.startswith(b"From "):
            line = b">" + line
        out_lines.append(line)
    body = b"\n".join(out_lines) + b"\n"

    date = None
    m = re.search(rb"(?im)^Date:[ \t]*(.+)$", body)
    if m:
        try:
            date = parsedate_to_datetime(m.group(1).decode("latin-1"))
        except (ValueError, TypeError):
            date = None
    days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
              "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    if date is None:
        from_line = b"From MAILER-DAEMON Sat Jan  1 00:00:00 2000\n"
    else:
        dstr = "%s %s %2d %02d:%02d:%02d %d" % (
            days[date.weekday()], months[date.month - 1], date.day,
            date.hour, date.minute, date.second, date.year)
        from_line = f"From MAILER-DAEMON {dstr}\n".encode("ascii")
    return from_line + body + b"\n"


def convert(snm_path: Path, mbox_path: Path) -> int:
    data = snm_path.read_bytes()
    messages = extract_messages(data)
    with mbox_path.open("wb") as f:
        for msg in messages:
            f.write(to_mbox_message(msg))
    return len(messages)


def main():
    snm = Path(sys.argv[1])
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else snm.with_suffix(".mbox")
    n = convert(snm, out)
    print(f"{n} messages -> {out}")


if __name__ == "__main__":
    main()
