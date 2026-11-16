# WI200-AC08, round 1: the real presales meeting, judged point by point

2026-11-15. Tree d80a8d0 (branch work-item/01M7B76KPE7XJMKQ2820C15Z9H-resumen-fiel-y-notas).
Summary stage only, run twice (`--type presale --language en --notes`), model gemini-3.8-flash:
run 1 US$0.187 (3 attempts, two of them HTTP 503), run 2 US$0.069 (1 attempt). Outputs, sources and
the judge's detailed report stay in the owner's data folder (client material, outside git).

Judge: a general-purpose agent that did not build the change and saw neither its code nor the
builder's reasoning, checking each point against the transcript, the notes and the frame reading.

| Point | Run 1 | Run 2 |
|---|---|---|
| 1. No demo figure as the client's problem or metric | PASS | PASS |
| 2. No invented cost or deadline; a loosely promised delivery dated as said | PASS | PARTIAL: a soft "a week or two" turned into a date |
| 3. Who approves and who only gives a blessing, as the client said | PARTIAL: the blessing written as formal sign-off | PASS |
| 4. The four statements that matter for selling (price, business case, approvers, competition) | FAIL: 2 of 4 | FAIL: 1.5 of 4 |
| 5. Disagreements with the notes in «Recording and notes» | FAIL: 1 of the 4 that matter | PARTIAL: 2 of the 4 that matter |
| 6. What only the notes say, with its origin | PARTIAL: two facts unattributed | FAIL: notes facts given as the meeting's, one with a false origin |
| 7. The incomplete recording notice | PASS | PASS |
| 8. The template report does not open with the template's sample text | PASS | PASS |
| 9. No selling observation, no personal deliverable, no demo screen without a client comment | FAIL: selling wording, a personal item, a summary line of uncommented screens | FAIL: selling wording, a summary line of uncommented screens |

Outside the checklist the judge also reported: client problems stitched from unrelated remarks or
inflated (run 2); important client statements lost in both runs (the strongest positive remark and
three more about the client's process); some statements
inverted (run 1); and the [VERIFICAR] mark on a figure that the project context and the screen do say,
while the same figure goes unmarked in sections the net does not check.

Result: AC08 not met. The changes made in response go in the next round's record.
