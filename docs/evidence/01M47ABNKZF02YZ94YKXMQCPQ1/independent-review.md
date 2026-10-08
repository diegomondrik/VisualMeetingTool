# Revisiones de WI22 (01M47ABNKZF02YZ94YKXMQCPQ1): la independiente y la de seguridad, commit 6daabab contra main 59343c9

Por el buzón de INGOL, 2026-10-05. El texto de cada revisión es su respuesta tal como llegó; el implementador sólo bajó un nivel sus títulos.

## Revisión independiente (rol `revisor-independiente`)

## Revisión independiente — WI22 (VisualMeetingTool), commit `6daabab` contra la base `59343c9`

**Veredicto: aprobar con correcciones.** Hay un P1: un campo activo cuyo nombre arma otro campo anidado pasa el filtro y llega al informe del cliente. El arreglo es chico y no rechaza ninguna plantilla legítima de las que probé. El resto del trabajo está bien y los criterios AC01 a AC05 se cumplen con evidencia ejecutada.

### Qué leí

- El contrato y el plan: `contract.yaml` y `plan.yaml`.
- El cambio completo: `git diff 59343c9 6daabab`, que toca 15 archivos.
- Las pruebas nuevas, `compare_pilot_tests.py`, `mutations.py`, `mutations.txt` y `changed-tests.md`.
- Las filas de WI22 en `REGISTER.md`.
- Las partes de `layout.py` que arman campos en el informe.

No leí historial ni handoffs.

### Qué ejecuté

| Qué | Resultado |
|---|---|
| `python -m unittest discover -s tests` | 459 pruebas, todas pasan; 3 se saltean (son las `test_d1_*` que necesitan los kits de INGOL) |
| `mutations.py` sobre `6daabab` | Las 16 mutaciones se detectan y, sin mutar, pasan las 40 pruebas. Coincide con `mutations.txt` (que se corrió sobre `c8576fe`) |
| `compare_pilot_tests.py` contra la carpeta de pruebas del piloto de INGOL | La clase `AR04FiltroDeCamposEludible` y las constantes `W` y `CAMPO` son idénticas a las de INGOL; sale con código 0 |
| `reproduce.py WI22-P3-1..4` | Las 4 coinciden con lo que dice el registro |
| Las pruebas nuevas contra el código viejo (`59343c9`), copiadas a una carpeta aparte | AR04 falla. También fallan las formas de AC02 que dependen de leer XML (referencia de carácter decimal o hexadecimal, comillas simples, otro prefijo, espacio de nombres por defecto, CDATA, comentario, instrucción borrada, Strict), y fallan AC03 y AC04. Con el código viejo pasan igual: tal cual, minúsculas, mayúsculas mezcladas, partido en varias corridas o párrafos, encabezado, pie y nota al pie |
| Pruebas armadas por mí, con las funciones auxiliares de las pruebas del proyecto | Resultados abajo |
| `git diff --check` y `compileall` | Limpios |

### Hallazgos

#### P0
Ninguno.

#### P1 — Un campo cuyo nombre arma un campo anidado pasa el filtro y llega al informe del cliente
- **Dónde:** `meetingtool/report/document.py:123-145` (`field_instructions`) y `:59`/`:210` (`ACTIVE_FIELDS` busca la palabra en cualquier lugar de la instrucción).
- **Qué pasa:** probé la plantilla `{ {QUOTE 68 68 69 65 85 84 79} "c:\windows\system32\cmd.exe" "/k calc" }`. Los códigos 68…79 deletrean `DDEAUTO`.
  - `set_template` la acepta.
  - `build_report` entrega el informe con el campo intacto: `QUOTE 68 68 69…` y `cmd.exe` quedan en `word/document.xml` del informe.
  - La revisión del informe antes de entregarlo (AC04) tampoco lo detecta, porque aplica la misma regla.
  - Lo mismo pasa con `{ {QUOTE "INCL"}{QUOTE "UDEPICTURE"} "…" }`.
