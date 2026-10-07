"""WI26-AC02: a text transcript is read the same whatever the encoding Windows saved it in.

The same transcript, in the three shapes the application reads, is saved as UTF-8, UTF-8 with a byte order mark
(Notepad), UTF-16 in both orders with a mark (Windows PowerShell 5.1's Out-File) and cp1252 (a Windows in Spanish or
English), each with Windows, Unix and old Mac line endings; both readers give the same turns, the first one
included, with the accents right. These tests need nothing outside this repository (the CI runs them); INGOL's
pilot test of the same defect is TranscripcionDeTexto, in test_d1_barrido.py, which needs its kits.
"""

import codecs
import tempfile
import time
import unittest
from pathlib import Path

from meetingtool.frames import transcript

# One meeting, in the three shapes: (the text, the turns it holds as (start seconds, speaker, words)).
TEAMS = ("Reunión de costos\nAna Pérez   0:04\n¿Cuánto cuesta el año?\nJuan Gómez   1:22\nMañana, señor.\n",
         [(4, "Ana Pérez", "¿Cuánto cuesta el año?"), (82, "Juan Gómez", "Mañana, señor.")])
BRACKET = ("[00:00:04] Ana: ¿Cuánto cuesta el año?\n[00:01:22] Juan: Mañana, señor.\n",
           [(4, "", "Ana: ¿Cuánto cuesta el año?"), (82, "", "Juan: Mañana, señor.")])
ALONE = ("Reunión de costos\n0:04\n¿Cuánto cuesta el año?\n\n1:22\nMañana, señor.\n",
         [(4, "", "¿Cuánto cuesta el año?"), (82, "", "Mañana, señor.")])
SHAPES = {"Teams, with names": TEAMS, "[HH:MM:SS]": BRACKET, "time alone": ALONE}

ENCODINGS = {
    "utf-8": lambda text: text.encode("utf-8"),
    "utf-8 with BOM": lambda text: codecs.BOM_UTF8 + text.encode("utf-8"),
    "utf-16 LE with BOM": lambda text: codecs.BOM_UTF16_LE + text.encode("utf-16-le"),
    "utf-16 BE with BOM": lambda text: codecs.BOM_UTF16_BE + text.encode("utf-16-be"),
    "cp1252": lambda text: text.encode("cp1252"),
}
LINE_ENDINGS = {"LF": "\n", "CRLF": "\r\n", "CR": "\r"}


