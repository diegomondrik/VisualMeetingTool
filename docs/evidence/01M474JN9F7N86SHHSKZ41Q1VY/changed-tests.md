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

## The pilot's test, `tests/test_d1_final_de_la_reunion.py` (WI21-AC01)

Written by the criterion role in the pilot, red on main. It changes in two
lines, both because the product no longer has the names it used, and
nothing else: its slides, its transcript and its assertion are as they were.

| Line | What changed |
|---|---|
| `mock.patch.object(extract_module, "TRANSCRIPT_TAIL", 5.0)` | Now `..., 5.0, create=True`, with a one-line comment. `patch.object` raises `AttributeError` for a name the module does not have, and `TRANSCRIPT_TAIL` is gone with the cut. The patch now does nothing; if a cut comes back under that name, the test still shows it on its short video. |
| `{con.read_until}` in the failure message | Now `{getattr(con, 'read_until', None)}`. Python builds the message before the assertion runs, and `ExtractionResult` no longer has `read_until`. |

## Not changed, and why it still passes

- `test_a_sample_below_the_minimum_becomes_a_candidate_only_next_to_a_phrase`
  and the other transcript tests of `test_frames.py` are untouched: the
  boost works as before.
- Removed from the product with the cut: `TRANSCRIPT_TAIL`,
  `ExtractionResult.read_until` and `VisualReferences.last` (the summary
  module's `transcript.last` is another object, from `read_turns`). The
  mutations in `mutations.py` put back what each one needs.
