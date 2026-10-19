import base64
import importlib.util
import io
import tempfile
import sys
import unittest
import mailbox
import quopri
from pathlib import Path
from unittest.mock import patch
from email import policy
from email.parser import BytesParser

# Dash-named CLI script: load it as importable module "mbox_encoding_fix".
_spec = importlib.util.spec_from_file_location(
    "mbox_encoding_fix",
    Path(__file__).resolve().parents[1] / "mbox-encoding-fix.py",
)
check_encoding = importlib.util.module_from_spec(_spec)
sys.modules["mbox_encoding_fix"] = check_encoding
_spec.loader.exec_module(check_encoding)

Finding = check_encoding.Finding
add_correction_headers = check_encoding.add_correction_headers
add_suspect_headers = check_encoding.add_suspect_headers
check_tree = check_encoding.check_tree
inspect_text = check_encoding.inspect_text
main = check_encoding.main
repair_mojibake = check_encoding.repair_mojibake
repair_message = check_encoding.repair_message


class EncodingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.output_directory = tempfile.TemporaryDirectory()
        self.output_root = Path(self.output_directory.name)

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()
        self.output_directory.cleanup()

    def write_mbox(self, relative_path: str, message: bytes) -> Path:
        path = self.root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(message)
        return path

    def test_detects_mojibake_in_subject_sender_and_body(self) -> None:
        self.write_mbox(
            "Local Folders/Inbox",
            b"From sender@example.com Sat Jan  1 00:00:00 2022\n"
            b"From: =?utf-8?b?Sm9zw4PCqQ==?= <jose@example.com>\n"
            b"Subject: =?utf-8?b?Q2Fmw4PCqQ==?=\n"
            b"Content-Type: text/plain; charset=utf-8\n\n"
            b"Bonjour, j'ai mang\xc3\x83\xc2\xa9.\n",
        )

        count, findings = check_tree(self.root)

        self.assertEqual(count, 1)
        self.assertEqual(
            {finding.field for finding in findings},
            {"subject", "sender", "body (text/plain)"},
        )
        self.assertTrue(all("mojibake" in finding.problem for finding in findings))

    def test_detects_invalid_declared_charset_but_ignores_attachment(self) -> None:
        self.write_mbox(
            "Inbox",
            b"From sender@example.com Sat Jan  1 00:00:00 2022\n"
            b"Subject: test\n"
            b"MIME-Version: 1.0\n"
            b"Content-Type: multipart/mixed; boundary=x\n\n"
            b"--x\nContent-Type: text/plain; charset=ascii\n\n"
            b"bad: \xff\n"
            b"--x\nContent-Type: text/plain; name=attached.txt\n"
            b"Content-Disposition: attachment; filename=attached.txt\n"
            b"Content-Transfer-Encoding: base64\n\n"
            b"/w==\n"
            b"--x\nContent-Type: multipart/mixed; boundary=y\n"
            b"Content-Disposition: attachment; filename=attached.eml\n\n"
            b"--y\nContent-Type: text/plain; charset=utf-8\n\n"
            b"Caf\xc3\x83\xc2\xa9\n"
            b"--y--\n--x--\n",
        )

        count, findings = check_tree(self.root)

        self.assertEqual(count, 1)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].field, "body (text/plain)")
        self.assertIn("invalid for ascii", findings[0].problem)

    def test_clean_unicode_text_is_not_flagged(self) -> None:
        findings = inspect_text("Café — déjà vu", Path("Inbox"), 1, "subject")

        self.assertEqual(findings, [])

    def test_replacement_character_excerpt_shows_error_context(self) -> None:
        text = (
            "un texte sans problème " * 20
            + "Retrouvez l\ufffdensemble de nos biens sur citya.com"
            + " texte après " * 20
        )

        findings = inspect_text(text, Path("Inbox"), 1, "body (text/html)")

        replacement_finding = next(
            finding for finding in findings if "U+FFFD" in finding.problem
        )
        self.assertIn("Retrouvez l\ufffdensemble", replacement_finding.excerpt)
        self.assertLess(len(replacement_finding.excerpt), len(text))
        self.assertTrue(replacement_finding.excerpt.startswith("..."))
        self.assertTrue(replacement_finding.excerpt.endswith("..."))

    def test_mojibake_detection_avoids_common_french_words(self) -> None:
        clean_text = "À cet âge, il préfère le théâtre et la poésie."
        findings = inspect_text(clean_text, Path("Inbox"), 1, "body")

        self.assertEqual(findings, [])

    def test_repairs_only_reversible_mojibake(self) -> None:
        self.assertEqual(repair_mojibake("FranÃ§ais â€™ texte"), "Français ’ texte")
        self.assertEqual(
            repair_mojibake('Déjà vu; title="DÃ©sinscription"; coût €'),
            'Déjà vu; title="Désinscription"; coût €',
        )
        self.assertEqual(
            repair_mojibake("Привет, FranÃ§ais 😀"),
            "Привет, Français 😀",
        )
        mojibake_c_cedilla = bytes.fromhex("c383c2a7").decode("utf-8")
        c_cedilla = bytes.fromhex("c3a7").decode("utf-8")
        self.assertEqual(
            repair_mojibake(f"{mojibake_c_cedilla}\ufffd"),
            f"{c_cedilla}\ufffd",
        )
        mojibake_e_acute = bytes.fromhex("c383c2a9").decode("utf-8")
        e_acute = bytes.fromhex("c3a9").decode("utf-8")
        self.assertEqual(
            repair_mojibake(f"{mojibake_e_acute} lost \ufffd"),
            f"{e_acute} lost \ufffd",
        )
        mojibake_i_umlaut = bytes.fromhex("c38f").decode("latin-1")
        i_umlaut = bytes.fromhex("c38f").decode("utf-8")
        self.assertEqual(
            repair_mojibake(f"FO{mojibake_i_umlaut}S"),
            f"FO{i_umlaut}S",
        )

    def test_partial_repair_stays_suspect_if_replacement_character_remains(self) -> None:
        source = self.write_mbox(
            "partially-repairable",
            b"From sender@example.com Sat Jan  1 00:00:00 2022\n"
            b"Subject: message\n"
            b"Content-Type: text/plain; charset=utf-8\n"
            b"Content-Transfer-Encoding: quoted-printable\n\n"
            b"Caf=C3=83=C2=A9 et perdu =EF=BF=BD\n",
        )
        suspects = self.output_root / "suspects.mbox"
        corrected = self.output_root / "corrected.mbox"

        count, findings = check_tree(
            source,
            suspects_mbox=suspects,
            corrected_mbox=corrected,
        )

        self.assertEqual(count, 1)
        self.assertTrue(any("possible mojibake" in f.problem for f in findings))
        self.assertTrue(any("U+FFFD" in f.problem for f in findings))
        parser = BytesParser(policy=policy.default)
        suspect_store = mailbox.mbox(
            suspects, factory=lambda stream: parser.parse(stream)
        )
        corrected_store = mailbox.mbox(
            corrected, factory=lambda stream: parser.parse(stream)
        )
        try:
            self.assertEqual(len(suspect_store), 1)
            suspect_message = parser.parsebytes(suspect_store.get_file(0).read())
            suspect_body = suspect_message.get_content()
            self.assertEqual(
                [ord(character) for character in suspect_body[:4]],
                [67, 97, 102, 233],
            )
            self.assertIn("\ufffd", suspect_body)
            self.assertTrue(
                any(
                    "U+FFFD" in str(header)
                    for header in suspect_message.get_all(
                        "X-Encoding-Suspect", []
                    )
                )
            )
            self.assertFalse(
                any(
                    "possible mojibake" in str(header)
                    for header in suspect_message.get_all(
                        "X-Encoding-Suspect", []
                    )
                )
            )
            self.assertTrue(
                any(
                    "repaired reversible mojibake" in str(header)
                    for header in suspect_message.get_all(
                        "X-Encoding-Correction", []
                    )
                )
            )
            self.assertEqual(len(corrected_store), 0)
        finally:
            suspect_store.close()
            corrected_store.close()

    def test_corrected_mbox_decodes_unknown_8bit_rfc2047_header(self) -> None:
        source = self.write_mbox(
            "unknown-8bit",
            b"From sender@example.com Sat Jan  1 00:00:00 2022\n"
            b"Subject: Net@scope =?unknown-8bit?q?Actualit=E9s?= wow !\n"
            b"Content-Type: text/plain; charset=utf-8\n\n"
            b"Hello\n",
        )
        corrected = self.output_root / "unknown-8bit-fixed.mbox"

        count, findings = check_tree(source, corrected_mbox=corrected)

        self.assertEqual(count, 1)
        self.assertEqual(findings, [])
        parser = BytesParser(policy=policy.default)
        corrected_store = mailbox.mbox(
            corrected, factory=lambda stream: parser.parse(stream)
        )
        try:
            fixed_message = parser.parsebytes(corrected_store.get_file(0).read())
        finally:
            corrected_store.close()
        self.assertEqual(
            str(fixed_message["Subject"]),
            "Net@scope Actualités wow !",
        )
        corrections = fixed_message.get_all(
            "X-Encoding-Correction", []
        )
        self.assertTrue(
            any("Subject: decoded RFC-2047" in str(value) for value in corrections)
        )

    def test_valid_utf8_html_is_not_flagged_for_mojibake(self) -> None:
        html = 'Déjà vu; title="DÃ©sinscription"; coût €'
        source = self.write_mbox(
            "mixed-unicode-html",
            b"From sender@example.com Sat Jan  1 00:00:00 2022\n"
            b"Subject: message\n"
            b"Content-Type: text/html; charset=utf-8\n\n"
            + html.encode("utf-8")
            + b"\n",
        )
        corrected = self.output_root / "mixed-unicode-html-fixed.mbox"
        suspects = self.output_root / "mixed-unicode-html-suspects.mbox"

        count, findings = check_tree(
            source,
            suspects_mbox=suspects,
            corrected_mbox=corrected,
        )

        self.assertEqual(count, 1)
        self.assertEqual(findings, [])
        parser = BytesParser(policy=policy.default)
        suspect_store = mailbox.mbox(suspects)
        corrected_store = mailbox.mbox(
            corrected, factory=lambda stream: parser.parse(stream)
        )
        try:
            self.assertEqual(len(suspect_store), 0)
            self.assertEqual(len(corrected_store), 0)
        finally:
            suspect_store.close()
            corrected_store.close()

    def test_recovers_replacement_from_matching_html_alternative(self) -> None:
        plain = (
            "Votre compte de règlement se trouve au Compte Ch\ufffdque, "
            "référence finale 12345."
        )
        html_body = (
            "<p>Votre compte de règlement se trouve au Compte Chèque, "
            "référence finale 12345.</p>"
        )
        source = self.write_mbox(
            "recoverable-replacement",
            b"From sender@example.com Sat Jan  1 00:00:00 2022\n"
            b"Subject: message\n"
            b"MIME-Version: 1.0\n"
            b"Content-Type: multipart/alternative; boundary=x\n\n"
            b"--x\nContent-Type: text/plain; charset=utf-8\n\n"
            + plain.encode("utf-8")
            + b"\n--x\nContent-Type: text/html; charset=utf-8\n\n"
            + html_body.encode("utf-8")
            + b"\n--x--\n",
        )
        suspects = self.output_root / "recoverable-replacement-suspects.mbox"
        corrected = self.output_root / "recoverable-replacement-corrected.mbox"

        count, findings = check_tree(
            source,
            suspects_mbox=suspects,
            corrected_mbox=corrected,
        )

        self.assertEqual(count, 1)
        self.assertTrue(any("U+FFFD" in finding.problem for finding in findings))
        parser = BytesParser(policy=policy.default)
        suspect_store = mailbox.mbox(suspects)
        corrected_store = mailbox.mbox(
            corrected, factory=lambda stream: parser.parse(stream)
        )
        try:
            self.assertEqual(len(suspect_store), 0)
            fixed_message = parser.parsebytes(corrected_store.get_file(0).read())
        finally:
            suspect_store.close()
            corrected_store.close()
        self.assertIn("Compte Chèque", fixed_message.get_body(("plain",)).get_content())
        corrections = fixed_message.get_all(
            "X-Encoding-Correction", []
        )
        self.assertTrue(
            any(
                "recovered 1 replacement character(s) from HTML body" in str(value)
                for value in corrections
            )
        )

    def test_recovers_replacements_from_html_alternative_with_markup_in_plain_part(self) -> None:
        plain = (
            "MESSAGE IMPORTANT\n\n"
            "Prochainement votre Assembl\ufffde G\ufffdn\ufffdrale\n\n"
            "<a href=\"https://example.com\">"
            "Si vous ne parvenez pas &agrave; visualiser cet email, cliquez ici"
            "</a>\n\n"
            "Ch\ufffdre soci\ufffdtaires, référence finale 12345."
        )
        html_body = (
            "<html><body><p>MESSAGE IMPORTANT</p>"
            "<p>Prochainement votre Assemblée Générale</p>"
            "<a href=\"https://example.com\">"
            "Si vous ne parvenez pas à visualiser cet email, cliquez ici"
            "</a><p>Chère sociétaires, référence finale 12345.</p>"
            "</body></html>"
        )
        source = self.write_mbox(
            "recoverable-markup-replacement",
            b"From sender@example.com Sat Jan  1 00:00:00 2022\n"
            b"Subject: message\n"
            b"MIME-Version: 1.0\n"
            b"Content-Type: multipart/alternative; boundary=x\n\n"
            b"--x\nContent-Type: text/plain; charset=utf-8\n\n"
            + plain.encode("utf-8")
            + b"\n--x\nContent-Type: text/html; charset=utf-8\n\n"
            + html_body.encode("utf-8")
            + b"\n--x--\n",
        )
        suspects = self.output_root / "recoverable-markup-suspects.mbox"
        corrected = self.output_root / "recoverable-markup-corrected.mbox"

        count, _ = check_tree(
            source,
            suspects_mbox=suspects,
            corrected_mbox=corrected,
        )

        self.assertEqual(count, 1)
        parser = BytesParser(policy=policy.default)
        suspect_store = mailbox.mbox(suspects)
        corrected_store = mailbox.mbox(
            corrected, factory=lambda stream: parser.parse(stream)
        )
        try:
            self.assertEqual(len(suspect_store), 0)
            fixed_message = parser.parsebytes(corrected_store.get_file(0).read())
        finally:
            suspect_store.close()
            corrected_store.close()
        fixed_plain = fixed_message.get_body(("plain",)).get_content()
        self.assertIn("Assemblée Générale", fixed_plain)
        self.assertIn("Chère sociétaires", fixed_plain)

    def test_does_not_guess_between_different_matching_words(self) -> None:
        plain = "This is a c\ufffdt marker string with enough surrounding context."
        html_body = (
            "<p>This is a cat marker string with enough surrounding context.</p>"
            "<p>This is a cut marker string with enough surrounding context.</p>"
        )
        source = self.write_mbox(
            "ambiguous-alternative-replacement",
            b"From sender@example.com Sat Jan  1 00:00:00 2022\n"
            b"Subject: message\n"
            b"MIME-Version: 1.0\n"
            b"Content-Type: multipart/alternative; boundary=x\n\n"
            b"--x\nContent-Type: text/plain; charset=utf-8\n\n"
            + plain.encode("utf-8")
            + b"\n--x\nContent-Type: text/html; charset=utf-8\n\n"
            + html_body.encode("utf-8")
            + b"\n--x--\n",
        )
        suspects = self.output_root / "ambiguous-replacement-suspects.mbox"
        corrected = self.output_root / "ambiguous-replacement-corrected.mbox"

        count, findings = check_tree(
            source,
            suspects_mbox=suspects,
            corrected_mbox=corrected,
        )

        self.assertEqual(count, 1)
        self.assertTrue(any("U+FFFD" in finding.problem for finding in findings))

    def test_binary_like_text_part_is_reported_but_left_unchanged(self) -> None:
        binary_like = b"\x00" * 32 + b"opaque\xffdata" * 20
        source = self.write_mbox(
            "binary-like-text-part",
            b"From sender@example.com Sat Jan  1 00:00:00 2022\n"
            b"Subject: message\n"
            b"Content-Type: text/plain; charset=utf-8\n"
            b"Content-Transfer-Encoding: base64\n\n"
            + base64.b64encode(binary_like)
            + b"\n",
        )
        suspects = self.output_root / "binary-like-suspects.mbox"
        corrected = self.output_root / "binary-like-corrected.mbox"

        count, findings = check_tree(
            source,
            suspects_mbox=suspects,
            corrected_mbox=corrected,
        )

        self.assertEqual(count, 1)
        self.assertTrue(any("opaque binary-like content" in f.problem for f in findings))
        parser = BytesParser(policy=policy.default)
        suspect_store = mailbox.mbox(
            suspects, factory=lambda stream: parser.parse(stream)
        )
        try:
            suspect_message = parser.parsebytes(suspect_store.get_file(0).read())
        finally:
            suspect_store.close()
        self.assertEqual(
            suspect_message.get_payload(decode=True),
            binary_like,
        )

    def test_corrected_mbox_repairs_unknown_8bit_sender_without_false_finding(self) -> None:
        source = self.write_mbox(
            "unknown-8bit-sender",
            b"From sender@example.com Sat Jan  1 00:00:00 2022\n"
            b"From: =?unknown-8bit?q?R=E9mi?= Peyronnet "
            b"<peyronr2@cti.ecp.fr>\n"
            b"Subject: Test\n\n"
            b"Message body\n",
        )
        corrected = self.output_root / "unknown-8bit-sender-fixed.mbox"

        count, findings = check_tree(source, corrected_mbox=corrected)

        self.assertEqual(count, 1)
        self.assertEqual(findings, [])
        parser = BytesParser(policy=policy.default)
        corrected_store = mailbox.mbox(
            corrected, factory=lambda stream: parser.parse(stream)
        )
        try:
            fixed_message = parser.parsebytes(corrected_store.get_file(0).read())
        finally:
            corrected_store.close()
        self.assertEqual(
            str(fixed_message["From"]),
            "Rémi Peyronnet <peyronr2@cti.ecp.fr>",
        )
        corrections = fixed_message.get_all(
            "X-Encoding-Correction", []
        )
        self.assertTrue(
            any("From: decoded RFC-2047" in str(value) for value in corrections)
        )

    def test_corrected_mbox_repairs_utf8_bytes_misread_as_latin1(self) -> None:
        source = self.write_mbox(
            "mixed-latin1-utf8",
            b"From sender@example.com Sat Jan  1 00:00:00 2022\n"
            b"Subject: message\n"
            b"Content-Type: text/plain; charset=iso-8859-1\n\n"
            b"Cinema Marina FO\xc3\x8fS\n",
        )
        suspects = self.output_root / "latin1-suspects.mbox"
        corrected = self.output_root / "latin1-corrected.mbox"

        count, findings = check_tree(
            source,
            suspects_mbox=suspects,
            corrected_mbox=corrected,
        )

        self.assertEqual(count, 1)
        self.assertTrue(any("possible mojibake" in f.problem for f in findings))
        parser = BytesParser(policy=policy.default)
        suspect_store = mailbox.mbox(suspects)
        corrected_store = mailbox.mbox(
            corrected, factory=lambda stream: parser.parse(stream)
        )
        try:
            self.assertEqual(len(suspect_store), 0)
            self.assertEqual(len(corrected_store), 1)
            fixed_message = parser.parsebytes(corrected_store.get_file(0).read())
        finally:
            suspect_store.close()
            corrected_store.close()
        expected_i_umlaut = bytes.fromhex("c38f").decode("utf-8")
        self.assertIn(
            f"FO{expected_i_umlaut}S",
            fixed_message.get_content(),
        )

    def test_corrected_mbox_decodes_x_user_defined_q_header(self) -> None:
        source = self.write_mbox(
            "x-user-defined",
            b"From sender@example.com Sat Jan  1 00:00:00 2022\n"
            b"Subject: =?x-user-defined?Q?David_M=E9neret?=\n\n"
            b"Message body\n",
        )
        corrected = self.output_root / "x-user-defined-fixed.mbox"

        count, findings = check_tree(source, corrected_mbox=corrected)

        self.assertEqual(count, 1)
        self.assertEqual(findings, [])
        parser = BytesParser(policy=policy.default)
        corrected_store = mailbox.mbox(
            corrected, factory=lambda stream: parser.parse(stream)
        )
        try:
            fixed_message = parser.parsebytes(corrected_store.get_file(0).read())
        finally:
            corrected_store.close()
        self.assertEqual(str(fixed_message["Subject"]), "David_Méneret")

    def test_corrected_mbox_unfolds_folded_header_before_repair(self) -> None:
        source = self.write_mbox(
            "folded-header",
            b"From sender@example.com Sat Jan  1 00:00:00 2022\n"
            b"Subject: =?utf-8?q?Caf=C3=83=C2=A9?=\r\n"
            b"  historique\n\n"
            b"Message body\n",
        )
        corrected = self.output_root / "folded-header-fixed.mbox"

        count, findings = check_tree(source, corrected_mbox=corrected)

        self.assertEqual(count, 1)
        self.assertTrue(any(finding.field == "subject" for finding in findings))
        parser = BytesParser(policy=policy.default)
        corrected_store = mailbox.mbox(
            corrected, factory=lambda stream: parser.parse(stream)
        )
        try:
            fixed_message = parser.parsebytes(corrected_store.get_file(0).read())
        finally:
            corrected_store.close()
        self.assertEqual(str(fixed_message["Subject"]), "Café historique")

    def test_uses_windows_1252_as_preview_when_utf8_is_invalid(self) -> None:
        mbox = self.write_mbox(
            "legacy",
            b"From sender@example.com Sat Jan  1 00:00:00 2022\n"
            b"Subject: legacy\nContent-Type: text/plain\n\n"
            b"Caf\xe9\n",
        )

        _, findings = check_tree(mbox)

        self.assertEqual(len(findings), 1)
        self.assertIn("Windows-1252", findings[0].problem)
        self.assertIn("Café", findings[0].excerpt)
        self.assertNotIn("\ufffd", findings[0].excerpt)

    def test_readable_legacy_text_mislabeled_ascii_is_not_suspect(self) -> None:
        body = (
            "Voilà le planning de perm, première version. "
            "Manquent quelques personnes qui ne m'ont pas mailé. "
            "Comme vous pourrez le constater, le texte est lisible en français. "
        ).encode("cp1252")
        encoded_body = quopri.encodestring(body)
        mbox = self.write_mbox(
            "legacy-ascii",
            b"From sender@example.com Sat Jan  1 00:00:00 2022\n"
            b"Subject: planning\n"
            b"Content-Type: text/plain; charset=US-ASCII\n"
            b"Content-Transfer-Encoding: quoted-printable\n\n"
            + encoded_body
            + b"\n",
        )

        count, findings = check_tree(mbox)

        self.assertEqual(count, 1)
        self.assertEqual(findings, [])

    def test_auxiliary_files_are_not_treated_as_mailboxes(self) -> None:
        (self.root / "Inbox.msf").write_bytes(b"From not-a-message\n")
        (self.root / "notes.txt").write_text("not an mbox")

        count, findings = check_tree(self.root)

        self.assertEqual((count, findings), (0, []))

    def test_checks_a_single_mbox_file(self) -> None:
        mbox = self.write_mbox(
            "single.mbox",
            b"From sender@example.com Sat Jan  1 00:00:00 2022\n"
            b"Subject: =?utf-8?b?Q2Fmw4PCqQ==?=\n"
            b"Content-Type: text/plain; charset=utf-8\n\n"
            b"Hello\n",
        )

        count, findings = check_tree(mbox)

        self.assertEqual(count, 1)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].mailbox, mbox)

    def test_rejects_non_mbox_file_input(self) -> None:
        not_a_mailbox = self.root / "notes.txt"
        not_a_mailbox.write_text("not an mbox")

        with self.assertRaisesRegex(ValueError, "Not an mbox file"):
            check_tree(not_a_mailbox)

    def test_single_mbox_can_export_suspects_without_overwriting_it(self) -> None:
        mbox = self.write_mbox(
            "single.mbox",
            b"From sender@example.com Sat Jan  1 00:00:00 2022\n"
            b"Subject: =?utf-8?b?Q2Fmw4PCqQ==?=\n"
            b"Content-Type: text/plain; charset=utf-8\n\n"
            b"Hello\n",
        )
        output = self.output_root / "suspects.mbox"

        count, findings = check_tree(mbox, output)

        self.assertEqual(count, 1)
        self.assertEqual(len(findings), 1)
        suspect_store = mailbox.mbox(output)
        try:
            self.assertEqual(len(suspect_store), 1)
        finally:
            suspect_store.close()

        with self.assertRaisesRegex(ValueError, "must not overwrite the input"):
            check_tree(mbox, mbox)

    def test_in_place_repairs_only_corrected_messages_and_preserves_others(self) -> None:
        mbox = self.write_mbox(
            "in-place.mbox",
            b"From first@example.com Sat Jan  1 00:00:00 2022\n"
            b"Subject: =?utf-8?b?Q2Fmw4PCqQ==?=\n"
            b"Content-Type: text/plain; charset=utf-8\n\n"
            b"Fran\xc3\x83\xc2\xa7ais\n"
            b"From second@example.com Sun Jan  2 00:00:00 2022\n"
            b"Subject: untouched\n"
            b"X-Preserved: exact header\n\n"
            b"Body stays unchanged\n",
        )
        original_bytes = mbox.read_bytes()
        untouched_message = (
            b"From second@example.com Sun Jan  2 00:00:00 2022\n"
            b"Subject: untouched\n"
            b"X-Preserved: exact header\n\n"
            b"Body stays unchanged\n"
        )

        count, findings = check_tree(mbox, in_place=True)

        self.assertEqual(count, 2)
        self.assertTrue(findings)
        self.assertNotEqual(mbox.read_bytes(), original_bytes)
        self.assertTrue(
            mbox.read_bytes().startswith(
                b"From first@example.com Sat Jan  1 00:00:00 2022\r\n"
            )
        )
        self.assertIn(untouched_message, mbox.read_bytes())
        parser = BytesParser(policy=policy.default)
        store = mailbox.mbox(mbox, factory=lambda stream: parser.parse(stream))
        try:
            self.assertEqual(len(store), 2)
            fixed_message = store[0]
            self.assertEqual(fixed_message["Subject"], "Café")
            self.assertEqual(fixed_message.get_content(), "Français\n")
            self.assertTrue(fixed_message.get_all("X-Encoding-Correction"))
        finally:
            store.close()
        self.assertEqual(list(mbox.parent.glob(f".{mbox.name}.*.tmp")), [])
        self.assertEqual(list(mbox.parent.glob(f".{mbox.name}.*.bak")), [])

    def test_in_place_writes_when_subject_encoded_word_splits_multibyte_char(
        self,
    ) -> None:
        mbox = self.write_mbox(
            "split-encoded-word.mbox",
            b"From first@example.com Sat Jan  1 00:00:00 2022\n"
            b"Subject: =?UTF-8?Q?Votre_demande_Carrefour_Drive_"
            b"n=C2=B0210618-000010_a_bien_=C3?=\n"
            b"    =?UTF-8?Q?=A9t=C3=A9_prise_en_compte.?=\n"
            b"Content-Type: text/plain; charset=utf-8\n\n"
            b"Fran\xc3\x83\xc2\xa7ais\n",
        )

        count, findings = check_tree(mbox, in_place=True, only_unresolved=True)

        self.assertEqual(count, 1)
        self.assertEqual(findings, [])
        parser = BytesParser(policy=policy.default)
        store = mailbox.mbox(mbox, factory=lambda stream: parser.parse(stream))
        try:
            fixed_message = store[0]
            self.assertEqual(fixed_message.get_content(), "Français\n")
        finally:
            store.close()

    def test_in_place_saves_partial_repairs_only_when_requested(self) -> None:
        original = (
            b"From sender@example.com Sat Jan  1 00:00:00 2022\n"
            b"Subject: partial\n"
            b"Content-Type: text/plain; charset=utf-8\n\n"
            b"Soci\xc3\xa9t\xc3\xa9 coop\xc3\xa9rative \xef\xbf\xbd capital variable; "
            b"un autre caract\xc3\xa8re perdu: \xef\xbf\xbd\n"
        )
        mbox = self.write_mbox("in-place-partial.mbox", original)

        _, findings = check_tree(mbox, in_place=True)

        self.assertTrue(any("U+FFFD" in finding.problem for finding in findings))
        self.assertEqual(mbox.read_bytes(), original)

        stdout = io.StringIO()
        stderr = io.StringIO()
        with patch("sys.stdout", stdout), patch("sys.stderr", stderr):
            result = main(
                ["--in-place", "--in-place-partial", str(mbox)]
            )

        self.assertEqual(result, 1)
        self.assertIn("Applied safe in-place corrections", stdout.getvalue())
        self.assertIn("replacement character (U+FFFD)", stdout.getvalue())
        self.assertTrue(any("U+FFFD" in finding.problem for finding in findings))
        parser = BytesParser(policy=policy.default)
        store = mailbox.mbox(mbox, factory=lambda stream: parser.parse(stream))
        try:
            body = store[0].get_content()
            self.assertIn("Société coopérative à capital variable", body)
            self.assertIn("un autre caractère perdu: \ufffd", body)
            self.assertTrue(store[0].get_all("X-Encoding-Correction"))
        finally:
            store.close()

    def test_in_place_partial_option_requires_in_place(self) -> None:
        with self.assertRaisesRegex(ValueError, "requires in_place=True"):
            check_tree(self.root, in_place_partial=True)

    def test_in_place_scan_failure_leaves_original_mailboxes_unchanged(self) -> None:
        first = self.write_mbox(
            "Inbox",
            b"From first@example.com Sat Jan  1 00:00:00 2022\n"
            b"Subject: =?utf-8?b?Q2Fmw4PCqQ==?=\n\nBody\n",
        )
        second = self.write_mbox(
            "Archive",
            b"From second@example.com Sat Jan  1 00:00:00 2022\n"
            b"Subject: =?utf-8?b?Q2Fmw4PCqQ==?=\n\nBody\n",
        )
        originals = {path: path.read_bytes() for path in (first, second)}

        original_repair_message = repair_message
        repair_calls = 0

        def fail_on_second_message(message):
            nonlocal repair_calls
            repair_calls += 1
            if repair_calls == 2:
                raise OSError("repair failed")
            return original_repair_message(message)

        with patch("mbox_encoding_fix.repair_message", side_effect=fail_on_second_message):
            with self.assertRaisesRegex(OSError, "repair failed"):
                check_tree(self.root, in_place=True)

        self.assertEqual({path: path.read_bytes() for path in originals}, originals)
        self.assertEqual(list(self.root.rglob(".*.tmp")), [])
        self.assertEqual(list(self.root.rglob(".*.bak")), [])

    def test_cli_in_place_option_updates_source_mbox(self) -> None:
        mbox = self.write_mbox(
            "cli-in-place.mbox",
            b"From sender@example.com Sat Jan  1 00:00:00 2022\n"
            b"Message-ID: <encoding-check-1@example.com>\n"
            b"Subject: =?utf-8?b?Q2Fmw4PCqQ==?=\n\nBody\n",
        )
        stdout = io.StringIO()
        stderr = io.StringIO()

        with patch("sys.stdout", stdout), patch("sys.stderr", stderr):
            result = main(["--in-place", str(mbox)])

        self.assertEqual(result, 0)
        self.assertIn("Applied safe in-place corrections", stdout.getvalue())
        self.assertIn("found 0 unresolved issue(s)", stdout.getvalue())
        self.assertNotIn("body (text/plain):", stdout.getvalue())
        self.assertIn(f"Correction: {mbox} [message 1]", stdout.getvalue())
        self.assertIn("Message-ID: <encoding-check-1@example.com>", stdout.getvalue())
        self.assertIn("Subject: Café", stdout.getvalue())
        self.assertIn("Subject: repaired reversible mojibake", stdout.getvalue())
        store = mailbox.mbox(
            mbox,
            factory=lambda stream: BytesParser(policy=policy.default).parse(stream),
        )
        try:
            self.assertEqual(store[0]["Subject"], "Café")
        finally:
            store.close()

    def test_corrected_mbox_repairs_mojibake_and_legacy_charset_safely(self) -> None:
        source = self.write_mbox(
            "Inbox",
            b"From one@example.com Sat Jan  1 00:00:00 2022\n"
            b"From: =?utf-8?q?Fran=C3=83=C2=A7ois?= <one@example.com>\n"
            b"Subject: =?utf-8?q?Fran=C3=83=C2=A7ais?=\n"
            b"MIME-Version: 1.0\n"
            b"Content-Type: multipart/mixed; boundary=x\n\n"
            b"--x\nContent-Type: text/plain; charset=utf-8\n\n"
            b"Fran\xc3\x83\xc2\xa7ais\n"
            b"--x\nContent-Type: application/octet-stream; name=file.bin\n"
            b"Content-Disposition: attachment; filename=file.bin\n"
            b"Content-Transfer-Encoding: base64\n\n"
            b"AAEC/w==\n--x--\n"
            b"From two@example.com Sat Jan  1 00:00:01 2022\n"
            b"Subject: legacy\nContent-Type: text/plain; format=flowed\n\n"
            b"Caf\xe9\n"
            b"From three@example.com Sat Jan  1 00:00:02 2022\n"
            b"Subject: already lost\nContent-Type: text/plain; charset=utf-8\n\n"
            b"bad: \xef\xbf\xbd\n",
        )
        corrected = self.output_root / "corrected.mbox"
        original_contents = source.read_bytes()

        _, findings = check_tree(
            source,
            corrected_mbox=corrected,
        )

        self.assertTrue(findings)
        self.assertEqual(source.read_bytes(), original_contents)
        parser = BytesParser(policy=policy.default)
        corrected_store = mailbox.mbox(
            corrected, factory=lambda stream: parser.parse(stream)
        )
        try:
            self.assertEqual(len(corrected_store), 2)
            messages = [
                parser.parsebytes(corrected_store.get_file(i).read())
                for i in range(2)
            ]
        finally:
            corrected_store.close()
        first = messages[0]
        self.assertIn("François", str(first["From"]))
        self.assertEqual(str(first["Subject"]), "Français")
        self.assertEqual(first.get_payload()[0].get_content().strip(), "Français")
        corrections = first.get_all("X-Encoding-Correction", [])
        self.assertTrue(
            any("repaired reversible mojibake" in str(value) for value in corrections)
        )
        self.assertTrue(
            any("text/plain: decoded as UTF-8" in str(value) for value in corrections)
        )
        self.assertEqual(
            first.get_payload()[1].get_payload(decode=True),
            b"\x00\x01\x02\xff",
        )
        second = messages[1]
        self.assertEqual(second.get_content_charset(), "utf-8")
        self.assertEqual(second.get_param("format"), "flowed")
        self.assertEqual(second.get_content().strip(), "Café")

    def test_suspects_mbox_excludes_messages_also_written_as_corrected(self) -> None:
        source = self.write_mbox(
            "Inbox",
            b"From repaired@example.com Sat Jan  1 00:00:00 2022\n"
            b"Subject: =?utf-8?q?Caf=C3=83=C2=A9?=\n"
            b"Content-Type: text/plain; charset=utf-8\n\n"
            b"Hello\n"
            b"From unrepaired@example.com Sat Jan  1 00:00:01 2022\n"
            b"Subject: bad encoding\n"
            b"Content-Type: text/plain; charset=ascii\n\n"
            b"bad: \xef\xbf\xbd\n",
        )
        suspects = self.output_root / "suspects.mbox"
        corrected = self.output_root / "corrected.mbox"

        _, findings = check_tree(
            source,
            suspects_mbox=suspects,
            corrected_mbox=corrected,
        )

        self.assertGreaterEqual(len(findings), 2)
        parser = BytesParser(policy=policy.default)
        suspect_store = mailbox.mbox(
            suspects, factory=lambda stream: parser.parse(stream)
        )
        corrected_store = mailbox.mbox(
            corrected, factory=lambda stream: parser.parse(stream)
        )
        try:
            self.assertEqual(len(suspect_store), 1)
            self.assertEqual(
                str(suspect_store.get_message(0)["Subject"]),
                "bad encoding",
            )
            suspect_headers = suspect_store.get_message(0).get_all(
                "X-Encoding-Suspect"
            )
            self.assertTrue(suspect_headers)
            self.assertTrue(any("body (text/plain)" in h for h in suspect_headers))
            self.assertTrue(any("U+FFFD" in h for h in suspect_headers))
            self.assertEqual(len(corrected_store), 1)
            self.assertEqual(
                str(
                    parser.parsebytes(
                        corrected_store.get_file(0).read()
                    )["Subject"]
                ),
                "Café",
            )
        finally:
            suspect_store.close()
            corrected_store.close()

    def test_repaired_mbox_uses_html_meta_charset_when_mime_charset_is_bogus(self) -> None:
        source = self.write_mbox(
            "html",
            b"From sender@example.com Sat Jan  1 00:00:00 2022\n"
            b"Subject: html\n"
            b"Content-Type: text/html; charset=charset\n\n"
            b'<html><head><meta charset="windows-1252"></head><body>Caf\xe9</body></html>\n',
        )
        corrected = self.output_root / "corrected-html.mbox"

        _, findings = check_tree(source, corrected_mbox=corrected)

        self.assertTrue(any("unknown declared charset" in f.problem for f in findings))
        parser = BytesParser(policy=policy.default)
        corrected_store = mailbox.mbox(
            corrected, factory=lambda stream: parser.parse(stream)
        )
        try:
            message = parser.parsebytes(corrected_store.get_file(0).read())
        finally:
            corrected_store.close()
        self.assertEqual(message.get_content_charset(), "utf-8")
        self.assertIn("Café", message.get_content())

    def test_html_meta_charset_takes_precedence_over_mime_charset(self) -> None:
        source = self.write_mbox(
            "html-charset-mismatch",
            b"From sender@example.com Sat Jan  1 00:00:00 2022\n"
            b"Subject: html mismatch\n"
            b"Content-Type: text/html; charset=utf-8\n\n"
            b'<html><head><meta charset="iso-8859-1"></head>'
            b"<body>Caf\xc3\xa9</body></html>\n",
        )
        suspects = self.output_root / "html-mismatch-suspects.mbox"
        corrected = self.output_root / "html-mismatch-corrected.mbox"

        _, findings = check_tree(
            source,
            suspects_mbox=suspects,
            corrected_mbox=corrected,
        )

        self.assertTrue(
            any("conflicts with HTML meta charset" in f.problem for f in findings)
        )
        parser = BytesParser(policy=policy.default)
        suspects_store = mailbox.mbox(suspects)
        corrected_store = mailbox.mbox(
            corrected, factory=lambda stream: parser.parse(stream)
        )
        try:
            self.assertEqual(len(suspects_store), 0)
            self.assertEqual(len(corrected_store), 1)
            message = parser.parsebytes(corrected_store.get_file(0).read())
        finally:
            suspects_store.close()
            corrected_store.close()

        html = message.get_content()
        self.assertEqual(message.get_content_charset(), "utf-8")
        self.assertIn('<meta charset="utf-8">', html)
        self.assertIn("Café", html)
        corrections = message.get_all("X-Encoding-Correction", [])
        self.assertTrue(
            any(
                "aligned HTML meta charset to UTF-8" in str(value)
                for value in corrections
            )
        )

    def test_html_mime_charset_is_used_when_meta_charset_cannot_decode(self) -> None:
        source = self.write_mbox(
            "html-meta-undecodable",
            b"From sender@example.com Sat Jan  1 00:00:00 2022\n"
            b"Subject: html fallback\n"
            b"Content-Type: text/html; charset=cp1252\n\n"
            b'<html><head><meta charset="utf-8"></head>'
            b"<body>Caf\xe9</body></html>\n",
        )
        corrected = self.output_root / "html-fallback-corrected.mbox"

        _, findings = check_tree(source, corrected_mbox=corrected)

        self.assertTrue(
            any("decoded using Windows-1252" in f.problem for f in findings)
        )
        parser = BytesParser(policy=policy.default)
        corrected_store = mailbox.mbox(
            corrected, factory=lambda stream: parser.parse(stream)
        )
        try:
            self.assertEqual(len(corrected_store), 1)
            message = parser.parsebytes(corrected_store.get_file(0).read())
        finally:
            corrected_store.close()
        self.assertEqual(message.get_content_charset(), "utf-8")
        self.assertIn('<meta charset="utf-8">', message.get_content())
        self.assertIn("Café", message.get_content())
        corrections = message.get_all("X-Encoding-Correction", [])
        self.assertTrue(
            any(
                "changed MIME charset from cp1252 to UTF-8" in str(value)
                for value in corrections
            )
        )

    def test_utf16_bom_takes_precedence_over_unknown_mime_charset(self) -> None:
        html_body = (
            '<html><body><p>Bonjour, Fran\u00e7ais.</p></body></html>\r\n'
        ).encode("utf-16")
        source = self.write_mbox(
            "utf16-html",
            b"From sender@example.com Sat Jan  1 00:00:00 2022\n"
            b"Subject: UTF-16 HTML\n"
            b"Content-Type: text/html; charset=x-user-defined\n\n"
            + html_body,
        )
        corrected = self.output_root / "utf16-corrected.mbox"
        suspects = self.output_root / "utf16-suspects.mbox"

        _, findings = check_tree(
            source,
            suspects_mbox=suspects,
            corrected_mbox=corrected,
        )

        self.assertTrue(any("byte-order mark" in finding.problem for finding in findings))
        parser = BytesParser(policy=policy.default)
        suspect_store = mailbox.mbox(suspects)
        corrected_store = mailbox.mbox(
            corrected, factory=lambda stream: parser.parse(stream)
        )
        try:
            self.assertEqual(len(suspect_store), 0)
            self.assertEqual(len(corrected_store), 1)
            message = parser.parsebytes(corrected_store.get_file(0).read())
        finally:
            suspect_store.close()
            corrected_store.close()
        self.assertEqual(message.get_content_charset(), "utf-8")
        self.assertIn("Bonjour, Fran\u00e7ais.", message.get_content())
        self.assertTrue(
            any(
                "byte-order mark" in str(value)
                for value in message.get_all("X-Encoding-Correction", [])
            )
        )

    def test_html_replacements_are_recovered_from_plain_alternative(self) -> None:
        source = self.write_mbox(
            "html-alternative",
            b"From sender@example.com Sat Jan  1 00:00:00 2022\n"
            b"Subject: alternative\n"
            b"MIME-Version: 1.0\n"
            b"Content-Type: multipart/alternative; boundary=x\n\n"
            b"--x\nContent-Type: text/plain; charset=utf-8\n\n"
            b"Caf\xc3\xa9\n"
            b"--x\nContent-Type: text/html; charset=utf-8\n\n"
            b"<html><body><p>Caf\xef\xbf\xbd</p></body></html>\n"
            b"--x--\n",
        )
        corrected = self.output_root / "html-alternative-corrected.mbox"
        suspects = self.output_root / "html-alternative-suspects.mbox"

        _, findings = check_tree(
            source,
            suspects_mbox=suspects,
            corrected_mbox=corrected,
        )

        self.assertEqual(findings, [])
        parser = BytesParser(policy=policy.default)
        suspect_store = mailbox.mbox(suspects)
        corrected_store = mailbox.mbox(
            corrected, factory=lambda stream: parser.parse(stream)
        )
        try:
            self.assertEqual(len(suspect_store), 0)
            self.assertEqual(len(corrected_store), 1)
            message = parser.parsebytes(corrected_store.get_file(0).read())
        finally:
            suspect_store.close()
            corrected_store.close()
        html_part = next(
            part for part in message.walk() if part.get_content_type() == "text/html"
        )
        self.assertIn("Caf\u00e9", html_part.get_content())
        self.assertTrue(
            any(
                "from text/plain alternative" in str(value)
                for value in message.get_all("X-Encoding-Correction", [])
            )
        )

    def test_known_contextual_fragments_are_reconstructed_and_reported(self) -> None:
        source = self.write_mbox(
            "contextual-fragments",
            b"From sender@example.com Sat Jan  1 00:00:00 2022\n"
            b"Subject: Citya\n"
            b"Content-Type: text/plain; charset=utf-8\n\n"
            b"Retrouvez l'ensemble\n"
            b"R\xc3\x89MI, \xef\xbf\xbd la recherche\n"
            b"Nous tenons \xef\xbf\xbd vous remercier\n"
            b"proc\xef\xbf\xbdd\xef\xbf\xbd \xef\xbf\xbd un remboursement\n"
            b"l\xef\xbf\xbdensemble de nos biens\n",
        )
        corrected = self.output_root / "contextual-corrected.mbox"
        _, findings = check_tree(source, corrected_mbox=corrected)

        self.assertTrue(any("U+FFFD" in finding.problem for finding in findings))
        parser = BytesParser(policy=policy.default)
        corrected_store = mailbox.mbox(
            corrected, factory=lambda stream: parser.parse(stream)
        )
        try:
            self.assertEqual(len(corrected_store), 1)
            message = parser.parsebytes(corrected_store.get_file(0).read())
        finally:
            corrected_store.close()
        self.assertIn("l'ensemble de nos biens", message.get_content())
        self.assertIn("R\u00c9MI, \u00e0 la recherche", message.get_content())
        self.assertIn("Nous tenons \u00e0 vous remercier", message.get_content())
        self.assertIn(
            "proc\u00e9d\u00e9 \u00e0 un remboursement",
            message.get_content(),
        )
        self.assertTrue(
            any(
                "known damaged text fragment" in str(value)
                for value in message.get_all("X-Encoding-Correction", [])
            )
        )

    def test_repairs_additional_recoverable_replacement_words(self) -> None:
        source = self.write_mbox(
            "additional-contextual-fragments",
            b"From sender@example.com Sat Jan  1 00:00:00 2022\n"
            b"Subject: Recoverable words\n"
            b"Content-Type: text/plain; charset=utf-8\n\n"
            b"Merci de votre r\xef\xbf\xbdpons. L'\xef\xbf\xbdvolution "
            b"\xef\xbf\xbdtant \xef\xbf\xbdgalement "
            b"\xef\xbf\xbdlectronique.\n",
        )
        corrected = self.output_root / "additional-contextual-corrected.mbox"

        _, findings = check_tree(source, corrected_mbox=corrected)

        self.assertTrue(any("U+FFFD" in finding.problem for finding in findings))
        parser = BytesParser(policy=policy.default)
        corrected_store = mailbox.mbox(
            corrected, factory=lambda stream: parser.parse(stream)
        )
        try:
            self.assertEqual(len(corrected_store), 1)
            message = parser.parsebytes(corrected_store.get_file(0).read())
        finally:
            corrected_store.close()
        self.assertIn(
            "Merci de votre réponse. L'évolution étant également électronique.",
            message.get_content(),
        )

    def test_recovers_accents_and_special_characters_only(self) -> None:
        source = self.write_mbox(
            "special-character-recovery",
            b"From sender@example.com Sat Jan  1 00:00:00 2022\n"
            b"Subject: Special characters\n"
            b"Content-Type: text/plain; charset=utf-8\n\n"
            b"De 4 \xef\xbf\xbd 10 euros, 249\xef\xbf\xbd. N\xef\xbf\xbd fiscal, "
            b"n\xef\xbf\xbd de t\xef\xbf\xbdl. L'\xef\xbf\xbdt\xef\xbf\xbd dernier.\n",
        )
        corrected = self.output_root / "special-character-corrected.mbox"

        _, findings = check_tree(source, corrected_mbox=corrected)

        self.assertTrue(any("U+FFFD" in finding.problem for finding in findings))
        parser = BytesParser(policy=policy.default)
        corrected_store = mailbox.mbox(
            corrected, factory=lambda stream: parser.parse(stream)
        )
        try:
            self.assertEqual(len(corrected_store), 1)
            message = parser.parsebytes(corrected_store.get_file(0).read())
        finally:
            corrected_store.close()
        self.assertEqual(
            message.get_content(),
            "De 4 à 10 euros, 249€. N° fiscal, n° de tél. "
            "L'été dernier.\r\n",
        )

    def test_recovers_remaining_contextual_accents_without_guessing_ascii(self) -> None:
        source = self.write_mbox(
            "remaining-contextual-recovery",
            b"From sender@example.com Sat Jan  1 00:00:00 2022\n"
            b"Subject: Contextual recovery\n"
            b"Content-Type: text/plain; charset=utf-8\n\n"
            b"Re\xc3\xa7u de paiement \xef\xbf\xbd conserver. "
            b"C'est l\xef\xbf\xbd-bas. En g\xc3\xa9n\xc3\xa9ral, "
            b"\xef\xbf\xbda vaut le coup. 249 \xef\xbf\xbd. "
            b"On sait que \xef\xbf\xbda vaut le coup. "
            b"Je suis q\xef\xbf\xbd la caisse. "
            b"\xef\xbf\xbda allait de 4 \xc3\xa0 10 euros. "
            b"Les comptes auront \xef\xbf\xbdt\xef\xbf\xbd cr\xc3\xa9\xc3\xa9s. "
            b"Auraient port\xef\xbf\xbd un int\xc3\xa9r\xc3\xaat au projet. "
            b"Des suggestions d'am\xef\xbf\xbdlioration : "
            b"e-mail \xef\xbf\xbd idee@example.test. "
            b"Signature !!!\xef\xbf\xbd\xef\xbf\xbd\xef\xbf\xbd\xef\xbf\xbd\n"
            b"--\xef\xbf\xbd\nJ\xc3\xa9r\xc3\xa9mie\n"
            b"documents stock\xc3\xa9s dans\n"
            b"\xef\xbf\xbd\xef\xbf\xbdvotre coffre s\xc3\xa9curis\xc3\xa9\n"
            b"conservez-les\n"
            b"\xef\xbf\xbd\xef\xbf\xbddans votre coffre\n"
            b"Soci\xc3\xa9t\xc3\xa9 coop\xc3\xa9rative "
            b"\xef\xbf\xbd capital variable\n"
            b"\xef\xbf\xbd capital variable\n"
            b"Vous avez acc\xc3\xa8s \xef\xbf\xbd\xef\xbf\xbd "
            b"tous les profils. C'est un travail \xef\xbf\xbd faire.\n",
        )
        corrected = self.output_root / "remaining-contextual-corrected.mbox"

        _, findings = check_tree(source, corrected_mbox=corrected)

        self.assertTrue(any("U+FFFD" in finding.problem for finding in findings))
        parser = BytesParser(policy=policy.default)
        corrected_store = mailbox.mbox(
            corrected, factory=lambda stream: parser.parse(stream)
        )
        try:
            self.assertEqual(len(corrected_store), 1)
            message = parser.parsebytes(corrected_store.get_file(0).read())
        finally:
            corrected_store.close()
        body = message.get_content()
        self.assertIn("Reçu de paiement à conserver.", body)
        self.assertIn("C'est là-bas.", body)
        self.assertIn("En général, ça vaut le coup. 249 €.", body)
        self.assertIn("On sait que ça vaut le coup.", body)
        self.assertIn("Je suis qà la caisse.", body)
        self.assertIn("ça allait de 4 à 10 euros.", body)
        self.assertIn("Les comptes auront été créés.", body)
        self.assertIn("Auraient porté un intérêt au projet.", body)
        self.assertIn(
            "Des suggestions d'amélioration : e-mail à idee@example.test.",
            body,
        )
        self.assertIn("Vous avez accès à tous les profils.", body)
        self.assertIn("C'est un travail à faire.", body)
        self.assertIn("Signature !!!", body)
        self.assertIn("-- \r\nJérémie", body)
        self.assertIn("documents stockés dans\r\nvotre coffre sécurisé", body)
        self.assertIn("conservez-les\r\ndans votre coffre", body)
        self.assertIn("Société coopérative à capital variable", body)
        self.assertIn("\r\nà capital variable", body)

    def test_valid_utf8_html_is_not_reported_but_known_signature_markers_are_removed(
        self,
    ) -> None:
        source = self.write_mbox(
            "valid-utf8-html",
            b"From sender@example.com Sat Jan  1 00:00:00 2022\n"
            b"Subject: HTML\n"
            b"Content-Type: text/html; charset=utf-8\n\n"
            b'<p>Fran\xc3\x83\xc2\xa7ais \xef\xbf\xbd</p>'
            b'<span style="font-family:&quot;Tahoma&quot;,sans-serif">'
            b"\xef\xbf\xbd\xef\xbf\xbd\xef\xbf\xbd\xef\xbf\xbd"
            b"</span>\n",
        )
        corrected = self.output_root / "valid-utf8-html-corrected.mbox"

        _, findings = check_tree(source, corrected_mbox=corrected)

        self.assertEqual(findings, [])
        parser = BytesParser(policy=policy.default)
        corrected_store = mailbox.mbox(
            corrected, factory=lambda stream: parser.parse(stream)
        )
        try:
            self.assertEqual(len(corrected_store), 1)
            message = parser.parsebytes(corrected_store.get_file(0).read())
        finally:
            corrected_store.close()
        html_part = next(
            part for part in message.walk()
            if part.get_content_type() == "text/html"
        )
        self.assertIn("FranÃ§ais \ufffd", html_part.get_content())
        self.assertNotIn("\ufffd\ufffd\ufffd\ufffd", html_part.get_content())

    def test_recovers_danaides_from_matching_html_alternative(self) -> None:
        source = self.write_mbox(
            "danaides-alternative",
            b"From sender@example.com Sat Jan  1 00:00:00 2022\n"
            b"Subject: Les Danaides\n"
            b"MIME-Version: 1.0\n"
            b"Content-Type: multipart/alternative; boundary=x\n\n"
            b"--x\nContent-Type: text/plain; charset=utf-8\n\n"
            b"LES DANA\xef\xbf\xbd?DES\n"
            b"--x\nContent-Type: text/html; charset=utf-8\n\n"
            b"<p>LES DANA&Iuml;DES</p>\n"
            b"--x--\n",
        )
        corrected = self.output_root / "danaides-corrected.mbox"

        _, findings = check_tree(source, corrected_mbox=corrected)

        self.assertTrue(any("U+FFFD" in finding.problem for finding in findings))
        parser = BytesParser(policy=policy.default)
        corrected_store = mailbox.mbox(
            corrected, factory=lambda stream: parser.parse(stream)
        )
        try:
            self.assertEqual(len(corrected_store), 1)
            message = parser.parsebytes(corrected_store.get_file(0).read())
        finally:
            corrected_store.close()
        plain_part = next(
            part
            for part in message.walk()
            if part.get_content_type() == "text/plain"
        )
        self.assertEqual(plain_part.get_content(), "LES DANAÏDES\r\n")

    def test_utf8_bom_matching_declared_charset_is_not_reported(self) -> None:
        source = self.write_mbox(
            "utf8-bom",
            b"From sender@example.com Sat Jan  1 00:00:00 2022\n"
            b"Subject: UTF-8 BOM\n"
            b"Content-Type: text/plain; charset=utf-8\n\n"
            b"\xef\xbb\xbfBonjour, Fran\xc3\xa7ais.\n",
        )

        _, findings = check_tree(source)

        self.assertEqual(findings, [])

    def test_writes_each_suspect_message_once_and_preserves_attachments(self) -> None:
        self.write_mbox(
            "Inbox",
            b"From sender@example.com Sat Jan  1 00:00:00 2022\n"
            b"From: =?utf-8?b?Sm9zw4PCqQ==?= <jose@example.com>\n"
            b"Subject: =?utf-8?b?Q2Fmw4PCqQ==?=\n"
            b"MIME-Version: 1.0\n"
            b"Content-Type: multipart/mixed; boundary=x\n\n"
            b"--x\nContent-Type: text/plain; charset=utf-8\n\n"
            b"Caf\xc3\x83\xc2\xa9\n"
            b"--x\nContent-Type: application/octet-stream; name=file.bin\n"
            b"Content-Disposition: attachment; filename=file.bin\n"
            b"Content-Transfer-Encoding: base64\n\n"
            b"AAEC/w==\n--x--\n"
            b"From clean@example.com Sat Jan  1 00:00:01 2022\n"
            b"Subject: clean\nContent-Type: text/plain; charset=utf-8\n\n"
            b"Hello\n",
        )
        output = self.output_root / "suspects.mbox"

        count, findings = check_tree(self.root, output)

        self.assertEqual(count, 2)
        self.assertEqual(len(findings), 3)
        suspect_store = mailbox.mbox(output)
        try:
            self.assertEqual(len(suspect_store), 1)
            suspect_message = suspect_store.get_message(0)
        finally:
            suspect_store.close()
        attachment = suspect_message.get_payload()[1]
        self.assertEqual(attachment.get_filename(), "file.bin")
        self.assertEqual(attachment.get_payload(decode=True), b"\x00\x01\x02\xff")

    def test_suspect_header_escapes_unicode_and_embedded_encoded_words(self) -> None:
        message = BytesParser(policy=policy.default).parsebytes(
            b"Subject: test\n\nBody\n"
        )
        finding = Finding(
            Path("Inbox"),
            1,
            "body (text/plain)",
            "possible mojibake",
            "�(中国教育网推荐产品) =?utf-8?q?=C3=A9lectronique?=",
        )
        add_suspect_headers(message, [finding])
        output = self.output_root / "unicode-diagnostic.mbox"
        store = mailbox.mbox(output)
        try:
            store.add(message)
        finally:
            store.close()

        parser = BytesParser(policy=policy.default)
        store = mailbox.mbox(output, factory=lambda stream: parser.parse(stream))
        try:
            saved_message = parser.parsebytes(store.get_file(0).read())
        finally:
            store.close()
        diagnostic = str(
            saved_message["X-Encoding-Suspect"]
        )
        self.assertIn(r"\ufffd", diagnostic)
        self.assertIn(r"\u4e2d", diagnostic)
        self.assertIn("= ?utf-8?q?", diagnostic)

    def test_correction_headers_are_safe_to_serialize(self) -> None:
        message = BytesParser(policy=policy.default).parsebytes(
            b"Subject: test\n\nBody\n"
        )
        add_correction_headers(
            message,
            [
                "body (text/html): repaired mojibake in Café; "
                "aligned meta charset =?utf-8?q? with UTF-8"
            ],
        )
        output = self.output_root / "unicode-correction.mbox"
        store = mailbox.mbox(output)
        try:
            store.add(message)
        finally:
            store.close()

        parser = BytesParser(policy=policy.default)
        store = mailbox.mbox(output, factory=lambda stream: parser.parse(stream))
        try:
            saved_message = parser.parsebytes(store.get_file(0).read())
        finally:
            store.close()
        correction = str(saved_message["X-Encoding-Correction"])
        self.assertIn(r"Caf\xe9", correction)
        self.assertIn("= ?utf-8?q?", correction)

    def test_does_not_overwrite_existing_or_create_output_inside_tree(self) -> None:
        existing_output = self.output_root / "existing.mbox"
        existing_output.write_bytes(b"keep this content")

        with self.assertRaisesRegex(FileExistsError, "existing.mbox"):
            check_tree(self.root, existing_output)
        self.assertEqual(existing_output.read_bytes(), b"keep this content")

        with self.assertRaisesRegex(ValueError, "outside the mbox/sbd tree"):
            check_tree(self.root, self.root / "suspects.mbox")

    def test_force_replaces_existing_output_only_after_successful_scan(self) -> None:
        self.write_mbox(
            "Inbox",
            b"From sender@example.com Sat Jan  1 00:00:00 2022\n"
            b"Subject: =?utf-8?b?Q2Fmw4PCqQ==?=\n"
            b"Content-Type: text/plain; charset=utf-8\n\n"
            b"Hello\n",
        )
        output = self.output_root / "existing.mbox"
        output.write_bytes(b"old output")

        count, findings = check_tree(self.root, output, force=True)

        self.assertEqual(count, 1)
        self.assertTrue(findings)
        store = mailbox.mbox(output)
        try:
            self.assertEqual(len(store), 1)
        finally:
            store.close()

    def test_force_preserves_existing_output_when_scan_fails(self) -> None:
        self.write_mbox(
            "Inbox",
            b"From sender@example.com Sat Jan  1 00:00:00 2022\n"
            b"Subject: content\n\nBody\n",
        )
        output = self.output_root / "existing.mbox"
        output.write_bytes(b"old output")

        with patch("mbox_encoding_fix.inspect_message", side_effect=RuntimeError("scan")):
            with self.assertRaisesRegex(RuntimeError, "scan"):
                check_tree(self.root, output, force=True)

        self.assertEqual(output.read_bytes(), b"old output")

    def test_force_cannot_overwrite_input_mbox(self) -> None:
        source = self.write_mbox(
            "Inbox",
            b"From sender@example.com Sat Jan  1 00:00:00 2022\n"
            b"Subject: content\n\nBody\n",
        )
        original = source.read_bytes()

        with self.assertRaisesRegex(ValueError, "must not overwrite the input"):
            check_tree(source, corrected_mbox=source, force=True)

        self.assertEqual(source.read_bytes(), original)

    def test_cli_short_corrected_option_and_force_override(self) -> None:
        self.write_mbox(
            "Inbox",
            b"From sender@example.com Sat Jan  1 00:00:00 2022\n"
            b"Subject: =?utf-8?b?Q2Fmw4PCqQ==?=\n"
            b"Content-Type: text/plain; charset=utf-8\n\n"
            b"Hello\n",
        )
        output = self.output_root / "corrected.mbox"
        suspects = self.output_root / "suspects.mbox"
        output.write_bytes(b"old output")
        stdout = io.StringIO()
        stderr = io.StringIO()

        with patch("sys.stdout", stdout), patch("sys.stderr", stderr):
            result = main(
                ["-o", str(suspects), "-c", str(output), "-f", str(self.root)]
            )

        self.assertEqual(result, 0)
        self.assertIn("Wrote 1 automatically corrected", stdout.getvalue())
        self.assertIn("Wrote 0 suspect message(s)", stdout.getvalue())
        self.assertIn("found 0 unresolved issue(s)", stdout.getvalue())
        self.assertNotIn("possible mojibake", stdout.getvalue())
        suspect_store = mailbox.mbox(suspects)
        store = mailbox.mbox(output)
        try:
            self.assertEqual(len(suspect_store), 0)
            self.assertEqual(len(store), 1)
        finally:
            suspect_store.close()
            store.close()

    def test_reports_scan_progress_by_mailbox_and_message_count(self) -> None:
        self.write_mbox(
            "Inbox",
            b"From one@example.com Sat Jan  1 00:00:00 2022\n"
            b"Subject: one\n\nFirst\n"
            b"From two@example.com Sat Jan  1 00:00:01 2022\n"
            b"Subject: two\n\nSecond\n",
        )
        statuses: list[str] = []

        count, _ = check_tree(self.root, progress=statuses.append)

        self.assertEqual(count, 2)
        self.assertIn("Progress: mailbox 1/1:", statuses[0])
        self.assertIn(
            "Progress: 1/1 mailboxes completed; 2 message(s) scanned; "
            "0 message(s) corrected; 0 suspect message(s) remain",
            statuses[-1],
        )

    def test_progress_counts_suspect_messages_once(self) -> None:
        self.write_mbox(
            "Inbox",
            b"From one@example.com Sat Jan  1 00:00:00 2022\n"
            b"From: =?utf-8?b?Sm9zw4PCqQ==?= <jose@example.com>\n"
            b"Subject: =?utf-8?b?Q2Fmw4PCqQ==?=\n"
            b"Content-Type: text/plain; charset=utf-8\n\n"
            b"Caf\xc3\x83\xc2\xa9\n"
            b"From two@example.com Sat Jan  1 00:00:01 2022\n"
            b"Subject: unresolved\nContent-Type: text/plain; charset=utf-8\n\n"
            b"Hello \xef\xbf\xbd\n",
        )
        statuses: list[str] = []

        count, findings = check_tree(
            self.root,
            suspects_mbox=self.output_root / "progress-suspects.mbox",
            corrected_mbox=self.output_root / "progress-corrected.mbox",
            progress=statuses.append,
        )

        self.assertEqual(count, 2)
        self.assertEqual(len(findings), 4)
        self.assertIn(
            "Progress: 1/1 mailboxes completed; 2 message(s) scanned; "
            "1 message(s) corrected; 1 suspect message(s) remain",
            statuses[-1],
        )
        suspects = mailbox.mbox(self.output_root / "progress-suspects.mbox")
        corrected = mailbox.mbox(self.output_root / "progress-corrected.mbox")
        try:
            self.assertEqual(len(suspects), 1)
            self.assertEqual(len(corrected), 1)
        finally:
            suspects.close()
            corrected.close()

    def test_main_escapes_output_not_representable_in_windows_console(self) -> None:
        self.write_mbox(
            "Inbox",
            b"From sender@example.com Sat Jan  1 00:00:00 2022\n"
            b"Subject: bad encoding\n"
            b"Content-Type: text/plain; charset=ascii\n\n"
            b"bad: \xef\xbf\xbd\n",
        )
        stdout_buffer = io.BytesIO()
        stderr_buffer = io.BytesIO()
        stdout = io.TextIOWrapper(stdout_buffer, encoding="cp1252")
        stderr = io.TextIOWrapper(stderr_buffer, encoding="cp1252")

        with patch("sys.stdout", stdout), patch("sys.stderr", stderr):
            result = main([str(self.root)])
            stdout.flush()
            stderr.flush()
            output = stdout_buffer.getvalue()

        self.assertEqual(result, 1)
        self.assertIn(b"bad: \\ufffd", output)


if __name__ == "__main__":
    unittest.main()
