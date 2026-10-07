"""Tests for Markup Compatibility in a company's Word template (WI23, the
independent review of 6e33e4c, P1): Word reads one branch of an
mc:AlternateContent (mc:Choice or mc:Fallback, whichever it understands) and
skips an element of a namespace that mc:Ignorable names, with what is inside
it. A filter that reads the XML as one stream joined the pieces of an
instruction across two branches, or across an element Word skips and one it
reads, so the name it judged (an allowed one) was not the name Word reads.

- HiddenFieldTest: a field outside the list, hidden that way, is refused at the
  template and at the report's last check.
- UncertainTest: Markup Compatibility that leaves unknown what Word reads is
  refused naming the part.
- LegitimateTest: the alternatives and ignorable namespaces a template really
  has are accepted, and the application's own report and the example template.

Synthetic templates only: the one host named is example.invalid or made up.
"""

import unittest
from unittest import mock

from meetingtool.report import document
from tests.test_allowed_fields import Templates
from tests.test_report import package_parts
from tests.test_template_filter import RESULT, instruction, mark, nested, paragraph, run, write_package

SAME = "word/document.xml: "
UNKNOWN = "so what Word would read is not known"


def alternate(choice, fallback, requires=b"w14"):
    """An mc:AlternateContent (the prefix mc is declared by the template's root)."""
    return (b'<mc:AlternateContent><mc:Choice Requires="' + requires + b'">' + choice + b"</mc:Choice><mc:Fallback>"
            + fallback + b"</mc:Fallback></mc:AlternateContent>")


def skipped(inner):
    """An element of a namespace the root makes ignorable (see ignorable_root)."""
    return b"<x:wrap>" + inner + b"</x:wrap>"


def ignorable_root(extra=b""):
    """An edit of the body's root: the prefix x, of a made-up namespace, is ignorable (and what else is in extra)."""
    def edit(xml):
        old = b'mc:Ignorable="w14 wp14"'
        assert old in xml
        return xml.replace(old, b'mc:Ignorable="w14 wp14 x" xmlns:x="urn:example.invalid:skipped"' + extra, 1)
    return edit


def field(*pieces):
    """A complex field whose instruction is made of these pieces (runs, or an alternative holding them)."""
    return paragraph(mark(b"begin"), *pieces, mark(b"separate"), RESULT, mark(b"end"))


class Compat(Templates):
    def variant(self, fragment, edit=None):
        parts = self.parts_with(fragment)
        if edit:
            parts["word/document.xml"] = edit(parts["word/document.xml"])
        return write_package(parts, self.tmp / "compat.docx")

    def assert_refused_both_ways(self, path, expected):
        """Refused when the template is set, and, with that check switched off, when the report is checked."""
        self.assertIn(expected, self.refused(path))
        with mock.patch.object(document, "template_bytes", side_effect=lambda p: p.read_bytes()):
            with self.assertRaisesRegex(document.ReportError, "the report was not written") as raised:
                self.build(template=path)
        self.assertIn(expected, str(raised.exception))
        self.assertNothingWritten()


