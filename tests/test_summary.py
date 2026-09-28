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
from unittest import mock

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
        if heading == writer.KEY_POINTS[language] and language == "en":
            body = "- John sends the detail on Friday\n- The total is above what was expected" if points else "(none)"
        elif heading == writer.KEY_POINTS[language]:
            body = "- Juan manda el detalle el viernes\n- El total supera lo esperado" if points else "(ninguno)"
        else:
            body = f"The text of {heading}." if language == "en" else f"Texto de {heading}."
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


class ReviewCorrectionsTest(Workspace):
    """The review's P1-1, P2-1, P2-2 and P2-4, and the input side of the budget."""

    def setUp(self):
        super().setUp()
        store.create_project(self.data, "Acme", "Acme SA")

    def test_a_date_the_project_would_refuse_is_refused_before_any_request(self):
        with FakeGemini() as fake:
            for date in ("20260922", "2026-W39-2", "2026-02-30"):
                with self.subTest(date=date):
                    with self.assertRaises(writer.SummaryError):
                        self.summarise(fake, project="acme", title="T", date=date)
        self.assertEqual(fake.requests, [])

    def test_a_meeting_that_cannot_be_added_after_the_summary_is_written_is_a_clear_error(self):
        def refuse(*args, **kwargs):
            raise OSError("disk full")
        with FakeGemini([returning(summary_text())]) as fake, mock.patch.object(store, "add_meeting", refuse):
            with self.assertRaises(writer.SummaryError) as caught:
                self.summarise(fake, project="acme", title="T", date="2026-09-22")
        self.assertIn("was written, but the meeting could not be added", str(caught.exception))
        self.assertTrue(self.output().exists(), "the paid summary is kept")

    def test_headings_in_bold_with_a_colon_numbered_or_at_level_four_are_accepted(self):
        text = summary_text()
        variants = [text.replace("## Temas", "## **Temas**"), text.replace("## Temas", "#### Temas:"),
                    text.replace("## Temas", "## 7. Temas"), text.replace("## Temas", "## _Temas_")]
        for variant in variants:
            with self.subTest(variant=variant[text.find("Temas") - 8:text.find("Temas") + 12]):
                self.assertEqual(writer.check_summary(answer(variant), writer.required_headings("es"), "es"), variant)

    def test_a_rule_or_an_italic_note_is_not_a_key_point(self):
        text = summary_text(points=False) + "\n---\n*No hubo puntos clave.*"
        with self.assertRaises(writer.SummaryError):
            writer.check_summary(answer(text), writer.required_headings("es"), "es")
        self.assertEqual(writer.key_points("## Puntos clave\n- uno\n* dos\n---\n", "es"), ["uno", "dos"])

    def test_a_read_frames_folder_inside_a_git_work_tree_is_refused_before_any_request(self):
        repository = self.tmp / "some-repository"
        inside = repository / "frames"
        inside.mkdir(parents=True)
        subprocess.run(["git", "init", "-q", str(repository)], check=True)
        (inside / gemini.OUTPUT_NAME).write_text("[FRAME 1]\n", encoding="utf-8")
        with FakeGemini() as fake:
            with self.assertRaises(gemini.ReadingError) as caught:
                writer.write_summary(inside, self.transcript, KEY, endpoint=fake.endpoint)
        self.assertIn("inside the git work tree", str(caught.exception))
        self.assertEqual(fake.requests, [])

    def test_the_budget_counts_the_input_as_well_as_the_output_cap(self):
        just_the_output = gemini.token_cost(0, writer.MAX_OUTPUT_TOKENS)
        with FakeGemini() as fake:
            with self.assertRaises(gemini.ReadingError):
                self.summarise(fake, max_cost_usd=just_the_output + 0.0001)
        self.assertEqual(fake.requests, [])


NEW_TYPES = ("presale", "negotiation", "requirements")
# The sections of every type as they were before D-178: they must not change.
UNCHANGED = {
    None: ["Resumen ejecutivo", "Participantes", "Decisiones", "Tareas", "Lo que se vio en pantalla",
           "Pendientes prometidos", "Temas", "Más allá de la agenda", "Puntos clave"],
    "kickoff": ["Definición del proyecto", "Estructura del equipo"],
    "status": ["Estado del proyecto", "Cambios desde la reunión anterior"],
    "technical": ["Decisiones técnicas", "Análisis visual técnico", "Dependencias y riesgos técnicos"],
    "training": ["Contexto de la capacitación", "Evaluación de comprensión", "Brechas y material de seguimiento",
                 "Próximos pasos de adopción"],
}


