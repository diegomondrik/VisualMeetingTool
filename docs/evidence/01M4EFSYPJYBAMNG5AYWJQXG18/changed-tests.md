# WI33: existing tests that changed, and the rule that changed each

WI33-AC02/AC03: every test that existed before passes, or is named here with the rule of this work item that changed it.
Base: the installer's branch (WI18) brought up to date with main, `c4be853`. `git diff c4be853 -- tests/` shows the changes.

**One test that existed before changed.**

- `tests/test_packaging.py`, `InstallerTest.test_the_shortcuts_open_the_window_program` is now
  `test_the_shortcuts_open_the_window_program_and_the_user_manual`. It said that every line of the installer's `[Icons]`
  and `[Run]` opens `MeetingTool.exe`. WI33 adds one entry for the manual to each list (a Start menu shortcut and an
  unticked offer to open it at the end), so the rule is now: every line opens the program, except exactly one per list,
  which opens `manual\user-manual.html`. Nothing it protected is weaker: a shortcut that opens something else, a second
  manual entry or a missing one still fail.

New:

- `tests/test_packaging.py`: `test_the_user_manual_is_installed_next_to_the_program_and_offered_unticked` (the `[Files]`
  line, its source and destination; the offer is `postinstall skipifsilent unchecked shellexec`; the manual's name and the
  offer's text exist in Spanish and in English).
- `tests/test_user_manual.py`, `StructureTest` (WI33-AC01): a whole English page that needs nothing from outside (no
  script, frame, image, outside file or link; no style that reaches the network); every link of the page has its place and
  no id is repeated; the sections are numbered in order and each is in the contents; it covers what a first-time installer
  has to do; it follows the theme, has a viewport and prints.
- `tests/test_user_manual.py`, `ItIsTrueTest` (WI33-AC03): every name of a screen, field, button or setting that the
  manual quotes is, exactly, a text of the program's English catalogue; the default ceiling, the upload limits, the logo's
  limit and the file types are the code's; the data folder, the log and the program's folder are the ones the program and
  the installer use; no price is quoted and the ceiling is called an estimate, "not a guarantee".

The first draft of the manual quoted the field of the ceiling by its old name; `ItIsTrueTest` failed on it (WI28 renamed
it "Estimated spending ceiling in dollars"), and the manual was corrected, including what it says about a request already
sent being paid and a run stopping when an answer costs more than estimated.

## After the independent review

No other test that existed before changed. Added in `tests/test_user_manual.py`:

- `test_every_name_the_page_marks_is_exactly_the_text_of_the_key_it_names`: each of the 42 names the manual marks with
  `data-ui="<key>"` equals, exactly, that text of the program's English catalogue. It replaces trusting a list kept by hand.
- In `test_the_numbers_it_gives_are_the_code_s`: the largest ceiling is read from `jobs.check_request` and checked
  against the form (`pages.py`) and the manual ("above 0 and up to 5").
- In `test_the_places_it_names_are_the_ones_the_program_uses`: the log's place comes from `window.log_dir()` and
  `window.LOG_NAME`, not from a fixed text.

`mutations.txt` has 18 mutations, all detected, including a mutation of the largest ceiling and one that points a marked
name at another text of the program.
