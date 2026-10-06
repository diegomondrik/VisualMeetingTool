"""Tests for the filter of a company's Word template (WI22, the external
review's R02): every XML part is read as XML, with its namespaces, so an
active field or a macro-enabled content type is refused however its XML is
written, and the report built from a template is checked again before it is
delivered.

- FieldFormsTest (WI22-AC02): each active field in each equivalent form is
  refused; each form, read by a second and simpler reader, really yields the
  field's name; the same forms with a harmless field are accepted.
- PackageTest (WI22-AC03): a macro-enabled content type however it is written,
  a part that is not XML, a part Word reads by its content type.
- ReportCheckTest (WI22-AC04): the report is checked again.

Synthetic templates only: the one host named is example.invalid or made up.
"""

import unittest
import xml.dom.minidom
import zipfile
from unittest import mock

from meetingtool.report import document
from tests.test_report import REL, Workspace, company_template, edit_package, package_parts, relationship

# Written here, not taken from the product: a test that borrowed the product's
# constants would agree with it even where it is wrong.
WORD = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
STRICT = "http://purl.oclc.org/ooxml/wordprocessingml/main"
FIELDS = ["DDEAUTO", "DDE", "INCLUDETEXT", "INCLUDEPICTURE", "INCLUDE", "IMPORT", "LINK"]
TARGET = b' "\\\\inventado.invalid\\share\\x.png" '  # a UNC path to a made-up host

BODY = ("word/document.xml", b"<w:sectPr")
HEADER = ("word/header1.xml", b"</w:hdr>")
FOOTER = ("word/footer1.xml", b"</w:ftr>")
FOOTNOTES = ("word/footnotes.xml", None)  # a part the clean template lacks; add_footnotes makes it


def run(inner):
    return b"<w:r>" + inner + b"</w:r>"


def mark(kind):
    return run(b'<w:fldChar w:fldCharType="' + kind + b'"/>')


def instruction(text, tag=b"w:instrText"):
    return run(b"<" + tag + b' xml:space="preserve">' + text + b"</" + tag + b">")


def paragraph(*inner):
    return b"<w:p>" + b"".join(inner) + b"</w:p>"


RESULT = run(b"<w:t>x</w:t>")


def complex_field(*pieces, tag=b"w:instrText"):
    """A complex field whose instruction is written in these pieces, a run each."""
    return paragraph(mark(b"begin"), *(instruction(piece, tag) for piece in pieces), mark(b"separate"), RESULT,
                     mark(b"end"))


def name(field):
    return field.encode()


