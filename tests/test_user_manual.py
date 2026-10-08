"""Tests for the user manual (docs/manual/user-manual.html, WI33).

The manual is a page for a person who has never seen the program, in English, installed next to it. It is
only worth having if it stays true, so these tests tie it to the program: every name of a screen, field or
button it quotes is in the program's English texts, the numbers it gives are the code's, and the places it
names are the ones the installer and the window use. They read files; nothing is installed or opened.
"""

import html
import re
import unittest
from html.parser import HTMLParser
from pathlib import Path

from meetingtool import texts
from meetingtool.app import company, jobs, server, window
from meetingtool.projects import store

ROOT = Path(__file__).resolve().parent.parent
MANUAL = ROOT / "docs" / "manual" / "user-manual.html"
SOURCE = MANUAL.read_text(encoding="utf-8")

# What the manual calls a screen, a field, a button or a setting, each exactly as the program shows it in English.
# A name in this list has to be in the manual and in the program's texts; renaming one in either place fails here.
UI_NAMES = (
    "Projects", "Settings", "New project", "Create the project", "Name", "Client", "New meeting", "Title", "Date",
    "Transcript", "Video", "Meeting type", "No type", "Language of the result", "The meeting's",
    "Estimated spending ceiling in dollars", "Process", "Summary", "Questions and answers", "Processing",
    "Frames of the video", "Reading of the frames", "Word report", "Saving the meeting in the project",
    "Open the Word report", "What the project already knows", "Kept from runs that failed", "Discard",
    "Language of the application", "Company", "Gemini key", "New key", "Save the key", "Delete the key",
    "The company's Word template", "Download an example template",
    "Presale", "Sales or negotiation", "Requirements gathering", "Project kickoff", "Status", "Technical",
    "Training",
)


