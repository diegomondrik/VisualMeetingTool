# Revisión independiente de WI33 (01M4EFSYPJYBAMNG5AYWJQXG18)

Revisor independiente por el buzón de INGOL (rol `revisor-independiente`, sin herramientas de escritura): el texto es el que devolvió, copiado por el implementador. Al final, lo que se hizo con cada hallazgo.

## Revisión del commit b9c117e, 2026-10-08: aprobar con correcciones

# Revisión independiente de WI33 (manual de usuario de VisualMeetingTool), commit `b9c117e`

**Veredicto: aprobar con correcciones.** Una frase del manual dice lo contrario de lo que hace el programa (P1). Se arregla reemplazando una oración, sin rediseño. Además faltan dos piezas de evidencia que el propio contrato exige.

## Alcance leído
- El contrato y el plan de WI33.
- `git diff c4be853 b9c117e`: el manual, `installer.iss`, las dos pruebas, el README y la evidencia.
- Contra el código: `jobs.py` completo, `texts/en.py` completo, y las partes que hacían falta de `window.py`, `pages.py`, `server.py`, `static/app.js`, `reading/gemini.py`, `summary/writer.py` y `summary/qa.py`.
- No leí el historial ni otros work items. Sólo busqué en la evidencia de WI18 el tamaño del instalador y el espacio en disco.

## Qué ejecuté y qué dio
- **Pruebas** (`python -m unittest tests.test_user_manual tests.test_packaging`): corrieron 27 y pasaron todas.
- **Mutaciones** (`mutations.py . <carpeta nueva en el scratchpad>`): el commit es `b9c117e` con el árbol limpio. Las 16 mutaciones se detectan y la corrida sin mutar pasa. Reproduce `mutations.txt`, que se había grabado en `a6ad9f6`; entre ese commit y `b9c117e` sólo cambian archivos de evidencia.
- **Compilación con Inno Setup** (`ISCC /DVersion=0.0.0 /DSource=<carpeta con un archivo> /O<scratchpad>`): compila bien. Comprime `packaging\\..\docs\manual\user-manual.html`; la doble barra de `{#SourcePath}\..` se tolera. Interpreta bien los nuevos `[CustomMessages]`, `[Icons]` y `[Run]`.
- **Caracteres no ASCII:** `installer.iss` es ASCII puro. El manual tiene 6 líneas con caracteres no ASCII (…, →, «») y declara `meta charset utf-8`, así que no hay problema.
- No instalé el `.exe`: habría tenido efecto sobre la máquina.

## Hallazgos

### P1
**P1-1. Cerrar la ventana a mitad de una corrida** (`user-manual.html:152`, leído).
- El manual dice: *"If you confirm, that meeting is dropped and nothing of it is kept."*
- Es falso. El programa conserva lo ya pagado: lo dicen `app.window.closing_running` ("what was already paid for stays… you can discard it later"), `Runner.close()`, `clear_leftovers()` y el README. También lo contradice la nota de la línea 153 del propio manual.
- **Consecuencia:** quien cierra para descartar una reunión confidencial cree que no quedó nada en el disco. En realidad, las respuestas de Gemini sobre esa reunión siguen en `<proyecto>\processing` hasta que las descarte.
- **Corrección:** *"If you confirm, the meeting is not added to the project; what was already paid for is kept, as for a failed run, so that processing it again does not pay for it twice (see **Kept from runs that failed** in Troubleshooting). If it was just being saved, it is saved whole."*

### P2
**P2-1. Fila de tope superado en Troubleshooting** (`:223`, leído).
- El manual dice *"Nothing was sent or written."*
- El mensaje real incluye "with about US$… already spent". Las tandas anteriores de esa corrida sí se enviaron a Google y se pagaron. Lo que no se envió es sólo esa petición.
- **Corrección:** *"That request was not sent and nothing was written. What earlier requests of the run cost was paid and is kept (see the row about Kept from runs that failed). Raise the ceiling (section 6) and process the meeting again."*

