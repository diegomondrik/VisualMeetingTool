"""Tests for meetingtool.summary. Gemini is the fake on localhost from
test_reading: no test reaches the network. Transcripts, frames readings and
projects are invented at test time in a temporary folder."""

import contextlib
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from meetingtool.frames.transcript import read_turns
from meetingtool.projects import store
from meetingtool.reading import gemini
from meetingtool.summary import writer
from meetingtool.summary.__main__ import main
from tests.test_frames import write_teams_docx
from tests.test_reading import KEY, FakeGemini

REPOSITORY = Path(__file__).resolve().parent.parent
SPANISH = [("Ana Pérez", "0:04", "Buen día, revisamos el costo de proceso de la planta."),
           ("Juan Gómez", "1:22", "Fijate el total de la columna, que está por encima de lo esperado."),
           ("Ana Pérez", "1:02:03", "Queda acordado: Juan manda el detalle el viernes.")]
ENGLISH = [("Ann Parker", "0:04", "Good morning, we are reviewing the plant's processing cost."),
           ("John Green", "1:22", "Look at the total of the column, it is above what we expected."),
           ("Ann Parker", "1:02:03", "Agreed: John sends the detail on Friday.")]


def summary_text(language="es", meeting_type=None, drop=None, repeat=None, swap=False, points=True):
    headings = writer.required_headings(language, meeting_type)
    if swap:
        headings[1], headings[2] = headings[2], headings[1]
    parts = []
    for heading in headings:
        if heading == drop:
            continue
        if heading == writer.KEY_POINTS[language]:
            body = "- Juan manda el detalle el viernes\n- El total supera lo esperado" if points else "(ninguno)"
        else:
            body = f"Texto de {heading}."
        parts.append(f"## {heading}\n{body}")
        if heading == repeat:
            parts.append(f"## {heading}\nOtra vez.")
    return "\n\n".join(parts)


def answer(text, finish="STOP"):
    return {"candidates": [{"content": {"parts": [{"text": text}]}, "finishReason": finish}],
            "usageMetadata": {"promptTokenCount": 30000, "candidatesTokenCount": 3000, "thoughtsTokenCount": 2000},
            "modelVersion": "fake-flash-1"}


def returning(text, finish="STOP"):
    return lambda first, count: answer(text, finish)


