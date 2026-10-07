"""Mutation run for 01M48RAZZ5MGGHYTJNYR2VQP0Z (WI23, WI23-AC03): each mutation
undoes or bends one part of the list of allowed fields, in a copy of the working
tree, and runs the tests that guard it. Every mutation must make them fail. None
needs INGOL's kits: the tests are the ones the CI runs.

    python docs/evidence/01M48RAZZ5MGGHYTJNYR2VQP0Z/mutations.py <repository> <a folder outside it, which must not exist yet> [label part]

With a label part, only the mutations whose label holds it are run. The
repository must be a clean checkout: the script prints its commit, and the
output of the recorded run is mutations.txt next to this file. Modelled on
docs/evidence/01M47ABNKZF02YZ94YKXMQCPQ1/mutations.py (WI22).
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

DOCUMENT = "meetingtool/report/document.py"
TESTS = ["tests.test_allowed_fields", "tests.test_markup_compatibility", "tests.test_template_filter",
         "tests.test_d1_r02_plantilla"]

# (label, [(file, old, new)]); each `old` has to be found exactly once.
MUTATIONS = [
    ("a refused name added to the list: INCLUDETEXT, which WI22 refused",
     [(DOCUMENT, r'''"IF", "SEQ", "="})''', r'''"IF", "SEQ", "=", "INCLUDETEXT"})''')]),
    ("a refused name added to the list: ADDIN, which the owner chose to refuse",
     [(DOCUMENT, r'''"IF", "SEQ", "="})''', r'''"IF", "SEQ", "=", "ADDIN"})''')]),
    ("an allowed name taken off the list: the formula (=)",
     [(DOCUMENT, r'''"IF", "SEQ", "="})''', r'''"IF", "SEQ"})''')]),
    ("the list check switched off: no field is refused for its name",
     [(DOCUMENT, r'''            if word not in ALLOWED_FIELDS:''', r'''            if False:''')]),
    ("the list compared against the whole instruction, not the written-out name: refused only when no word of the "
     "instruction is on the list",
     [(DOCUMENT, r'''            if word not in ALLOWED_FIELDS:''',
       r'''            if not any(part.upper() in ALLOWED_FIELDS for part in re.findall(r"\w+|=", field.text)):''')]),
    ("the list compared against the whole instruction, not the written-out name: the whole text must be on the list",
     [(DOCUMENT, r'''            if word not in ALLOWED_FIELDS:''',
       r'''            if field.text.strip().upper() not in ALLOWED_FIELDS:''')]),
    ("the text that no field holds, and a field with nothing written, judged for the name they do not have",
     [(DOCUMENT, r'''            if not word:  # nothing written, or the text no field holds: there is no name to judge
                continue
''', "")]),
    ("a name that does not start with a word (a quote, a dash) judged as no name",
     [(DOCUMENT, r'''            word = word.group() if word else field.name.strip()''',
       r'''            word = word.group() if word else ""''')]),
    ("the case kept: a name matched only in upper case",
     [(DOCUMENT, r'''            word = word.upper() if word.isascii() else word''',
       r'''            word = word if word.isascii() else word''')]),
    ("the upper case of a name that is not ASCII (a long s for an S)",
     [(DOCUMENT, r'''            word = word.upper() if word.isascii() else word''', r'''            word = word.upper()''')]),
    ("a field inside another's instruction not judged: only the outermost of each is",
     [(DOCUMENT, r'''                fields.append(_closed(open_fields.pop()))''',
       r'''                closed = _closed(open_fields.pop())
                fields.extend([] if open_fields else [closed])''')]),
    # The independent review of 6e33e4c (P1): Markup Compatibility.
    ("the branches of an mc:AlternateContent read as one stream, as before the review (a Choice and a Fallback "
     "joined into one instruction)",
     [(DOCUMENT, r'''        if _is_branch(element) or _namespace(element) in names:''',
       r'''        if _namespace(element) in names:''')]),
    ("an element of an ignorable namespace read as one stream with the rest, as before the review",
     [(DOCUMENT, r'''        if _is_branch(element) or _namespace(element) in names:''',
       r'''        if _is_branch(element):''')]),
    ("the ignorable namespaces not read (mc:Ignorable names none)",
     [(DOCUMENT, r'''        names = ignorable[-1] | _named_namespaces(element, "Ignorable", scopes)[0] if element in scopes else ignorable[-1]''',
       r'''        names = ignorable[-1]''')]),
    ("the Markup Compatibility that leaves unknown what Word reads accepted",
     [(DOCUMENT, r'''        for key, what in compatibility_problems(root, scopes):''', r'''        for key, what in []:''')]),
    ("an mc:AlternateContent that is not formed as it is defined accepted",
     [(DOCUMENT, r'''            elif local == "AlternateContent":
                branches.update(id(child) for child in element)
                if "Choice" not in children''', r'''            elif local == "AlternateContent":
                branches.update(id(child) for child in element)
                if False and "Choice" not in children''')]),
    ("the prefixes that mc:Ignorable and mc:Requires name not checked against the declarations",
     [(DOCUMENT, r'''                problems.update(("report.active.compat_prefix", prefix) for prefix in lost)''', r'''                problems.update([])'''),
      (DOCUMENT, r'''                problems.update(("report.active.compat_prefix", prefix) for prefix in required if prefix not in scope)''',
       r'''                problems.update([])''')]),
    ("the report not checked again before it is delivered",
     [(DOCUMENT, r'''    check_active_content(path)
    document = docx.Document(str(path))''', r'''    document = docx.Document(str(path))''')]),
    ("the template not checked when it is set (only the report's last check stands)",
     [(DOCUMENT, r'''    active = active_content(parts)
    if active:
        raise ReportError("report.active"''', r'''    active = []
    if active:
        raise ReportError("report.active"''')]),
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
    print("mutation run for 01M48RAZZ5MGGHYTJNYR2VQP0Z: each mutation is applied alone to a copy of the working tree;")
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
