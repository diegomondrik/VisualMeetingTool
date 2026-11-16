"""WI-2.0.0, amendment 1: the summary's model chosen in Settings and on the
command line (WI200-AC12), each provider's key (WI200-AC13), and a whole
run whose summary is written by GPT-6.1 Sol against a fake OpenAI server,
with the frames read by a fake Gemini. No key and no network."""

import contextlib
import io
import json

from meetingtool.app import company, jobs
from meetingtool.summary import providers, writer
from meetingtool.summary.__main__ import main as summary_main
from tests import test_summary
from tests.test_app import Processing, Running
from tests.test_proveedores import FakeProvider, openai_answer
from tests.test_reading import KEY, FakeGemini, answer_for

OPENAI_KEY = "sk-" + "t3st" * 10


class ModelSettingsTest(Running):
    model = None  # the application as it is installed: nothing chosen yet
    ceiling_floor = True

    def test_sol_is_chosen_by_default_and_the_claude_models_are_marked_untested(self):
        self.assertEqual(company.summary_model(self.data), "gpt-6.1-sol")
        text = self.page("/settings")
        self.assertIn('value="gpt-6.1-sol" checked', text)
        self.assertIn("GPT-6.1 Sol — OpenAI · recomendado", text)
        self.assertIn("Claude Opus 5.5 — Anthropic · sin probar en la aplicación", text)
        self.assertIn("Claude Sonnet 5.5 — Anthropic · sin probar en la aplicación", text)
        self.assertIn("Gemini Flash — Google", text)
        self.assertIn(f"~{text_money(providers.shown_cost('gpt-6.1-sol'))} el resumen", text)

    def test_the_model_is_saved_in_the_settings_and_one_outside_the_list_is_refused(self):
        self.api("/api/summary-model", {"model": "claude-opus-5-5"})
        self.assertEqual(company.summary_model(self.data), "claude-opus-5-5")
        self.assertEqual(json.loads((self.data / company.SETTINGS_NAME).read_text(encoding="utf-8"))["summary_model"],
                         "claude-opus-5-5")
        self.assertIn('value="claude-opus-5-5" checked', self.page("/settings"))
        for wrong in ("gpt-6.1-terra", "", 7, None):
            with self.subTest(model=wrong):
                self.api("/api/summary-model", {"model": wrong}, expect=400)
        self.assertEqual(company.summary_model(self.data), "claude-opus-5-5")

    def test_a_record_edited_by_hand_falls_back_to_the_default(self):
        (self.data / company.SETTINGS_NAME).write_text('{"summary_model": "gpt-9"}', encoding="utf-8")
        self.assertEqual(company.summary_model(self.data), providers.DEFAULT_MODEL)

    def test_a_new_meeting_starts_with_the_ceiling_the_chosen_model_needs(self):
        project = self.new_project()
        self.assertIn('name="max_cost" type="number" min="0.01" max="5" step="0.01" value="1.00"',
                      self.page(f"/p/{project}/new"))
        self.api("/api/summary-model", {"model": "claude-opus-5-5"})
        self.assertIn('value="1.80"', self.page(f"/p/{project}/new"))


def text_money(value):
    return f"US${value:,.3f}".replace(",", "_").replace(".", ",").replace("_", ".")


class ProviderKeysTest(Running):
    def test_each_providers_key_is_saved_and_deleted_by_its_name_and_never_shown(self):
        text = self.page("/settings")
        for name in ("gemini", "openai", "anthropic"):
            self.assertIn(f'id="key-status-{name}"', text)
        self.api("/api/key", {"provider": "openai", "key": f"  {OPENAI_KEY}  "})
        self.assertEqual(self.keys.others, {"VisualMeetingTool/openai": OPENAI_KEY})
        self.assertEqual(self.keys.key, KEY)  # Gemini's is left as it was
        text = self.page("/settings")
        self.assertNotIn(OPENAI_KEY, text)
        status = text.split('id="key-status-openai">', 1)[1].split("</p>", 1)[0]
        self.assertEqual(status, f"Hay una clave guardada ({len(OPENAI_KEY)} caracteres). No se muestra nunca.")
        self.assertIn("¿Borrar la clave de OpenAI guardada?", text)
        self.api("/api/key/delete", {"provider": "openai"})
        self.assertEqual(self.keys.others, {})
        self.assertEqual(self.keys.key, KEY)

    def test_an_unknown_provider_is_refused(self):
        self.api("/api/key", {"provider": "deepseek", "key": OPENAI_KEY}, expect=400)
        self.api("/api/key/delete", {"provider": ["openai"]}, expect=400)
        self.assertEqual(self.keys.others, {})


class SolRun(Processing):
    model = "gpt-6.1-sol"
    ceiling_floor = True

    def setUp(self):
        self.openai = FakeProvider("/v1/responses", lambda body: openai_answer(
            test_summary.summary_text("es", "requirements"))).__enter__()
        self.addCleanup(self.openai.__exit__, None, None, None)
        super().setUp()
        self.keys.save(OPENAI_KEY, "VisualMeetingTool/openai")

    def script(self):
        return [lambda first, count: answer_for(first, count)]

    def summary_endpoints(self):
        return {"openai": self.openai.endpoint}


