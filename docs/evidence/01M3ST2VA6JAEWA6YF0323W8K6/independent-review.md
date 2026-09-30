# Revisión independiente de WI16 (01M3ST2VA6JAEWA6YF0323W8K6), commit d0cce57 contra main f365587

Subagente `revisor-independiente`, 2026-09-30. Su rol no tiene herramientas de
escritura: el texto lo transcribió el implementador tal como lo devolvió.

**Veredicto: NO LISTO.** Hay un defecto de un solo origen: el punto donde
empieza el informe se mide antes de reescribir el índice. Por eso el control de
completitud falla en los dos sentidos: rechaza informes buenos, y en un caso deja
pasar un campo sin llenar. El arreglo es de pocas líneas. Lo demás está bien
hecho.

## Qué leí

- El contrato WI16 (AC01 a AC11) y la sección WI16 de la propuesta de D-188.
- El diff completo de `meetingtool/report/{layout,document,__main__}.py`,
  `meetingtool/app/{jobs,pages,server}.py`, `tests/test_app.py`, las pruebas
  nuevas de `tests/test_report.py`, el README y `mutations.py`.
- La autorización de `server.py` (refusal, _segments, _put) y `app.js`
  (templateForm).
- No leí `plan.yaml` ni el contrato de WI11.

## Qué ejecuté

Todo en un clon con `--no-hardlinks` de d0cce57 bajo `%TEMP%`, ya borrado. El
repositorio original no se tocó.

- **Suite completa:** `python -m unittest discover -s tests`, 324 pruebas OK en
  198 s.
- **Pruebas previas:** `git diff f365587 d0cce57 -- tests/`. La única aserción
  existente que cambia es la de Ajustes (`empresa.docx`), como declara AC11. Las
  otras dos líneas quitadas son imports. `git diff --check` sale limpio.
- **Sondas propias** contra `build_report`, con plantillas armadas en el momento:
  índice largo, dos índices, texto antes del campo, índice de figuras, salto de
  sección, índice de una línea, índice vacío, y campos partidos con tabulación,
  hipervínculo, cuadro de texto Choice/Fallback, `{informe}` partido y `w:br`.
- **11 mutaciones propias** sobre `tests.test_report`.
- **Inspección del XML generado:** orden de hijos de `w:p`, fldChar, marcadores y
  relaciones externas.
- **Word no lo abrí.** Lo de Word (Office 16) queda tal como lo afirma el
  implementador, sin comprobar.

## P1

**P1-1: `start` queda viejo después de `fill_toc`.**

- Dónde: `meetingtool/report/document.py:527` (se calcula `start`), `:578`
  (`fill_toc` después cambia cuántos párrafos tiene la portada) y `:586`
  (`check_report` usa el `start` viejo en `:449` y `:460`).
- Si el índice guardado tenía k párrafos y el nuevo tiene n, en el documento
  final todo el límite portada/informe se corre n−k posiciones.
- Pasa sólo con un índice que no está dentro de un control de contenido. El
  contrato lo cubre explícitamente ("plain or inside a content control").

Casos ejecutados:

1. **El índice se achica y se rechaza un informe bueno.** Índice común con 12 o
   más renglones guardados y una reunión de 9 secciones: `ReportError: the Word
   document is missing the section(s) [...las 9...]`. Con 3, 10 u 11 renglones
   construye bien. Con el mismo índice de 20 renglones dentro de un control de
   contenido, también construye bien. Consecuencia: una plantilla que Ajustes
   aceptó ("Tiene índice") después rechaza cada informe con un mensaje falso de
   que faltan todas las secciones.
2. **Dos índices comunes: siempre se rechaza.** El primero crece y el segundo
   queda fuera de `children[:start]`, así que la comparación de `contents` falla.
   Consecuencia: una plantilla con dos índices no sirve nunca.
3. **El índice crece y el control de campos falla abierto (AC03).** Plantilla:
   portada, índice común de 1 renglón, "Cliente: {cliente}", `{informe}`. Con
   `fill_fields` anulado, el Word **se entrega con `{cliente}` sin llenar**.
   Consecuencia: el control "un campo sin llenar no se entrega" no puede fallar
   en esa forma de plantilla.

