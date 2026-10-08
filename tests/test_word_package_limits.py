"""Tests for what a Word package expands to (WI29, the external review's R08;
the limitations register's WI22-P3-2): every package the program reads
(a Word transcript, a report template, the report's last check) is read by
meetingtool.word_package, which refuses, before parsing anything, a package
with more than 4,000 entries, a part that expands to more than 32 MB, or
parts that expand to more than 256 MB together, counting the bytes it
decompresses and not what the package's directory says.

- LimitsTest (WI29-AC01): each limit, through the reader, with the message in
  both languages; the review's own case (about 5 KB expanding to 5,000,000
  characters) is read; the refusal stops reading at the limit, in bytes
  decompressed and in memory.
- CallersTest (WI29-AC01): the three readers (transcript, template, report
  check) refuse each limit with their own message.
- DirectoryTest (WI29-AC02): the size the directory states decides nothing.

The packages are made here, of repetitive bytes, so they are kilobytes on
disk and tens or hundreds of megabytes once expanded; nothing is committed.
"""

import struct
import tempfile
import tracemalloc
import unittest
import zipfile
from pathlib import Path
from unittest import mock

from meetingtool import word_package
from meetingtool.frames import transcript
from meetingtool.report import document
from tests.test_report import company_template, package_parts

MB = 1024 * 1024
# Written here, not taken from the product: a test that borrowed the product's
# constants would agree with it even where it is wrong.
ENTRIES, PART, PACKAGE = 4000, 32 * MB, 256 * MB
DOCUMENT_OPEN = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                 '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>')
DOCUMENT_CLOSE = "</w:body></w:document>"
TEAMS_BLOCK = "<w:p><w:r><w:br/><w:t>Ana   0:05</w:t><w:br/><w:t>hola</w:t></w:r></w:p>"
RUN = b"<w:t>a</w:t>"


class Filler:
    """A part of `size` bytes, written in pieces so that it is never held whole."""

    def __init__(self, size, unit=RUN, head=b"", tail=b""):
        self.size, self.unit, self.head, self.tail = size, unit, head, tail

    def write_to(self, handle):
        handle.write(self.head)
        piece = self.unit * (MB // len(self.unit))
        left = (self.size - len(self.head) - len(self.tail)) // len(self.unit)  # whole units: the XML stays well formed
        while left > 0:
            handle.write(piece[:left * len(self.unit)])
            left -= len(piece) // len(self.unit)
        handle.write(self.tail)


def write_package(path, parts, level=1):
    """A ZIP at path: each part is bytes or a Filler. Level 1 compression, as
    the repetitive parts shrink to a few thousandths of their size anyway."""
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED, compresslevel=level) as archive:
        for name, content in parts.items():
            if isinstance(content, Filler):
                with archive.open(name, "w") as handle:
                    content.write_to(handle)
            else:
                archive.writestr(name, content)
    return Path(path)


def document_xml(size):
    """A transcript's document.xml of `size` bytes: a Teams block, then runs."""
    return Filler(size, head=(DOCUMENT_OPEN + TEAMS_BLOCK).encode(), tail=DOCUMENT_CLOSE.encode())


def state_size(path, size):
    """The package at path (one part) with the size its directory states, in
    the central directory and in the local header, changed to `size`."""
    raw = bytearray(Path(path).read_bytes())
    struct.pack_into("<I", raw, raw.rindex(b"PK\x01\x02") + 24, size)
    struct.pack_into("<I", raw, raw.index(b"PK\x03\x04") + 22, size)
    Path(path).write_bytes(bytes(raw))
    return Path(path)


