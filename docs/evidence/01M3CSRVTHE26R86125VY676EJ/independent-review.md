# Independent review: work item 01M3CSRVTHE26R86125VY676EJ (frame selection)

Reviewer: `revisor-independiente` subagent, own context window, 2026-09-25.
Reviewed: branch `work-item/01M3CSRVTHE26R86125VY676EJ-frame-selection`, head `df95cde`, against base `main` `8bd99e2` (3 commits, 8 files).
Verdict: **approved with the limitations listed below. No P0 or P1.**

## What I read

- The contract and plan for this work item.
- The previous work item's review, for the format.
- The full diff `8bd99e2..df95cde`, plus `extract.py` and `signals.py` in full.
- Both evidence files.

I did not open anything under `VisualMeetingTool-data`.

## What I ran

- **Test suite in the working repo:** `python -m unittest discover -s tests`. 55 tests, OK. The working tree was clean before and after.
- **Tested commit:** `git rev-parse 165cfff^{tree}` gives `5aadf82f…`, the same `tested_tree` that `local-test-run.txt` declares. `git diff fca3382 df95cde` touches only the two evidence files, so the code that ran on the real meeting (`fca3382`) is the code at HEAD.
- **TP-06 by hand:** `git diff --name-only` lists 8 paths. All fall under the four declared `affected_surfaces` and none under `controlled_by_content`. I did not run `ingol audit` because it is not on PATH here.
- **Client data:** no media, transcript or `.docx` file appears anywhere in `git log --all`. The only new writes in the diff are test fixtures in temporary folders, built from made-up text. `transcript.py` writes nothing, and its error messages carry the path, not the content.
- **Mutations:** 14 run on a throwaway clone of `df95cde` in the scratchpad. 10 turn the suite red, 4 survive.
  - **Red:**
    - the pre-budget check always False;
    - substring matching instead of whole words;
    - `boosted_in` never counted;
    - no cap at 1;
    - an unreadable transcript silently ignored;
    - Teams time without hours;
    - the tie-break inverted, which is still caught with the check patched off;
    - duplicates left out of `candidate_times`/`last_candidate`;
    - the boost left out of the pipeline;
    - the post-budget check removed.
  - **Survived:** see P3-1.
- **Probes:**
  - A synthetic ranking case (P2-1).
  - Transcript edge cases:
    - UTF-8 with a BOM (P3-2);
    - latin-1, refused with a clear `TranscriptError`;
    - a tab separator;
    - a non-breaking-space separator, which is accepted;
    - a text line ending in `   10:30`;
    - a curly apostrophe;
    - blocks with no text;
    - blocks out of order, which are sorted;
    - minutes above 59, which are accepted without validation and do no harm.

## Checks on specific points

- **The pre-budget check.** It compares the candidate with `last_distinct_gray`: the content area at the saved size, before JPEG compression. If the shapes differ, the candidate counts as distinct and nothing crashes, although no test covers that path. A-B-A works: A is compared with B, so it counts as distinct. The fixture A, B, B(camera), C, A still keeps A, B, C, A. Duplicates still count in `candidate_times`/`last_candidate`, and the real run confirms it: candidates, `low_score` and `minimum_gap` are identical before and in run A (360 / 11874 / 1800). The memory claim holds: the extra state is one grayscale image.
- **The changed tie-break test.** The executor's claim is honest.
  - In that test the sample at 3 s is slide B again, so the new check would drop it and the test would stop reaching the tie-break.
  - The assertion is unchanged, and the inverted-tie-break mutation still turns it red.
  - It is weaker only in that it now runs with production logic patched off. A fixture with a distinct slide at 3 s would test the same thing without the patch (P3-4).
- **The AC01 test's self-check.** The "old order" test does fail when the post-budget check is removed, so it really does pin the old failure mode.

## Findings

### P0 / P1

None.

### P2-1: a slide is ranked by its first candidate's score, so a later, better-scoring repeat cannot save it

The pre-budget check sets `last_distinct_gray` before the budget decides (`extract.py:195`). As a result, repeats of a candidate are dropped as `near_duplicate` even when that candidate was rejected by the budget on arrival, or evicted from the pool later. The slide's place in the budget then depends only on its first candidate's score.

Reproduced on a synthetic recording: slides A (3 s), B, C; scores 0.3, 0.9 (a repeat of A), 0.5, 0.5; budget 2.

