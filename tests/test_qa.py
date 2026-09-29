"""Tests for the question-and-answer register (meetingtool.summary.qa, WI14).
Gemini is the fake on localhost from test_reading: no test reaches the
network. Transcripts, frames and registers are invented at test time in a
temporary folder."""

import contextlib
import copy
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import docx
from PIL import Image

from meetingtool.reading import gemini
from meetingtool.report import document
from meetingtool.summary import qa, writer
from meetingtool.summary.__main__ import main
from tests.test_frames import write_teams_docx
from tests.test_reading import KEY, FakeGemini, answer_for
from tests.test_summary import answer

SPANISH = [("Ana Pérez", "0:04", "Buen día. Primera duda: ¿quién carga los estándares de horas por kilo en la planilla?"),
           ("Juan Gómez", "0:40", "Los carga el área de procesos una vez por mes, con la fuente del sistema de planta."),
           ("Ana Pérez", "2:10", "Segunda duda: ¿cómo viaja el costo del semielaborado entre las plantas?"),
           ("Juan Gómez", "2:30", "Te muestro la planilla, ¿están viendo? El costo viaja por kilo con la tarifa de "
                                  "cada etapa."),
           ("Ana Pérez", "5:00", "Perfecto. Queda acordado: Juan manda el detalle el 25 de septiembre."),
           ("Juan Gómez", "5:30", "Dale, lo mando. Gracias a todos, chau.")]
ENGLISH = [("Ann Parker", "0:04", "Good morning. First doubt: who loads the hours per kilo standards in the sheet?"),
           ("John Green", "0:40", "The processing team loads them once a month, from the plant system."),
           ("Ann Parker", "2:10", "Second doubt: how does the cost of the semi-finished product travel between plants?"),
           ("John Green", "2:30", "Let me show you the sheet, can you see it? The cost travels per kilo with the rate "
                                  "of each stage."),
           ("Ann Parker", "5:00", "Great. Agreed: John sends the detail on September 25."),
           ("John Green", "5:30", "Sure, I will send it. Thanks everybody, bye.")]
# 0:10 is on screen when the second answer begins (2:10); 2:20 is kept during
# it; 4:00 and 6:00 are after it.
FRAMES = {"frame_001_t00-00-10.jpg": (200, 30, 30), "frame_002_t00-02-20.jpg": (30, 30, 200),
          "frame_003_t00-04-00.jpg": (30, 160, 30), "frame_004_t00-06-00.jpg": (90, 90, 90)}

REGISTER = {"questions": [
    {"question": "¿Quién carga los estándares de horas por kilo en la planilla?", "asked_by": "Ana Pérez",
     "start": "0:00:04", "end": "0:00:40",
     "answers": [{"speaker": "Juan Gómez", "text": "Los carga el área de procesos una vez por mes, con la fuente "
                                                   "del sistema de la planta."}],
     "quote": "Los carga el área de procesos una vez por mes", "agreement": "", "pending": "", "deadline": "",
     "status": "resolved", "screen": False, "screen_quote": ""},
    {"question": "¿Cómo viaja el costo del semielaborado entre las plantas?", "asked_by": "Ana Pérez",
     "start": "0:02:10", "end": "0:02:30",
     "answers": [{"speaker": "Juan Gómez", "text": "El costo viaja por kilo con la tarifa de cada etapa."}],
     "quote": "El costo viaja por kilo con la tarifa de cada etapa", "agreement": "Juan manda el detalle.",
     "pending": "Juan manda el detalle del costo por etapa.", "deadline": "el 25 de septiembre",
     "status": "resolved_with_caveat", "screen": True, "screen_quote": "Te muestro la planilla"}],
    "knowledge": {"rules": ["El costo viaja por kilo con la tarifa de cada etapa."],
                  "owners": ["El área de procesos carga los estándares de horas por kilo."],
                  "figures": [], "glossary": [], "scope": []}}
