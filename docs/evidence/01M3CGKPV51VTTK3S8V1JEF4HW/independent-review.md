# Independent review — work item 01M3CGKPV51VTTK3S8V1JEF4HW (projects and meeting memory)

Reviewer: `revisor-independiente` subagent, own context window, 2026-09-25.
Reviewed: commit `0d5c49a` on `main` `8f44a2c` (7 files).
Verdict: **approved for `independent_review`, no P0/P1.** Approval record
`01M3CHHK5Q7BMZKD09CHWV2SMH`, bound to the contract digest `758f0c3b…c260`
(the contract did not change in the correction).

What the reviewer executed: the suite (25 tests, exit 0); `ingol audit
--work-item` (0 blocked); TP-06 by hand (the diff matches the declared
surfaces and touches nothing of work 2: no `meetingtool/__main__.py`,
`pyproject.toml`, `README.md`, `.gitignore`, `meetingtool/frames/`,
`tests/test_frames*`); line endings; mutations in a throwaway clone (five
killed, four survived, all four now covered, see below); adversarial probes
in temporary folders only, never in the owner's data folder.

## Correction pass (one pass, per the review budget), commit `91231a1`

Applied after the review and **not re-reviewed**, as the budget allows:

| Finding | Correction | Proven by |
|---|---|---|
| P2-1: a project id was not validated, so `--project ../repo/x` or an absolute path, or a link inside the data folder, could write client memory into a git work tree | A project id must equal its own slug; the project's final folder is checked with the same git-work-tree rule. The now-redundant check in `add_meeting` was removed (the folder check covers it) | Tests for a path instead of an id, and for a project folder that is a link (junction on Windows) into a repository; mutations removing either check turn the suite red |
| P2-2: redirected output crashed on characters outside the Windows ANSI code page | stdout/stderr reconfigured to UTF-8 in `main` | Test with `Łódź`, `✓` and `→` through `list`, `meetings` and `knowledge`; mutation removing it turns the suite red |
| Test gaps: refusal in `add_meeting`, `.git` as a file, all key points | Three tests added | Mutations `.git` only as a folder, first key point only: red |

The executor's final mutation run: **12 of 12 red** on `91231a1`. The owner-
machine commands were re-run read-only with the corrected code (appended to
`owner-machine-run.txt`), including a refused `--project ../prueba-f8`.

## Known limitations recorded from the review (do not reopen the cycle)

| ID | Finding |
|---|---|
| P2-3 | `pyproject.toml` lists only the top package, so `pip install .` would leave out `meetingtool.projects` (and work 2's `meetingtool.frames`). Not a surface of either parallel work item (condition 7); for a later work item |
| P3 | `slugify` drops letters such as `Ł`, `ß`, `ø`; wholly non-Latin names all map to `project` and collide |
| P3 | A very long title raises a raw `OSError` on Windows instead of `ProjectError` |
| P3 | A summary with `\r\n` makes `rebuild_knowledge`'s return differ from `knowledge_context`'s read; the file-equality test is close to tautological |
| P3 | `knowledge_context` on a missing `knowledge.md` raises `FileNotFoundError`, not `ProjectError` |
| P3 | `~` in `--data-dir` or the environment variable is not expanded (a surprising folder, never inside a repository) |
| P3 | Two meetings on the same day added within the same second list alphabetically, not in the order added |
| P3 | The AC05 evidence holds synthetic context, summaries and a key point besides titles; no client content |
