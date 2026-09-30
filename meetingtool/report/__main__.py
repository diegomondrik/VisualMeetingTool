"""Command line:

    python -m meetingtool.report build --frames DIR [--title TITLE] [--date YYYY-MM-DD]
        [--project ID] [--type TYPE] [--neutral]
    python -m meetingtool.report template set FILE
    python -m meetingtool.report template show
    python -m meetingtool.report template remove
    python -m meetingtool.report template example FILE

The summary must have been written first (python -m meetingtool.summary).
Building the report uses no network and no key.
"""

import argparse
import datetime
import re
import sys
from pathlib import Path

from meetingtool.projects import store
from meetingtool.report import document, layout


def _date(value):
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise argparse.ArgumentTypeError(f"{value!r} is not a YYYY-MM-DD date")
    try:
        return datetime.date.fromisoformat(value).isoformat()
    except ValueError:
        raise argparse.ArgumentTypeError(f"{value!r} is not a valid date") from None


def _project(data_dir, project_id):
    for project in store.list_projects(data_dir or store.default_data_dir()):
        if project["id"] == project_id:
            return project
    raise document.ReportError("report.no_project", project=project_id)


def _describe(info):
    """What the kept template is and what was understood of it."""
    name = f"{info.name}, set {info.set_utc}" if info.name else "its original name was not recorded (set it again)"
    lines = [f"template: {name} ({info.path})",
             "  fills: " + (", ".join(info.fields) if info.fields else "no field"),
             f"  table of contents: {'yes' if info.tables_of_contents else 'no'}"]
    if info.start:
        where = "its table of contents" if info.start == "index" else "{informe}"
        lines.append(f"  dropped after {where}: {info.dropped} paragraph(s) with text")
    else:
        lines.append("  cover: everything on its page")
    return "\n".join(lines)


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
    build.add_argument("--project", help="the project's id, for its name and client")
    build.add_argument("--type", choices=sorted(layout.TYPES["en"]), help="the meeting's type, for {tipo}")
    build.add_argument("--neutral", action="store_true", help="ignore the company's template")
    template = commands.add_parser("template", help="the company's Word template, one per installation")
    actions = template.add_subparsers(dest="action", required=True)
    actions.add_parser("set", help="check a .docx or .dotx and keep a copy").add_argument("file")
    actions.add_parser("show", help="say whether a template is kept, and where")
    actions.add_parser("remove", help="stop using the template")
    actions.add_parser("example", help="write a template to start from").add_argument("file")
    args = parser.parse_args(argv)
    try:
        if args.command == "template":
            if args.action == "set":
                document.set_template(args.file, args.data_dir)
                print(_describe(document.template_info(args.data_dir)))
            elif args.action == "show":
                kept = document.template_info(args.data_dir)
                print(_describe(kept) if kept else "no template: reports use the neutral design")
            elif args.action == "example":
                target = Path(args.file)
                if target.exists():
                    raise document.ReportError("report.example_exists", path=str(target.resolve()))
                target.write_bytes(document.example_template())
                print(f"example template written: {target.resolve()}")
            else:
                print("template removed" if document.remove_template(args.data_dir) else "there was no template")
            return 0
        project = _project(args.data_dir, args.project) if args.project else {}
        result = document.build_report(args.frames, title=args.title, date=args.date, project_name=project.get("name"),
                                       client=project.get("client"), meeting_type=args.type,
                                       data_dir=args.data_dir, neutral=args.neutral)
    except (document.ReportError, store.ProjectError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    design = f"template {result.template}" + (" with its cover" if result.cover else "") if result.template \
        else "neutral design"
    print(f"report built in {result.seconds:.1f}s: {result.sections} section(s), {result.images} image(s), "
          f"{result.size_bytes / 1_000_000:.1f} MB, language {result.language}, {design}")
    if result.template:
        print(f"template: filled {', '.join(result.fields) or 'no field'}; {result.contents} table of contents "
              f"entr{'y' if result.contents == 1 else 'ies'}; {result.dropped} paragraph(s) of its model left out")
    print(f"written: {result.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
