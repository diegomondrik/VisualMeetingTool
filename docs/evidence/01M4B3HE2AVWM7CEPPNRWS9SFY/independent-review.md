# Revisión independiente de WI25 (01M4B3HE2AVWM7CEPPNRWS9SFY), commit d19f8a6 contra main eff7ef7

Por el buzón de INGOL, 2026-10-07. El texto es la respuesta tal como llegó; el implementador sólo bajó un nivel sus títulos.

## La revisión

## Revisión independiente: VMT WI25 (`01M4B3HE2AVWM7CEPPNRWS9SFY`) en `d19f8a6`, contra la base `eff7ef7`

**Veredicto: aprobar con correcciones.** No hay nada P0 ni P1. Encontré dos P2 baratos de arreglar: un año inventado que todavía pasa en ciertas formas de escribir la fecha, y cifras escritas como "48 mil" que se rechazan aunque se dijeron. Además dejo tres P3. El cambio cumple el contrato y el hallazgo R04 en las formas que más se usan. Las pruebas, las mutaciones y las reproducciones dan lo que la evidencia declara.

### Qué leí
- El contrato, el plan y `git diff eff7ef7 d19f8a6` completo: `qa.py`, `writer.py`, los textos, las pruebas, el README, la evidencia y el registro de limitaciones.
- Las dos pruebas del piloto de INGOL, en `repo/docs/work-items/dev-capabilities/evidence/d1/ac05-base-revisada/pruebas/`.
- No leí el historial ni otras revisiones.

### Qué corrí y qué salió
| Comando | Resultado |
|---|---|
| `python -m unittest discover -s tests` en `d19f8a6` | **582 pruebas, OK, 3 salteadas, 684 s** |
| `mutations.py` sobre `d19f8a6` con el árbol limpio | **16 de 16 detectadas**; sin mutar, 38 pruebas en verde. Coincide con `mutations.txt` (que se había corrido sobre `e94a4ce`) |
| `compare_pilot_tests.py` contra la carpeta del piloto en INGOL | Las dos clases son idénticas a las de INGOL; sale con 0 |
| `TrazabilidadDelRegistro` y `AR06ResumenVacio` con los kits, en `d19f8a6` | 2 de 2 en verde |
| Las mismas dos pruebas con el código de `eff7ef7` (extraído con `git archive`) | **2 de 2 fallan**, o sea que muestran el defecto |
| `reproduce.py` de WI25-P3-1 a P3-6 y WI20-P3-6 | Las 7 coinciden con el registro; sale con 0 |
| Dos scripts míos de sondeo en el scratchpad, sobre `figures_in`, `_check_text`, `empty_sections`, `check_summary` y `revise` | Ver los hallazgos |

El árbol de trabajo quedó limpio después de todo (`git status` vacío).

### Criterios
- **AC01**: cumple. Las dos clases son idénticas a las de INGOL según el script. Fallan en la base y pasan en `d19f8a6`, incluida `TrazabilidadDelRegistro` con los kits.
- **AC02**: cumple. `EmptySectionTest` recorre cada sección vaciada por turno, en castellano y en inglés y con cada tipo de reunión. La línea "no hubo nada" se acepta. Con Gemini simulado, el reintento nombra las secciones vacías. La reserva de presupuesto cubre la nota aunque nombre todas las secciones de todos los tipos; lo comprobé con `revise` (la nota se recorta a `RETRY_NOTE_CHARS`).
- **AC03**: cumple en las formas que prueba: "de 2030", `25/09/2030`, ISO, inglés, día en palabras, año de la reunión, sin año, 48.000 / 48,000 / 48000, y coma decimal. Pero quedan formas por las que el año inventado se escapa (P2-1).
- **AC04**: cumple en parte, como estaba previsto. Las mutaciones, `changed-tests.md` y las reproducciones están y las verifiqué. Faltan, porque así se acordó, la corrida final en un clon limpio con los kits (`local-test-run.txt`) y el registro de esta revisión.

### Hallazgos

**P0 y P1: ninguno.**

