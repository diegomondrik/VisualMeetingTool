# Revisión independiente de WI26 (01M4BGTP1940T4ASG54GC323WT), commit c18ac9b contra main 41f6722

Por el buzón de INGOL, 2026-10-07. El texto es la respuesta tal como llegó; el implementador sólo bajó un nivel sus títulos.

## La revisión

## Revisión independiente de WI26 (VisualMeetingTool): `c18ac9b` contra `main` `41f6722`

**Veredicto: aprobar.** No encontré nada de P0 a P2. Los cuatro hallazgos son P3 y no reabren el ciclo. Antes de abrir el PR falta una sola cosa, y es a propósito: la corrida final de la suite en un clon limpio con los kits.

### Qué leí
- El contrato y el plan.
- `git diff 41f6722 c18ac9b`, completo.
- `meetingtool/frames/transcript.py` entero.
- Los tests nuevos y la evidencia: `compare_pilot_tests.py`, `mutations.py`/`.txt` y `changed-tests.md`.
- Los otros lectores de la transcripción: `qa.py`, `writer.py` y `jobs.py`. Todos pasan por `transcript.py`; ninguno la lee aparte con `encoding="utf-8"`.

No leí el historial. Para esta revisión no hizo falta.

### Qué ejecuté y qué dio
| Qué | Resultado |
|---|---|
| Suite completa, sin kits | **602 tests OK, 3 salteados** (705 s, exit 0) |
| `compare_pilot_tests.py` contra la carpeta `pruebas/` de INGOL | Las tres piezas (la clase, `TEXTO`, `turnos`) son iguales a las de INGOL; exit 0 |
| `TranscripcionDeTexto` con los kits (`PYTHONPATH=~/.claude/ingol-kits/python`) | 3 OK |
| Los tests nuevos (la clase piloto y `test_transcript_encodings`) copiados sobre la base `41f6722` | **FAILED (failures=24, errors=38)**: muestran el defecto |
| `mutations.py` sobre `c18ac9b` | Detecta las 4 mutaciones; la corrida sin mutar da OK. Coincide con `mutations.txt`, que se grabó sobre `620d394`; desde ese commit `transcript.py` y los tests no cambiaron |
| Dos mutaciones mías: cp1252→latin-1, y UTF-16→sólo LE | Las dos se detectan |
| `reproduce.py WI05-P3-2 WI05-P3-3 WI26-P3-1` | 3 MATCH (fixed, open, open) |
| Equivalencia del patrón viejo y el nuevo de `_SPEAKER_TIME` en 281.056 líneas al azar ya recortadas (espacio, tab, NBSP, U+3000, U+2009, U+FEFF, U+200B, dígitos, `:`) | **0 diferencias**, en si coincide y en los grupos |
| Tiempo de lectura con tiras de 20.000 tabs o NBSP, `" a"`×20.000 y `"ab  "`×10.000 | ≤ 0,002 s cada una |

### Criterios del contrato
- **WI26-AC01: cumple.** El script compara la clase con la de INGOL (exit 0), y las tres pruebas pasan con los kits. Sobre la base fallan.
- **WI26-AC02: cumple.** Hay 5 codificaciones × 3 finales de línea × 3 formas. Para cada combinación coinciden `read_turns`, `read_blocks`, `names_no_one` y `read_text`. Con una sola línea con hora el archivo se lee, en las 5 codificaciones. Los 20.000 espacios van en medio de la línea (no en una línea que el recorte deja vacía) y se leen en menos de 1 s.
- **WI26-AC03: cumple en parte, como estaba previsto.** Cumplido: las mutaciones, `WI05-P3-2` pasada a "fixed" (y reproducido), `changed-tests.md` y las limitaciones reproducidas. Falta: `local-test-run.txt`, la corrida en un clon limpio con los kits.

### Respuestas a las cinco preguntas
1. **¿Algo que antes se leía bien ahora se lee distinto?** No.
   - **El patrón:** lo ejecuté. Sobre líneas recortadas (`_read` hace `.strip()`, y `\s` cubre los mismos caracteres que `str.isspace`), la versión vieja y la nueva son equivalentes. El nombre más corto posible ya terminaba siempre en un carácter que no es espacio.
   - **El respaldo a cp1252:** sólo entra con bytes que no son UTF-8 válido, y esos archivos antes se rechazaban. Un archivo que antes se leía no cambia.
2. **¿Se puede seguir perdiendo la primera intervención sin aviso?** Sí, en dos casos raros (P3-1). Con una UTF-32 o una UTF-16 sin marca el archivo se rechaza: no hay pérdida silenciosa, pero el mensaje es el equivocado (P3-3). Los espacios raros al principio (NBSP, U+3000) se leen bien.
3. **¿Un binario renombrado a .txt ahora da turnos basura?** En la práctica no. Datos al azar de 1 KB nunca se pudieron leer como cp1252 (0 de 2000 intentos). PNG, JPEG y GIF generados con PIL se siguen rechazando como ilegibles. Un binario armado a mano sin ninguno de los 5 bytes que cp1252 no define, y con una línea `12:34`, sí da un turno basura; lo ejecuté. Un BMP en blanco y un zip muy comprimible ahora se rechazan como "sin línea con su minuto", ya no como ilegibles (P3-3).
4. **¿Hay un mecanismo más simple?** `data.decode("utf-8-sig")` en lugar de sacar la marca a mano. Es lo mismo que pedía la clase piloto ("En verde si: `_text_lines` lee con `utf-8-sig`") y ya se usa en `build_report`. La garantía es la misma y no cambia nada de fondo. Lo que sí agregaría garantía es el arreglo de P3-1.

