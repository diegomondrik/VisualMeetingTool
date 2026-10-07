# WI26: existing tests that changed, and the rule that changed each

WI26-AC03: every test that existed before passes, or is named here with the rule of this work item that changed it.
Base: `c7b3b88` (the work item's contract and plan, on `41f6722`, main). `git diff c7b3b88 -- tests/` shows the
changes.

**No test that existed before changed.** Every assertion of every earlier test is as it was, and all of them pass.

The new tests:

- `tests/test_transcript_encodings.py` (new file, `TextEncodingsTest`, needs nothing outside this repository, so the
  CI runs it): the same transcript in the three shapes the application reads, saved in five encodings (UTF-8, UTF-8
  with a mark, UTF-16 LE and BE with a mark, cp1252) and three line endings (LF, CRLF, a lone CR), read by both
  readers to the same turns; the first turn not lost to the mark; one timed line with a mark read, not refused; a
  line of 20,000 spaces read in under a second; bytes no encoding reads refused as `transcript.unreadable`; an
  empty file or only a mark refused as having no timed line.
- `TranscripcionDeTexto` (INGOL's, appended to `tests/test_d1_barrido.py`, code unchanged; needs the kits).
  `docs/evidence/01M4BGTP1940T4ASG54GC323WT/compare_pilot_tests.py` checks it, and the constant `TEXTO` and the
  function `turnos` it uses, against INGOL's file.

Not tests, but changed with them:

- `tests/test_d1_barrido.py`: inside the guard that skips the file without the kits it also imports `variantes`
  (what `TranscripcionDeTexto` uses), and it imports `transcript` as `transcripcion`, defines `TEXTO` and `turnos`,
  and its header names the new class. The classes of WI20 and WI25 are as they were.
- `meetingtool/texts/es.py`: `transcript.unreadable` no longer says that the transcript "tiene que ser un texto
  UTF-8": it says UTF-8, UTF-16 or the Windows one. `tests/test_texts.py` checks every entry and raise without a
  change.
