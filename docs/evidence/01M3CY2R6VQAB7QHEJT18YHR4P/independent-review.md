# Independent review: work item 01M3CY2R6VQAB7QHEJT18YHR4P (limitations register)

Reviewer: `revisor-independiente` subagent, own context window, 2026-09-25.
Reviewed: branch `work-item/01M3CY2R6VQAB7QHEJT18YHR4P-limitations`, commits `1fce3d7` (contract, plan, register, script) and `a76829a` (evidence only), on `main` `3729407`. There are 7 files, and all of them fall under the three declared `affected_surfaces`.
Verdict: **approve, with the limitations listed below. There is no P0 or P1.** One correction pass followed (P2-1, P3-5, P3-2); it was verified, see the last section.

## What I read

- The contract and plan of this work item, `REGISTER.md`, `reproduce.py`, and the three evidence files.
- The five `docs/evidence/*/independent-review.md` files, in full.
- The sources for H1 to H6:
  - H1 and H2: rows 20 and 21 of INGOL's `contract-proposal.md`;
  - H3, H4 and H6: the findings table of `step0-evidence/README.md`;
  - H5: the index lines of D-162 to D-164.
- `meetingtool/frames/extract.py`, `signals.py`, and the `near()` edge in `transcript.py`, to judge whether each mutation is real.

I did not read INGOL's history, the full decision register or the checker's source.

## What I ran

- **Identities.**
  - `git rev-parse 1fce3d7^{tree}` gives `8e0c8a06…`, which matches all three evidence headers.
  - `git diff 1fce3d7 a76829a` touches only the three evidence files.
- **Fixing commits, checked with `git show` and pickaxe.** All six are correct:
  - `a977049` widened the guard (WI02);
  - `ba02528` touches only `.gitignore`;
  - `91231a1` holds the project-id check and the UTF-8 reconfigure;
  - `c38353c` first introduced `"meetingtool.*"` in `pyproject.toml`;
  - `5f20bf7` introduced `-candidates` in the heap entry;
  - `67a6e4e` added the 76-frame source sentence.
- **PR #6 identities.** `3729407`'s parents are `8bd99e2` and `6835fcb`, which are `PR6_BASE` and `PR6_HEAD`. `165cfff..3729407` differs in 3 files, all evidence or approval.
- **Full run in a fresh clone of the branch head `a76829a`, with `--ingol-repo`:**
  - **46 MATCH, 0 MISMATCH, 0 SKIPPED, 0 ERROR, exit 0, 2 minutes.**
  - The output is byte-identical to `reproduce-run.txt` once timings, the temp folder name and the commit line are removed.
  - Afterwards the clone held only 4 ignored `__pycache__` folders.
