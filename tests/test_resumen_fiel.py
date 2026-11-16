"""WI-2.0.0: a summary that does not invent (AC01), the net for figures nobody
said (AC02), the RECORDING line and its notice (AC04), the template's warning
(AC05) and the version in view (AC06).

The cases come from a real presales meeting processed with 1.0.0 (kept out of
the repository): its summary turned the figures of our own demo into the
client's problems, wrote costs and deadlines nobody said, and did not say that
the recording started mid-conversation. Every meeting here is invented."""

import io
import shutil
import tempfile
import unittest
from pathlib import Path

import docx
from docx.enum.text import WD_BREAK

from meetingtool import __version__
from meetingtool.report import document
from meetingtool.summary import writer
from tests.test_app import Running
from tests.test_frames import write_teams_docx
from tests.test_reading import KEY, FakeGemini
from tests.test_summary import Workspace, returning, saved, summary_text

# Invented lines (the independent review of WI-2.0.0: no line of a real meeting in the repository).
DEMO = [("Ana Pérez", "0:03", "Would you roll it out one warehouse at a time, or all at once?"),
        ("Laura Díaz", "0:11", "Forecasting goes all at once. We have 4 planners and forty-nine warehouses."),
        ("Ana Pérez", "21:10", "I will send you the spreadsheet today or tomorrow."),
        ("Laura Díaz", "33:02", "The steering group decides; the owners only sign it off.")]


def prompt_of(fake, index=-1):
    return fake.requests[index]["body"]["contents"][0]["parts"][0]["text"]


def instructions_of(prompt):
    return prompt[:prompt.index(writer.MATERIAL)]


class RequestTest(Workspace):
    """AC01: what the request asks, and that it carries the meeting's date."""

    def presale_prompt(self, date="2026-11-05"):
        with FakeGemini([returning(summary_text("en", "presale"))]) as fake:
            self.summarise(fake, meeting_type="presale", language="en", date=date)
        return instructions_of(prompt_of(fake))

    def test_the_presale_stance_keeps_our_demo_apart_from_the_clients_data(self):
        prompt = self.presale_prompt()
        self.assertIn("The screens our side shows are our own product: their figures are demo data, not the client's",
                      prompt)
        self.assertIn("never present them as the client's situation, problems or metrics", prompt)
        self.assertIn("What was seen on the screens of our own demo is never a problem of the client's", prompt)

    def test_a_demo_screen_is_named_only_when_the_client_commented_on_it(self):
        prompt = self.presale_prompt()
        self.assertIn("Name a screen of our own demo only when the client made an important comment about what it "
                      "showed", prompt)
        self.assertIn("a screen the client said nothing about is not named", prompt)
        self.assertIn("never what the screen \"proves\" or \"validates\"", prompt)

    def test_nothing_asks_for_what_nobody_said(self):
        prompt = self.presale_prompt()
        self.assertNotIn("implied but never said", prompt)
        self.assertNotIn("Include implied commitments", prompt)
        self.assertNotIn("marked as implied", prompt)
        self.assertNotIn("what it costs them today.", prompt)
        self.assertIn("what it costs them today only if someone said it; otherwise write \"cost not stated\"", prompt)
        self.assertIn("A problem nobody stated goes under \"Beyond the agenda\", as our reading, not here", prompt)
        self.assertIn("or \"not set\" when nobody said one; never infer a deadline", prompt)
        self.assertIn("Never invent a figure, a date, a cost, a deadline or a commitment", prompt)
        self.assertIn("Only work or material for the meeting's purpose; nothing personal or social (photos, jokes, "
                      "favours between people).", prompt)
        self.assertIn("A loose estimate (\"probably a week or two\", \"soon\") is written as said, never turned into "
                      "a date.", prompt)
        self.assertIn("Our own reading, and the only section for it", prompt)

    def test_the_sales_signals_ask_for_the_buying_process(self):
        prompt = self.presale_prompt()
        for asked in ("the stages of the purchase and who approves each one", "when price is discussed",
                      "the documents the client asks for or will prepare", "the client's success criteria",
                      "whether it is estimated, presented or approved, exactly as said",
                      "how the client compares the providers, only in the client's words",
                      "including when the client says they all can do it or all look alike",
                      "never our own judgment of how well we are placed",
                      "the meetings the client wants us to have with other people",
                      "an approval the client calls a formality is written as one",
                      "Mark each as a clear or a weak signal"):
            self.assertIn(asked, prompt)

    def test_the_request_carries_the_meetings_date_and_weekday(self):
        prompt = self.presale_prompt("2026-11-05")
        self.assertIn("MEETING DATE: 2026-11-05 (Thursday). A date said relative to the meeting", prompt)

    def test_without_a_date_the_request_says_none(self):
        with FakeGemini([returning(summary_text())]) as fake:
            self.summarise(fake)
        self.assertNotIn("MEETING DATE", prompt_of(fake))

    def test_a_date_that_is_not_a_date_is_refused_before_any_request(self):
        with FakeGemini([returning(summary_text())]) as fake:
            with self.assertRaises(writer.SummaryError) as caught:
                self.summarise(fake, date="2026-13-40")
        self.assertEqual(caught.exception.message.key, "meeting.bad_date")
        self.assertEqual(fake.requests, [])

    def test_the_request_asks_for_the_recording_line(self):
        prompt = self.presale_prompt()
        self.assertIn(writer.RECORDING_RULE, prompt)
        for value in writer.RECORDING_VALUES:
            self.assertIn(f"\"RECORDING: {value}\"", prompt)


