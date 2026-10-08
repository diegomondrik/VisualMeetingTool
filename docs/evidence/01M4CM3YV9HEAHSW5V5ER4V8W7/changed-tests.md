# WI31: existing tests that changed, and the rule that changed each

WI31-AC03: every test that existed before passes, or is named here with the rule of this work item that changed it.
Base: `1a78ce4` (main, after WI27). `git diff 1a78ce4 -- tests/` shows the changes.

**No test that existed before changed.** The only change under `tests/` is a new file, `tests/test_pinned_versions.py`
(it reads files only: no kits, no network, nothing installed is looked at, so the CI runs it). The workflow
`.github/workflows/tests.yml` changed (the install step takes `-c constraints.txt`; a step prints the versions), and
the tests below fix both.

Class `PinnedVersionsTest`, the pins (WI31-AC01):

- `test_every_library_of_pyproject_has_an_exact_pin_at_or_above_its_minimum`: the real files, no problem found.
- `test_pyproject_declares_the_libraries_with_a_minimum`: the tests compare with a minimum, so each library of
  `pyproject.toml` must have one (`>=`); a library declared another way fails here, not silently.
- `test_a_library_missing_from_the_constraints_is_found` and
  `test_a_library_brought_by_the_others_missing_from_the_constraints_is_found`: numpy and lxml dropped.
- `test_a_range_is_not_a_pin` and `test_a_library_with_no_version_or_a_wildcard_is_not_a_pin`: `>=`, no version,
  `==` with nothing and `==2.*` are refused.
- `test_a_pin_below_the_minimum_of_pyproject_is_found`: `numpy==1.20.0` against `numpy>=1.26`.
- `test_versions_are_compared_as_numbers_not_as_text`: 9 is below 14 though "9" > "14" as text.
- `test_a_name_is_the_same_whatever_its_case_or_separator`: `Python_Docx` is `python-docx`.
- `test_the_pins_are_the_ones_of_the_installer`: the six versions are those of the installer's
  `requirements-build.txt` (WI18); the two lists change together.

Class `WorkflowInstallsWithTheConstraintsTest`, the CI (WI31-AC01):

- `test_the_install_step_uses_the_constraints_file`, `test_the_install_step_installs_every_library_of_pyproject`,
  `test_the_log_shows_the_versions_installed` and `test_the_workflow_runs_on_windows_with_python_3_12`.

The guide (WI31-AC02) is not checked by a test but by `check_guide.py` in this folder: it looks up each name between
backticks in `docs/MAINTAINING.md` (134 of 175; the rest are flags, snippets and files a run writes). Run it after
editing the guide. `mutations.txt` shows twelve mutations (nine of the pins and the workflow, three of the guide);
each makes its guard fail, and each guard ran to its end (a process that dies is counted "NOT RUN", never detected).

## After the independent review (P1-1, P2-1)

No test that existed before changed. The review found the guide (and the README, before WI31) saying that all
`tests/test_d1_*.py` skip without INGOL's kits: three of the six files do not use the kits and the CI runs them. Both
texts now name the three that skip. And a pin with an environment marker (`numpy==2.5.3; python_version < "3"`) passed
the pin test, though pip ignores such a constraint where the marker does not apply.

- `test_a_pin_with_an_environment_marker_is_not_a_pin` (new): two markers, each found.
- `WorkflowInstallsWithTheConstraintsTest.install_lines` (helper of the existing tests, no assertion changed) now also
  finds `pip3 install` and `pip.exe install`, not only the text `pip install` (the review's P3).

Known limits the review named and the work item does not close: the list of libraries the others bring
(`BROUGHT`) is written by hand, so a new transitive dependency would be unpinned until someone adds it (the log's
`pip list` would show it); `constraints.txt` and the installer's list are tied by a test that repeats the six
versions, since WI18 is not integrated; and the installer's build prints the Python version without requiring the
CI's 3.12.
