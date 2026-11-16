"""WI-2.0.0, amendment 1 (WI200-AC14): every model of the list against a
fake server of its provider. The request each one sends, how its answer is
read, what it costs (reasoning included), the ceiling, the retry, the paid
answer kept, and prices that change on a given day. No key and no network."""

import datetime
import http.server
import json
import shutil
import threading
import unittest
from unittest import mock

from meetingtool.reading import gemini
from meetingtool.summary import providers, writer
from tests.test_reading import KEY
from tests.test_summary import Workspace, saved, summary_text


class FakeProvider:
    """A local stand-in for one provider's API. `script` is a list of
    responses: an int status (an error with a JSON message) or a callable
    taking the request's body and returning the answer. When it runs out,
    every request gets `default`."""

    def __init__(self, path, default, script=()):
        self.script, self.default, self.requests = list(script), default, []
        fake = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                fake.requests.append({"path": self.path, "headers": {k.lower(): v for k, v in self.headers.items()},
                                      "body": body})
                step = fake.script.pop(0) if fake.script else fake.default
                if isinstance(step, int):
                    status, data = step, {"error": {"type": "error", "message": f"fake error {step}"}}
                else:
                    status, data = 200, step(body)
                raw = json.dumps(data).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.endpoint = f"http://127.0.0.1:{self.server.server_address[1]}{path}"
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *exc):
        self.server.shutdown()
        self.server.server_close()


def openai_answer(text, status="completed", reason=None, refusal=False, usage=(30000, 9000, 4000)):
    """A Responses API answer: a reasoning item, then the message; usage is
    (input, output with reasoning, of which reasoning)."""
    content = [{"type": "refusal", "refusal": "I can't help with that."}] if refusal else \
        [{"type": "output_text", "text": text, "annotations": []}]
    answer = {"id": "resp_1", "object": "response", "status": status, "model": "gpt-6.1-sol-2026-10-01",
              "output": [{"type": "reasoning", "id": "rs_1", "summary": []},
                         {"type": "message", "id": "msg_1", "role": "assistant", "content": content}],
              "usage": {"input_tokens": usage[0], "output_tokens": usage[1],
                        "output_tokens_details": {"reasoning_tokens": usage[2]}, "total_tokens": usage[0] + usage[1]}}
    if reason:
        answer["incomplete_details"] = {"reason": reason}
    return answer


def anthropic_answer(text, stop="end_turn", usage=(30000, 9000)):
    return {"id": "msg_1", "type": "message", "role": "assistant", "model": "claude-opus-5-5",
            "content": [{"type": "thinking", "thinking": "", "signature": "x"}, {"type": "text", "text": text}],
            "stop_reason": stop, "usage": {"input_tokens": usage[0], "output_tokens": usage[1]}}


class ProviderRun(Workspace):
    MODEL = "gpt-6.1-sol"
    PATH = "/v1/responses"

    def answer(self, text, **kwargs):
        return lambda body: openai_answer(text, **kwargs)

    def write(self, fake, **kwargs):
        options = dict(model=self.MODEL, endpoint=fake.endpoint, sleep=self.sleeps.append, data_dir=self.data,
                       retry_delays=(0, 0), language="en")
        options.update(kwargs)
        return writer.write_summary(self.frames, self.transcript, KEY, **options)


