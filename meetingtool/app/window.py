"""The installed application in a window of its own (INGOL D-187, WI18).

The installer starts this, not the browser: the same server as `meetingtool
app` (meetingtool.app.server), on this machine only and with its session
token, shown inside a Windows window through WebView2, the web component that
Windows 11 already has. Only that window is given the token, and no other
page shares the window. `python -m meetingtool app` keeps opening the browser.

- The language the installer was read in, which the installer writes next to
  the program (installation.ini), is the application's default: a language
  chosen in Settings wins over it.
- One application per data folder: a second start says so and stops.
- Closed with the X while a meeting is being processed, the window asks
  first; confirmed, the meeting is dropped (meetingtool.app.jobs.Runner.close)
  and what it left is cleared at the next start.
- What happened at the last start is written to a log (LOG_NAME, in the
  user's local application data, outside the data folder; the session token
  never in it). WebView2 can fail to start and leave the window blank, saying
  it only to pywebview's log (it did in Windows Sandbox, whose WebView2 is
  registered but cannot start): that failure is said at once in a box, how to
  repair it and the log's place; a page that has not loaded after LOAD_WAIT
  seconds for any other reason is said too.

Everything that touches the machine (pywebview, the message boxes, the
registry) can be replaced, so the tests need none of them.
"""

import configparser
import logging
import os
import platform
import sys
import threading
from pathlib import Path

from meetingtool import __version__, texts
from meetingtool.app import company, jobs, server
from meetingtool.projects import store

TITLE = "MeetingTool"
INSTALLATION_FILE = "installation.ini"
SIZE, MIN_SIZE = (1200, 860), (820, 600)
LOAD_WAIT = 30
LOG_NAME = "window.log"
# The WebView2 runtime's client in EdgeUpdate: machine-wide (64- and 32-bit views) or for this user.
WEBVIEW2_CLIENT = "Microsoft\\EdgeUpdate\\Clients\\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"
WEBVIEW2_KEYS = (("HKEY_LOCAL_MACHINE", "SOFTWARE\\WOW6432Node\\" + WEBVIEW2_CLIENT),
                 ("HKEY_LOCAL_MACHINE", "SOFTWARE\\" + WEBVIEW2_CLIENT),
                 ("HKEY_CURRENT_USER", "Software\\" + WEBVIEW2_CLIENT))

# MessageBoxW
MB_OK, MB_YESNO, IDYES = 0x0, 0x4, 6
MB_ICONERROR, MB_ICONWARNING, MB_DEFBUTTON2 = 0x10, 0x30, 0x100
MB_SETFOREGROUND, MB_TOPMOST = 0x10000, 0x40000

log = logging.getLogger("meetingtool.window")


def program_dir():
    """The installed program's folder; None when run from the code."""
    return Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else None


def log_dir():
    return Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "VisualMeetingTool"


def installed_language(folder):
    """The language the installer was read in, or None (no installer, or a
    file that does not name one of the application's languages)."""
    if folder is None:
        return None
    parser = configparser.ConfigParser()
    try:
        parser.read(Path(folder) / INSTALLATION_FILE, encoding="utf-8")
    except (OSError, configparser.Error, UnicodeDecodeError):
        return None
    value = parser.get("installation", "language", fallback="").strip().lower()
    return value if value in texts.LANGUAGES else None


def webview2_version():
    """The WebView2 runtime's version on this machine, as Microsoft says to
    find it (a version other than 0.0.0.0 under any of its keys), or None."""
    try:
        import winreg
    except ImportError:
        return None
    for root, path in WEBVIEW2_KEYS:
        try:
            with winreg.OpenKey(getattr(winreg, root), path) as key:
                version, _ = winreg.QueryValueEx(key, "pv")
        except OSError:
            continue
        if version and version != "0.0.0.0":
            return version
    return None


def _message_box(text, title, flags):
    import ctypes

    return ctypes.windll.user32.MessageBoxW(None, text, title, flags | MB_SETFOREGROUND | MB_TOPMOST)


def ask(title, text):
    """Yes or no, No by default."""
    return _message_box(text, title, MB_YESNO | MB_ICONWARNING | MB_DEFBUTTON2) == IDYES


def tell(title, text):
    _message_box(text, title, MB_OK | MB_ICONERROR)


class Hidden(logging.Filter):
    """Keeps the session token out of the log: pywebview writes the addresses it loads."""

    def __init__(self):
        super().__init__()
        self.secrets = []

    def filter(self, record):
        message = record.getMessage()
        hidden = message
        for secret in self.secrets:
            hidden = hidden.replace(secret, "<hidden>")
        if hidden != message:
            record.msg, record.args = hidden, ()
        return True


class WebView2Failed(logging.Handler):
    """Hears pywebview say that WebView2 could not start."""

    SIGN = "WebView2 initialization failed"

    def __init__(self, failed, settled):
        super().__init__(logging.ERROR)
        self.failed, self.settled = failed, settled

    def emit(self, record):
        if self.SIGN in record.getMessage():
            self.failed.set()
            self.settled.set()


