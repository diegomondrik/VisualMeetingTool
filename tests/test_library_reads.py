"""WI30: showing one meeting, or one file of it, reads that meeting only (the
external review of 2026-10-02, R09).

These tests need nothing but the project's libraries, so the CI runs them.
The reads are counted as the review counted them: Path.read_text is wrapped
(it still reads, and returns what it returned) and every call on a summary.md
is noted; builtins.open is wrapped the same way for the meeting.json records.
docs/evidence/01M4CM3YV88S4K9B9SR5ANTNVZ/mutations.py undoes each part of the
fix and shows a test here fails.
"""

import builtins
import contextlib
import datetime
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from PIL import Image

from meetingtool.app import library
from meetingtool.projects import store
from meetingtool.summary import writer
from tests.test_app import Running

FRAME = "frame_007_t00-12-34.jpg"
SUMMARY = f"## Resumen ejecutivo\n\nSe revisó el costo.\n\n## Qué se mostró\n\n- La planilla [{FRAME}]\n"
BAD_NAMES = ("..", ".", "A B", "x/y", "x\\y", "", "No-Slug", "a--b", "-a", "a-", "ñ", None, 7)


@contextlib.contextmanager
def counting_reads():
    """Yields what is read while it is open: the summary.md files read with
    Path.read_text and the meeting.json records opened. Nothing is changed in
    what the wrapped calls do."""
    seen = {"summaries": [], "records": []}
    read_text, opened = Path.read_text, builtins.open

    def counted_read_text(self, *args, **kwargs):
        if self.name == writer.OUTPUT_NAME:
            seen["summaries"].append(self)
        return read_text(self, *args, **kwargs)

    def counted_open(file, *args, **kwargs):
        if isinstance(file, (str, Path)) and Path(file).name == "meeting.json":
            seen["records"].append(Path(file))
        return opened(file, *args, **kwargs)

    with mock.patch.object(Path, "read_text", counted_read_text), mock.patch.object(builtins, "open", counted_open):
        yield seen


def write_result(folder, text=SUMMARY):
    """A result folder as the application leaves it: summary, one frame, a report."""
    folder.mkdir(parents=True)
    (folder / writer.OUTPUT_NAME).write_text(text, encoding="utf-8")
    Image.new("RGB", (16, 9), (20, 90, 200)).save(folder / FRAME)
    (folder / library.REPORT_NAME).write_bytes(b"PK\x03\x04 a report")


def add_meetings(data, project_id, count):
    """`count` meetings with a result each, a day apart; their records."""
    first = datetime.date(2026, 1, 1)
    records = []
    for number in range(count):
        day = (first + datetime.timedelta(days=number)).isoformat()
        folder = data / project_id / library.RESULTS_DIR / f"{day}-reunion-{number:02d}"
        write_result(folder)
        records.append(store.add_meeting(data, project_id, f"Reunión {number:02d}", day, summary=f"Reunión {number}",
                                         meeting_folder=f"{library.RESULTS_DIR}/{folder.name}"))
    return records


def add_loose(data, count):
    names = [f"d{number:03d}-suelta" for number in range(count)]
    for name in names:
        write_result(data / name)
    return names


class LibraryReadsTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.data = Path(self._tmp.name) / "data"
        self.data.mkdir()
        self.project = store.create_project(self.data, "Cermaq Sprint 3", "Cermaq")["id"]

    # ── WI30-AC01: what is read ──────────────────────────────────────────────

    def test_serving_the_report_or_an_image_of_one_of_twelve_meetings_reads_no_summary(self):
        records = add_meetings(self.data, self.project, 12)
        record = records[5]
        folder = self.data / self.project / record["folder"]
        for name in (FRAME, library.REPORT_NAME):
            with counting_reads() as seen:
                path = library.meeting_file(self.data, self.project, record["id"], name)
            self.assertEqual(path, folder / name)
            self.assertEqual(seen["summaries"], [], name)
            self.assertEqual(seen["records"], [folder.parent.parent / "meetings" / record["id"] / "meeting.json"])

    def test_the_meeting_page_reads_only_its_own_summary_and_record(self):
        records = add_meetings(self.data, self.project, 12)
        record = records[5]
        with counting_reads() as seen:
            entry = library.meeting(self.data, self.project, record["id"])
        folder = self.data / self.project / record["folder"]
        self.assertEqual(seen["summaries"], [folder / writer.OUTPUT_NAME])
        self.assertEqual(len(seen["records"]), 1)
        self.assertEqual(entry["record"], record)
        self.assertEqual(entry["result"]["summary"], SUMMARY)
        self.assertEqual((entry["result"]["frames"], entry["result"]["report"]), ([FRAME], True))

    def test_the_reads_do_not_grow_with_the_number_of_meetings(self):
        counted = {}
        for count in (12, 30):
            data = self.data.parent / f"data{count}"
            data.mkdir()
            project = store.create_project(data, "Cermaq", "Cermaq")["id"]
            record = add_meetings(data, project, count)[count // 2]
            with counting_reads() as seen:
                library.meeting_file(data, project, record["id"], FRAME)
                library.meeting_file(data, project, record["id"], library.REPORT_NAME)
            with counting_reads() as page:
                library.meeting(data, project, record["id"])
            counted[count] = (len(seen["summaries"]), len(seen["records"]), len(page["summaries"]), len(page["records"]))
        self.assertEqual(counted, {12: (0, 2, 1, 1), 30: (0, 2, 1, 1)})

    def test_serving_a_file_of_a_loose_result_reads_no_summary_and_the_page_reads_its_own(self):
        names = add_loose(self.data, 12)
        for name in (FRAME, library.REPORT_NAME):
            with counting_reads() as seen:
                path = library.loose_file(self.data, names[4], name)
            self.assertEqual(path, self.data / names[4] / name)
            self.assertEqual(seen["summaries"], [], name)
        with counting_reads() as seen:
            entry = library.loose_result(self.data, names[4])
        self.assertEqual(seen["summaries"], [self.data / names[4] / writer.OUTPUT_NAME])
        self.assertEqual(entry["name"], names[4])
        self.assertEqual(entry["result"]["summary"], SUMMARY)

    def test_the_reads_of_a_loose_result_do_not_grow_with_the_number_of_loose_results(self):
        counted = {}
        for count in (12, 30):
            data = self.data.parent / f"loose{count}"
            data.mkdir()
            names = add_loose(data, count)
            with counting_reads() as seen:
                library.loose_file(data, names[count // 2], FRAME)
            with counting_reads() as page:
                library.loose_result(data, names[count // 2])
            counted[count] = (len(seen["summaries"]), len(page["summaries"]))
        self.assertEqual(counted, {12: (0, 1), 30: (0, 1)})

    # ── WI30-AC02: another meeting's trouble, and what is still not found ───

    def break_two_meetings(self, records):
        """The first meeting's record is not JSON; the second's summary.md is
        not text. Returns the two."""
        broken_record, broken_summary = records[0], records[1]
        (self.data / self.project / "meetings" / broken_record["id"] / "meeting.json").write_bytes(b"\xff\xfe{ not json")
        (self.data / self.project / broken_summary["folder"] / writer.OUTPUT_NAME).write_bytes(b"## Resumen\n\n\xff\xfe\xc3(")
        return broken_record, broken_summary

    def test_a_broken_record_or_summary_of_another_meeting_does_not_stop_a_sound_one(self):
        records = add_meetings(self.data, self.project, 6)
        self.break_two_meetings(records)
        sound = records[4]
        folder = self.data / self.project / sound["folder"]
        entry = library.meeting(self.data, self.project, sound["id"])
        self.assertEqual((entry["record"], entry["result"]["summary"]), (sound, SUMMARY))
        self.assertEqual(library.meeting_file(self.data, self.project, sound["id"], FRAME), folder / FRAME)
        self.assertEqual(library.meeting_file(self.data, self.project, sound["id"], library.REPORT_NAME),
                         folder / library.REPORT_NAME)

    def test_a_meeting_whose_record_cannot_be_read_is_not_found_and_one_whose_summary_is_not_text_has_its_files(self):
        records = add_meetings(self.data, self.project, 6)
        broken_record, broken_summary = self.break_two_meetings(records)
        for call in (library.meeting_record, library.meeting):
            with self.assertRaises(library.NotFound):
                call(self.data, self.project, broken_record["id"])
        with self.assertRaises(library.NotFound):
            library.meeting_file(self.data, self.project, broken_record["id"], FRAME)
        folder = self.data / self.project / broken_summary["folder"]
        self.assertEqual(library.meeting_file(self.data, self.project, broken_summary["id"], FRAME), folder / FRAME)

    def test_a_record_missing_a_field_is_unreadable_as_it_is_for_the_project_page(self):
        record = add_meetings(self.data, self.project, 2)[0]
        path = self.data / self.project / "meetings" / record["id"] / "meeting.json"
        path.write_text('{"id": "%s", "title": "Sin fecha"}' % record["id"], encoding="utf-8")
        with self.assertRaises(store.ProjectError):
            store.list_meetings(self.data, self.project)
        with self.assertRaises(library.NotFound):
            library.meeting_record(self.data, self.project, record["id"])

    def test_a_broken_loose_result_does_not_stop_a_sound_one(self):
        names = add_loose(self.data, 4)
        (self.data / names[0] / writer.OUTPUT_NAME).write_bytes(b"\xff\xfe\xc3(")
        sound = names[2]
        self.assertEqual(library.loose_result(self.data, sound)["result"]["summary"], SUMMARY)
        self.assertEqual(library.loose_file(self.data, sound, FRAME), self.data / sound / FRAME)
        self.assertEqual(library.loose_file(self.data, names[0], FRAME), self.data / names[0] / FRAME)

    def test_an_unknown_or_ill_formed_identifier_is_not_found(self):
        record = add_meetings(self.data, self.project, 3)[1]
        pointing_at_a_real_one = [f"../meetings/{record['id']}", f"x/../{record['id']}", record["id"].upper(),
                                  record["id"] + "/", record["id"] + " ", record["id"] + "."]
        for bad in (*BAD_NAMES, *pointing_at_a_real_one, "2026-02-30-no-existe"):
            for call in (library.meeting_record, library.meeting):
                with self.assertRaises(library.NotFound, msg=f"{call.__name__} {bad!r}"):
                    call(self.data, self.project, bad)
            with self.assertRaises(library.NotFound, msg=f"meeting_file {bad!r}"):
                library.meeting_file(self.data, self.project, bad, FRAME)
        with self.assertRaises(library.NotFound):
            library.meeting(self.data, "no-existe", record["id"])
        with self.assertRaises(library.NotFound):
            library.meeting_file(self.data, "..", record["id"], FRAME)

    def test_an_empty_identifier_is_not_a_meeting_even_with_a_record_in_the_meetings_folder_itself(self):
        """The review's P3-2: "" is its own slug, so it built meetings/meeting.json."""
        record = add_meetings(self.data, self.project, 1)[0]
        meetings = self.data / self.project / "meetings"
        (meetings / "meeting.json").write_text(json.dumps({**record, "id": ""}), encoding="utf-8")
        self.assertIsNone(store.read_meeting(self.data, self.project, ""))
        with self.assertRaises(library.NotFound):
            library.meeting_record(self.data, self.project, "")

    def test_a_record_found_in_a_folder_that_is_not_called_as_its_id_is_not_found(self):
        record = add_meetings(self.data, self.project, 2)[0]
        meetings = self.data / self.project / "meetings"
        (meetings / record["id"]).rename(meetings / "otra-carpeta")
        for name in ("otra-carpeta", record["id"]):
            with self.assertRaises(library.NotFound, msg=name):
                library.meeting_record(self.data, self.project, name)

    def test_a_record_whose_own_id_is_not_a_slug_is_not_reached_by_that_name(self):
        """The name is checked before the path is built, not only against the record's id (a hand-edited record
        can say anything)."""
        record = add_meetings(self.data, self.project, 2)[0]
        odd = f"../meetings/{record['id']}"
        path = self.data / self.project / "meetings" / record["id"] / "meeting.json"
        path.write_text(json.dumps({**record, "id": odd}), encoding="utf-8")
        for call in (library.meeting_record, library.meeting):
            with self.assertRaises(library.NotFound):
                call(self.data, self.project, odd)
        with self.assertRaises(library.NotFound):
            library.meeting_file(self.data, self.project, odd, FRAME)

    def test_an_unknown_or_ill_formed_loose_name_is_not_found(self):
        names = add_loose(self.data, 2)
        (self.data / "sin-resumen").mkdir()
        (self.data / "sin-resumen" / "transcript.txt").write_text("[00:00:01] hola", encoding="utf-8")
        (self.data / "Con Espacio").mkdir()
        write_result(self.data / "Con-Mayuscula")
        for bad in (*[name for name in BAD_NAMES if isinstance(name, str)], "no-existe", "sin-resumen", "Con Espacio", "Con-Mayuscula", self.project,
                    f"../{names[0]}", f"{names[0]}/", names[0].upper(), "con-mayuscula"):
            with self.assertRaises(library.NotFound, msg=f"loose_result {bad!r}"):
                library.loose_result(self.data, bad)
            with self.assertRaises(library.NotFound, msg=f"loose_file {bad!r}"):
                library.loose_file(self.data, bad, FRAME)

    def test_a_folder_with_a_project_record_is_not_a_loose_result(self):
        add_meetings(self.data, self.project, 1)
        write_result(self.data / "con-proyecto")
        (self.data / "con-proyecto" / "project.json").write_text("{}", encoding="utf-8")
        with self.assertRaises(library.NotFound):
            library.loose_result(self.data, "con-proyecto")
        with self.assertRaises(library.NotFound):
            library.loose_file(self.data, "con-proyecto", FRAME)
        self.assertNotIn("con-proyecto", [entry["name"] for entry in library.loose(self.data)])

    def test_the_paths_served_are_a_frame_or_the_report_of_the_results_folder_and_nothing_else(self):
        record = add_meetings(self.data, self.project, 2)[0]
        folder = self.data / self.project / record["folder"]
        (folder / "run.json").write_text("{}", encoding="utf-8")
        for name in ("run.json", writer.OUTPUT_NAME, "../project.json", "..", "frame_7.jpg", "frame_007_t00-12-34.png",
                     "frame_999_t00-00-00.jpg", "", "sub/" + FRAME):
            with self.assertRaises(library.NotFound, msg=name):
                library.meeting_file(self.data, self.project, record["id"], name)
        names = add_loose(self.data, 1)
        (self.data / names[0] / "transcript.txt").write_text("hola", encoding="utf-8")
        for name in ("transcript.txt", writer.OUTPUT_NAME, "../project.json", "frame_999_t00-00-00.jpg"):
            with self.assertRaises(library.NotFound, msg=name):
                library.loose_file(self.data, names[0], name)

    def test_a_meeting_added_from_the_terminal_has_its_record_and_no_files(self):
        record = store.add_meeting(self.data, self.project, "Relevamiento", "2026-09-10", summary="Primero.")
        entry = library.meeting(self.data, self.project, record["id"])
        self.assertEqual((entry["record"], entry["result"]), (record, None))
        with self.assertRaises(library.NotFound):
            library.meeting_file(self.data, self.project, record["id"], FRAME)

    def test_a_record_naming_a_folder_outside_its_results_is_not_followed(self):
        write_result(self.data / "d181-suelta")
        record = store.add_meeting(self.data, self.project, "Falsa", "2026-09-26", meeting_folder="../d181-suelta")
        self.assertIsNone(library.meeting(self.data, self.project, record["id"])["result"])
        with self.assertRaises(library.NotFound):
            library.meeting_file(self.data, self.project, record["id"], FRAME)

    # ── WI30-AC02: the lists are as they were ────────────────────────────────

    def test_the_project_page_lists_every_meeting_with_its_result_as_before(self):
        records = add_meetings(self.data, self.project, 5)
        terminal = store.add_meeting(self.data, self.project, "Desde la terminal", "2025-12-31", summary="Sin carpeta.")
        listed = library.meetings(self.data, self.project)
        expected = [{"record": record, "result": library.result(library.meeting_folder(self.data, self.project, record))}
                    for record in store.list_meetings(self.data, self.project)]
        self.assertEqual(listed, expected)
        self.assertEqual([entry["record"]["id"] for entry in listed], [terminal["id"]] + [r["id"] for r in records])
        self.assertIsNone(listed[0]["result"])
        self.assertTrue(all(entry["result"]["summary"] == SUMMARY for entry in listed[1:]))

    def test_the_project_page_still_stops_on_a_broken_record_as_before(self):
        records = add_meetings(self.data, self.project, 3)
        (self.data / self.project / "meetings" / records[0]["id"] / "meeting.json").write_bytes(b"\xff{")
        with self.assertRaises(store.ProjectError):
            library.meetings(self.data, self.project)

    def test_the_home_page_lists_every_loose_result_with_its_result_as_before(self):
        names = add_loose(self.data, 4)
        (self.data / "sin-resumen").mkdir()
        write_result(self.data / "Con-Mayuscula")
        add_meetings(self.data, self.project, 1)
        listed = library.loose(self.data)
        self.assertEqual([entry["name"] for entry in listed], names)
        self.assertEqual(listed, [{"name": name, "result": library.result(self.data / name)} for name in names])
        self.assertEqual(library.loose(self.data / "no-existe"), [])


class ServerReadsTest(Running):
    """The same through the running application."""

    def setUp(self):
        super().setUp()
        self.project = self.new_project()
        self.records = add_meetings(self.data, self.project, 12)
        self.names = add_loose(self.data, 12)
        self.base = f"/p/{self.project}/m/{self.records[5]['id']}"

    def summaries_read_by(self, method, path):
        with counting_reads() as seen:
            status, _, _ = self.request(method, path)
        return status, len(seen["summaries"])

    def test_an_image_or_the_report_of_a_meeting_reads_no_summary_and_its_page_reads_one(self):
        self.assertEqual(self.summaries_read_by("GET", f"{self.base}/f/{FRAME}"), (200, 0))
        self.assertEqual(self.summaries_read_by("GET", f"{self.base}/f/{library.REPORT_NAME}"), (200, 0))
        self.assertEqual(self.summaries_read_by("GET", self.base), (200, 1))

    def test_an_image_of_a_loose_result_reads_no_summary_and_its_page_reads_one(self):
        self.assertEqual(self.summaries_read_by("GET", f"/r/{self.names[3]}/f/{FRAME}"), (200, 0))
        self.assertEqual(self.summaries_read_by("GET", f"/r/{self.names[3]}"), (200, 1))

    def test_opening_the_report_on_the_machine_reads_no_summary(self):
        with counting_reads() as seen:
            self.api("/api/open", {"target": f"{self.project}/{self.records[5]['id']}"})
            self.api("/api/open", {"target": self.names[3]})
        self.assertEqual(seen["summaries"], [])
        self.assertEqual(len(self.opened), 2)

    def test_a_broken_meeting_does_not_stop_the_others_and_is_itself_not_found(self):
        (self.data / self.project / "meetings" / self.records[0]["id"] / "meeting.json").write_bytes(b"\xff\xfe{")
        (self.data / self.project / self.records[1]["folder"] / writer.OUTPUT_NAME).write_bytes(b"\xff\xfe\xc3(")
        self.assertEqual(self.request("GET", f"{self.base}/f/{FRAME}")[0], 200)
        self.assertEqual(self.request("GET", self.base)[0], 200)
        broken = f"/p/{self.project}/m/{self.records[0]['id']}"
        self.assertEqual(self.request("GET", broken)[0], 404)
        self.assertEqual(self.request("GET", f"{broken}/f/{FRAME}")[0], 404)
        other = f"/p/{self.project}/m/{self.records[1]['id']}"
        self.assertEqual(self.request("GET", f"{other}/f/{FRAME}")[0], 200)

    def test_an_unknown_or_ill_formed_identifier_is_404(self):
        for bad in ("%2E%2E", "A%20B", "x%2Fy", "No-Existe", "2026-02-30-no-existe"):
            self.assertEqual(self.request("GET", f"/p/{self.project}/m/{bad}")[0], 404, bad)
            self.assertEqual(self.request("GET", f"/p/{self.project}/m/{bad}/f/{FRAME}")[0], 404, bad)
            self.assertEqual(self.request("GET", f"/r/{bad}")[0], 404, bad)
            self.assertEqual(self.request("GET", f"/r/{bad}/f/{FRAME}")[0], 404, bad)
        self.assertEqual(self.request("GET", f"/r/{self.project}")[0], 404)
