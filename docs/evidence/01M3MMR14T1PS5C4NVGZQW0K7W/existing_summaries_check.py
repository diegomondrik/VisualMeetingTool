"""WI13-AC03 for 01M3MMR14T1PS5C4NVGZQW0K7W: the range check applied, with no
request, to the five real summaries in the owner's data folder. Only counts
and verdicts are printed; the summaries are client data and stay where they
are. Added after the independent review (P3-3), so the count can be run again.

    PYTHONPATH=. python docs/evidence/01M3MMR14T1PS5C4NVGZQW0K7W/existing_summaries_check.py <data folder>

The output of the recorded run is existing-summaries-check.txt next to this file.
"""

import subprocess
import sys
from pathlib import Path

from meetingtool.report import document
from meetingtool.summary import writer

FOLDERS = ["d178-relevamiento", "d178-preventa", "d178-venta", "d178-relevamiento-en", "wi09-frames"]


def main(data):
    commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip()
    print("WI13-AC03: the range check applied, with no request, to the five real summaries in the")
    print("owner's data folder (outside any repository; contents are client data and are not copied here).")
    print(f"Code: {commit} (plus any uncommitted change in the working tree).")
    print()
    for name in FOLDERS:
        folder = Path(data) / name
        text = (folder / "summary.md").read_text(encoding="utf-8")
        frames = {path.name for path in folder.glob("frame_*.jpg")}
        ranges = sum(len(writer.FRAME_RANGE.findall(line)) for line in text.splitlines())
        named = len(set(writer.FRAME_REF.findall(text)))
        try:
            writer.check_frames(text, frames)
            summary = "accepted"
        except writer.SummaryError as error:
            summary = f"refused ({str(error).split(':')[0]})"
        try:
            document.cited_frames(text, folder)
            report = "accepted"
        except document.ReportError:
            report = "refused"
        print(f"{name}: frames named {named}, ranges {ranges}; summary check {summary}; report {report}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
