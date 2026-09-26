# Independent review: WI08 (01M3DH07MRDHA8YR446R3C940D), faster frame extraction

**Reviewer:** revisor-independiente (Claude Opus 5.5), read-only. **Date:** 2026-09-25.
**Branch:** `work-item/01M3DH07MRDHA8YR446R3C940D-faster-extraction` at `ee52955` (`eb792fd`, `8e41141`, `ee52955` on `main` `1cf4699`).

## What I read

- D-175 in full, the last section of `OWNER_DECISIONS_FULL.md`.
- The full branch diff: `contract.yaml`, `plan.yaml`, `extract.py`, `test_frames.py` and both evidence files.
- `signals.py`, `pyproject.toml` and the steps of the CI workflow.
- The WI07 real-run evidence at `1cf4699`, read only to check the "before" timings that the WI08 evidence cites.
- File names in `C:/Users/Diego/VisualMeetingTool-data`. No file there was opened.

## What I ran

All runs were in a scratch clone made with `--no-hardlinks` under `C:/Users/Diego/AppData/Local/Temp/wi08-review-7f3k2`.

| Check | Result |
|---|---|
| `python -m unittest discover -s tests` at `ee52955` (Python 3.12.10, PyAV 18.1.0, numpy 2.5.1) | 84 tests, OK |
| Mutation: never scale (`if width > ANALYSIS_WIDTH` becomes `if False`) | The new full-HD test fails, as it should |
| Mutation: drop the content crop in `_analysis_gray` | `test_scoring_sees_only_the_content_area_below_the_camera_strip` fails (320x240 path) |
| Pixel probe: the grey level from `rgb24` + `to_gray` (old path) against `_analysis_gray` (new path), on yuv420p frames at 320x240, 1920x1080, 642x362, 1366x768, 1280x720 and 641x480, plus frames tagged full-range or BT.709 | The same values, or within 1 level. FFmpeg's `gray` output is expanded to full range (Y 16/235 becomes 0/255), as in the old RGB path, and full-range-tagged input is handled the same way by both paths |
| `interpolation="AREA"` on PyAV 18.1 | Works. Lowercase `"area"` raises KeyError, so the exact spelling matters |
| `git diff eb792fd ee52955 -- meetingtool tests .ingol` | Empty: the code measured at `eb792fd` is the code being integrated |
| `git diff --name-only 1cf4699 ee52955` | 6 files, all inside the declared surfaces; no image or media file |
| `git diff --check` | Clean |
| Tree of `8e41141` | `27a9b46…`, which matches `tested_tree` in `local-test-run.txt` |
| Search every ref for "2189" | Found only in the WI08 evidence itself (see P2-1) |
| Names in the data folder | `comparacion-extraccion-wi08` holds 34 `.jpg` files (21 + 13), which matches the evidence |

## Answers to the requested checks

**1. Correctness and faithfulness to D-175**

- **The kept frame still comes from the full sample.** `rgb = frame.to_ndarray("rgb24")` runs only for candidates. The pre-budget duplicate check, the JPEG and the post-budget check all use it. The test shows the kept frame is 1280x720 on a 1920x1080 input.
- **The content crop is consistent.** `roi_top` is applied after scaling, as a fraction of the scaled height. At 1080p that is 54 of 360 rows, the same proportion as 162 of 1080; rounding differs by at most one row.
- **The grey levels mean the same as before.** FFmpeg's `gray` output is full range and matches the old luma within 1 level, so the zone threshold (8.0 grey levels) and the edge threshold (50) are in the same units. What changes is the spatial scale they are applied at, and the contract does not spell that out (P3-1):
  - area averaging keeps block means, so a zone's mean difference can stay the same or shrink;
  - thin strokes of 1–2 px lose contrast at one third of the width, so the edge density changes.

  The contract does say "Scaling can change which samples score above the threshold", and AC03 measures the effect: on the real meeting, low_score discards went from 9246 to 9294.
- **Odd sizes are handled.** Heights are rounded (1366x768 becomes 640x360). Odd sizes such as 641x480 work, and grey has no chroma subsampling to worry about.
- **Recordings 640 wide or narrower are not scaled.** swscale only converts them to grey, and the values match the old path within 1 level.
- **PyAV 14 is not verified.** `interpolation="AREA"` works on 18.1. The declared floor, PyAV 14, cannot be checked without the network, and CI does not run the Python suite (P3-2).

**2. Tests**

