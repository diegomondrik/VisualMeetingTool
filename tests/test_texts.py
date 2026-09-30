"""Tests for the language of the application and the list of messages
(meetingtool.texts, WI17, INGOL D-188).

- CatalogTest (WI17-AC04): every entry in every language, with the same data.
- SourceTest (WI17-AC06, and the script's half of AC03): every error the
  program raises, and every text it names, is an entry of the list.
- ScreensLanguageTest (WI17-AC03): every screen in each language, and in a
  language made up here whose every text is a marker, so that a text written
  in a page instead of the list shows up as a word outside the markers.
- StageLanguageTest (WI17-AC05): each stage fails, through the application,
  in the language it is set to.
- OutsideTest (WI17-AC07): what comes from outside is a detail.
- TerminalTest (WI17-AC09): the terminal keeps its English.
"""

import ast
import html.parser
import json
import re
import string
import unittest
from pathlib import Path
from unittest import mock

from PIL import Image

from meetingtool import texts
from meetingtool.app import company, jobs, library, pages
from meetingtool.projects import store
from meetingtool.reading import gemini
from meetingtool.report import document
from meetingtool.summary import writer
from tests import test_qa, test_report, test_summary
from tests.test_app import Processing, Running
from tests.test_reading import answer_for

REPOSITORY = Path(__file__).resolve().parent.parent
PACKAGE = REPOSITORY / "meetingtool"
SCRIPT = PACKAGE / "app" / "static" / "app.js"
LANGUAGES = texts.LANGUAGES
SPANISH, ENGLISH = writer._SPANISH, writer._ENGLISH
OTHER_WORDS = {"es": ENGLISH, "en": SPANISH}
PSEUDO = "xx"
MARKER = re.compile(r"⟦[a-z0-9_.]+⟧")


def fields(text):
    """(name, conversion, spec) of each piece of data a text names, in order,
    once each."""
    seen, found = set(), []
    for _, field, spec, conversion in string.Formatter().parse(text):
        if field and field not in seen:
            seen.add(field)
            found.append((field, conversion, spec))
    return found


def sample(text):
    """Data for every name of a text, of a kind its format takes."""
    return {name: 1.5 if spec and spec[-1] in "fdg" else "x" for name, _, spec in fields(text)}


def pseudo_catalog():
    """A language of markers: each entry says only its key, and the data it
    names, so that nothing of it is a word."""
    catalog = {}
    for key, text in texts.catalog("en").items():
        detail = texts.detail_names(text)

        def said(name, conversion, spec):
            return "{" + name + (f"!{conversion}" if conversion else "") + (f":{spec}" if spec else "") + "}"

        plain = " ".join(said(*field) for field in fields(text) if field[0] not in detail)
        hidden = " ".join(said(*field) for field in fields(text) if field[0] in detail)
        catalog[key] = f"⟦{key}⟧" + (f" {plain}" if plain else "") + (f"[[ {hidden}]]" if hidden else "")
    return catalog


def with_pseudo_language(test):
    """Run `test` with the made-up language available to the application."""
    patcher = mock.patch.object(texts, "LANGUAGES", LANGUAGES + (PSEUDO,))
    patcher.start()
    texts._catalogs[PSEUDO] = pseudo_catalog()
    test.addCleanup(patcher.stop)
    test.addCleanup(texts._catalogs.pop, PSEUDO, None)


# ── WI17-AC04: every entry in every language, with the same data ──────────────

