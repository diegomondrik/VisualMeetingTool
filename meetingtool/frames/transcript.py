"""The transcript boost: a sample near a phrase that points at the screen
scores higher.

Ported from the original MeetingTool (tools/extract_frames.py): a sample
within WINDOW seconds of a transcript block holding a visual-reference phrase
gets BOOST added to its score, capped at 1. Two changes: phrases match whole
words, not substrings (the original's "ver" matched inside "verdad" and
"volver"); and a Teams .docx is read with the standard library instead of
python-docx. The transcript's content stays in memory; nothing here writes it.
"""

import bisect
import codecs
import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree

from meetingtool import texts, word_package

BOOST = 0.12
WINDOW = 30.0

VISUAL_REFERENCE_PHRASES = (
    "mirá", "look at", "ver", "acá ven", "el número",
    "on screen", "right here", "this shows", "notice", "en pantalla",
    "as you can see", "here you can see", "if you look",
    "I'm showing", "pointing", "fijate", "acá vemos",
)

_PHRASE = re.compile(
    r"(?<!\w)(?:" + "|".join(re.escape(p) for p in VISUAL_REFERENCE_PHRASES) + r")(?!\w)",
    re.IGNORECASE,
)
# Teams: "Speaker Name   1:22" or "Speaker Name   1:02:03", the text on the lines after.
# The name ends on a character that is not a space, so a long run of spaces is tried from one place
# only (with "(.+?)\s{2,}" 20,000 spaces took about 6 s: every start of the run was tried again).
_SPEAKER_TIME = re.compile(r"^(.*?\S)\s{2,}(\d{1,2}:\d{2}(?::\d{2})?)\s*$")
# Teams without speaker names: the time alone on its line ("0:02", "1:02:03"), the words on the lines after.
# It starts a block only in a transcript with no "Speaker   M:SS" or "[HH:MM:SS]" line.
# Minutes and seconds are below 60, so a line such as "10:75" is not a time.
_TIME_ALONE = re.compile(r"^\d{1,2}:[0-5]\d(?::[0-5]\d)?$")
# The original's cleaned text: "[01:02:03] Speaker:".
_BRACKET_TIME = re.compile(r"^\[(\d{1,2}):(\d{2}):(\d{2})\]\s*(.*)$")
_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


class TranscriptError(texts.Failure):
    """A transcript that cannot be read into timed blocks."""


def _seconds(clock):
    parts = [int(p) for p in clock.split(":")]
    while len(parts) < 3:
        parts.insert(0, 0)
    hours, minutes, seconds = parts
    return hours * 3600 + minutes * 60 + seconds


def _docx_lines(path):
    try:
        root = ElementTree.fromstring(word_package.read_parts(path, ["word/document.xml"])["word/document.xml"])
    except word_package.PackageError as error:
        raise TranscriptError("transcript.word_too_big", path=str(path), reason=error.message) from None
    except (zipfile.BadZipFile, KeyError, ElementTree.ParseError, OSError) as error:
        raise TranscriptError("transcript.word_unreadable", path=str(path),
                              detail=texts.External(str(error))) from error
    lines = []
    for paragraph in root.iter(f"{_W}p"):
        pieces = []
        for node in paragraph.iter():
            if node.tag == f"{_W}t":
                pieces.append(node.text or "")
            elif node.tag == f"{_W}br":
                pieces.append("\n")
            elif node.tag == f"{_W}tab":
                pieces.append("\t")
        lines.extend("".join(pieces).split("\n"))
    return lines


def _decode(data):
    """The text of a transcript's bytes (WI26): the byte order mark says the
    encoding (UTF-8, UTF-16 in either order: what Notepad and Windows
    PowerShell write); with none, UTF-8, and if the bytes are not valid UTF-8,
    cp1252, the Windows code page of Spanish and English. Raises
    UnicodeDecodeError when none of them reads the bytes."""
    if data.startswith(codecs.BOM_UTF8):
        return data[len(codecs.BOM_UTF8):].decode("utf-8")
    if data.startswith((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)):
        return data.decode("utf-16")  # this codec reads the mark and drops it
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return data.decode("cp1252")


