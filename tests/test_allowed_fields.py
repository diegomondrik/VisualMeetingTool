"""Tests for the list of fields a company's Word template may hold (WI23, the
security review of WI22, P2; WI22-P3-5 of the limitations register): a field's
name, written out in the file, has to be one of a short list, and every other
field is refused naming it, at the template and at the report's last check.

- AllowedFieldsTest (WI23-AC01): every allowed field accepted in a template,
  simple and complex, and its report built; the report the application writes,
  the example template and a template in the shape of the owner's accepted.
- RefusedFieldsTest (WI23-AC02): every field outside the list refused, in each
  of the forms of WI22-AC02 (tests/test_template_filter.py), at the template and
  at the report's last check.
- NameTest: what counts as the name of a field, against the list.

Synthetic templates only: the one host named is example.invalid or made up.
"""

import html
import unittest
import zipfile
from unittest import mock

from meetingtool.report import document
from tests.test_report import (MEETING, Workspace, company_template, fields_template, owner_shaped,
                               package_parts)
from tests.test_template_filter import (FIELDS as WI22_REFUSED, FORMS, RESULT, TARGET, complex_field, instruction,
                                        mark, nested, paragraph, quote, read_instructions, with_field, write_package)

# Written here, not taken from the product: a test that borrowed the product's list would agree with it even where
# it is wrong. The owner's decision of 2026-10-06.
ALLOWED = ["PAGE", "NUMPAGES", "SECTIONPAGES", "SECTION", "TOC", "PAGEREF", "REF", "NOTEREF", "STYLEREF",
           "HYPERLINK", "DATE", "TIME", "CREATEDATE", "SAVEDATE", "PRINTDATE", "DOCPROPERTY", "TITLE", "SUBJECT",
           "AUTHOR", "IF", "SEQ", "="]
# The fields WI22 refused, and the ones this work item adds (those the owner named, two more, and a made-up one).
REFUSED = WI22_REFUSED + ["ADDIN", "FILLIN", "MERGEFIELD", "ASK", "QUOTE", "AUTOTEXT", "EMBED", "INVENTADO"]

# What each allowed field is written with, as Word writes it (the name is all that is compared; HYPERLINK needs an
# address that a hyperlink may have).
TEXT = {
    "=": " = 1 + 1 ",
    "TOC": ' TOC \\o "1-3" \\h \\z \\u ',
    "PAGEREF": " PAGEREF _Toc100 \\h ",
    "REF": " REF _Toc100 \\h ",
    "NOTEREF": " NOTEREF _Ref100 \\h ",
    "STYLEREF": ' STYLEREF "Heading 1" ',
    "HYPERLINK": ' HYPERLINK "https://example.invalid/a" ',
    "DOCPROPERTY": ' DOCPROPERTY "Title" ',
    "DATE": ' DATE \\@ "d/M/yyyy" ',
    "IF": ' IF 1 = 1 "a" "b" ',
    "SEQ": " SEQ Figure \\* ARABIC ",
}


def written(field):
    """The instruction an allowed field is written with."""
    return TEXT.get(field, f" {field} ")


def simple_field(text):
    return b"<w:p><w:fldSimple w:instr=\"" + html.escape(text, quote=True).encode() + b"\">" + RESULT + b"</w:fldSimple></w:p>"


def written_field(field, shape):
    """The field in the simple (fldSimple) or the complex (fldChar and instrText) form."""
    return simple_field(written(field)) if shape == "simple" else complex_field(written(field).encode())


