# WI20: existing tests that changed, and the rule that changed each

WI20-AC09: every test that existed before passes, or is named here with the
rule of this work item that changed it. Base: `03b8573`. `git diff 03b8573 --
tests/test_app.py tests/test_summary.py tests/test_reading.py
tests/test_report.py tests/test_texts.py` shows each change.

## The rule the owner approved on 2026-10-05

"If a stage fails, nothing is left of the run" became "if a stage fails, the
meeting is not added; what was paid stays until the meeting is processed
again or the person discards it" (the external review's R03).

| Test | What changed |
|---|---|
| `test_app.Processing.assertNothingLeft` | Still asserts no meeting, no results folder and no upload. It now also asserts what stays in `processing/`: nothing when the run paid nothing (`kept=False`), exactly the failed run's folder holding an accepted paid answer when it did (`kept=True`). The old version asserted `processing/` was empty in every case. |
| `test_app.FailureTest.test_a_summary_refused_twice_stops_at_the_summary_and_says_what_was_spent` | `assertNothingLeft(job, kept=True)`: the reading was accepted and paid. |
| `test_app.FailureTest.test_a_report_that_cannot_be_built_stops_at_the_report` | `kept=True`: the reading and the summary were paid. |
| `test_app.FailureTest.test_a_meeting_that_cannot_be_recorded_leaves_no_folder` | `kept=True`. |
| `test_app.FailureTest.test_one_ceiling_covers_every_stage` | `kept=True`: the reading was paid before the summary was stopped by the ceiling. |
| `test_app.ReviewFixesTest.test_a_save_that_fails_half_way_leaves_no_meeting` | `kept=True`. |
| `test_app.ReviewFixesTest.test_a_name_taken_by_another_meeting_is_not_removed` | The other meeting's folder is still untouched (unchanged assertion); `processing/` now holds the failed run's own folder instead of nothing. |

The two failure tests that paid nothing (a recording that cannot be read, a
reading Gemini refuses) keep `assertNothingLeft(job)` and now also prove that
nothing is kept.

## The same request to Gemini is not paid twice (R03)

Each accepted paid answer is kept in the run's folder under the fingerprint of
the request. Tests that send the same request twice in the same folder, on
purpose, to exercise a different answer each time, would now get the kept
answer the second time; they drop it first.

| Test | What changed |
|---|---|
| `test_qa.Workspace.register` | Its rule was already "each run starts without the batches kept by the one before, unless the test is about them": it removed `qa-parts/`, and now `paid-answers/` too. Found by the suite in a fresh clone of `7252f74`, which failed 13 cases of `test_qa` once the register's parts were also kept by fingerprint (the correction of the review's P2-2). |
| `test_summary.Workspace.forget_paid` | New helper: removes `paid-answers/` of the test's folder. |
| `test_summary.LanguageTypeKeyBudgetTest.test_a_meeting_type_adds_its_sections_and_they_are_required` | `forget_paid()` before the second, refused, summary. |
| `test_summary.LanguageTypeKeyBudgetTest.test_the_key_never_appears_in_any_output` | `forget_paid()` before each of its three runs; the check that no file holds the key now reads every file under the folder (`rglob`), the kept answers included. |
| `test_summary.KeyAndBudgetWithTypesTest.test_the_key_never_appears_with_a_type_and_a_language` | The same two changes. |
| `test_reading.KeyNeverShownTest.test_the_key_goes_only_in_the_header` | Reads every file under the folder (`rglob`): a folder (`paid-answers/`) made the old `iterdir` loop fail, and the kept answers are now checked for the key too. |
| `test_app.ProcessTest.test_the_summary_request_is_the_one_the_command_sends` | Removes `paid-answers/` from the copied folder: the test compares the request the command sends, and a kept answer would mean none is sent. |

## The data folder's lock (R01)

| Test | What changed |
|---|---|
| `test_report.TemplateInfoTest.test_remove_removes_the_record_too` | After removing the template, the data folder holds only `.meetingtool-write.lock`, the lock file every writer shares; before, it was empty. |

## The list of messages (WI17's checks)

| Test | What changed |
|---|---|
| `test_texts.OUTSIDE_RAISES` | `library.NotFound` raised in `meetingtool/app/jobs.py` (discarding a kept run that does not exist), never said: the server answers `app.not_found`, as for the two places already listed. |
| `test_texts.SCRIPT_TECHNICAL` | The page script's new technical strings: two class names (`hint kept`, `message`), an element (`span`), an attribute and its value (`role`, `status`) and the address `/api/kept/discard`. Every text a person reads comes from the list (`js.kept`, `js.discard`, `js.discard_confirm`, `js.discarded`). |
