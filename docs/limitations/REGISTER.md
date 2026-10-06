# Limitations register

Every known limitation of this project, and of INGOL as this project met
it, in one place (INGOL WI028-AC08). An entry is here because something was
run that shows it, not because a review said so.

**How to reproduce an entry.** From the repository root:

```
python docs/limitations/reproduce.py <ID>
```

The entries about INGOL (`H1`, `H3`, `H4`, `H6`) also need a local clone of
INGOL and Go: add `--ingol-repo <path to the clone>`. The script builds INGOL
at the exact revision this project's wrapper pins
(`.github/workflows/ingol-bootstrap.yml`) and runs INGOL's own commands
against copies of this project. With no ID it runs every entry. It writes
only to temporary folders and makes no network call.

**States.**

- **open**: the limitation reproduces today.
- **fixed**: it did reproduce; the commit named fixed it, and the script shows
  it no longer does.
- **not reproducible here**: nothing on this machine can show it; the entry
  says why and where it comes from.

The script reads each entry's state from the first words of its State cell
here, and keeps no copy of its own. It exits 1 when what it sees differs
from that state, when an entry here has no reproduction there (or the other
way round), or when a state is none of the three. A fixed limitation
therefore turns the script red until this register says so, and a state
written here that the reproduction does not show turns it red too.

**Not yet in this register:** the findings of the review of the work item
that made it (`01M3CY2R6VQAB7QHEJT18YHR4P`), which are in its
`independent-review.md`. They enter the register with the next work item
that changes it, so that a review of this register does not have to review
its own entries.

**What "reproduces" means for a test gap.** Findings of the form "no test
pins X" are reproduced by a mutation: X is changed on purpose in a throwaway
clone and the relevant tests still pass. The unmutated tests must pass first
in that same clone.

## INGOL, as this project met it

