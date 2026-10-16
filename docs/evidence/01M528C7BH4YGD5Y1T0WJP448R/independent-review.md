# Revisión independiente de la versión 1.0.0 (01M528C7BH4YGD5Y1T0WJP448R)

Revisor: un agente de contexto limpio y solo lectura, lanzado desde la sesión del implementador (el buzón de INGOL no estaba disponible en esta máquina). Revisó el commit 625dba2. Veredicto: **aprobar con correcciones**, sin P0. El implementador comprobó por su cuenta el hallazgo P2 de "one" (`words_numbers` devolvía `{1}` para "no one knows") antes de corregirlo.

Alcance: contrato, plan, `git diff 257787b HEAD` completo del código, la evidencia, y pruebas propias (`tests.test_qa`, `tests.test_verificar_rojo`, `tests.test_nombre_docx`, `tests.test_packaging`, `tests.test_user_manual`: todas pasaron). No instaló el .exe.

## Hallazgos y qué se hizo (commit 9af4c17)

| Prioridad | Hallazgo | Qué se hizo |
|---|---|---|
| P1 | El manual decía que toda cifra no dicha en dígitos sale en rojo y que la marca lleva "las palabras dichas". Falso: las cifras dichas en palabras en inglés se aceptan sin marca, y si la cita no está en la transcripción la marca lleva lo que escribió Gemini. | Manual corregido (sección de resultados). |
| P2 | Un "one" suelto ("no one", "one of the issues") y ordinales como "a 3rd party" o "a 5th of July" contaban como cifra dicha. | `words_numbers` solo cuenta "one" con "and a half", "percent", "million", "thousand" o "hundred"; `fractions` solo acepta "th", denominador desde 4, y no un día de mes. Pruebas nuevas en `DatesTest`. |
| P2 | El campo `measures` no se revisaba: un "99 %" inventado quedaba sin marca. | `_figure` mete dentro de la marca todo `measures` que traiga un número que nadie dijo. Prueba nueva. |
| P2 | La evidencia de AC01 no tenía la instalación silenciosa. | Hecha y registrada en `installer-build.txt` (código 0, `language=es`, desinstalación limpia). |
| P3 | `local-test-run.txt` no decía el commit. | Ahora lo dice. |
| P3 | Nombres reservados con extensión (`CON.report`), superíndices (`COM¹`), U+202E y U+007F pasaban; "x.docx" daba "x.docx.docx". | `report_name` corregido. Pruebas nuevas en `test_nombre_docx.py`. |
| P3 | Los resultados fuera de un proyecto bajaban como `summary.docx`. | Ahora bajan con el nombre de su carpeta. Prueba nueva en `test_app.py`; el test de reunión de proyecto verifica el nombre exacto. |
| P3 | Los delimitadores `«` `»` `[` `]` dentro de la marca la rompían. | Se quitan del texto antes de armarla. Prueba nueva. |

Queda abierto a propósito: cuando la cita de Gemini no está en la transcripción, la marca sigue llevando lo que escribió Gemini (el manual ahora lo dice). Marcarlo de otra forma sería un cambio de formato aparte.

El instalador de esta versión se recompiló desde 9af4c17 (SHA-256 en `installer-build.txt`), no desde 0077d9c.
