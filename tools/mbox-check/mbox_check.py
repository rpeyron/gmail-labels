#!/usr/bin/env python3
"""Check the structure of an mbox/sbd mail store and the coherence of its messages."""

from __future__ import annotations

import argparse
import codecs
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path


IGNORED_SUFFIXES = {".msf", ".html", ".log", ".dat", ".json", ".zip", ".7z"}
TEXT_ASCII = frozenset({9, 10, 13}) | frozenset(range(32, 127))
CONTROL_PATTERN = re.compile(rb"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
ENVELOPE = re.compile(
    rb"^From \S+ \w{3} \w{3} +\d+ \d{2}:\d{2}:\d{2} \d{4}$"
)
BINARY_SIGNATURES = (
    (b"PK\x03\x04", "ZIP archive"),
    (b"\x1f\x8b\x08", "gzip stream"),
    (b"BZh9", "bzip2 stream"),
    (b"\xfd7zXZ", "xz stream"),
    (b"\x89PNG", "PNG image"),
    (b"GIF8", "GIF image"),
    (b"\xff\xd8\xff", "JPEG image"),
    (b"%PDF", "PDF document"),
    (b"Rar!\x1a\x07", "RAR archive"),
    (b"7z\xbc\xaf\x27\x1c", "7z archive"),
    (b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1", "OLE2 document"),
    (b"\x25\x21PS", "PostScript document"),
)
TRANSFER_ENCODINGS = re.compile(
    rb"^content-transfer-encoding\s*:\s*([A-Za-z0-9-]+)", re.IGNORECASE | re.MULTILINE
)
BOUNDARY = re.compile(
    rb"boundary\s*=\s*\"?([^\";\r\n]+)", re.IGNORECASE
)
EXAMPLES_PER_KIND = 20


@dataclass
class Problem:
    """One problem found in the mail store."""

    path: Path
    kind: str
    detail: str
    message_number: int | None = None
    offset: int | None = None

    def location(self) -> str:
        parts = [str(self.path)]
        if self.message_number is not None:
            parts.append(f"message {self.message_number}")
        if self.offset is not None:
            parts.append(f"offset {self.offset}")
        return " ".join(parts)


@dataclass
class Report:
    """The problems found in a mail store, grouped by kind."""

    problems: list[Problem] = field(default_factory=list)
    mailboxes: int = 0
    messages: int = 0
    bytes_scanned: int = 0

    def add(self, problem: Problem) -> None:
        self.problems.append(problem)

    def by_kind(self) -> dict[str, list[Problem]]:
        grouped: dict[str, list[Problem]] = {}
        for problem in self.problems:
            grouped.setdefault(problem.kind, []).append(problem)
        return grouped

    def counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for problem in self.problems:
            counts[problem.kind] = counts.get(problem.kind, 0) + 1
        return counts


def is_mbox(path: Path) -> bool:
    """Return True when the file starts with an mbox envelope line."""
    try:
        with path.open("rb") as stream:
            first = stream.readline()
    except OSError:
        return False
    return first.startswith(b"From ") and bool(ENVELOPE.match(first.rstrip(b"\r\n")))


def iter_mailboxes(root: Path) -> list[Path]:
    """Return the files of the tree that are not indexes or side files."""
    files: list[Path] = []
    for directory, _subdirectories, filenames in os.walk(root):
        folder = Path(directory)
        for filename in sorted(filenames):
            path = folder / filename
            if path.suffix.lower() in IGNORED_SUFFIXES:
                continue
            files.append(path)
    return files


def split_messages(blob: bytes) -> list[tuple[int, int]]:
    """Return the (start, end) offsets of the messages of an mbox."""
    starts = [0]
    offset = 0
    while True:
        index = blob.find(b"\nFrom ", offset)
        if index < 0:
            break
        starts.append(index + 1)
        offset = index + 1
    starts.append(len(blob))
    return [
        (starts[number], starts[number + 1])
        for number in range(len(starts) - 1)
        if starts[number] < starts[number + 1]
    ]


def _character_start(data: bytes, end: int) -> int | None:
    """Return the start offset of the UTF-8 character that ends at ``end``."""
    for length in (2, 3, 4):
        start = end - length
        if start < 0:
            continue
        lead = data[start]
        if lead & 0xC0 != 0xC0:
            continue
        if any(data[start + offset] & 0xC0 != 0x80 for offset in range(1, length)):
            continue
        return start
    return None


def trailing_padding(data: bytes, charset: str | None = None) -> tuple[int, int]:
    """Return the (offset, length) of the trailing run of non-text bytes.

    A byte is text when it is a printable ASCII character, a tab or a line
    break, or part of a printable character of the declared charset.
    Anything else at the end of a message is padding: NUL bytes, a
    repeated filler byte, or a truncated binary blob. The line breaks that
    close the message are not part of the padding.
    """
    end = len(data)
    while end > 0 and data[end - 1] in (9, 10, 13, 32):
        end -= 1
    # The padding sits between the last text and the line breaks that close
    # the message, so it is found by walking back from the text.
    text_end = end
    while text_end > 0:
        byte = data[text_end - 1]
        if byte < 0x80:
            if byte in TEXT_ASCII:
                break
            text_end -= 1
            continue
        if charset is not None and _is_printable_in(byte, charset):
            break
        start = _character_start(data, text_end)
        if start is None:
            text_end -= 1
            continue
        try:
            character = data[start:text_end].decode("utf-8")
        except UnicodeDecodeError:
            text_end -= 1
            continue
        if character.isprintable():
            break
        text_end = start
    return text_end, end - text_end


def _is_printable_in(byte: int, charset: str) -> bool:
    """Return True when the byte is a printable character of the charset."""
    try:
        character = bytes([byte]).decode(charset)
    except (UnicodeDecodeError, LookupError):
        return False
    return character.isprintable()


def check_tree(root: Path) -> Report:
    """Check the mail store and return what was found."""
    report = Report()
    for path in iter_mailboxes(root):
        if path.is_dir():
            continue
        if path.stat().st_size == 0:
            continue
        blob = path.read_bytes()
        report.bytes_scanned += len(blob)
        if not blob.startswith(b"From "):
            report.add(
                Problem(
                    path,
                    "not-an-mbox",
                    "file does not start with a 'From ' line",
                )
            )
            continue
        report.mailboxes += 1
        check_mailbox(path, blob, report)
    check_layout(root, report)
    return report


def check_layout(root: Path, report: Report) -> None:
    """Check that the folders and the indexes of the tree match."""
    for directory, _subdirectories, filenames in os.walk(root):
        folder = Path(directory)
        for filename in sorted(filenames):
            path = folder / filename
            if path.suffix.lower() != ".msf":
                continue
            if not path.with_suffix("").exists():
                report.add(
                    Problem(
                        path,
                        "index-without-mailbox",
                        "index has no matching mbox file",
                    )
                )
        if folder == root:
            continue
        if folder.name.endswith(".sbd") and not folder.with_suffix("").exists():
            report.add(
                Problem(
                    folder,
                    "folder-without-mailbox",
                    "sub-folder has no matching mbox file",
                )
            )


def check_mailbox(path: Path, blob: bytes, report: Report) -> None:
    """Check the messages of one mbox."""
    for number, (start, end) in enumerate(split_messages(blob), start=1):
        report.messages += 1
        check_message(path, number, start, blob[start:end], report)


CHARSET = re.compile(
    rb"charset\s*=\s*\"?([A-Za-z0-9._-]+)", re.IGNORECASE
)


def _charset_of(headers: bytes) -> str | None:
    """Return the charset declared by the headers of a message."""
    match = CHARSET.search(headers)
    if match is None:
        return None
    charset = match.group(1).decode("ascii", "replace")
    try:
        codecs.lookup(charset)
    except LookupError:
        return None
    return charset


def _split_headers(message: bytes) -> tuple[bytes, bytes, bool]:
    """Split a message into its headers and its body.

    The empty line that separates them may end with a line feed alone or
    with a carriage return and a line feed. The third value tells whether
    that empty line was found.
    """
    index = message.find(b"\n\n")
    if index >= 0:
        return message[:index], message[index + 2 :], True
    index = message.find(b"\r\n\r\n")
    if index >= 0:
        return message[:index], message[index + 4 :], True
    return message, b"", False


def check_message(
    path: Path,
    number: int,
    start: int,
    message: bytes,
    report: Report,
) -> None:
    """Check one message of an mbox."""
    headers, body, separated = _split_headers(message)
    if not separated and not headers.endswith((b"\n", b"\r")):
        report.add(
            Problem(
                path,
                "no-header-body-separator",
                "message has no empty line between its headers and its body",
                number,
            )
        )

    check_headers(path, number, start, headers, report)
    check_body(path, number, start, headers, body, report)
    check_padding(path, number, start, body, _charset_of(headers), report)


def check_headers(
    path: Path,
    number: int,
    start: int,
    headers: bytes,
    report: Report,
) -> None:
    """Check the headers of a message."""
    for line in headers.split(b"\n"):
        line = line.rstrip(b"\r")
        if not line or line[:1] in (b" ", b"\t"):
            continue  # folded continuation of the previous header
        match = CONTROL_PATTERN.search(line)
        if match is not None:
            report.add(
                Problem(
                    path,
                    "control-byte-in-header",
                    f"header line holds the control byte {match.group()!r}",
                    number,
                    start,
                )
            )
            return


def _split_chunks(headers: bytes, body: bytes) -> list[tuple[bytes, bytes]]:
    """Split a body into the (headers, payload) of each MIME part."""
    match = BOUNDARY.search(headers)
    if match is None:
        return [(headers, body)]
    boundary = b"--" + match.group(1).strip()
    chunks: list[tuple[bytes, bytes]] = []
    for piece in body.split(boundary):
        if not piece.strip():
            continue
        separator = piece.find(b"\n\n")
        if separator < 0:
            chunks.append((piece, b""))
            continue
        chunks.append((piece[:separator], piece[separator + 2 :]))
    return chunks


def check_body(
    path: Path,
    number: int,
    start: int,
    headers: bytes,
    body: bytes,
    report: Report,
) -> None:
    """Check the body of a message, part by part."""
    if not body:
        return
    for chunk_headers, payload in _split_chunks(headers, body):
        if not payload:
            continue
        encoding = TRANSFER_ENCODINGS.search(chunk_headers)
        if encoding is not None:
            # An encoded part must stay 7-bit clean whatever the encoding.
            match = CONTROL_PATTERN.search(payload)
            if match is not None:
                report.add(
                    Problem(
                        path,
                        "control-byte-in-body",
                        f"part declares {encoding.group(1).decode('ascii', 'replace')} "
                        f"but holds the control byte {match.group()!r}",
                        number,
                        start,
                    )
                )
            continue
        for signature, name in BINARY_SIGNATURES:
            if payload.startswith(signature):
                report.add(
                    Problem(
                        path,
                        "binary-in-body",
                        f"body holds a {name} that has no MIME part",
                        number,
                        start,
                    )
                )
                break
        else:
            control = sum(
                1 for byte in payload if byte < 32 and byte not in (9, 10, 13)
            )
            if control and control / len(payload) > 0.02:
                report.add(
                    Problem(
                        path,
                        "binary-in-body",
                        f"body holds {control} control byte(s) without a MIME part",
                        number,
                        start,
                    )
                )


def check_padding(
    path: Path,
    number: int,
    start: int,
    body: bytes,
    charset: str | None,
    report: Report,
) -> None:
    """Check that a message does not end with binary padding."""
    offset, length = trailing_padding(body, charset)
    if not length:
        return
    filler = body[offset : offset + min(length, 16)]
    report.add(
        Problem(
            path,
            "binary-padding",
            f"message ends with {length} byte(s) of binary padding "
            f"({filler!r})",
            number,
            start + offset,
        )
    )


def strip_padding(blob: bytes) -> tuple[bytes, int]:
    """Remove the binary padding of the messages of an mbox.

    Returns the new content and the number of bytes removed.
    """
    result = bytearray()
    removed = 0
    for start, end in split_messages(blob):
        message = blob[start:end]
        headers, body, separated = _split_headers(message)
        if not separated or not body:
            result += message
            continue
        offset, length = trailing_padding(body, _charset_of(headers))
        if length:
            body = body[:offset] + body[offset + length :]
            removed += length
        result += headers + _separator_of(message) + body
    return bytes(result), removed


def _separator_of(message: bytes) -> bytes:
    """Return the empty line that separates the headers of a message."""
    index = message.find(b"\n\n")
    if index >= 0:
        return b"\n\n"
    index = message.find(b"\r\n\r\n")
    if index >= 0:
        return b"\r\n\r\n"
    return b""


def clean_file(path: Path) -> int:
    """Remove the binary padding of one mbox and return the bytes removed."""
    blob = path.read_bytes()
    cleaned, removed = strip_padding(blob)
    if removed:
        path.write_bytes(cleaned)
    return removed


def format_report(report: Report) -> list[str]:
    """Return the lines of the report."""
    lines = [
        f"Checked {report.mailboxes} mailbox(es), {report.messages} message(s), "
        f"{report.bytes_scanned} byte(s)."
    ]
    grouped = report.by_kind()
    if not grouped:
        lines.append("No problem found.")
        return lines
    for kind in sorted(grouped):
        entries = grouped[kind]
        lines.append("")
        lines.append(f"{kind} ({len(entries)}):")
        for problem in entries[:EXAMPLES_PER_KIND]:
            lines.append(f"  {problem.location()} {problem.detail}")
        if len(entries) > EXAMPLES_PER_KIND:
            lines.append(f"  ... and {len(entries) - EXAMPLES_PER_KIND} more")
    lines.append("")
    counts = report.counts()
    lines.append(
        f"Found {len(report.problems)} problem(s): "
        + ", ".join(f"{kind}={count}" for kind, count in sorted(counts.items()))
    )
    return lines


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("root", type=Path, help="mbox/sbd directory to check")
    parser.add_argument(
        "--clean",
        action="store_true",
        help="remove the binary padding of the messages (--dry-run by default)",
    )
    parser.add_argument(
        "--in-place",
        action="store_true",
        help="with --clean, write the cleaned mailboxes to disk",
    )
    args = parser.parse_args(argv)

    if not args.root.is_dir():
        parser.error(f"not a directory: {args.root}")
    if args.in_place and not args.clean:
        parser.error("--in-place requires --clean")

    if args.clean:
        removed = 0
        cleaned_files = 0
        for path in iter_mailboxes(args.root):
            if path.is_dir() or not is_mbox(path):
                continue
            blob = path.read_bytes()
            if args.in_place:
                count = clean_file(path)
            else:
                _, count = strip_padding(blob)
            if count:
                removed += count
                cleaned_files += 1
                print(f"{count} byte(s) of padding in {path}")
        verb = "removed" if args.in_place else "would remove"
        print(f"{verb} {removed} byte(s) in {cleaned_files} mailbox(es)")

    report = check_tree(args.root)
    for line in format_report(report):
        print(line)
    return 1 if report.problems else 0


if __name__ == "__main__":
    sys.exit(main())
