"""Tests for the installer's recipe (packaging/, WI18): what the installer
writes is what the window reads, its languages are the application's, and the
build refuses tools that are not the pinned ones. They read the recipes; the
build itself is run by packaging/build.py and its output is evidence."""

import importlib.util
import re
import tempfile
import unittest
from pathlib import Path

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

    def test_the_shortcuts_open_the_window_program(self):
        for line in section("Icons") + section("Run"):
            self.assertIn('Filename: "{app}\\MeetingTool.exe"', line)

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

    def test_inno_setup_is_found_where_its_installer_puts_it(self):
        place = self.tmp / "Programs" / "Inno Setup 6"
        place.mkdir(parents=True)
        (place / "ISCC.exe").write_bytes(b"")
        self.assertEqual(self.build.find_iscc({"LOCALAPPDATA": str(self.tmp), "PATH": ""}), place / "ISCC.exe")
        self.assertIsNone(self.build.find_iscc({"ISCC": str(self.tmp / "missing.exe")}))
