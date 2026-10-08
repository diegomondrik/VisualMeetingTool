# Revisión independiente de WI28 (01M4CM3YV6DMY3QDWAZDMAANW6)

Revisor independiente por el buzón de INGOL (rol `revisor-independiente`, sin herramientas de escritura): el texto es el que devolvió, copiado por el implementador. Al final, lo que se hizo con cada hallazgo.

## Revisión independiente, 2026-10-07 (commit 6e5418a)

# Revisión independiente de WI28 (VisualMeetingTool, `6e5418a` contra `1a78ce4`)

**Veredicto: aprobar con correcciones.** Hay dos hallazgos P1. El mecanismo hace lo que dice el WI28-AC01 al pie de la letra, pero los textos y la limitación le atribuyen una protección que no tiene, y el caso de R07 sigue abierto cuando el exceso cae en el último pedido.

## Alcance leído
Leí el contrato, el plan, el diff completo, `call_checked` y `new_counters`, los llamadores (`jobs.py`, `writer.py`, `qa.py`), la ayuda de los comandos, `changed-tests.md`, `mutations.py` y `mutations.txt`. No leí el historial ni otros work items. Todo lo que cambió cae dentro de `affected_surfaces`; no hay superficies sin declarar.

## Qué ejecuté
| Comando | Resultado |
|---|---|
| `python -m unittest tests.test_spending_estimate` | 18 pruebas, OK |
| `mutations.py . <scratch>` en `6e5418a` | 7 de 7 detectadas; sin mutar, OK |
| `reproduce.py WI28-P3-1` | MATCH |
| `python -m unittest discover -s tests` | 643 pruebas, OK, 3 salteadas (las que necesitan los kits) |
| Prueba propia: una corrida de la aplicación con exceso en el resumen | Ver P1-2 |

## Hallazgos

**P0:** ninguno.

**P1-1. Un cambio de precio no se detecta nunca, pero los textos dicen que sí.** Ejecutado y leído.
- **Dónde:** `meetingtool/reading/gemini.py:264-270`.
- **Qué pasa:** el costo real se calcula con `token_cost(usage)`, que usa las mismas constantes `PRICE_*` que la estimación. La respuesta de Gemini sólo trae cantidades de tokens, nunca un precio. Por eso `cost > worst` sólo puede dispararse cuando hay más tokens que los estimados. Si Google sube la tarifa, o el alias `-latest` pasa a una versión más cara con los mismos tokens, nada se frena.
- **Qué textos lo contradicen:**
  - El README (líneas 60-62) dice "the prices changed".
  - `gemini.estimate_short` (`en.py:49`, `es.py:51`) culpa a los precios del código. Cuando ese mensaje sale, los precios nunca son la causa, y corregirlos no cambia nada: la proporción entre costo y estimación queda igual.
  - `WI28-P3-1` (`REGISTER.md:256`) dice que el problema "se nota" cuando la respuesta cuesta más.
  - La reproducción (`reproduce.py:1433,1444`) dice simular "four times the prices" pero lo que hace es dividir `worst` por 4. Es decir, simula una estimación de tokens corta, no un precio. Pasa sin reproducir lo que afirma.
- **Consecuencia:** el owner queda creyendo cubierta la mitad de R07 que habla de la tarifa ("correspondencia… entre la versión del modelo y su tarifa"), y no lo está.
- **Nota:** el propio contrato pide que el mensaje diga "prices may be out of date", así que el error de premisa viene del contrato. Corregir esa frase toca el contrato: lo decide el owner.
- **Arreglo mínimo:** que los textos digan que la parada detecta más tokens que los estimados (por la entrada o por un modelo nuevo) y que un cambio de precio no se detecta. Reescribir `WI28-P3-1` para decir "no se nota nunca" y que su reproducción muestre eso: un precio distinto, ninguna parada.

**P1-2. Si el exceso cae en el último pedido, la corrida termina como "done", por encima del techo y sin aviso.** Ejecutado.
- **Prueba:** formato resumen, techo de US$0,50, el pedido del resumen con 3.000.000 de tokens de entrada. Resultado: `state=done`, `spent=2.2727`, `error=''`, y la reunión se agrega al proyecto.
- **Por qué importa:** el resumen siempre es el último pedido en ese formato, y en el comando `summary` es el único. Es justo el caso que denuncia R07 ("se acepta la respuesta aunque el contador supere el límite").
- **Qué contradice:** el README y el objetivo del contrato dicen que la corrida "fails saying what was estimated and what it cost".
- **Registro:** el constructor lo avisó, pero no está en `REGISTER.md`.
- **Consecuencia:** la parada promete cubrir el pedido más caro y no lo cubre.
- **Arreglo mínimo, una de dos:**
  - (a) En `jobs._run` y en las líneas de comandos, si al terminar `counters["overrun"]` no es `None`, fallar con `gemini.estimate_short` (la respuesta ya quedó guardada, así que repetir la corrida no paga nada).
  - (b) Si el owner prefiere no cambiar el mecanismo, decirlo en el README y registrarlo como limitación.

