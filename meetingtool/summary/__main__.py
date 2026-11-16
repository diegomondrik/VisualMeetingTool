"""Command line:

    python -m meetingtool.summary --frames DIR --transcript FILE
        [--project ID --title TITLE --date YYYY-MM-DD] [--type TYPE] [--language es|en] [--format summary|qa]
        [--notes FILE [--notes-by NAME]] [--model MODEL]

TYPE is one of presale, negotiation, requirements, kickoff, status, technical
or training (INGOL D-178).

The summary needs the frames read first (python -m meetingtool.reading read).
The question-and-answer register (--format qa) does not: it reads the
transcript first, and then only the frames of the answers that relied on the
screen; with no video, DIR is any folder outside a repository for the result.

--notes gives the summary a participant's notes (.docx or .txt) as a second
source, and --notes-by who took them (WI-2.0.0); the register takes none.

--model chooses who writes the summary (WI-2.0.0, amendment 1): gpt-6.1-sol
(the default, OpenAI), claude-opus-5-5 or claude-sonnet-5-5 (Anthropic), or
gemini-flash-latest (Google). Each provider's key is its own, in the Windows
Credential Manager: Gemini's is saved with python -m meetingtool.reading key
set or in the application's Settings, the others in Settings.
The frames and the register are read by Gemini, whatever the model.
"""

import argparse
import sys
import time

from meetingtool.reading import credentials, gemini
from meetingtool.summary import providers, qa, writer


def main(argv=None, *, read_key=None, endpoint=gemini.ENDPOINT, endpoints=None, sleep=time.sleep):
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    read_key = read_key or credentials.read_key
    parser = argparse.ArgumentParser(prog="meetingtool.summary", description="Write the meeting summary with Gemini.")
    parser.add_argument("--frames", required=True, help="the frames folder, already read (with --format qa, "
                                                        "read or not, or any folder for the result)")
    parser.add_argument("--transcript", required=True, help="the transcript (Teams .docx or [HH:MM:SS] text)")
    parser.add_argument("--project", help="add the meeting to this project (its id) and use what it knows")
    parser.add_argument("--title", help="the meeting's title (needed with --project)")
    parser.add_argument("--date", help="the meeting's date, YYYY-MM-DD (needed with --project)")
    # No argparse choices: the writer refuses an unknown or retired type and
    # says what replaces a retired one, before any request.
    parser.add_argument("--type", dest="meeting_type", metavar="TYPE",
                        help="the kind of meeting: presale, negotiation and requirements (the discovery of a "
                             "project to be built) change how the whole summary reads it; kickoff, status, "
                             "technical and training add their sections")
    parser.add_argument("--language", choices=sorted(writer.SECTIONS),
                        help="the summary's language, whatever the meeting's (default: the transcript's language)")
    parser.add_argument("--format", choices=qa.FORMATS, default="summary",
                        help="summary (default), or qa: every question of the meeting with its complete answer, "
                             "reading only the frames of the answers that relied on the screen")
    parser.add_argument("--video", help="the recording, stored with the meeting in the project")
    parser.add_argument("--notes", help="a participant's notes (.docx or .txt), a second source for the summary")
    parser.add_argument("--notes-by", default="", help="who took the notes (default: a participant)")
    parser.add_argument("--data-dir", help="the projects' data folder (default: as for meetingtool.projects)")
    parser.add_argument("--model", default=providers.DEFAULT_MODEL,
                        help=f"who writes the summary: {', '.join(providers.MODELS)} (default "
                             f"{providers.DEFAULT_MODEL}); the register is always written by Gemini")
    parser.add_argument("--max-cost", type=float, default=None,
                        help="estimated spending ceiling in US$ (default: two attempts at the model's worst case, "
                             f"never under {writer.MAX_COST_USD:.2f}), from list prices; a request that could go "
                             "over it is not sent, and a run in which an answer used more tokens than estimated "
                             "stops")
    args = parser.parse_args(argv)
    try:
        spec = providers.model(args.model)
    except gemini.ReadingError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    summary = args.format != "qa"
    provider = spec.provider if summary else providers.GEMINI
    if args.max_cost is None:
        args.max_cost = (providers.summary_ceiling(args.model, writer.MAX_OUTPUT_TOKENS) if summary
                         else writer.MAX_COST_USD)
    write = qa.write_register if args.format == "qa" else writer.write_summary
    if args.notes and args.format == "qa":
        print("error: --notes goes with the summary; the register (--format qa) takes no notes", file=sys.stderr)
        return 2
    notes = {"notes": args.notes, "notes_author": args.notes_by} if args.notes else {}
    if summary:  # the model and its own address (the tests' fake servers, through endpoints)
        notes["model"] = args.model
        endpoint = endpoint if provider is providers.GEMINI else (endpoints or {}).get(provider.name)
    try:
        # Gemini's key is the credential functions' default (as before); another provider's goes by its name.
        saved = read_key() if provider is providers.GEMINI else read_key(provider.key_name)
        if not saved:
            where = ("python -m meetingtool.reading key set" if provider is providers.GEMINI
                     else "the application's Settings")
            print(f"error: no {provider.label} key is saved. Save yours with: {where}", file=sys.stderr)
            return 2
        result = write(args.frames, args.transcript, saved, data_dir=args.data_dir, project=args.project,
                       title=args.title, date=args.date, meeting_type=args.meeting_type, language=args.language,
                       recording=args.video, endpoint=endpoint, max_cost_usd=args.max_cost, sleep=sleep, **notes)
    except (gemini.ReadingError, credentials.CredentialError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    if args.format == "qa":
        print(f"register written in {result.seconds:.1f}s ({result.questions} question(s), language "
              f"{result.language}); frames read: {result.frames_read} of {result.frames_total}")
        print("on screen: " + (", ".join(f"{identifier} ({start})" for identifier, start in result.on_screen)
                               or "none"))
        for stage in result.stages:
            print(f"stage {stage.name}: {stage.attempts} attempt(s), US${stage.cost_usd:.3f}")
        print(f"tokens: input {result.input_tokens}, output {result.output_tokens}, thinking "
              f"{result.thinking_tokens}; estimated cost US${result.estimated_cost_usd:.3f} (budget "
              f"US${args.max_cost:.2f}); model {', '.join(result.model_versions) or 'not reported'}")
    else:
        print(f"summary written in {result.seconds:.1f}s ({result.attempts} attempt(s), language {result.language}); "
              f"tokens: input {result.input_tokens}, output {result.output_tokens}, thinking {result.thinking_tokens}; "
              f"estimated cost US${result.estimated_cost_usd:.3f} (budget US${args.max_cost:.2f}); "
              f"model {', '.join(result.model_versions) or 'not reported'}")
    print(f"written: {result.output}")
    if result.meeting_id:
        print(f"added to project {args.project} as meeting {result.meeting_id}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