class Text(HTMLParser):
    """The visible text of the page, the ids it defines and the links and files it points to."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.ids, self.links, self.tags, self.parts = set(), [], [], []
        self.skip = 0

    def handle_starttag(self, tag, attributes):
        attributes = dict(attributes)
        self.tags.append((tag, attributes))
        if "id" in attributes:
            self.ids.add(attributes["id"])
        if "href" in attributes:
            self.links.append(attributes["href"])
        if tag in ("style", "script"):
            self.skip += 1

    def handle_endtag(self, tag):
        if tag in ("style", "script"):
            self.skip -= 1

    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)


PAGE = Text()
PAGE.feed(SOURCE)
VISIBLE = html.unescape(" ".join(PAGE.parts))
VISIBLE = re.sub(r"\s+", " ", VISIBLE)


def program_texts():
    """Every sentence and word of the program's English catalogue, as a set of strings with the markup of its
    placeholders left out, to look a quoted name up in."""
    catalogue = texts.catalog("en")
    return {re.sub(r"\[\[.*?\]\]", "", value) for value in catalogue.values()}


class StructureTest(unittest.TestCase):
    def test_it_is_a_whole_english_page_that_needs_nothing_from_outside(self):
        self.assertTrue(SOURCE.lstrip().lower().startswith("<!doctype html>"))
        html_tag = next(attributes for tag, attributes in PAGE.tags if tag == "html")
        self.assertEqual(html_tag.get("lang"), "en")
        self.assertTrue(re.search(r"<title>[^<]+</title>", SOURCE))
        self.assertFalse([tag for tag, _ in PAGE.tags if tag in ("script", "iframe", "object", "embed", "img", "link")],
                         "it carries a script, a frame or an outside file")
        for tag, attributes in PAGE.tags:
            for name in ("src", "srcset", "data"):
                self.assertNotIn(name, attributes, f"<{tag}> points to a file")
        self.assertNotRegex(SOURCE, r"url\(\s*['\"]?(?:https?:)?//", "a style reaches the network")
        for link in PAGE.links:
            self.assertTrue(link.startswith("#"), f"a link leaves the page: {link}")

    def test_every_link_inside_the_page_has_a_place_to_go_and_the_ids_are_not_repeated(self):
        for link in PAGE.links:
            self.assertIn(link[1:], PAGE.ids, link)
        ids = re.findall(r'\sid="([^"]+)"', SOURCE)
        self.assertEqual(len(ids), len(set(ids)))

    def test_the_sections_are_numbered_in_order_and_each_is_in_the_contents(self):
        headings = re.findall(r'<h2 id="([^"]+)">(\d+)\. ([^<]+)</h2>', SOURCE)
        self.assertGreaterEqual(len(headings), 10)
        self.assertEqual([int(number) for _, number, _ in headings], list(range(1, len(headings) + 1)))
        contents = re.search(r'<nav class="toc".*?</nav>', SOURCE, re.DOTALL).group(0)
        for identifier, _, title in headings:
            self.assertIn(f'href="#{identifier}"', contents)
            self.assertIn(html.unescape(title), html.unescape(contents))

    def test_it_covers_what_a_person_installing_it_for_the_first_time_has_to_do(self):
        for needle in ("Installing", "Gemini key", "Your first meeting", "Cost and the spending ceiling",
                       "Where your files are", "Privacy", "Updating and uninstalling", "Troubleshooting",
                       "Run anyway", "WebView2", "Credential Manager"):
            self.assertIn(needle, VISIBLE)

    def test_it_changes_with_the_system_theme_and_prints_without_its_menu(self):
        self.assertIn("prefers-color-scheme: dark", SOURCE)
        self.assertIn('name="viewport"', SOURCE)
        self.assertIn("@media print", SOURCE)


class ItIsTrueTest(unittest.TestCase):
    def test_every_name_it_quotes_from_the_screens_is_in_the_program_and_in_the_manual(self):
        known = program_texts()
        for name in UI_NAMES:
            self.assertIn(name, VISIBLE, f"the manual does not say {name!r}")
            self.assertIn(name, known, f"the program does not show {name!r}")

    def test_the_numbers_it_gives_are_the_code_s(self):
        self.assertEqual(f"US${jobs.DEFAULT_MAX_COST_USD:.2f}", "US$1.00")
        self.assertIn("US$1.00", VISIBLE)
        limits = server.UPLOAD_LIMITS
        self.assertIn(f"Up to {limits['transcript'] // 1_000_000} MB", VISIBLE)
        self.assertIn(f"up to {limits['recording'] // 1_000_000_000} GB", VISIBLE)
        self.assertIn("up to 1 MB", VISIBLE)  # the logo
        self.assertEqual(company.LOGO_LIMIT, 1024 * 1024)

    def test_the_files_it_accepts_are_the_ones_the_program_accepts(self):
        for suffix in jobs.RECORDING_SUFFIXES:
            self.assertIn(suffix, VISIBLE)
        for suffix in jobs.TRANSCRIPT_SUFFIXES:
            self.assertIn(suffix, VISIBLE)

    def test_the_places_it_names_are_the_ones_the_program_uses(self):
        self.assertIn(f"C:\\Users\\<you>\\{store.DEFAULT_DATA_DIR_NAME}", VISIBLE)
        self.assertIn(f"AppData\\Local\\VisualMeetingTool\\{window.LOG_NAME}", VISIBLE)
        iss = (ROOT / "packaging" / "installer.iss").read_text(encoding="utf-8")
        self.assertIn("DefaultDirName={autopf}\\VisualMeetingTool", iss)
        self.assertIn("C:\\Users\\<you>\\AppData\\Local\\Programs\\VisualMeetingTool", VISIBLE)

    def test_the_languages_and_the_kinds_of_meeting_it_lists_are_the_program_s(self):
        self.assertEqual(sorted(texts.LANGUAGES), ["en", "es"])
        for word in ("Spanish", "English"):
            self.assertIn(word, VISIBLE)

    def test_it_does_not_promise_what_the_program_does_not_do(self):
        # No price is quoted: the program works from list prices that Google can change.
        self.assertNotRegex(VISIBLE, r"US\$\s*0\.\d")
        # The ceiling is an estimate (WI28), and the manual calls it so.
        self.assertIn("not a guarantee", VISIBLE)
        self.assertIn("estimated ceiling", VISIBLE)
        self.assertEqual(jobs.DEFAULT_MAX_COST_USD, 1.0)


if __name__ == "__main__":
    unittest.main()
