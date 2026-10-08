# Revisión independiente de WI29 (01M4CM3YV7RF9ET37K61XBYVRY)

Revisor independiente por el buzón de INGOL (rol `revisor-independiente`, sin herramientas de escritura): el texto es el que devolvió, copiado por el implementador. Al final, lo que se hizo con cada hallazgo.

## Primera revisión independiente, 2026-10-07 (commit 3c8c41e): no aprobar

# Revisión independiente de WI29 (VisualMeetingTool, R08): veredicto **no aprobar**, con un solo arreglo pendiente

Lo que sí funciona está bien hecho. Pero un .docx de 767 bytes cuyas partes están comprimidas con BZIP2 (o LZMA) hace que el programa use más de 1 GB de memoria antes de rechazarlo. El work item existe para impedir justamente eso, y el registro ya marca WI22-P3-2 como "fixed". El arreglo es chico y entra en la única pasada de corrección prevista.

## Qué leí
- El contrato y el plan del work item.
- `git diff 1a78ce4 3c8c41e` completo: `word_package.py`, `transcript.py`, `document.py` (líneas 439–515 y 744–830), los textos, README, REGISTER, `reproduce.py`, las pruebas nuevas, `mutations.py`, `mutations.txt` y `changed-tests.md`.
- `server.py` (límites de carga) y `extract.py` (formato de los fotogramas).
- El código fuente de `zipfile.ZipExtFile._read1` y `_read2` en Python 3.12.10.
- No leí nada más. Mis paquetes de prueba quedaron en mi carpeta temporal: el buzón no me deja escribir en la carpeta de salida.

## Qué ejecuté y qué salió
| Comando | Resultado |
|---|---|
| `python -m unittest tests.test_word_package_limits -v` | 14 pruebas, OK (8,6 s) |
| `mutations.py` sobre 3c8c41e (árbol limpio) | 7 de 7 detectadas, y la corrida sin mutar da OK. Coincide con `mutations.txt` (grabado en ae05d94; entre ese commit y 3c8c41e sólo cambian archivos de evidencia) |
| `reproduce.py WI22-P3-2 WI29-P3-1` | 2 MATCH, 0 MISMATCH |
| test_report, test_template_filter, test_allowed_fields, test_markup_compatibility, test_transcript_encodings, test_texts | 218 pruebas, OK (362 s). **No corrí la suite completa** (unos 12 min) |
| Identidad del commit | b16f047 existe y es el commit del código, como dice el REGISTER |
| Memoria pico de `read_parts` (medida con `K32GetProcessMemoryInfo`) | Ver P1 y P2 |

## Hallazgos

### P0
Ninguno.

### P1 — Las partes BZIP2/LZMA saltean la cota de memoria (ejecutado)
- **Dónde:** `meetingtool/word_package.py:49-50`.
- **Qué pasa:** `zipfile` sólo acota el tamaño de salida para deflate (`decompress(data, n)`). Para BZIP2 y LZMA llama `self._decompressor.decompress(data)` sin máximo, y recién después recorta al tamaño declarado. Un único `part.read(64 KB)` puede expandirse sin límite antes de que el contador vea el primer byte.
- **Lo que medí:**
  - Deflate, 512 MB (522 KB en disco): rechazado, pico de 52 MB. Correcto.
  - **BZIP2, 512 MB (767 bytes en disco): rechazado con el mensaje de 32 MB, pero con pico de 1094 MB.**
  - **LZMA, 256 MB (38 KB en disco): pico de 586 MB.**
  - Lo mismo pasa por `transcript._docx_lines` y por `document.template_bytes`.
  - BZIP2 comprime 1 GiB en 786 bytes, así que una subida de pocos KB se traduce en decenas de GB.
