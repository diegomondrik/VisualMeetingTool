"""Keeps client meeting data out of the repository.

Recordings, audio, transcript exports and Word reports belong to clients and
must never be tracked by git. `.gitignore` keeps them out by accident; this
guard is the check that fails if one gets in anyway (for example with
`git add -f`).
"""

import subprocess
from pathlib import PurePosixPath

MEETING_DATA_EXTENSIONS = frozenset({".mp4", ".mov", ".m4a", ".wav", ".docx", ".vtt"})


def meeting_data_paths(paths):
    """Return the paths whose extension marks them as meeting data."""
    return sorted(p for p in paths if PurePosixPath(p).suffix.lower() in MEETING_DATA_EXTENSIONS)


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
