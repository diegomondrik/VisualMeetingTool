"""Mutation run for 01M3JS6BH8TTPN0C76NFB7E6N6 (WI12): each mutation removes
one check or one piece of the request from meetingtool/summary/writer.py in a
copy of the working tree, runs `python -m unittest tests.test_summary`, and
must make it fail.

    python docs/evidence/01M3JS6BH8TTPN0C76NFB7E6N6/mutations.py <repository> <empty folder outside it>

The output of the recorded run is mutations.txt next to this file.
"""

import shutil
import subprocess
import sys
from pathlib import Path

MUTATIONS = [
    ("a type's own sections left out (AC01)",
     "    return standard[:kind.after] + list(zip(kind.headings[language], kind.guides)) + standard[kind.after:]\n",
     "    return standard\n"),
    ("the unchanged types moved after the participants (AC01)",
     "    after: int = len(GUIDE)\n", "    after: int = 2\n"),
    ("stance removed (AC02)",
     "    if meeting_type and MEETING_TYPES[meeting_type].stance:\n", "    if False:\n"),
    ("section overrides removed (AC02)",
     "kind.overrides.get(index, guide)", "guide"),
    ("retired type accepted as unknown (AC03)",
     "    if meeting_type in RETIRED_TYPES:\n", "    if False:\n"),
    ("note on the retired type removed (AC03)",
     "        for name in retired:\n", "        for name in []:\n"),
    ("language check removed (AC04)",
     "    check_language(text, headings, language)\n", ""),
    ("whole-summary language check removed (AC04)",
     "    if other >= wanted:\n", "    if False:\n"),
    ("section language check removed (AC04)",
     "        if other >= FOREIGN_SECTION_WORDS and other > 2 * wanted:\n", "        if False:\n"),
    ("section language check judges a few words (AC04)",
     "FOREIGN_SECTION_WORDS = 8\n", "FOREIGN_SECTION_WORDS = 1\n"),
    ("quotes counted as text (AC04)",
     '    text = _QUOTED.sub(" ", text)\n', ""),
    ("language rule left out of the request (AC04)",
     "              LANGUAGE_RULE.format(name=LANGUAGE_NAMES[language]),\n", ""),
    ("review F1: fenced code counted as text (AC04)",
     '    text = _FENCED.sub(" ", text)\n', ""),
    ("review F1: tables counted in a section (AC04)",
     "language, tables=False)", "language)"),
    ("missing-frame check removed (AC08)",
     "    if missing:\n", "    if False:\n"),
    ("other-mention check removed (AC08)",
     '        if FRAME_LIKE.search(FRAME_REF.sub("", line)):\n', "        if False:\n"),
    ("frames not checked when writing (AC08)",
     "check_summary(answer, headings, language, frame_names)", "check_summary(answer, headings, language)"),
]


def summary_line(stderr):
    return [line for line in stderr.splitlines() if line.startswith(("FAILED", "OK"))][-1]


def main(source, work):
    source, work = Path(source), Path(work)
    shutil.copytree(source, work, ignore=shutil.ignore_patterns(".git", "__pycache__"))
    target = work / "meetingtool/summary/writer.py"
    original = target.read_text(encoding="utf-8")
    print("mutation run for 01M3JS6BH8TTPN0C76NFB7E6N6: each mutation is applied alone to a copy of the")
    print("working tree, `python -m unittest tests.test_summary` is run, and the mutation must make it fail")
    detected_all = True
    try:
        for label, old, new in MUTATIONS:
            if original.count(old) != 1:
                raise SystemExit(f"mutation {label!r} does not apply exactly once")
            target.write_text(original.replace(old, new), encoding="utf-8")
            run = subprocess.run([sys.executable, "-m", "unittest", "tests.test_summary"], cwd=work,
                                 capture_output=True, text=True)
            detected = run.returncode != 0
            detected_all &= detected
            print(f"- {label}: exit {run.returncode}, {summary_line(run.stderr)} -> "
                  f"{'DETECTED' if detected else 'NOT DETECTED'}")
        target.write_text(original, encoding="utf-8")
        run = subprocess.run([sys.executable, "-m", "unittest", "tests.test_summary"], cwd=work,
                             capture_output=True, text=True)
        print(f"- unmutated: exit {run.returncode}, {summary_line(run.stderr)}")
    finally:
        shutil.rmtree(work)
    print("all mutations detected" if detected_all and run.returncode == 0 else "A MUTATION WAS NOT DETECTED")
    return 0 if detected_all and run.returncode == 0 else 1


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:3]))
