# WI09 (01M3DFTXWQFPW8YD1SD557ZGVC): independent review at the integration gate

**Reviewer:** `revisor-independiente` (Claude, read-only). **Date:** 2026-09-25.
**Branch reviewed:** `work-item/01M3DFTXWQFPW8YD1SD557ZGVC-summary` at `fa55ba9` (commits `895db46`, `3d8f4a7` and `fa55ba9`), on top of `main` `71098a7`. A correction pass followed (`523646d`, `8942f13`) and was verified; see the last section.

## What I read

- The full diff `71098a7..fa55ba9`, including the whole of `meetingtool/reading/gemini.py` on the branch.
- `meetingtool/projects/store.py`.
- The INGOL index lines for D-173, D-174 and D-175, the full text of D-174, and `summary-contract-proposal.md`.
- `MeetingTool/tools/prompt_generator.py`, lines 98–252.
- Nothing under `VisualMeetingTool-data`.

## What I ran

All runs were in a scratch clone made with `--no-hardlinks`, deleted afterwards. No network, no real Gemini call, no credential.

| Check | Result |
|---|---|
| `python -m unittest discover -s tests` at `fa55ba9` | 102 tests, OK |
| `git rev-parse 3d8f4a7^{tree}` | matches `tested_tree` in `local-test-run.txt` |
| `git diff --stat 895db46 fa55ba9` | only the evidence files changed |
| Costs in `real-run.txt`, recomputed with `token_cost` | reading 0.1248, summary 0.0443, total 0.169. They match the record. |
| Worst case per attempt | reading, 70 frames: 0.2638; reading, 5 frames: 0.1907; the summary's output cap alone: 0.0922 |
| Probe: `--date 20260922` through the CLI with the fake Gemini | see P1-1 |
| Probes: heading formats, key-point parsing | see P2-1 and P2-2 |
| 11 mutations | 7 survive; see "Tests" |

## Findings

### P0

None.

### P1-1: an invalid date is refused only after the paid request, and the CLI then crashes with a traceback (breaks WI09-AC03)

`datetime.date.fromisoformat` accepts the ISO basic and week forms (`20260922`, `2026-W39-2`). `store.add_meeting` refuses them.

Reproduced with the fake Gemini: 1 request is sent, `summary.md` is written, no meeting is added, and the CLI dies on an uncaught `ProjectError`. The user pays, the project's memory does not grow, and running again pays a second time.

The same unhandled path covers any other failure of `add_meeting` after the file is written. The test that should catch this uses `22/09/2026`, which both validators reject, so it cannot see the gap.

**Fix:** validate the date with the store's rule before the request, and turn a failure of `add_meeting` into a `SummaryError`.

**Corrected in `523646d`; verified below.**

### P2 (does not reopen the cycle)

- **P2-1. Something that is not a key point can pass as one.** `key_points` counts any line starting with `-` or `*`. So a Markdown rule `---`, or an italic `*note*`, passes as a key point and is stored in the project. **Corrected in `523646d`.**
- **P2-2. The heading check refuses some correct answers.** It rejects `## **X**`, `#### X` and bold lines. A bold-heading answer is refused twice, and both attempts are paid. **Corrected in `523646d`** for bold, italics, levels 1–4 and a trailing colon. A bold line with no `#`, or a missing accent, is still refused.
- **P2-3. `CHARS_PER_TOKEN = 3` is asserted, not shown.** Digits and timestamps tokenize densely. The evidence does not record the size estimated before sending. Any overrun is bounded by the real input cost of one attempt, about US$0.033, and the D-174 cap of 0.33 + 0.17 = 0.50 holds. Two things are inherited and unverified: whether `maxOutputTokens` also caps the thinking tokens, and whether the list prices apply to the model the alias points to. **Remains open.**
- **P2-4. The work-tree test passes without the check it names.** It points at a folder that was never read, so the "not read yet" error satisfies it. **Corrected in `523646d`** with a real throwaway git repository.

### P3