**P2-2. Privacidad: lo que sale de la computadora** (`:202`, leído).
- El manual dice *"Nothing else is sent"*.
- Los dos prompts envían también el título de la reunión (`MEETING TITLE:` en `writer.py:376` y `qa.py:704`) y el tipo de reunión. Un título con el nombre del cliente sale de la computadora sin que el manual lo diga.
- **Corrección:** *"…the **text of the transcript**, the meeting's **title** and **type**, plus what earlier meetings of the project taught it."*

**P2-3. "La grabación no se copia"** (`:175`, leído).
- El manual dice *"The recording itself is **not copied** into the program's folders"*.
- Es falso mientras se procesa. El video se sube a `<datos>\.meetingtool-uploads`, se mueve a la carpeta de trabajo y se borra recién después de extraer los fotogramas (`jobs.py:485-490`). Si se cierra la ventana en esa etapa, la copia queda hasta el próximo inicio.
- Además falta un requisito: hace falta espacio libre igual al tamaño del video (hasta 16 GB) en el disco de la carpeta de datos.
- **Corrección:** *"While a meeting is processed the recording is copied into the data folder, so that drive needs free space for it; the copy is deleted once its frames are taken, and the meeting keeps only the frames, the transcript, the text and the report."* Agregar lo mismo en la sección 2.

**P2-4. El tope máximo de 5 no está atado a ninguna prueba** (`tests/test_user_manual.py:127-134`, leído).
- El contrato (AC03) pide atar "the default and the largest ceiling".
- Nada verifica el "up to 5" de `:138`. El 5 está escrito a mano en `jobs.py:163` y en `pages.py:383`, sin constante. Cambiar el manual a "up to 10" no haría fallar ninguna prueba.
- **Arreglo mínimo:** sacar el 5 a una constante en `jobs`, usarla en `pages`, verificarla en el manual y agregar la mutación correspondiente.

**P2-5. Afirmación de costo sin respaldo** (`:162`, leído).
- El manual dice: *"in the developer's tests, reading the screens of a two-hour meeting and writing its summary cost well under one US dollar."*
- No hay en el clon evidencia de una corrida de dos horas. `jobs.py:45-46` cita 70 fotogramas con una reserva de unos US$0,26.
- Además roza el "quotes no price" del contrato: la prueba sólo busca `US$0.x` y no lo detecta.
- **Arreglo:** quitar la viñeta, o citar la corrida real con su duración y su fuente.

### P3 (no reabren el ciclo)
- **`:146-150`:** "Saving the meeting in the project" no es una fila de la página Processing. Las filas son 4 (`jobs.py:87`); ese nombre sólo aparece cuando falla el guardado.
- **`:146`:** dice *"not people's faces"*, pero es un filtro heurístico de cámara (`signals.is_camera_view`). Más preciso: *"not frames that only show people on camera"*.
- **`:146`:** "several minutes for a two-hour meeting" no tiene medición en el clon.
- **`:183`:** "first page becomes the cover" es impreciso. Es lo que está antes del índice o de `{report}`; lo que sigue se descarta como modelo.
- **`:210`:** el desinstalador deja la carpeta del log, `AppData\Local\VisualMeetingTool`, y el manual no la nombra entre lo que hay que borrar a mano.
- **`:219`:** la cita dice "on this folder", pero el mensaje real muestra la ruta.
- **Impresión** (incierto, no lo verifiqué en un navegador): `@media print` no fuerza las variables claras. Si el sistema está en tema oscuro y el navegador imprime en ese esquema sin fondos, saldría texto claro sobre papel blanco. Arreglo: repetir las variables claras en `@media print`.
- **Falta un paso para el usuario nuevo:** cómo bajar la transcripción `.docx` de Teams.
- **La prueba del log** compara un texto fijo y no `window.log_dir()`.

## Pruebas y un mecanismo más simple
- **Lo que sí garantizan.** Las pruebas detectan de verdad nombres, números, rutas, estructura, recursos externos y las entradas del instalador; las 16 mutaciones lo confirman. La comparación de nombres contra `en.py` es por igualdad exacta con un texto completo del catálogo, así que es fuerte.
- **Lo que no ven.**
  - Cualquier afirmación de comportamiento: qué pasa al cerrar, qué se envía, qué se guarda. Los P1/P2 de arriba son justamente de ese tipo; para eso existe esta revisión.
  - Cualquier nombre nuevo que el manual cite y no esté en la lista `UI_NAMES`, que se mantiene a mano.