def prompt_of(request):
    return request["body"]["contents"][0]["parts"][0]["text"]


def guide_in(prompt, heading):
    """The guide the prompt gives under '## heading'."""
    return prompt.split(f"\n## {heading}\n", 1)[1].split("\n## ", 1)[0].split("\n\n", 1)[0]


class NewTypesTest(Workspace):
    """WI12-AC01: the three new types ask for their sections and a summary
    without them is not complete; the other types stay as they were."""

    def test_each_new_type_is_accepted_with_its_sections_in_both_languages(self):
        for meeting_type in NEW_TYPES:
            for language in ("es", "en"):
                with self.subTest(meeting_type=meeting_type, language=language):
                    headings = writer.required_headings(language, meeting_type)
                    own = writer.MEETING_TYPES[meeting_type].headings[language]
                    self.assertEqual(headings[2:2 + len(own)], own, "its own sections come after the participants")
                    text = summary_text(language, meeting_type)
                    self.assertEqual(writer.check_summary(answer(text), headings, language), text)

    def test_a_summary_missing_any_section_of_its_type_is_refused(self):
        for meeting_type in NEW_TYPES:
            for heading in writer.MEETING_TYPES[meeting_type].headings["es"]:
                with self.subTest(meeting_type=meeting_type, heading=heading):
                    with FakeGemini([returning(summary_text(meeting_type=meeting_type, drop=heading))] * 2) as fake:
                        with self.assertRaises(writer.SummaryError) as caught:
                            self.summarise(fake, meeting_type=meeting_type)
                    self.assertIn(f"'{heading}' 0 times", str(caught.exception))
                    self.assertEqual(len(fake.requests), 2)
                    self.assertFalse(self.output().exists())

    def test_a_summary_without_a_type_is_not_complete_for_a_new_type(self):
        for meeting_type in NEW_TYPES:
            with self.subTest(meeting_type=meeting_type):
                with self.assertRaises(writer.SummaryError):
                    writer.check_summary(answer(summary_text()), writer.required_headings("es", meeting_type), "es")

    def test_the_other_types_keep_their_sections_their_place_and_their_guides(self):
        self.assertEqual(writer.required_headings("es"), UNCHANGED[None])
        for meeting_type, own in UNCHANGED.items():
            if meeting_type is None:
                continue
            with self.subTest(meeting_type=meeting_type):
                self.assertEqual(writer.required_headings("es", meeting_type),
                                 UNCHANGED[None][:-1] + own + UNCHANGED[None][-1:])
                prompt = writer.build_prompt([(4, "Ana", "Hola")], "[FRAME 1]", "es", meeting_type)
                self.assertNotIn("MEETING TYPE:", prompt)
                for heading, guide in zip(writer.SECTIONS["es"], writer.GUIDE):
                    self.assertEqual(guide_in(prompt, heading), guide)

    def test_the_command_offers_the_new_types_and_not_the_retired_one(self):
        result = subprocess.run([sys.executable, "-m", "meetingtool.summary", "--help"], cwd=REPOSITORY,
                                capture_output=True, text=True)
        for meeting_type in NEW_TYPES:
            self.assertIn(meeting_type, result.stdout)
        for meeting_type, words in (("discovery", "use 'presale' or 'requirements'"),
                                    ("sales", "unknown meeting type 'sales'; one of presale, negotiation")):
            stderr = io.StringIO()
            with FakeGemini() as fake, contextlib.redirect_stderr(stderr):
                code = main(["--frames", str(self.frames), "--transcript", str(self.transcript), "--type",
                             meeting_type], read_key=lambda: KEY, endpoint=fake.endpoint)
            self.assertEqual(code, 2)
            self.assertIn(words, stderr.getvalue())
            self.assertEqual(fake.requests, [])


