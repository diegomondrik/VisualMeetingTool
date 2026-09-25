# WI07 (01M3D814MW97RJQR5Z7TQQDJM4): independent review, integration gate

**Reviewer:** revisor-independiente (Claude Opus 5.5), read-only. **Date:** 2026-09-25.
**Candidate:** branch `work-item/01M3D814MW97RJQR5Z7TQQDJM4-gemini-reading`, commits `b02f826` and `d249166` on `main` `8754413`.
**Out of scope for the first pass:** WI07-AC06 (the real paid run) and WI07-AC07 (the fresh-clone suite run). Their evidence did not exist yet and was checked in the correction pass (last section).

## What I read

- The index lines for D-170 and D-173, and the full text of D-173.
- `gemini-contract-proposal.md`.
- `contract.yaml` and `plan.yaml`.
- The full diff `8754413..d249166`.
- `meetingtool/frames/extract.py`, only `enclosing_git_work_tree` and the frame size and JPEG settings.
- The original `MeetingTool/tools/gemini_client.py`, only its key lines: the prompt, 70 frames per chunk, the 4096 output cap, and the key sent as a URL parameter.
- The source of the owner's `guardar_clave.py`, to check that it stores the credential the same way. It does: UTF-16 blob, generic credential, target `VisualMeetingTool/gemini`.

I did not read any credential value, did not call Gemini, and used no network.

## What I ran

All runs were in a scratch clone made with `--no-hardlinks` under `AppData/Local/Temp`. Both scratch folders were deleted afterwards with their own `rm -rf`. One probe left a tempfile folder behind: it holds a single 8x8 black JPEG, no client data, and its random name is unknown.

| Check | Result |
|---|---|
| `python -m unittest discover -s tests` (Python 3.12.10, Windows) | 75 tests, OK. The Windows round-trip test ran: it created and then deleted a credential named `VisualMeetingTool/test-<uuid>`. |
| `python -m unittest tests.test_reading -v` | 20 tests, OK |
| `git diff --name-only 8754413 HEAD` | 8 files, all inside the declared `affected_surfaces`. No image or read text is tracked. |
| Mutation run on `gemini.py`, 10 mutants | 4 killed, 6 survived (listed in P3-5 below) |
| Direct calls to `check_answer` | Labels written in bold (`**[FRAME 1]**`) are **refused**. Answers made only of labels (`[FRAME 1]\n[FRAME 2]`) **pass as complete**. |
| Command line against a fake server that returns HTTP 200 with a non-JSON body | Exit 1 with a Python traceback (`JSONDecodeError`). The key does not appear in stdout or stderr, and nothing is written. |
| `issubclass(http.client.IncompleteRead, OSError)` | False, so this error is not caught |

## Findings

### P1: nothing enforces the US$0.50 ceiling D-173 set for the real run

**Consequence:** the authorised real run (AC06) can bill more than the US$0.50 the owner approved. That spend is irreversible and outside the authorisation, and the code does nothing to stop it.

How the worst case adds up, for about 81 frames (2 requests, of 70 and 11 frames):

- **Attempts per request.** `_read_chunk` allows up to 4 attempts for each request: the first, one retry for an incomplete answer, and two retries for 503/429/500/timeout.
- **Size of each answer.** Every attempt that gets an answer may be up to `MAX_OUTPUT_TOKENS = 65536` output tokens. Thinking counts inside that cap and is not bounded either.
- **Billed answers without timeouts.** Two incomplete HTTP 200 answers per request give 4 billed answers of up to 65,536 tokens each. At Flash output prices (about US$2.50 per million tokens for 2.5 Flash, about US$3.00 for 3 Flash) that is **about US$0.66 to 0.79**, before input.
- **Timeouts make it worse.** A 65,536-token non-streamed answer at about 200 tokens per second takes roughly 330 seconds, longer than `TIMEOUT = 300`. So the runaway answers most likely to cost the most are also the ones that time out and get retried twice. If Google bills a generation the client disconnected from, and **I am not certain it does**, the worst case rises to 8 answers, about US$1.3 to 1.6.
- **The price itself is unknown.** `MODEL = "gemini-flash-latest"` is a moving alias, so the price per token is not fixed (see P2-1).

The expected cost is well under the ceiling, roughly US$0.10 to 0.25. The problem is that the ceiling is kept only by luck.

