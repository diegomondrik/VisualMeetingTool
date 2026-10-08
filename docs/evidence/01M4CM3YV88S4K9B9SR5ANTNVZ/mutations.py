"""Mutation run for 01M4CM3YV88S4K9B9SR5ANTNVZ (WI30, WI30-AC03): each mutation undoes or bends one part of how one
meeting, or one file of it, is looked up by its own identifier, in a copy of the working tree, and runs the tests that
guard it. Every mutation must make them fail. None needs INGOL's kits: the tests are the ones the CI runs.

    python docs/evidence/01M4CM3YV88S4K9B9SR5ANTNVZ/mutations.py <repository> <a folder outside it, which must not exist yet> [label part]

With a label part, only the mutations whose label holds it are run. The
repository must be a clean checkout: the script prints its commit, and the
output of the recorded run is mutations.txt next to this file. Modelled on
docs/evidence/01M4CB9FV6XGEYENDJYAEQZWQX/mutations.py (WI27).
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

LIBRARY = "meetingtool/app/library.py"
STORE = "meetingtool/projects/store.py"
TESTS = ["tests.test_library_reads"]

# (label, [(file, old, new)]); each `old` has to be found exactly once.
MUTATIONS = [
    ("meeting_file back on the whole list: it finds the meeting among every meeting of the project, reading each one's result",
     [(LIBRARY, """    record = meeting_record(data_dir, project_id, meeting_id)
    return file_path(meeting_folder(data_dir, project_id, record), name)
""", """    entry = next((e for e in meetings(data_dir, project_id) if e["record"]["id"] == meeting_id), None)
    if entry is None:
        raise NotFound(meeting_id)
    return file_path(meeting_folder(data_dir, project_id, entry["record"]), name)
""")]),
    ("the meeting page loading every result: meeting() builds the whole list and picks the meeting from it",
     [(LIBRARY, """    record = meeting_record(data_dir, project_id, meeting_id)
    return {"record": record, "result": result(meeting_folder(data_dir, project_id, record))}
""", """    for entry in meetings(data_dir, project_id):
        if entry["record"]["id"] == meeting_id:
            return entry
    raise NotFound(meeting_id)
""")]),
    ("the loose file back on the list of loose results: loose_file looks the name up among every loose result",
     [(LIBRARY, """    return file_path(_loose_folder(data_dir, folder_name), name)""",
       """    if folder_name not in [entry["name"] for entry in loose(data_dir)]:
        raise NotFound(folder_name)
    return file_path(Path(data_dir) / folder_name, name)""")]),
    ("the loose page back on the list of loose results: loose_result picks the name from the whole list",
     [(LIBRARY, """    return {"name": name, "result": result(_loose_folder(data_dir, name))}
""", """    for entry in loose(data_dir):
        if entry["name"] == name:
            return entry
    raise NotFound(name)
""")]),
    ("the meeting identifier not checked as a slug: it is used as it comes to build the path of the record",
     [(STORE, """    if not isinstance(meeting_id, str) or meeting_id != slugify(meeting_id, fallback=""):
        return None
""", """    if not isinstance(meeting_id, str):
        return None
""")]),
    ("the loose name not checked as a slug: it is used as it comes to build the path of the folder",
     [(LIBRARY, """    if not is_slug(name) or not _is_loose(Path(data_dir) / name):""",
       """    if not _is_loose(Path(data_dir) / name):""")]),
    ("the record's own id not compared with the folder it was read from: any folder's record answers to its name",
     [(STORE, """    return record if record["id"] == meeting_id else None
""", """    return record
""")]),
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
    print("mutation run for 01M4CM3YV88S4K9B9SR5ANTNVZ: each mutation is applied alone to a copy of the working tree;")
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
