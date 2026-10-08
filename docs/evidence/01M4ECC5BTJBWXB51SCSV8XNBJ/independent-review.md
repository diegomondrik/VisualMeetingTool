# Revisión independiente de WI32 (01M4ECC5BTJBWXB51SCSV8XNBJ)

Revisor independiente por el buzón de INGOL (rol `revisor-independiente`, sin herramientas de escritura): el texto es el que devolvió, copiado por el implementador. Al final, lo que se hizo con cada hallazgo.

## Revisión del commit ae54101, 2026-10-08: aprobar con correcciones

# Revisión independiente de WI32 (VisualMeetingTool): commit `ae54101` contra la base `2a6766f`

**Veredicto: aprobar con correcciones.** No está listo para abrir el PR: la reproducción de D1-01 no es estable, así que WI32-AC01 no se cumple. Además, la de D1-05 escribe dentro del repositorio, así que WI32-AC02 tampoco se cumple. Las dos correcciones son chicas y quedan dentro de `docs/limitations/reproduce.py`.

## Qué leí
- El contrato, el plan y `git diff 2a6766f ae54101`. El diff toca 4 archivos: los dos del work item, `REGISTER.md` y `reproduce.py`.
- El código de producción en el que se apoya cada afirmación del registro:
  - `report/document.py:915-929`
  - `frames/extract.py:238-253`
  - `app/jobs.py:340-358`, `jobs.py:398-405` y `jobs.py:544-566`
  - `projects/store.py:210-229` y `store.py:280-297`
  - `summary/qa.py`
- Los fixtures que usan las reproducciones: `test_report`, `test_qa`, `test_data_integrity`, `test_texts.StageLanguageTest` y `test_reading.FakeGemini`.
- No leí el borrador del juez, que no está en el repositorio.

## Qué ejecuté
| Comando | Resultado |
|---|---|
| `reproduce.py D1-01 D1-02 D1-04 D1-05 D1-09` | 5 MATCH, salida 0 |
| `reproduce.py D1-01` repetido 12 veces | **7 MATCH, 3 MISMATCH (`seen=fixed`), 2 ERROR** |
| `reproduce.py D1-02 D1-04 D1-05` repetido 5 veces | 15 de 15 MATCH |
| `reproduce.py` (el registro entero) | 86 MATCH, 0 MISMATCH, 4 SKIPPED, 3 ERROR: WI05-P3-5, WI05-P3-7 (también fallan en main) y **D1-01** |
| `StageLanguageTest` a mano, con la carpeta temporal dentro de `3-de-codex` y en una carpeta normal | 2 fallas `['de'] != []` en el primer caso; OK en el segundo |
| `git status --ignored` después de correr | quedó **`meetingtool/__pycache__`, `meetingtool/projects/__pycache__` y `meetingtool/texts/__pycache__`** dentro del repositorio |

## Hallazgos

**P1-1. La reproducción de D1-01 no es determinista** (`reproduce.py:1527-1567`). Lo ejecuté.
- **Qué pasa:** la barrera sincroniza los dos hilos *después* de guardar. No controla cuál de los dos guarda último ni impide que los dos guarden a la vez.
  - Si A guarda último, el archivo trae "Title A" y la reproducción da `seen=fixed` (MISMATCH).
  - Si los dos guardados se pisan, el paquete queda corrupto. A muere con `BadZipFile`, que no es un `ReportError`, y `docx.Document` termina en `PackageNotFoundError` (ERROR).
- **Consecuencia:** en 5 de 12 corridas el registro sale con código 1, y en 3 de ellas dice que D1-01 está corregida cuando no lo está. El control "determinista" de AC01 no lo es.
- **Arreglo mínimo:** forzar el orden.
  1. Arrancar B recién cuando A ya guardó y entró a `check`: A marca `a_saved` y espera `b_saved`; B marca `b_saved` y espera `a_done`.
  2. Correrla 20 veces o más y guardar esa salida como evidencia.

**P1-2. D1-05 escribe bytecode dentro del repositorio** (`reproduce.py:1640-1646`). Lo ejecuté.
- **Qué pasa:** `subprocess.run([sys.executable, "-c", code])` hereda el entorno sin `PYTHONDONTWRITEBYTECODE`. Los `.pyc` que aparecen son justo los de los módulos que importa ese subproceso (`store`, `disk` y `texts`), con la hora de esa corrida. Las demás entradas que lanzan subprocesos sí desactivan el bytecode (líneas 69, 919 y 1667).
- **Consecuencia:** WI32-AC02 ("writes only to temporary folders") no se cumple, y se rompe lo que el propio docstring del script promete ("not even Python's bytecode cache"). El daño práctico es nulo, porque `.gitignore` ignora esos archivos.
- **Arreglo mínimo:** pasar `env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}` o el flag `-B`.

**P2-1. D1-09 puede dar MATCH por una razón equivocada** (`reproduce.py:1659-1671`). Lo leí y lo ejecuté a mano.
- **Qué pasa:** la reproducción sólo comprueba que la corrida falle (código distinto de 0 y "FAILED"). No corre la versión de control en una carpeta normal, aunque el registro dice "in the normal folder: OK". Tampoco comprueba que la falla sea por la palabra `de`.
- **Hoy las dos afirmaciones son ciertas:** lo comprobé a mano. Pero cualquier otra rotura de `StageLanguageTest` mantendría D1-09 como "open".
- **Arreglo:** agregar la corrida de control (que tiene que dar 0) y exigir `['de']` en la salida de error.