- **Mecanismo más simple con la misma garantía, o mayor:** marcar cada nombre citado en el HTML, por ejemplo `<strong data-text="app.key.save">Save the key</strong>`, y que la prueba compare el texto de cada elemento con `catalog("en")[clave]`. Elimina la lista a mano y cubre automáticamente cualquier cita nueva.

## Criterios
- **WI33-AC01 — cumple.** La página es autocontenida, en inglés, tiene las 12 secciones en orden con índice funcional, tema oscuro, viewport e impresión. Las pruebas lo verifican; queda la duda de la impresión en tema oscuro (P3).
- **WI33-AC02 — cumple en el script, falta evidencia.**
  - Mi compilación confirma que el manual entra en el instalador y que `[Icons]`, `[Run]` y las dos lenguas compilan. El acceso del menú Inicio y la oferta sin tildar están declarados; no los vi funcionar porque no instalé.
  - En `docs/evidence/01M4EFSYPJYBAMNG5AYWJQXG18/` no está la salida del build con la lista de archivos del instalador, que el criterio exige commiteada.
  - El cambio de la prueba existente está nombrado y justificado.
- **WI33-AC03 — no cumple todavía.**
  - El P1-1 y los P2-1 a P2-3 son afirmaciones falsas o engañosas para un usuario nuevo.
  - El tope máximo no está atado (P2-4).
  - Falta `local-test-run.txt` (la suite completa en un clon limpio con los kits de INGOL).
  - Las mutaciones están bien.

## Limitaciones residuales
- No abrí la página en un navegador ni ejecuté el instalador compilado.
- No corrí la suite completa: el pedido nombraba sólo dos módulos.
- No hay evidencia en el clon de los tiempos ni de los costos reales que cita el manual.

## Lo que se hizo con cada hallazgo

- P1-1 (el manual decía que al cerrar la ventana la reunión se descarta y no queda nada): corregido con la frase que propuso el revisor, más la remisión a "Kept from runs that failed".
- P2-1 (el tope "no envió nada"): corregido; ahora dice que esa petición no se envió y que lo que costaron las anteriores se pagó y queda guardado.
- P2-2 (lo que sale de la computadora): agregados el título y el tipo de la reunión, con el consejo de elegir los títulos en consecuencia; el archivo de video no se sube nunca.
- P2-3 (la grabación no se copia): corregido; se copia mientras se procesa, se borra al sacar los fotogramas, y hace falta espacio libre igual al video; agregado también a los requisitos.
- P2-4 (el tope máximo de 5 no estaba atado al código): la prueba lee el límite de `jobs.check_request` y de `pages.py` y exige que el manual diga el mismo; mutación nueva (de 5 a 10), detectada.
- P2-5 (el costo "bien por debajo de un dólar" sin respaldo): quitado; en su lugar, el consejo de empezar con un tope bajo.
- P3: corregidos "Saving the meeting" (el manual dice que la página lo muestra sólo si falla), "not people's faces", "several minutes", la portada, la carpeta del log que deja el desinstalador, el mensaje de "already open", la impresión con tema oscuro (variables claras en `@media print`), el paso para bajar la transcripción de Teams, y la prueba del log (ahora usa `window.log_dir()`).
- Mecanismo más simple (marcar cada nombre citado con la clave del texto del programa): adoptado. 42 nombres del manual llevan `data-ui="<clave>"` y la prueba compara cada uno con el texto exacto de esa clave del catálogo en inglés; la lista `UI_NAMES` queda como segunda red. Mutación nueva (una clave apuntando a otro texto), detectada.
- AC02 (falta la salida del armado con la lista de archivos del instalador) y AC03 (falta la suite completa): se agregan antes del PR, en `build-run.txt` y `local-test-run.txt`.
- Mutaciones: 18, todas detectadas con pruebas que corrieron y fallaron (`mutations.txt`).
