# Revisión independiente de WI27 (01M4CB9FV6XGEYENDJYAEQZWQX), commit d549b2d contra main f1bde92

Por el buzón de INGOL, 2026-10-07. El texto es la respuesta tal como llegó; el implementador sólo bajó un nivel sus títulos.

## La revisión

## Revisión independiente de WI27 (VisualMeetingTool), commit d549b2d contra main f1bde92

**Veredicto: no aprobar.** Una corrección en una línea lo deja listo. Al separar la lista, una mención que hoy se rechaza como rango pasa a aceptarse.

### Qué leí
- El contrato y el plan del work item.
- `git diff f1bde92 d549b2d` completo.
- En `writer.py`: `check_frames`, `retry_note`, `revise`, `check_summary` y `write_summary`.
- `gemini.call_checked` y `_kept_answer` (las respuestas pagadas que se reutilizan).
- `document.cited_frames` y `mention` (el informe Word).
- `changed-tests.md` y `mutations.txt`.

No leí historial ni nada más.

### Qué ejecuté
- **`python -m unittest tests.test_summary`:** 112 pruebas, OK.
- **`python -m unittest discover -s tests` en el clon:** 624 pruebas, OK, 3 salteadas (las `test_d1_*` que necesitan los kits).
- **`mutations.py . <scratchpad>` en d549b2d con el árbol limpio:** detecta las 6 mutaciones; sin mutar, OK.
- **Un script propio** que pasa por `separate_frames` y `check_frames` 31 casos: rangos, listas con un ítem malo, envoltorios, espacios y saltos de línea.
- **Un script propio** sobre `_kept_answer` y sobre el largo de `retry_note`.

No usé red, claves ni Gemini. Un primer intento de mi script quedó colgado esperando entrada y se cortó solo; lo volví a correr bien. No afecta nada.

### Hallazgos

#### P1 — "entre [a y b]" y "between [a and b]" antes se rechazaban y ahora entran al informe como dos imágenes
- **Dónde:** `meetingtool/summary/writer.py`, en `separate_frames` (`one_pair_each` une siempre con `", "`, línea ~454) y en `FRAME_RANGE` (líneas 216-218).
- **Cómo lo sé:** lo ejecuté.
  - `entre [frame_029…jpg y frame_037…jpg]` se convierte en `entre [a], [b]` y se **acepta**.
  - Pasa lo mismo con `between [a and b]`, `entre [a e b]`, `entre [a, b]` y `between [a, and b]`.
  - En main los cinco se rechazaban (como `frame_unbracketed`).
  - La forma con un corchete por imagen, `entre [a] y [b]`, se sigue rechazando como `frame_range`.
- **Por qué pasa:** la reescritura cambia "y"/"and" por ", ", y la alternativa `entre X y Y` de `FRAME_RANGE` deja de reconocer el texto. `document.cited_frames` usa el mismo `FRAME_RANGE` sobre el texto ya reescrito, así que el informe tampoco lo frena.
- **Consecuencia:** un rango escrito en palabras dentro de un corchete llega al Word del cliente con las dos imágenes de los extremos, que nadie eligió. Eso es justo lo que prohíbe D-181, y contradice el contrato ("Everything else is checked as today: … a range … is still refused").
- **Arreglo mínimo:** conservar el separador original en vez de normalizarlo. Por ejemplo, `re.sub(_NAME, lambda m: f"{mark}[{m.group(0)}]{mark}", found.group("names"))`, de modo que `[a y b]` quede `[a] y [b]`. Así una lista en un corchete se juzga igual que los mismos nombres escritos cada uno en su corchete, y `entre [a y b]` vuelve a rechazarse, ahora como `frame_range`. Agregar `entre [a y b]` y `between [a and b]` a las pruebas de rango y una mutación que vuelva a unir con ", ".

#### P2 — El aviso del constructor sobre "entre [a, b] y [c]"
- Aceptarlo como tres imágenes es correcto: un rango tiene dos extremos, y con tres nombres "entre" significa "entre estos".
- Con el arreglo del P1 sigue aceptándose, y es coherente con cómo se trata hoy `entre [a], [b] y [c]`.
- Lo que no es correcto es el caso de dos nombres, que es el P1.

#### P3 — Limitaciones menores
- **Un rango dentro de un corchete se rechaza con la razón de "sin corchetes", no de rango.**
  - El caso: `[a – b]`, `[a to b]`, `[a..b]` se rechazan como `frame_unbracketed`.
  - La nota del reintento dice "never mention a frame by its number, its time or part of its name", pero no "never a range". Gemini podría reintentar con `[a] – [b]` y volver a ser rechazado.
  - La prueba `test_a_range_inside_one_pair_is_not_split_and_is_still_refused` acepta cualquiera de las dos razones, así que el "naming the case" de AC02 se cumple sólo en sentido débil.
  - Arreglo opcional: agregar "never a range of frames" al consejo de `frame_unbracketed`.
- **`mutations.txt` se grabó en 3e0d46c con el árbol sucio, no en d549b2d.** Mi corrida en d549b2d limpio da el mismo resultado. Conviene regrabarlo después del arreglo del P1.
- **`**[a, b]` (envoltorio sólo a la izquierda) queda `**[a], [b]`.** Es sólo de forma: se acepta, el informe lo lee bien y antes se rechazaba.

### Lo que pediste revisar

