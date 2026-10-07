# Revisión independiente de WI23 (01M48RAZZ5MGGHYTJNYR2VQP0Z) y su verificación

Por el buzón de INGOL: motor Claude, rol `revisor-independiente` (sin
herramientas de escritura), cuenta empresa, modelo pedido por rol
(`rol:criterio`, resuelto a `opus`), esfuerzo alto. El texto de cada una es
su respuesta tal como llegó; el implementador sólo bajó un nivel sus títulos.

## La revisión de 6e33e4c (2026-10-07, 00:31 a 01:03)

El buzón guarda el último mensaje del revisor. Ese mensaje remite a un
informe anterior de la misma corrida que no quedó guardado: de la revisión
sólo se conserva su conclusión, que es esta.

Esas dos notificaciones son sólo los bucles de espera de las mutaciones, que terminaron. Los resultados (13 de 13 detectadas y la corrida sin mutar en verde) ya están en el reporte anterior, así que no cambia nada.

El veredicto se mantiene: **aprobar con correcciones**. Antes de abrir el PR hay que registrar o arreglar el P1: con Markup Compatibility un campo `INCLUDEPICTURE` hacia una ruta de red pasa los dos controles y llega al informe del cliente.

Lo próximo le toca al owner: decidir si ese P1 se arregla dentro de WI23 o se registra como limitación abierta y va a un work item propio.

## La verificación de la corrección, 13b60ad (2026-10-07, 02:48 a 03:00)

## Verificación de la corrección de WI23 (6e33e4c → 13b60ad), VisualMeetingTool

**Veredicto: NO LISTO.** El caso del P1 original quedó cerrado, pero la corrección abrió otro camino de la misma clase, y es un P1 nuevo.

### Qué leí
- `git diff 6e33e4c 13b60ad` de `document.py`, `en.py`/`es.py`, `README.md` y `REGISTER.md`.
- `tests/test_markup_compatibility.py` entero.
- Los helpers que ese archivo usa de `test_template_filter`, `test_allowed_fields` y `test_report`.

No leí `mutations.py`/`.txt`, `changed-tests.md` ni el contrato: no hacían falta para estos cuatro puntos.

### Qué ejecuté (todo dentro de la carpeta temporal de borradores; no modifiqué el clon)
- **Pruebas pedidas:** `python -m unittest tests.test_markup_compatibility tests.test_allowed_fields tests.test_template_filter tests.test_report`: **181 pruebas, OK**.
- **Suite completa:** `python -m unittest discover -s tests`: **548 pruebas, OK (3 omitidas)**, 606 s.
- **Sondas propias:** plantillas sintéticas con host `example.invalid` / `inventado.invalid`. Cada una pasó por `active_content`, `set_template`, la construcción del informe y `check_active_content`.
- **Filtro viejo contra el nuevo:** corrí `document.py` de 6e33e4c (sacado con `git show`) y el actual sobre los mismos paquetes.
- **Plantillas reales de Word:** las 23 `.dotx` que trae Office instalado (`C:\Program Files\Microsoft Office\root\Templates\*`). Suman 355 partes con Markup Compatibility y unos 800 `mc:AlternateContent`.

### Punto 1: el caso del P1 se rechaza en las dos etapas → **confirmado, con una excepción grave (ver P1 nuevo)**
- **Caso original** (Choice con `PAGE`, Fallback con `ADDIN`, dentro de un mismo campo): 6e33e4c lo aceptaba y 13b60ad lo rechaza como `a ADDIN field`. Lo ejecuté.
- **Variantes que se rechazan en `set_template` y en la última revisión del informe** (ejecutadas, por las 14 pruebas de la suite más mis sondas):
  - ramas invertidas;
  - Choice sin Fallback con la instrucción afuera;
  - anidadas;
  - en una tabla;
  - en un elemento ignorable;
  - con ProcessContent;
  - con Ignorable declarado debajo de la raíz;
  - en el encabezado (`word/header1.xml`).

### Punto 2: lo legítimo no se rechaza → **confirmado**
- **Informe propio, plantilla de ejemplo y AlternateContent sin campos:** aceptados y el informe se construye (`LegitimateTest`, ejecutado).
- **Plantillas de Office:** ninguna de las 23 recibe un rechazo por Markup Compatibility. El filtro nuevo no rechaza nada que el viejo no rechazara: 15 de 23 aceptadas por los dos. Las otras 8 las rechazan los dos filtros por campos fuera de la lista; es `WI23-P3-1`, por diseño. Lo ejecuté.

### Punto 3: lo "incierto" no abarca lo que escriben Word o python-docx → **confirmado en lo medido**
- Las 23 plantillas guardadas por Word y la plantilla de python-docx (que trae `mc:Ignorable`) pasan sin ningún mensaje `compat_*`. Lo ejecuté.
- **Lo que no pude probar:** documentos de Word con gráficos o SmartArt (`c14`, `dgm14`), ni documentos guardados en formato Strict. Ninguna de las plantillas tenía eso. No tengo motivo concreto para esperar un rechazo, pero no está probado.

