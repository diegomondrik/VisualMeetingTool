# Revisión independiente de la versión 2.0.0 (01M7B76KPE7XJMKQ2820C15Z9H)

Revisor: un agente de contexto limpio y solo lectura (Claude Opus 5.5, rol `revisor-criterio`), lanzado desde la
sesión del implementador; no construyó el cambio. Hizo dos pasadas el 2026-11-16: la revisión completa de
`git diff main...HEAD` y, después de las correcciones, una verificación de cada una. Veredicto final: **aprobar con
condiciones**: ningún hallazgo de código o documentos abierto; las condiciones eran el instalador (AC10) y que la
evidencia de la suite nombrara un commit publicado. Las dos están cumplidas (`installer-build.txt`,
`local-test-run.txt`).

Alcance: contrato, plan, propuesta (con la enmienda 1), toda la evidencia, el código de proveedores, resumen,
lectura, aplicación, textos, manual y guía de mantenimiento; pruebas propias de los archivos tocados (334 pruebas,
todas OK) y dos sondas propias contra servidores falsos, sin red. No llamó a ninguna API ni instaló el .exe.

## Hallazgos y qué se hizo

| Prioridad | Hallazgo | Qué se hizo |
|---|---|---|
| P1 | Archivos del repositorio (público) citaban la reunión real usada como caso de prueba: frases con su minuto en la propuesta, líneas de prueba copiadas de la transcripción, cifras de la demo vista en esa reunión y notas de prueba con la forma de las reales. | Por decisión del owner, todo reemplazado por datos inventados o descripciones neutras; historia rehecha en commits limpios desde `main` (ver `history.md`); el PR #37 de la propuesta, cerrado y su rama borrada. La verificación buscó cada cita, minuto y hecho en el árbol y en cada commit nuevo: ninguno queda. Lo que GitHub guarda del PR #37 cerrado solo lo puede purgar su soporte (decisión del owner). |
| P2 | Una respuesta pagada que se aceptó en el reintento se volvía a revisar como primera respuesta al reprocesar, se rechazaba por elogio y se pagaba de nuevo. | Las respuestas guardadas se revisan sin el rechazo por elogio (`check_kept`); lo que elogien se marca igual. Prueba nueva: cero pedidos al reprocesar. |
| P2 | El rechazo por "vender" corría en todos los tipos de reunión y tomaba palabras comunes ("la prueba que hicieron", "favorable"). | Solo en preventa; patrones más angostos. Pruebas nuevas con frases neutras y con las que sí venden. |
| P2 | El manual decía que las notas van a Gemini; van al proveedor del modelo del resumen. | Corregido. |
| P2 | No se reintentaba el 529 de Anthropic (sobrecarga) ni 502/504. | Se reintentan. Prueba nueva. |
| P3 | Textos y docstring que nombraban a Gemini cuando responde otro proveedor; mínimos del techo del manual que cambian el 2027-01-01; el campo del techo "empieza en 1"; tres líneas mal cortadas. | Corregidos. |

Quedan abiertos a propósito (el revisor dijo que no bloquean): el nombre de quien tomó las notas va en la parte de
instrucciones del pedido (lo escribe el propio usuario, hasta 80 caracteres, sin marcas); no hay prueba de notas de
más de 20 MB (vale el límite general de subida); el aviso de la plantilla solo mira el texto después de un salto
de página; el mensaje de rechazo del proveedor no dice cuál de las claves falló.

El instalador se compiló desde cfe71d6 (SHA-256 en `installer-build.txt`), después de todas las correcciones.