class StanceTest(Workspace):
    """WI12-AC02: each new type changes the request for the whole summary,
    not only the sections at its end."""

    def prompts(self):
        return {meeting_type: writer.build_prompt(read_turns(self.transcript), "[FRAME 1]", "es", meeting_type)
                for meeting_type in (None,) + NEW_TYPES}

    def test_each_new_type_sets_a_stance_before_the_sections(self):
        for meeting_type, prompt in self.prompts().items():
            with self.subTest(meeting_type=meeting_type):
                if meeting_type is None:
                    self.assertNotIn("MEETING TYPE:", prompt)
                    continue
                stance = f"MEETING TYPE: {meeting_type}. {writer.MEETING_TYPES[meeting_type].stance}"
                self.assertIn(stance, prompt)
                self.assertLess(prompt.index(stance), prompt.index("## Resumen ejecutivo"))

    def test_each_new_type_changes_the_guide_of_the_decisions_and_they_all_differ(self):
        guides = {meeting_type: guide_in(prompt, "Decisiones") for meeting_type, prompt in self.prompts().items()}
        self.assertEqual(guides[None], writer.GUIDE[2])
        self.assertEqual(len(set(guides.values())), len(guides), "every type reads the decisions its own way")

    def test_in_a_discovery_the_pending_items_are_what_is_still_to_be_found_out(self):
        prompts = self.prompts()
        self.assertIn("still to be found out", guide_in(prompts["requirements"], "Pendientes prometidos"))
        self.assertEqual(guide_in(prompts[None], "Pendientes prometidos"), writer.GUIDE[5])
        self.assertIn("biggest unknowns", guide_in(prompts["requirements"], "Resumen ejecutivo"))
        self.assertIn("signal, not a decision", prompts["presale"])

    def test_the_request_sent_carries_the_stance(self):
        with FakeGemini([returning(summary_text(meeting_type="requirements"))]) as fake:
            self.summarise(fake, meeting_type="requirements")
        prompt = prompt_of(fake.requests[0])
        self.assertIn("MEETING TYPE: requirements.", prompt)
        self.assertIn("## Proceso actual\nHow the client works today", prompt)


class RetiredTypeTest(Workspace):
    """WI12-AC03: a meeting stored with the retired type is still read."""

    def setUp(self):
        super().setUp()
        store.create_project(self.data, "Acme", "Acme SA")
        # As the code before D-178 stored it.
        store.add_meeting(self.data, "acme", "Primera charla", "2026-09-01", meeting_type="discovery",
                          summary="Relevamos el costo de proceso.", key_points=["Falta el detalle por planta"])

    def test_the_old_meeting_is_listed_and_read_into_the_next_summary(self):
        with FakeGemini([returning(summary_text(meeting_type="requirements"))]) as fake:
            result = self.summarise(fake, project="acme", title="Relevamiento", date="2026-09-22",
                                    meeting_type="requirements")
        self.assertEqual([m["meeting_type"] for m in store.list_meetings(self.data, "acme")],
                         ["discovery", "requirements"])
        prompt = prompt_of(fake.requests[0])
        self.assertIn("### 2026-09-01: Primera charla (discovery)", prompt)
        self.assertIn("- Falta el detalle por planta", prompt)
        self.assertIn("A meeting marked (discovery) above used a meeting type that no longer exists", prompt)
        self.assertTrue(result.meeting_id)

    def test_the_note_is_only_there_when_an_old_meeting_is(self):
        prompt = writer.build_prompt([(4, "Ana", "Hola")], "[FRAME 1]", "es", knowledge="### 2026-09-01: X (status)\n")
        self.assertNotIn("no longer exists", prompt)

    def test_a_new_summary_cannot_take_the_retired_type_and_is_told_what_replaces_it(self):
        with FakeGemini() as fake:
            with self.assertRaises(writer.SummaryError) as caught:
                self.summarise(fake, meeting_type="discovery")
        self.assertIn("'presale' or 'requirements'", str(caught.exception))
        self.assertEqual(fake.requests, [])


