"""Mutation run for 01M47ABNKZF02YZ94YKXMQCPQ1 (WI22, WI22-AC05): each mutation
undoes one part of what WI22 added, in a copy of the working tree, and runs the
tests that guard it. Every mutation must make them fail. None needs INGOL's
kits: the tests are the ones the CI runs.

    python docs/evidence/01M47ABNKZF02YZ94YKXMQCPQ1/mutations.py <repository> <a folder outside it, which must not exist yet> [label part]

With a label part, only the mutations whose label holds it are run. The
repository must be a clean checkout: the script prints its commit, and the
output of the recorded run is mutations.txt next to this file.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

DOCUMENT = "meetingtool/report/document.py"
TESTS = ["tests.test_d1_r02_plantilla", "tests.test_template_filter"]

# (label, [(file, old, new)], note on what is expected to catch it)
MUTATIONS = [
    ("the namespace ignored: instructions looked for by the prefix w: in the raw bytes, as before WI22",
     [(DOCUMENT, '''        for field in field_instructions(root):
''', '''        codes = [b" ".join(re.findall(rb'w:instr="([^"]*)"', data)),
                 b"".join(re.findall(rb"<w:instrText[^>]*>([^<]*)</w:instrText>", data))]
        for field in [_field(text, text, False) for text in (code.decode("utf-8", "replace") for code in codes)]:
''')]),
    ("the decoding skipped: instructions taken from the raw bytes of an element with any prefix, not decoded",
     [(DOCUMENT, '''        for field in field_instructions(root):
''', '''        codes = [b" ".join(re.findall(rb"instr=.([^<>]*?)\\s*/?>", data)),
                 b"".join(re.findall(rb"<(?:\\w+:)?instrText[^>]*>([^<]*)</(?:\\w+:)?instrText>", data))]
        for field in [_field(text, text, False) for text in (code.decode("utf-8", "replace") for code in codes)]:
''')]),
    ("the case kept: a field's name matched only in upper case",
     [(DOCUMENT, '''RD)\\b",
                           re.IGNORECASE)''', '''RD)\\b",
                           0)'''),
      (DOCUMENT, '''word = word.group().upper() if word else ""''', '''word = word.group() if word else ""''')]),
    ("the simple fields (fldSimple) not read",
     [(DOCUMENT, '''        if kind == "fldSimple":
''', '''        if False:
''')]),
    ("the complex fields (instrText) not read",
     [(DOCUMENT, '''        elif kind in ("instrText", "delInstrText"):''', '''        elif False:''')]),
    ("a deleted instruction (delInstrText) not read",
     [(DOCUMENT, '''        elif kind in ("instrText", "delInstrText"):''', '''        elif kind in ("instrText",):''')]),
    ("the pieces of every field run together, not each field on its own",
     [(DOCUMENT, '''            (loose if top is None or top["separated"] else top["pieces"]).append(''', '''            loose.append(''')]),
    ("the headers and footers skipped",
     [(DOCUMENT, '''        if not _is_xml(name, types):
            continue
''', '''        if not _is_xml(name, types) or name.startswith(("word/header", "word/footer")):
            continue
''')]),
    ("the footnotes skipped",
     [(DOCUMENT, '''        if not _is_xml(name, types):
            continue
''', '''        if not _is_xml(name, types) or name.startswith("word/footnotes"):
            continue
''')]),
    ("only the body read",
     [(DOCUMENT, '''        if not _is_xml(name, types):
            continue
''', '''        if not _is_xml(name, types) or name != "word/document.xml":
            continue
''')]),
    ("a part Word reads by its content type, not by its name, not read",
     [(DOCUMENT, '''    return content_type.lower().endswith("xml")''', '''    return False''')]),
    ("the Strict namespace not read",
     [(DOCUMENT, '''WORD_NAMESPACES = frozenset({"http://schemas.openxmlformats.org/wordprocessingml/2006/main",
                             "http://purl.oclc.org/ooxml/wordprocessingml/main"})''',
       '''WORD_NAMESPACES = frozenset({"http://schemas.openxmlformats.org/wordprocessingml/2006/main"})''')]),
    ("the report not checked again before it is delivered",
     [(DOCUMENT, '''    check_active_content(path)
    document = docx.Document(str(path))''', '''    document = docx.Document(str(path))''')]),
    ("the content types checked as bytes again (macroEnabled, as written)",
     [(DOCUMENT, '''    return (any(Path(name).name.lower().startswith("vbaproject") for name in parts)
            or any(macro in content_type.lower() for _, content_type in _content_types(parts)
                   for macro in MACRO_TYPES))''',
       '''    return (any(Path(name).name.lower().startswith("vbaproject") for name in parts)
            or b"macroEnabled" in parts.get("[Content_Types].xml", b""))''')]),
    ("a part that is not XML let through without a word",
     [(DOCUMENT, '''            found.append(texts.Message("report.active.unreadable", part=name, detail=texts.External(str(error))))
            continue''', '''            continue''')]),
    ("the relationships compared in the case they are written (type and mode)",
     [(DOCUMENT, '''relationship.get("TargetMode", "").lower() == "external" and kind.lower() != "hyperlink"''',
       '''relationship.get("TargetMode", "") == "External" and kind != "hyperlink"'''),
      (DOCUMENT, '''elif kind.lower() in _ACTIVE_RELATIONSHIPS:''', '''elif kind in ACTIVE_RELATIONSHIPS:''')]),
    # The review of 6daabab: the name of a field is written out whole in the file; DATABASE and RD; the schemes.
    ("the name rule off: a refused name looked for in all the text of a field, as before the review of 6daabab",
     [(DOCUMENT, '''            if ACTIVE_FIELDS.fullmatch(word):
                names.add(word)
''', '''            names.update(match.upper() for match in ACTIVE_FIELDS.findall(field.text))
            if False:
                names.add(word)
''')]),
    ("a field with no name written out in the file let through",
     [(DOCUMENT, '''            unnamed = unnamed or field.unnamed
''', '''            unnamed = False
''')]),
    ("DATABASE and RD taken off the list of refused fields",
     [(DOCUMENT, '''LINK|DATABASE|RD)\\b",''', '''LINK)\\b",''')]),
    ("the schemes of a hyperlink relationship not checked",
     [(DOCUMENT, '''                elif kind.lower() == "hyperlink" and not HYPERLINK_ALLOWED.match(target):''',
       '''                elif False:''')]),
    ("the scheme of a HYPERLINK field's address not checked",
     [(DOCUMENT, '''                elif destination is not None and not HYPERLINK_ALLOWED.match(destination):''',
       '''                elif False:''')]),
    ("a HYPERLINK whose address another field builds let through",
     [(DOCUMENT, '''                if destination is None and field.nested and not anchor:''', '''                if False:''')]),
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
    print("mutation run for 01M47ABNKZF02YZ94YKXMQCPQ1: each mutation is applied alone to a copy of the working tree;")
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
