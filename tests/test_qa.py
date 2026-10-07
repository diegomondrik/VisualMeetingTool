"""Tests for the question-and-answer register (meetingtool.summary.qa, WI14).
Gemini is the fake on localhost from test_reading: no test reaches the
network. Transcripts, frames and registers are invented at test time in a
temporary folder."""

import contextlib
import copy
import io
import json
import shutil
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
from tests.test_frames import TIMED, write_teams_docx, write_timed_docx
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

    def register(self, fake, transcript=None, keep=False, **kwargs):
        # Each run starts without the batches kept by the one before, unless
        # the test is about them: the register's parts, and every paid answer
        # kept by its fingerprint (WI20).
        if not keep:
            shutil.rmtree(self.frames / qa.PARTS_DIR, ignore_errors=True)
            shutil.rmtree(self.frames / gemini.KEPT_DIR, ignore_errors=True)
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

    def test_a_transcript_with_no_speaker_is_refused_before_any_request_in_both_languages(self):
        """WI24-AC02: the register says who asked and who answered; a transcript that
        names no one cannot give it, and the refusal comes before anything is paid."""
        timed = self.tmp / "timed.docx"
        write_timed_docx(timed, TIMED)
        for source in (timed,):
            for language in ("es", "en"):
                with self.subTest(source=source.name, language=language), FakeGemini() as fake:
                    with self.assertRaises(qa.QAError) as caught:
                        self.register(fake, source, language=language)
                    self.assertEqual(fake.requests, [])
                    self.assertEqual(caught.exception.message.key, "qa.needs_speakers")
                    self.assertNothingWritten()
                    self.assertIn("names no speaker", str(caught.exception))
                    self.assertIn("write the summary instead", caught.exception.text("en"))
                    self.assertIn("no dice quién habla", caught.exception.text("es"))
                    self.assertIn("escribí el resumen", caught.exception.text("es"))
                    self.assertIn(str(source), caught.exception.text("es"))

    def test_a_text_with_timed_lines_and_names_is_written_as_in_main(self):
        """WI24's review, P1-1: "[HH:MM:SS] Name: text" names its speakers, and the register of such a file
        was written before WI24 (spoke() lets every name pass there): it still is."""
        bracketed = self.tmp / "bracketed.txt"
        bracketed.write_text("\n".join(f"[00:{clock.rjust(5, '0')}] {speaker}: {text}"
                                       for speaker, clock, text in SPANISH), encoding="utf-8")
        with FakeGemini([json_answer(verbal())]) as fake:
            result = self.register(fake, bracketed, language="es")
        self.assertEqual(len(fake.requests), 1)
        self.assertEqual(result.questions, 2)
        self.assertTrue(self.output().exists())

    def test_a_transcript_where_someone_is_named_is_not_refused_for_lack_of_speakers(self):
        # A time alone on its line inside a transcript that names speakers is words of the turn (WI24's review, P3-1).
        named = self.tmp / "named.txt"
        named.write_text("Ana Pérez   0:04\n¿Quién carga los estándares de horas por kilo en la planilla?\n"
                         "0:40\nLos carga el área de procesos una vez por mes.\n", encoding="utf-8")
        with FakeGemini([json_answer({"questions": [], "knowledge": REGISTER["knowledge"]})]) as fake:
            self.register(fake, named, language="es")
        self.assertEqual(len(fake.requests), 1)

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
        self.last_error = caught.exception
        return fake

    def test_a_fragment_not_in_the_transcript_is_refused(self):
        # Two words of ten changed: 80 % said, under the 85 % asked for.
        fake = self.assertRefused(changed(verbal(), 1, quote="Los carga el equipo de ventas una vez por mes"),
                                  "question 1: its verbatim fragment is not in the transcript")
        self.assertEqual(len(fake.requests), 2)

    def test_a_fragment_with_one_word_changed_in_thirteen_is_accepted(self):
        quote = "Los carga el área de procesos una vez al mes con la fuente del sistema"
        with FakeGemini([json_answer(changed(verbal(), 1, quote=quote))]) as fake:
            self.register(fake, language="es")
        self.assertEqual(len(fake.requests), 1)

    def test_a_fragment_is_matched_through_the_noise_of_the_transcript(self):
        noisy = [(0, "Diego", "Pongamos, Pongamos una pantalla de captura. It. Six. Donde sea una premisa, cierto.")]
        transcript = qa.Transcript.read(noisy, "")
        self.assertTrue(transcript.says("Pongamos una pantalla de captura donde sea una premisa", 0, 0))
        self.assertFalse(transcript.says("una premisa donde sea una pantalla de captura pongamos", 0, 0))
        self.assertFalse(transcript.says("Pongamos una planilla de costos donde sea una tarifa", 0, 0))
        self.assertFalse(transcript.says("Pongamos una pantalla de captura donde sea una premisa", 400, 500))

    def test_a_fragment_scattered_over_a_long_stretch_is_refused(self):
        # The same five words, in order, but far apart: not a fragment of what was said.
        spread = " ".join(f"{word} " + "relleno " * 6 for word in "el costo viaja por kilo".split())
        transcript = qa.Transcript.read([(0, "Juan", spread)], "")
        self.assertFalse(transcript.says("el costo viaja por kilo", 0, 0))
        self.assertTrue(qa.Transcript.read([(0, "Juan", "el costo viaja por kilo")], "").says(
            "el costo viaja por kilo", 0, 0))

    def test_the_words_that_show_the_screen_must_be_literal(self):
        # They are printed between quotation marks, so the 85 % does not apply.
        said = [(0, "Juan", "Te muestro ahora la planilla de costos de la planta del sur")]
        transcript = qa.Transcript.read(said, "")
        self.assertTrue(transcript.says("Te muestro ahora la planilla de costos de la planta del", 0, 0))
        self.assertFalse(transcript.says("Te muestro ahora la planilla de gastos de la planta del", 0, 0, exact=True))
        self.assertTrue(transcript.says("te muestro ahora la planilla", 0, 0, exact=True))
        broken = changed(verbal(), 2, screen=True, screen_quote="Te muestro la planilla, ¿están viendo? El costo viaja "
                                                               "por litro con la tarifa")
        self.assertRefused(broken, "question 2 is marked on screen, but the words that show it are not")

    def test_a_fragment_too_short_is_refused(self):
        self.assertRefused(changed(verbal(), 1, quote="Los carga"), "its verbatim fragment is not in the transcript")

    def test_an_answer_given_to_someone_who_did_not_speak_is_refused(self):
        broken = changed(verbal(), 2, answers=[{"speaker": "Pedro Ruiz", "text": "El costo viaja por kilo."}])
        self.assertRefused(broken, "question 2: the answer is given to 'Pedro Ruiz', who did not speak")

    def test_a_name_and_what_they_said_in_the_speakers_field_is_split_and_the_name_checked(self):
        # Found by the first real run: "Name: what they said" as the speaker.
        point = {"speaker": "Juan Gómez: El costo viaja por kilo con la tarifa de cada etapa.", "text": ""}
        with FakeGemini([json_answer(changed(verbal(), 2, answers=[point]))]) as fake:
            self.register(fake, language="es")
        self.assertIn("  - **Juan Gómez:** El costo viaja por kilo con la tarifa de cada etapa.", self.text())
        point = {"speaker": "Juan Gómez: lo que dijo", "text": "El costo viaja por kilo."}
        self.output().unlink()
        with FakeGemini([json_answer(changed(verbal(), 2, answers=[point]))]) as fake:
            self.register(fake, language="es")
        self.assertIn("  - **Juan Gómez:** El costo viaja por kilo.", self.text())
        broken = changed(verbal(), 2, answers=[{"speaker": "Pedro Ruiz: " + "palabra " * 40, "text": "El costo."}])
        for name in (writer.OUTPUT_NAME, qa.REGISTER_NAME):
            (self.frames / name).unlink()
        self.assertRefused(broken, "question 2: the answer is given to 'Pedro Ruiz: palabra palabra")
        self.assertNotIn("palabra " * 12, str(self.last_error))

    def test_a_stopped_run_says_what_it_spent_and_both_refusals(self):
        first = changed(verbal(), 1, quote="nada de esto se dijo en la reunión")
        second = changed(verbal(), 1, status="answered")
        with FakeGemini([json_answer(first), json_answer(second)]) as fake:
            with self.assertRaises(qa.QAError) as caught:
                self.register(fake, language="es")
        message = str(caught.exception)
        self.assertIn("status 'answered' is not one of", message)
        self.assertIn("the answer before was refused too: 1 question(s) refused: question 1: its verbatim fragment", message)
        self.assertIn("[stopped at register 1/1 after 2 attempt(s) of it; about US$0.083 spent in all; the register "
                      "was not written]", message)

    def test_every_refused_question_is_named_for_the_retry(self):
        broken = changed(changed(verbal(), 1, quote="nada de esto se dijo en la reunión"), 2, status="answered")
        with FakeGemini([json_answer(broken), json_answer(verbal())]) as fake:
            self.register(fake, language="es")
        retry = fake.requests[1]["body"]["contents"][0]["parts"][0]["text"]
        note = retry.index("YOUR PREVIOUS ANSWER WAS REFUSED: 2 question(s) refused: question 1: its verbatim")
        self.assertIn("question 2: status 'answered'", retry[note:])
        self.assertLess(note, retry.index(qa.MATERIAL))

    def test_a_refused_answer_is_kept_to_see_why(self):
        broken = changed(verbal(), 1, quote="nada de esto se dijo en la reunión")
        self.assertRefused(broken, "its verbatim fragment")
        kept = sorted(path.name for path in (self.frames / qa.PARTS_DIR).iterdir())
        self.assertEqual(kept, ["refused-part-1-attempt-1.json", "refused-part-1-attempt-2.json"])
        record = json.loads((self.frames / qa.PARTS_DIR / kept[0]).read_text(encoding="utf-8"))
        self.assertIn("its verbatim fragment", record["refused"])
        self.assertEqual(json.loads(record["answer"]), broken)

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
                    self.register(fake, language="es", date="2026-09-25")
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
        first, second = (request["body"]["contents"][0]["parts"][0]["text"] for request in fake.requests)
        self.assertNotIn("YOUR PREVIOUS ANSWER WAS REFUSED", first)
        self.assertIn("YOUR PREVIOUS ANSWER WAS REFUSED: 1 question(s) refused: question 1: its verbatim fragment is "
                      "not in the transcript",
                      second)
        note = second.index("YOUR PREVIOUS ANSWER WAS REFUSED")
        self.assertEqual(second[:note] + second[second.index(qa.MATERIAL):], first)

    def test_a_fragment_said_at_another_moment_of_the_meeting_is_refused(self):
        self.assertRefused(changed(verbal(), 1, quote="Queda acordado: Juan manda el detalle"),
                           "question 1: its verbatim fragment is not in the transcript between 0:04 and 0:40")

    def test_words_showing_the_screen_said_at_another_moment_are_refused(self):
        self.assertRefused(changed(verbal(), 1, screen=True, screen_quote="Gracias a todos"),
                           "question 1 is marked on screen, but the words that show it are not in the transcript "
                           "between 0:04 and 0:40")

    def test_a_deadline_said_without_an_agreement_is_kept(self):
        with FakeGemini([json_answer(changed(verbal(), 1, deadline="el 25 de septiembre"))]) as fake:
            self.register(fake, language="es")
        self.assertEqual(self.text().count("- **Plazo:** el 25 de septiembre"), 2)

    def test_what_was_seen_in_labels_and_figures_only_is_accepted(self):
        seen = {"answers": [dict(SEEN["answers"][0], seen="Tabla: SKU, Planta, Kg.")]}
        with FakeGemini([json_answer(REGISTER), reading, json_answer(seen)]) as fake:
            self.register(fake, language="es")
        self.assertIn("- **Lo visto en pantalla:** Tabla: SKU, Planta, Kg.", self.text())

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

    def test_a_question_outside_its_batch_is_left_to_the_other_batch(self):
        # Both batches answer both questions: each keeps only the one raised in
        # its part, so none is lost or repeated, and nothing is refused.
        with mock.patch.object(qa, "batches", return_value=SPLIT), \
                FakeGemini([json_answer(verbal()), json_answer(verbal())]) as fake:
            result = self.register(fake, language="es")
        self.assertEqual((len(fake.requests), result.questions), (2, 2))
        self.assertEqual(self.text().count("### P"), 2)
        self.assertIn("### P1 · ¿Quién carga", self.text())
        self.assertIn("### P2 · ¿Cómo viaja", self.text())

    def test_a_batch_accepted_is_not_paid_again_when_the_run_is_made_again(self):
        first = {"questions": [REGISTER["questions"][0]], "knowledge": {}}
        second = {"questions": [changed(verbal(), 2)["questions"][1]], "knowledge": REGISTER["knowledge"]}
        broken = changed(second, None)
        broken["questions"] = [dict(second["questions"][0], quote="nada de esto se dijo en la reunión")]
        with mock.patch.object(qa, "batches", return_value=SPLIT), \
                FakeGemini([json_answer(first), json_answer(broken), json_answer(broken)]) as fake:
            with self.assertRaises(qa.QAError):
                self.register(fake, language="es")
        self.assertTrue((self.frames / qa.PARTS_DIR / "part-1-of-2.json").exists())
        with mock.patch.object(qa, "batches", return_value=SPLIT), \
                FakeGemini([json_answer(second)]) as fake:
            result = self.register(fake, language="es", keep=True)
        self.assertEqual(len(fake.requests), 1)
        self.assertIn("part 2 of 2", fake.requests[0]["body"]["contents"][0]["parts"][0]["text"])
        self.assertEqual([(s.name, s.attempts) for s in result.stages],
                         [("register 1/2 (kept from an earlier run)", 0), ("register 2/2", 1)])
        self.assertEqual(result.questions, 2)
        # Kept for another request (another meeting type): asked again.
        with mock.patch.object(qa, "batches", return_value=SPLIT), \
                FakeGemini([json_answer(first), json_answer(second)]) as fake:
            self.register(fake, language="es", keep=True, meeting_type="presale")
        self.assertEqual(len(fake.requests), 2)

    def test_a_question_taken_up_again_after_the_split_is_not_registered_twice(self):
        second = {"questions": [REGISTER["questions"][0]] + [changed(verbal(), 2)["questions"][1]],
                  "knowledge": REGISTER["knowledge"]}
        with mock.patch.object(qa, "batches", return_value=SPLIT), \
                FakeGemini([json_answer({"questions": [REGISTER["questions"][0]], "knowledge": {}}),
                            json_answer(second)]) as fake:
            result = self.register(fake, language="es")
        self.assertEqual(result.questions, 2)
        self.assertEqual(self.text().count("¿Quién carga los estándares"), 2)  # the board's row and the heading


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
        self.assertEqual(self.image_requests(fake)[0]["body"]["generationConfig"]["maxOutputTokens"], 4000)
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
        later = frames + [Path("frame_005_t00-20-00.jpg")]
        self.assertEqual([p.name for p in qa.span_frames(later, 130, 2000)],
                         ["frame_001_t00-00-10.jpg", "frame_002_t00-02-20.jpg", "frame_003_t00-04-00.jpg",
                          "frame_004_t00-06-00.jpg"])
        self.assertEqual(qa.span_frames(later, 1200 - qa.SPAN_MAX, 2000)[-1].name, "frame_005_t00-20-00.jpg")
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
        for text, year in (("el 25 de septiembre", None), ("el 25/09", None), ("25/09/2026", 2026),
                           ("2026-09-25", 2026), ("September 25th", None), ("25 of September", None),
                           ("el 25 setiembre", None)):
            with self.subTest(text=text):
                self.assertEqual(qa.written_dates(text), {(25, 9, year)})

    def test_figures_minutes_and_months_alone_are_not_dates(self):
        for text in ("0,14 USD/kg", "1.250 kilos", "en abril", "1:22:57", "la próxima semana", "el viernes",
                     "aporte 2,40 %", "el 40/99", "1/2 de la producción", "atención 24/7", "3/4 partes",
                     "turnos 2/3", "versión 1/12", "the lead time of 10 may change"):
            with self.subTest(text=text):
                self.assertEqual(qa.written_dates(text), set())

    def test_a_day_said_in_words_is_a_date(self):
        self.assertEqual(qa.written_dates("lo mandamos el dos de mayo"), {(2, 5, None)})
        self.assertEqual(qa.written_dates("hasta el treinta y uno de marzo"), {(31, 3, None)})
        self.assertEqual(qa.written_dates("on the 10 of May"), {(10, 5, None)})
        self.assertEqual(qa.written_dates("antes del 2/5"), {(2, 5, None)})

    def test_a_minute_may_come_in_square_brackets(self):
        self.assertEqual(qa.parse_clock("[00:12:05]"), 725)
        self.assertEqual(qa.parse_clock("4:43"), 283)
        self.assertIsNone(qa.parse_clock("al principio"))


