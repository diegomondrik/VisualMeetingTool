"""Mutation run for 01M3T40A8C7JPW6PPP7N5EVVQE (WI17): each mutation bends
one part of the language of the application, of the list of messages or of
the company's name and logo, in a copy of the working tree, runs the tests
that guard it, and must make them fail.

    python docs/evidence/01M3T40A8C7JPW6PPP7N5EVVQE/mutations.py <repository> <empty folder outside it>

The output of the recorded run is mutations.txt next to this file.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

PAGES = "meetingtool/app/pages.py"
SCRIPT = "meetingtool/app/static/app.js"
JOBS = "meetingtool/app/jobs.py"
COMPANY = "meetingtool/app/company.py"
TEXTS = "meetingtool/texts/__init__.py"
ES = "meetingtool/texts/es.py"
EN = "meetingtool/texts/en.py"
GEMINI = "meetingtool/reading/gemini.py"
FRAMES = "meetingtool/frames/extract.py"
TESTS = ["tests.test_texts", "tests.test_app.CompanyTest", "tests.test_qa", "tests.test_summary"]
MUTATIONS = [
    ("a text written in a page instead of the list (AC03)", PAGES,
     "<h2>{view.t('app.project.meetings')}</h2>", "<h2>Reuniones</h2>"),
    ("a text written in the page's script instead of the list (AC03)", SCRIPT,
     'say(form, text("js.wait"));', 'say(form, "Un momento…");'),
    ("the language chosen not kept (AC03)", COMPANY,
     '    settings["language"] = code\n    _write(data_dir, settings)\n', '    settings["language"] = code\n'),
    ("an English text left in the Spanish list (AC03, AC04)", ES,
     '"app.cost.title": "Lo que costó",', '"app.cost.title": "What it cost",'),
    ("a Spanish entry without one of its data (AC04)", ES,
     '"{shown} imágenes en el informe, de {total} que quedaron del video."',
     '"{shown} imágenes en el informe."'),
    ("an entry missing in Spanish (AC04)", ES,
     '    "app.key.none": "No hay una clave guardada: sin ella no se puede procesar.",\n', ""),
    ("a stage's error said in English whatever the language (AC05)", JOBS,
     "        error, detail = texts.said(self.error, language)\n",
     '        error, detail = texts.said(self.error, "en")\n'),
    ("a stage's name said in Spanish whatever the language (AC05)", JOBS,
     "    return texts.Message(STAGE_KEYS[name]).text(language) if name in STAGE_KEYS else \"\"\n",
     "    return texts.Message(STAGE_KEYS[name]).text(\"es\") if name in STAGE_KEYS else \"\"\n"),
    ("an error raised with text written in the code (AC06)", GEMINI,
     '        raise ReadingError("gemini.bad_key")\n',
     '        raise ReadingError("the saved key has characters a Gemini key never has; save it again")\n'),
    ("an error raised without the data its entry names (AC06)", FRAMES,
     'raise FramesError("frames.not_local", path=str(video_path))', 'raise FramesError("frames.not_local")'),
    ("what comes from outside said inside the application's sentence (AC07)", TEXTS,
     "        if app and outside:\n", "        if False and outside:\n"),
    ("a detail inside a message inside another lost (AC07)", TEXTS,
     "        text, found = value.render(language, app)\n        details.extend(found)\n",
     "        text, found = value.render(language, app)\n"),
    ("an unexpected failure said without its text (AC07)", JOBS,
     '"app.unexpected", detail=texts.External(str(error) or error.__class__.__name__))',
     '"app.unexpected", detail=texts.External(""))'),
    ("the company's name placed as markup (AC02)", PAGES,
     "company += f'<span class=\"company\">{e(view.company_name)}</span>'",
     "company += f'<span class=\"company\">{view.company_name}</span>'"),
    ("an SVG under another name taken for a picture (AC02)", COMPANY,
     '    if suffix == ".svg" or _looks_like_svg(data):\n', '    if suffix == ".svg":\n'),
    ("the logo not decoded: only its name checked (AC02)", COMPANY,
     '    suffix = Path(name).suffix.lower()\n    if suffix == ".svg"',
     '    return LOGO_NAMES["PNG"], data\n    suffix = Path(name).suffix.lower()\n    if suffix == ".svg"'),
    ("a logo of more than 1 MB accepted (AC02)", COMPANY,
     "    if len(data) > LOGO_LIMIT:\n", "    if False:\n"),
    ("the logo kept as it was sent, not written again (AC02)", COMPANY,
     "    partial.write_bytes(clean)\n", "    partial.write_bytes(data)\n"),
    ("the logo missing from the screens (AC01)", PAGES, "    if view.has_logo:\n", "    if False:\n"),
    ("the company's name missing from the tab's name (AC01)", PAGES,
     "    tab = \" · \".join(part for part in (title, view.company_name, BRAND) if part)\n",
     "    tab = \" · \".join(part for part in (title, BRAND) if part)\n"),
    ("a terminal message changed (AC09)", EN,
     '"qa.stopped": "{error}{before} [stopped at {stage}', '"qa.stopped": "{error}{before} [halted at {stage}'),
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
    print("mutation run for 01M3T40A8C7JPW6PPP7N5EVVQE: each mutation is applied alone to a copy of the")
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
