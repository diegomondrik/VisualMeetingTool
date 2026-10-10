# WI34-AC04 — revisión independiente

Hecha por el subagente `revisor-independiente` de INGOL, en su propia ventana, solo lectura, el 2026-10-10. Transcripción resumida de sus dos
informes; el nombre del cliente no aparece, el revisor lo llamó "el nombre".

## Primera revisión (sobre `e21a15d`): aprobar con correcciones

- **P1.** En `tests/test_app.py` (líneas 574, 591, 601 y 607) la prueba de aislamiento buscaba antes el nombre del cliente en una respuesta
  rechazada, y ese nombre estaba tanto en el proyecto como en el cliente. Con `b"Cliente Demo"` solo encontraba el del cliente: una fuga del nombre
  del proyecto ya no la hacía fallar. Probado con una mutación en clones descartables: en `main`, 3 fallas; en la rama, 11 pruebas bien.
  Corrección probada: buscar `b"Demo"`.
- **P2.** "27 commits" no decía lo que parecía: 28 con el commit de limpieza; 229 de 307 commits contienen el nombre en su árbol.
- **P3.** La descripción de las sustituciones no cubría "the client", "a_client" ni `wi14-qa-client`; `real-run.txt` nombra una carpeta de datos que no
  existe en el disco del owner; 19 registros de corridas muestran un método que no existía; el script sin segundo argumento terminaba en
  `IndexError`; la evidencia no estaba commiteada.
- Lo que salió bien: nada cambia en `meetingtool/` salvo la línea de comentario de `qa.py`; las pruebas cambian solo en nombres; la evidencia
  cambia solo en el nombre; el contrato de WI14 es idéntico a `main` y el digest de su registro sigue valiendo; no hay variantes codificadas del nombre
  (UTF-16, UTF-32, invertido, base64, hex, partido) en los 377 archivos versionados.

## Segunda revisión (sobre `a330884`): aprobar

- P1 resuelto: sin mutación, 11 pruebas bien; con la fuga del nombre del proyecto o del cliente, 3 fallas en cada caso.
- P2 resuelto: la cifra del contrato es correcta (227 de 305 commits anteriores a la rama; 27 commits de `main` agregaron o cambiaron el nombre).
- AC03 corrida por el revisor en un clon limpio: 765 pruebas, bien, 3 salteadas, salida 0.
- P3 nuevos sin consecuencia: el script sin segundo argumento imprime el uso y sale con código 1 (no 2); el registro de la suite decía "copied below unchanged" y
  a la vez que acortaba la línea de puntos (corregido después de esta revisión).

## Lo que el revisor no pudo verificar

La suite en Linux (GitHub); los forks o copias que ya existan fuera del repositorio.
