"""Read the extracted frames with Gemini's paid tier (INGOL D-170, D-173).

Ported from the original MeetingTool (tools/gemini_client.py): the vision
instructions and up to 70 frames per request are kept. Three things are
fixed. The answer is checked: it must have finished normally and hold
exactly one [FRAME n] block per frame sent, or it is retried once and then
refused (the original capped output at 4096 tokens, below what 35 frames
already need, and passed a cut answer on). There is no fallback reading: a
busy or rate-limited service is retried twice and then the run fails (the
original fell back to local OCR). The key travels in a header, never in the
URL, so no error message can carry it.

Only the standard library is used. Nothing is written unless every request
succeeded, and the frames folder must be outside any git work tree: frames
and what they show are client data.
"""

import base64
import dataclasses
import json
import re
import time
import urllib.error
import urllib.request
from pathlib import Path

from meetingtool.frames.extract import enclosing_git_work_tree

ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models"
MODEL = "gemini-flash-latest"
CHUNK_SIZE = 70
MAX_OUTPUT_TOKENS = 65536
RETRY_DELAYS = (30.0, 60.0)
RETRYABLE_STATUS = frozenset({429, 500, 503})
TIMEOUT = 300
OUTPUT_NAME = "frames_read.md"

PROMPT = """You are analysing screenshots from a business meeting recording.
For each image, in order, extract all visible structured information.

Output one block per image, starting with its label exactly as given:

[FRAME n]
- Window/App: <active application or window title>
- Content Type: <slide | spreadsheet | ERP | email | dashboard | code | video-call | other>
- Key Data: <tables, numbers, KPIs, metrics; copy exact values, each with its row and column label>
- Text: <headings, bullet points, labels, code snippets, formulas>
- Notable: <anything highlighted, flagged, referenced or unusual>

Rules:
- Every image gets exactly one block, even if it is uninformative: then write
  "[FRAME n]" and "- Content: uninformative".
- Copy numbers and metrics exactly; never paraphrase them.
- If a value or text is partly visible or unclear, write [ILLEGIBLE] instead
  of guessing or leaving it out.
- Ignore empty participant video panels (plain black or grey rectangles).
- Capture visual signals: elements in red, green or orange (alert states),
  the most prominent element on screen, and any emphasis (bold, large font,
  highlighted cell).
- If an image looks like the previous one, say what changed.
- Plain text, no markdown headers.
"""

_BLOCK = re.compile(r"^\s*\[FRAME (\d+)\]", re.MULTILINE)


class ReadingError(Exception):
    """A reading that could not be completed; nothing was written."""


@dataclasses.dataclass
class ReadingResult:
    frames: int
    requests: int
    attempts: int
    seconds: float
    input_tokens: int
    output_tokens: int
    thinking_tokens: int
    output: Path


def frame_files(frames_dir):
    """The extractor's frames, in their order (frame_NNN_tHH-MM-SS.jpg)."""
    return sorted(Path(frames_dir).glob("frame_*.jpg"))


def _payload(frames, first):
    parts = [{"text": PROMPT}]
    for offset, path in enumerate(frames):
        parts.append({"text": f"[FRAME {first + offset}] {path.name}"})
        parts.append({"inline_data": {"mime_type": "image/jpeg",
                                      "data": base64.b64encode(path.read_bytes()).decode("ascii")}})
    return {"contents": [{"role": "user", "parts": parts}],
            "generationConfig": {"temperature": 0.1, "maxOutputTokens": MAX_OUTPUT_TOKENS}}


def check_answer(answer, first, count):
    """The answer's text if it is complete for frames first..first+count-1;
    otherwise ReadingError naming what is wrong."""
    try:
        candidate = answer["candidates"][0]
        text = "".join(part.get("text", "") for part in candidate["content"]["parts"])
        finish = candidate.get("finishReason")
    except (KeyError, IndexError, TypeError, AttributeError) as error:
        raise ReadingError(f"Gemini's answer has no text ({type(error).__name__})") from None
    if finish != "STOP":
        raise ReadingError(f"Gemini's answer did not finish normally (finishReason {finish})")
    numbers = [int(n) for n in _BLOCK.findall(text)]
    expected = list(range(first, first + count))
    if numbers != expected:
        missing = sorted(set(expected) - set(numbers))
        extra = sorted(set(numbers) - set(expected))
        repeated = sorted({n for n in numbers if numbers.count(n) > 1})
        raise ReadingError(f"Gemini's answer does not hold one block per frame {first}-{first + count - 1}: "
                           f"missing {missing}, repeated {repeated}, not sent {extra}")
    return text


