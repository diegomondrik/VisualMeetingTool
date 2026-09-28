# Independent review: WI12 (01M3JS6BH8TTPN0C76NFB7E6N6), meeting types and summary language

**Reviewer:** revisor-independiente (Claude Opus 5.5), read-only. **Date:** 2026-09-28.
**Branch:** `work-item/01M3JS6BH8TTPN0C76NFB7E6N6-meeting-types` at `9ede6a9`, on `main` `94d3ad9`.

## Verdict

**LISTO CON LIMITACIONES.** I found no P0 or P1. Everything the work item claims, I reproduced: 179 tests pass, all 15 mutations are caught, the tested commit is the one named, the counts on the real summaries match, and the frame check refused the same two real summaries the report refused. There are four P2 findings. Two of them are cheap to fix in the one correction pass (F1 and F2). The other two need a plain sentence in the pull request (F3 and F4).

## What I read

- The approved proposal, `meeting-types-contract-proposal.md`, in full, and the D-178 line of `DECISIONS_INDEX.md` (found with grep).
- `contract.yaml` and `plan.yaml` in `.ingol/work-items/01M3JS6BH8TTPN0C76NFB7E6N6/`.
- The whole diff `main...HEAD` (94d3ad9...9ede6a9): `writer.py`, `__main__.py`, `README.md`, `tests/test_summary.py`.
- The evidence: `mutations.py`, `mutations.txt`, `real-summary-run.txt`, and the head and tail of `local-test-run.txt`.
- For comparison: `meetingtool/report/document.py` (`cited_frames` and the paths where the report refuses), `meetingtool/projects/store.py` (`render_knowledge`) and `gemini.call_checked` (the budget).
- The four real `summary.md` files, read by code only to count. No text, names or numbers from them appear in this report.

I did not read `history/`, the full decisions file, or the WI11 review file. The report layout follows the caller's description.

## What I ran

All runs were in a throwaway clone at `C:/Users/Diego/AppData/Local/Temp/rev-wi12-*`. The clone and the probe folders were deleted afterwards.

| Command / probe | Result |
|---|---|
| `git rev-parse HEAD main` | 9ede6a9…, 94d3ad9… as declared |
| `git rev-parse ebce3f1 ebce3f1^{tree}` vs `local-test-run.txt` | Commit ebce3f17… and tree d84a2805… match exactly |
| `git diff --stat ebce3f1 HEAD` | Only `local-test-run.txt` and `real-summary-run.txt` change. No code after the tested commit |
| `git diff --name-only main...HEAD` | 10 files, all inside `affected_surfaces` |
| `python -m unittest discover -s tests` (Python 3.12.10) | Ran 179, OK |
| `mutations.py <clone> <empty Temp folder>` | 15 of 15 caught, and the unmutated run passes. Output is identical to `mutations.txt` line for line, failure counts included |
| Old `writer.py` from `main` vs new, for no type, kickoff, status, technical and training, in es and en | Headings, guides, SECTIONS, GUIDE and ROLE are identical. The prompt is byte-identical except for the one added LANGUAGE_RULE line |
| Language and frame checks on the 4 real summaries (counts only) | Whole-text wanted/other: 566/2, 421/0, 532/2, 261/0, which matches the evidence. The highest count of the other language in any one section is 2, far below the threshold of 8. All four pass the language check. The frame check refuses negotiation-es (a mention without a file name) and requirements-en (a frame that is not in the folder). `cited_frames` refuses the same two |
| Randomised parity test, `check_frames` vs `cited_frames`, 30,000 texts with 18 kinds of mention and normal frame files | 0 disagreements. The FRAME_REF and FRAME_LIKE patterns and flags are identical |
| The same test with two unusual folder entries added | They disagree only on (a) a directory named like a frame and (b) a file whose name differs only in case on Windows (see F6) |
| Synthetic language-check probes | See F1 and F5 |
| `python -m meetingtool.summary … --type discovery` | argparse says `invalid choice: 'discovery' (choose from …)` (see F2) |
| grep for `AIza` or `api_key` in the evidence | Nothing found |
| `git diff main...HEAD -- meetingtool/reading` | Empty. The budget path is untouched |

## Findings by severity

### P0 / P1

None.

### P2 (non-blocking; record as known limitations)

**F1. The language check wrongly refuses a section that is mostly code or foreign-language labels.** `_QUOTED` only removes one-line quotes and inline backtick spans. Fenced code blocks and Markdown tables still count. I built two cases and both were refused:
- A Spanish summary of a `technical` meeting whose "Análisis visual técnico" section holds a fenced SQL query was refused: `(1 common words of it, 11 of the other language)`. The words that tip it are AND and IS.
- An English summary whose "What was on screen" section is a table of unquoted Spanish on-screen labels was refused: `(1 … 13 …)`.

