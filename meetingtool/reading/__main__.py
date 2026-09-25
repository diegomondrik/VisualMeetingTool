"""Command line:

    python -m meetingtool.reading read --frames DIR
    python -m meetingtool.reading key set | status | delete
"""

import argparse
import getpass
import sys
import time

from meetingtool.reading import credentials, gemini

BILLING_NOTICE = ("Use a key from a Google Cloud project with billing enabled. On the free tier Google may use "
                  "what is sent to improve its products, and people may read it: meeting frames are client data.")


def main(argv=None, *, read_key=None, save_key=None, delete_key=None, ask_key=None,
         endpoint=gemini.ENDPOINT, sleep=time.sleep):
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    read_key = read_key or credentials.read_key
    save_key = save_key or credentials.save_key
    delete_key = delete_key or credentials.delete_key
    ask_key = ask_key or (lambda: getpass.getpass("Paste your Gemini key (it is not shown) and press Enter: "))

    parser = argparse.ArgumentParser(prog="meetingtool.reading", description="Read the extracted frames with Gemini.")
    commands = parser.add_subparsers(dest="command", required=True)
    read = commands.add_parser("read", help="read the frames of a folder")
    read.add_argument("--frames", required=True, help="folder of frame_*.jpg, outside any git repository")
    key = commands.add_parser("key", help="the Gemini key in the Windows Credential Manager")
    key.add_argument("action", choices=["set", "status", "delete"])
    args = parser.parse_args(argv)

    try:
        if args.command == "key":
            if args.action == "set":
                print(BILLING_NOTICE)
                save_key(ask_key())
                print(f"Key saved in the Windows Credential Manager as {credentials.TARGET}.")
            elif args.action == "status":
                saved = read_key()
                print(f"A key is saved ({len(saved)} characters)." if saved else "No key is saved.")
            else:
                print("Key deleted." if delete_key() else "No key was saved.")
            return 0
        saved = read_key()
        if not saved:
            print("error: no Gemini key is saved. Save yours with: python -m meetingtool.reading key set",
                  file=sys.stderr)
            return 2
        result = gemini.read_frames(args.frames, saved, endpoint=endpoint, sleep=sleep)
    except (gemini.ReadingError, credentials.CredentialError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    print(f"{result.frames} frames read in {result.requests} request(s) ({result.attempts} attempt(s)), "
          f"{result.seconds:.1f}s; tokens: input {result.input_tokens}, output {result.output_tokens}, "
          f"thinking {result.thinking_tokens}")
    print(f"written: {result.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