class CatalogTest(unittest.TestCase):
    def test_every_language_has_every_entry(self):
        keys = set(texts.catalog(texts.TERMINAL))
        for language in LANGUAGES:
            self.assertEqual(set(texts.catalog(language)), keys, language)
        self.assertGreater(len(keys), 300)

    def test_every_entry_names_the_same_data_in_every_language(self):
        for key, english in texts.catalog("en").items():
            for language in LANGUAGES:
                other = texts.catalog(language)[key]
                self.assertEqual(texts.names(other), texts.names(english), (language, key))
                self.assertEqual(texts.detail_names(other), texts.detail_names(english), (language, key))
                self.assertEqual({(n, c, s) for n, c, s in fields(other)}, {(n, c, s) for n, c, s in fields(english)},
                                 (language, key))

    def test_every_entry_can_be_said_in_the_terminal_and_the_application(self):
        for key, english in texts.catalog("en").items():
            for language in LANGUAGES:
                text = texts.catalog(language)[key]
                self.assertEqual(text.count("[["), text.count("]]"), (language, key))
                params = sample(english)
                texts.render(key, params, language, app=False)
                outside = {name: texts.External("y") if name in texts.detail_names(english) else value
                           for name, value in params.items()}
                said, details = texts.render(key, outside, language, app=True)
                self.assertNotIn("[[", said, (language, key))
                self.assertEqual(len(details), len(texts.detail_names(english)), (language, key))

    def test_what_comes_from_outside_is_only_ever_in_a_detail(self):
        # A name inside [[ ]] must not appear outside it too: the application
        # drops the part and would still say the outside text.
        for language in LANGUAGES:
            for key, text in texts.catalog(language).items():
                outside = texts.SEGMENT.sub("", text)
                self.assertFalse(texts.names(outside) & texts.detail_names(text), (language, key))

    def test_the_scripts_entries_carry_plain_names(self):
        # static/app.js puts the data in itself, by {name}: no format, no detail.
        for language in LANGUAGES:
            for key, text in texts.catalog(language).items():
                if key.startswith("js."):
                    self.assertNotIn("[[", text, key)
                    self.assertFalse([f for f in fields(text) if f[1] or f[2]], key)
                    self.assertNotIn("{{", text, key)

    def test_each_language_speaks_its_own(self):
        """An entry left in the other language (copied and not translated) is
        caught: an English entry holds no common Spanish word, and a Spanish
        one no common English word, their data left out."""
        for language in LANGUAGES:
            for key, text in texts.catalog(language).items():
                bare = re.sub(r"\{[^{}]*\}", " ", text)
                self.assertEqual(OTHER_WORDS[language].findall(bare), [], (language, key, text))

    def test_an_entry_is_the_same_in_both_languages_only_where_it_should(self):
        same = {key for key, text in texts.catalog("en").items()
                if text == texts.catalog("es")[key] and re.search(r"[^\W\d_]{3,}", re.sub(r"\{[^{}]*\}", "", text))}
        self.assertEqual(same, set(KNOWN_SAME))


# Entries that are written the same in both languages, and why.
KNOWN_SAME = {
    "app.company.logo": "a logo is a logo",
    "app.new.recording": "video, in both",
    "app.console.error": "the console's prefix, as the commands write it",
}


# ── WI17-AC06: every error the program raises is an entry ─────────────────────

def failure_classes():
    """The names of the program's errors, which say an entry."""
    import importlib
    import pkgutil

    found = {}
    for module in pkgutil.walk_packages([str(PACKAGE)], "meetingtool."):
        if module.name.endswith("__main__"):
            continue
        loaded = importlib.import_module(module.name)
        for name, value in vars(loaded).items():
            if isinstance(value, type) and issubclass(value, BaseException) and value.__module__ == loaded.__name__:
                found[name] = value
    return found


# A raise of an error that is not the program's, and why it says no entry.
OUTSIDE_RAISES = {
    ("meetingtool/frames/similarity.py", "ValueError"): "a programming error: two images of different sizes",
    ("meetingtool/summary/qa.py", "ValueError"): "caught on the next line and said as meeting.bad_date",
    ("meetingtool/report/__main__.py", "argparse.ArgumentTypeError"): "the terminal's argument parser says it",
    ("meetingtool/app/library.py", "NotFound"): "never said: the server answers app.not_found",
    ("meetingtool/app/server.py", "library.NotFound"): "never said: the server answers app.not_found",
}
# Errors of the program that are not said to anyone.
UNSAID = {"NotFound"}
# Calls that name an entry by its key, as their first argument (Refused: second).
SAYING = {"Message", "t", "say", "markup", "said"}
# Every text of the page's script that is not for a person: addresses, names of
# fields, events and elements, headers.
SCRIPT_TECHNICAL = {
    "X-MeetingTool", "1", "{}", "{", "}", "use strict", "US$", "es", ".", ",", ".message", "bad", "POST", "PUT",
    "Content-Type", "application/json", "application/octet-stream", "same-origin", "file", "radio", "submit",
    "form[data-api]", "project", "/p/", "button[data-open]", "click", "/api/open", "?name=", "template",
    "/api/template", "logo", "/api/logo", "process", "button[type=submit]", "summary",
    "/api/upload?kind=transcript&name=", "/api/upload?kind=recording&name=", "/api/process", "/job/", "td", "h2",
    "table", "list", "tr", "th", "stage ", "pending", "skipped", "", " s", "done", "p", "a", "button", "/m/",
    "failed", "hint detail", "/new", "job", "/api/jobs/", "running", "/api/running", "DOMContentLoaded", " — ",
}


