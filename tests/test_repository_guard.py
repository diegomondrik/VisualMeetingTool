import subprocess
import tempfile
import unittest
from pathlib import Path

from meetingtool import repository_guard

REPOSITORY = Path(__file__).resolve().parent.parent

ORDINARY_PATHS = [
    "README.md",
    "pyproject.toml",
    "requirements.txt",
    "meetingtool/__init__.py",
    "meetingtool/report_writer.py",
    "meetingtool/projects/store.py",
    "meetingtool/frames/extract.py",
    "tests/frames/test_extract.py",
    "docs/evidence/X/local-test-run.txt",
    ".ingol/work-items/X/approvals/Y.json",
]


def git(repository, *args):
    return subprocess.run(["git", "-C", str(repository), *args], check=True, capture_output=True, text=True)


class GuardRulesTest(unittest.TestCase):
    """WI02-AC01."""

    def test_every_listed_extension_is_rejected_in_any_case(self):
        for extension in sorted(repository_guard.MEETING_DATA_EXTENSIONS):
            for path in (f"a{extension}", f"deep/dir/b{extension.upper()}"):
                with self.subTest(path=path):
                    self.assertTrue(repository_guard.is_meeting_data(path))

    def test_the_old_pipeline_output_names_are_rejected(self):
        for path in (
            "report_20260925.md",
            "notes/REPORT_client.md",
            "handoff_part1.json",
            "transcript.txt",
            "Transcript_half2.TXT",
        ):
            with self.subTest(path=path):
                self.assertTrue(repository_guard.is_meeting_data(path))

    def test_everything_under_a_root_data_folder_is_rejected(self):
        for path in ("meetings/2026-09-25/notes.md", "projects/acme/project.json", "Frames/f1.txt"):
            with self.subTest(path=path):
                self.assertTrue(repository_guard.is_meeting_data(path))

    def test_ordinary_paths_are_accepted(self):
        self.assertEqual(repository_guard.meeting_data_paths(ORDINARY_PATHS), [])

    def test_the_contracted_extension_list_is_complete(self):
        contracted = {
            ".mp4", ".mov", ".mkv", ".webm", ".avi", ".wmv", ".m4v",
            ".m4a", ".wav", ".mp3", ".aac", ".ogg", ".flac", ".wma", ".opus",
            ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".tif", ".tiff", ".heic",
            ".vtt", ".srt",
            ".docx", ".doc", ".pdf", ".pptx", ".xlsx",
        }
        self.assertEqual(set(repository_guard.MEETING_DATA_EXTENSIONS), contracted)


class GuardOnRepositoriesTest(unittest.TestCase):
    """WI02-AC02."""

    def test_guard_names_one_tracked_file_per_rule_in_a_throwaway_repository(self):
        planted = ["Client Meeting 0925.MP4", "report_acme.md", "projects/acme/meeting.json"]
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            git(repository, "init", "-q")
            (repository / "README.md").write_text("clean\n")
            for relative in planted:
                target = repository / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text("not real meeting data\n")
            git(repository, "add", "-f", "README.md", *planted)
            self.assertEqual(repository_guard.check_repository(repository), sorted(planted))

    def test_this_repository_tracks_no_meeting_data(self):
        self.assertEqual(repository_guard.check_repository(REPOSITORY), [])


class GitignoreTest(unittest.TestCase):
    """WI02-AC03."""

    def ignored(self, path):
        result = subprocess.run(
            ["git", "-C", str(REPOSITORY), "-c", "core.ignorecase=false", "check-ignore", "-q", "--no-index", path],
            capture_output=True,
        )
        return result.returncode == 0

    def test_every_extension_is_ignored_in_two_letter_cases(self):
        for extension in sorted(repository_guard.MEETING_DATA_EXTENSIONS):
            for path in (f"a{extension}", f"deep/B{extension.upper()}"):
                with self.subTest(path=path):
                    self.assertTrue(self.ignored(path), f"{path} is not ignored")

    def test_root_data_folders_are_ignored(self):
        for folder in sorted(repository_guard.MEETING_DATA_ROOT_FOLDERS):
            with self.subTest(folder=folder):
                self.assertTrue(self.ignored(f"{folder}/x/file.json"))

    def test_a_code_folder_named_projects_below_the_root_is_not_ignored(self):
        self.assertFalse(self.ignored("meetingtool/projects/store.py"))


if __name__ == "__main__":
    unittest.main()
