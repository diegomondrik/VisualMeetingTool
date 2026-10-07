# WI27: existing tests that changed, and the rule that changed each

WI27-AC04: every test that existed before passes, or is named here with the rule of this work item that changed it.
Base: `5aa47ad` (the work item's contract and plan, on `f1bde92`, main). `git diff 5aa47ad -- tests/` shows the
changes.

**No test that existed before changed.** Every assertion of every earlier test is as it was, and all of them pass.
The only edit to an existing line of `tests/test_summary.py` is `import hashlib` among the module's imports, which the
new class uses.

The new tests, all in `tests/test_summary.py`, class `FrameListTest` (needs nothing outside this repository, so the CI
runs it). The class writes five small real images in the frames folder, because one of the tests builds the report.

WI27-AC01, a list of whole frame names in one pair of brackets is taken:

- `test_the_line_of_the_owners_meeting_is_saved_with_one_pair_of_brackets_for_each_frame`: the line of the owner's
  meeting ("- **Outlier Treatment Mechanics** [frame_029_t00-23-24.jpg, frame_037_t00-31-24.jpg]: ...") through
  `write_summary`: one request, and `summary.md` holds one pair for each frame.
- `test_three_names_are_three_pairs_in_the_same_order`: three names, with commas and with "y" last; the order is the
  order written.
- `test_a_comma_a_semicolon_y_e_and_and_a_comma_before_them_separate_the_names`: every separator the contract lists,
  with and without spaces, in capitals, with tabs and a non-breaking space.
- `test_spaces_inside_the_brackets_are_taken`.
- `test_names_in_backticks_or_bold_are_taken_as_a_single_name_is`: with each of the marks a single name accepts, the
  mark goes round each name; a mark not closed round the list is left where it was.
- `test_the_report_built_from_a_summary_with_a_list_shows_both_frames`: the summary written by `write_summary` goes
  through `build_report`, and the two images are in the Word document, in order (before, a list would have left both
  out of the report).
- `test_the_summary_and_the_report_agree_on_every_list_once_it_is_rewritten`: the summary's check and the report's
  (`cited_frames`) accept the same rewritten text and read the same names (as `test_the_summary_and_the_report_agree_on_every_case`
  does for the cases of WI13).

WI27-AC02, everything else is judged as before:

- `test_a_list_with_a_name_that_does_not_exist_is_refused_naming_it`: `summary.frames_missing`, naming only the
  missing one.
- `test_a_list_with_an_item_that_is_not_a_whole_frame_name_is_refused`: words, a number alone, a name without its
  extension or with another, trailing or leading commas, a separator with nothing after it, two names with no
  separator: the text is not changed and is refused as `summary.frame_unbracketed`.
- `test_a_range_inside_one_pair_is_not_split_and_is_still_refused`: "a", "to", "al", "hasta", "through", "until",
  "–", "—", "-", "--", "..", "...", "…", "->", "→", with and without spaces: not changed, and refused as
  `summary.frame_range` or `summary.frame_unbracketed`.
- `test_a_range_written_next_to_a_list_is_still_a_range`: "[a, b] a [c]", "[a] to [b, c]", "[a, b] - [c]".
- `test_a_frame_named_without_brackets_is_still_refused`.
- `test_a_single_name_and_everything_accepted_before_comes_out_byte_for_byte_the_same`: a single name (plain, bold,
  backticks), the mentions the earlier tests accept (`NOT_RANGES` and others) and the ones they refuse (`RANGES`)
  come out of `separate_frames` unchanged; the accepted ones also come out of `check_summary` unchanged.
- `test_a_list_already_rewritten_is_not_changed_again`.

WI27-AC03, the retry says why:

- `test_a_range_then_a_good_answer_is_delivered_and_the_retry_says_why`: the second request carries the note (what was
  refused, with the text, and to name each frame in its own brackets); the first has none; the second is the first
  plus the note, before the material.
- `test_a_range_inside_one_pair_then_a_good_answer_is_delivered_and_the_retry_says_why`: "[a – b]" is refused as a
  frame without its own brackets, and the note says so.
- `test_a_frame_without_brackets_then_a_good_answer_is_delivered_and_the_retry_says_why`.
- `test_two_answers_refused_for_how_a_frame_is_named_are_refused_and_nothing_is_written`: both refusals, twice:
  two requests, the refusal raised, no `summary.md`.
- `test_the_retry_names_every_reason_when_the_answer_had_a_range_and_an_empty_section` and
  `test_the_retry_names_every_reason_when_the_answer_had_no_key_points_and_a_frame_without_brackets`: with another
  refusal in the same answer the note lists both, numbered.
- `test_the_note_with_every_reason_at_its_longest_fits_what_the_budget_reserves`: the five reasons with a datum of
  5,000 characters, and every tail of the list, stay within `RETRY_NOTE_CHARS`.

The mutations (`mutations.py`, output in `mutations.txt`) each make these tests fail.
