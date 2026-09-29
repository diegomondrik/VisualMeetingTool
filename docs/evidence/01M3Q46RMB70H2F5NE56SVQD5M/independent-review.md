# WI14 — revisión independiente de e1649d6 y su disposición

Revisor: subagente `revisor-independiente` (INGOL), sesión 117, 2026-09-29.
Leyó el contrato, el plan y `git diff cebd990..e1649d6`; corrió la suite (229
OK) y una sonda propia fuera del repositorio; no abrió datos del cliente.
Veredicto: **no listo** (P1-1), listo con limitaciones una vez corregido P1-1.

| # | Sev. | Hallazgo | Disposición |
|---|---|---|---|
| 1 | P1 | El tope de US$0,50 no alcanzaba para el recorrido completo de Cermaq aun sin reintentos (reservas: ~0,18 por tanda, ~0,21 la lectura de 20 imágenes por reservar la salida de 70, ~0,06 lo visto: ~0,63); el corte llegaba después de pagar el registro | **Corregido.** La lectura de imágenes elegidas reserva 2.000 + 1.000 tokens por imagen (`gemini.listed_output_tokens`); el registro baja su tope de salida a 32.768. Prueba `BudgetTest`: el peor caso de todo el recorrido (dos tandas de ~115.000 caracteres, 20 imágenes, lo visto) suma menos de 0,50. Mutación que lo deshace, detectada |
| 2 | P2 | El reintento reenviaba el mismo pedido | **Corregido.** El reintento agrega por qué se rechazó (`qa.revise`, `call_checked(revise=...)`); la reserva cubre ese agregado. Prueba y mutación |
| 3 | P2 | El tramo de una respuesta retomada mucho después se inflaba | **Corregido.** El tramo se corta a 10 minutos desde que empezó (`SPAN_MAX`). Prueba y mutación |
| 4 | P2 | Una pregunta retomada en la segunda tanda hacía rechazar la tanda | **Corregido.** Una pregunta fuera de la mitad de su tanda se deja afuera (la otra tanda la registra). Pruebas y mutación. Queda como limitación: lo retomado en la segunda tanda no se suma |
| 5 | P2 | Fechas: falsos positivos («1/2», «24/7», «10 may change») y días en palabras no reconocidos | **Corregido en parte.** Día/mes sin año sólo cuenta tras una palabra que introduce una fecha; «may» tras un día sólo con «of»; días en palabras en castellano. Pruebas y mutación. Limitación: día/mes suelto no se controla; días en palabras en inglés tampoco |
| 6 | P2 | Fragmento y palabras de pantalla buscados en toda la transcripción | **Corregido.** Se buscan en los turnos entre los minutos de la respuesta, con dos minutos de margen. Pruebas y mutación. Limitación: un fragmento dicho fuera de ese margen se rechaza |
| 7 | P3 | El plazo sin acuerdo ni pendiente se perdía | **Corregido.** Prueba y mutación |
| 8 | P3 | «Lo visto» sólo con etiquetas y cifras se rechazaba por idioma | **Corregido.** Sin palabras comunes de ningún idioma no se juzga. Prueba |
| 9 | P3 | Cuatro tipos no tienen postura | Limitación en el contrato |
| 10 | P3 | Minutos entre corchetes rechazados | **Corregido.** Prueba |
| 11 | P3 | Hablante vacío | Sin cambio: con nombres en la transcripción se rechaza; sin nombres ([HH:MM:SS]) pasa y se muestra sin nombre. Coherente |
| 12 | P3 | El control final de imágenes corre después de pagar, fuera del reintento | Limitación en el contrato (casi inalcanzable: el registro ya rechaza cualquier mención de imagen) |
| 13 | P3 | Una corrida que se frena no imprime el costo por etapa | Limitación en el contrato |
| 14 | P3 | Huecos de prueba y mutaciones faltantes | **Corregido.** Nueve mutaciones más (30 en total); pruebas del tope, del corte del tramo y de la salida de la lectura |

Suite tras la corrección: 238 pruebas OK.
