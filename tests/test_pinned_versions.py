"""The suite runs on the exact versions the program ships with (WI31, R10).

pyproject.toml declares minimums; constraints.txt pins, exactly, each library
and what it brings, at the versions the Windows installer packs; the CI
installs with `-c constraints.txt`. These tests fail when a library of
pyproject.toml has no pin, when a pin is not exact (`==`) or is below the
minimum, and when the workflow stops installing with the constraints.

Versions are compared without any third-party package: a version is read as
the tuple of its leading whole numbers ("12.3.0" -> (12, 3, 0)), which is
enough for the versions of these libraries (no pre-release or epoch is used
in a pin or a minimum). Nothing here looks at what is installed on the
machine: it reads files only.
"""

import re
import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYPROJECT = ROOT / "pyproject.toml"
CONSTRAINTS = ROOT / "constraints.txt"
WORKFLOW = ROOT / ".github" / "workflows" / "tests.yml"

# Brought by the libraries of pyproject.toml; pinned too, because the
# installer packs them (python-docx needs both).
BROUGHT = ("lxml", "typing_extensions")

REQUIREMENT = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)\s*(===|==|>=|<=|~=|!=|>|<)?\s*([^\s;#]*)")


def normal(name):
    return re.sub(r"[-_.]+", "-", name).lower()


def version_tuple(text):
    """"12.3.0" -> (12, 3, 0). Stops at the first part that is not a whole number."""
    parts = []
    for piece in text.split("."):
        found = re.match(r"\d+", piece)
        if not found:
            break
        parts.append(int(found.group(0)))
        if found.group(0) != piece:
            break
    return tuple(parts)


def at_least(version, minimum):
    size = max(len(version), len(minimum))
    return version + (0,) * (size - len(version)) >= minimum + (0,) * (size - len(minimum))


def requirements(lines):
    """[(name, operator, version)] of the requirement lines; comments and blank lines are skipped."""
    found = []
    for line in lines:
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        match = REQUIREMENT.match(line)
        found.append((normal(match.group(1)), match.group(2) or "", match.group(3)) if match else (line, "", ""))
    return found


def problems(dependencies, constraints_text):
    """What is wrong with the pins, as sentences; empty when they are right."""
    pins = {}
    said = []
    for name, operator, version in requirements(constraints_text.splitlines()):
        if name in pins:
            said.append(f"{name} is pinned more than once")
        pins[name] = (operator, version)
    for name, (operator, version) in pins.items():
        if operator != "==" or not version_tuple(version) or "*" in version:
            said.append(f"{name} is not pinned exactly with ==: {operator}{version}")
    for name in BROUGHT:
        if normal(name) not in pins:
            said.append(f"{name} (brought by the libraries) has no pin")
    for dependency in dependencies:
        name, operator, minimum = requirements([dependency])[0]
        if name not in pins:
            said.append(f"{name} (pyproject.toml: {dependency}) has no pin")
            continue
        operator_pinned, pinned = pins[name]
        if operator_pinned != "==" or not version_tuple(pinned):
            continue  # already said
        if operator == ">=" and not at_least(version_tuple(pinned), version_tuple(minimum)):
            said.append(f"{name} is pinned at {pinned}, below the minimum {minimum} of pyproject.toml")
    return said


def declared():
    return tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))["project"]["dependencies"]


def constraints():
    return CONSTRAINTS.read_text(encoding="utf-8")


class PinnedVersionsTest(unittest.TestCase):
    def test_every_library_of_pyproject_has_an_exact_pin_at_or_above_its_minimum(self):
        self.assertEqual(problems(declared(), constraints()), [])

    def test_pyproject_declares_the_libraries_with_a_minimum(self):
        for dependency in declared():
            name, operator, minimum = requirements([dependency])[0]
            self.assertEqual(operator, ">=", dependency)
            self.assertTrue(version_tuple(minimum), dependency)

    def test_a_library_missing_from_the_constraints_is_found(self):
        text = constraints().replace("numpy==2.5.3\n", "")
        said = problems(declared(), text)
        self.assertEqual(len(said), 1, said)
        self.assertIn("numpy", said[0])

    def test_a_library_brought_by_the_others_missing_from_the_constraints_is_found(self):
        text = constraints().replace("lxml==6.1.3\n", "")
        said = problems(declared(), text)
        self.assertEqual(len(said), 1, said)
        self.assertIn("lxml", said[0])

    def test_a_range_is_not_a_pin(self):
        text = constraints().replace("numpy==2.5.3", "numpy>=2.5.3")
        said = problems(declared(), text)
        self.assertEqual(len(said), 1, said)
        self.assertIn("numpy is not pinned exactly", said[0])

    def test_a_library_with_no_version_or_a_wildcard_is_not_a_pin(self):
        for line in ("numpy", "numpy==", "numpy==2.*"):
            text = constraints().replace("numpy==2.5.3", line)
            self.assertTrue(problems(declared(), text), line)

    def test_a_pin_below_the_minimum_of_pyproject_is_found(self):
        text = constraints().replace("numpy==2.5.3", "numpy==1.20.0")
        said = problems(declared(), text)
        self.assertEqual(len(said), 1, said)
        self.assertIn("numpy is pinned at 1.20.0, below the minimum 1.26", said[0])

    def test_versions_are_compared_as_numbers_not_as_text(self):
        # 9 is below 14 as a number, though "9" > "14" as text; 1.100 is above 1.26
        self.assertFalse(at_least(version_tuple("9.0.0"), version_tuple("14")))
        self.assertTrue(at_least(version_tuple("19.0.0"), version_tuple("14")))
        self.assertTrue(at_least(version_tuple("1.100"), version_tuple("1.26")))
        self.assertTrue(at_least(version_tuple("14"), version_tuple("14.0.0")))
        self.assertFalse(at_least(version_tuple("1.25.9"), version_tuple("1.26")))

    def test_a_name_is_the_same_whatever_its_case_or_separator(self):
        text = constraints().replace("python-docx", "Python_Docx")
        self.assertEqual(problems(declared(), text), [])

    def test_the_pins_are_the_ones_of_the_installer(self):
        # The versions the installer's requirements-build.txt freezes (WI18); change both together.
        pins = {name: version for name, _, version in requirements(constraints().splitlines())}
        self.assertEqual(pins, {"av": "19.0.0", "lxml": "6.1.3", "numpy": "2.5.3", "pillow": "12.3.0",
                                "python-docx": "1.2.0", "typing-extensions": "4.16.0"})


class WorkflowInstallsWithTheConstraintsTest(unittest.TestCase):
    def install_lines(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        return [line.strip() for line in text.splitlines()
                if "pip install" in line and not line.strip().startswith("#")]

    def test_the_install_step_uses_the_constraints_file(self):
        lines = self.install_lines()
        self.assertEqual(len(lines), 1, lines)
        self.assertRegex(lines[0], r"pip install\s+(-c|--constraint)[ =]constraints\.txt\b")

    def test_the_install_step_installs_every_library_of_pyproject(self):
        line = self.install_lines()[0]
        for dependency in declared():
            self.assertIn(f'"{dependency}"', line)

    def test_the_log_shows_the_versions_installed(self):
        self.assertRegex(WORKFLOW.read_text(encoding="utf-8"), r"(?m)^\s+run: python -m pip (list|freeze)\s*$")

    def test_the_workflow_runs_on_windows_with_python_3_12(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("runs-on: windows-latest", text)
        self.assertIn('python-version: "3.12"', text)


if __name__ == "__main__":
    unittest.main()