REGISTER_EN = {"questions": [
    {"question": "Who loads the hours per kilo standards in the sheet?", "asked_by": "Ann Parker",
     "start": "0:00:04", "end": "0:00:40",
     "answers": [{"speaker": "John Green", "text": "The processing team loads them once a month, from the plant "
                                                   "system."}],
     "quote": "The processing team loads them once a month", "agreement": "", "pending": "", "deadline": "",
     "status": "resolved", "screen": False, "screen_quote": ""},
    {"question": "How does the cost of the semi-finished product travel between the plants?",
     "asked_by": "Ann Parker", "start": "0:02:10", "end": "0:02:30",
     "answers": [{"speaker": "John Green", "text": "The cost travels per kilo with the rate of each stage."}],
     "quote": "The cost travels per kilo with the rate of each stage", "agreement": "John sends the detail.",
     "pending": "John sends the detail of the cost of each stage.", "deadline": "on September 25",
     "status": "resolved_with_caveat", "screen": True, "screen_quote": "Let me show you the sheet"}],
    "knowledge": {"rules": ["The cost travels per kilo with the rate of each stage."], "owners": [], "figures": [],
                  "glossary": [], "scope": []}}
SEEN = {"answers": [{"id": "P2", "seen": "La planilla muestra la tarifa por kilo de cada etapa del proceso.",
                     "frames": ["frame_002_t00-02-20.jpg"]}]}
SEEN_EN = {"answers": [{"id": "Q2", "seen": "The sheet shows the rate per kilo of each stage of the process.",
                        "frames": ["frame_002_t00-02-20.jpg"]}]}


def json_answer(data, finish="STOP"):
    return lambda first, count: answer(data if isinstance(data, str) else json.dumps(data, ensure_ascii=False), finish)


def reading(first, count):
    return answer_for(first, count)


def changed(register=REGISTER, number=None, **fields):
    """A copy of the register with fields of question `number` (1-based)
    changed, or of the whole object without a number."""
    data = copy.deepcopy(register)
    target = data if number is None else data["questions"][number - 1]
    target.update(fields)
    return data


def verbal(register=REGISTER):
    data = copy.deepcopy(register)
    for question in data["questions"]:
        question["screen"], question["screen_quote"] = False, ""
    return data


