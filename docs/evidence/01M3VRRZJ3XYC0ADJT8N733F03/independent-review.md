# Revisión independiente de WI18 (01M3VRRZJ3XYC0ADJT8N733F03), commit 1a4bd76 contra main db10ea2

Subagente `revisor-independiente`, 2026-10-01. Su rol no tiene herramientas de escritura: el texto lo transcribió el implementador tal como lo devolvió. Al final, lo que se hizo con cada hallazgo.

## Veredicto

**LISTO PARA INTEGRAR.** No encontré ningún P1. Encontré tres P2, que son huecos reales pero no bloquean. Dos se arreglan con una o dos líneas cada uno, y conviene meterlos en la pasada de corrección.

Antes de abrir el PR faltan dos cosas que el contrato exige y que no están en este commit: la salida del armado (AC05) y la salida completa de la suite en un clon limpio (AC09, D-163). En `docs/evidence/01M3VRRZJ3XYC0ADJT8N733F03/` solo está el intento en Windows Sandbox. Eso es trabajo pendiente, no un defecto del código. La prueba en máquina limpia (AC07) quedó fuera de esta revisión.

## Qué leí

- El contrato, el `plan.yaml` y la propuesta aprobada.
- Completo, `git diff db10ea2 1a4bd76` de `company.py`, `jobs.py`, `server.py`, `window.py` y los textos.
- `packaging/` entero (`build.py`, `installer.iss`, `launcher.py`, `meetingtool.spec`, `requirements-build.*`).
- `tests/test_window.py`, `tests/test_packaging.py`, el agregado del README y la evidencia del Sandbox.
- Del fuente de pywebview 6.2.1:
  - `event.py`
  - `__init__.py` (`settings`, `start`)
  - `guilib.py`
  - `util.py` (`is_local_url`, `js_bridge_call`)
  - `platforms/winforms.py` (elección del motor, `on_closing`)
  - `platforms/edgechromium.py` (inicialización, descargas, ventanas nuevas, logging)
- Una regla de permisos me bloqueó `meetingtool/reading/credentials.py`. No lo leí; no hacía falta para nada de lo revisado.

## Qué ejecuté

Todo en clones con `--no-hardlinks` dentro de `AppData/Local/Temp`, ya borrados. No usé red ni claves, y no abrí ninguna ventana.

1. **Suite completa**, Python 3.12.10 del sistema, en un clon en 1a4bd76 (`1a4bd763d4b5abb9960e93b3b56195da84ffcdb2`): `python -m unittest discover -s tests` dio `Ran 414 tests in 237.622s`, `OK`, sin pruebas omitidas.
2. **Base de las pruebas nuevas**: `tests.test_window` + `tests.test_packaging` dio `Ran 35 tests`, `OK`.
3. **Mutaciones** sobre un segundo clon, una por vez y revertidas. Las que tocan `jobs.py` y `company.py` corrieron contra `test_window` + `test_app` (91 pruebas); las demás contra `test_window` (25).

| Mutación | Resultado |
|---|---|
| quitar el chequeo `if self.closed` | la detectan |
| `close()` sin el lock | la detectan |
| `closing()` sin `runner.close()` | la detectan |
| el servidor ignora el idioma por defecto | la detectan |
| el filtro no registra el token | la detectan |
| Ajustes deja de ganarle al instalador | la detectan |
| **quitar `saving.acquire()` de `_run`** | **sobrevive (91 OK)** |
| **liberar el lock fuera del `finally`** | **sobrevive (91 OK)** |
| **quitar `runner.close()` del `finally` de la ventana** | **sobrevive** |
| **`build.py`: ignorar versiones distintas** | **sobrevive (`test_packaging` OK)** |
| **`build.py`: ignorar árbol sucio** | **sobrevive** |

4. **`build.py` con el Python del entorno de armado**, con `ISCC` apuntando a una ruta inexistente para que no arme nada:
   - Python del sistema (otras versiones): sale con 2.
   - Un cambio en un archivo versionado: sale con 2.
   - Un archivo nuevo sin versionar: lo rechaza.
   - Un `.jpg` ignorado por git dentro de `meetingtool/`: pasa el chequeo y llega hasta Inno Setup. `collect_data_files("meetingtool")` lo incluye.
   - Las versiones fijadas coinciden con las del entorno de armado.
