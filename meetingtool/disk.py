"""How the program writes what it keeps (WI20; the external review of
2026-10-02, R01).

The same two rules for the application, the terminal commands, and two of
either at once:

- A file is written whole or not at all: to a temporary file of a unique
  name next to it, flushed to the disk, and put in place with one replace.
  Whoever reads it sees it as it was before or as it is after, never half of
  it; a process that dies while writing leaves the file as it was (and, at
  most, a hidden temporary file beside it).
- Whatever reads, changes and writes the data folder, or chooses a new
  identifier in it, does so holding the folder's lock: a file of the folder
  locked through the system, so the lock holds between processes, and the
  system drops it when the process ends, however it ends. A lock taken in
  memory would hold only inside one process (the review's finding: the
  application's own lock did not cover the terminal).

Only the standard library is used, and the program's list of messages.
"""

import contextlib
import os
import secrets
import threading
import time
from pathlib import Path

from meetingtool import texts

LOCK_NAME = ".meetingtool-write.lock"
# How long a writer waits for another one before giving up: every write
# under the lock takes milliseconds, so a long wait means something is stuck.
LOCK_WAIT_SECONDS = 30.0
_POLL_SECONDS = 0.02
# On Windows a file cannot be replaced while a reader has it open; readers
# hold it for an instant, so the replace is tried again for about a second.
_REPLACE_TRIES = 50

_held = threading.local()


class LockTimeout(texts.Failure):
    """The folder's lock was not free within the wait."""


def replace(source, target):
    """os.replace, tried again for a moment while the target is open for
    reading (Windows refuses to replace an open file)."""
    for attempt in range(_REPLACE_TRIES):
        try:
            os.replace(source, target)
            return
        except PermissionError:
            if attempt == _REPLACE_TRIES - 1:
                raise
            time.sleep(_POLL_SECONDS)


def write_bytes(path, data):
    """Write data to path whole or not at all."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{secrets.token_hex(6)}.partial")
    try:
        with open(temporary, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        replace(temporary, path)
    except BaseException:
        with contextlib.suppress(OSError):
            temporary.unlink()
        raise


def write_text(path, text, newline=None):
    """Write text as UTF-8, whole or not at all. With newline=None every
    "\\n" becomes the system's line ending, as a file opened for text does;
    newline="\\n" keeps it."""
    if newline is None:
        newline = os.linesep
    if newline != "\n":
        text = text.replace("\n", newline)
    write_bytes(path, text.encode("utf-8"))


def _try_lock(handle):
    handle.seek(0)
    if os.name == "nt":
        import msvcrt

        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
    else:
        import fcntl

        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)


def _unlock(handle):
    handle.seek(0)
    if os.name == "nt":
        import msvcrt

        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
    else:
        import fcntl

        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


@contextlib.contextmanager
def locked(folder, wait=None):
    """Hold folder's lock while the block runs; LockTimeout if another
    process or thread holds it longer than `wait` seconds (by default
    LOCK_WAIT_SECONDS). A thread that already holds it goes on: an operation
    under the lock may call another one that takes it."""
    folder = Path(folder)
    key = os.path.normcase(os.path.abspath(folder))
    depth = getattr(_held, "depth", None)
    if depth is None:
        depth = _held.depth = {}
    if depth.get(key):
        depth[key] += 1
        try:
            yield
        finally:
            depth[key] -= 1
        return
    folder.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + (LOCK_WAIT_SECONDS if wait is None else wait)
    with open(folder / LOCK_NAME, "a+b") as handle:
        while True:
            try:
                _try_lock(handle)
                break
            except OSError:
                if time.monotonic() >= deadline:
                    raise LockTimeout("projects.busy", folder=str(folder.resolve()),
                                      seconds=float(LOCK_WAIT_SECONDS if wait is None else wait)) from None
                time.sleep(_POLL_SECONDS)
        depth[key] = 1
        try:
            yield
        finally:
            del depth[key]
            _unlock(handle)