class Templates(Workspace):
    """A clean company template, and a package made of it with a fragment in
    its body."""

    def setUp(self):
        super().setUp()
        self.clean = company_template(self.tmp / "clean.docx")
        self.base = package_parts(self.clean)

    def parts_with(self, fragment):
        parts = dict(self.base)
        parts["word/document.xml"] = parts["word/document.xml"].replace(b"<w:sectPr", fragment + b"<w:sectPr", 1)
        return parts

    def package_with(self, fragment, name="variant.docx"):
        return write_package(self.parts_with(fragment), self.tmp / name)

    def refused(self, path):
        """The message of the refusal of a template at set_template, which keeps nothing."""
        with self.assertRaises(document.ReportError) as raised:
            document.set_template(path, self.data)
        self.assertIsNone(document.stored_template(self.data))
        return str(raised.exception)

    def accepted_and_built(self, path):
        """The template is set and a report is built from it, which passes its own check; the report's fields."""
        document.set_template(path, self.data)
        self.assertIsNotNone(document.stored_template(self.data))
        result = self.build(**MEETING)
        self.assertEqual(document.active_content(package_parts(self.output())), [])
        return result


class AllowedFieldsTest(Templates):
    """WI23-AC01."""

    def test_the_list_is_the_owners(self):
        self.assertEqual(sorted(document.ALLOWED_FIELDS), sorted(ALLOWED))
        self.assertEqual(len(ALLOWED), 22)

    def test_every_allowed_field_is_accepted_in_both_forms_and_its_report_builds(self):
        for field in ALLOWED:
            for shape in ("simple", "complex"):
                with self.subTest(field=field, shape=shape):
                    parts = self.parts_with(written_field(field, shape))
                    # the field is really there, read by a second reader that holds none of the product's code
                    found = [text.split()[0].upper() for text in read_instructions(parts["word/document.xml"])
                             if text.strip()]
                    self.assertEqual(found, [field])
                    self.assertEqual(document.active_content(parts), [])
                    self.accepted_and_built(write_package(parts, self.tmp / "allowed.docx"))

    def test_every_allowed_field_is_accepted_in_every_form_of_wi22(self):
        # The forms of WI22-AC02 (another prefix, Strict, CDATA, split across runs, a header, a footnote...) with an
        # allowed field instead of a refused one. HYPERLINK is left out, as its address is the made-up UNC path of
        # those forms; the formula, for its name of one character, which some of the forms take apart.
        for form in FORMS:
            for field in ALLOWED:
                if field not in ("HYPERLINK", "="):
                    with self.subTest(form=form, field=field):
                        parts, part = with_field(self.base, form, field)
                        self.assertEqual([text.split()[0].upper() for text in read_instructions(parts[part])
                                          if text.strip()], [field])
                        self.assertEqual(document.active_content(parts), [])
        parts, _ = with_field(self.base, "in a footnote", "SEQ")  # the form that needs most of the package
        self.accepted_and_built(write_package(parts, self.tmp / "footnote.docx"))

    def test_the_names_are_read_in_any_case(self):
        for field in ALLOWED:
            for text in (field.lower(), field.capitalize()):
                with self.subTest(text=text):
                    self.assertEqual(document.active_content(
                        self.parts_with(complex_field(b" " + text.encode() + b" "))), [])

    def test_a_field_inside_another_is_accepted_when_both_are_allowed(self):
        for label, fragment in {"an IF over a PAGE": nested(b" IF ", [b" PAGE "], b' > 1 "a" "b" '),
                                "a formula over NUMPAGES, with spaces": nested(b" = ", [b" NUMPAGES "], b" - 1 "),
                                "a formula over NUMPAGES, without": nested(b"=", [b"NUMPAGES"], b"-1")}.items():
            with self.subTest(label):
                self.accepted_and_built(self.package_with(fragment))

    def test_the_report_the_application_writes_passes_its_own_check(self):
        # With no template: the neutral report.
        self.build(neutral=True)
        document.check_active_content(self.output())
        self.assertEqual(document.active_content(package_parts(self.output())), [])
        self.output().unlink()
        # With a template that has a table of contents: the report writes TOC, PAGEREF and links of its own.
        document.set_template(owner_shaped(self.tmp / "owner.docx"), self.data)
        result = self.build(**MEETING)
        document.check_active_content(self.output())
        names = {text.split()[0].upper() for text in read_instructions(package_parts(self.output())["word/document.xml"])
                 if text.strip()}
        self.assertTrue(names and names <= {"TOC", "PAGEREF", "HYPERLINK"}, names)
        self.assertGreater(result.contents, 0)

    def test_the_example_template_is_accepted_and_its_report_builds(self):
        path = self.tmp / "example.docx"
        path.write_bytes(document.example_template())
        result = self.accepted_and_built(path)
        self.assertTrue(result.cover)
        # everything the example holds is allowed, by a second reader and not by the product's
        with zipfile.ZipFile(path) as archive:
            for part in archive.namelist():
                if part.endswith(".xml"):
                    for text in read_instructions(archive.read(part)):
                        if text.strip():
                            self.assertIn(text.split()[0].upper(), ALLOWED, (part, text))

    def test_a_template_in_the_shape_of_the_owners_is_accepted(self):
        # A cover with the company's {placeholders}, in the body, the header and the footer, and no Word field at all.
        path = fields_template(self.tmp / "owner-shape.docx", [
            "{cliente}", "Proyecto: {proyecto}", "Reunión: {reunion}", "Fecha: {fecha}", "Tipo: {tipo}"],
            header="{proyecto} · Empresa Inventada", footer="{fecha}")
        with zipfile.ZipFile(path) as archive:
            for part in archive.namelist():
                if part.endswith(".xml"):  # without this the control could pass by being something else
                    self.assertEqual([text for text in read_instructions(archive.read(part)) if text.strip()], [])
                    for tag in (b"fldChar", b"fldSimple", b"instrText"):
                        self.assertNotIn(tag, archive.read(part), part)
        result = self.accepted_and_built(path)
        self.assertEqual(result.fields, ["client", "project", "meeting", "date", "type"])
        self.assertTrue(result.cover)

    def test_a_field_with_nothing_written_and_text_that_no_field_holds_are_not_judged_for_a_name(self):
        # An empty instruction, and the empty text no field holds (which the filter reads as one more field), have
        # no name: nothing to refuse, though no name is in the list.
        for label, fragment in {"a field with nothing written": paragraph(mark(b"begin"), mark(b"separate"),
                                                                           RESULT, mark(b"end")),
                                "an empty instruction": nested(b""),
                                "an instruction of spaces": nested(b"   "),
                                "an empty simple field": simple_field(""),
                                "a stray instruction that is a name of the list": paragraph(instruction(b" PAGE "))
                                }.items():
            with self.subTest(label):
                self.assertEqual(document.active_content(self.parts_with(fragment)), [])
        self.assertEqual(document.active_content(self.base), [])  # and a template with no field at all


