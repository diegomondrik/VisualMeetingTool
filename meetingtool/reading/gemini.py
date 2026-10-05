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

Every run has a spend budget (INGOL D-173 set US$0.50 for the real run):
before each attempt, the most that attempt could cost, its estimated input
plus the whole output cap at output prices, is added to what was already
spent, and the attempt is not sent if that could go over the budget. An
attempt that got no answer is counted at its maximum, since it may have
been billed. Prices are the list prices read for D-169; the model that
answered is recorded, so the estimate can be checked against its price.

Only the standard library is used. The reading is written only once every
request succeeded, but each accepted answer is kept as it arrives, in
KEPT_DIR of the frames folder, so that reading again after a failure pays
only what is missing (WI20). The frames folder must be outside any git work
tree: frames and what they show are client data.
"""

import base64
import dataclasses
import hashlib
import http.client
import json
import re
import time
import urllib.error
import urllib.request
from pathlib import Path

from meetingtool import disk, texts
from meetingtool.frames.extract import enclosing_git_work_tree

ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models"
MODEL = "gemini-flash-latest"
CHUNK_SIZE = 70
# 35 frames took 9328 output and 9881 thinking tokens (D-169), so 70 need
# about 38,500: the cap leaves room and bounds the cost of one answer.
MAX_OUTPUT_TOKENS = 49152
# Spend budget. Prices in US$ per million tokens, the list prices used for
# D-169 (thinking is billed as output); input estimated per frame from the
# 39510 tokens 35 frames took (1129 each), rounded up.
MAX_COST_USD = 0.50
PRICE_INPUT_PER_MILLION = 0.75
PRICE_OUTPUT_PER_MILLION = 3.75
INPUT_TOKENS_PER_FRAME = 1500
PROMPT_TOKENS = 1000
RETRY_DELAYS = (30.0, 60.0)
RETRYABLE_STATUS = frozenset({429, 500, 503})
TIMEOUT = 300
OUTPUT_NAME = "frames_read.md"
# Where the accepted answers of paid requests are kept, by fingerprint (see call_checked).
KEPT_DIR = "paid-answers"

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

# A label at the start of a line, even if the model wraps it in bold, a list mark or a quote.
_BLOCK = re.compile(r"^[\s*_#>-]*\[FRAME (\d+)\]", re.MULTILINE | re.IGNORECASE)


class ReadingError(texts.Failure):
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
    estimated_cost_usd: float = 0.0
    model_versions: tuple = ()


def frame_files(frames_dir):
    """The extractor's frames, in their order (frame_NNN_tHH-MM-SS.jpg)."""
    return sorted(Path(frames_dir).glob("frame_*.jpg"))


def token_cost(input_tokens, output_tokens):
    return (input_tokens * PRICE_INPUT_PER_MILLION + output_tokens * PRICE_OUTPUT_PER_MILLION) / 1e6


def listed_output_tokens(frame_count):
    """The output cap for reading frame_count frames chosen one by one: 35
    frames took about 550 output and thinking tokens each (D-169), so 1000
    each leaves room, and a few frames do not reserve the cap of 70
    (WI14's review: the register's run must fit its budget)."""
    return min(MAX_OUTPUT_TOKENS, 2000 + 1000 * frame_count)


def worst_attempt_cost(frame_count, max_output_tokens=MAX_OUTPUT_TOKENS):
    """The most one attempt for frame_count frames can cost."""
    return token_cost(PROMPT_TOKENS + frame_count * INPUT_TOKENS_PER_FRAME, max_output_tokens)


def _payload(frames, first, max_output_tokens=MAX_OUTPUT_TOKENS):
    parts = [{"text": PROMPT}]
    for offset, path in enumerate(frames):
        parts.append({"text": f"[FRAME {first + offset}] {path.name}"})
        parts.append({"inline_data": {"mime_type": "image/jpeg",
                                      "data": base64.b64encode(path.read_bytes()).decode("ascii")}})
    return {"contents": [{"role": "user", "parts": parts}],
            "generationConfig": {"temperature": 0.1, "maxOutputTokens": max_output_tokens}}


def check_answer(answer, first, count):
    """The answer's text if it is complete for frames first..first+count-1;
    otherwise ReadingError naming what is wrong."""
    try:
        candidate = answer["candidates"][0]
        text = "".join(part.get("text", "") for part in candidate["content"]["parts"])
        finish = candidate.get("finishReason")
    except (KeyError, IndexError, TypeError, AttributeError) as error:
        raise ReadingError("gemini.no_text", kind=type(error).__name__) from None
    if finish != "STOP":
        raise ReadingError("gemini.unfinished", finish=finish)
    numbers = [int(n) for n in _BLOCK.findall(text)]
    expected = list(range(first, first + count))
    if numbers != expected:
        missing = sorted(set(expected) - set(numbers))
        extra = sorted(set(numbers) - set(expected))
        repeated = sorted({n for n in numbers if numbers.count(n) > 1})
        raise ReadingError("gemini.blocks", first=first, last=first + count - 1, missing=missing,
                           repeated=repeated, extra=extra)
    return text