class BudgetTest(unittest.TestCase):
    def test_the_whole_run_on_a_meeting_like_cermaq_fits_the_ceiling_at_its_worst_without_retries(self):
        # About 115,000 characters of request per batch (the transcript whole
        # in both), 20 frames read, and about 20,000 characters of what they
        # show: every attempt reserved at its worst must fit US$0.50 together.
        batch = gemini.token_cost((115000 + qa.RETRY_NOTE_CHARS) / writer.CHARS_PER_TOKEN, qa.MAX_OUTPUT_TOKENS)
        frames = gemini.worst_attempt_cost(20, gemini.listed_output_tokens(20))
        seen = gemini.token_cost((20000 + qa.RETRY_NOTE_CHARS) / writer.CHARS_PER_TOKEN, qa.SEEN_OUTPUT_TOKENS)
        self.assertLess(2 * batch + frames + seen, writer.MAX_COST_USD)

    def test_a_few_frames_do_not_reserve_the_output_of_seventy(self):
        self.assertEqual(gemini.listed_output_tokens(2), 4000)
        self.assertEqual(gemini.listed_output_tokens(70), gemini.MAX_OUTPUT_TOKENS)
        self.assertEqual(gemini.worst_attempt_cost(70), gemini.worst_attempt_cost(70, gemini.MAX_OUTPUT_TOKENS))


