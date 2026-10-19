#!/usr/bin/env python3
from email.header import decode_header, make_header
import os
import sys
import json
import mailbox
from email.utils import parsedate_to_datetime
from email import policy
import argparse


# 1. Run the script to generate the JSON data:   python generate.py [-o OUT] <mbox|maildir>...
# 2. Serve the files with a local HTTP server:   python start-web.py
# 3. Open the HTML viewer in a browser:         http://localhost:9000/

PATH_MAILS_JSON = "data/mails.json"


def resolve_output(name):
    if os.path.isdir(name) or name.endswith(('/', '\\')):
        return os.path.join(name, "mails.json")
    if not os.path.splitext(name)[1]:
        name += ".json"
    if not os.path.dirname(name):
        name = os.path.join("data", name)
    return name


def safe_header(msg, name):
    raw = msg.get(name)
    if raw is None:
        return ""
    try:
        return str(make_header(decode_header(raw))).strip()
    except Exception:
        return str(raw).strip()

def extract_gmail_labels(msg):
    labels = safe_header(msg, "X-Gmail-Labels")
    if labels:
        return [l.strip() for l in labels.split(",") if l.strip()]
    return []

def extract_gmail_id(msg):
    return (
        safe_header(msg, "X-GM-THRID")
        or safe_header(msg, "X-Gmail-Message-Id")
        or safe_header(msg, "Message-ID")
    )

def safe_message_size(msg):
    try:
        return len(msg.as_bytes(policy=policy.default))
    except Exception:
        pass
    try:
        return len(msg.as_string().encode("utf-8", errors="replace"))
    except Exception:
        pass
    return len(repr(msg).encode("utf-8", errors="replace"))

def iter_maildir(root):
    mdir = mailbox.Maildir(root, factory=None)
    for key, msg in mdir.iteritems():
        yield msg, os.path.join(root, "cur"), key

def iter_mbox(path):
    mbox = mailbox.mbox(path, factory=None)
    for key, msg in mbox.iteritems():
        yield msg, path, key

def is_mbox_file(path):
    """Check if file is an mbox/sbd tree file (no extension, not in skip list)."""
    if not os.path.isfile(path):
        return False
    base = os.path.basename(path)
    _, ext = os.path.splitext(base)
    # Skip files with extensions and known non-mbox files
    skip = {'.msf', '.dat', '.html', '.json', '.sbd'}
    skip_names = {'msgfilterrules.dat', 'filterlog.html', 'mozmsgs'}
    if ext in skip or base in skip_names or base.startswith('.'):
        return False
    return True

def iter_mbox_tree(root):
    """Recursively walk mbox/sbd directory tree."""
    for entry in os.scandir(root):
        if entry.is_file() and is_mbox_file(entry.path):
            print(f"Processing: {entry.path}", file=sys.stderr)
            try:
                for msg, src, key in iter_mbox(entry.path):
                    yield msg, src, key
            except Exception as e:
                print(f"Warning: skipped {entry.path}: {e}", file=sys.stderr)
        elif entry.is_dir():
            # Recurse into subdirs (including .sbd dirs)
            if not entry.name.startswith('.') or entry.name.endswith('.sbd'):
                yield from iter_mbox_tree(entry.path)

def extract_real_date(msg):
    """Latest date found in Received headers (after the last ';'), or None."""
    best = None
    for received in msg.get_all("Received") or []:
        received = str(received)
        if ";" not in received:
            continue
        date_part = received.rsplit(";", 1)[1].strip()
        try:
            dt = parsedate_to_datetime(date_part)
        except Exception:
            continue
        if best is None or (dt.replace(tzinfo=None) if dt.tzinfo else dt) > \
                           (best.replace(tzinfo=None) if best.tzinfo else best):
            best = dt
    return best

def build_record(msg, src_path):
    subject = safe_header(msg, "Subject")
    from_ = safe_header(msg, "From")
    to = safe_header(msg, "To")
    date_raw = safe_header(msg, "Date")

    dt = None
    if date_raw:
        try:
            dt = parsedate_to_datetime(date_raw)
        except Exception:
            pass

    real_dt = extract_real_date(msg)
    year_dt = real_dt if real_dt is not None else dt
    year = year_dt.year if year_dt else None

    mid = safe_header(msg, "Message-ID")
    gmail_labels = extract_gmail_labels(msg)
    gmail_id = extract_gmail_id(msg)
    size = safe_message_size(msg)

    return {
        "subject": subject,
        "from": from_,
        "to": to,
        "date": dt.isoformat() if dt else None,
        "real_date": real_dt.isoformat() if real_dt else None,
        "year": year,
        "message_id": mid,
        "gmail_labels": gmail_labels,
        "gmail_id": gmail_id,
        "size": size,
        "source_file": src_path,
    }

def parse_source(path):
    if os.path.isdir(path):
        # Detect Maildir (has cur/new/tmp subdirs) vs mbox/sbd tree
        has_maildir_structure = all(
            os.path.isdir(os.path.join(path, d)) for d in ['cur', 'new', 'tmp']
        )
        if has_maildir_structure:
            for msg, src, key in iter_maildir(path):
                yield build_record(msg, src)
        else:
            # Treat as mbox/sbd tree
            for msg, src, key in iter_mbox_tree(path):
                yield build_record(msg, src)
    else:
        for msg, src, key in iter_mbox(path):
            yield build_record(msg, src)

def main():
    parser = argparse.ArgumentParser(description="Generate mails JSON from mbox|maildir|mbox-tree sources")
    parser.add_argument("-o", "--output", default=PATH_MAILS_JSON,
                        help="output JSON file (default: data/mails.json); "
                             "a directory places mails.json inside it; "
                             ".json extension added if missing; "
                             "bare filenames go into data/")
    parser.add_argument("sources", nargs="+", metavar="<mbox|maildir|mbox-tree>")
    args = parser.parse_args()

    json_path = resolve_output(args.output)
    records = []

    for src in args.sources:
        # Strip quotes from path (shell escaping artifacts)
        src = src.strip('"').strip("'")

        if not os.path.exists(src):
            print(f"Error: path does not exist: {src}", file=sys.stderr)
            sys.exit(1)

        for rec in parse_source(src):
            records.append(rec)

    dirname = os.path.dirname(json_path)
    if dirname:
        os.makedirs(dirname, exist_ok=True)
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False)

    print(f"JSON écrit : {json_path} ({len(records)} mails)")

if __name__ == "__main__":
    main()
