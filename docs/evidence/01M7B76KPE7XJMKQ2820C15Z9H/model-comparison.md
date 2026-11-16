# WI200-AC08: which model writes the summary, judged blind

2026-11-15, at the owner's request after three rounds that did not converge (regression-round-3.md).

Same case, same request: the exact text `writer.build_prompt` produced on tree 4d65584 (139,281 characters:
instructions, transcript, notes, frame reading, project context). Each answer went through the app's own
checks and marks (check_summary, [VERIFICAR] marks for praise, approximate dates and unsaid figures, the
recording notice). Outputs stay in the owner's data folder (client material).

Candidates, two runs each:
- Gemini 3.8 Flash: round 3's two app runs (each needed the automatic retry; first answers refused for praise).
- Claude Sonnet 5.5 and Claude Opus 5.5: run as Claude Code subagents on the owner's Claude subscription
  (not the API; the agent adds its own base instructions), one attempt.
- GPT-6.1 Sol: run with Codex on the owner's ChatGPT subscription (not the API), one attempt.

Judge: GPT-6 Astra (Codex, read-only), blind: the eight summaries under shuffled letters, the key kept
outside its folder. The judge's folder held the eight summaries, the checklist, the transcript and the notes as
text, the frame reading and the project context; both judges were told to read every file. Point 8 (Word template) does not apply to a comparison of texts.

| Model | Run | Passes the app's checks first time | PASS of 8 | Point 9 | Judge's rank |
|---|---|---|---|---|---|
| GPT-6.1 Sol | 2 | yes | 7 | FAIL: the client's praise paraphrased | 1 |
| GPT-6.1 Sol | 1 | no (praise, marked) | 7 | FAIL: the client's praise paraphrased | 2 |
| Claude Opus 5.5 | 1 | yes | 7 | FAIL: an uncommented screen noted in our reading | 3 |
| Claude Opus 5.5 | 2 | yes | 7 | FAIL: an uncommented screen noted in our reading | 4 |
| Claude Sonnet 5.5 | 1 | yes | 7 | FAIL: an uncommented screen described | 5 |
| Claude Sonnet 5.5 | 2 | yes | 7 | FAIL: an uncommented screen noted in our reading | 6 |
| Gemini 3.8 Flash | 1 | no (praise) | 3 | FAIL: our fit claimed in our own words | 7 |
| Gemini 3.8 Flash | 2 | no (praise) | 3 | FAIL: our fit claimed; the personal item | 8 |

Every non-Gemini run passed points 1 to 7. Both Gemini runs failed 2 and 6 and were partial on 4 and 5.
Outside the checklist the judge found overstatements in every summary (budget status, attributions), the
most serious and numerous in the two Gemini runs.

## Second blind judge: Claude Opus 5.5

Same folder, same instructions, a subagent restricted to the judge's folder (the key was outside it).

| Model | Run | PASS of 8, judge 1 (GPT-6 Astra) | PASS of 8, judge 2 (Claude Opus 5.5) | Rank, judge 1 | Rank, judge 2 | Mean rank |
|---|---|---|---|---|---|---|
| Claude Opus 5.5 | 1 | 7 | 7 | 3 | 1 | 2.0 |
| GPT-6.1 Sol | 1 | 7 | 7 | 2 | 4 | 3.0 |
| GPT-6.1 Sol | 2 | 7 | 7 | 1 | 5 | 3.0 |
| Claude Opus 5.5 | 2 | 7 | 7 | 4 | 3 | 3.5 |
| Claude Sonnet 5.5 | 2 | 7 | 8 | 6 | 2 | 4.0 |
| Claude Sonnet 5.5 | 1 | 7 | 7 | 5 | 6 | 5.5 |
| Gemini 3.8 Flash | 1 | 3 | 3 | 7 | 7 | 7.0 |
| Gemini 3.8 Flash | 2 | 3 | 2 | 8 | 8 | 8.0 |

Each judge ranked its own company's models higher (judge 1 put GPT-6.1 Sol first and second; judge 2 put
Claude first and second), which is why both were used. What both agree on: Gemini 3.8 Flash last, far
behind; the other three models on 7 or 8 points; Claude Opus 5.5 in the top four in both runs and with both
judges; Claude Sonnet 5.5 the most uneven (one run ranked 2nd and 6th; its other run listed uncommented demo
screens and stated a wrong fact about the demo's time). Point 9 for the non-Gemini runs: judge 2 marked the
client's praise paraphrased without its minute in the executive summary as PARTIAL (the body quotes it).

Limits: one meeting; the non-Gemini candidates ran through subscriptions as agents, not through the API the
app would use.
