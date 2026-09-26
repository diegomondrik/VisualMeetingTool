"""Command line:

    python -m meetingtool.summary --frames DIR --transcript FILE
        [--project ID --title TITLE --date YYYY-MM-DD] [--type TYPE] [--language es|en]

The frames must have been read first (python -m meetingtool.reading read).
"""

import argparse
import sys
import time

from meetingtool.reading import credentials, gemini
from meetingtool.summary import writer


def main(argv=None, *, read_key=None, endpoint=gemini.ENDPOINT, sleep=time.sleep):
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    read_key = read_key or credentials.read_key
    parser = argparse.ArgumentParser(prog="meetingtool.summary", description="Write the meeting summary with Gemini.")
    parser.add_argument("--frames", required=True, help="the frames folder, already read")
    parser.add_argument("--transcript", required=True, help="the transcript (Teams .docx or [HH:MM:SS] text)")
    parser.add_argument("--project", help="add the meeting to this project (its id) and use what it knows")
    parser.add_argument("--title", help="the meeting's title (needed with --project)")
    parser.add_argument("--date", help="the meeting's date, YYYY-MM-DD (needed with --project)")
    parser.add_argument("--type", dest="meeting_type", choices=sorted(writer.MEETING_TYPES),
                        help="add the sections for this kind of meeting")
    parser.add_argument("--language", choices=sorted(writer.SECTIONS), help="default: the transcript's language")
    parser.add_argument("--video", help="the recording, stored with the meeting in the project")
    parser.add_argument("--data-dir", help="the projects' data folder (default: as for meetingtool.projects)")
    parser.add_argument("--max-cost", type=float, default=writer.MAX_COST_USD,
                        help=f"spend budget in US$ (default {writer.MAX_COST_USD:.2f}); a request that could go "
                             "over it is not sent")
    args = parser.parse_args(argv)
    try:
        saved = read_key()
        if not saved:
            print("error: no Gemini key is saved. Save yours with: python -m meetingtool.reading key set",
                  file=sys.stderr)
            return 2
        result = writer.write_summary(args.frames, args.transcript, saved, data_dir=args.data_dir,
                                      project=args.project, title=args.title, date=args.date,
                                      meeting_type=args.meeting_type, language=args.language, recording=args.video,
                                      endpoint=endpoint, max_cost_usd=args.max_cost, sleep=sleep)
    except (gemini.ReadingError, credentials.CredentialError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
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