- **Consecuencia:** el informe que recibe el cliente lleva un DDEAUTO u otro campo activo. Es exactamente lo que el objetivo del contrato dice cerrar: "refused in every form Word would read it in".
- **Qué no verifiqué:** si Word evalúa un nombre armado así. No hay Word acá, igual que en la revisión externa de R02. Entiendo que es una técnica de ofuscación publicada para DDE en 2017, pero no lo comprobé. El agente lo anotó como `WI22-P3-3`; eso lo subestima frente al texto del objetivo. Bajarlo a limitación es decisión del owner, no del implementador.
- **Pregunta 3 del pedido** (rechazar todo campo que tenga otro campo dentro de su instrucción): cerraría el hueco, pero rechaza plantillas legítimas. `{= {NUMPAGES} - 1}`, que se usa para numerar sin contar la portada, y `{IF {PAGE} > 1 …}` hoy se aceptan y con esa regla se rechazarían. No conviene.
- **Arreglo mínimo:** exigir que el nombre de cada campo esté escrito literalmente. El nombre es la primera palabra del texto propio del campo, antes de cualquier campo anidado, y tiene que estar completo (seguido de un espacio, o ser `=`). Si falta o está incompleto, se rechaza. El resultado de la lista de prohibidos se compara contra ese nombre. Lo probé en un prototipo de unas 20 líneas:
  - marca como no literal: `QUOTE→DDEAUTO` e `IN{QUOTE "CLUDETEXT"}`;
  - acepta: `= {NUMPAGES}-1`, `={NUMPAGES}-1`, `IF {PAGE}`, `TOC` y `HYPERLINK`;
  - sigue detectando `INCLUDEPICTURE {QUOTE url}`.
  - Además resuelve el P2-1.
  - Hay que sumar una prueba de esta forma en AC02 y una mutación en AC05.

#### P2 (no bloqueantes)
1. **Falsos rechazos por palabras sueltas** (`document.py:210`). Como la expresión busca `\bLINK\b` y las demás en toda la instrucción, se rechazan plantillas legítimas. Lo comprobé con estas instrucciones:
   - `HYPERLINK "https://empresa.example/link/contacto"`
   - `…/import-export/`
   - `…/dde`
   - `DOCPROPERTY "Link"`
   - `MERGEFIELD Import`

   Venía de antes: el filtro viejo ya rechazaba todas estas, salvo en la forma `fldSimple` con comillas simples, que ahora también se rechaza. El impacto es acotado porque Word guarda los hipervínculos normales como `w:hyperlink` con relación, no como campo. El arreglo del P1 lo resuelve.
2. **La lista de prohibidos está incompleta.** `DATABASE` (con cadena de conexión externa) y `RD` (documento externo) se aceptan; lo ejecuté. Hoy se actualizan sólo a pedido, porque `no_update_on_open` está puesto. Está fuera de los siete campos que nombra el contrato, así que es una limitación y no un defecto de WI22.

#### P3
1. **La forma "the Strict namespace"** (`tests/test_template_filter.py:95`) no es una forma que Word lea: un elemento Strict dentro de un documento Transitional. El "segundo lector" independiente comparte la misma suposición (`:144`), así que no prueba que sea un campo real. Es inocuo, porque rechazar de más acá no tiene costo.
2. **La forma "in a deleted instruction"** (`:101`) pone `w:delInstrText` fuera de un `w:del`. Es igual de dudosa como forma real, y también inocua.
3. **Una parte XML de `customXml` codificada en Shift_JIS u otra codificación multibyte que no sea UTF** se rechaza como "no es XML legible"; lo ejecuté (expat no soporta esas codificaciones). Un SVG de Illustrator, con su DTD y entidades internas, se lee bien; también lo ejecuté. El riesgo de un falso rechazo es bajo.
4. **`mutations.py:6`** dice `<empty folder outside it>`, pero falla con `FileExistsError` si la carpeta ya existe (hace `copytree` en la línea 113). La carpeta tiene que no existir. Corregir el docstring.

### Lo que el agente agregó sin que el contrato lo pidiera

Ninguno de los agregados rompe nada.

- **`delInstrText`:** correcto. Si alguien rechaza el cambio registrado, el campo vuelve.
- **Namespace Strict:** sobra, pero no hace daño. python-docx no abre paquetes Strict de todos modos.
- **Relaciones sin distinguir mayúsculas:** es una precaución que no hace daño.
- **Leer como XML toda parte `.xml`/`.rels` o declarada XML:** es necesario para AC03 y para cubrir notas al pie, glosario y comentarios. El único costo es el P3-3.

En la plantilla buena de AC01, en la plantilla de ejemplo y en el informe neutral no apareció ningún falso rechazo: la suite completa pasa. El informe sólo crea `w:hyperlink`, `TOC` y `PAGEREF` con nombres de marcador fijos (`layout.py:299-345`); ningún texto del usuario termina dentro de una instrucción.

### Mecanismo más simple

Comparar contra el **nombre** del campo, como en el arreglo del P1, es más simple y más preciso que buscar la palabra en cualquier parte de la instrucción. Con eso alcanza.