# Each form: (target part, bytes for it), from the field's name.
FORMS = {
    "as written": lambda f: (BODY, complex_field(b" " + name(f) + TARGET)),
    "a character reference in the name": lambda f: (
        BODY, complex_field(b" &#" + str(ord(f[0])).encode() + b";" + name(f)[1:] + TARGET)),
    "a hexadecimal character reference in the name": lambda f: (
        BODY, complex_field(b" " + name(f)[:2] + b"&#x" + hex(ord(f[2]))[2:].encode() + b";" + name(f)[3:] + TARGET)),
    "lower case": lambda f: (BODY, complex_field(b" " + name(f.lower()) + TARGET)),
    "mixed case": lambda f: (BODY, complex_field(b" " + name(f.capitalize()) + TARGET)),
    "simple, with single quotes": lambda f: (
        BODY, b"<w:p><w:fldSimple w:instr=' " + name(f) + TARGET + b"'>" + RESULT + b"</w:fldSimple></w:p>"),
    "simple, with a character reference": lambda f: (
        BODY, b"<w:p><w:fldSimple w:instr=' &#" + str(ord(f[0])).encode() + b";" + name(f)[1:] + TARGET + b"'>"
        + RESULT + b"</w:fldSimple></w:p>"),
    "complex, split across runs": lambda f: (BODY, complex_field(b" " + name(f)[:3], name(f)[3:] + TARGET)),
    "complex, split across paragraphs": lambda f: (
        BODY, paragraph(mark(b"begin"), instruction(b" " + name(f)[:2])) + paragraph(
            instruction(name(f)[2:] + TARGET), mark(b"separate"), RESULT, mark(b"end"))),
    "complex, split in three runs by empty ones": lambda f: (
        BODY, complex_field(b" " + name(f)[:1], b"", name(f)[1:-1], name(f)[-1:] + TARGET)),
    "another prefix for the namespace": lambda f: (
        BODY, paragraph(mark(b"begin"), run(b'<v:instrText xmlns:v="' + WORD.encode() + b'" xml:space="preserve"> '
                                            + name(f) + TARGET + b"</v:instrText>"), mark(b"end"))),
    "another prefix, simple": lambda f: (
        BODY, b'<w:p><x:fldSimple xmlns:x="' + WORD.encode() + b'" x:instr=\' ' + name(f) + TARGET + b"'/></w:p>"),
    "the namespace as the default one": lambda f: (
        BODY, paragraph(mark(b"begin"), run(b'<instrText xmlns="' + WORD.encode() + b'"> ' + name(f) + TARGET
                                            + b"</instrText>"), mark(b"end"))),
    "the Strict namespace": lambda f: (
        BODY, paragraph(mark(b"begin"), run(b'<s:instrText xmlns:s="' + STRICT.encode() + b'"> ' + name(f) + TARGET
                                            + b"</s:instrText>"), mark(b"end"))),
    "inside CDATA": lambda f: (BODY, complex_field(b"<![CDATA[ " + name(f) + TARGET + b"]]>")),
    "split by a comment": lambda f: (
        BODY, complex_field(b" " + name(f)[:4] + b"<!-- a comment in the name -->" + name(f)[4:] + TARGET)),
    "in a deleted instruction": lambda f: (BODY, complex_field(b" " + name(f) + TARGET, tag=b"w:delInstrText")),
    "in a header": lambda f: (HEADER, complex_field(b" " + name(f) + TARGET)),
    "in a footer": lambda f: (FOOTER, complex_field(b" " + name(f) + TARGET)),
    "in a footnote": lambda f: (FOOTNOTES, b'<w:footnote w:id="1">' + complex_field(b" " + name(f) + TARGET)
                                + b"</w:footnote>"),
}

FOOTNOTES_PART = (b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<w:footnotes xmlns:w="' + WORD.encode()
                  + b'">%s</w:footnotes>')


def with_field(base, form, field):
    """(the parts of base with the form's bytes for a field in the part it
    names, the part's name); base is a package's parts, by name."""
    (part, marker), data = FORMS[form](field)
    parts = dict(base)
    if part == FOOTNOTES[0]:
        parts[part] = FOOTNOTES_PART % data
        parts["[Content_Types].xml"] = parts["[Content_Types].xml"].replace(
            b"</Types>", b'<Override PartName="/word/footnotes.xml" ContentType="application/vnd.openxmlformats-'
                         b'officedocument.wordprocessingml.footnotes+xml"/></Types>')
        parts["word/_rels/document.xml.rels"] = parts["word/_rels/document.xml.rels"].replace(
            b"</Relationships>", relationship("footnotes", "footnotes.xml", False) + b"</Relationships>")
    else:
        parts[part] = parts[part].replace(marker, data + marker, 1)
    return parts, part


def write_package(parts, path):
    with zipfile.ZipFile(path, "w", zipfile.ZIP_STORED) as archive:
        for name, data in parts.items():
            archive.writestr(name, data)
    return path


def read_instructions(data):
    """The instructions in a part's bytes, read the simplest way and with no
    code of the product's: minidom, element by name and namespace, the text and
    CDATA nodes of each instruction joined (comments left out, references
    decoded by the parser). A complex field's pieces are joined in document
    order; the form of a test holds one field."""
    found, pieces = [], []
    dom = xml.dom.minidom.parseString(data)
    for namespace in (WORD, STRICT):
        for tag in ("instrText", "delInstrText"):
            for node in dom.getElementsByTagNameNS(namespace, tag):
                pieces.append("".join(child.data for child in node.childNodes
                                      if child.nodeType in (child.TEXT_NODE, child.CDATA_SECTION_NODE)))
        for node in dom.getElementsByTagNameNS(namespace, "fldSimple"):
            found.append(node.getAttributeNS(namespace, "instr"))
    return found + ["".join(pieces)] if pieces else found


