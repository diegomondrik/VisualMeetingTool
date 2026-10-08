# Revisiones de WI20 (01M46KHBYCXMGM0K6N2RM651PE): la independiente y la de seguridad, commit 860751c contra main 03b8573

Por el buzón de INGOL, 2026-10-05. El texto de cada revisión es su respuesta tal como llegó; el implementador sólo bajó un nivel sus títulos.

## Revisión independiente (rol `revisor-independiente`)

## Revisión independiente — WI20 de VisualMeetingTool (`860751c`, base `03b8573`)

**Veredicto: aprobar con correcciones.** No encontré nada bloqueante (ni P0 ni P1). Hay dos P2 que conviene arreglar antes del PR, y al commit todavía le falta la evidencia que los criterios AC08 y AC09 piden "antes del PR".

### Qué leí
- El contrato y el plan del work item.
- `git diff 03b8573 860751c`: 30 archivos. Todos caen dentro de las superficies que el contrato declara; no hay cambios fuera de ellas.
- Con más detalle: `disk.py`, `store.py`, `jobs.py`, `company.py`, `gemini.py`, `qa.py`, `writer.py`, `document.py`, `pages.py`, `app.js`, las pruebas cambiadas y `test_data_integrity.py`.

No leí historial ni handoffs.

### Qué corrí
| Comando | Resultado |
|---|---|
| `python -m unittest discover -s tests` | 410 pruebas OK, 3 salteadas (las `test_d1_*`, por no tener los kits) |
| Con los kits: `test_d1_wi20_fallas` y `test_d1_barrido` | 8 OK (236 s) |
| Con los kits: AR01, AR02 y AR03 de `test_d1_hallazgos_arquitecto` | 3 OK |
| `compare_pilot_tests.py` contra las pruebas del piloto en el repo de INGOL | Las 9 clases son iguales; sale con 0 |
| `diff` completo de las dos copias contra el original de INGOL | Fuera de las clases sólo cambian los imports y el docstring; no hay funciones sueltas que el comparador deje sin mirar |
| `mutations.py` sin los kits | Detecta las 16 mutaciones; sin mutar, 28 OK |
| Tres scripts propios en el scratchpad | Uno por hallazgo P2-1, P2-2 y P3-1 |

No corrí AR05 ni AR10, que tardan más de 20 minutos. Mi conclusión no depende de ellas: las pruebas sin kits ya cubren el candado y los ajustes, y las mutaciones lo confirman.

### Hallazgos

**P2-1 — Crear un proyecto se queda con una carpeta suelta hecha por los comandos.**
- **Dónde:** `meetingtool/projects/store.py:139-145`.
- **Qué pasa:** si la carpeta ya existe y no tiene `project.json`, `create_project` la toma como "una creación cortada" y escribe adentro. Antes de este cambio la rechazaba con `projects.exists`. Una carpeta de resultados hecha con los comandos (la que la aplicación lista como de sólo lectura) se convierte en un proyecto vacío y desaparece de esa lista. Sus archivos no se borran.
- **Cómo lo mostré (ejecutado):** armé `data/acme/` con `summary.md` y un frame. `create_project(data, "Acme")` lo aceptó y dejó en la carpeta `frame_001…jpg`, `knowledge.md`, `project.json` y `summary.md`.
- **Arreglo mínimo:** reusar la carpeta sólo si está vacía, sin contar los temporales `.*.partial`. Es exactamente lo que deja una creación cortada. Vale lo mismo para la carpeta de una reunión.

**P2-2 — Una corrida cortada al cerrar la aplicación conserva lo pagado, pero la página dice que costó US$0.**
- **Dónde:** `meetingtool/app/jobs.py:416-420` (escribe `kept.json` con `paid_usd: 0.0` al empezar) y `:250-266`.
- **Qué pasa:** el costo y la etapa se escriben sólo en `_settle_failure`, y si el proceso muere esa función nunca corre. En el próximo arranque la corrida sigue guardada y listada, pero la página muestra etapa "—" y "US$0,000". El AC07 pide que la página diga "lo que costó". Consecuencia: la persona descarta algo creyendo que no pagó nada, y procesar de nuevo lo vuelve a pagar.
- **Cómo lo mostré (ejecutado):** simulé la carpeta que deja un proceso muerto después de la lectura y corrí `clear_leftovers` y `project_page`. La fila salió con `—` y `US$0,000`.
- **Arreglo mínimo:** guardar el costo en cada archivo de respuesta guardada y sumarlo en `kept_runs`, o actualizar `paid_usd` cada vez que se guarda una respuesta.

