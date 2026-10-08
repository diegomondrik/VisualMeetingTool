"""Mutation run for 01M4CM3YV7RF9ET37K61XBYVRY (WI29, WI29-AC03): each mutation undoes or bends one part of how a Word
package is read and bounded, in a copy of the working tree, and runs the tests that guard it. Every mutation must make
them fail. None needs INGOL's kits: the tests are the ones the CI runs.

    python docs/evidence/01M4CM3YV7RF9ET37K61XBYVRY/mutations.py <repository> <a folder outside it, which must not exist yet> [label part]

With a label part, only the mutations whose label holds it are run. The
repository must be a clean checkout: the script prints its commit, and the
output of the recorded run is mutations.txt next to this file. Modelled on
docs/evidence/01M4CB9FV6XGEYENDJYAEQZWQX/mutations.py (WI27).
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

READER = "meetingtool/word_package.py"
TRANSCRIPT = "meetingtool/frames/transcript.py"
DOCUMENT = "meetingtool/report/document.py"
TESTS = ["tests.test_word_package_limits"]

PART_CHECK = "                    if size > MAX_PART_BYTES:\n"
TOTAL_CHECK = "                    if total > MAX_PACKAGE_BYTES:\n"
OFF = "                    if False:\n"
OPEN_PART = "            with archive.open(name) as part:"
FROM_DIRECTORY = (
    "            if archive.getinfo(name).file_size > MAX_PART_BYTES:\n"
    "                raise PackageError(\"package.part_too_big\", part=name, limit=MAX_PART_BYTES // MEGABYTE)\n"
    + OPEN_PART)
TRANSCRIPT_VIA_READER = (
    '        root = ElementTree.fromstring(word_package.read_parts(path, ["word/document.xml"])["word/document.xml"])\n')
TRANSCRIPT_DIRECT = (
    '        with zipfile.ZipFile(path) as archive:\n'
    '            root = ElementTree.fromstring(archive.read("word/document.xml"))\n')
TEMPLATE_VIA_READER = (
    '        parts = word_package.read_parts(path)\n'
    '        names = list(parts)\n'
    '        types = parts["[Content_Types].xml"]\n')
TEMPLATE_DIRECT = (
    '        with zipfile.ZipFile(path) as archive:\n'
    '            names = archive.namelist()\n'
    '            types = archive.read("[Content_Types].xml")\n'
    '            parts = {name: archive.read(name) for name in names}\n')
CHECK_VIA_READER = (
    '    try:\n'
    '        parts = word_package.read_parts(path)\n'
    '    except word_package.PackageError as error:\n'
    '        raise ReportError("report.too_big"')
CHECK_DIRECT = (
    '    try:\n'
    '        with zipfile.ZipFile(path) as archive:\n'
    '            parts = {name: archive.read(name) for name in archive.namelist()}\n'
    '    except word_package.PackageError as error:\n'
    '        raise ReportError("report.too_big"')

# (label, [(file, old, new)]); each `old` has to be found exactly once.
MUTATIONS = [
    ("the limit per part removed: a part of any size is read",
     [(READER, PART_CHECK, OFF)]),
    ("the total not counted: parts each within the limit are read however many they are",
     [(READER, TOTAL_CHECK, OFF)]),
    ("the size taken from the directory (ZipInfo.file_size) instead of counted",
     [(READER, PART_CHECK, OFF), (READER, OPEN_PART, FROM_DIRECTORY)]),
    ("the entries not counted: a package of any number of parts is read",
     [(READER, "        if len(present) > MAX_ENTRIES:\n", "        if False:\n")]),
    ("the transcript's reader left on zipfile directly",
     [(TRANSCRIPT, TRANSCRIPT_VIA_READER, TRANSCRIPT_DIRECT)]),
    ("the template's reader left on zipfile directly",
     [(DOCUMENT, TEMPLATE_VIA_READER, TEMPLATE_DIRECT)]),
    ("the report check's reader left on zipfile directly",
     [(DOCUMENT, CHECK_VIA_READER, CHECK_DIRECT)]),
]


def summary_line(stderr):
    lines = [line for line in stderr.strip().splitlines() if line.startswith(("Ran ", "OK", "FAILED"))]
    return " ".join(lines[-2:]) if lines else "(no result line)"


def run_tests(work):
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONDONTWRITEBYTECODE": "1"}
    env.pop("PYTHONPATH", None)  # no kits: what the CI runs
    try:
        return subprocess.run([sys.executable, "-m", "unittest", *TESTS], cwd=work, capture_output=True, text=True,
                              encoding="utf-8", errors="replace", env=env, timeout=3600)
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess([], 124, "", "FAILED (timeout)")


def main(argv):
    source, work = Path(argv[0]), Path(argv[1])
    only = argv[2] if len(argv) > 2 else ""
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=source, capture_output=True, text=True).stdout.strip()
    dirty = subprocess.run(["git", "status", "--porcelain"], cwd=source, capture_output=True, text=True).stdout.strip()
    shutil.copytree(source, work, ignore=shutil.ignore_patterns(".git", "__pycache__"))
    names = sorted({name for _, edits in MUTATIONS for name, _, _ in edits})
    originals = {name: (work / name).read_text(encoding="utf-8") for name in names}
    print("mutation run for 01M4CM3YV7RF9ET37K61XBYVRY: each mutation is applied alone to a copy of the working tree;")
    print(f"`python -m unittest {' '.join(TESTS)}` (no kits, what the CI runs) must fail")
    print(f"commit: {head}" + (" (the working tree has uncommitted changes)" if dirty else " (clean working tree)"))
    detected_all = True
    try:
        for label, edits in MUTATIONS:
            if only not in label:
                continue
            changed = dict(originals)
            for name, old, new in edits:
                if changed[name].count(old) != 1:
                    raise SystemExit(f"mutation {label!r} does not apply exactly once in {name}")
                changed[name] = changed[name].replace(old, new)
            for name in names:
                (work / name).write_text(changed[name], encoding="utf-8", newline="\n")
            result = run_tests(work)
            detected = result.returncode != 0
            detected_all &= detected
            print(f"- {label}: exit {result.returncode}, {summary_line(result.stderr)} -> "
                  f"{'DETECTED' if detected else 'NOT DETECTED'}", flush=True)
            for name in names:
                (work / name).write_text(originals[name], encoding="utf-8", newline="\n")
        result = run_tests(work)
        print(f"- unmutated: exit {result.returncode}, {summary_line(result.stderr)}")
        unmutated_ok = result.returncode == 0
    finally:
        shutil.rmtree(work, ignore_errors=True)
    ok = detected_all and unmutated_ok
    print("all mutations detected" if ok else "A MUTATION WAS NOT DETECTED, OR THE UNMUTATED RUN FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
