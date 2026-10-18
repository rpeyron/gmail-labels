#!/usr/bin/env python3
"""Merge Thunderbird mail-store trees while preserving their folder layout."""

# python .\merge_thunderbird.py --output .\MailsRecover-merged .\MailsRecover\*


from __future__ import annotations

import argparse
import glob
import shutil
import sys
from collections import defaultdict
from pathlib import Path


IGNORED_SUFFIXES = {".html", ".log", ".msf"}
COPY_BUFFER_SIZE = 1024 * 1024


def is_mbox(path: Path) -> bool:
    """Recognize an mbox by its first separator line; empty files are valid."""
    with path.open("rb") as mailbox:
        first_line = mailbox.readline()
    return not first_line or first_line.startswith(b"From ")


def iter_tree(root: Path) -> tuple[set[Path], dict[Path, list[Path]]]:
    directories: set[Path] = set()
    files: dict[Path, list[Path]] = defaultdict(list)

    for path in root.rglob("*"):
        relative_path = path.relative_to(root)
        if path.is_dir():
            directories.add(relative_path)
        elif path.is_file() and path.suffix.lower() not in IGNORED_SUFFIXES:
            files[relative_path].append(path)

    return directories, files


def validate_paths(inputs: list[Path], output: Path) -> None:
    resolved_inputs = [path.resolve() for path in inputs]
    resolved_output = output.resolve()

    if len(set(resolved_inputs)) != len(resolved_inputs):
        raise ValueError("The same source directory was specified more than once.")

    for index, source in enumerate(resolved_inputs):
        if not source.is_dir():
            raise ValueError(f"Source directory does not exist: {source}")
        if resolved_output == source or source in resolved_output.parents:
            raise ValueError(
                f"Output directory cannot be inside a source directory: {source}"
            )
        if any(
            source in other.parents or other in source.parents
            for other in resolved_inputs[index + 1 :]
        ):
            raise ValueError("Source directories must not overlap.")

    if resolved_output.exists() and (
        not resolved_output.is_dir() or any(resolved_output.iterdir())
    ):
        raise ValueError("Output directory must be absent or empty.")


def expand_input_patterns(inputs: list[Path]) -> list[Path]:
    expanded: list[Path] = []
    for pattern in inputs:
        matches = sorted(Path(match) for match in glob.glob(str(pattern)))
        if glob.has_magic(str(pattern)):
            matches = [match for match in matches if match.is_dir()]
        if not matches:
            raise ValueError(f"No source directories matched input pattern: {pattern}")
        expanded.extend(matches)
    return expanded


def copy_file(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def merge_mboxes(sources: list[Path], destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w+b") as merged:
        for source in sources:
            if source.stat().st_size == 0:
                continue
            with source.open("rb") as mailbox:
                if merged.tell():
                    merged.seek(-1, 2)
                    needs_newline = merged.read(1) != b"\n"
                    merged.seek(0, 2)
                    if needs_newline:
                        merged.write(b"\n")
                shutil.copyfileobj(mailbox, merged, COPY_BUFFER_SIZE)

    shutil.copystat(sources[0], destination)


def merge_trees(inputs: list[Path], output: Path) -> None:
    validate_paths(inputs, output)
    trees = [iter_tree(root) for root in inputs]
    all_directories = set().union(*(directories for directories, _ in trees))
    files_by_path: dict[Path, list[Path]] = defaultdict(list)
    for _, files in trees:
        for relative_path, sources in files.items():
            files_by_path[relative_path].extend(sources)

    conflicts = sorted(
        (path for path in files_by_path if path in all_directories),
        key=str,
    )
    if conflicts:
        paths = ", ".join(str(path) for path in conflicts)
        raise ValueError(f"File/directory conflict in source trees: {paths}")

    actions: list[tuple[Path, list[Path], bool]] = []
    for relative_path, sources in sorted(
        files_by_path.items(), key=lambda item: str(item[0])
    ):
        classified_sources = [(source, is_mbox(source)) for source in sources]
        mailbox_sources = [
            source for source, mailbox in classified_sources if mailbox
        ]
        non_mailbox_sources = [
            source for source, mailbox in classified_sources if not mailbox
        ]

        if mailbox_sources and non_mailbox_sources:
            raise ValueError(
                f"Different file types at the same path: {relative_path}"
            )
        if mailbox_sources:
            actions.append((relative_path, mailbox_sources, True))
        else:
            first = non_mailbox_sources[0]
            if any(
                not file_contents_equal(first, source)
                for source in non_mailbox_sources[1:]
            ):
                raise ValueError(
                    f"Different auxiliary files at the same path: {relative_path}"
                )
            actions.append((relative_path, [first], False))

    for relative_path in sorted(
        all_directories, key=lambda path: (len(path.parts), str(path))
    ):
        (output / relative_path).mkdir(parents=True, exist_ok=True)

    for relative_path, sources, is_mailbox in actions:
        destination = output / relative_path
        if is_mailbox:
            merge_mboxes(sources, destination)
        else:
            copy_file(sources[0], destination)


def file_contents_equal(first: Path, second: Path) -> bool:
    with first.open("rb") as left, second.open("rb") as right:
        while True:
            left_chunk = left.read(COPY_BUFFER_SIZE)
            right_chunk = right.read(COPY_BUFFER_SIZE)
            if left_chunk != right_chunk:
                return False
            if not left_chunk:
                return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Merge multiple Thunderbird mail trees. "
            "Mbox files with the same relative path are concatenated."
        ),
        epilog=(
            "Files with .msf, .html, and .log suffixes are ignored. "
            "Sources must be distinct, and the output directory must be absent or empty."
        ),
    )
    parser.add_argument(
        "-o",
        "--output",
        required=True,
        type=Path,
        help="destination directory",
    )
    parser.add_argument(
        "inputs",
        nargs="+",
        type=Path,
        help="Thunderbird root directories to merge",
    )
    arguments = parser.parse_args(argv)

    try:
        merge_trees(expand_input_patterns(arguments.inputs), arguments.output)
    except (OSError, ValueError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
