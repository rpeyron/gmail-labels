#!/usr/bin/env python3
"""Remove empty mbox files (and their indexes) from an mbox/sbd mail-store."""

# python .\clean_empty_mbox.py --dry-run "C:\Users\me\AppData\Roaming\Thunderbird\Profiles\xxx\Mail\Local Folders"

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


def clean_tree(root: Path, dry_run: bool = False) -> list[Path]:
    """Delete empty mboxes, their .msf, and emptied .sbd folders (deepest first)."""
    removed: list[Path] = []

    # Deepest-first so a subfolder emptied now lets its parent .sbd go too.
    for directory, _subdirectories, filenames in os.walk(root, topdown=False):
        folder = Path(directory)

        for filename in filenames:
            mailbox = folder / filename
            if mailbox.suffix or mailbox.stat().st_size != 0:
                continue
            subfolders = folder / f"{mailbox.name}.sbd"
            if subfolders.is_dir() and any(subfolders.iterdir()):
                continue  # empty parent folder must stay while it has children
            if not dry_run:
                mailbox.unlink()
                index = mailbox.with_suffix(".msf")
                if index.exists():
                    index.unlink()
            removed.append(mailbox)

        if folder != root and folder.name.endswith(".sbd") and not any(folder.iterdir()):
            if not dry_run:
                folder.rmdir()
            removed.append(folder)

    return removed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("root", type=Path, help="mbox/sbd directory to clean")
    parser.add_argument("-n", "--dry-run", action="store_true", help="only list what would be removed")
    args = parser.parse_args(argv)

    if not args.root.is_dir():
        parser.error(f"not a directory: {args.root}")

    removed = clean_tree(args.root, dry_run=args.dry_run)
    prefix = "would remove" if args.dry_run else "removed"
    for path in removed:
        print(f"{prefix} {path}")
    print(f"{prefix} {len(removed)} path(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