class YearsAndFiguresTest(Workspace):
    """WI25-AC03: the register's dates keep their year, and the figures of
    "figures said" are searched in the transcript (the external review's R04)."""

    FIGURES = ("Procesamos 48.000 kilos por mes, con un margen del 1,5 % y un 15% de merma, "
               "a las 10:30 y en 3 turnos.")

    def said(self, *lines, blocks=SPANISH):
        """A transcript like the Spanish one, with these lines more, said by Juan Gómez after 2:30."""
        path = self.tmp / f"said-{len(list(self.tmp.glob('said-*.docx')))}.docx"
        write_teams_docx(path, blocks[:4] + [("Juan Gómez", f"3:{10 + number}", line)
                                             for number, line in enumerate(lines)] + blocks[4:])
        return path

    def run_register(self, data, transcript=None, date=None, language="es"):
        """(None, fake) if the register was accepted; (the refusal, fake) if not."""
        with FakeGemini([json_answer(data), json_answer(data)]) as fake:
            try:
                self.register(fake, transcript, language=language, date=date)
            except qa.QAError as error:
                return error, fake
        return None, fake

    def cause(self, refusal):
        """The refusal of the last attempt, which the error that stops the run carries."""
        return refusal.message.params["error"]

    def figures(self, *entries):
        return changed(verbal(), knowledge=dict(REGISTER["knowledge"], figures=list(entries)))

    def test_a_date_with_a_year_nobody_said_is_refused_naming_it(self):
        for value, shown in (("el 25 de septiembre de 2030", "25/9/2030"), ("el 25/09/2030", "25/9/2030"),
                             ("el 2030-09-25", "25/9/2030"), ("September 25, 2030", "25/9/2030"),
                             ("el veinticinco de septiembre de 2030", "25/9/2030")):
            with self.subTest(value=value):
                refusal, fake = self.run_register(changed(verbal(), 2, deadline=value), date="2026-09-25")
                self.assertEqual(self.cause(refusal).key, "qa.refused")
                self.assertIn(f"question 2 writes a date the transcript does not say ({shown})", str(refusal))
                self.assertEqual(len(fake.requests), 2, "a refused register is retried once")
                self.assertNothingWritten()

    def test_the_year_of_the_meeting_is_accepted_with_a_date_the_transcript_says(self):
        for value in ("el 25 de septiembre de 2026", "el 25/09/2026", "el 2026-09-25", "September 25, 2026",
                      "el 25/09/26", "25 de septiembre del 2026"):
            with self.subTest(value=value):
                refusal, fake = self.run_register(changed(verbal(), 2, deadline=value), date="2026-09-25")
                self.assertIsNone(refusal)
                self.assertEqual(len(fake.requests), 1)

    def test_the_year_of_the_meeting_is_not_the_year_of_every_date(self):
        refusal, _ = self.run_register(changed(verbal(), 2, deadline="el 25 de septiembre de 2027"),
                                       date="2026-09-25")
        self.assertIn("question 2 writes a date the transcript does not say (25/9/2027)", str(refusal))
        refusal, _ = self.run_register(changed(verbal(), 2, deadline="el 25 de septiembre de 2026"))
        self.assertIn("(25/9/2026)", str(refusal), "with no date of the meeting, a year nobody said is not known")

    def test_a_year_the_transcript_says_is_accepted(self):
        for line in ("Queda para el 25 de septiembre de 2027.", "Es un plan para 2027, por el 25 de septiembre.",
                     "El 25/09/2027 cerramos."):
            with self.subTest(line=line):
                transcript = self.said(line)
                refusal, _ = self.run_register(changed(verbal(), 2, deadline="el 25 de septiembre de 2027"),
                                               transcript, date="2026-09-25")
                self.assertIsNone(refusal)

    def test_a_year_the_transcript_says_does_not_make_another_one_accepted_nor_a_day_it_did_not_say(self):
        transcript = self.said("Queda para el 25 de septiembre de 2027.")
        for value, shown in (("el 25 de septiembre de 2028", "25/9/2028"), ("el 3 de octubre de 2027", "3/10/2027"),
                             ("el 3 de octubre", "3/10")):
            with self.subTest(value=value):
                refusal, _ = self.run_register(changed(verbal(), 2, deadline=value), transcript, date="2026-09-25")
                self.assertIn(f"({shown})", str(refusal))

    def test_a_date_without_a_year_is_checked_by_day_and_month_as_before(self):
        for value in ("el 25 de septiembre", "el 25/09", "September 25th", "25 of September"):
            with self.subTest(value=value):
                refusal, _ = self.run_register(changed(verbal(), 2, deadline=value))
                self.assertIsNone(refusal)
        refusal, _ = self.run_register(changed(verbal(), 2, deadline="el 30 de septiembre"))
        self.assertIn("(30/9)", str(refusal))

    def test_the_year_is_checked_in_every_place_a_date_is_written(self):
        year = "el 25 de septiembre de 2030"
        for data in (changed(verbal(), 2, pending=year), changed(verbal(), 2, agreement=year),
                     changed(verbal(), 2, answers=[{"speaker": "Juan Gómez", "text": f"Se manda {year}."}]),
                     changed(verbal(), knowledge=dict(REGISTER["knowledge"], scope=[f"Se entrega {year}."]))):
            with self.subTest(data=str(data)[-70:]):
                refusal, _ = self.run_register(data, date="2026-09-25")
                self.assertIn("writes a date the transcript does not say (25/9/2030)", str(refusal))

    def test_a_date_said_with_its_year_is_one_date_not_two(self):
        self.assertEqual(qa.written_dates("el 25/09/2027 y el 3 de octubre de 2028 y el 7/11"),
                         {(25, 9, 2027), (3, 10, 2028), (7, 11, None)})
        self.assertEqual(qa.written_years("el 25/09/2027, 3 de octubre de 2028 y para 2029, 2.500 y 2,40"),
                         {2027, 2028, 2029})

    def test_a_figure_nobody_said_is_refused_and_the_retry_says_which(self):
        transcript = self.said(self.FIGURES)
        refusal, fake = self.run_register(self.figures("Se procesan 52.000 kilos por mes."), transcript)
        self.assertEqual(self.cause(refusal).key, "qa.invented_figure")
        self.assertIn("the knowledge 'figures' writes a figure nobody said in the meeting (52.000)", str(refusal))
        self.assertEqual(len(fake.requests), 2)
        self.assertNothingWritten()
        retry = fake.requests[1]["body"]["contents"][0]["parts"][0]["text"]
        self.assertIn("YOUR PREVIOUS ANSWER WAS REFUSED: the knowledge 'figures' writes a figure nobody said", retry)

    def test_every_figure_nobody_said_is_what_the_refusal_names(self):
        refusal, _ = self.run_register(self.figures("Se procesan 52.000 kilos, con 7 turnos y 48.000 de stock."),
                                       self.said(self.FIGURES))
        self.assertIn("(52.000, 7)", str(refusal))

    def test_a_figure_that_was_said_written_in_another_form_is_accepted(self):
        transcript = self.said(self.FIGURES)
        for entry in ("Se procesan 48.000 kilos por mes.", "Se procesan 48,000 kilos por mes.",
                      "Se procesan 48000 kilos por mes.", "Se procesan 48 000 kilos por mes.",
                      "Se procesan 48.000,00 kilos por mes.", "El margen es de 1,5 %.", "El margen es de 1.5 %.",
                      "El margen es de 1,50 por ciento.", "La merma es del 15 %.", "La merma es de 15 por ciento.",
                      "Son 3 turnos.", "Se procesan 48000 kg."):
            with self.subTest(entry=entry):
                refusal, _ = self.run_register(self.figures(entry), transcript)
                self.assertIsNone(refusal)

    def test_a_figure_said_another_way_is_not_the_one_written(self):
        transcript = self.said(self.FIGURES)
        for entry in ("Se procesan 48 kilos por mes.", "El margen es de 5 %.", "El margen es de 0,15 %.",
                      "La merma es de 0,5 %.", "Se procesan 4.800 kilos por mes.", "Son 30 turnos."):
            with self.subTest(entry=entry):
                refusal, _ = self.run_register(self.figures(entry), transcript)
                self.assertEqual(self.cause(refusal).key, "qa.invented_figure")

    def test_the_dates_the_times_the_codes_and_the_years_of_a_figure_are_not_figures_to_find(self):
        transcript = self.said(self.FIGURES)
        for entry in ("Se procesan 48.000 kilos el 25 de septiembre.", "Se procesan 48.000 kilos el 25/09.",
                      "Se procesan 48.000 kilos a las 10:30.", "El SKU A12 pesa 48.000 kilos.",
                      "Se procesan 48.000 kilos en 2026.", "Se procesan 48.000 kilos el 2026-09-25."):
            with self.subTest(entry=entry):
                refusal, _ = self.run_register(self.figures(entry), transcript, date="2026-09-25")
                self.assertIsNone(refusal)

    def test_only_the_figures_group_is_checked(self):
        transcript = self.said(self.FIGURES)
        for group in ("rules", "owners", "glossary", "scope"):
            with self.subTest(group=group):
                knowledge = dict(REGISTER["knowledge"], **{group: ["Se procesan 52.000 kilos, el doble de los 26.000."]})
                refusal, _ = self.run_register(changed(verbal(), knowledge=knowledge), transcript)
                self.assertIsNone(refusal)
        sum_of_two = changed(verbal(), 1, answers=[{"speaker": "Juan Gómez", "text": "Entre las dos son 96.000."}])
        refusal, _ = self.run_register(sum_of_two, transcript)
        self.assertIsNone(refusal)

    def test_a_figure_nobody_said_in_the_figures_then_a_register_without_it_is_accepted(self):
        transcript = self.said(self.FIGURES)
        with FakeGemini([json_answer(self.figures("Se procesan 52.000 kilos por mes.")),
                         json_answer(self.figures("Se procesan 48.000 kilos por mes."))]) as fake:
            self.register(fake, transcript, language="es")
        self.assertEqual(len(fake.requests), 2)
        self.assertIn("- Se procesan 48.000 kilos por mes.", self.text())

    def test_numbers_are_compared_as_numbers(self):
        for token in ("48.000", "48,000", "48 000", "48\xa0000", "48000", "48.000,00", "48,000.00"):
            with self.subTest(token=token):
                self.assertEqual(qa.number(token), qa.number("48000"))
        for token, other in (("1,5", "1.5"), ("1,50", "1.5"), ("1.250,75", "1,250.75"), ("0,125", "0.125")):
            with self.subTest(token=token):
                self.assertEqual(qa.number(token), qa.number(other))
        for token, other in (("48.000", "48"), ("1,5", "15"), ("1.5", "1500"), ("0,125", "125"), ("2,40", "240")):
            with self.subTest(token=token, other=other):
                self.assertNotEqual(qa.number(token), qa.number(other))
        self.assertEqual(qa.figures_in("48000 y 1,5 y 7", {qa.number("48.000"), qa.number("1.5")}), ["7"])

    def test_spaced_thousands_may_also_be_two_figures_in_the_transcript(self):
        transcript = self.said("Pasaron 5 100 cajas.")
        for entry in ("Pasaron 5 cajas.", "Pasaron 100 cajas.", "Pasaron 5100 cajas."):
            with self.subTest(entry=entry):
                refusal, _ = self.run_register(self.figures(entry), transcript)
                self.assertIsNone(refusal)


