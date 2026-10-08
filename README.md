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

The command that selects the frames of a meeting
(`python -m meetingtool.frames`) reads the recording to its end, with a
transcript or without one: a transcript says when each line starts, not when
the meeting ends, so it never shortens the reading. With `--transcript`, the
samples near a phrase that points at the screen score higher, and the
command says how many candidates that raised. A recording that runs on after
the meeting is read to its end too, and a slide shown there can reach the
report.

The frames are read with Gemini's paid tier, using your own key. Save it
once in the Windows Credential Manager; it is never shown or written
anywhere:

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
    --project <project id> --title "<meeting title>" --date YYYY-MM-DD [--type requirements] [--language en]
```

The summary is written to `summary.md` in the frames folder. It has the
sections of the original MeetingTool's report: executive summary,
participants, decisions, action items, what was on screen, pending
deliverables, key topics, beyond the agenda, and key points. With
`--project`, the summary also reads what the project knows from earlier
meetings, and the meeting is added to the project with its key points, so
the next summary knows them. The transcript is sent to Gemini's paid tier. A
summary that is cut short, missing a section, in the wrong language, or
naming a frame the report could not embed is retried once and never
delivered; when the refusal is a frame that does not exist, the retry says
which names do not exist and that names are copied exactly as each block of
the reading labels them. Every section must say something: one with nothing
under its heading is refused naming it, and the retry says which sections were
empty, and an answer refused for several reasons (an empty section, no key
point, a frame that does not exist) is retried with all of them named; a line
saying plainly that there was nothing (no decisions, no screen shared) is
content.

A transcript may be a Teams `.docx` or a `.txt` in any of three forms:
`Speaker   M:SS` with the words after it, `[HH:MM:SS] Speaker:`, or, when
Teams names no one, each time alone on its line (`0:02`, `1:02:03`) with the
words on the lines after it (a time alone counts only in a file with no
`Speaker   M:SS` or `[HH:MM:SS]` line). The summary of a transcript with no
speaker names no one; the question-and-answer register needs who asked and who
answered, so it refuses such a transcript, when it is asked for and before
sending anything. A `.txt` is read by its byte order mark (UTF-8 or
UTF-16, what Notepad and Windows PowerShell write); with none, as UTF-8 and,
when it is not valid UTF-8, as Windows cp1252; Windows and Unix line endings
alike.

Every frame the summary names goes into the report, so the summary is asked
to name only the screens that were shared to show content someone would
otherwise write down by hand (a data model, the structure of a spreadsheet,
the values discussed), never navigation or a detour (a file explorer, email,
a transition, rows without data), and one frame for each thing shown: the one
that shows it best, with its headings and the values discussed visible. Two
frames named as a range on one line ("from one to the other", with a dash or
an arrow, in bold or not) are refused like a missing frame: the report would
show their two ends, which nobody chose. The rest of the rule is asked of
Gemini, not checked.

`--type` says what kind of meeting it was. `presale` (preventa),
`negotiation` (venta o negociación) and `requirements` (relevamiento de un
proyecto a desarrollar) change how the whole meeting is read, not only add
their own sections: in a presale, interest is a signal and not a decision; in
a negotiation, what was offered, accepted and still open are kept apart; in a
requirements meeting, the pending items are mostly what is still to be found
out and who can answer it. `kickoff`, `status`, `technical` and `training`
add their sections at the end. Meetings stored in a project with the earlier
`discovery` type are still read; a new summary uses `presale` or
`requirements` instead.

`--language es` or `--language en` chooses the summary's language whatever
language the meeting was held in; without it, the summary is in the
transcript's language. Verbatim quotes stay in the language they were said,
with a translation.

### Questions and answers

`--format qa` writes, instead of the summary, every question of the meeting
with its complete answer (any meeting type, either language):

```
python -m meetingtool.summary --frames <folder> --transcript <transcript.docx> --format qa [--type requirements]
```

No list of questions is needed: they are found in the conversation. Each one
has who raised it, the answer point by point with who gave it, the minutes,
the agreement, what is pending, the deadline as it was said and a status
(resolved, resolved with a caveat, pending, out of scope); then the project's
knowledge grouped (rules, who owns and loads each piece of data, figures,
glossary, scope) and the pending items. The transcript is read first; an
answer that relied on the screen ("te muestro", "¿están viendo?") then gets
only the frames of its own span read, and what they show is written apart
from what was said. With no answer on screen, no frame is read, and the
folder may hold no frames at all. Every answer carries a verbatim fragment,
speakers, minutes, status and written dates that are checked against the
transcript: a date, or any other year, written however it is written needs that year said
in the transcript (or be the meeting's own year), and every figure of
"figures said" needs to have been said, whichever way it is written (48.000,
48,000, 48000 and "48 mil" are the same number; the figures of any other place
are not checked, so that a sum is not refused). A register that fails is asked once more and then not delivered.
It is written to `summary.md` (with `qa.json`), and the Word report is built
from it as from a summary.

## The report in Word

Once the summary is written, the report for the client is built from it,
with no network and no key, so it costs nothing and can be built again after
the summary is edited by hand:

```
python -m meetingtool.report build --frames <frames folder> [--title "<meeting title>"] \
    [--date YYYY-MM-DD] [--project <project id>] [--type <meeting type>]
