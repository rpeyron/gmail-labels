#!/usr/bin/env python3
from email.header import decode_header, make_header
import os
import sys
import json
import mailbox
from email.utils import parsedate_to_datetime
from email import policy


# 1. Run the script to generate the JSON data:   python mbox-gen-html.py <mbox|maildir>...
# 2. Serve the files with a local HTTP server:   python -m http.server 9000
# 3. Open the HTML viewer in a browser:         http://localhost:9000/mbox-gen-html.html

PATH_MAILS_JSON = "data/mails.json"


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

def build_record(msg, src_path):
    subject = safe_header(msg, "Subject")
    from_ = safe_header(msg, "From")
    to = safe_header(msg, "To")
    date_raw = safe_header(msg, "Date")

    dt = None
    year = None
    if date_raw:
        try:
            dt = parsedate_to_datetime(date_raw)
            year = dt.year
        except Exception:
            pass

    mid = safe_header(msg, "Message-ID")
    gmail_labels = extract_gmail_labels(msg)
    gmail_id = extract_gmail_id(msg)
    size = safe_message_size(msg)

    return {
        "subject": subject,
        "from": from_,
        "to": to,
        "date": dt.isoformat() if dt else None,
        "year": year,
        "message_id": mid,
        "gmail_labels": gmail_labels,
        "gmail_id": gmail_id,
        "size": size,
        "source_file": src_path,
    }

def parse_source(path):
    if os.path.isdir(path):
        for msg, src, key in iter_maildir(path):
            yield build_record(msg, src)
    else:
        for msg, src, key in iter_mbox(path):
            yield build_record(msg, src)

def main():
    if len(sys.argv) < 2:
        print("Usage: script.py <mbox|maildir>...")
        sys.exit(1)

    json_path = PATH_MAILS_JSON
    sources = sys.argv[1:]
    records = []

    for src in sources:
        for rec in parse_source(src):
            records.append(rec)

    os.makedirs(os.path.dirname(json_path), exist_ok=True)
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False)

    print(f"JSON écrit : {json_path} ({len(records)} mails)")

if __name__ == "__main__":
    main()
