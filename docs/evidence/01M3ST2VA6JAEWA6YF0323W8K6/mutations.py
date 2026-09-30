"""Mutation run for 01M3ST2VA6JAEWA6YF0323W8K6 (WI16): each mutation removes
or bends one part of the company's template handling (meetingtool/report/*,
and the settings of meetingtool/app/server.py), in a copy of the working
tree, runs `python -m unittest tests.test_report tests.test_app`, and must
make it fail.

    python docs/evidence/01M3ST2VA6JAEWA6YF0323W8K6/mutations.py <repository> <empty folder outside it>

The output of the recorded run is mutations.txt next to this file.
"""

import shutil
import subprocess
import sys
from pathlib import Path

LAYOUT = "meetingtool/report/layout.py"
DOCUMENT = "meetingtool/report/document.py"
SERVER = "meetingtool/app/server.py"
TESTS = ["tests.test_report", "tests.test_app"]
MUTATIONS = [
    ("the header and footer fields not filled (AC01)", LAYOUT,
     "    for part in header_footer_parts(document):\n        for element in paragraphs([part]):\n"
     "            _fill_paragraph(element, values)\n", ""),
    ("a field filled only when it is within one run (AC02)", LAYOUT,
     "            if offset < match.end() and offset + length > match.start():\n",
     "            if offset <= match.start() and offset + length >= match.end():\n"),
    ("a known field left in the finished document delivered (AC03)", DOCUMENT,
     "    if left:\n", "    if False:\n"),
    ("an unknown field accepted (AC03)", LAYOUT, "    if unknown:\n", "    if False:\n"),
    ("the template's model kept in the report (AC04)", LAYOUT,
     "    if layout.start is None:\n        return\n", "    return\n"),
    ("a table of contents inside a content control not found (AC04)", LAYOUT,
     "    tocs = [toc for toc in tocs if id(_top(toc[0], body)) in kept_ids]\n",
     "    tocs = [toc for toc in tocs if toc[0].getparent() is body]\n"),
    ("the table of contents left as Word saved it (AC05)", DOCUMENT,
     "        contents = [layout.fill_toc(document, toc, placed, bookmarks) for toc in found.tocs]\n",
     "        contents = []\n"),
    ("the field's levels ignored (AC05)", LAYOUT,
     "zip(headings, bookmarks) if low <= level <= high]\n", "zip(headings, bookmarks)]\n"),
    ("an entry linking nowhere (AC05)", LAYOUT,
     '    link.set(qn("w:anchor"), bookmark)\n', '    link.set(qn("w:anchor"), "_Toc0")\n'),
    ("Word asked to update fields on opening (AC05)", DOCUMENT,
     "        layout.no_update_on_open(document)\n", ""),
    ("a field marked to update kept so (AC05)", LAYOUT,
     '        char.attrib.pop(qn("w:dirty"), None)\n', "        pass\n"),
    ("the completeness check reads the cover too, and its table of contents (AC06)", DOCUMENT,
     "for child in children[start:] if child.tag", "for child in children if child.tag"),
    ("the table of contents not checked (AC06)", DOCUMENT,
     "    if found_contents != [list(entries) for entries in contents]:\n", "    if False:\n"),
    ("the name the page gave not kept (AC07)", SERVER,
     "                app.set_template(target, app.data_dir, name=name)\n",
     "                app.set_template(target, app.data_dir)\n"),
]


def summary_line(stderr):
    lines = [line for line in stderr.splitlines() if line.startswith(("FAILED", "OK"))]
    return lines[-1] if lines else "no summary line (the run stopped)"


def run_tests(work):
    try:
        return subprocess.run([sys.executable, "-m", "unittest", *TESTS], cwd=work, capture_output=True, text=True,
                              timeout=900)
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess([], 124, "", "FAILED (timeout)")


def main(source, work):
    source, work = Path(source), Path(work)
    shutil.copytree(source, work, ignore=shutil.ignore_patterns(".git", "__pycache__"))
    names = sorted({name for _, name, _, _ in MUTATIONS})
    originals = {name: (work / name).read_text(encoding="utf-8") for name in names}
    print("mutation run for 01M3ST2VA6JAEWA6YF0323W8K6: each mutation is applied alone to a copy of the")
    print(f"working tree, `python -m unittest {' '.join(TESTS)}` is run, and the mutation must make it fail")
    detected_all = True
    try:
        for label, name, old, new in MUTATIONS:
            original = originals[name]
            if original.count(old) != 1:
                raise SystemExit(f"mutation {label!r} does not apply exactly once")
            (work / name).write_text(original.replace(old, new), encoding="utf-8", newline="\n")
            run = run_tests(work)
            (work / name).write_text(original, encoding="utf-8", newline="\n")
            detected = run.returncode != 0
            detected_all &= detected
            print(f"- {label}: exit {run.returncode}, {summary_line(run.stderr)} -> "
                  f"{'DETECTED' if detected else 'NOT DETECTED'}", flush=True)
        run = run_tests(work)
        print(f"- unmutated: exit {run.returncode}, {summary_line(run.stderr)}")
    finally:
        shutil.rmtree(work, ignore_errors=True)
    print("all mutations detected" if detected_all and run.returncode == 0 else "A MUTATION WAS NOT DETECTED")
    return 0 if detected_all and run.returncode == 0 else 1


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:3]))
