"""Tests for meetingtool.frames. Every recording is synthesised at test time
with PyAV and deleted afterwards: this public repository commits no media."""

import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path
from unittest import mock

import av
import numpy as np
from PIL import Image

from meetingtool.frames import FramesError, extract_frames, signals
from meetingtool.frames import extract as extract_module
from meetingtool.frames.similarity import ssim

REPOSITORY = Path(__file__).resolve().parent.parent
WIDTH, HEIGHT, FPS = 320, 240, 4
STRIP = int(HEIGHT * 0.15)  # rows 0..STRIP-1 are the camera strip


def slide(color, box, bars):
    """A white slide below the strip with a coloured box and black bars."""
    image = np.full((HEIGHT, WIDTH, 3), 255, dtype=np.uint8)
    image[:STRIP] = 40  # a still camera strip
    (y0, x0, y1, x1) = box
    image[y0:y1, x0:x1] = color
    for y in bars:
        image[y:y + 4, 20:WIDTH - 20] = 0
    return image


SLIDE_A = slide((220, 30, 30), (60, 20, 140, 120), (170, 190, 210))
SLIDE_B = slide((30, 180, 30), (90, 110, 170, 210), (50, 200))
SLIDE_C = slide((30, 30, 220), (140, 200, 230, 310), (60, 80, 100, 120))
SLIDES = {"A": SLIDE_A, "B": SLIDE_B, "C": SLIDE_C}


def write_video(path, segments, size=(WIDTH, HEIGHT)):
    """segments: (image, seconds, move_the_camera_strip) in order."""
    container = av.open(str(path), "w")
    stream = container.add_stream("mpeg4", rate=FPS)
    stream.width, stream.height = size
    stream.pix_fmt = "yuv420p"
    stream.bit_rate = 4_000_000
    counter = 0
    for image, seconds, move_strip in segments:
        for _ in range(int(seconds * FPS)):
            frame_image = image.copy()
            if move_strip:
                frame_image[: int(size[1] * 0.15) - 2] = (counter * 37) % 256
            counter += 1
            for packet in stream.encode(av.VideoFrame.from_ndarray(frame_image, format="rgb24")):
                container.mux(packet)
    for packet in stream.encode():
        container.mux(packet)
    container.close()


def which_slide(jpeg_path):
    content = np.asarray(Image.open(jpeg_path).convert("RGB").resize((WIDTH, HEIGHT)))[STRIP:].astype(float)
    distances = {name: np.abs(content - image[STRIP:].astype(float)).mean() for name, image in SLIDES.items()}
    return min(distances, key=distances.get)


