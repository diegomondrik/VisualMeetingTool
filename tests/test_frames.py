"""Tests for meetingtool.frames. Every recording is synthesised at test time
with PyAV and deleted afterwards: this public repository commits no media."""

import contextlib
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import tomllib
import unittest
import zipfile
from pathlib import Path
from unittest import mock

import av
import numpy as np
from PIL import Image

from meetingtool.frames import FramesError, extract_frames, signals, transcript
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

    def test_among_equal_scores_the_budget_keeps_the_earliest_as_the_original_did(self):
        tie = self.tmp / "tie.mp4"
        write_video(tie, [(SLIDE_A, 2, False), (SLIDE_B, 2, False), (SLIDE_C, 2, False)])
        scores = iter([0.5, 0.5, 0.7, 0.1, 0.1])  # samples at 1, 2, 3, 4, 5 s
        # The sample at 3 s repeats the one at 2 s; the check before the budget (WI05-AC01)
        # is switched off so this test still reaches the budget's tie-break.
        with mock.patch.object(extract_module, "composite_score", lambda *args: next(scores)), \
                mock.patch.object(extract_module, "_is_near_duplicate", lambda *args: False):
            result = extract_frames(tie, self.out, budget=2, fps_analyze=1.0, min_gap=0.0)
        self.assertEqual(result.kept_times, [1.0, 3.0])

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

    def test_a_full_hd_recording_is_compared_small_and_keeps_the_same_slides(self):
        """INGOL D-175: the signals see a copy at most 640 wide; the kept frames are full samples."""
        big = self.tmp / "full-hd.mp4"
        segments = [(np.asarray(Image.fromarray(image).resize((1920, 1080))), seconds, move)
                    for image, seconds, move in [(SLIDE_A, 6, False), (SLIDE_B, 6, False), (SLIDE_B, 6, True),
                                                 (SLIDE_C, 6, False), (SLIDE_A, 6, False)]]
        write_video(big, segments, size=(1920, 1080))
        widths = []
        real_score = extract_module.composite_score

        def spy(prev_gray, curr_gray, *args):
            widths.append(curr_gray.shape[1])
            return real_score(prev_gray, curr_gray, *args)

        with mock.patch.object(extract_module, "composite_score", spy):
            result = extract_frames(big, self.out)
        self.assertEqual(set(widths), {extract_module.ANALYSIS_WIDTH})
        self.assertEqual([which_slide(self.out / name) for name in result.kept], ["A", "B", "C", "A"], result)
        with Image.open(self.out / result.kept[0]) as image:
            self.assertEqual(image.size, (1280, 720), "the kept frame comes from the full sample")


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

    def test_a_url_is_refused_before_anything_opens_it(self):
        # FFmpeg is native code the socket patch cannot see; refusing anything but
        # a local file is what keeps it from opening a connection.
        with mock.patch.object(extract_module.av, "open", side_effect=AssertionError("av.open was called")):
            for source in ("https://example.com/meeting.mp4", "rtmp://example.com/live", str(self.tmp / "missing.mp4")):
                with self.subTest(source=source), self.assertRaisesRegex(FramesError, "not a local file"):
                    extract_frames(source, self.out)


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


class DuplicatesBeforeTheBudgetTest(Workspace):
    """WI05-AC01: a repeated screen cannot take the place of a distinct one."""

    def extract_long_a_then_b(self, check_before_budget=True):
        video = self.tmp / "long-a.mp4"
        write_video(video, [(SLIDE_A, 4, False), (SLIDE_B, 2, False)])
        scores = iter([0.9, 0.9, 0.9, 0.5, 0.1])  # samples at 1, 2, 3 s (A) and 4, 5 s (B)
        patches = [mock.patch.object(extract_module, "composite_score", lambda *args: next(scores))]
        if not check_before_budget:
            patches.append(mock.patch.object(extract_module, "_is_near_duplicate", lambda *args: False))
        with contextlib.ExitStack() as stack:
            for patch in patches:
                stack.enter_context(patch)
            return extract_frames(video, self.out, budget=2, fps_analyze=1.0, min_gap=0.0)

    def test_repeats_are_dropped_before_the_budget_so_every_slide_is_kept(self):
        result = self.extract_long_a_then_b()
        self.assertEqual([which_slide(self.out / name) for name in result.kept], ["A", "B"])
        self.assertEqual(result.discards["near_duplicate"], 2)
        log = (self.out / "frames_discarded.log").read_text(encoding="utf-8")
        self.assertEqual(log.count("near_duplicate (before the budget)"), 2)

    def test_the_old_order_loses_the_slide_so_this_test_can_fail(self):
        result = self.extract_long_a_then_b(check_before_budget=False)
        self.assertEqual([which_slide(self.out / name) for name in result.kept], ["A"])
        self.assertGreater(result.discards["budget"], 0)