class LanguageControlTest(Workspace):
    """WI12-AC04: the language asked for wins over the meeting's, and a
    summary in the other language is not delivered."""

    def test_the_language_asked_for_is_the_one_requested_whatever_the_meeting(self):
        write_teams_docx(self.transcript, ENGLISH)
        with FakeGemini([returning(summary_text("es", "requirements"))]) as fake:
            result = self.summarise(fake, language="es", meeting_type="requirements")
        prompt = prompt_of(fake.requests[0])
        self.assertEqual(result.language, "es")
        self.assertIn("Write the summary in Spanish.", prompt)
        self.assertIn(writer.LANGUAGE_RULE.format(name="Spanish"), prompt)
        self.assertIn("## Proceso actual", prompt)
        self.assertIn("[00:00:04] Ann Parker: Good morning", prompt)

    def test_a_summary_in_the_other_language_is_retried_once_then_refused(self):
        # Spanish headings, English text: the headings alone would pass.
        english_body = summary_text("es").replace("Texto de", "This is the text of the")
        english_body = english_body.replace("- Juan manda el detalle el viernes", "- John sends it on Friday")
        english_body = english_body.replace("- El total supera lo esperado", "- The total is above what we expected")
        store.create_project(self.data, "Acme", "Acme SA")
        with FakeGemini([returning(english_body)] * 2) as fake:
            with self.assertRaises(writer.SummaryError) as caught:
                self.summarise(fake, language="es", project="acme", title="T", date="2026-09-22")
        self.assertIn("not in Spanish", str(caught.exception))
        self.assertEqual(len(fake.requests), 2)
        self.assertFalse(self.output().exists())
        self.assertEqual(store.list_meetings(self.data, "acme"), [])

    def test_a_wrong_language_then_the_right_one_is_delivered(self):
        # English headings, Spanish text, then a summary wholly in English.
        spanish_body = summary_text("en").replace("The text of", "Texto de la sección").replace(
            "- John sends the detail on Friday", "- Juan manda el detalle el viernes").replace(
            "- The total is above what was expected", "- El total está por encima de lo esperado")
        with FakeGemini([returning(spanish_body), returning(summary_text("en"))]) as fake:
            result = self.summarise(fake, language="en")
        self.assertEqual(result.attempts, 2)
        self.assertEqual(self.output().read_text(encoding="utf-8").strip(), summary_text("en"))

    def test_one_section_in_the_other_language_is_refused_and_named(self):
        text = summary_text("es").replace(
            "Texto de Temas.", "The team said that it is the cost of the plant and that this is the topic.")
        with self.assertRaises(writer.SummaryError) as caught:
            writer.check_summary(answer(text), writer.required_headings("es"), "es")
        self.assertIn("the section 'Temas' is not in Spanish", str(caught.exception))

    def test_quotes_keep_their_language_and_do_not_count(self):
        quote = ('"We have to see the total of the column, it is what the board is asking for, and it is not '
                 'there yet" (tenemos que ver el total de la columna)')
        text = summary_text("es").replace("Texto de Temas.", f"Texto de Temas. Juan dijo: {quote}.")
        self.assertEqual(writer.check_summary(answer(text), writer.required_headings("es"), "es"), text)
        english = summary_text("en").replace("The text of Key topics.", 'The text of Key topics: «que el total de la '
                                             'columna es lo que pide el directorio y no está» (the total is missing).')
        self.assertEqual(writer.check_summary(answer(english), writer.required_headings("en"), "en"), english)

    def test_code_and_tables_of_labels_seen_on_screen_keep_their_language(self):
        """The review's F1: a query seen on screen, or a table of the labels
        of a Spanish spreadsheet, made a section look foreign."""
        query = ("```sql\nSELECT total FROM cost WHERE plant IS NOT NULL AND line = 'fillet' AND total IS NOT NULL\n"
                 "AND year = 2026 AND month IS NOT NULL AND this = that AND it = the\n```")
        text = summary_text("es", "technical").replace("Texto de Análisis visual técnico.",
                                                       f"Texto de Análisis visual técnico:\n\n{query}")
        self.assertEqual(writer.check_summary(answer(text), writer.required_headings("es", "technical"), "es"), text)
        table = ("| Frame | Label on screen | Value |\n| --- | --- | --- |\n"
                 "| 1 | Costo de la planta de proceso y de la línea | 1.250 |\n"
                 "| 2 | Total de la columna de gastos y de los fletes para la planta | 3.400 |")
        english = summary_text("en").replace("The text of What was on screen.", f"The text of What was on screen:\n\n{table}")
        self.assertEqual(writer.check_summary(answer(english), writer.required_headings("en"), "en"), english)

    def test_a_section_whose_prose_is_in_the_other_language_is_still_refused_next_to_a_table(self):
        table = "| Frame | Value |\n| --- | --- |\n| 1 | 1.250 |"
        text = summary_text("es").replace(
            "Texto de Temas.", f"{table}\n\nThe team said that it is the cost of the plant and that this is the topic.")
        with self.assertRaises(writer.SummaryError) as caught:
            writer.check_summary(answer(text), writer.required_headings("es"), "es")
        self.assertIn("the section 'Temas' is not in Spanish", str(caught.exception))

    def test_a_few_words_of_the_other_language_in_a_section_are_not_judged(self):
        # Six common Spanish words, none English: below the threshold of eight.
        text = summary_text("en").replace("The text of Key topics.", "Costo de la planta y de la línea de proceso.")
        self.assertEqual(writer.check_summary(answer(text), writer.required_headings("en"), "en"), text)

    def test_the_default_is_still_the_transcripts_language(self):
        write_teams_docx(self.transcript, ENGLISH)
        with FakeGemini([returning(summary_text("en", "presale"))]) as fake:
            self.assertEqual(self.summarise(fake, meeting_type="presale").language, "en")
        self.assertIn("## Client problems", prompt_of(fake.requests[0]))