- **H4 probed beyond the script** (INGOL built at the wrapper's pin `2e862e9`):
  - The CRLF clone has 28 files with CRLF. `doctor` exits 1 with 27 of 29 surfaces blocked, and each blocked surface's detail is literally "present but not byte-identical to this installation's own copy".
  - The LF clone has 0 CRLF files; `doctor` exits 0 with 0 blocked.
  - `ingol audit` exits 0 with 0 blocked on both clones, so the register's claim that `audit` is unaffected holds.
- **H3 probed beyond the script.**
  - TP-05, TP-15 and CI-TRUST all fail, each with the detail "workflow set must contain only ingol-bootstrap.yml, got [ingol-bootstrap.yml tests.yml]". The variant fails for the stated reason only.
  - Without the replica's `GITHUB_*`/`RUNNER_*` variables, the positive control itself fails on TP-07. The simulated environment is therefore load-bearing, and it is declared as such.
- **Adversarial runs of my own, in the clone, all restored with `git checkout`:**
  - `--flip H2 --flip WI01-P2-1` gives 2 MISMATCH.
  - The row `H5` renamed to `H5x` gives "REGISTER MISMATCH … without a register entry ['H5']" and exit 1.
  - The register's state for WI05-P3-2 edited to "fixed by deadbeef", with the code unchanged: **exit 0, MATCH** (see P2-1).
  - The first sample logged as a discard in `extract.py`, which is the natural fix of WI04-P3-6: **still MATCH open** (see P3-1).
- **Mutation honesty.** None of the eight product mutations (WI04-P3-1, WI05-P3-1) is equivalent:
  - `candidate_times` does feed `temporal_score`;
  - `W_ZONE` does feed the score;
  - the container-duration branch is real;
  - the `<=` edge is real.
  - The baseline-passes-first guard runs once per selection. WI05-P3-4 is a mutation that must be killed, run through the same harness, so the clone is shown to pick up mutated files.

## Completeness against the sources

Every P2 and P3 of the five reviews has exactly one entry, and so does each of H1 to H6. No ID is invented. Wording is faithful, with three partial omissions (P3-2 below).

## Findings

### P0 / P1

None.

### P2-1: the register's State column is not under the control; only its IDs are

`reproduce.py` carries its own hard-coded claim for each entry. It prints that claim as `claim=`, and it compares only the IDs with `REGISTER.md`. I demonstrated the gap: `REGISTER.md` said "fixed by deadbeef" for an open limitation, and the script exited 0 with MATCH.

- **Consequence:** the register, which is the artifact WI028-AC08 asks for, can misstate an entry's state while its control stays green.
- **Two statements in the increment overclaim:**
  - `REGISTER.md` says "A fixed limitation therefore turns the script red until this register says so". In fact it stays red only until the *script's* claim changes.
  - WI06-AC02 and the objective say the script prints "what the register claims".
- **Why not P1:** today all 46 states agree by hand check (mine), and a wrong state needs a second editing error.
- **Simpler mechanism that closes it:** `register_ids()` also captures the State cell's leading word (`open` / `fixed` / `not reproducible`) and uses it as the claim, which removes the duplicated constant.

**Corrected in `9d7577a`; verified below.**

### P3 (known limitations, do not reopen the cycle)

| ID | Finding |
|---|---|
| P3-1 | Some reproductions check a proxy that a natural fix would not flip, so a fixed limitation could stay "open" in silence:<br>- **WI04-P3-6** counts samples, not log lines. Logging the first sample still gives MATCH open (demonstrated).<br>- **WI04-P3-7** is "open" whenever the installed PyAV is not 14.x.<br>- **WI04-P3-5** infers "3 held" as `len(pool)+1` inside `heappushpop`. That is structurally true, but it is not a measurement. |
| P3-2 | Fidelity gaps against the sources:<br>- WI03-P3-3 drops "the file-equality test is close to tautological".<br>- WI05-P3-7 drops its third bullet: the run times cannot be compared because the runs were concurrent.<br>- The WI04 review's unnumbered known-limitation row (a 41.6-minute recording takes about 10 minutes) is left out without a word. It carries no P label, but it sits in the "Known limitations" table.<br>**Corrected in `9d7577a`; verified below.** |
| P3-3 | WI05-P3-4 counts any non-zero exit of the mutated test as reproduced, so an import or syntax error would also count. Today it is `FAILED (failures=1)`, and the exact-once text match makes drift an ERROR, which is fail-safe. |
| P3-4 | WI05-P3-7 recognises the "before" numbers by the substrings `210` and `115` across `docs/evidence/*/*.txt`, this work item's own evidence included. Future evidence could flip it. That direction is a false alarm, not a silent pass. |
| P3-5 | "No network call" and "writes only to temporary folders" are not enforced:<br>- `go build` fetches INGOL's modules (and, if needed, a Go toolchain) when the module cache is cold. `GOPROXY=off` and `GOTOOLCHAIN=local` in the build environment would make the claim hold by construction.<br>- Runs with `cwd=REPO` write ignored `__pycache__` folders into the repository, as the evidence headers themselves record.<br>**Corrected in `9d7577a`; verified below.** |
| P3-6 | Without `--ingol-repo`, the default run exits 0 with H1, H3, H4 and H6 SKIPPED. This is documented, but a plain run does not cover the INGOL entries. |
| P3-7 | H2 is a constant (`None`) and H5 checks only its preconditions. Both are declared as such, and `--flip` shows they can mismatch. |
| P3-8 | Mutation entries run against the committed HEAD, while the others run against the working tree. A fix that is not yet committed flips only the latter. |
| P3-9 | `reproduce-run.txt` holds local paths (`C:\Users\Diego\…\SDAD Methodology\Ingol\repo`) in a public repository. There is precedent in the WI03 evidence, and it is not client data. |

## Scope and data

- The diff is exactly the three declared surfaces.
- No product code changed.
- All fixture text in the script is synthetic. No media, transcript or `.docx` is committed.
- The only remotes the script touches are `remote set-url` calls. Nothing fetches from them, and every clone and fetch is local.
- The repository's working tree was clean before and after my review. My scratch clone was deleted.

## Residual limitations of this review

- I could not see the edits behind `adversarial-checks.txt`. I reproduced the same classes of check independently.
- I did not read INGOL's checker source. H3's attribution rests on the checker's own failure details.
- H2 (GitHub plans) is not verifiable offline. I accepted the cited documentation.

## Verdict (first pass)

**Approve with the listed limitations** (P2-1, P3-1 … P3-9). No P0 or P1.

Reviewed commits: `1fce3d7` (tested tree `8e0c8a063eba45b163264e0b24738bc57c99e561`) and `a76829a` (evidence only), base `3729407`. The full reproduction was re-run by the reviewer at `a76829a`: 46 of 46 MATCH, exit 0.

## Correction pass verified

Verifier: `revisor-independiente` subagent, own context window, 2026-09-25. This checks the correction only; it is not a new review. Scope: `git diff a76829a 9d7577a` (only `REGISTER.md` and `reproduce.py`) and `9d7577a..a7136b4` (only the three evidence files). `git rev-parse 9d7577a^{tree}` gives `5de5c6f0…`, which matches all three evidence headers.

**P2-1 is fixed.**
- **The script no longer carries its own claims.** `@entry` no longer takes a claim. `register_claims()` reads the leading words of each row's State cell (the cell before the last). Any other wording is a `REGISTER MISMATCH`.
- **All 46 rows parse to the intended state.** I checked this in a fresh clone of `a7136b4`: every H row has 5 cells, every WI row has 4, and each State cell starts with `open`, `fixed` or `not reproducible`.
- **Re-run with every register edit restored:**
  - my original case, WI05-P3-2 written as "fixed by deadbeef" with the code unchanged: MISMATCH, exit 1;
  - H2 written as "open": MISMATCH;
  - WI04-P3-4 written as "Fixed" (capital F): REGISTER MISMATCH "state not open/fixed/not reproducible ['WI04-P3-4']", exit 1.
- The rewritten `REGISTER.md` sentence now matches this behaviour.

**P3-5 is fixed.**
- After a full run, `git status --ignored` in the clone shows nothing left behind.
- With `GOMODCACHE` pointed at an empty folder, H1 reports `ERROR CalledProcessError` from `go build` and the script exits 1. The cache folder held only three `.lock` files and no module archive, so `GOPROXY=off` stops the build before any download.
- Residual: `local-test-run.txt` still lists four ignored `__pycache__` folders. That file records the suite command (`python -m unittest`), not the script, so this is expected, not a regression.

**P3-2 is fixed.** Three changes:
- WI03-P3-3 now carries the "close to tautological" remark.
- WI05-P3-7 now carries the concurrency bullet, correctly marked as stated in the evidence and not reproduced.
- The WI04 row with no P label is now named in the register with a reason. Leaving it out is defensible: it is a measured cost that needs the owner's real recording.

The new note that this work item's own review findings enter the register with the next work item that changes it is a sound disposition.

**No regression found.**
- The full run at `a7136b4` with `--ingol-repo`: 46 MATCH, 0 MISMATCH, 0 SKIPPED, 0 ERROR, exit 0.
- Its output is byte-identical to the committed `reproduce-run.txt` once timings, the temp folder name and the commit line are removed.
- `--flip` still works.
- The ID cross-check still works: all six adversarial runs in `adversarial-checks.txt` show exit 1, including the new deadbeef case.

**New residual (P3-10, recorded, does not reopen the cycle).** The State cell is located by splitting the row on `|`. A literal `|` written inside a later cell would shift which cell is read as the state. The likely outcome is an unreadable state, which fails safe; a misread that happens to match is possible but unlikely.

The earlier P3-1, P3-3, P3-4 and P3-6 to P3-9 stay as recorded limitations.

**Final verdict: approve with the listed limitations** (P3-1, P3-3, P3-4, P3-6 … P3-10). There is no P0 or P1. Verified commits: `9d7577a` (tested tree `5de5c6f0710455b25e2d905ee71c10932d918be6`) and `a7136b4` (evidence only). The reviewer re-ran the reproduction at `a7136b4`: 46 of 46 MATCH, exit 0.

Per INGOL's review policy the P3 findings do not reopen the cycle. They are recorded here, and they enter `docs/limitations/REGISTER.md` with the next work item that changes it.
