# Revisión independiente de WI24 (01M495140RMJM90PFDGBN7XZMF), commit 0f6a3a8 contra main bde64df

Por el buzón de INGOL, 2026-10-06. El texto es la respuesta tal como llegó; el implementador sólo bajó un nivel sus títulos.

## La revisión

## Revisión independiente de WI24 (VisualMeetingTool), commit `0f6a3a8` contra `bde64df`

**Veredicto: aprobar con correcciones.** Hay que corregir una regresión (P1-1) antes de abrir el pull request. El resto está bien.

### Qué leí

- El contrato y el plan del work item.
- `git diff bde64df 0f6a3a8` completo, en el código, los tests, el README y `docs/`.
- De la base `bde64df`, sólo lo que hacía falta para comparar: el lector de transcripciones viejo, `qa.spoke()`, `gemini.call_checked`, `read_frames` y `check_request`.

No leí el historial ni otras fuentes.

### Qué ejecuté

| Comando | Resultado |
|---|---|
| `python -m unittest discover -s tests` | **493 tests, OK** (3 salteados, los de los kits), 382 s |
| `mutations.py . <scratch>/mut` sobre `0f6a3a8` | **Las 7 mutaciones detectadas.** Sin mutar, pasa antes y después. Coincide con `mutations.txt`, que se hizo sobre `3e20a8a`; de ahí a `0f6a3a8` sólo cambia ese archivo, verificado con `git diff --stat` |
| `reproduce.py WI24-P3-1..4 WI05-P3-2 WI05-P3-3` | 6 de 6 coinciden con lo que dice el registro |
| Prueba propia: el registro con una transcripción `.txt` `[HH:MM:SS] Nombre: texto`, Gemini simulado, sobre la base y sobre la rama | **base: registro escrito, 2 preguntas, 1 pedido. rama: rechazado con `qa.needs_speakers`, 0 pedidos** |
| Prueba propia: `label_frames` y `revise` con casos borde | Abajo, en la pregunta 5 |

### Hallazgos

#### P1-1. Regresión: el registro ya no acepta una transcripción `[HH:MM:SS] Nombre: texto` (ejecutado)

- **Dónde:** `meetingtool/summary/qa.py:766-769`. La prueba que fija el comportamiento está en `tests/test_qa.py:194-212`, con la transcripción entre corchetes en la línea 200.
- **Consecuencia:** en `main`, el registro de preguntas y respuestas se escribía con una transcripción `.txt` `[HH:MM:SS] Nombre: texto`. Ahora se rechaza diciendo que la transcripción "no dice quién habla".
- **Por qué pasa:** el lector deja vacío el hablante de esas líneas, porque el nombre viaja dentro del texto. La regla nueva rechaza toda transcripción en la que ningún turno tiene hablante, y por eso las incluye.
- **El diseño de `main` lo permitía a propósito:** `spoke()` (`qa.py:356-363`) dice "with no speaker names in the transcript ([HH:MM:SS] lines) … every name passes".
- **Lo contradice el propio README del cambio** (líneas 77-82): presenta `[HH:MM:SS] Speaker:` como una forma con hablante, y dice que se rechaza sólo "such a transcript", la que no nombra a nadie.
- **El contrato no pide quitarlo:** WI24-AC02 habla de "a transcript with no speaker", y el objetivo dice "instead of failing later", pero estas transcripciones no fallaban después.
- **Cambio sin declarar:** `changed-tests.md` no lo menciona.
- **Por qué no lo detectó la suite:** no había ningún test previo del registro con este formato, y el test nuevo exige el rechazo, así que fija la regresión.
- **Arreglo mínimo:** rechazar sólo cuando ninguna línea trae hablante de ninguna forma. Por ejemplo, que `_turns` diga qué forma leyó, o que `qa` también mire si hay alguna línea `_BRACKET_TIME`. Hay que sacar `brackets` del test de rechazo y agregar uno que pruebe que con corchetes el registro se escribe, como en la base.

#### P3-1. WI24-P3-3 sigue abierto con un arreglo más simple al alcance (ejecutado con `reproduce.py`)

- **Qué pasa:** en una transcripción con nombres, un renglón hablado que sea sólo "10:30" abre un bloque sin hablante a los 630 s.
- **Consecuencia:**
  - La palabra "10:30" desaparece del texto.
  - Lo que sigue se separa del turno de quien lo dijo.
  - Como los turnos se ordenan por hora, ese pedazo se muda al minuto 10:30.
