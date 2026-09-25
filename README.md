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

## Running the tests

Python 3.11 or newer, no other library needed:

```
python -m unittest discover -s tests -v
```
