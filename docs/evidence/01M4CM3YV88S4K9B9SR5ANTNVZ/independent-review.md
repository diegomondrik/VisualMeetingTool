# Revisión independiente de WI30 (01M4CM3YV88S4K9B9SR5ANTNVZ)

Revisor independiente por el buzón de INGOL (rol `revisor-independiente`, sin herramientas de escritura): el texto es el que devolvió, copiado por el implementador. Al final, lo que se hizo con cada hallazgo.

## Revisión independiente, 2026-10-08 (commit 3eac906): aprobar con correcciones

# Revisión independiente: WI30 de VisualMeetingTool (`3eac906` contra `main` `1a78ce4`)

**Veredicto: aprobar con correcciones.** No hay nada bloqueante. Hay una corrección corta antes del PR (P2-1), porque hoy el WI30-AC02 no se cumple al pie de la letra en Windows.

## Qué leí
- El contrato y el plan.
- Todo el `git diff 1a78ce4 3eac906`.
- `library.py` completo.
- Las partes de `store.py` que usa el cambio: `_project_dir`, `_read_record`, `add_meeting`, `slugify`.
- Los llamadores en `server.py`: `_segments`, `/p/…/m/…`, `/r/…` y `/api/open`.
- `changed-tests.md` y `mutations.py`/`.txt`.

No leí historial ni datos de clientes.

## Qué ejecuté
| Comando | Resultado |
|---|---|
| `python -m unittest tests.test_library_reads -v` | 25 pruebas, todas OK |
| `python -m unittest tests.test_app tests.test_projects tests.test_data_integrity tests.test_cli` | 123 pruebas, todas OK |
| `mutations.py` sobre `3eac906` (árbol limpio) | Las 7 mutaciones fallan las pruebas, como corresponde; la corrida sin mutar da OK. Coincide con `mutations.txt`, que se grabó en `12cf731`; entre los dos commits sólo cambian archivos de evidencia (lo comprobé con `git diff --stat`) |
| `git diff 1a78ce4 3eac906 -- tests/` | Sólo hay un archivo nuevo. Ninguna prueba anterior cambió, como dice `changed-tests.md` |
| Prueba propia en el scratchpad, sobre el código nuevo y sobre la base | Ver P2-1 y P3-2 |

No corrí la suite completa (unos 12 minutos). El contrato la deja a propósito para la corrida final en un clon limpio con los kits.

## Hallazgos

**P0 / P1:** ninguno.

**P2-1 — En Windows, un resultado suelto que la portada no muestra ahora se sirve.** Lo ejecuté.
- **Dónde:** `meetingtool/app/library.py:149-153` (`_loose_folder`). Cómo lo probé: creé una carpeta `data/Con-Mayuscula/` con `summary.md` y un cuadro.
- **Qué pasa:**
  - `library.loose()` no la lista, igual que antes.
  - `loose_file(data, "con-mayuscula", FRAME)` **devuelve el cuadro**. En la base daba `NotFound`.
  - La causa: `is_slug(name)` revisa el nombre que viene en el pedido, no el de la carpeta en disco. En un disco que no distingue mayúsculas (Windows, y macOS por defecto) `Path(data)/"con-mayuscula"` llega a `Con-Mayuscula`.
  - Afecta a `/r/<nombre>`, `/r/<nombre>/f/<archivo>` y `/api/open`.
- **Gravedad:** no cruza ninguna frontera de confianza. Sigue siendo la carpeta de datos del mismo usuario, en su máquina, con su sesión, y sólo sirve cuadros o el Word. Pero contradice dos cosas: "the paths served are the same as today" del WI30-AC02, y la coherencia entre lo que lista la portada y lo que se sirve por dirección.
- **Por qué las pruebas no lo ven:** `test_an_unknown_or_ill_formed_loose_name_is_not_found` sólo prueba el nombre literal `"Con-Mayuscula"`, no su versión en minúsculas.
- **Arreglo mínimo:** en `_loose_folder`, exigir además `name in os.listdir(data_dir)`. Eso lee nombres, no resúmenes, así que el AC01 se mantiene. Y agregar `"con-mayuscula"` a la lista de nombres malos de esa prueba.
- Es P2 porque no tiene consecuencia de seguridad. Si se aprueba sin corregirlo, el AC02 tiene que quedar como no cumplido en Windows y registrado como limitación.

**P2-2 — Pasar el error de lectura a 404 es innecesario y empeora el diagnóstico.** Lo leí y lo confirmé con la prueba del servidor.
- **Dónde:** `meetingtool/app/library.py:122-125`.
- **Qué pasa:** `meeting_record` convierte el `ProjectError` de un `meeting.json` dañado en `NotFound`. Quien abre esa reunión desde un marcador o con "abrir Word" (`/api/open`) ve "no encontrada" cuando la reunión existe y está rota.
- **No esconde el daño del todo:** la página del proyecto sigue cortando con 400 y nombra el archivo, y eso está fijado por `test_the_project_page_still_stops_on_a_broken_record_as_before`.
- **Mecanismo más simple con la misma garantía:** sacar el `try/except` y dejar que el `ProjectError` suba, que el servidor muestra como 400 con el nombre del archivo. Así una vecina rota sigue sin afectar a una reunión sana, porque sólo se lee el registro pedido. Cambian dos pruebas: `test_a_meeting_whose_record_cannot_be_read…` y `test_a_broken_meeting_does_not_stop_the_others_and_is_itself_not_found` pasan a esperar `ProjectError`/400. Y desaparece uno de los dos cambios de conducta declarados.
- El 404 es aceptable si el owner lo prefiere. No bloquea.

