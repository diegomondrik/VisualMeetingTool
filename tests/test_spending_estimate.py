"""WI28: the spending ceiling says what it is, and a run stops when an answer
cost more than its estimate (the external review's R07).

- EstimateTest (WI28-AC01): an answer that cost more than the most its request
  was estimated to cost is returned and kept, and the run sends nothing more.
- StagesTest (WI28-AC01): the same across the stages of one run, through the
  application's job.
- WordingTest (WI28-AC02): the texts call the ceiling an estimated ceiling.

These tests need nothing but the project's libraries, so the CI runs them.
Each one pins a part of the rule: docs/evidence/01M4CM3YV6DMY3QDWAZDMAANW6/
mutations.py undoes each part and shows a test here fails.
"""

import json
import tempfile
import unittest
from pathlib import Path

from meetingtool import texts
from meetingtool.projects import store
from meetingtool.reading import gemini
from meetingtool.texts import en, es
from tests import test_summary
from tests.test_app import Processing
from tests.test_reading import KEY, FakeGemini, Workspace, answer_for

REPOSITORY = Path(__file__).resolve().parent.parent
# The review's case: an answer of 800,000 input tokens, which costs US$0.60, for a request estimated at US$0.10
# and a ceiling of US$0.50.
WORST = 0.10
CEILING = 0.50


def costing(text, prompt_tokens=800000, candidates=1, thoughts=0):
    """An answer that finished normally with the usage given."""
    answer = test_summary.answer(text)
    answer["usageMetadata"] = {"promptTokenCount": prompt_tokens, "candidatesTokenCount": candidates,
                               "thoughtsTokenCount": thoughts}
    return answer


def returning(answer):
    return lambda first, count: answer


def text_of(answer):
    return answer["candidates"][0]["content"]["parts"][0]["text"]


def refusing_first(answer):
    """A check that refuses the first answer it sees and takes the rest."""
    seen = []

    def check(received):
        seen.append(received)
        if len(seen) == 1:
            raise gemini.ReadingError("gemini.unfinished", finish="MAX_TOKENS")
        return text_of(received)
    return check