class KeyAndBudgetWithTypesTest(Workspace):
    """WI12-AC05: the key never appears and the same budget applies, with a
    type and a language."""

    def test_the_key_never_appears_with_a_type_and_a_language(self):
        outputs = []
        spanish_body = summary_text("en", "requirements").replace("The text of", "Texto de la sección")
        scripts = ([returning(summary_text("en", "requirements"))], [returning(spanish_body)] * 2)
        for script in scripts:
            stdout, stderr = io.StringIO(), io.StringIO()
            with FakeGemini(script) as fake, contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                code = main(["--frames", str(self.frames), "--transcript", str(self.transcript), "--type",
                             "requirements", "--language", "en"],
                            read_key=lambda: KEY, endpoint=fake.endpoint, sleep=self.sleeps.append)
            outputs.append((code, stdout.getvalue() + stderr.getvalue()))
            self.assertNotIn(KEY, json.dumps(fake.requests[0]["body"]) + fake.requests[0]["path"])
        self.assertEqual([code for code, _ in outputs], [0, 2])
        self.assertIn("not in English", outputs[1][1])
        for _, text in outputs:
            self.assertNotIn(KEY, text)
        for path in self.frames.iterdir():
            self.assertNotIn(KEY, path.read_text(encoding="utf-8"))

    def test_a_typed_request_that_could_go_over_the_budget_is_not_sent(self):
        with FakeGemini() as fake:
            with self.assertRaises(gemini.ReadingError) as caught:
                self.summarise(fake, meeting_type="negotiation", language="en", max_cost_usd=0.05)
        self.assertIn("budget of US$0.05", str(caught.exception))
        self.assertEqual(fake.requests, [])


