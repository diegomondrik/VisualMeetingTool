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
| `WI05-P3-2` | A text transcript saved as UTF-8 with a BOM loses its first timed block without an error | fixed by `a90cfd1` (work item 26): a text transcript is read by its byte order mark (UTF-8, UTF-16), as UTF-8 with none, and as cp1252 when it is not valid UTF-8 | The same file with a BOM: two timed lines read as two blocks; one timed line is read, not refused |
| `WI05-P3-3` | Transcript reading rules not checked against real Teams variants: a single tab between speaker and time, a spoken line ending in two spaces and a time, Word's curly apostrophe, and the filler "a ver" | open | All four, each shown |
| `WI05-P3-4` | The tie-break test runs with the duplicate check switched off, so it does not test the tie-break on the real path | open | Without the switch the test fails |
| `WI05-P3-5` | No test pins that the transcript is read before the video is opened | open | The reading moved after the video opens, closing it if the reading fails: tests still pass. A variant that leaves the video open is caught on Windows, but only because the test cannot delete a file in use |
| `WI05-P3-6` | No test changes the resolution mid-recording, so that branch of the duplicate check never runs | open | That branch made to raise: tests still pass |
| `WI05-P3-7` | The WI05 evidence did not measure again the 15- and 18-minute gaps that motivated it, its "before" numbers exist only there, and the seconds of its two runs cannot be compared because they ran at the same time | open | The evidence says the gaps were not measured again; no other evidence file holds the before numbers. The concurrency is stated in the evidence and not reproduced |
| `WI05-P3-8` | The Word transcript reader had no size limit (a local file the owner chooses, so not a trust issue) | fixed by `b16f047` (work item 29, with `WI22-P3-2`): the transcript is read by `meetingtool/word_package.py`, which refuses a part over 32 MB expanded | A 60 KB file of 60 MB of text: refused, naming the part and the 32 MB limit |

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
| `WI20-P3-6` | INGOL's pilot tests (`tests/test_d1_*.py`) need INGOL's kits, which are not in this public repository nor in its CI: on GitHub they are skipped, and only the owner's machine runs them | open | `test_d1_*` without the kits: the three files that need them skipped (the fourth, WI21's pilot test of R05, the fifth, WI22's of R02, and the sixth, WI25's of R04, need none and run) |
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
| `WI22-P3-2` | What a Word package expands to was not limited: a few kilobytes of compressed XML were read whole into memory by the filter, as they are by the library that opens the template (review R08, second batch) | fixed by `b16f047` (work item 29): every Word package the program reads (a transcript, a template, the report's last check) is read by `meetingtool/word_package.py`, which counts the bytes it decompresses and refuses, before parsing anything, one with more than 4,000 entries, a part over 32 MB expanded, or more than 256 MB expanded in all, naming the limit and the part | A package of a few KB holding one 40 MB part: refused, naming the part and the 32 MB limit |
| `WI22-P3-3` | A field whose name does not appear in the file, because other fields build it when Word evaluates them (two `QUOTE` fields giving `INCLUDETEXT`, a `QUOTE` with character codes, `IN{QUOTE "CLUDETEXT"}`), was not recognised: the filter looked for the names in all the text of an instruction (review of `6daabab`, P1) | fixed by `e18acff` | A field whose name is the result of two `QUOTE` fields: refused as a field with no name written out in the file |
| `WI22-P3-4` | A hyperlink (an external relationship of that type, or a `HYPERLINK` field) was accepted to any address, a `file:` one or a network path included (security review of `6daabab`, P3) | fixed by `e18acff`: a hyperlink goes only to `http`, `https`, `mailto` or a place in the document | A hyperlink to a `file:` address of a made-up host: refused |
| `WI22-P3-5` | The filter was a list of the fields it refuses, not of those it allows: a field that brings content from outside and is not on the list (or that Word adds in a later version) passed. A list of allowed fields closes it, at the cost of refusing the less common fields a company's template may have (`ADDIN`, `FILLIN`...): the owner's decision, 2026-10-06 (see `WI23-P3-1`) | fixed by `e0ccb19` (and, for a field written across the branches of an `mc:AlternateContent` or around an element of an ignorable namespace, which that commit let through, by `8271896`): a template may hold only the fields of a short list (`PAGE`, `NUMPAGES`, `TOC`, `PAGEREF`, `HYPERLINK`, `DATE`, `DOCPROPERTY`, `IF`, `SEQ`... listed in the README), and any other is refused naming it, at the template and at the report's last check | A field with an invented name and an address: refused as a field of that name |
| `WI22-P3-6` | Embedded fonts (a relationship of type `font` from `fontTable.xml`) are accepted, and they reach the report: they are not loaded from outside, but they are binary data of the template that the client receives, unread | open | A template with an embedded font part: accepted, and the font is in the report |
| `WI22-P3-7` | A part in a multibyte encoding that is not UTF (Shift_JIS, for instance, in a `customXml` part) cannot be read by the XML parser of the standard library, so the filter refuses the template as one with a part that is not readable XML, although Word saved it | open | A `customXml` part in Shift_JIS: the template is refused, naming the part |

## Work item 23, the allowed fields (`01M48RAZZ5MGGHYTJNYR2VQP0Z`)

Source: the limitations the contract declares
(`.ingol/work-items/01M48RAZZ5MGGHYTJNYR2VQP0Z/contract.yaml`). Its reproduction builds a synthetic
template in a temporary folder, with a field the way a citation manager writes it and a made-up
address (`example.invalid`).

| ID | What it means | State | Seen by running |
|---|---|---|---|
| `WI23-P3-1` | A company template that holds a field outside the short list (a citation manager's `ADDIN`, `FILLIN`, `MERGEFIELD`, `ASK`, `QUOTE`, `AUTOTEXT`, `EMBED`, or any field Word may add later) is refused, naming the field, and the company has to take it out of the template before it can be used. The owner chose it on 2026-10-06 over a list of refused fields (which let through any field not on it): the only Word document that comes from outside is the company's template (cover, design, placeholders), and the report is written by the application, so nobody needs those fields | open, by design: the owner's decision, 2026-10-06 | A template with an `ADDIN` field (a citation manager's, with a made-up item): refused as an `ADDIN` field, and nothing stored |
| `WI23-P3-2` | Every branch of an `mc:AlternateContent` (`mc:Choice` and `mc:Fallback`) and every element of a namespace that `mc:Ignorable` names is read, and its fields judged, though Word reads only one branch and skips an ignorable element it does not understand: which one depends on the Word that opens the file, and the file does not say. So a field outside the list in a branch Word would not read is refused as if it did, and so is Markup Compatibility that leaves that unknown (an alternative that is not formed as it is defined, a prefix nothing declares). A template saved by Word has neither a field in such a branch nor those cases | open, by design: the reading that cannot be fooled costs refusing what Word would not have read | A template whose `mc:Fallback` holds a whole `ADDIN` field and whose `mc:Choice` a `PAGE`: refused as an `ADDIN` field |
| `WI23-P3-3` | A field whose `begin` is inside a branch of an `mc:AlternateContent` (or inside an element of an ignorable namespace, named by `mc:ProcessContent`) and whose instruction is outside it is not judged as a field: the loose text outside is joined and only the first word of the whole is read, so a field outside the list can pass `set_template` and the report's last check. Accepted because the only Word file that comes from outside is the company's own template, which the owner loads himself; it is not checked in Word, and Word does not update those fields when it opens a file | open, accepted by the owner on 2026-10-07 (the verification called it P1) | A template with that arrangement and an `ADDIN` field, with no address or argument: accepted, and the report's last check does not refuse it |

## Work item 24, what stopped the first real meeting (`01M495140RMJM90PFDGBN7XZMF`)

Source: the limitations the contract declares
(`.ingol/work-items/01M495140RMJM90PFDGBN7XZMF/contract.yaml`) and the ones found
while building it and left. Their reproductions use a synthetic transcript in the
shape of the first real meeting (a title, then each time alone on its line and the
words after it) made up in a temporary folder; nothing from the real meeting is in
this repository.

| ID | What it means | State | Seen by running |
|---|---|---|---|
| `WI24-P3-1` | A transcript that names no one (each time alone on its line) is read and its summary written, but the summary names no one: its participants and who owns each task are inferred from the conversation, not read from it. The register of questions and answers, which needs who asked and who answered, refuses such a transcript before sending anything (one with `[HH:MM:SS] Name: text` lines is not refused: it names them, and the register checks no name there, as before WI24). Naming the speakers of a transcript that has none is not done (contract WI24) | open | The made-up transcript: every turn with no speaker; the summary's request has them with no name; the register stops with `qa.needs_speakers` after 0 requests. A `[HH:MM:SS] Name: text` file is written (tests) |
| `WI24-P3-2` | Whether the real Gemini now copies the frames' names right, with the name of its frame heading each block of the reading, is not run: the tests are synthetic (a reading of 141 frames, Gemini faked) and show what the request says and that a name that does not exist is never let through, not what the model does with it | not reproducible here: it needs the real Gemini and the owner's meeting. Source: contract WI24 (the owner's run is his use of the application, not this work item's evidence) | — |
| `WI24-P3-3` | A line of someone's words that is only a time ("10:30") started a block with no speaker, also in a transcript with speakers: the rule for the time alone on its line did not look at whether the file had lines with a speaker (the independent review of `0f6a3a8`, P3-1) | fixed by `efb72fa`: the rule applies only to a file with no "Speaker   M:SS" and no "[HH:MM:SS]" line; in one that has them, a line that is only a time is words of the turn, as before WI24 | "Ana Pérez   0:04", then "El cierre es a las", "10:30", "según dijeron.": two blocks, the second at 630 s and with no speaker |
| `WI24-P3-4` | The application refused a register of a transcript that names no one only when the register's stage began, after the frames of the recording were extracted (minutes, on a long recording), not when the request was made (review of `0f6a3a8`, P3-2) | fixed by `efb72fa`: the request is refused when it is made, with a message in both languages, before anything runs | A request for the register with the made-up transcript: refused by the application's check of the request, before any run |

## Work item 25, what a summary and a register must say (`01M4B3HE2AVWM7CEPPNRWS9SFY`)

Source: the limitations the contract declares
(`.ingol/work-items/01M4B3HE2AVWM7CEPPNRWS9SFY/contract.yaml`) and the ones found while building it and
left. Their reproductions use a synthetic transcript and a synthetic summary made up in a temporary folder, and Gemini
faked.

| ID | What it means | State | Seen by running |
|---|---|---|---|
| `WI25-P3-1` | The summary's own figures and dates are not checked against the transcript: a summary that writes a date with a year nobody said, or a figure nobody said, in a section with content, is delivered. Only the register is checked that way (its dates by day, month and year; its "figures said" by number). INGOL's `TrazabilidadDelResumen` asks for it and its own reviewer warned that it would refuse derived figures (a sum, a percentage, a total of the frames' columns), which a summary is meant to write; the contract leaves it out | open, left out by the contract | A summary whose "Decisions" section says a delivery on the 25th of September 2030 and a cost of US$ 48.000, over a transcript that says neither: `check_summary` returns it, with no transcript to compare |
| `WI25-P3-2` | A register date whose year nobody said and that is not the meeting's year is refused even when it is legitimate: in a meeting of the 10th of December of 2026, "el 15 de enero de 2027" when the transcript says "el 15 de enero" and no year (what it means is next January). The retry names the date, and the register stays valid if the date is written without its year, as said | open | A register of a meeting of 2026-12-10 whose deadline reads "el 15 de enero de 2027", over a transcript that says "el 15 de enero": refused, naming 15/1/2027 |
| `WI25-P3-3` | A figure or a year said in words in the transcript ("tres turnos", "dos mil veintisiete") is not read as a number: a register's "figures said" entry that writes it in digits ("3 turnos") is refused as a figure nobody said, though it was said. Teams writes most figures in digits, which is what the check relies on; a transcript that spells them out will see retries | open | A transcript that says "tres turnos" and a "figures" entry "Se trabaja en 3 turnos.": refused as a figure nobody said (3) |
| `WI25-P3-4` | A section with only the header row of a table and its rule (or any one line with a letter or a digit) counts as content: the check looks for a line with words, not for a row of data. A section that is a table with its header and no rows is accepted | open | A summary whose "Decisions" section is a table with the header row "Decisión, Responsable" and its rule, and no rows: accepted |
| `WI25-P3-5` | A year said anywhere in the transcript makes a date with that year acceptable, even if what the transcript said it about was not a date ("2030 cajas" accepts "el 25 de septiembre de 2030", when the day and month are said). The year is compared by itself, not with the date it was said next to, so that a year said before or after its date, or in another sentence, is not refused | open | A transcript that says "2030 cajas" and "el 25 de septiembre", and a deadline "el 25 de septiembre de 2030": accepted |
| `WI25-P3-6` | A number written with one separator and exactly three digits after it ("1,250", "1.250") is read as a thousands separator (1250), as the figures of this program's transcripts are, so a transcript that said "1,250 kilos" meaning 1.25 and a figure that writes "1,25 kilos" are different numbers, and the figure is refused. A percentage is compared by its number ("15 %" is 15), whichever way it was said | open | A transcript that says "pesa 1,250 kilos" and a "figures" entry "Pesa 1,25 kilos": refused as a figure nobody said (1,25) |
| `WI25-P3-7` | The figures of what the register's answers, agreements, pending items and deadlines say, and of the knowledge groups other than "figures said" (rules, owners, glossary, scope), are not checked against the transcript: only the "figures said" group is. A figure nobody said written in an answer is delivered (a derived figure, a sum, a percentage, is meant to be written there). The dates and years of every place are checked | open, left out by the contract | A register whose second answer says "Se procesan 52.000 kilos por mes." over a transcript that says no such figure: accepted |
| `WI25-P3-8` | A year said short ("el 15 de enero del 27", "el 27") is not read as a year, so a register that writes it in full ("el 15 de enero de 2027") is refused when 2027 is not the meeting's year and the transcript says no year in full. The retry names the year; writing the date as said, with no year, is accepted | open | A transcript that says "el 15 de enero del 27" and a deadline "el 15 de enero de 2027", in a meeting of 2026-12-10: refused, naming 15/1/2027 |
| `WI25-P3-9` | A number said with its scale is read ("48 mil", "1,5 millones", "3 million", "48k"), but one said only as "mil" ("mil kilos"), as "medio millón" or with the number in words ("dos mil") is not: a "figures said" entry that writes it in digits ("1.000 kilos") is refused as a figure nobody said | open | A transcript that says "Hay mil kilos." and a "figures" entry "Hay 1.000 kilos.": refused as a figure nobody said (1.000) |
| `WI25-P3-10` | Any number of four digits from 1900 to 2099 (a quantity of 2000 boxes, a sum that comes to 1990) written in any text of the register is read as a year, and refused if the transcript and the meeting do not say that number, whatever it counts: the check cannot tell a year from a quantity by its looks. Said in the transcript, or as a number with a separator ("2.000"), it is accepted | open | A transcript that says no 2000 and a pending item "Se mandan 2000 cajas.": refused as a year the transcript does not say (2000) |

## Work item 26, text transcripts in any Windows encoding (`01M4BGTP1940T4ASG54GC323WT`)

Source: the limitation the contract declares (`.ingol/work-items/01M4BGTP1940T4ASG54GC323WT/contract.yaml`). Its
reproduction uses a synthetic line saved in a temporary folder.

| ID | What it means | State | Seen by running |
|---|---|---|---|
| `WI26-P3-1` | A text transcript with no byte order mark that is not valid UTF-8 is read as cp1252, the Windows code page of Spanish and English. A file saved in another encoding (the DOS code page 850 of an old console, Latin-2, a Mac's) is read all the same, with no error, and its accents may come out as other characters: the program cannot tell which encoding a file without a mark is in. Only a file with bytes cp1252 does not define (0x81, 0x8D, 0x8F, 0x90, 0x9D) is refused as unreadable. The same goes for a UTF-8 file with a single byte of another encoding in it (a paste): the whole file is read as cp1252, so every accent of it comes out wrong, where before WI26 the file was refused (WI26's review, P3-2) | open | A line "mañana, ¿cómo estás?" saved in cp850: read as cp1252, its accents come out as other characters |
| `WI26-P3-2` | Some files that cannot be a transcript are now refused with the wrong message: a UTF-32 file (its mark starts like UTF-16's), a UTF-16 file with no mark, or a binary file that cp1252 happens to read are refused as having no timed line, not as unreadable. They are still refused; only the message misleads (WI26's review, P3-3) | open | A transcript saved as UTF-32: refused as having no timed line |
| `WI27-P3-1` | A range of two frames written with a comma before its last word, "between [a], and [b]" or "entre [a], y [b]", or with only a comma, "entre [a], [b]", is not taken as a range: the range check knows "entre/between X y/and Y" with nothing else between the two names. It was so before WI27 with each name in its own pair; since WI27 a list in one pair, "between [a, and b]", is judged the same way, so it is not taken as a range either (WI27's review, P1) | open | "between [a, and b]": the summary is accepted with both frames |
| `WI28-P3-1` | The model is the alias `gemini-flash-latest` and the prices are constants in the code (`PRICE_INPUT_PER_MILLION`, `PRICE_OUTPUT_PER_MILLION`, the list prices read for D-169). Google's answer holds token counts, not prices, and the run counts what an answer cost with those same constants, so a change of price, or a new version of the model billed at another price for the same tokens, is never noticed: the run neither stops nor shows it, and what it records as spent is not the bill. What the stop of WI28 detects is more tokens than estimated (a longer input than estimated, a version that thinks or writes more). Neither the model nor the prices were changed: either changes what the meetings cost or how they read, and that is the owner's decision (WI28's review, P1-1) | open | The same tokens at twice the prices in the code: the run records half the bill, sees no overrun and sends the second request |
| `WI28-P3-2` | A run that stopped because an answer used more tokens than estimated, processed again, starts with new counters: what it kept costs nothing, but a request it has to pay for goes out, and can overrun again with the same estimate. Each time it is processed again it can pay one more overrun, never two in the same run (WI28's review, P3) | open | Two runs with their own counters: both requests are sent and both overrun |
| `WI29-P3-1` | The limits on a Word package (32 MB a part, 256 MB in all) bound what is read, not what the XML parser takes to read it: a part of 32 MB made of many small elements is held as a tree of about ten times its size (and a package of 256 MB of such parts is read whole into memory first), so a package inside the limits can still take hundreds of megabytes (contract WI29, not done) | open | A part of 2 MB of small elements: the tree takes more than five times its size in memory |
| `WI29-P3-2` | The directory of a ZIP is read whole before anything is counted: a Word package inside the upload limit (50 MB) with hundreds of thousands of entries is refused for having more than 4,000, but only after zipfile has built a record for each, so refusing it takes memory in proportion to the entries (the independent review of WI29 measured 449 MB for 900,000 entries in 47.7 MB). It is bounded by the upload limit, about ten times it; the code does not change for this | open | A package of 60,000 empty parts: refused, and reading it took more than three times its size in memory |

## Work item 32, the external judge's findings left open (`01M4ECC5BTJBWXB51SCSV8XNBJ`)

Source: the external judge of INGOL on `main` `f1bde92`, 2026-10-07 (its draft, kept by the owner outside this
repository). On 2026-10-08 the owner decided to leave the findings below as known limitations of version 0.1.0,
each with a reproduction, to be solved in a later version. The rest of the judge's findings are not here because they
are closed or decided elsewhere: D1-03 is `WI23-P3-3` (accepted by the owner), D1-06 is R08 (`WI22-P3-2`, `WI05-P3-8`,
work item 29), D1-07 is R09 (work item 30) and D1-08 is R11 (work item 31). The reproductions use the project's own
test fixtures and a fake Gemini; nothing reaches the network.

| ID | What it means | State | Seen by running |
|---|---|---|---|
| `D1-01` | **P0 (the judge's), left open.** Outputs that do not share the store's write guarantee: two Word reports built in the same folder at once share one temporary file (`summary.docx.partial`), so one call can return success with the other's document and the other fail; and extracting the frames again deletes the old images before writing the new ones, so a write that fails leaves none. Nothing the application does reaches the first (it runs one job at a time, in its own folder for each run); the commands and the library can. No recording or transcript is lost, only derived files (`meetingtool/report/document.py`, `meetingtool/frames/extract.py`) | open | Two reports in one folder: A returns success and the file holds B's title, B is refused; extracting again with one image write failing: 3 images before, 0 after, the recording intact |
| `D1-02` | **P1, left open.** If the save of a finished run fails and, as well, moving its folder back to being worked on fails, the folder is deleted and what was paid goes with it: the run fails with nothing kept to resume (`meetingtool/app/jobs.py`, `_settle_failure`). It needs two failures in a row, for example a record that cannot be written and a permission error on the rename | open | The save fails and so does the move back: failed at saving, 2 paid requests, nothing kept, no working folder and no result left |
| `D1-04` | **P1, left open.** A register of questions and answers that comes back empty is accepted and delivered as "No question was raised in the meeting", with no retry and no warning, even when the transcript has explicit questions: the checks look at what the model returns, not at what it left out (`meetingtool/summary/qa.py`, `check_register`). The model has to answer with an empty list for it to happen; how often the real one does is not measured | open | A transcript with two explicit questions and an empty answer from the (fake) model: 0 questions accepted, the register says there were none |
| `D1-05` | P2, left open. A process that dies after a meeting's record is saved and before the project's knowledge file is rebuilt leaves the knowledge one meeting behind; the application's next start repairs it, but a summary or register made from the terminal before that reads the old knowledge without an error (`meetingtool/projects/store.py`) | open | A process killed at the rebuild (exit 77): 2 meetings listed, the next summary's knowledge lacks the new agreement |
| `D1-09` | P3, left open. Two tests of the language of the stages (`tests/test_texts.py`, `StageLanguageTest`) fail when the folder the tests run in has a word of the other language in its path (for example `3-de-codex`): they look for Spanish words in the whole English message, the inserted path included. A false positive of the tests, not a translation fault of the program | open | `StageLanguageTest` run with the temporary folder inside `3-de-codex`: 2 failures; in the normal folder: OK |
