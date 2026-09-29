"""Mutation run for 01M3Q46RMB70H2F5NE56SVQD5M (WI14): each mutation removes
or bends one check or one piece of the question-and-answer register in
meetingtool/summary/qa.py (or, for the option, meetingtool/summary/__main__.py),
in a copy of the working tree, runs
`python -m unittest tests.test_qa tests.test_summary tests.test_report`, and
must make it fail.

    python docs/evidence/01M3Q46RMB70H2F5NE56SVQD5M/mutations.py <repository> <empty folder outside it>

The output of the recorded run is mutations.txt next to this file.
"""

import shutil
import subprocess
import sys
from pathlib import Path

QA = "meetingtool/summary/qa.py"
MAIN = "meetingtool/summary/__main__.py"
MUTATIONS = [
    ("without the option, the register is written instead of the summary (AC01)", MAIN,
     'write = qa.write_register if args.format == "qa" else writer.write_summary', "write = qa.write_register"),
    ("the meeting type's stance left out of the request (AC02)", QA,
     "    if meeting_type and writer.MEETING_TYPES[meeting_type].stance:\n        lines += [f\"MEETING TYPE",
     "    if False:\n        lines += [f\"MEETING TYPE"),
    ("the language left out of the request (AC02)", QA, 'f"Write the register in {name}.", ', ""),
    ("the pending item of a question left out of the register (AC02)", QA,
     "            lines.append(f\"- **{labels['open']}:** {_line(q.pending)}\")", "            pass"),
    ("the verbatim fragment not checked against the transcript (AC03)", QA,
     ' or not transcript.says(fields["quote"])', ""),
    ("the answering speaker not checked (AC03)", QA, "        if not transcript.spoke(speaker):\n",
     "        if False:\n"),
    ("the asker not checked (AC03)", QA, 'if fields["asked_by"] and not transcript.spoke(fields["asked_by"]):',
     "if False:"),
    ("a minute after the meeting accepted (AC03)", QA, "if end > transcript.last + END_SLACK:", "if False:"),
    ("an answer ending before it starts accepted (AC03)", QA, "if end < start:", "if False:"),
    ("a status outside the four accepted (AC03)", QA, 'if fields["status"] not in STATUSES:', "if False:"),
    ("a date the transcript does not say accepted (AC03)", QA,
     "invented = sorted(written_dates(text) - transcript.dates)", "invented = []"),
    ("on screen accepted without the words that show it (AC03)", QA,
     'if screen and (len(plain_words(fields["screen_quote"]))',
     'if False and (len(plain_words(fields["screen_quote"]))'),
    ("a question outside its batch accepted (AC03)", QA, "if not window[0] <= start < window[1]:", "if False:"),
    ("the register's language not checked (AC03)", QA,
     '_check_language("\\n".join(said), "the register", language)', "pass"),
    ("a frame mentioned in the register's text accepted (AC03)", QA,
     '    if writer.FRAME_LIKE.search(text):\n        raise QAError(f"{where} mentions a frame")',
     '    if False:\n        raise QAError(f"{where} mentions a frame")'),
    ("what was seen may name a frame outside the span (AC03, AC06)", QA,
     "outside = [name for name in frames if name not in needing[identifier]]", "outside = []"),
    ("what was seen may go to an answer that is not on screen (AC03, AC06)", QA,
     "        if identifier not in needing:\n", "        if False:\n"),
    ("every frame read, whatever the answers (AC05)", QA,
     "wanted = sorted({path for paths in spans.values() for path in paths})", "wanted = sorted(frames)"),
    ("the span widened to the whole meeting (AC06)", QA,
     "return before[-1:] + [path for second, path in timed if start <= second <= end]",
     "return [path for _, path in timed]"),
    ("a verbal answer looks for frames too (AC06)", QA,
     "spans = {q.id: span_frames(frames, q.start, q.end) for q in questions if q.screen}",
     "spans = {q.id: span_frames(frames, q.start, q.end) for q in questions}"),
    ("the frame on screen when an answer began left out of its span (AC06)", QA,
     "return before[-1:] + [", "return [] + ["),
]
TESTS = ["tests.test_qa", "tests.test_summary", "tests.test_report"]


def summary_line(stderr):
    return [line for line in stderr.splitlines() if line.startswith(("FAILED", "OK"))][-1]


def main(source, work):
    source, work = Path(source), Path(work)
    shutil.copytree(source, work, ignore=shutil.ignore_patterns(".git", "__pycache__"))
    originals = {name: (work / name).read_text(encoding="utf-8") for name in (QA, MAIN)}
    print("mutation run for 01M3Q46RMB70H2F5NE56SVQD5M: each mutation is applied alone to a copy of the")
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