class FieldFormsTest(Workspace):
    """WI22-AC02."""

    def setUp(self):
        super().setUp()
        self.clean = company_template(self.tmp / "clean.docx")
        self.base = package_parts(self.clean)

    def refused(self, path):
        with self.assertRaises(document.ReportError) as raised:
            document.set_template(path, self.data)
        self.assertIsNone(document.stored_template(self.data))
        return str(raised.exception)

    def assert_form_refused(self, form):
        """Every active field written in this form is refused, saying which and where."""
        for field in FIELDS:
            with self.subTest(form=form, field=field):
                parts, part = with_field(self.base, form, field)
                message = self.refused(write_package(parts, self.tmp / "variant.docx"))
                self.assertIn(f"\n  {part}: a {field} field\n", message)  # the only thing found, and where

    def test_each_form_is_a_real_field_once_decoded(self):
        # So that a form cannot pass the tests above by being nonsense the filter refuses for another reason:
        # a second reader, parsing the form and decoding it, finds the field's name as the instruction's first word.
        for form in FORMS:
            for field in FIELDS:
                with self.subTest(form=form, field=field):
                    parts, part = with_field(self.base, form, field)
                    instructions = read_instructions(parts[part])
                    # the clean template's own parts hold no field, so what is found is the form's
                    self.assertEqual([text.split()[0].upper() for text in instructions if text.strip()], [field])

    def test_the_same_forms_with_a_harmless_field_are_accepted(self):
        for form in FORMS:
            with self.subTest(form=form):
                parts, _ = with_field(self.base, form, "PAGE")
                self.assertEqual(document.active_content(parts), [])
        # the fields a template has, together
        every = b"".join(complex_field(b" " + field + b" ") for field in (b"PAGE", b"NUMPAGES", b"TOC", b"PAGEREF"))
        every += complex_field(b' HYPERLINK "https://example.invalid/a" ')
        parts = dict(self.base, **{"word/document.xml": self.base["word/document.xml"].replace(
            b"<w:sectPr", every + b"<w:sectPr", 1)})
        self.assertEqual(document.active_content(parts), [])
        # and the template as a whole, in the form that needs most of the package
        parts, _ = with_field(self.base, "in a footnote", "PAGE")
        document.set_template(write_package(parts, self.tmp / "footnote.docx"), self.data)
        self.assertIsNotNone(document.stored_template(self.data))

    def test_a_field_named_next_to_another_in_the_same_part_is_not_run_together(self):
        # Two fields one after the other: their pieces are not one instruction ("PAGELINK"), and each is read.
        two = paragraph(mark(b"begin"), instruction(b"PAGE"), mark(b"end"), mark(b"begin"),
                        instruction(b"LINK" + TARGET), mark(b"end"))
        path = edit_package(self.clean, self.tmp / "two.docx", insert={"word/document.xml": (b"<w:sectPr", two)})
        self.assertEqual(document.active_content(package_parts(path)), ["word/document.xml: a LINK field"])

    def test_a_field_inside_another_fields_instruction_is_read(self):
        nested = paragraph(mark(b"begin"), instruction(b" IF "), mark(b"begin"), instruction(b" INCLUDETEXT" + TARGET),
                           mark(b"end"), instruction(b' = "a" "b" '), mark(b"end"))
        path = edit_package(self.clean, self.tmp / "nested.docx", insert={"word/document.xml": (b"<w:sectPr", nested)})
        self.assertEqual(document.active_content(package_parts(path)),
                         ["word/document.xml: a INCLUDETEXT field"])

    def test_a_field_name_inside_a_longer_word_is_not_a_field(self):
        # HYPERLINK holds LINK, and INCLUDED holds INCLUDE: the name is a whole word, as before.
        words = complex_field(b' HYPERLINK "https://example.invalid/a" ') + complex_field(b" INCLUDED ")
        path = edit_package(self.clean, self.tmp / "words.docx", insert={"word/document.xml": (b"<w:sectPr", words)})
        self.assertEqual(document.active_content(package_parts(path)), [])

    def test_every_part_under_word_is_checked(self):
        # Not only the body, the headers and the footers: a comments part, a glossary one.
        for part in ("word/comments.xml", "word/endnotes.xml", "word/glossary/document.xml"):
            with self.subTest(part=part):
                data = (b'<w:x xmlns:w="' + WORD.encode() + b'">' + complex_field(b" LINK" + TARGET) + b"</w:x>")
                path = edit_package(self.clean, self.tmp / "other.docx", add={part: data})
                self.assertIn(f"{part}: a LINK field", self.refused(path))