class Window:
    def __init__(self, data_dir=None, *, folder=None, webview=None, ask=ask, tell=tell,
                 has_webview2=webview2_version, make_app=server.App, log_folder=None, load_wait=LOAD_WAIT):
        self.data_dir = Path(data_dir or store.default_data_dir())
        self.default_language = installed_language(folder) or texts.DEFAULT_LANGUAGE
        self.folder = folder
        self.webview = webview
        self.ask, self.tell = ask, tell
        self.has_webview2 = has_webview2
        self.make_app = make_app
        self.log_path = Path(log_folder or log_dir()) / LOG_NAME
        self.load_wait = load_wait
        self.loaded, self.webview2_failed = threading.Event(), threading.Event()
        self.settled = threading.Event()  # loaded, or WebView2 failed
        self.hidden = Hidden()
        self.app = None

    @property
    def language(self):
        try:
            return company.language(self.data_dir, self.default_language)
        except OSError:
            return self.default_language

    def say(self, message):
        text, details = texts.said(message, self.language)
        return "\n\n".join([text, *details])

    def fail(self, error):
        log.error("failed: %s", error, exc_info=error)
        message = error.message if isinstance(error, texts.Failure) else texts.Message(
            "app.window.failed", error=texts.outside(error))
        self.tell(TITLE, self.say(message))
        return 1

    def closing(self, *args):
        """pywebview asks before the window closes: False keeps it open."""
        if self.app is None or self.app.runner.running() is None:
            log.info("closed")
            return True
        if not self.ask(self.say(texts.Message("app.window.closing_title")),
                        self.say(texts.Message("app.window.closing_running"))):
            log.info("close refused while a meeting is processed")
            return False
        self.app.runner.close()
        log.info("closed while a meeting was processed: dropped")
        return True

    def on_loaded(self, *args):
        log.info("page loaded")
        self.loaded.set()
        self.settled.set()

    def on_shown(self, *args):
        log.info("window shown, renderer %s", getattr(self.webview, "renderer", None))
        threading.Thread(target=self.watch_the_load, daemon=True).start()

    def watch_the_load(self):
        self.settled.wait(self.load_wait)
        if self.webview2_failed.is_set():
            self.tell(TITLE, self.say(texts.Message("app.window.webview2_failed", log=str(self.log_path))))
        elif not self.loaded.is_set():
            log.error("the page did not load in %s seconds", self.load_wait)
            self.tell(TITLE, self.say(texts.Message("app.window.not_shown", log=str(self.log_path))))

    def start_log(self):
        """The log of this start, replacing the last one's."""
        root = logging.getLogger()
        try:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            handler = logging.FileHandler(self.log_path, mode="w", encoding="utf-8")
        except OSError:
            return None
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
        handler.addFilter(self.hidden)
        root.addHandler(handler)
        root.setLevel(logging.INFO)
        log.info("VisualMeetingTool %s, Python %s, Windows %s, program %s", __version__,
                 platform.python_version(), platform.version(), self.folder)
        return handler

    def run(self):
        handler = self.start_log()
        hearing = WebView2Failed(self.webview2_failed, self.settled)
        logging.getLogger("pywebview").addHandler(hearing)
        try:
            return self._run()
        finally:
            logging.getLogger("pywebview").removeHandler(hearing)
            if handler is not None:
                logging.getLogger().removeHandler(handler)
                handler.close()

    def _run(self):
        version = self.has_webview2()
        log.info("WebView2 runtime %s; language %s (installer's: %s)", version, self.language,
                 installed_language(self.folder))
        if not version:
            self.tell(TITLE, self.say(texts.Message("app.window.no_webview2")))
            return 1
        try:
            store.check_data_dir(self.data_dir)
            lock = server.DataFolderLock(self.data_dir).acquire()
        except Exception as error:  # said in a box: there is no console
            return self.fail(error)
        try:
            jobs.clear_leftovers(self.data_dir)
            self.app = self.make_app(self.data_dir, default_language=self.default_language).start()
            self.hidden.secrets.append(self.app.token)
            log.info("server at %s", self.app.url)
            webview = self.webview = self.webview or _pywebview()
            webview.settings["ALLOW_DOWNLOADS"] = True  # the Word report and the example template
            window = webview.create_window(TITLE, self.app.launch_url, width=SIZE[0], height=SIZE[1],
                                           min_size=MIN_SIZE)
            window.events.closing += self.closing
            window.events.shown += self.on_shown
            window.events.loaded += self.on_loaded
            # Edge's WebView2 only: never the old Internet Explorer component.
            webview.start(gui="edgechromium", private_mode=True)
            log.info("window gone")
            return 0
        except Exception as error:
            return self.fail(error)
        finally:
            if self.app is not None:
                self.app.runner.close()
                self.app.stop()
            lock.release()


def _pywebview():
    import webview

    return webview


def main(argv=None):
    # A program without a console has no streams: what would be printed is dropped.
    for name in ("stdout", "stderr"):
        if getattr(sys, name) is None:
            setattr(sys, name, open(os.devnull, "w", encoding="utf-8"))
    return Window(folder=program_dir()).run()


if __name__ == "__main__":
    sys.exit(main())