def call_name(node):
    func = node.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        prefix = call_name(ast.Call(func=func.value, args=[], keywords=[])) if isinstance(func.value, (ast.Name, ast.Attribute)) else ""
        return f"{prefix}.{func.attr}" if prefix else func.attr
    return ""


def sources():
    for path in sorted(PACKAGE.rglob("*.py")):
        yield path.relative_to(REPOSITORY).as_posix(), ast.parse(path.read_text(encoding="utf-8"))


def check_key_call(node, key_index, where):
    """Problems of a call naming an entry: its key is one, and its data is
    the entry's."""
    if len(node.args) <= key_index:
        return [f"{where}: no key"]
    key = node.args[key_index]
    if isinstance(key, ast.Attribute) and key.attr == "message" and not node.keywords:
        return []  # another failure's message, said again
    if not (isinstance(key, ast.Constant) and isinstance(key.value, str)):
        return []  # a key held in a table: the table's keys are checked as texts of the program
    if key.value not in texts.catalog(texts.TERMINAL):
        return [f"{where}: {key.value!r} is not an entry of the list"]
    if any(keyword.arg is None for keyword in node.keywords):
        return []
    given = {keyword.arg for keyword in node.keywords}
    wanted = texts.names(texts.catalog(texts.TERMINAL)[key.value])
    if given != wanted:
        return [f"{where}: {key.value} names {sorted(wanted)}, and the call gives {sorted(given)}"]
    return []


def source_problems():
    classes = failure_classes()
    failures = {name for name, cls in classes.items() if issubclass(cls, texts.Failure)}
    problems = []
    for name, cls in classes.items():
        if not issubclass(cls, texts.Failure) and name not in UNSAID:
            problems.append(f"{cls.__module__}.{name} is an error of the program that says no entry")
    for relative, tree in sources():
        if relative.startswith("meetingtool/texts/"):
            continue
        for node in ast.walk(tree):
            where = f"{relative}:{getattr(node, 'lineno', '?')}"
            if isinstance(node, ast.Raise) and isinstance(node.exc, ast.Call):
                name = call_name(node.exc)
                simple = name.rsplit(".", 1)[-1]
                if simple in failures:
                    problems += check_key_call(node.exc, 1 if simple == "Refused" else 0, where)
                    first = node.exc.args[1 if simple == "Refused" else 0] if node.exc.args else None
                    if not (isinstance(first, ast.Constant) or (isinstance(first, ast.Attribute)
                                                                and first.attr == "message")):
                        problems.append(f"{where}: {simple} raised with text that is not a key")
                elif (relative, name) not in OUTSIDE_RAISES:
                    problems.append(f"{where}: {name} is raised with text outside the list of messages")
            elif isinstance(node, ast.Call) and call_name(node).rsplit(".", 1)[-1] in SAYING:
                problems += check_key_call(node, 0, where)
    return problems


def program_keys():
    """Every text of the program (Python and the page's script) that is a
    key, or looks like one."""
    namespaces = {key.split(".", 1)[0] for key in texts.catalog(texts.TERMINAL)}
    shape = re.compile(rf"^(?:{'|'.join(namespaces)})(?:\.[a-z0-9_]+)+$")
    found = []
    for relative, tree in sources():
        if relative.startswith("meetingtool/texts/"):
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str) and shape.match(node.value):
                found.append((relative, node.value))
    for literal in script_literals():
        if shape.match(literal):
            found.append(("meetingtool/app/static/app.js", literal))
    return [(where, key) for where, key in found if key.rsplit(".", 1)[-1] not in FILE_SUFFIXES]