class Workspace(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.frames = self.tmp / "frames-out"
        self.frames.mkdir()
        (self.frames / gemini.OUTPUT_NAME).write_text(
            "# What each frame shows\n\n- FRAME 1: frame_001_t00-01-22.jpg\n\n[FRAME 1]\n- Key Data: total 1.250\n",
            encoding="utf-8")
        self.transcript = self.tmp / "meeting.docx"
        write_teams_docx(self.transcript, SPANISH)
        self.data = self.tmp / "data"
        self.sleeps = []

    def tearDown(self):
        self._tmp.cleanup()

    def summarise(self, fake, **kwargs):
        return writer.write_summary(self.frames, self.transcript, KEY, endpoint=fake.endpoint, sleep=self.sleeps.append,
                                    data_dir=self.data, **kwargs)

    def output(self):
        return self.frames / writer.OUTPUT_NAME


class TurnsTest(Workspace):
    def test_turns_keep_the_speaker_and_the_time(self):
        turns = read_turns(self.transcript)
        self.assertEqual([(t, s) for t, s, _ in turns], [(4, "Ana Pérez"), (82, "Juan Gómez"), (3723, "Ana Pérez")])
        self.assertIn("columna", turns[1][2])
        text = self.tmp / "timed.txt"
        text.write_text("[00:00:05] John: hello\n[00:01:00] bye\n", encoding="utf-8")
        self.assertEqual(read_turns(text), [(5, "", "John: hello"), (60, "", "bye")])


class WritingTest(Workspace):
    """WI09-AC01."""

    def test_one_request_carries_everything_and_the_summary_is_written_next_to_the_frames(self):
        with FakeGemini([returning(summary_text())]) as fake:
            result = self.summarise(fake)
        self.assertEqual(len(fake.requests), 1)
        request = fake.requests[0]
        prompt = request["body"]["contents"][0]["parts"][0]["text"]
        self.assertEqual(request["headers"]["x-goog-api-key"], KEY)
        self.assertNotIn(KEY, request["path"] + json.dumps(request["body"]))
        self.assertIn("[00:01:22] Juan Gómez: Fijate el total", prompt)
        self.assertIn("[FRAME 1]\n- Key Data: total 1.250", prompt)
        self.assertIn("Write the summary in Spanish.", prompt)
        for heading in writer.required_headings("es"):
            self.assertIn(f"## {heading}", prompt)
        self.assertEqual(request["body"]["generationConfig"]["maxOutputTokens"], 24576)
        self.assertEqual(self.output().read_text(encoding="utf-8").strip(), summary_text())
        self.assertEqual((result.language, result.attempts, result.model_versions), ("es", 1, ("fake-flash-1",)))
        self.assertAlmostEqual(result.estimated_cost_usd, gemini.token_cost(30000, 5000))
        self.assertEqual(result.meeting_id, "")

    def test_frames_not_yet_read_are_refused_before_any_request(self):
        (self.frames / gemini.OUTPUT_NAME).unlink()
        with FakeGemini() as fake:
            with self.assertRaises(writer.SummaryError) as caught:
                self.summarise(fake)
        self.assertIn("python -m meetingtool.reading read", str(caught.exception))
        self.assertEqual(fake.requests, [])

    def test_a_frames_folder_inside_a_git_work_tree_is_refused_before_any_request(self):
        with FakeGemini() as fake:
            with self.assertRaises(gemini.ReadingError):
                writer.write_summary(REPOSITORY / "not-created", self.transcript, KEY, endpoint=fake.endpoint)
        self.assertEqual(fake.requests, [])


class IncompleteSummaryTest(Workspace):
    """WI09-AC02."""

    def assert_refused(self, text, words, finish="STOP"):
        with FakeGemini([returning(text, finish), returning(text, finish)]) as fake:
            with self.assertRaises(writer.SummaryError) as caught:
                self.summarise(fake, project="acme", title="Revisión", date="2026-09-25")
        self.assertIn(words, str(caught.exception))
        self.assertEqual(len(fake.requests), 2, "an incomplete summary is retried exactly once")
        self.assertFalse(self.output().exists())
        self.assertEqual(store.list_meetings(self.data, "acme"), [])

    def setUp(self):
        super().setUp()
        store.create_project(self.data, "Acme", "Acme SA")

    def test_a_missing_section_is_refused(self):
        self.assert_refused(summary_text(drop="Tareas"), "'Tareas' 0 times")

    def test_a_repeated_section_is_refused(self):
        self.assert_refused(summary_text(repeat="Temas"), "'Temas' 2 times")

    def test_sections_out_of_order_are_refused(self):
        self.assert_refused(summary_text(swap=True), "not in the required order")

    def test_no_key_point_is_refused(self):
        self.assert_refused(summary_text(points=False), "no bullet point")

    def test_a_cut_summary_is_refused(self):
        self.assert_refused(summary_text(), "finishReason MAX_TOKENS", finish="MAX_TOKENS")

    def test_an_incomplete_summary_then_a_complete_one_succeeds(self):
        with FakeGemini([returning(summary_text(drop="Temas")), returning(summary_text())]) as fake:
            result = self.summarise(fake)
        self.assertEqual(result.attempts, 2)
        self.assertTrue(self.output().exists())


class ProjectTest(Workspace):
    """WI09-AC03."""

    def setUp(self):
        super().setUp()
        store.create_project(self.data, "Acme", "Acme SA", context="Costo de proceso")

    def test_the_meeting_is_added_and_the_next_summary_reads_what_the_project_knows(self):
        with FakeGemini([returning(summary_text(meeting_type="status")), returning(summary_text())]) as fake:
            first = self.summarise(fake, project="acme", title="Revisión de costos", date="2026-09-22", meeting_type="status")
            meetings = store.list_meetings(self.data, "acme")
            self.assertEqual([m["id"] for m in meetings], [first.meeting_id])
            self.assertEqual(meetings[0]["key_points"], ["Juan manda el detalle el viernes", "El total supera lo esperado"])
            self.assertEqual(meetings[0]["summary"], "Texto de Resumen ejecutivo.")
            self.assertIn("- Juan manda el detalle el viernes", store.knowledge_context(self.data, "acme"))
            self.summarise(fake, project="acme", title="Seguimiento", date="2026-09-29")
        second_prompt = fake.requests[1]["body"]["contents"][0]["parts"][0]["text"]
        self.assertIn("WHAT THE PROJECT ALREADY KNOWS", second_prompt)
        self.assertIn("Juan manda el detalle el viernes", second_prompt)
        self.assertIn("Costo de proceso", fake.requests[0]["body"]["contents"][0]["parts"][0]["text"])
        self.assertEqual(len(store.list_meetings(self.data, "acme")), 2)

    def test_a_bad_project_title_or_date_sends_nothing(self):
        cases = [dict(project="nope", title="T", date="2026-09-22"),
                 dict(project="acme", title="", date="2026-09-22"),
                 dict(project="acme", title="T", date="22/09/2026"),
                 dict(project="../x", title="T", date="2026-09-22")]
        with FakeGemini() as fake:
            for case in cases:
                with self.subTest(case=case):
                    with self.assertRaises(writer.SummaryError):
                        self.summarise(fake, **case)
        self.assertEqual(fake.requests, [])


class LanguageTypeKeyBudgetTest(Workspace):
    """WI09-AC04."""

    def test_the_language_is_the_transcripts_unless_given(self):
        self.assertEqual(writer.detect_language(" ".join(t for *_, t in SPANISH)), "es")
        self.assertEqual(writer.detect_language(" ".join(t for *_, t in ENGLISH)), "en")
        write_teams_docx(self.transcript, ENGLISH)
        with FakeGemini([returning(summary_text("en")), returning(summary_text("es"))]) as fake:
            self.assertEqual(self.summarise(fake).language, "en")
            self.assertEqual(self.summarise(fake, language="es").language, "es")
        self.assertIn("## Executive summary", fake.requests[0]["body"]["contents"][0]["parts"][0]["text"])
        self.assertIn("Write the summary in Spanish.", fake.requests[1]["body"]["contents"][0]["parts"][0]["text"])

    def test_a_meeting_type_adds_its_sections_and_they_are_required(self):
        with FakeGemini([returning(summary_text(meeting_type="technical"))] + [returning(summary_text())] * 2) as fake:
            self.summarise(fake, meeting_type="technical")
            with self.assertRaises(writer.SummaryError):
                self.summarise(fake, meeting_type="technical")
        self.assertIn("## Decisiones técnicas", fake.requests[0]["body"]["contents"][0]["parts"][0]["text"])

    def test_a_request_that_could_go_over_the_budget_is_not_sent(self):
        with FakeGemini() as fake:
            with self.assertRaises(gemini.ReadingError) as caught:
                self.summarise(fake, max_cost_usd=0.05)
        self.assertIn("budget of US$0.05", str(caught.exception))
        self.assertEqual(fake.requests, [])

    def test_the_key_never_appears_in_any_output(self):
        outputs = []
        for script in ([returning(summary_text())], [400], [returning(summary_text(drop="Temas"))] * 2):
            stdout, stderr = io.StringIO(), io.StringIO()
            with FakeGemini(script) as fake, contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                code = main(["--frames", str(self.frames), "--transcript", str(self.transcript)],
                            read_key=lambda: KEY, endpoint=fake.endpoint, sleep=self.sleeps.append)
            outputs.append((code, stdout.getvalue() + stderr.getvalue()))
        self.assertEqual([code for code, _ in outputs], [0, 2, 2])
        for _, text in outputs:
            self.assertNotIn(KEY, text)
        for path in self.frames.iterdir():
            self.assertNotIn(KEY, path.read_text(encoding="utf-8"))

    def test_with_no_key_saved_nothing_is_sent(self):
        stderr = io.StringIO()
        with FakeGemini() as fake, contextlib.redirect_stderr(stderr):
            code = main(["--frames", str(self.frames), "--transcript", str(self.transcript)],
                        read_key=lambda: None, endpoint=fake.endpoint)
        self.assertEqual(code, 2)
        self.assertIn("key set", stderr.getvalue())
        self.assertEqual(fake.requests, [])

    def test_the_module_runs_as_a_command(self):
        result = subprocess.run([sys.executable, "-m", "meetingtool.summary", "--help"], cwd=REPOSITORY,
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0)
        self.assertIn("--project", result.stdout)


if __name__ == "__main__":
    unittest.main()