5. **Sondas** sobre `installed_language`, el filtro `Hidden` con `exc_info`, y una carrera de `close()` entre `os.replace` y `add_meeting`. Los resultados están en los hallazgos.

## Hallazgos P1

Ninguno.

## Hallazgos P2

**P2-1. Un `installation.ini` con `%` impide que la aplicación abra.** (`meetingtool/app/window.py:73-78`)
- **Consecuencia:** con un `installation.ini` editado o corrupto que tenga un `%`, MeetingTool no abre. No muestra su propio cartel y no escribe nada en `window.log`, porque el registro todavía no arrancó.
- **Causa:** `configparser.ConfigParser()` interpola, y `parser.get(...)` está fuera del `try`. `fallback` solo cubre una sección o una opción que falten, no los errores de interpolación.
- **Cómo lo mostré (sonda):**
  - `language=en%` lanza `InterpolationSyntaxError` desde `installed_language` y desde `Window(...)`.
  - `language=%(x)s` lanza `InterpolationMissingOptionError`.
  - Un BOM sí se tolera (devuelve `None`).
- **Arreglo:** `ConfigParser(interpolation=None)`, o meter el `get` dentro del `try`.

**P2-2. El chequeo de árbol limpio deja pasar archivos ignorados, y el armado los empaqueta.** (`packaging/build.py:120`, `packaging/meetingtool.spec:18`)
- **Consecuencia:** una imagen, video o `.docx` de un cliente que quede por error dentro de `meetingtool/` (y que `.gitignore` ignora a propósito) se publica dentro del instalador de la página pública de versiones, aunque `build.py` diga que el árbol está limpio.
- **Cómo lo mostré:** con `meetingtool/app/static/frame_001.jpg` presente, `git status --porcelain` sale vacío, `build.py` pasa el chequeo y `collect_data_files` devuelve ese archivo.
- AC05 pide armar en un clon nuevo, lo que lo mitiga, pero `build.py` no lo exige.
- **Arreglo:** que `build.py` también rechace `git status --porcelain --ignored -- meetingtool packaging` (filtrando `__pycache__`), o que arme desde `git archive HEAD`.

**P2-3. La prueba de cierre durante el guardado no ejercita el lock de `_run`.** (`tests/test_window.py:430-442`)
- **Consecuencia:** si una regresión quita `self.saving.acquire()` de `_run`, la suite sigue en verde. Cerrar justo entre `os.replace` y `add_meeting` dejaría entonces una carpeta en resultados sin su registro, y `clear_leftovers` no la limpia.
- **Por qué:** `CloseWhileSavingTest` toma el lock a mano y prueba el `Lock` en sí, no que `_run` lo use.
- **Cómo lo mostré:**
  - La mutación que quita `saving.acquire()` sobrevive a las 91 pruebas.
  - Mi sonda (frena `add_meeting` y llama a `closing()` con respuesta sí) da `close() esperó: True` con el código actual y `False` con la mutación. Ese mismo observable sirve de prueba faltante.
- El código actual es correcto en este punto; lo que falta es la prueba.

## Hallazgos P3

**P3-1. `gui="edgechromium"` no garantiza que nunca se use el motor de Internet Explorer.** (`meetingtool/app/window.py:264-265`, `tests/test_window.py:156-157`)
- En pywebview, `winforms.py:130-155` cae a MSHTML siempre que su propia detección falla. `forced_gui_` solo se compara con `'cef'` y `'mshtml'`; `'edgechromium'` no aparece en la lógica de selección (comprobado con grep).
- La garantía real la da el chequeo previo `webview2_version()`, pero sus claves difieren de las de pywebview:
  - acepta la vista de 64 bits de HKLM, que pywebview no mira;
  - acepta cualquier versión, mientras pywebview pide 86 o más.
- En Windows 11 es prácticamente inalcanzable. La prueba que verifica `started == {"gui": "edgechromium", ...}` no prueba lo que dice el comentario.
- **Arreglo opcional:** en `on_shown`, si `renderer != "edgechromium"`, mostrar un cartel y cerrar.
- Lo mostré solo leyendo el fuente. No lo ejecuté porque importar `winforms` con MSHTML escribe en el registro.