**P3 (limitaciones conocidas; no reabren el ciclo):**
1. **El candado puede bloquearse a sí mismo con dos nombres de la misma carpeta.**
   - **Dónde:** `disk.py:120`.
   - **Qué pasa:** la reentrada reconoce la carpeta por `normcase(abspath)`, no por la ruta real. Si un mismo hilo toma el candado con un nombre y después con otro de la misma carpeta (por ejemplo, el nombre corto 8.3 de Windows), espera su propio candado hasta el límite y falla.
   - **Cómo lo mostré (ejecutado):** con la ruta larga y su nombre corto, el segundo intento falló por tiempo (`LockTimeout`) a los 2 s.
   - **Alcance:** hoy ninguna llamada anidada cambia de nombre. Entre procesos y entre hilos la exclusión sí vale, porque el bloqueo es sobre el mismo archivo.
   - **Arreglo:** usar `os.path.realpath`.
2. **Descartar no está protegido contra una corrida que arranca en ese momento.**
   - **Dónde:** `server.py:352-356` y `jobs.py:268-281`.
   - **Qué pasa:** el servidor atiende cada pedido en su propio hilo. Entre la comprobación de que no hay corrida en curso y el borrado, puede arrancar una corrida que retoma esa misma carpeta. La ventana es chica. Lo vi leyendo el código.
   - **Arreglo:** hacer la comprobación y el borrado bajo `runner.lock`.
3. **Las partes guardadas de preguntas y respuestas no distinguen el modelo.**
   - **Dónde:** `qa.py:798`.
   - **Qué pasa:** la huella de cada parte cubre sólo el texto del pedido, no el modelo ni la configuración. Entonces lo que dice el AC06 ("otro modelo paga de nuevo") no se cumple para estas partes.
   - **Alcance:** hoy no se puede llegar ahí desde la aplicación ni desde los comandos, porque ninguno deja elegir el modelo.
4. **Quedan restos de un intento anterior en la carpeta del resultado.**
   - **Dónde:** `jobs.py:421-433`.
   - **Qué pasa:** pueden quedar `frames_read_qa.md` si el nuevo intento no lee imágenes, el registro de imágenes descartadas, y hasta una copia de la grabación si un intento anterior falló al sacar las imágenes. Eso contradice el README ("the recording itself is not copied").
   - **Alcance:** nada los usa para armar el resumen ni el informe, así que la salida no se mezcla. Lo vi leyendo el código.
5. **El costo de una reunión retomada queda por debajo de lo pagado.**
   - **Dónde:** `jobs.py:475`.
   - **Qué pasa:** `run.json` registra sólo lo gastado en el último intento, y lo pagado antes se pierde al borrar `kept.json`. La prueba propia lo confirma: espera `spent_usd == 0`.
6. **La plantilla y su registro no se escriben como una sola cosa.**
   - **Dónde:** `document.py:217-219`.
   - **Qué pasa:** se escriben como dos archivos. Un corte entre los dos deja la plantilla nueva con el nombre de la anterior. Ya pasaba antes de este cambio; sólo afecta lo que se muestra.

**Pruebas cambiadas (punto 5).** Cada cambio corresponde a la regla nueva aprobada o a la existencia del archivo del candado, y no encontré ninguno que debilite otra garantía. Lo único es un nombre: `test_a_meeting_that_cannot_be_recorded_leaves_no_folder` ahora sí deja una carpeta, a propósito.

**Mecanismo más simple (punto 6).** Un caché de respuestas pagas por proyecto, indexado por la huella del pedido, daría la misma garantía de "no pagar dos veces el mismo pedido". Y la regla "si falla, no queda nada de la corrida" podría seguir como estaba. Se eliminarían `kept.json`, la búsqueda de la corrida a retomar, el reacomodo al arrancar, el botón de descarte y los restos del punto 4. Tiene dos condiciones: que sacar las imágenes dé siempre los mismos bytes, y alguna forma de vaciar el caché. Además cambia el diseño aprobado, así que lo dejo como observación, no como defecto.