class Workspace(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.frames = self.tmp / "frames-out"
        self.frames.mkdir()
        for name, colour in FRAMES.items():
            Image.new("RGB", (320, 180), colour).save(self.frames / name)
        self.transcript = self.tmp / "meeting.docx"
        write_teams_docx(self.transcript, SPANISH)
        self.english = self.tmp / "meeting-en.docx"
        write_teams_docx(self.english, ENGLISH)
        self.data = self.tmp / "data"
        self.sleeps = []

    def tearDown(self):
        self._tmp.cleanup()

    def register(self, fake, transcript=None, **kwargs):
        return qa.write_register(self.frames, transcript or self.transcript, KEY, endpoint=fake.endpoint,
                                 sleep=self.sleeps.append, data_dir=self.data, **kwargs)

    def output(self):
        return self.frames / writer.OUTPUT_NAME

    def text(self):
        return self.output().read_text(encoding="utf-8")

    def assertNothingWritten(self):
        for name in (writer.OUTPUT_NAME, qa.REGISTER_NAME, qa.READING_NAME):
            self.assertFalse((self.frames / name).exists(), name)

    def image_requests(self, fake):
        return [request for request in fake.requests if request["images"]]


class RequestTest(Workspace):
    def test_the_first_request_is_the_transcript_alone_with_no_list_and_asks_for_json(self):
        with FakeGemini([json_answer(verbal())]) as fake:
            self.register(fake, language="es")
        body = fake.requests[0]["body"]
        prompt = body["contents"][0]["parts"][0]["text"]
        self.assertEqual(len(body["contents"][0]["parts"]), 1)
        self.assertEqual(body["generationConfig"]["responseMimeType"], "application/json")
        self.assertIn("nobody gives you a list", prompt)
        self.assertIn("[00:02:10] Ana Pérez: Segunda duda", prompt)
        self.assertNotIn("WHAT WAS READ IN EACH FRAME", prompt)
        self.assertIn("Write the register in Spanish.", prompt)
        for field in ('"asked_by"', '"answers"', '"quote"', '"agreement"', '"pending"', '"deadline"', '"status"',
                      '"screen"', '"screen_quote"', '"knowledge"'):
            self.assertIn(field, prompt)
        self.assertIn("never shorten an answer to one line", prompt)
        self.assertIn("Never write a date that was not said", prompt)
        self.assertIn("job title", prompt)
        self.assertIn("farewell", prompt)

    def test_every_meeting_type_and_both_languages_deliver_a_register(self):
        for language, transcript, register in (("es", None, REGISTER), ("en", "en", REGISTER_EN)):
            for meeting_type in [None, *writer.MEETING_TYPES]:
                with self.subTest(language=language, meeting_type=meeting_type):
                    self.output().unlink(missing_ok=True)
                    with FakeGemini([json_answer(verbal(register))]) as fake:
                        result = self.register(fake, self.english if transcript else None, language=language,
                                               meeting_type=meeting_type)
                    prompt = fake.requests[0]["body"]["contents"][0]["parts"][0]["text"]
                    stance = writer.MEETING_TYPES[meeting_type].stance if meeting_type else ""
                    if stance:
                        self.assertIn(f"MEETING TYPE: {meeting_type}. {stance}", prompt)
                    else:
                        self.assertNotIn("MEETING TYPE:", prompt)
                    self.assertIn(f"Write the register in {writer.LANGUAGE_NAMES[language]}.", prompt)
                    self.assertEqual(result.questions, 2)
                    self.assertTrue(self.text().startswith(f"## {qa.LABELS[language]['questions']}\n"))

    def test_a_retired_or_unknown_type_is_refused_before_any_request(self):
        with FakeGemini() as fake:
            for meeting_type in ("discovery", "brainstorm"):
                with self.assertRaises(qa.QAError):
                    self.register(fake, meeting_type=meeting_type)
        self.assertEqual(fake.requests, [])

    def test_without_the_option_the_summary_is_written_as_before(self):
        (self.frames / gemini.OUTPUT_NAME).write_text("# What each frame shows\n\n[FRAME 1]\n- Key Data: 1\n",
                                                     encoding="utf-8")
        from tests.test_summary import summary_text
        with FakeGemini([lambda first, count: answer(summary_text())]) as fake, \
                contextlib.redirect_stdout(io.StringIO()):
            code = main(["--frames", str(self.frames), "--transcript", str(self.transcript), "--language", "es"],
                        read_key=lambda: KEY, endpoint=fake.endpoint, sleep=self.sleeps.append)
        self.assertEqual(code, 0)
        self.assertEqual(len(fake.requests), 1)
        self.assertNotIn("responseMimeType", fake.requests[0]["body"]["generationConfig"])
        self.assertIn("WHAT WAS READ IN EACH FRAME", fake.requests[0]["body"]["contents"][0]["parts"][0]["text"])
        self.assertFalse((self.frames / qa.REGISTER_NAME).exists())


class RegisterTest(Workspace):
    def run_spanish(self):
        with FakeGemini([json_answer(REGISTER), reading, json_answer(SEEN)]) as fake:
            result = self.register(fake, language="es")
        return fake, result

    def test_the_register_is_question_by_question_with_every_field(self):
        _, result = self.run_spanish()
        text = self.text()
        self.assertEqual(result.questions, 2)
        self.assertIn("| P1 | ¿Quién carga los estándares de horas por kilo en la planilla? | 0:04 | Resuelta |", text)
        self.assertIn("### P1 · ¿Quién carga los estándares de horas por kilo en la planilla?", text)
        self.assertIn("### P2 · ¿Cómo viaja el costo del semielaborado entre las plantas?", text)
        self.assertIn("- **Planteó:** Ana Pérez", text)
        self.assertIn("- **Minuto:** 2:10 a 2:30", text)
        self.assertIn("- **Estado:** Resuelta con salvedad", text)
        self.assertIn("  - **Juan Gómez:** El costo viaja por kilo con la tarifa de cada etapa.", text)
        self.assertIn("- **Acuerdo:** Juan manda el detalle.", text)
        self.assertIn("- **Pendiente:** Juan manda el detalle del costo por etapa.", text)
        self.assertIn("- **Plazo:** el 25 de septiembre", text)
        self.assertIn("- **Apoyo:** sólo verbal", text)
        self.assertIn("- **Apoyo:** con pantalla: «Te muestro la planilla»", text)
        self.assertIn("- **Lo visto en pantalla:** La planilla muestra la tarifa por kilo", text)
        self.assertIn("  - [frame_002_t00-02-20.jpg]", text)
        self.assertIn("## Conocimiento del proyecto", text)
        self.assertIn("### Reglas acordadas\n\n- El costo viaja por kilo", text)
        self.assertIn("### Cifras dichas\n\nNada de esto se dijo en la reunión.", text)
        self.assertIn("## Pendientes\n\n| Pendiente | Pregunta | Plazo |", text)
        self.assertIn("| Juan manda el detalle del costo por etapa. | P2 | el 25 de septiembre |", text)
        self.assertEqual(text.count("[frame_"), 1)
        record = json.loads((self.frames / qa.REGISTER_NAME).read_text(encoding="utf-8"))
        self.assertEqual([q["id"] for q in record["questions"]], ["P1", "P2"])

    def test_the_register_is_in_english_when_asked(self):
        with FakeGemini([json_answer(REGISTER_EN), reading, json_answer(SEEN_EN)]) as fake:
            self.register(fake, self.english, language="en")
        text = self.text()
        self.assertIn("### Q2 · How does the cost", text)
        self.assertIn("- **Status:** Resolved with a caveat", text)
        self.assertIn("- **Support:** on screen: «Let me show you the sheet»", text)
        self.assertIn("- **Seen on screen:** The sheet shows", text)
        self.assertIn("## Project knowledge", text)

    def test_no_deadline_said_is_written_as_such(self):
        with FakeGemini([json_answer(changed(verbal(), 2, deadline=""))]) as fake:
            self.register(fake, language="es")
        self.assertIn("- **Plazo:** sin fecha dicha", self.text())
        self.assertIn("| P2 | sin fecha dicha |", self.text())

    def test_a_meeting_with_a_project_adds_the_register_to_it(self):
        from meetingtool.projects import store
        project = store.create_project(self.data, "Planta", "Cliente")["id"]
        with FakeGemini([json_answer(verbal())]) as fake:
            result = self.register(fake, language="es", project=project, title="Dudas", date="2026-09-25")
        [meeting] = store.list_meetings(self.data, project)
        self.assertEqual(meeting["id"], result.meeting_id)
        self.assertEqual(meeting["key_points"], ["Juan manda el detalle."])
        self.assertEqual(meeting["summary"], "Preguntas y respuestas: 2 (1 resuelta, 1 resuelta con salvedad, "
                                             "0 pendiente, 0 fuera de alcance).")


class ChecksTest(Workspace):
    """Each check: a register breaking only it is retried once and then
    refused, and nothing is written."""

    def assertRefused(self, broken, message, register=None, script=None):
        with FakeGemini(script or [json_answer(broken), json_answer(broken)]) as fake:
            with self.assertRaises(qa.QAError) as caught:
                self.register(fake, language="es")
        self.assertIn(message, str(caught.exception))
        self.assertNothingWritten()
        return fake

    def test_a_fragment_not_in_the_transcript_is_refused(self):
        fake = self.assertRefused(changed(verbal(), 1, quote="Los carga el área de ventas una vez por mes"),
                                  "question 1: its verbatim fragment is not in the transcript")
        self.assertEqual(len(fake.requests), 2)

    def test_a_fragment_too_short_is_refused(self):
        self.assertRefused(changed(verbal(), 1, quote="Los carga"), "its verbatim fragment is not in the transcript")

    def test_an_answer_given_to_someone_who_did_not_speak_is_refused(self):
        broken = changed(verbal(), 2, answers=[{"speaker": "Pedro Ruiz", "text": "El costo viaja por kilo."}])
        self.assertRefused(broken, "question 2: the answer is given to 'Pedro Ruiz', who did not speak")

    def test_a_question_raised_by_someone_who_did_not_speak_is_refused(self):
        self.assertRefused(changed(verbal(), 1, asked_by="Pedro Ruiz"), "raised by 'Pedro Ruiz', who did not speak")

    def test_a_minute_after_the_meeting_is_refused(self):
        self.assertRefused(changed(verbal(), 2, end="0:09:00"), "question 2: minute 9:00 is after the meeting")

    def test_an_answer_ending_before_it_starts_is_refused(self):
        self.assertRefused(changed(verbal(), 2, end="0:01:00"), "its answer ends (1:00) before it starts (2:10)")

    def test_a_minute_that_is_not_a_minute_is_refused(self):
        self.assertRefused(changed(verbal(), 1, start="al principio"), "its minutes are not H:MM:SS")

    def test_a_status_that_is_not_one_of_the_four_is_refused(self):
        self.assertRefused(changed(verbal(), 1, status="answered"), "status 'answered' is not one of")

    def test_no_answer_is_only_for_a_pending_question(self):
        self.assertRefused(changed(verbal(), 1, answers=[]), "no answer, and yet its status is resolved")

    def test_a_date_the_transcript_does_not_say_is_refused(self):
        for field, value in (("deadline", "el 30 de septiembre"), ("pending", "Juan manda el detalle el 30/09."),
                             ("agreement", "Se revisa el 2026-10-02.")):
            with self.subTest(field=field):
                self.assertRefused(changed(verbal(), 2, **{field: value}),
                                   "question 2 writes a date the transcript does not say")

    def test_an_invented_date_in_an_answer_or_the_knowledge_is_refused(self):
        broken = changed(verbal(), 2, answers=[{"speaker": "Juan Gómez", "text": "Se manda el 3 de octubre."}])
        self.assertRefused(broken, "question 2 writes a date the transcript does not say (3/10)")
        broken = changed(verbal(), knowledge=dict(REGISTER["knowledge"], scope=["Se entrega el 1 de octubre."]))
        self.assertRefused(broken, "the knowledge 'scope' writes a date the transcript does not say")

    def test_a_date_the_transcript_says_is_accepted_whatever_its_writing(self):
        for value in ("el 25 de septiembre", "el 25/09", "el 2026-09-25", "September 25th"):
            with self.subTest(value=value):
                self.output().unlink(missing_ok=True)
                with FakeGemini([json_answer(changed(verbal(), 2, deadline=value))]) as fake:
                    self.register(fake, language="es")
                self.assertTrue(self.output().exists())

    def test_on_screen_without_the_words_that_show_it_is_refused(self):
        for value in ("", "Ahora lo comparto en pantalla"):
            with self.subTest(screen_quote=value):
                self.assertRefused(changed(REGISTER, 2, screen_quote=value),
                                   "question 2 is marked on screen, but the words that show it are not")

    def test_screen_must_be_true_or_false(self):
        self.assertRefused(changed(verbal(), 1, screen="no"), "'screen' is not true or false")

    def test_an_answer_that_is_not_json_or_did_not_finish_is_refused(self):
        self.assertRefused(None, "is not JSON", script=[json_answer("## Resumen"), json_answer("## Resumen")])
        self.assertRefused(None, "did not finish normally",
                           script=[json_answer(verbal(), "MAX_TOKENS"), json_answer(verbal(), "MAX_TOKENS")])

    def test_a_register_in_the_other_language_is_refused(self):
        # Quotes and names as in the Spanish transcript; everything written, in English.
        english = verbal()
        for spanish, translated in zip(english["questions"], REGISTER_EN["questions"]):
            spanish["question"] = translated["question"]
            spanish["answers"] = [dict(point, text=text["text"])
                                  for point, text in zip(spanish["answers"], translated["answers"])]
            spanish["agreement"], spanish["pending"] = translated["agreement"], translated["pending"]
            spanish["deadline"] = ""
        english["knowledge"] = REGISTER_EN["knowledge"]
        self.assertRefused(english, "is not in Spanish")

    def test_a_register_mentioning_a_frame_is_refused(self):
        self.assertRefused(changed(verbal(), 1, agreement="Ver frame_002 de la planilla."), "mentions a frame")

    def test_a_refused_register_is_retried_once_and_a_good_one_is_delivered(self):
        broken = changed(verbal(), 1, quote="nada de esto se dijo en la reunión")
        with FakeGemini([json_answer(broken), json_answer(verbal())]) as fake:
            result = self.register(fake, language="es")
        self.assertEqual(len(fake.requests), 2)
        self.assertEqual(result.questions, 2)

    def test_what_was_seen_outside_the_span_or_for_a_verbal_answer_is_refused(self):
        cases = ((dict(frames=["frame_003_t00-04-00.jpg"]), "P2: frame(s) outside its span or not read"),
                 (dict(id="P1"), "is given to 'P1', which is not an answer on screen"),
                 (dict(seen="Se ve [frame_002_t00-02-20.jpg] con la tarifa por kilo."), "what was seen names a frame"),
                 (dict(seen=""), "P2: nothing is said of what was seen"))
        for fields, message in cases:
            with self.subTest(fields=fields):
                broken = {"answers": [dict(SEEN["answers"][0], **fields)]}
                self.assertRefused(None, message, script=[json_answer(REGISTER), reading, json_answer(broken),
                                                          json_answer(broken)])
        self.assertRefused(None, "what was seen on screen is missing for P2",
                           script=[json_answer(REGISTER), reading, json_answer({"answers": []}),
                                   json_answer({"answers": []})])


SPLIT = [(0, 130), (130, float("inf"))]


class BatchesTest(Workspace):
    def test_a_transcript_is_split_only_when_long_at_a_turn_near_the_middle_of_its_text(self):
        turns = [(0, "A", "x" * 10), (60, "B", "x" * 10), (120, "A", "x" * 10), (180, "B", "x" * 10)]
        self.assertEqual(qa.batches(turns), [(0, float("inf"))])
        with mock.patch.object(qa, "SPLIT_CHARS", 30):
            self.assertEqual(qa.batches(turns), [(0, 120), (120, float("inf"))])

    def test_a_long_transcript_is_asked_in_two_batches_and_the_register_joined(self):
        first = {"questions": [REGISTER["questions"][0]], "knowledge": {}}
        second = {"questions": [changed(verbal(), 2)["questions"][1]], "knowledge": REGISTER["knowledge"]}
        with mock.patch.object(qa, "batches", return_value=SPLIT), \
                FakeGemini([json_answer(first), json_answer(second)]) as fake:
            result = self.register(fake, language="es")
        prompts = [request["body"]["contents"][0]["parts"][0]["text"] for request in fake.requests]
        self.assertEqual(len(prompts), 2)
        self.assertIn("This request is part 1 of 2: register only the questions raised from 00:00:00 up to 00:02:10",
                      prompts[0])
        self.assertIn('Leave "knowledge" with empty lists', prompts[0])
        self.assertIn("part 2 of 2: register only the questions raised from 00:02:10 up to the end", prompts[1])
        self.assertIn('Also fill "knowledge"', prompts[1])
        self.assertEqual(result.questions, 2)
        self.assertIn("### P2 · ", self.text())
        self.assertIn("### Reglas acordadas\n\n- El costo viaja", self.text())

    def test_a_question_outside_its_batch_is_refused(self):
        with mock.patch.object(qa, "batches", return_value=SPLIT), \
                FakeGemini([json_answer(verbal()), json_answer(verbal())]) as fake:
            with self.assertRaises(qa.QAError) as caught:
                self.register(fake, language="es")
        self.assertIn("question 2: raised at 2:10, outside the part of the meeting asked for", str(caught.exception))
        self.assertNothingWritten()


class ScreenTest(Workspace):
    def test_with_every_answer_verbal_no_frame_is_read(self):
        with FakeGemini([json_answer(verbal())]) as fake:
            result = self.register(fake, language="es")
        self.assertEqual(len(fake.requests), 1)
        self.assertEqual(self.image_requests(fake), [])
        self.assertEqual((result.frames_read, result.frames_total), (0, 4))
        self.assertFalse((self.frames / qa.READING_NAME).exists())
        self.assertNotIn("[frame_", self.text())

    def test_with_no_frames_an_answer_on_screen_has_no_image_and_nothing_is_read(self):
        for path in self.frames.glob("frame_*.jpg"):
            path.unlink()
        with FakeGemini([json_answer(REGISTER)]) as fake:
            result = self.register(fake, language="es")
        self.assertEqual(len(fake.requests), 1)
        self.assertEqual(result.frames_read, 0)
        self.assertIn("- **Lo visto en pantalla:** sin imagen disponible.", self.text())

    def test_only_the_frames_of_the_span_of_an_answer_on_screen_are_read_once(self):
        with FakeGemini([json_answer(REGISTER), reading, json_answer(SEEN)]) as fake:
            result = self.register(fake, language="es")
        sent = [label for request in self.image_requests(fake) for label in request["labels"]]
        self.assertEqual(sent, ["[FRAME 1] frame_001_t00-00-10.jpg", "[FRAME 2] frame_002_t00-02-20.jpg"])
        self.assertEqual((result.frames_read, result.on_screen), (2, (("P2", "2:10"),)))
        seen_prompt = fake.requests[2]["body"]["contents"][0]["parts"][0]["text"]
        self.assertIn("ANSWER P2 (2:10 to 2:30)", seen_prompt)
        self.assertIn(writer.FRAME_RULE, seen_prompt)
        self.assertNotIn("ANSWER P1", seen_prompt)
        self.assertNotIn("frame_003", seen_prompt)
        self.assertTrue((self.frames / qa.READING_NAME).exists())

    def test_frames_read_and_none_worth_naming(self):
        seen = {"answers": [dict(SEEN["answers"][0], seen="La pantalla sólo mostraba el explorador de archivos.",
                                 frames=[])]}
        with FakeGemini([json_answer(REGISTER), reading, json_answer(seen)]) as fake:
            self.register(fake, language="es")
        self.assertIn("- **Lo visto en pantalla:** La pantalla sólo mostraba el explorador", self.text())
        self.assertNotIn("[frame_", self.text())

    def test_the_span_holds_the_frame_on_screen_when_the_answer_began(self):
        frames = [Path(name) for name in FRAMES]
        self.assertEqual([p.name for p in qa.span_frames(frames, 130, 150)],
                         ["frame_001_t00-00-10.jpg", "frame_002_t00-02-20.jpg"])
        first = frames[:1]
        self.assertEqual([p.name for p in qa.span_frames(first, 10 + qa.LEAD, 10 + qa.LEAD + 2)],
                         ["frame_001_t00-00-10.jpg"])
        self.assertEqual([p.name for p in qa.span_frames(first, 10 + qa.LEAD + 1, 10 + qa.LEAD + 2)], [])
        self.assertEqual([p.name for p in qa.span_frames(frames, 240, 360)],
                         ["frame_002_t00-02-20.jpg", "frame_003_t00-04-00.jpg", "frame_004_t00-06-00.jpg"])


class ReportTest(Workspace):
    def test_the_word_report_builds_from_the_register_with_only_the_frames_seen(self):
        with FakeGemini([json_answer(REGISTER), reading, json_answer(SEEN)]) as fake:
            self.register(fake, language="es")
        result = document.build_report(self.frames, title="Dudas", data_dir=self.data, neutral=True)
        self.assertEqual((result.images, result.language), (1, "es"))
        texts = [paragraph.text for paragraph in docx.Document(str(result.output)).paragraphs]
        self.assertIn("P1 · ¿Quién carga los estándares de horas por kilo en la planilla?", texts)
        self.assertIn("Conocimiento del proyecto", texts)
        self.assertIn("Imagen del minuto 2:20 de la reunión", texts)

    def test_the_english_report_is_in_english(self):
        with FakeGemini([json_answer(REGISTER_EN), reading, json_answer(SEEN_EN)]) as fake:
            self.register(fake, self.english, language="en")
        self.assertEqual(document.build_report(self.frames, data_dir=self.data, neutral=True).language, "en")


class CommandTest(Workspace):
    def test_the_command_prints_the_stages_and_the_answers_on_screen(self):
        out = io.StringIO()
        with FakeGemini([json_answer(REGISTER), reading, json_answer(SEEN)]) as fake, contextlib.redirect_stdout(out):
            code = main(["--frames", str(self.frames), "--transcript", str(self.transcript), "--format", "qa",
                         "--language", "es", "--type", "requirements"], read_key=lambda: KEY, endpoint=fake.endpoint,
                        sleep=self.sleeps.append)
        self.assertEqual(code, 0)
        printed = out.getvalue()
        self.assertIn("register written", printed)
        self.assertIn("2 question(s)", printed)
        self.assertIn("frames read: 2 of 4", printed)
        self.assertIn("on screen: P2 (2:10)", printed)
        self.assertIn("stage register 1/1: 1 attempt(s)", printed)
        self.assertIn("stage frames: 1 attempt(s)", printed)
        self.assertIn("stage seen on screen: 1 attempt(s)", printed)


class DatesTest(unittest.TestCase):
    def test_written_dates_are_read_whatever_their_writing(self):
        for text in ("el 25 de septiembre", "el 25/09", "25/09/2026", "2026-09-25", "September 25th", "25 of September",
                     "el 25 setiembre"):
            with self.subTest(text=text):
                self.assertEqual(qa.written_dates(text), {(25, 9)})

    def test_figures_minutes_and_months_alone_are_not_dates(self):
        for text in ("0,14 USD/kg", "1.250 kilos", "en abril", "1:22:57", "la próxima semana", "el viernes",
                     "aporte 2,40 %", "40/99"):
            with self.subTest(text=text):
                self.assertEqual(qa.written_dates(text), set())


if __name__ == "__main__":
    unittest.main()
