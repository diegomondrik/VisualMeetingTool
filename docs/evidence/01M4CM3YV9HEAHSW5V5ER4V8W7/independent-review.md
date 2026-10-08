# Revisión independiente de WI31 (01M4CM3YV9HEAHSW5V5ER4V8W7)

Revisor independiente por el buzón de INGOL (rol `revisor-independiente`, sin herramientas de escritura): el texto es el que devolvió, copiado por el implementador. Al final, lo que se hizo con cada hallazgo.

## Revisión independiente, 2026-10-08 (commit b46498b): aprobar con correcciones

## Revisión independiente: WI31 de VisualMeetingTool (b46498b contra main 1a78ce4)

**Veredicto: aprobar con correcciones.** Hay que cambiar una frase de la guía antes de abrir el PR. El resto está sustentado.

### Qué leí
El contrato y el plan, `git diff 1a78ce4 b46498b` completo y `docs/MAINTAINING.md` línea por línea contra el código: `jobs.py`, `server.py`, `store.py`, `disk.py`, `company.py`, `extract.py`, `writer.py`, `qa.py`, `pages.py`, `texts/__init__.py`, `app.js`, las pruebas `test_d1_*`, `test_texts`, `test_summary` y `test_qa`, y los dos workflows. Del instalador leí sólo `packaging/requirements-build.txt`, `requirements-build.in` y `build.py`, con `git show` sobre la rama de WI18. No leí historial.

### Qué ejecuté y qué salió
- **`python -m unittest tests.test_pinned_versions -v`:** 14 pruebas, todas OK.
- **`check_guide.py`:** "every name the guide looks up exists" (134 de 175 nombres; termina con código 0).
- **`mutations.py` en una carpeta nueva:** detectó las 12 mutaciones y el control sin mutar dio OK. Lo corrí sobre el commit b46498b y coincide con `mutations.txt`, que se había grabado en daf9b74. Entre los dos commits sólo se agregó evidencia.
- **`reproduce.py WI31-P3-1`:** MATCH, la limitación sigue abierta.
- **Pins contra el instalador:** las seis versiones de `constraints.txt` son las mismas de `requirements-build.txt` en la rama de WI18. Lo comprobé, no lo tomé del informe.
- **`discover -p "test_d1_*"` sin los kits** (`ingol_kits` no se puede importar): **corrieron 8 pruebas, se saltearon 3 y pasaron 5.**
- **Formas de pin que la prueba podría no ver:** armé casos en un script aparte que usa la función `problems()` de la prueba (resultados en P2-1).
- No corrí la suite entera: el pedido la da por pasada (639 pruebas).

### Hallazgos

**P1-1 — `docs/MAINTAINING.md:134-136`: la guía dice algo falso sobre las pruebas automáticas.** Lo ejecuté.
- La guía dice que sin los kits los `tests/test_d1_*.py` "skip, so the CI never runs them".
- En realidad sólo tres de los seis archivos se saltean sin los kits: `test_d1_barrido`, `test_d1_hallazgos_arquitecto` y `test_d1_wi20_fallas`.
- Los otros tres no importan `ingol_kits`, así que corren en la CI: `test_d1_final_de_la_reunion`, `test_d1_r02_plantilla` y `test_d1_r04_resumen`, con 5 pruebas en total.
- **Consecuencia:** WI31-AC02 ("nothing in it contradicts the code") no se cumple, y la guía repite justo el tipo de error que R11 manda corregir. Un mantenedor creería que la CI no cubre ninguna reproducción de la revisión externa, cuando cubre 5.
- El mismo texto ya estaba en `README.md:278-282` antes de este cambio, pero el README está dentro del alcance del contrato.
- **Arreglo mínimo:** en los dos lugares, decir que los que usan `ingol_kits` se saltean sin ellos y que los demás corren en la CI.

**P2-1 — `tests/test_pinned_versions.py:30` y `requirements()`: un pin con marcador de entorno pasa la prueba.** Lo ejecuté.
- `numpy==2.5.3; python_version < "3"` y `numpy==2.5.3;sys_platform=="linux"` dan cero problemas: la expresión regular corta en el `;` y descarta el marcador.
- Hasta donde sé, pip ignora una restricción cuyo marcador no aplica. En Windows con 3.12, numpy quedaría sin fijar y la prueba seguiría verde. Esto último lo sé por cómo funciona pip, no lo ejecuté (necesita red).
- El `pip list` del log sí lo mostraría. No lo hago bloqueante porque nadie escribió un pin así.
- **Arreglo:** que `problems()` rechace cualquier resto después de la versión, o cualquier `;`.