class OpenAITest(ProviderRun):
    def test_the_request_goes_to_the_responses_api_with_its_key_and_nothing_stored(self):
        with FakeProvider(self.PATH, self.answer(summary_text("en"))) as fake:
            result = self.write(fake)
        sent = fake.requests[0]
        self.assertEqual(sent["path"], "/v1/responses")
        self.assertEqual(sent["headers"]["authorization"], f"Bearer {KEY}")
        self.assertNotIn("x-goog-api-key", sent["headers"])
        body = sent["body"]
        self.assertEqual((body["model"], body["store"], body["reasoning"], body["max_output_tokens"]),
                         ("gpt-6.1-sol", False, {"effort": "medium"}, writer.MAX_OUTPUT_TOKENS))
        self.assertNotIn("temperature", body)
        self.assertIn(writer.MATERIAL, body["input"])
        self.assertNotIn(KEY, json.dumps(body))
        self.assertEqual(self.output().read_text(encoding="utf-8").strip(), saved(summary_text("en")))
        self.assertEqual(result.model_versions, ("gpt-6.1-sol-2026-10-01",))

    def test_the_cost_counts_the_reasoning_as_output_at_sols_price(self):
        with FakeProvider(self.PATH, self.answer(summary_text("en"), usage=(30000, 9000, 4000))) as fake:
            result = self.write(fake)
        self.assertAlmostEqual(result.estimated_cost_usd, (30000 * 2.00 + 9000 * 10.00) / 1e6)
        self.assertEqual((result.input_tokens, result.output_tokens, result.thinking_tokens), (30000, 5000, 4000))

    def test_an_answer_cut_at_its_output_limit_is_refused_and_retried(self):
        cut = self.answer("## Executive summary\nHalf", status="incomplete", reason="max_output_tokens")
        with FakeProvider(self.PATH, self.answer(summary_text("en")), [cut]) as fake:
            result = self.write(fake)
        self.assertEqual((result.attempts, len(fake.requests)), (2, 2))

    def test_two_cut_answers_are_refused_and_nothing_is_written(self):
        cut = self.answer("## Executive summary\nHalf", status="incomplete", reason="max_output_tokens")
        with FakeProvider(self.PATH, cut) as fake:
            with self.assertRaises(writer.SummaryError) as caught:
                self.write(fake)
        self.assertEqual(caught.exception.message.key, "summary.unfinished")
        self.assertIn("max_output_tokens", str(caught.exception))
        self.assertFalse(self.output().exists())

    def test_a_refusal_is_not_a_summary(self):
        with FakeProvider(self.PATH, self.answer("", refusal=True)) as fake:
            with self.assertRaises(writer.SummaryError) as caught:
                self.write(fake)
        self.assertIn("REFUSAL", str(caught.exception))

    def test_the_retry_says_why_in_the_input(self):
        with FakeProvider(self.PATH, self.answer(summary_text("en")),
                          [self.answer(summary_text("en", recording=None))]) as fake:
            self.write(fake)
        self.assertIn("YOUR PREVIOUS ANSWER WAS REFUSED: it did not start with one RECORDING line",
                      fake.requests[1]["body"]["input"])
        self.assertNotIn("YOUR PREVIOUS ANSWER", fake.requests[0]["body"]["input"])

    def test_a_busy_service_is_retried_and_a_refused_request_is_not(self):
        with FakeProvider(self.PATH, self.answer(summary_text("en")), [503, 429]) as fake:
            self.write(fake)
        self.assertEqual(len(fake.requests), 3)
        shutil.rmtree(self.frames / gemini.KEPT_DIR)  # or the answer just paid would be taken from there
        with FakeProvider(self.PATH, self.answer(summary_text("en")), [401]) as fake:
            with self.assertRaises(gemini.ReadingError) as caught:
                self.write(fake)
        self.assertEqual((caught.exception.message.key, len(fake.requests)), ("gemini.refused", 1))
        self.assertIn("fake error 401", str(caught.exception))

    def test_the_paid_answer_is_kept_and_the_same_request_pays_nothing_again(self):
        with FakeProvider(self.PATH, self.answer(summary_text("en"))) as fake:
            self.write(fake)
            self.output().unlink()
            again = self.write(fake)
        self.assertEqual(len(fake.requests), 1)
        self.assertEqual(again.estimated_cost_usd, 0)
        self.assertTrue(self.output().exists())

    def test_a_ceiling_below_the_worst_attempt_sends_nothing(self):
        with FakeProvider(self.PATH, self.answer(summary_text("en"))) as fake:
            with self.assertRaises(gemini.ReadingError) as caught:
                self.write(fake, max_cost_usd=0.10)
        self.assertEqual((caught.exception.message.key, fake.requests), ("gemini.over_budget", []))

    def test_the_request_asks_for_the_clients_praise_quoted(self):
        with FakeProvider(self.PATH, self.answer(summary_text("en", "presale"))) as fake:
            self.write(fake, meeting_type="presale")
        self.assertIn("The client's praise is quoted, in the client's words with the minute, wherever it is told, the "
                      "executive summary and the key points too; never paraphrased.", fake.requests[0]["body"]["input"])


