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

Everything that touches the machine (pywebview, the message boxes, the
registry) can be replaced, so the tests need none of them.
"""

import configparser
import os
import sys
from pathlib import Path

from meetingtool import texts
from meetingtool.app import company, jobs, server
from meetingtool.projects import store

TITLE = "MeetingTool"
INSTALLATION_FILE = "installation.ini"
SIZE, MIN_SIZE = (1200, 860), (820, 600)
# The WebView2 runtime's client in EdgeUpdate: machine-wide (64- and 32-bit views) or for this user.
WEBVIEW2_CLIENT = "Microsoft\\EdgeUpdate\\Clients\\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"
WEBVIEW2_KEYS = (("HKEY_LOCAL_MACHINE", "SOFTWARE\\WOW6432Node\\" + WEBVIEW2_CLIENT),
                 ("HKEY_LOCAL_MACHINE", "SOFTWARE\\" + WEBVIEW2_CLIENT),
                 ("HKEY_CURRENT_USER", "Software\\" + WEBVIEW2_CLIENT))

# MessageBoxW
MB_OK, MB_YESNO, IDYES = 0x0, 0x4, 6
MB_ICONERROR, MB_ICONWARNING, MB_DEFBUTTON2 = 0x10, 0x30, 0x100
MB_SETFOREGROUND, MB_TOPMOST = 0x10000, 0x40000


def program_dir():
    """The installed program's folder; None when run from the code."""
    return Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else None


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


def webview2_installed():
    """Whether the WebView2 runtime is on this machine, as Microsoft says to
    find it: a version other than 0.0.0.0 under any of its keys."""
    try:
        import winreg
    except ImportError:
        return False
    for root, path in WEBVIEW2_KEYS:
        try:
            with winreg.OpenKey(getattr(winreg, root), path) as key:
                version, _ = winreg.QueryValueEx(key, "pv")
        except OSError:
            continue
        if version and version != "0.0.0.0":
            return True
    return False


def _message_box(text, title, flags):
    import ctypes

    return ctypes.windll.user32.MessageBoxW(None, text, title, flags | MB_SETFOREGROUND | MB_TOPMOST)


def ask(title, text):
    """Yes or no, No by default."""
    return _message_box(text, title, MB_YESNO | MB_ICONWARNING | MB_DEFBUTTON2) == IDYES


def tell(title, text):
    _message_box(text, title, MB_OK | MB_ICONERROR)


class Window:
    def __init__(self, data_dir=None, *, folder=None, webview=None, ask=ask, tell=tell,
                 has_webview2=webview2_installed, make_app=server.App):
        self.data_dir = Path(data_dir or store.default_data_dir())
        self.default_language = installed_language(folder) or texts.DEFAULT_LANGUAGE
        self.webview = webview
        self.ask, self.tell = ask, tell
        self.has_webview2 = has_webview2
        self.make_app = make_app
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
        message = error.message if isinstance(error, texts.Failure) else texts.Message(
            "app.window.failed", error=texts.outside(error))
        self.tell(TITLE, self.say(message))
        return 1

    def closing(self, *args):
        """pywebview asks before the window closes: False keeps it open."""
        if self.app is None or self.app.runner.running() is None:
            return True
        if not self.ask(self.say(texts.Message("app.window.closing_title")),
                        self.say(texts.Message("app.window.closing_running"))):
            return False
        self.app.runner.close()
        return True

    def run(self):
        if not self.has_webview2():
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
            webview = self.webview or _pywebview()
            webview.settings["ALLOW_DOWNLOADS"] = True  # the Word report and the example template
            window = webview.create_window(TITLE, self.app.launch_url, width=SIZE[0], height=SIZE[1],
                                           min_size=MIN_SIZE)
            window.events.closing += self.closing
            # Edge's WebView2 only: never the old Internet Explorer component.
            webview.start(gui="edgechromium", private_mode=True)
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
