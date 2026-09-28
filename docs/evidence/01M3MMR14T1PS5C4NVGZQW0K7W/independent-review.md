# Independent review of WI13 (01M3MMR14T1PS5C4NVGZQW0K7W), screen selection

Reviewer: `revisor-independiente` (INGOL), its own context, read-only, on
4553284 (base main 477ae6d). Its report is kept as written, in Spanish;
the correction that follows is the executor's.

## Qué leí

`git diff main...HEAD` (477ae6d..4553284, 5 commits, 13 archivos);
`contract.yaml`, `plan.yaml`; `mutations.py`, `mutations.txt`,
`existing-summaries-check.txt`, `real-run.txt`, `local-test-run.txt`
(cabecera y cola); `call_checked` en gemini.py, `check_summary`/`check_frames`/
`write_summary` en writer.py y `cited_frames` en document.py. No leí los
resúmenes reales del owner (datos de cliente fuera del repo) ni D-181/D-182/
D-173 (tomé su contenido del pedido).

## Qué ejecuté

- `python -m unittest discover -s tests`: **189 tests, OK** (coincide con
  `local-test-run.txt`: 189 OK, exit 0, de 6a07a67; 4553284 sólo agrega ese
  archivo, así que el código probado es el de HEAD).
- `git diff --name-only main...HEAD`: los 13 archivos están dentro de
  `affected_surfaces`; ninguna superficie cambiada sin declarar.
- `git diff 95c3d4d HEAD -- meetingtool`: desde el primer commit sólo cambió
  gemini.py, así que `FRAME_RANGE` es el mismo con el que se corrió AC03.
- `token_cost(88386, 9139+3584)` = 0,11400, coincide con los US$0,114 de
  `real-run.txt`; el peor caso de un intento da ≈US$0,125 (el "US$0.12" del
  aviso).
- Sonda propia de `check_frames` vs `cited_frames` con 33 casos (fuera del
  repo):
  - Tablas: `| [a] | - | [b] |`, `| [a] | a | [b] |`, `| [a] | [b] |`, filas
    con celdas `-`, listas con `-` en líneas separadas, `[a] – la tabla; [b]`
    → **aceptadas** (el `|` corta la coincidencia). Sin falsos positivos en
    tablas.
  - Falsos positivos: `[a] a [b] muestran`, `comparado [a] a [b]`,
    `[a] al [b]` → rechazados (el caso "a" está declarado en el contrato).
  - Falsos negativos (el rango llega al Word): `**[a]** a **[b]**` (negrita),
    `[a] -> [b]`, `[a] → [b]`, `[a] -- [b]`, `[a] (5:27) a [b]`,
    `entre [a], y [b]`, `between [a] and the [b]`, y `[a]\na [b]` (dos
    líneas, declarado).
  - Paridad resumen/reporte: coinciden en los 33 casos, incluido el de varias
    líneas (misma `writer.FRAME_RANGE` sobre `splitlines()`; ambos rechazan
    ante cualquier problema).

## Hallazgos

**P0 / P1:** ninguno.

**P2**

1. **El control de rangos se saltea con formato Markdown común.**
   Consecuencia: un resumen que escriba `**[a]** a **[b]**` o `[a] → [b]` se
   entrega y el Word muestra dos extremos que nadie eligió, justo el defecto
   de D-181. El contrato declara sólo "en dos líneas o en otras palabras", y
   el README dice que un rango "is refused" en general. `_NAMED` admite
   backticks pero no `**`; el guion no admite `->` ni `--`. Mitigante: el
   control primario es la regla en el pedido, y la corrida real no produjo
   rangos. Limitación conocida; no reabre el ciclo.

**P3**

2. **El contrato y el plan no reflejan el tope con el que se corrió.** AC04
   dice "budget US$0.15 … asked to raise to US$0.25" y el control del plan
   dice `--max-cost 0.15`; el intento 2 corrió con `--max-cost 0.50` (techo
   D-173) por indicación del owner, registrada en `real-run.txt`. El total
   (≈US$0,164) quedó bajo 0,25 igual. Consecuencia: quien audite AC04 contra
   el plan ve un tope que no se usó.
