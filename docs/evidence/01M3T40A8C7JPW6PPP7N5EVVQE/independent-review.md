# Revisión independiente de WI17 (01M3T40A8C7JPW6PPP7N5EVVQE), commit 5d4c63a contra main a2b98aa

Subagente `revisor-independiente`, 2026-09-30. Su rol no tiene herramientas de escritura: el texto lo transcribió el implementador tal como lo devolvió.

**Veredicto: NO LISTO.** La suite no pasa de forma confiable en Windows. La prueba del logo de más de 1 MB falla de a ratos: el servidor contesta 413 sin haber leído el cuerpo y cierra la conexión. Eso choca de frente con AC09, que exige la suite completa en verde en la máquina del owner. El arreglo es chico. Todo lo demás está bien hecho: la terminal dice exactamente lo mismo que antes, y el escapado, el logo, las rutas nuevas y las garantías de WI15 se sostienen. Los tres P2 son huecos de los controles, no defectos de hoy.

## Qué leí

- El contrato (AC01 a AC09) y la sección WI17 de la propuesta de D-188. `plan.yaml` no lo leí.
- El diff completo de las etapas: `frames/{extract,transcript}.py`, `projects/store.py`, `reading/{credentials,gemini}.py`, `summary/{writer,qa}.py`, `report/{document,layout,__main__}.py`.
- `texts/__init__.py` y `texts/en.py` completos. De `es.py` sólo lo que muestran las pruebas.
- `app/company.py` completo, y el diff de `app/server.py` y `app/jobs.py`.
- De `app/pages.py`: `View`, `layout_page`, Ajustes, `message_page` y el bloque de la empresa.
- De `app.js`: `text()`, `settingForm` y los sumideros de HTML (no hay `innerHTML`).
- `tests/test_texts.py` completo, el diff de `tests/test_app.py` y `mutations.py`.

## Qué ejecuté

Todo en un clon `--no-hardlinks` de 5d4c63a, en `C:/Users/Diego/AppData/Local/Temp/rev-wi17-1790806439`. Las sondas están en `C:/Users/Diego/AppData/Local/Temp/rev-wi17-probe/`. Quedan ahí; el árbol del clon quedó limpio. Sin red y sin Gemini.

- **Suite completa** (`python -m unittest discover -s tests`): **375 pruebas en 214 s, FAILED (errors=1).** Falla `CompanyTest.test_a_logo_of_more_than_1_mb_is_refused_saying_why` con `ConnectionAbortedError [WinError 10053]`.
  - Esa prueba sola, 8 veces: **3 fallas y 5 OK.**
- **Pruebas previas:** `git diff a2b98aa 5d4c63a -- tests/` confirma lo declarado. En `test_app.py` cambian el import, las 7 aserciones de `jobs.LABELS` y la de "stopped before sending the summary". Nada más. `git diff --check` sale limpio.
- **AC09, raise por raise:** comparé cada f-string viejo con su entrada en `en.py` más los datos. Miré `!r`, `.2f`, `.3f`, listas, `{refusal:.300}` contra `str(error)[:300]`, el "the summary" que se reemplazaba en `_check_language`, `{{informe}}`, `report.active` con `\n  ` y `strerror=None`. No encontré ninguna diferencia.
  - La nota de reintento a Gemini sigue siendo `str(error)` (qa.py:678), que da el mismo inglés.
  - `LANGUAGE_NAMES` y la descripción del tipo retirado siguen en inglés en los pedidos.
- **Destino de lo que viene de afuera (AST):** los 13 `detail=texts.External(...)` caen dentro de `[[ ]]` de su entrada. El `External` de `gemini.py:179` sólo llega a `{reason}` dentro de `[[ ]]`.
- **Sondas del logo** contra `check_logo`, con 25 casos. Resultados:
  - PNG con HTML agregado al final, con tEXt, o con EXIF/COM en JPG: se reescriben y la carga no queda.
  - PNG y JPG truncados: rechazados.
  - SVG con nombre `.png`, SVG precedido de un comentario de 3 KB, HTML con nombre `.jpg`, GIF o WebP con nombre `.png`, y cabecera de 30000×30000: rechazados.
  - 4000×4000: aceptado, dentro del límite.
- **Sondas del servidor** (sobre la clase `Running`):
  - Un nombre con `"><script>` queda escapado en la página y en `<title>`. Los caracteres U+202E y U+200B se rechazan.
  - `/company/logo` sin cookie da 403. `/api/logo/remove` sin `X-MeetingTool` da 403. `/api/upload?kind=logo` da 404.
  - **Una página rechazada con 403 muestra el nombre de la empresa** (ver P2-1).
- **Mutaciones propias**, contra `tests.test_texts`, todas sumando texto sin quitar ninguna clave: **5 de 7 no detectadas.** El detalle está en P2-2 y P2-3.

