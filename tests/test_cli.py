import subprocess
import sys
import unittest
from pathlib import Path

import meetingtool

REPOSITORY = Path(__file__).resolve().parent.parent


class VersionTest(unittest.TestCase):
    """WI01-AC01."""

    def test_version_flag_prints_the_package_version(self):
        result = subprocess.run(
            [sys.executable, "-m", "meetingtool", "--version"],
            cwd=REPOSITORY,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), f"meetingtool {meetingtool.__version__}")

    def test_import_needs_only_the_standard_library(self):
        probe = (
            "import sys\n"
            "before = set(sys.modules)\n"
            "import meetingtool, meetingtool.__main__, meetingtool.repository_guard\n"
            "added = {m.split('.')[0] for m in set(sys.modules) - before}\n"
            "foreign = sorted(added - set(sys.stdlib_module_names) - {'meetingtool'})\n"
            "print(','.join(foreign))\n"
        )
        result = subprocess.run(
            [sys.executable, "-c", probe],
            cwd=REPOSITORY,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "", "modules outside the standard library were imported")


if __name__ == "__main__":
    unittest.main()
