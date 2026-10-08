# WI29: existing tests that changed, and the rule that changed each

WI29-AC03: every test that existed before passes, or is named here with the rule of this work item that changed it.
Base: `ede5e4b` (the work item's contract and plan, on `1a78ce4`, main). `git diff ede5e4b -- tests/` shows the
changes.

**No test that existed before changed.** The only change to the tests is a new module, `tests/test_word_package_limits.py`.
The modules that read Word packages (`test_frames`, `test_report`, `test_template_filter`, `test_allowed_fields`,
`test_markup_compatibility`, `test_transcript_encodings`, `test_texts`, `test_d1_r02_plantilla`, `test_qa`,
`test_summary`) pass as they were. `test_texts` checks the new messages (both languages, the same data, each used).

The new tests build their packages at test time (a ZIP of repetitive bytes, kilobytes on disk, tens or hundreds of
megabytes once expanded) and commit none. The module takes about 9 seconds, most of it making the packages.

`LimitsTest`, WI29-AC01, through `meetingtool.word_package.read_parts`:

- `test_the_limits_are_the_contract_s`: 4,000 entries, 32 MB, 256 MB, written in the test and not taken from the product.
- `test_a_package_within_the_limits_is_read_whole`: the example template reads as it is; a package of exactly 4,000
  entries is read; asking for one part gives that part.
- `test_a_part_the_package_lacks_is_a_key_error_as_before`.
- `test_more_entries_than_the_limit_are_refused_before_reading_anything`: 4,002 entries; no part is opened; the message
  in both languages.
- `test_a_part_over_the_limit_is_refused_naming_the_part`: WI22-P3-2's case, under 1 MB on disk and 40 MB expanded.
- `test_parts_each_within_the_limit_that_together_are_over_it_are_refused`: nine parts of 30 MB; the message names the
  part where the total was passed.
- `test_the_refusal_stops_reading_at_the_limit`: of a part of 100 MB, no more than the limit and a chunk is
  decompressed (counted at `ZipExtFile.read`), and `tracemalloc`'s peak stays under twice the limit.
- `test_the_review_s_case_is_read`: a DOCX under 10 KB whose document.xml expands to about 5,000,000 characters is read
  by `read_turns`, as a transcript.

`CallersTest`, WI29-AC01, each of the three readers:

- `test_a_word_transcript_over_a_limit_is_refused`: entries and a part (the transcript reads one part only, so the total
  cannot be passed there); `transcript.word_too_big`.
- `test_a_template_over_a_limit_is_refused`: entries, a part, the total; `report.template_too_big`.
- `test_a_report_over_a_limit_is_not_delivered`: `check_active_content`; `report.too_big`.
- `test_the_example_template_and_a_clean_report_are_read_as_before`.

`DirectoryTest`, WI29-AC02:

- `test_a_directory_that_states_less_than_the_part_holds_does_not_get_it_read`: a part of 40 MB whose directory (central
  and local) says 100 bytes is not returned. Python's `zipfile` stops at the stated size and raises `BadZipFile` for the
  checksum, so the refusal is that error (and, for a transcript, `word_unreadable`), not the limit's message.
- `test_a_directory_that_states_more_than_the_limit_does_not_refuse_what_is_small`: a part of 1 KB whose directory says
  40 MB is read. This is the test that shows the limit is counted and not taken from `ZipInfo.file_size`.

The mutations (`mutations.py`, output in `mutations.txt`) each make these tests fail.