## P1

**P1-1: un logo de más de 1 MB puede cortar la conexión en vez de explicar el rechazo, y la suite falla de a ratos.**

- Dónde:
  - `meetingtool/app/server.py:370`: rechaza con 413 apenas lee `Content-Length`.
  - `server.py:217`: `_discard_body` sólo lee el cuerpo si pesa hasta `JSON_LIMIT` (1.000.000 bytes), y el límite del logo es 1.048.576.
  - `tests/test_app.py:442`: la prueba manda unos 1,47 MB.
- Qué pasa: el servidor contesta sin haber leído el cuerpo y cierra. En Windows, el cliente muchas veces recibe un reset antes de leer la respuesta.
- Caso ejecutado: esa prueba sola da 3 fallas en 8 corridas, y la corrida completa también falló por ella.
- Consecuencia: la suite en un clon limpio en la máquina del owner (AC09) sale roja una de cada tres veces. En el navegador, lo probable es que el usuario vea "se perdió la conexión" en vez de "el logo pesa más de 1 MB" (AC02). Esto último no lo verifiqué en un navegador.
- Arreglo más simple, cualquiera de estos:
  - descartar el cuerpo hasta un tope razonable (por ejemplo, unos MB) antes de contestar el 413;
  - que `app.js` compare `file.size` con 1 MB antes de subir, manteniendo el control del servidor.
- Para cerrar el P1 hay que repetir la prueba unas 20 veces seguidas sin una sola falla.

## P2 (no reabren el ciclo)

**P2-1: el nombre de la empresa sale en páginas que se sirven sin sesión.**

- Dónde: `server.py:160` usa `self.view()` también para los rechazos de `refusal` (`:184`).
- Caso ejecutado: `GET /` sin cookie, con cookie falsa o con `Host: evil.example` devuelve 403, y el nombre aparece en la cabecera y en `<title>`.
- Consecuencia: cualquier proceso local sin la cookie, o una página de afuera usando *DNS rebinding*, puede leer el nombre de la empresa y el idioma. Antes de WI17, un rechazo no mostraba nada de la carpeta de datos.
- Lo dejo en P2 porque el dato es de bajo valor, pero es un dato que cruza la frontera de la sesión. Si el owner considera que el nombre es sensible, se eleva.
- Arreglo: para los rechazos, usar `pages.View(language)` sin la empresa.

**P2-2: el control de AC03 tiene salidas.** Tres mutaciones pasaron sin que fallara ninguna prueba:

- Texto en `app.js` entre comillas simples o entre acentos graves: `say(form, 'Un momento')` y `` say(form, `Un momento`) ``. Motivo: `script_literals` (`tests/test_texts.py:291`) sólo lee comillas dobles. Hoy `app.js` no usa ninguna de esas dos formas, así que alcanza con prohibirlas o con leerlas.
- Texto en un atributo que no está en `SAID_ATTRIBUTES` (`test_texts.py:357`), por ejemplo `<input type="submit" value="Crear">`.
- Texto en una rama que ninguna pantalla de la prueba muestra, por ejemplo junto a `app.key.none` (`pages.py:429`, porque la prueba siempre tiene una clave guardada).

**P2-3: el control de AC06 sólo mira la forma `raise X(...)`.**

- Dónde:
  - `test_texts.py:250`;
  - `Failure` acepta cualquier texto que no sea una clave (`texts/__init__.py:172`).
- Tres mutaciones pasaron sin que fallara ninguna prueba:
  - `error = ReadingError("the saved key is bad"); raise error`;
  - `return self._json({"error": "clave mala"}, 400)` en `/api/key`;
  - `job.error = "algo falló"`.
- Hoy no hay ningún caso en el código: busqué con AST todas las construcciones de un `Failure` fuera de un `raise` y encontré cero.
- Mecanismo más simple y más fuerte: que `Failure` rechace en tiempo de ejecución un texto que no sea clave (las pruebas usarían una clave de prueba), y que la revisión AST mire toda llamada a una clase `Failure`, esté o no dentro de un `raise`.

**P2-4: "no viaja nada escondido en el archivo" no es del todo cierto.**

- Dónde: `company.py:143` (`image.save(out, "PNG")`).
- Caso ejecutado: un PNG con un perfil ICC de bytes elegidos por quien lo sube conserva el chunk `iCCP` con esos mismos bytes.
- Se sirve como `image/png` con `nosniff` y sólo al mismo origen, así que no encontré forma de ejecutarlo. Pero la afirmación del contrato no se sostiene para este caso.
- Arreglo: guardar con `icc_profile=None`, o convertir antes.

## P3