**P3-1. D1-08 figura como cerrada por un work item que todavía no está integrado** (`REGISTER.md:267`, "D1-08 is R11 (work item 31)").
- WI31 no está ni en la base ni en el candidato. Existe en una rama (`…01M4CM3YV9HEAHSW5V5ER4V8W7-tested-versions-and-guide`) que no está mergeada.
- No pude verificar que R11 sea D1-08, porque el borrador del juez no está.
- **Arreglo:** decir "la cierra WI31, no integrado todavía" o confirmarlo antes del merge.

**P3-2. La entrada de D1-01 se queda corta en un caso** (`REGISTER.md:274`). Lo vi al ejecutar.
- Las corridas con ERROR muestran un tercer desenlace: los dos guardados se pisan, el paquete queda corrupto y A falla con una excepción que no es un `ReportError`.
- La entrada sólo describe "una tiene éxito con el documento de la otra y la otra falla". Es opcional mencionarlo.

## Lo que encontré bien sustentado (leído y ejecutado)
- **D1-01:** el temporal compartido existe (`document.py:915`), y la extracción borra las imágenes viejas antes de escribir las nuevas (`extract.py:239-253`). "Nothing the application does reaches the first" se sostiene: hay un único trabajo a la vez (`jobs.py:403-405`).
- **D1-02:** `os.replace` falla, entonces `rmtree(final)` y no queda nada que retomar (`jobs.py:550-553`). Coincide con lo que muestra la reproducción: 2 pedidos pagos y `kept: None`.
- **D1-04:** el transcript del fixture tiene dos preguntas explícitas ("Primera duda: ¿…?" y "Segunda duda: ¿…?"). La respuesta vacía se acepta y se entrega con el texto `no_questions` (`qa.py:91`).
- **D1-05:** `os._exit` evita la limpieza de `add_meeting`. Lo de "the next start repairs it" es cierto: `clear_leftovers` reconstruye el conocimiento (`jobs.py:340-358`).
- **Probabilidad para un usuario:** las condiciones están dichas con honestidad (dos comandos sobre una misma carpeta, dos fallas seguidas, frecuencia no medida). La gravedad aparece como la del juez. No veo exageración ni minimización, salvo P3-2.
- **Red:** el Gemini falso escucha sólo en `127.0.0.1` (`test_reading.py:90`). No vi ninguna otra conexión.
- **Procesos:** no queda ningún proceso vivo; el subproceso de D1-05 muere con `os._exit(77)`.
- **Temporales:** las cinco entradas limpian sus carpetas temporales. Quedan carpetas `vmt-limitations-*` en `%TEMP%` de entradas WI03 anteriores (`ignore_cleanup_errors`). Ya pasaba antes de este cambio y no es de WI32.
- **Coherencia del registro:** el chequeo de conjunto del script pasó, así que cada entrada tiene su reproducción y cada reproducción su entrada. Las nueve ids D1-01..D1-09 del contrato están todas contabilizadas. No puedo descartar ids del juez que no figuren en el contrato.

## Criterios
- **WI32-AC01: no se cumple.** Las entradas y las reproducciones están, y el registro dice qué pasó con los otros hallazgos, pero D1-01 no da MATCH de forma estable (P1-1).
- **WI32-AC02: se cumple a medias.** El diff toca sólo superficies declaradas, pero D1-05 escribe `__pycache__` dentro del repositorio (P1-2).
- **WI32-AC03: pendiente.** Esta revisión cubre su primera mitad. Todavía no existe `docs/evidence/01M4ECC5BTJBWXB51SCSV8XNBJ/` ni la corrida de la suite en un clon limpio.

## Lo que queda abierto
- No verifiqué que R11 sea D1-08 ni que no haya otros hallazgos del juez fuera del contrato (el borrador no está).
- La frecuencia de D1-04 con el Gemini real sigue sin medir, como el propio contrato reconoce.

**Qué sigue:** el implementador corrige P1-1 y P1-2 (y P2-1, si quiere) en `reproduce.py`, corre D1-01 20 veces o más y el registro entero, y guarda esas salidas como evidencia antes de abrir el PR.

## Lo que se hizo con cada hallazgo

- P1-1 (la reproducción de D1-01 no era determinista): corregida. El orden de los dos hilos se fuerza (A guarda y espera; B guarda encima; A comprueba y mueve; recién entonces B comprueba). 20 corridas seguidas dieron MATCH las 20 [`d1-01-20-runs.txt`].
- P1-2 (la reproducción de D1-05 escribía bytecode dentro del repositorio): corregida con `-B` y `PYTHONDONTWRITEBYTECODE=1` en el subproceso. Comprobado: ningún `.pyc` más nuevo que el inicio de una corrida de las cinco entradas.
- P2-1 (D1-09 podía dar MATCH por otra razón): corregida. Ahora corre además la versión de control en una carpeta normal (tiene que pasar) y exige `['de']` en la salida del fallo.
- P3-1 (D1-08 figuraba cerrada por un work item no integrado): al corregir, WI31 ya estaba integrado (PR #30).
- P3-2 (un tercer desenlace de D1-01): agregado a la entrada del registro.
- Las reproducciones de WI05-P3-5 y WI05-P3-7, que fallaban en main antes de este trabajo, se repararon (se agregó al contrato, antes de su firma). El registro entero: 90 coincidencias, 0 errores [`register-run.txt`].