class NamedFramesTest(Workspace):
    """WI12-AC08, found by the real run: the English summary named a frame
    that does not exist, the number of one frame with the minute of the one
    before, and the report refused it. A summary is now delivered only if the
    report could embed every frame it names. INGOL D-181 (WI13) adds the
    owner's rule for which frames to name, and refuses a range."""

    def setUp(self):
        super().setUp()
        for name in ("frame_001_t00-01-22.jpg", "frame_002_t00-05-00.jpg"):
            (self.frames / name).write_bytes(b"")

    def with_frames(self, mention):
        return summary_text().replace("Texto de Lo que se vio en pantalla.",
                                      f"Texto de Lo que se vio en pantalla: {mention}, con el total de la columna.")

    def test_a_summary_naming_frames_that_exist_is_delivered(self):
        text = self.with_frames("[frame_001_t00-01-22.jpg] y [frame_002_t00-05-00.jpg]")
        with FakeGemini([returning(text)]) as fake:
            self.summarise(fake)
        self.assertEqual(self.output().read_text(encoding="utf-8").strip(), text)

    def test_a_frame_that_is_not_in_the_folder_is_retried_once_then_refused(self):
        # The real case: frame 002's number with frame 001's minute.
        text = self.with_frames("[frame_002_t00-01-22.jpg]")
        with FakeGemini([returning(text)] * 2) as fake:
            with self.assertRaises(writer.SummaryError) as caught:
                self.summarise(fake)
        self.assertIn("not in the frames folder: frame_002_t00-01-22.jpg", str(caught.exception))
        self.assertEqual(len(fake.requests), 2)
        self.assertFalse(self.output().exists())

    def test_a_frame_mentioned_without_its_file_name_is_refused(self):
        for mention in ("(frame_001, t00:01:22)", "[frames_001-002]", "frame_001_t00-01-22.jpg"):
            with self.subTest(mention=mention):
                with self.assertRaises(writer.SummaryError) as caught:
                    writer.check_summary(answer(self.with_frames(mention)), writer.required_headings("es"), "es",
                                         {"frame_001_t00-01-22.jpg"})
                self.assertIn("without its file name in square brackets", str(caught.exception))

    def test_a_wrong_frame_then_a_right_one_is_delivered(self):
        with FakeGemini([returning(self.with_frames("[frame_003_t00-09-00.jpg]")),
                         returning(self.with_frames("[frame_001_t00-01-22.jpg]"))]) as fake:
            self.assertEqual(self.summarise(fake).attempts, 2)

    def test_the_summary_and_the_report_agree_on_every_case(self):
        from meetingtool.report import document
        cases = ["[frame_001_t00-01-22.jpg]", "[frame_002_t00-01-22.jpg]", "(frame_001, t00:01:22)",
                 "[frame_001_t00-01-22.jpg] y [frame_002_t00-05-00.jpg]", "sin imágenes"] + RANGES + NOT_RANGES
        names = {path.name for path in gemini.frame_files(self.frames)}
        for mention in cases:
            with self.subTest(mention=mention):
                text = self.with_frames(mention)
                try:
                    writer.check_frames(text, names)
                    summary_accepts = True
                except writer.SummaryError:
                    summary_accepts = False
                try:
                    document.cited_frames(text, self.frames)
                    report_accepts = True
                except document.ReportError:
                    report_accepts = False
                self.assertEqual(summary_accepts, report_accepts)

    # INGOL D-181: every frame the summary names goes into the Word report,
    # so the request says which screens are worth naming, and two frames
    # named as a range (the report showed their two ends, which nobody
    # chose) are refused like a missing frame.

    def test_every_request_carries_the_owners_rule_before_the_sections(self):
        for language in writer.SECTIONS:
            for meeting_type in (None,) + tuple(writer.MEETING_TYPES):
                with self.subTest(language=language, meeting_type=meeting_type):
                    prompt = writer.build_prompt(read_turns(self.transcript), "[FRAME 1]", language, meeting_type)
                    self.assertEqual(prompt.count(writer.FRAME_RULE), 1)
                    self.assertLess(prompt.index(writer.FRAME_RULE),
                                    prompt.index(f"## {writer.SECTIONS[language][0]}"))
                    screen = guide_in(prompt, writer.SECTIONS[language][4])
                    self.assertIn("rule for frames", screen)
                    self.assertNotIn("For each relevant frame", screen)

    def test_the_rule_says_what_the_owner_asked(self):
        rule = " ".join(writer.FRAME_RULE.split())
        for words in ("write down by hand", "the reason the screen was shared", "a file explorer, email, a calendar",
                      "a transition between two views", "rows or areas without data",
                      "one frame for each distinct thing shown", "column and row headings visible",
                      "never a range of frames"):
            self.assertIn(words, rule)

    def test_the_request_sent_carries_the_rule(self):
        with FakeGemini([returning(summary_text())]) as fake:
            self.summarise(fake)
        self.assertIn(writer.FRAME_RULE, prompt_of(fake.requests[0]))

    def test_a_range_is_retried_once_then_refused_and_nothing_is_written(self):
        with FakeGemini([returning(self.with_frames(RANGES[0]))] * 2) as fake:
            with self.assertRaises(writer.SummaryError) as caught:
                self.summarise(fake)
        self.assertIn("a range of frames instead of each frame on its own", str(caught.exception))
        self.assertEqual(len(fake.requests), 2)
        self.assertFalse(self.output().exists())

    def test_every_way_of_writing_a_range_is_refused_and_two_frames_are_not_a_range(self):
        names = {"frame_001_t00-01-22.jpg", "frame_002_t00-05-00.jpg"}
        for mention in RANGES:
            with self.subTest(mention=mention):
                with self.assertRaises(writer.SummaryError):
                    writer.check_frames(self.with_frames(mention), names)
        for mention in NOT_RANGES:
            with self.subTest(mention=mention):
                writer.check_frames(self.with_frames(mention), names)

    def test_a_retry_stopped_by_the_budget_says_why_the_answer_before_was_refused(self):
        # D-181's real run: the first answer was refused and the retry did not
        # fit the budget, and the stop did not say what was refused.
        prompt = writer.build_prompt(read_turns(self.transcript), (self.frames / gemini.OUTPUT_NAME).read_text(
            encoding="utf-8"), "es")
        worst = gemini.token_cost(len(prompt) / writer.CHARS_PER_TOKEN, writer.MAX_OUTPUT_TOKENS)
        with FakeGemini([returning(self.with_frames(RANGES[0]))] * 2) as fake:
            with self.assertRaises(gemini.ReadingError) as caught:
                self.summarise(fake, max_cost_usd=worst + gemini.token_cost(30000, 5000) / 2)
        self.assertEqual(len(fake.requests), 1)
        self.assertIn("stopped before sending the summary", str(caught.exception))
        self.assertIn("the answer before was refused: the summary names a range of frames", str(caught.exception))
        self.assertFalse(self.output().exists())

    def test_a_range_then_each_frame_on_its_own_is_delivered(self):
        text = self.with_frames(NOT_RANGES[1])
        with FakeGemini([returning(self.with_frames(RANGES[0])), returning(text)]) as fake:
            self.assertEqual(self.summarise(fake).attempts, 2)
        self.assertEqual(self.output().read_text(encoding="utf-8").strip(), text)