- El detalle de un logo ilegible incluye `cannot identify image file <_io.BytesIO object at 0x…>`: una dirección de memoria que no le sirve a nadie (`company.py:149`).
- `POST /api/language` sin el campo `language` responde "no hay un idioma None para la aplicación".
- `Failure(message, **params)` ignora en silencio los datos cuando recibe un `Message`.
- El `display:flex` del encabezado cambia un poco su CSS aun sin empresa. El HTML sin empresa es igual al de antes: `<title>` queda "título · MeetingTool".

## Lo que comprobé y está bien

- **AC09:** todas las entradas coinciden con el texto viejo. El truncado `.300`, los floats y las listas dan igual. Los pedidos a Gemini no cambian. El mensaje queda igual si la excepción se *picklea*, porque se guarda en `__dict__`.
- **AC07:** Google, el sistema y los fallos inesperados salen como detalle, también cuando un mensaje va dentro de otro. En las pruebas por etapa, el texto de afuera no aparece en la frase.
- **Seguridad:**
  - el nombre se escapa en la página, en `value=` y en `<title>`;
  - `data-texts` va escapado y `app.js` usa sólo `textContent`;
  - las rutas nuevas pasan por `refusal`;
  - el logo se decodifica y se reescribe, con los tipos fijos `image/png` e `image/jpeg`;
  - el SVG se rechaza con cualquier nombre;
  - la cookie, el CSP sin script inline y `nosniff` siguen igual.
- **Alcance:** todos los archivos del diff están dentro de `affected_surfaces`.

## Limitaciones de esta revisión

- No abrí la aplicación en un navegador. Lo que dije del reset en la subida es inferencia.
- No corrí `mutations.py` completo, y `mutations.txt` no está commiteado.
- AC08 (la corrida real) y la salida de la suite para AC09 todavía no están en `docs/evidence/`. El contrato las pide antes del PR.
- De `es.py` no revisé la calidad del castellano, sólo lo que controlan las pruebas.

---

# Corrección del implementador, commit b7b749d

Una sola pasada de corrección, como manda la política de revisión.

- **P1-1, corregido.** Un logo rechazado por pesar más de 1 MB se lee entero (hasta 32 MB) antes de contestar, así que la página recibe el motivo y no una conexión cortada (`server.py`, `_drop`). Prueba nueva: 20 subidas seguidas de más de 1 MB, cada una con su 413 y "pesa más de 1 MB". La prueba que fallaba, sola, 10 corridas: 10 OK. Mutación que lo quita: detectada.
- **P2-1, corregido.** Un pedido rechazado antes de la sesión (sin cookie, cookie falsa, otro Host, la dirección de inicio vencida) recibe el rechazo en el idioma de la aplicación, sin nombre ni logo de la empresa. Prueba y mutación nuevas.
- **P2-2, corregido en lo que señala.** El control del script lee también comillas simples y acentos graves; el de las páginas lee el `value` de un botón; las pantallas de la prueba incluyen Ajustes sin clave y sin plantilla, y con una plantilla que ya no sirve. Sigue siendo un control de lo que las pruebas recorren: un texto en una rama que ninguna prueba muestra, o armado concatenando partes en el script, puede escaparse (limitación conocida).
- **P2-3, corregido a medias.** La revisión de fuentes mira toda construcción de un error del programa, esté o no en un `raise` (la mutación `error = ReadingError("…"); raise error` ahora se detecta). **No se hizo** que `Failure` rechace en tiempo de ejecución un texto que no sea clave: obligaría a cambiar pruebas existentes que simulan errores con texto. Queda como limitación: un texto puesto a mano en `job.error` o en una respuesta JSON no lo detecta ningún control.
- **P2-4, corregido.** El logo se reescribe sin perfil de color, texto ni metadatos del archivo; se conserva el color transparente, que es parte de la imagen. Prueba y mutación nuevas.
- **P3, la dirección de memoria:** corregida (se saca del detalle). **Los otros tres P3 quedan como están:** "no hay un idioma None", los datos ignorados al pasar un `Message` a `Failure`, y el `display:flex` del encabezado.

---

# Re-verificación de WI17, commit b7b749d (corrección sobre 5d4c63a)

Subagente `revisor-independiente`. Transcripta por el implementador.

**Veredicto: LISTO PARA INTEGRAR.** El P1-1 queda cerrado. La suite completa pasa dos veces seguidas. Las correcciones de P2-1, P2-2, P2-3 y P2-4 funcionan y no abren huecos nuevos. Quedan dos salidas menores del control de textos, que no son bloqueantes, y la evidencia que el contrato pide antes del PR.

## Qué ejecutó

Clon nuevo con `--no-hardlinks` de b7b749d en `C:/Users/Diego/AppData/Local/Temp/rev-wi17b-1790816528`. Queda ahí, con el árbol limpio. Sin red, sin Gemini y sin tocar el repositorio original.