# A file's name has the shape of a key: summary.docx, qa.json, app.js...
FILE_SUFFIXES = {"docx", "dotx", "json", "md", "js", "css", "jpg", "png", "txt", "log"}


def script_literals(source=None):
    source = SCRIPT.read_text(encoding="utf-8") if source is None else source
    source = re.sub(r"^\s*//.*$", "", source, flags=re.MULTILINE)
    return re.findall(r'"((?:[^"\\\n]|\\.)*)"', source)


def script_problems(source=None):
    problems = []
    for literal in script_literals(source):
        if literal.startswith("js."):
            if literal not in texts.catalog(texts.TERMINAL):
                problems.append(f"app.js: {literal!r} is not an entry of the list")
        elif literal not in SCRIPT_TECHNICAL:
            problems.append(f"app.js: {literal!r} is written in the script, not taken from the list")
    return problems


class SourceTest(unittest.TestCase):
    def test_every_error_the_program_raises_is_an_entry_with_its_data(self):
        self.assertEqual(source_problems(), [])

    def test_the_check_catches_text_and_missing_data(self):
        """WI17-AC06 shown here too: a raise with written text, one with a
        missing value, and one of a key that does not exist are caught."""
        planted = {
            "meetingtool/planted.py": "from meetingtool.frames.extract import FramesError\n"
                                      "def f(path):\n    raise FramesError(f'recording {path} is broken')\n",
            "meetingtool/planted2.py": "from meetingtool.frames.extract import FramesError\n"
                                       "def f(path):\n    raise FramesError('frames.not_local')\n",
            "meetingtool/planted3.py": "from meetingtool.frames.extract import FramesError\n"
                                       "def f(path):\n    raise FramesError('frames.no_such_entry', path=path)\n",
        }
        real = sources

        def with_planted():
            yield from real()
            for relative, source in planted.items():
                yield relative, ast.parse(source)

        with mock.patch(f"{__name__}.sources", with_planted):
            problems = source_problems()
        self.assertEqual(len(problems), 3, problems)
        self.assertIn("raised with text that is not a key", problems[0])
        self.assertIn("names ['path']", problems[1])
        self.assertIn("is not an entry of the list", problems[2])

    def test_every_key_the_program_names_is_an_entry_and_every_entry_is_used(self):
        named = program_keys()
        catalog = set(texts.catalog(texts.TERMINAL))
        self.assertEqual([(where, key) for where, key in named if key not in catalog], [])
        used = {key for _, key in named}
        self.assertEqual(sorted(catalog - used), [])

    def test_the_page_script_takes_every_text_from_the_list(self):
        self.assertEqual(script_problems(), [])

    def test_a_text_written_in_the_script_is_caught(self):
        source = SCRIPT.read_text(encoding="utf-8").replace('say(form, text("js.wait"));',
                                                           'say(form, "Un momento…");')
        self.assertEqual(script_problems(source), ["app.js: 'Un momento…' is written in the script, not taken "
                                                   "from the list"])


# ── WI17-AC03: every screen in the language it is set to ──────────────────────

class _Visible(html.parser.HTMLParser):
    """What a person reads in a page: its text, the titles and alternative
    texts, what the script will say (data-texts) and the confirmations."""

    SAID_ATTRIBUTES = ("title", "alt", "placeholder", "aria-label", "data-confirm")

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts, self.skip, self.script_texts = [], 0, {}

    def handle_starttag(self, tag, attributes):
        if tag in ("script", "style"):
            self.skip += 1
        for name, value in attributes:
            if name in self.SAID_ATTRIBUTES and value:
                self.parts.append(value)
            if name == "data-texts" and value:
                self.script_texts = json.loads(value)

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self.skip -= 1

    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)


def visible(page):
    """(the text a person reads, what the page's script says) of a page, with
    the meeting's own content (its summary, the project's knowledge) left out:
    it is in the language it was written in."""
    page = re.sub(r'<section class="summary">.*?</section>', " ", page, flags=re.DOTALL)
    page = re.sub(r'<div class="summary knowledge">.*?</div>', " ", page, flags=re.DOTALL)
    reader = _Visible()
    reader.feed(page)
    return "\n".join(reader.parts), reader.script_texts