- **Consecuencia:** una transcripción o plantilla subida de menos de 1 KB tumba el servidor por memoria. Eso contradice la cláusula de memoria de WI29-AC01 y el "fixed" de WI22-P3-2.
- **Por qué las pruebas no lo ven:** `test_the_refusal_stops_reading_at_the_limit` sólo arma paquetes deflate, así que no puede fallar por esto.
- **Arreglo mínimo:**
  - Antes de abrir nada, recorrer `archive.infolist()` y rechazar con `PackageError` toda entrada con `compress_type` distinto de `ZIP_STORED` o `ZIP_DEFLATED`, y toda entrada cifrada (`flag_bits & 1`). Mensaje nuevo en es/en, nombrando la parte.
  - Agregar una prueba con una parte BZIP2 grande que verifique que se rechaza sin abrir nada (con `mock` de `open`, como la prueba de entradas).
  - Agregar una mutación que saque ese chequeo.
  - Efecto secundario bueno: hoy deflate64 da `NotImplementedError` y una parte cifrada da `RuntimeError`, y ninguna de las tres funciones que leen el paquete los captura (ejecutado; ya pasaba antes de WI29). Con este arreglo pasan a ser un rechazo limpio.

### P2 — Memoria del directorio central: conocida pero no registrada (ejecutado)
- **Dónde:** `word_package.py:39-42`.
- **Qué pasa:** `ZipFile()` lee el directorio central entero y arma un `ZipInfo` por entrada antes de que se cuenten las entradas.
- **Lo que medí:** un archivo de 47,7 MB (entra en el límite de carga de 50 MB) con 900.000 entradas se rechaza bien, pero con un pico de 449 MB. Queda acotado a unas 10 veces el límite de carga.
- **El problema:** el constructor lo avisó, pero WI29-P3-1 sólo habla de la memoria del lector de XML, y el registro calla esto.
- **Arreglo:** agregarlo al registro con su reproducción. No hace falta código.

### P3 (no reabren el ciclo)
1. **Hay un mecanismo más simple con la misma garantía (leído y ejecutado).**
   - `_read1` recorta a `file_size` (`data[:self._left]`) y después falla el CRC. La propia prueba "lies-small" lo muestra.
   - Por eso `zipfile` nunca devuelve más que el tamaño declarado. Sumar los `file_size` del directorio antes de leer acota lo mismo, y además rechaza sin descomprimir nada.
   - La mutación "size taken from the directory" se detecta sólo porque una prueba exige *aceptar* un paquete cuyo directorio miente hacia arriba. Esa prueba cuida una decisión de diseño, no la garantía.
   - El docstring de `word_package.py:11-13` sugiere que confiar en el directorio sería inseguro, y no lo es.
   - El contrato eligió contar los bytes y esa elección es válida. Lo que sobra es la justificación.
2. **python-docx vuelve a leer el paquete (leído).** Pasa en `document.py:472-474`, `:508`, `:823` y `:769`. Siempre lee bytes que ya pasaron por `read_parts`, así que queda dentro de los mismos límites; ningún lugar abre un ZIP sin pasar por el control.
   - Pero `:472` vuelve a leer el archivo del disco: hay una ventana de tiempo entre la revisión y la lectura, que ya existía antes de WI29.
   - Una plantilla de 256 MB, que está dentro del límite, ocupa 2 a 3 veces eso en memoria. WI29-P3-1 no lo dice.
3. **Nombres duplicados (leído).** `dict.fromkeys` más `NameToInfo` leen sólo la última entrada de cada nombre. No es un bypass del límite: las entradas anteriores no las descomprime nadie, y python-docx también se queda con la última.
   - Si Word lee otra copia que la que revisa el filtro de contenido activo, ese es un tema de WI22 y ya existía antes de WI29. No lo verifiqué con Word.
4. **Word legítimo afuera: estimado, no ejecutado.** Los fotogramas son JPEG de 1280×720 con calidad 85. Llegar a 256 MB exige del orden de mil fotogramas citados en un informe. El contrato cita 146 fotogramas y la plantilla de 1,1 MB.
   - Si un informe pasa el límite, se borra después de todo el trabajo y el mensaje es claro. El riesgo es bajo.