- **Diff leído:** `git diff 5d4c63a b7b749d`, completo, en `meetingtool/` y en `tests/`.
- **P1-1:**
  - La prueba vieja (`test_a_logo_of_more_than_1_mb_is_refused_saying_why`), 20 veces seguidas: **0 fallas.** En 5d4c63a fallaba 3 de cada 8.
  - La prueba nueva (`..._gets_its_reason_every_time`, que sube el logo 20 veces), 5 corridas: **0 fallas.**
- **Suite completa** (`python -m unittest discover -s tests`): **378 pruebas, OK**, en 216 s y en 224 s. La primera corrida pudo coincidir con mis mutaciones, por eso la segunda la repetí sola, con el árbol limpio.
- **Mutaciones repetidas** contra `tests.test_texts`, todas sumando texto sin quitar ninguna clave:

| Mutación | 5d4c63a | b7b749d |
|---|---|---|
| Texto en `app.js` entre comillas simples | no detectada | detectada |
| Texto en `app.js` entre acentos graves | no detectada | detectada |
| Texto en `value=` de un `<input type="submit">` | no detectada | detectada |
| Texto en la rama "sin clave" de Ajustes | no detectada | detectada |
| `e = ReadingError("texto"); raise e` | no detectada | detectada |
| `ReadingError("texto")` armado en una función auxiliar (nueva) | — | detectada |
| `self._json({"error": "clave mala"}, 400)` en `/api/key` | no detectada | **no detectada** |
| `job.error = "algo falló"` | no detectada | **no detectada** |

- **Sondas de P2-1:** `GET /` sin cookie, con cookie falsa o con `Host: evil.example` da 403 sin el nombre de la empresa y sin el logo. `/company/logo` sin cookie da 403.
- **Sondas de P2-4:**
  - Un perfil ICC elegido por quien sube el archivo no queda, ni en PNG ni en JPG.
  - Tampoco quedan tEXt, EXIF de PNG ni HTML agregado al final.
  - La transparencia de un PNG en modo P y el canal alfa de un RGBA se conservan.
  - El detalle de un archivo ilegible ya no trae la dirección de memoria.

## Lo nuevo no abre huecos

- **`_drop` (`server.py`):**
  - Sólo se alcanza después de `refusal`, o sea con cookie y con `X-MeetingTool`. Ningún pedido de afuera puede hacer que el servidor lea 32 MB.
  - Lee de a 1 MB y no guarda nada.
  - Si el cliente manda menos de lo que declaró y cierra, corta.
  - Marca `_body_read`, así que `_discard_body` no vuelve a leer y la conexión se cierra igual.
- **`view(session=False)`:**
  - Se usa en los dos caminos anteriores a la sesión: los rechazos de `refusal` y el `/open` con token inválido. Después de la sesión no hay otros.
  - Sólo deja ver el idioma, que está declarado y aceptado.

## P1

Ninguno.

## P2 (no reabren el ciclo; limitaciones conocidas)

- **El control de AC06 y AC03 sigue sin ver texto que no pasa por un `Failure`.** Puede ser una respuesta JSON armada a mano en `server.py` o un `job.error` asignado con texto en `jobs.py`. Esos textos sólo los atrapa la prueba de pantallas si el camino se recorre. Hoy no hay ningún caso así en el código. Rechazar el texto en tiempo de ejecución, que no se hizo, tampoco lo cubriría.

## P3

- Un logo de más de 32 MB sigue recibiendo la conexión cortada, en lugar del motivo. `app.js` no mira el tamaño antes de subir.
- En Ajustes, una plantilla inservible muestra la frase pero no su detalle (`server.py`, `error.text(...)`). Ya era así antes de esta corrección.

## Pendiente antes del PR (no es hallazgo)

- La corrida real de AC08.
- La salida de la suite para AC09, en un clon limpio en la máquina del owner.
- La salida de `mutations.py`.
- `independent-review.md`, hoy sin commitear.

---

# Nota del implementador después de la re-verificación, commit 7955616

La corrida de mutaciones sobre b7b749d (mutations.txt, corrida 2) **no detectó** la mutación que quita la corrección de P1-1: la prueba de 20 subidas no siempre muestra la conexión cortada, así que no protegía la corrección. Se agregó una prueba que no depende del azar (`CompanyTest.test_a_logo_of_more_than_1_mb_is_read_before_the_answer`): manda sólo una parte del cuerpo y exige que el servidor espere el resto antes de contestar. Con la corrección pasa (5 de 5); sin ella falla (corrida 3: DETECTED). Sólo cambió una prueba y `mutations.py` (un filtro por etiqueta); el código del programa es el que la re-verificación aprobó. Suite completa en un clon limpio de 7955616: 379 pruebas, OK.
