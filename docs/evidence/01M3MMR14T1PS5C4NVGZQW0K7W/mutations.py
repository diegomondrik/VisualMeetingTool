"""Mutation run for 01M3MMR14T1PS5C4NVGZQW0K7W (WI13): each mutation removes
or bends one piece of the owner's frame rule (INGOL D-181) in
meetingtool/summary/writer.py or meetingtool/report/document.py, in a copy of
the working tree, runs `python -m unittest tests.test_summary tests.test_report`,
and must make it fail.

    python docs/evidence/01M3MMR14T1PS5C4NVGZQW0K7W/mutations.py <repository> <empty folder outside it>

The output of the recorded run is mutations.txt next to this file.
"""

import shutil
import subprocess
import sys
from pathlib import Path

WRITER = "meetingtool/summary/writer.py"
REPORT = "meetingtool/report/document.py"
MUTATIONS = [
    ("rule left out of the request (AC01)", WRITER,
     'LANGUAGE_RULE.format(name=LANGUAGE_NAMES[language]), "", FRAME_RULE, "",',
     "LANGUAGE_RULE.format(name=LANGUAGE_NAMES[language]),"),
    ("on-screen guide asks again for every relevant frame (AC01)", WRITER,
     '"Only the screens chosen by the rule for frames above, one frame for each distinct thing shown. For each: "',
     '"For each relevant frame: "'),
    ("rule loses the transitions and empty rows (AC01)", WRITER,
     "a transition between two views,\nrows or areas without data, ", ""),
    ("range check removed from the summary (AC02)", WRITER,
     "        found = FRAME_RANGE.search(line)\n", "        found = None\n"),
    ("range check removed from the report (AC02)", REPORT,
     "        found = writer.FRAME_RANGE.search(line)\n", "        found = None\n"),
    ("Spanish 'a' not read as a range (AC02)", WRITER,
     "(?:a|al|hasta|", "(?:al|hasta|"),
    ("a dash not read as a range (AC02)", WRITER,
     "(?:-|–|—|…|", "(?:–|—|…|"),
    ("'entre ... y' not read as a range (AC02)", WRITER,
     r"|\b(?:entre|between)\s+", r"|\b(?:zzentre|zzbetween)\s+"),
    ("two frames joined by 'y' read as a range (AC02)", WRITER,
     "(?:a|al|hasta|", "(?:y|and|a|al|hasta|"),
]
TESTS = ["tests.test_summary", "tests.test_report"]


def summary_line(stderr):
    return [line for line in stderr.splitlines() if line.startswith(("FAILED", "OK"))][-1]


def main(source, work):
    source, work = Path(source), Path(work)
    shutil.copytree(source, work, ignore=shutil.ignore_patterns(".git", "__pycache__"))
    originals = {name: (work / name).read_text(encoding="utf-8") for name in (WRITER, REPORT)}
    print("mutation run for 01M3MMR14T1PS5C4NVGZQW0K7W: each mutation is applied alone to a copy of the")
    print(f"working tree, `python -m unittest {' '.join(TESTS)}` is run, and the mutation must make it fail")
    detected_all = True
    try:
        for label, name, old, new in MUTATIONS:
            original = originals[name]
            if original.count(old) != 1:
                raise SystemExit(f"mutation {label!r} does not apply exactly once")
            (work / name).write_text(original.replace(old, new), encoding="utf-8")
            run = subprocess.run([sys.executable, "-m", "unittest", *TESTS], cwd=work, capture_output=True, text=True)
            (work / name).write_text(original, encoding="utf-8")
            detected = run.returncode != 0
            detected_all &= detected
            print(f"- {label}: exit {run.returncode}, {summary_line(run.stderr)} -> "
                  f"{'DETECTED' if detected else 'NOT DETECTED'}")
        run = subprocess.run([sys.executable, "-m", "unittest", *TESTS], cwd=work, capture_output=True, text=True)
        print(f"- unmutated: exit {run.returncode}, {summary_line(run.stderr)}")
    finally:
        shutil.rmtree(work)
    print("all mutations detected" if detected_all and run.returncode == 0 else "A MUTATION WAS NOT DETECTED")
    return 0 if detected_all and run.returncode == 0 else 1


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:3]))
