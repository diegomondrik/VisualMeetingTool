# WI18 — el instalador de Windows: propuesta de contrato

2026-10-01. **Aprobada por el owner («dale», 2026-10-01)**, con el idioma del
instalador agregado a su pedido antes de aprobar. Sigue el plan de `D-185`
(renumerado por `D-188`: instalador WI18, guía WI19) y la ventana propia de
`D-187`. Su contrato es
`.ingol/work-items/01M3VRRZJ3XYC0ADJT8N733F03/contract.yaml` y su evidencia
está en `docs/evidence/01M3VRRZJ3XYC0ADJT8N733F03/`.

## Qué se entrega

Un archivo `VisualMeetingTool-Setup-<versión>.exe`, bajado de la página de
versiones del repositorio en GitHub. Alguien de tu equipo:

1. le hace doble clic; Windows muestra su aviso por programa sin firmar (ver
   «Tres preguntas» abajo); pasa con «Más información → Ejecutar de todas
   formas»;
2. lo primero que muestra el instalador es **en qué idioma quiere leerlo:
   castellano o inglés**. Todo el instalador sigue en ese idioma, y ese es
   también el idioma con el que arranca la aplicación instalada;
3. el instalador no pide permiso de administrador: instala sólo para esa
   persona, en su usuario, y deja un acceso directo en el menú Inicio y, si
   lo marca, en el escritorio;
4. abre VisualMeetingTool desde el acceso directo: aparece **una ventana
   propia**, con las mismas pantallas de hoy (proyectos, reuniones, reunión
   nueva, ajustes), sin navegador, sin pestañas y sin terminal, en el idioma
   elegido al instalar;
5. la primera vez, Ajustes le pide su clave de Gemini, como hoy;
6. la cierra con la X; si hay una reunión procesándose, la ventana pregunta
   antes de cerrar y, si dice que sí, la reunión se descarta sin dejar nada a
   medias (como hoy cuando se corta).

No hace falta Python ni ninguna otra cosa instalada: el `.exe` lleva todo.

## Qué entra

- **La ventana** (`D-187`): las pantallas de WI15 a WI17 dentro de una ventana
  de Windows, con el componente que Windows 11 ya trae para mostrar páginas
  (el mismo que usa Edge por dentro). Todo lo que hoy anda en el navegador
  tiene que andar ahí: subir un video y una transcripción, subir la plantilla
  y el logo, bajar la plantilla de ejemplo, abrir el Word.
- **Las mismas protecciones de hoy.** El servidor interno sigue escuchando sólo
  en tu máquina y con su llave de sesión; la ventana es la única que la tiene.
  No se abre ninguna puerta nueva.
- **El idioma.** El instalador pregunta primero en qué idioma se lo quiere
  leer (castellano o inglés, los dos que tiene la aplicación desde WI17).
  Todas sus pantallas, y las de la desinstalación, salen en ese idioma. La
  aplicación instalada arranca en ese mismo idioma. Es el idioma por defecto:
  se cambia cuando se quiera en Ajustes, como hoy. Si esa persona ya había
  elegido un idioma en Ajustes (porque ya tenía la aplicación), manda lo que
  eligió ella y el instalador no lo pisa. El idioma de los resúmenes sigue
  aparte, como hoy.
- **Una sola copia a la vez.** Si ya hay una ventana abierta, abrir otra no
  arranca una segunda aplicación sobre los mismos datos: lo dice y no hace
  nada más.
- **Los datos quedan fuera del programa.** Los proyectos y reuniones siguen en
  la carpeta de datos del usuario, como hoy. Desinstalar borra el programa y no
  los datos; instalar una versión nueva encima los deja como estaban, y la
  clave de Gemini también.
- **Desinstalar** desde «Aplicaciones instaladas» de Windows, como cualquier
  programa.
- **La receta para armar el instalador**, en el repositorio: un comando que,
  en una máquina con las herramientas instaladas, arma el `.exe` desde el
  código. Las herramientas son gratuitas y sus versiones quedan fijadas, para
  que dos armados del mismo código den el mismo programa.
- **Una versión publicada**: la primera, con el `.exe` adjunto, en la página
  de versiones de GitHub.

## Qué NO entra

- La guía para el equipo (WI19): se escribe cuando esto anda en una máquina
  limpia.
- Firmar el programa (sacar el aviso de Windows) y la actualización automática:
  ver «Tres preguntas».