# The data the screens show, written so that none of it is a word of either
# language: what is left of a page without it is what the application says.
PROJECT, CLIENT, COMPANY = "Zeta 9", "Omega", "Nexo"
PROCESSED, TERMINAL, LOOSE, TEMPLATE = "Kappa 3", "Sigma 2", "tanda-07", "G7.dotx"
DATA = (PROJECT, CLIENT, COMPANY, PROCESSED, TERMINAL, LOOSE, TEMPLATE, "zeta-9", "MeetingTool", "US$", "HTTP",
        "Gemini", "Word")
ALLOWED_WORDS = {"s", PSEUDO}  # the seconds' unit, next to a number; the made-up language's code
NAMES = re.compile(r"\{[a-z_]+\}")  # the data an entry of the page's script names, which the script puts in


def without_data(text, more=()):
    for value in sorted(DATA + tuple(more), key=len, reverse=True):
        text = text.replace(value, " ")
    return NAMES.sub(" ", text)


def leftover_words(text, more=()):
    """The words of a text of the made-up language that are not markers or data."""
    text = without_data(MARKER.sub(" ", text), more)
    return [word for word in re.findall(r"[^\W\d_]+", text) if word not in ALLOWED_WORDS]


class ScreensLanguageTest(Running):
    """Every screen, set to each language."""

    key = "AIzaFAKEFAKEFAKE"

    def setUp(self):
        super().setUp()
        with_pseudo_language(self)
        self.project = store.create_project(self.data, PROJECT, CLIENT)["id"]
        folder = self.data / self.project / library.RESULTS_DIR / "2026-09-25-kappa-3-a1b2c3"
        folder.mkdir(parents=True)
        frame = "frame_007_t00-12-34.jpg"
        (folder / writer.OUTPUT_NAME).write_text(f"## Resumen ejecutivo\n\nThe data of the meeting [{frame}].\n",
                                                 encoding="utf-8")
        Image.new("RGB", (64, 36), (20, 90, 200)).save(folder / frame)
        (folder / library.REPORT_NAME).write_bytes(b"PK\x03\x04 a report")
        (folder / library.RUN_NAME).write_text(json.dumps({
            "format": "summary", "cost_usd": 0.1234, "max_cost_usd": 1.0, "seconds": 321.0,
            "stages": [jobs.Stage(name).as_dict() | {"state": state, "seconds": 3.0}
                       for name, state in (("frames", "done"), ("reading", "done"), ("summary", "done"),
                                           ("report", "done"))]}), encoding="utf-8")
        self.processed = store.add_meeting(self.data, self.project, PROCESSED, "2026-09-25", "requirements",
                                           summary="Omega", key_points=["Omega"],
                                           meeting_folder=f"{library.RESULTS_DIR}/{folder.name}")
        self.terminal = store.add_meeting(self.data, self.project, TERMINAL, "2026-09-10", "presale",
                                          summary="Omega", key_points=["Omega"])
        loose = self.data / LOOSE
        loose.mkdir()
        (loose / writer.OUTPUT_NAME).write_text(f"## Summary\n\nOmega [{frame}].\n", encoding="utf-8")
        Image.new("RGB", (64, 36), (10, 10, 10)).save(loose / frame)
        document.set_template(test_report.owner_shaped(self.tmp / TEMPLATE), self.data, name=TEMPLATE)
        company.set_company_name(self.data, COMPANY)
        logo = self.tmp / "logo.png"
        Image.new("RGB", (40, 20), (200, 10, 10)).save(logo)
        company.set_logo(self.data, logo.read_bytes(), "logo.png")
        job = jobs.Job({"project": self.project, "title": PROCESSED, "max_cost": 1.0, "format": "summary"})
        job.state, job.failed_stage = "failed", "reading"
        job.stages[0].state, job.stages[1].state = "done", "failed"
        job.error = gemini.ReadingError("gemini.refused", status=400, reason=texts.External("fake error 400")).message
        self.app.runner.jobs[job.id] = job
        self.job = job.id

    def screens(self):
        """{what: (status, page)} of every screen, and of the answers the page's
        script reads."""
        pid, processed, terminal = self.project, self.processed["id"], self.terminal["id"]
        said = {}
        for path in ("/", f"/p/{pid}", f"/p/{pid}/new", f"/p/{pid}/m/{processed}", f"/p/{pid}/m/{terminal}",
                     f"/r/{LOOSE}", "/settings", f"/job/{self.job}", "/no-such-page"):
            status, _, body = self.request("GET", path)
            said[path] = (status, body.decode("utf-8"))
        return said

    def answers(self):
        """What the page's script shows, from the server's answers: a job that
        failed, and requests refused."""
        said = []
        job = json.loads(self.request("GET", f"/api/jobs/{self.job}")[2])
        said += [job["error"], job["failed_stage"]] + [stage["label"] for stage in job["stages"]]
        for path, data in (("/api/process", {"project": self.project, "title": " "}),
                           ("/api/projects", {"name": PROJECT, "client": ""}),
                           ("/api/company", {"name": "x" * 200}),
                           ("/api/language", {"language": "9"})):
            status, _, body = self.request("POST", path, data, {"Content-Type": "application/json",
                                                                "X-MeetingTool": "1"})
            self.assertEqual(status, 400, body)
            said.append(json.loads(body)["error"])
        status, _, body = self.request("PUT", "/api/logo?name=logo.svg", b"<svg/>",
                                       {"Content-Type": "application/octet-stream", "X-MeetingTool": "1"})
        said.append(json.loads(body)["error"])
        return [text for text in said if text]

    def set_language(self, language):
        self.assertEqual(self.request("POST", "/api/language", {"language": language},
                                      {"Content-Type": "application/json", "X-MeetingTool": "1"})[0], 200)

    def test_the_made_up_language_leaves_no_word_outside_the_list(self):
        """A text written in a page instead of the list stays a word here."""
        self.set_language(PSEUDO)
        paths = (str(self.data.resolve()), str(self.data))
        for path, (status, page) in self.screens().items():
            text, script = visible(page)
            self.assertEqual(leftover_words(text), [], path)
            self.assertEqual(leftover_words(" ".join(script.values())), [], path)
            self.assertIn(f'lang="{PSEUDO}"', page, path)
        for answer in self.answers():
            self.assertEqual(leftover_words(answer, paths), [], answer)

    def test_each_screen_speaks_only_its_language(self):
        for language in LANGUAGES:
            self.set_language(language)
            paths = (str(self.data.resolve()), str(self.data))
            for path, (status, page) in self.screens().items():
                text, script = visible(page)
                self.assertEqual(OTHER_WORDS[language].findall(without_data(text)), [], (language, path))
                self.assertEqual(OTHER_WORDS[language].findall(without_data(" ".join(script.values()))), [],
                                 (language, path))
                self.assertIn(f'lang="{language}"', page)
            for answer in self.answers():
                self.assertEqual(OTHER_WORDS[language].findall(without_data(answer, paths)), [], (language, answer))

    def test_the_language_changes_the_screens_and_is_kept(self):
        self.set_language("en")
        page = self.page("/settings")
        self.assertIn("<h1>Settings</h1>", page)
        self.assertIn('<option value="en" selected>English</option>', page)
        self.assertEqual(company.language(self.data), "en")
        self.set_language("es")
        self.assertIn("<h1>Ajustes</h1>", self.page("/settings"))
        (self.data / company.SETTINGS_NAME).write_text('{"language": "fr"}', encoding="utf-8")
        self.assertIn("<h1>Ajustes</h1>", self.page("/settings"))  # a record edited by hand: the default

    def test_the_summary_keeps_its_own_language(self):
        """The application's language is not the summary's: a meeting can still
        be asked in English with the application in Spanish, and the other way."""
        self.set_language("es")
        page = self.page(f"/p/{self.project}/new")
        self.assertIn('<option value="en">Inglés</option>', page)
        self.set_language("en")
        page = self.page(f"/p/{self.project}/new")
        self.assertIn('<option value="es">Spanish</option>', page)
        self.assertIn("Language of the result", page)


