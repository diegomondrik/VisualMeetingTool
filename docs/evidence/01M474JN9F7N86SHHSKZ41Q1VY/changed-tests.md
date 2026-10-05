# WI21: existing tests that changed, and the rule that changed each

WI21-AC05: every test that existed before passes, or is named here with the
rule of this work item that changed it. Base: `bc24f89` (main with WI20).
`git diff bc24f89 -- tests/` shows each change.

## The rule the owner approved on 2026-10-05

"With a transcript, extraction stops `TRANSCRIPT_TAIL` (120) seconds after
the transcript's last line starts" (WI10, INGOL D-176) became "the recording
is read to its end, with a transcript or without one" (the external review's
R05: a transcript says when each line starts, not when the meeting ends).
The terminal command no longer prints "read until".

## Tests of `tests/test_frames.py`, `MeetingRealityTest`

Both pinned the cut. They are replaced, not edited: a test of the old rule
cannot pass with the new one.

| Test | What changed |
|---|---|
| `test_with_a_transcript_reading_stops_soon_after_its_last_line` | Removed. It patched `TRANSCRIPT_TAIL` to 5 s and required `read_until == 9.0`, no candidate after 9 s, at most 19 samples. Replaced by `test_a_transcript_that_ends_early_does_not_shorten_the_reading`, `test_a_last_line_that_is_long_does_not_shorten_the_reading` and `test_a_transcript_whose_times_run_past_the_recording_does_not_change_the_reading` (WI21-AC02: samples, candidates and frames kept equal those without a transcript, on a 140 s recording whose last slide shows after the old stop time, with no patch of the constant), and by `test_a_transcript_that_ends_early_still_raises_the_candidates_next_to_its_phrases` (what the transcript still does). |
| `test_the_command_line_says_where_reading_stopped` | Removed. It ran the command with `TRANSCRIPT_TAIL = 5.0` and required the line "read until 6s of 30s: ...". Replaced by `test_the_command_line_reads_to_the_end_with_a_transcript_and_says_what_the_transcript_raised`: no "read until" in the output, the line about the candidates the transcript raised still there, and the first line (duration, samples, candidates, frames) the same as without a transcript. |

## Not changed, and why it still passes

- `tests/test_d1_final_de_la_reunion.py` (WI21-AC01) is unchanged. It patches
  `extract.TRANSCRIPT_TAIL` and puts `result.read_until` in its failure
  message, which Python builds before the assertion runs, so both names stay
  in `meetingtool/frames/extract.py`: the constant is no longer read and the
  field is always `None`. Removing them takes a change to that test, which
  the owner asked to leave as written.
- `test_a_sample_below_the_minimum_becomes_a_candidate_only_next_to_a_phrase`
  and the other transcript tests of `test_frames.py` are untouched: the
  boost works as before.
