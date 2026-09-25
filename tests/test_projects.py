import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from meetingtool.projects import store

REPOSITORY = Path(__file__).resolve().parent.parent


class DataFolderTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.data = Path(self._tmp.name) / "data"
        self.assertIsNone(store.enclosing_git_work_tree(self.data), "the temporary folder must be outside git")

    def tearDown(self):
        self._tmp.cleanup()


class ProjectTest(DataFolderTestCase):
    """WI03-AC01."""

    def test_create_and_list_projects(self):
        record = store.create_project(self.data, "Acme Rollout — Fase 1", "Acme", "Planning rollout")
        store.create_project(self.data, "Beta", "Beta Corp")
        self.assertEqual(record["id"], "acme-rollout-fase-1")
        self.assertEqual([p["id"] for p in store.list_projects(self.data)], ["acme-rollout-fase-1", "beta"])

    def test_a_second_project_with_the_same_identifier_is_rejected(self):
        store.create_project(self.data, "Acme", "Acme")
        with self.assertRaisesRegex(store.ProjectError, "project acme already exists"):
            store.create_project(self.data, "ACME!", "Other")


class MeetingTest(DataFolderTestCase):
    """WI03-AC02."""

    def setUp(self):
        super().setUp()
        store.create_project(self.data, "Acme", "Acme")

    def test_meetings_are_listed_in_date_order_and_repeats_survive(self):
        store.add_meeting(self.data, "acme", "Status", "2026-09-20")
        store.add_meeting(self.data, "acme", "Kickoff", "2026-09-01")
        store.add_meeting(self.data, "acme", "Status", "2026-09-20")
        meetings = store.list_meetings(self.data, "acme")
        self.assertEqual([m["date"] for m in meetings], ["2026-09-01", "2026-09-20", "2026-09-20"])
        self.assertEqual({m["id"] for m in meetings[1:]}, {"2026-09-20-status", "2026-09-20-status-2"})

    def test_date_order_does_not_depend_on_the_file_system_listing_order(self):
        # Windows lists folders by name, and meeting ids start with their date,
        # so only a reversed listing (possible on Linux) shows the sort is real.
        for title, date in (("A", "2026-09-01"), ("B", "2026-09-10"), ("C", "2026-09-20")):
            store.add_meeting(self.data, "acme", title, date)
        real_iterdir = Path.iterdir
        with mock.patch.object(Path, "iterdir", lambda self: reversed(sorted(real_iterdir(self)))):
            dates = [m["date"] for m in store.list_meetings(self.data, "acme")]
        self.assertEqual(dates, ["2026-09-01", "2026-09-10", "2026-09-20"])

    def test_an_invalid_date_is_rejected(self):
        for bad in ("25/09/2026", "2026-13-01", "2026-9-1", ""):
            with self.subTest(date=bad), self.assertRaisesRegex(store.ProjectError, "not a valid YYYY-MM-DD"):
                store.add_meeting(self.data, "acme", "Status", bad)

    def test_a_meeting_for_a_missing_project_is_rejected(self):
        with self.assertRaisesRegex(store.ProjectError, "project nope does not exist"):
            store.add_meeting(self.data, "nope", "Status", "2026-09-20")


class KnowledgeTest(DataFolderTestCase):
    """WI03-AC03."""

    def test_the_knowledge_holds_every_meeting_earlier_first(self):
        store.create_project(self.data, "Acme", "Acme Inc", "ERP migration for finance")
        store.add_meeting(self.data, "acme", "Design review", "2026-09-15", "technical",
                          summary="Agreed on the data model.", key_points=["Keep one ledger", "Weekly sync"])
        first = store.knowledge_context(self.data, "acme")
        self.assertIn("Design review", first)
        store.add_meeting(self.data, "acme", "Kickoff", "2026-09-01", summary="Scope set.")
        text = store.knowledge_context(self.data, "acme")
        self.assertIn("ERP migration for finance", text)
        self.assertIn("Agreed on the data model.", text)
        self.assertIn("- Keep one ledger", text)
        self.assertLess(text.index("### 2026-09-01: Kickoff"), text.index("### 2026-09-15: Design review (technical)"))
        on_disk = (self.data / "acme" / "knowledge.md").read_text(encoding="utf-8")
        self.assertEqual(on_disk, text)


class DataFolderLocationTest(unittest.TestCase):
    """WI03-AC04."""

    def test_a_data_folder_inside_a_git_work_tree_is_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            subprocess.run(["git", "init", "-q", str(repository)], check=True)
            inside = repository / "client-data"
            with self.assertRaisesRegex(store.ProjectError, "inside the git work tree"):
                store.create_project(inside, "Acme", "Acme")
            self.assertFalse(inside.exists(), "nothing may be written before the refusal")

    def test_this_repository_is_refused_as_a_data_folder(self):
        with self.assertRaisesRegex(store.ProjectError, "inside the git work tree"):
            store.check_data_dir(REPOSITORY / "projects")

    def test_the_default_data_folder_is_outside_this_repository(self):
        previous = os.environ.pop(store.DATA_DIR_ENV, None)
        try:
            default = store.default_data_dir().resolve()
        finally:
            if previous is not None:
                os.environ[store.DATA_DIR_ENV] = previous
        self.assertNotIn(REPOSITORY, (default, *default.parents))

    def test_the_environment_variable_sets_the_data_folder(self):
        previous = os.environ.get(store.DATA_DIR_ENV)
        os.environ[store.DATA_DIR_ENV] = "somewhere-else"
        try:
            self.assertEqual(store.default_data_dir(), Path("somewhere-else"))
        finally:
            if previous is None:
                del os.environ[store.DATA_DIR_ENV]
            else:
                os.environ[store.DATA_DIR_ENV] = previous


class CommandLineTest(DataFolderTestCase):
    """WI03-AC05, test half."""

    def run_cli(self, *args):
        return subprocess.run(
            [sys.executable, "-m", "meetingtool.projects", "--data-dir", str(self.data), *args],
            cwd=REPOSITORY, capture_output=True, text=True,
        )

    def test_a_project_with_two_meetings_round_trips_through_the_command_line(self):
        self.assertEqual(self.run_cli("new", "--name", "Acme", "--client", "Acme Inc").stdout, "created project acme\n")
        second = self.run_cli("add-meeting", "--project", "acme", "--title", "Follow-up", "--date", "2026-09-22",
                              "--summary", "Closed two open items.", "--key-point", "Go-live 1 Oct")
        first = self.run_cli("add-meeting", "--project", "acme", "--title", "Kickoff", "--date", "2026-09-08")
        self.assertEqual((second.returncode, first.returncode), (0, 0), second.stderr + first.stderr)
        listing = self.run_cli("meetings", "--project", "acme").stdout.splitlines()
        self.assertEqual([line.split("\t")[2] for line in listing], ["Kickoff", "Follow-up"])
        knowledge = self.run_cli("knowledge", "--project", "acme").stdout
        self.assertIn("- Go-live 1 Oct", knowledge)
        self.assertEqual(self.run_cli("list").stdout, "acme\tAcme\tAcme Inc\n")

    def test_errors_exit_with_status_2_and_a_message(self):
        result = self.run_cli("meetings", "--project", "missing")
        self.assertEqual(result.returncode, 2)
        self.assertIn("error: project missing does not exist", result.stderr)


if __name__ == "__main__":
    unittest.main()