Found while using INGOL on this project (INGOL's phase F8). They are INGOL's
to fix, not this project's; INGOL's own register points here.

| ID | Source | What it means | State | Seen by running |
|---|---|---|---|---|
| `H1` | INGOL D-162 | `ingol init` only accepts an empty folder, so INGOL cannot be put on a project that already exists | open | `ingol init` on a folder holding one file: refused, "is not empty" |
| `H2` | INGOL D-162 | Protecting `main` of a **private** repository, which INGOL's review needs, requires a paid GitHub plan; public repositories and CI minutes are not the issue | not reproducible here: the owner's account has Pro, where the protection exists. Source: GitHub's plans documentation, read 2026-09-25 | — |
| `H3` | INGOL D-163 | A governed project can carry only INGOL's wrapper as a workflow, so its own tests cannot run on GitHub; this project runs them locally and commits the output instead | open | A local replica of the protected review: pull request #6 passes; the same pull request, with a `tests.yml` workflow added to the protected `main`, fails TP-05, TP-15 and CI-TRUST, "workflow set must contain only ingol-bootstrap.yml". The replica sets the environment variables a GitHub runner provides (run id, runner name) and says so |
| `H4` | INGOL trabajo 0 | `ingol init` writes no `.gitignore`, no `.gitattributes` and no git repository. The consequence, measured here: on Windows' default git setting (`core.autocrlf=true`), a clone of a freshly initialised project makes `ingol doctor` fail, marking 27 of its 29 surfaces blocked as "not byte-identical" to INGOL's own copy, because git rewrote their line endings. `ingol audit` is unaffected. This project avoids it with its own `.gitattributes` | open | `ingol init`, commit, then `ingol doctor` on two clones: LF clone exit 0, 0 blocked; CRLF clone exit 1, 27 blocked |
| `H5` | INGOL D-164 | This repository is public, and INGOL's review runs on `pull_request_target` with a read token of INGOL's private installation, so anyone can trigger it from a fork. Mitigated by design (the token is used only by the first checkout, the candidate is read as data); the residual risk is a checker defect that leaks the token, worst case read access to INGOL's code | open, preconditions only: the extraction of the token was not attempted, because that would be an attack | The wrapper's trigger and secret, and `target_visibility: public`, read from this repository |
| `H6` | INGOL trabajo 0 | TP-09 checks the text of `.gitignore`, not its effect: `/generated/` (anchored) isolates the folder just as well, yet TP-09 blocks it, so `generated/` stays the one unanchored folder line here | open | `ingol audit`: TP-09 proven with `generated/`, blocked with `/generated/`, while git still ignores `generated/state.json` |

## Work item 1, the skeleton (`01M3C5MCNJ0FQJW936SZYSNPS6`)

Source: `docs/evidence/01M3C5MCNJ0FQJW936SZYSNPS6/independent-review.md`.

| ID | What it means | State | Seen by running |
|---|---|---|---|
| `WI01-P2-1` | The guard's first list missed other audio and video and the old pipeline's outputs | fixed by `a977049` (work item 2) | `.mp3`, `.mkv`, `.webm`, `transcript.txt`, `report_*.md`, `handoff_*.json`, `frames/…` are all flagged |
| `WI01-P2-2` | `.gitignore` folder lines were not anchored, so a code folder such as `meetingtool/projects/` was ignored | fixed by `ba02528`, except `generated/` (see `H6`) | No code path is ignored |
| `WI01-P2-3` | "The suite ran on the exact tree that is integrated" cannot hold literally: the evidence is committed after the run | open, by design: the integrated commit may differ only in the work item's evidence and approval | WI05: the tested `165cfff` and the integrated `3729407` differ in evidence and approval files only |
| `WI01-P3-1` | `.gitignore` covered upper-case extensions only where git ignores case (Windows) | fixed by `ba02528` | `a.MP4`, `B.DOCX`, `c.Mp3` ignored with case-exact matching |
| `WI01-P3-2` | The guard reads what git tracks now, not history: a recording added and removed inside one pull request stays in history, and `x.mp4.zip` passes | open | A throwaway repository: committed then removed, the guard reports nothing; `recording.mp4.zip` not flagged |
| `WI01-P3-3` | The tests import `meetingtool` from the current folder, so they must run from the repository root | open | The suite started from another folder: "No module named 'meetingtool'" |

## Work item 2, the guard (`01M3CG1XGTT95MT2WNTMH1TXR2`)

Source: `docs/evidence/01M3CG1XGTT95MT2WNTMH1TXR2/independent-review.md`.

| ID | What it means | State | Seen by running |
|---|---|---|---|
| `WI02-P2-A` | The guard rejects any image, video or `transcript*.txt` anywhere, `tests/fixtures/` included, so tests cannot commit sample media; they generate it at run time | open, by choice | `tests/fixtures/slide.png`, `sample.mp4`, `transcript_sample.txt` all rejected |
| `WI02-P2-B` | Data saved inside the package (`meetingtool/projects/acme/memory.json`) is caught by neither the guard nor `.gitignore`; the projects code keeps data outside any repository instead | open | Neither flags nor ignores that path |
| `WI02-P3-A` | `.gitignore` does not cover the old pipeline's names, nor root data folders in other letter cases on Linux; the guard covers both | open | `report_acme.md`, `handoff_1.json`, `transcript.txt`, `Frames/…`, `MEETINGS/…` not ignored; all flagged by the guard |
| `WI02-P3-B` | The `.gitignore` test checks root folders in lower case only | open | The test passes while `Frames/x/file.json` is not ignored |
| `WI02-P3-C` | The "not ignored" test would also pass if `git check-ignore` itself failed | open | With git pointed at a missing repository, `check-ignore` exits 128 and the test still passes |
| `WI02-P3-D` | The closed list leaves out archives, `.csv`, legacy Office formats and transcripts with free names | open, the list is closed by contract | `export.zip`, `attendees.csv`, `slides.ppt`, `budget.xls`, `notas-reunion.txt` not flagged |
| `WI02-P3-E` | The `transcript` prefix, with no underscore, also rejects a file such as `transcription.md` | open | `transcription.md` flagged |

## Work item 3, projects and meeting memory (`01M3CGKPV51VTTK3S8V1JEF4HW`)

Source: `docs/evidence/01M3CGKPV51VTTK3S8V1JEF4HW/independent-review.md`. The
review lists its P3 findings without numbers; they are numbered here in the
review's order.

| ID | What it means | State | Seen by running |
|---|---|---|---|
| `WI03-P2-1` | A path given as project id (`../repo/x`), or a link in the data folder, could write client data into a repository | fixed by `91231a1`, in the same review cycle | A path as project id is refused |
| `WI03-P2-2` | Redirected output crashed on characters outside the Windows code page | fixed by `91231a1`, in the same review cycle | Its test passes |
| `WI03-P2-3` | `pyproject.toml` listed only the top package, so an install would leave out the subpackages | fixed by `c38353c` (work item 4) | The subpackages are declared and the packaging test passes. Building a real wheel needs `setuptools`, not installed here |
| `WI03-P3-1` | Project ids drop letters such as `Ł`, `ß`, `ø`; wholly non-Latin names all become `project` and collide | open | `Łódź` → `odz`; a second non-Latin project is refused as already existing |
| `WI03-P3-2` | A very long project name raises a raw `OSError` on Windows instead of a clear error | open | A 300-character name |
| `WI03-P3-3` | A summary with Windows line endings makes the knowledge text returned differ from the one read back; the test comparing the file with the returned text is close to tautological | open | `rebuild_knowledge` and `knowledge_context` differ |
| `WI03-P3-4` | A missing `knowledge.md` raises `FileNotFoundError`, not a clear error | fixed by `ef0abc5` (WI20: a missing copy is made from the records) | The file deleted, then read: the knowledge comes back |
| `WI03-P3-5` | `~` in the data folder setting is not expanded | open | `MEETINGTOOL_DATA_DIR=~/vmt-data` gives a folder literally named `~` |
| `WI03-P3-6` | Two meetings of the same day added within the same second list alphabetically, not in the order added | open | "Zeta" then "Alpha" list as Alpha, Zeta |
| `WI03-P3-7` | The WI03-AC05 evidence holds synthetic context, summaries and a key point besides titles; no client content | open, noted only | The evidence file holds `--context`, `--summary`, `--key-point` |

## Work item 4, frames (`01M3CGKPVGGAAK06A1RD5C3XWZ`)

Source: `docs/evidence/01M3CGKPVGGAAK06A1RD5C3XWZ/independent-review.md`.
That review's table of known limitations also holds one row with no P
label: a 41.6-minute recording takes about 10 minutes. It is a measured
cost, not a finding, and reproducing it needs the owner's real recording;
its number is in `real-recording-run.txt` of that work item, and it has no
entry here.

| ID | What it means | State | Seen by running |
|---|---|---|---|
| `WI04-P2-1` | Among equal scores at the budget cut the earliest candidate was dropped; the original keeps it | fixed by `5f20bf7`, in the same review cycle | The tie-break test passes |
| `WI04-P3-1` | No test pins the port's numbers to the original's: weights, thresholds, where the duration comes from and which times count for coverage can change with the tests still green | open | Four mutations, one of each kind, all survive the frames tests |
| `WI04-P3-2` | Small undeclared differences from the original | open | Run: a recording with no duration gives 0; old frames are still there during the analysis; the discard log is in English with UTC times. Read from the code, not run: similarity is measured on the decoded JPEG, and a frame whose size differs skips the comparison |
| `WI04-P3-3` | The no-network test watched Python sockets only; FFmpeg would open a URL | fixed by `5f20bf7`, in the same review cycle | Its test passes: a URL is refused before the video library is called |
| `WI04-P3-4` | The evidence gave the original's 76 frames without a source | fixed by `67a6e4e`, in the same review cycle | The evidence names its source |
| `WI04-P3-5` | While the budget replaces a candidate, budget + 1 images are held for an instant | open | Budget 2: three held at once |
| `WI04-P3-6` | The first sample never appears in the discard log (as in the original) | open | Every other sample is a candidate or a logged discard; the first is neither |
| `WI04-P3-7` | Only PyAV 18.1 was tested; the declared floor, `av>=14`, is not verified | open | The installed PyAV is 18.1 |

## Work item 5, frame selection (`01M3CSRVTHE26R86125VY676EJ`)

Source: `docs/evidence/01M3CSRVTHE26R86125VY676EJ/independent-review.md`.

| ID | What it means | State | Seen by running |
|---|---|---|---|
| `WI05-P2-1` | When the budget is full, a slide is ranked by its first candidate's score, so a later, better-scoring repeat cannot save it; a transcript boost landing on a repeat is lost too. Not seen on the real meeting, where the budget never filled | open | Slide A scores 0.3, then 0.9 on its repeat, budget 2: B and C kept, A lost; the previous order kept A |
| `WI05-P3-1` | Four changes to the frame selection survive the tests | open | The reviewer's four mutations, all surviving |
| `WI05-P3-2` | A text transcript saved as UTF-8 with a BOM loses its first timed block without an error | open | Two timed lines read as one; one timed line is refused as none |
| `WI05-P3-3` | Transcript reading rules not checked against real Teams variants: a single tab between speaker and time, a spoken line ending in two spaces and a time, Word's curly apostrophe, and the filler "a ver" | open | All four, each shown |
| `WI05-P3-4` | The tie-break test runs with the duplicate check switched off, so it does not test the tie-break on the real path | open | Without the switch the test fails |
| `WI05-P3-5` | No test pins that the transcript is read before the video is opened | open | The reading moved after the video opens, closing it if the reading fails: tests still pass. A variant that leaves the video open is caught on Windows, but only because the test cannot delete a file in use |
| `WI05-P3-6` | No test changes the resolution mid-recording, so that branch of the duplicate check never runs | open | That branch made to raise: tests still pass |
| `WI05-P3-7` | The WI05 evidence did not measure again the 15- and 18-minute gaps that motivated it, its "before" numbers exist only there, and the seconds of its two runs cannot be compared because they ran at the same time | open | The evidence says the gaps were not measured again; no other evidence file holds the before numbers. The concurrency is stated in the evidence and not reproduced |
| `WI05-P3-8` | The Word transcript reader has no size limit (a local file the owner chooses, so not a trust issue) | open | A 60 KB file read as 60 MB of text |

## Work item 20, the project's data and what was paid (`01M46KHBYCXMGM0K6N2RM651PE`)

Source: `docs/evidence/01M46KHBYCXMGM0K6N2RM651PE/independent-review.md` (the
independent and the security reviews of `860751c`, and what was done with
each finding). The findings fixed in the same review cycle are there, not
here; these are the ones left open, and three the work item itself declared.

| ID | What it means | State | Seen by running |
|---|---|---|---|
| `WI20-P3-1` | The register's kept parts (`qa-parts/`) are found by the text of their request only, not its model: another model would be given the part paid with the first one. Neither the application nor the commands let the model be chosen (review P3-3) | open | The register asked with one model, then with another, in one folder: requests 1 then 0 |
| `WI20-P3-2` | The template and its record are two files: a cut between them leaves the new template with the old one's name shown (review P3-6; already so before WI20) | open | A disk error on the record: the new template in place, the old name said |
| `WI20-P3-3` | A process that dies between saving a meeting's record and rewriting `knowledge.md` leaves the copy one meeting behind; the application's next start rewrites it, but a summary made from the commands before that reads it without the meeting | open | The rewrite skipped: the meeting missing from the knowledge until `clear_leftovers` |
| `WI20-P3-4` | A meeting record broken by hand is found when the meeting is saved, after the summary or register was paid; what was paid is kept, but once the record is fixed the project's knowledge differs, so the request differs and is paid again | open | A record cut by hand: 1 request paid, then the meeting not added |
| `WI20-P3-5` | The same request is never paid twice in one folder: asking the commands again for the same summary to get a different answer returns the kept one. To pay for a new answer, `paid-answers/` of the folder is deleted | open, by design | The same summary asked twice in one folder: 1 request paid |
| `WI20-P3-6` | INGOL's pilot tests (`tests/test_d1_*.py`) need INGOL's kits, which are not in this public repository nor in its CI: on GitHub they are skipped, and only the owner's machine runs them | open | `test_d1_*` without the kits: the three files that need them skipped (the fourth, WI21's pilot test of R05, and the fifth, WI22's of R02, need none and run) |
| `WI20-P3-7` | A failed run that paid keeps the meeting's transcript, frames and Gemini's answers in the data folder until the meeting is processed again or the run is discarded (before WI20 they were removed at once; the owner approved the change, the security review noted it) | open, by design | A run failed at the report: its folder kept with `transcript.docx` and its frames |

## Work item 21, reading to the end (`01M474JN9F7N86SHHSKZ41Q1VY`)

Source: the limitations the contract declares
(`.ingol/work-items/01M474JN9F7N86SHHSKZ41Q1VY/contract.yaml`), and the
independent review's P3-4 (`docs/evidence/01M474JN9F7N86SHHSKZ41Q1VY/independent-review.md`).
Their reproductions use a synthetic 140 s recording whose transcript ends at
1 s; the 120 s of the old cut are written in the script, since the constant
is gone. What reading to the end costs on a longer synthetic recording is in
this work item's `synthetic-run.txt` (the owner chose it over the real
meeting); on the real meeting, WI10's evidence measured the cut saving 19% of
the time, the recording running 35 minutes past the last line.

