"""Tests for meetingtool.reading. Gemini is a fake HTTP server on localhost:
no test reaches the network. Frames are generated at test time in a
temporary folder and deleted afterwards: this public repository commits no
media and no read text."""

import base64
import contextlib
import http.server
import io
import json
import subprocess
import sys
import tempfile
import threading
import unittest
import uuid
from pathlib import Path
from unittest import mock

from PIL import Image

from meetingtool.reading import credentials, gemini
from meetingtool.reading.__main__ import main

REPOSITORY = Path(__file__).resolve().parent.parent
KEY = "AIzaTEST-" + "k3y" * 10  # distinctive, so any leak is found


def answer_for(first, count, finish="STOP", skip=(), repeat=(), extra=0):
    blocks = []
    for n in range(first, first + count):
        if n in skip:
            continue
        blocks.append(f"[FRAME {n}]\n- Window/App: Excel\n- Key Data: row {n}: 1, 2, 3")
        if n in repeat:
            blocks.append(f"[FRAME {n}]\n- Content: uninformative")
    for n in range(first + count, first + count + extra):
        blocks.append(f"[FRAME {n}]\n- Content: uninformative")
    return {"candidates": [{"content": {"parts": [{"text": "\n\n".join(blocks)}]}, "finishReason": finish}],
            "usageMetadata": {"promptTokenCount": 1000 * count, "candidatesTokenCount": 100 * count,
                              "thoughtsTokenCount": 50 * count}}


class FakeGemini:
    """A local stand-in for the Gemini API. `script` is a list of responses:
    an int status (an error with a JSON message), or a callable taking the
    first frame number and the frame count and returning an answer. When the
    script runs out, every request gets a complete answer."""

    def __init__(self, script=()):
        self.script = list(script)
        self.requests = []
        fake = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                labels = [p["text"] for p in body["contents"][0]["parts"] if p.get("text", "").startswith("[FRAME ")]
                images = [p for p in body["contents"][0]["parts"] if "inline_data" in p]
                first = int(labels[0].split()[1].rstrip("]"))
                fake.requests.append({"path": self.path, "headers": {k.lower(): v for k, v in self.headers.items()},
                                      "body": body,
                                      "labels": labels, "images": images})
                step = fake.script.pop(0) if fake.script else (lambda f, c: answer_for(f, c))
                if isinstance(step, int):
                    self._send(step, {"error": {"code": step, "message": f"fake error {step}"}})
                else:
                    self._send(200, step(first, len(images)))

            def _send(self, status, data):
                raw = json.dumps(data).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.endpoint = f"http://127.0.0.1:{self.server.server_address[1]}/v1beta/models"
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *exc):
        self.server.shutdown()
        self.server.server_close()


