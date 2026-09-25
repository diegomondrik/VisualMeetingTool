# Independent review — work item 01M3CG1XGTT95MT2WNTMH1TXR2 (guard)

Reviewer: `revisor-independiente` subagent, own context window, 2026-09-25.
Reviewed: commit `a977049` on `main` `7b25859` (5 files).
Verdict: **approved for `independent_review`, no P0/P1.** Approval record
`01M3CGFJDSPXCRZPXX0B0Z7XH1`, bound to the contract digest `667a5828…ba58`.

What the reviewer executed: the suite (12 tests, exit 0); `ingol audit
--work-item` (0 blocked); TP-06 by hand (the diff matches the declared
surfaces exactly, nothing under `controlled_by_content`); eight mutations of
its own in a throwaway clone, all red, on top of the executor's six (all
red); `git check-ignore` with and without `core.ignorecase=false`, showing
the override is what makes the `.gitignore` test represent Linux; global
git excludes, which hide nothing; and a search of INGOL's code for file
names the name rule could reject (none).

## Known limitations recorded from the review (P2/P3 do not reopen the cycle)

| ID | Finding | Where it goes |
|---|---|---|
| P2-A | The guard rejects any tracked image, video or `transcript*.txt` anywhere, `tests/fixtures/` included, so a work item cannot commit sample media | **Written as a constraint into the contracts of the two parallel work items:** test media is generated at test time, never committed |
| P2-B | Data saved inside the package (for example `meetingtool/projects/acme/memory.json`) is caught by neither the guard nor `.gitignore`, which only watch the root folders | **Written into the projects work item's contract:** meeting data lives outside the repository by default |
| P3-A | `.gitignore` does not cover the old pipeline's name patterns, nor root folders in other letter cases on Linux; the guard covers both | Recorded |
| P3-B | The `.gitignore` test checks root folders in lower case only | Recorded |
| P3-C | The "not ignored" test would also pass if `git check-ignore` itself errored | Recorded; the other two tests of the class would fail in that case |
| P3-D | The closed list leaves out archives, `.csv`, legacy office formats and other rare media, and transcripts with free names | Recorded; the list is closed by contract |
| P3-E | The `transcript` prefix without underscore rejects a document such as `transcription.md` | Recorded |

Residual, not a defect of this increment: in a public repository the guard
only acts when the developer runs the suite (INGOL D-163); the protected
review does not stop a force-added file.
