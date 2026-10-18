#!/usr/bin/env python3
"""Diff two mails.json synthesis files by Message-ID.

Usage: python json-mbox-diff.py <fileA.json> <fileB.json>
Writes data/diff-<A>-vs-<B>.json with diff_status:
  only-A / only-B (matched on message_id, <> and whitespace normalized;
  empty/placeholder mids like "", "   ", "null" treated as missing;
  duplicates of a message_id absent from the other file are all kept here)
  both (normalized message_id present in both files — every occurrence is
  classified both, whatever the number of duplicates on each side)
  both_no_mid (unmatched by mid, matched on subject+date+from when at least
  one side has no message_id)
"""
import json
import os
import sys
from collections import Counter, defaultdict

OUT_DIR = "data"


def load(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def norm_mid(m):
    """Return normalized message_id, or "" if empty/placeholder/near-empty."""
    raw = m.get("message_id")
    if not isinstance(raw, str):
        return ""
    s = raw.strip().strip("<>").strip()
    if s.lower() in ("", "none", "null", "n/a", "na", "-"):
        return ""
    return s


def fallback_key(m):
    return (m.get("subject") or "", m.get("date") or "", m.get("from") or "")


def main():
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(1)

    path_a, path_b = sys.argv[1], sys.argv[2]
    a = load(path_a)
    b = load(path_b)

    a_mid = [norm_mid(m) for m in a]
    b_mid = [norm_mid(m) for m in b]

    status_a = ["only-A"] * len(a)
    status_b = ["only-B"] * len(b)

    # Pass 1: match on message_id
    ids_a = {mid for mid in a_mid if mid}
    ids_b = {mid for mid in b_mid if mid}

    for i, mid in enumerate(a_mid):
        if mid and mid in ids_b:
            status_a[i] = "both"
    for j, mid in enumerate(b_mid):
        if mid and mid in ids_a:
            status_b[j] = "skip"  # already represented by its A twin

    # Pass 2: fallback on subject+date+from for still-unmatched items,
    # only when at least one side of the pair has no message_id
    a_no = defaultdict(list)
    a_has = defaultdict(list)
    b_no = defaultdict(list)
    b_has = defaultdict(list)

    for i, m in enumerate(a):
        if status_a[i] != "only-A":
            continue
        (a_no if not a_mid[i] else a_has)[fallback_key(m)].append(i)
    for j, m in enumerate(b):
        if status_b[j] != "only-B":
            continue
        (b_no if not b_mid[j] else b_has)[fallback_key(m)].append(j)

    def pair(k):
        # no-mid A with no-mid B, then cross with has-mid on either side
        for la, lb in ((a_no[k], b_no[k]), (a_no[k], b_has[k]), (a_has[k], b_no[k])):
            n = min(len(la), len(lb))
            for _ in range(n):
                ai = la.pop()
                bi = lb.pop()
                status_a[ai] = "both_no_mid"
                status_b[bi] = "skip"

    for k in set(a_no) | set(a_has) | set(b_no) | set(b_has):
        pair(k)

    records = []
    for m, s in zip(a, status_a):
        records.append({**m, "diff_status": s})
    for m, s, mid in zip(b, status_b, b_mid):
        if s == "skip":
            # pass-1 skip: mid present in A too → common, keep every occurrence
            # (pass-2 skip = both_no_mid twin, already represented by its A record)
            if mid and mid in ids_a:
                records.append({**m, "diff_status": "both"})
            continue
        records.append({**m, "diff_status": s})

    name_a = os.path.splitext(os.path.basename(path_a))[0]
    name_b = os.path.splitext(os.path.basename(path_b))[0]
    out = os.path.join(OUT_DIR, f"diff-{name_a}-vs-{name_b}.json")

    os.makedirs(OUT_DIR, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False)

    counts = Counter(r["diff_status"] for r in records)
    print(f"Écrit : {out}")
    print(f"  communs : {counts['both']} | communs sans mid : {counts['both_no_mid']}"
          f" | seulement A : {counts['only-A']} | seulement B : {counts['only-B']}")


if __name__ == "__main__":
    main()
