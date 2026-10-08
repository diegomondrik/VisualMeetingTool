"""Mutation run for 01M4EFSYPJYBAMNG5AYWJQXG18 (WI33, WI33-AC03): each mutation breaks one thing the user manual or the installer's
entry for it relies on, in a copy of the working tree, and runs the tests that guard it. Every mutation must make
them fail. None needs INGOL's kits.

    python docs/evidence/01M4EFSYPJYBAMNG5AYWJQXG18/mutations.py <repository> <a folder outside it, which must not exist yet> [label part]

A mutation counts as detected only when the tests ran and failed: a process that died has no result line and is
"NOT RUN". The repository must be a clean checkout: the script prints its commit, and the output of the recorded
run is mutations.txt next to this file. Modelled on the mutation scripts of work items 28 to 31.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

MANUAL = "docs/manual/user-manual.html"
ISS = "packaging/installer.iss"
TESTS = ["tests.test_user_manual", "tests.test_packaging"]

# (label, file, old, new[, "all"]); each `old` has to be found exactly once, or at least once with "all" (a name
# the manual says in several places is changed in all of them: a test must see a name that is wrong everywhere).
MUTATIONS = [
    ("a screen name renamed in the manual (the field of the ceiling goes back to its old name)", MANUAL,
     '<strong data-ui="app.new.ceiling">Estimated spending ceiling in dollars</strong>',
     '<strong data-ui="app.new.ceiling">Spending ceiling in dollars</strong>'),
    ("a button renamed in the manual (Save the key)", MANUAL, '<strong data-ui="app.key.save">Save the key</strong>',
     '<strong data-ui="app.key.save">Store the key</strong>'),
    ("a name of the manual pointing to another text of the program (the key of the Save button)", MANUAL,
     'data-ui="app.key.save"', 'data-ui="app.key.delete"'),
    ("the largest ceiling changed in the manual (up to 5)", MANUAL, "above 0 and up to 5", "above 0 and up to 10"),

    ("the default ceiling changed in the manual", MANUAL, "<strong>US$1.00</strong>", "<strong>US$2.00</strong>"),
    ("the largest upload changed in the manual (the video, 16 GB)", MANUAL, "up to 16 GB", "up to 32 GB", "all"),
    ("the data folder changed in the manual", MANUAL, "VisualMeetingTool-data", "MeetingData", "all"),
    ("the log's name changed in the manual", MANUAL, "window.log", "meetingtool.log", "all"),
    ("a file type the program accepts dropped from the manual (.mkv)", MANUAL, "<code>.mkv</code>, ", ""),
    ("a section of the manual removed (Troubleshooting) but left in the contents", MANUAL,
     '<h2 id="trouble">12. Troubleshooting</h2>', '<h2 id="trouble-x">12. Troubleshooting</h2>'),
    ("a link of the contents pointing nowhere", MANUAL, 'href="#privacy"', 'href="#privacidad"', "all"),
    ("an outside script added to the manual", MANUAL, "</body>", '<script src="https://example.com/a.js"></script></body>'),
    ("a price quoted in the manual", MANUAL, "raise it only if the run stops.", "raise it only if the run stops; it costs about US$0.30."),
    ("the manual said not to be an estimate (the ceiling called a guarantee)", MANUAL, "not a guarantee",
     "a guarantee", "all"),
    ("the installer no longer copies the manual", ISS,
     'Source: "{#SourcePath}\\..\\docs\\manual\\user-manual.html"; DestDir: "{app}\\manual"; Flags: ignoreversion\n', ""),
    ("the installer's offer to open the manual ticked by default", ISS,
     "postinstall skipifsilent unchecked", "postinstall skipifsilent"),
    ("the Start menu entry of the manual removed", ISS,
     'Name: "{autoprograms}\\{cm:UserManual}"; Filename: "{app}\\manual\\user-manual.html"\n', ""),
    ("the manual's name missing in Spanish", ISS, "es.UserManual=", "xx.UserManual="),
]


def summary_line(stderr):
    lines = [line for line in stderr.strip().splitlines() if line.startswith(("Ran ", "OK", "FAILED"))]
    return " ".join(lines[-2:]) if lines else "(no result line)"


def run_tests(work):
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONDONTWRITEBYTECODE": "1"}
    env.pop("PYTHONPATH", None)
    try:
        return subprocess.run([sys.executable, "-B", "-m", "unittest", *TESTS], cwd=work, capture_output=True, text=True,
                              encoding="utf-8", errors="replace", env=env, timeout=1800)
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess([], 124, "", "FAILED (timeout)")


def main(argv):
    source, work = Path(argv[0]), Path(argv[1])
    only = argv[2] if len(argv) > 2 else ""
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=source, capture_output=True, text=True).stdout.strip()
    dirty = subprocess.run(["git", "status", "--porcelain"], cwd=source, capture_output=True, text=True).stdout.strip()
    shutil.copytree(source, work, ignore=shutil.ignore_patterns(".git", "__pycache__"))
    names = sorted({entry[1] for entry in MUTATIONS})
    originals = {name: (work / name).read_bytes().decode("utf-8") for name in names}
    print("mutation run for 01M4EFSYPJYBAMNG5AYWJQXG18: each mutation is applied alone to a copy of the working tree;")
    print(f"`python -m unittest {' '.join(TESTS)}` (no kits, what the CI runs) must fail")
    print(f"commit: {head}" + (" (the working tree has uncommitted changes)" if dirty else " (clean working tree)"))
    detected_all = True
    try:
        for label, name, old, new, *flags in MUTATIONS:
            if only not in label:
                continue
            text = originals[name]
            if text.count(old) != 1 and not (flags and text.count(old) >= 1):
                raise SystemExit(f"mutation {label!r} does not apply exactly once in {name}")
            (work / name).write_bytes(text.replace(old, new).encode("utf-8"))
            result = run_tests(work)
            ran = "Ran " in result.stderr
            detected = ran and result.returncode == 1 and "FAILED" in result.stderr
            detected_all &= detected
            verdict = "DETECTED" if detected else ("NOT DETECTED" if ran and result.returncode == 0
                                                   else "NOT RUN (the tests did not finish)")
            print(f"- {label}: exit {result.returncode}, {summary_line(result.stderr)} -> {verdict}", flush=True)
            (work / name).write_bytes(text.encode("utf-8"))
        result = run_tests(work)
        print(f"- unmutated: exit {result.returncode}, {summary_line(result.stderr)}")
        unmutated_ok = result.returncode == 0 and "OK" in result.stderr
    finally:
        shutil.rmtree(work, ignore_errors=True)
    ok = detected_all and unmutated_ok
    print("all mutations detected" if ok else "A MUTATION WAS NOT DETECTED, OR THE UNMUTATED RUN FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