def post_generate(url, key, payload):
    """One request: (status, parsed JSON or None, short reason). The reason
    is a message of the program, or Google's own words (External)."""
    request = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), method="POST",
                                     headers={"Content-Type": "application/json", "x-goog-api-key": key})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            raw = response.read()
            status = response.status
        try:
            return status, json.loads(raw.decode("utf-8")), ""
        except ValueError:
            return status, None, texts.Message("gemini.reason.not_json")
    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8", "replace")
        try:
            reason = json.loads(body)["error"]["message"]
        except (ValueError, KeyError, TypeError):
            reason = body
        return error.code, None, texts.External(" ".join(reason.split())[:200])
    except (urllib.error.URLError, TimeoutError, OSError, http.client.HTTPException) as error:
        return None, None, texts.Message("gemini.reason.no_answer", kind=type(error).__name__)


def new_counters():
    return {"attempts": 0, "input": 0, "output": 0, "thinking": 0, "spent": 0.0, "models": set()}


def fingerprint(url, payload):
    """What identifies a request: the model it goes to and everything it
    sends (text, images, settings); not the key, nor the service's address."""
    model = url.rstrip("/").rsplit("/", 1)[-1]
    sent = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(f"{model}\n{sent}".encode("utf-8")).hexdigest()


def _kept_answer(path, check):
    """check() of the answer kept at path, or None if there is none or it no
    longer passes the check."""
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
        answer = {"candidates": [{"content": {"parts": [{"text": record["answer"]}]}, "finishReason": "STOP"}]}
        return check(answer)
    except (OSError, ValueError, KeyError, TypeError, AttributeError, texts.Failure):
        return None


def call_checked(url, key, payload, check, worst, what, retry_delays, sleep, counters, max_cost_usd, revise=None,
                 keep=None):
    """Send one request and return check(answer), within the budget and after
    the allowed retries: an answer check refuses is retried once; a busy,
    rate-limited or unanswered request twice, after the given pauses; any
    other error ends at once. `worst` is the most one attempt can cost.
    With `revise`, the retry of a refused answer sends revise(payload, error)
    instead, so the request can say what was refused; `worst` must cover it.

    With `keep`, a folder, an accepted answer is kept there under the
    request's fingerprint, and the same request made again (the same model,
    exactly the same content) takes it from there, checked again, without
    paying (WI20: what was paid is never thrown away). Any other request,
    even one differing in a single character, pays."""
    kept = Path(keep) / f"{fingerprint(url, payload)}.json" if keep is not None else None
    if kept is not None:
        found = _kept_answer(kept, check)
        if found is not None:
            return found
    incomplete_retried = False
    refused = ""  # why the answer before was refused, so a stop by the budget says it (INGOL D-181's run)
    what = what if isinstance(what, texts.Message) else texts.External(what)
    delays = list(retry_delays)
    while True:
        if counters["spent"] + worst > max_cost_usd:
            raise ReadingError("gemini.over_budget", what=what, worst=float(worst), spent=float(counters["spent"]),
                               budget=float(max_cost_usd), refused=refused)
        counters["attempts"] += 1
        status, answer, reason = post_generate(url, key, payload)
        if status is None:
            counters["spent"] += worst  # no answer: it may have been billed in full
            refused = texts.Message("gemini.before.no_answer", reason=reason)
        if status == 200:
            usage = answer.get("usageMetadata") if isinstance(answer, dict) else None
            if isinstance(usage, dict) and "promptTokenCount" in usage:
                counters["input"] += usage.get("promptTokenCount", 0)
                counters["output"] += usage.get("candidatesTokenCount", 0)
                counters["thinking"] += usage.get("thoughtsTokenCount", 0)
                counters["spent"] += token_cost(usage.get("promptTokenCount", 0),
                                                usage.get("candidatesTokenCount", 0) + usage.get("thoughtsTokenCount", 0))
            else:
                counters["spent"] += worst  # an answer with no usage is counted at its maximum
            if isinstance(answer, dict) and answer.get("modelVersion"):
                counters["models"].add(str(answer["modelVersion"]))
            try:
                value = check(answer)
            except ReadingError as error:
                if incomplete_retried:
                    raise
                incomplete_retried = True
                refused = texts.Message("gemini.before.refused", error=error.message)
                if revise is not None:
                    payload = revise(payload, error)
                continue
            if kept is not None:
                text = "".join(part.get("text", "") for part in answer["candidates"][0]["content"]["parts"])
                disk.write_text(kept, json.dumps({"answer": text, "model": answer.get("modelVersion", "")},
                                                 ensure_ascii=False) + "\n")
            return value
        if status is not None and status not in RETRYABLE_STATUS:
            raise ReadingError("gemini.refused", status=status, reason=reason)
        if not delays:
            label = f"HTTP {status}" if status is not None else reason
            raise ReadingError("gemini.no_answer", what=what, retries=len(retry_delays), label=label, reason=reason)
        sleep(delays.pop(0))


