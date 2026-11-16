"""The models that can write the summary, and how each provider is spoken to
(WI-2.0.0, amendment 1, approved by the owner on 2026-11-16).

Three rounds of the real presales meeting did not reach the nine points with
Gemini Flash, and a blind comparison judged by two models of different
companies put it last (docs/evidence/01M7B76KPE7XJMKQ2820C15Z9H/
model-comparison.md). The owner chose GPT-6.1 Sol, with the model left to
choose: "usemos sol pero podamos configurarlo para otro modelo".

The list is closed, so that the spending ceiling can reserve the worst case
of every attempt at that model's price (gemini.call_checked). Each price
carries the day it holds from, and a cost is counted at the price of the day
it is paid (Gemini Flash doubles on 2027-01-01). Prices are the providers'
own pages read on 2026-11-15 (OpenAI, Google) and Anthropic's price table of
2026-11-03.

Every provider is reached the way Gemini already was: plain HTTP with the
standard library, the key in a header and never in the URL. Each answer is
turned into the shape Gemini answers in (candidates, finishReason,
usageMetadata, modelVersion), so the spending meter, the retry, the paid
answers kept and the summary's checks are the same for every model. The
frames are still read by Gemini, and the question register is still written
by it.
"""

import dataclasses
import datetime

from meetingtool.reading import gemini

# The day from which a price holds, and the price in US$ per million tokens (input, output; reasoning is billed
# as output by every provider here).
ALWAYS = datetime.date(2000, 1, 1)


@dataclasses.dataclass(frozen=True)
class Provider:
    """How one provider is spoken to: where, with which header, what the
    request holds, and how its answer becomes Gemini's shape."""
    name: str
    label: str
    key_name: str
    endpoint: str

    def url(self, endpoint, model):
        if self.name == "gemini":
            return gemini.model_url(endpoint, model)
        return endpoint

    def headers(self, key):
        if self.name == "openai":
            return {"Content-Type": "application/json", "Authorization": f"Bearer {key}"}
        if self.name == "anthropic":
            return {"Content-Type": "application/json", "x-api-key": key, "anthropic-version": ANTHROPIC_VERSION}
        return {"Content-Type": "application/json", "x-goog-api-key": key}

    def payload(self, model, text, max_output_tokens):
        if self.name == "openai":
            # store false: the Responses API keeps a stored response for 30 days; abuse logs are kept anyway.
            return {"model": model, "input": text, "max_output_tokens": max_output_tokens,
                    "reasoning": {"effort": "medium"}, "store": False}
        if self.name == "anthropic":
            # No temperature: the current API version refuses sampling settings.
            return {"model": model, "max_tokens": max_output_tokens, "output_config": {"effort": "medium"},
                    "messages": [{"role": "user", "content": text}]}
        return {"contents": [{"role": "user", "parts": [{"text": text}]}],
                "generationConfig": {"temperature": 0.3, "maxOutputTokens": max_output_tokens}}

    def prompt_of(self, payload):
        if self.name == "openai":
            return payload["input"]
        if self.name == "anthropic":
            return payload["messages"][0]["content"]
        return payload["contents"][0]["parts"][0]["text"]

    def with_prompt(self, payload, text):
        """A copy of payload with its text replaced (the retry's note)."""
        if self.name == "openai":
            return {**payload, "input": text}
        if self.name == "anthropic":
            return {**payload, "messages": [{"role": "user", "content": text}]}
        contents = [{**payload["contents"][0], "parts": [{**payload["contents"][0]["parts"][0], "text": text}]}]
        return {**payload, "contents": contents}

    def normalize(self, answer):
        """The answer in Gemini's shape. Whatever does not have the
        expected form is passed on as it is, for the check to refuse."""
        if self.name == "gemini" or not isinstance(answer, dict):
            return answer
        if self.name == "openai":
            return _from_openai(answer)
        return _from_anthropic(answer)


ANTHROPIC_VERSION = "2026-10-21"

OPENAI = Provider("openai", "OpenAI", "VisualMeetingTool/openai", "https://api.openai.com/v1/responses")
ANTHROPIC = Provider("anthropic", "Anthropic", "VisualMeetingTool/anthropic", "https://api.anthropic.com/v1/messages")
GEMINI = Provider("gemini", "Google", "VisualMeetingTool/gemini", gemini.ENDPOINT)
PROVIDERS = {provider.name: provider for provider in (OPENAI, ANTHROPIC, GEMINI)}


@dataclasses.dataclass(frozen=True)
class Model:
    id: str
    label: str
    provider: Provider
    prices: tuple
    # Run through the application (its API, its checks and its retry) on the real meeting: only those.
    tested: bool


MODELS = {model.id: model for model in (
    Model("gpt-6.1-sol", "GPT-6.1 Sol", OPENAI, ((ALWAYS, 2.00, 10.00),), True),
    Model("claude-opus-5-5", "Claude Opus 5.5", ANTHROPIC, ((ALWAYS, 4.00, 20.00),), False),
    Model("claude-sonnet-5-5", "Claude Sonnet 5.5", ANTHROPIC, ((ALWAYS, 2.00, 10.00),), False),
    Model(gemini.MODEL, "Gemini Flash", GEMINI, gemini.PRICES, True),
)}
DEFAULT_MODEL = "gpt-6.1-sol"