class HiddenFieldTest(Compat):
    """A field outside the list written so that the filter's reading and Word's differ."""

    def cases(self):
        add = b" ADDIN x "
        page = b" PAGE "
        return {
            # Word reads the Fallback when it does not understand what the Choice requires: its name is ADDIN
            "the allowed name in the Choice, the refused one in the Fallback": (
                field(alternate(instruction(page), instruction(add))), None),
            "the refused name in the Choice, the allowed one in the Fallback": (
                field(alternate(instruction(add), instruction(page))), None),
            "a Choice that requires a namespace nothing understands": (
                field(alternate(instruction(page), instruction(add), requires=b"x")), ignorable_root()),
            "the allowed name before the alternatives, the refused one in a branch": (
                field(instruction(page), alternate(instruction(add), instruction(page))), None),
            "a whole refused field in the Choice": (alternate(field(instruction(add)), field(instruction(page))), None),
            "a whole refused field in the Fallback": (alternate(field(instruction(page)), field(instruction(add))), None),
            "a refused simple field in a branch": (
                alternate(b'<w:fldSimple w:instr=" ADDIN x ">' + RESULT + b"</w:fldSimple>", run(b"<w:t>y</w:t>")), None),
            "alternatives inside a branch": (
                field(alternate(alternate(instruction(page), instruction(add)), instruction(page))), None),
            "a field in a branch of an alternative inside a table cell": (
                b"<w:tbl><w:tr><w:tc>" + paragraph(alternate(field(instruction(add)), RESULT)) + b"</w:tc></w:tr></w:tbl>",
                None),
            # Word skips the element and what is inside it: its name is ADDIN
            "the allowed name in an element Word skips": (
                field(skipped(instruction(page)), instruction(add)), ignorable_root()),
            "the allowed name in a skipped element, with the refused one after it": (
                field(skipped(instruction(page) + instruction(b" REF ")), instruction(add)), ignorable_root()),
            "a whole refused field in an element Word skips": (skipped(field(instruction(add))), ignorable_root()),
            "an element Word skips, named by mc:ProcessContent": (
                field(skipped(instruction(page)), instruction(add)), ignorable_root(b' mc:ProcessContent="x:wrap"')),
            "a prefix made ignorable on an element below the root": (
                b'<w:p xmlns:y="urn:example.invalid:other" mc:Ignorable="y">' + mark(b"begin") + b"<y:wrap>"
                + instruction(page) + b"</y:wrap>" + instruction(add) + mark(b"separate") + RESULT + mark(b"end")
                + b"</w:p>", None),
        }

    def test_each_hidden_field_is_refused_at_the_template_and_at_the_report(self):
        for label, (fragment, edit) in self.cases().items():
            with self.subTest(label):
                self.assert_refused_both_ways(self.variant(fragment, edit), SAME + "a ADDIN field")

    def test_a_name_split_across_the_branches_is_refused_by_its_pieces(self):
        # Neither piece is a name on the list, so the field is refused whichever branch Word reads.
        fragment = field(instruction(b" ADD"), alternate(instruction(b"IN x "), instruction(b"IN x ")))
        found = document.active_content(self.parts_with(fragment))
        self.assertEqual(found, [SAME + "a ADD field", SAME + "a IN field"])

    def test_a_hidden_field_of_the_other_refused_names_is_refused_too(self):
        for name in ("INCLUDETEXT", "FILLIN", "MERGEFIELD", "DDEAUTO"):
            with self.subTest(name=name):
                fragment = field(alternate(instruction(b" PAGE "), instruction(b" " + name.encode() + b" x ")))
                self.assert_refused_both_ways(self.variant(fragment), SAME + f"a {name} field")


class UncertainTest(Compat):
    """What Markup Compatibility leaves unknown is refused, naming the part."""

    def cases(self):
        text = run(b"<w:t>a</w:t>")
        return {
            "a Choice with no Requires": (b"<mc:AlternateContent><mc:Choice>" + text + b"</mc:Choice></mc:AlternateContent>",
                                          None, "mc:Choice is not formed"),
            "a Choice that requires a prefix nothing declares": (
                alternate(text, text, requires=b"nothing"), None, "names nothing"),
            "a Fallback first": (b'<mc:AlternateContent><mc:Fallback>' + text + b'</mc:Fallback><mc:Choice Requires="w14">'
                                 + text + b"</mc:Choice></mc:AlternateContent>", None, "mc:AlternateContent is not formed"),
            "an alternative with no Choice": (b"<mc:AlternateContent><mc:Fallback>" + text
                                              + b"</mc:Fallback></mc:AlternateContent>", None,
                                              "mc:AlternateContent is not formed"),
            "an alternative with two Fallbacks": (
                b'<mc:AlternateContent><mc:Choice Requires="w14">' + text + b"</mc:Choice><mc:Fallback>" + text
                + b"</mc:Fallback><mc:Fallback>" + text + b"</mc:Fallback></mc:AlternateContent>", None,
                "mc:AlternateContent is not formed"),
            "an alternative with something else in it": (
                b'<mc:AlternateContent><mc:Choice Requires="w14">' + text + b"</mc:Choice>" + text
                + b"</mc:AlternateContent>", None, "mc:AlternateContent is not formed"),
            "a Choice outside an alternative": (b'<mc:Choice Requires="w14">' + text + b"</mc:Choice>", None,
                                                "mc:Choice is not formed"),
            "an element of the namespace that is not known": (b"<mc:Anything>" + text + b"</mc:Anything>", None,
                                                              "mc:Anything, which is not a known part"),
            "an attribute of the namespace that is not known": (
                b'<w:p mc:Odd="1">' + text + b"</w:p>", None, "mc:Odd, which is not a known part"),
            "an Ignorable that names a prefix nothing declares": (
                b"<w:p>" + text + b"</w:p>", lambda xml: xml.replace(b'mc:Ignorable="w14 wp14"',
                                                                     b'mc:Ignorable="w14 wp14 nothing"', 1),
                "names nothing"),
            "an Ignorable that names Word's own namespace": (
                b"<w:p>" + text + b"</w:p>", lambda xml: xml.replace(b'mc:Ignorable="w14 wp14"',
                                                                     b'mc:Ignorable="w14 wp14 w"', 1),
                "names mc:Ignorable"),
            "a MustUnderstand that names a prefix nothing declares": (
                b'<w:p mc:MustUnderstand="nothing">' + text + b"</w:p>", None, "names nothing"),
            "a ProcessContent that names a prefix nothing declares": (
                b'<w:p mc:ProcessContent="nothing:wrap">' + text + b"</w:p>", None, "names nothing"),
        }

    def test_each_is_refused_naming_the_part_at_the_template_and_at_the_report(self):
        for label, (fragment, edit, expected) in self.cases().items():
            with self.subTest(label):
                path = self.variant(fragment, edit)
                self.assert_refused_both_ways(path, SAME)
                found = document.active_content(package_parts(path))
                self.assertTrue(found and all(item.startswith(SAME) and UNKNOWN in item for item in found), found)
                self.assertTrue(any(expected in item for item in found), (expected, found))

    def test_the_refusal_is_said_in_both_languages(self):
        path = self.variant(b"<mc:Anything/>")
        with self.assertRaises(document.ReportError) as raised:
            document.set_template(path, self.data)
        english, _ = raised.exception.message.render("en")
        spanish, _ = raised.exception.message.render("es")
        self.assertIn("word/document.xml: mc:Anything, which is not a known part of Markup Compatibility", english)
        self.assertIn("word/document.xml: mc:Anything, que no es una parte conocida de Markup Compatibility", spanish)


