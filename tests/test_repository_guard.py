import subprocess
import tempfile
import unittest
from pathlib import Path

from meetingtool import repository_guard

REPOSITORY = Path(__file__).resolve().parent.parent


def git(repository, *args):
    subprocess.run(["git", "-C", str(repository), *args], check=True, capture_output=True)


class RepositoryGuardTest(unittest.TestCase):
    """WI01-AC02."""

    def test_every_meeting_data_extension_is_rejected_in_any_case(self):
        paths = [
            "a.mp4", "b.MOV", "c.m4a", "d.Wav", "e.docx", "f.VTT",
            "nested/dir/report_20260925.DOCX",
            "notes.md", "requirements.txt", "meetingtool/__init__.py",
        ]
        self.assertEqual(
            repository_guard.meeting_data_paths(paths),
            sorted(["a.mp4", "b.MOV", "c.m4a", "d.Wav", "e.docx", "f.VTT", "nested/dir/report_20260925.DOCX"]),
        )

    def test_guard_names_a_tracked_recording_in_a_throwaway_repository(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            git(repository, "init", "-q")
            (repository / "README.md").write_text("clean\n")
            (repository / "Client Meeting 0925.MP4").write_bytes(b"not really a video")
            git(repository, "add", "-f", "README.md", "Client Meeting 0925.MP4")
            self.assertEqual(repository_guard.check_repository(repository), ["Client Meeting 0925.MP4"])

    def test_this_repository_tracks_no_meeting_data(self):
        self.assertEqual(repository_guard.check_repository(REPOSITORY), [])


if __name__ == "__main__":
    unittest.main()