# ── WI17-AC05 and AC07: each stage fails in the application's language ────────

class StageLanguageTest(Processing):
    """Each stage made to fail through the application, with Gemini faked, in
    each language: the stage's name and its error are in that language, and
    what came from outside is a detail."""

    def set_language(self, language):
        company.set_language(self.data, language)

    def process(self, with_recording=True, expect=200, **fields):
        # A title that is no word of either language: the error names the run's folder, which carries it.
        return super().process(with_recording, expect, **dict({"title": "Kappa 3"}, **fields))

    def check(self, job, stage, said):
        """`said`: {language: words of the error}."""
        self.assertEqual(job["state"], "failed")
        self.assertEqual(job["failed_stage_name"], stage)
        language = company.language(self.data)
        self.assertEqual(job["failed_stage"], texts.Message(jobs.STAGE_KEYS[stage]).text(language))
        self.assertIn(said[language], job["error"])
        self.assertEqual(OTHER_WORDS[language].findall(job["error"]), [], job["error"])
        for stage_said in job["stages"]:
            self.assertEqual(stage_said["label"], texts.Message(jobs.STAGE_KEYS[stage_said["name"]]).text(language))
        return job

    def each_language(self, run, stage, said):
        jobs_said = {}
        for language in LANGUAGES:
            with self.subTest(language=language):
                self.set_language(language)
                self.fake.requests.clear()
                jobs_said[language] = self.check(run(), stage, said)
        return jobs_said

    def test_the_frames(self):
        self.video.write_bytes(b"this is not a video")
        found = self.each_language(self.process, "frames", {"es": "no se puede abrir la grabación",
                                                            "en": "cannot open recording"})
        for job in found.values():
            self.assertEqual(len(job["detail"]), 1)  # what the video library said

    def test_the_reading(self):
        def run():
            self.fake.script[:] = [400]
            return self.process()
        found = self.each_language(run, "reading", {"es": "Gemini rechazó el pedido (HTTP 400)",
                                                    "en": "Gemini refused the request (HTTP 400)"})
        for job in found.values():
            self.assertEqual(job["detail"], ["fake error 400"])
            self.assertNotIn("fake error", job["error"])

    def test_the_summary(self):
        broken = test_summary.returning(test_summary.summary_text("es", drop="Decisiones"))

        def run():
            self.fake.script[:] = [lambda first, count: answer_for(first, count), broken, broken]
            return self.process(meeting_type="", language="es")
        self.each_language(run, "summary", {"es": "el resumen tiene la sección «Decisiones» 0 veces, no una",
                                            "en": "the summary has the section 'Decisiones' 0 times, not once"})

    def test_the_questions_and_answers(self):
        self.transcript_blocks = test_qa.SPANISH
        from tests.test_frames import write_teams_docx
        write_teams_docx(self.transcript, test_qa.SPANISH)
        broken = test_qa.json_answer({"questions": "none"})

        def run():
            self.fake.script[:] = [broken, broken]
            return self.process(with_recording=False, format="qa", meeting_type="", language="es")
        found = self.each_language(run, "qa", {"es": "[se frenó en registro 1/1", "en": "[stopped at register 1/1"})
        self.assertTrue(found["es"]["error"].startswith("el registro no trae la lista de preguntas"))
        self.assertTrue(found["en"]["error"].startswith("the register has no list of questions"))

    def test_the_report(self):
        broken = self.tmp / "broken.docx"
        broken.write_bytes(b"not a word file")

        def run():
            self.fake.script[:] = [lambda first, count: answer_for(first, count),
                                   test_summary.returning(test_summary.summary_text("es"))]
            # A template that could no longer be used when the report is built.
            (self.data / document.TEMPLATE_NAME).write_bytes(broken.read_bytes())
            return self.process(meeting_type="")
        found = self.each_language(run, "report", {"es": "no se puede abrir: fijate que sea un archivo de Word",
                                                   "en": "cannot be opened"})
        for job in found.values():
            self.assertEqual(len(job["detail"]), 1)

    def test_the_saving(self):
        def run():
            self.fake.script[:] = [lambda first, count: answer_for(first, count),
                                   test_summary.returning(test_summary.summary_text("es"))]
            with mock.patch.object(store, "add_meeting",
                                   side_effect=store.ProjectError("projects.missing", project=self.project,
                                                                  folder=str(self.data))):
                return self.process(meeting_type="")
        self.each_language(run, "saving", {"es": f"el proyecto {self.project} no existe en",
                                           "en": f"project {self.project} does not exist in"})


