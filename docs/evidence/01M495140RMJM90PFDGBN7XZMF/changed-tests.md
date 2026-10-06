# WI24: existing tests that changed, and the rule that changed each

WI24-AC05: every test that existed before passes, or is named here with the
rule of this work item that changed it. Base: `3c7b458` (the work item's
contract and plan on `main`'s `bde64df`). `git diff 3c7b458 -- tests/` shows every change; apart from the one
below, the changes to the existing test files only add tests, helpers and imports.

One test changed, and one assertion in it:

| Test | What changed |
|---|---|
| `test_summary.WritingTest.test_one_request_carries_everything_and_the_summary_is_written_next_to_the_frames` | It asserted that the summary's request held the reading's block as the reading wrote it, `[FRAME 1]\n- Key Data: total 1.250`. The rule of WI24 (WI24-AC03) is that each block of the reading is labelled in the request with its frame's exact file name, so the assertion is now `[frame_001_t00-01-22.jpg]\n- Key Data: total 1.250`: the same block, the same content, with the label the rule gives it. Nothing else in the test changed. |

Not tests, but changed with them:

- The message `transcript.no_timed_line` (the list of messages, in both languages) named the two forms the
  application read, "Teams 'Speaker   M:SS' or '[HH:MM:SS]'"; it now names the third, a time alone on its line. No test
  pinned its text (`tests/test_texts.py` checks the list's structure, which holds).
- `qa.needs_speakers` is a new message in both languages.
- The existing test `test_summary.NamedFramesTest.test_a_retry_stopped_by_the_budget_says_why_the_answer_before_was_refused`
  computes the worst case of a request as `len(prompt) / CHARS_PER_TOKEN`; the request now reserves the retry's note
  (`RETRY_NOTE_CHARS`) too, so the real worst case is a little higher. The test did not change and passes: its budget
  leaves a margin of half a request's cost, far more than the note's.
- The register's entries `WI05-P3-2` and `WI05-P3-3` (the BOM, and the tab, the "  10:30" spoken line, the curly
  apostrophe and the filler) still reproduce after the parser change, and keep their state `open`. No entry of the
  register changed state.

The tests of the work item are new: `tests/test_frames.py` (`TranscriptTest`: the time alone on its line in a Word file and in
a text file, the two readers, what is not a time), `tests/test_summary.py` (`NoSpeakerTest`, `FrameLabelsTest`),
`tests/test_qa.py` (`RequestTest`: the register refused in both languages) and `tests/test_app.py` (`RunningStageTest`).
