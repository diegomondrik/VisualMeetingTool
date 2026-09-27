# Independent review: WI11 (01M3HZZEGY9DVGN05MQC2QEGBS), the report in Word

**Reviewer:** revisor-independiente (Claude Opus 5.5), read-only. **Date:** 2026-09-27.
**Branch:** `work-item/01M3HZZEGY9DVGN05MQC2QEGBS-word-report` at `fc999f3` (`3385859`, `fc999f3` on `main` `43469d7`).

## Verdict

**NO LISTO — P1-1: a company template can make every client report load an external Word template (a `.dotm` with macros included), and the macro check never looks at it.**

The code meets AC01–AC07 as the contract words them. All nine recorded mutations fail as recorded. The fresh-clone evidence matches the tested commit. The blocking gap is in what the macro refusal actually guarantees to whoever receives the report. The fix is small and local to `template_bytes`.

## What I read

- D-177 in `OWNER_DECISIONS_FULL.md` (that entry only) and `word-contract-proposal.md`.
- `contract.yaml` and `plan.yaml`.
- The full diff `43469d7..fc999f3`: `document.py`, `__main__.py`, `__init__.py`, `test_report.py`, `pyproject.toml`, `README.md` and the three evidence files.
- In `meetingtool/summary/writer.py`: the prompt, the sections, `_heading_positions` and `check_summary`.
- The `.gitignore` and `repository_guard.py` extension lists.
- The layout of the WI10 review.

I did not read the owner's data folder.

## What I ran

Everything ran in a throwaway clone at `C:/Users/Diego/AppData/Local/Temp/rev-wi11-a7k3`, checked out at `fc999f3`. Probes used only synthetic summaries, frames and templates under `C:/Users/Diego/AppData/Local/Temp/rv11*`.

| Check | Result |
|---|---|
| `python -m unittest discover -s tests` | 143 tests, OK (56 s). |
| `git rev-parse 3385859 3385859^{tree}` | `3385859ba403…` / `0ed928464c67…`. Both equal `tested_commit` and `tested_tree` in `local-test-run.txt`. The log has 143 `ok`, 31 of them from `test_report`, and 112 + 31 = 143. |
| `git diff --stat 3385859 fc999f3` | Only the two evidence files. No code or test change after the tested commit. |
| `git diff --name-only` / `git diff --check` | 11 files, all inside `affected_surfaces`. Whitespace is clean. |
| `git ls-tree -r fc999f3` for docx/dotx/docm/jpg/png | None committed. The evidence files hold numbers only; title and paths are redacted. |
| CI (`.github/workflows`) | Runs only the INGOL bootstrap check, not the Python suite. So D-163's local run is the only suite evidence, as intended. |
| My own mutations, one at a time, each run against `tests.test_report` | The nine recorded ones are all detected, with the same failure counts as `mutations.txt`. The one exception is "cover always cleared": 5 failures vs 4 recorded, a different form of the same mutation. See the list after this table. |
| `summary.md` → report conversion on realistic variants | See P2-1, P2-2 and P3-1 to P3-3. |
| Template probes: remote `attachedTemplate`, embedded OLE part, external image relationship, DDEAUTO field | See P1-1. |
| Word via COM, read-only, on a synthetic report whose template attaches a local `.dotx` | Word reports `AttachedTemplate = …\elsewhere.dotx`. The report makes the recipient's Word load the template the company's file names. |
| `summary.docx` held open (Windows handle, no share-delete), then rebuilt | ReportError "could not be replaced; if it is open in Word…". No `.partial` left behind, and the earlier report is byte-identical. |

The extra mutations I tried:
- Detected:
  - order not checked (`list` instead of iterator in `check_report`);
  - `check_report` call removed from the build;
  - the git-work-tree check removed;
  - `.partial` not removed on failure;
  - no dedup of embedded frames;
  - cover images not counted;
  - English labels forced to Spanish;
  - `FRAME_LIKE` made case-sensitive;
  - cover always kept;
  - the vbaProject check alone removed;
  - the macroEnabled check alone removed.