### Criterios
- **AC01 — cumplido.** El comparador da las 9 clases iguales. Con los kits corrí y pasaron AR01–AR03 y las tres de `test_d1_barrido`; AR05 y AR10 no los corrí.
- **AC02 — cumplido.** Las pruebas de cortes con kits y las sin kits pasan, y las mutaciones de "escribir en el lugar", "reacomodo al arrancar" y "conocimiento sin rehacer" se detectan.
- **AC03 — cumplido.** Las pruebas de dos operaciones a la vez pasan, y las mutaciones del candado, del identificador y de los ajustes se detectan.
- **AC04 — cumplido.** La prueba con un comando de la terminal en otro proceso pasa, y la mutación "candado en memoria" se detecta.
- **AC05 — cumplido.** El registro ilegible se nombra en los dos idiomas, y la corrida termina "failed" sin dejar carpeta de resultados (prueba y mutación).
- **AC06 — cumplido, con la salvedad del P3-3.** Las partes de preguntas y respuestas no distinguen el modelo, aunque hoy no se pueda llegar ahí.
- **AC07 — cumplido para las corridas que fallan; no cumplido para una corrida cortada al cerrar la aplicación.** En ese caso la página dice que costó US$0 (P2-2).
- **AC08 — parcial.** Las 16 mutaciones se detectan sin kits (lo corrí). La corrida con kits no la verifiqué, y `mutations.txt` no está commiteado en la evidencia, aunque el criterio lo exige.
- **AC09 — no cumplido todavía.** Falta `local-test-run.txt` de un clon limpio, y el registro de limitaciones no tiene ninguna limitación de WI20 (sólo marca WI03-P3-4 como arreglada). Estos P3 son los candidatos a cargar ahí. La suite sin kits pasa en mi corrida.

**Veredicto: aprobar con correcciones** — arreglar P2-1 y P2-2, y commitear `mutations.txt`, `local-test-run.txt` y el registro con estos P3 antes de abrir el PR.

Lo que sigue lo hace el implementador: esas correcciones y la evidencia en el mismo commit, y después abrir el PR.

## Revisión de seguridad (rol `revisor-seguridad`)

## Revisión de seguridad de WI20 (VisualMeetingTool, commit `860751c`, diff contra `03b8573`)

No encontré nada explotable de severidad P0, P1 ni P2. Sólo queda un P3 de endurecimiento, y no lo puede disparar un tercero. Las 94 pruebas pedidas (`tests.test_data_integrity tests.test_app`) pasan.

### Hallazgos

#### P3: el control de "corrida en curso" del descarte no es atómico (sólo leído, no ejecutado; confianza 80)
- **Dónde:** `meetingtool/app/server.py:352-355` y `meetingtool/app/jobs.py:268-276`.
- **El problema:** el servidor primero pregunta si hay una corrida en curso (`app.runner.running()`) y después llama a `discard_kept`, que hace `shutil.rmtree`. Entre los dos pasos no hay ningún candado: ni `runner.lock` ni el candado del disco. Como el servidor atiende pedidos en paralelo (`ThreadingHTTPServer`), un `POST /api/process` de la misma reunión puede arrancar justo en ese intervalo, retomar esa carpeta (`_kept_for`) y quedarse sin ella.
- **Qué puede pasar:** la corrida falla y vuelve a pagar lo que estaba guardado. Nada se borra fuera de `<datos>/<proyecto>/processing/<corrida>`.
- **Quién puede provocarlo:** sólo el propio usuario, con dos pestañas y una coincidencia de milisegundos. Un tercero no: la ruta exige cookie de sesión, `X-MeetingTool: 1`, JSON, Host, Origin y Sec-Fetch-Site válidos.
- **Arreglo mínimo:** hacer el control y el borrado bajo `app.runner.lock`, y que `start` tome ese mismo candado. Alcanza con un método `Runner.discard(...)` que haga las dos cosas juntas.

### Respuestas a las cinco preguntas

**1. ¿La ruta de descarte puede borrar algo fuera de `processing/<corrida>`? No.** Lo probé ejecutando, con datos sintéticos en `C:/Users/Diego/AppData/Local/Temp/vmt-wi20-sec-repro-15433`:
- **Identificadores hostiles:** todos dan `NotFound` y la corrida real queda intacta. Probé `..`, `../..`, `..\..`, mayúsculas (`…-T-ABC123`, `Proyecto`), `C:\Windows`, `con`, `processing`, espacio o barra al final, `None` y listas.
- **Por qué no hay forma de escaparse:** `is_slug` sólo acepta `[a-z0-9-]`, y además la corrida tiene que figurar en `kept_runs`, que sale de `iterdir()`.
- **Junction en `processing/<corrida>` apuntando afuera:** el descarte termina en `OSError: Cannot call rmtree on a symbolic link` y la carpeta de afuera queda intacta.
- **Junction dentro de la corrida (`paid-answers` → afuera):** se borra el enlace y el destino queda intacto.
- **Corrida en curso:** el servidor la rechaza, salvo la carrera del P3.