```

It is written to `summary.docx` next to `summary.md`. Only the frames the
summary names are embedded, each after the paragraph that first names it,
with the minute of the meeting it shows. A named frame that is missing, a
mention that names no frame file, or two frames named as a range, stops the
build and is named. The document
is opened again before it is delivered: if a section or an image is missing,
it is not delivered.

The company that runs the analysis can give the report its own design: a
Word document or template (`.docx` or `.dotx`, never one with macros) with
its logo, header, footer, colours and fonts. What is written on its page
becomes the cover of every report. It is kept once per installation, in the
data folder; without one, reports use a neutral design:

```
python -m meetingtool.report template set <company template.dotx>
python -m meetingtool.report template show
python -m meetingtool.report template remove
python -m meetingtool.report template example <new file.docx>
```

A template that would load or run something from outside when a report is opened (a field such as
`INCLUDEPICTURE` or `DDE`, a linked picture, an attached template, an embedded object) is refused, however
the field is written in the file, and each report is checked for the same before it is delivered. A field whose
name another field builds is refused too, and a hyperlink may go only to a web page (`http`, `https`), a mail
address or a place in the document. A template may hold only these Word fields, whatever their case: `PAGE`,
`NUMPAGES`, `SECTIONPAGES`, `SECTION`, `TOC`, `PAGEREF`, `REF`, `NOTEREF`, `STYLEREF`, `HYPERLINK`, `DATE`, `TIME`,
`CREATEDATE`, `SAVEDATE`, `PRINTDATE`, `DOCPROPERTY`, `TITLE`, `SUBJECT`, `AUTHOR`, `IF`, `SEQ` and the formula (`=`);
any other field (`ADDIN`, `FILLIN`, `MERGEFIELD`...) is refused, naming it, and the company's `{placeholders}` are
not Word fields, so they are not affected. Every branch of a Markup Compatibility alternative (`mc:AlternateContent`) is judged the same way, and one
that leaves unknown what Word would read is refused, naming the part.
A Word file (a template, a Word transcript, a report) is refused, naming the part, when it holds more than 4,000 parts,
one part that expands to more than 32 MB, or parts that expand to more than 256 MB together; the bytes are counted
as they are decompressed, whatever the file says it holds.

Where the template has a field name in braces, in its body, header or
footer, the report puts that meeting's data with the template's format:
`{cliente}`, `{proyecto}`, `{reunion}`, `{fecha}` (written in the report's
language) or `{tipo}`, or their English names `{client}`, `{project}`,
`{meeting}`, `{date}`, `{type}`. The client comes from `--project`. A name in
braces that is not a field is refused when the template is set. If the
template has a Word table of contents, it lists the report's sections, each a
link to it, without page numbers (Word adds them when the table is updated);
what comes after it, or after `{informe}` alone on a line, is a model and is
left out of every report. `template show` says the file's name and what was
understood of it; `template example` writes a template to start from.

## The application

Everything above can also be done from a window, without the commands:

```
python -m meetingtool app
```

It opens the browser on a page served by this machine only (127.0.0.1): the
projects and their meetings with the summary or the register, their frames,
the Word report to open and what each cost; a form to process a new meeting
(the transcript, and the recording if there is one, uploaded from the
browser; type, language, format and spending ceiling); and the settings (the
application's language, the company's name and logo, the Gemini key, never
shown back, and the company's Word template). Keep the window it was started
from open while it is used.

The application speaks Spanish, or English if it is set so in its settings:
every screen, notice and error, those of every stage included. That is apart
from the summary's language, chosen for each meeting. The commands keep
speaking English. Everything the program says is an entry of
`meetingtool/texts/<language>.py`; another language is another such file. What
comes from outside the program (Google's reason for refusing a request, a
system error) is shown as it came, below the application's own sentence.

The company's name and logo appear at the top of every screen and in the
tab's name. The logo is a PNG or JPG of up to 1 MB; it is checked to be a real
image and kept written again, and an SVG is refused, since it could carry a
script. Both are kept in the data folder (`app-settings.json`,
`company-logo.png` or `.jpg`).

"Procesar" runs the same functions as the commands, in order: frames,
reading (for the summary), summary or register, Word report. One ceiling
covers the whole run. The meeting is added to its project only once its Word
report is built; if a stage fails, the meeting is not added and the page says
which stage failed, why and what was spent. What Gemini already answered is
not thrown away: a failed run that paid for something keeps its folder in
`<data>/<project>/processing/<run>/`, listed in the project's page, and
processing the same meeting again (the same transcript and format) continues
there and pays only what is missing. It goes when that run succeeds or when
it is discarded from the page; a run that paid nothing leaves nothing. Each
processed meeting keeps its frames, transcript, summary, report and a record
of the run in `<data>/<project>/results/<run>/`; the recording itself is not
copied. Folders of the data folder made with the commands outside a project
are listed read-only.

Everything kept in the data folder is written whole or not at all (to a
temporary file, then put in place at once), and every change to it holds the
folder's lock (`.meetingtool-write.lock`), which the application and the
commands share: two saves at once never take the same name, and a save cut
short leaves every record readable. A record that still cannot be read (one
edited by hand) is named in an error, not skipped.

Only this machine can use it: the server listens on 127.0.0.1, every request
needs the session cookie set when the browser opens the launch address (a new
token at each start), and a request from a page of another site (another
Origin, Sec-Fetch-Site or Host) is refused. `--port` fixes the port and
`--no-browser` only prints the launch address.

## Running the tests

Python 3.11 or newer, with the libraries in `pyproject.toml` installed:

```
python -m unittest discover -s tests -v
```

The `test_d1_*.py` files are INGOL's reproductions of the external review of
2026-10-02; they need INGOL's test kits, which are not part of this
repository, and are skipped without them. With the kits installed
(`~/.claude/ingol-kits`), they run with
`PYTHONPATH=<home>/.claude/ingol-kits/python`.
