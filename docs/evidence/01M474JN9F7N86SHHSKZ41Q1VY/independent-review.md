# Revisión independiente de WI21 (01M474JN9F7N86SHHSKZ41Q1VY), commit a9a09f3 contra main bc24f89

Por el buzón de INGOL, 2026-10-05. El texto es la respuesta tal como llegó; el implementador sólo bajó un nivel sus títulos.

## La revisión

**Revisión independiente de WI21 (VisualMeetingTool, R05): leer el video hasta el final aunque haya transcripción**

Apruebo lo revisado. No encontré nada P0, P1 ni P2. Hay cuatro P3, que no son bloqueantes. Todavía no está listo para integrar, pero sólo porque faltan AC04 y la corrida final de AC05, que quedaron pendientes a propósito.

**Qué leí.** El contrato y el plan, `git diff bc24f89 a9a09f3` (13 archivos, todos dentro de las superficies que declara el contrato), el lazo de `extract.py`, `transcript.py`, `__main__.py`, el lugar donde la aplicación llama a la extracción (`app/jobs.py:419-463`), cómo el registro de preguntas elige los frames (`summary/qa.py:283-293,436`), y `tests.yml`. No leí nada del historial.

### Qué ejecuté
| Comando | Resultado |
|---|---|
| `git rev-parse HEAD` y `git status` | `a9a09f3d62e9…`, sin cambios (sólo las carpetas `__pycache__` ignoradas) |
| `python -m unittest discover -s tests` | 419 pruebas, OK, 3 salteadas (los `test_d1_*` que piden los kits), 342 s |
| `mutations.py . <scratchpad>` sobre a9a09f3 | Las 7 mutaciones detectadas, con los mismos conteos de fallas que `mutations.txt`. La corrida sin mutar pasa |
| La prueba del piloto sobre 8f5fe69 (el commit en rojo) | Falla: queda `['A']`, se corta en 6.0 s |
| Las pruebas nuevas con el código de `main` (con el corte de WI10, 120 s reales) | 5 de 6 fallan. Sólo pasa la del caso "horarios más allá del video", y es lo esperable |
| `reproduce.py WI21-P3-1 WI21-P3-2 WI21-P3-3 WI20-P3-6` | 4 MATCH, 0 MISMATCH |

### Respuestas a las seis preguntas
1. **¿Queda algún corte?** No. `extract_frames` es el único lugar que decodifica, y no quedan `stop_at`, `break` por transcripción ni `.last`. La aplicación siempre pasa la transcripción (`jobs.py:462`) y no hace nada con el resultado más que contar los frames guardados. Subir candidatos sigue igual (`extract.py:199`, `transcript.py:157`), y la línea de la consola sobre lo que subió la transcripción sigue estando. Hay un caso aparte, preexistente, en el formato de preguntas: lo anoto como P3-4.
2. **¿Las pruebas detectan que el corte vuelva?** Sí, lo ejecuté. Contra el corte real de `main` fallan cuatro pruebas de `test_frames` y la del piloto. La del caso "horarios más allá del video" pasa aunque el corte esté, porque con el último renglón a los 600 s el corte de WI10 nunca se dispara. No sirve para detectar el corte; cubre el tercer caso de AC02. Las otras tres comparan la cantidad exacta de muestras leídas con y sin transcripción, y eso agarra cualquier salida temprana.
3. **¿Se perdió algo al reemplazar las dos pruebas de WI10?** No. Lo que no tenía que ver con el corte sigue cubierto:
   - que con transcripción se guardan las diapositivas correctas (ahora A, B y C);
   - que sin transcripción se lee todo el video (ahora `samples > 270` y la igualdad con el caso sin transcripción);
   - que el comando con `--transcript` termina bien. Ahora se prueba mejor: con `-m meetingtool.frames` real, sin parchear el módulo.
4. **¿Las limitaciones nuevas dicen lo que muestran?** Sí, con un matiz. En WI21-P3-1, el "about 243" es un cálculo y no algo observado, pero el registro lo escribe como "about", así que no exagera. Además P3-1 mide muestras, no tiempo; el tiempo lo va a medir AC04. WI21-P3-3 sólo busca las opciones `--end`, `--until` y `--stop`, pero imprime la lista completa, que se puede verificar a ojo. El cambio de WI20-P3-6 (3 salteadas y 4 corridas) coincide con lo que ejecuté.
5. **¿Abre algo de seguridad?** No. El cambio sólo quita código: no agrega entradas, rutas ni archivos nuevos. El tope que ponía la transcripción nunca protegía nada, porque la transcripción la entrega el mismo usuario: un renglón a las 99:00:00 ya hacía decodificar el video entero. El límite de subida de 16 GB (`server.py:50`) no cambió.
6. **¿Hay un mecanismo más simple?** No con la misma garantía: el arreglo ya es borrar código. Lo único que se podría simplificar es el tiempo de las pruebas. Las tres pruebas de AC02 vuelven a extraer el mismo video de 140 s sin transcripción. Compartir esa extracción ahorraría segundos, pero no cambia ninguna garantía y es opcional.