- Mac o Linux; Windows 10 (el componente de la ventana no siempre viene
  instalado; si alguien lo necesita, es otro trabajo).
- Cambiar qué hace la aplicación o cómo procesa una reunión. `python -m
  meetingtool app` sigue abriendo el navegador, como dice `D-187`, para quien
  use los comandos.
- Compartir proyectos entre personas: cada uno ve los suyos, en su máquina.

## Cómo se prueba en una máquina limpia

Con **Windows Sandbox**, que viene con Windows 11 Pro: una máquina Windows
nueva, vacía, que se abre en una ventana y se borra entera al cerrarla. No
tiene Python ni nada nuestro. Hay que activarla una vez (es una casilla en
«Activar o desactivar características de Windows» y pide reiniciar): **eso lo
hacés vos**, porque pide permiso de administrador. Si preferís no activarla,
la alternativa es la computadora de alguien del equipo que nunca tuvo
VisualMeetingTool.

En esa máquina limpia:

1. se instala el `.exe` bajado de la página de versiones (el mismo que va a
   bajar el equipo, no una copia local), eligiendo inglés;
2. se abre desde el acceso directo: tiene que arrancar en inglés; se
   recorren las pantallas;
3. se procesa una reunión **sin gasto** (con un techo tan bajo que no se manda
   nada a Gemini, como en WI17): tiene que frenarse con el aviso correcto y
   costo cero;
4. **una corrida real, si querés**: escribís tu clave de Gemini en esa máquina
   (se borra con ella) y se procesa una reunión corta, con techo de US$1,00;
   se ve el Word;
5. se cierra con la X durante un procesamiento: tiene que preguntar;
6. se elige inglés en Ajustes y se instala la misma versión otra vez
   encima, ahora eligiendo castellano en el instalador: los datos siguen ahí
   y la aplicación sigue en inglés, porque la persona ya lo había elegido;
7. se desinstala y la carpeta de datos sigue ahí.

Lo que no se puede ver en la máquina limpia y se dice así: si el antivirus de
alguien del equipo desconfía del programa (pasa a veces con programas sin
firmar armados así). En la prueba se registra qué dice el antivirus de
Windows.

## Cuánto cuesta

- **Armar y publicar: cero.** Las herramientas son gratuitas; el repositorio es
  público y GitHub no cobra por la página de versiones.
- **La corrida real en la máquina limpia: hasta US$1,00** con tu clave, si la
  autorizás (una reunión corta debería costar bastante menos). Sin ella, la
  prueba se hace igual con la corrida sin gasto.
- **Lo que no cuesta plata pero sí espacio:** el instalador va a pesar del
  orden de cien megas, porque lleva Python y la librería de video adentro. Se
  mide y se anota.

## Tres preguntas, de a una

**1. La clave de Gemini, ¿por persona o compartida?** Para el instalador **no
hace falta decidirla**: en ningún caso el instalador lleva una clave adentro.
Cada persona escribe una clave en Ajustes la primera vez y queda guardada en
el almacén de claves de Windows de su usuario, como hoy. Si es la suya o una
tuya que le pasaste es lo que cambia, y eso es materia de la guía (WI19):
cómo se consigue una clave, y quién paga. **Queda abierta para WI19**, con la
misma recomendación de antes: cada uno la suya.

**2. El aviso de Windows por programa sin firmar.** Va sin firmar: el aviso
aparece la primera vez que alguien lo instala, y la guía explica cómo pasarlo.
Sacarlo exige un certificado de firma que se paga por año. **Queda fuera de
WI18 y nombrado**: si después del uso del equipo el aviso molesta, te traigo
las opciones con precio y es un trabajo aparte (firmar se agrega al armado sin
rehacer nada).

**3. La actualización automática.** No entra. Una versión nueva se instala
bajando el instalador nuevo y corriéndolo encima: los datos y la clave
quedan (criterio 7). **Queda fuera de WI18 y nombrada**: un aviso «hay una
versión nueva» dentro de la aplicación es lo más chico que se podría agregar
después, y significaría que la aplicación consulte GitHub cada vez que abre.

## Criterios de aceptación