**P2-1. Un año inventado todavía pasa en el registro si la fecha no está escrita como "de/del/of/, AAAA".** Lo ejecuté.
- **Dónde:** `meetingtool/summary/qa.py:192` (`_YEAR_AFTER`) y `:484` (`_check_text`).
- **Qué pasa:** el año sólo se compara cuando forma parte de una fecha que los patrones reconocen.
  - Con una transcripción que dice "el 25 de septiembre" y una reunión de 2026, se **aceptan**: "el 25 de septiembre del año 2030", "el 25 de septiembre (2030)", "Sept. 25, 2030", "25 sep 2030", "septiembre de 2030", "para 2030" y "Q3 de 2030".
  - "25-09-2030" y "25.09.2030" ni siquiera se reconocen como fecha. Eso ya pasaba antes de WI25.
- **Consecuencia:** puede llegar al cliente un año que nadie dijo, que es justo la mitad de R04. La probabilidad es baja: el pedido ahora le dice a Gemini que escriba un año sólo si se dijo, y la forma con "de 2030" sí se rechaza. Por eso no lo pongo como bloqueante.
- **Arreglo mínimo, y además más simple que el actual:** en `_check_text`, rechazar también `written_years(text) - transcript.years`. Así el año se controla por sí solo, escrito como sea. `written_years` ya devuelve 2030 en todos los casos de arriba (lo comprobé), salvo "25-09-2030".
  - Costo: una cantidad entre 1900 y 2099 que el registro calcule por su cuenta (no "dicha") se rechazaría. Es raro, pero conviene una prueba de control.
  - Si no se arregla, hay que registrarlo como limitación. Hoy no figura en el registro.

**P2-2. Las cifras dichas con "mil" o "millones" se rechazan.** Lo ejecuté.
- **Dónde:** `qa.py:420`; `Transcript.read` sólo lee dígitos.
- **Qué pasa:** con la transcripción "48 mil kilos", la cifra "48.000 kilos" se rechaza. Lo mismo con "3 millones" contra "3.000.000" y con "1,5 millones" contra "1.500.000". En cambio "1,5 millones" contra "1,5 millones" pasa.
- **Diferencia con WI25-P3-3:** esa limitación cubre números dichos todo en palabras ("tres turnos"), no la forma mixta "dígito + mil/millones". La forma mixta es habitual cuando se habla en castellano de montos.
- **Consecuencia:** un pedido pago repetido. Si Gemini vuelve a normalizar la cifra en el segundo intento, el registro de esa reunión no se entrega.
- **Duda:** no sé con qué frecuencia Teams transcribe "48 mil" en lugar de "48.000", ni con qué frecuencia Gemini lo reescribe. No lo afirmo como frecuente.
- **Arreglo mínimo:** en `Transcript.read`, cuando a un número le sigue `mil|millón|millones|thousand|million|k`, sumar también el valor multiplicado. Si no, registrar la forma mixta junto con P3-3.

**P3**, no reabren el ciclo:
- **P3-a: el reintento nombra un solo problema.** Se lee en `writer.py:504-506`, `key_points` va antes que `empty_sections` y el control de imágenes después. Si "Puntos clave" está vacío y además hay otras secciones vacías, el reintento no menciona las otras: lo ejecuté y la negativa es `summary.no_key_points`. Lo mismo pasa con una sección vacía más una imagen inexistente. Costo: posible segundo rechazo. Arreglo: juntar los motivos en una sola nota, o al menos poner las vacías en la nota de `no_key_points`.
- **P3-b: fechas con año dicho de forma corta, falso rechazo.** Si la transcripción dice "el 15 de enero del 27" (año dicho), la fecha "el 15 de enero de 2027" se rechaza cuando el año no es el de la reunión. Lo ejecuté. Es pariente de P3-2 y P3-3 pero no está registrado.
- **P3-c: la propia prueba del piloto pide más de lo que el contrato alcanza.** El docstring de `TrazabilidadDelRegistro` dice "las cifras del conocimiento **y de las respuestas**". El contrato excluye a propósito las cifras de otros lugares, y la prueba sólo ejerce el grupo "figures". No es un defecto, pero conviene que un lector no crea que las respuestas se controlan. P3-1 ya lo cubre para el resumen; para las respuestas del registro no hay una línea.
- **Detalles sin consecuencia:** una sección con sólo "—", "…", un emoji o `- [ ]` se rechaza por vacía, y es discutible porque el pedido exige una línea explícita. Un comentario HTML con letras cuenta como contenido. "#1 prioridad: …" se lee como subtítulo y la sección queda vacía. Lo ejecuté; no lo eleve.

