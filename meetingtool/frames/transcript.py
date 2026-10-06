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
import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree

from meetingtool import texts

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
_SPEAKER_TIME = re.compile(r"^(.+?)\s{2,}(\d{1,2}:\d{2}(?::\d{2})?)\s*$")
# Teams without speaker names: the time alone on its line ("0:02", "1:02:03"), the words on the lines after.
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
        with zipfile.ZipFile(path) as archive:
            root = ElementTree.fromstring(archive.read("word/document.xml"))
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


def _text_lines(path):
    try:
        return Path(path).read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError) as error:
        raise TranscriptError("transcript.unreadable", path=str(path), detail=texts.External(str(error))) from error


def _turns(path):
    """[(start seconds, speaker, text)] in time order: the one parser behind
    both readers of a transcript. A block starts at a Teams line with a
    speaker and a time, at a "[HH:MM:SS]" line, or (WI24) at a line that is
    only a time (M:SS, MM:SS or H:MM:SS), which Teams writes when it names
    no one; the non-empty lines after it are its text. A time inside a line
    of words starts nothing."""
    path = Path(path)
    if not path.is_file():
        raise TranscriptError("transcript.not_a_file", path=str(path))
    lines = _docx_lines(path) if path.suffix.lower() == ".docx" else _text_lines(path)
    turns = []
    for raw in lines:
        line = raw.strip()
        if not line:
            continue
        teams = _SPEAKER_TIME.match(line)
        bracket = _BRACKET_TIME.match(line)
        alone = _TIME_ALONE.match(line)
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
    return sorted(((start, speaker, "\n".join(text)) for start, speaker, text in turns), key=lambda turn: turn[0])


def read_blocks(path):
    """[(start seconds, text)] in time order, from a Teams .docx or a text
    file with timed lines. Refuses a transcript with no timed line. The same
    blocks as read_turns, without the speaker: the boost only needs when."""
    return [(start, text) for start, _, text in _turns(path)]


def read_turns(path):
    """[(start seconds, speaker, text)] in time order: what read_blocks reads,
    with the speaker the Teams line names ("" for [HH:MM:SS] lines and for a
    time alone on its line). The summary needs who said what."""
    return _turns(path)


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