def _post(url, key, payload):
    """One request: (status, parsed JSON or None, short reason)."""
    request = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), method="POST",
                                     headers={"Content-Type": "application/json", "x-goog-api-key": key})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            return response.status, json.loads(response.read().decode("utf-8")), ""
    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8", "replace")
        try:
            reason = json.loads(body)["error"]["message"]
        except (ValueError, KeyError, TypeError):
            reason = body
        return error.code, None, " ".join(reason.split())[:200]
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        return None, None, f"no answer ({type(error).__name__})"


def _read_chunk(url, key, frames, first, retry_delays, sleep, counters):
    """The checked text for one chunk, after the allowed retries."""
    payload = _payload(frames, first)
    incomplete_retried = False
    delays = list(retry_delays)
    while True:
        counters["attempts"] += 1
        status, answer, reason = _post(url, key, payload)
        if status == 200:
            usage = answer.get("usageMetadata", {}) if isinstance(answer, dict) else {}
            counters["input"] += usage.get("promptTokenCount", 0)
            counters["output"] += usage.get("candidatesTokenCount", 0)
            counters["thinking"] += usage.get("thoughtsTokenCount", 0)
            try:
                return check_answer(answer, first, len(frames))
            except ReadingError:
                if incomplete_retried:
                    raise
                incomplete_retried = True
                continue
        if status is not None and status not in RETRYABLE_STATUS:
            raise ReadingError(f"Gemini refused the request (HTTP {status}): {reason}")
        if not delays:
            what = f"HTTP {status}" if status is not None else reason
            raise ReadingError(f"Gemini did not answer frames {first}-{first + len(frames) - 1} after "
                               f"{len(retry_delays)} retries ({what}: {reason}); nothing was written")
        sleep(delays.pop(0))


def read_frames(frames_dir, key, endpoint=ENDPOINT, model=MODEL, chunk_size=CHUNK_SIZE,
                retry_delays=RETRY_DELAYS, sleep=time.sleep):
    """Read every frame of frames_dir with Gemini and write OUTPUT_NAME next to
    them, only once every request succeeded."""
    frames_dir = Path(frames_dir)
    work_tree = enclosing_git_work_tree(frames_dir)
    if work_tree is not None:
        raise ReadingError(f"frames folder {frames_dir.resolve()} is inside the git work tree {work_tree}; "
                           "frames and what they show must live outside any repository")
    frames = frame_files(frames_dir)
    if not frames:
        raise ReadingError(f"no frame_*.jpg in {frames_dir.resolve()}")
    if chunk_size < 1:
        raise ReadingError("the chunk size must be at least 1")
    url = f"{endpoint.rstrip('/')}/{model}:generateContent"
    counters = {"attempts": 0, "input": 0, "output": 0, "thinking": 0}
    started = time.monotonic()
    answers = []
    for start in range(0, len(frames), chunk_size):
        chunk = frames[start:start + chunk_size]
        answers.append(_read_chunk(url, key, chunk, start + 1, retry_delays, sleep, counters))
    header = ["# What each frame shows (read by Gemini)", "",
              f"{len(frames)} frames, {len(answers)} request(s), model {model}.", ""]
    header += [f"- FRAME {n}: {path.name}" for n, path in enumerate(frames, start=1)] + [""]
    output = frames_dir / OUTPUT_NAME
    partial = frames_dir / (OUTPUT_NAME + ".partial")
    partial.write_text("\n".join(header) + "\n" + "\n\n".join(a.strip() for a in answers) + "\n", encoding="utf-8")
    partial.replace(output)
    return ReadingResult(len(frames), len(answers), counters["attempts"], time.monotonic() - started,
                         counters["input"], counters["output"], counters["thinking"], output)
