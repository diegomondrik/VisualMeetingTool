"""The Word report downloads under the meeting's title, with its extension, and a name Windows accepts."""

import unittest

from meetingtool.app import server


class ReportNameTest(unittest.TestCase):
    def test_the_name_is_the_meeting_title_with_the_docx_extension(self):
        self.assertEqual(server.report_name("License Catch up"), "License Catch up.docx")

    def test_characters_windows_does_not_allow_are_replaced(self):
        self.assertEqual(server.report_name('a/b:c? "x"'), "a b c x.docx")

    def test_a_reserved_or_empty_title_gets_a_plain_name(self):
        self.assertEqual(server.report_name("CON"), "summary.docx")
        self.assertEqual(server.report_name("  "), "summary.docx")

    def test_a_reserved_name_with_an_extension_or_a_superscript_gets_a_plain_name(self):
        for title in ("CON.report", "nul.x", "COM¹", "LPT³.txt", "com1 . "):
            with self.subTest(title=title):
                self.assertEqual(server.report_name(title), "summary.docx")
        self.assertEqual(server.report_name("Console notes"), "Console notes.docx")

    def test_the_marks_that_reverse_the_text_and_delete_are_removed(self):
        self.assertEqual(server.report_name("a‮cod.exe\x7f"), "a cod.exe.docx")

    def test_a_title_that_already_ends_in_docx_is_not_doubled(self):
        self.assertEqual(server.report_name("Notes.docx"), "Notes.docx")

    def test_the_download_header_carries_the_extension_and_the_utf8_name(self):
        header = server.attachment("Reunión <x>.docx")
        self.assertIn('filename="Reuni_n <x>.docx"', header)
        self.assertIn("filename*=UTF-8''Reuni%C3%B3n%20%3Cx%3E.docx", header)


if __name__ == "__main__":
    unittest.main()
