"""Command-line entry point: `python -m meetingtool`."""

import argparse
import sys

from meetingtool import __version__


def main(argv=None):
    parser = argparse.ArgumentParser(prog="meetingtool")
    parser.add_argument("--version", action="version", version=f"meetingtool {__version__}")
    parser.parse_args(argv)
    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