**P3-2. El token puede aparecer en la traza de una excepción.** (`meetingtool/app/window.py:122-129` y `176`)
- `Hidden` filtra `getMessage()` pero no el traceback de `exc_info`. Una excepción cuyo texto lleve la dirección con el token lo deja en `window.log`.
- **Sonda:** el mensaje sale con `token=<hidden>`, pero la línea `RuntimeError: ...token=TOKEN_abc123` de la traza queda en claro.
- No encontré hoy un camino real que meta el token en una excepción. pywebview solo escribe la URL en `debug`, como mensaje, y eso sí se filtra.

**P3-3. El cartel promete «no queda nada» y la reunión puede guardarse igual.** (`meetingtool/app/window.py:187-191`)
- Si la corrida llega a la fase de guardado mientras el cartel de cierre está abierto, la reunión se guarda entera aunque la persona confirmó y leyó «no queda nada de ella».
- Mi sonda de carrera lo muestra: respuesta sí, estado `done`, una reunión registrada. El docstring de `Runner.close` lo admite; el texto del cartel no.
- No hay datos a medias; es solo que el mensaje no se cumple.

**P3-4. Dos mutaciones de defensa sobreviven.**
- Quitar `runner.close()` del `finally` de `Window._run`: es lo que protege el caso en que el manejador de cierre lanza una excepción y pywebview cierra igual.
- Sacar del `finally` anidado la liberación del lock: es lo que evita un bloqueo de la interfaz si `forget_meeting` falla.
- El código actual hace lo correcto en los dos; no hay prueba que lo cuide.

**P3-5. Las negativas de `build.py` no tienen prueba.** (`packaging/build.py:113-124`)
- Las pruebas cubren `pins()` y `tool_problems()`, pero no `main()`. Las dos mutaciones de la tabla sobreviven.
- Hoy el rechazo funciona (lo mostré en el punto 4 de «Qué ejecuté»).

**P3-6. Ni la versión de Inno Setup ni la de Python están fijadas ni se verifican.** (`build.py`, README `winget install --id JRSoftware.InnoSetup -e`)
- La propuesta dice «para que dos armados del mismo código den el mismo programa».
- `build.py` imprime la versión de Python, pero no la compara contra nada.

**P3-7. La propuesta todavía dice que no está aprobada.** (`docs/proposals/wi18-installer-proposal.md:3`)
- Sigue diciendo «**Todavía no aprobada.**», mientras el contrato la da por aprobada («dale», 2026-10-01).

## Lo que verifiqué y está bien

- **Frontera de confianza: ninguna puerta nueva.**
  - No hay `js_api`. El puente de pywebview solo expone funciones internas: mover la ventana y eventos del DOM.
  - La URL `http://` no es «local» para pywebview, así que no levanta su servidor Bottle.
  - Las herramientas de desarrollo y los menús contextuales están apagados (`debug=False`).
  - El modo privado borra las cookies al arrancar.
  - Las páginas no tienen enlaces externos ni `target=_blank`, así que `OPEN_EXTERNAL_LINKS_IN_BROWSER` no aplica.
  - Las descargas vienen del mismo servidor y pasan por el diálogo de guardar.
  - El servidor sigue exigiendo cookie, Host, Origin y Sec-Fetch-Site; las pruebas de WI15 pasan sin cambios.
- **Uso de pywebview, correcto.**
  - `events.closing` se crea con `should_lock=True` y corre en el hilo de la interfaz. Un `False` hace `args.Cancel = True` (`winforms.py:400-403`).
  - La firma `*args` hace que pywebview llame a `closing()` sin argumentos.
  - `shown` y `loaded` corren en hilos aparte.
  - El texto que escucha `WebView2Failed` coincide con el de `edgechromium.py:270`.
  - `settings["ALLOW_DOWNLOADS"]` es lo que mira `on_download_starting`.
- **`Runner.close()` y el lock `saving`.**
  - No hay camino que deje el lock tomado: se toma después de `run.json` y se libera en un `finally` anidado, incluso ante `BaseException`.
  - No hay bloqueo mutuo: `close()` solo espera la fase corta de guardado.
  - Un `close()` entre `os.replace` y `add_meeting` espera y la reunión queda entera (sonda).
  - Una corrida previa al guardado se descarta. Lo que dejó lo limpia `clear_leftovers` al próximo arranque, porque los hilos de las corridas son daemon y mueren al salir.
