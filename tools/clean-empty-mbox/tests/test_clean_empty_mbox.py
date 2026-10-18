import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from clean_empty_mbox import clean_tree


class CleanEmptyMboxTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def _touch(self, relative: str, content: bytes = b"") -> Path:
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return path

    def test_deletes_empty_mbox_and_msf(self) -> None:
        self._touch("Trash")
        self._touch("Trash.msf", b"index")

        clean_tree(self.root)

        self.assertFalse((self.root / "Trash").exists())
        self.assertFalse((self.root / "Trash.msf").exists())

    def test_keeps_empty_mbox_when_sbd_has_children(self) -> None:
        self._touch("Inbox")
        self._touch("Inbox.sbd/Sub", b"From x\n")

        clean_tree(self.root)

        self.assertTrue((self.root / "Inbox").exists())
        self.assertTrue((self.root / "Inbox.sbd/Sub").exists())

    def test_deletes_empty_mbox_then_its_empty_sbd(self) -> None:
        self._touch("Spam")
        self._touch("Spam.msf", b"index")
        (self.root / "Spam.sbd").mkdir()

        clean_tree(self.root)

        self.assertFalse((self.root / "Spam").exists())
        self.assertFalse((self.root / "Spam.msf").exists())
        self.assertFalse((self.root / "Spam.sbd").exists())

    def test_cascades_nested_empty_folders_deepest_first(self) -> None:
        self._touch("A")
        self._touch("A.sbd/B")
        (self.root / "A.sbd" / "B.sbd").mkdir(parents=True)

        clean_tree(self.root)

        self.assertFalse((self.root / "A").exists())
        self.assertFalse((self.root / "A.sbd").exists())

    def test_keeps_nonempty_mbox_and_foreign_files(self) -> None:
        self._touch("Sent", b"From x\n")
        self._touch("panacea.dat")
        self._touch("Inbox.sbd/Stuff", b"From y\n")

        clean_tree(self.root)

        self.assertTrue((self.root / "Sent").exists())
        self.assertTrue((self.root / "panacea.dat").exists())
        self.assertTrue((self.root / "Inbox.sbd/Stuff").exists())

    def test_dry_run_removes_nothing(self) -> None:
        self._touch("Trash")
        self._touch("Trash.msf", b"index")

        removed = clean_tree(self.root, dry_run=True)

        self.assertEqual(removed, [self.root / "Trash"])
        self.assertTrue((self.root / "Trash").exists())
        self.assertTrue((self.root / "Trash.msf").exists())


if __name__ == "__main__":
    unittest.main()