class AnthropicTest(ProviderRun):
    MODEL = "claude-opus-5-5"
    PATH = "/v1/messages"

    def answer(self, text, **kwargs):
        return lambda body: anthropic_answer(text, **kwargs)

    def test_the_request_goes_to_the_messages_api_with_its_key_and_version(self):
        with FakeProvider(self.PATH, self.answer(summary_text("en"))) as fake:
            result = self.write(fake)
        sent = fake.requests[0]
        self.assertEqual(sent["path"], "/v1/messages")
        self.assertEqual((sent["headers"]["x-api-key"], sent["headers"]["anthropic-version"]),
                         (KEY, providers.ANTHROPIC_VERSION))
        self.assertNotIn("authorization", sent["headers"])
        body = sent["body"]
        self.assertEqual((body["model"], body["max_tokens"], body["output_config"]),
                         ("claude-opus-5-5", writer.MAX_OUTPUT_TOKENS, {"effort": "medium"}))
        self.assertNotIn("temperature", body)
        self.assertEqual(body["messages"][0]["role"], "user")
        self.assertIn(writer.MATERIAL, body["messages"][0]["content"])
        self.assertEqual(self.output().read_text(encoding="utf-8").strip(), saved(summary_text("en")))
        self.assertEqual(result.model_versions, ("claude-opus-5-5",))

    def test_only_the_text_is_read_and_the_cost_is_at_opuss_price(self):
        with FakeProvider(self.PATH, self.answer(summary_text("en"), usage=(30000, 9000))) as fake:
            result = self.write(fake)
        self.assertAlmostEqual(result.estimated_cost_usd, (30000 * 4.00 + 9000 * 20.00) / 1e6)

    def test_an_answer_cut_at_max_tokens_is_refused_and_retried_with_a_note(self):
        cut = self.answer("## Executive summary\nHalf", stop="max_tokens")
        with FakeProvider(self.PATH, self.answer(summary_text("en")), [cut]) as fake:
            result = self.write(fake)
        self.assertEqual(result.attempts, 2)

    def test_overloaded_and_a_gateway_error_are_retried(self):
        # The independent review of WI-2.0.0: Anthropic's "overloaded" is 529; 502 and 504 come from a gateway.
        for status in (529, 502, 504):
            with self.subTest(status=status):
                shutil.rmtree(self.frames / gemini.KEPT_DIR, ignore_errors=True)
                with FakeProvider(self.PATH, self.answer(summary_text("en")), [status]) as fake:
                    result = self.write(fake)
                self.assertEqual((len(fake.requests), result.attempts), (2, 2))
                self.assertEqual(self.output().read_text(encoding="utf-8").strip(), saved(summary_text("en")))

    def test_sonnet_goes_to_the_same_api_at_its_own_price(self):
        with FakeProvider(self.PATH, self.answer(summary_text("en"), usage=(30000, 9000))) as fake:
            result = self.write(fake, model="claude-sonnet-5-5")
        self.assertEqual(fake.requests[0]["body"]["model"], "claude-sonnet-5-5")
        self.assertAlmostEqual(result.estimated_cost_usd, (30000 * 2.00 + 9000 * 10.00) / 1e6)


class ModelListTest(Workspace):
    def test_a_model_outside_the_list_is_refused_before_anything_is_sent(self):
        with FakeProvider("/v1/responses", lambda body: openai_answer(summary_text("en"))) as fake:
            with self.assertRaises(writer.SummaryError) as caught:
                writer.write_summary(self.frames, self.transcript, KEY, model="gpt-6.1-terra", endpoint=fake.endpoint)
        self.assertEqual(caught.exception.message.key, "summary.unknown_model")
        self.assertIn("gpt-6.1-sol", str(caught.exception))
        self.assertEqual(fake.requests, [])

    def test_the_list_its_default_and_what_was_tested(self):
        self.assertEqual(list(providers.MODELS), ["gpt-6.1-sol", "claude-opus-5-5", "claude-sonnet-5-5",
                                                  "gemini-flash-latest"])
        self.assertEqual(providers.DEFAULT_MODEL, "gpt-6.1-sol")
        self.assertEqual([m.id for m in providers.MODELS.values() if not m.tested],
                         ["claude-opus-5-5", "claude-sonnet-5-5"])
        self.assertEqual({m.provider.key_name for m in providers.MODELS.values()},
                         {"VisualMeetingTool/openai", "VisualMeetingTool/anthropic", "VisualMeetingTool/gemini"})


