# WI22: existing tests that changed, and the rule that changed each

WI22-AC06: every test that existed before passes, or is named here with the
rule of this work item that changed it. Base: `59343c9` (main), the work item's
contract and plan at `927b2c8`. `git diff 927b2c8 -- tests/test_report.py` shows the change; the other
existing test files are untouched.

One test changed, and no assertion in it:

| Test | What changed |
|---|---|
| `test_report.ReviewCorrectionsTest.test_p1_1_dde_fields_are_found_even_when_split` | It gave `active_content` three loose fragments of XML (`<w:r>...</w:r>`, `<w:fldSimple .../>`), with the prefix `w:` bound nowhere: fine for a filter that looked for text in the bytes, not for one that reads each part as XML (the rule of WI22: a part that is not readable XML is refused naming it). Each fragment is now wrapped in a part that binds the prefix (`word_part`, new, in the same file). The three expected results are the same as before: `a DDEAUTO field` for the field split across runs, `a DDE field` for the simple one, and none for the harmless pair. |

Not tests, but changed with them:

- The message `report.active.unreadable` (the list of messages, in both languages) said
  "unreadable relationships"; it now says the part is not readable XML, since every XML part is read and not only
  the relationships. No test pinned its text (`tests/test_texts.py` checks the list's structure, which holds).
- `docs/limitations/reproduce.py`, entry `WI20-P3-6` ("`test_d1_*` without the kits: the files that need them are
  skipped"): the run now counts 7 tests instead of 4, the three of `tests/test_d1_r02_plantilla.py` being
  ones that need no kits (it is the fifth file); its register row says so. The state stays `open`.
