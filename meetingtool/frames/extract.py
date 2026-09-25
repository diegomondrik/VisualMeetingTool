"""Extract and select the frames of a meeting recording.

The recording is decoded with PyAV, which bundles FFmpeg, so no ffmpeg
executable is needed. The selection is the original MeetingTool's (see
signals.py) with three changes: only the best `budget` candidates are held,
as JPEG bytes, so memory stays bounded; near-duplicates are found with a numpy
SSIM (similarity.py); and that check, like the scoring, looks only below the
camera strip. The opening slide needs no special case: the first sample has
nothing to compare with, and the next one enters on time coverage alone.
"""

import collections
import dataclasses
import datetime
import heapq
import io
from pathlib import Path

import av
import numpy as np
from PIL import Image

from meetingtool.frames.signals import composite_score, to_gray
from meetingtool.frames.similarity import ssim

MAX_WIDTH = 1280
MAX_HEIGHT = 720
JPEG_QUALITY = 85
DISCARD_LOG = "frames_discarded.log"


class FramesError(Exception):
    """An extraction that cannot be carried out."""


@dataclasses.dataclass
class ExtractionResult:
    duration: float
    samples: int
    candidates: int
    max_pool: int
    kept: list
    kept_times: list
    candidate_times: list
    discards: collections.Counter


def enclosing_git_work_tree(path):
    """Return the folder holding .git that contains path, or None."""
    current = Path(path).resolve()
    for candidate in (current, *current.parents):
        if (candidate / ".git").exists():
            return candidate
    return None


def timestamp_label(seconds):
    total = int(seconds)
    return f"t{total // 3600:02d}-{total % 3600 // 60:02d}-{total % 60:02d}"


def _content_area(rgb, roi_top):
    return rgb[int(rgb.shape[0] * roi_top):, :]


def _jpeg(rgb):
    image = Image.fromarray(rgb)
    width, height = image.size
    if width > MAX_WIDTH or height > MAX_HEIGHT:
        scale = min(MAX_WIDTH / width, MAX_HEIGHT / height)
        image = image.resize((max(1, int(width * scale)), max(1, int(height * scale))), Image.LANCZOS)
    buffer = io.BytesIO()
    image.save(buffer, "JPEG", quality=JPEG_QUALITY)
    return buffer.getvalue()


def _content_gray_of_jpeg(data, roi_top):
    rgb = np.asarray(Image.open(io.BytesIO(data)).convert("RGB"))
    return to_gray(_content_area(rgb, roi_top))


def _duration(container, stream):
    if container.duration:
        return float(container.duration / av.time_base)
    if stream.duration and stream.time_base:
        return float(stream.duration * stream.time_base)
    return 0.0


def extract_frames(video_path, output_dir, budget=150, fps_analyze=2.0, roi_top=0.15, min_gap=3.0,
                   min_score=0.15, ssim_threshold=0.95):
    """Select up to `budget` frames of the recording and write them to
    output_dir as frame_NNN_tHH-MM-SS.jpg, with a log of every discard."""
    output_dir = Path(output_dir)
    work_tree = enclosing_git_work_tree(output_dir)
    if work_tree is not None:
        raise FramesError(
            f"output folder {output_dir.resolve()} is inside the git work tree {work_tree}; "
            "frames of a meeting must live outside any repository"
        )
    if budget < 1:
        raise FramesError("the frame budget must be at least 1")
    try:
        container = av.open(str(video_path))
    except (av.error.FFmpegError, OSError) as error:
        raise FramesError(f"cannot open recording {video_path}: {error}") from error

    discards = collections.Counter()
    log_lines = []
    pool = []  # min-heap of (score, order, timestamp, jpeg bytes), at most `budget` long
    candidate_times = []
    samples = candidates = max_pool = 0
    try:
        stream = container.streams.video[0]
        duration = _duration(container, stream)
        interval = 1.0 / fps_analyze
        last_sampled = -interval
        last_candidate = None
        prev_gray = None
        for frame in container.decode(stream):
            if frame.pts is None:
                continue
            timestamp = float(frame.pts * stream.time_base)
            if timestamp - last_sampled < interval:
                continue
            last_sampled = timestamp
            samples += 1
            rgb = frame.to_ndarray(format="rgb24")
            gray = to_gray(_content_area(rgb, roi_top))
            if prev_gray is None:
                prev_gray = gray
                continue
            if last_candidate is not None and timestamp - last_candidate < min_gap:
                discards["minimum_gap"] += 1
                log_lines.append((timestamp, f"minimum_gap ({timestamp - last_candidate:.1f}s after the previous candidate)"))
                prev_gray = gray
                continue
            score = composite_score(prev_gray, gray, timestamp, duration, budget, candidate_times)
            prev_gray = gray
            if score < min_score:
                discards["low_score"] += 1
                log_lines.append((timestamp, f"low_score (score={score:.3f})"))
                continue
            candidates += 1
            candidate_times.append(timestamp)
            last_candidate = timestamp
            if len(pool) >= budget and score <= pool[0][0]:
                discards["budget"] += 1
                log_lines.append((timestamp, f"budget (score={score:.3f})"))
                continue
            entry = (score, candidates, timestamp, _jpeg(rgb))
            if len(pool) >= budget:
                dropped = heapq.heappushpop(pool, entry)
                discards["budget"] += 1
                log_lines.append((dropped[2], f"budget (score={dropped[0]:.3f})"))
            else:
                heapq.heappush(pool, entry)
            max_pool = max(max_pool, len(pool))
    except av.error.FFmpegError as error:
        raise FramesError(f"cannot decode recording {video_path}: {error}") from error
    finally:
        container.close()

    output_dir.mkdir(parents=True, exist_ok=True)
    for old in output_dir.glob("frame_*.jpg"):
        old.unlink()
    kept = []
    kept_times = []
    last_kept_gray = None
    for score, _, timestamp, data in sorted(pool, key=lambda entry: entry[2]):
        gray = _content_gray_of_jpeg(data, roi_top)
        if last_kept_gray is not None and last_kept_gray.shape == gray.shape:
            similarity = ssim(last_kept_gray, gray)
            if similarity > ssim_threshold:
                discards["near_duplicate"] += 1
                log_lines.append((timestamp, f"near_duplicate (ssim={similarity:.3f})"))
                continue
        name = f"frame_{len(kept) + 1:03d}_{timestamp_label(timestamp)}.jpg"
        (output_dir / name).write_bytes(data)
        kept.append(name)
        kept_times.append(timestamp)
        last_kept_gray = gray

    run = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    lines = [f"{run} | {timestamp_label(t)} | {reason}" for t, reason in sorted(log_lines, key=lambda x: x[0])]
    (output_dir / DISCARD_LOG).write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    return ExtractionResult(duration, samples, candidates, max_pool, kept, kept_times, candidate_times, discards)