### Los focos que pediste
- **Falsos rechazos en el resumen:** no encontré ninguno que importe. Se aceptan las tablas, las secciones con sólo subtítulos y contenido debajo, las listas anidadas, "No hubo …", "*Ninguna.*", "N/A", las citas y las referencias a imágenes. Los subtítulos sin contenido y las reglas sueltas se rechazan, como corresponde.
- **Cifras legítimas:** pasan los separadores de miles con punto, coma o espacio; la coma decimal; los porcentajes; "1.200,00" contra "1200"; las versiones; los códigos; y los años dichos. No pasan "mil/millones" (P2-2), "10.30 h" contra "10:30", "48k", ni "0,15" contra "15 por ciento". Los últimos tres los dejo en P3: dependen de que Gemini reescriba la cifra.
- **Resumen vacío o con año inventado que todavía pasa:** un resumen vacío no pasa. Un año inventado sí, en el registro (P2-1), y en el resumen siempre, por P3-1, que el contrato deja fuera.
- **Reintento y presupuesto:** los dos están bien (AC02).
- **Pruebas que cambiaron:** las tres de `changed-tests.md` no debilitan nada. Siguen afirmando las mismas fechas, ahora con su año. A `ChecksTest` se le agrega la fecha de la reunión, y eso es realista: la aplicación siempre la pasa (`jobs.py:135`). Sólo la línea de comandos sin `--project` puede omitirla, y en ese caso una fecha con el año de la reunión se rechaza. Es menor.
- **WI25-P3-1 a P3-6:** todas siguen como P3. P3-1 (resumen sin control de cifras ni fechas) es la de mayor exposición frente a un cliente, pero está excluida explícitamente por el contrato aprobado. Promoverla es decisión del owner, no de esta revisión. P3-2, P3-3 y P3-6 fallan del lado seguro: rechazan y reintentan. P3-4 y P3-5 dejan pasar casos poco probables.
- **Mecanismo más simple:** para los años, el control independiente de P2-1 es más simple que llevar el año dentro de la tupla de la fecha, y da una garantía mayor. Para las secciones vacías, el mecanismo actual ya es mínimo.

### Lo que queda abierto
La corrida final en un clon limpio con los kits sigue pendiente, como estaba previsto. No pude verificar el comportamiento del Gemini real frente a `EMPTY_RULE`: las pruebas usan respuestas simuladas.

**Veredicto: aprobar con correcciones.** Lo mínimo es aplicar el arreglo de P2-1, o al menos registrarlo, y registrar P2-2 junto con P3-3. Nada de esto bloquea abrir el PR.

## Lo que se hizo con cada hallazgo

Una sola pasada de corrección (commits `0f90e95`, `2ac8734`), hecha por el
agente del rol de construcción (Sonnet), que se cortó por el límite de uso de
la cuenta después de dejarla commiteada; el criterio verificó y corrió la
evidencia sobre `2ac8734`. La revisión, de `d19f8a6`, llegó por el buzón de
INGOL: motor Claude, rol `revisor-independiente` (sin herramientas de
escritura), cuenta empresa, modelo pedido por rol (`rol:criterio`, resuelto a
`opus`), esfuerzo alto, de 09:56 a 10:11.

| Hallazgo | Qué se hizo |
|---|---|
| P2-1: un año inventado pasaba si la fecha no estaba escrita como "de/del/of/, AAAA" | Corregido: el año se controla solo, escrito como se escriba (`qa.invented_year`); "25-09-2030" y "25.09.2030" se leen como fecha. Lo que esto rechaza de más queda como `WI25-P3-10` |
| P2-2: cifras dichas con su escala ("48 mil", "1,5 millones") se rechazaban | Corregido: una cifra dicha con su escala se lee como su valor, en la transcripción y en la cifra; lo que queda sin leer ("mil" solo) es `WI25-P3-9` |
| P3-a: el reintento nombraba un solo motivo | Corregido: la nota del reintento junta todos los motivos (secciones vacías, puntos clave, imágenes inexistentes) |
| P3-b: un año dicho corto ("del 27") | Limitación conocida `WI25-P3-8` |
| P3-c: las cifras de las respuestas del registro no se contrastan | Limitación conocida `WI25-P3-7` |

Después de la corrección, sobre `2ac8734` en clones limpios: las 21
mutaciones detectadas (`mutations.txt`); la suite completa con los kits de
INGOL (`local-test-run.txt`); `reproduce.py`, 76 coincidencias, 0
diferencias (el único error es `WI05-P3-5`, que ya falla en main).