## Respuesta a tus preguntas
1. **¿Algo abre un Word sin `read_parts`?** No. Los únicos `ZipFile` de lectura de `meetingtool` están en `word_package.py`. python-docx relee el paquete sólo después del control (ver P3-2).
2. **¿Se puede pasar el límite sin que se note?** Sí, por el método de compresión (P1). Partes repetidas, nombres raros, una parte pedida dos veces o un total que sólo cuenta lo pedido no lo permiten.
3. **¿Queda afuera algún Word legítimo?** Ninguno en las pruebas existentes ni en los casos del contrato (ver P3-4).
4. **¿Las pruebas y mutaciones pueden fallar de verdad?** Sí, salvo la del directorio, que cuida una decisión de diseño (P3-1), y salvo que ninguna cubre BZIP2/LZMA (P1).

## Criterios
- **WI29-AC01 — no se cumple del todo.** Los límites, los mensajes en es/en, los tres lectores, el caso de la revisión (se lee) y el de 40 MB (se rechaza) están ejecutados y OK. La cláusula de memoria falla con BZIP2/LZMA (1094 MB medidos).
- **WI29-AC02 — cumple.** El directorio que miente hacia abajo se rechaza y el que miente hacia arriba se lee, ejecutado. Las 218 pruebas de los módulos que leen Word pasan. Falta la suite completa con los kits.
- **WI29-AC03 — parcial.** Las mutaciones dan 7/7 y `reproduce.py` da MATCH en ambas limitaciones. `changed-tests.md` está correcto. El "fixed" de WI22-P3-2 es prematuro por P1. La corrida en un clon limpio con los kits falta, como estaba previsto.

## Veredicto
**No aprobar** — una parte BZIP2/LZMA de pocos bytes rompe la cota de memoria que el work item declara cerrada.

Siguiente paso: el constructor agrega el rechazo de métodos de compresión distintos de stored/deflate (y de partes cifradas), con su prueba y su mutación, y registra lo de P2. Después, corrida final en un clon limpio con los kits y PR.

## Segunda revisión, acotada, 2026-10-08 (commit 63477aa… revisado en bfa579b): aprobar

# Segunda revisión de WI29 (VisualMeetingTool): corrección del P1 de los paquetes Word

**Veredicto: aprobar.** El P1 queda cerrado: lo medí por las tres rutas y no pude reabrirlo con ninguna variante de cabecera. Los tres P3 de abajo no reabren el ciclo.

## Qué leí
- `git diff 3c8c41e bfa579b`. El código cambió solo en `a2ef2fc`; `bfa579b` toca únicamente `changed-tests.md` y `mutations.txt`.
- `meetingtool/word_package.py` completo y los tres puntos que lo llaman: `transcript._docx_lines`, `document.template_bytes` y `document.check_active_content`.
- El manejo de errores en `server.py` y `jobs.py`.
- El código de `zipfile.ZipFile.open` y `_get_decompressor` de Python 3.12.10, para ver qué campos de cabecera usa de verdad.

No leí historial, decisiones ni `history/`.

## Qué ejecuté y qué salió

| Prueba | Resultado |
|---|---|
| Paquetes de 512 MB expandidos: BZIP2 (878 B en disco) y LZMA (76 KB), por las tres rutas. Pico de memoria medido con `PeakPagefileUsage` en un proceso nuevo por caso | Las 6 combinaciones se rechazan con `package.unreadable_part`. El pico no sube nada: 281–282 MB antes y después, y esos 281 MB son lo que ocupa importar el programa |
| **Control del instrumento**: los mismos paquetes contra `3c8c41e`, el commit anterior a la corrección | BZIP2 por la verificación del informe: 286 → 1358 MB. LZMA por la transcripción: 282 → 1291 MB. La medición sí detecta el P1 cuando existe |
| Variantes armadas a mano, leídas con `read_parts` | Ver la tabla siguiente |
| `python -m unittest tests.test_word_package_limits -v` | 17 OK |
| `mutations.py . <carpeta nueva>` | 9 de 9 detectadas, todas con pruebas que corrieron y fallaron; la corrida sin mutar da OK |
| `reproduce.py WI22-P3-2 WI29-P3-1 WI29-P3-2` | 3 MATCH. WI29-P3-2: 60.000 partes vacías (6,5 MB), rechazado, pico de 34 MB (5,2 veces su tamaño) |
| `tests.test_texts` | 29 OK |
| Suite completa (`unittest discover`) | 642 OK, 3 skipped |
| `git status` al terminar | limpio |

