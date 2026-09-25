"""Command line: `python -m meetingtool.frames --video REC --out DIR`."""

import argparse
import sys

from meetingtool.frames.extract import FramesError, extract_frames


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(prog="meetingtool.frames", description="Select the frames of a meeting recording.")
    parser.add_argument("--video", required=True, help="the meeting recording")
    parser.add_argument("--out", required=True, help="output folder, outside any git repository")
    parser.add_argument("--budget", type=int, default=150, help="maximum frames to keep (default 150)")
    parser.add_argument("--fps", type=float, default=2.0, help="samples analysed per second (default 2)")
    args = parser.parse_args(argv)
    try:
        result = extract_frames(args.video, args.out, budget=args.budget, fps_analyze=args.fps)
    except FramesError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    print(f"duration {result.duration:.1f}s, {result.samples} samples, {result.candidates} candidates, "
          f"{len(result.kept)} frames kept")
    for reason, count in sorted(result.discards.items()):
        print(f"discarded {reason}: {count}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