Una **lista de permitidos** (`PAGE`, `NUMPAGES`, `SECTIONPAGES`, `TOC`, `PAGEREF`, `HYPERLINK`, `REF`, `STYLEREF`, `DATE`, `DOCPROPERTY`, `IF`, `=`, `SEQ`…) cerraría también `DATABASE`/`RD` y los campos que aparezcan en el futuro. A cambio puede rechazar plantillas reales con campos menos comunes, como `ADDIN` de Zotero o EndNote, o `FILLIN`. Elegirla es decisión del owner, no corrección de este work item.

### Criterios

- **WI22-AC01 — cumple.** AR04 es idéntica a la de INGOL (comparador con código 0), falla en `59343c9` y pasa en `6daabab`. La plantilla buena se acepta y su informe se construye.
- **WI22-AC02 — cumple.** Están todos los campos en todas las formas, con una prueba por forma y la verificación del segundo lector (con las salvedades P3-1 y P3-2). Las formas que el contrato enumera pero que el filtro viejo ya detectaba quedan como regresión, no como prueba que distinga. El hueco del P1 no está entre las formas enumeradas.
- **WI22-AC03 — cumple.** El tipo con macros se detecta en 6 escrituras más `Default` y `vbaData`, y una parte ilegible se rechaza nombrándola. Ambas cosas fallan con el código viejo.
- **WI22-AC04 — cumple.** Con el chequeo de la plantilla apagado, el informe falla, se borra el `.partial` y no se escribe nada. También falla con el código viejo.
- **WI22-AC05 — cumple.** Las 16 mutaciones se detectan; lo reejecuté sobre `6daabab`.
- **WI22-AC06 — pendiente a propósito.** Faltan las dos revisiones y `local-test-run.txt` desde un clon limpio con los kits. Las 4 limitaciones del registro se reproducen y `changed-tests.md` es consistente con el diff de `tests/test_report.py`.

### Limitaciones de esta revisión

- No corrí Word, así que el comportamiento real de los nombres anidados no está verificado.
- No corrí las `test_d1_*` que necesitan los kits.
- No revisé la seguridad más allá de este filtro; eso queda para la revisión de seguridad.

**Qué sigue:** el owner decide una sola cosa: si el P1 se corrige en este work item (recomendado, unas 20 líneas más una prueba y una mutación) o queda como limitación `WI22-P3-3` aceptada. Después corresponde la revisión de seguridad.

## Revisión de seguridad (rol `revisor-seguridad`)

## Revisión de seguridad de WI22 (VisualMeetingTool, commit 6daabab)

**Una aclaración primero:** un clasificador de seguridad cortó mi trabajo mientras armaba las plantillas sintéticas de ataque. No construí ninguna plantilla de reproducción. Lo único que corrí fueron las pruebas que ya existían en la carpeta de trabajo (`tests.test_template_filter`, `tests.test_d1_r02_plantilla`, `tests.test_report`): 119 pruebas, todas pasan. Todo lo de abajo sale de leer el código, salvo donde digo lo contrario. Ningún hallazgo está demostrado ejecutándolo.

Versiones en la carpeta de trabajo: Python 3.12.10, expat 2.7.1, python-docx 1.2.0, lxml 6.1.1.

### Hallazgos

#### P2 — El filtro bloquea una lista fija de nombres de campo, y esa lista deja afuera campos que también traen contenido de afuera
**Leído, no ejecutado. Confianza 85.** `meetingtool/report/document.py:59` y `:209-212`.

- **Cómo está hecho:** `ACTIVE_FIELDS` lista siete nombres y busca cada uno como palabra suelta en cualquier parte de la instrucción. Todo campo que no esté en la lista se acepta.
- **Qué falta:** campos que se conectan a una base de datos o a un documento externo cuando el campo se actualiza (por ejemplo `DATABASE`, `RD`) no figuran. Son del mismo tipo que `INCLUDE*` o `LINK`, que sí se bloquean.
- **Qué puede hacer alguien:** si una plantilla de un tercero trae uno de esos campos, `check_report` repite las mismas reglas, así que el campo pasa al informe.
- **Lo que no verifiqué:** si Word actúa al abrir el archivo o sólo cuando el lector actualiza los campos o imprime. Sin Word no se puede comprobar, igual que WI22-P3-1.
- **Arreglo mínimo:** cambiar la lista de prohibidos por una de permitidos. Sería un nombre literal como primera palabra de la instrucción, tomado de una lista corta: los que usa un buen informe, como `PAGE`, `NUMPAGES`, `TOC`, `HYPERLINK`, `DATE`, `STYLEREF` y los de propiedades del documento. Todo lo demás se rechaza. Hoy el filtro también tiene el problema contrario: rechaza instrucciones legítimas que mencionan la palabra en otro lado, por ejemplo una URL que contiene `/link`. Eso no es de seguridad, pero la lista de permitidos lo arregla igual.