Por qué no lo agarraron las pruebas: las de AC06 calculan `start` sobre el
informe ya guardado (`start_of`), no con el `start` que usa `build_report`. Y
`owner_shaped` tiene 3 renglones contra 9 secciones: crece, y en ese sentido el
control de secciones igual acierta por el orden de búsqueda.

Arreglo más simple: guardar una referencia al primer elemento del informe y tomar
`start` como su índice en el cuerpo después de `fill_toc`. Hacen falta pruebas
con un índice largo, dos índices, y un campo después del índice con `{informe}`.

## P2 (no reabren el ciclo)

- **P2-1: se pierde el salto de sección de la portada.** `layout.py:151`, `:177`
  y `:184` (con `start_kind=index`, el párrafo vacío que lleva el `w:sectPr`
  después del índice se descarta como "modelo") y `layout.py:342-363` (el `pPr`
  del párrafo final del índice, que puede llevar ese `sectPr`, no se conserva).
  Una plantilla con 2 secciones da un informe con 1. Consecuencia: si la
  plantilla tiene la portada en su propia sección, la portada sale con el
  encabezado, pie y página de la sección del cuerpo.
- **P2-2: la verificación del índice compara contra lo que el mismo `fill_toc`
  dice haber escrito**, no contra `expected` filtrado por niveles. Verifica que
  lo escrito sobrevive al guardado, no que el índice liste "exactamente las
  secciones". No encontré un caso concreto que diverja.
- **P2-3: texto antes del campo en el mismo párrafo** (por ejemplo "Índice: " +
  campo TOC). Se acepta al cargar y rechaza cada informe, porque `toc_entries`
  suma ese texto a la primera entrada. Seguro, pero el rechazo llega al
  construir.

## P3

- `layout.py:337` y el `LayoutError` de `fill_toc` no son `ReportError`: con el
  `begin` del TOC dentro de `w:ins`, `w:hyperlink` o un sdt en línea, al
  construir `__main__` muestra un traceback en vez de "error:".
- Un índice cuyo resultado no tiene texto y es lo único en la hoja se acepta al
  cargar, pero el informe falla con `AttributeError`: `_clear_body` quita el
  índice y después `fill_toc` opera sobre elementos sueltos.
- Un índice de figuras (`\c`) queda con su contenido viejo y no marca el inicio
  del modelo. Coherente con el contrato, pero es contenido viejo entregado.
- `{cli<tab>ente}` se trata como campo y queda "ACME\t". El campo dentro del
  resultado de un campo de Word se llena, pero el `instrText` conserva
  `{cliente}`, así que Word lo restauraría al actualizar. Ninguno es realista.
- Hueco de pruebas: no se detectan las mutaciones que hacen que
  `leftover_fields` ignore encabezados y pies, que los ids de marcador empiecen
  en 0, que se descarten los runs `before` o `after` del índice, ni la de
  "campo no anidado".
- `pages._day` da 500 si `report-template.json` fue editado a mano con `name`
  válido y `set_utc` inválido.

## Lo que comprobé y está bien

- **Llenado de campos partidos** (ejecutado): `{`, `cli`, `ente}` con formatos
  distintos; campo a caballo de un `w:hyperlink`; cuadro de texto duplicado en
  `mc:Choice` y `mc:Fallback` (las dos copias quedan "ACME"); `w:br` después del
  campo; `{informe}` partido. Las llaves dentro de `instrText` no se tocan.
- **XML del índice** (inspeccionado): primer párrafo `pPr, r(begin), r(instr),
  r(separate), hyperlink`; último `pPr, hyperlink, r(end)`; fldChar balanceados;
  marcadores `pPr, bookmarkStart, r, bookmarkEnd` con ids `max+1`; hipervínculos
  sólo con `w:anchor`; sin `TargetMode="External"`; índice de una línea bien; se
  quitan `w:dirty` y `w:updateFields`.
- **Seguridad** (leído y cubierto por pruebas): el nombre se guarda como
  `Path(name).name[:200]` y se muestra con `e()`; `/plantilla-de-ejemplo.docx`
  pasa por `refusal()`; la plantilla de ejemplo se genera en memoria, sin
  relaciones externas; las plantillas siguen pasando por los controles de WI11 y
  ahora también por `read_layout`.
