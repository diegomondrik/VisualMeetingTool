"""Mutation run for 01M4CM3YV6DMY3QDWAZDMAANW6 (WI28, WI28-AC03): each mutation undoes or bends one part of how a run
stops when an answer cost more than its estimate, in a copy of the working tree, and runs the tests that guard it.
Every mutation must make them fail. None needs INGOL's kits: the tests are the ones the CI runs.

    python docs/evidence/01M4CM3YV6DMY3QDWAZDMAANW6/mutations.py <repository> <a folder outside it, which must not exist yet> [label part]

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

GEMINI = "meetingtool/reading/gemini.py"
WRITER = "meetingtool/summary/writer.py"
QA = "meetingtool/summary/qa.py"
TESTS = ["tests.test_spending_estimate"]

# (label, [(file, old, new)]); each `old` has to be found exactly once.
MUTATIONS = [
    ("the stop after an overrun removed: a run with an answer that cost more than estimated goes on sending",
     [(GEMINI, '''        if counters["overrun"] is not None:
            stop_for_estimate(counters, texts.Message("gemini.estimate_short.before", what=what), refused)
''', "")]),
    ("the overrun compared against the ceiling (max_cost_usd) instead of against the request's estimate",
     [(GEMINI, "if cost > worst and counters", "if cost > max_cost_usd and counters")]),
    ("the overrun never marked: an answer that cost more than estimated is counted and nothing else",
     [(GEMINI, 'counters["overrun"] = {"what": what, "estimated": float(worst), "cost": float(cost)}', "pass")]),
    ("the kept answer not written when it overran",
     [(GEMINI, "            if kept is not None:\n                text = ",
       "            if kept is not None and counters[\"overrun\"] is None:\n                text = ")]),
    ("the retry of a refused answer that overran is sent: the stop is skipped after a refusal",
     [(GEMINI, '        if counters["overrun"] is not None:\n',
       '        if counters["overrun"] is not None and not refused:\n')]),
    ("an answer at exactly its estimate counts as an overrun",
     [(GEMINI, "if cost > worst and counters", "if cost >= worst and counters")]),
    ("the end-of-run check removed from the reading: an overrun on its last request is written and done",
     [(GEMINI, "    check_estimate(counters)\n    header = ", "    header = ")]),
    ("the end-of-run check removed from the summary: an overrun on its last request is written and done (the review's P1-2)",
     [(WRITER, "    gemini.check_estimate(counters)\n", "")]),
    ("the end-of-run check removed from the register",
     [(QA, "    gemini.check_estimate(counters)\n", "")]),
    ("the end-of-run check does nothing: check_estimate returns without raising",
     [(GEMINI, '''    if counters["overrun"] is not None:
        stop_for_estimate(counters, texts.Message("gemini.estimate_short.end"))''', "    return")]),
    ("the counters of a run made without the overrun key",
     [(GEMINI, ', "models": set(), "overrun": None}', ', "models": set()}')]),
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
    print("mutation run for 01M4CM3YV6DMY3QDWAZDMAANW6: each mutation is applied alone to a copy of the working tree;")
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
