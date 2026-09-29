"""Mutation run for 01M3Q46RMB70H2F5NE56SVQD5M (WI14): each mutation removes
or bends one check or one piece of the question-and-answer register in
meetingtool/summary/qa.py (or, for the option, meetingtool/summary/__main__.py,
and for the reading and the retry, meetingtool/reading/gemini.py),
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
GEMINI = "meetingtool/reading/gemini.py"
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
     ' or not transcript.says(fields["quote"], start, end)', ""),
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
    ("a question outside its batch kept, so registered twice (AC03, review P2-4)", QA,
     "    if raised is not None and not window[0] <= raised < window[1]:\n        return None",
     "    if False:\n        return None"),
    ("a verbatim fragment of fewer than five words accepted (AC03)", QA,
     'len(plain_words(fields["quote"])) < QUOTE_WORDS or ', ""),
    ("a fragment said at another moment of the meeting accepted (AC03, review P2-6)", QA,
     "if start - QUOTE_MARGIN <= second <= end + QUOTE_MARGIN)", "if True)"),
    ("a date in the project's knowledge not checked (AC03)", QA,
     "_check_text(entry, f\"the knowledge '{group}'\", transcript)", "pass"),
    ("a day/month without a year read as a date anywhere (AC03, review P2-5)", QA,
     'hasta el|desde el|para el|antes del|después del|on|by|until|before|after|from)"\n'
     '                r"\\s+(\\d{1,2})', 'hasta el|desde el|para el|antes del|después del|on|by|until|before|after|from)?"\n'
     '                r"\\s*(\\d{1,2})'),
    ("the retry resends the same request (review P2-2)", GEMINI,
     "                    payload = revise(payload, error)\n", "                    pass\n"),
    ("a deadline said without an agreement or a pending item left out (review P3-7)", QA,
     "if q.deadline or q.agreement or q.pending:", "if q.agreement or q.pending:"),
    ("what was seen missing for an answer on screen accepted (AC03)", QA,
     "    if missing:\n        raise QAError", "    if False:\n        raise QAError"),
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
     "return before[-1:] + [path for second, path in timed if start <= second <= min(end, start + SPAN_MAX)]",
     "return [path for _, path in timed]"),
    ("a verbal answer looks for frames too (AC06)", QA,
     "spans = {q.id: span_frames(frames, q.start, q.end) for q in questions if q.screen}",
     "spans = {q.id: span_frames(frames, q.start, q.end) for q in questions}"),
    ("the frame on screen when an answer began left out of its span (AC06)", QA,
     "return before[-1:] + [", "return [] + ["),
    ("the span of an answer taken up again later not bounded (AC06, review P2-3)", QA,
     "second <= min(end, start + SPAN_MAX)]", "second <= end]"),
    ("a few frames reserve the output of seventy (review P1-1)", GEMINI,
     "listed_output_tokens(len(chunk)))", "MAX_OUTPUT_TOKENS)"),
    ("any fragment sharing one word with the answer's minutes accepted (owner's 85%, run 2)", QA,
     "math.ceil(QUOTE_MATCH * len(wanted))", "1"),
    ("'Name: what they said' in the speaker's field refused (run 1)", QA,
     "if colon and not transcript.spoke(speaker) and transcript.spoke(name):", "if False:"),
    ("the retry told of the first refused question only (run 2)", QA,
     "            refused.append(str(error))\n", "            raise\n"),
    ("an accepted batch not kept, so paid again (run 2)", QA,
     '_keep(kept, {"digest": digest, "answer": text})', "pass"),
    ("the words that show the screen matched at 85% instead of literally (re-verification P2-1)", QA,
     'transcript.says(fields["screen_quote"], start, end, exact=True)',
     'transcript.says(fields["screen_quote"], start, end)'),
    ("a fragment's words matched however far apart (re-verification P2-2)", QA,
     "len(wanted) + max(4, len(wanted) // 2))", "10 ** 6)"),
]
TESTS = ["tests.test_qa", "tests.test_summary", "tests.test_report"]


def summary_line(stderr):
    return [line for line in stderr.splitlines() if line.startswith(("FAILED", "OK"))][-1]


def main(source, work):
    source, work = Path(source), Path(work)
    shutil.copytree(source, work, ignore=shutil.ignore_patterns(".git", "__pycache__"))
    originals = {name: (work / name).read_text(encoding="utf-8") for name in (QA, MAIN, GEMINI)}
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