| # | Criterio | Cómo se comprueba |
|---|---|---|
| 1 | Abierta desde la ventana, cada pantalla y cada acción anda como en el navegador: subir video, transcripción, plantilla y logo; bajar la plantilla de ejemplo; abrir el Word | Pruebas que abren la ventana con datos inventados, sin red y sin clave; y vos las recorrés en la máquina limpia |
| 2 | Cerrar con la X mientras se procesa pregunta; si se confirma, no queda nada a medias; si no se procesa nada, cierra sin preguntar | Pruebas con Gemini simulado |
| 3 | Una segunda apertura sobre los mismos datos no arranca otra aplicación | Prueba |
| 4 | Las protecciones de hoy siguen: un pedido desde otra máquina o desde otra página se rechaza, también con la ventana abierta | Las pruebas de WI15 pasan sin cambios, más una que lo intenta con la ventana |
| 5 | El instalador se arma desde el código con un comando, en un clon limpio | Corrida del comando; su salida y el tamaño del `.exe` van a la evidencia |
| 6 | El instalador pregunta primero el idioma (castellano o inglés) y sigue en ese idioma, también al desinstalar; la aplicación instalada arranca en ese idioma; si la persona ya había elegido uno en Ajustes, se respeta el suyo | Pruebas de cómo la aplicación toma el idioma del instalador; y en la máquina limpia, instalar en inglés y reinstalar en castellano |
| 7 | En Windows Sandbox: instalar sin administrador, abrir, procesar sin gasto, cerrar con la X durante un proceso, reinstalar encima y desinstalar, sin perder datos | La corrida, con capturas y el texto de lo que pasó, en la evidencia; y qué dijo el antivirus de Windows |
| 8 | Corrida real (si la autorizás): una reunión corta procesada en la máquina limpia con tu clave, techo US$1,00, Word abierto | Tu clave, escrita por vos; **vos decís si se entiende** |
| 9 | Sin el instalador, todo sigue igual: los comandos y `python -m meetingtool app` hacen lo de hoy | La suite completa en un clon limpio de tu máquina (`D-163`) |

## Qué autoriza aprobar esto

Dentro de lo que ya cubren `D-100` y `D-107`, sin pedir de nuevo:

- construir WI18 y su rama, push, PR, integración y borrado de rama en
  VisualMeetingTool.

**Y dos cosas que ese alcance no cubre, por eso van con el formato de
autorización:**

```
AUTORIZACIÓN — instalar las herramientas que arman el .exe y publicar la
primera versión de VisualMeetingTool en GitHub

1. ¿Qué cambia fuera de mi máquina?
   Se bajan de internet e instalan en tu máquina tres herramientas gratuitas
   y conocidas: dos librerías de Python (una arma el programa sin Python,
   otra abre la ventana) y el armador de instaladores Inno Setup. Y, una vez
   integrado, se publica en la página de versiones del repositorio (público)
   la primera versión con el .exe adjunto: cualquiera puede bajarla, como ya
   puede bajar el código.

2. ¿Cuánto cuesta y con qué techo?
   Cero. La corrida real en la máquina limpia, hasta US$1,00 con tu clave, y
   sólo si la pedís (criterio 8).

3. ¿Es reversible? ¿Cómo?
   Sí. Las herramientas se desinstalan; la versión publicada se borra de la
   página de versiones. Quien ya la bajó, la conserva.

4. ¿Qué se rompe si sale mal?
   Nada de lo que hoy anda: los comandos y la aplicación en el navegador no
   cambian (criterio 9). Lo peor realista es un instalador que no anda en
   alguna máquina del equipo, o que un antivirus lo frena: se borra la
   versión y se corrige.

5. ¿Qué otras opciones había y por qué esta?
   Armarlo en los servidores de GitHub en vez de en tu máquina: hoy INGOL no
   deja que el proyecto corra sus propios procesos ahí (D-163, trabajo de la
   otra línea). Entregar el programa sin instalador (un .exe suelto): sin
   acceso directo ni desinstalación, y más avisos del antivirus.

Para autorizar respondé: "dale" o "dale, con <condición>".
Para rechazar: "no" o "no, hacé <otra cosa>".
```

**Lo que hacés vos:** activar Windows Sandbox (una casilla y un reinicio)
antes de la prueba en máquina limpia; y, si querés la corrida real, escribir
tu clave dentro de la máquina limpia.

**Lo que no autoriza:** firmar el programa, la actualización automática, la
guía, gasto en Gemini fuera de la corrida del criterio 8, ni tocar INGOL.