| Order | Frames kept | Slides kept |
|---|---|---|
| New | `[3.0, 4.0]` | B, C |
| Old | `[2.0, 3.0]` | A, B |

Slide A is lost although its 0.9 candidate was the best of the recording. The number of distinct frames is the same, so the objective (duplicates no longer take budget places) holds. What changes is which slides survive when the budget binds, and the contract does not declare this.

It interacts with the boost: a transcript boost landing on a repeat of a still slide is thrown away. That is consistent with run B, where there were 506 raised candidates and 717 near-duplicates, but only 78 → 81 frames kept.

No effect was observed on the real meeting, because the budget never filled there (at most 81 held out of 150). A fix would keep the highest score seen in the run on the pool entry that represents it, but that does not fit a heap without extra bookkeeping. Record it as a limitation.

### P3 (known limitations, do not reopen the cycle)

| ID | Finding |
|---|---|
| P3-1 | Four mutations survive:<br>1. Comparing with the immediately previous candidate instead of the previous distinct one. The contract's wording is not pinned, so slow drift, such as scrolling or typing, is untested.<br>2. `<=` → `<` at the window's +30 s edge. `near(130)` tests the lower edge only.<br>3. Counting `boosted` for every candidate. The `boosted` figure printed by the command line and cited in the evidence is asserted nowhere.<br>4. Setting `last_distinct_gray` only when the candidate enters the pool (the P2-1 variant). |
| P3-2 | A UTF-8 text transcript with a BOM loses its first timed block without any error. The BOM keeps `[HH:MM:SS]` from matching, and `strip()` does not remove the BOM character. A file whose only timed line is the first one is refused as "no timed line". One-line fix: `encoding="utf-8-sig"`. |
| P3-3 | Parsing heuristics that are not verified against real Teams variants:<br>- a speaker and time separated by a single tab do not match (`\s{2,}`);<br>- a spoken line ending in two spaces and `10:30` is read as a new block;<br>- `"I'm showing"` does not match Word's curly apostrophe `’`;<br>- whole-word `ver` still matches the filler "a ver".<br>Run B shows that the parser worked on the owner's real `.docx`. The phrase list is the original's. |
| P3-4 | The tie-break test now runs with `_is_near_duplicate` patched off. It is honest, but a fixture whose sample at 3 s is a distinct slide would test the tie-break on the production path. |
| P3-5 | No test pins that the transcript is read before the video is opened. Moving the read after `av.open` but before `mkdir` would still pass. The contract only requires "before any frame is written", which is met. |
| P3-6 | No test changes the resolution mid-recording, so the shape-mismatch branch of the pre-budget check is never run. |
| P3-7 | Evidence (AC04):<br>- **The motivating internal gaps (15 and 18 min) were not measured again.** The only gap reported is the 37.1-minute one at the end, and the evidence says so openly.<br>- **The "before" numbers are recorded only here.** No earlier evidence file carries them, so they cannot be checked independently.<br>- **The runs' seconds cannot be compared.** Runs A and B were concurrent (the evidence says so). By reasoning, the extra cost is one LANCZOS resize and one SSIM per candidate (360 / 798), small against about 2,000 s. Candidates that enter the pool are resized twice. |
| P3-8 | The `.docx` reader loads `word/document.xml` with no size limit. It only reads a local file the owner chooses, so this is not a trust-boundary issue. |

## Residual limitations of this review

- `ingol audit --work-item` was not run: the CLI is not available in this environment.
- I did not check the phrase list and the ±30 s window against the original MeetingTool source. I took the port's statement that they match the original.
- I could not check the real-run numbers against anything. They are internally consistent: 282 + 78 = 360, 717 + 81 = 798, and the budget never filled.

## Verdict

**Approve with the listed limitations** (P2-1, P3-1 … P3-8). No P0 or P1.

Reviewed commit: `df95cde`, tested tree `5aadf82f8cc11e1911f9ed73336defa16ffca808` (at `165cfff`; `df95cde` adds only the suite evidence), base `8bd99e2`.

## Disposition (executor)

No correction pass: P2 and P3 findings do not reopen the cycle (INGOL review policy); they are recorded here as known limitations of this work item and go into the project's limitations register (INGOL WI028-AC08).