class Packages(unittest.TestCase):
    """The packages the tests read, made once."""

    @classmethod
    def setUpClass(cls):
        folder = tempfile.TemporaryDirectory()
        cls.addClassCleanup(folder.cleanup)
        cls.tmp = Path(folder.name)
        cls.clean = company_template(cls.tmp / "clean.docx")
        cls.clean_parts = package_parts(cls.clean)
        cls.too_many = write_package(cls.tmp / "many.docx", {
            **{f"customXml/item{number}.xml": b"<x/>" for number in range(ENTRIES + 1)},
            "word/document.xml": document_xml(1000)})
        cls.at_the_limit = write_package(cls.tmp / "four-thousand.docx", {
            **{f"customXml/item{number}.xml": b"<x/>" for number in range(ENTRIES - 1)},
            "word/document.xml": document_xml(1000)})
        cls.big_part = write_package(cls.tmp / "part.docx", {"word/document.xml": document_xml(40 * MB)})
        cls.huge_part = write_package(cls.tmp / "huge.docx", {"word/document.xml": document_xml(100 * MB)})
        cls.spread = write_package(cls.tmp / "spread.docx", {
            **{f"customXml/item{number}.xml": Filler(30 * MB) for number in range(9)},
            "word/document.xml": document_xml(1000)})
        cls.review_case = write_package(cls.tmp / "review.docx", {"word/document.xml": Filler(
            5_000_000, unit=b"a", head=(DOCUMENT_OPEN + "<w:p><w:r><w:br/><w:t>Ana   0:05</w:t><w:br/><w:t>").encode(),
            tail=("</w:t></w:r></w:p>" + DOCUMENT_CLOSE).encode())}, level=9)

    def template(self, name, extra):
        """The clean template with more parts."""
        return write_package(self.tmp / name, {**self.clean_parts, **extra})


class LimitsTest(Packages):
    def test_the_limits_are_the_contract_s(self):
        self.assertEqual((word_package.MAX_ENTRIES, word_package.MAX_PART_BYTES, word_package.MAX_PACKAGE_BYTES),
                         (ENTRIES, PART, PACKAGE))

    def test_a_package_within_the_limits_is_read_whole(self):
        self.assertEqual(word_package.read_parts(self.clean), self.clean_parts)
        self.assertEqual(word_package.read_parts(self.clean, ["word/document.xml"]),
                         {"word/document.xml": self.clean_parts["word/document.xml"]})
        self.assertEqual(len(word_package.read_parts(self.at_the_limit)), ENTRIES)

    def test_a_part_the_package_lacks_is_a_key_error_as_before(self):
        with self.assertRaises(KeyError):
            word_package.read_parts(self.clean, ["word/nothing.xml"])

    def test_more_entries_than_the_limit_are_refused_before_reading_anything(self):
        with mock.patch.object(zipfile.ZipFile, "open", side_effect=AssertionError("a part was opened")):
            with self.assertRaises(word_package.PackageError) as raised:
                word_package.read_parts(self.too_many)
        self.assertIn(f"the file holds {ENTRIES + 2} parts, and a Word file may hold at most {ENTRIES}",
                      raised.exception.text("en"))
        self.assertIn(f"el archivo trae {ENTRIES + 2} partes, y uno de Word puede traer {ENTRIES} como máximo",
                      raised.exception.text("es"))

    def test_a_part_over_the_limit_is_refused_naming_the_part(self):
        """WI22-P3-2's case: a few kilobytes that expand to 40 MB."""
        self.assertLess(self.big_part.stat().st_size, 1024 * 1024)
        with self.assertRaises(word_package.PackageError) as raised:
            word_package.read_parts(self.big_part)
        self.assertIn("the part word/document.xml is larger than 32 MB once expanded", raised.exception.text("en"))
        self.assertIn("la parte word/document.xml ocupa más de 32 MB una vez expandida", raised.exception.text("es"))

    def test_parts_each_within_the_limit_that_together_are_over_it_are_refused(self):
        self.assertLess(self.spread.stat().st_size, 5_000_000)
        with self.assertRaises(word_package.PackageError) as raised:
            word_package.read_parts(self.spread)
        self.assertIn("the parts together are larger than 256 MB once expanded", raised.exception.text("en"))
        self.assertIn("(it went over at customXml/item8.xml)", raised.exception.text("en"))
        self.assertIn("las partes juntas ocupan más de 256 MB una vez expandidas", raised.exception.text("es"))
        self.assertIn("(se pasó en customXml/item8.xml)", raised.exception.text("es"))

    def test_the_refusal_stops_reading_at_the_limit(self):
        """Of a part that expands to 100 MB, no more than the limit (and a
        chunk) is decompressed, and the memory held stays near the limit."""
        counted = [0]
        original = zipfile.ZipExtFile.read

        def read(extracted, size=-1):
            data = original(extracted, size)
            counted[0] += len(data)
            return data

        tracemalloc.start()
        try:
            with mock.patch.object(zipfile.ZipExtFile, "read", read):
                with self.assertRaises(word_package.PackageError):
                    word_package.read_parts(self.huge_part)
            peak = tracemalloc.get_traced_memory()[1]
        finally:
            tracemalloc.stop()
        self.assertLessEqual(counted[0], PART + word_package.CHUNK)
        self.assertLess(peak, 2 * PART)

    def test_the_review_s_case_is_read(self):
        """About 5 KB that expand to 5,000,000 characters are within the limits."""
        self.assertLess(self.review_case.stat().st_size, 10_000)
        turns = transcript.read_turns(self.review_case)
        self.assertEqual(turns[0][:2], (5, "Ana"))
        self.assertGreater(len(turns[0][2]), 4_900_000)