**Simplest fix that keeps the guarantee:** a spend budget per run, with the worst case counted in advance. Before each attempt, refuse to send it if the tokens already spent plus `MAX_OUTPUT_TOKENS` for this attempt (plus an input estimate) would go over the budget, and count a timed-out attempt as if it had used all `MAX_OUTPUT_TOKENS`. Alternatively, lower the cap and bound thinking so that 4 to 8 answers at the maximum stay under US$0.50. Either way, put the arithmetic in the AC06 evidence. This must be fixed before AC06 is run.

**Corrected in `5769a77`; verified below.**

### P2 (do not reopen the cycle)

- **P2-1: model version drift.** `MODEL = "gemini-flash-latest"` is an alias Google can point at a different model, and neither the code nor `ReadingResult` records the `modelVersion` that Gemini returns. The AC06 evidence therefore cannot say which model was billed, and its "estimated cost" rests on a price table it cannot identify. Suggestion: record `modelVersion`, or pin a dated model name.
  **`modelVersion` is recorded since `5769a77`; the alias stays.**
- **P2-2: the completeness check can wrongly reject a real answer.** `_BLOCK = ^\s*\[FRAME (\d+)\]` refuses labels in bold (`**[FRAME 1]**`, verified), labels written as list items (`- [FRAME 1]`) and a different letter case (`[Frame 1]`). Flash models commonly add bold even when told not to. The check stays safe, since it never passes a bad answer this way, but a good answer can be paid for, retried and then refused. Suggestion: allow an optional leading `*`/`-` and ignore letter case.
  **Corrected in `5769a77`.**

### P3 (known limitations)

- **P3-1: an answer made only of labels passes.** `[FRAME 1]\n[FRAME 2]` with no content counts as complete (verified). The check counts labels, not the content of each block. This is acceptable under the contract's wording ("one block per frame"), but weaker than "complete".
- **P3-2: some failures crash with a traceback instead of a clear error.** These are not turned into `ReadingError`:
  - HTTP 200 with a body that is not JSON (`JSONDecodeError`, verified);
  - `http.client.IncompleteRead` or `BadStatusLine`, which are not `OSError`;
  - a key with characters outside Latin-1 (`UnicodeEncodeError`);
  - `partial.replace` failing on Windows while `frames_read.md` is open elsewhere, which leaves `frames_read.md.partial` behind.

  **Corrected in `5769a77`, except the last item.**
- **P3-3: an old result file can look like a new one.** A failed run leaves any earlier `frames_read.md` in place, and it can be mistaken for the output of the run that just failed.
- **P3-4: the test named for "never uses the network" does not prove it.** It shows only that the default endpoint goes through `urlopen`. The suite stays off the network only because every other test passes the fake endpoint.
- **P3-5: tests that survived mutation.** Each of these changes left the reading tests passing:
  - `timeout=TIMEOUT` removed;
  - the retry allowance shared across the whole run instead of per request;
  - the block order ignored;
  - a pause added before the retry of an incomplete answer;
  - the file name removed from the frame label;
  - `MAX_OUTPUT_TOKENS = 4096`.

  **The last one is pinned since `5769a77`.**
- **P3-6: tests do not cover a server that echoes the key.** The code copies up to 200 characters of an error body into the message. Real Gemini errors are not known to echo the key, so this is a gap in coverage, not a demonstrated leak.
- **P3-7: payload size is not controlled.** 70 frames of up to 1280x720 at JPEG quality 85, base64-encoded, may exceed Gemini's limit of roughly 20 MB for inline request data if the frames are dense. That would give an immediate HTTP 400, at no cost.

## What checks out

- **Scope and D-173.** The work stays within the declared surfaces and matches D-173 and the proposal: 70 frames per request, one block per frame, a `finishReason` check, no fallback reading, two spaced retries, the key in the `x-goog-api-key` header, and one credential per user in the Windows Credential Manager with set, status and delete.
- **Nothing is written until every request succeeded.** Everything is held in memory until all requests are done, then written through a `.partial` file. A frames folder inside a git work tree is refused before any request.
- **Keys.** The key is never in the URL. None of urllib's exceptions carry request headers.
- **`credentials.py`.** The structure layout, the signatures, `use_last_error` with `get_last_error`, `ERROR_NOT_FOUND = 1168`, the UTF-16 blob length, and `CredFree` in `finally` are all correct. The format matches the owner's existing helper.
- **The Windows round-trip test** uses only `VisualMeetingTool/test-<uuid>` and deletes it in `finally`.