- Survived:
  - the `PermissionError` branch removed (untested; see P3-4);
  - the build-time re-validation of the stored template skipped (see P3-4);
  - macro extensions added to the allow-list. This one is equivalent: the `MACRO_EXTENSIONS` check runs first.

## Acceptance, criterion by criterion

- **AC01:** met and tested. The git-tree and no-summary refusals happen before anything is written.
- **AC02:** met. The sha256 comparison and the position check are real. A table mention puts the image after the table. English labels work.
- **AC03:** met for the listed forms. Every problem is named at once, and the earlier report stays intact.
- **AC04:** met. The check re-reads from disk, and the drop, add and order tests fail when it is weakened. One weakness: the expected headings come from the builder's own parser (P2-2).
- **AC05:** met. The socket is patched to refuse. The key-store probe names the real module (`meetingtool.reading.credentials` exists), so it is not vacuous.
- **AC06:** met. Header, footer, logo, colour, font, cover plus page break, an empty page, cover images and `--neutral` are all tested.
- **AC07:** met as worded (`.docm`/`.dotm`, macro-enabled content type, vbaProject part, unreadable file, data folder in a git tree). The gap is P1-1.
- **AC08:** the numbers are recorded, and I could not verify them; they are the owner's data. The contract also says "the owner opens both documents and judges them". No record of that judgement exists yet (P3-8).
- **AC09:** met, and the commit identity is verified.

## Findings

**P0:** none.

**P1-1: the macro refusal can be bypassed by reference, and other active or external content passes into every client report.**
- Consequence: a template built on a macro-enabled `.dotm` (on a file share, an http URL or a template-marketplace file) passes `template set`, and every report sent to a client makes the client's Word load that `.dotm` when the report is opened.
- What I verified:
  - I added a `word/_rels/settings.xml.rels` relationship of type `attachedTemplate` with `TargetMode="External"`, and `<w:attachedTemplate>` in `settings.xml`.
  - `template set` accepted the file, and the built `summary.docx` still carries the relationship.
  - Pointed at a local `.dotx`, Word itself loads it from the report (`AttachedTemplate.FullName` is that file).
- The same package also accepts, and the report keeps verbatim:
  - an embedded OLE part (`word/embeddings/oleObject1.bin`, `oleObject` relationship);
  - an external image relationship (`http://…/pixel.png`, `TargetMode="External"`), which is a fetch on open.
- What I did not run:
  - a `.dotm` with a real macro;
  - a UNC or http target, because that would be network.
- Whether the attached `.dotm`'s macros actually run depends on the recipient's Trust Center. That is the same condition under which a `.docm`'s macros run, and `.docm` is exactly what this control refuses.
- It also happens by accident. A corporate letterhead created from a `.dotm` on `\\server\templates` carries this reference. Every client would then get a report that reaches for the consultant's internal server on open.
- The proposal gives the reason for the control: "un informe que se manda a terceros no tiene que llevar código que se ejecute al abrirlo". The current check does not deliver that.
- Fix (simpler and stronger than the current deny-list):
  - in `template_bytes`, parse every `*.rels` part;
  - refuse any relationship with `TargetMode="External"` except `hyperlink`;
  - refuse any `attachedTemplate`, `oleObject`, `package`, `control`/`activeX` or `vbaProject` relationship type;
  - add one test per kind, and one mutation.
- This single allow-list also covers the existing vbaProject and name checks.

**P2-1: a frame named in a sub-heading makes the build fail, with a message that blames the document.**
- `_blocks` never calls `mention()` for headings. A summary that writes `### [frame_001_t00-01-22.jpg] Tablero de costos` has the frame counted by `cited_frames` but never embedded.
- `check_report` then correctly refuses: "the Word document has 1 image(s) missing and 0 unexpected". The control works.
- The consequence: a well-formed summary cannot become a report, and the message points at the Word file instead of the heading line. That is plausible for Gemini, since the prompt asks for several fields per frame.
- Bold lines (`**[frame_…]**`) work. Fix: pass headings through `mention()` too, and put the image after the heading.

