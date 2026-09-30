"""Command-line entry point: `python -m meetingtool`, and `meetingtool app`."""

import argparse
import sys

from meetingtool import __version__


def main(argv=None):
    parser = argparse.ArgumentParser(prog="meetingtool")
    parser.add_argument("--version", action="version", version=f"meetingtool {__version__}")
    commands = parser.add_subparsers(dest="command")
    app = commands.add_parser("app", help="open the application in the browser; only this machine can reach it")
    app.add_argument("--data-dir", help="the data folder (default: as for meetingtool.projects)")
    app.add_argument("--port", type=int, default=0, help="the port (default: a free one)")
    app.add_argument("--no-browser", action="store_true", help="do not open the browser")
    args = parser.parse_args(argv)
    if args.command == "app":
        # Imported only here: the entry point itself needs only the standard library.
        from meetingtool.app.server import serve

        return serve(args.data_dir, args.port, not args.no_browser)
    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