### Hallazgos
**P0, P1 y P2: ninguno.**

- **P3-1. La evidencia de las mutaciones no nombra un commit.** `mutations.txt:4` dice que se grabó sobre "a9c80f0 plus the removal…", un estado que nunca se commiteó. Lo ejecuté en a9a09f3 y el resultado es idéntico.
  - **Arreglo:** volver a grabarlo en la corrida de AC05 sobre un clon limpio, nombrando el commit.
- **P3-2. Una frase falsa sobre la CI.** `mutations.py:10` y lo que imprime dicen que `MeetingRealityTest` es "what the CI runs". En realidad la CI corre `discover -s tests -v` (`tests.yml:98`), que incluye más pruebas. No cambia la conclusión. Lo leí, no lo ejecuté.
  - **Arreglo:** decir "the frames tests, part of what the CI runs".
- **P3-3. `changed-tests.md:22` puede leerse mal.** Pone la prueba de "times past the recording" entre los reemplazos de la prueba del corte, pero esa prueba no detecta el corte (ejecutado, ver la pregunta 2).
  - **Arreglo:** una frase que diga que cubre AC02, no AC03.
- **P3-4. El mismo patrón de R05 sigue en el formato de preguntas.** Es preexistente y está fuera del contrato. En `summary/qa.py:288-293`, para una respuesta se leen sólo los frames hasta `min(end, start+600)`, y `end` es cuando *empezó* su último turno (como mucho `transcript.last + 60`, `qa.py:436`). Una diapositiva mostrada durante una explicación final larga ahora sí se extrae, pero en el formato de preguntas no se lee. En el formato resumen se lee igual. Lo leí, no lo ejecuté.
  - **Arreglo:** nada en WI21. Que el owner decida si lo anota como limitación.

### Criterios
- **WI21-AC01:** cumple. Ejecutado: pasa en a9a09f3 y falla en 8f5fe69.
- **WI21-AC02:** cumple. Ejecutado: los tres casos y la prueba de lo que sube la transcripción.
- **WI21-AC03:** cumple. Re-ejecutado en a9a09f3: las 7 detectadas.
- **WI21-AC04:** pendiente a propósito, pero encaminado. Ojo: ahora la consola ya no imprime ni los segundos ni cuántos frames guardados quedan después del último renglón. Hace falta medir eso aparte, con los nombres de los frames y un cronómetro.
- **WI21-AC05:** parcial. Ya están: la suite pasa acá sin los kits, `changed-tests.md`, el README, el docstring, y el registro con sus reproducciones. Falta `local-test-run.txt`, de un clon limpio con los kits.

### Limitaciones de esta revisión
- Corrí todo sin los kits de INGOL, así que los tres `test_d1_*` que los piden no se ejecutaron.
- No probé la aplicación de punta a punta.
- P3-4 surge sólo de leer el código.

**Veredicto:** aprobar. NO LISTO para integrar: faltan AC04 y la corrida de AC05 en un clon limpio, pendientes a propósito.

Siguiente paso, del owner: correr AC04 con su grabación real y AC05 en un clon limpio, y antes del PR decidir una sola cosa: si P3-4 se anota como limitación.

## Lo que se hizo con cada hallazgo

Una sola pasada de corrección. La revisión, del commit `a9a09f3`, llegó por el
buzón de INGOL: motor Claude, rol `revisor-independiente` (sin herramientas de
escritura), cuenta empresa, modelo pedido por rol (`rol:criterio`, resuelto a
`opus`), esfuerzo alto, de 20:45 a 20:53. No se pidió una revisión de
seguridad aparte: el cambio sólo quita código; la pregunta 5 de esta revisión
lo confirma.

| Hallazgo | Qué se hizo |
|---|---|
| P3-1: `mutations.txt` no nombra un commit | Se vuelve a grabar sobre un commit con nombre, en la corrida final |
| P3-2: "what the CI runs" | Ahora dice "the frames tests, part of what the CI runs" |
| P3-3: `changed-tests.md` puede leerse mal | Dice que la prueba de los horarios más allá del video cubre WI21-AC02 y no detecta el corte; las otras tres sí |
| P3-4: el registro de preguntas lee los frames de una respuesta hasta que empezó su último turno | Limitación conocida `WI21-P3-4`, reproducida por `reproduce.py`; ya pasaba antes de WI21 y queda fuera de este contrato |
| AC04 pendiente | Hecho sobre una grabación sintética (`synthetic-run.txt`), por decisión del owner del 2026-10-05; la medición cronometra la extracción y cuenta los frames posteriores a la última línea, como pedía la revisión |
| AC05 parcial | La suite completa con los kits en un clon limpio va en `local-test-run.txt` |

Ningún hallazgo fue P0, P1 ni P2.