- **Idioma.** Ajustes siempre gana (mutación detectada). Un idioma inválido en el `.ini` cae al valor por defecto; la excepción es el caso P2-1.
- **`installer.iss`.**
  - `PrivilegesRequired=lowest` con `{autopf}`: instala en la carpeta de programas del usuario.
  - No toca la carpeta de datos (`~/VisualMeetingTool-data`).
  - Usa el mismo AppId en todas las versiones, así que una nueva se instala encima de la anterior.
  - Reescribe el `.ini` en cada instalación y lo borra al desinstalar.
  - Pregunta el idioma cada vez (`UsePreviousLanguage=no`).

## Limitaciones residuales (no verificadas, no son hallazgos)

- `installer.iss` no tiene `[InstallDelete]`. Al reinstalar encima quedan los archivos de la versión anterior que la nueva ya no trae. Probablemente sea inofensivo con PyInstaller en modo carpeta, pero no lo probé.
- `window.log` en `%LOCALAPPDATA%\VisualMeetingTool` queda después de desinstalar.
- Comprobé el comportamiento real de WebView2 (descargas, el diálogo de guardar, el cartel de cierre) solo contra el fuente, no ejecutándolo. Lo cubre AC07.

## Condiciones antes del PR (las pide el contrato, no son hallazgos)

- AC05: la salida de `build.py` en un clon nuevo, con tamaño y SHA-256, en la carpeta de evidencia.
- AC09: la salida completa de `python -m unittest discover -s tests -v` en un clon nuevo del commit final, después de la corrección.

---

## Qué se hizo con cada hallazgo (el implementador, corrección b9bce22)

Una pasada de corrección, sin re-verificación del revisor (presupuesto: una revisión, una corrección). Cada control nuevo se muestra capaz de fallar en `mutations.txt`: 12 de 12 mutaciones detectadas, incluidas las cinco que sobrevivían en la tabla de arriba.

- **P2-1, corregido.** `ConfigParser(interpolation=None)` y el `get` dentro del `try`. Prueba: `en%`, `%(x)s` y `%` dan `None`, y la ventana abre con `en%`. Mutación: el código original.
- **P2-2, corregido.** `build.py` se niega, aun con `--allow-dirty`, si git ignora archivos dentro de `meetingtool/` o `packaging/` (menos los cachés de Python), y los nombra. Pruebas de `stray_files` y de `main()`. Ejecutado de verdad con un `.jpg` suelto en `meetingtool/app/static/`: se negó y lo nombró.
- **P2-3, corregido.** `ClosingTest` frena la corrida real dentro de `add_meeting` y cierra con «sí»: la ventana espera y la reunión queda entera. Detecta la mutación que quita `saving.acquire()`.
- **P3-1, corregido.** Si pywebview no usa `edgechromium`, la ventana lo dice como un WebView2 que no arrancó. Prueba con el motor `mshtml`.
- **P3-2, corregido.** El filtro escribe la traza dentro del mensaje y la oculta también. Prueba con una excepción que lleva la dirección con el token.
- **P3-3, corregido en el texto.** El cartel dice ahora «si justo se estaba guardando, se guarda entera».
- **P3-4, mitad corregida.** Prueba de que la ventana cierra el `Runner` aunque nunca haya corrido su manejador de cierre. La liberación del lock en el `finally` anidado sigue sin prueba: queda como limitación conocida.
- **P3-5, corregido.** Pruebas de las tres negativas de `main()` y de que con todo en orden sigue hasta buscar Inno Setup.
- **P3-6, limitación conocida.** Ni Inno Setup ni Python se verifican contra una versión fijada; `build.py` los imprime y quedan en la evidencia del armado.
- **P3-7, corregido.** La propuesta dice aprobada y nombra su contrato.
- **Limitaciones residuales:** quedan como limitaciones conocidas, en el contrato.


---

# Segunda revisión independiente, 2026-10-08 (commit 2f2fb92, tras actualizar la rama con main): aprobar con correcciones

Revisor independiente por el buzón de INGOL (rol `revisor-independiente`), copiado por el implementador tal como lo devolvió.

# Segunda revisión de WI18 (VisualMeetingTool, instalador de Windows), commit 2f2fb92

**Veredicto: aprobar con correcciones.** El código unido está bien. Falta una sola cosa antes del PR: la evidencia de la suite completa (AC09) es de un commit anterior a la unión con main y hay que volver a generarla.