class OutsideTest(Processing):
    """WI17-AC07: what comes from outside the program is shown apart."""

    def test_an_unexpected_failure_is_said_with_its_text_as_a_detail(self):
        for language, said in (("es", "falló algo inesperado"), ("en", "something unexpected failed")):
            company.set_language(self.data, language)
            with mock.patch("meetingtool.frames.extract.extract_frames",
                            side_effect=RuntimeError("the disk exploded")):
                job = self.process()
            self.assertEqual(job["error"], said)
            self.assertEqual(job["detail"], ["the disk exploded"])

    def test_google_s_reason_is_a_detail_in_the_application_and_inline_in_the_terminal(self):
        error = gemini.ReadingError("gemini.refused", status=403, reason=texts.External("API key not valid."))
        self.assertEqual(str(error), "Gemini refused the request (HTTP 403): API key not valid.")
        self.assertEqual(error.text("en"), "Gemini refused the request (HTTP 403)")
        self.assertEqual(error.details("en"), ["API key not valid."])
        self.assertTrue(error.text("es").startswith("Gemini rechazó el pedido (HTTP 403)"))
        self.assertEqual(error.details("es"), ["API key not valid."])

    def test_a_detail_inside_a_message_inside_another_comes_up(self):
        inner = document.ReportError("report.cannot_open", name="t.docx", detail=texts.External("Bad zip"))
        outer = store.ProjectError("summary.not_added", output="o", project="p", error=inner.message)
        self.assertEqual(outer.details("es"), ["Bad zip"])
        self.assertNotIn("Bad zip", outer.text("es"))
        self.assertIn("Bad zip", str(outer))

    def test_a_server_failure_is_said_with_its_text_as_a_detail(self):
        company.set_language(self.data, "en")
        with mock.patch.object(library, "projects", side_effect=RuntimeError("index broken")):
            status, _, body = self.request("GET", "/")
        self.assertEqual(status, 500)
        page = body.decode("utf-8")
        self.assertIn("something unexpected failed", page)
        self.assertIn("Detail: index broken", page)
        with mock.patch.object(store, "create_project", side_effect=OSError("the disk is full")):
            status, _, body = self.request("POST", "/api/projects", {"name": "x", "client": ""},
                                           {"Content-Type": "application/json", "X-MeetingTool": "1"})
        self.assertEqual((status, json.loads(body)), (500, {"error": "something unexpected failed",
                                                            "detail": ["the disk is full"]}))


