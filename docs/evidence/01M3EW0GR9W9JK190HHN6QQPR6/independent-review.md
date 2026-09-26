# Independent review: WI10 (01M3EW0GR9W9JK190HHN6QQPR6), camera close-ups and the end of the meeting

**Reviewer:** revisor-independiente (Claude Opus 5.5), read-only. **Date:** 2026-09-26.
**Branch:** `work-item/01M3EW0GR9W9JK190HHN6QQPR6-camera-and-end` at `c4fb464` (`efbca74`, `c4fb464` on `main` `69944af`).

## What I read

- The D-176 section of `OWNER_DECISIONS_FULL.md`.
- The full branch diff: `contract.yaml`, `plan.yaml`, `extract.py` (the whole function at `efbca74`), `signals.py`, `transcript.py` (`read_blocks`/`VisualReferences`), `__main__.py`, `test_frames.py`, and the three evidence files.
- `wi09-frames/frames_read.md` and the names of the frame files. To test the threshold claim, I read the 75 JPEGs where they sit and computed two numbers per frame in memory. Nothing was copied or written, and I printed only numbers.
- The header and section layout of the WI08 review.

## What I ran

All runs were in a `--no-hardlinks` clone at `C:/Users/Diego/AppData/Local/Temp/wi10-review-258093861`, checked out at `efbca74`.

| Check | Result |
|---|---|
| `python -m unittest discover -s tests` | 112 tests, OK. This matches `local-test-run.txt`: 112 tests `ok`, `tested_commit` is the full hash of `efbca74`. |
| Mutations M1–M5 from `mutations.txt` (check removed, always true, density only, share only, `or`) | All fail: 1 / 6 / 5 / 1 / 6 failures, the same counts the file records. |
| M6 (stop removed, the whole `if` replaced) | Fails, with 2 failures instead of the recorded 1, because the CLI test also fails. This is a different way of removing the stop, not a disagreement. |
| Extra: camera check moved after the `candidate_times`/`last_candidate` update | Fails. |
| Extra: `last = min(...)` instead of `max` | Fails. |
| Extra: `read_until` never set | Fails. |
| Extra: camera reason removed from the log | Fails. |
| Extra: density threshold changed to 0.05 | Fails. |
| Extra: `>=` instead of `>` at the stop | Passes (harmless boundary). |
| Extra: share threshold changed to 0.5 | Passes. See P3-3. |
| `git diff 69944af efbca74 -- tests/test_frames.py` | 61 lines added, 0 removed (AC03). |
| `git diff efbca74 c4fb464 -- meetingtool tests .ingol` | Empty. |
| `git diff --name-only 69944af c4fb464` | 10 files, all inside `affected_surfaces`. No image, video or docx. `git diff --check` is clean. |
| Evidence arithmetic | Checked item by item below. |
| Measuring the thresholds on the 75 kept frames of D-174 | Content area, resized to 640x360 with Lanczos, box or bilinear, plus 3 more variants. Results below. |

Evidence arithmetic, item by item:
- `14035 − 1 − 9294 − 3950 = 790` candidates, `790 − 715 = 75` kept.
- `9987 − 1 − 151 − 5695 − 3450 = 690` candidates, `690 − 632 = 58` kept.
- Samples: `9987 = 2·4993 + 1` and `14035 = 2·7017 + 1`.
- `4993 = 4873 + 120`, and `4873 s = 1:21:13`.
- Fewer samples: 29% (28.8). Less time: 19% (19.1).
- `75 = 59 + 16`, and 16 camera + 9 gallery + 50 screen add up.
- Gemini's content types give 25 video-call frames, and the unmatched times (frames 003–018) are exactly the 16 close-ups of one speaker.
- The frame at `1:34` is `t00-01-34` (m:ss, 94 s), so the gallery pairing and the discard log line are possible.
- Main kept nothing after `1:19:50`, so cutting the tail lost no kept frame.

## Answers to the requested checks

- **The stop matches D-176.**
  - `last = max(starts)` handles blocks in any order. `read_blocks` already sorts, and it raises `TranscriptError` when there is no timed line, so `last` is never `None` on the `from_file` path.
  - If the last line is at 0, only the first 120 s are read.
  - If the last line is past the end of the recording, nothing breaks, `read_until` stays `None` and no CLI line is printed. That is correct.
  - The break runs before the interval check, so reading stops at the first decoded frame after `stop_at`. The counts are right, and the test's `samples <= 19` pins this.
- **The camera check matches D-176.**
  - It runs after `low_score` and before any candidate bookkeeping. `prev_gray` is already updated, so the first screen after a camera stretch scores as a large change.
  - Because camera samples do not set `last_candidate`, `min_gap` stops blocking the samples right after them (minimum_gap discards went from 3950 to 3450).
  - Because camera samples stay out of `candidate_times`, the temporal score stays high through camera stretches. That costs only a cheap check per sample: 151 camera discards.
  - Because camera samples do not update `last_distinct_gray`, a gallery on either side of a camera stretch is deduplicated. That explains the 59/58 difference, and it is the intended behaviour.
- **What D-176 excludes is respected:** no gallery filter, no still-screen minimum, no stricter duplicate check, and the transcript does not choose frames.

## Findings

**P0:** none. **P1:** none.

**P2-1: the stated margins cannot be reproduced, and they overstate the separation.**
- The contract and the `is_camera_view` docstring say: "camera views at most 0.021 and 0.14, screens at least 0.031 and 0.35". No measurement script and no per-frame table is committed.
- On the same 75 frames, with the repo's `to_gray` and the same 640x360 content crop, none of my six preprocessing variants gives those numbers.
- With the box filter I get:
  - camera: up to 0.022 density and 0.142 share;
  - screens: down to 0.020 density (the title card, frame 1) and 0.153 share (frame 31, a desktop wallpaper of a seascape).
