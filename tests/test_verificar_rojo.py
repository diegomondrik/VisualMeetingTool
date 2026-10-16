"""A figure to be corrected by hand is written in red and bold in the Word report, and nothing else is."""

import unittest

import docx
from docx.shared import RGBColor

from meetingtool.report import document


class VerifyMarkTest(unittest.TestCase):
    def test_the_mark_is_red_and_bold_and_the_rest_keeps_its_format(self):
        paragraph = docx.Document().add_paragraph()
        document._add_text(paragraph, "Inventario: [VERIFICAR: «a buck and a half»] y **negrita** normal")
        marked = [run for run in paragraph.runs if run.font.color.rgb == RGBColor(0xC0, 0x00, 0x00)]
        self.assertEqual([run.text for run in marked], ["[VERIFICAR: «a buck and a half»]"])
        self.assertTrue(marked[0].bold)
        bold = [run.text for run in paragraph.runs if run.bold and run.font.color.rgb is None]
        self.assertEqual(bold, ["negrita"])
        self.assertEqual("".join(run.text for run in paragraph.runs),
                         "Inventario: [VERIFICAR: «a buck and a half»] y negrita normal")


if __name__ == "__main__":
    unittest.main()