**Alcance leído:** el merge 2f2fb92 (padres 09241f5, la rama, y 06d7c93, main); `meetingtool/app/jobs.py`, `window.py`, `server.py` y `company.py`; los textos es/en; README; el contrato de WI18; `tests/test_window.py`, y en `test_app.py` y `test_data_integrity.py` sólo las partes que esas pruebas usan; la lista de archivos de la evidencia de WI18. No leí el historial ni otros work items.

**Aviso sobre la base del diff:** el `origin/main` de la carpeta de trabajo es a5624cb, que está detrás del main unido (06d7c93). Lo comprobé: `jobs.py` es igual en los dos, así que el diff del pedido sirve. Contra 06d7c93, todo lo que la rama cambia está dentro de las superficies que declara el contrato. Sin red no pude confirmar que 06d7c93 sea el main remoto de hoy.

## Qué ejecuté

| Comando | Resultado |
|---|---|
| `python -m unittest tests.test_window tests.test_packaging tests.test_texts` | 73 pruebas OK (42 s) |
| `python -m unittest discover -s tests` sobre 2f2fb92 | **751 pruebas OK, 3 salteadas** (782 s) |
| Claves de `texts/es.py` y `texts/en.py` leídas con `ast` | 393 y 393, mismo orden, sin repetidas ni faltantes |
| `git diff 2f2fb92^2 2f2fb92 -- tests/test_app.py` | vacío: igual a main |
| Diff de `server.py` y `company.py` contra main | Sólo los agregados de WI18; el bloqueo de configuración de main (`_change`) está intacto |
| `constraints.txt` contra `packaging/requirements-build.txt` | Hoy fijan las mismas versiones de las bibliotecas |
| `disk.py` y `word_package.py` (nuevos en main) | Se importan en forma estática, así que PyInstaller los encuentra |

## Los puntos 1 a 4

1. **Candado de guardado (`jobs.py`): bien.** Se toma dentro del `try` (línea 529) y se suelta en un `finally` anidado (557–559). Ese `finally` corre en cualquier salida: éxito, `JobError`, una excepción de `_settle_failure` (la atrapa el `except` de la línea 555) e incluso una `BaseException`. Dos hilos no pueden tenerlo a la vez: es un `Lock`, y `start()` no deja arrancar una segunda corrida mientras la primera siga en `running`, estado que cambia recién después de soltar el candado. `close()` y `discard()` usan candados distintos y no se cruzan. Además, `discard()` rechaza mientras la corrida siga en `running`, incluso durante su cierre. No encontré forma de bloqueo mutuo: el `close()` de la ventana no toma `data_lock`. Lo leí; no hice mutaciones.
2. **Decisión del 2026-10-08: consistente** en `closing_running` (es/en), README, contrato, docstring de `close()` y la prueba. Quedan dos textos viejos, ninguno dicho a la persona (ver P3-1 y P3-2). Nada queda a medias:
   - Las subidas se borran al arrancar de nuevo (`Uploads.clear`).
   - Una carpeta de trabajo sin nada pagado se borra en ese mismo arranque (`clear_leftovers`).
   - Un resultado sin reunión no puede quedar: `close()` espera al guardado, y `_settle_cut_saves` cubre una muerte del proceso a mitad del guardado.
   - Una corrida cortada que ya había pagado queda listada con su costo; lo prueba `test_a_run_cut_by_closing_the_application_says_what_it_paid`, que vino de main.
3. **Pruebas de WI18 contra el código de main: ninguna pasa por la razón equivocada.** Un matiz: `test_answered_yes_…_stays_kept` prueba el camino en que el hilo sigue vivo después de `close()`. En la aplicación real el proceso sale y el hilo daemon muere. Ese otro camino lo cubren las pruebas de main (`clear_leftovers` y la corrida cortada). Entre las dos se cubre lo que importa.
4. **Main no se rompió:** textos completos y en el mismo orden, `test_app.py` igual a main y suite completa en verde.

## Hallazgos

**P0:** ninguno.