class Workspace(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.frames = Path(self._tmp.name) / "frames-out"
        self.frames.mkdir()
        for n in range(1, 6):
            Image.new("RGB", (64, 36), (n * 40, 20, 20)).save(self.frames / f"frame_{n:03d}_t00-00-{n:02d}.jpg")
        self.sleeps = []

    def tearDown(self):
        self._tmp.cleanup()

    def read(self, fake, **kwargs):
        kwargs.setdefault("chunk_size", 2)
        return gemini.read_frames(self.frames, KEY, endpoint=fake.endpoint, sleep=self.sleeps.append, **kwargs)

    def output(self):
        return self.frames / gemini.OUTPUT_NAME


class ChunkingTest(Workspace):
    """WI07-AC01."""

    def test_frames_go_in_chunks_with_their_labels_and_the_answer_is_written_next_to_them(self):
        with FakeGemini() as fake:
            result = self.read(fake)
        self.assertEqual([len(r["images"]) for r in fake.requests], [2, 2, 1])
        self.assertEqual([r["labels"][0].split()[1] for r in fake.requests], ["1]", "3]", "5]"])
        first = fake.requests[0]
        self.assertEqual(first["path"], f"/v1beta/models/{gemini.MODEL}:generateContent")
        self.assertEqual(first["body"]["contents"][0]["parts"][0]["text"], gemini.PROMPT)
        self.assertEqual(first["body"]["generationConfig"]["maxOutputTokens"], gemini.MAX_OUTPUT_TOKENS)
        sent = base64.b64decode(first["images"][0]["inline_data"]["data"])
        self.assertEqual(sent, (self.frames / "frame_001_t00-00-01.jpg").read_bytes())
        self.assertEqual((result.frames, result.requests, result.attempts), (5, 3, 3))
        self.assertEqual((result.input_tokens, result.output_tokens, result.thinking_tokens), (5000, 500, 250))
        text = self.output().read_text(encoding="utf-8")
        self.assertEqual([n for n in range(1, 6) if f"[FRAME {n}]" in text], [1, 2, 3, 4, 5])
        self.assertIn("FRAME 5: frame_005_t00-00-05.jpg", text)
        self.assertEqual(self.sleeps, [])

    def test_the_default_is_seventy_frames_per_request(self):
        self.assertEqual(gemini.CHUNK_SIZE, 70)
        with FakeGemini() as fake:
            self.read(fake, chunk_size=gemini.CHUNK_SIZE)
        self.assertEqual([len(r["images"]) for r in fake.requests], [5])

    def test_a_frames_folder_inside_a_git_work_tree_is_refused_before_any_request(self):
        inside = REPOSITORY / "frames-test-never-created"
        with FakeGemini() as fake:
            with self.assertRaises(gemini.ReadingError) as caught:
                gemini.read_frames(inside, KEY, endpoint=fake.endpoint, sleep=self.sleeps.append)
        self.assertIn("inside the git work tree", str(caught.exception))
        self.assertEqual(fake.requests, [])


class IncompleteAnswerTest(Workspace):
    """WI07-AC02."""

    def assert_refused(self, bad, words):
        with FakeGemini([bad, bad]) as fake:
            with self.assertRaises(gemini.ReadingError) as caught:
                self.read(fake)
        self.assertIn(words, str(caught.exception))
        self.assertEqual(len(fake.requests), 2, "an incomplete answer is retried exactly once")
        self.assertFalse(self.output().exists())
        self.assertEqual(list(self.frames.glob("*.partial")), [])

    def test_a_missing_block_is_refused(self):
        self.assert_refused(lambda f, c: answer_for(f, c, skip={f + 1}), "missing [2]")

    def test_a_repeated_block_is_refused(self):
        self.assert_refused(lambda f, c: answer_for(f, c, repeat={f}), "repeated [1]")

    def test_a_block_for_a_frame_not_sent_is_refused(self):
        self.assert_refused(lambda f, c: answer_for(f, c, extra=1), "not sent [3]")

    def test_a_cut_answer_is_refused_even_with_every_block(self):
        self.assert_refused(lambda f, c: answer_for(f, c, finish="MAX_TOKENS"), "finishReason MAX_TOKENS")

    def test_an_incomplete_answer_followed_by_a_complete_one_succeeds(self):
        with FakeGemini([lambda f, c: answer_for(f, c, skip={f})]) as fake:
            result = self.read(fake)
        self.assertEqual((result.requests, result.attempts), (3, 4))
        self.assertTrue(self.output().exists())

    def test_a_failure_in_a_later_chunk_writes_nothing(self):
        bad = lambda f, c: answer_for(f, c, skip={f})  # noqa: E731
        with FakeGemini([lambda f, c: answer_for(f, c), bad, bad]) as fake:
            with self.assertRaises(gemini.ReadingError):
                self.read(fake)
        self.assertEqual(len(fake.requests), 3)
        self.assertFalse(self.output().exists())


class RetryTest(Workspace):
    """WI07-AC03."""

    def test_busy_and_rate_limited_are_retried_twice_with_pauses(self):
        with FakeGemini([503, 429]) as fake:
            result = self.read(fake)
        self.assertEqual(self.sleeps, list(gemini.RETRY_DELAYS))
        self.assertEqual(gemini.RETRY_DELAYS, (30.0, 60.0))
        self.assertEqual((result.requests, result.attempts), (3, 5))

    def test_three_failures_in_a_row_end_the_run_with_nothing_written(self):
        for status in (503, 429, 500):
            with self.subTest(status=status):
                self.sleeps.clear()
                with FakeGemini([status, status, status]) as fake:
                    with self.assertRaises(gemini.ReadingError) as caught:
                        self.read(fake)
                self.assertEqual(len(fake.requests), 3)
                self.assertIn(f"HTTP {status}", str(caught.exception))
                self.assertIn("nothing was written", str(caught.exception))
                self.assertFalse(self.output().exists())

    def test_any_other_error_ends_the_run_at_once(self):
        with FakeGemini([400]) as fake:
            with self.assertRaises(gemini.ReadingError) as caught:
                self.read(fake)
        self.assertEqual(len(fake.requests), 1)
        self.assertEqual(self.sleeps, [])
        self.assertIn("HTTP 400", str(caught.exception))

    def test_no_answer_at_all_is_retried_then_refused(self):
        with self.assertRaises(gemini.ReadingError) as caught:
            gemini.read_frames(self.frames, KEY, endpoint="http://127.0.0.1:9/v1beta/models", chunk_size=2,
                               sleep=self.sleeps.append)
        self.assertEqual(self.sleeps, list(gemini.RETRY_DELAYS))
        self.assertIn("no answer", str(caught.exception))


class KeyNeverShownTest(Workspace):
    """WI07-AC04."""

    def run_cli(self, fake, *args):
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = main(list(args), read_key=lambda: KEY, endpoint=fake.endpoint, sleep=self.sleeps.append)
        return code, stdout.getvalue() + stderr.getvalue()

    def test_the_key_goes_only_in_the_header(self):
        with FakeGemini([503, 503, 503, 400]) as fake:
            codes_and_outputs = [self.run_cli(fake, "read", "--frames", str(self.frames)),  # fails after retries
                                 self.run_cli(fake, "read", "--frames", str(self.frames)),  # 400 at once
                                 self.run_cli(fake, "read", "--frames", str(self.frames))]  # succeeds
        self.assertEqual([code for code, _ in codes_and_outputs], [2, 2, 0])
        for code, output in codes_and_outputs:
            self.assertNotIn(KEY, output)
            self.assertNotIn(KEY[:12], output)
        for request in fake.requests:
            self.assertEqual(request["headers"].get("x-goog-api-key"), KEY)
            self.assertNotIn(KEY, request["path"])
            self.assertNotIn("key=", request["path"])
            self.assertNotIn(KEY, json.dumps(request["body"]))
        for path in self.frames.iterdir():
            if path.suffix != ".jpg":
                self.assertNotIn(KEY, path.read_text(encoding="utf-8"))
        self.assertTrue(self.output().exists())

    def test_no_error_message_carries_the_key(self):
        for script in ([400], [503, 503, 503], [lambda f, c: answer_for(f, c, skip={f})] * 2):
            with FakeGemini(script) as fake:
                with self.assertRaises(gemini.ReadingError) as caught:
                    self.read(fake)
            self.assertNotIn(KEY, str(caught.exception))
            self.assertNotIn(KEY, repr(caught.exception.__cause__))


class KeyCommandsTest(Workspace):
    """WI07-AC05."""

    def cli(self, *args, **kwargs):
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = main(list(args), **kwargs)
        return code, stdout.getvalue(), stderr.getvalue()

    def test_with_no_key_saved_reading_says_how_to_save_one_and_sends_nothing(self):
        with FakeGemini() as fake:
            code, _, err = self.cli("read", "--frames", str(self.frames), read_key=lambda: None,
                                    endpoint=fake.endpoint, sleep=self.sleeps.append)
        self.assertEqual(code, 2)
        self.assertIn("python -m meetingtool.reading key set", err)
        self.assertEqual(fake.requests, [])

    def test_set_warns_about_billing_and_status_shows_only_the_length(self):
        saved = []
        code, out, _ = self.cli("key", "set", save_key=saved.append, ask_key=lambda: KEY)
        self.assertEqual((code, saved), (0, [KEY]))
        self.assertIn("billing enabled", out)
        self.assertNotIn(KEY, out)
        code, out, _ = self.cli("key", "status", read_key=lambda: KEY)
        self.assertEqual(out.strip(), f"A key is saved ({len(KEY)} characters).")
        code, out, _ = self.cli("key", "status", read_key=lambda: None)
        self.assertEqual(out.strip(), "No key is saved.")

    @unittest.skipUnless(sys.platform == "win32", "the key lives in the Windows Credential Manager")
    def test_a_key_round_trips_through_the_windows_credential_manager(self):
        target = f"VisualMeetingTool/test-{uuid.uuid4().hex}"
        try:
            self.assertIsNone(credentials.read_key(target))
            credentials.save_key("  " + KEY + "\n", target)
            self.assertEqual(credentials.read_key(target), KEY)
            credentials.save_key(KEY[::-1], target)
            self.assertEqual(credentials.read_key(target), KEY[::-1])
            self.assertTrue(credentials.delete_key(target))
            self.assertIsNone(credentials.read_key(target))
            self.assertFalse(credentials.delete_key(target))
        finally:
            with contextlib.suppress(credentials.CredentialError):
                credentials.delete_key(target)
        with self.assertRaises(credentials.CredentialError):
            credentials.save_key("   ", target)

    def test_reading_never_uses_the_network_in_this_suite(self):
        self.assertTrue(gemini.ENDPOINT.startswith("https://generativelanguage.googleapis.com/"))
        with mock.patch.object(gemini.urllib.request, "urlopen", side_effect=AssertionError("network")):
            with self.assertRaises(AssertionError):
                gemini.read_frames(self.frames, KEY, sleep=self.sleeps.append)


class CommandLineTest(unittest.TestCase):
    def test_the_module_runs_as_a_command(self):
        result = subprocess.run([sys.executable, "-m", "meetingtool.reading", "--help"], cwd=REPOSITORY,
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0)
        self.assertIn("key", result.stdout)


if __name__ == "__main__":
    unittest.main()
