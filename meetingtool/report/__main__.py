"""Command line:

    python -m meetingtool.report build --frames DIR [--title TITLE] [--date YYYY-MM-DD]
        [--project ID] [--neutral]
    python -m meetingtool.report template set FILE
    python -m meetingtool.report template show
    python -m meetingtool.report template remove

The summary must have been written first (python -m meetingtool.summary).
Building the report uses no network and no key.
"""

import argparse
import datetime
import re
import sys

from meetingtool.projects import store
from meetingtool.report import document


def _date(value):
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise argparse.ArgumentTypeError(f"{value!r} is not a YYYY-MM-DD date")
    try:
        return datetime.date.fromisoformat(value).isoformat()
    except ValueError:
        raise argparse.ArgumentTypeError(f"{value!r} is not a valid date") from None


def _project_name(data_dir, project_id):
    for project in store.list_projects(data_dir or store.default_data_dir()):
        if project["id"] == project_id:
            return project["name"]
    raise document.ReportError(f"there is no project {project_id!r}; list them with python -m meetingtool.projects")


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(prog="meetingtool.report", description="Build the meeting report in Word.")
    parser.add_argument("--data-dir", help="the data folder (default: as for meetingtool.projects)")
    commands = parser.add_subparsers(dest="command", required=True)
    build = commands.add_parser("build", help="build summary.docx from summary.md and its frames")
    build.add_argument("--frames", required=True, help="the frames folder, with summary.md")
    build.add_argument("--title", help="the meeting's title (default: a generic one)")
    build.add_argument("--date", type=_date, help="the meeting's date, YYYY-MM-DD")
    build.add_argument("--project", help="the project's id, to print its name")
    build.add_argument("--neutral", action="store_true", help="ignore the company's template")
    template = commands.add_parser("template", help="the company's Word template, one per installation")
    actions = template.add_subparsers(dest="action", required=True)
    actions.add_parser("set", help="check a .docx or .dotx and keep a copy").add_argument("file")
    actions.add_parser("show", help="say whether a template is kept, and where")
    actions.add_parser("remove", help="stop using the template")
    args = parser.parse_args(argv)
    try:
        if args.command == "template":
            if args.action == "set":
                print(f"template kept: {document.set_template(args.file, args.data_dir)}")
            elif args.action == "show":
                kept = document.stored_template(args.data_dir)
                print(f"template: {kept}" if kept else "no template: reports use the neutral design")
            else:
                print("template removed" if document.remove_template(args.data_dir) else "there was no template")
            return 0
        project_name = _project_name(args.data_dir, args.project) if args.project else None
        result = document.build_report(args.frames, title=args.title, date=args.date, project_name=project_name,
                                       data_dir=args.data_dir, neutral=args.neutral)
    except (document.ReportError, store.ProjectError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    design = f"template {result.template}" + (" with its cover" if result.cover else "") if result.template \
        else "neutral design"
    print(f"report built in {result.seconds:.1f}s: {result.sections} section(s), {result.images} image(s), "
          f"{result.size_bytes / 1_000_000:.1f} MB, language {result.language}, {design}")
    print(f"written: {result.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