| ID | What it means | State | Seen by running |
|---|---|---|---|
| `WI21-P3-1` | A recording that runs on after the meeting (people leave, the screen stays shared) is read to its end, with or without a transcript: the time the WI10 cut saved is spent again. On the owner's real 117-minute meeting the recording ran 35 minutes past the last line and the cut saved 19% of the time | open, by design | The 140 s recording with a transcript ending at 1 s: every sample read: 280, against about 243 if reading still stopped 120 s after the last line |
| `WI21-P3-2` | The frames shown in that tail can reach the report, since nothing leaves them out (camera close-ups are still never candidates, since WI10) | open | The slide shown from 130 s on, after the last line plus 120 s, is kept |
| `WI21-P3-3` | The person cannot set where the recording ends, and nothing says when the transcript and the recording seem misaligned (a transcript whose times run past the recording, or end long before it): the command prints no warning and has no option for an end | open | A transcript with a line at 10 min on a 140 s recording: the command ends well, says nothing about it, and its options hold no end |
| `WI21-P3-4` | The questions-and-answers register reads, for each answer, the frames until its last turn began (at most 10 minutes after it began): a slide shown during a long last explanation is now extracted but not read for that answer. The summary reads every frame. Already so before WI21 (review P3-4) | open | An answer from 0:10 whose last turn begins at 0:20: the frame at 5:00 is not among those read |

