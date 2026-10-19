import tempfile
import unittest
from pathlib import Path

from merge_mbox import expand_input_patterns, main, merge_trees


class MergeMboxTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.first = self.root / "first"
        self.second = self.root / "second"
        self.output = self.root / "merged"
        self.first.mkdir()
        self.second.mkdir()

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_merges_matching_mboxes_and_preserves_nested_folders(self) -> None:
        first_mailbox = self.first / "Inbox"
        second_mailbox = self.second / "Inbox"
        first_mailbox.write_bytes(b"From first\nSubject: one\n\nMessage one")
        second_mailbox.write_bytes(b"From second\nSubject: two\n\nMessage two\n")
        (self.first / "Inbox.sbd").mkdir()
        (self.first / "Inbox.sbd" / "Work").write_bytes(b"From nested\n")

        merge_trees([self.first, self.second], self.output)

        self.assertEqual(
            (self.output / "Inbox").read_bytes(),
            b"From first\nSubject: one\n\nMessage one\n"
            b"From second\nSubject: two\n\nMessage two\n",
        )
        self.assertEqual(
            (self.output / "Inbox.sbd" / "Work").read_bytes(), b"From nested\n"
        )
        self.assertFalse((self.second / "Inbox").read_bytes().endswith(b"Message one"))

    def test_empty_mailbox_and_ignored_index(self) -> None:
        (self.first / "Drafts").touch()
        (self.first / "Drafts.msf").write_text("stale index")
        (self.second / "Drafts").write_bytes(b"From sender\n\nBody\n")

        merge_trees([self.first, self.second], self.output)

        self.assertEqual((self.output / "Drafts").read_bytes(), b"From sender\n\nBody\n")
        self.assertFalse((self.output / "Drafts.msf").exists())

    def test_conflicting_auxiliary_files_fail_before_writing_output(self) -> None:
        (self.first / "helper.cfg").write_text("first configuration")
        (self.second / "helper.cfg").write_text("second configuration")

        with self.assertRaisesRegex(ValueError, "Different auxiliary files"):
            merge_trees([self.first, self.second], self.output)

        self.assertFalse(self.output.exists())

    def test_rejects_output_inside_source(self) -> None:
        nested_output = self.first / "merged"
        with self.assertRaisesRegex(ValueError, "cannot be inside a source directory"):
            merge_trees([self.first, self.second], nested_output)

    def test_expands_wildcard_input_directories(self) -> None:
        (self.first / "Inbox").write_bytes(b"From first\n")
        (self.second / "Inbox").write_bytes(b"From second\n")
        (self.root / "dedup_with_mailbox.log").write_text("log")
        self.assertEqual(
            expand_input_patterns([self.root / "*"]),
            [self.first, self.second],
        )

        result = main(
            [
                "--output",
                str(self.output),
                str(self.root / "*"),
            ]
        )

        self.assertEqual(result, 0)
        self.assertEqual(
            (self.output / "Inbox").read_bytes(),
            b"From first\nFrom second\n",
        )

    def test_rejects_wildcard_without_matches(self) -> None:
        with self.assertRaisesRegex(
            ValueError, "No source directories matched input pattern"
        ):
            expand_input_patterns([self.root / "missing-*"])


if __name__ == "__main__":
    unittest.main()