class SolRunTest(SolRun):
    def test_the_frames_go_to_gemini_and_the_summary_to_sol_with_its_own_key(self):
        job = self.process(max_cost=jobs.default_ceiling(self.data))
        self.assertEqual(job["state"], "done", job["error"])
        self.assertTrue(all(request["images"] for request in self.fake.requests))  # Gemini read the frames only
        self.assertEqual(len(self.openai.requests), 1)
        sent = self.openai.requests[0]
        self.assertEqual(sent["headers"]["authorization"], f"Bearer {OPENAI_KEY}")
        self.assertEqual((sent["body"]["model"], sent["body"]["store"]), ("gpt-6.1-sol", False))
        self.assertNotIn(KEY, json.dumps(sent))
        self.assertTrue(all(r["headers"]["x-goog-api-key"] == KEY for r in self.fake.requests))
        self.assertIn("gpt-6.1-sol-2026-10-01", job_models(self, job))

    def test_without_the_openai_key_nothing_is_sent(self):
        self.keys.delete("VisualMeetingTool/openai")
        answer = self.process(expect=400, max_cost=jobs.default_ceiling(self.data))
        self.assertIn("no hay una clave de OpenAI guardada", answer["error"])
        self.assertEqual((self.fake.requests, self.openai.requests), ([], []))

    def test_a_ceiling_under_what_the_model_needs_is_refused_saying_the_minimum(self):
        answer = self.process(expect=400, max_cost=0.5)
        self.assertIn("con GPT-6.1 Sol el techo tiene que ser de al menos US$1,00", answer["error"])
        self.assertEqual((self.fake.requests, self.openai.requests), ([], []))


def job_models(test, job):
    from meetingtool.app import library
    record = next(m for m in __import__("meetingtool.projects.store", fromlist=["x"]).list_meetings(
        test.data, test.project) if m["id"] == job["meeting"])
    run = json.loads((test.data / test.project / record["folder"] / library.RUN_NAME).read_text(encoding="utf-8"))
    return run["models"]


class CommandTest(test_summary.Workspace):
    def test_the_command_writes_with_sol_by_default_and_its_own_key(self):
        keys = {"VisualMeetingTool/openai": OPENAI_KEY}
        with FakeProvider("/v1/responses", lambda body: openai_answer(test_summary.summary_text("en"))) as fake, \
                contextlib.redirect_stdout(io.StringIO()) as out:
            code = summary_main(["--frames", str(self.frames), "--transcript", str(self.transcript), "--language", "en"],
                                read_key=lambda target=None: keys.get(target), endpoints={"openai": fake.endpoint},
                                sleep=lambda s: None)
        self.assertEqual(code, 0)
        self.assertEqual(fake.requests[0]["body"]["model"], "gpt-6.1-sol")
        self.assertIn("budget US$0.80", out.getvalue())
        self.assertIn("model gpt-6.1-sol-2026-10-01", out.getvalue())

    def test_without_the_providers_key_or_with_a_model_outside_the_list_nothing_is_sent(self):
        with FakeProvider("/v1/responses", lambda body: openai_answer(test_summary.summary_text("en"))) as fake:
            error = io.StringIO()
            with contextlib.redirect_stderr(error):
                code = summary_main(["--frames", str(self.frames), "--transcript", str(self.transcript)],
                                    read_key=lambda target=None: KEY if target is None else None,
                                    endpoints={"openai": fake.endpoint})
            self.assertEqual(code, 2)
            self.assertIn("no OpenAI key is saved. Save yours with: the application's Settings", error.getvalue())
            error = io.StringIO()
            with contextlib.redirect_stderr(error):
                code = summary_main(["--frames", str(self.frames), "--transcript", str(self.transcript), "--model",
                                     "gpt-6.1-terra"], read_key=lambda target=None: KEY)
            self.assertEqual(code, 2)
            self.assertIn("there is no model 'gpt-6.1-terra' for the summary", error.getvalue())
        self.assertEqual(fake.requests, [])

    def test_the_register_is_still_gemini_s_whatever_the_model(self):
        from tests import test_qa
        # Where the request goes is what is checked: the answer is another transcript's, so it is refused.
        with FakeGemini([test_qa.json_answer(test_qa.verbal())] * 2) as fake,                 contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            summary_main(["--frames", str(self.frames), "--transcript", str(self.transcript), "--format", "qa",
                          "--language", "es"], read_key=lambda: KEY, endpoint=fake.endpoint, sleep=lambda s: None)
        self.assertTrue(fake.requests)
        self.assertTrue(all(r["path"].endswith(":generateContent") for r in fake.requests))
        self.assertEqual({r["headers"]["x-goog-api-key"] for r in fake.requests}, {KEY})
