"""Command line for projects and meetings: `python -m meetingtool.projects`."""

import argparse
import sys

from meetingtool.projects import store


def build_parser():
    parser = argparse.ArgumentParser(prog="meetingtool.projects", description="Projects and their meetings.")
    parser.add_argument("--data-dir", help=f"data folder (default: ${store.DATA_DIR_ENV} or ~/{store.DEFAULT_DATA_DIR_NAME})")
    commands = parser.add_subparsers(dest="command", required=True)

    new = commands.add_parser("new", help="create a project")
    new.add_argument("--name", required=True)
    new.add_argument("--client", default="")
    new.add_argument("--context", default="")

    commands.add_parser("list", help="list projects")

    add = commands.add_parser("add-meeting", help="add a meeting to a project")
    add.add_argument("--project", required=True, help="project identifier")
    add.add_argument("--title", required=True)
    add.add_argument("--date", required=True, help="YYYY-MM-DD")
    add.add_argument("--type", default="", dest="meeting_type")
    add.add_argument("--recording", default="")
    add.add_argument("--transcript", default="")
    add.add_argument("--summary", default="")
    add.add_argument("--key-point", action="append", default=[], dest="key_points")

    meetings = commands.add_parser("meetings", help="list a project's meetings in date order")
    meetings.add_argument("--project", required=True)

    knowledge = commands.add_parser("knowledge", help="print a project's accumulated knowledge")
    knowledge.add_argument("--project", required=True)
    return parser


def main(argv=None):
    # Summaries may hold any character; a redirected Windows console would
    # otherwise encode with the ANSI code page and fail.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    args = build_parser().parse_args(argv)
    data_dir = args.data_dir or store.default_data_dir()
    try:
        if args.command == "new":
            record = store.create_project(data_dir, args.name, args.client, args.context)
            print(f"created project {record['id']}")
        elif args.command == "list":
            for record in store.list_projects(data_dir):
                print(f"{record['id']}\t{record['name']}\t{record['client']}")
        elif args.command == "add-meeting":
            record = store.add_meeting(
                data_dir, args.project, args.title, args.date, args.meeting_type,
                args.recording, args.transcript, args.summary, args.key_points,
            )
            print(f"added meeting {record['id']}")
        elif args.command == "meetings":
            for record in store.list_meetings(data_dir, args.project):
                print(f"{record['date']}\t{record['id']}\t{record['title']}")
        elif args.command == "knowledge":
            print(store.knowledge_context(data_dir, args.project), end="")
    except store.ProjectError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