def _form_test(form):
    return lambda self: self.assert_form_refused(form)


for _form in FORMS:  # one test per form, each over every field
    setattr(FieldFormsTest, "test_refused_" + "_".join(_form.replace(",", "").split()), _form_test(_form))
del _form


class PackageTest(Workspace):
    """WI22-AC03."""

    MACRO = b"application/vnd.ms-word.document.macroEnabled.main+xml"

    def setUp(self):
        super().setUp()
        self.clean = company_template(self.tmp / "clean.docx")

    def refused(self, path, text):
        with self.assertRaises(document.ReportError) as raised:
            document.set_template(path, self.data)
        self.assertIn(text, str(raised.exception))
        self.assertIsNone(document.stored_template(self.data))

    def retype(self, name, old, new):
        """The clean template with a replacement in [Content_Types].xml."""
        parts = package_parts(self.clean)
        self.assertIn(old, parts["[Content_Types].xml"])
        types = parts["[Content_Types].xml"].replace(old, new)
        return edit_package(self.clean, self.tmp / name, add={"[Content_Types].xml": types})

    def test_a_macro_enabled_content_type_is_refused_however_it_is_written(self):
        main = document.DOCUMENT_TYPE
        writings = {
            "plainly": self.MACRO,
            "a character reference": b"application/vnd.ms-word.document.macro&#69;nabled.main+xml",
            "a hexadecimal one": b"application/vnd.ms-word.document.&#x6d;acroEnabled.main+xml",
            "lower case": self.MACRO.lower(),
            "upper case": self.MACRO.upper(),
            "a template's macro-enabled type": b"application/vnd.ms-word.template.macroEnabledTemplate.main+xml",
        }
        for label, content_type in writings.items():
            with self.subTest(writing=label):
                self.refused(self.retype("typed.docx", main, content_type), "carries macros")
        # in the other element and with the other quotes: a Default, single quotes
        types = (b"</Types>", b"<Default Extension='bin' ContentType='application/vnd.ms-office.vbaProject'/>")
        self.refused(edit_package(self.clean, self.tmp / "default.docx", insert={"[Content_Types].xml": types}),
                     "carries macros")
        # the type given by a CDATA-free but entity-decoded attribute in an Override of another part
        types = (b"</Types>", b'<Override PartName="/word/vbaData.xml" ContentType="application/vnd.ms-word.vba'
                              b'Data&#43;xml"/>')
        self.refused(edit_package(self.clean, self.tmp / "vba-data.docx", insert={"[Content_Types].xml": types}),
                     "carries macros")

    def test_a_macro_project_part_is_still_refused_whatever_its_case(self):
        for part in ("word/vbaProject.bin", "word/VBAPROJECT.BIN", "word/vbaProjectSignature.bin"):
            with self.subTest(part=part):
                self.refused(edit_package(self.clean, self.tmp / "project.docx", add={part: b"\x00" * 16}),
                             "carries macros")

    def test_a_part_that_is_not_xml_is_refused_naming_it(self):
        broken = {
            "word/header1.xml": b"this is not xml",
            "word/footer1.xml": b"<w:ftr",
            "word/styles.xml": b"",
            "word/settings.xml": b'<w:settings xmlns:w="' + WORD.encode() + b'"><w:a></w:b></w:settings>',
            "word/_rels/document.xml.rels": b"<Relationships><Relationship",
            "customXml/item1.xml": b"\xff\xfe not a document",
            "word/document.xml": b"<w:document><w:body/></w:document>",  # the prefix is not bound
            "[Content_Types].xml": b"<Types>",
        }
        for part, data in broken.items():
            with self.subTest(part=part):
                path = edit_package(self.clean, self.tmp / "broken.docx", add={part: data})
                self.refused(path, f"{part}: is not readable XML")

    def test_a_part_word_reads_by_its_content_type_is_checked_as_xml(self):
        # Word takes a part's kind from its content type, not from its name: a header called .dat is a header.
        override = (b"</Types>", b'<Override PartName="/word/header9.dat" ContentType="application/vnd.openxmlformats-'
                                 b'officedocument.wordprocessingml.header+xml"/>')
        field = b'<w:hdr xmlns:w="' + WORD.encode() + b'">' + complex_field(b" INCLUDETEXT" + TARGET) + b"</w:hdr>"
        path = edit_package(self.clean, self.tmp / "odd.docx", insert={"[Content_Types].xml": override},
                            add={"word/header9.dat": field})
        self.refused(path, "word/header9.dat: a INCLUDETEXT field")
        path = edit_package(self.clean, self.tmp / "odd-broken.docx", insert={"[Content_Types].xml": override},
                            add={"word/header9.dat": b"not xml"})
        self.refused(path, "word/header9.dat: is not readable XML")

    def test_a_binary_part_is_not_read_as_xml(self):
        # The thumbnail and a printer's settings are not XML, and a good template has them.
        self.assertIn("docProps/thumbnail.jpeg", package_parts(self.clean))
        printer = (b"</Types>", b'<Default Extension="bin" ContentType="application/vnd.openxmlformats-officedocument.'
                                b'presentationml.printerSettings"/>')
        path = edit_package(self.clean, self.tmp / "binary.docx", insert={"[Content_Types].xml": printer},
                            add={"word/printerSettings/printerSettings1.bin": b"\x00\x01<"})
        document.set_template(path, self.data)
        self.assertIsNotNone(document.stored_template(self.data))

    def test_the_relationships_are_read_whatever_the_case_of_what_they_say(self):
        items = {"an external link with the mode in lower case":
                 f'<Relationship Id="rId901" Type="{REL}image" Target="http://example.invalid/x" '
                 'TargetMode="external"/>',
                 "an object with the type in upper case":
                 f'<Relationship Id="rId902" Type="{REL}OLEOBJECT" Target="embeddings/o.bin"/>'}
        for label, item in items.items():
            with self.subTest(case=label):
                path = edit_package(self.clean, self.tmp / "rels.docx", insert={
                    "word/_rels/document.xml.rels": (b"</Relationships>", item.encode())})
                self.refused(path, "load or run from outside")


