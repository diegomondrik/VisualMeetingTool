"""Mutation run for 01M4CB9FV6XGEYENDJYAEQZWQX (WI27, WI27-AC04): each mutation undoes or bends one part of how a
list of frames in one pair of square brackets is taken, or of what the retry says about how a frame is named, in a
copy of the working tree, and runs the tests that guard it. Every mutation must make them fail. None needs INGOL's
kits: the tests are the ones the CI runs.

    python docs/evidence/01M4CB9FV6XGEYENDJYAEQZWQX/mutations.py <repository> <a folder outside it, which must not exist yet> [label part]

With a label part, only the mutations whose label holds it are run. The
repository must be a clean checkout: the script prints its commit, and the
output of the recorded run is mutations.txt next to this file. Modelled on
docs/evidence/01M4BGTP1940T4ASG54GC323WT/mutations.py (WI26).
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

WRITER = "meetingtool/summary/writer.py"
TESTS = ["tests.test_summary.FrameListTest"]

# (label, [(file, old, new)]); each `old` has to be found exactly once.
MUTATIONS = [
    ("the rewriting switched off: check_summary does not separate the frames of a list",
     [(WRITER, "    text = separate_frames(text)\n", "")]),
    ("a list split across a range word: \"a\" and \"to\" separate two names like \"y\" does",
     [(WRITER, r"""|;|\b(?i:y|e|and)\b){_SPACE}""", r"""|;|\b(?i:y|e|and|a|to)\b){_SPACE}""")]),
    ("a list split across a range mark: a hyphen separates two names like a semicolon does",
     [(WRITER, r"""|;|\b(?i:y|e|and)\b){_SPACE}""", r"""|;|-|\b(?i:y|e|and)\b){_SPACE}""")]),
    ("the wrapper lost: backticks or bold round a list are dropped from the pairs",
     [(WRITER, 'f"{mark}[{name}]{mark}" for name', 'f"[{name}]" for name')]),
    ("the retry note for a range removed from REASONS",
     [(WRITER, '''    "summary.frame_range": (
        "it named a range of frames instead of each frame on its own: {names}", "text",
        "Name each frame in its own square brackets, one file name for each pair, as in [frame_017_t00-13-03.jpg]; "
        "never a range of frames, and never a list of frames inside one pair of brackets."),
''', "")]),
    ("the retry note for a frame without its own brackets removed from REASONS",
     [(WRITER, '''    "summary.frame_unbracketed": (
        "it mentioned a frame without its file name in square brackets: {names}", "text",
        "Name each frame in its own square brackets, one whole file name for each pair, as in "
        "[frame_017_t00-13-03.jpg]; never mention a frame by its number, its time or part of its name."),
''', "")]),
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
    print("mutation run for 01M4CB9FV6XGEYENDJYAEQZWQX: each mutation is applied alone to a copy of the working tree;")
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
