"""Mutation run for 01M4CM3YV9HEAHSW5V5ER4V8W7 (WI31, WI31-AC03): each mutation breaks one thing the pins or the guide
rely on, in a copy of the working tree, and runs what guards it. Every mutation must make that fail.

    python docs/evidence/01M4CM3YV9HEAHSW5V5ER4V8W7/mutations.py <repository> <a folder outside it, which must not exist yet> [label part]

A mutation of constraints.txt or of the workflow is guarded by `python -m unittest tests.test_pinned_versions` (no kits,
what the CI runs); a mutation of the guide, by check_guide.py next to this file. A mutation counts as detected only when
the guard ran and failed: a process that died has no result line and is "NOT RUN". The repository must be a clean
checkout: the script prints its commit, and the output of the recorded run is mutations.txt next to this file.
Modelled on docs/evidence/01M4CM3YV6DMY3QDWAZDMAANW6/mutations.py (WI28).
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

HERE = "docs/evidence/01M4CM3YV9HEAHSW5V5ER4V8W7/check_guide.py"
CONSTRAINTS = "constraints.txt"
WORKFLOW = ".github/workflows/tests.yml"
GUIDE = "docs/MAINTAINING.md"
TESTS = ["unittest", "tests.test_pinned_versions"]
CHECK = [HERE]

# (label, guard, file, old, new); each `old` has to be found exactly once.
MUTATIONS = [
    ("a library of pyproject.toml dropped from constraints.txt (numpy)", TESTS, CONSTRAINTS, "numpy==2.5.3\n", ""),
    ("a library the others bring dropped from constraints.txt (lxml)", TESTS, CONSTRAINTS, "lxml==6.1.3\n", ""),
    ("a pin made a range (numpy>=2.5.3)", TESTS, CONSTRAINTS, "numpy==2.5.3", "numpy>=2.5.3"),
    ("a pin made a wildcard (pillow==12.*)", TESTS, CONSTRAINTS, "pillow==12.3.0", "pillow==12.*"),
    ("a pin below the minimum of pyproject.toml (numpy==1.20.0)", TESTS, CONSTRAINTS, "numpy==2.5.3", "numpy==1.20.0"),
    ("a pin below the minimum, the version read as text (av==9.0.0 against av>=14)", TESTS, CONSTRAINTS,
     "av==19.0.0", "av==9.0.0"),
    ("a library pinned twice", TESTS, CONSTRAINTS, "numpy==2.5.3\n", "numpy==2.5.3\nnumpy==2.5.2\n"),
    ("the CI installs without the constraints", TESTS, WORKFLOW, "pip install -c constraints.txt", "pip install"),
    ("the CI no longer shows the versions installed", TESTS, WORKFLOW, "run: python -m pip list", "run: python --version"),
    ("a function the guide names does not exist (jobs.Runner._run renamed in the guide)", CHECK, GUIDE,
     "`jobs.Runner._run`", "`jobs.Runner._runn`"),
    ("a file the guide names does not exist (tests/test_texts.py renamed in the guide)", CHECK, GUIDE,
     "`tests/test_texts.py`", "`tests/test_textos.py`"),
    ("a command the guide names does not exist (python -m meetingtool.report)", CHECK, GUIDE,
     "`python -m meetingtool.report build`", "`python -m meetingtool.informe build`"),
]


def summary_line(stderr):
    lines = [line for line in stderr.strip().splitlines() if line.startswith(("Ran ", "OK", "FAILED"))]
    return " ".join(lines[-2:]) if lines else "(no result line)"


def run_guard(work, guard):
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONDONTWRITEBYTECODE": "1"}
    env.pop("PYTHONPATH", None)  # no kits: what the CI runs
    arguments = [sys.executable, "-m", *guard] if guard[0] == "unittest" else [sys.executable, *guard]
    try:
        return subprocess.run(arguments, cwd=work, capture_output=True, text=True, encoding="utf-8", errors="replace",
                              env=env, timeout=3600)
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess([], 124, "", "FAILED (timeout)")


def verdict(guard, result):
    """DETECTED only when the guard ran to its end and said something is wrong."""
    if guard[0] == "unittest":
        ran = "Ran " in result.stderr
        text = summary_line(result.stderr)
        failed = ran and result.returncode == 1 and "FAILED" in result.stderr
    else:
        ran = "names between backticks" in result.stdout
        text = (result.stdout.strip().splitlines() or ["(no output)"])[-1]
        failed = ran and result.returncode == 1
    if failed:
        return "DETECTED", text
    return ("NOT DETECTED" if ran and result.returncode == 0 else "NOT RUN (the guard did not finish)"), text


def main(argv):
    source, work = Path(argv[0]), Path(argv[1])
    only = argv[2] if len(argv) > 2 else ""
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=source, capture_output=True, text=True).stdout.strip()
    dirty = subprocess.run(["git", "status", "--porcelain"], cwd=source, capture_output=True, text=True).stdout.strip()
    shutil.copytree(source, work, ignore=shutil.ignore_patterns(".git", "__pycache__"))
    names = sorted({name for _, _, name, _, _ in MUTATIONS})
    originals = {name: (work / name).read_text(encoding="utf-8") for name in names}
    print("mutation run for 01M4CM3YV9HEAHSW5V5ER4V8W7: each mutation is applied alone to a copy of the working tree;")
    print("`python -m unittest tests.test_pinned_versions` (constraints and workflow) or check_guide.py (the guide) must fail")
    print(f"commit: {head}" + (" (the working tree has uncommitted changes)" if dirty else " (clean working tree)"))
    detected_all = True
    try:
        for label, guard, name, old, new in MUTATIONS:
            if only not in label:
                continue
            if originals[name].count(old) != 1:
                raise SystemExit(f"mutation {label!r} does not apply exactly once in {name}")
            (work / name).write_text(originals[name].replace(old, new), encoding="utf-8", newline="\n")
            result = run_guard(work, guard)
            said, text = verdict(guard, result)
            detected_all &= said == "DETECTED"
            print(f"- {label}: exit {result.returncode}, {text} -> {said}", flush=True)
            (work / name).write_text(originals[name], encoding="utf-8", newline="\n")
        tests, guide = run_guard(work, TESTS), run_guard(work, CHECK)
        print(f"- unmutated: tests exit {tests.returncode}, {summary_line(tests.stderr)}; "
              f"guide exit {guide.returncode}, {(guide.stdout.strip().splitlines() or ['(no output)'])[-1]}")
        unmutated_ok = tests.returncode == 0 and "OK" in tests.stderr and guide.returncode == 0
    finally:
        shutil.rmtree(work, ignore_errors=True)
    ok = detected_all and unmutated_ok
    print("all mutations detected" if ok else "A MUTATION WAS NOT DETECTED, OR THE UNMUTATED RUN FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