**2. Lo guardado y la clave de Gemini: no hay fuga ni mezcla entre pedidos.** Lo ejecuté con un transporte falso, sin red:
- **Contenido guardado:** cada archivo de `paid-answers/` contiene sólo `{"answer", "model"}`. La clave no aparece, porque viaja en la cabecera `x-goog-api-key` y no en la URL. `kept.json` tampoco la lleva: tiene la huella, el título, la fecha, el formato, las fechas de inicio y falla, la etapa que falló y el monto pagado.
- **Huella:** se calcula sobre el modelo y el contenido exacto del pedido. Un pedido distinto por un solo carácter vuelve a pagar. Además las respuestas guardadas viven dentro de la carpeta de cada corrida, que sólo se retoma con el mismo proyecto, el mismo formato y los mismos bytes de transcripción.
- **Respuesta manipulada a mano:** se vuelve a validar con el mismo `check` que una respuesta nueva (`gemini.py:201`; lo mismo hace `qa._kept_part`):
  - Si no pasa el control (bloques que no coinciden, o un tipo que no es texto), se descarta y se paga de nuevo.
  - Si pasa, entra igual que una respuesta nueva de Gemini. Probé texto con `<script>` y frases de inyección: no tiene más poder que una respuesta real, y la página escapa lo que muestra.
- **Para manipularla hay que escribir en la carpeta de datos.** Quien puede hacer eso ya puede editar `knowledge.md` o los informes directamente, así que no se gana nada nuevo.

**3. Candado y temporales: no hay una carrera explotable.**
- Los temporales se llaman `.<nombre>.<12 hex de secrets>.partial`, así que no se pueden predecir.
- El candado es un bloqueo del sistema sobre `.meetingtool-write.lock`, que se abre en modo `a+b` sin escribir nada.
- Otro proceso del mismo usuario puede retener el candado, pero sólo consigue que los demás fallen a los 30 segundos con un mensaje claro. Ese proceso ya tiene acceso total a los datos, así que no cruza ninguna frontera. Esto lo leí, no lo ejecuté.

**4. `clear_leftovers` no toca nada que no esté bajo la carpeta de datos.** Lo ejecuté:
- **Junctions en `processing/` sin nada pagado, o dentro de una corrida:** `rmtree(..., ignore_errors=True)` se niega a seguirlos y lo de afuera queda intacto.
- **Una junction en `results/` que contiene `kept.json`:** se mueve el enlace en sí, no su contenido, y el destino queda intacto.
- **Comparado con antes:** el código anterior hacía `rmtree` de todo `processing/`; ahora borra menos.
- **Corridas de otra instancia:** sólo hay una aplicación por carpeta de datos (`DataFolderLock`), así que no puede pisar una corrida de otra instancia.

**5. Los textos nuevos de la página van escapados.** Lo ejecuté con el título `"><img onerror…> <script>…`:
- **Página del proyecto:** en `data-confirm` (`pages.py:268`) llega todo escapado, tanto en castellano como en inglés. `view.t` usa `html.escape(quote=True)`.
- **Nombre de la corrida:** es un slug y también pasa por `e()`.
- **Monto:** se convierte a número en `kept_runs`.
- **JavaScript:** usa `textContent` y `window.confirm` con texto plano (`app.js:83` y el nuevo `keptNotice`).

### Observación (no es una vulnerabilidad)
Con la regla nueva, que el owner aprobó, una corrida fallida que pagó algo deja en `processing/` la transcripción, los cuadros y las respuestas de Gemini hasta que la reunión se procese de nuevo o el usuario la descarte. Antes eso se borraba al fallar. Queda dentro de la carpeta de datos, fuera del repositorio, y se lista con su botón de descarte.

**Conclusión: el cambio no abre ninguna vía de explotación que antes no estuviera abierta. Lo único que cambia es cuánto tiempo quedan en disco los datos de cliente de una corrida fallida, y eso es una decisión aprobada.**

Varios conectores MCP de claude.ai (GitHub, Gmail, Drive, entre otros) piden autorización. No hicieron falta para esta revisión; si los querés usar, se habilitan desde la configuración de conectores de claude.ai.

