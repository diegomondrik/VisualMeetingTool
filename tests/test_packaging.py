"""Tests for the installer's recipe (packaging/, WI18): what the installer
writes is what the window reads, its languages are the application's, and the
build refuses tools that are not the pinned ones. They read the recipes; the
build itself is run by packaging/build.py and its output is evidence."""

import contextlib
import importlib.util
import io
import re
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from meetingtool import texts
from meetingtool.app import window

ROOT = Path(__file__).resolve().parent.parent
PACKAGING = ROOT / "packaging"
ISS = (PACKAGING / "installer.iss").read_text(encoding="utf-8")


def load_build():
    spec = importlib.util.spec_from_file_location("packaging_build", PACKAGING / "build.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def section(name):
    match = re.search(rf"^\[{name}\]\n(.*?)(?=^\[|\Z)", ISS, re.MULTILINE | re.DOTALL)
    return [line for line in match.group(1).splitlines() if line.strip() and not line.startswith(";")]


def setting(name):
    match = re.search(rf"^{name}=(.*)$", ISS, re.MULTILINE)
    return match.group(1).strip() if match else None


class InstallerTest(unittest.TestCase):
    def test_its_languages_are_the_application_s_and_it_asks_for_one_every_time(self):
        names = [re.match(r'Name: "([^"]+)"', line).group(1) for line in section("Languages")]
        self.assertEqual(sorted(names), sorted(texts.LANGUAGES))
        self.assertEqual(setting("ShowLanguageDialog"), "yes")
        self.assertEqual(setting("UsePreviousLanguage"), "no")  # a reinstall asks again

    def test_it_writes_the_chosen_language_where_the_window_reads_it(self):
        [line] = section("INI")
        self.assertIn(f'Filename: "{{app}}\\{window.INSTALLATION_FILE}"', line)
        self.assertIn('Section: "installation"', line)
        self.assertIn('Key: "language"', line)
        self.assertIn('String: "{language}"', line)

    def test_it_installs_for_the_user_without_administrator_rights(self):
        self.assertEqual(setting("PrivilegesRequired"), "lowest")
        self.assertIsNone(setting("PrivilegesRequiredOverridesAllowed"))
        self.assertTrue(setting("DefaultDirName").startswith("{autopf}"))  # the user's own programs folder

    def test_every_version_installs_over_the_last_and_never_touches_the_data(self):
        self.assertRegex(setting("AppId"), r"^\{\{[0-9A-F-]{36}\}$")
        self.assertNotIn("VisualMeetingTool-data", ISS)
        self.assertNotIn("{userdocs}", ISS)
        self.assertNotIn("{%USERPROFILE}", ISS)

    def test_the_shortcuts_open_the_window_program_and_the_user_manual(self):
        # WI33: besides the program's own entries there is one for the manual in each list, and nothing else.
        manual = 'Filename: "{app}\\manual\\user-manual.html"'
        for lines in (section("Icons"), section("Run")):
            others = [line for line in lines if manual not in line]
            self.assertTrue(others)
            for line in others:
                self.assertIn('Filename: "{app}\\MeetingTool.exe"', line)
            self.assertEqual(len(lines) - len(others), 1, "the manual has one entry here")

    def test_the_user_manual_is_installed_next_to_the_program_and_offered_unticked(self):
        [manual] = [line for line in section("Files") if "user-manual.html" in line]
        self.assertIn('Source: "{#SourcePath}\\..\\docs\\manual\\user-manual.html"', manual)
        self.assertIn('DestDir: "{app}\\manual"', manual)
        [offer] = [line for line in section("Run") if "user-manual.html" in line]
        self.assertIn("postinstall", offer)
        self.assertIn("skipifsilent", offer)
        self.assertIn("unchecked", offer)  # the program's launch stays the one ticked
        self.assertIn("shellexec", offer)  # a .html is opened by the user's browser, not run
        names = [re.match(r"(\w+)\.(\w+)=", line) for line in section("CustomMessages")]
        for language in texts.LANGUAGES:
            for key in ("UserManual", "OpenManual"):
                self.assertIn((language, key), [match.groups() for match in names if match])

    def test_the_program_starts_the_window(self):
        launcher = (PACKAGING / "launcher.py").read_text(encoding="utf-8")
        self.assertIn("from meetingtool.app.window import main", launcher)
        spec = (PACKAGING / "meetingtool.spec").read_text(encoding="utf-8")
        self.assertIn('name="MeetingTool"', spec)
        self.assertIn("console=False", spec)
        self.assertIn('f"meetingtool.texts.{language}" for language in texts.LANGUAGES', spec)


class BuildTest(unittest.TestCase):
    def setUp(self):
        self.build = load_build()
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_pins_are_exact(self):
        good = self.tmp / "good.txt"
        good.write_text("# tools\nPyInstaller==6.0.0\npywebview==5.0  # the window\n\n", encoding="utf-8")
        self.assertEqual(self.build.pins(good), {"pyinstaller": "6.0.0", "pywebview": "5.0"})
        for line in ("pyinstaller>=6", "pyinstaller", "==6.0"):
            bad = self.tmp / "bad.txt"
            bad.write_text(line + "\n", encoding="utf-8")
            with self.assertRaises(ValueError, msg=line):
                self.build.pins(bad)

    def test_a_tool_that_is_not_the_pinned_one_is_named(self):
        pinned = {"pyinstaller": "6.0.0", "pywebview": "5.0"}
        self.assertEqual(self.build.tool_problems(pinned, {"pyinstaller": "6.0.0", "pywebview": "5.0"}), [])
        self.assertEqual(self.build.tool_problems(pinned, {"pyinstaller": "6.1.0"}),
                         ["pyinstaller: pinned 6.0.0, installed 6.1.0", "pywebview: pinned 5.0, installed nothing"])

    def test_the_pinned_file_pins_the_tools_and_the_program_s_libraries(self):
        frozen = PACKAGING / "requirements-build.txt"
        if not frozen.exists():
            self.skipTest("requirements-build.txt is frozen once the build environment is installed")
        pinned = self.build.pins(frozen)
        for name in ("pyinstaller", "pywebview", "av", "numpy", "pillow", "python-docx"):
            self.assertIn(name, pinned)

    def test_files_git_ignores_inside_what_is_packed_are_named(self):
        """Review P2-2: client data that .gitignore hides would be packed all the same."""
        status = ("!! meetingtool/__pycache__/\n!! meetingtool/app/__pycache__/server.cpython-312.pyc\n"
                  "!! meetingtool/app/static/frame_001.jpg\n!! \"packaging/reunión cliente.mp4\"\n"
                  " M meetingtool/app/window.py\n")
        self.assertEqual(self.build.stray_files(status),
                         ["meetingtool/app/static/frame_001.jpg", "packaging/reunión cliente.mp4"])

    def run_main(self, tools=(), changes="", ignored="", args=()):
        """build.main with the machine replaced; it must stop before building anything."""
        def git(*command):
            return ignored if "--ignored" in command else changes

        def never(*a, **k):
            raise AssertionError("it built")

        with mock.patch.object(self.build, "tool_problems", lambda pinned: list(tools)), \
                mock.patch.object(self.build, "git", git), \
                mock.patch.object(self.build, "find_iscc", lambda: None), \
                mock.patch.object(self.build.subprocess, "run", never), \
                contextlib.redirect_stderr(io.StringIO()) as said:
            return self.build.main(list(args)), said.getvalue()

    def test_the_build_refuses_tools_that_are_not_the_pinned_ones(self):
        code, said = self.run_main(tools=["pyinstaller: pinned 6.0.0, installed 6.1.0"])
        self.assertEqual(code, 2)
        self.assertIn("pinned 6.0.0, installed 6.1.0", said)

    def test_the_build_refuses_changes_not_committed(self):
        code, said = self.run_main(changes=" M meetingtool/app/window.py")
        self.assertEqual(code, 2)
        self.assertIn("not committed", said)

    def test_the_build_refuses_ignored_files_even_when_allowed_to_be_dirty(self):
        code, said = self.run_main(ignored="!! meetingtool/app/static/frame_001.jpg", args=["--allow-dirty"])
        self.assertEqual(code, 2)
        self.assertIn("frame_001.jpg", said)

    def test_with_everything_in_order_it_goes_on_to_look_for_inno_setup(self):
        code, said = self.run_main(ignored="!! meetingtool/__pycache__/")
        self.assertEqual(code, 2)
        self.assertIn("ISCC.exe", said)

    def test_inno_setup_is_found_where_its_installer_puts_it(self):
        place = self.tmp / "Programs" / "Inno Setup 6"
        place.mkdir(parents=True)
        (place / "ISCC.exe").write_bytes(b"")
        self.assertEqual(self.build.find_iscc({"LOCALAPPDATA": str(self.tmp), "PATH": ""}), place / "ISCC.exe")
        self.assertIsNone(self.build.find_iscc({"ISCC": str(self.tmp / "missing.exe")}))