## Verdict (first pass)

**Changes required** for P1. Once it is fixed, and with the P2 and P3 items listed as known limitations, the code and tests are fit to approve.

## Correction pass verified

**Scope:** `git diff d249166 14701a5`: commits `5769a77` (correction), `68f1a2b` (AC06 evidence) and `14701a5` (AC07 evidence and `mutations.txt`). Read-only. No network calls, no credential values read.

**What I ran**

- `git diff --stat 5769a77 14701a5` touches only the three evidence files. The code of the real run (`5769a77`) is therefore the same as the code of the tested commit (`68f1a2b`) and of the head.
- `git rev-parse 68f1a2b^{tree}` = `7d2d712d998f51ccbaf8f4255553a02404e865bb`, which matches `local-test-run.txt`.
- A fresh `--no-hardlinks` clone of `14701a5`: `python -m unittest discover -s tests` gave 83 tests OK, the same as the AC07 evidence.
- Cost figures:
  - `worst_attempt_cost(70)` = 0.2638;
  - `worst_attempt_cost(11)` = 0.1974;
  - `token_cost(91542, 18414+4914)` = 0.15614.
- A probe with a fake Gemini on localhost against 150 frames, the extractor's default `--budget`. Its token counts per frame followed D-169's measured density: 1129 input, 267 output and 282 thinking.
- Both scratch folders were deleted.

**P1: fixed.**

- Before each attempt the code checks that `spent + worst_attempt_cost(frames) <= max_cost_usd`.
- After each attempt the actual usage is added. An attempt with no answer, or a 200 with no usage data, counts at its maximum.
- As long as no attempt costs more than its computed worst case, total spend cannot exceed the budget. Two tests and two killed mutations pin this ("no budget check", "no-answer counted as free").
- The default of 0.50 matches D-173, and `--max-cost` is wired through.

**The budget arithmetic in the evidence holds.** The worst cases of US$0.264 (70 frames) and US$0.197 (11 frames) are correct. US$0.156 is exactly (91542 × 0.75 + 23328 × 3.75) / 10⁶. The second chunk's worst case (0.156 + 0.197 = 0.353) fits under 0.50.

Two assumptions could not be verified; they are residual limitations:

- that `maxOutputTokens = 49152` also bounds thinking tokens;
- that US$0.75/M input and US$3.75/M output are the list prices of `gemini-3.8-flash`, the model that answered. The evidence correctly defers the exact charge to Google billing.

**One new P2, no P0 or P1.**

- **P2-3: with the default budget, a large folder can pay for its first two requests and then write nothing.**
  - At D-169's density, 150 frames sent 2 requests, spending about US$0.41, then stopped before frames 141 to 150. Nothing was written, and the message does not name `--max-cost`.
  - At the density of the real run, 150 frames squeezes through; about 180 frames or more would fail after spending about US$0.27.
  - It never overspends the authorised ceiling, and the AC06 run (81 frames) is unaffected.
  - Suggested fix: before the first request, refuse if the sum of the per-chunk worst cases exceeds the budget, and name `--max-cost` in that message and in the mid-run stop message.
- **The other corrections all check out:** a non-JSON 200 is treated as incomplete; `http.client.HTTPException` is caught; a non-ASCII or non-printable key is refused without being echoed; `MAX_OUTPUT_TOKENS` is pinned; `modelVersion` is recorded; the label pattern accepts bold, list-mark, quote-mark and any-case labels and still rejects a label in mid-sentence.

**Evidence notes, not findings**

- **The earlier failed attempt (22:05Z)** read an empty credential, exited 2 and sent nothing. The Credential Manager showed an older, empty version of the credential; the cause is unknown and remains open.
- **The frames were deleted after that failure.** That was a defect of the executor's measurement script, not of the repository. The meeting was extracted again and gave the same 81 frames.
- **Only numbers are recorded:** nothing identifying the meeting and no read text, and the frames folder is recorded as deleted.

**Known limitations carried forward:** P2-3 (new), the two unverified assumptions above, P3-1, P3-3, P3-4, P3-6, P3-7, and the rest of P3-5.

**Final verdict: approve with listed limitations.** P1 is fixed, and the AC06 and AC07 evidence is consistent with the code and with D-173's US$0.50 ceiling.