**P3-1 — Se deja de servir la reunión cuya carpeta no se llama igual que su id.** Lo leí y está probado por `test_a_record_found_in_a_folder_that_is_not_called_as_its_id_is_not_found`.
- `add_meeting` siempre crea la carpeta con el nombre del id (`store.py:213-223`). Ni siquiera la reutilización de una carpeta a medio crear produce un id distinto. La estructura documentada en `store.py:6` es `meetings/<meeting id>/meeting.json`.
- Sólo afecta datos editados o copiados a mano. En ese caso la página del proyecto lista la reunión pero su enlace da 404.
- Queda como limitación conocida. No verifiqué el "3 de 3" en los datos reales del owner: no los toqué.

**P3-2 — `read_meeting` acepta un id vacío.** Lo ejecuté.
- **Dónde:** `meetingtool/projects/store.py:255`, donde `"" == slugify("", fallback="")` da verdadero.
- **Qué pasa:** con `meeting_id=""` arma `meetings/meeting.json`. Por GET no se llega, porque `_segments` rechaza las partes vacías. Por `/api/open` con `target "proj/"` sí. Haría falta además un `meetings/meeting.json` puesto a mano con `"id": ""`.
- **Gravedad:** sin consecuencia práctica.
- **Arreglo:** `if not meeting_id or …`, o usar `library.is_slug`.

**P3-3 — El conteo de lecturas tiene un alcance limitado.**
- Cuenta sólo `Path.read_text` sobre `summary.md` y `open` sobre `meeting.json`. No cuenta los `glob`/`is_file` de `result()`.
- Igual mide bien lo que dice: las aserciones positivas (exactamente 1 resumen y 1 registro en la página) prueban que el contador ve las lecturas, y la mutación "vuelta a la lista" lo hace fallar.
- Como `result()` sólo se llama donde lee el resumen, no medir el recorrido de carpetas no deja ningún hueco hoy.

## Criterios
- **WI30-AC01 — cumplido.** Con 12 y con 30 reuniones: servir un cuadro o el Word lee 0 resúmenes y 1 registro por archivo; la página lee 1 y 1; lo mismo para los resultados sueltos y a través del servidor. Lo ejecuté y las mutaciones muestran que la prueba puede fallar.
- **WI30-AC02 — cumplido salvo P2-1.**
  - Que una vecina rota no afecta, que un identificador malo da "no encontrado", que las rutas siguen limitadas a un cuadro o al Word de `results/`, y que la portada y la página del proyecto listan igual: todo ejecutado.
  - En Windows, un resultado suelto que la portada no lista se sirve por su nombre en minúsculas.
- **WI30-AC03 — parcial, como estaba previsto.**
  - Las 7 mutaciones fallan las pruebas, y lo reproduje en `3eac906`.
  - Las pruebas cambiadas están nombradas: ninguna anterior cambió.
  - Esta revisión es la revisión independiente.
  - Faltan la corrida completa en un clon limpio con los kits (`local-test-run.txt`) y reproducir las limitaciones conocidas (`reproduce.py`).

## Qué queda abierto
- No corrí la suite completa ni la corrida con los kits. Eso queda para el paso final del AC03.
- La corrida dejó carpetas `__pycache__` en el clon descartable; no modifiqué nada versionado.

**Veredicto: aprobar con correcciones.** Corregir P2-1 antes del PR (o registrar el AC02 como no cumplido en Windows). P2-2 es recomendado, no obligatorio.

**Qué sigue:** el constructor aplica P2-1, y P2-2 si el owner lo elige, y después corre la suite final en un clon limpio con los kits. La única decisión del owner: si una reunión con el archivo dañado, abierta por su dirección, debe mostrar el error que nombra el archivo (como antes) o "no encontrada".

## Lo que se hizo con cada hallazgo

- P2-1 (en Windows un resultado suelto que la portada no lista se servía por su nombre en minúsculas): corregido en 8da90f4; `library._loose_folder` exige además que el nombre sea uno de los de la carpeta de datos en disco; prueba y mutación nuevas.
- P2-2 (404 en lugar del error que nombra el archivo, para una reunión dañada pedida por su dirección): decisión del dueño; queda como se construyó (cambio de conducta declarado en el contrato) hasta que decida.
- P3-1 (la reunión cuya carpeta no se llama como su id deja de servirse): conducta declarada; los 3 de 3 datos reales coinciden.
- P3-2 (identificador vacío): corregido en 8da90f4, con prueba y mutación. P3-3 (alcance del conteo de lecturas): sin cambio, la revisión concluye que no deja ningún hueco hoy.