**P3 (limitaciones conocidas, no reabren el ciclo):**
1. **`test_pinned_versions.py:162-165`: el control de "un solo paso de instalación" se puede esquivar.** Busca el texto literal `"pip install"`, así que un paso con `pip3 install X` o con `pip  install` (doble espacio) no cuenta. Lo leí, no lo ejecuté.
2. **`BROUGHT` está escrito a mano** (`:28`). Si una versión futura trae una dependencia transitiva nueva, queda sin pin y ninguna prueba avisa; sólo lo mostraría `pip list`.
3. **El instalador y `constraints.txt` no están atados por un mecanismo.** `test_the_pins_are_the_ones_of_the_installer` repite los mismos seis valores a mano, y el propio candidato puede cambiar las dos cosas juntas. Es inevitable mientras WI18 no esté integrado, y la guía lo dice (`:144-150`).
4. **La versión de Python no está fijada del lado del instalador.** La CI corre en 3.12, pero `build.py` de WI18 sólo imprime la versión de Python, no la exige. Así que la combinación probada no es idéntica del todo a la empaquetada. Lo leí.
5. **`check_guide.py` sólo mira nombres entre comillas invertidas,** y para un nombre de archivo suelto le alcanza con encontrarlo en el código. Es así por diseño y está declarado.

**Mecanismo más simple:** no encontré uno claramente mejor. Instalar con `pip install -r constraints.txt` evitaría repetir la lista de bibliotecas en el workflow, pero se perdería que pip mismo verifique que cada pin cumple el mínimo de `pyproject.toml`. La forma actual es razonable.

**Revisé la guía contra el código y coincide** en el flujo de cuatro etapas y su orden en `Runner._run`, el tope de gasto compartido, las subidas y sus nombres, el SVG rechazado y los metadatos borrados, `refusal` (incluido el cuerpo JSON), la carpeta de datos y su ubicación, la escritura con `.partial` y `fsync`, el lock, la recuperación de un corte (`_settle_failure`, `request_fingerprint`, `discard_kept` nunca durante una corrida, `clear_leftovers` antes de levantar el servidor), las subórdenes de cada comando y todo lo de agregar un idioma, incluida la frase "no test checks qa.LABELS…". **Lo único falso es P1-1.**

### Criterios
- **WI31-AC01 — se cumple en lo que se puede verificar acá.**
  - Pins = WI18: verificado.
  - La CI instala con `-c constraints.txt`: verificado.
  - La prueba falla si falta un pin, si es un rango o si queda por debajo del mínimo: verificado por las mutaciones.
  - Queda pendiente que el log de la CI muestre las versiones: hace falta el PR.
  - El hueco del marcador es P2-1.
- **WI31-AC02 — no se cumple.** El README ya no dice que la suite no corre en GitHub, la guía tiene las cinco partes y los nombres existen, pero la guía contradice el código en P1-1.
- **WI31-AC03 — se cumple en lo que toca a esta revisión.** Mutaciones 12/12 reproducidas, limitación reproducida (MATCH), `changed-tests.md` correcto (sólo se agregó un archivo de pruebas). Quedan pendientes, a propósito: la corrida en un clon limpio con los kits, la CI del PR y este informe como `independent-review.md`.

### Contexto
No me faltó contexto para revisar. En la carpeta descartable sólo quedó `tests/__pycache__` de mis corridas, y está ignorado por git.

**Veredicto: aprobar con correcciones.** Hace falta corregir P1-1 (una frase en la guía y la misma en el README). P2-1 conviene arreglarlo si es barato; si no, va al registro de limitaciones.

Sigue el agente constructor: corrige P1-1, decide qué hace con P2-1 y después hace la corrida en el clon limpio y abre el PR.

## Lo que se hizo con cada hallazgo

- P1-1 (la guía y el README decían que todos los test_d1 se saltean sin los kits; son tres de seis): corregido en cf8e2d6, en los dos lugares.
- P2-1 (un pin con marcador de entorno pasaba la prueba): corregido en cf8e2d6; prueba y mutación nuevas.
- P3-1 (el paso de instalación se buscaba con el texto literal `pip install`): corregido en cf8e2d6 (también `pip3` y `pip.exe`).
- P3-2 a P3-5 (la lista de lo que traen las bibliotecas está escrita a mano; pins e instalador atados por una prueba que repite los valores; Python no exigido por el instalador; la guía se comprueba por nombres): límites conocidos, dichos en `changed-tests.md`.