class RecordingLineTest(Workspace):
    """AC04: the RECORDING line is read, taken out, and turned into a notice."""

    def test_the_line_is_read_and_taken_out(self):
        for value in writer.RECORDING_VALUES:
            with self.subTest(value=value):
                found, rest = writer.take_recording_line(f"RECORDING: {value}\n\n## Resumen ejecutivo\nTexto.")
                self.assertEqual(found, value)
                self.assertEqual(rest, "## Resumen ejecutivo\nTexto.")

    def test_a_line_written_with_marks_or_another_case_is_read(self):
        for line in ("**RECORDING: complete**", "recording: Complete", "> RECORDING : complete.", "`RECORDING: complete`"):
            with self.subTest(line=line):
                self.assertEqual(writer.take_recording_line(f"{line}\n## A\nb")[0], "complete")

    def test_no_line_an_unknown_value_two_lines_or_a_line_after_a_heading_is_none(self):
        for text in ("## Resumen ejecutivo\nTexto.", "RECORDING: partial\n## A\nb",
                     "RECORDING: complete\nRECORDING: complete\n## A\nb", "## A\nRECORDING: complete\nb"):
            with self.subTest(text=text):
                self.assertIsNone(writer.take_recording_line(text)[0])

    def test_a_summary_without_the_line_is_refused_and_retried_with_a_note_saying_why(self):
        with FakeGemini([returning(summary_text(recording=None)), returning(summary_text())]) as fake:
            result = self.summarise(fake)
        self.assertEqual(result.attempts, 2)
        retry = prompt_of(fake, 1)
        self.assertIn("YOUR PREVIOUS ANSWER WAS REFUSED: it did not start with one RECORDING line", retry)
        self.assertEqual(self.output().read_text(encoding="utf-8").strip(), saved(summary_text()))

    def test_two_answers_without_the_line_are_refused_and_nothing_is_written(self):
        with FakeGemini([returning(summary_text(recording=None)), returning(summary_text(recording="partial"))]) as fake:
            with self.assertRaises(writer.SummaryError) as caught:
                self.summarise(fake)
        self.assertEqual(caught.exception.message.key, "summary.recording_line")
        self.assertFalse(self.output().exists())

    def test_a_complete_recording_has_no_notice(self):
        with FakeGemini([returning(summary_text())]) as fake:
            self.summarise(fake)
        text = self.output().read_text(encoding="utf-8")
        self.assertTrue(text.startswith("## Resumen ejecutivo"), text[:80])
        self.assertNotIn("RECORDING", text)

    def test_a_recording_that_starts_mid_conversation_opens_with_a_notice_in_the_summary_and_the_report(self):
        with FakeGemini([returning(summary_text("en", recording="starts-mid-conversation"))]) as fake:
            self.summarise(fake, language="en")
        text = self.output().read_text(encoding="utf-8")
        notice = "The recording starts with the meeting already under way: what was said before is not in this summary."
        self.assertTrue(text.startswith(f"**⚠ {notice}**\n\n## Executive summary"), text[:200])
        report = document.build_report(self.frames, title="Reunión", neutral=True)
        paragraphs = [p.text for p in docx.Document(str(report.output)).paragraphs if p.text.strip()]
        self.assertEqual(paragraphs[1], f"⚠ {notice}")  # right after the title

    def test_each_value_says_its_notice_in_the_summarys_language(self):
        self.assertEqual(writer.recording_notice("complete", "es"), "")
        self.assertIn("termina antes que la reunión", writer.recording_notice("ends-mid-conversation", "es"))
        self.assertIn("before and after", writer.recording_notice("starts-and-ends-mid-conversation", "en"))
        self.assertTrue(writer.recording_notice("starts-mid-conversation", "es", notes=True).endswith(
            "Salvo lo que traen las notas.**"))


