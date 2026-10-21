import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mbox_check import (
    check_tree,
    clean_file,
    split_messages,
    strip_padding,
    trailing_padding,
)


ENVELOPE = b"From sender@example.com Sat Jan  1 00:00:00 2022\n"


class MboxCheckTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def _write(self, relative: str, content: bytes) -> Path:
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return path

    def _kinds(self) -> dict[str, int]:
        report = check_tree(self.root)
        return report.counts()

    def test_empty_tree_has_no_problem(self) -> None:
        report = check_tree(self.root)

        self.assertEqual(report.problems, [])
        self.assertEqual(report.mailboxes, 0)

    def test_a_clean_mailbox_has_no_problem(self) -> None:
        self._write(
            "Inbox",
            ENVELOPE
            + b"Subject: hello\n"
            b"Content-Type: text/plain; charset=utf-8\n\n"
            b"Hello world\n",
        )

        report = check_tree(self.root)

        self.assertEqual(report.problems, [])
        self.assertEqual(report.mailboxes, 1)
        self.assertEqual(report.messages, 1)

    def test_reports_nul_padding_at_the_end_of_a_message(self) -> None:
        self._write(
            "Inbox",
            ENVELOPE
            + b"Subject: hello\n"
            b"Content-Type: text/plain; charset=utf-8\n\n"
            b"Body text\n"
            + b"\x00" * 128
            + b"\n",
        )

        report = check_tree(self.root)

        self.assertEqual(report.counts().get("binary-padding"), 1)
        problem = report.by_kind()["binary-padding"][0]
        self.assertEqual(problem.message_number, 1)
        self.assertIn("128 byte(s)", problem.detail)

    def test_reports_a_repeated_filler_byte_as_padding(self) -> None:
        self._write(
            "Inbox",
            ENVELOPE
            + b"Subject: hello\n"
            b"Content-Type: text/plain; charset=utf-8\n\n"
            b"Body text\n"
            + b"\xc9" * 64
            + b"\n",
        )

        report = check_tree(self.root)

        self.assertEqual(report.counts().get("binary-padding"), 1)

    def test_reports_a_binary_blob_as_padding(self) -> None:
        self._write(
            "Inbox",
            ENVELOPE
            + b"Subject: hello\n"
            b"Content-Type: text/plain; charset=utf-8\n\n"
            b"Body text\n"
            + bytes(range(200, 256))
            + b"\n",
        )

        report = check_tree(self.root)

        self.assertEqual(report.counts().get("binary-padding"), 1)

    def test_padding_before_the_next_message_is_found(self) -> None:
        self._write(
            "Inbox",
            ENVELOPE
            + b"Subject: one\n"
            b"Content-Type: text/plain; charset=utf-8\n\n"
            b"First body\n"
            + b"\x00" * 40
            + b"\n"
            + ENVELOPE
            + b"Subject: two\n"
            b"Content-Type: text/plain; charset=utf-8\n\n"
            b"Second body\n",
        )

        report = check_tree(self.root)

        self.assertEqual(report.counts().get("binary-padding"), 1)
        problem = report.by_kind()["binary-padding"][0]
        self.assertEqual(problem.message_number, 1)

    def test_a_emoji_at_the_end_of_a_body_is_not_padding(self) -> None:
        self._write(
            "Inbox",
            ENVELOPE
            + b"Subject: hello\n"
            b"Content-Type: text/plain; charset=utf-8\n\n"
            + "Joyeux Noël ☃ ❤\n".encode("utf-8"),
        )

        report = check_tree(self.root)

        self.assertEqual(report.problems, [])

    def test_reports_a_control_byte_in_a_header(self) -> None:
        self._write(
            "Inbox",
            ENVELOPE
            + b"Subject: hello\x00world\n"
            b"Content-Type: text/plain; charset=utf-8\n\n"
            b"Body\n",
        )

        report = check_tree(self.root)

        self.assertEqual(report.counts().get("control-byte-in-header"), 1)

    def test_reports_a_binary_body_without_a_mime_part(self) -> None:
        self._write(
            "Inbox",
            ENVELOPE
            + b"Subject: hello\n\n"
            b"PK\x03\x04" + b"\x00" * 200 + b"\n",
        )

        report = check_tree(self.root)

        self.assertEqual(report.counts().get("binary-in-body"), 1)
        problem = report.by_kind()["binary-in-body"][0]
        self.assertIn("ZIP archive", problem.detail)

    def test_a_binary_attachment_in_a_mime_part_is_not_reported(self) -> None:
        self._write(
            "Inbox",
            ENVELOPE
            + b"Subject: hello\n"
            b"MIME-Version: 1.0\n"
            b"Content-Type: multipart/mixed; boundary=x\n\n"
            b"--x\n"
            b"Content-Type: application/octet-stream; name=f.bin\n"
            b"Content-Transfer-Encoding: base64\n\n"
            b"AAEC/w==\n"
            b"--x--\n",
        )

        report = check_tree(self.root)

        self.assertNotIn("binary-in-body", report.counts())

    def test_reports_a_message_without_a_header_body_separator(self) -> None:
        self._write("Inbox", ENVELOPE + b"Subject: hello")

        report = check_tree(self.root)

        self.assertEqual(report.counts().get("no-header-body-separator"), 1)

    def test_a_message_with_only_headers_has_no_separator_problem(self) -> None:
        self._write("Inbox", ENVELOPE + b"Subject: hello\n")

        report = check_tree(self.root)

        self.assertNotIn("no-header-body-separator", report.counts())

    def test_a_message_with_crlf_endings_has_no_separator_problem(self) -> None:
        self._write(
            "Inbox",
            ENVELOPE
            + b"Subject: hello\r\n"
            b"Content-Type: text/plain; charset=utf-8\r\n\r\n"
            b"Body text\r\n",
        )

        report = check_tree(self.root)

        self.assertNotIn("no-header-body-separator", report.counts())
        self.assertNotIn("binary-padding", report.counts())

    def test_reports_a_file_that_is_not_an_mbox(self) -> None:
        self._write("Archives mailo", b"PK\x03\x04 not a mailbox")

        report = check_tree(self.root)

        self.assertEqual(report.counts().get("not-an-mbox"), 1)

    def test_reports_an_index_without_its_mailbox(self) -> None:
        self._write("Orphan.msf", b"index")

        report = check_tree(self.root)

        self.assertEqual(report.counts().get("index-without-mailbox"), 1)

    def test_reports_a_sub_folder_without_its_mailbox(self) -> None:
        (self.root / "Archives.sbd").mkdir()
        (self.root / "Archives.sbd" / "Sub").mkdir(parents=True)

        report = check_tree(self.root)

        self.assertEqual(report.counts().get("folder-without-mailbox"), 1)

    def test_a_mbox_with_its_index_has_no_layout_problem(self) -> None:
        self._write("Inbox", ENVELOPE + b"Subject: x\n\nBody\n")
        self._write("Inbox.msf", b"index")

        report = check_tree(self.root)

        self.assertNotIn("index-without-mailbox", report.counts())
        self.assertNotIn("folder-without-mailbox", report.counts())

    def test_a_latin1_character_at_the_end_is_not_padding(self) -> None:
        self._write(
            "Inbox",
            ENVELOPE
            + b"Subject: hello\n"
            b"Content-Type: text/plain; charset=iso-8859-1\n\n"
            b"-- \r\nAndr\xe9\r\n",
        )

        report = check_tree(self.root)

        self.assertNotIn("binary-padding", report.counts())

    def test_trailing_padding_ignores_the_line_breaks(self) -> None:
        offset, length = trailing_padding(b"text\r\n")

        self.assertEqual(length, 0)

    def test_trailing_padding_finds_the_nul_run(self) -> None:
        offset, length = trailing_padding(b"text\n\x00\x00\x00")

        self.assertEqual(length, 3)
        self.assertEqual(offset, 5)

    def test_strip_padding_removes_the_filler(self) -> None:
        blob = (
            ENVELOPE
            + b"Subject: hello\n"
            b"Content-Type: text/plain; charset=utf-8\n\n"
            b"Body text\n"
            + b"\x00" * 10
            + b"\n"
        )

        cleaned, removed = strip_padding(blob)

        self.assertEqual(removed, 10)
        self.assertNotIn(b"\x00", cleaned)
        self.assertIn(b"Body text", cleaned)

    def test_clean_file_rewrites_the_mailbox(self) -> None:
        path = self._write(
            "Inbox",
            ENVELOPE
            + b"Subject: hello\n"
            b"Content-Type: text/plain; charset=utf-8\n\n"
            b"Body text\n"
            + b"\x00" * 10
            + b"\n",
        )

        removed = clean_file(path)

        self.assertEqual(removed, 10)
        self.assertNotIn(b"\x00", path.read_bytes())

    def test_split_messages_finds_every_message(self) -> None:
        blob = (
            ENVELOPE
            + b"Subject: one\n\nFirst\n"
            + ENVELOPE
            + b"Subject: two\n\nSecond\n"
        )

        spans = split_messages(blob)

        self.assertEqual(len(spans), 2)
        self.assertEqual(blob[spans[0][0]: spans[0][1]].count(b"Subject"), 1)
        self.assertEqual(blob[spans[1][0]: spans[1][1]].count(b"Subject"), 1)


if __name__ == "__main__":
    unittest.main()
