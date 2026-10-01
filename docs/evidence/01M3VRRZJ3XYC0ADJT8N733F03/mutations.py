"""WI18: each control the independent review found missing (and the ones it
found working) is shown able to fail. Every mutation breaks the code in one
place, in a fresh clone of HEAD under the temporary folder, and the tests named
must then fail; the clone is restored between mutations and removed at the end.

    python docs/evidence/01M3VRRZJ3XYC0ADJT8N733F03/mutations.py

It prints one line per mutation and exits 1 if any was not caught.
"""

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]

WINDOW = "meetingtool/app/window.py"
JOBS = "meetingtool/app/jobs.py"
BUILD = "packaging/build.py"

MUTATIONS = [
    ("the run does not take the saving lock (review P2-3)", JOBS,
     "            self.saving.acquire()\n            saving = True\n", "            saving = False\n",
     ["tests.test_window.ClosingTest"]),
    ("close() does not wait for a saving", JOBS,
     "        with self.saving:\n            self.closed = True\n", "        self.closed = True\n",
     ["tests.test_window.ClosingTest", "tests.test_window.CloseWhileSavingTest"]),
    ("a run saves its meeting after close()", JOBS,
     "            if self.closed:\n                raise JobError(\"app.run.closed\")\n", "",
     ["tests.test_window.ClosingTest"]),
    ("the window does not close the runner when pywebview returns (review P3-4)", WINDOW,
     "            if self.app is not None:\n                self.app.runner.close()\n                self.app.stop()\n",
     "            if self.app is not None:\n                self.app.stop()\n",
     ["tests.test_window.LogTest"]),
    ("a % in installation.ini is read as a reference (review P2-1)", WINDOW,
     "configparser.ConfigParser(interpolation=None)", "configparser.ConfigParser()",
     ["tests.test_window.LanguageTest"]),
    ("the trace of an exception keeps the token (review P3-2)", WINDOW,
     "            record.exc_info, record.exc_text = None, None\n", "",
     ["tests.test_window.LogTest"]),
    ("Internet Explorer's component goes unsaid (review P3-1)", WINDOW,
     "        if renderer != \"edgechromium\":", "        if False:",
     ["tests.test_window.LogTest"]),
    ("WebView2 failing to start goes unsaid", WINDOW,
     "        if self.SIGN in record.getMessage():", "        if False:",
     ["tests.test_window.LogTest"]),
    ("the installer's language is not the default", WINDOW,
     "        self.default_language = installed_language(folder) or texts.DEFAULT_LANGUAGE",
     "        self.default_language = texts.DEFAULT_LANGUAGE",
     ["tests.test_window.LanguageTest"]),
    ("the build ignores tools that are not the pinned ones (review P3-5)", BUILD,
     "    problems = tool_problems(pins())\n", "    problems = []\n",
     ["tests.test_packaging.BuildTest"]),
    ("the build ignores changes not committed (review P3-5)", BUILD,
     "    if changes and not args.allow_dirty:", "    if False:",
     ["tests.test_packaging.BuildTest"]),
    ("the build packs files git ignores (review P2-2)", BUILD,
     "    if stray:  # even with --allow-dirty", "    if False:  # even with --allow-dirty",
     ["tests.test_packaging.BuildTest"]),
]


def main():
    clone = Path(tempfile.mkdtemp(prefix="wi18-mutations-"))
    subprocess.run(["git", "clone", "-q", "--no-hardlinks", str(ROOT), str(clone)], check=True)
    head = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=clone, capture_output=True, text=True,
                          check=True).stdout.strip()
    print(f"clone of {head} in {clone}")
    missed = 0
    try:
        for name, relative, old, new, tests in MUTATIONS:
            path = clone / relative
            source = path.read_bytes().decode("utf-8")
            if source.count(old) != 1:
                print(f"NOT APPLIED  {name}: the text to change is not there once")
                missed += 1
                continue
            path.write_bytes(source.replace(old, new).encode("utf-8"))
            result = subprocess.run([sys.executable, "-m", "unittest", *tests], cwd=clone, capture_output=True,
                                    text=True)
            subprocess.run(["git", "checkout", "-q", "--", relative], cwd=clone, check=True)
            caught = result.returncode != 0
            missed += not caught
            last = (result.stderr.strip().splitlines() or [""])[-1]
            print(f"{'caught' if caught else 'MISSED':11}  {name}  [{' '.join(tests)}: {last}]")
    finally:
        shutil.rmtree(clone, ignore_errors=True)
    print(f"{len(MUTATIONS) - missed} of {len(MUTATIONS)} caught")
    return 1 if missed else 0


if __name__ == "__main__":
    sys.exit(main())