Variantes de cabecera:

| Variante | Resultado |
|---|---|
| deflate64 (9) solo en el directorio central | rechazado |
| PPMd (98) solo en el directorio central | rechazado |
| BZIP2 en el central y deflate en el encabezado local | rechazado |
| Encabezado local dice 9 o 12, central dice 8 | aceptado y leído como deflate (acotado) |
| 512 MB de datos BZIP2 reales con el central diciendo 8 | `zlib.error` inmediato, sin memoria extra |
| Bit de cifrado (bit 0) solo en el central | rechazado |
| Bit de cifrado solo en el encabezado local | aceptado: zipfile lo ignora y lee la parte sin cifrar |
| Flags 0x808 (descriptor de datos + nombre UTF-8) | aceptado |
| Paquete ZIP_STORED con entrada de directorio `word/` | aceptado |
| `word/` con BZIP2 | rechazado |
| Documento guardado con python-docx | aceptado |
| Bit 5 o bit 6 en los flags | `NotImplementedError` (ver P3-1) |

## Respuesta a las cuatro preguntas

1. **¿El P1 queda cerrado?** Sí. En 3.12, `ZipFile.open` elige el descompresor y decide el cifrado con el `ZipInfo` del directorio central. Lo que diga el encabezado local nunca llega al descompresor. Por eso la lista permitida sobre `info.compress_type` alcanza:
   - mentir en el encabezado local no sirve;
   - mentir en el central hace que los datos se lean como deflate o stored, que sí están acotados.

   Se recorre `infolist()` entero, así que también se revisan los nombres duplicados y las partes que no se piden. No encontré un camino a `ZipExtFile.read` con un método sin cota.

2. **¿Rechaza algún Word legítimo?** No en lo que probé: python-docx, ZIP_STORED, entradas de directorio guardadas, y flags de descriptor de datos y UTF-8. Con archivos reales de Word, LibreOffice y Google Docs **no lo ejecuté**: en el repositorio no hay ningún .docx. Que esos programas escriben solo deflate o stored, sin el bit 0, lo sé del formato, no lo medí.
   - Un Word protegido con contraseña no es un ZIP sino un archivo OLE, así que ya falla antes como `BadZipFile`.
   - Una entrada de directorio con BZIP2 o LZMA se rechaza. No conozco ninguna herramienta que las escriba así.

3. **¿Las pruebas y las mutaciones pueden fallar?** Sí.
   - La prueba de BZIP2/LZMA le pone a `ZipFile.open` un reemplazo que falla si se lo llama, así que detecta un control puesto después de abrir.
   - La de deflate64 detecta una lista de métodos prohibidos en lugar de una lista de permitidos.
   - El script exige `Ran` + exit 1 + `FAILED`, así que un proceso que se murió no cuenta como "detectada".
   - Que una mutación no aplique exactamente una vez corta la corrida.
   - `mutations.txt` se generó en `a2ef2fc`. Como `bfa579b` no toca código, sigue valiendo, y mi corrida en `bfa579b` dio lo mismo.