### Punto 4: hallazgos

**P1 (nuevo, lo introduce la corrección): un `fldChar begin` dentro de una rama deja la instrucción del campo como "texto suelto", y del texto suelto sólo se juzga la primera palabra.**
- **Dónde:** `meetingtool/report/document.py`
  - **L297:** al cerrar una rama, `_finish` cierra el campo abierto sin instrucción y no lo juzga.
  - **L324 y L269–273:** la instrucción que sigue afuera cae en `loose`, y todo el texto suelto de la parte se junta y se juzga como un solo campo.
  - **L411:** ahí se juzga sólo la primera palabra de ese texto.
- **Cómo se arma:** se escriben dos campos así, `<w:r><mc:AlternateContent><mc:Choice Requires="w14"><w:fldChar begin/></mc:Choice></mc:AlternateContent></w:r>` + instrucción + separate + end. El primero dice ` PAGE ` y el segundo ` INCLUDETEXT "http://example.invalid/x" `.
  - El filtro junta el texto suelto: `PAGE  INCLUDETEXT …` → nombre `PAGE` → aceptado.
  - Word preprocesa la rama: `begin` + `INCLUDETEXT …` → campo `INCLUDETEXT`.
- **Lo ejecuté.** Con este armado se aceptan en `set_template`, el informe se construye y **pasa `check_active_content`**, con el campo adentro del informe:
  - `INCLUDETEXT`;
  - `ADDIN`;
  - `INCLUDEPICTURE`;
  - `HYPERLINK` a `file://`;
  - la misma variante con el `begin` en un elemento ignorable con `mc:ProcessContent`.
- **6e33e4c rechazaba exactamente este paquete** (`a INCLUDETEXT field`). Es una regresión de la corrección.
- **Consecuencia:** una plantilla con un campo fuera de la lista, que trae contenido de afuera, pasa los dos controles y llega al informe del cliente. Es lo mismo que el P1 original.
- **Incertidumbre:** no abrí Word. Que Word lea un `fldChar` dentro de `mc:Choice` y lo continúe afuera sale de la semántica de Markup Compatibility (la rama elegida reemplaza al `AlternateContent`), no de una prueba en Word.
- **Arreglo más simple que conserva la garantía:**
  - rechazar, como `compat_structure`, una rama o un elemento ignorable que termina con un campo abierto, o que tiene un `separate`/`end` sin su `begin`;
  - o, alternativamente, juzgar cada pieza de texto suelto por separado y no sólo la primera palabra del total.

**P3 (limitación; no reabre el ciclo):** con `mc:ProcessContent`, Word lee el contenido del elemento como si estuviera en el padre, pero el filtro lo trata como un contexto aparte (L301–303). Hoy eso sólo lleva a rechazar de más; el agujero real de ese camino es el P1 de arriba.

Sin otros hallazgos.

### El P1 está cerrado: **no**
El caso original sí quedó cerrado, pero la corrección abrió un bypass equivalente: un `begin` dentro de una rama más la instrucción afuera. Tiene que agregarse a `HiddenFieldTest` antes de integrar.

---
Aparte: varios conectores de claude.ai (GitHub, Gmail, Drive y otros) necesitan autorización desde la configuración de conectores de claude.ai. No se usaron en esta revisión.

**Qué sigue:** el implementador corrige el P1 (ver arreglo propuesto) y vuelve a pedir esta verificación. El owner no tiene que decidir nada.

## Lo que se hizo

| Hallazgo | Qué se hizo |
|---|---|
| Revisión de 6e33e4c, P1: un campo fuera de la lista, escondido con Markup Compatibility, pasaba los dos controles | Corregido en la única pasada de corrección (`8271896`, `e4b72ac`, `13b60ad`): cada rama de mc:AlternateContent y cada elemento ignorable se juzga por separado, y lo que no se puede leer con certeza se rechaza nombrando la parte |
| Verificación de 13b60ad, P1: la corrección dejó un camino equivalente (un `begin` dentro de una rama, la instrucción afuera) | Aceptado por el owner el 2026-10-07 como riesgo bajo, sin otra pasada (el único Word de afuera es la plantilla de su propia empresa, que carga él; no está comprobado en Word; Word no actualiza esos campos al abrir). Registrado como `WI23-P3-3`, con reproducción (`3645d1f`) |
| Verificación, P3: mc:ProcessContent se trata como contexto aparte | Sin cambio: hoy sólo lleva a rechazar de más |

La suite completa con los kits de INGOL corrió en un clon limpio de `13b60ad`
(`local-test-run.txt`: 558 OK). De `13b60ad` a lo integrado sólo cambian el
registro de limitaciones, su reproducción y esta evidencia.