class LegitimateTest(Compat):
    """The Markup Compatibility a template really has stays accepted."""

    def test_the_templates_own_parts_use_ignorable_and_are_accepted(self):
        # Without this the test below could pass by the parts holding none: python-docx's template has mc:Ignorable.
        self.assertIn(b"mc:Ignorable", self.base["word/document.xml"])
        self.assertEqual(document.active_content(self.base), [])
        path = self.tmp / "example.docx"
        path.write_bytes(document.example_template())
        self.assertIn(b"mc:Ignorable", package_parts(path)["word/header1.xml"])
        self.accepted_and_built(path)
        self.output().unlink()
        self.build(neutral=True)
        document.check_active_content(self.output())

    def test_alternatives_without_a_field_outside_the_list_are_accepted_and_the_report_builds(self):
        text, other = run(b"<w:t>a</w:t>"), run(b"<w:t>b</w:t>")
        for label, fragment, edit in (
                ("alternatives with no field", paragraph(alternate(text, other)), None),
                ("alternatives, a branch with no fallback prefix", paragraph(alternate(text, other, requires=b"w14 wp14")),
                 None),
                ("an allowed field in each branch", alternate(field(instruction(b" PAGE ")), field(instruction(b" PAGE "))),
                 None),
                ("the same allowed field split across a Choice and a Fallback alike",
                 field(alternate(instruction(b" PAGE "), instruction(b" PAGE "))), None),
                ("alternatives inside alternatives", paragraph(alternate(alternate(text, other), other)), None),
                ("an allowed field in an element Word skips", skipped(field(instruction(b" PAGE "))), ignorable_root()),
                ("an element Word skips, with text", paragraph(skipped(text)), ignorable_root()),
                ("an element Word skips, named by mc:ProcessContent", paragraph(skipped(text)),
                 ignorable_root(b' mc:ProcessContent="x:wrap"')),
                ("a MustUnderstand that names a declared prefix", b'<w:p mc:MustUnderstand="w14">' + text + b"</w:p>", None),
                ("a formula over a field, with alternatives around", nested(b"=", [b"NUMPAGES"], b"-1"), None)):
            with self.subTest(label):
                path = self.variant(fragment, edit)
                self.assertEqual(document.active_content(package_parts(path)), [])
                self.accepted_and_built(path)

    def test_a_part_nested_deeper_than_the_interpreter_allows_is_read(self):
        # Nothing here recurses over the tree: a part cannot make the reading fail with RecursionError.
        depth = 3000
        deep = b"<w:p>" * depth + instruction(b" ADDIN x ") + b"</w:p>" * depth
        self.assertEqual(document.active_content(self.parts_with(deep)), [SAME + "a ADDIN field"])


if __name__ == "__main__":
    unittest.main()
