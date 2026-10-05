"""Mutation run for 01M46KHBYCXMGM0K6N2RM651PE (WI20, WI20-AC08): each
mutation undoes one part of what WI20 added, in a copy of the working tree,
and runs the tests that guard it. Every mutation must make the tests without
INGOL's kits fail (tests.test_data_integrity, which the CI runs); with the
kits, the INGOL tests named for it are run too, and what they say is
recorded, caught or not.

    python docs/evidence/01M46KHBYCXMGM0K6N2RM651PE/mutations.py <repository> <empty folder outside it> [--kits <kits python folder>] [label part]

With a label part, only the mutations whose label holds it are run. The
output of the recorded run is mutations.txt next to this file.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

DISK = "meetingtool/disk.py"
STORE = "meetingtool/projects/store.py"
GEMINI = "meetingtool/reading/gemini.py"
JOBS = "meetingtool/app/jobs.py"
COMPANY = "meetingtool/app/company.py"
SERVER = "meetingtool/app/server.py"
FREE = ["tests.test_data_integrity"]
AR = "tests.test_d1_hallazgos_arquitecto."
SWEEP = "tests.test_d1_barrido."
CUTS = "tests.test_d1_wi20_fallas"

TRY_LOCK = "def _try_lock(handle):\n    handle.seek(0)\n"
UNLOCK = "def _unlock(handle):\n    handle.seek(0)\n"
MEETING_ID = '''        meeting_id, counter = base_id, 2
        while True:
            try:
                (meetings / meeting_id).mkdir(parents=True)
                break
            except FileExistsError:
                if (meetings / meeting_id).is_dir() and not (meetings / meeting_id / "meeting.json").exists():
                    break
            meeting_id, counter = f"{base_id}-{counter}", counter + 1
'''
DISCARD_CHECKS = '''    if not all(isinstance(value, str) and library.is_slug(value) for value in (project_id, run)):
        raise library.NotFound(str(run))
    if run not in {kept["run"] for kept in kept_runs(data_dir, project_id)}:
        raise library.NotFound(run)
'''

# (label, [(file, old, new)], INGOL tests to run with the kits)
MUTATIONS = [
    ("a file written in place, not to a temporary file (AC02)",
     [(DISK, '    temporary = path.with_name(f".{path.name}.{secrets.token_hex(6)}.partial")\n',
       "    temporary = path\n")],
     [AR + "AR02EscrituraNoAtomica", CUTS]),
    ("no lock at all (AC03)",
     [(DISK, TRY_LOCK, "def _try_lock(handle):\n    return\n"), (DISK, UNLOCK, "def _unlock(handle):\n    return\n")],
     [AR + "AR05AltasSimultaneas", AR + "AR10AjustesSimultaneos", SWEEP + "ProyectosConElMismoNombre"]),
    ("a lock held in memory, inside one process only (AC04)",
     [(DISK, "_held = threading.local()\n", "_held = threading.local()\n_MEMORY = threading.Lock()\n"),
      (DISK, TRY_LOCK, "def _try_lock(handle):\n    if not _MEMORY.acquire(blocking=False):\n"
                       "        raise OSError('busy')\n    return\n"),
      (DISK, UNLOCK, "def _unlock(handle):\n    _MEMORY.release()\n    return\n")],
     [AR + "AR05AltasSimultaneas"]),
    ("a meeting's identifier chosen by looking at which exist (AC03)",
     [(STORE, MEETING_ID, '''        meeting_id, counter = base_id, 2
        while (meetings / meeting_id / "meeting.json").exists():
            meeting_id, counter = f"{base_id}-{counter}", counter + 1
        (meetings / meeting_id).mkdir(parents=True, exist_ok=True)
''')],
     [AR + "AR05AltasSimultaneas"]),
    ("a project's folder taken even if it exists (AC03)",
     [(STORE, "            folder.mkdir(parents=True)\n", "            folder.mkdir(parents=True, exist_ok=True)\n")],
     [SWEEP + "ProyectosConElMismoNombre"]),
    ("an unreadable record skipped instead of named (AC05)",
     [(STORE, '        raise ProjectError("projects.unreadable", file=str(path), detail=texts.External(str(error))) '
              'from None\n', "        return None\n"),
      (STORE, '    return sorted(records, key=lambda m: (m["date"], m["added_utc"], m["id"]))\n',
       '    records = [record for record in records if record]\n'
       '    return sorted(records, key=lambda m: (m["date"], m["added_utc"], m["id"]))\n')],
     [AR + "AR01TrabajoColgado"]),
    ("a meeting kept although the knowledge could not take it (AC02, AC05)",
     [(STORE, "            shutil.rmtree(meetings / meeting_id, ignore_errors=True)\n            raise\n",
       "            raise\n")],
     [AR + "AR01TrabajoColgado"]),
    ("a kept answer's fingerprint that ignores what is sent (AC06)",
     [(GEMINI, '    sent = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))\n',
       '    sent = ""\n')],
     [SWEEP + "LecturaEnTandas"]),
    ("kept answers never used (AC06)",
     [(GEMINI, "        found = _kept_answer(kept, check)\n", "        found = None\n")],
     [SWEEP + "LecturaEnTandas", AR + "AR03LoPagadoSeTira"]),
    ("a failed run's folder removed although it holds what was paid (AC06, AC07)",
     [(JOBS, '    return any((folder / gemini.KEPT_DIR).glob("*.json")) or any((folder / qa.PARTS_DIR).glob('
             '"part-*.json"))\n', "    return False\n")],
     [AR + "AR03LoPagadoSeTira", CUTS]),
    ("a kept run not continued by the same meeting (AC06)",
     [(JOBS, "            work = _kept_for(project_dir, fingerprint)\n", "            work = None\n")],
     [AR + "AR03LoPagadoSeTira"]),
    ("a discard that removes any folder named (AC07)",
     [(JOBS, DISCARD_CHECKS, "")], []),
    ("a discard while a meeting is being processed (AC07)",
     [(SERVER, "            if app.runner.running() is not None:  # it may be continuing in that very folder\n",
       "            if False:\n")], []),
    ("a save cut half way left as a result no meeting names (AC02, AC07)",
     [(JOBS, "        cut = [run for run in results.iterdir() if (run / KEPT_RECORD).is_file()]\n",
       "        cut = []\n")],
     [CUTS]),
    ("the settings read, changed and written outside the lock (AC03)",
     [(COMPANY, "    with store.data_lock(folder):\n        settings = _read(folder)\n",
       "    if True:\n        settings = _read(folder)\n")],
     [AR + "AR10AjustesSimultaneos"]),
    ("a knowledge file left behind not rewritten at start (AC02)",
     [(JOBS, "                store.rebuild_knowledge(data_dir, project.parent.name)\n", "                pass\n")],
     []),
]


def summary_line(stderr):
    lines = [line for line in stderr.strip().splitlines() if line.startswith(("Ran ", "OK", "FAILED"))]
    return " ".join(lines[-2:]) if lines else "(no result line)"


def run_tests(work, names, kits=None):
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    if kits:
        env["PYTHONPATH"] = str(kits)
    try:
        return subprocess.run([sys.executable, "-m", "unittest", *names], cwd=work, capture_output=True, text=True,
                              encoding="utf-8", errors="replace", env=env, timeout=3600)
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess([], 124, "", "FAILED (timeout)")


def main(argv):
    source, work = Path(argv[0]), Path(argv[1])
    rest = argv[2:]
    kits = None
    if rest[:1] == ["--kits"]:
        kits, rest = Path(rest[1]), rest[2:]
    only = rest[0] if rest else ""
    shutil.copytree(source, work, ignore=shutil.ignore_patterns(".git", "__pycache__"))
    names = sorted({name for _, edits, _ in MUTATIONS for name, _, _ in edits})
    originals = {name: (work / name).read_text(encoding="utf-8") for name in names}
    print("mutation run for 01M46KHBYCXMGM0K6N2RM651PE: each mutation is applied alone to a copy of the working")
    print(f"tree; `python -m unittest {' '.join(FREE)}` (no kits, what the CI runs) must fail" +
          (f"; with the kits ({kits}), the INGOL tests named for it are run and recorded" if kits else ""))
    detected_all = True
    try:
        for label, edits, kit_tests in MUTATIONS:
            if only not in label:
                continue
            changed = dict(originals)
            for name, old, new in edits:
                if changed[name].count(old) != 1:
                    raise SystemExit(f"mutation {label!r} does not apply exactly once in {name}")
                changed[name] = changed[name].replace(old, new)
            for name in names:
                (work / name).write_text(changed[name], encoding="utf-8", newline="\n")
            free = run_tests(work, FREE)
            detected = free.returncode != 0
            detected_all &= detected
            line = (f"- {label}: without the kits exit {free.returncode}, {summary_line(free.stderr)} -> "
                    f"{'DETECTED' if detected else 'NOT DETECTED'}")
            if kits and kit_tests:
                kit = run_tests(work, kit_tests, kits)
                line += (f"; with the kits ({', '.join(t.rsplit('.', 1)[-1] for t in kit_tests)}) exit "
                         f"{kit.returncode}, {summary_line(kit.stderr)} -> "
                         f"{'caught' if kit.returncode != 0 else 'not caught'}")
            print(line, flush=True)
            for name in names:
                (work / name).write_text(originals[name], encoding="utf-8", newline="\n")
        free = run_tests(work, FREE)
        print(f"- unmutated, without the kits: exit {free.returncode}, {summary_line(free.stderr)}")
        unmutated_ok = free.returncode == 0
        if kits:
            kit = run_tests(work, sorted({t for _, _, tests in MUTATIONS for t in tests}), kits)
            print(f"- unmutated, with the kits: exit {kit.returncode}, {summary_line(kit.stderr)}")
            unmutated_ok &= kit.returncode == 0
    finally:
        shutil.rmtree(work, ignore_errors=True)
    ok = detected_all and unmutated_ok
    print("all mutations detected without the kits" if ok else "A MUTATION WAS NOT DETECTED, OR THE UNMUTATED RUN FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