4. **¿WI29-P3-2 dice la verdad?** Sí.
   - Que se rechaza con `too_many_entries`, después de que zipfile armó un registro por entrada: verificado.
   - "Más de tres veces su tamaño": medí 5,2 veces.
   - "Unas diez veces el límite de subida": 449/47,7 ≈ 9,4.
   - El límite de subida de transcripción y de plantilla es 50 MB (`server.py:50`).

   Matiz: la reproducción mide con `tracemalloc`, que cuenta solo lo que reserva Python y no el pico del proceso. Para lo que afirma alcanza.

## Hallazgos
- **P0:** ninguno.
- **P1:** ninguno.
- **P2:** ninguno.
- **P3-1. Dos bits de flag siguen dando error técnico en vez de rechazo.**
  - Dónde: `meetingtool/word_package.py:51` (ejecutado).
  - Qué pasa: una parte con el bit 5 (0x20) o el bit 6 (0x40) en el central lanza `NotImplementedError` desde `zipfile.open`, y ninguna de las tres rutas lo atrapa. El servidor responde 500 con "app.unexpected" (`server.py:207`) y el trabajo termina con el error técnico (`jobs.py:526`). No cuesta memoria.
  - Por qué importa: es justo lo que la prueba nueva dice haber resuelto ("refused, not a crash"), pero solo para el bit 0.
  - Arreglo mínimo: `ENCRYPTED = 0x1 | 0x20 | 0x40`, con un caso más en la subprueba.
- **P3-2. Datos deflate corruptos dan `zlib.error` sin atrapar.**
  - Dónde: `transcript.py:65` y `document.py:455` (ejecutado con `bz_c8.docx`).
  - Qué pasa: `zlib.error` no es `OSError`, así que tampoco se atrapa. Ya pasaba antes de WI29; no es regresión.
  - Arreglo mínimo: agregar `zlib.error` a las tuplas de excepciones.
- **P3-3. Bytes de control invisibles en la prueba.**
  - Dónde: `tests/test_word_package_limits.py:98` (leído y verificado por bytes).
  - Qué pasa: los literales `b"PK\x03\x04"` y `b"PK\x01\x02"` tienen los bytes 0x03 0x04 0x01 0x02 crudos, no escritos como secuencias de escape. Al leerlo se ve `b"PK"`, y yo mismo lo leí primero como un error del helper. Hoy funciona; si un editor los borrara, la prueba fallaría en vez de pasar en silencio.
  - Arreglo mínimo: escribirlos con escapes, como en la línea 88.

**Nota menor:** el pedido dice "carpeta vacía", pero `mutations.py` hace `copytree` y falla si la carpeta ya existe. Hay que pasarle una ruta que no exista.

## Limitaciones residuales
- No probé archivos reales de Word, LibreOffice ni Google Docs (pregunta 2).
- Medí solo en Python 3.12.10. La garantía depende de que `zipfile` siga tomando el método del directorio central.
- Siguen abiertas WI29-P3-1 (memoria del lector XML dentro del límite) y WI29-P3-2 (directorio central), ya registradas.

**Veredicto: aprobar.**

Lo que sigue lo decide el owner: integrar, y si quiere, anotar o corregir los tres P3.

## Lo que se hizo con cada hallazgo

- P1 (BZIP2/LZMA saltean la cota de memoria): corregido en a2ef2fc. `word_package.read_parts` rechaza, antes de abrir nada, toda entrada que no sea almacenada o deflate y toda entrada cifrada; mensaje `package.unreadable_part` en es/en; tres pruebas nuevas y dos mutaciones nuevas.
- P2 (memoria del directorio central): registrado como `WI29-P3-2` con su reproducción.
- P3-1 de la primera (la justificación del docstring): no se cambió el diseño; queda dicho que contar los bytes es una elección válida.
- Segunda revisión, P3-1 (bits 5 y 6 de las banderas): corregido en 0360f0f. P3-3 (bytes de control crudos en la prueba): corregido en 0360f0f. P3-2 (`zlib.error` de un deflate corrupto, sin atrapar): ya ocurría antes de WI29 y no cuesta memoria; queda dicho en `changed-tests.md`.