- **Compatibilidad** (ejecutado): las pruebas de WI11 pasan sin cambios; una
  plantilla sin campos ni índice da `start=None` y todo es portada.

## Limitaciones de esta revisión

- No abrí el informe en Word ni vi la plantilla real del owner.
- No corrí `mutations.py` completo.
- La salida de la suite para AC11 todavía no está commiteada.

---

# Re-verificación, commit 24de6a7 (correcciones sobre d0cce57)

Mismo subagente. Transcripta por el implementador.

**Veredicto: NO LISTO.** Los arreglos de la revisión anterior funcionan: P1-1,
P2-2, P2-3 y los P3, y P2-1 en los dos casos de dos secciones pedidos. Pero la
corrección de P2-1 abre un P1 nuevo.

## Qué ejecutó

Clon descartable de 24de6a7 con `--no-hardlinks`, borrado. Suite completa: 333
pruebas OK en 184 s. Sondas anteriores repetidas:

| Sonda | d0cce57 | 24de6a7 |
|---|---|---|
| Índice común de 12 renglones | rechazado ("faltan las 9 secciones") | OK, 9 entradas |
| Índice común de 20 renglones | rechazado | OK, 9 entradas |
| Dos índices comunes | rechazado | OK, 18 entradas (9 + 9) |
| Índice de 1 renglón + `{cliente}` + `{informe}`, con `fill_fields` anulado | **entregado con `{cliente}`** | rechazado |
| P2-1 variante 1: salto de sección después del índice | 2 secciones → 1 | 2 → 2 |
| P2-1 variante 2: salto de sección en el último renglón del índice | 2 → 1 | 2 → 2 |
| P2-3: "Índice: " antes del campo | rechazado | OK, 9 entradas |

Sondas nuevas: portada como sección propia con datos en su pie (dos variantes),
y tres secciones (portada | índice | modelo).

## P1

**P1-A (lo introduce la corrección de P2-1): el pie o encabezado propio de la
portada queda sin llenar y el informe se rechaza siempre.** `build_report` corre
`drop_model` (que separa el `sectPr` de la portada) antes de `fill_fields`, y lo
vuelve a enganchar recién después: mientras está separado, `fill_fields` no ve
esa sección. Caso: portada, índice, salto de sección en el párrafo siguiente;
pie de la sección 1 "Portada {fecha}" → `ReportError: ... still has {fecha}
unfilled`. Consecuencia: una plantilla así se acepta en Ajustes y rechaza cada
informe. Arreglo: volver a enganchar el `sectPr` antes de llenar.

## P2

- **P2-A: con tres o más secciones se pierde la sección del índice.** La regla
  correcta: el primer `sectPr` descartado cierra la última sección guardada,
  salvo que el último elemento guardado ya lleve su propio salto.
- **P2-B: probable página en blanco cuando la portada termina en un salto de
  sección** (salto de sección y además salto de página). No verificado en Word.

## P3

- `toc_entries` lee sólo hipervínculos: debilitamiento teórico, sin caso.
- Un salto de sección "continuo" conservado dejaría el informe en la misma hoja
  que la portada. No probado.

## Lo que comprobó y está bien

P1-1 (`first` es siempre el párrafo del título, en todas las sondas quedó en
`start`), P2-2 (lista esperada desde las líneas `#` del resumen con la misma
fórmula de nivel), P2-3 y P3.

## Qué hizo el implementador (commit siguiente)

- P1-A y P2-A: `drop_model` deja el primer salto descartado en una línea vacía
  al final de lo guardado, antes de llenar los datos, salvo que lo guardado ya
  termine en un salto.
- P2-B y el P3 del salto continuo: el salto de página después de la portada se
  agrega sólo si la portada no termina en un salto de sección de página nueva.
- Pruebas: portada en sección propia con un dato en el pie (dos variantes), tres
  secciones, salto continuo; las cuatro fallan sobre 24de6a7. Tres mutaciones
  nuevas.
