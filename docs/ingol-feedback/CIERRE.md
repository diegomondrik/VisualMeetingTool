# Informe de cierre para INGOL — VisualMeetingTool, piloto D1

Escrito el 2026-10-08 por el ejecutor (Claude Code) para que el owner lo lleve a una sesión de INGOL, que lo lee en
sólo lectura (D-179, D-189). Este archivo es del proyecto; no se escribió nada en archivos de INGOL.

**Cómo leerlo.** Cada afirmación lleva su evidencia entre corchetes: un comando, un archivo o un commit. "No
verificado" quiere decir que no pude comprobarlo en esta sesión. "No medido" quiere decir que nadie lo midió; no hay
estimaciones. Las rutas son de este repositorio salvo que diga otra cosa. Las cifras de `metrics.yaml` salen de
`C:/Users/Diego/VisualMeetingTool-data/metricas/metrics.yaml` (fuera del repositorio, a pedido del owner; D-179).

**Estado en una mirada.**

- Primera tanda (R01 a R06): integrada en `main`.
- Segunda tanda (R07 a R11): construida, revisada y con la suite completa en verde, pero **sin integrar**. Tres de sus
  PR están abiertos (#28, #29, #30) y la revisión protegida de INGOL los rechaza por una causa de proceso (TP-08, punto
  2.1). El PR de R09 todavía no está abierto.
- El juez externo de INGOL corrió una vez, se cortó por cuota y dejó un borrador con **1 P0 y 2 P1 abiertos** más un P1
  aceptado por el owner.

---

## 1. Qué se hizo

### 1.1 R01 a R11

La revisión externa de Codex es del 2026-10-02 [`.ingol/work-items/*/contract.yaml`, que la citan]. Cada hallazgo se
cerró con un work item (WI) y su PR. "Commit" es el de integración en `main`, o la punta de la rama si no se integró.

| R | Qué decía (en una línea) | WI y PR | Estado | Commit |
|---|---|---|---|---|
| R01 | Dos guardados pueden devolver éxito sobre el mismo id y los JSON se escriben directo al destino | WI20, PR #20 | Cerrada | `bc24f89` |
| R03 | El modo de preguntas y respuestas descarta lo pagado ante cualquier error | WI20, PR #20 | Cerrada | `bc24f89` |
| R05 | Con transcripción, el video se lee sólo hasta donde llega la transcripción | WI21, PR #21 | Cerrada | `59343c9` |
| R02 | El filtro de la plantilla de Word miraba texto, no XML | WI22, PR #22; seguimiento WI23, PR #24 (lista de campos permitidos) | Cerrada, con un residual aceptado por el owner (`WI23-P3-3`) | `bde64df`, `eff7ef7` |
| R04 | Secciones vacías en el resumen; años y cifras del registro sin contrastar | WI25, PR #25 | Cerrada | `41f6722` |
| R06 | Una transcripción de texto sólo se leía en una codificación | WI26, PR #26 | Cerrada | `f1bde92` |
| R07 | Techo de gasto: una respuesta que costó más de lo estimado | WI28, PR #28 | **Abierta**: hecha y revisada, sin integrar | `30a9583` (punta de la rama) |
| R08 | El límite de subida no limita lo que un Word descomprime | WI29, PR #29 | **Abierta**: sin integrar | `0ecf53f` (punta de la rama) |
| R09 | Cada imagen de una reunión relee los resúmenes de todo el proyecto | WI30, PR todavía no abierto | **Abierta**: sin integrar | `ccda496` (punta de la rama local, no empujada) |
| R10 | La suite no prueba las versiones que empaqueta el instalador | WI31, PR #30 | **Abierta**: sin integrar | `f787048` (punta de la rama) |
| R11 | La guía contradice el estado de las pruebas | WI31, PR #30 | **Abierta**: sin integrar | `f787048` (punta de la rama) |

[Los números de PR y los commits de integración: `gh pr list --state all`; `git log origin/main --merges`. Qué R cerró
cada WI: el primer párrafo de cada `contract.yaml` (línea 6 en WI20, WI21, WI22 y WI25; línea 5 en WI26, WI28,
WI29 y WI30; WI31 en su rama). La gravedad de cada R no está en el repositorio
salvo R08 y R09, que sus contratos llaman P2; el resto: no verificado.]

