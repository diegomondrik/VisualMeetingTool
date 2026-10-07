"""Mutation run for 01M4B3HE2AVWM7CEPPNRWS9SFY (WI25, WI25-AC04): each mutation undoes or bends one part of what
a summary and a register must say, in a copy of the working tree, and runs the tests that guard it. Every mutation
must make them fail. None needs INGOL's kits: the tests are the ones the CI runs.

    python docs/evidence/01M4B3HE2AVWM7CEPPNRWS9SFY/mutations.py <repository> <a folder outside it, which must not exist yet> [label part]

With a label part, only the mutations whose label holds it are run. The
repository must be a clean checkout: the script prints its commit, and the
output of the recorded run is mutations.txt next to this file. Modelled on
docs/evidence/01M48RAZZ5MGGHYTJNYR2VQP0Z/mutations.py (WI23).
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

WRITER = "meetingtool/summary/writer.py"
QA = "meetingtool/summary/qa.py"
TESTS = ["tests.test_summary.EmptySectionTest", "tests.test_summary.SeveralReasonsTest",
         "tests.test_qa.YearsAndFiguresTest", "tests.test_qa.YearsAnywhereAndScalesTest", "tests.test_qa.DatesTest",
         "tests.test_d1_r04_resumen"]

# (label, [(file, old, new)]); each `old` has to be found exactly once.
MUTATIONS = [
    ("empty sections accepted: the check of the empty sections off",
     [(WRITER, r"""    if empty:
        problems.append(""", r"""    if False:
        problems.append(""")]),
    ("empty sections accepted: a rule, an empty bullet or a table's rule counted as content",
     [(WRITER, r"""_CONTENT = re.compile(r"[^\W_]")""", r"""_CONTENT = re.compile(r"\S")""")]),
    ("the refusal names only the first of the empty sections",
     [(WRITER, r"""texts.Message("summary.empty_sections", headings=", ".join(empty))""",
       r"""texts.Message("summary.empty_sections", headings=empty[0])""")]),
    ("an empty section's end taken at any heading: the content under its subsections is not its content",
     [(WRITER, r"""re.finditer(rf"^#{{1,{level}}}\s", body, re.MULTILINE)""", r"""re.finditer(r"^#{1,4}\s", body, re.MULTILINE)""")]),
    ("an empty section's end not taken at the next required heading: a deeper heading after it runs it on",
     [(WRITER, r"""        if after:
""", r"""        if False:
""")]),
    ("the retry without the empty sections: it sends the same request, as for any other refusal",
     [(WRITER, r"""    "summary.empty_sections": (""", r"""    "summary.empty_sections_not_told": (""")]),
    ("the request does not tell Gemini that every section has content or says there was none",
     [(WRITER, r"""    lines += ["", EMPTY_RULE]
""", "")]),
    ("the year dropped again: written_dates keeps day and month only",
     [(QA, r"""    return {date for _, _, date in _dates_in(text.casefold())}""",
       r"""    return {(day, month, None) for _, _, (day, month, _) in _dates_in(text.casefold())}""")]),
    ("the year not compared: a date with a year is checked by day and month",
     [(QA, r"""if date[:2] not in transcript.dates or (date[2] and date[2] not in transcript.years)""",
       r"""if date[:2] not in transcript.dates""")]),
    ("the meeting's year not accepted: only the years the transcript says",
     [(QA, r"""            years.add(day.year)
""", "")]),
    ("the years of the transcript not read: only the meeting's year is accepted",
     [(QA, r"""        years = written_years(f"{text}\n{spoken}")""", r"""        years = set()""")]),
    ("the figures not checked",
     [(QA, r"""                if group == "figures":""", r"""                if False:""")]),
    ("every group checked as figures said: the derived figures of the other places refused",
     [(QA, r"""                if group == "figures":""", r"""                if True:""")]),
    ("figures compared as text, not as numbers",
     [(QA, r"""        figures = {value for token in _NUMBERS.finditer(clockless) for value in _values(token.group())}""",
       r"""        figures = {token.group() for token in _NUMBERS.finditer(clockless)}"""),
      (QA, r"""if values.get(token.start(), number(token.group())) not in said]""", r"""if token.group() not in said]""")]),
    ("figures compared as numbers, a single separator with three digits read as a decimal point",
     [(QA, r"""    elif len(marks) > 1 or re.fullmatch(r"[1-9]\d{0,2}[.,]\d{3}", token):""", r"""    elif len(marks) > 1:""")]),
    ("the year on its own off: only the years written in a date are checked",
     [(QA, r"""    years = sorted(written_years(text) - transcript.years)""", r"""    years = []""")]),
    ("the scale said with a number not read in the transcript: 48 mil is only 48",
     [(QA, r"""        figures |= {value for _, _, value in scaled(clockless)}
""", "")]),
    ("the scale written with a number not read in the figure: 48 mil is only 48",
     [(QA, r"""    values = {start: value for start, end, value in scaled(lowered)}""", r"""    values = {}""")]),
    ("the retry's note with a single reason: only the first refusal is named",
     [(WRITER, r"""for message in (error.message, *getattr(error, "others", ())) if getattr(message, "key", "") in REASONS]""",
       r"""for message in (error.message,) if getattr(message, "key", "") in REASONS]""")]),
    ("the other reasons of the refusal not kept: only the first travels with the error",
     [(WRITER, r"""        error.others = tuple(problems[1:])""", r"""        error.others = ()""")]),
    ("the dates of a figure's entry looked for as figures",
     [(QA, r"""    for start, end, _ in reversed(_dates_in(lowered)):
        lowered = lowered[:start] + " " + lowered[end:]
""", "")]),
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
    print("mutation run for 01M4B3HE2AVWM7CEPPNRWS9SFY: each mutation is applied alone to a copy of the working tree;")
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