class EstimateTest(unittest.TestCase):
    def call(self, fake, keep, counters, text="¿Qué se decidió?", worst=WORST, ceiling=CEILING, check=text_of,
             retry_delays=()):
        payload = {"contents": [{"role": "user", "parts": [{"text": text}]}]}
        return gemini.call_checked(gemini.model_url(fake.endpoint, "gemini-flash-latest"), KEY, payload, check, worst,
                                   "x", retry_delays, lambda seconds: None, counters, ceiling, keep=keep)

    def kept(self, keep):
        return [json.loads(path.read_text(encoding="utf-8")) for path in sorted(keep.glob("*.json"))]

    def test_the_reviews_case_the_answer_is_kept_and_the_next_request_is_not_sent(self):
        with tempfile.TemporaryDirectory() as tmp, FakeGemini([returning(costing("Uno.")),
                                                               returning(costing("Dos."))]) as fake:
            keep, counters = Path(tmp) / gemini.KEPT_DIR, gemini.new_counters()
            self.assertEqual(self.call(fake, keep, counters), "Uno.")
            self.assertAlmostEqual(counters["overrun"]["cost"], 0.6, places=4)
            self.assertEqual(counters["overrun"]["estimated"], WORST)
            self.assertEqual([record["answer"] for record in self.kept(keep)], ["Uno."])
            with self.assertRaises(gemini.ReadingError) as raised:
                self.call(fake, keep, counters, text="Otra pregunta.")
            self.assertEqual(raised.exception.message.key, "gemini.estimate_short")
            self.assertEqual(len(fake.requests), 1)
            self.assertIn("US$0.6000", str(raised.exception))
            self.assertIn("US$0.1000", str(raised.exception))
            self.assertIn("PRICE_INPUT_PER_MILLION", str(raised.exception))

    def test_an_answer_under_the_ceiling_but_over_its_estimate_stops_the_run_all_the_same(self):
        # The estimate is what fell short, not the ceiling: US$0.60 of a ceiling of US$5.00.
        with tempfile.TemporaryDirectory() as tmp, FakeGemini([returning(costing("Uno.")),
                                                               returning(costing("Dos."))]) as fake:
            keep, counters = Path(tmp) / gemini.KEPT_DIR, gemini.new_counters()
            self.call(fake, keep, counters, ceiling=5.0)
            self.assertLess(counters["spent"] + WORST, 5.0)
            with self.assertRaises(gemini.ReadingError) as raised:
                self.call(fake, keep, counters, text="Otra pregunta.", ceiling=5.0)
            self.assertEqual(raised.exception.message.key, "gemini.estimate_short")
            self.assertEqual(len(fake.requests), 1)

    def test_a_refused_answer_that_cost_more_than_estimated_is_not_retried(self):
        with tempfile.TemporaryDirectory() as tmp, FakeGemini([returning(costing("Uno.")),
                                                               returning(costing("Dos."))]) as fake:
            keep, counters = Path(tmp) / gemini.KEPT_DIR, gemini.new_counters()
            with self.assertRaises(gemini.ReadingError) as raised:
                self.call(fake, keep, counters, ceiling=5.0, check=refusing_first(costing("Uno.")))
            self.assertEqual(raised.exception.message.key, "gemini.estimate_short")
            self.assertEqual(len(fake.requests), 1, "the retry was sent")
            self.assertIn("finishReason MAX_TOKENS", str(raised.exception))  # why the answer was refused
            self.assertEqual(self.kept(keep), [])  # refused: nothing to keep
            self.assertIsNotNone(counters["overrun"])
            self.assertAlmostEqual(counters["spent"], 0.6, places=4)  # but it was paid, and counted

    def test_a_retry_that_cost_more_than_estimated_is_returned_and_kept_and_stops_the_run(self):
        with tempfile.TemporaryDirectory() as tmp, FakeGemini([returning(test_summary.answer("Uno.")),
                                                               returning(costing("Dos.")),
                                                               returning(costing("Tres."))]) as fake:
            keep, counters = Path(tmp) / gemini.KEPT_DIR, gemini.new_counters()
            self.assertEqual(self.call(fake, keep, counters, ceiling=5.0, check=refusing_first(None)), "Dos.")
            self.assertEqual(len(fake.requests), 2)
            self.assertEqual([record["answer"] for record in self.kept(keep)], ["Dos."])
            with self.assertRaises(gemini.ReadingError):
                self.call(fake, keep, counters, text="Otra pregunta.", ceiling=5.0)
            self.assertEqual(len(fake.requests), 2)

    def test_the_kept_answer_says_what_it_cost_and_the_same_request_again_pays_nothing(self):
        with tempfile.TemporaryDirectory() as tmp, FakeGemini([returning(costing("Uno."))]) as fake:
            keep = Path(tmp) / gemini.KEPT_DIR
            self.call(fake, keep, gemini.new_counters())
            self.assertAlmostEqual(self.kept(keep)[0]["cost_usd"], 0.6, places=4)
            again = gemini.new_counters()
            self.assertEqual(self.call(fake, keep, again), "Uno.")
            self.assertEqual((len(fake.requests), again["spent"], again["attempts"], again["overrun"]),
                             (1, 0.0, 0, None))

    def test_an_answer_at_its_estimate_or_under_it_changes_nothing(self):
        at = gemini.token_cost(1000, 500)
        with tempfile.TemporaryDirectory() as tmp, FakeGemini([
                returning(costing("Uno.", 1000, 500)), returning(costing("Dos.", 1000, 499)),
                returning(costing("Tres.", 1000, 400, 99))]) as fake:
            keep, counters = Path(tmp) / gemini.KEPT_DIR, gemini.new_counters()
            for n, text in enumerate(("Uno.", "Dos.", "Tres.")):
                self.assertEqual(self.call(fake, keep, counters, text=text, worst=at, ceiling=5.0), text)
            self.assertIsNone(counters["overrun"])
            self.assertEqual(len(fake.requests), 3)

    def test_one_token_more_than_the_estimate_is_an_overrun(self):
        at = gemini.token_cost(1000, 500)
        with tempfile.TemporaryDirectory() as tmp, FakeGemini([returning(costing("Uno.", 1000, 500, 1))]) as fake:
            counters = gemini.new_counters()
            self.call(fake, Path(tmp) / gemini.KEPT_DIR, counters, worst=at, ceiling=5.0)
            self.assertEqual(counters["overrun"]["estimated"], at)

    def test_an_answer_with_no_usage_is_counted_at_its_estimate_and_is_not_an_overrun(self):
        answer = costing("Uno.")
        del answer["usageMetadata"]
        with tempfile.TemporaryDirectory() as tmp, FakeGemini([returning(answer)]) as fake:
            counters = gemini.new_counters()
            self.call(fake, Path(tmp) / gemini.KEPT_DIR, counters, ceiling=5.0)
            self.assertEqual((counters["spent"], counters["overrun"]), (WORST, None))

    def test_every_run_starts_with_no_overrun(self):
        self.assertIsNone(gemini.new_counters()["overrun"])
        self.assertIsNot(gemini.new_counters(), gemini.new_counters())


