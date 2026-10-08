"""Tests for the installed application's window (meetingtool.app.window, WI18).

pywebview, the message boxes and the registry are replaced: a fake webview
records what the window asked of it and, while "shown", reaches the server the
way the window would. No test opens a real window, needs a key or reaches the
network."""

import http.client
import logging
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

from meetingtool import texts
from meetingtool.app import company, jobs, library, server, window
from meetingtool.projects import store
from tests import test_summary
from tests.test_app import Keys, Processing
from tests.test_reading import KEY, answer_for


class Event:
    """pywebview's event: handlers added with +=; set() runs them, and a
    handler answering False keeps the window open."""

    def __init__(self):
        self.handlers = []

    def __add__(self, handler):  # as pywebview's: `+=` goes through __add__
        self.handlers.append(handler)
        return self

    def set(self):
        return all(handler() is not False for handler in self.handlers)


class FakeWindow:
    def __init__(self, title, url, options):
        self.title, self.url, self.options = title, url, options
        self.events = type("Events", (), {})()
        self.events.closing, self.events.shown, self.events.loaded = Event(), Event(), Event()


class FakeWebview:
    """`while_shown(webview)` runs inside start(), as the user would while the
    window is open."""

    renderer = "edgechromium"

    def __init__(self, while_shown=None, fail=None, loads=True):
        self.settings = {"ALLOW_DOWNLOADS": False}
        self.windows, self.started = [], None
        self.while_shown, self.fail, self.loads = while_shown, fail, loads

    def create_window(self, title, url, **options):
        self.windows.append(FakeWindow(title, url, options))
        return self.windows[-1]

    def start(self, **options):
        self.started = options
        if self.fail:
            raise self.fail
        self.windows[0].events.shown.set()
        if self.loads:
            self.windows[0].events.loaded.set()
        if self.while_shown:
            self.while_shown(self)


class Boxes:
    def __init__(self, answer=False):
        self.asked, self.told, self.answer = [], [], answer

    def ask(self, title, text):
        self.asked.append((title, text))
        return self.answer

    def tell(self, title, text):
        self.told.append((title, text))


def fetch(url, cookie=None):
    """(status, headers, body) of a GET to the server, as the window sends it."""
    address = url.split("://", 1)[1]
    host, _, rest = address.partition("/")
    name, port = host.split(":")
    connection = http.client.HTTPConnection(name, int(port), timeout=30)
    connection.request("GET", "/" + rest, headers={"Cookie": cookie} if cookie else {})
    response = connection.getresponse()
    body = response.read()
    connection.close()
    return response.status, {k.lower(): v for k, v in response.getheaders()}, body


def session_of(launch_url):
    status, headers, _ = fetch(launch_url)
    assert status == 303, status
    return headers["set-cookie"].split(";")[0]


