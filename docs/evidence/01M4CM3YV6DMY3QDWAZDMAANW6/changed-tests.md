# WI28: existing tests that changed, and the rule that changed each

WI28-AC03: every test that existed before passes, or is named here with the rule of this work item that changed it.
Base: `46d92b1` (the work item's contract and plan, on `1a78ce4`, main). `git diff 46d92b1 -- tests/` shows the changes.

**No test that existed before changed.** Every assertion of every earlier test is as it was, and all of them pass; the
only file under `tests/` that changed is the new `tests/test_spending_estimate.py`. The answers the earlier tests' fake
service returns (`answer_for` of `test_reading`, `answer` of `test_summary`) cost less than the most their request was
estimated to cost, so none of them marks an overrun.

The new tests, all in `tests/test_spending_estimate.py` (they need nothing outside this repository, so the CI runs
them).

WI28-AC01, class `EstimateTest` (`call_checked` with a fake service):

- `test_the_reviews_case_the_answer_is_kept_and_the_next_request_is_not_sent`: the review's own case, an answer of
  800,000 input tokens (US$0.60) for a request estimated at US$0.10 and a ceiling of US$0.50. The answer is returned
  and kept; `counters["overrun"]` says what was estimated and what it cost; the next `call_checked` of the same counters
  raises `gemini.estimate_short` and the fake saw one request; the message names both amounts and the prices in the
  code.
- `test_an_answer_under_the_ceiling_but_over_its_estimate_stops_the_run_all_the_same`: the same with a ceiling of
  US$5.00, where the budget check alone would still allow the next request: it is the estimate that fell short that
  stops the run (this is the test that tells the real check from a comparison against the ceiling).
- `test_a_refused_answer_that_cost_more_than_estimated_is_not_retried`: the check refuses the first answer, which
  cost more than estimated: no second request, the error is `gemini.estimate_short` and names why the answer was
  refused, nothing is kept, and the answer is counted as paid.
- `test_a_retry_that_cost_more_than_estimated_is_returned_and_kept_and_stops_the_run`: a refused answer within its
  estimate, then a retry that overran and is accepted: it is returned and kept, and the run sends nothing more.
- `test_the_kept_answer_says_what_it_cost_and_the_same_request_again_pays_nothing`: the answer that overran is in
  `paid-answers` with its cost; the same request again, with new counters, takes it from there: no request, nothing
  spent, no overrun.
- `test_an_answer_at_its_estimate_or_under_it_changes_nothing`: an answer costing exactly the estimate, one token
  under and a split of the same tokens between answer and thinking: no overrun, and the three are sent.
- `test_one_token_more_than_the_estimate_is_an_overrun`: the other side of the same line (no tolerance is needed:
  the estimate and the cost come from the same function).
- `test_an_answer_with_no_usage_is_counted_at_its_estimate_and_is_not_an_overrun`: as before WI28.
- `test_every_run_starts_with_no_overrun`: `new_counters()` holds the key, `None`, and each call returns its own dict.

WI28-AC01, class `ReadingTest` (the reading's chunks):

- `test_the_chunk_after_an_answer_that_cost_more_than_estimated_is_not_sent`: five frames in chunks of two; the first
  answer overran: one request, `gemini.estimate_short`, `frames_read.md` not written, and the paid chunk is kept.
- `test_the_default_run_of_the_fake_never_trips_it`: the reading with the fake's usual answers sends its three
  requests.

WI28-AC01, class `StagesTest` (through the application's job):

- `test_a_later_stage_sends_nothing_and_the_page_says_why_and_the_next_run_pays_nothing_for_the_reading`: the
  reading's answer overran; the reading stage is done, the summary stage fails without sending anything, the job's
  error is the Spanish message with what it cost, the working folder is kept with the paid reading, and the same
  meeting processed again sends only the summary (the reading costs 0).
- `test_a_run_whose_answers_cost_what_was_estimated_goes_on_to_the_end`: the same job with ordinary answers is done.

WI28-AC02, class `WordingTest`:

- `test_the_form_the_run_page_and_the_message_call_it_estimated_in_each_language`: `app.new.ceiling`,
  `app.cost.total_html` and `js.spent` say "estimated" / "estimado"; the hint and the total say "list prices" /
  "precios de lista".
- `test_the_form_says_a_request_already_sent_is_paid_and_the_run_stops_when_an_answer_cost_more`: the hint, in both
  languages, says a request already sent is paid even if its answer is refused and that the run stops if an answer
  cost more than estimated; the run page's total says the first.
- `test_the_message_of_a_run_that_stopped_says_what_was_estimated_what_it_cost_and_what_was_not_sent`:
  `gemini.estimate_short` in each language holds the request not sent, the answer that overran, both amounts, the
  two price constants and that nothing more is sent.
- `test_no_text_about_the_ceiling_calls_it_a_guarantee`: the six texts about the ceiling, in both languages, say
  neither "guarantee" nor "garantía" nor "seguro".
- `test_the_readme_and_the_module_say_the_same`: the README's paragraph and the docstring of `gemini.py`.

The mutations (`mutations.py`, output in `mutations.txt`) each make these tests fail. The limitation `WI28-P3-1` is in
`docs/limitations/REGISTER.md`, reproduced by `python docs/limitations/reproduce.py WI28-P3-1`.