def _text_lines(path):
    try:
        # A second mark (a file saved with its mark twice) would stay before the first line and hide it
        # (WI26's review, P3-1).
        return _decode(Path(path).read_bytes()).lstrip("\ufeff").splitlines()
    except (OSError, UnicodeDecodeError) as error:
        raise TranscriptError("transcript.unreadable", path=str(path), detail=texts.External(str(error))) from error


def _read(path):
    """([(start seconds, speaker, text)] in time order, labelled): the one
    parser behind both readers of a transcript. A block starts at a Teams
    line with a speaker and a time, or at a "[HH:MM:SS]" line (a transcript
    with either is `labelled`); and (WI24), in a transcript with neither, at
    a line that is only a time (M:SS, MM:SS or H:MM:SS), which Teams writes
    when it names no one. The non-empty lines after it are its text; in a
    labelled transcript a line that is only a time is text, as it always
    was. A time inside a line of words starts nothing."""
    path = Path(path)
    if not path.is_file():
        raise TranscriptError("transcript.not_a_file", path=str(path))
    lines = [line.strip() for line in (_docx_lines(path) if path.suffix.lower() == ".docx" else _text_lines(path))]
    labelled = any(_SPEAKER_TIME.match(line) or _BRACKET_TIME.match(line) for line in lines)
    turns = []
    for line in lines:
        if not line:
            continue
        teams = _SPEAKER_TIME.match(line)
        bracket = _BRACKET_TIME.match(line)
        alone = _TIME_ALONE.match(line) and not labelled
        if teams:
            turns.append([_seconds(teams.group(2)), teams.group(1).strip(), []])
        elif bracket:
            hours, minutes, seconds, rest = bracket.groups()
            turns.append([int(hours) * 3600 + int(minutes) * 60 + int(seconds), "", [rest] if rest else []])
        elif alone:
            turns.append([_seconds(line), "", []])
        elif turns:
            turns[-1][2].append(line)
    if not turns:
        raise TranscriptError("transcript.no_timed_line", path=str(path))
    return sorted(((start, speaker, "\n".join(text)) for start, speaker, text in turns),
                  key=lambda turn: turn[0]), labelled


def names_no_one(path):
    """True if the transcript has no line that can name a speaker: no Teams
    "Speaker   M:SS" line and no "[HH:MM:SS]" line, only times alone on their
    lines. (A "[HH:MM:SS] Name: text" file is not: the register accepts it and
    checks no name, as it always did.)"""
    return not _read(path)[1]


def read_blocks(path):
    """[(start seconds, text)] in time order, from a Teams .docx or a text
    file with timed lines. Refuses a transcript with no timed line. The same
    blocks as read_turns, without the speaker: the boost only needs when."""
    return [(start, text) for start, _, text in _read(path)[0]]


def read_turns(path):
    """[(start seconds, speaker, text)] in time order: what read_blocks reads,
    with the speaker the Teams line names ("" for [HH:MM:SS] lines and for a
    time alone on its line). The summary needs who said what."""
    return _read(path)[0]


def read_text(path):
    """Every line of the transcript, the header before the first turn (a
    Teams title and date) included: what a written date is checked against."""
    path = Path(path)
    if not path.is_file():
        raise TranscriptError("transcript.not_a_file", path=str(path))
    return "\n".join(_docx_lines(path) if path.suffix.lower() == ".docx" else _text_lines(path))


def has_visual_reference(text):
    return _PHRASE.search(text) is not None


class VisualReferences:
    """The start times of the transcript blocks that point at the screen."""

    def __init__(self, blocks):
        self.times = sorted(start for start, text in blocks if has_visual_reference(text))

    @classmethod
    def from_file(cls, path):
        return cls(read_blocks(path))

    def near(self, timestamp, window=WINDOW):
        index = bisect.bisect_left(self.times, timestamp - window)
        return index < len(self.times) and self.times[index] <= timestamp + window

    def boost(self, score, timestamp):
        """The score, raised by BOOST (capped at 1) when a reference is near."""
        return min(score + BOOST, 1.0) if self.near(timestamp) else score