**P2:** ninguno.

**P3** (no reabren el ciclo):
- **P3-1.** Cada vez que se repite la corrida empieza con contadores nuevos, así que puede pagar otro exceso con la misma estimación. Es una corrida más por cada pedido que sobra. Así lo define el contrato ("same run"), pero no está escrito como limitación.
- **P3-2.** La ayuda de `--max-cost` (`reading/__main__.py:33`, `summary/__main__.py:49`) sigue diciendo "spend budget… is not sent". Está declarado y el AC02 no cubre la línea de comandos.
- **P3-3.** `mutations.txt` registra `fe38a35`, no `6e5418a`. Entre los dos sólo cambian archivos de evidencia, y yo volví a correrlo en `6e5418a` con el mismo resultado.
- **P3-4.** Falta `local-test-run.txt`, la suite en un clon limpio con los kits. Es pendiente declarado.

## Las preguntas del pedido
- **Pedidos que salen después de un exceso:** no encontré ninguno. El chequeo está arriba del bucle, así que cubre el reintento por respuesta rechazada y el reintento por 429/5xx o falta de respuesta. Los contadores son compartidos por todas las etapas de la aplicación (`jobs.py:88`, 485, 499). En el formato de preguntas y respuestas, `read_listed` y las partes pasan por `call_checked`, y `_stage` envuelve el error. No hay otro `urlopen` en el código. Las respuestas guardadas se sirven sin mandar nada, lo que es coherente con la regla. Cada comando es su propia corrida.
- **Corridas normales:** no cambian. Una respuesta igual o menor a la estimación no marca exceso (hay prueba de borde exacto). Una respuesta sin `usage` se cuenta como la estimación, igual que antes. Una respuesta guardada no cuesta nada ni marca exceso. La suite completa pasa sin cambiar ninguna prueba previa. Un falso positivo en uso normal es muy improbable, porque la estimación incluye el tope de salida completo (49.152 tokens a 3,75 equivalen a unos US$0,18 de margen por fragmento de lectura).
  - **Duda:** no verifiqué, sin red, que el `maxOutputTokens` de Gemini incluya los tokens de razonamiento. Si no los incluyera, podría haber falsos positivos.
- **Textos:** dicen "estimado" en los dos idiomas, sin la palabra garantía, y la página de la corrida muestra la falla y el monto (lo prueba `StagesTest`). El problema es lo que atribuyen a los precios (P1-1).
- **Mutaciones:** son reales. Cada una rompe al menos una prueba y la comparación contra el techo se distingue de la comparación contra la estimación. Pero ninguna prueba cubre el caso del último pedido, y la reproducción de `WI28-P3-1` no puede fallar por lo que dice probar.
- **Mecanismo más simple:** lanzar `estimate_short` dentro de `call_checked` justo después de guardar la respuesta que se excedió. No necesita estado entre llamadas, cierra el P1-2 y repetir la corrida reutiliza lo guardado. A cambio, la etapa que recibió la respuesta falla aunque esa respuesta sea válida, y eso contradice el "is returned" del WI28-AC01.

## Criterios
- **WI28-AC01:** cumplido al pie de la letra (el caso de la revisión, la otra etapa, el reintento, la respuesta guardada; todo ejecutado). No cumple el objetivo en el último pedido (P1-2).
- **WI28-AC02:** los textos dicen "estimado", "precios de lista", "se paga aunque se rechace" y "se frena", sin "garantía". Pero afirman que se detecta un cambio de precio, y eso es falso (P1-1).
- **WI28-AC03:** mutaciones 7 de 7 y tests cambiados nombrados. La limitación se reproduce, pero no prueba lo que dice (P1-1). Faltan la suite en clon limpio con kits y la revisión por el buzón (esta).

Sigue el constructor, con las dos correcciones de una pasada. Antes, el owner decide una sola cosa: si el mensaje deja de decir que los precios pueden estar desactualizados (es una frase que pide su contrato), y si el exceso en el último pedido hace fallar la corrida o queda como limitación escrita.

## Lo que se hizo con cada hallazgo

- P1-1 (los textos y la limitación decían que se detecta un cambio de precios, y no se puede): corregido en 61c88fb; los textos y el registro ya no lo dicen.
- P1-2 (el exceso en el último pedido no frenaba la corrida): corregido en 61c88fb; una respuesta que usó más tokens de los estimados falla la corrida también si fue su último pedido (`check_estimate` al terminar el resumen, la lectura y el registro), con sus pruebas y mutaciones.
- Después se rehízo la corrida de las mutaciones: la de la noche del 7 al 8 había contado como 'detectadas' tres mutaciones cuyo proceso se cayó por falta de memoria (código de salida 3221225773 y 3221225495); el guion ahora sólo cuenta una corrida de pruebas que terminó y falló. Resultado: once mutaciones, once detectadas de verdad (a542355).
