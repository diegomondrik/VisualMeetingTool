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

    def test_the_download_header_carries_the_extension_and_the_utf8_name(self):
        header = server.attachment("Reunión <x>.docx")
        self.assertIn('filename="Reuni_n <x>.docx"', header)
        self.assertIn("filename*=UTF-8''Reuni%C3%B3n%20%3Cx%3E.docx", header)


if __name__ == "__main__":
    unittest.main()
