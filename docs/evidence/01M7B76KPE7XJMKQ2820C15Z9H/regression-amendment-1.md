# WI200-AC08 (amendment 1): the real presales meeting with GPT-6.1 Sol, judged blind by two judges

2026-11-16. Tree 8ca68fd (amendment 1 complete; full suite on 19fcf8f: 874 OK, 3 skipped). Summary stage
only, run twice by the owner with `correr-regresion.ps1` (`--type presale --language en --notes --model
gpt-6.1-sol --max-cost 0.75`), through OpenAI's API with the owner's key. The frames' reading was already
paid and not repeated. Then the Word report of each run, built with the company's template (the one with
`{informe}`), for point 8.

| Run | Attempts | Input tokens | Output + reasoning tokens | Estimated cost |
|---|---|---|---|---|
| 1 | 1 | 40,432 | 5,488 + 153 | US$0.137 |
| 2 | 1 | 40,432 | 5,413 + 373 | US$0.139 |

Total US$0.276 of the US$1.50 approved for this one round. No answer was refused, no retry was needed.

Judges, each given only the two summaries under random letters, the two reports' text, the template's
text, the transcript, the notes, the frames' reading, the project's context and the 9-point checklist (not
the code, the earlier rounds or the builder's reasoning):
- GPT-6 Astra through the Codex CLI, read-only;
- Claude Opus 5.5 as a separate agent.

| Point | Run 1 (Astra / Claude) | Run 2 (Astra / Claude) |
|---|---|---|
| 1. No demo figure as the client's problem or metric | PASS / PASS | PASS / PASS |
| 2. No invented cost or deadline; a loosely promised delivery dated as said | PASS / PASS | PASS / PASS |
| 3. Who approves and who only gives a blessing, as the client said | PASS / PASS | PASS / PASS |
| 4. The four statements that matter for selling (price, business case, approvers, competition) | PASS / PASS | PASS / PASS |
| 5. Disagreements with the notes in «Recording and notes» | PASS / PASS | PASS / PASS |
| 6. What only the notes say, with its origin | PASS / PASS | PASS / PASS |
| 7. The incomplete recording notice | PASS / PASS | PASS / PASS |
| 8. The template report does not open with the template's sample text | PASS / PASS | PASS / PASS |
| 9. No selling, no personal deliverable, no demo screen without a client comment | PASS / PASS | PASS / PASS |

Neither summary needed a [VERIFICAR] mark to pass. Both judges listed the disagreements between notes and
recording on their own (Astra 11, Claude 7 that matter plus 5 minor) and found all of them reported in both runs.

Outside the checklist (both judges; not part of AC08, written down for a later work item):
- Both runs leave out one statement of the client about who leads the project.
- Run 2 leaves out three more statements of the client that matter for selling, and one row states as a
  client wish what the client only implied (the builder checked the quote: it was a remark, not a stated
  requirement).
- Run 1 cuts one client quote before its key half, and also leaves out one of those statements.
- Claude's judge calls one screen of our own response matrix a borderline case for point 9 (it was
  discussed in general, not commented on screen by screen); both judges marked point 9 PASS.

Not verified by the judges: the images themselves (only their reading), the Word file's look (only its
text), the audio.

Result: AC08 met. Both runs pass the 9 points with both judges, in one round, at US$0.28.
The verdicts and the material stay outside git, in the case's data folder (`ac08/`).