class CallersTest(Packages):
    """Each of the three readers turns the refusal into its own message."""

    def test_a_word_transcript_over_a_limit_is_refused(self):
        # Only word/document.xml is read, so the total cannot be passed here.
        for label, path, key in (("entries", self.too_many, "the file holds"),
                                 ("a part", self.big_part, "the part word/document.xml is larger than 32 MB")):
            with self.subTest(label):
                with self.assertRaises(transcript.TranscriptError) as raised:
                    transcript.read_turns(path)
                self.assertEqual(raised.exception.message.key, "transcript.word_too_big")
                self.assertIn(f"cannot read the Word transcript {path}: ", str(raised.exception))
                self.assertIn(key, str(raised.exception))
                self.assertIn("no se puede leer la transcripción de Word", raised.exception.text("es"))

    def test_a_template_over_a_limit_is_refused(self):
        for label, parts, key in (
                ("entries", {f"customXml/item{number}.xml": b"<x/>" for number in range(ENTRIES)}, "the file holds"),
                ("a part", {"customXml/big.xml": Filler(40 * MB)}, "the part customXml/big.xml is larger than 32 MB"),
                ("the total", {f"customXml/item{number}.xml": Filler(30 * MB) for number in range(9)},
                 "the parts together are larger than 256 MB")):
            with self.subTest(label):
                path = self.template("template.docx", parts)
                with self.assertRaises(document.ReportError) as raised:
                    document.template_bytes(path)
                self.assertEqual(raised.exception.message.key, "report.template_too_big")
                self.assertIn(key, str(raised.exception))
                self.assertIn("la plantilla template.docx no se puede usar", raised.exception.text("es"))

    def test_a_report_over_a_limit_is_not_delivered(self):
        path = self.template("report.docx", {"customXml/big.xml": Filler(40 * MB)})
        with self.assertRaises(document.ReportError) as raised:
            document.check_active_content(path)
        self.assertEqual(raised.exception.message.key, "report.too_big")
        self.assertIn("the report was not written: the part customXml/big.xml is larger than 32 MB",
                      str(raised.exception))
        self.assertIn("no se escribió el informe: la parte customXml/big.xml ocupa más de 32 MB",
                      raised.exception.text("es"))

    def test_the_example_template_and_a_clean_report_are_read_as_before(self):
        self.assertTrue(document.template_bytes(self.clean))
        document.check_active_content(self.clean)


class DirectoryTest(Packages):
    """WI29-AC02: the size the package's directory states decides nothing."""

    def test_a_directory_that_states_less_than_the_part_holds_does_not_get_it_read(self):
        """The library itself stops at the stated size and finds the checksum
        wrong, so nothing is returned; the next test is the one that shows
        the limit is not taken from the directory."""
        path = state_size(write_package(self.tmp / "lies-small.docx",
                                        {"word/document.xml": document_xml(40 * MB)}), 100)
        with self.assertRaises((word_package.PackageError, zipfile.BadZipFile)):
            word_package.read_parts(path)
        with self.assertRaises(transcript.TranscriptError):
            transcript.read_turns(path)

    def test_a_directory_that_states_more_than_the_limit_does_not_refuse_what_is_small(self):
        """The bytes decompressed are counted, not the directory's number."""
        path = state_size(write_package(self.tmp / "lies-big.docx", {"word/document.xml": document_xml(1000)}),
                          40 * MB)
        with zipfile.ZipFile(path) as archive:
            self.assertEqual(archive.getinfo("word/document.xml").file_size, 40 * MB)
        self.assertGreater(len(word_package.read_parts(path)["word/document.xml"]), 900)
        self.assertEqual(transcript.read_turns(path)[0][:2], (5, "Ana"))


if __name__ == "__main__":
    unittest.main()