class ReadingTest(Workspace):
    """The reading's own chunks are stages of one run too."""

    def test_the_chunk_after_an_answer_that_cost_more_than_estimated_is_not_sent(self):
        def big(first, count):
            answer = answer_for(first, count)
            answer["usageMetadata"]["promptTokenCount"] = 800000
            return answer

        with FakeGemini([big]) as fake:
            with self.assertRaises(gemini.ReadingError) as raised:
                self.read(fake, max_cost_usd=5.0)
        self.assertEqual(raised.exception.message.key, "gemini.estimate_short")
        self.assertEqual(len(fake.requests), 1)
        self.assertFalse(self.output().exists())  # nothing is written, as when any chunk fails
        self.assertEqual(len(list((self.frames / gemini.KEPT_DIR).glob("*.json"))), 1)  # but what was paid is kept

    def test_the_default_run_of_the_fake_never_trips_it(self):
        with FakeGemini() as fake:
            result = self.read(fake)
        self.assertEqual(result.requests, 3)


class StagesTest(Processing):
    """The reading's answer cost more than estimated: the summary is not sent, and the meeting processed again
    reuses the reading."""

    def script(self):
        def big(first, count):
            answer = answer_for(first, count)
            answer["usageMetadata"]["promptTokenCount"] = 800000
            return answer

        return [big, test_summary.returning(test_summary.summary_text("es", "requirements"))]

    def test_a_later_stage_sends_nothing_and_the_page_says_why_and_the_next_run_pays_nothing_for_the_reading(self):
        failed = self.process(max_cost=5)
        self.assertEqual(failed["state"], "failed", failed["error"])
        self.assertEqual(self.states(failed)[1:3], [("reading", "done"), ("summary", "failed")])
        self.assertEqual(failed["failed_stage_name"], "summary")
        self.assertIn("se frenó antes de mandar el resumen", failed["error"])
        self.assertIn("costó US$0,60", failed["error"])  # the application speaks Spanish, with its decimal comma
        self.assertIn("PRICE_INPUT_PER_MILLION", failed["error"])
        self.assertEqual(self.summary_requests(), [])
        self.assertEqual(len(self.fake.requests), 1)
        self.assertNothingLeft(failed, kept=True)  # the reading, which was paid
        self.assertAlmostEqual(failed["kept"]["paid_usd"], failed["spent_usd"], places=3)
        paid = len(self.fake.requests)
        done = self.process(max_cost=5)
        self.assertEqual(done["state"], "done", done["error"])
        self.assertEqual(len(self.fake.requests) - paid, 1, "only the summary is sent")
        self.assertEqual(len(self.summary_requests()), 1)
        self.assertEqual(len(store.list_meetings(self.data, self.project)), 1)
        self.assertEqual(done["stages"][1]["cost_usd"], 0)  # the reading, from what was kept

    def test_a_run_whose_answers_cost_what_was_estimated_goes_on_to_the_end(self):
        self.fake.script[:] = [lambda first, count: answer_for(first, count),
                               test_summary.returning(test_summary.summary_text("es", "requirements"))]
        done = self.process(max_cost=5)
        self.assertEqual(done["state"], "done", done["error"])