- **The new test can fail for the right reason.** The mutation above shows it for the width, and the 1280x720 check would fail if the kept frame came from the small copy.
- **Its slide-order assertion does not tell full size from small size.** It is a regression guard, not the discriminating part. That is acceptable, because AC01 claims only a failure "if the copy is taken at full size".
- **The older tests still exercise what they claim.** The 320x240 fixtures now go through the grey reformat without scaling. The crop test still discriminates (mutation above). The tie-break and pool tests mock `composite_score` and are unaffected. The diff only adds lines, so the earlier tests are unchanged.
- **One gap:** no test pins down that the pre-budget duplicate check uses the full sample on a recording wider than 640. The contract does not claim it, so it is not a defect (P3-3).

**3. Evidence**

- **The before/after numbers are consistent with each other.** Duration and sample count match; the candidate and discard counts add up; 21 + 13 = 34 frames, which matches the review folder.
- **The unmatched frames are stated plainly,** with timestamps and the best SSIM of each. On the before side, 15 of the 21 unmatched frames are in the first 90 s; on the after side, 10 of the 13. So "most in the first 90 seconds" holds.
- **The cross-match method is described but not fully verifiable.** It compares grey copies 640 wide, content area only, and only against frames within 10 minutes. That window is narrower than the contract's wording ("among the other version's frames"); a narrower search can only lower the match counts, so it is conservative. The script is not committed (P3-4).
- **Timing:** see P2-1 and P3-5.

**4. Scope**

- All 6 changed files are inside the declared surfaces.
- No frames, media or meeting text are committed.
- The full frame sets are recorded as deleted. 34 frames remain outside any repository, for the owner to look at.

## Findings

**P0:** none. **P1:** none.

**P2-1: a cited number is not in the source it cites.** `real-recording-run.txt` says the current code "took 2189 s and 2226 s in two earlier runs today (WI07 evidence)". The WI07 evidence at `1cf4699` records only one timing, 2226 s. It mentions a second extraction but gives no time for it, and "2189" appears in no committed file on any ref except this evidence file.

- **Consequence:** the committed record contains a figure nothing backs. The speedup conclusion does not depend on it, because this work item measured 1667 s itself.
- **Fix:** cite the actual source or drop the figure. This does not reopen the cycle.

**P3 (known limitations, do not reopen the cycle)**

- **P3-1: the thresholds are applied at a new scale.** The ported thresholds now apply at about one third of the width. Grey levels mean the same, but the spatial scale differs, and the contract does not say so explicitly. The only check is one real meeting.
- **P3-2: the PyAV floor is not exercised.** `av>=14` is untested for `reformat(..., interpolation="AREA")`, no Python CI job exists, and the spelling is case-sensitive.
- **P3-3: the duplicate check is untested above 640.** No test shows that the pre-budget duplicate check on a recording wider than 640 uses the full sample and not the small copy.
- **P3-4: the cross-match script is not committed.** The 60 and 62 figures rest on the executor's word, supported by the consistent counts.
- **P3-5: the timings are noisy.** Each figure comes from a single run on a noisy machine: the same code took 1667 s and 2226 s. The evidence did not say whether the before and after runs were sequential or concurrent. The speedup, about 5x, is large enough that this does not change the conclusion.
- **P3-6: the "reading" line is loosely worded.**
  - It calls the unmatched frames "kept by only one version", yet several pair up at about the same moment with an SSIM of 0.74–0.93: for example before 0:06 and after 0:07, both 0.86.
  - Its list of "the rest" includes frames inside the first 90 s: 0:44, 1:00, 1:12 and 1:18.
  - The exact lists above that line are correct.
- **P3-7: "the decoder scales" is loose wording.** The contract and the docstring say the decoder does the scaling. It is libswscale, called through `frame.reformat` after decoding. The behaviour is correct.
- **P3-8: the owner's look at the frames is not recorded.** That is fine under D-175, which asks which frames are gained or lost. The evidence gives them by timestamp and does not judge their content.

## Simpler mechanism?

None found. Taking the Y plane in numpy and averaging it down would need its own range and scaling code. One `reformat` call to grey at 640 wide is the simplest way to keep the same guarantee.

## Verdict

**Approve with the listed limitations** (P2-1, P3-1 to P3-8). No P0 or P1.

## Correction after the review (executor)

P2-1 and P3-5 are fixed in the evidence text alone. `real-recording-run.txt` now says:

- the 2226 s run is the one in the WI07 evidence;
- the 2189 s run happened earlier the same day, and its record was not kept;
- the before and after runs here were sequential.

P3-6 is fixed in the "reading" line. It now says:

- many unmatched frames pair up with a frame of the other version about a second away;
- 15 of the 21 before-side and 10 of the 13 after-side frames are in the first 90 seconds;
- the list of frames after 90 seconds is exact.

No code changed after the review. The other P3 items stay as known limitations.