class RefusedFieldsTest(Templates):
    """WI23-AC02: each field outside the list, in each form of WI22-AC02, at the
    template (set_template) and at the report's last check (the template's own
    check switched off, as WI22's AC04 test does)."""

    def assert_form_refused(self, form):
        for field in REFUSED:
            with self.subTest(form=form, field=field):
                parts, part = with_field(self.base, form, field)
                path = write_package(parts, self.tmp / "variant.docx")
                line = f"\n  {part}: a {field} field\n"  # the only thing found, and where
                self.assertIn(line, self.refused(path))
                with mock.patch.object(document, "template_bytes", side_effect=lambda p: p.read_bytes()):
                    with self.assertRaisesRegex(document.ReportError, "the report was not written") as raised:
                        self.build(template=path)
                self.assertIn(line, str(raised.exception))
                self.assertNothingWritten()

    def test_the_fields_of_wi22_and_the_new_ones_are_all_there(self):
        self.assertEqual(REFUSED[:9], ["DDEAUTO", "DDE", "INCLUDETEXT", "INCLUDEPICTURE", "INCLUDE", "IMPORT", "LINK",
                                      "DATABASE", "RD"])
        self.assertFalse(set(REFUSED) & set(ALLOWED))

    def test_each_form_is_a_real_field_once_decoded(self):
        # As in WI22, for the names this work item adds: a form cannot be refused for being nonsense.
        for form in FORMS:
            for field in REFUSED[9:]:
                with self.subTest(form=form, field=field):
                    parts, part = with_field(self.base, form, field)
                    self.assertEqual([text.split()[0].upper() for text in read_instructions(parts[part])
                                      if text.strip()], [field])

    def test_a_refused_field_is_refused_in_the_simple_and_complex_forms_with_its_own_arguments(self):
        for field in REFUSED:
            for shape in ("simple", "complex"):
                with self.subTest(field=field, shape=shape):
                    text = f' {field} "https://example.invalid/x" \\* MERGEFORMAT '
                    fragment = simple_field(text) if shape == "simple" else complex_field(text.encode())
                    self.assertEqual(document.active_content(self.parts_with(fragment)),
                                     [f"word/document.xml: a {field} field"])

    def test_a_field_inside_another_is_judged_too(self):
        cases = {
            "an IF over an INCLUDETEXT": (nested(b" IF ", [b" INCLUDETEXT" + TARGET], b' = "a" "b" '), ["INCLUDETEXT"]),
            "an IF over an ADDIN": (nested(b" IF ", [b" ADDIN x "], b' = "a" "b" '), ["ADDIN"]),
            "a formula over a MERGEFIELD": (nested(b"=", [b"MERGEFIELD x"], b"-1"), ["MERGEFIELD"]),
            "an allowed field and a refused one, side by side": (nested(b" IF ", [b" PAGE "], b" = ", [b" FILLIN "]),
                                                                 ["FILLIN"]),
            "a refused field with an allowed one inside": (nested(b" ASK x ", [b" PAGE "]), ["ASK"]),
        }
        for label, (fragment, names) in cases.items():
            with self.subTest(label):
                self.assertEqual(document.active_content(self.parts_with(fragment)),
                                 [f"word/document.xml: a {name} field" for name in names])
                self.assertIn(f"a {names[0]} field", self.refused(self.package_with(fragment)))

    def test_a_name_made_by_another_field_is_still_refused_for_that(self):
        # WI22 stays: QUOTE builds the name, and the field is refused as one whose name is not written out.
        found = document.active_content(self.parts_with(nested(quote(b"68 68 69 65 85 84 79"), b" x ")))
        self.assertIn("word/document.xml: a field whose name is not written out in the file (another field builds it), "
                      "so what it is cannot be known", found)

    def test_the_text_that_no_field_holds_is_judged_only_when_it_says_a_name(self):
        # Without a field around it, an instruction is read as one (WI22): by the name it says, and not for none.
        self.assertEqual(document.active_content(self.parts_with(paragraph(instruction(b" ADDIN x ")))),
                         ["word/document.xml: a ADDIN field"])
        self.assertEqual(document.active_content(self.parts_with(paragraph(instruction(b" PAGE ")))), [])
        self.assertEqual(document.active_content(self.parts_with(paragraph(instruction(b"   ")))), [])

    def test_the_refusal_says_which_field_and_which_are_allowed_in_both_languages(self):
        path = self.package_with(complex_field(b' ADDIN ZOTERO_ITEM CSL_CITATION {} '))
        with self.assertRaises(document.ReportError) as raised:
            document.set_template(path, self.data)
        english, _ = raised.exception.message.render("en")
        spanish, _ = raised.exception.message.render("es")
        self.assertIn("word/document.xml: a ADDIN field", english)
        self.assertIn("word/document.xml: un campo ADDIN", spanish)
        self.assertIn("The only fields a template may hold are", english)
        self.assertIn("Los únicos campos que una plantilla puede tener son", spanish)
        for field in ALLOWED:
            self.assertIn(field, english)
            self.assertIn(field, spanish)
        with mock.patch.object(document, "template_bytes", side_effect=lambda p: p.read_bytes()):
            with self.assertRaises(document.ReportError) as raised:
                self.build(template=path)
        spanish, _ = raised.exception.message.render("es")
        self.assertIn("un campo ADDIN", spanish)
        self.assertIn("Los únicos campos que una plantilla puede tener son", spanish)


