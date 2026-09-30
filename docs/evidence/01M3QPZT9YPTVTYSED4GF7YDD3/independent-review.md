# Independent review of WI15 (01M3QPZT9YPTVTYSED4GF7YDD3)

Reviewer: the `revisor-independiente` subagent, in its own context window, on
commit `afb0d9f` against base `2eb02f3`. Written down by the executor from its
report; each finding carries what was done with it.

**Verdict: listo con limitaciones.** No P1. One real "nothing half done" defect
(P2-1), kept as P2 because it needs a disk error at one precise step.

## What the reviewer ran

- `git diff --stat 2eb02f3..afb0d9f -- tests/`: only `tests/test_app.py`, new.
- `python -m unittest tests.test_app`: 42 tests OK (the "no other address of the
  machine answers" test ran, not skipped).
- `python -m unittest discover -s tests`: 289 OK, in the working tree.
- The entry point imports no docx, av, numpy, PIL, lxml, nor `meetingtool.app`.
- Three probes of its own, which confirmed P2-1, P3-1 and P3-2.

## Findings

| # | Finding | Done |
|---|---|---|
| P2-1 | `store.add_meeting` writes `meeting.json` and then rebuilds `knowledge.md`; if that fails, the run removed the folder and the meeting stayed in the project without its report, while the page said nothing was left | Fixed in `9bf8cb9`: `jobs.forget_meeting` removes a record naming the run's folder and rebuilds the knowledge; `ReviewFixesTest.test_a_save_that_fails_half_way_leaves_no_meeting`; mutation detected |
| P2-2 | Closing the window during a run (the run's thread is a daemon) leaves `<project>/processing/<run>` with the client's transcript, frames and maybe the recording, never cleaned | Fixed in `9bf8cb9`: `jobs.clear_leftovers` at every start; test and mutation |
| P3-1 | A refused request after its uploads leaves them in `.meetingtool-uploads`; a retry uploads everything again | The uploads of a refused request are removed (`9bf8cb9`, test and mutation); uploading again on a retry stays, as a limitation in the contract |
| P3-2 | `rmtree(final)` ran even if this run moved nothing there: a name collision (1 in 16 million) would remove another meeting's results | Fixed in `9bf8cb9`: only a folder this run moved is removed, and a taken name is refused; test and mutation |
| P3-3 | Two applications over one data folder: the second clears the first's uploads (and, with the P2-2 fix, its run) | Fixed in `9bf8cb9`: one application per data folder (`DataFolderLock`); test and mutation |
| P3-4 | The request compared with the command's is the summary's (and the register's), not the reading's | Limitation in the contract |
| P3-5 | The Edge run attacks from `localhost:<other port>`, not from `127.0.0.1:<other port>`, where the browser does send the SameSite=Strict cookie and only Origin and Sec-Fetch-Site refuse it (covered by unit tests and mutations, not by a browser); any local process can get the cookie by serving on 127.0.0.1, outside the threat model | Limitation in the contract |
| P3-6 | `HTTPServer` sets `SO_REUSEADDR`; on Windows another local process might bind the same port (not verified) | `9bf8cb9`: no reuse, `SO_EXCLUSIVEADDRUSE`. Measured on the owner's machine: a second socket with `SO_REUSEADDR` is refused even without it, so the setting is kept and not counted as a control (no mutation) |
| P3-7 | AC04's evidence: the owner's folder has no project; the script uses `App`, not `serve`; the run predates the commit and does not name it | Rerun on `9bf8cb9`, naming it; the folder having no project stays as a limitation in the contract |
| P3-8 | While a stage runs its own cost shows 0; the total is live | Limitation in the contract |

## Found without fault (by reading the code, except where the reviewer ran it)

`refusal` (peer, Host, Origin, Sec-Fetch-Site, cookie, before any route; OPTIONS
without CORS headers; `/open` needs the token); paths from slug identifiers,
records compared with the project, file names by pattern, the meeting's folder
by its own pattern and a containment check (traversal answers 404, run);
escaping (Markdown escaped before it is converted, attributes escaped,
`app.js` only `textContent`, CSP without inline script, `nosniff`); one shared
spending meter (`test_one_ceiling_covers_every_stage`, run); AC06 defaults byte
for byte as before; 22 mutations covering each guard.

## After the review

- `5e4792e`: the ceiling of one meeting is US$1.00 (INGOL D-186), after the
  first real run stopped in the reading with US$0.50; a stop by the ceiling
  after a request that got no answer says why it got none.
- `868a415`: the real runs (real-run.txt).

## Re-verification of `868a415`

Same reviewer role, in a fresh context, in a `--no-hardlinks` clone of
`868a415` (removed afterwards).

**Verdict: listo con limitaciones.** No P1 or P2; two new P3.

- **Ran:** `tests.test_app`, 50 OK. The whole suite, 297 OK, which matches
  local-test-run.txt. Three probes:
  - removing the `rmtree(final)` of a moved run makes 2 tests fail;
  - removing the new line of `gemini.py` makes its test fail;
  - a `meeting.json` half written gives P3-A.
- **Confirmed by reading the code:**
  - P2-1 is resolved for the case it names (the record written, the knowledge not).
  - P2-2, P3-1 (what it says), P3-2, P3-3 and P3-6 are resolved as described.
  - The change of `gemini.py` only adds text to the message of a stop by the
    ceiling. The commands keep their US$0.50; the US$1.00 is the application's only.
  - The limitations written in the contract say what the code does.
  - `mutations.txt` ran on `9bf8cb9`, and what came after touches no mutated line.
  - AC05's numbers add up.
- **P3-A:** if writing `meeting.json` itself fails half way (a full disk),
  the broken record cannot be read. `forget_meeting` skips it and it stays, and
  from then on the project's meetings cannot be listed until the folder is
  removed by hand. Suggested: note the names under `meetings/` before
  `add_meeting`, and remove the new ones if it fails. Kept as a known
  limitation, for the next work item that touches the application.
- **P3-B:** AC04's check runs the application through `App`, not `serve()`.
  The real start adds `.meetingtool-app.lock` to the data folder, and removes
  only what the application itself left (`*/processing` of projects,
  `.meetingtool-uploads`). No data of the owner is touched, but "every file has
  the same bytes" is true of the screens, not of the start. Kept as a known
  limitation.
- **Residual:** the US$1.00 is justified by one request of 70 frames. A much
  longer meeting may again not fit a retry. That is the owner's decision
  (D-186); the page allows up to US$5.

The reviewer approved the contract as it stands:
`.ingol/work-items/01M3QPZT9YPTVTYSED4GF7YDD3/contract.yaml`, SHA-256
`45b2dab6da39f3a45449195fe2b40e2d302147f3c0a31266955afbb3e4acf917`,
which the executor recomputed and found equal. The contract was not edited
for P3-A or P3-B, so that approval stays bound to it.