class ReportCheckTest(Workspace):
    """WI22-AC04: the report is checked again before it is delivered."""

    def with_field(self, name, form="as written", field="INCLUDETEXT"):
        base = package_parts(company_template(self.tmp / "company.docx"))
        return write_package(with_field(base, form, field)[0], self.tmp / name)

    def test_a_template_that_got_past_its_check_does_not_reach_the_report(self):
        for form in ("as written", "in a header", "in a footer"):
            with self.subTest(form=form):
                path = self.with_field("active.docx", form)
                with self.assertRaises(document.ReportError):
                    document.set_template(path, self.data)  # the template's own check refuses it
                # the check of the template switched off on purpose: it is read as it is, unchecked
                with mock.patch.object(document, "template_bytes", side_effect=lambda p: p.read_bytes()):
                    with self.assertRaisesRegex(document.ReportError, "the report was not written") as raised:
                        self.build(template=path)
                self.assertIn("a INCLUDETEXT field", str(raised.exception))
                self.assertNothingWritten()

    def test_a_report_without_active_content_is_delivered_as_before(self):
        path = company_template(self.tmp / "company.docx")
        with mock.patch.object(document, "template_bytes", side_effect=lambda p: p.read_bytes()):
            self.build(template=path)
        self.assertEqual(document.active_content(package_parts(self.output())), [])

    def test_the_check_of_a_report_names_what_it_found_in_both_languages(self):
        path = self.with_field("active.docx")
        with mock.patch.object(document, "template_bytes", side_effect=lambda p: p.read_bytes()):
            with self.assertRaises(document.ReportError) as raised:
                self.build(template=path)
        spanish, _ = raised.exception.message.render("es")
        self.assertIn("no se escribió el informe", spanish)
        self.assertIn("un campo INCLUDETEXT", spanish)


if __name__ == "__main__":
    unittest.main()
