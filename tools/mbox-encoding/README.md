# mbox/sbd encoding checker

`mbox-encoding-fix.py` scans an mbox/sbd tree (or a single mbox file) for encoding issues in message subjects, senders, and `text/plain`/`text/html` bodies. MIME attachments are skipped during inspection.

## Usage

```bash
# Scan an mbox/sbd tree and export suspect messages:
python tools/mbox-encoding/mbox-encoding-fix.py --suspects-mbox "C:\Users\me\Desktop\suspects.mbox" "C:\Users\me\AppData\Roaming\Thunderbird\Profiles\xxx\Mail\Local Folders"

# Scan one mbox directly:
python tools/mbox-encoding/mbox-encoding-fix.py "C:\Users\me\AppData\Roaming\Thunderbird\Profiles\xxx\Mail\Local Folders\Inbox"

# Export messages with safely repairable encoding problems (-c is the short form):
python tools/mbox-encoding/mbox-encoding-fix.py -c "C:\Users\me\Desktop\corrected.mbox" "C:\Users\me\AppData\Roaming\Thunderbird\Profiles\xxx\Mail\Local Folders"

# Explicitly replace existing output files:
python tools/mbox-encoding/mbox-encoding-fix.py -f -c "C:\Users\me\Desktop\corrected.mbox" "C:\Users\me\AppData\Roaming\Thunderbird\Profiles\xxx\Mail\Local Folders"

# Safely correct supported issues in the source mailbox(es):
python tools/mbox-encoding/mbox-encoding-fix.py --in-place "C:\Users\me\AppData\Roaming\Thunderbird\Profiles\xxx\Mail\Local Folders"

# Also save safe partial corrections when other issues remain in a message:
python tools/mbox-encoding/mbox-encoding-fix.py --in-place --in-place-partial "C:\Users\me\AppData\Roaming\Thunderbird\Profiles\xxx\Mail\Local Folders"
```

## Findings and output

The checker reports the mailbox and message number, affected field, and a short excerpt for each unresolved problem. For long fields, the excerpt is centered around the detected mojibake or first U+FFFD replacement character so the location of the problem is visible. After the correction logs, stdout lists only problems that remain unresolved and summarizes their count; resolved findings are omitted. Progress is written to stderr, including periodic updates for large mboxes, and shows messages scanned, fully corrected messages, and suspect messages still unresolved among those scanned. A message with a partial correction remains in the suspect count until all findings in it have been resolved. Characters that the current console encoding cannot display are escaped in the output. After a successful scan, each corrected message is logged to stdout with its mailbox path, Message-ID, subject, and individual corrections.

With `--suspects-mbox` (`-o`), it creates a new mbox containing each message with one or more findings exactly once, including any attachments. Each exported suspect carries an `X-Encoding-Suspect` header for every remaining issue, containing its field, reason, and excerpt; non-ASCII characters and embedded encoded-word markers in that diagnostic are escaped to keep the header safely serializable. Messages modified during repair also receive one `X-Encoding-Correction` header per change, describing the repaired field/body, decoding fallback, or charset alignment. These headers are included in the corrected mbox and on partially repaired messages kept in the suspects mbox.

With `--corrected-mbox` (`-c`), it creates a separate mbox containing only messages corrected automatically. Supported repairs include reversible UTF-8 mojibake in subject/sender/body, RFC-2047 encoded words with unsupported labels such as `unknown-8bit` or `x-user-defined` decoded with Windows-1252 and then ISO-8859-1 fallbacks, and text parts recoverable from a declared HTML/MIME charset or a Windows-1252 fallback. Subject and sender diagnosis uses the same fallback decoding, avoiding false U+FFFD findings when an `unknown-8bit` header can be recovered. For `x-user-defined` Q-encoded words, literal underscores are preserved. Long, printable Western text declared as ASCII but decoded cleanly as Windows-1252 is treated as readable legacy text rather than a suspect; this avoids false alarms on older quoted-printable messages, but may leave a mismatched charset declaration unchanged.

The checker reads only subject, sender, and `text/plain`/`text/html` body parts. MIME attachments are skipped during inspection. A `text/html` part that decodes cleanly as UTF-8 is not flagged for replacement characters or mojibake-looking text; this avoids treating valid UTF-8 HTML as corrupt. It can still be repaired when a matching plain-text alternative uniquely supplies a missing character, and an explicitly recognized empty signature marker can be removed. Invalid UTF-8 or charset conflicts continue to be reported. Only copied MIME text parts that are actually repaired are marked UTF-8; other content-type parameters are preserved, and attachments are left untouched. Mojibake detection is heuristic, so review the corrected mbox before using it.

By default, output paths must not already exist; use `--force` (`-f`) to replace existing output files. Forced outputs are staged and only moved into place after a successful scan. Outputs must remain distinct from each other and outside the scanned tree; in-place corrections are the explicit exception to the rule that input mboxes are not overwritten.

When both `--suspects-mbox` and `--corrected-mbox` are used, messages fully repaired and included in the corrected mbox are omitted from the suspects mbox. Independently reversible mojibake in a message can be repaired even if another character in the same body is U+FFFD; if other findings remain, the partially repaired message stays in the suspects mbox and is not included in the corrected mbox.

With `--in-place`, safe corrections are applied to the scanned mbox file or files only after the entire scan succeeds. By default, only messages with no remaining findings after correction are written back; messages that are unchanged or still have unresolved findings are retained byte-for-byte. Add `--in-place-partial` to also write messages where safe corrections were made but other findings remain. This option requires `--in-place`. Each mailbox is staged beside its original and atomically replaced, with rollback if an update fails. Close your mail client (e.g. Thunderbird) before an in-place run so it cannot modify a mailbox concurrently.

## Charset and replacement handling

For `text/html` parts that declare different charsets in the MIME `Content-Type` and an HTML `<meta charset>`, the meta charset is tried first. If it can decode the payload it takes precedence; otherwise the MIME charset is tried. A message with conflicting declarations is reported and the corrected copy is normalized to UTF-8, with both the MIME charset and HTML meta charset updated to match the repaired body.

The checker trusts a valid Unicode byte-order mark (including UTF-16) over a conflicting or unsupported MIME charset and normalizes repaired text parts to UTF-8. A UTF-8 BOM paired with a UTF-8 MIME charset is considered consistent and is not reported on its own.

For multipart/alternative messages, a `U+FFFD` in `text/plain` can be restored when matching `text/html` supplies exactly one printable character between identical surrounding context, or an otherwise identical word with only the replacement positions differing. It also attempts the inverse recovery, restoring a visible `U+FFFD` in HTML from a uniquely matching plain-text word. HTML markup and entities sometimes copied literally into `text/plain` are normalized for this comparison. Ambiguous or unmatched replacement characters remain reported because their original value cannot be inferred safely.

A small set of known damaged phrases and words can be reconstructed when their specific context matches, especially where the missing character is an accented letter or a symbol such as `€`, `°`, or `©` (for example, `�a allait de` to `ça allait de`, or `auront �t�` to `auront été`); these high-confidence heuristics are recorded in `X-Encoding-Correction`. They are not byte-for-byte recovery, so review them in the corrected mbox. Plain ASCII letters are not inferred just to make a phrase look grammatical. Any replacement character without a unique alternative or a recognized context remains a suspect.

Parts that strongly resemble binary data (ZIP signature, substantial NUL bytes, or a high proportion of control bytes) are left untouched and reported as opaque rather than treated as ordinary text encoding failures; they are excluded as recovery sources too.
