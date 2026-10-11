#!/usr/bin/env python3
import mailbox
from email.utils import parsedate_to_datetime
from email.header import decode_header, make_header
from email import policy
from collections import Counter, defaultdict
import sys


# Script to analyze Gmail Takeout mbox files and generate statistics by year and Gmail label.
# This version parse the mbox file with the slow but resilient mbox parsing

# MBOX_FILE = r"D:\Backups\Tous les messages, y compris ceux du dossier Spam et de la corbeille.mbox"
MBOX_FILE = r"D:\Backups\All mail Including Spam and Trash.mbox"


# ------------------------------------------------------------
# Taille robuste : ne plante jamais
# ------------------------------------------------------------
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


# ------------------------------------------------------------
# Décodage RFC 2047 multiligne (standard, sans heuristiques)
# ------------------------------------------------------------
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
    return "".join(out).replace("\r", "").replace("\n", "")

def decode_gmail_labels(raw):
    if not raw:
        return []

    rfc = decode_rfc2047(raw)
    decoded = [p.strip() for p in rfc.split(",") if p.strip()]

    return decoded


def extract_labels(msg):
    raw = msg.get("X-Gmail-Labels")
    return decode_gmail_labels(raw)


# ------------------------------------------------------------
# Extraction de l'année
# ------------------------------------------------------------
def extract_year(msg):
    date = msg.get("Date")
    if not date:
        return None
    try:
        dt = parsedate_to_datetime(date)
        return dt.year
    except Exception:
        return None


# ------------------------------------------------------------
# Format humain
# ------------------------------------------------------------
def human_size(n):
    units = ["octets", "Ko", "Mo", "Go", "To"]
    i = 0
    while n >= 1024 and i < len(units) - 1:
        n /= 1024
        i += 1
    return f"{n:.2f} {units[i]}"


# ------------------------------------------------------------
# Lecture du MBOX (une seule fois)
# ------------------------------------------------------------
mbox = mailbox.mbox(MBOX_FILE)

counts_year = Counter()
size_year = defaultdict(int)

counts_label = Counter()
size_label = defaultdict(int)

processed = 0
total_size = 0

print("Traitement en cours (un point = 1000 mails) :")

for msg in mbox:
    processed += 1

    raw_bytes = safe_message_size(msg)
    total_size += raw_bytes

    if processed % 1000 == 0:
        sys.stdout.write(".")
        sys.stdout.flush()

    year = extract_year(msg)
    if year:
        counts_year[year] += 1
        size_year[year] += raw_bytes

    labels = extract_labels(msg)
    for lbl in labels:
        counts_label[lbl] += 1
        size_label[lbl] += raw_bytes


print("\n\n--- Résultat par année ---")
for year in sorted(counts_year):
    print(f"{year}: {counts_year[year]} mails, {human_size(size_year[year])}")

print("\nTotal mails :", sum(counts_year.values()))
print("Taille totale :", human_size(total_size))
print("Taille moyenne :", human_size(total_size // max(1, sum(counts_year.values()))))

print("\n--- Résultat par label Gmail ---")
for lbl in sorted(counts_label):
    print(f"{lbl}: {counts_label[lbl]} mails, {human_size(size_label[lbl])}")

