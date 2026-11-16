# The INGOL kit case "cifra-inventada", brought up to date (WI-2.0.0)

2026-11-13, at the owner's request ("podes actualizar ingol aca?").

`tests/test_d1_barrido.py::TrazabilidadDelRegistro` is a copy of a class of INGOL's
D1 pilot tests (WI25). Its case `cifra-inventada` expected the question register to
**refuse** a figure nobody said. Since 1.0.0 the owner's decision (WI100-AC02) is that
such a figure does not refuse the meeting: it is written as `[VERIFICAR: «…»]`, in red,
for a person to correct. The case had been failing on `main` since then (checked on
9d6e8e4 in a throwaway worktree, before any change of this work item); the three kit
tests were skipped in the 1.0.0 suite run, which is why nobody saw it.

What changed: the case now expects the register to be delivered, and fails if the
figure is written anywhere outside a `[VERIFICAR]` mark, or if no mark is written at
all. The invented year is still refused. With
`PYTHONPATH=<home>/.claude/ingol-kits/python`, `python -m unittest tests.test_d1_barrido`
runs 7 tests, OK.

Consequence, on purpose: `docs/evidence/01M4B3HE2AVWM7CEPPNRWS9SFY/compare_pilot_tests.py`
(WI25's proof that the copy was INGOL's, unchanged) now reports
`TrazabilidadDelRegistro: DIFFERS` against INGOL's
`docs/work-items/dev-capabilities/evidence/d1/ac05-base-revisada/pruebas/`. That is
the record of a closed INGOL work item and is not changed from here; bringing INGOL's
own copy up to date, if wanted, is INGOL's work.
