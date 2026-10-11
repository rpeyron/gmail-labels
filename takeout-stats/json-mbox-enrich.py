#!/usr/bin/env python3
"""Add/refresh mid_dup and mid_invalid fields on existing mails.json files.

Usage: python json-mbox-enrich.py data/*.json

mid_dup:       message_id if it appears more than once in the file, else ""
mid_invalid:   reason if message_id violates RFC 5322 msg-id syntax, else ""
               reasons: missing_angles / no_at_sign / bad_chars
               (absent message_id stays "" — header is optional, not invalid)
"""
import json
import re
import sys
from collections import Counter


def mid_invalid(raw):
    if not isinstance(raw, str) or not raw.strip():
        return ""
    s = raw.strip()
    if not (s.startswith("<") and s.endswith(">")):
        return "missing_angles"
    inner = s[1:-1]
    if "@" not in inner:
        return "no_at_sign"
    if not re.fullmatch(r"[^<>\s@]+@[^<>\s@]+", inner):
        return "bad_chars"
    return ""


def enrich(records):
    counts = Counter(r.get("message_id") for r in records if r.get("message_id"))
    for r in records:
        mid = r.get("message_id")
        r["mid_dup"] = mid if mid and counts[mid] > 1 else ""
        r["mid_invalid"] = mid_invalid(mid)
    return records


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    for path in sys.argv[1:]:
        with open(path, "r", encoding="utf-8") as f:
            records = json.load(f)
        enrich(records)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(records, f, ensure_ascii=False)
        d = sum(1 for r in records if r["mid_dup"])
        n = sum(1 for r in records if r["mid_invalid"])
        print(f"{path}: {len(records)} mails, mid_dup={d}, mid_invalid={n}")


if __name__ == "__main__":
    main()