- Each measure alone therefore puts one screen on the camera side. The separation holds only because both measures must agree. The closest screen is frame 31 at density 0.031–0.034 against a threshold of 0.028, and camera frames reach 0.024 with Lanczos.
- The code is right, and the real run proves no screen was lost on this meeting. What is wrong is the documented margin.
- Consequence: anyone who later retunes the thresholds starts from a margin that does not exist.
- Fix: correct the numbers, or commit the measurement.

**P2-2: two real risks are missing from the contract's "not done" list.**
- **(a) Full-screen photographs, shared video and image-heavy slides.**
  - Frame 31 shows this case is real: a photo sits at camera-like share and survives on density by 0.004, only because of the taskbar and a participant overlay.
  - Removing the downscale misclassifies 3 screens (31, 37, 38; 37 and 38 are dark-theme Excel), so the thresholds depend on scale.
  - The dark/sparse-slide risk is not written anywhere in the contract either. Only a test comment mentions photographs.
- **(b) A transcript that ends early by mistake.**
  - Transcription can be stopped, or a wrong or partial file passed.
  - Everything after the last line plus 120 s is then silently never read. The only signal is one CLI line.
  - D-176 chose this behaviour, so it does not block, but the loss is silent and should be written down as a limitation.
  - I am not sure whether Teams transcript times count from the start of the recording or from the start of transcription. If from transcription, any offset over 120 s cuts real content, and the boost already depends on the same alignment.

**P3 (known limitations, do not reopen the cycle)**
- **P3-1: the "camera" class is really one sample.** All 16 close-ups are the same speaker against the same outdoor background, within 90 s. Other people or backgrounds (bookshelves, sharp virtual backgrounds) may pass the check. That failure is benign: the frame is kept, as before. D-176 already leaves validation on a second meeting pending.
- **P3-2: the thresholds were measured on a different image from the one the code checks.** They come from saved JPEGs (1280x720, q85) resized to 640. The code checks the decoder's AREA-scaled grey from the 1080p source. That was not measured on the actual input, and the real run is the only end-to-end confirmation. The synthetic tests are 320x240, below the width at which frames get scaled.
- **P3-3: the share threshold is not pinned by any test.** Changing it to 0.5 passes the suite. The density threshold is pinned.
- **P3-4: the transcript-raised counts are identical in both runs (506/441)** even though there are 100 fewer candidates. That is plausible if no reference phrase falls near the first 94 s or after 4993 s. I cannot check it without the recording.
- **P3-5: small differences in the numbers.** `mutations.txt` records 1 failure for M6, and my variant gives 2. The contract says "36 minutes" and the evidence says "35 minutes" for the same 35 min 44 s.

## Simpler mechanism?

None that keeps the same guarantee. Mutations M3 and M4 show that either measure alone loses a screen. The stop is already one comparison.

## Verdict

**Approved with limitations** (P2-1, P2-2, P3-1 to P3-5). No P0 or P1. I recommend fixing the P2-1 numbers in the docstring and contract, and adding P2-2 (a) and (b) to the stated limitations before the PR. Neither needs a code change.

## Correction check

**Reviewer:** revisor-independiente (Claude Opus 5.5), read-only. **Date:** 2026-09-26. **Commit:** `e1e4acb` on `c4fb464`.

- **`git diff c4fb464 e1e4acb`:** changes 3 files, all inside `affected_surfaces`: `contract.yaml`, `signals.py` and the new `thresholds-measured.txt`. `git diff --check` is clean.
- **`git diff efbca74 e1e4acb -- meetingtool tests`:** only the `is_camera_view` docstring changes. No logic, threshold or test changes, so the real-meeting run of `efbca74` still stands.
- **`thresholds-measured.txt`:** 75 rows, each classed as screen, gallery or camera, matching the counts from Gemini's reading (50, 9, 16).
  - I recomputed the "camera by the code" column from each row's density and share against 0.028 and 0.25: no mismatches. Exactly frames 03–18 are called camera.
  - The per-kind ranges in the table match its own summary lines: camera 0.0179–0.0219 and 0.129–0.142; screen 0.0199–0.1077 and 0.153–0.744.
  - These values equal my box-filter measurement to the third decimal (camera up to 0.022 and 0.142; frame 31 at 0.032 and 0.153; frame 1 at 0.020 and 0.744).
- **Numbers cited in the docstring and contract match the table:**
  - "camera at most 0.022 and 0.142" matches 0.0219 and 0.142.
  - "photograph passed on density by 0.004" matches frame 31: 0.0324 − 0.028.
  - "dark-theme Excel on share by 0.05" matches frame 37: 0.301 − 0.25.
  - "every screen past at least one threshold, neither alone separates" is borne out by frames 1 and 31.
- **P2-2 (a) and (b), P3-1 to P3-3:** now stated in the contract's "Known limitations" paragraph (photo, video and dark screen; transcript ending early or offset in time; one meeting and one speaker; measured on saved frames, not the decoder's copy; share threshold not pinned by a test).
- **P3-5:** fixed; both documents now say 35 minutes.
- **P3-4:** not addressed (the transcript-raised counts are identical in both runs). It is a note that does not need to be addressed.
- **`local-test-run.txt`:** names `tested_commit` `e1e4acb2953098468669611753b07f961b526160`, and its `tested_tree` equals `git rev-parse e1e4acb^{tree}`. It shows 112 tests `ok`, "Ran 112 tests", `OK`, exit code 0. It must be committed before the PR, as AC05 and D-163 require.

**Final verdict: approved with limitations.** P2-1 is fixed. P2-2 and P3-1 to P3-5 are the known limitations of this work item. No P0 or P1.