class Workspace(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.video = self.tmp / "synthetic.mp4"
        self.out = self.tmp / "frames-out"
        write_video(self.video, [
            (SLIDE_A, 6, False),
            (SLIDE_B, 6, False),
            (SLIDE_B, 6, True),   # only the camera strip changes
            (SLIDE_C, 6, False),
            (SLIDE_A, 6, False),  # a slide shown again later
        ])

    def tearDown(self):
        self._tmp.cleanup()


class SelectionTest(Workspace):
    """WI04-AC02."""

    def test_opening_slide_and_each_change_kept_camera_strip_and_repeats_ignored(self):
        result = extract_frames(self.video, self.out)
        slides = [which_slide(self.out / name) for name in result.kept]
        self.assertEqual(slides, ["A", "B", "C", "A"], result)
        for kept_at, change_at in zip(result.kept_times, (0, 6, 18, 24)):
            self.assertLessEqual(abs(kept_at - change_at), 3.5)
        self.assertGreater(result.discards["near_duplicate"], 0)

    def test_the_minimum_gap_holds_between_candidates(self):
        result = extract_frames(self.video, self.out)
        gaps = [b - a for a, b in zip(result.candidate_times, result.candidate_times[1:])]
        self.assertTrue(gaps and all(gap >= 3.0 for gap in gaps), gaps)
        self.assertGreater(result.discards["minimum_gap"], 0)

    def test_the_budget_caps_kept_frames_and_the_candidate_pool(self):
        result = extract_frames(self.video, self.out, budget=2)
        self.assertLessEqual(len(result.kept), 2)
        self.assertLessEqual(result.max_pool, 2)
        self.assertGreater(result.discards["budget"], 0)
        self.assertGreater(result.candidates, 2)

    def test_a_candidate_that_cannot_enter_a_full_pool_is_never_encoded(self):
        real_jpeg = extract_module._jpeg
        calls = []
        with mock.patch.object(extract_module, "_jpeg", lambda rgb: calls.append(1) or real_jpeg(rgb)):
            result = extract_frames(self.video, self.out, budget=1)
        self.assertLess(len(calls), result.candidates)

    def test_scoring_sees_only_the_content_area_below_the_camera_strip(self):
        shapes = []
        real_score = extract_module.composite_score

        def spy(prev_gray, curr_gray, *args):
            shapes.append(curr_gray.shape)
            return real_score(prev_gray, curr_gray, *args)

        with mock.patch.object(extract_module, "composite_score", spy):
            extract_frames(self.video, self.out)
        self.assertTrue(shapes)
        self.assertEqual({shape[0] for shape in shapes}, {HEIGHT - int(HEIGHT * 0.15)})


class SignalsTest(unittest.TestCase):
    """WI04-AC02, the ported scores."""

    def gray(self, image):
        return signals.to_gray(image[STRIP:])

    def test_zone_score_counts_changed_zones(self):
        a = self.gray(SLIDE_A)
        self.assertEqual(signals.zone_score(a, a.copy()), 0.0)
        local = a.copy()
        local[: a.shape[0] // 3, : a.shape[1] // 4] = 0  # one zone of twelve
        self.assertAlmostEqual(signals.zone_score(a, local), 1 / 12)
        self.assertGreater(signals.zone_score(a, self.gray(SLIDE_C)), 0.3)

    def test_edge_score_is_zero_for_the_same_image_and_positive_for_another(self):
        a = self.gray(SLIDE_A)
        self.assertEqual(signals.edge_score(a, a.copy()), 0.0)
        self.assertGreater(signals.edge_score(a, self.gray(SLIDE_C)), 0.0)

    def test_temporal_score_rewards_uncovered_segments(self):
        self.assertEqual(signals.temporal_score(5, 100, 10, []), 1.0)
        self.assertEqual(signals.temporal_score(5, 100, 10, [1]), 0.6)
        self.assertEqual(signals.temporal_score(5, 100, 10, [1, 2]), 0.3)
        self.assertEqual(signals.temporal_score(5, 100, 10, [1, 2, 3]), 0.1)
        self.assertEqual(signals.temporal_score(15, 100, 10, [1, 2, 3]), 1.0)


class SimilarityTest(unittest.TestCase):
    """WI04-AC02, the similarity function."""

    def test_identical_images_score_one_and_different_ones_less(self):
        a = SLIDE_A[STRIP:, :, 0]
        self.assertAlmostEqual(ssim(a, a.copy()), 1.0, places=9)
        self.assertLess(ssim(a, SLIDE_C[STRIP:, :, 0]), 0.95)
        noisy = np.clip(a.astype(int) + np.random.default_rng(1).integers(-60, 60, a.shape), 0, 255).astype(np.uint8)
        self.assertLess(ssim(a, noisy), 0.95)

    def test_images_of_different_shape_are_rejected(self):
        with self.assertRaises(ValueError):
            ssim(np.zeros((10, 10)), np.zeros((10, 11)))


class OutputTest(Workspace):
    """WI04-AC03."""

    def test_kept_frames_are_named_in_time_order_and_every_discard_is_logged(self):
        result = extract_frames(self.video, self.out)
        files = sorted(p.name for p in self.out.glob("frame_*.jpg"))
        self.assertEqual(files, result.kept)
        for index, name in enumerate(result.kept, start=1):
            self.assertRegex(name, rf"^frame_{index:03d}_t\d{{2}}-\d{{2}}-\d{{2}}\.jpg$")
        self.assertEqual(result.kept_times, sorted(result.kept_times))
        log = (self.out / "frames_discarded.log").read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(log), sum(result.discards.values()))
        reasons = {re.split(r"[ (]", line.split(" | ")[2])[0] for line in log}
        self.assertLessEqual(reasons, {"minimum_gap", "low_score", "budget", "near_duplicate"})

    def test_large_frames_are_saved_as_jpeg_within_1280x720(self):
        big = self.tmp / "big.mp4"
        large_a = np.asarray(Image.fromarray(SLIDE_A).resize((1920, 1080)))
        large_c = np.asarray(Image.fromarray(SLIDE_C).resize((1920, 1080)))
        write_video(big, [(large_a, 2, False), (large_c, 4, False)], size=(1920, 1080))
        result = extract_frames(big, self.out)
        self.assertTrue(result.kept)
        for name in result.kept:
            with Image.open(self.out / name) as image:
                self.assertEqual(image.format, "JPEG")
                self.assertLessEqual(image.size, (1280, 720))

    def test_an_output_folder_inside_a_git_work_tree_is_refused_before_writing(self):
        repository = self.tmp / "repo"
        subprocess.run(["git", "init", "-q", str(repository)], check=True)
        target = repository / "frames-out"
        with self.assertRaisesRegex(FramesError, "inside the git work tree"):
            extract_frames(self.video, target)
        self.assertFalse(target.exists())


class NoNetworkTest(Workspace):
    """WI04-AC04."""

    def test_extraction_opens_no_network_connection(self):
        def refuse(*args, **kwargs):
            raise AssertionError("extraction tried to open a network connection")

        with mock.patch.object(socket, "socket", refuse), mock.patch.object(socket, "create_connection", refuse):
            result = extract_frames(self.video, self.out)
        self.assertTrue(result.kept)


class NoFfmpegExecutableTest(Workspace):
    """WI04-AC01."""

    def test_the_command_line_extracts_frames_with_no_ffmpeg_on_the_path(self):
        folders = os.environ.get("PATH", "").split(os.pathsep)
        path = os.pathsep.join(f for f in folders if f and not shutil.which("ffmpeg", path=f))
        self.assertIsNone(shutil.which("ffmpeg", path=path))
        environment = dict(os.environ, PATH=path, PYTHONDONTWRITEBYTECODE="1")
        result = subprocess.run(
            [sys.executable, "-m", "meetingtool.frames", "--video", str(self.video), "--out", str(self.out)],
            cwd=REPOSITORY, env=environment, capture_output=True, text=True, encoding="utf-8",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("frames kept", result.stdout)
        self.assertTrue(list(self.out.glob("frame_*.jpg")))


class PackagingTest(unittest.TestCase):
    """WI04-AC06."""

    def test_runtime_packages_and_subpackage_discovery_are_declared(self):
        project = tomllib.loads((REPOSITORY / "pyproject.toml").read_text(encoding="utf-8"))
        names = {re.split(r"[<>=!~ ;\[]", dep, maxsplit=1)[0].lower() for dep in project["project"]["dependencies"]}
        self.assertLessEqual({"av", "numpy", "pillow"}, names)
        include = project["tool"]["setuptools"]["packages"]["find"]["include"]
        self.assertIn("meetingtool.*", include)
        self.assertIn("meetingtool", include)


if __name__ == "__main__":
    unittest.main()