Además de las R, dos WI nacieron del uso real del owner: WI24 (PR #23, `32700a1`, la primera reunión real) y WI27
(PR #27, `1a78ce4`, la segunda) [`metrics.yaml`, pasos 5 y 11]. WI18 (el instalador de Windows) no es una R; su PR #19
sigue abierto [`gh pr view 19`].

"Cerrada" quiere decir: el contrato se cumplió con pruebas, mutaciones, revisión independiente y la suite completa con
los kits en un clon limpio. No quiere decir que el juez externo no encontró hermanos del mismo problema (punto 1.2).

### 1.2 El juez externo de INGOL

Corrió una vez, sobre `main` `f1bde92` (primera tanda cerrada), el 2026-10-07: motor codex, 19 minutos, **se cortó por
la cuota de Codex al escribir la entrega** y no dejó `informe.md` ni `hallazgos.yaml`; el implementador corrió el script
que el juez había escrito para armarlos [`metrics.yaml`, paso 9]. El owner tomó ese borrador como el resultado, sin
volver a correrlo [paso 10; copia en `C:/Users/Diego/VisualMeetingTool-data/metricas/juez-d1-20261007/`]. La corrida
de la suite en el entorno del juez quedó sin cerrar. No se volvió a correr el juez después de la segunda tanda.

Resultado del borrador: 9 hallazgos, 1 P0, 3 P1, 3 P2, 2 P3 [`hallazgos.yaml`]. Estado de cada uno hoy:

| Hallazgo | Gravedad | Qué es | Estado hoy |
|---|---|---|---|
| D1-01 | **P0** | El Word y la reextracción de imágenes no comparten la garantía de escritura atómica (temporal fijo `summary.docx.partial`; la reextracción borra las imágenes antes de escribir las nuevas) | **Abierto.** Verificado en `main`: `meetingtool/report/document.py:912` sigue usando el temporal de nombre fijo y `meetingtool/frames/extract.py:240` sigue borrando antes de escribir. Sin work item |
| D1-02 | **P1** | Si también falla la vuelta atrás del guardado, se borra lo ya pagado | **Abierto.** Verificado en `main`: `meetingtool/app/jobs.py:553` hace `shutil.rmtree(final)` si falla el segundo renombrado. Sin work item |
| D1-03 | P1 | Un campo de imagen externa atraviesa el filtro de plantilla por `mc:AlternateContent` | **Aceptado por el owner** el 2026-10-07 como riesgo bajo (`WI23-P3-3`, con reproducción) [`metrics.yaml`, pasos 6 y 9]. No verificado si esa aceptación cubre exactamente la variante con campo de imagen externa que cita el juez |
| D1-04 | **P1** | Un registro de preguntas vacío se entrega como "no hubo preguntas" | **Abierto.** Verificado en `main`: `meetingtool/summary/qa.py:590-612` acepta `questions=[]`, y `qa.py:745` escribe "No se planteó ninguna pregunta". Sin work item |
| D1-05 | P2 | Tras un corte, la CLI puede usar conocimiento anterior a una reunión guardada | Abierto. No verificado en esta sesión |
| D1-06 | P2 | = R08 | WI29, PR #29 abierto |
| D1-07 | P2 | = R09 | WI30, sin PR |
| D1-08 | P3 | La explicación de dónde corren las pruebas contradice el workflow | WI31, PR #30 abierto (corrige el README y la guía) |
| D1-09 | P3 | Dos pruebas de idioma fallan por palabras en la ruta de trabajo | Abierto. No verificado en esta sesión |

**P0 y P1 abiertos hoy: 1 P0 (D1-01) y 2 P1 (D1-02, D1-04).** La meta de la tanda ("R01 a R06 cerrados, ningún P0 ni
P1 nuevo") no se cumplió [`metrics.yaml`, paso 9]. El owner pidió terminar R07 a R11 en la noche del 2026-10-07 [`contract.yaml` de WI29 y WI30: "The owner asked on
2026-10-07 to finish all of R07 to R11 overnight"]; los tres abiertos del juez (D1-01, D1-02, D1-04) no tienen work item
y esperan su orden [la orden misma no está escrita en un archivo: no verificado].

---

## 2. Problemas con INGOL

Costo: sólo lo que se midió; el resto dice "no medido". Los mensajes del owner por problema no se registraron uno por
uno (`metrics.yaml` sólo los acumula por sesión).

### 2.1 Los registros de aprobación los tiene que escribir el owner a mano, y mientras tanto los PR quedan en rojo

- **Qué pasó.** La revisión protegida (`bootstrap`) falla en el predicado TP-08: "work item … requires an approval
  record for authority independent_review in the standard lane, and none is present". Pasa con los tres PR de la
  segunda tanda (#28, #29, #30) y con el PR #19 (WI18), abierto desde 2026-10-02. La suite `tests` de los mismos PR
  pasa. El ejecutor no puede escribir esos registros (un clasificador de seguridad lo impide, y la autoaprobación es
  rechazada por el propio TP-08), así que cada work item pide que el owner pegue un bloque de PowerShell [INGOL,
  `docs/method/firma_pendiente.md`, como lo describe: "El clasificador de seguridad no deja que el ejecutor escriba los
  registros de aprobación"; archivo de INGOL leído en sólo lectura].
- **Cómo reproducirlo.** `gh pr checks 28` (también 29, 30, 19): `bootstrap fail`, `tests pass`.
  `gh run view 37795002294 --log | grep "predicates failed"` da `TP-08`. El registro que falta es un
  `.ingol/work-items/<id>/approvals/<id>.json` con `authority: independent_review` y el digest del contrato (el
  `sha256` del `contract.yaml`: verificado con `sha256sum` contra el registro de WI27).
- **Cuánto costó.** Una acción del owner por work item. En esta tanda: 4 trabajos (WI28 a WI31) más WI18. Minutos del
  owner: no medidos. El PR de WI18 lleva abierto desde 2026-10-02T00:18 [`gh pr view 19`]; por qué sigue abierto además
  del TP-08: no verificado.
- **Resuelto.** No. Pendiente del owner al cierre de este informe.
- **ID en el registro de limitaciones.** No tiene.

### 2.2 `ingol init` no sirve para un proyecto que ya existe (H1)

- **Qué pasó.** `ingol init` sólo acepta una carpeta vacía. [`docs/limitations/REGISTER.md`, H1]
- **Reproducirlo.** `python docs/limitations/reproduce.py --ingol-repo <clon de INGOL> H1` (necesita Go).
- **Costo.** No medido. **Resuelto.** No: abierto. **ID.** H1.

### 2.3 `ingol init` no escribe `.gitignore`, `.gitattributes` ni el repositorio git, y `doctor` falla en Windows por eso (H4)

- **Qué pasó.** Con `core.autocrlf=true` (el valor por defecto de git en Windows), un clon de un proyecto recién
  iniciado hace que `ingol doctor` marque 27 de 29 superficies como bloqueadas por no ser idénticas byte a byte. Este
  proyecto lo evita con su propio `.gitattributes`. [REGISTER, H4]
- **Reproducirlo.** `python docs/limitations/reproduce.py --ingol-repo <clon> H4`: clon LF exit 0, 0 bloqueadas; clon
  CRLF exit 1, 27 bloqueadas.
- **Costo.** No medido. **Resuelto.** Sólo para este proyecto (con su `.gitattributes`); en INGOL: abierto. **ID.** H4.

### 2.4 TP-09 mira el texto de `.gitignore`, no su efecto (H6)

- **Qué pasó.** `/generated/` aísla la carpeta igual que `generated/`, pero TP-09 bloquea la primera. El proyecto dejó
  `generated/` como la única línea de carpeta sin anclar. [REGISTER, H6]
- **Reproducirlo.** `python docs/limitations/reproduce.py --ingol-repo <clon> H6`.
- **Costo.** No medido. **Resuelto.** No: abierto. **ID.** H6.

### 2.5 Un proyecto gobernado no podía correr sus propias pruebas en GitHub (H3)

- **Qué pasó.** Sólo se admitía el workflow de INGOL, así que del WI01 al WI17 las pruebas corrieron en la máquina del
  owner y su salida se commiteó como evidencia. [REGISTER, H3]
- **Cómo se resolvió.** INGOL WI-029 (D-190): el wrapper fijado a INGOL `feb1e53` y un `tests.yml` en su forma cerrada;
  commit `03b8573` en este proyecto, el 2026-10-01. La reproducción local contra un `main` con el wrapper pasa
  CI-TRUST, TP-05 y TP-15 [REGISTER, H3; `python docs/limitations/reproduce.py --ingol-repo <clon> H3`].
- **Costo.** Hasta ese commit las pruebas se corrían en la máquina y su salida se commiteaba [REGISTER, H3]. Cuántos PR
  se integraron así y el tiempo del owner: no medidos. **Resuelto.** Sí. **ID.** H3.

### 2.6 Los kits son privados, no están en la CI, y las pruebas que los usan son lentas y se quedan sin memoria

- **Qué pasó.** Tres de los seis archivos `tests/test_d1_*.py` usan `ingol_kits`: sin los kits se saltean, así que
  GitHub nunca los corre [REGISTER, `WI20-P3-6`; verificado: `grep -L ingol_kits tests/test_d1_*.py` lista los otros
  tres]. Con los kits, la suite entera tarda unos 40 minutos por corrida: 2.306 s (WI28), 2.365 s (WI29), 2.344 s
  (WI30), 2.362 s (WI31) [`Ran N tests in …` en cada `docs/evidence/<id>/local-test-run.txt` de las ramas]. Dos pruebas
  del paquete (AR05 y AR10) esperan un candado real: AR05 unos 21 min, AR10 unos 2 [`metrics.yaml`, paso 2].
- **Memoria.** El 2026-10-07 dos intentos de la suite con los kits murieron en AR05 con `MemoryError`, "can't start new
  thread" y fork fallido; hubo que partir la corrida en dos (603 OK sin kits, 22 OK del paquete con kits) [paso 8; mismo
  recurso en el paso 11]. En esta tanda, varios agentes en paralelo agotaron la memoria virtual de Windows: tres
  corridas de mutaciones terminaron con los códigos de salida 3221225773 y 3221225495 y un `WinError 8` [primera
  versión de `docs/evidence/01M4CM3YV6DMY3QDWAZDMAANW6/mutations.txt`, antes de `1a666bc`; el texto del error está en la
  transcripción del subagente, que no está en el repositorio].
- **Reproducirlo.** `PYTHONPATH=~/.claude/ingol-kits/python python -m unittest discover -s tests -v` en un clon limpio
  (necesita los kits).
- **Costo.** Las cuatro suites de la segunda tanda sumaron 9.377 s (2 h 36 min) de corrida, una detrás de otra porque por
  la memoria no pueden ir juntas (la suma de los cuatro `Ran … in …s` de arriba); la de WI30 se está rehaciendo. El
  reloj de espera de esta sesión: no medido.
- **Resuelto.** Parcial: este proyecto agregó pruebas propias sin kits que fijan el núcleo de cada arreglo, para que la
  CI las corra (por ejemplo `tests/test_data_integrity.py`). Los kits siguen fuera de la CI. **ID.** `WI20-P3-6`.

### 2.7 El paquete del piloto trajo el nombre de un cliente real en sus pruebas

- **Qué pasó.** Las pruebas del piloto copiadas al proyecto usaban el nombre de un cliente real; el repositorio es
  público, así que se cambió por uno neutro. [`.ingol/work-items/01M46KHBYCXMGM0K6N2RM651PE/contract.yaml`: "the project
  name of the copied tests is a neutral one instead of a client's"]
- **Costo.** No medido. **Resuelto.** Sí, en este proyecto. **ID.** No tiene.

### 2.8 El buzón: pérdidas y límites

- **El revisor sólo deja su último mensaje.** En la revisión de WI23 el buzón guardó sólo la conclusión del revisor
  (un P1 de Markup Compatibility), no el informe completo [`metrics.yaml`, paso 6, "no medido"]. Desde entonces los
  pedidos de revisión dicen "escribí el informe entero en tu mensaje final (es lo único que se guarda)" [los pedidos están
  en la carpeta temporal de la sesión, no en el repositorio: no verificable desde acá].
- **El revisor no puede escribir su evidencia.** La revisión de WI29 dice: "el buzón no me deja escribir en la carpeta de
  salida" [`C:/Users/Diego/Documents/Codex/buzon/3-de-codex/20261007-234800-vmt-wi29-revision-independiente/respuesta.md`;
  copiada en `docs/evidence/01M4CM3YV7RF9ET37K61XBYVRY/independent-review.md`, rama de WI29].
- **Un clasificador cortó a un revisor.** El revisor de seguridad de WI22 no pudo armar plantillas de ataque; sus
  hallazgos son "leídos", no ejecutados [`metrics.yaml`, paso 4].
- **La cuota de Codex cortó al juez.** 19 minutos y 215.075 tokens, sin entrega [paso 9].
- **El vigilante del buzón tenía un candado viejo** (`.vigilante.lock` con un proceso muerto) el 2026-10-05 y hubo que
  borrarlo y volver a arrancarlo. Fuente: una nota de memoria de la sesión, no un archivo del repositorio: **no
  verificado**.
- **Costo.** El de las corridas del buzón (cuenta empresa): no medido [pasos 2, 3, 4, 6, 7, 8]. **Resuelto.** Los
  pedidos se adaptaron; las causas siguen. **ID.** No tiene.

### 2.9 `medir_cambios.py` devolvió una lista vacía

- **Qué pasó.** El 2026-10-05 GitHub devolvió una lista vacía de corridas de `main` "después de 4 intentos" y el script
  no midió; el owner corrigió el comando (`--control-prefijos .ingol/,docs/evidence/ --cache <temporal>`)
  [`metrics.yaml`, paso 1, dos aclaraciones].
- **Costo.** Dos aclaraciones en `metrics.yaml`; minutos: no medidos. **Resuelto.** Sí, con el comando corregido.

### 2.10 "La suite corrió sobre el árbol exacto que se integra" no puede cumplirse al pie de la letra

- **Qué pasó.** La evidencia se commitea después de la corrida, así que el commit integrado difiere del probado en
  archivos de evidencia y de aprobación. [REGISTER, `WI01-P2-3`]
- **Reproducirlo.** `python docs/limitations/reproduce.py WI01-P2-3`. **Resuelto.** No, "por diseño". **Costo.** No
  medido.

### 2.11 El registro de hallazgos no tiene dónde vivir en este proyecto

- **Qué pasó.** El formato común de hallazgos de INGOL pide `docs/hallazgos/registro.yaml` y prohíbe ponerlo dentro de
  `.ingol` (control TP-12) [skill `hallazgos`, leída]. Este proyecto no lo tiene: `ls docs` muestra `evidence`,
  `limitations`, `proposals` y esta carpeta. Los hallazgos de las revisiones están sólo en cada `independent-review.md`,
  así que el tablero de INGOL no los ve. **Costo.** No medido. **Resuelto.** No. **ID.** No tiene.

---

## 3. Lo que INGOL hizo bien

1. **Las pruebas del piloto fallaban por la razón correcta.** Sobre `03b8573`, 18 de 18 pruebas del paquete fallaban por
   aserción, ninguna por importación ni entorno, en 54,1 s. La de R05 mostraba la diapositiva perdida: con transcripción
   la lectura se cortaba a los 6,0 s [`metrics.yaml`, paso 1].
2. **El control de superficies no declaradas funciona.** El PR #2 (una prueba negativa a propósito, "undeclared
   surface") fue rechazado por TP-06, TP-08, TP-12 y TP-03 [`gh run view 36147998376 --log | grep "predicates failed"`].
3. **TP-08 hace su trabajo.** Impide integrar un work item sin el registro de revisión independiente atado al digest del
   contrato. Hoy detiene los PR #28 a #30 y el #19 por esa falta (punto 2.1): es una molestia, y es también el control
   actuando [`gh pr checks 28`].
4. **La revisión independiente encontró defectos reales casi siempre.** De 12 revisiones (WI20 a WI31), 7 encontraron
   al menos un P1: WI22 (nombre de campo armado por campos anidados), WI23 (Markup Compatibility), WI24 (regresión del
   registro con `.txt [HH:MM:SS]`), WI27 (`entre [a y b]` pasaba como lista), WI28 (dos P1), WI29 y WI31 [`metrics.yaml`,
   pasos 4, 6, 5, 11; `docs/evidence/<id>/independent-review.md` de WI28, WI29 y WI31]. Las otras cinco no tenían P1.
   Dos casos concretos:
   - WI29: un `.docx` de 767 bytes con una parte BZIP2 hacía usar más de 1 GB (1.094 MB medidos) antes de rechazarlo; el
     revisor lo midió en un proceso nuevo y también contra el commit anterior para comprobar su instrumento (286 → 1.358
     MB) [`docs/evidence/01M4CM3YV7RF9ET37K61XBYVRY/independent-review.md`, rama de WI29].
   - WI30: en Windows, un resultado suelto que la portada no lista se servía igual por su nombre en minúsculas, porque el
     disco no distingue mayúsculas [`docs/evidence/01M4CM3YV88S4K9B9SR5ANTNVZ/independent-review.md`, P2-1].
5. **Las mutaciones obligan a que cada prueba pueda fallar.** Con los kits, 3 mutaciones de WI20 no eran detectadas por
   las pruebas del paquete (candado en memoria, id elegido mirando con el candado puesto, reunión guardada aunque el
   conocimiento falle); el porqué de cada una quedó escrito en `mutations.txt` [`metrics.yaml`, paso 2].
6. **La suite entera en un clon limpio antes del PR encontró una regresión propia:** 13 casos de `test_qa` rotos por la
   corrección de un P2 de WI20; sólo se había corrido `test_data_integrity` tras corregir [paso 2].
7. **El juez externo encontró cosas que el proceso del proyecto no había visto** (D1-01 y D1-02 son del tipo "una
   segunda falla encadenada" y "una salida que no usa el escritor común"), con ejecución y no sólo lectura [`hallazgos.yaml`
   del juez]. Quedó sin cerrar por la cuota, pero su borrador alcanzó.

---

## 4. Lecciones aprendidas

Tres tipos: (a) del proyecto, (b) de plataforma, (c) de método. "Convertida" dice si ya es una prueba o un control.

### (c) De método

| Regla | Qué la originó | Convertida |
|---|---|---|
| Una mutación cuenta como detectada sólo si las pruebas **terminaron y fallaron**; un proceso caído no es una detección | En la noche del 7 al 8, tres mutaciones de WI28 salieron con códigos de falta de memoria y el guion las marcó `DETECTED` | Sí, en los guiones de las cuatro ramas (`1a666bc`, `a2ef2fc`, `8da90f4`, `daf9b74`): exigen la línea `Ran N tests`, salida 1 y `FAILED`, y imprimen `NOT RUN` si no |
| No se salta la revisión independiente por ser un cambio "chico" | 7 de 12 revisiones encontraron un P1 (punto 3.4) | No: es práctica, no control |
| Un "no aprobar" pide una segunda revisión, acotada, del arreglo | WI29: la primera dijo no aprobar; la segunda aprobó y encontró dos P3 más (bits de bandera 5 y 6; bytes de control crudos) | No: es práctica |
| Si el texto afirma que algo se detecta, la reproducción tiene que mostrar esa detección, no un sustituto | WI28 P1-1: los textos decían que se detecta un cambio de precios; no se puede, y la reproducción dividía la estimación en vez de cambiar un precio | Parcial: los textos se corrigieron (`61c88fb`); la regla no es un control |
| Una guía se comprueba en dos sentidos: que los nombres existen, y que lo que dice es cierto | WI31: el script de nombres pasó una frase falsa ("todos los `test_d1` se saltean sin kits") que el revisor encontró leyendo | Los nombres: sí, `docs/evidence/01M4CM3YV9HEAHSW5V5ER4V8W7/check_guide.py` (rama de WI31). Lo cierto: sólo la revisión |
| Tras una corrección, una mutación puede volverse equivalente a otra comprobación; hay que quitar las dos juntas o descartarla | WI30: al agregar la búsqueda del nombre en disco, la comprobación de "es un slug" quedó cubierta y su mutación dejó de detectarse | Sí, en el guion de WI30 (comentario y mutación conjunta) |
| Un script que genera o edita archivos puede dejar bytes de control invisibles; después de editar con scripts, buscarlos | WI29: el ayudante de una prueba quedó con `\x03\x04` crudos; lo vio el segundo revisor, no yo | Parcial: se corrigió, y se buscó en las cuatro ramas (`python` que cuenta bytes < 32 distintos de tab, LF y CR en los archivos del diff); no hay prueba permanente |
| Trabajos pesados, uno por vez en esta máquina | Falta de memoria virtual (puntos 2.6 y 2.8) | No: se hace a mano, en cola |
| El uso real del owner encuentra más que cualquier revisión sintética | WI24 y WI27 nacieron de dos reuniones reales; la primera costó US$0,548 en dos corridas fallidas antes de obtener el informe [`metrics.yaml`, paso 5]; la segunda, US$0,492 pagados sin informe [paso 10] | Sí, cada una tiene pruebas |

### (b) De plataforma

| Regla | Qué la originó | Convertida |
|---|---|---|
| Windows no distingue mayúsculas: `Path(carpeta)/"con-mayuscula"` llega a `Con-Mayuscula`. Comprobar el nombre contra el listado de la carpeta | WI30 P2-1 | Sí, `library._loose_folder` y su prueba (rama de WI30, `8da90f4`) |
| Nunca comparar rutas como texto: la carpeta temporal puede llegar por su nombre corto (`C:\Users\RUNNER~1`) | Una prueba de WI15 falló en las máquinas Windows de GitHub | Sí, `f7b8737` |
| `zipfile` de Python sólo acota la salida de la descompresión para deflate; BZIP2 y LZMA se expanden sin cota. Aceptar sólo métodos acotados | WI29 P1 | Sí, `meetingtool/word_package.py` y tres pruebas (rama de WI29, `a2ef2fc`, `0360f0f`) |
| Windows Sandbox en Windows 11 24H2 no puede arrancar WebView2; una prueba en máquina limpia necesita una máquina real | El primer intento del instalador en Windows Sandbox | Parcial: la ventana ahora dice que WebView2 no arrancó y cómo repararlo (`app.window.webview2_failed`); la prueba se hizo en la computadora de un integrante del equipo [`docs/evidence/01M3VRRZJ3XYC0ADJT8N733F03/clean-machine-sandbox-attempt.txt`, `clean-machine-run.txt`, en la rama de WI18] |
| La memoria virtual de Windows se agota con varias suites a la vez; los fallos se ven como códigos `0xC000012D` (3221225773), `0xC0000017` (3221225495) o `WinError 8` | Punto 2.6 | Sí, en los guiones de mutaciones (ver arriba) |
| Un repositorio público con la revisión de INGOL en `pull_request_target` expone el token de lectura a quien dispare el flujo desde un fork | H5 | No: aceptado como mitigado por diseño [REGISTER, H5] |

### (a) Del proyecto

| Regla | Qué la originó | Convertida |
|---|---|---|
| Los datos de clientes no entran al repositorio (público); las pruebas usan nombres neutros | El nombre de un cliente real en las pruebas del piloto (punto 2.7) | Sí, `repository_guard.py` y su prueba |
| Lo pagado a Gemini no se tira ni se repite: se guarda y se reutiliza sólo para el pedido exactamente igual | R03 y las dos reuniones reales con corridas fallidas | Sí, WI20 y sus pruebas |
| Las versiones de las bibliotecas que prueba la CI son las que empaqueta el instalador | R10 | Sí, `constraints.txt` y `tests/test_pinned_versions.py` (rama de WI31) |

---

## 5. Medición para D2-AC09

Cambios reales hechos en este proyecto, leídos de `metrics.yaml`. Líneas agregadas por `medir_cambios.py`
(`--control-prefijos .ingol/,docs/evidence/`). **"Pedido → integrado" no está medido**: el único tiempo registrado es el
del PR abierto hasta integrado. **Mensajes del owner por cambio: no medido**; la última columna es la diferencia entre
dos acumulados de la sesión, que incluye todo lo que el owner dijo en ese tramo, no sólo ese cambio.

| Cambio | PR | Abierto → integrado | Producto | Pruebas | Control | Docs | CI verde al primer intento | Mensajes del owner (diferencia de acumulados) |
|---|---|---|---|---|---|---|---|---|
| WI20 (R01, R03) | #20 | 11,2 min | 694 | 1.072 | 1.227 | 196 | No (1 empuje) | 7 acumulados; diferencia: no medida |
| WI21 (R05) | #21 | 5,3 min | 10 | 102 | 957 | 98 | Sí | +3 (7 → 10) |
| WI22 (R02) | #22 | 5,9 min | 211 | 768 | 1.149 | 136 | Sí | +2 (10 → 12) |
| WI24 (primera reunión real) | #23 | 6,2 min | 136 | 381 | 1.019 | 99 | Sí | +10 (12 → 22), incluye el uso de la aplicación |
| WI23 (lista de campos) | #24 | 12,8 min | 192 | 598 | 1.035 | 70 | Sí | +5 (22 → 27) |
| WI25 (R04) | #25 | 11,2 min | 251 | 596 | 1.142 | 182 | Sí | +3 (27 → 30) |
| WI26 (R06) | #26 | 11,2 min | 24 | 178 | 1.066 | 41 | Sí | +3 (30 → 33) |
| WI27 (segunda reunión real) | #27 | 9,5 min | 41 | no medido | 1.132 | no medido | Sí | no medido |

[`metrics.yaml`, `pilot_d1_steps`, pasos 2 a 8 y 11. Los cambios más chicos en producto: WI21 (10 líneas, casi todo
borrar código), WI26 (24) y WI27 (41). La proporción control/producto va de 1,77 (WI20) a 95,7 (WI21) y 27,61 (WI27).]

**Tanda 2 (WI28 a WI31): ninguno integrado, así que no hay tiempos "abierto → integrado" ni medición de PR.** Sí hay, de
las ramas: pruebas con los kits en clon limpio, 663 (WI28), 656 (WI29), 665 (WI30, sobre un commit anterior a la última
decisión; se está rehaciendo) y 654 (WI31), todas OK, y mutaciones detectadas 11, 9, 9 y 13
[`docs/evidence/<id>/local-test-run.txt` y `mutations.txt` de cada rama]. La sesión de esta tanda (`medir_sesiones.py`):
no medida; queda para el cierre [`metrics.yaml`, paso 11].

Tamaño del pedido que ya se sabe: WI29, WI30 y WI31 los pidió el owner "de noche, sin ver cada contrato" (2026-10-07)
[`contract.yaml` de cada uno], lo que hace que su "mensajes del owner" sea bajo pero no comparable.

---

## 6. Qué le pediría a INGOL que haga distinto

Ordenado por impacto.

1. **Que el registro de revisión independiente no dependa de un bloque de PowerShell pegado a mano por cada work item.**
   Problema concreto: hoy los PR #28, #29, #30 y #19 están en rojo por TP-08, y no hay forma de integrarlos sin una
   acción del owner por trabajo (punto 2.1). Pedido: un comando de INGOL que, dado el veredicto del buzón, deje el
   registro atado al digest del contrato y pida al owner **una** confirmación, o que el owner pueda firmar varios a la
   vez.
2. **Que las pruebas del paquete del piloto puedan correr en la CI y sean más baratas.** Problema: tres archivos se
   saltean en GitHub, y con los kits la suite tarda unos 40 minutos y se queda sin memoria si se corre con otras cosas
   (punto 2.6). Pedido: una versión de los kits que se pueda instalar en la CI (aunque sea con las pruebas rápidas), y
   que AR05/AR10 acepten un tiempo de espera configurable del candado.
3. **Que el buzón guarde todo lo que produce un revisor y no pierda una entrega por la cuota.** Problema: el informe
   completo de WI23 se perdió, el revisor de WI29 no pudo escribir evidencia, y el juez gastó 19 minutos y 215.075 tokens
   sin entrega (punto 2.8). Pedido: guardar el mensaje completo y los archivos escritos, y un reintento automático o un
   resultado parcial marcado cuando la cuota corta.
4. **Que `ingol init` sirva para un proyecto existente y escriba `.gitignore` y `.gitattributes`.** Problema: H1, H4 y
   H6 siguen abiertos; con `autocrlf=true` `doctor` marca 27 de 29 superficies bloqueadas.
5. **Un lugar y un corredor estándar para los hallazgos y las mutaciones.** Problema: el proyecto no tiene
   `docs/hallazgos/registro.yaml`, así que el tablero no ve los hallazgos de las revisiones (punto 2.11); y cada
   proyecto reescribe su guion de mutaciones, con el mismo error de contar un proceso caído como detección (punto 4).
   Pedido: un corredor de mutaciones en los kits que distinga "las pruebas fallaron" de "el proceso murió", y una
   plantilla del registro de hallazgos que se genere con el contrato.

---

*Fuentes leídas para este informe: `metrics.yaml` y la copia del juez (carpeta de datos del owner); `docs/limitations/REGISTER.md`;
los `contract.yaml` y `independent-review.md` de cada work item (en `main` o en su rama); `gh pr list`, `gh pr checks` y
`gh run view` del 2026-10-08; el código de `origin/main` en las líneas que se citan. Archivos de INGOL leídos en sólo
lectura: `docs/method/firma_pendiente.md` y `docs/method/ACTIVE_CONTROLS.md`.*