- **Qué tan probable es:** baja, porque Teams suele puntuar ("10:30."), y `_TIME_ALONE` (`transcript.py:38`) no acepta puntuación. No lo verifiqué contra una transcripción real.
- **Arreglo:** aplicar la regla de la hora sola sólo si el archivo no tiene ninguna línea "Nombre   hora" ni `[HH:MM:SS]`. Da la misma garantía para el formato del owner y elimina el riesgo en los formatos que ya existían.
  - Lo único que se pierde es el caso mixto: renglones con nombre y renglones con la hora sola en el mismo archivo. Hoy sólo existe en un test sintético (`test_qa.py:214-221`), y no sé si Teams lo produce.
- **Sin evidencia:** puede que el encabezado de una transcripción de Teams traiga la duración con el formato `H:MM:SS` en un renglón propio. Si es así, también abriría un bloque vacío. Con el mismo arreglo queda cubierto.

#### P3-2. WI24-P3-4: conviene verificar al pedir, pero no bloquea (leído)

- **Lo que dice el registro de limitaciones es correcto:** para el registro de preguntas y respuestas la etapa de lectura de imágenes se saltea (`jobs.py:474-479`), así que lo único que se pierde es el tiempo de extraer las imágenes, sin gasto.
- **Cómo moverlo al pedido:** en `check_request` (`jobs.py:144`), si `kind == "qa"`, leer la transcripción y aplicar la misma regla. Son unas 4 líneas.
- **Ojo:** `check_request` hoy no lee la transcripción en ningún caso, así que esto sería nuevo. Si se hace, que use la regla ya corregida en P1-1.

#### P3-3. Cambia el prompt, así que lo ya pagado no se reaprovecha (leído)

- **Qué pasa:** cambió `FRAME_RULE`, que también usa el pedido de "lo visto en pantalla" del registro (`qa.py:595`). Por eso cambia la huella de ese pedido, y una corrida repetida del registro vuelve a pagar esos pedidos en vez de tomarlos de lo guardado (WI20).
- **Costo:** chico, y no rompe nada.
- **El texto nuevo de la regla queda bien en el pedido del registro:** allí el nombre de la imagen encabeza cada bloque, y la regla habla de copiar el nombre "as it appears next to the block".

### Las preguntas del pedido

1. **Criterios:** la tabla al final.
2. **Un solo lector:** sí. `read_blocks` y `read_turns` salen de `_turns`. El ciclo es el mismo que el de la base, con la rama `alone` agregada (`transcript.py:108`). Los formatos "Nombre   0:02" y `[HH:MM:SS]` se leen igual que antes; la BOM queda igual (WI05-P3-2 coincide). Sobre el riesgo de la regla nueva en transcripciones con nombres, ver P3-1: es real pero de baja probabilidad, y sí conviene restringirla.
3. **Registro con `.txt` `[HH:MM:SS]`:** funcionaba. **Es una regresión** (P1-1, ejecutada).
4. **Verificar al pedir:** conviene, no bloquea (P3-2).
5. **Imágenes en el pedido del resumen:**
   - **No encontré ningún camino por el que un nombre inexistente llegue al informe.**
     - `check_frames` no cambió.
     - Sólo se guarda una respuesta aceptada, y al reusarla se vuelve a verificar.
     - Hay un único reintento por respuesta rechazada (`incomplete_retried`), así que la nota no se acumula.
   - **El presupuesto alcanza para la nota del reintento.**
     - `worst` reserva `RETRY_NOTE_CHARS` (`writer.py:511`).
     - Con 500 nombres, la nota midió 1493 caracteres, contra 1500 reservados.
     - Los nombres salen de `FRAME_REF` (`frame_\d+_t…\.jpg`), así que no pueden meter instrucciones en el pedido.
     - Que el presupuesto no alcance para un segundo intento ya pasaba antes y tiene su propio test.
   - **Caso borde, sin impacto en el informe:** una referencia "[FRAME 2]" dentro del texto de otro bloque queda como número, porque `_BLOCK_LABEL` sólo reemplaza al principio del renglón. No puede producir una imagen inexistente: `FRAME_REF` no la toma como imagen y `FRAME_LIKE` no la detecta.
   - **El pedido del registro no se rompió**, salvo lo de P3-3.