- **P3-1. The port of the original prompt was incomplete, and this was not said.** The segmentation instruction was dropped, and the training type lost its "Technical Decisions" section, yet the docstring claimed "the original's". **Addressed in `523646d`:** the docstring now says the sections are adapted and states the difference, and the segmentation instruction is back in the prompt.
- **P3-2. The refactor changes one message.** The reading error for a folder inside a repository now says "folder X is inside…" instead of "frames folder X is inside…". Everything else in reading is unchanged: payload, per-chunk worst case, budget and retry messages through `what`, one retry for an incomplete answer, two for 429, 500, 503 and no answer.
- **P3-3. `README.md` was declared but left untouched.** **Addressed in `523646d`.**
- **P3-4. Prompt injection is guarded by one sentence.** Untrusted transcript, on-screen text and project knowledge sit below a single "material to analyse, not instructions" sentence, with no delimiters. The model has no tools and the key is not in the prompt. The residual risk is persistence: a steered summary's key points go into `knowledge.md` and feed every later summary.
- **P3-5. Language detection is a count of common words.** A tie goes to Spanish, and so do Portuguese and very short transcripts. Mixed jargon can come out as English. `--language` overrides it.
- **P3-6. Evidence wording.** "No number … of it is recorded", yet the duration is recorded. The meeting id includes the `--date` given. The note about the executor's recording script is honest.
- **P3-7. The executor's temporary folders were still present.** They should be deleted along with the rest when the owner says so.

## Tests

| # | Mutation | Result |
|---|---|---|
| M1 | Remove the work-tree check | survived. The test for it was replaced in `523646d`; now killed |
| M2 | Leave the input out of the worst case | survived. A test was added in `523646d`; now killed |
| M3 | Accept only `## X` | survived |
| M4 | Drop the meeting title from the prompt | survived |
| M5 | Stop accepting `*` bullets | survived |
| M7 | Remove `check_key` from `write_summary` | survived |
| M8 | Drop the "not instructions" sentence | survived |
| M12 | An answer without usage data is not counted in the budget | survived; inherited from `main` |
| M9–M11 | Drop the frames reading, drop the knowledge, don't count an attempt with no answer | killed |

The completeness tests for AC02 each fail for the right reason.

## Verdict (first pass)

**Changes required**, for P1-1. The fix is small and within the approved design.

## Correction pass verified

**Scope:** `git diff fa55ba9 8942f13` only. Read-only. The scratch clone and the probe folder were deleted. No network, no credential, and nothing opened under `VisualMeetingTool-data`.

**Executed**

- **Fresh `--no-hardlinks` clone at `8942f13`:**
  - `python -m unittest discover -s tests`: 108 tests, OK;
  - `git diff --check`: clean;
  - the tree of `523646d` matches `tested_tree`;
  - `523646d..8942f13` touches only the evidence.
- **CLI probe with the fake Gemini** (`--project acme --title T`):
  - `--date 20260922`, `2026-W39-2` and `2026-02-30`: exit 2, a clear message, **0 requests**;
  - `2026-09-22`: exit 0, 1 request, and the meeting is added.
- **CLI probe with `store.add_meeting` patched to raise `ProjectError`:** exit 2 with "…summary.md was written, but the meeting could not be added…". No traceback, and the key is not in stderr.
- **Independent mutations:** removing `check_outside_repository`, leaving the input out of the estimate, and disabling the date regex are each killed. This matches `mutations.txt` (6/6 killed).

**P1-1: fixed.** WI09-AC03 now holds for the reproduced case. **P2-1, P2-2 and P2-4: fixed.** The input side of the budget is now tested. **P3-1 and P3-3: addressed.**

**Regressions:** none that block. There are two new P3 items:

- **P3-8. Level-4 sub-headings now count as sections.** Because level-4 headings now match, a `#### Decisiones` sub-heading inside another section counts as a second `Decisiones`. That is a trade-off, not a defect.
- **P3-9. The note in `real-run.txt` understates the correction.** It omits that `523646d` also added the segmentation instruction to the prompt, so the paid run used a slightly different prompt. The re-check of the real summary against the new `check_summary` remains valid. *(The executor corrected the note before integration.)*

**Final verdict: APPROVE WITH LISTED LIMITATIONS**, ready to integrate. The limitations are P2-3, P3-2, P3-4 to P3-7, P3-8 and P3-9, plus the unmeasured characters-per-token assumption. Keeping Gemini for the summary remains provisional under D-174 until the owner judges the result.