## Work item 22, the Word template's filter (`01M47ABNKZF02YZ94YKXMQCPQ1`)

Source: the limitations the contract declares
(`.ingol/work-items/01M47ABNKZF02YZ94YKXMQCPQ1/contract.yaml`), and the two
gaps found while building it and left. Their reproductions build synthetic
templates in a temporary folder (a made-up host, `example.invalid` or a UNC path to one).
What the filter refuses, in each equivalent form, is in `tests/test_template_filter.py`
and `tests/test_d1_r02_plantilla.py`, not here.

| ID | What it means | State | Seen by running |
|---|---|---|---|
| `WI22-P3-1` | Whether Word itself would act on each field the filter refuses, written in each form it reads (and whether it would on a form the filter does not know), is not run: there is no Word here, as in the external review. The forms are shown to be real fields by a second reader of the XML, not by Word | not reproducible here: it needs Word. Source: contract WI22 (not done) and the external review of 2026-10-02 | — |
| `WI22-P3-2` | What a Word package expands to is not limited: a few kilobytes of compressed XML are read whole into memory by the filter, as they are by the library that opens the template (review R08, second batch) | open | A package of a few KB holding one 40 MB part: accepted |
| `WI22-P3-3` | A field whose name does not appear in the file, because other fields build it when Word evaluates them (two `QUOTE` fields giving `INCLUDETEXT`), is not recognised: the filter reads the names written, not their results. Whether Word acts on it is `WI22-P3-1` | open | A field whose name is the result of two `QUOTE` fields: accepted |
| `WI22-P3-4` | A hyperlink (an external relationship of that type, or a `HYPERLINK` field) is accepted to any address, a `file:` one or a network path included: nothing is loaded when the document opens, and the client's click opens it. A hyperlink is part of a good template | open, by design | A hyperlink to a `file:` address of a made-up host: accepted |