# ── WI17-AC09: the terminal keeps its English ─────────────────────────────────

class TerminalTest(unittest.TestCase):
    def test_a_message_is_its_english_text(self):
        message = texts.Message("gemini.over_budget", what=texts.Message("summary.what"), worst=0.26, spent=0.1,
                                budget=0.5, refused="")
        self.assertEqual(message, "stopped before sending the summary: that request could cost up to US$0.26, and "
                                  "with about US$0.10 already spent it could go over the budget of US$0.50; nothing "
                                  "was written")
        self.assertEqual(message.text("es"), "se frenó antes de mandar el resumen: ese pedido podía costar hasta "
                                             "US$0,26, y con unos US$0,10 ya gastados podía pasar el techo de "
                                             "US$0,50; no se escribió nada")

    def test_the_prompts_to_gemini_do_not_change(self):
        # A retired type's description goes into the request, in English.
        self.assertEqual(str(writer.RETIRED_TYPES["discovery"][0]), "both presales and requirements gathering")

    def test_text_that_is_not_an_entry_is_kept_as_it_is(self):
        error = document.ReportError("the report could not be opened again")
        self.assertEqual((str(error), error.text("es"), error.details("es")),
                         ("the report could not be opened again", "the report could not be opened again", []))


if __name__ == "__main__":
    unittest.main()
