"""Keeps client meeting data out of the repository.

Recordings, audio, extracted frames, transcripts and reports belong to
clients and must never be tracked by git. `.gitignore` keeps them out by
accident; this guard is the check that fails if one gets in anyway (for
example with `git add -f`). A path is meeting data when any of three rules
matches: its extension, its file name, or the root folder it lives under.
"""

import subprocess
from pathlib import PurePosixPath

VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".wmv", ".m4v"}
AUDIO_EXTENSIONS = {".m4a", ".wav", ".mp3", ".aac", ".ogg", ".flac", ".wma", ".opus"}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".tif", ".tiff", ".heic"}
SUBTITLE_EXTENSIONS = {".vtt", ".srt"}
DOCUMENT_EXTENSIONS = {".docx", ".doc", ".pdf", ".pptx", ".xlsx"}

MEETING_DATA_EXTENSIONS = frozenset(
    VIDEO_EXTENSIONS | AUDIO_EXTENSIONS | IMAGE_EXTENSIONS | SUBTITLE_EXTENSIONS | DOCUMENT_EXTENSIONS
)

# Output names of the original MeetingTool pipeline: report_*.md,
# handoff_*.json, transcript*.txt. The extension is part of the rule so a
# code module such as report_writer.py stays allowed.
MEETING_OUTPUT_PREFIXES = ("report_", "handoff_", "transcript")
MEETING_OUTPUT_EXTENSIONS = frozenset({".md", ".txt", ".json"})

# Root folders reserved for meeting data; the same names deeper in the tree
# are ordinary code or test folders.
MEETING_DATA_ROOT_FOLDERS = frozenset({"meetings", "projects", "frames"})


def is_meeting_data(path):
    """Return True when the repository-relative path is meeting data."""
    posix = PurePosixPath(path)
    name = posix.name.lower()
    suffix = posix.suffix.lower()
    if suffix in MEETING_DATA_EXTENSIONS:
        return True
    if name.startswith(MEETING_OUTPUT_PREFIXES) and suffix in MEETING_OUTPUT_EXTENSIONS:
        return True
    return len(posix.parts) > 1 and posix.parts[0].lower() in MEETING_DATA_ROOT_FOLDERS


def meeting_data_paths(paths):
    """Return the paths that are meeting data, sorted."""
    return sorted(p for p in paths if is_meeting_data(p))


def tracked_paths(repository):
    """Return every path git tracks in the given repository."""
    result = subprocess.run(
        ["git", "-C", str(repository), "ls-files", "-z"],
        check=True,
        capture_output=True,
    )
    return [p for p in result.stdout.decode("utf-8").split("\0") if p]


def check_repository(repository):
    """Return the tracked meeting-data paths; an empty list means clean."""
    return meeting_data_paths(tracked_paths(repository))