6. **Tiempo de la etapa en curso:** correcto. `as_dict` calcula el tiempo transcurrido mientras la etapa corre; `app.js:188` lo muestra; el test lo prueba de punta a punta y su mutación se detecta.
7. **Algo más simple:** para la regla de la hora sola, restringirla a archivos sin ningún hablante (P3-1). Para el rechazo del registro, el criterio de P1-1, que además es el correcto. Etiquetar las imágenes con su nombre y avisar en el reintento ya es mínimo, y copia el patrón de `revise` que ya usa el registro.

### Criterios

| Criterio | Estado | Evidencia |
|---|---|---|
| WI24-AC01 | Cumple | `TranscriptTest` y `NoSpeakerTest` pasan; las mutaciones de la regla de la hora sola y de los lectores separados se detectan |
| WI24-AC02 | Cumple lo literal, pero se pasa de alcance | El rechazo en los dos idiomas sin enviar nada funciona. También alcanza a las transcripciones `[HH:MM:SS]`, que tienen hablante (P1-1) |
| WI24-AC03 | Cumple | Prueba con 141 imágenes; el reintento nombra lo inexistente; se acepta una segunda respuesta buena y se rechaza una mala; mutaciones detectadas |
| WI24-AC04 | Cumple | `RunningStageTest`; mutación detectada |
| WI24-AC05 | Parcial, a propósito | Mutaciones, `reproduce.py` y `changed-tests.md` están, aunque `changed-tests.md` no declara el cambio de P1-1. Falta, como está previsto, la corrida en un clon limpio con los kits |

### Limitaciones de esta revisión

- No corrí los tests `test_d1_*` porque necesitan los kits de INGOL.
- No sé si las transcripciones reales de Teams producen el caso de P3-1 ni la duración en el encabezado.
- WI24-P3-2 (si el Gemini real ahora copia bien los nombres) sigue sin poder comprobarse sin red.

**Sigue:** el agente de construcción corrige P1-1 (la regla del registro y su test) y, si quiere, P3-1. Después, el criterio corre la suite en un clon limpio con los kits y abre el pull request.

## Lo que se hizo con cada hallazgo

Una sola pasada de corrección (commits `efb72fa`, `53a784d`, `faa1856`), hecha
por el agente del rol de construcción (Sonnet) y revisada por el criterio. La
revisión, de `0f6a3a8`, llegó por el buzón de INGOL: motor Claude, rol
`revisor-independiente` (sin herramientas de escritura), cuenta empresa,
modelo pedido por rol (`rol:criterio`, resuelto a `opus`), esfuerzo alto, de
15:29 a 15:37.

| Hallazgo | Qué se hizo |
|---|---|
| P1-1: el registro rechazaba un .txt `[HH:MM:SS] Nombre: texto`, que en main se escribía | Corregido: el registro se frena sólo si el archivo no trae ninguna línea "Nombre   hora" ni `[HH:MM:SS]` (`transcript.names_no_one`); una prueba nueva escribe el registro con ese .txt, como en main |
| P3-1: la hora sola abría un bloque también en transcripciones con nombres | Corregido: sólo en un archivo sin líneas rotuladas; en uno que las tiene, una hora sola es texto del turno, como en main. `WI24-P3-3` queda "fixed by efb72fa" |
| P3-2: el pedido de registro sin hablantes se rechazaba después de extraer las imágenes | Corregido: `check_request` lo rechaza al pedirlo (`app.request.qa_needs_speakers`). `WI24-P3-4` queda "fixed by efb72fa" |
| P3-3: el cambio de `FRAME_RULE` cambia la huella de los pedidos de "lo visto en pantalla" del registro | Sin cambio de código: lo dice `changed-tests.md` (una corrida repetida del registro hecha antes de WI24 vuelve a pagar esos pedidos) |

Después de la corrección, sobre `faa1856`: la suite sin los kits, 497 pruebas
OK; las 10 mutaciones detectadas (`mutations.txt`, sobre `53a784d`, el mismo
código); `reproduce.py`, 63 coincidencias, 0 diferencias (el único error es
`WI05-P3-5`, que ya falla en main).