#### P2 — WI22-P3-3: un campo cuyo nombre lo arman otros campos metidos en su instrucción
**Leído, no ejecutado. Confianza 85 en que el filtro lo deja pasar; no sé si Word lo ejecuta.** `document.py:123-146`.

- **Por qué pasa:** `field_instructions` lee aparte cada campo metido dentro de otro (eso está bien). Pero el campo de afuera queda sólo con el texto literal que lo rodea. Como lo que devuelven los campos de adentro no se lee, el nombre armado nunca aparece.
- **Severidad:** el chequeo del informe no ayuda, porque aplica la misma regla y tiene el mismo punto ciego. Si Word arma el nombre así, el campo llega al cliente. No lo pude confirmar, así que lo dejo en P2 y no en P1. Si una prueba con Word lo confirma, sube a P1.
- **¿Rechazar todo campo que tenga otro adentro lo cierra?** Para esta vía, sí. Pero rechaza plantillas legítimas, por ejemplo un `IF` o un `=` que adentro usa `PAGE`.
- **Arreglo mínimo, más preciso:** que todo campo tenga como nombre una palabra literal, escrita antes de cualquier campo de adentro, que esté en la lista de permitidos. Además, que ningún campo de la lista quede con el nombre vacío o pegado a un campo de adentro. Esto cierra la construcción de nombres sin romper `IF` ni `=`.

#### P3 — WI22-P3-4: hipervínculos a `file:` o a rutas de red
**Leído. Confianza 90 en que se aceptan** (el registro trae su reproducción). `document.py:205`.

- **Riesgo:** necesita que el cliente haga clic, y Word muestra una advertencia. Aun así, el informe sale con el nombre de la empresa, y el texto visible puede no coincidir con el destino. Una ruta de red puede dejar filtrar credenciales de Windows al hacer clic.
- **Para un informe que va a un cliente,** no lo considero aceptable sin un límite.
- **Arreglo:** permitir sólo `http`, `https`, `mailto` y anclas internas, tanto en las relaciones de tipo hipervínculo como en el campo `HYPERLINK`. Todo lo demás se rechaza.

#### P3 — Endurecimiento: fuentes incrustadas
**Leído. Confianza 80.**

- Las relaciones internas de tipo `font` (de `fontTable.xml`) no están en `ACTIVE_RELATIONSHIPS`. python-docx conserva toda parte alcanzable, así que una fuente de un tercero llega al informe.
- No traen ni ejecutan nada de afuera, pero es código binario de terceros que Word interpreta.
- **Arreglo:** rechazarlas o quitarlas.

### Respuestas a las preguntas

**1. ¿Queda alguna vía para que un campo traiga o ejecute contenido de afuera?** Sí, dos, según lo leído: los campos que la lista no nombra (primer P2) y los nombres armados por campos de adentro (segundo P2). Las formas que nombra R02 (entidades, mayúsculas, prefijos, comillas simples, CDATA, comentarios, encabezado, pie y notas al pie) están cubiertas, y las pruebas lo muestran para cada campo de la lista.

**2. Otras vías de contenido activo.**
- **Cubiertas por las relaciones:** `altChunk`, OLE (`oleObject` y `package`), controles y ActiveX, `attachedTemplate`, `subDocument`, `frame` y toda relación externa que no sea un hipervínculo. Eso incluye una imagen vinculada con `a:blip r:link`, el VML que apunta a una relación externa y un objeto OLE vinculado. El tipo de relación se compara por su último segmento y sin distinguir mayúsculas, así que también entra el espacio de nombres Strict.
- **No cubiertas:** las fuentes incrustadas (P3 de arriba).
- **Sin conclusión:** los atributos VML con rutas directas, sin relación de por medio, y los elementos de combinación de correspondencia en `settings.xml` que no usan una relación. No pude confirmar si Word los usa, así que no los presento como hallazgo; quedan para la prueba con Word.

**3. Leer XML de terceros con `xml.etree`.** Está bien acotado. `ElementTree` no busca entidades externas, y expat 2.7.1 limita la expansión: una bomba falla al leerse y la parte se rechaza como ilegible, cosa que una prueba existente ya cubre. Si una plantilla trae un DTD inofensivo, python-docx (con lxml sin resolver entidades) no lo copia al guardar, así que la revisión del informe falla y no entrega nada. El tamaño total del paquete queda en R08.