class WordingTest(unittest.TestCase):
    """WI28-AC02: the ceiling is called an estimate, in both languages, and never a guarantee."""

    CEILING_KEYS = ("app.new.ceiling", "app.new.ceiling_hint", "app.cost.total_html", "js.spent",
                    "gemini.over_budget", "gemini.estimate_short")

    def test_the_form_the_run_page_and_the_message_call_it_estimated_in_each_language(self):
        for catalog, estimated in ((en.TEXTS, "estimated"), (es.TEXTS, "estimad")):
            for key in ("app.new.ceiling", "app.cost.total_html", "js.spent"):
                self.assertIn(estimated, catalog[key].lower(), key)
        self.assertIn("list prices", en.TEXTS["app.new.ceiling_hint"])
        self.assertIn("list prices", en.TEXTS["app.cost.total_html"])
        self.assertIn("precios de lista", es.TEXTS["app.new.ceiling_hint"])
        self.assertIn("precios de lista", es.TEXTS["app.cost.total_html"])

    def test_the_form_says_a_request_already_sent_is_paid_and_the_run_stops_when_an_answer_cost_more(self):
        hint = en.TEXTS["app.new.ceiling_hint"]
        self.assertIn("already sent is paid even if its answer is refused", hint)
        self.assertIn("stops if an answer cost more than estimated", hint)
        hint = es.TEXTS["app.new.ceiling_hint"]
        self.assertIn("ya mandado se paga aunque se rechace su respuesta", hint)
        self.assertIn("se frena si una respuesta costó más de lo estimado", hint)
        self.assertIn("already sent is paid even if its answer is refused", en.TEXTS["app.cost.total_html"])
        self.assertIn("ya mandado se paga aunque se rechace su respuesta", es.TEXTS["app.cost.total_html"])

    def test_the_message_of_a_run_that_stopped_says_what_was_estimated_what_it_cost_and_what_was_not_sent(self):
        message = texts.Message("gemini.estimate_short", what=texts.External("the summary"),
                                after=texts.External("frames 1-2"), estimated=0.1, cost=0.6, refused="")
        for language, words in (("en", ("the summary", "frames 1-2", "US$0.6000", "US$0.1000", "PRICE_OUTPUT_PER_MILLION",
                                        "nothing more is sent", "out of date")),
                                ("es", ("the summary", "frames 1-2", "US$0,6000", "US$0,1000", "PRICE_OUTPUT_PER_MILLION",
                                        "no se manda nada más", "desactualizados"))):
            said = message.text(language)
            for word in words:
                self.assertIn(word, said, language)

    def test_no_text_about_the_ceiling_calls_it_a_guarantee(self):
        for catalog in (en.TEXTS, es.TEXTS):
            for key in self.CEILING_KEYS:
                self.assertNotRegex(catalog[key].lower(), r"guarant|garant|asegur|seguro", key)

    def test_the_readme_and_the_module_say_the_same(self):
        readme = " ".join((REPOSITORY / "README.md").read_text(encoding="utf-8").split())
        for words in ("is an estimate, not a guarantee", "list prices", "is paid even if its answer is then refused",
                      "the run sends nothing more", "estimated spending ceiling"):
            self.assertIn(words, readme)
        for words in ("estimated spending ceiling", "not a guarantee", "list prices",
                      "paid even if its answer is\nrefused", "sends nothing more"):
            self.assertIn(words, gemini.__doc__)


if __name__ == "__main__":
    unittest.main()