**P2-2: the completeness check shares the builder's parser, so a heading the parser misses is neither rendered nor expected, and the report is delivered.**
- Two verified cases:
  - A summary re-saved by an editor that adds a UTF-8 BOM (the hand-edit path D-177 promises). The first section, *Resumen ejecutivo*, comes out as the literal body text `\ufeff## Resumen ejecutivo`. The build reports 8 sections and delivers.
  - `##Decisiones` with no space, which `writer.check_summary` accepts (`#{1,4}\s*`). It is rendered as body text and delivered with 8 sections.
- The consequence is visible when the document is read, but "si falta algo no se entrega" does not hold for these cases.
- Fix:
  - read with `encoding="utf-8-sig"`;
  - match `HEADING` to what the writer accepts (`\s*`);
  - or take the expected sections independently, from `writer._heading_positions` over `writer.required_headings`.

**P3 (known limitations, do not reopen the cycle)**
- **P3-1:** `FRAME_LIKE = r"frames?_"` has no word boundary. `sales_dataframe_v2` or `keyframe_interval` in a technical summary stops the build as a "frame mention". It fails closed and names the line. Fix: `\bframes?_`.
- **P3-2: Markdown gaps.**
  - A table without outer pipes becomes text lines, including `---|---|---`.
  - `***x***` leaves literal asterisks.
  - `_italic_`, `[text](url)` and `> quote` stay literal.
  - A model-added `# Title` duplicates the report title and counts as a section.
- **P3-3: two error paths are wrong.**
  - A named frame that exists but is not a valid image raises an uncaught `UnrecognizedImageError` traceback (nothing is written).
  - A `PermissionError` while reading a frame or saving the partial file prints the "open in Word" message.
- **P3-4: two behaviours are not pinned by tests.**
  - The `PermissionError` branch: the mutation survives. I verified the behaviour by hand.
  - Build-time re-validation of the stored template: the mutation survives. A file dropped by hand into the data folder as `report-template.docx` is re-checked only because the code happens to do it.
- **P3-5: zip handling is naive.** `template_bytes` reads every part into memory: a zip bomb gives `MemoryError`, and an encrypted entry gives an uncaught `RuntimeError`. It is self-inflicted, since the template comes from whoever installs the tool. XML entity resolution is off in python-docx, and nothing is extracted to disk.
- **P3-6: the repository guard does not cover templates.** It lists `.docx` but not `.dotx`, `.docm` or `.dotm`, so a company template with its logo could be committed without the guard noticing.
- **P3-7: `check_report` matches heading text, not heading style.** It accepts any body paragraph with that text (cover included). It proves the text is there in order, not that it is a heading. `BuildTest` covers the style.
- **P3-8: evidence gaps.**
  - `mutations.txt` records outcomes but not the mutation diffs or the script. My re-implementation matched the counts, but it is not reproducible from the file.
  - The owner's judgement of the two Word files (AC08) is not recorded yet.
  - I could not test DDE fields: Windows Defender locked my synthetic DDEAUTO template. Fields on the cover are carried as-is.
- **P3-9: README and header data.**
  - The README code block has a run of spaces (`[--title "<meeting title>"]     [--date …]`).
  - Title and date come only from flags, not from the project's meeting record. D-177 only asks that they appear.

## Simpler mechanism?

- **For P1-1, yes.** A relationship-type allow-list with no external targets replaces the name and content-type deny-list and closes every by-reference path in one place.
- **Elsewhere, no.** The completeness check is already minimal. Its independence (P2-2) is a matter of where the expected headings come from, not of mechanism.

## Residual limitations after the fix

- Whether an attached `.dotm` actually runs code depends on the recipient's Office settings. I did not execute that.
- The report was not checked against Word versions other than the owner's.

Probe files are left under `C:/Users/Diego/AppData/Local/Temp/rev-wi11-a7k3` and `C:/Users/Diego/AppData/Local/Temp/rv11*`, synthetic only. The probe scripts are in the session scratchpad (`mut.py`, `probe1.py`–`probe6.py`, `word.ps1`).

