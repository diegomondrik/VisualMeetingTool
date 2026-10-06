"""Mutation run for 01M495140RMJM90PFDGBN7XZMF (WI24, WI24-AC05): each mutation
undoes one part of what WI24 added, in a copy of the working tree, and runs the
tests that guard it. Every mutation must make them fail. None needs INGOL's
kits: the tests are the ones the CI runs.

    python docs/evidence/01M495140RMJM90PFDGBN7XZMF/mutations.py <repository> <a folder outside it, which must not exist yet> [label part]

With a label part, only the mutations whose label holds it are run. The
repository must be a clean checkout: the script prints its commit, and the
output of the recorded run is mutations.txt next to this file.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

TRANSCRIPT = "meetingtool/frames/transcript.py"
WRITER = "meetingtool/summary/writer.py"
QA = "meetingtool/summary/qa.py"
JOBS = "meetingtool/app/jobs.py"
TESTS = ["tests.test_frames.TranscriptTest", "tests.test_summary.NoSpeakerTest",
         "tests.test_summary.FrameLabelsTest", "tests.test_qa.RequestTest", "tests.test_app.RunningStageTest",
         "tests.test_app.NoSpeakerRequestTest"]

# What read_blocks was before WI24: its own loop, with no rule for a time alone on its line.
OLD_READ_BLOCKS = r'''    path = Path(path)
    if not path.is_file():
        raise TranscriptError("transcript.not_a_file", path=str(path))
    lines = _docx_lines(path) if path.suffix.lower() == ".docx" else _text_lines(path)
    blocks = []
    for raw in lines:
        line = raw.strip()
        if not line:
            continue
        teams = _SPEAKER_TIME.match(line)
        bracket = _BRACKET_TIME.match(line)
        if teams:
            blocks.append([_seconds(teams.group(2)), []])
        elif bracket:
            hours, minutes, seconds, rest = bracket.groups()
            blocks.append([int(hours) * 3600 + int(minutes) * 60 + int(seconds), [rest] if rest else []])
        elif blocks:
            blocks[-1][1].append(line)
    if not blocks:
        raise TranscriptError("transcript.no_timed_line", path=str(path))
    return sorted(((start, "\n".join(text)) for start, text in blocks), key=lambda block: block[0])
'''

# (label, [(file, old, new)])
MUTATIONS = [
    ("the time-only rule removed: a line that is only a time starts no block",
     [(TRANSCRIPT, r'''        elif alone:
            turns.append([_seconds(line), "", []])
''', "")]),
    ("the two readers apart again: read_blocks keeps its old loop, with no rule for a time alone",
     [(TRANSCRIPT, r'''    return [(start, text) for start, _, text in _read(path)[0]]
''', OLD_READ_BLOCKS)]),
    ("the blocks of the reading labelled by number only, with the list of names at its top, as before WI24",
     [(WRITER, r'''              label_frames(frames_reading)]''', r'''              frames_reading.strip()]''')]),
    ("the retry without what was wrong: the same request sent again after a refusal",
     [(WRITER, r'''max_cost_usd, revise,
''', r'''max_cost_usd,
''')]),
    ("the retry's note without the names that do not exist",
     [(WRITER, r'''FRAMES_NOTE.format(names=message.params["names"][:RETRY_NOTE_CHARS - len(FRAMES_NOTE)])''',
       r'''FRAMES_NOTE.format(names="")''')]),
    ("the running stage's time frozen at 0: its seconds only when it ends",
     [(JOBS, r'''        running = self.state == "running" and self.started is not None
''', r'''        running = False
''')]),
    ("the register's stop for a transcript with no speaker removed",
     [(QA, r'''    if nobody:''', r'''    if False:''')]),
    # The independent review of 0f6a3a8.
    ("the register's stop applied also to a transcript with [HH:MM:SS] lines, which have no name in the turn",
     [(QA, r'''    if nobody:''', r'''    if not any(speaker.strip() for _, speaker, _ in turns):''')]),
    ("the time-only rule applied although the file has lines with a speaker or [HH:MM:SS] lines",
     [(TRANSCRIPT, r'''        alone = _TIME_ALONE.match(line) and not labelled
''', r'''        alone = _TIME_ALONE.match(line)
''')]),
    ("the check of the request for a register with a transcript that names no one removed",
     [(JOBS, r'''        if nobody:
            raise JobError''', r'''        if False:
            raise JobError''')]),
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
    if work.exists():
        raise SystemExit(f"{work} exists: give a folder that does not, which this script creates and removes")
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=source, capture_output=True, text=True).stdout.strip()
    dirty = subprocess.run(["git", "status", "--porcelain"], cwd=source, capture_output=True, text=True).stdout.strip()
    shutil.copytree(source, work, ignore=shutil.ignore_patterns(".git", "__pycache__"))
    names = sorted({name for _, edits in MUTATIONS for name, _, _ in edits})
    originals = {name: (work / name).read_text(encoding="utf-8") for name in names}
    print("mutation run for 01M495140RMJM90PFDGBN7XZMF: each mutation is applied alone to a copy of the working tree;")
    print(f"`python -m unittest {' '.join(TESTS)}` (no kits, what the CI runs) must fail")
    print(f"commit: {head}" + (" (the working tree has uncommitted changes)" if dirty else " (clean working tree)"))
    detected_all = True
    try:
        result = run_tests(work)
        print(f"- unmutated: exit {result.returncode}, {summary_line(result.stderr)}", flush=True)
        unmutated_ok = result.returncode == 0
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
        print(f"- unmutated again: exit {result.returncode}, {summary_line(result.stderr)}")
        unmutated_ok = unmutated_ok and result.returncode == 0
    finally:
        shutil.rmtree(work, ignore_errors=True)
    ok = detected_all and unmutated_ok
    print("all mutations detected" if ok else "A MUTATION WAS NOT DETECTED, OR THE UNMUTATED RUN FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