**4. Hipervínculos a `file:` o rutas de red.** Ver el P3 de arriba: necesitan un límite.

**5. ¿Se puede saltear el chequeo del informe final?** Según lo leído, no. `build_report` siempre llama a `check_report` antes del `os.replace` (`document.py:688-704`). Los dos caminos que llegan acá, `app/jobs.py:486` y `report/__main__.py:93`, pasan por `build_report`. Hay un detalle: `template_bytes` lee el archivo dos veces (`:227` y `:247`), y la segunda lectura no se revisa. Eso no saltea nada porque el informe se revisa igual al final. Lo que no revisé: el servidor (`server.py:_file`) entrega cualquier `.docx` de la carpeta sin volver a revisarlo, así que un archivo cambiado a mano después de armarse sale tal cual. Eso queda fuera de este cambio.

### Conclusión

¿El cambio cierra R02? Sí, para lo que R02 describe: el mismo nombre de campo escrito en otra forma equivalente. No cierra el problema de fondo, que el filtro reconozca contenido activo por una lista de prohibidos. Los dos P2 quedan abiertos, y conviene que la lista de permitidos entre antes del pull request o quede registrada como limitación P2, no P3.

Sigue: el owner decide si los dos P2 bloquean el pull request o quedan registrados como limitaciones.

## Lo que se hizo con cada hallazgo

Una sola pasada de corrección (commits `e18acff`, `4a711be`, `6cd5e26`), hecha
por el agente del rol de construcción y revisada por el criterio. Las dos
revisiones, de `6daabab`, llegaron por el buzón de INGOL: motor Claude, roles
`revisor-independiente` y `revisor-seguridad`, cuenta empresa, modelo pedido
por rol (`rol:criterio`, resuelto a `opus`), esfuerzo alto. Ninguno de los dos
roles tiene herramientas de escritura. A la revisión de seguridad un
clasificador le cortó el armado de plantillas de ataque: sus hallazgos son
leídos, no ejecutados, como dice su texto.

| Hallazgo | Qué se hizo |
|---|---|
| Independiente P1 y seguridad P2: un campo cuyo nombre arman campos anidados | Corregido: el nombre de cada campo tiene que estar escrito completo en el archivo, antes de cualquier campo anidado; un campo sin nombre escrito, o con el nombre pegado a un campo anidado, se rechaza (`report.active.unnamed_field`). `= {NUMPAGES} - 1` e `IF {PAGE} ...` se siguen aceptando. `WI22-P3-3` queda "fixed by e18acff" |
| Independiente P2-1: falsos rechazos por una palabra suelta (`/link/` en una URL, `DOCPROPERTY "Link"`) | Corregido por lo mismo: la lista se compara sólo contra el nombre del campo |
| Independiente P2-2 y seguridad P2: `DATABASE` y `RD` faltaban en la lista | Agregados, con sus pruebas en todas las formas |
| Seguridad P2: la lista es de prohibidos, no de permitidos | Limitación conocida `WI22-P3-5`; cambiar a una lista de permitidos es una decisión del owner (puede rechazar plantillas reales con campos poco comunes) |
| Seguridad P3: hipervínculos a `file:` o rutas de red | Corregido: un hipervínculo (relación o campo `HYPERLINK`) sólo puede ir a `http`, `https`, `mailto` o a un ancla; `WI22-P3-4` queda "fixed by e18acff" |
| Seguridad P3: fuentes incrustadas | Limitación conocida `WI22-P3-6` |
| Independiente P3-1 y P3-2: las formas "Strict" y "delInstrText fuera de w:del" pueden no ser formas que Word lea | Se dejan: rechazar de más ahí no cuesta nada (la misma revisión lo dice) |
| Independiente P3-3: una parte en Shift_JIS se rechaza como ilegible | Limitación conocida `WI22-P3-7` |
| Independiente P3-4: el docstring de `mutations.py` | Corregido: la carpeta de trabajo no tiene que existir |
| Seguridad, sin hallazgo: el servidor entrega un `.docx` cambiado a mano sin volver a revisarlo | Fuera de este trabajo: lo que se revisa es lo que la aplicación arma |

Después de la corrección, sobre `6cd5e26` en clones limpios: la suite sin los
kits, 473 pruebas OK; las 22 mutaciones detectadas (`mutations.txt`);
`reproduce.py`, 59 coincidencias, 0 diferencias (el único error es
`WI05-P3-5`, que ya falla en main).