Consequence: a real summary is refused after two paid requests, and the command offers no way around it. The `technical` guide itself asks Gemini to report the queries seen on screen, so the first case is plausible for this owner's work. The four real runs did not hit it, because their largest count was 2. The fix is small and stays in scope: add fenced ```…``` blocks, multi-line, to what `_QUOTED` leaves out. Neither the contract nor the README mentions this limitation.

**F2. From the command line, `--type discovery` does not say what replaces it.** The writer's message ("use 'presale' or 'requirements'") only reaches someone calling the library. The command is how the owner actually uses the program, and there argparse refuses first with a generic "invalid choice" and the list of choices. Criterion AC03 says the user "is told what replaces it". That is only tested at the library level (`test_a_new_summary_cannot_take_the_retired_type…`). The command-line test checks only that it exits and sends nothing. Two possible fixes: let `discovery` through argparse so the writer's refusal is the one shown, or add a custom message.

**F3. AC08 changes when a summary is refused, and D-178 did not approve that.** The frame check makes a summary fail, after a retry, whenever it misnames a frame, even though the Markdown summary could still be read. This was a finding from the real run. It does not contradict D-177 or D-178, and it stays inside `meetingtool/summary/**`. But it trades a readable summary for one the Word report can use, and the owner has not explicitly made that choice. Nobody has measured whether the retry actually fixes a bad frame reference, and the evidence says so honestly. Tell the owner in one plain sentence in the pull request.

**F4. Seguimiento (the `status` type): the proposal says two things, and the implementation follows one of them.**
- The table row ("Como hoy") and criterion 1 ("los demás tipos siguen igual") say status stays as it is. The implementation keeps it as it is. I checked this byte for byte against `main`.
- The proposal's example ("en un seguimiento, las decisiones se leen contra lo acordado antes") and the literal "Cada tipo" in criterion 2 suggest a new way of reading decisions.

Status's existing "Delta since last meeting" section already compares against earlier agreements using the project's knowledge, but its Decisions guide is the generic one. My judgement: this is not a conflict with a decision. The proposal is ambiguous, and the implementation chose the reading that satisfies the testable criterion (AC1). If the proposal had asked for a new reading for status, that would have broken "siguen igual". The owner should still be told in one plain line that seguimiento does not get a new reading.

### P3

- **F5.** The language check can be fooled by a summary whose body is written entirely inside quotes. It is a guard against model mistakes, not against someone trying to trick it. The contract already notes the related weakness of quotes without quotation marks.
- **F6.** Two unusual folder entries make `check_frames` and `cited_frames` disagree: `check_frames` compares against the names `glob` returns, while the report checks `is_file()`. The first is a directory named like a frame. The second is a file whose name differs from the summary's only in case, on Windows. The extractor produces neither.
- **F7.** The parity test uses 5 fixed cases. It would not catch the report's FRAME_LIKE losing IGNORECASE, or losing the plural `frames_`. Parity holds today because the patterns are copied exactly. A simpler way to keep that guarantee is for `document.py` to use `writer`'s patterns, since it already imports `writer`. That change is outside this work item's surfaces, so it belongs to the report's own work item.
- **F8.** The "no longer exists" note for the retired type matches `^###\s.*\(discovery\)\s*$`. A meeting of any type, or none, whose title ends in "(discovery)" would also trigger the note. Harmless.
- **F9.** Building the Word report from the requirements summary ("at the owner's request, session 114") and criterion AC08 were added after D-178. There is no decision line recording them, and D-178 is the last entry in the index. Both are local and cost nothing. Consider recording the request.
- **F10.** A test docstring quotes one real frame file name (a frame number and a timestamp). It is metadata, not meeting content. Mentioned only for completeness.
- The report can also refuse a summary for reasons `check_summary` does not look at, such as a line that starts with `#` but is not a heading, or a frame file that cannot be embedded. AC08 does not claim to cover these. I am noting it only so that "never delivered when the report could not embed it" in the README is not read more broadly than it is.

### Residual limitations (not defects)

- I cannot verify from the repository that the model was gemini-3.8-flash, the cost of US$0.214, or that Word opened the reports. Those are recorded observations from the owner's machine.
- It is unmeasured whether a retry fixes a wrong language or a bad frame reference, and the evidence says so.
- The language check tells Spanish from English by counting about 15 common words of each. It is not a general language detector.

## Criteria

