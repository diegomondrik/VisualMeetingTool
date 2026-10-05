"""WI20: the project's data is never lost, never left half written, and what
was paid is never thrown away (the external review of 2026-10-02, R01 and
R03).

These tests need nothing but the project's libraries, so the CI runs them;
the exhaustive versions (every write boundary cut, every order of two
operations) are INGOL's pilot tests in test_d1_*.py, which need INGOL's kits.
Each test here pins the core of one fix: docs/evidence/
01M46KHBYCXMGM0K6N2RM651PE/mutations.py undoes each fix and shows a test here
fails.
"""

import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

from meetingtool import disk, texts
from meetingtool.app import company, jobs, library
from meetingtool.projects import store
from meetingtool.reading import gemini
from meetingtool.report import document
from meetingtool.summary import qa
from tests import test_qa, test_summary
from tests.test_app import Processing
from tests.test_frames import write_teams_docx
from tests.test_reading import KEY, FakeGemini, answer_for

ROOT = Path(__file__).resolve().parent.parent


class Folder(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.data = self.tmp / "data"
        self.project = store.create_project(self.data, "Planta Demo", "Cliente Demo")["id"]

    def tearDown(self):
        self._tmp.cleanup()

    def titles(self):
        return [m["title"] for m in store.list_meetings(self.data, self.project)]


class Paused:
    """Runs fn in a thread that stops at `point` (a function of the module
    patched with it) until released, holding whatever it holds there."""

    def __init__(self, target, name, fn):
        self.reached, self.go = threading.Event(), threading.Event()
        self.error, self.value = None, None
        original = getattr(target, name)

        def stop_there(*args, **kwargs):
            if threading.current_thread() is self.thread:
                self.reached.set()
                self.go.wait(10)
            return original(*args, **kwargs)

        self.patch = mock.patch.object(target, name, stop_there)

        def run():
            try:
                self.value = fn()
            except Exception as error:  # noqa: BLE001 - reported by the test
                self.error = error

        self.thread = threading.Thread(target=run, daemon=True)

    def __enter__(self):
        self.patch.start()
        self.thread.start()
        if not self.reached.wait(10):
            raise AssertionError("the paused operation never reached its point")
        return self

    def __exit__(self, *exc):
        self.go.set()
        self.thread.join(10)
        self.patch.stop()


# ── AC02: whole or not at all ─────────────────────────────────────────────────

class WholeOrNothingTest(Folder):
    def test_a_reader_never_sees_the_knowledge_half_written(self):
        store.add_meeting(self.data, self.project, "Relevamiento", "2026-09-10", summary="La de antes.")
        knowledge = self.data / self.project / "knowledge.md"
        before = knowledge.read_text(encoding="utf-8")
        seen = []
        real_fsync = os.fsync

        def look(fd):  # the new text is written, not yet in place: a reader now sees the old one
            seen.append(knowledge.read_text(encoding="utf-8"))
            return real_fsync(fd)

        with mock.patch.object(disk.os, "fsync", look):
            store.add_meeting(self.data, self.project, "Cierre", "2026-09-25", summary="La nueva.")
        self.assertTrue(seen)
        self.assertEqual(seen[-1], before)
        self.assertIn("La nueva.", knowledge.read_text(encoding="utf-8"))

    def test_a_disk_error_while_saving_a_meeting_leaves_the_project_as_it_was(self):
        store.add_meeting(self.data, self.project, "Relevamiento", "2026-09-10", summary="La de antes.")
        knowledge = (self.data / self.project / "knowledge.md").read_text(encoding="utf-8")
        for failing in range(1, 4):  # the record's write, the knowledge's write, ...
            calls = []

            def flaky(path, data, failing=failing):
                calls.append(path)
                if len(calls) == failing:
                    raise OSError(28, "No space left on device")
                return real(path, data)

            real = disk.write_bytes
            with self.subTest(failing=failing), mock.patch.object(disk, "write_bytes", flaky):
                try:
                    store.add_meeting(self.data, self.project, "Cierre", "2026-09-25", summary="La nueva.")
                except OSError:
                    pass
                else:
                    continue
                self.assertEqual(self.titles(), ["Relevamiento"])
                self.assertEqual((self.data / self.project / "knowledge.md").read_text(encoding="utf-8"), knowledge)
        self.assertEqual(list((self.data / self.project).rglob("*.partial")), [])

    def test_settings_are_written_whole(self):
        company.set_company_name(self.data, "Consultora Demo")
        seen = []
        real_fsync = os.fsync

        def look(fd):
            seen.append(company._read(self.data))
            return real_fsync(fd)

        with mock.patch.object(disk.os, "fsync", look):
            company.set_language(self.data, "en")
        self.assertEqual(seen, [{"company_name": "Consultora Demo"}])
        self.assertEqual(company._read(self.data), {"company_name": "Consultora Demo", "language": "en"})


# ── AC03: two at once ─────────────────────────────────────────────────────────

class TwoAtOnceTest(Folder):
    def test_a_second_meeting_waits_for_the_first_and_gets_its_own_id(self):
        first = lambda: store.add_meeting(self.data, self.project, "Sesión", "2026-09-25", summary="Desde la app.")
        with Paused(store, "rebuild_knowledge", first) as paused:
            second = threading.Thread(target=lambda: store.add_meeting(
                self.data, self.project, "Sesión", "2026-09-25", summary="Desde la terminal."), daemon=True)
            second.start()
            second.join(0.5)
            self.assertTrue(second.is_alive(), "the second save did not wait for the first one's lock")
        second.join(10)
        self.assertIsNone(paused.error)
        ids = sorted(m["id"] for m in store.list_meetings(self.data, self.project))
        self.assertEqual(ids, ["2026-09-25-sesion", "2026-09-25-sesion-2"])
        knowledge = store.knowledge_context(self.data, self.project)
        self.assertIn("Desde la app.", knowledge)
        self.assertIn("Desde la terminal.", knowledge)

    def test_a_meeting_folder_taken_while_the_id_is_chosen_is_not_overwritten(self):
        # Another writer that does not take the lock (a version before WI20)
        # makes the same meeting's folder at the last moment: the id is
        # reserved by making the folder, so this save takes the next one.
        other = self.data / self.project / "meetings" / "2026-09-25-sesion"
        real_mkdir = Path.mkdir

        def mkdir(path, *args, **kwargs):
            if path == other and not other.exists():
                real_mkdir(other, parents=True)
                (other / "meeting.json").write_text(json.dumps({
                    "id": "2026-09-25-sesion", "title": "Sesión", "date": "2026-09-25", "added_utc": "x",
                    "meeting_type": "", "summary": "La otra.", "key_points": []}), encoding="utf-8")
            return real_mkdir(path, *args, **kwargs)

        with mock.patch.object(Path, "mkdir", mkdir):
            record = store.add_meeting(self.data, self.project, "Sesión", "2026-09-25", summary="Esta.")
        self.assertEqual(record["id"], "2026-09-25-sesion-2")
        self.assertEqual(sorted(m["summary"] for m in store.list_meetings(self.data, self.project)),
                         ["Esta.", "La otra."])

    def test_two_projects_of_the_same_name_one_is_refused(self):
        with Paused(store, "rebuild_knowledge",
                    lambda: store.create_project(self.data, "Proyecto Nuevo", "Cliente A")) as paused:
            with self.assertRaises(store.ProjectError) as refused:
                store.create_project(self.data, "Proyecto Nuevo", "Cliente B")  # waits, then finds it made
        self.assertIsNone(paused.error)
        self.assertEqual(refused.exception.message.key, "projects.exists")
        self.assertEqual([p["client"] for p in store.list_projects(self.data) if p["id"] == "proyecto-nuevo"],
                         ["Cliente A"])

    def test_two_settings_changed_at_once_keep_both(self):
        with Paused(company, "_write", lambda: company.set_language(self.data, "en")) as paused:
            other = threading.Thread(target=lambda: company.set_company_name(self.data, "Consultora Demo"),
                                     daemon=True)
            other.start()
            other.join(0.5)
            self.assertTrue(other.is_alive(), "the second change did not wait for the first one's lock")
        other.join(10)
        self.assertIsNone(paused.error)
        self.assertEqual(company._read(self.data), {"language": "en", "company_name": "Consultora Demo"})

    def test_the_template_is_set_under_the_lock(self):
        from tests import test_report
        template = test_report.company_template(self.tmp / "plantilla.docx")
        with store.data_lock(self.data):
            setter = threading.Thread(target=lambda: document.set_template(template, self.data), daemon=True)
            setter.start()
            setter.join(0.5)
            self.assertTrue(setter.is_alive())
            self.assertIsNone(document.stored_template(self.data))
        setter.join(30)
        self.assertIsNotNone(document.stored_template(self.data))


# ── AC04: between processes ───────────────────────────────────────────────────

class BetweenProcessesTest(Folder):
    def command(self, *argv, wait=None):
        code = "import sys; from meetingtool import disk; from meetingtool.projects import __main__ as cli; "
        if wait is not None:
            code += f"disk.LOCK_WAIT_SECONDS = {wait}; "
        code += "sys.exit(cli.main(sys.argv[1:]))"
        return subprocess.Popen([sys.executable, "-c", code, "--data-dir", str(self.data), *argv], cwd=ROOT,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8")

    def test_the_terminal_waits_while_the_application_holds_the_lock(self):
        with store.data_lock(self.data):
            store.add_meeting(self.data, self.project, "Sesión", "2026-09-25", summary="Desde la app.")
            process = self.command("add-meeting", "--project", self.project, "--title", "Sesión", "--date", "2026-09-25",
                                   "--summary", "Desde la terminal.")
            time.sleep(1.5)
            self.assertIsNone(process.poll(), "the command did not wait for the lock")
            self.assertEqual(self.titles(), ["Sesión"])
        out, err = process.communicate(timeout=60)
        self.assertEqual(process.returncode, 0, err)
        self.assertIn("added meeting 2026-09-25-sesion-2", out)
        self.assertEqual(sorted(m["summary"] for m in store.list_meetings(self.data, self.project)),
                         ["Desde la app.", "Desde la terminal."])

    def test_a_command_that_waits_too_long_says_so_and_writes_nothing(self):
        with store.data_lock(self.data):
            process = self.command("add-meeting", "--project", self.project, "--title", "Sesión", "--date", "2026-09-25",
                                   wait=1)
            out, err = process.communicate(timeout=60)
        self.assertEqual(process.returncode, 2)
        self.assertIn("has held the data folder", err)
        self.assertEqual(self.titles(), [])


# ── AC05: a record that cannot be read ────────────────────────────────────────

class UnreadableRecordTest(Folder):
    def test_listing_names_the_unreadable_record_in_both_languages(self):
        store.add_meeting(self.data, self.project, "Relevamiento", "2026-09-10", summary="Antes.")
        record = next((self.data / self.project / "meetings").glob("*/meeting.json"))
        record.write_bytes(record.read_bytes()[:40])
        with self.assertRaises(store.ProjectError) as raised:
            store.list_meetings(self.data, self.project)
        self.assertEqual(raised.exception.message.key, "projects.unreadable")
        self.assertIn(str(record), raised.exception.text("es"))
        self.assertIn("no se puede leer el registro", raised.exception.text("es"))
        self.assertIn("cannot be read", raised.exception.text("en"))
        self.assertTrue(raised.exception.details("en"))  # the JSON error, as a detail

    def test_a_record_missing_its_fields_is_unreadable_too(self):
        folder = self.data / self.project / "meetings" / "2026-09-10-a-mano"
        folder.mkdir(parents=True)
        (folder / "meeting.json").write_text('{"title": "A mano"}', encoding="utf-8")
        with self.assertRaises(store.ProjectError) as raised:
            store.list_meetings(self.data, self.project)
        self.assertEqual(raised.exception.message.key, "projects.unreadable")

    def test_a_knowledge_file_left_behind_is_rewritten_at_the_next_start(self):
        # A process that died after saving a meeting's record and before
        # rewriting knowledge.md: the application's next start rewrites it.
        store.add_meeting(self.data, self.project, "Relevamiento", "2026-09-10", summary="La de antes.")
        with mock.patch.object(store, "rebuild_knowledge"):
            store.add_meeting(self.data, self.project, "Cierre", "2026-09-25", summary="La que no llegó a la copia.")
        self.assertNotIn("La que no llegó", store.knowledge_context(self.data, self.project))
        jobs.clear_leftovers(self.data)
        self.assertIn("La que no llegó a la copia.", store.knowledge_context(self.data, self.project))

    def test_a_missing_knowledge_file_is_made_from_the_records(self):
        store.add_meeting(self.data, self.project, "Relevamiento", "2026-09-10", summary="La de antes.")
        (self.data / self.project / "knowledge.md").unlink()
        self.assertIn("La de antes.", store.knowledge_context(self.data, self.project))

    def test_a_meeting_the_knowledge_cannot_take_is_not_kept(self):
        broken = self.data / self.project / "meetings" / "2026-09-10-roto"
        broken.mkdir(parents=True)
        (broken / "meeting.json").write_text("{", encoding="utf-8")
        with self.assertRaises(store.ProjectError):
            store.add_meeting(self.data, self.project, "Nueva", "2026-09-25", summary="x")
        self.assertFalse((self.data / self.project / "meetings" / "2026-09-25-nueva").exists())


# ── AC06: a kept answer is used only for the exact same request ──────────────

class KeptAnswerTest(unittest.TestCase):
    def call(self, fake, keep, text="¿Qué se decidió?", model="gemini-flash-latest"):
        payload = {"contents": [{"role": "user", "parts": [{"text": text}]}]}
        counters = gemini.new_counters()
        def text_of(answer):
            return answer["candidates"][0]["content"]["parts"][0]["text"]

        return gemini.call_checked(gemini.model_url(fake.endpoint, model), KEY, payload, text_of, 0.01, "x", (),
                                   lambda s: None, counters, 1.0, keep=keep), counters

    def test_the_same_request_is_not_paid_twice_and_any_other_is(self):
        with tempfile.TemporaryDirectory() as tmp, FakeGemini([test_summary.returning("Uno.")] * 4) as fake:
            keep = Path(tmp) / gemini.KEPT_DIR
            first, paid = self.call(fake, keep)
            again, unpaid = self.call(fake, keep)
            self.assertEqual((first, again, len(fake.requests), unpaid["spent"], unpaid["attempts"]),
                             ("Uno.", "Uno.", 1, 0.0, 0))
            self.call(fake, keep, text="¿Qué se decidió?.")
            self.call(fake, keep, model="gemini-pro-latest")
            self.assertEqual(len(fake.requests), 3)
            self.assertEqual(len(list(keep.glob("*.json"))), 3)

    def test_a_kept_answer_that_no_longer_passes_the_check_is_paid_again(self):
        with tempfile.TemporaryDirectory() as tmp, FakeGemini([test_summary.returning("Uno.")] * 2) as fake:
            keep = Path(tmp) / gemini.KEPT_DIR
            self.call(fake, keep)
            for kept in keep.glob("*.json"):
                kept.write_text("{not json", encoding="utf-8")
            self.call(fake, keep)
            self.assertEqual(len(fake.requests), 2)

    def test_a_reading_cut_at_its_last_batch_pays_only_that_batch_again(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as tmp:
            frames = Path(tmp) / "frames"
            frames.mkdir()
            for n in (1, 2, 3):
                Image.new("RGB", (64, 36), (60 * n, 30, 30)).save(frames / f"frame_00{n}_t00-00-0{n}.jpg")
            options = dict(retry_delays=(), sleep=lambda s: None, chunk_size=1)
            with FakeGemini([answer_for, answer_for, 400]) as fake:
                with self.assertRaises(gemini.ReadingError):
                    gemini.read_frames(frames, KEY, endpoint=fake.endpoint, **options)
            with FakeGemini() as fake:
                gemini.read_frames(frames, KEY, endpoint=fake.endpoint, **options)
                self.assertEqual([r["labels"] for r in fake.requests], [["[FRAME 3] frame_003_t00-00-03.jpg"]])


# ── AC06 and AC07: the application keeps what was paid ───────────────────────

class KeptRunTest(Processing):
    def script(self):
        return [lambda first, count: answer_for(first, count),
                test_summary.returning(test_summary.summary_text("es", "requirements"))]

    def processing(self):
        folder = self.data / self.project / library.PROCESSING_DIR
        return sorted(p.name for p in folder.iterdir()) if folder.is_dir() else []

    def results(self):
        folder = self.data / self.project / library.RESULTS_DIR
        return sorted(p.name for p in folder.iterdir()) if folder.is_dir() else []

    def fail_at_the_report(self, **fields):
        with mock.patch("meetingtool.report.document.build_report",
                        side_effect=document.ReportError("report.no_summary", summary="x", folder="y")):
            return self.process(**fields)

    def test_a_report_that_fails_keeps_the_reading_and_the_summary_and_the_next_run_pays_nothing(self):
        failed = self.fail_at_the_report()
        self.assertEqual((failed["state"], failed["failed_stage_name"]), ("failed", "report"))
        paid = len(self.fake.requests)
        self.assertEqual(paid, 2)  # the reading and the summary
        self.assertEqual(failed["kept"], {"run": self.processing()[0], "paid_usd": round(failed["spent_usd"], 4)})
        self.assertEqual(store.list_meetings(self.data, self.project), [])
        self.assertEqual(self.results(), [])
        done = self.process()
        self.assertEqual(done["state"], "done", done["error"])
        self.assertEqual(len(self.fake.requests), paid, "the second run paid again")
        self.assertEqual(done["spent_usd"], 0)
        self.assertEqual(self.processing(), [])
        meeting = store.list_meetings(self.data, self.project)[0]
        self.assertEqual(meeting["folder"], f"{library.RESULTS_DIR}/{failed['kept']['run']}")
        self.assertFalse((self.data / self.project / meeting["folder"] / jobs.KEPT_RECORD).exists())

    def test_a_save_that_fails_keeps_what_was_paid_and_leaves_no_result(self):
        with mock.patch.object(store, "add_meeting", side_effect=store.ProjectError("projects.needs_title")):
            failed = self.process(meeting_type="")
        self.assertEqual(failed["failed_stage_name"], "saving")
        self.assertEqual(self.results(), [])
        self.assertEqual(len(self.processing()), 1)
        self.assertIsNotNone(failed["kept"])
        done = self.process(meeting_type="")
        self.assertEqual(done["state"], "done", done["error"])
        self.assertEqual(len(self.fake.requests), 2)

    def test_another_transcript_is_another_meeting_and_pays(self):
        self.fail_at_the_report()
        other = self.tmp / "otra.docx"
        write_teams_docx(other, test_summary.SPANISH[:-1])
        self.fake.script[:] = self.script()
        self.transcript = other
        done = self.process()
        self.assertEqual(done["state"], "done", done["error"])
        self.assertEqual(len(self.fake.requests), 4)
        self.assertEqual(len(self.processing()), 1, "the first meeting's kept run stays")

    def test_a_run_that_paid_nothing_leaves_nothing(self):
        self.video.write_bytes(b"this is not a video")
        failed = self.process()
        self.assertEqual((failed["failed_stage_name"], failed["kept"]), ("frames", None))
        self.assertEqual(self.processing(), [])

    def test_a_kept_run_survives_a_restart_and_a_cut_one_with_nothing_paid_does_not(self):
        failed = self.fail_at_the_report()
        cut = self.data / self.project / library.PROCESSING_DIR / "2026-09-25-cortada-abc123"
        cut.mkdir()
        (cut / "transcript.docx").write_bytes(b"client data")
        jobs.clear_leftovers(self.data)
        self.assertEqual(self.processing(), [failed["kept"]["run"]])

    def test_a_save_cut_half_way_is_settled_at_the_next_start(self):
        # The process died after the run's folder became a result: with no
        # meeting naming it, it goes back to being a kept run; with one, it
        # stays a result and stops being marked as kept.
        failed = self.fail_at_the_report()
        run = failed["kept"]["run"]
        results = self.data / self.project / library.RESULTS_DIR
        results.mkdir()
        (self.data / self.project / library.PROCESSING_DIR / run).rename(results / run)
        jobs.clear_leftovers(self.data)
        self.assertEqual((self.processing(), self.results()), ([run], []))
        (self.data / self.project / library.PROCESSING_DIR / run).rename(results / run)
        store.add_meeting(self.data, self.project, "Sesión de dudas", "2026-09-25",
                          meeting_folder=f"{library.RESULTS_DIR}/{run}")
        jobs.clear_leftovers(self.data)
        self.assertEqual((self.processing(), self.results()), ([], [run]))
        self.assertFalse((results / run / jobs.KEPT_RECORD).exists())

    def test_the_project_lists_it_in_both_languages_and_it_can_be_discarded(self):
        failed = self.fail_at_the_report()
        run = failed["kept"]["run"]
        page = self.page(f"/p/{self.project}")
        self.assertIn(texts.Message("app.kept.title").text("es"), page)
        self.assertIn(f'value="{run}"', page)
        company.set_language(self.data, "en")
        self.assertIn(texts.Message("app.kept.title").text("en"), self.page(f"/p/{self.project}"))
        self.assertEqual(self.api("/api/kept/discard", {"project": self.project, "run": run}), {"discarded": True})
        self.assertEqual(self.processing(), [])
        self.assertNotIn(texts.Message("app.kept.title").text("en"), self.page(f"/p/{self.project}"))
        self.api("/api/kept/discard", {"project": self.project, "run": run}, expect=404)
        self.api("/api/kept/discard", {"project": self.project, "run": "../../x"}, expect=404)
        self.api("/api/kept/discard", {"project": 3, "run": run}, expect=404)

    def test_nothing_is_discarded_while_a_meeting_is_processed(self):
        failed = self.fail_at_the_report()
        with mock.patch.object(self.app.runner, "running", return_value=object()):
            self.api("/api/kept/discard", {"project": self.project, "run": failed["kept"]["run"]}, expect=400)
        self.assertEqual(self.processing(), [failed["kept"]["run"]])


class KeptRegisterTest(Processing):
    transcript_blocks = test_qa.SPANISH

    def script(self):
        return [test_qa.json_answer(test_qa.verbal())] * 2

    def test_the_register_paid_before_a_failed_report_is_not_paid_again(self):
        with mock.patch("meetingtool.report.document.build_report",
                        side_effect=document.ReportError("report.no_summary", summary="x", folder="y")):
            failed = self.process(with_recording=False, format="qa")
        self.assertEqual(failed["failed_stage_name"], "report")
        kept = self.data / self.project / library.PROCESSING_DIR / failed["kept"]["run"] / qa.PARTS_DIR
        self.assertTrue(list(kept.glob("part-*.json")))
        done = self.process(with_recording=False, format="qa")
        self.assertEqual(done["state"], "done", done["error"])
        self.assertEqual(len(self.fake.requests), 1)

    def test_a_save_that_meets_an_unreadable_record_ends_failed_and_leaves_no_result(self):
        store.add_meeting(self.data, self.project, "Relevamiento", "2026-09-10", summary="Antes.")
        record = next((self.data / self.project / "meetings").glob("*/meeting.json"))
        record.write_bytes(record.read_bytes()[:40])
        failed = self.process(with_recording=False, format="qa")
        self.assertEqual((failed["state"], failed["failed_stage_name"]), ("failed", "saving"))
        self.assertIn(str(record), failed["error"])
        self.assertIsNone(self.app.runner.running())
        results = self.data / self.project / library.RESULTS_DIR
        self.assertEqual(list(results.iterdir()) if results.is_dir() else [], [])
        self.assertIsNotNone(failed["kept"])
        self.assertEqual(len(list((self.data / self.project / "meetings").glob("*/meeting.json"))), 1)


if __name__ == "__main__":
    unittest.main()
