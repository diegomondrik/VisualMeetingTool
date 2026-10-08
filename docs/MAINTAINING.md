# Maintaining MeetingTool

For whoever keeps this program running. It is the map as the code is today;
why each thing is as it is stays in the work items under `.ingol/work-items/`
and their evidence under `docs/evidence/`. Every file, function and command
named between backticks here is checked to exist by
`docs/evidence/01M4CM3YV9HEAHSW5V5ER4V8W7/check_guide.py`; run it after
editing this file.

## 1. The flow, and where untrusted input enters

A meeting goes through four stages. Each is a function with a command of its
own, and the application runs the same functions in this order.

- Frames: `extract.extract_frames` selects frames of the recording and writes
  `frame_NNN_tHH-MM-SS.jpg` files (`python -m meetingtool.frames`).
- Reading: `gemini.read_frames` has Gemini say what each frame shows and
  writes `frames_read.md` (`python -m meetingtool.reading read`).
- Summary or register: `writer.write_summary` writes `summary.md`;
  `qa.write_register` writes `qa.json` and the register as `summary.md`
  (`python -m meetingtool.summary`, with `--format qa` for the register).
- Report: `document.build_report` builds `summary.docx` from `summary.md` and
  its frames, with no network (`python -m meetingtool.report build`).

`python -m meetingtool.projects` keeps projects and meetings
(`store.add_meeting`). `python -m meetingtool app` starts the application
(`server.serve`): a server on 127.0.0.1 whose `jobs.Runner` runs the stages
in a thread, one run at a time, under one spending ceiling for the whole run
(`jobs.DEFAULT_MAX_COST_USD`, shared through `gemini.new_counters`). Every
text the program says is an entry of `meetingtool/texts/<language>.py`.

What reaches the program from outside, and what looks at it first:

- Uploads (transcript, recording, template, logo): `server.Handler._put`
  checks the kind, the suffix and the size (`server.UPLOAD_SUFFIXES`,
  `server.UPLOAD_LIMITS`) and writes it under a name the server makes
  (`jobs.Uploads.new_path`); a run takes only a name of that shape
  (`jobs.Uploads.get`). A logo goes through `company.check_logo`: an SVG is
  refused, the image is decoded and written again without its metadata.
- The request to process: `jobs.check_request` (project, date, type, language,
  format, ceiling, a transcript with speakers for the register).
- Transcripts (`.docx` or `.txt`): `transcript.read_turns` decodes them
  (`transcript.names_no_one` tells a transcript with no speaker) and refuses
  with `transcript.TranscriptError`.
- Company templates: `document.template_bytes` refuses macros
  (`document.carries_macros`) and anything that loads or runs content from
  outside (`document.active_content`, `document.field_instructions`,
  `document.compatibility_problems`); the only fields allowed are
  `document.ALLOWED_FIELDS`. Each finished report is checked again by
  `document.check_active_content` and `document.check_report`.
- The recording: `extract.extract_frames` opens only a local file, turns what
  the decoder refuses into `extract.FramesError`, and writes only outside a git
  work tree (`extract.enclosing_git_work_tree`).
- Gemini's answers: every paid request goes through `gemini.call_checked`
  with the stage's check, which refuses a bad answer and allows one retry:
  `gemini.check_answer` (reading), `writer.check_summary` (headings, language,
  empty sections, and `writer.check_frames` for the frames it names) and
  `qa.check_register` (fragments, speakers, minutes, dates and figures against
  the transcript). The transcript and the frame readings are sent as material
  after `writer.MATERIAL`, not as instructions.
- HTTP requests to the application: `server.refusal` runs before any route (a
  loopback peer, the server's own Host and Origin, `Sec-Fetch-Site`, the
  session cookie, the `X-MeetingTool` header, a JSON body);
  `server.Handler._read_json` bounds the body (`server.JSON_LIMIT`).
  Addresses are built from identifiers checked by `library.is_slug`, and only
  a frame or the report is served (`library.file_path`).
- The data folder itself: `store.check_data_dir` refuses one inside a git work
  tree. Client files are kept out of the repository by `.gitignore` and
  `repository_guard.py`, which `tests/test_repository_guard.py` runs.

## 2. The data folder

