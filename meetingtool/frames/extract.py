"""Extract and select the frames of a meeting recording.

The recording is decoded with PyAV, which bundles FFmpeg, so no ffmpeg
executable is needed. The selection is the original MeetingTool's (see
signals.py) with these changes: only the best `budget` candidates are held,
as JPEG bytes, so memory stays bounded; near-duplicates are found with a numpy
SSIM (similarity.py); that check, like the scoring, looks only below the
camera strip; and a near-duplicate of the previous distinct candidate is
dropped before it can take a budget place (the original dropped duplicates
only after the budget, so they crowded distinct frames out). The check after
the budget stays: removing a candidate can leave two duplicates side by side.
An optional transcript raises the score of samples near a phrase that points
at the screen (transcript.py). The three signals are computed on a small grey
copy of each sample, at most ANALYSIS_WIDTH wide, which the decoder itself
scales (INGOL D-175): on a 1080p meeting, computing them at full size took
most of the time. The frames kept, and the duplicate checks on them, still
use the full sample. The opening slide needs no special case: the
first sample has nothing to compare with, and the next one enters on time
coverage alone. Two uses of what a meeting is (INGOL D-176): a sample that
shows a person on camera never becomes a candidate (signals.is_camera_view),
and with a transcript the recording is read only until TRANSCRIPT_TAIL
seconds after its last line starts, since a recording often runs on after
everyone has stopped talking.
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

from meetingtool.frames.signals import composite_score, is_camera_view, to_gray
from meetingtool.frames.similarity import ssim
from meetingtool.frames.transcript import TranscriptError, VisualReferences

MAX_WIDTH = 1280
ANALYSIS_WIDTH = 640
MAX_HEIGHT = 720
JPEG_QUALITY = 85
DISCARD_LOG = "frames_discarded.log"
TRANSCRIPT_TAIL = 120.0


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
    boosted: int = 0      # candidates whose score the transcript raised
    boosted_in: int = 0   # of those, the ones that were below the minimum score without it
    read_until: float = None  # where reading stopped because the transcript had ended; None if it did not


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


def _saved_size(rgb):
    image = Image.fromarray(rgb)
    width, height = image.size
    if width > MAX_WIDTH or height > MAX_HEIGHT:
        scale = min(MAX_WIDTH / width, MAX_HEIGHT / height)
        image = image.resize((max(1, int(width * scale)), max(1, int(height * scale))), Image.LANCZOS)
    return image


def _jpeg(rgb):
    buffer = io.BytesIO()
    _saved_size(rgb).save(buffer, "JPEG", quality=JPEG_QUALITY)
    return buffer.getvalue()


def _analysis_gray(frame, roi_top):
    """What the three signals compare: the content area of the sample in grey,
    scaled by the decoder to at most ANALYSIS_WIDTH wide."""
    width, height = frame.width, frame.height
    if width > ANALYSIS_WIDTH:
        width, height = ANALYSIS_WIDTH, max(1, round(height * ANALYSIS_WIDTH / width))
    gray = frame.reformat(width=width, height=height, format="gray", interpolation="AREA").to_ndarray()
    return gray[int(gray.shape[0] * roi_top):, :]


def _content_gray_at_saved_size(rgb, roi_top):
    """What the check after the budget compares, before JPEG compression."""
    return to_gray(_content_area(np.asarray(_saved_size(rgb).convert("RGB")), roi_top))


def _is_near_duplicate(previous_gray, gray, threshold):
    """Whether a candidate repeats the previous distinct one, checked before the budget."""
    return previous_gray is not None and previous_gray.shape == gray.shape and ssim(previous_gray, gray) > threshold


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
                   min_score=0.15, ssim_threshold=0.95, transcript=None):
    """Select up to `budget` frames of the recording and write them to
    output_dir as frame_NNN_tHH-MM-SS.jpg, with a log of every discard.
    `transcript`, a Teams .docx or a text file with [HH:MM:SS] lines, is read
    before anything else is opened or written."""
    output_dir = Path(output_dir)
    work_tree = enclosing_git_work_tree(output_dir)
    if work_tree is not None:
        raise FramesError(
            f"output folder {output_dir.resolve()} is inside the git work tree {work_tree}; "
            "frames of a meeting must live outside any repository"
        )
    if budget < 1:
        raise FramesError("the frame budget must be at least 1")
    references = None
    if transcript is not None:
        try:
            references = VisualReferences.from_file(transcript)
        except TranscriptError as error:
            raise FramesError(str(error)) from error
    if not Path(video_path).is_file():
        # a local file only: av.open would also accept a URL and open a connection
        raise FramesError(f"recording {video_path} is not a local file")
    try:
        container = av.open(str(video_path))
    except (av.error.FFmpegError, OSError) as error:
        raise FramesError(f"cannot open recording {video_path}: {error}") from error

    discards = collections.Counter()
    log_lines = []
    # min-heap of (score, -order, timestamp, jpeg bytes), at most `budget` long. Among equal
    # scores the later candidate sorts lower and leaves first, so the earliest is kept, as in
    # the original's stable sort by score.
    pool = []
    candidate_times = []
    samples = candidates = max_pool = boosted = boosted_in = 0
    last_distinct_gray = None
    stop_at = references.last + TRANSCRIPT_TAIL if references is not None else None
    read_until = None
    try:
        stream = container.streams.video[0]
        stream.thread_type = "AUTO"  # decode on every core; frames and their order do not change
        duration = _duration(container, stream)
        interval = 1.0 / fps_analyze
        last_sampled = -interval
        last_candidate = None
        prev_gray = None
        for frame in container.decode(stream):
            if frame.pts is None:
                continue
            timestamp = float(frame.pts * stream.time_base)
            if stop_at is not None and timestamp > stop_at:
                read_until = stop_at
                break
            if timestamp - last_sampled < interval:
                continue
            last_sampled = timestamp
            samples += 1
            gray = _analysis_gray(frame, roi_top)
            if prev_gray is None:
                prev_gray = gray
                continue
            if last_candidate is not None and timestamp - last_candidate < min_gap:
                discards["minimum_gap"] += 1
                log_lines.append((timestamp, f"minimum_gap ({timestamp - last_candidate:.1f}s after the previous candidate)"))
                prev_gray = gray
                continue
            base_score = composite_score(prev_gray, gray, timestamp, duration, budget, candidate_times)
            score = references.boost(base_score, timestamp) if references else base_score
            prev_gray = gray
            if score < min_score:
                discards["low_score"] += 1
                log_lines.append((timestamp, f"low_score (score={score:.3f})"))
                continue
            if is_camera_view(gray):
                discards["camera"] += 1
                log_lines.append((timestamp, "camera (a person on camera, no screen content)"))
                continue
            candidates += 1
            candidate_times.append(timestamp)
            last_candidate = timestamp
            if score > base_score:
                boosted += 1
                boosted_in += base_score < min_score
            rgb = frame.to_ndarray(format="rgb24")  # the full sample, only for candidates
            saved_gray = _content_gray_at_saved_size(rgb, roi_top)
            if _is_near_duplicate(last_distinct_gray, saved_gray, ssim_threshold):
                discards["near_duplicate"] += 1
                log_lines.append((timestamp, "near_duplicate (before the budget)"))
                continue
            last_distinct_gray = saved_gray
            if len(pool) >= budget and score <= pool[0][0]:
                discards["budget"] += 1
                log_lines.append((timestamp, f"budget (score={score:.3f})"))
                continue
            entry = (score, -candidates, timestamp, _jpeg(rgb))
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
    return ExtractionResult(duration, samples, candidates, max_pool, kept, kept_times, candidate_times, discards,
                            boosted, boosted_in, read_until)