| # | Verdict | Basis |
|---|---|---|
| WI12-AC01 | Met | The three new types put their sections after the participants, in es and en. A missing section is retried once and refused, with nothing written. The other four types and "no type" match `main` byte for byte apart from the language rule line. 2 mutations caught |
| WI12-AC02 | Met | The stance comes before the sections. The Decisions guide differs for all four cases (the three new types and no type). For requirements, the executive summary and pending items are about what is still unknown. 2 mutations caught. Whether Gemini actually reads the meeting differently is the owner's call, as the contract says. The seguimiento reading is F4 |
| WI12-AC03 | Met at library level | Stored `discovery` meetings are still listed and read, with the note. A new summary is refused with no request sent. The command line does not say what replaces it (F2). 2 mutations caught |
| WI12-AC04 | Met, with F1 | The whole text and each section are checked, quotes are left out, and an answer in the wrong language is retried then refused, naming the language or section. 6 mutations caught. Real margins are wide. Fenced code and label tables can cause a wrong refusal (F1) |
| WI12-AC05 | Met | The key is absent from outputs, the request body and path, and the files, including on the refusal path. A request that could go over the budget is not sent. `gemini.py` and the worst-case formula are untouched |
| WI12-AC06 | Met (evidence recorded, not reproducible by me) | Numbers only. The counts I could recompute match. The four budgets add up to at most 0.50 |
| WI12-AC07 | Met | Tested commit and tree match. Only evidence files come after it. 179 OK reproduced in my clone |
| WI12-AC08 | Met, with F3, F6 and F7 | The check reproduces "refuses exactly the two" on the real summaries. Randomised parity shows 0 disagreements on normal folders. 3 mutations caught |

No files were written in the real repositories. The throwaway clone and probe folders under `C:/Users/Diego/AppData/Local/Temp/` were removed.

## Correction pass (executor, after this review)

- **F1 corrected:** fenced code blocks are left out of the language count everywhere, and a section is judged on its prose without its table rows (the whole summary still counts tables). Tests: `test_code_and_tables_of_labels_seen_on_screen_keep_their_language` (both of the reviewer's cases) and `test_a_section_whose_prose_is_in_the_other_language_is_still_refused_next_to_a_table`. Two new mutations, both detected (17 of 17 in `mutations.txt`). The four real summaries give the same results as before.
- **F2 corrected:** `--type` has no argparse choices; the writer refuses an unknown or retired type before any request, and the command prints its message (`use 'presale' or 'requirements'`, or the list of types). The command-line test now checks the message and exit code 2.
- **F10 corrected:** the real frame file name is gone from the test docstring.
- **F3, F4, F5 to F8:** recorded as known limitations in `contract.yaml`, and F3 and F4 said plainly in the pull request.
- **F9:** the owner's request is recorded in INGOL's ledger for session 114.

## Re-review of the correction (reviewer, head 78f4fe6)

**Verdict: still LISTO CON LIMITACIONES.** The correction adds no P0 or P1. F1, F2 and F10 are fixed, and the contract records F3 to F8 accurately. Checked in a new throwaway clone at 78f4fe6 (deleted afterwards); the correction commit is 063ee0b and only `local-test-run.txt` changes after it; the full suite gives 181 tests OK.

1. **F1 fixed.** Both probes of the first review pass; a section with a small table plus a paragraph in the other language is still refused (0 words of the right language, 14 of the other); the four real summaries still pass. The fix loosens the check in three ways: a section written entirely as a table is judged only as part of the whole summary (P2, recorded in the contract); text in the other language inside a fenced block is not counted, the fenced variant of F5 (P3; a whole summary in the other language, even as one-cell tables, is still refused: 5 words against 168); an unclosed fence is still counted, so malformed Markdown can still cause a wrong refusal (P3).
2. **F2 fixed.** `--type` has no fixed list; for `discovery` the command exits 2, names "use 'presale' or 'requirements'" and sends no request; an unknown type says "unknown meeting type". Checked through the updated command test and the code (a hand run with a fake key under Temp was denied at the permission prompt). Without a saved key, or with frames not yet read, those messages come first; nothing is sent either way (P3).
3. **F10 fixed at head.** The frame name remains in the branch's earlier commits (775ad9f to 9ede6a9) unless squash-merged; it is a frame number and a timestamp, not meeting content (P3).
4. **Mutations reproduce 17/17**, matching `mutations.txt` line for line apart from line endings; both new mutations make a test fail.
5. **Suite evidence is for the right commit:** tested_commit 063ee0bd…, tested_tree 7e853060…, equal to `git rev-parse`; 11 files in `main...HEAD`, all inside `affected_surfaces`.
6. **Contract limitations accurate**; the only omission was the fenced-block variant of F5.

Executor, after the re-review: the fenced-block variant of F5, the unclosed fence and the order of messages without a key were added to the contract's known limitations (text only, no code change).