class NameTest(Templates):
    """What is compared with the list is the name written out in the file (WI22's
    rule): the first word, whole, in upper case when it is ASCII."""

    def found(self, text):
        return document.active_content(self.parts_with(complex_field(text)))

    def test_a_name_that_only_starts_like_an_allowed_one_is_refused(self):
        for text in (b" PAGES ", b" PAGEREFS _x ", b" SEQUENCE ", b" DATES ", b" TITLES ", b" PAGE1 ", b" IFF ",
                     b" TOCS ", b" REFS x ", b" HYPERLINKS x "):
            with self.subTest(text=text):
                self.assertEqual(self.found(text), [f"word/document.xml: a {text.split()[0].decode()} field"])

    def test_the_name_is_the_first_word_and_the_rest_is_arguments(self):
        for text in (b" PAGE \\* MERGEFORMAT ", b"PAGE\\* MERGEFORMAT", b' DATE \\@ "d" ADDIN ',
                     b' DOCPROPERTY ADDIN ', b' REF MERGEFIELD \\h ', b' IF "ADDIN" = "FILLIN" "a" "b" '):
            with self.subTest(text=text):
                self.assertEqual(self.found(text), [])

    def test_a_name_that_does_not_start_with_a_word_is_refused_as_written(self):
        for text, shown in ((b' "PAGE" ', '"PAGE"'), (b" -PAGE ", "-PAGE"), (b" {PAGE} ", "{PAGE}"), (b" /SEQ ", "/SEQ")):
            with self.subTest(text=text):
                self.assertEqual(self.found(text), [f"word/document.xml: a {shown} field"])

    def test_a_name_with_letters_that_only_look_like_an_allowed_one_is_refused(self):
        # "ſ" (long s) is "S" in upper case, and "ı" (dotless i) is "I": Python's upper() would make these allowed.
        for name in ("ſEQ", "ſECTION", "ıF", "ＰＡＧＥ", "РAGE"):  # the last: a Cyrillic Er
            with self.subTest(name=name):
                self.assertEqual(self.found(f" {name} ".encode()), [f"word/document.xml: a {name} field"])

    def test_a_long_name_is_not_said_whole(self):
        found = self.found(b" " + b"A" * 300 + b" ")
        self.assertEqual(found, ["word/document.xml: a " + "A" * 40 + " field"])

    def test_a_simple_field_is_named_by_its_instruction(self):
        for text, expected in ((" ADDIN x", ["a ADDIN field"]), (" PAGE", []), (" HYPERLINK https://example.invalid/x", []),
                               ("MERGEFIELD nombre", ["a MERGEFIELD field"]), ("", [])):
            with self.subTest(text=text):
                found = document.active_content(self.parts_with(simple_field(text)))
                self.assertEqual(found, [f"word/document.xml: {item}" for item in expected])

    def test_each_part_says_its_own_refused_fields_once(self):
        parts, _ = with_field(self.base, "in a header", "ADDIN")
        parts["word/document.xml"] = self.parts_with(complex_field(b" ADDIN a ") + complex_field(b" ADDIN b ")
                                                     + complex_field(b" FILLIN c "))["word/document.xml"]
        self.assertEqual(document.active_content(parts), ["word/document.xml: a ADDIN field",
                                                          "word/document.xml: a FILLIN field",
                                                          "word/header1.xml: a ADDIN field"])


def _form_test(form):
    return lambda self: self.assert_form_refused(form)


for _form in FORMS:  # one test per form, each over every refused field
    setattr(RefusedFieldsTest, "test_refused_" + "_".join(_form.replace(",", "").split()), _form_test(_form))
del _form


if __name__ == "__main__":
    unittest.main()
