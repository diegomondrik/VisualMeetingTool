# MeetingTool

Turns a meeting recording and its transcript into a report with the key
images and what they show. This repository is the redesign of the original
MeetingTool, built from scratch.

## Governed by INGOL

This project is governed by [INGOL](https://github.com/diegomondrik/ingol):
every change is a work item with an approved contract under
`.ingol/work-items/`, and a pull request to `main` is judged by INGOL's
protected review (`.github/workflows/ingol-bootstrap.yml`), which the change
itself cannot alter.

A governed project can carry no other workflow, so the test suite does not
run on GitHub. It runs on the developer's machine before each integration,
and its output is committed under `docs/evidence/<work item>/`.

## Client data never enters this repository

Recordings, audio, transcripts and reports belong to clients. `.gitignore`
keeps them out, and `tests/test_repository_guard.py` fails if one is tracked
anyway.

## Reading the frames with Gemini

The frames of a meeting (`python -m meetingtool.frames`) are read with
Gemini's paid tier, using your own key. Save it once in the Windows
Credential Manager; it is never shown or written anywhere:

```
python -m meetingtool.reading key set
python -m meetingtool.reading read --frames <frames folder>
```

The key must come from a Google Cloud project with billing enabled. On the
free tier Google may use what is sent to improve its products, and meeting
frames are client data. What each frame shows is written to
`frames_read.md` in the frames folder, which must be outside any
repository. A run that cannot be completed writes nothing and says why;
there is no lower-quality fallback. `key status` shows only whether a key
is saved and its length, and `key delete` removes it.

## Writing the meeting summary

Once the frames are read, Gemini writes the summary from the transcript and
what it read in each frame, with the same key:

```
python -m meetingtool.summary --frames <frames folder> --transcript <transcript.docx>
python -m meetingtool.summary --frames <frames folder> --transcript <transcript.docx> \
    --project <project id> --title "<meeting title>" --date YYYY-MM-DD [--type status]
```

The summary is written to `summary.md` in the frames folder, in the
language of the transcript. It has the sections of the original
MeetingTool's report: executive summary, participants, decisions, action
items, what was on screen, pending deliverables, key topics, beyond the
agenda, and key points. With `--project`, the summary also reads what the
project knows from earlier meetings, and the meeting is added to the project
with its key points, so the next summary knows them. The transcript is sent
to Gemini's paid tier. A summary that is cut short or missing a section is
retried once and never delivered incomplete.

## Running the tests

Python 3.11 or newer, no other library needed:

```
python -m unittest discover -s tests -v
```