class YearsAnywhereAndScalesTest(Workspace):
    """WI25's review: a year is a year whichever way it is written (P2-1), and a figure said with its scale
    ("48 mil") is the figure written out (P2-2)."""

    said = YearsAndFiguresTest.said
    run_register = YearsAndFiguresTest.run_register
    cause = YearsAndFiguresTest.cause
    figures = YearsAndFiguresTest.figures

    def test_a_year_nobody_said_is_refused_whichever_way_it_is_written(self):
        for value, shown in (("del año 2030", "year the transcript does not say (2030)"),
                             ("para (2030)", "year the transcript does not say (2030)"),
                             ("el 25 de Sept. de 2030", "year the transcript does not say (2030)"),
                             ("Sept. 25, 2030", "year the transcript does not say (2030)"),
                             ("el 25 sep 2030", "year the transcript does not say (2030)"),
                             ("en septiembre de 2030", "year the transcript does not say (2030)"),
                             ("para 2030", "year the transcript does not say (2030)"),
                             ("en el Q3 de 2030", "year the transcript does not say (2030)"),
                             ("el 25-09-2030", "date the transcript does not say (25/9/2030)"),
                             ("el 25.09.2030", "date the transcript does not say (25/9/2030)"),
                             ("el 25 de septiembre de 2030", "date the transcript does not say (25/9/2030)")):
            with self.subTest(value=value):
                refusal, _ = self.run_register(changed(verbal(), 2, deadline=value), date="2026-09-25")
                self.assertIn(f"question 2 writes a {shown}", str(refusal))

    def test_a_year_is_refused_in_every_place_text_is_written(self):
        year = "para el año 2030"
        for data in (changed(verbal(), 2, pending=year), changed(verbal(), 2, agreement=year),
                     changed(verbal(), 2, answers=[{"speaker": "Juan Gómez", "text": f"Se manda {year}."}]),
                     changed(verbal(), knowledge=dict(REGISTER["knowledge"], scope=[f"Se entrega {year}."])),
                     self.figures("Se procesan 2030 kilos.")):
            with self.subTest(data=str(data)[-70:]):
                refusal, _ = self.run_register(data, date="2026-09-25")
                self.assertIn("writes a year the transcript does not say (2030)", str(refusal))

    def test_a_year_the_transcript_or_the_meeting_says_is_accepted_whichever_way_it_is_written(self):
        transcript = self.said("Son 2030 cajas.")
        for value in ("del año 2030", "(2030)", "Sept. 25, 2030", "el 25 sep 2030", "en septiembre de 2030",
                      "para 2030", "en el Q3 de 2030", "el 25-09-2030", "el 25.09.2030"):
            with self.subTest(value=value):
                refusal, _ = self.run_register(changed(verbal(), 2, deadline=value), transcript, date="2026-09-25")
                self.assertIsNone(refusal)
        for value in ("del año 2026", "para 2026", "el 25-09-2026", "el 25.09.2026", "en el Q3 de 2026"):
            with self.subTest(value=value):
                refusal, _ = self.run_register(changed(verbal(), 2, deadline=value), date="2026-09-25")
                self.assertIsNone(refusal)

    def test_a_quantity_that_is_not_a_year_or_that_the_transcript_says_is_not_refused(self):
        transcript = self.said("Son 2030 cajas y 1500 kilos.")
        for entry in ("Hay 2030 cajas.", "Hay 1500 kilos.", "Son 3.500 cajas.", "Son 1.2030 cajas."):
            with self.subTest(entry=entry):
                answers = [{"speaker": "Juan Gómez", "text": entry}]
                refusal, _ = self.run_register(changed(verbal(), 2, answers=answers), transcript, date="2026-09-25")
                self.assertIsNone(refusal)
        answers = [{"speaker": "Juan Gómez", "text": "Hay 1500 kilos."}]
        refusal, _ = self.run_register(changed(verbal(), 2, answers=answers), date="2026-09-25")
        self.assertIsNone(refusal, "1500 is not a year, and what an answer says about quantities is not checked")

    def test_written_years_are_every_year_whichever_its_writing(self):
        self.assertEqual(qa.written_years("del año 2030, (2031), Q3 de 2032, 25-09-2033 y 2034."),
                         {2030, 2031, 2032, 2033, 2034})
        self.assertEqual(qa.written_years("2.500, 2,40, 1.2030, 12030 y 1850"), set())
        self.assertEqual(qa.written_dates("25-09-2030 y 25.09.2031 y 25-09-2030"), {(25, 9, 2030), (25, 9, 2031)})

    def test_a_figure_said_with_its_scale_is_the_figure_written_out(self):
        transcript = self.said("Procesamos 48 mil kilos, con 3 millones de pesos y 1,5 millones de dólares.",
                               "Son 2 million de unidades y 5k de stock.")
        for entry in ("Se procesan 48.000 kilos.", "Se procesan 48 mil kilos.", "Son 3.000.000 de pesos.",
                      "Son 3 millones de pesos.", "Son 1.500.000 dólares.", "Son 1,5 millones de dólares.",
                      "Son 2.000.000 de unidades.", "Son 2 million de unidades.", "Hay 5.000 de stock.",
                      "Hay 5k de stock."):
            with self.subTest(entry=entry):
                refusal, _ = self.run_register(self.figures(entry), transcript)
                self.assertIsNone(refusal)

    def test_a_figure_that_is_not_the_scaled_one_is_refused(self):
        transcript = self.said("Procesamos 48 mil kilos, con 3 millones de pesos y 1,5 millones de dólares.")
        for entry in ("Se procesan 49.000 kilos.", "Se procesan 49 mil kilos.", "Son 30.000.000 de pesos.",
                      "Son 3 mil de pesos.", "Son 1.500 dólares.", "Son 15 millones de dólares."):
            with self.subTest(entry=entry):
                refusal, _ = self.run_register(self.figures(entry), transcript)
                self.assertEqual(self.cause(refusal).key, "qa.invented_figure")

    def test_the_scales_are_read_as_numbers(self):
        spans = qa.scaled("48 mil kilos, 1,5 millones, 3 million, 48k y 5 km y 2 millón")
        self.assertEqual([value for _, _, value in spans], [48000, 1500000, 3000000, 48000, 2000000])
        self.assertEqual(qa.figures_in("48.000 y 3.000.000 y 1.500.000 y 48 mil y 7",
                                       {qa.number("48000"), qa.number("3000000"), qa.number("1500000")}), ["7"])


if __name__ == "__main__":
    unittest.main()