**Qué cambia de lo que se acepta y se rechaza**
- **Se siguen rechazando:**
  - un nombre que no existe dentro de una lista (`frames_missing`);
  - un nombre armado con partes de dos (`frame_029_t00-31-24`), como `frames_missing`;
  - un ítem que no es un nombre completo;
  - `; and`;
  - una lista partida en dos líneas;
  - `[a – b]`, `[a to b]`, `[a a b]` y `[a..b]`;
  - `[a, ..., b]`;
  - un rango escrito al lado de una lista (`[a, b] to [c]`, `[a] to [b, c]`, `[a, b] hasta [c]`).
- **Lo aceptado hoy sale igual byte a byte:** lo verifica una prueba y lo confirmé.
- **La única regresión es el P1.**

**El texto guardado, el informe y las respuestas pagadas**
- `summary.md` guarda el texto ya separado, el mismo que se controló.
- El Word lo lee con `FRAME_REF`; la prueba lo construye y muestra las dos imágenes.
- Una respuesta pagada (`paid-answers`) que se reutiliza vuelve a pasar por `check_summary`, y por lo tanto por la separación. Lo leí y lo ejecuté con `_kept_answer`; no hay una prueba específica, pero es la misma función de control.

**Las notas nuevas del reintento**
- Dicen qué se rechazó y cómo escribirlo.
- Se combinan con las de WI25 en una lista numerada (lo cubren dos pruebas).
- Con tres razones y 80 caracteres de dato miden 816 a 822 caracteres, contra 2000 de `RETRY_NOTE_CHARS`. La prueba del peor caso con cinco razones también pasa.

**Las pruebas y las mutaciones**
- Pueden fallar de verdad: las 6 mutaciones se detectan.
- Ninguna cubre el P1.

**¿Hay un mecanismo más simple?**
Reescribir en un único punto (`check_summary`) ya es el diseño simple correcto: todo lo que viene después lee el texto ya reescrito. Conservar el separador original, como propone el P1, es igual de simple y además da una garantía más fuerte: una lista en un corchete se juzga exactamente igual que sus nombres escritos cada uno en su corchete.

### Superficies e identidad
Los 7 archivos cambiados están dentro de las superficies que declara el contrato. Los commits van de 5aa47ad a d549b2d sobre f1bde92, como dice el pedido.

### Criterios
- **WI27-AC01 — cumplido.** La línea de la reunión del owner, las listas de tres nombres, los separadores ";", "y", "e", "and" y ", and", los backticks y la negrita: todos se aceptan y se guardan con un corchete por imagen, y el informe muestra las dos imágenes. Lo ejecuté.
- **WI27-AC02 — no cumplido.** `entre [a y b]` y `between [a and b]`, que hoy se rechazan, pasan a aceptarse (P1). El resto de los casos se cumple.
- **WI27-AC03 — cumplido.** La nota dice qué se rechazó, se combina con las otras y respeta `RETRY_NOTE_CHARS`. Lo ejecuté.
- **WI27-AC04 — parcial, como se esperaba.** Mutaciones 6 de 6 detectadas y `changed-tests.md` presente. Faltan, a propósito, la corrida en un clon limpio con los kits (`local-test-run.txt`) y `reproduce.py`. Falta una mutación para el P1.

### Veredicto
**No aprobar:** el P1 hace que un rango escrito en palabras dentro de un corchete llegue al informe del cliente. Se arregla conservando el separador original en `separate_frames`, más una prueba y una mutación.

Sigue que el constructor aplique el arreglo del P1 y regrabe `mutations.txt`; no hace falta otra revisión completa, alcanza con verificar ese cambio.

## Lo que se hizo con cada hallazgo

La revisión, de `d549b2d`, llegó por el buzón de INGOL: motor Claude, rol
`revisor-independiente` (sin herramientas de escritura), cuenta empresa,
modelo pedido por rol (`rol:criterio`, resuelto a `opus`), esfuerzo alto, de
20:52 a 21:10. No aprobó por un P1; la pasada de corrección la hizo el
criterio (`dd2376c`), y el revisor dijo que alcanzaba con verificar ese
cambio.

| Hallazgo | Qué se hizo |
|---|---|
| P1: "entre [a y b]" y "between [a and b]" se aceptaban como dos imágenes | Corregido como propuso: al separar una lista se conserva lo que separaba los nombres ("[a y b]" queda "[a] y [b]"), así una lista se juzga igual que sus nombres cada uno en su corchete; prueba nueva (`test_a_range_in_words_inside_one_pair_is_still_a_range`) y mutación nueva (unir siempre con ", ") |
| P2: "entre [a, b] y [c]" como tres imágenes | Correcto según el revisor; sigue así |
| P3-1: un rango dentro de un corchete se rechaza como "sin corchetes" y el aviso no decía "nunca un rango" | El aviso de imagen sin corchetes dice ahora también "never a range of frames" |
| P3-2: `mutations.txt` grabado con el árbol sucio | Regrabado sobre `dd2376c`, en una copia limpia |
| P3-3: `**[a, b]` queda `**[a], [b]` | Sólo de forma: se acepta y el informe lo lee bien; sin cambio |
| Lo que el arreglo deja igual que antes | Un rango de dos con una coma delante de la última palabra ("between [a, and b]", "entre [a], [b]") no se toma como rango, igual que con cada nombre en su corchete: `WI27-P3-1` en el registro, con reproducción |

La corrida final sobre `dd2376c` se hizo en dos partes, una después de la
otra, porque la máquina sigue corta de memoria (lo dice el encabezado de
`local-test-run.txt`): la suite sin los kits y las pruebas del paquete con
los kits. Las mutaciones, sobre el mismo commit y solas.