**Corrected in `bf4cc4a` (P1-1, P2-1, P2-2, P3-1, P3-3, P3-4, P3-8, P3-9); re-run evidence in `7b0733b`. Verified below.**

## Re-review

**Reviewer:** revisor-independiente (Claude Opus 5.5), read-only. **Date:** 2026-09-27.
**Commits:** `bf4cc4a` (correction) and `7b0733b` (re-run evidence), on `fc999f3`.

### Verdict

**LISTO CON LIMITACIONES.** P1-1 is closed for the case that made it blocking:
- a template that attaches another template (`attachedTemplate`) is now refused, with the relationships parsed as XML, both at `template set` and again at every build;
- embedded objects and linked pictures are refused too.

P2-1, P2-2, P3-1, P3-3, P3-4, P3-8 and P3-9 are fixed and pinned by tests. One new P2 and three P3s remain. None of them reopens the cycle.

### Full suite or a bounded subset

A bounded subset would have been enough under the review policy. `git diff fc999f3 bf4cc4a` touches only `meetingtool/report/document.py` and `tests/test_report.py` among code and tests. No other module changed, so `tests.test_report` covers the changed surface.

I ran the full suite anyway because it takes 57 s. That also checks the committed "153 OK" claim directly.

### What I ran

Everything ran in a fresh clone at `C:/Users/Diego/AppData/Local/Temp/rev-wi11-b9m2`, checked out at `7b0733b`. All probe files were synthetic, in `C:/Users/Diego/AppData/Local/Temp/rv11r-*` and `rv11word`.

| Check | Result |
|---|---|
| `git diff --stat fc999f3 7b0733b`, `git diff --check` | 10 files, all inside `affected_surfaces`. Whitespace is clean. `bf4cc4a..7b0733b` changes only `local-test-run.txt` and `real-summary-run.txt`. |
| `git rev-parse bf4cc4a bf4cc4a^{tree}` | `bf4cc4ae7d8f…` / `0a277914c8e6…`. Both equal `tested_commit` and `tested_tree` in `local-test-run.txt`. |
| `python -m unittest discover -s tests` | 153 tests, OK. |
| `python docs/evidence/…/mutations.py <clone> <new folder>` | All 20 mutations detected, with failure counts identical to `mutations.txt`. Unmutated: OK. |
| My original P1-1 probe (`attachedTemplate` → local `.dotx`, which Word had loaded from the report) | Refused at `template set`. The message names the relationship. |
| The same with `TargetMode="external"` in lower case | Refused, because it is in the relationship-type list. |
| Templates saved by Word 16 via COM (`.docx` and `.dotx` with header, footer PAGE field and a hyperlink) | `active_content` returns `[]` and `template_bytes` accepts both. No false positive on normal Word output. |
| Markdown probes from the first pass, re-run on `7b0733b` | Every case behaved as intended, listed below. |
| Field-check evasion probes: INCLUDETEXT written in three ways Word never writes itself | All three accepted by `template set`. Word via COM reads each built report as having 1 field of type 68 (INCLUDETEXT), with the full code. See P2-A. |
| sha256 of `.ingol/work-items/01M3HZZEGY9DVGN05MQC2QEGBS/contract.yaml` | `d100579ab59e844ba6c35745af24c918d60f5be154d0c4dd708943d07f5bd7b5`. Taken from the committed blob at `7b0733b`; the checked-out file has the same hash (`eol=lf`). `bf4cc4a..7b0733b` does not touch `.ingol/`. |

What the Markdown probes showed:
- A frame named in a `###` heading: built, and the image follows the heading.
- A summary with a BOM and CRLF line endings: 9 sections.
- `##Decisiones` (no space): rendered as Heading 1.
- `dataframe_` or `keyframe_` in the text: builds.
- A corrupt JPG: ReportError that names the frame.
- A report held open while rebuilding: ReportError, and the earlier report stays intact.