class FiguresTest(unittest.TestCase):
    """AC02: a figure of the client's problems, the sales signals or the key
    points that nobody said is marked; a said one is left as it is."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.transcript = Path(self._tmp.name) / "demo.docx"
        write_teams_docx(self.transcript, DEMO)
        from meetingtool.frames.transcript import read_turns
        self.said = writer.said_figures(read_turns(self.transcript), "2026-11-05")

    def tearDown(self):
        self._tmp.cleanup()

    def mark(self, text, language="en"):
        return writer.mark_unsaid_figures(text, language, self.said)

    def test_an_unsaid_figure_of_the_demo_is_marked_with_its_word(self):
        text = ("## Client problems\n- Plant K207 runs at ~61.4% attainment, with an estimated $18.3M excess.\n"
                "## Key points\n- (**$2.07M** peak inventory)")
        marked = self.mark(text)
        self.assertIn("~[VERIFICAR: «61.4%»] attainment", marked)
        self.assertIn("estimated [VERIFICAR: «$18.3M»] excess.", marked)
        self.assertIn("(**[VERIFICAR: «$2.07M»]** peak inventory)", marked)
        self.assertIn("Plant K207 runs", marked)  # a code is no figure

    def test_a_said_figure_in_digits_or_in_words_is_left_as_it_is(self):
        text = "## Sales signals\n- 4 planners run 49 warehouses; the spreadsheet goes on 5 November 2026 or 6 November."
        self.assertEqual(self.mark(text), text)

    def test_the_other_sections_are_not_checked(self):
        text = ("## Executive summary\n61.4% everywhere.\n## What was on screen\n- [frame_017_t00-13-03.jpg] "
                "$18.3M above max\n## Beyond the agenda\n- 117% load")
        self.assertEqual(self.mark(text), text)

    def test_list_numbers_frame_names_clock_times_and_marks_already_there_are_left_as_they_are(self):
        text = ("## Key points\n1. Seen at 13:05 on [frame_017_t00-13-03.jpg].\n"
                "2. Already [VERIFICAR: «un palo»] marked.")
        self.assertEqual(self.mark(text), text)

    def test_the_spanish_sections_are_checked(self):
        text = "## Problemas del cliente\n- Hay 812 SKUs sin stock.\n## Puntos clave\n- 4 planificadores."
        self.assertEqual(self.mark(text, "es"),
                         "## Problemas del cliente\n- Hay [VERIFICAR: «812»] SKUs sin stock.\n## Puntos clave\n"
                         "- 4 planificadores.")

    def test_a_figure_only_the_notes_say_is_not_marked(self):
        from meetingtool.frames.transcript import read_turns
        said = writer.said_figures(read_turns(self.transcript), "2026-11-05", notes="They have 12 stores and 5 warehouses.")
        text = "## Key points\n- 12 stores and 5 warehouses (according to Juan's notes)."
        self.assertEqual(writer.mark_unsaid_figures(text, "en", said), text)

    def test_the_summary_is_delivered_with_its_marks_and_the_project_keeps_them(self):
        workspace = Path(self._tmp.name) / "frames"
        workspace.mkdir()
        from meetingtool.reading import gemini
        (workspace / gemini.OUTPUT_NAME).write_text("# What each frame shows\n", encoding="utf-8")
        body = summary_text("en", "presale").replace(
            "The text of Client problems.", "- Inventory is $18.3M above max (cost not stated).")
        with FakeGemini([returning(body)]) as fake:
            result = writer.write_summary(workspace, self.transcript, KEY, endpoint=fake.endpoint,
                                          sleep=lambda s: None, meeting_type="presale", language="en",
                                          date="2026-11-05")
        written = result.output.read_text(encoding="utf-8")
        self.assertIn("- Inventory is [VERIFICAR: «$18.3M»] above max (cost not stated).", written)
        report = document.build_report(workspace, title="Demo", neutral=True)
        runs = [run for p in docx.Document(str(report.output)).paragraphs for run in p.runs
                if run.text == "[VERIFICAR: «$18.3M»]"]
        self.assertEqual(len(runs), 1)
        self.assertTrue(runs[0].bold)
        self.assertEqual(str(runs[0].font.color.rgb), "C00000")


PRAISED = ("- The cockpit is exactly what the client requires; Laura commended the "
           "admin rule.\n*The remainder of our product demo covered baselines, outlier detection and alerts.*")


class PraiseTest(Workspace):
    """Round 2 of AC08: praise of our own product in the summary's own words,
    and the screens nobody commented on told as a list, are refused once and,
    if the retry still writes them, delivered marked [VERIFICAR]."""

    def presale(self, screen):
        return summary_text("en", "presale").replace("The text of What was on screen.", screen)

    def test_praise_and_a_listed_demo_are_refused_and_the_retry_says_why(self):
        with FakeGemini([returning(self.presale(PRAISED)), returning(summary_text("en", "presale"))]) as fake:
            result = self.summarise(fake, meeting_type="presale", language="en")
        self.assertEqual(result.attempts, 2)
        retry = prompt_of(fake, 1)
        self.assertIn("YOUR PREVIOUS ANSWER WAS REFUSED, for 2 reasons: (1) it praised our own product in its own "
                      "words: - The cockpit is exactly what the client requires", retry)
        self.assertIn("(2) it listed what demo screens showed that the client did not comment on: *The remainder of "
                      "our product demo covered", retry)
        self.assertIn("Leave out the demo screens the client said nothing about", retry)
        self.assertEqual(self.output().read_text(encoding="utf-8").strip(), saved(summary_text("en", "presale")))

    def test_what_the_retry_still_writes_is_delivered_marked_not_refused(self):
        with FakeGemini([returning(self.presale(PRAISED))] * 2) as fake:
            result = self.summarise(fake, meeting_type="presale", language="en")
        self.assertEqual(result.attempts, 2)
        written = self.output().read_text(encoding="utf-8")
        self.assertIn("The cockpit is [VERIFICAR: «exactly what the client requires»]; Laura "
                      "[VERIFICAR: «commended»] the admin rule.", written)
        self.assertIn("*The [VERIFICAR: «remainder of our product demo covered»] baselines", written)

    def test_quotes_beyond_the_agenda_and_neutral_words_are_not_judged(self):
        text = self.presale('- Laura: "this is exactly what we need" (00:38:15). The '
                            "rest of the meeting covered dates.").replace(
            "The text of Beyond the agenda.", "Our reading: we are well positioned.")
        self.assertEqual(writer.praise_and_lists(text, "en"), [])
        self.assertEqual(writer.mark_praise_and_lists(text, "en"), text)

    def test_the_spanish_phrases_are_judged_too(self):
        text = summary_text("es", "presale").replace(
            "Texto de Lo que se vio en pantalla.", "- La pantalla es exactamente lo que el cliente necesita.\n"
            "- El resto de la demo mostró alertas.")
        self.assertEqual([problem.message.key for problem in writer.praise_and_lists(text, "es")],
                         ["summary.selling", "summary.demo_listed"])


    def test_our_fit_in_our_own_words_and_an_unquoted_reaction_are_judged(self):
        for phrase in ("What we offer addresses their structure", "Our modular architecture supports the rollout",
                       "The interface aligns directly with her preference", "She gave positive feedback on it",
                       "Lo que ofrecemos resuelve su estructura", "Tuvo una reacción positiva"):
            with self.subTest(phrase=phrase):
                self.assertTrue(writer.PRAISE.search(phrase), phrase)
        for neutral in ("Our platform does not cover the multi-echelon cost", "The board aligns with the committee",
                        "She addresses the board in December"):
            with self.subTest(neutral=neutral):
                self.assertIsNone(writer.PRAISE.search(neutral), neutral)

    def test_an_approximate_date_is_marked_and_an_exact_one_is_not(self):
        text = summary_text("en", "presale").replace(
            "The text of Action items.", "| Consolidate scores | Laura | a week or two (~2026-11-19) | High |\n"
            "| Send the matrix | Ana | tomorrow (2026-11-06) | High |")
        marked = writer.mark_praise_and_lists(text, "en")
        self.assertIn("a week or two ([VERIFICAR: «~2026-11-19»])", marked)
        self.assertIn("tomorrow (2026-11-06)", marked)

    def test_an_answer_accepted_on_the_retry_is_kept_and_not_paid_again(self):
        # The independent review of WI-2.0.0: the kept retry was checked as a first answer, refused and paid again.
        with FakeGemini([returning(self.presale(PRAISED))] * 2) as fake:
            self.summarise(fake, meeting_type="presale", language="en")
        first = self.output().read_text(encoding="utf-8")
        self.output().unlink()
        with FakeGemini([returning(summary_text("en", "presale"))]) as fake:
            result = self.summarise(fake, meeting_type="presale", language="en")
        self.assertEqual(fake.requests, [])
        self.assertEqual(result.attempts, 0)
        self.assertEqual(self.output().read_text(encoding="utf-8"), first)

    def test_only_a_presale_is_judged_for_selling(self):
        heading = writer.required_headings("es", "technical")[1]
        text = summary_text("es", "technical").replace(
            f"Texto de {heading}.", "- La prueba es exactamente lo que el cliente necesita.\n"
            "- El resto de la demo mostró alertas.")
        with FakeGemini([returning(text)]) as fake:
            result = self.summarise(fake, meeting_type="technical", language="es")
        self.assertEqual(result.attempts, 1)
        written = self.output().read_text(encoding="utf-8")
        self.assertIn("exactamente lo que el cliente necesita", written)
        self.assertNotIn("VERIFICAR", written)

    def test_ordinary_words_are_not_taken_for_selling(self):
        # The independent review of WI-2.0.0: these were refused, and marked in red, as praise.
        for neutral in ("La prueba que hicieron en marzo falló", "El tipo de cambio fue favorable",
                        "Sales were favorable in Q3", "The test run proves that the import fails"):
            with self.subTest(neutral=neutral):
                self.assertIsNone(writer.PRAISE.search(neutral), neutral)
        for phrase in ("La demo prueba que el cockpit alcanza", "She responded favourably to the cockpit",
                       "Respondió favorablemente al tablero", "This proves that our cockpit fits"):
            with self.subTest(phrase=phrase):
                self.assertTrue(writer.PRAISE.search(phrase), phrase)


class ContextFiguresTest(unittest.TestCase):
    """Round 2 of AC08: a figure the owner wrote in the project's context was
    said; one an earlier summary wrote was not."""

    KNOWLEDGE = ("# Knowledge: Demo\n\nClient: Acme\n\n## Context\n\nWe answer 59 requirements.\n\n## Meetings\n\n"
                 "### 2026-10-01: Earlier\n\nThe earlier summary invented 777 units.\n")

    def test_only_the_context_counts_never_an_earlier_summary(self):
        self.assertEqual(writer.project_context(self.KNOWLEDGE), "We answer 59 requirements.")
        self.assertEqual(writer.project_context(self.KNOWLEDGE.replace("We answer 59 requirements.", "(none)")), "")
        said = writer.said_figures([(0, "Ana", "hello")], context=writer.project_context(self.KNOWLEDGE))
        marked = writer.mark_unsaid_figures("## Key points\n- 59 requirements and 777 units.", "en", said)
        self.assertEqual(marked, "## Key points\n- 59 requirements and [VERIFICAR: «777»] units.")


def template_with(*body, start=None):
    """A template: a cover line, then a page break, then `body`; with `start`,
    that line ({informe}) right after the break."""
    template = docx.Document()
    template.add_paragraph("{cliente}")
    template.add_paragraph().add_run().add_break(WD_BREAK.PAGE)
    if start:
        template.add_paragraph(start)
    for line in body:
        template.add_paragraph(line)
    data = io.BytesIO()
    template.save(data)
    return data.getvalue()


class TemplateWarningTest(Running):
    """AC05: a template whose sample text would be copied into every report is
    kept and warned about; one with {informe} or a table of contents is not."""

    def set_template(self, data):
        path = self.tmp / "plantilla.docx"
        path.write_bytes(data)
        status, _, body = self.request("PUT", "/api/template?name=plantilla.docx", data,
                                       {"Content-Type": "application/octet-stream", "X-MeetingTool": "1"})
        self.assertEqual(status, 200, body)
        return document.template_info(self.data)

    def test_sample_text_after_the_page_break_is_warned_about(self):
        info = self.set_template(template_with("RESUMEN EJECUTIVO", "Subtitulo", "", "Texto Normal"))
        self.assertEqual((info.start, info.after_break), (None, 3))
        page = self.page("/settings")
        self.assertIn("después del salto de página tiene 3 párrafos con texto", page)
        self.assertIn("se va a copiar en cada informe", page)

    def test_one_paragraph_is_said_in_the_singular(self):
        self.set_template(template_with("Caso 1"))
        self.assertIn("tiene 1 párrafo con texto", self.page("/settings"))

    def test_a_template_with_its_report_start_has_no_warning(self):
        info = self.set_template(template_with("Modelo", start="{informe}"))
        self.assertEqual((info.start, info.after_break), ("marker", 0))
        self.assertNotIn("salto de página", self.page("/settings"))

    def test_a_cover_alone_has_no_warning(self):
        info = self.set_template(template_with())
        self.assertEqual(info.after_break, 0)
        self.assertIn("sale como portada de cada informe", self.page("/settings"))


class VersionTest(Running):
    """AC06: the version is in Settings and at the foot of every screen."""

    def test_the_version_is_2_0_0_and_is_shown(self):
        self.assertEqual(__version__, "2.0.0")
        self.assertIn("VisualMeetingTool 2.0.0", self.page("/settings"))
        for path in ("/", "/settings"):
            footer = self.page(path).split("<footer>", 1)[1]
            self.assertIn("VisualMeetingTool 2.0.0", footer)


if __name__ == "__main__":
    unittest.main()