def write_teams_docx(path, blocks):
    """A minimal Word file shaped like a Teams transcript: each paragraph is a
    line break, 'Speaker   M:SS', a line break, then the text."""
    paragraphs = "".join(
        f'<w:p><w:r><w:br/><w:t xml:space="preserve">{speaker}   {clock}</w:t><w:br/><w:t>{text}</w:t></w:r></w:p>'
        for speaker, clock, text in blocks
    )
    document = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
                f'<w:body><w:p><w:r><w:t>Meeting title</w:t></w:r></w:p>{paragraphs}</w:body></w:document>')
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("word/document.xml", document)


BLOCKS = [("Ana Pérez", "0:04", "Buen día a todos."),
          ("Juan Gómez", "1:22", "Fijate el total de la columna."),
          ("Ana Pérez", "1:02:03", "Es verdad, hay que volver a eso.")]


class TranscriptTest(Workspace):
    """WI05-AC02 and WI05-AC03."""

    def test_the_boost_is_whole_words_within_the_window_and_capped(self):
        references = transcript.VisualReferences([(100, "Mirá el total"), (500, "es verdad"), (900, "hay que volver")])
        self.assertEqual(references.times, [100])
        self.assertTrue(references.near(75))
        self.assertTrue(references.near(130))
        self.assertFalse(references.near(131))
        self.assertAlmostEqual(references.boost(0.5, 100), 0.62)
        self.assertEqual(references.boost(0.95, 100), 1.0)
        self.assertEqual(references.boost(0.5, 500), 0.5)
        self.assertTrue(transcript.has_visual_reference("vamos a VER el número"))
        self.assertFalse(transcript.has_visual_reference("la verdad, volver a revisar"))

    def test_a_teams_docx_and_a_timed_text_read_to_the_same_blocks(self):
        docx = self.tmp / "meeting.docx"
        write_teams_docx(docx, BLOCKS)
        text = self.tmp / "meeting.txt"
        text.write_text("\n".join(f"[{transcript._seconds(c) // 3600:02d}:{transcript._seconds(c) % 3600 // 60:02d}:"
                                  f"{transcript._seconds(c) % 60:02d}] {s}:\n{t}" for s, c, t in BLOCKS), encoding="utf-8")
        from_docx = transcript.read_blocks(docx)
        from_text = transcript.read_blocks(text)
        self.assertEqual([start for start, _ in from_docx], [4, 82, 3723])
        self.assertEqual([start for start, _ in from_text], [4, 82, 3723])
        self.assertEqual([transcript.has_visual_reference(t) for _, t in from_docx], [False, True, False])
        self.assertEqual([transcript.has_visual_reference(t) for _, t in from_text], [False, True, False])

    def test_a_sample_below_the_minimum_becomes_a_candidate_only_next_to_a_phrase(self):
        near = self.tmp / "near.txt"
        near.write_text("[00:00:05] Ana:\nfijate acá", encoding="utf-8")
        far = self.tmp / "far.txt"
        far.write_text("[00:10:00] Ana:\nfijate acá", encoding="utf-8")
        with mock.patch.object(extract_module, "composite_score", lambda *args: 0.1):
            without = extract_frames(self.video, self.out)
            too_far = extract_frames(self.video, self.out, transcript=far)
            boosted = extract_frames(self.video, self.out, transcript=near)
        self.assertEqual((without.candidates, too_far.candidates), (0, 0))
        self.assertGreater(boosted.candidates, 0)
        self.assertEqual(boosted.boosted_in, boosted.candidates)
        self.assertTrue(boosted.kept)

    def test_an_unreadable_transcript_is_refused_before_anything_is_written(self):
        broken = self.tmp / "broken.docx"
        broken.write_bytes(b"not a word file")
        untimed = self.tmp / "untimed.txt"
        untimed.write_text("hello\nno times here\n", encoding="utf-8")
        for source in (broken, untimed, self.tmp / "missing.docx"):
            with self.subTest(source=source.name), self.assertRaises(FramesError):
                extract_frames(self.video, self.out, transcript=source)
            self.assertFalse(self.out.exists())

    def test_the_command_line_accepts_a_transcript(self):
        docx = self.tmp / "meeting.docx"
        write_teams_docx(docx, BLOCKS)
        result = subprocess.run(
            [sys.executable, "-m", "meetingtool.frames", "--video", str(self.video), "--out", str(self.out),
             "--transcript", str(docx)],
            cwd=REPOSITORY, env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"),
            capture_output=True, text=True, encoding="utf-8",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("raised by the transcript", result.stdout)


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