Where it is: `store.default_data_dir` (the environment variable
`store.DATA_DIR_ENV`, else a folder named `store.DEFAULT_DATA_DIR_NAME` in the
user's home). Under it:

- `<data>/<project>/project.json`: the project's record.
- `<data>/<project>/knowledge.md`: written again from all the meetings
  (`store.rebuild_knowledge`) and read by the next summary.
- `<data>/<project>/meetings/<id>/meeting.json`: one meeting; its id is the
  date and the title as a slug, and its folder is made exclusively under the
  lock, which reserves the id (`store.add_meeting`). A meeting of the
  application names its results folder in `folder`.
- `<data>/<project>/results/<run>/`: what a finished run keeps (frames,
  transcript, readings, `summary.md`, `summary.docx`, `run.json`; not the
  recording).
- `<data>/<project>/processing/<run>/`: a run being worked on, or one that
  failed after paying. It holds `kept.json` (`jobs.KEPT_RECORD`: what was
  asked and what was paid), `paid-answers/` (`gemini.KEPT_DIR`) and, for the
  register, `qa-parts/` (`qa.PARTS_DIR`).
- `<data>/app-settings.json`, `<data>/company-logo.png` (or `.jpg`) and
  `<data>/report-template.docx`: the application's language, the company's
  name and logo, and its Word template.
- `<data>/.meetingtool-uploads`, `<data>/.meetingtool-write.lock` and
  `<data>/.meetingtool-app.lock`.

Two rules for any code that stores something. A file is written whole or not
at all: `disk.write_text` and `disk.write_bytes` write a hidden `.partial`
file, flush it and put it in place with `disk.replace`. Whatever reads,
changes and writes the folder holds its lock, `disk.locked` (reached through
`store.data_lock`), which holds between the application and the commands, is
dropped by the system when a process ends, and gives up with
`disk.LockTimeout` after `disk.LOCK_WAIT_SECONDS`. Only one application runs
per data folder (`server.DataFolderLock`). A record that cannot be read is
named in an error (`store.ProjectError`), never skipped.

How a cut run is recovered. The run works in `processing/<run>` and moves it
to `results/<run>` before adding the meeting (`jobs.Runner._run`). If it fails,
`jobs.Runner._settle_failure` removes the folder when nothing was paid and
keeps it when `jobs.holds_paid` finds a paid answer; `jobs.kept_runs` lists
those runs. Processing the same meeting again (same project, format and
transcript bytes: `jobs.request_fingerprint`) continues in that folder, and
`gemini.call_checked` takes a kept answer only for the exact same request.
A kept run goes when its retry succeeds or when the person discards it
(`jobs.discard_kept`, through `jobs.Runner.discard`, never during a run). When
the application starts, `jobs.clear_leftovers` runs before the server does: it
settles a save cut half way (`jobs._settle_cut_saves`), writes each knowledge
file again, removes the working folders that paid nothing and empties the
uploads.

## 3. Tests and builds

- The suite is the standard library's `python -m unittest discover -s tests -v`
  from the repository root. It needs no Gemini key and no network (Gemini is a
  fake on localhost, `test_reading.FakeGemini`).
- The CI is `.github/workflows/tests.yml`: every pull request to `main`, on
  Windows, with Python 3.12. It installs the libraries of `pyproject.toml`
  with `-c constraints.txt`, which pins them and what they bring at exact
  versions, and prints the installed ones (`python -m pip list`).
  `tests/test_pinned_versions.py` fails when a library has no pin, a pin is a
  range or is below the minimum of `pyproject.toml`. To change a version,
  change `constraints.txt` in one work item and read the CI log of its pull
  request. The minimums themselves are not tested (`WI31-P3-1`).
- The tests named `tests/test_d1_*.py` reproduce the external review of
  2026-10-02. Three of the six files (`test_d1_barrido`,
  `test_d1_hallazgos_arquitecto` and `test_d1_wi20_fallas`) use INGOL's test
  kits, which are not in this repository: without them those skip, so the CI
  does not run them. The other three need no kits and the CI runs them. With
  the kits:
  `PYTHONPATH=<home>/.claude/ingol-kits/python python -m unittest discover -s tests -p "test_d1_*"`.
  The run of the whole suite with the kits is committed as evidence.
- The register of known limitations is `docs/limitations/REGISTER.md`; each row
  has a reproduction in `docs/limitations/reproduce.py`, run with
  `python docs/limitations/reproduce.py <ID>`. The script fails when a state in
  the register is not what the reproduction shows, so a fixed limitation changes
  its row.
- The Windows installer is WI18's branch,
  work-item/01M3VRRZJ3XYC0ADJT8N733F03-windows-installer, not integrated into
  `main`. Its file packaging/requirements-build.txt (on that branch, so not checked here) freezes the build environment, and its
  build refuses other versions. `constraints.txt` holds the same versions for
  the six libraries of the program. When that branch is integrated, its build
  should take its pins from `constraints.txt`, so that one list says what the
  suite runs on and what the installer packs.

## 4. How a change is integrated

- A change is a work item. Its contract is `.ingol/work-items/<id>/contract.yaml`
  (the objective and the acceptance criteria), with a `plan.yaml` and the
  approvals under `.ingol/work-items/<id>/approvals`. The work is on a branch
  named `work-item/<id>-<short name>`.
- Its evidence is committed under `docs/evidence/<id>/`: `changed-tests.md`
  (every test that existed before and changed, and why), `mutations.py` with
  its `mutations.txt` (each mutation must make a test fail),
  `local-test-run.txt` (the whole suite in a fresh clone, with the kits) and
  `independent-review.md` (an independent review through INGOL's mailbox, with
  what was done about each finding).
- The pull request goes to `main`. Its description starts with the line
  `INGOL-Work-Item: <id>`. Two workflows judge it: the protected review
  `.github/workflows/ingol-bootstrap.yml`, which runs INGOL from a pinned
  version against the baseline and reads the candidate as data, so the change
  cannot alter its own judge, and `.github/workflows/tests.yml`. With both green
  the pull request is merged.
- A limitation found and not fixed goes to the register with a reproduction
  (section 3) in the same work item.

## 5. Adding a language

There are two languages to tell apart: the one the application speaks, and
the one a summary or a report is written in. A language may be added to either.

The application's language (every screen, notice and error):

- Write `meetingtool/texts/<language>.py` with `TEXTS`, the same keys as
  `texts/en.py` and the same `{data}` names; the parts in `[[ ]]` are where the
  application shows a detail from outside.
- Add its code to `texts.LANGUAGES`, and its name as an entry
  `app.language.<code>` in every catalogue (and in `pages.LANGUAGE_KEYS`).
- A language that writes decimals with a comma needs the number formatting
  that says `"es"` in `texts._Number`, `pages.View.money` and `app.js`.
- `tests/test_texts.py` checks the catalogues: `test_texts.CatalogTest` (every
  language has every entry, with the same data, and none keeps another
  language's common words), and `test_texts.ScreensLanguageTest` and
  `test_texts.StageLanguageTest` (every screen and stage in each language).
  `test_texts.OTHER_WORDS` has an entry for each language, so add one.

The summary's and the report's language (what Gemini writes and the Word shows):

- `writer.SECTIONS`, `writer.KEY_POINTS` and the `headings` of each type in
  `writer.MEETING_TYPES`: the section headings, in the same order as
  `writer.GUIDE`. `writer.LANGUAGE_NAMES` is the English name the requests use
  and `writer.LANGUAGE_KEYS` the catalogue entry `language.<code>` that names it
  (add that entry in every catalogue). `--language` and the processing form
  list the keys of `writer.SECTIONS` (`pages.languages`).
- The wrong-language check compares two word lists, `writer._SPANISH` and
  `writer._ENGLISH` (`writer.detect_language`, `writer._word_counts`). A third
  language needs a list of its own and those two functions made to take it.
- The register: `qa.LABELS` (its headings, labels and statuses; `qa.HEADINGS`
  follows), and the prefix of the question numbers, chosen by language in
  `qa.write_register`.
- The Word report: `document.LABELS`, `layout.MONTHS`, `layout.TYPES` and the
  way `layout.field_values` writes a date; `layout.FIELDS` holds the names a
  template may put in braces, in each language.
- The prompt tests of `tests/test_summary.py` loop over `writer.SECTIONS`, so
  they fail if a meeting type has no headings in the new language. No test
  checks that `qa.LABELS`, `document.LABELS`, `layout.MONTHS`, `layout.TYPES`
  and `layout.FIELDS` cover every language: that failure comes when the
  language is used, so run a summary, a register and a report in it.
