"""Mutation run for 01M4BGTP1940T4ASG54GC323WT (WI26, WI26-AC03): each mutation undoes or bends one part of how a
text transcript is read, in a copy of the working tree, and runs the tests that guard it. Every mutation must make
them fail. None needs INGOL's kits: the tests are the ones the CI runs.

    python docs/evidence/01M4BGTP1940T4ASG54GC323WT/mutations.py <repository> <a folder outside it, which must not exist yet> [label part]

With a label part, only the mutations whose label holds it are run. The
repository must be a clean checkout: the script prints its commit, and the
output of the recorded run is mutations.txt next to this file. Modelled on
docs/evidence/01M4B3HE2AVWM7CEPPNRWS9SFY/mutations.py (WI25).
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

TRANSCRIPT = "meetingtool/frames/transcript.py"
TESTS = ["tests.test_transcript_encodings", "tests.test_frames.TranscriptTest"]

# (label, [(file, old, new)]); each `old` has to be found exactly once.
MUTATIONS = [
    ("the byte order mark kept: a UTF-8 file with a mark is read as plain UTF-8, U+FEFF before its first line",
     [(TRANSCRIPT, r"""        return data[len(codecs.BOM_UTF8):].decode("utf-8")""",
       r"""        return data.decode("utf-8")"""),
      (TRANSCRIPT, r"""        return _decode(Path(path).read_bytes()).lstrip("\ufeff").splitlines()""",
       r"""        return _decode(Path(path).read_bytes()).splitlines()""")]),
    ("a second mark kept: a file saved with its mark twice keeps U+FEFF before its first line (review P3-1)",
     [(TRANSCRIPT, r"""        return _decode(Path(path).read_bytes()).lstrip("\ufeff").splitlines()""",
       r"""        return _decode(Path(path).read_bytes()).splitlines()""")]),
    ("UTF-16 not detected: a file with a UTF-16 mark goes through the UTF-8 and cp1252 readings",
     [(TRANSCRIPT, r"""    if data.startswith((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)):""", r"""    if False:""")]),
    ("no cp1252 fallback: a file that is not valid UTF-8 is refused",
     [(TRANSCRIPT, r"""        return data.decode("cp1252")""", r"""        raise""")]),
    ("the backtracking pattern back: the speaker-and-time pattern as it was before WI26",
     [(TRANSCRIPT, r"""_SPEAKER_TIME = re.compile(r"^(.*?\S)\s{2,}(\d{1,2}:\d{2}(?::\d{2})?)\s*$")""",
       r"""_SPEAKER_TIME = re.compile(r"^(.+?)\s{2,}(\d{1,2}:\d{2}(?::\d{2})?)\s*$")""")]),
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
    print("mutation run for 01M4BGTP1940T4ASG54GC323WT: each mutation is applied alone to a copy of the working tree;")
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
