"""Mutation run for 01M3QPZT9YPTVTYSED4GF7YDD3 (WI15): each mutation removes
or bends one guard of the application (meetingtool/app/*, and the shared
spending meter of meetingtool/reading/gemini.py), in a copy of the working
tree, runs `python -m unittest tests.test_app`, and must make it fail.

    python docs/evidence/01M3QPZT9YPTVTYSED4GF7YDD3/mutations.py <repository> <empty folder outside it>

Not mutated: listening on every address instead of 127.0.0.1, which on
Windows can make the firewall ask the user; tests.test_app checks the address
the server listens on and that no other address of the machine answers.

The output of the recorded run is mutations.txt next to this file.
"""

import shutil
import subprocess
import sys
from pathlib import Path

SERVER = "meetingtool/app/server.py"
JOBS = "meetingtool/app/jobs.py"
LIBRARY = "meetingtool/app/library.py"
PAGES = "meetingtool/app/pages.py"
GEMINI = "meetingtool/reading/gemini.py"
TESTS = ["tests.test_app"]
MUTATIONS = [
    ("a peer that is not this machine accepted (AC02)", SERVER,
     "        if not ipaddress.ip_address(peer).is_loopback:\n", "        if False:\n"),
    ("another Host accepted: a DNS rebinding (AC02)", SERVER,
     '    if headers.get("Host", "") not in app.hosts:\n', "    if False:\n"),
    ("another Origin accepted (AC02)", SERVER,
     "    if origin is not None and origin not in app.origins:\n", "    if False:\n"),
    ("Sec-Fetch-Site of another site accepted (AC02)", SERVER,
     '    if site is not None and site not in ("same-origin", "none"):\n', "    if False:\n"),
    ("a request without the session cookie accepted (AC02)", SERVER,
     "    if session is None or not hmac.compare_digest(session.value.encode(), app.token.encode()):\n",
     "    if False:\n"),
    ("a change without the X-MeetingTool header accepted (AC02)", SERVER,
     '        if headers.get("X-MeetingTool") != "1":\n', "        if False:\n"),
    ("a change that is not JSON accepted (AC02)", SERVER,
     '        if method == "POST" and headers.get("Content-Type", "")', '        if False and headers.get("Content-Type", "")'),
    ("the launch address sets the cookie without the token (AC02)", SERVER,
     "            if not hmac.compare_digest(token.encode(), app.token.encode()):\n", "            if False:\n"),
    ("the cookie sent with requests of other sites (no SameSite) (AC02)", SERVER,
     'Path=/; HttpOnly; SameSite=Strict"', 'Path=/; HttpOnly"'),
    ("the pages may be framed by another site (AC02)", SERVER,
     "form-action 'self'; frame-ancestors 'none'; base-uri 'none'", "form-action 'self'; base-uri 'none'"),
    ("what a summary says placed without escaping (AC01)", PAGES, "    escaped = e(text)\n",
     "    escaped = str(text)\n"),
    ("any file of a meeting's folder served (AC01)", LIBRARY,
     "    if folder is None or not (FRAME_NAME.fullmatch(name) or name == REPORT_NAME):\n",
     "    if folder is None:\n"),
    ("a meeting's folder followed wherever its record says (AC01)", LIBRARY,
     "    match = FOLDER.fullmatch(record.get(\"folder\", \"\") or \"\")\n    if not match:\n        return None\n",
     "    folder = Path(data_dir) / project_id / (record.get(\"folder\") or \"-\")\n"
     "    return folder if folder.is_dir() else None\n"),
    ("the meeting added by the summary at once, before the Word report (AC03)", JOBS,
     "counters=job.counters, add_meeting=record_later)", "counters=job.counters, add_meeting=None)"),
    ("the run's folder kept after a failure (AC03)", JOBS,
     "                shutil.rmtree(work, ignore_errors=True)\n                shutil.rmtree(final, ignore_errors=True)\n",
     "                pass\n"),
    ("the summary given a spending meter of its own (AC03)", JOBS,
     "counters=job.counters, add_meeting=record_later)", "counters=None, add_meeting=record_later)"),
    ("the reading given a spending meter of its own (AC03)", GEMINI,
     "    counters = new_counters() if counters is None else counters\n", "    counters = new_counters()\n"),
    ("two runs at a time (AC03)", JOBS,
     '            if any(job.state == "running" for job in self.jobs.values()):\n', "            if False:\n"),
    ("the summary started without a recording (AC03)", JOBS,
     '    if kind == "summary" and recording is None:\n', "    if False:\n"),
    ("the copy of the recording kept in the meeting (AC03)", JOBS,
     "                recording.unlink()  # the meeting keeps", "                pass  # the meeting keeps"),
    ("the meeting's record naming the transcript of the working folder (AC03)", JOBS,
     '            later["kwargs"]["transcript"] = str(final / transcript.name)\n', ""),
    ("the job said done or failed before its folder was cleaned (AC03)", JOBS,
     "        except Exception as error:  # every failure ends the job with its reason\n"
     "            job.error = str(error) or error.__class__.__name__\n",
     "        except Exception as error:  # every failure ends the job with its reason\n"
     "            job.error = str(error) or error.__class__.__name__\n            job.state = \"failed\"\n"
     "            time.sleep(0.5)\n"),
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
    print("mutation run for 01M3QPZT9YPTVTYSED4GF7YDD3: each mutation is applied alone to a copy of the")
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