### Hallazgos
**P0 / P1 / P2: ninguno.**

**P3-1. Una marca BOM doble sigue haciendo perder la primera intervención sin aviso.** En `meetingtool/frames/transcript.py:87-90`, `_decode` saca una sola marca. Si el archivo trae dos (UTF-8 con BOM×2, o UTF-16 con BOM y un U+FEFF adentro), queda un U+FEFF delante de la primera línea, y `str.strip()` no lo quita. **Lo ejecuté:** el archivo da `[(60, '', 'Luis: chau')]` y el turno de las 0:04 se pierde. Notepad no escribe dos marcas, así que es raro, pero es la misma falla que corrige R06.
- **Arreglo mínimo, probado:** `_decode(...).lstrip("\ufeff")` en `_text_lines`, línea 99. Lee los dos casos y la suite de transcripción sigue en verde.
- **Mismo síntoma, preexistente y fuera del alcance:** un U+200B al principio también hace perder la primera intervención (lo ejecuté).

**P3-2. Un UTF-8 con un solo byte de otra codificación se lee entero como cp1252, sin error.** Línea 94. Un byte de cp1252 suelto (por ejemplo, de un pegado) convierte el archivo completo en texto deformado: `mañana` pasa a `ma\xc3\xb1ana` (lo ejecuté). Antes ese archivo se rechazaba; ahora llegan al resumen y al registro acentos rotos sin advertencia. `WI26-P3-1` sólo nombra el caso "otra codificación" y no este archivo mezclado.
- **Arreglo mínimo:** ampliar el texto de `WI26-P3-1` para que lo nombre.
- **Mecanismo opcional:** si los bytes tienen secuencias UTF-8 multibyte válidas, decodificar `utf-8` con `errors="replace"` en lugar de cp1252.

**P3-3. Algunos rechazos ahora dan el mensaje equivocado.** Un binario que cp1252 alcanza a leer (BMP en blanco, zip chico), una UTF-32 (su marca LE empieza igual que la de UTF-16 LE y se decodifica como UTF-16) o una UTF-16 sin marca con acentos se rechazan como "no tiene ninguna línea con su minuto", ya no como "no se puede leer". Lo ejecuté. Se siguen rechazando; sólo el mensaje engaña al usuario. Arreglo mínimo: anotarlo como limitación conocida.

**P3-4. La corrida pendiente con kits puede no correr las pruebas `test_d1_*` sin que nadie lo note.** Esto es para la corrida pendiente de AC03 (`tests/test_d1_barrido.py:20-24`). Si el kit instalado no trae `variantes`, el `ImportError` hace que se salte todo el archivo, incluidas las clases de WI20 y WI25, con el mensaje de "kits ausentes". Lo leí y no lo ejecuté. El kit local sí trae `variantes`.
- **Arreglo mínimo:** que `local-test-run.txt` muestre que las pruebas `test_d1_*` corrieron (con `-v`), y no sólo "OK (skipped=N)".

### Otras limitaciones y comprobaciones
- **Lo que cambió está todo declarado.** Todos los archivos tocados están dentro de `affected_surfaces`. `changed-tests.md` es correcto: ninguna prueba que ya existía cambió.
- **Las identidades que declara el incremento se sostienen.** `fixed by a90cfd1`: `transcript.py` no cambió de `a90cfd1` a `c18ac9b`. El commit de `mutations.txt` (`620d394`) también es real.
- **El incremento no puede aprobarse a sí mismo.** `compare_pilot_tests.py` compara contra el archivo de INGOL; no compara contra una copia que el propio incremento pueda tocar.

---
Sigue el constructor de VisualMeetingTool: corre la suite en un clon limpio con los kits, guarda `local-test-run.txt` mostrando que las pruebas `test_d1_*` corrieron, y abre el PR. Los P3 van a la lista de limitaciones; no hay nada que decida el owner.

## Lo que se hizo con cada hallazgo

La revisión, de `c18ac9b`, llegó por el buzón de INGOL: motor Claude, rol
`revisor-independiente` (sin herramientas de escritura), cuenta empresa,
modelo pedido por rol (`rol:criterio`, resuelto a `opus`), esfuerzo alto, de
14:08 a 14:21. Aprobó; la pasada de corrección, chica, la hizo el criterio
(`ae6a883`).

| Hallazgo | Qué se hizo |
|---|---|
| P3-1: una marca escrita dos veces escondía la primera intervención | Corregido: las marcas que queden al principio del texto se quitan; prueba y mutación nuevas |
| P3-2: un UTF-8 con un byte de otra codificación se lee entero como cp1252 | Dicho en `WI26-P3-1` |
| P3-3: algunos archivos que no son transcripciones se rechazan con el mensaje equivocado | Limitación conocida `WI26-P3-2`, con reproducción |
| P3-4: que la corrida con los kits muestre que los `test_d1_*` corrieron | `local-test-run.txt` es verboso: cada prueba del paquete aparece con su resultado |

La corrida final sobre `ae6a883` se hizo en dos partes, una después de la
otra, porque la máquina estaba corta de memoria (lo dice el encabezado de
`local-test-run.txt`): la suite sin los kits, 603 OK; las pruebas del paquete
con los kits, 22 OK. Las mutaciones, sobre el mismo commit y solas, las cinco
detectadas.