**P1-1. La evidencia AC09 no corresponde al commit que se va a integrar** (`docs/evidence/01M3VRRZJ3XYC0ADJT8N733F03/local-test-run.txt`).
- **Qué pasa:** el AC09 del contrato pide la suite completa en un clon limpio del commit probado, guardada antes del PR (INGOL D-163). El archivo es la corrida de 04ed9bc. Todavía nombra `test_answered_yes_the_meeting_is_dropped_and_nothing_of_it_is_left` (línea 414), una prueba que ya no existe.
- **Consecuencia:** el PR integraría la resolución nueva de `jobs.py` y el código de WI20 a WI31 sin evidencia AC09 propia. Ese criterio queda incumplido tal como está escrito.
- **Cómo lo sé:** leído. Mi corrida (751 OK) muestra que el código está sano, pero no la hice en la máquina del owner ni sobre un clon limpio.
- **Arreglo mínimo:** volver a correr AC09 en un clon limpio de la punta final y guardar la salida.

**P2:** ninguno.

**P3 (no reabren el ciclo):**
- **P3-1. Docstring de `window.py`, líneas 13–15:** todavía dice "what it left is cleared at the next start". Hoy sólo se borra lo que no tiene nada pagado. Arreglo: "what paid nothing is cleared at the next start; what was paid stays (WI20)". Leído.
- **P3-2. `app.run.closed`** (`es.py:427` "no se guardó"; `en.py:424` "it was not saved"): suena contrario a "lo pagado queda guardado". Hoy nadie lo ve: la ventana ya cerró y el texto no queda grabado en el registro de la corrida guardada. Arreglo opcional: "no se agregó al proyecto". Leído.
- **P3-3. `docs/proposals/wi18-installer-proposal.md:30`** todavía dice "la reunión se descarta sin dejar nada a medias". El contrato registra el cambio y la decisión del owner pesa más que el contrato, así que la autoridad está bien. Pero el contrato también dice que la propuesta manda en lo que él resume. Arreglo opcional: una nota en la propuesta que remita a la decisión del 2026-10-08.
- **P3-4. Las versiones del instalador no están atadas a las que prueba CI.** Las bibliotecas de `packaging/requirements-build.txt` coinciden hoy con `constraints.txt`, pero ninguna prueba exige que sigan coincidiendo. Si cambia `constraints.txt`, el instalador llevaría versiones que CI no probó. Hoy no pasa nada. Ejecutado (comparación).
- **P3-5. `build-run.txt` (AC05) es de 37d14df.** `packaging/` no cambió con la unión, pero el código que se empaqueta sí. El instalador que se publique saldrá igual del commit integrado. Leído.

## Limitaciones residuales

- El contrato da como limitación conocida que "la liberación del candado en su `finally` anidado no tiene prueba". Es más pesimista de lo real: sin esa liberación, `test_closed_while_the_run_saves…` fallaría, porque el hilo que cierra quedaría esperando para siempre. Esto lo leí; no corrí la mutación. Lo que sí no tiene prueba es la liberación cuando `_settle_failure` lanza una excepción.
- No construí el instalador ni probé WebView2 (fuera del alcance del pedido).
- No corrí ninguna mutación: no podía escribir archivos.

**Siguiente paso:** el implementador vuelve a generar la evidencia AC09 sobre la punta final; con eso, el PR puede abrirse.

## Lo que se hizo con cada hallazgo de la segunda revisión

- P1-1 (la evidencia de la suite completa AC09 no era de la punta final): se vuelve a correr sobre la punta final en un clon limpio, con los kits, y se guarda en `local-test-run.txt` (ver su encabezado, que nombra el commit).
- P3-1 (docstring de `window.py`) y P3-2 (`app.run.closed`: "no se guardó"): corregidos en f8335b3.
- P3-3 (la propuesta decía "se descarta"): nota en la propuesta con la decisión del 2026-10-08, en f8335b3.
- P3-4 (las versiones del instalador no estaban atadas a las que prueba la CI): prueba nueva `BuildTest.test_the_installer_packs_the_versions_the_ci_tests`, en f8335b3.
- P3-5 (`build-run.txt` es de un commit anterior): el instalador se vuelve a armar desde el commit integrado y su salida reemplaza a `build-run.txt`.
- Mutaciones: las 12 de WI18 vuelven a correrse sobre el código unido: 12 de 12 detectadas (`mutations.txt`).
- Limitación que el revisor señala: la liberación del candado cuando `_settle_failure` lanza una excepción no tiene prueba; se mantiene como limitación conocida del contrato.
- Decisión del owner de la sesión (2026-10-08): la ventana cerrada a mitad de una corrida no descarta lo pagado (regla de WI20), y quedó escrita en el contrato.
