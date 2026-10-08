"""WI21-AC04: what reading to the end costs and gives, on a synthetic
recording, with no Gemini (the owner chose a synthetic recording over the
real meeting on 2026-10-05).

    python docs/evidence/01M474JN9F7N86SHHSKZ41Q1VY/synthetic_run.py <repository> <work folder outside it>

Run once from a fresh clone of main and once from a fresh clone of the
branch: the repository given is the one whose meetingtool is measured. The
recording is the same each time (made by this script with the test
helpers): 8 minutes at 4 fps, slides A, B and C during the meeting, the
transcript's last line at 3:20 while slide B is still explained, slide C
from 5:40 (past the old cut at 3:20 + 120 s), and a tail from 6:30 to 8:00
showing one gallery-like still image after everyone stopped talking.
"""

import sys
import time
from pathlib import Path


def main(repository, work):
    repository, work = Path(repository).resolve(), Path(work)
    sys.path.insert(0, str(repository))
    from meetingtool.frames import extract as extract_module
    from meetingtool.frames.extract import extract_frames
    from tests.test_frames import SLIDE_A, SLIDE_B, SLIDE_C, which_slide, write_video
    import numpy as np

    work.mkdir(parents=True, exist_ok=False)
    video = work / "synthetic-meeting.mp4"
    gallery = np.full_like(SLIDE_A, 60)  # a flat dark still, like an empty gallery of participants
    write_video(video, [(SLIDE_A, 100, False), (SLIDE_B, 240, False), (SLIDE_C, 50, False), (gallery, 90, False)])
    transcript = work / "synthetic-meeting.txt"
    transcript.write_text("[00:00:05] Ana:\nEmpezamos con el tablero.\n"
                          "[00:01:45] Luis:\nEn la pantalla se ve la columna de costos.\n"
                          "[00:03:20] Ana:\nTe explico el resto del tablero, columna por columna, y cerramos con el "
                          "resumen que ves en la pantalla.\n", encoding="utf-8")
    last_line = 200.0
    started = time.monotonic()
    result = extract_frames(video, work / "frames", transcript=transcript)
    seconds = time.monotonic() - started
    slides = [which_slide(work / "frames" / name) for name in result.kept]
    after = [t for t in result.kept_times if t > last_line]
    print(f"meetingtool from: {repository}")
    print(f"cut in the code: {'yes, TRANSCRIPT_TAIL = ' + str(extract_module.TRANSCRIPT_TAIL) if hasattr(extract_module, 'TRANSCRIPT_TAIL') else 'no'}")
    print(f"duration {result.duration:.1f}s, {result.samples} samples, {result.candidates} candidates, "
          f"{len(result.kept)} frames kept, {seconds:.1f}s")
    print(f"frames kept at (s): {[round(t, 1) for t in result.kept_times]}")
    print(f"slides of the frames kept (nearest of A, B, C): {slides}")
    print(f"frames kept after the transcript's last line ({last_line:.0f}s): {len(after)} at {[round(t, 1) for t in after]}")
    print(f"slide C kept: {'C' in slides}")


if __name__ == "__main__":
    main(*sys.argv[1:3])