3. **AC03 figura como "deterministic" pero el script que produjo
   `existing-summaries-check.txt` no está commiteado.** Consecuencia: el
   conteo no se puede reproducir desde el repo, sólo aceptarse tal cual. Los
   veredictos coinciden con lo que afirma el contrato.
4. **Texto de cliente en consola.** El aviso de tope ahora incluye el texto
   del error del chequeo; en el caso `FRAME_LIKE` (y otros `check_*`) son hasta
   80 caracteres del resumen. Consecuencia: ese texto puede terminar en la
   consola en la parada por presupuesto y hay que redactarlo a mano antes de
   pegarlo en evidencia. No es una fuga nueva (ya salía en el segundo
   rechazo); la clave no puede aparecer.
5. **Redacción del aviso en "rechazo → red caída → tope".** Dice "the answer
   before was refused" aunque el intento inmediatamente anterior fue de red.
   Verdadero pero impreciso. Si el único fallo previo fue de red, `refused`
   queda vacío y no afirma nada falso.
6. **Falsos positivos declarados.** `[a] a [b] muestran` se rechaza; si se
   repite en los dos intentos, no se entrega nada y se paga el intento. Ya
   declarado.

## Veredicto

**LISTO PARA INTEGRAR, con limitaciones**: P2-1 y los P3 van a limitaciones
conocidas. Conviene que el README y la limitación del contrato mencionen
negrita y flechas.

## Corrección (executor, one pass by INGOL's review policy)

- **P2-1, corrected in code, not only declared:** `_NAMED` admits `*`, `**`,
  `_`, `__` around a name, and the connectors admit `->`, `→` and `--`. Four
  new range cases (bold, `->`, `→`, `--`) and two new non-range cases (two
  bold names joined by "y"; a table row with a `-` cell) in the tests; a new
  mutation (bold names not read as a range) is detected. Run again on the
  five real summaries, the corrected pattern found **three bold ranges in
  WI09's summary** (`**[a]** a **[b]**`), the one behind the first Word
  report the owner judged, which the first pattern had let through: AC03 now
  refuses four and accepts one. The forms still not caught (text between a
  name and the connector, a comma before "y", "the" before the second name
  in "between", two lines, other words) are in the contract's limitations,
  and the README now says what is checked and that the rest is asked of
  Gemini.
- **P3-2:** AC04 in the contract and its control in the plan now say what
  was run: US$0.15, stopped before the retry, then US$0.50 by D-182.
- **P3-3:** `existing_summaries_check.py` is committed and produced the
  current `existing-summaries-check.txt`.
- **P3-4, P3-5, P3-6:** in the contract's known limitations.

## Re-verification (reviewer, same context, on dbc04eb)

- Suite: 189 tests OK (the new cases are subtests).
- Its 33-case probe plus 19 new cases against the new pattern: bold, italic,
  `->`, `→`, `--` ranges now refused; `**[a]** y **[b]**`, `**[a]**, **[b]**`,
  `**[a]** and **[b]**` and table rows with or without bold still accepted; no
  new false positives; summary and report agree on all 52 cases.
- `existing_summaries_check.py` reproduces `existing-summaries-check.txt`
  (only the "Code:" line differs); wi09-frames' three ranges start with `**`
  and use " a ", counted without printing client text.
- P2-1, P3-2, P3-3 resolved; P3-4 to P3-6 in the contract's limitations; all
  11 changed files inside `affected_surfaces`.
- New P3, limitations only: `***[a]*** a ***[b]***`, `[a] --- [b]`,
  `[a] => [b]`, `[a] ⟶ [b]` still pass; WI09's summary is now refused, so the
  first Word report the owner judged cannot be rebuilt from it. Both added to
  the contract's limitations.

**Verdict: LISTO PARA INTEGRAR**, with those P3 as known limitations.
