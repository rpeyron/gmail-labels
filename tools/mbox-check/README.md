# mbox/sbd structure checker

`mbox_check.py` checks the structure of an mbox/sbd mail store and the coherence of the messages it holds. It reports what is wrong; it never changes a file unless `--clean --in-place` is given.

## Usage

```bash
# Check a mail store:
python tools/mbox-check/mbox_check.py "C:\Users\me\AppData\Roaming\Thunderbird\Profiles\xxx\Mail\Local Folders"

# List the binary padding that could be removed (dry run):
python tools/mbox-check/mbox_check.py --clean "C:\Users\me\AppData\Roaming\Thunderbird\Profiles\xxx\Mail\Local Folders"

# Actually remove it:
python tools/mbox-check/mbox_check.py --clean --in-place "C:\Users\me\AppData\Roaming\Thunderbird\Profiles\xxx\Mail\Local Folders"
```

The report goes to stdout and the exit code is `1` when a problem was found, `0` otherwise. The tool only reads the files it checks.

## What is checked

### The tree

- `index-without-mailbox` — a `.msf` index with no matching mbox file.
- `folder-without-mailbox` — a `.sbd` sub-folder with no matching mbox file.
- `not-an-mbox` — a file that is not empty and does not start with a `From ` separator.

### The messages

- `no-header-body-separator` — a message with no empty line between its headers and its body.
- `control-byte-in-header` — a header line that holds a control byte. A header is a line of text, so a control byte means the message was damaged or a part of a binary blob was written where a header should be.
- `control-byte-in-body` — a part that declares a `Content-Transfer-Encoding` but still holds a control byte. The declared encoding was not applied, so the part is not decodable as it claims.
- `binary-in-body` — a part with no transfer encoding that holds a binary document (a ZIP archive, a PostScript file, a JPEG image and so on) or a high proportion of control bytes. The binary was written straight into the body without a MIME part, so a mail client shows it as garbage. A part that *does* declare a transfer encoding is never reported, so ordinary attachments are left alone.

### The binary padding

`binary-padding` — a message that ends with bytes that are not text. The padding sits between the last text of the body and the line breaks that close the message.

Every kind of padding is detected, not only NUL bytes:

- a run of NUL bytes, the padding left by a program that reserved room for a fixed-size record;
- a repeated filler byte, such as `\xc9` or `\xfe`;
- a truncated binary blob, the tail of a file that was copied into the body;
- a byte that is not text in the charset the message declares.

The last case needs care: a lone `\xe9` at the end of a message is the `é` of an ISO-8859-1 body and not padding, so the charset the message declares is used to decide whether a byte is text. A body that declares UTF-8 is read as UTF-8, and a body that declares nothing is read as UTF-8 with a fallback to ISO-8859-1.

The padding of a message is measured on its body, not on the whole mbox file, so the `From ` line that separates two messages is never mistaken for padding.

## Cleaning the padding

`--clean` lists the padding that could be removed. `--clean --in-place` writes the cleaned mailboxes. Only the padding is removed: the headers, the body and the message boundaries of the mailbox are left as they are, and a message that has no padding is not rewritten. A mailbox that holds no padding is not written at all.

The removal is a byte-level operation, so a message keeps its exact content apart from the padding. The `.msf` index of a mailbox holds the size and the offset of its messages, so it should be dropped after a clean, or the mail client should be closed while the mailboxes are changed.

## Notes

- The tool reads every byte of the tree, so it takes a while on a large mail store.
- A mailbox is a file that starts with a `From ` line. A file that does not is reported and skipped, which is how a stray archive such as `junklog.zip` is told apart from a mailbox.
- The index files (`.msf`), the side files (`.html`, `.log`) and the archives (`.zip`, `.7z`) are not treated as mailboxes.
