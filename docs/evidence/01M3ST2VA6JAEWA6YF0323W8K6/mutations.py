"""Mutation run for 01M3ST2VA6JAEWA6YF0323W8K6 (WI16): each mutation removes
or bends one part of the company's template handling (meetingtool/report/*,
and the settings of meetingtool/app/server.py), in a copy of the working
tree, runs `python -m unittest tests.test_report tests.test_app`, and must
make it fail.

    python docs/evidence/01M3ST2VA6JAEWA6YF0323W8K6/mutations.py <repository> <empty folder outside it>

The output of the recorded run is mutations.txt next to this file.
"""

import os
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
     "    if layout.start is None:\n        return None\n", "    return None\n"),
    ("a table of contents inside a content control not found (AC04)", LAYOUT,
     "    tocs = [toc for toc in tocs if id(_top(toc[0], body)) in kept_ids]\n",
     "    tocs = [toc for toc in tocs if toc[0].getparent() is body]\n"),
    ("the table of contents left as Word saved it (AC05)", DOCUMENT,
     "                layout.fill_toc(document, toc, placed, bookmarks)\n", "                pass\n"),
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
    # Added after the independent review of d0cce57.
    ("the report's start counted before the tables of contents are rewritten (review P1-1)", DOCUMENT,
     "    contents = []\n    if found is not None and found.tocs:\n",
     "    start = layout.body_children(document).index(first._p)\n    contents = []\n"
     "    if found is not None and found.tocs:\n"),
    ("the tables of contents checked against what was written in them (review P2-2)", DOCUMENT,
     "            for toc in found.tocs:\n"
     "                layout.fill_toc(document, toc, placed, bookmarks)\n"
     "        except layout.LayoutError as error:\n"
     '            raise ReportError(f"the template {Path(template).name} cannot be used: {error}") from None\n'
     "        # What each table of contents must list, from the summary's headings\n"
     "        # and the field's levels, not from what was written in it.\n"
     "        depth = [max(1, min(len(HEADING.match(line).group(1)) - 1, 3)) for line in text.splitlines()\n"
     "                 if HEADING.match(line)]\n"
     "        for _, _, instruction in found.tocs:\n"
     "            low, high = layout.levels(instruction)\n"
     "            contents.append([heading for level, heading in zip(depth, expected) if low <= level <= high])\n",
     "            for toc in found.tocs:\n"
     "                contents.append(layout.fill_toc(document, toc, placed, bookmarks))\n"
     "        except layout.LayoutError as error:\n"
     '            raise ReportError(f"the template {Path(template).name} cannot be used: {error}") from None\n'),
    ("a field left in a header or footer not looked for (review P3)", LAYOUT,
     "    elements += [p for part in header_footer_parts(document) for p in paragraphs([part])]\n", ""),
    ("the bookmarks numbered from 0, over the template's own (review P3)", LAYOUT,
     "    next_id = max(_bookmark_ids(document), default=0) + 1\n", "    next_id = 0\n"),
    ("the cover's own section dropped with the model (review P2-1)", LAYOUT,
     "        if section is not None and carried is None and not ended:\n", "        if False:\n"),
    ("the section break kept even when what is kept already ends one (re-verification P2-A)", LAYOUT,
     "        if section is not None and carried is None and not ended:\n",
     "        if section is not None and carried is None:\n"),
    ("a page break added after a cover that ends on a new page (re-verification P2-B)", DOCUMENT,
     "    if cover and not layout.ends_on_a_new_page(document):\n", "    if cover:\n"),
    ("a continuous section break taken for a new page (re-verification P3)", LAYOUT,
     '    return kind is None or kind.get(qn("w:val")) != "continuous"\n', "    return True\n"),
    ("the section ended by the table of contents' last line dropped (review P2-1)", LAYOUT,
     "    if section is not None:  # the table of contents ends a section", "    if False:  # the table of contents ends a section"),
    ("text before the field counted as an entry (review P2-3)", LAYOUT,
     'for link in element.iter(qn("w:hyperlink"))\n                                 for node in link.iter(qn("w:t"))',
     'for node in element.iter(qn("w:t"))'),
]


def summary_line(stderr):
    lines = [line for line in stderr.splitlines() if line.startswith(("FAILED", "OK"))]
    return lines[-1] if lines else "no summary line (the run stopped)"


def run_tests(work):
    try:
        return subprocess.run([sys.executable, "-m", "unittest", *TESTS], cwd=work, capture_output=True, text=True,
                              encoding="utf-8", errors="replace", env={**os.environ, "PYTHONIOENCODING": "utf-8"},
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