# What a summary request of a meeting like the test one weighs, to show its cost in Settings: 47,000 tokens in
# and 15,000 out (the 2026-11-15 rounds). The ceiling's minimum reserves more: two attempts at the whole output
# cap of a request of REFERENCE_INPUT_TOKENS, plus reading 70 frames.
SHOWN_INPUT_TOKENS = 47000
SHOWN_OUTPUT_TOKENS = 15000
REFERENCE_INPUT_TOKENS = 60000
REFERENCE_FRAMES = 70
CEILING_FLOOR = 1.00
CEILING_TOP = 5.00


def model(model_id):
    """The model of the list with that id; ReadingError for any other, before
    anything is sent."""
    try:
        return MODELS[model_id]
    except (KeyError, TypeError):
        raise gemini.ReadingError("summary.unknown_model", model=str(model_id)[:80],
                                  options=", ".join(MODELS)) from None


def shown_cost(model_id, day=None):
    """The estimated cost of one summary of a meeting like the test one, in
    one attempt, at today's price (or `day`'s)."""
    return gemini.token_cost(SHOWN_INPUT_TOKENS, SHOWN_OUTPUT_TOKENS, model(model_id).prices, day)


def needed_ceiling(model_id, max_output_tokens, with_frames=True, day=None):
    """The least a run's ceiling may be with this model: two summary attempts
    at the worst case of a request of REFERENCE_INPUT_TOKENS, plus reading
    REFERENCE_FRAMES frames, rounded up to ten cents. A ceiling set under it
    is refused before anything is spent."""
    worst = gemini.token_cost(REFERENCE_INPUT_TOKENS, max_output_tokens, model(model_id).prices, day)
    total = 2 * worst + (gemini.worst_attempt_cost(REFERENCE_FRAMES, day=day) if with_frames else 0.0)
    return _tenths_up(total)


def minimum_ceiling(model_id, max_output_tokens, with_frames=True, day=None):
    """A run's ceiling by default: needed_ceiling, never under CEILING_FLOOR
    (the US$1.00 a run always had)."""
    return max(CEILING_FLOOR, needed_ceiling(model_id, max_output_tokens, with_frames, day))


def _tenths_up(amount):
    """amount rounded up to the next ten cents (in whole cents first, so 1.0 stays 1.0)."""
    return -(-round(amount * 100) // 10) / 10


def summary_ceiling(model_id, max_output_tokens, day=None, floor=0.50):
    """The summary's own ceiling by default (the command line, and a summary
    written alone): two attempts at the worst case of a request of
    REFERENCE_INPUT_TOKENS, rounded up to ten cents, never under `floor` (the
    US$0.50 it always was)."""
    worst = gemini.token_cost(REFERENCE_INPUT_TOKENS, max_output_tokens, model(model_id).prices, day)
    return max(floor, _tenths_up(2 * worst))


def _from_openai(answer):
    """A Responses API answer in Gemini's shape. Text is in the output items of
    type "message", in their content of type "output_text"; a refusal is its
    own content type. status "completed" is a finished answer; "incomplete"
    (cut at max_output_tokens, for one) is not. Reasoning tokens are part of
    output_tokens and are reported apart."""
    parts, refused = [], False
    for item in answer.get("output") or []:
        if not isinstance(item, dict) or item.get("type") != "message":
            continue
        for content in item.get("content") or []:
            if isinstance(content, dict) and content.get("type") == "output_text":
                parts.append({"text": str(content.get("text", ""))})
            elif isinstance(content, dict) and content.get("type") == "refusal":
                refused = True
    status = answer.get("status")
    if refused:
        finish = "REFUSAL"
    elif status == "completed":
        finish = "STOP"
    else:
        details = answer.get("incomplete_details")
        reason = details.get("reason") if isinstance(details, dict) else None
        finish = f"{status}: {reason}" if reason else str(status)
    shaped = {"candidates": [{"content": {"parts": parts}, "finishReason": finish}]}
    usage = answer.get("usage")
    if isinstance(usage, dict) and "input_tokens" in usage:
        details = usage.get("output_tokens_details")
        reasoning = details.get("reasoning_tokens", 0) if isinstance(details, dict) else 0
        output = usage.get("output_tokens", 0)
        shaped["usageMetadata"] = {"promptTokenCount": usage.get("input_tokens", 0),
                                   "candidatesTokenCount": max(0, output - reasoning),
                                   "thoughtsTokenCount": reasoning}
    if answer.get("model"):
        shaped["modelVersion"] = answer["model"]
    return shaped


def _from_anthropic(answer):
    """A Messages API answer in Gemini's shape. Text is in the content blocks
    of type "text" (thinking blocks are left out); stop_reason "end_turn" or
    "stop_sequence" is a finished answer. output_tokens counts the thinking
    too, which this API does not report apart."""
    parts = [{"text": str(block.get("text", ""))} for block in answer.get("content") or []
             if isinstance(block, dict) and block.get("type") == "text"]
    stop = answer.get("stop_reason")
    finish = "STOP" if stop in ("end_turn", "stop_sequence") else str(stop).upper()
    shaped = {"candidates": [{"content": {"parts": parts}, "finishReason": finish}]}
    usage = answer.get("usage")
    if isinstance(usage, dict) and "input_tokens" in usage:
        shaped["usageMetadata"] = {"promptTokenCount": usage.get("input_tokens", 0),
                                   "candidatesTokenCount": usage.get("output_tokens", 0), "thoughtsTokenCount": 0}
    if answer.get("model"):
        shaped["modelVersion"] = answer["model"]
    return shaped
