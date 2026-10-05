"""Mutation run for 01M474JN9F7N86SHHSKZ41Q1VY (WI21, WI21-AC03): each mutation
puts back, in a copy of the working tree, a form of the cut WI21 removed (a
stop time taken from the transcript's last line, or the decode loop leaving
early when a transcript is given), or undoes what the transcript still does
(raising the score of the samples near a phrase that points at the screen),
and runs the tests that guard it. Every mutation must make the tests fail.

    python docs/evidence/01M474JN9F7N86SHHSKZ41Q1VY/mutations.py <repository> <empty folder outside it> [label part]

Two selections are run for each mutation, and the first one decides: the
frames tests of the repository's CI (`tests.test_frames.MeetingRealityTest`),
and the pilot's test of the defect (`tests.test_d1_final_de_la_reunion`),
recorded besides. With a label part, only the mutations whose label holds it
are run. The output of the recorded run is mutations.txt next to this file.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

EXTRACT = "meetingtool/frames/extract.py"
MAIN = "meetingtool/frames/__main__.py"
CI = ["tests.test_frames.MeetingRealityTest"]
PILOT = ["tests.test_d1_final_de_la_reunion"]

AFTER_LAST_DISTINCT = "    last_distinct_gray = None\n"
IN_THE_LOOP = "            timestamp = float(frame.pts * stream.time_base)\n"
THE_RESULT = "boosted, boosted_in)"
THE_BOOST = "            score = references.boost(base_score, timestamp) if references else base_score\n"
THE_REPORT = '        print(f"candidates raised by the transcript: {result.boosted} ({result.boosted_in} only because of it)")\n'

# What WI10 had, as it was: a stop time from the last line, the loop leaving at it, and the result saying so.
THE_CUT = [
    (EXTRACT, AFTER_LAST_DISTINCT, AFTER_LAST_DISTINCT +
     "    stop_at = references.last + TRANSCRIPT_TAIL if references is not None else None\n"
     "    read_until = None\n"),
    (EXTRACT, IN_THE_LOOP, IN_THE_LOOP +
     "            if stop_at is not None and timestamp > stop_at:\n"
     "                read_until = stop_at\n"
     "                break\n"),
    (EXTRACT, THE_RESULT, "boosted, boosted_in, read_until)"),
]

# (label, [(file, old, new)])
MUTATIONS = [
    ("the cut as WI10 had it: a stop time, the last line's start plus TRANSCRIPT_TAIL", THE_CUT),
    ("a stop time at the last line's start itself, no tail",
     [(EXTRACT, AFTER_LAST_DISTINCT, AFTER_LAST_DISTINCT +
       "    stop_at = references.last if references is not None else None\n"),
      (EXTRACT, IN_THE_LOOP, IN_THE_LOOP +
       "            if stop_at is not None and timestamp > stop_at:\n                break\n")]),
    ("a stop time only when the transcript ends before the recording does",
     [(EXTRACT, AFTER_LAST_DISTINCT, AFTER_LAST_DISTINCT +
       "    stop_at = None\n"
       "    if references is not None and references.last + TRANSCRIPT_TAIL < 140.0:\n"
       "        stop_at = references.last + TRANSCRIPT_TAIL\n"),
      (EXTRACT, IN_THE_LOOP, IN_THE_LOOP +
       "            if stop_at is not None and timestamp > stop_at:\n                break\n")]),
    ("the decode loop leaving early when a transcript is given, whatever it says",
     [(EXTRACT, IN_THE_LOOP, IN_THE_LOOP +
       "            if references is not None and samples >= 200:\n                break\n")]),
    ("the decode loop leaving after the last phrase that points at the screen, plus its window",
     [(EXTRACT, IN_THE_LOOP, IN_THE_LOOP +
       "            if references is not None and references.times and timestamp > references.times[-1] + 30.0:\n"
       "                break\n")]),
    ("the command line saying where reading stopped, whatever happened",
     [(MAIN, THE_REPORT, THE_REPORT + '        print("read until 1s of 140s: the transcript\'s last line starts 1s in")\n')]),
    ("the transcript no longer raising any candidate",
     [(EXTRACT, THE_BOOST, "            score = base_score\n")]),
]


def summary_line(stderr):
    lines = [line for line in stderr.strip().splitlines() if line.startswith(("Ran ", "OK", "FAILED"))]
    return " ".join(lines[-2:]) if lines else "(no result line)"


def run_tests(work, names):
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONDONTWRITEBYTECODE": "1"}
    try:
        return subprocess.run([sys.executable, "-m", "unittest", *names], cwd=work, capture_output=True, text=True,
                              encoding="utf-8", errors="replace", env=env, timeout=1800)
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess([], 124, "", "FAILED (timeout)")


def main(argv):
    source, work = Path(argv[0]), Path(argv[1])
    only = argv[2] if len(argv) > 2 else ""
    shutil.copytree(source, work, ignore=shutil.ignore_patterns(".git", "__pycache__"))
    names = sorted({name for _, edits in MUTATIONS for name, _, _ in edits})
    originals = {name: (work / name).read_text(encoding="utf-8") for name in names}
    print("mutation run for 01M474JN9F7N86SHHSKZ41Q1VY: each mutation is applied alone to a copy of the working")
    print(f"tree; `python -m unittest {' '.join(CI)}` (what the CI runs) must fail; "
          f"`python -m unittest {' '.join(PILOT)}` is run besides and recorded")
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
            ci = run_tests(work, CI)
            pilot = run_tests(work, PILOT)
            detected = ci.returncode != 0
            detected_all &= detected
            print(f"- {label}: frames tests exit {ci.returncode}, {summary_line(ci.stderr)} -> "
                  f"{'DETECTED' if detected else 'NOT DETECTED'}; pilot test exit {pilot.returncode}, "
                  f"{summary_line(pilot.stderr)}", flush=True)
            for name in names:
                (work / name).write_text(originals[name], encoding="utf-8", newline="\n")
        ci, pilot = run_tests(work, CI), run_tests(work, PILOT)
        print(f"- unmutated: frames tests exit {ci.returncode}, {summary_line(ci.stderr)}; "
              f"pilot test exit {pilot.returncode}, {summary_line(pilot.stderr)}")
        unmutated_ok = ci.returncode == 0 and pilot.returncode == 0
    finally:
        shutil.rmtree(work, ignore_errors=True)
    ok = detected_all and unmutated_ok
    print("all mutations detected" if ok else "A MUTATION WAS NOT DETECTED, OR THE UNMUTATED RUN FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
