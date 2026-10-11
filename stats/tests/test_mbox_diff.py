#!/usr/bin/env python3
"""Self-check for json-mbox-diff matching logic. Run: python test_mbox_diff.py"""
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))

A = [
    {"message_id": "m1", "subject": "S1", "date": "2020-01-01", "from": "a@x"},
    {"message_id": "", "subject": "S2", "date": "2020-02-02", "from": "b@x"},
    {"message_id": "", "subject": "S3", "date": "2020-03-03", "from": "c@x"},
    {"message_id": "m4", "subject": "S4", "date": "2020-04-04", "from": "d@x"},
    {"message_id": "", "subject": "S5", "date": "2020-05-05", "from": "e@x"},
    {"message_id": "   ", "subject": "S6", "date": "2020-06-06", "from": "f@x"},  # near-empty mid
    {"message_id": "", "subject": "S7", "date": "2020-07-07", "from": "g@x"},   # both_no_mid (B has mid)
    {"message_id": "<m8@x>", "subject": "S8", "date": "2020-08-08", "from": "h@x"},
    {"message_id": "m1", "subject": "S1dup", "date": "2020-01-01", "from": "a@x"},  # dup mid, skipped
]
B = [
    {"message_id": "m1", "subject": "S1", "date": "2020-01-01", "from": "a@x"},
    {"message_id": "", "subject": "S2", "date": "2020-02-02", "from": "b@x"},   # both_no_mid
    {"message_id": "m9", "subject": "S9", "date": "2020-09-09", "from": "z@x"},  # only-B
    {"message_id": "", "subject": "S5", "date": "2020-05-05", "from": "e@x"},   # both_no_mid
    {"message_id": "", "subject": "S5", "date": "2020-05-05", "from": "e@x"},   # only-B (duplicate)
    {"message_id": "", "subject": "S6", "date": "2020-06-06", "from": "f@x"},   # both_no_mid (near-empty A mid)
    {"message_id": "m7", "subject": "S7", "date": "2020-07-07", "from": "g@x"}, # both_no_mid (A has no mid)
    {"message_id": "m8@x", "subject": "S8", "date": "2020-08-08", "from": "h@x"},  # both (<> stripped)
    {"message_id": "m9", "subject": "S9dup", "date": "2020-09-09", "from": "z@x"},  # dup mid, skipped
]

with tempfile.TemporaryDirectory() as tmp:
    pa, pb = os.path.join(tmp, "a.json"), os.path.join(tmp, "b.json")
    json.dump(A, open(pa, "w"))
    json.dump(B, open(pb, "w"))
    out_dir = os.path.join(tmp, "data")
    os.makedirs(out_dir)
    cwd = os.getcwd()
    os.chdir(tmp)
    try:
        subprocess.run([sys.executable, os.path.join(HERE, "..", "json-mbox-diff.py"), "a.json", "b.json"],
                       check=True, capture_output=True)
        result = json.load(open(os.path.join(out_dir, "diff-a-vs-b.json")))
    finally:
        os.chdir(cwd)

by_status = {}
for r in result:
    by_status.setdefault(r["diff_status"], []).append(r["subject"])

assert sorted(by_status.get("both", [])) == ["S1", "S8"], by_status
assert sorted(by_status.get("both_no_mid", [])) == ["S2", "S5", "S6", "S7"], by_status
assert sorted(by_status.get("only-A", [])) == ["S3", "S4"], by_status
assert sorted(by_status.get("only-B", [])) == ["S5", "S9"], by_status
assert "S1dup" not in {s for v in by_status.values() for s in v}, "dup mid not skipped"
assert "S9dup" not in {s for v in by_status.values() for s in v}, "dup mid not skipped"

print("OK")