class TextEncodingsTest(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.tmp = Path(self.folder.name)

    def save(self, data, name="transcript.txt"):
        path = self.tmp / name
        path.write_bytes(data)
        return path

    def test_the_same_transcript_gives_the_same_turns_in_every_encoding_and_line_ending(self):
        for shape, (text, turns) in SHAPES.items():
            for encoding, encode in ENCODINGS.items():
                for ending, newline in LINE_ENDINGS.items():
                    with self.subTest(shape=shape, encoding=encoding, line_ending=ending):
                        path = self.save(encode(text.replace("\n", newline)))
                        self.assertEqual(transcript.read_turns(path), turns)
                        self.assertEqual(transcript.read_blocks(path), [(start, said) for start, _, said in turns])
                        self.assertEqual(transcript.names_no_one(path), shape == "time alone")
                        self.assertEqual(transcript.read_text(path), text[:-1])

    def test_the_first_turn_is_not_lost_to_the_byte_order_mark(self):
        """The defect of WI05-P3-2: U+FEFF stayed before the first line, so that line was no timed line."""
        for shape, (text, turns) in SHAPES.items():
            with self.subTest(shape=shape):
                path = self.save(codecs.BOM_UTF8 + text.encode("utf-8"))
                self.assertEqual(transcript.read_turns(path)[0], turns[0])
                self.assertFalse(transcript.read_text(path).startswith("﻿"))

    def test_a_mark_written_twice_does_not_hide_the_first_turn(self):
        """WI26's review, P3-1: a file saved with its mark twice."""
        text, turns = SHAPES["[HH:MM:SS]"]
        for name, data in {"UTF-8, two marks": codecs.BOM_UTF8 * 2 + text.encode("utf-8"),
                           "UTF-16 LE, a mark inside": codecs.BOM_UTF16_LE + ("\ufeff" + text).encode("utf-16-le"),
                           }.items():
            with self.subTest(file=name):
                self.assertEqual(transcript.read_turns(self.save(data)), turns)

    def test_a_transcript_with_one_timed_line_and_a_mark_is_read_not_refused(self):
        one = {"Teams, with names": ("Ana Pérez   0:04\nHola, ¿cómo están?\n", [(4, "Ana Pérez", "Hola, ¿cómo están?")]),
               "[HH:MM:SS]": ("[00:00:04] Hola, ¿cómo están?\n", [(4, "", "Hola, ¿cómo están?")]),
               "time alone": ("0:04\nHola, ¿cómo están?\n", [(4, "", "Hola, ¿cómo están?")])}
        for shape, (text, turns) in one.items():
            for encoding, encode in ENCODINGS.items():
                with self.subTest(shape=shape, encoding=encoding):
                    self.assertEqual(transcript.read_turns(self.save(encode(text))), turns)

    def test_a_line_of_twenty_thousand_spaces_is_read_in_under_a_second(self):
        """The speaker-and-time pattern backtracked: 20,000 spaces took about 6 s, and a transcript is read three
        times per run."""
        spaces = " " * 20000
        # (the text, the start of its first turn)
        lines = {"a name, the spaces and a word": (f"[00:00:01] hola\nAna{spaces}x\n", 1),
                 "a name, the spaces and an end that is not a time": (f"[00:00:01] hola\nAna{spaces}0:0x\n", 1),
                 "a name, the spaces and a time": (f"hola\nAna{spaces}0:02\n", 2),
                 "only spaces": (f"[00:00:01] hola\n{spaces}\n", 1),
                 "spaces in the middle of the words": (f"[00:00:01] hola{spaces}chau\n", 1)}
        for name, (text, start) in lines.items():
            with self.subTest(line=name):
                path = self.save(text.encode("utf-8"))
                started = time.perf_counter()
                turns = transcript.read_turns(path)
                self.assertLess(time.perf_counter() - started, 1.0)
                self.assertEqual(turns[0][0], start)

    def test_a_speaker_followed_by_a_run_of_spaces_and_a_time_is_still_read(self):
        """The new pattern reads what the old one read: the name is what comes before the run, spaces inside it kept."""
        path = self.save("Ana María Pérez        12:09\nHola\n".encode("utf-8"))
        self.assertEqual(transcript.read_turns(path), [(729, "Ana María Pérez", "Hola")])

    def test_bytes_that_no_encoding_reads_are_refused_with_the_unreadable_message(self):
        unreadable = {"a byte cp1252 does not define": b"[00:00:01] hola \x81\x8d\n",
                      "UTF-8 with a mark and then an invalid byte": codecs.BOM_UTF8 + b"[00:00:01] hola \xff\n",
                      "UTF-16 cut in the middle of a character": codecs.BOM_UTF16_LE + "[00:00:01] hola".encode("utf-16-le") + b"\x00",
                      "UTF-16 with a lone surrogate": codecs.BOM_UTF16_BE + b"\xd8\x00\x00a"}
        for name, data in unreadable.items():
            with self.subTest(file=name):
                with self.assertRaises(transcript.TranscriptError) as raised:
                    transcript.read_turns(self.save(data))
                self.assertEqual(raised.exception.message.key, "transcript.unreadable")
                self.assertIn("UTF-16", raised.exception.message.text("es"))  # the message no longer asks for UTF-8 only
                with self.assertRaises(transcript.TranscriptError):
                    transcript.read_text(self.save(data))

    def test_an_empty_file_or_only_a_mark_has_no_timed_line(self):
        for name, data in {"empty": b"", "UTF-8 mark": codecs.BOM_UTF8, "UTF-16 mark": codecs.BOM_UTF16_LE}.items():
            with self.subTest(file=name):
                with self.assertRaises(transcript.TranscriptError) as raised:
                    transcript.read_turns(self.save(data))
                self.assertEqual(raised.exception.message.key, "transcript.no_timed_line")


if __name__ == "__main__":
    unittest.main()