# Written as the real summaries of INGOL D-178 wrote them, and in the other
# ways a range is said in Spanish and English.
RANGES = ["`[frame_001_t00-01-22.jpg]` a `[frame_002_t00-05-00.jpg]`",
          "[frame_001_t00-01-22.jpg] – [frame_002_t00-05-00.jpg]",
          "[frame_001_t00-01-22.jpg]-[frame_002_t00-05-00.jpg]",
          "desde [frame_001_t00-01-22.jpg] hasta [frame_002_t00-05-00.jpg]",
          "entre [frame_001_t00-01-22.jpg] y [frame_002_t00-05-00.jpg]",
          "[frame_001_t00-01-22.jpg] to [frame_002_t00-05-00.jpg]",
          "[frame_001_t00-01-22.jpg] through the [frame_002_t00-05-00.jpg]",
          "[frame_001_t00-01-22.jpg] … [frame_002_t00-05-00.jpg]",
          # Found by the independent review (P2-1): bold names and arrows got through.
          "**[frame_001_t00-01-22.jpg]** a **[frame_002_t00-05-00.jpg]**",
          "[frame_001_t00-01-22.jpg] -> [frame_002_t00-05-00.jpg]",
          "[frame_001_t00-01-22.jpg] → [frame_002_t00-05-00.jpg]",
          "[frame_001_t00-01-22.jpg] -- [frame_002_t00-05-00.jpg]"]
NOT_RANGES = ["[frame_001_t00-01-22.jpg] y [frame_002_t00-05-00.jpg]",
              "[frame_001_t00-01-22.jpg], la tabla; y [frame_002_t00-05-00.jpg], el total",
              "[frame_001_t00-01-22.jpg] and [frame_002_t00-05-00.jpg]",
              "[frame_001_t00-01-22.jpg] a la derecha del total",
              "**[frame_001_t00-01-22.jpg]** y **[frame_002_t00-05-00.jpg]**",
              "| [frame_001_t00-01-22.jpg] | - | [frame_002_t00-05-00.jpg] |"]


if __name__ == "__main__":
    unittest.main()
