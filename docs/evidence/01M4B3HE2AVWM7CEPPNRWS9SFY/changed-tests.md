# WI25: existing tests that changed, and the rule that changed each

WI25-AC04: every test that existed before passes, or is named here with the rule of this work item that changed it.
Base: `0f3aa55` (the work item's contract and plan, on `eff7ef7`, main). `git diff 0f3aa55 -- tests/` shows the
changes. The new tests are `EmptySectionTest` (in `tests/test_summary.py`), `YearsAndFiguresTest` (in
`tests/test_qa.py`), the new file `tests/test_d1_r04_resumen.py` (INGOL's `AR06ResumenVacio`) and
`TrazabilidadDelRegistro` (INGOL's, appended to `tests/test_d1_barrido.py`).

The rule that changed them: `qa.written_dates` keeps the year when it is written, so it returns `(day, month, year)`
and the year is `None` when the date has none (it returned `(day, month)`); and a date written with a year is
accepted only with a year the transcript or the meeting says. Three tests of WI14 held the old shape or a year no
transcript said. No assertion was weakened: each one asserts the same dates, now with their year, and the one that
accepted a date with a year gives the meeting the date the year came from.

| Test | What changed |
|---|---|
| `tests/test_qa.py` `DatesTest.test_written_dates_are_read_whatever_their_writing` | The expected set was `{(25, 9)}` for every writing. It is `{(25, 9, year)}` with the year each writing holds: `2026` for `25/09/2026` and `2026-09-25`, `None` for the others. It now also shows that the year is read where it is written. |
| `tests/test_qa.py` `DatesTest.test_a_day_said_in_words_is_a_date` | The four expected sets are `{(2, 5, None)}`, `{(31, 3, None)}`, `{(10, 5, None)}` and `{(2, 5, None)}`: the same days and months, with no year, in the new shape. |
| `tests/test_qa.py` `ChecksTest.test_a_date_the_transcript_says_is_accepted_whatever_its_writing` | The register was written with no date of the meeting, and one of the four writings is `el 2026-09-25`: a date with the year 2026 that the test's transcript does not say (its dates have no year). The fixture was unrealistic, since a meeting has a date; the register is written with `date="2026-09-25"`, the day of the transcript's "25 de septiembre", and the four writings are accepted as before. |

Not tests, but changed with them:

- `tests/test_summary.py`: the helper `summary_text` takes two new parameters, `empty` (the heading of a section to
  leave with `emptied`, nothing by default); with neither, the text it makes is the one it always made, so no test of
  the summary needed a change. Every fixture that builds a summary already had content under every heading.
- `tests/test_d1_barrido.py`: its import of INGOL's kits also takes `resultado` (what `TrazabilidadDelRegistro`
  uses), and it imports `qa`, `test_qa` and `write_teams_docx`; its header names the new class. The classes WI20 copied
  are as they were.
- No fixture of a register had a year or a figure its transcript did not say, so no register fixture changed.

The messages `summary.empty_sections` and `qa.invented_figure` are new in both languages
(`tests/test_texts.py` checks them without a change). `qa.invented_date` names the year when the date has one
("25/9/2030").

`docs/evidence/01M46KHBYCXMGM0K6N2RM651PE/compare_pilot_tests.py` (WI20) lists the classes INGOL's `test_d1_barrido.py`
holds in this repository's copy; it reports `TrazabilidadDelRegistro` as one that is not WI20's (WI25 added it, and
`docs/evidence/01M4B3HE2AVWM7CEPPNRWS9SFY/compare_pilot_tests.py` checks it against INGOL's). WI20's script was not
changed: it is that work item's evidence.

## After the independent review of `d19f8a6` (P2-1, P2-2, P3-a)

The review asked for a year to be refused whichever way it is written ("del año 2030", "(2030)", "Q3 de 2030"), a
figure said with its scale ("48 mil", "3 millones") to match the figure written in digits, and the retry of a summary
refused for several reasons to name them all. `written_years` is now also applied to every text of the register
(`qa.invented_year`, a new message in both languages), `25-09-2030` and `25.09.2030` are dates, `qa.scaled` reads the
scales, and `writer.check_summary` keeps the reasons it did not raise first (`error.others`) for `writer.revise`, which
puts them in one note (`writer.retry_note`; `RETRY_NOTE_CHARS` is 2000 now, to hold three reasons at their longest).

No test that existed before changed in this round: every one passes as it was, including those that pin the notes of
one reason (`FrameLabelsTest`, `EmptySectionTest`), whose sentences `retry_note` writes the same for a single reason.
The new tests are `SeveralReasonsTest` (in `tests/test_summary.py`) and `YearsAnywhereAndScalesTest` (in
`tests/test_qa.py`).