Lo que sigue: el owner decide si el P3 se arregla antes del PR o queda anotado como limitación conocida.

## Lo que se hizo con cada hallazgo

Una sola pasada de corrección. Las dos revisiones, del commit `860751c`, llegaron
por el buzón de INGOL: motor Claude, rol `revisor-independiente` y rol
`revisor-seguridad`, cuenta empresa, modelo pedido por rol (`rol:criterio`,
resuelto a `opus`), esfuerzo alto. Ninguno de los dos roles tiene
herramientas de escritura. El texto de arriba es su respuesta tal como llegó.

| Hallazgo | Qué se hizo | Prueba que lo fija | Mutación |
|---|---|---|---|
| Independiente P2-1: crear un proyecto se queda con una carpeta de los comandos | Arreglado. Una carpeta existente se reutiliza sólo si no tiene nada más que los temporales que deja un corte (`store._left_by_a_cut`); vale también para la carpeta de una reunión | `TwoAtOnceTest.test_a_folder_of_the_commands_is_not_taken_over_by_a_new_project`, `test_a_folder_a_cut_left_empty_is_taken` | "a folder of the commands taken over by a new project" |
| Independiente P2-2: una corrida cortada al cerrar dice que costó US$0 | Arreglado. Cada respuesta guardada lleva lo que costó (`cost_usd`, con sus reintentos), también las partes del registro de preguntas; lo pagado de una corrida guardada es el mayor entre su registro y la suma de sus respuestas (`jobs.kept_cost`) | `KeptRunTest.test_a_run_cut_by_closing_the_application_says_what_it_paid` | "what a cut run paid read only from its record" |
| Independiente P3-1: el candado se bloquea con dos nombres de la misma carpeta | Arreglado: la reentrada usa la ruta real (`os.path.realpath`) | `TwoAtOnceTest.test_one_thread_takes_the_lock_again_under_another_name_of_the_folder` (con el nombre corto 8.3 de Windows) | — |
| Independiente P3-2 y seguridad P3: descartar y arrancar una corrida pueden cruzarse | Arreglado: `Runner.discard` controla y borra bajo el mismo candado con el que `Runner.start` arranca una corrida | `KeptRunTest.test_nothing_is_discarded_while_a_meeting_is_processed` | "a discard while a meeting is being processed" |
| Independiente P3-3: las partes guardadas del registro no distinguen el modelo | Limitación conocida `WI20-P3-1`: hoy no se puede elegir el modelo | `reproduce.py WI20-P3-1` | — |
| Independiente P3-4: restos de un intento anterior en el resultado | Arreglado: una corrida que se retoma borra de su carpeta todo salvo lo pagado (`paid-answers/`, `qa-parts/`) y `kept.json` | `KeptRunTest.test_a_resumed_run_keeps_only_what_was_paid_and_says_what_was_paid_before` | "a resumed run that keeps the attempt before's other files" |
| Independiente P3-5: el costo de una reunión retomada queda por debajo de lo pagado | Arreglado: `run.json` dice también `paid_before_usd`, lo que pagaron los intentos anteriores | la misma prueba | — |
| Independiente P3-6: la plantilla y su registro no se escriben como una sola cosa | Limitación conocida `WI20-P3-2` (ya pasaba antes de WI20) | `reproduce.py WI20-P3-2` | — |
| Independiente AC08 y AC09: falta la evidencia | `mutations.txt` y `local-test-run.txt` se generan sobre el commit corregido; el registro de limitaciones tiene ahora la sección de WI20 (`WI20-P3-1` a `WI20-P3-7`) | — | — |
| Independiente, mecanismo más simple (un caché por proyecto en lugar de conservar la corrida) | No se adopta: cambiaría el diseño aprobado por el owner ("lo pagado queda hasta que se procese de nuevo o se descarte") y supone que sacar las imágenes da siempre los mismos bytes | — | — |
| Seguridad, observación: los datos de una corrida fallida quedan en disco más tiempo | Es la regla aprobada; queda como `WI20-P3-7`, "open, by design" | `reproduce.py WI20-P3-7` | — |
| Independiente, nombre de una prueba: `test_a_meeting_that_cannot_be_recorded_leaves_no_folder` ahora deja una carpeta a propósito | Se deja el nombre: la prueba es anterior a WI20 y su cambio está explicado en `changed-tests.md` | — | — |

Ningún hallazgo fue P0 ni P1. Los P3 que quedan abiertos son limitaciones
conocidas y no reabren el ciclo.
