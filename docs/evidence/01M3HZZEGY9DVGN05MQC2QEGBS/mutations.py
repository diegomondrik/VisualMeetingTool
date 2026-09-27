"""Mutation run for 01M3HZZEGY9DVGN05MQC2QEGBS (WI11): each mutation removes
one check from meetingtool/report/document.py in a copy of the working tree,
runs `python -m unittest tests.test_report`, and must make it fail.

    python docs/evidence/01M3HZZEGY9DVGN05MQC2QEGBS/mutations.py <repository> <empty folder outside it>

The output of the recorded run is mutations.txt next to this file.
"""

import shutil
import subprocess
import sys
from pathlib import Path

MUTATIONS = [
    ("missing-frame check removed (AC03)",
     "                if not frames[name].is_file():\n", "                if False:\n"),
    ("malformed-mention check removed (AC03)",
     "        if FRAME_LIKE.search(leftover):\n", "        if False:\n"),
    ("check_report always passes (AC04)",
     "    document = docx.Document(str(path))\n    texts = iter", "    return\n    document = docx.Document(str(path))\n    texts = iter"),
    ("section comparison removed (AC04)",
     "    if missing:\n        raise ReportError(f\"the Word document is missing",
     "    if False:\n        raise ReportError(f\"the Word document is missing"),
    ("image comparison removed (AC04)",
     "    if found != expected:\n", "    if False:\n"),
    (".dotx content-type fix removed (AC06)",
     "    if TEMPLATE_TYPE in types:\n", "    if False:\n"),
    ("cover dropped: body always cleared (AC06)",
     "        if not cover:\n            _clear_body(document)\n", "        _clear_body(document)\n"),
    ("macro check removed (AC07)",
     '    if b"macroEnabled" in types or any(', '    if False and any('),
    ("macro extensions accepted (AC07)",
     "    if suffix in MACRO_EXTENSIONS:\n", "    if False:\n"),
    ("review P1-1: outside-content check removed (AC07)",
     "    active = active_content(parts)\n", "    active = []\n"),
    ("review P1-1: external relationships allowed (AC07)",
     '                if relationship.get("TargetMode") == "External" and kind != "hyperlink":\n',
     "                if False:\n"),
    ("review P1-1: field check removed (AC07)",
     '        elif name.startswith("word/") and name.endswith(".xml"):\n', "        elif False:\n"),
    ("review P1-1: fields not joined across runs (AC07)",
     'b"".join(FIELD_TEXT.findall(data))', 'b" ".join(FIELD_TEXT.findall(data))'),
    ("review P3-4: stored template not checked again at build (AC07)",
     "        document = docx.Document(io.BytesIO(template_bytes(template)))\n",
     "        document = docx.Document(io.BytesIO(Path(template).read_bytes()))\n"),
    ("review P2-1: mention in a heading not embedded (AC02)",
     "            _heading(document, mention(payload[1]), payload[0])\n",
     "            _heading(document, payload[1], payload[0])\n"),
    ("review P2-2: byte-order mark not removed (AC04)",
     'text = summary.read_text(encoding="utf-8-sig")', 'text = summary.read_text(encoding="utf-8")'),
    ("review P2-2: unread # lines not refused (AC04)",
     "    if unread:\n", "    if False:\n"),
    ("review P3-1: no word boundary before frame_ (AC03)",
     'FRAME_LIKE = re.compile(r"\\bframes?_"', 'FRAME_LIKE = re.compile(r"frames?_"'),
    ("review P3-3: unreadable frame not named (AC03)",
     "            except (UnrecognizedImageError, OSError) as error:\n", "            except KeyError as error:\n"),
    ("review P3-4: report open in Word not named (AC01)",
     '"; if it is open in Word, close it and try again" if isinstance', '"" if isinstance'),
]


def summary_line(stderr):
    return [line for line in stderr.splitlines() if line.startswith(("FAILED", "OK"))][-1]


def main(source, work):
    source, work = Path(source), Path(work)
    shutil.copytree(source, work, ignore=shutil.ignore_patterns(".git", "__pycache__"))
    target = work / "meetingtool/report/document.py"
    original = target.read_text(encoding="utf-8")
    print("mutation run for 01M3HZZEGY9DVGN05MQC2QEGBS: each mutation is applied alone to a copy of the")
    print("working tree, `python -m unittest tests.test_report` is run, and the mutation must make it fail")
    detected_all = True
    try:
        for label, old, new in MUTATIONS:
            if original.count(old) != 1:
                raise SystemExit(f"mutation {label!r} does not apply exactly once")
            target.write_text(original.replace(old, new), encoding="utf-8")
            run = subprocess.run([sys.executable, "-m", "unittest", "tests.test_report"], cwd=work,
                                 capture_output=True, text=True)
            detected = run.returncode != 0
            detected_all &= detected
            print(f"- {label}: exit {run.returncode}, {summary_line(run.stderr)} -> "
                  f"{'DETECTED' if detected else 'NOT DETECTED'}")
        target.write_text(original, encoding="utf-8")
        run = subprocess.run([sys.executable, "-m", "unittest", "tests.test_report"], cwd=work,
                             capture_output=True, text=True)
        print(f"- unmutated: exit {run.returncode}, {summary_line(run.stderr)}")
    finally:
        shutil.rmtree(work)
    print("all mutations detected" if detected_all and run.returncode == 0 else "A MUTATION WAS NOT DETECTED")
    return 0 if detected_all and run.returncode == 0 else 1


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:3]))
