#!/usr/bin/env python3

# Script to analyze Gmail Takeout mbox files and generate statistics by year and Gmail label.
# This 'fast' version parse manually the mbox file without the full and slow mbox parsing


import re
from email.utils import parsedate_to_datetime
from email.header import decode_header
from collections import Counter, defaultdict
import sys

MBOX_FILE = r"D:\Backups\Tous les messages, y compris ceux du dossier Spam et de la corbeille.mbox"

DATE_RE  = re.compile(r"^Date:\s*(.*)", re.IGNORECASE)
LABEL_RE = re.compile(r"^X-Gmail-Labels:\s*(.*)", re.IGNORECASE)

count_year  = Counter()
size_year   = defaultdict(int)

count_label = Counter()
size_label  = defaultdict(int)

processed = 0
total_size = 0


def human_size(n: int) -> str:
    for unit in ["octets", "Ko", "Mo", "Go", "To"]:
        if n < 1024:
            return f"{n:.2f} {unit}"
        n /= 1024
    return f"{n:.2f} Po"


def decode_rfc2047(s: str) -> str:
    """Décode proprement les fragments RFC 2047."""
    parts = decode_header(s)
    out = []
    for text, enc in parts:
        if isinstance(text, bytes):
            try:
                out.append(text.decode(enc or "utf-8", errors="ignore"))
            except Exception:
                out.append(text.decode("utf-8", errors="ignore"))
        else:
            out.append(text)
    return "".join(out)


print("Traitement (un point = 500 mails) :")

with open(MBOX_FILE, "r", errors="ignore") as f:
    msg_size = 0
    msg_year = None
    msg_labels = []

    collecting_labels = False
    label_buffer = []

    for line in f:

        # Nouveau message
        if line.startswith("From "):
            # Finalisation du précédent
            if msg_size > 0:
                total_size += msg_size

                if msg_year is not None:
                    count_year[msg_year] += 1
                    size_year[msg_year]  += msg_size

                for lbl in msg_labels:
                    count_label[lbl] += 1
                    size_label[lbl]  += msg_size

            # Reset
            msg_size = 0
            msg_year = None
            msg_labels = []
            collecting_labels = False
            label_buffer = []
            continue

        msg_size += len(line)

        # Date
        m = DATE_RE.match(line)
        if m:
            processed += 1
            if processed % 500 == 0:
                sys.stdout.write(".")
                sys.stdout.flush()

            raw_date = m.group(1).strip()
            try:
                dt = parsedate_to_datetime(raw_date)
                msg_year = dt.year
            except Exception:
                pass

        # Début d'un bloc X-Gmail-Labels
        m = LABEL_RE.match(line)
        if m:
            collecting_labels = True
            label_buffer.append(m.group(1).strip())
            continue

        # Lignes de continuation (RFC 822)
        if collecting_labels:
            if line.startswith(" ") or line.startswith("\t"):
                label_buffer.append(line.strip())
                continue
            else:
                # Fin du bloc multilignes
                collecting_labels = False

                merged = " ".join(label_buffer)
                decoded = decode_rfc2047(merged)

                for lbl in decoded.split(","):
                    lbl = lbl.strip()
                    if lbl:
                        msg_labels.append(lbl)

                label_buffer = []

    # Finalisation du dernier message
    if msg_size > 0:
        total_size += msg_size
        if msg_year is not None:
            count_year[msg_year] += 1
            size_year[msg_year]  += msg_size
        for lbl in msg_labels:
            count_label[lbl] += 1
            size_label[lbl]  += msg_size


print("\n\n--- Stats par année ---")
for year in sorted(count_year):
    print(f"{year}: {count_year[year]} mails, {human_size(size_year[year])}")

total_mails = sum(count_year.values())
print("\nTotal mails :", total_mails)
print("Taille totale :", human_size(total_size))
print("Taille moyenne :", human_size(total_size // max(1, total_mails)))

print("\n--- Stats par label Gmail ---")
for lbl in sorted(count_label):
    print(f"{lbl}: {count_label[lbl]} mails, {human_size(size_label[lbl])}")