class DatedPricesTest(unittest.TestCase):
    BEFORE, AFTER = datetime.date(2026, 12, 31), datetime.date(2027, 1, 1)

    def test_gemini_doubles_on_the_first_of_january_for_the_summary_and_the_frames(self):
        self.assertAlmostEqual(gemini.token_cost(1_000_000, 0, day=self.BEFORE), 0.75)
        self.assertAlmostEqual(gemini.token_cost(1_000_000, 0, day=self.AFTER), 1.50)
        self.assertAlmostEqual(gemini.token_cost(0, 1_000_000, day=self.AFTER), 7.50)
        self.assertAlmostEqual(gemini.worst_attempt_cost(10, day=self.AFTER),
                               2 * gemini.worst_attempt_cost(10, day=self.BEFORE))
        self.assertEqual(providers.MODELS["gemini-flash-latest"].prices, gemini.PRICES)

    def test_a_run_on_the_new_price_day_is_counted_at_the_new_price(self):
        answer = {"candidates": [{"content": {"parts": [{"text": "x"}]}, "finishReason": "STOP"}],
                  "usageMetadata": {"promptTokenCount": 100000, "candidatesTokenCount": 1000, "thoughtsTokenCount": 0}}
        from tests.test_reading import FakeGemini
        for day, price in ((self.BEFORE, 0.75), (self.AFTER, 1.50)):
            with self.subTest(day=day), mock.patch.object(gemini, "today", lambda day=day: day):
                with FakeGemini([lambda first, count: answer]) as fake:
                    counters = gemini.new_counters()
                    gemini.call_checked(gemini.model_url(fake.endpoint, gemini.MODEL), KEY,
                                        {"contents": [{"role": "user", "parts": [{"text": "y"}]}]},
                                        lambda reply: "ok", 1.0, "x", (), lambda s: None, counters, 5.0)
                self.assertAlmostEqual(counters["spent"], (100000 * price + 1000 * 2 * price / 0.4) / 1e6)

    def test_a_runs_ceiling_counts_the_frames_at_the_price_of_the_day(self):
        frames_then = gemini.worst_attempt_cost(providers.REFERENCE_FRAMES, day=self.AFTER)
        self.assertAlmostEqual(frames_then, 2 * gemini.worst_attempt_cost(providers.REFERENCE_FRAMES, day=self.BEFORE))
        for model_id in providers.MODELS:
            with self.subTest(model=model_id):
                self.assertGreaterEqual(providers.needed_ceiling(model_id, writer.MAX_OUTPUT_TOKENS, day=self.AFTER),
                                        frames_then)
        self.assertGreater(providers.needed_ceiling(gemini.MODEL, writer.MAX_OUTPUT_TOKENS, day=self.AFTER),
                           providers.needed_ceiling(gemini.MODEL, writer.MAX_OUTPUT_TOKENS, day=self.BEFORE))


class CeilingTest(unittest.TestCase):
    DAY = datetime.date(2026, 11, 16)

    def test_the_minimum_ceiling_covers_two_attempts_and_the_frames_and_is_never_under_a_dollar(self):
        for model_id in providers.MODELS:
            with self.subTest(model=model_id):
                minimum = providers.minimum_ceiling(model_id, writer.MAX_OUTPUT_TOKENS, day=self.DAY)
                needed = 2 * gemini.token_cost(providers.REFERENCE_INPUT_TOKENS, writer.MAX_OUTPUT_TOKENS,
                                               providers.MODELS[model_id].prices, self.DAY) \
                    + gemini.worst_attempt_cost(providers.REFERENCE_FRAMES, day=self.DAY)
                self.assertGreaterEqual(minimum, needed)
                self.assertLess(minimum - needed, 0.10 + 1e-9) if needed > 1 else self.assertEqual(minimum, 1.00)
                self.assertAlmostEqual(minimum * 10, round(minimum * 10))
        self.assertEqual(providers.minimum_ceiling("claude-opus-5-5", writer.MAX_OUTPUT_TOKENS, day=self.DAY), 1.80)
        self.assertEqual(providers.minimum_ceiling("gpt-6.1-sol", writer.MAX_OUTPUT_TOKENS, day=self.DAY), 1.00)

    def test_the_summarys_own_ceiling_fits_two_attempts_of_each_model(self):
        self.assertEqual(providers.summary_ceiling("gemini-flash-latest", writer.MAX_OUTPUT_TOKENS, self.DAY), 0.50)
        self.assertEqual(providers.summary_ceiling("gpt-6.1-sol", writer.MAX_OUTPUT_TOKENS, self.DAY), 0.80)
        self.assertEqual(providers.summary_ceiling("claude-opus-5-5", writer.MAX_OUTPUT_TOKENS, self.DAY), 1.50)

    def test_the_shown_cost_of_one_summary(self):
        self.assertAlmostEqual(providers.shown_cost("gpt-6.1-sol", self.DAY), 0.244)
        self.assertAlmostEqual(providers.shown_cost("claude-opus-5-5", self.DAY), 0.488)
        self.assertAlmostEqual(providers.shown_cost("gemini-flash-latest", self.DAY), 0.09150)
        self.assertAlmostEqual(providers.shown_cost("gemini-flash-latest", datetime.date(2027, 1, 1)), 0.18300)


if __name__ == "__main__":
    unittest.main()
