# WI30: existing tests that changed, and the rule that changed each

WI30-AC03: every test that existed before passes, or is named here with the rule of this work item that changed it.
Base: `bcf2e7f` (the work item's contract and plan, on `1a78ce4`, main). `git diff bcf2e7f -- tests/` shows the
changes.

**No test that existed before changed.** Every assertion of every earlier test is as it was, and the modules that
exercise the screens and the files (`tests.test_app` `ScreensTest`, `IsolationTest` and `CompanyTest`,
`tests.test_projects`, `tests.test_data_integrity`, `tests.test_cli`) pass.

The new tests are all in `tests/test_library_reads.py` (needs nothing outside this repository, so the CI runs it).
The reads are counted as the review counted them: `Path.read_text` is wrapped (it still reads and returns what it
returned) and every call on a `summary.md` is noted; `builtins.open` is wrapped the same way for the `meeting.json`
records.

Class `LibraryReadsTest`, through the library functions:

WI30-AC01, what is read:

- `test_serving_the_report_or_an_image_of_one_of_twelve_meetings_reads_no_summary`: 12 meetings with a result each
  (the review's own case); `meeting_file` for a frame and for the report reads no `summary.md` and opens one
  `meeting.json`, the meeting's own.
- `test_the_meeting_page_reads_only_its_own_summary_and_record`: `meeting` reads the meeting's own `summary.md` and
  one `meeting.json`, and returns the same record and result as before.
- `test_the_reads_do_not_grow_with_the_number_of_meetings`: 12 and 30 meetings read the same (0 summaries and 2
  records for two files; 1 and 1 for the page).
- `test_serving_a_file_of_a_loose_result_reads_no_summary_and_the_page_reads_its_own` and
  `test_the_reads_of_a_loose_result_do_not_grow_with_the_number_of_loose_results`: the same for 12 and 30 loose
  results.

WI30-AC02, another meeting's trouble, what is still not found, what is served and listed as before:

- `test_a_broken_record_or_summary_of_another_meeting_does_not_stop_a_sound_one`: one meeting's `meeting.json` is
  not JSON and another's `summary.md` is not UTF-8; a sound meeting's page and files are served.
- `test_a_meeting_whose_record_cannot_be_read_is_not_found_and_one_whose_summary_is_not_text_has_its_files`: the one
  with the unreadable record is "not found"; the one whose summary is not text still has its frames and report.
- `test_a_record_missing_a_field_is_unreadable_as_it_is_for_the_project_page`: the same fields are required as in
  `list_meetings` (the record is read by the same function).
- `test_a_broken_loose_result_does_not_stop_a_sound_one`.
- `test_an_unknown_or_ill_formed_identifier_is_not_found`: "..", ".", "A B", "x/y", "x\y", "", capitals, doubled or
  edge hyphens, an accent, a number, `None`, and names that would reach a real meeting if they were used as a path
  ("../meetings/<id>", "x/../<id>", the id in capitals, with "/", " " or "." at the end): `NotFound` from
  `meeting_record`, `meeting` and `meeting_file`.
- `test_a_record_found_in_a_folder_that_is_not_called_as_its_id_is_not_found`.
- `test_a_record_whose_own_id_is_not_a_slug_is_not_reached_by_that_name`: the name is checked before the path is
  built, not only against the record's id.
- `test_an_unknown_or_ill_formed_loose_name_is_not_found` and
  `test_a_folder_with_a_project_record_is_not_a_loose_result`: a folder with no summary, with a space or capitals, a
  project's folder, "../<name>", "<name>/".
- `test_the_paths_served_are_a_frame_or_the_report_of_the_results_folder_and_nothing_else`,
  `test_a_meeting_added_from_the_terminal_has_its_record_and_no_files` and
  `test_a_record_naming_a_folder_outside_its_results_is_not_followed`: the paths are as before.
- `test_the_project_page_lists_every_meeting_with_its_result_as_before`,
  `test_the_project_page_still_stops_on_a_broken_record_as_before` and
  `test_the_home_page_lists_every_loose_result_with_its_result_as_before`: `meetings` and `loose` list everything,
  in the same order and with the same results as listing the records and reading each result.

Class `ServerReadsTest`, through the running application (12 meetings and 12 loose results):

- `test_an_image_or_the_report_of_a_meeting_reads_no_summary_and_its_page_reads_one`,
  `test_an_image_of_a_loose_result_reads_no_summary_and_its_page_reads_one` and
  `test_opening_the_report_on_the_machine_reads_no_summary`.
- `test_a_broken_meeting_does_not_stop_the_others_and_is_itself_not_found`: 200 for the sound ones, 404 for the one
  with the unreadable record.
- `test_an_unknown_or_ill_formed_identifier_is_404`.

One behaviour changed on purpose, and no earlier test pinned it: a meeting whose `meeting.json` cannot be read, asked
for by its own address, is now "not found" (404); it was an error page (400) naming the file, because the whole list
was read to find it. The project page, which lists every meeting, still stops with that error naming the file
(`test_the_project_page_still_stops_on_a_broken_record_as_before`).

The mutations (`mutations.py`, output in `mutations.txt`) each make these tests fail.

## After the independent review (P2-1, P3-2)

No test that existed before changed. The review found that on a disk that ignores case (Windows) a loose result whose
folder is called `Con-Mayuscula`, which the home page does not list, was served by `con-mayuscula`: the name was
checked as a slug but not against the folder's own name. `library._loose_folder` now also requires the name to be one
of `os.listdir(data_dir)` (names only; no summary is read, so WI30-AC01 stands). And `store.read_meeting` refuses an
empty identifier, which was its own slug and built `meetings/meeting.json`.

- `test_an_unknown_or_ill_formed_loose_name_is_not_found` (existing, only a name added to its list of bad ones):
  `"con-mayuscula"`, the lower-case spelling of a folder that is not listed. On a disk that tells cases apart it passes
  without the fix; the CI runs on Windows, where it does not.
- `test_an_empty_identifier_is_not_a_meeting_even_with_a_record_in_the_meetings_folder_itself` (new).

`mutations.txt` now has nine mutations: two new (the name looked up on disk; the empty identifier), and the one about
the loose name's slug removes the slug check and the lookup together, since each alone is covered by the other. The
review's P2-2 (a broken record asked for by its address answered 404, hiding the damage) was decided on 2026-10-08 as
the review proposed: `library.meeting_record` no longer turns the `ProjectError` into `NotFound`, so a meeting whose
`meeting.json` cannot be read, asked for by its address, is answered 400 with the error that names the file, as the
project page already does; a sound neighbour is still served, since only the record asked for is read. Three tests of
`tests/test_library_reads.py` (all new in this work item) changed their expectation from `NotFound`/404 to
`ProjectError`/400 and were renamed; no test that existed before is touched. There is one behaviour change left to
declare (the meeting is found by the name of its folder), not two.