class Folders(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.data = self.tmp / "data"
        self.data.mkdir()
        self.program = self.tmp / "program"
        self.program.mkdir()
        self.boxes = Boxes()
        self.keys = Keys(KEY)

    def tearDown(self):
        self._tmp.cleanup()

    def installed_in(self, language):
        (self.program / window.INSTALLATION_FILE).write_text(f"[installation]\nlanguage={language}\n",
                                                             encoding="utf-8")

    def make_app(self, data_dir, **options):
        return server.App(data_dir, read_key=self.keys.read, save_key=self.keys.save, delete_key=self.keys.delete,
                          **options)

    def window(self, webview, has_webview2=lambda: True):
        return window.Window(self.data, folder=self.program, webview=webview, ask=self.boxes.ask,
                             tell=self.boxes.tell, has_webview2=has_webview2, make_app=self.make_app,
                             log_folder=self.tmp / "log", load_wait=self.load_wait or window.LOAD_WAIT)

    load_wait = None  # the window's own


# ── WI18-AC01 and AC04: the window shows the application's own server ─────────

class OpenTest(Folders):
    def test_the_window_shows_the_session_address_of_its_own_server_through_webview2(self):
        seen = {}

        def while_shown(webview):
            shown = webview.windows[0]
            seen["url"] = shown.url
            cookie = session_of(shown.url)
            seen["page"] = fetch(shown.url.split("/open")[0] + "/", cookie)
            seen["static"] = fetch(shown.url.split("/open")[0] + "/static/app.js", cookie)[0]

        webview = FakeWebview(while_shown)
        app_window = self.window(webview)
        self.assertEqual(app_window.run(), 0)
        self.assertTrue(seen["url"].startswith(f"http://{server.HOST}:"), seen["url"])
        self.assertIn("/open?token=", seen["url"])
        self.assertEqual(seen["page"][0], 200)
        self.assertIn(b"MeetingTool", seen["page"][2])
        self.assertEqual(seen["static"], 200)
        # Edge's component only, nothing kept between starts, and downloads let through.
        self.assertEqual(webview.started, {"gui": "edgechromium", "private_mode": True})
        self.assertTrue(webview.settings["ALLOW_DOWNLOADS"])
        self.assertEqual(webview.windows[0].title, window.TITLE)
        self.assertEqual(webview.windows[0].options["min_size"], window.MIN_SIZE)
        self.assertEqual(self.boxes.told, [])

    def test_closed_the_window_the_server_stops_and_the_data_folder_is_free(self):
        address = {}
        webview = FakeWebview(lambda w: address.update(url=w.windows[0].url))
        self.assertEqual(self.window(webview).run(), 0)
        with self.assertRaises(OSError):
            fetch(address["url"])
        server.DataFolderLock(self.data).acquire().release()

    def test_a_request_without_the_session_is_refused_while_the_window_holds_it(self):
        """WI18-AC04: the window gets the token; a page of another site or
        another program on this machine, without it, gets nothing."""
        seen = {}

        def while_shown(webview):
            base = webview.windows[0].url.split("/open")[0]
            seen["bare"] = fetch(base + "/")[0]
            seen["forged"] = fetch(base + "/", f"{server.COOKIE}=not-the-token")[0]
            seen["stale"] = fetch(base + "/open?token=not-the-token")[0]
            seen["running"] = fetch(base + "/api/running")[0]

        self.window(FakeWebview(while_shown)).run()
        self.assertEqual(seen, {"bare": 403, "forged": 403, "stale": 403, "running": 403})

    def test_without_webview2_it_says_what_is_missing_and_opens_nothing(self):
        webview = FakeWebview()
        self.assertEqual(self.window(webview, has_webview2=lambda: False).run(), 1)
        self.assertEqual(webview.windows, [])
        self.assertIsNone(webview.started)
        self.assertEqual(len(self.boxes.told), 1)
        self.assertIn("WebView2", self.boxes.told[0][1])
        self.assertIn("Falta el componente", self.boxes.told[0][1])
        self.assertFalse((self.data / server.DataFolderLock.NAME).exists())

    def test_a_failure_to_show_the_window_is_said_in_a_box_and_frees_the_folder(self):
        webview = FakeWebview(fail=RuntimeError("WebView2 could not start: 0x80070005"))
        self.assertEqual(self.window(webview).run(), 1)
        title, text = self.boxes.told[0]
        self.assertEqual(title, window.TITLE)
        self.assertIn("MeetingTool no pudo abrirse", text)
        self.assertIn("0x80070005", text)  # the outside text, as a detail
        server.DataFolderLock(self.data).acquire().release()

    def test_the_leftovers_of_a_run_cut_short_are_cleared_at_start(self):
        project = store.create_project(self.data, "Cermaq", "Cermaq")["id"]
        leftover = self.data / project / library.PROCESSING_DIR / "2026-09-25-cut-abc123"
        leftover.mkdir(parents=True)
        (leftover / "frame_001.jpg").write_bytes(b"x")
        self.window(FakeWebview()).run()
        self.assertFalse(leftover.exists())

    def test_without_a_console_what_would_be_printed_is_dropped(self):
        with mock.patch.object(sys, "stdout", None), mock.patch.object(sys, "stderr", None), \
                mock.patch.object(window.Window, "run", lambda self: (print("dropped"), 0)[1]):
            self.assertEqual(window.main(), 0)
            for stream in (sys.stdout, sys.stderr):
                self.assertIsNotNone(stream)
                stream.close()


class LogTest(Folders):
    """WebView2 can fail to start and leave the window blank, saying it only to
    pywebview's log (the first clean-machine run of WI18 met a blank window)."""

    load_wait = 0.3

    def test_the_log_says_what_the_start_found_and_never_the_session_token(self):
        seen = {}

        def while_shown(webview):
            seen["token"] = webview.windows[0].url.split("token=")[1]
            # pywebview writes the addresses it loads, its errors too.
            logging.getLogger("pywebview").error("navigation to %s failed", webview.windows[0].url)

        self.installed_in("en")
        self.window(FakeWebview(while_shown), has_webview2=lambda: "141.0.3537.71").run()
        written = (self.tmp / "log" / window.LOG_NAME).read_text(encoding="utf-8")
        for fact in ("VisualMeetingTool", "WebView2 runtime 141.0.3537.71", "language en (installer's: en)",
                     "server at http://127.0.0.1:", "window shown, renderer edgechromium", "page loaded",
                     "navigation to http://127.0.0.1:", "window gone"):
            self.assertIn(fact, written)
        self.assertNotIn(seen["token"], written)
        self.assertIn("token=<hidden>", written)

    def test_each_start_replaces_the_last_log(self):
        self.window(FakeWebview(), has_webview2=lambda: None).run()
        self.window(FakeWebview()).run()
        written = (self.tmp / "log" / window.LOG_NAME).read_text(encoding="utf-8")
        self.assertEqual(written.count("VisualMeetingTool 0"), 1)
        self.assertNotIn("WebView2 runtime None", written)

    def test_a_page_that_does_not_load_is_said_in_a_box_with_the_log_s_place(self):
        self.window(FakeWebview(lambda webview: time.sleep(1.5), loads=False)).run()
        self.assertEqual(len(self.boxes.told), 1)
        title, text = self.boxes.told[0]
        self.assertIn("no pudo mostrar sus pantallas", text)
        self.assertIn(str(self.tmp / "log" / window.LOG_NAME), text)
        self.assertIn("the page did not load", (self.tmp / "log" / window.LOG_NAME).read_text(encoding="utf-8"))

    def test_webview2_failing_to_start_is_said_at_once_with_how_to_repair_it(self):
        """As in Windows Sandbox: WebView2 registered, but it cannot start."""
        def while_shown(webview):
            logging.getLogger("pywebview").error(
                "WebView2 initialization failed with exception: Couldn't find a compatible Webview2 Runtime "
                "installation to host WebViews.")
            time.sleep(1.0)

        started = time.monotonic()
        self.load_wait = 20
        self.window(FakeWebview(while_shown, loads=False)).run()
        self.assertLess(time.monotonic() - started, 10)
        self.assertEqual(len(self.boxes.told), 1)
        text = self.boxes.told[0][1]
        self.assertIn("no pudo arrancar", text)
        self.assertIn("Microsoft Edge WebView2 Runtime", text)
        self.assertIn(str(self.tmp / "log" / window.LOG_NAME), text)
        self.assertIn("Couldn't find a compatible", (self.tmp / "log" / window.LOG_NAME).read_text(encoding="utf-8"))

    def test_the_token_is_hidden_in_a_trace_too(self):
        """Review P3-2: the filter hid the message but not the trace of an exception."""
        def while_shown(webview):
            url = webview.windows[0].url
            try:
                raise RuntimeError(f"could not load {url}")
            except RuntimeError:
                logging.getLogger("pywebview").exception("navigation failed")

        token = {}
        app_window = self.window(FakeWebview(while_shown))
        original = app_window.make_app

        def make_app(*args, **kwargs):
            app = original(*args, **kwargs)
            token["value"] = app.token
            return app

        app_window.make_app = make_app
        app_window.run()
        written = (self.tmp / "log" / window.LOG_NAME).read_text(encoding="utf-8")
        self.assertIn("RuntimeError: could not load http://127.0.0.1:", written)
        self.assertNotIn(token["value"], written)

    def test_internet_explorer_s_component_instead_of_webview2_is_said(self):
        """Review P3-1: pywebview falls back to it when its own check fails."""
        webview = FakeWebview(lambda w: time.sleep(1.0), loads=True)
        webview.renderer = "mshtml"
        self.load_wait = 20
        started = time.monotonic()
        self.window(webview).run()
        self.assertLess(time.monotonic() - started, 10)
        self.assertEqual(len(self.boxes.told), 1)
        self.assertIn("no pudo arrancar", self.boxes.told[0][1])

    def test_closed_however_it_closes_no_meeting_is_saved_after(self):
        """The window closes the runner once pywebview returns, even when its
        closing handler never ran (review P3-4)."""
        made = []
        app_window = self.window(FakeWebview())
        original = app_window.make_app
        app_window.make_app = lambda *a, **k: made.append(original(*a, **k)) or made[-1]
        app_window.run()
        self.assertTrue(made[0].runner.closed)

    def test_a_page_that_loads_says_nothing(self):
        self.window(FakeWebview(lambda webview: time.sleep(1.0))).run()
        self.assertEqual(self.boxes.told, [])


# ── WI18-AC03: one application per data folder ─────────────────────────────────

class SecondStartTest(Folders):
    def test_a_second_start_on_the_same_data_folder_says_so_and_starts_nothing(self):
        second = {}

        def while_shown(webview):
            other_boxes, made = Boxes(), []
            other = window.Window(self.data, folder=self.program, webview=FakeWebview(), ask=other_boxes.ask,
                                  tell=other_boxes.tell, has_webview2=lambda: True, log_folder=self.tmp / "log2",
                                  make_app=lambda *a, **k: made.append(a))
            second.update(code=other.run(), told=other_boxes.told, made=made)

        self.installed_in("en")
        self.assertEqual(self.window(FakeWebview(while_shown)).run(), 0)
        self.assertEqual(second["code"], 1)
        self.assertEqual(second["made"], [])
        self.assertEqual(len(second["told"]), 1)
        self.assertIn("MeetingTool is already open on", second["told"][0][1])
        self.assertIn(str(self.data), second["told"][0][1])


# ── WI18-AC06: the installer's language is the application's default ─────────

class LanguageTest(Folders):
    def language_of_the_window(self):
        seen = {}

        def while_shown(webview):
            url = webview.windows[0].url
            seen["page"] = fetch(url.split("/open")[0] + "/", session_of(url))[2].decode("utf-8")

        self.window(FakeWebview(while_shown)).run()
        return seen["page"]

    def test_the_installer_s_language_is_read_from_next_to_the_program(self):
        self.assertIsNone(window.installed_language(None))
        self.assertIsNone(window.installed_language(self.program))  # no file: run from the code
        for written, read in (("en", "en"), ("es", "es"), (" EN ", "en"), ("fr", None), ("", None)):
            self.installed_in(written)
            self.assertEqual(window.installed_language(self.program), read, written)
        (self.program / window.INSTALLATION_FILE).write_bytes(b"\xff\xfe not an ini")
        self.assertIsNone(window.installed_language(self.program))
        # A % is text, not a reference to another value (review P2-1): the window opens all the same.
        for written in ("en%", "%(x)s", "%"):
            self.installed_in(written)
            self.assertIsNone(window.installed_language(self.program), written)
        self.installed_in("en%")
        self.assertEqual(self.window(FakeWebview()).run(), 0)

    def test_installed_in_english_the_application_starts_in_english(self):
        self.installed_in("en")
        page = self.language_of_the_window()
        self.assertIn('<html lang="en">', page)

    def test_installed_in_spanish_the_application_starts_in_spanish(self):
        self.installed_in("es")
        self.assertIn('<html lang="es">', self.language_of_the_window())

    def test_a_language_chosen_in_settings_wins_over_the_installer_s(self):
        company.set_language(self.data, "es")
        self.installed_in("en")
        self.assertIn('<html lang="es">', self.language_of_the_window())
        company.set_language(self.data, "en")
        self.installed_in("es")
        self.assertIn('<html lang="en">', self.language_of_the_window())

    def test_the_installer_s_language_is_a_default_and_is_not_written(self):
        self.installed_in("en")
        self.language_of_the_window()
        self.assertFalse((self.data / company.SETTINGS_NAME).exists())

    def test_the_boxes_speak_the_installer_s_language_too(self):
        self.installed_in("en")
        self.window(FakeWebview(), has_webview2=lambda: False).run()
        self.assertIn("is missing", self.boxes.told[0][1])

    def test_without_an_installer_the_window_speaks_the_default_language(self):
        self.assertIn(f'<html lang="{texts.DEFAULT_LANGUAGE}">', self.language_of_the_window())


# ── WI18-AC02: closing with the X while a meeting is processed ────────────────

class ClosingTest(Processing):
    """A run held inside its reading, as a real one waits for Gemini, while the
    window is closed."""

    def setUp(self):
        self.reading, self.go_on = threading.Event(), threading.Event()
        super().setUp()
        self.boxes = Boxes()
        self.app_window = window.Window(self.data, ask=self.boxes.ask, tell=self.boxes.tell,
                                        log_folder=self.tmp / "log")
        self.app_window.app = self.app

    def tearDown(self):
        self.go_on.set()
        super().tearDown()

    def script(self):
        def held(first, count):
            self.reading.set()
            self.go_on.wait(60)
            return answer_for(first, count)

        return [held, test_summary.returning(test_summary.summary_text("es", "requirements"))]

    def start_a_run(self):
        data = {"project": self.project, "title": "Sesión de dudas", "date": "2026-09-25",
                "meeting_type": "requirements", "language": "", "format": "summary", "max_cost": 0.5,
                "transcript": self.upload("transcript", self.transcript),
                "recording": self.upload("recording", self.video)}
        job = self.api("/api/process", data)["job"]
        self.assertTrue(self.reading.wait(120), "the run did not reach its reading")
        return job

    def test_with_nothing_processed_it_closes_without_asking(self):
        self.assertTrue(self.app_window.closing())
        self.assertEqual(self.boxes.asked, [])
        self.assertFalse(self.app.runner.closed)

    def test_answered_no_the_window_stays_and_the_meeting_is_saved(self):
        job = self.start_a_run()
        self.boxes.answer = False
        self.assertFalse(self.app_window.closing())
        title, text = self.boxes.asked[0]
        self.assertEqual(title, "Cerrar MeetingTool")
        self.assertIn("Hay una reunión procesándose", text)
        self.go_on.set()
        done = self.wait(job)
        self.assertEqual(done["state"], "done", done["error"])
        self.assertEqual(len(store.list_meetings(self.data, self.project)), 1)

    def test_answered_yes_the_meeting_is_not_added_and_what_was_paid_stays_kept(self):
        job = self.start_a_run()
        self.boxes.answer = True
        self.assertTrue(self.app_window.closing())
        self.assertTrue(self.app.runner.closed)
        self.go_on.set()  # the reading's answer arrives after the window closed
        done = self.wait(job)
        self.assertEqual(done["error"], texts.Message("app.run.closed").text("es"))
        # WI20's rule for any failed run: no meeting, no result, and what was paid stays to be reused or discarded.
        self.assertNothingLeft(done, kept=True)
        self.assertIsNotNone(done["kept"])

    def test_the_question_is_in_the_application_s_language(self):
        company.set_language(self.data, "en")
        self.start_a_run()
        self.app_window.closing()
        self.assertEqual(self.boxes.asked[0][0], "Close MeetingTool")
        self.assertIn("A meeting is being processed", self.boxes.asked[0][1])

    def test_closed_while_the_run_saves_the_window_waits_and_the_meeting_is_saved_whole(self):
        """The run itself holds the saving (review P2-3): closed between moving
        the meeting into the project and recording it, the window waits."""
        saving, finish = threading.Event(), threading.Event()
        record = store.add_meeting

        def held(*args, **kwargs):
            saving.set()
            finish.wait(60)
            return record(*args, **kwargs)

        with mock.patch.object(store, "add_meeting", held):
            job = self.start_a_run()
            self.go_on.set()
            self.assertTrue(saving.wait(120), "the run did not reach its saving")
            self.boxes.answer = True
            closer = threading.Thread(target=self.app_window.closing)
            closer.start()
            time.sleep(0.5)
            self.assertTrue(closer.is_alive(), "the window did not wait for the saving")
            finish.set()
            closer.join(30)
            self.assertFalse(closer.is_alive())
            done = self.wait(job)
        self.assertEqual(done["state"], "done", done["error"])
        self.assertEqual(len(store.list_meetings(self.data, self.project)), 1)
        self.assertTrue(self.app.runner.closed)


class CloseWhileSavingTest(unittest.TestCase):
    def test_a_meeting_being_saved_is_saved_whole_before_the_window_closes(self):
        runner = jobs.Runner(tempfile.gettempdir(), lambda: KEY)
        runner.saving.acquire()  # a run in the middle of saving its meeting
        closer = threading.Thread(target=runner.close)
        closer.start()
        time.sleep(0.3)
        self.assertTrue(closer.is_alive(), "close() did not wait for the saving")
        self.assertFalse(runner.closed)
        runner.saving.release()
        closer.join(10)
        self.assertFalse(closer.is_alive())
        self.assertTrue(runner.closed)


if __name__ == "__main__":
    unittest.main()
