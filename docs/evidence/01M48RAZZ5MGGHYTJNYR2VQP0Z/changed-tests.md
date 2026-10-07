# WI23: existing tests that changed, and the rule that changed each

WI23-AC04: every test that existed before passes, or is named here with the rule of
this work item that changed it. Base: `32700a1` (main), the work item's contract and
plan at `6adfc8f`. `git diff 6adfc8f -- tests/` shows the changes; the new tests are
all in `tests/test_allowed_fields.py` (a new file).

The rule that changed them: a template may hold only the fields of a short list
(`document.ALLOWED_FIELDS`), and every other field is refused naming it, where WI22
refused only the nine it knew to pull or run outside content. Four tests of WI22 held
something that is not on the list; each one changed in what it uses, not in what it
means to show, and no assertion was weakened. All four are in
`tests/test_template_filter.py`.

| Test | What changed |
|---|---|
| `FieldNameTest.test_the_fields_a_template_has_are_accepted` (and, through the same table, `test_the_accepted_ones_reach_the_report`) | The table `ACCEPTED` had `MERGEFIELD Import`, to show that the word `Import` in a data field's argument is not the `IMPORT` field. `MERGEFIELD` is refused now (the owner's decision: a citation manager's or a mail merge's fields are not needed in a template). The entry is `REF Import` (`REF` is on the list); it shows the same thing. |
| `FieldNameTest.test_the_words_around_the_name_are_not_the_name` | Same reason: `MERGEFIELD DDE` is `REF DDE`. The other three texts are the same. |
| `FieldFormsTest.test_a_field_name_inside_a_longer_word_is_not_a_field` | It accepted a field called `INCLUDED` (the name is a whole word: `INCLUDED` is not `INCLUDE`, and `HYPERLINK` is not `LINK`). `INCLUDED` is not on the list either, so it is refused now, as `a INCLUDED field` and not as `a INCLUDE field`: the assertion is that exact finding, which keeps showing the name is read whole. `HYPERLINK` is still accepted. |
| `HyperlinkTest.test_a_hyperlink_whose_address_another_field_builds_is_refused` | It built the address with a `QUOTE` field. `QUOTE` is refused now as a field of its own, so the template had two findings and the test asserted one. The address is built by a `DOCPROPERTY` field (on the list); the expected finding (`an address that another field builds`) is the same. |

Not tests, but changed with them:

- The messages `report.active` and `report.active_in_report` (both languages) take the list of allowed fields (a new
  piece of data, `allowed`) and say a template "may not hold" a field besides content loaded from outside; the
  sentence "load or run from outside" that tests look for is kept. The message of each field, `report.active.field`
  (`a {field} field`), is the same: WI22's tests pin its exact words.
- The README says which fields a template may hold.
- `docs/limitations/`: `WI22-P3-5` became `fixed`, and `WI23-P3-1` is new (see the register).

The tests of WI22 that are not named here pass as they were, with no change:
`tests/test_template_filter.py` (the rest), `tests/test_d1_r02_plantilla.py` and `tests/test_report.py`.