### Status of the first-pass findings

- **P1-1: closed.** A relationship check that parses the package and refuses any external target except hyperlinks, plus a list of refused relationship types. It runs at set time and at every build, and five tests and five mutations pin it.
- **P2-1: closed.**
- **P2-2: closed.** The summary is read as `utf-8-sig`, `HEADING` now accepts no space after the hashes like the writer, and any `#` line the report cannot read as a heading stops the build.
- **P3-1, P3-3, P3-4, P3-8, P3-9: closed.**
- **P3-2, P3-5, P3-6, P3-7:** written as known limitations in `contract.yaml`, as asked.
- **AC08:** the owner's own judgement of the two Word files is still pending. It is his to give.

### New findings

**P2-A: the field check reads raw bytes with regular expressions, so a template crafted by hand can hide a DDE, INCLUDE or LINK field from it, and the field reaches the report.**
- Three encodings that Word itself never writes each pass `template set`:
  - an `instrText` element with a namespace prefix other than `w:`;
  - `w:fldSimple w:instr='…'` with single quotes;
  - a character reference inside the code (`&#73;NCLUDETEXT`).
- For each, Word opens the built report and lists the INCLUDETEXT field.
- Why it does not block:
  - it needs a deliberately crafted template, while the realistic, accidental path (the attached template) is closed;
  - Word asks before it updates linked fields or DDE.
- Consequence: the contract's AC07 wording ("a DDE, INCLUDE, IMPORT or LINK field even when split across runs") claims more than the check guarantees.
- Simpler and stronger fix: parse each `word/*.xml` part with ElementTree, as `active_content` already does for relationships. Then read the text of `{w-namespace}instrText` and the value of the `{w-namespace}instr` attribute, and match only the first word of each field code. Prefixes, quoting and entities stop mattering, and P3-A goes away too.

**P3 (known limitations, do not reopen the cycle)**
- **P3-A: false refusal from the field regex.** It matches anywhere in a field's code, not only its keyword. A cover or footer with a `HYPERLINK "https://empresa.example/link/"` field is refused as "a LINK field" (verified), and the same would happen with `/import`. It fails closed, but the message is misleading. Word's own Insert → Link writes a hyperlink element, not a field, and that passes.
- **P3-B: body lines that start with `#` become headings.** With the space after the hashes now optional, a line such as `#1 prioridad: …` or `#ventas pidió…` becomes a Heading 1 without its `#` (verified). Before the correction it was plain text. It is rare in Gemini's output and possible in a hand edit.
- **P3-C: `mutations.py` docstring.** It asks for an "empty folder outside it", but `shutil.copytree` needs a folder that does not exist yet, and an existing empty one gives `FileExistsError`.
- **P3-D: most refused relationship types have no test.** Only `attachedTemplate`, `oleObject` and external `image` are exercised. Removing `package`, `control`, `activeX*`, `aFChunk`, `subDocument` or `frame` from `ACTIVE_RELATIONSHIPS` would go undetected. The code is right as read.

### Residual limitations

- It is still unexecuted whether an attached `.dotm` would run its macros on the recipient's machine. That path is now refused, so this matters less.
- VML attributes that carry a URL directly (for example `v:imagedata` `src` or `o:href`, with no relationship) were not probed. I am not sure whether Word fetches them from a `.docx`.
- Word was exercised only as Office 16 in Spanish.

**Contract sha256 at `7b0733b`:** `d100579ab59e844ba6c35745af24c918d60f5be154d0c4dd708943d07f5bd7b5`

## Executor's note after the re-review

P2-A, P3-A to P3-D and the residual limitations are not corrected: by the review policy a P2 or P3 does not reopen the cycle. The contract approved at the digest above is left as it is, so its AC07 wording on fields claims more than the check guarantees against a template crafted by hand (P2-A); this review is where that is said. They go to the project's limitations register (`docs/limitations/REGISTER.md`) with the next work item that touches it, with the P2/P3 of WI06 to WI10.
