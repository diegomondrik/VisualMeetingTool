# Independent review — work item 01M3CGKPVGGAAK06A1RD5C3XWZ (frame extraction)

Reviewer: `revisor-independiente` subagent, own context window, 2026-09-25.
Reviewed: commits `c38353c` and `3ba6ed2` on `main` `8f44a2c` (10 files).
Verdict: **approved for `independent_review`, no P0/P1.**

What the reviewer executed: the suite (28 tests, exit 0); `ingol audit
--work-item` (0 blocked); TP-06 by hand (the 10 files fall under the declared
surfaces, none under `controlled_by_content`); the **intersection with work 1
is empty** (`git diff --name-only` of each branch against the common base
`8f44a2c`); the numpy SSIM against an independent brute-force reference over
five sizes up to 612x1280, maximum difference 1.9e-14, and by reading, the same
definition as scikit-image's default including its border crop; nine mutations
of its own; a tie-break reproduction against the original; and a check that
no media file exists anywhere in the history of any branch and that the real
run left no frame, recording or log behind.

## Correction pass (one pass, per the review budget), commit `5f20bf7`

Applied after the review and **not re-reviewed**, as the budget allows:

| Finding | Correction | Proven by |
|---|---|---|
| P2-1: an undeclared change. Among equal scores at the budget cut, the pool dropped the earliest candidate; the original's stable sort keeps the earliest. Static frames often tie (0.3, 0.18), and the budget was active in the real run | The heap orders by `(score, -order)`, the reviewer's verified one-line fix: the later of equal scores leaves first | A test with scores 0.5, 0.5, 0.7 and budget 2 requires the frames at 1 s and 3 s, as the original; the mutation back to the old order turns it red |
| P3-3: the no-network test patches Python sockets only, and `av.open` also accepts URLs, which FFmpeg (native code) would open | The recording must be an existing local file, checked before `av.open` | A test requires `https://`, `rtmp://` and a missing path to be refused without `av.open` ever being called; the mutation removing the check turns it red |
| P3-4: the evidence stated the original kept 76 frames without a source | Source added to `real-recording-run.txt`: the count of JPEG files in the original MeetingTool's output folder for that recording | — |

The executor's final mutation run: **16 of 16 red** on `5f20bf7`. The real
recording was run again on `5f20bf7` (run 3 in `real-recording-run.txt`).

## Known limitations recorded from the review (do not reopen the cycle)

| ID | Finding |
|---|---|
| P3-1 | No test pins the port's numeric fidelity to the original: weights, thresholds, the duration source and which times count for coverage could change with the suite still green. AC02 does not require it; today the code matches the original on those points |
| P3-2 | Minor undeclared differences: duration comes from the container first and falls back to 0 (the original fell back to frames/fps); SSIM runs on the decoded JPEG's luma, not on the scaled image before encoding; a frame whose shape differs from the last kept one skips the comparison instead of rescaling; old frames are removed after the analysis, not before; the discard log is in English with UTC times |
| P3-5 | During a pool replacement, budget + 1 JPEGs coexist for an instant |
| P3-6 | The first sample never appears in the discard log (as in the original) |
| P3-7 | Only PyAV 18.1 was tested; the `av>=14` floor is not verified |
| — | A 41.6-minute recording takes about 10 minutes on the owner's machine (x64 Python emulated on ARM64); threaded decoding saved about 9% |