def check_key(key):
    if not key.isascii() or not key.isprintable():
        raise ReadingError("gemini.bad_key")


def check_outside_repository(folder):
    work_tree = enclosing_git_work_tree(folder)
    if work_tree is not None:
        raise ReadingError("gemini.inside_repository", folder=str(Path(folder).resolve()), work_tree=str(work_tree))


def model_url(endpoint, model):
    return f"{endpoint.rstrip('/')}/{model}:generateContent"


def _read_chunk(url, key, frames, first, retry_delays, sleep, counters, max_cost_usd,
                max_output_tokens=MAX_OUTPUT_TOKENS, keep=None):
    """The checked text for one chunk, after the allowed retries and within the budget."""
    return call_checked(url, key, _payload(frames, first, max_output_tokens),
                        lambda answer: check_answer(answer, first, len(frames)),
                        worst_attempt_cost(len(frames), max_output_tokens),
                        texts.Message("gemini.what.frames", first=first, last=first + len(frames) - 1),
                        retry_delays, sleep, counters, max_cost_usd, keep=keep)


def read_listed(url, key, frames, retry_delays, sleep, counters, max_cost_usd, chunk_size=CHUNK_SIZE, keep=None):
    """What each of `frames` shows, as {name: its [FRAME n] block}, reading
    only those frames, each chunk checked and within the budget as
    read_frames does (the question-and-answer register reads only the frames
    of the answers that relied on the screen)."""
    readings = {}
    for start in range(0, len(frames), chunk_size):
        chunk = frames[start:start + chunk_size]
        text = _read_chunk(url, key, chunk, start + 1, retry_delays, sleep, counters, max_cost_usd,
                           listed_output_tokens(len(chunk)), keep=keep)
        found = list(_BLOCK.finditer(text))
        ends = [match.start() for match in found[1:]] + [len(text)]
        blocks = {int(match.group(1)): text[match.start():end].strip() for match, end in zip(found, ends)}
        for offset, path in enumerate(chunk):
            readings[path.name] = blocks[start + 1 + offset]
    return readings


def read_frames(frames_dir, key, endpoint=ENDPOINT, model=MODEL, chunk_size=CHUNK_SIZE,
                retry_delays=RETRY_DELAYS, sleep=time.sleep, max_cost_usd=MAX_COST_USD, counters=None):
    """Read every frame of frames_dir with Gemini and write OUTPUT_NAME next to
    them, only once every request succeeded and without going over the budget.
    `counters` (from new_counters) is shared with the stages of the same run,
    so the budget covers them together; by default the reading has its own."""
    check_key(key)
    frames_dir = Path(frames_dir)
    check_outside_repository(frames_dir)
    frames = frame_files(frames_dir)
    if not frames:
        raise ReadingError("gemini.no_frames", folder=str(frames_dir.resolve()))
    if chunk_size < 1:
        raise ReadingError("gemini.chunk_too_small")
    url = model_url(endpoint, model)
    counters = new_counters() if counters is None else counters
    started = time.monotonic()
    answers = []
    for start in range(0, len(frames), chunk_size):
        chunk = frames[start:start + chunk_size]
        answers.append(_read_chunk(url, key, chunk, start + 1, retry_delays, sleep, counters, max_cost_usd,
                                   keep=frames_dir / KEPT_DIR))
    header = ["# What each frame shows (read by Gemini)", "",
              f"{len(frames)} frames, {len(answers)} request(s), model {model}.", ""]
    header += [f"- FRAME {n}: {path.name}" for n, path in enumerate(frames, start=1)] + [""]
    output = frames_dir / OUTPUT_NAME
    disk.write_text(output, "\n".join(header) + "\n" + "\n\n".join(a.strip() for a in answers) + "\n")
    return ReadingResult(len(frames), len(answers), counters["attempts"], time.monotonic() - started,
                         counters["input"], counters["output"], counters["thinking"], output,
                         counters["spent"], tuple(sorted(counters["models"])))
