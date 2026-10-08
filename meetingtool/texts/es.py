"""Todo lo que dice el programa, en castellano: el idioma de la aplicación si
nadie lo cambia. Ver meetingtool/texts/__init__.py: cómo un texto nombra sus
datos y qué va entre [[ ]]."""

TEXTS = {
    # ── Imágenes de la grabación (meetingtool.frames) ───────────────────────
    "frames.inside_repository": "la carpeta de salida {folder} está dentro del repositorio git {work_tree}; las "
                                "imágenes de una reunión tienen que quedar fuera de cualquier repositorio",
    "frames.budget_too_small": "el cupo de imágenes tiene que ser al menos 1",
    "frames.not_local": "la grabación {path} no es un archivo de esta máquina",
    "frames.cannot_open": "no se puede abrir la grabación {path}: fijate que sea un video completo[[: {detail}]]",
    "frames.cannot_decode": "no se puede leer la grabación {path} hasta el final: puede estar dañada o cortada"
                            "[[: {detail}]]",
    "transcript.word_unreadable": "no se puede leer la transcripción de Word {path}: fijate que sea el .docx que "
                                  "baja Teams[[: {detail}]]",
    "transcript.word_too_big": "no se puede leer la transcripción de Word {path}: {reason}",
    "transcript.unreadable": "no se puede leer la transcripción {path}: tiene que ser un texto (UTF-8, UTF-16 o el de Windows)[[: {detail}]]",
    "transcript.not_a_file": "la transcripción {path} no es un archivo",
    "transcript.no_timed_line": "la transcripción {path} no tiene ninguna línea con su minuto (la de Teams, «Nombre   "
                                "M:SS», la hora sola en su renglón, o «[HH:MM:SS]»)",

    # ── Proyectos (meetingtool.projects) ────────────────────────────────────
    "projects.inside_repository": "la carpeta de datos {folder} está dentro del repositorio git {work_tree}; los "
                                  "datos de las reuniones tienen que quedar fuera de cualquier repositorio",
    "projects.bad_identifier": "{project!r} no es el identificador de un proyecto",
    "projects.missing": "el proyecto {project} no existe en {folder}",
    "projects.needs_name": "un proyecto necesita un nombre",
    "projects.exists": "ya existe el proyecto {project} en {folder}",
    "projects.needs_title": "una reunión necesita un título",
    "projects.unreadable": "no se puede leer el registro {file}[[: {detail}]]; no se cambió nada: arreglalo "
                           "o sacalo del proyecto",
    "projects.busy": "otro MeetingTool (la aplicación o un comando) tiene la carpeta de datos {folder} hace "
                     "más de {seconds:.0f} s; no se cambió nada: probá de nuevo cuando termine",
    "meeting.bad_date": "la fecha de la reunión {date!r} no es una fecha AAAA-MM-DD válida",

    # ── La clave de Gemini y la lectura de las imágenes (meetingtool.reading)
    "credentials.not_windows": "la clave de Gemini se guarda en el Administrador de credenciales de Windows; este "
                               "sistema no es Windows",
    "credentials.unreadable": "no se pudo leer el Administrador de credenciales de Windows (error {code})",
    "credentials.empty": "la clave está vacía; no se guardó nada",
    "credentials.refused": "el Administrador de credenciales de Windows no dejó guardar la clave (error {code})",
    "credentials.cannot_delete": "el Administrador de credenciales de Windows no dejó borrar la clave (error {code})",
    "gemini.no_text": "la respuesta de Gemini no trae texto ({kind})",
    "gemini.unfinished": "la respuesta de Gemini no terminó bien (finishReason {finish})",
    "gemini.blocks": "la respuesta de Gemini no trae un bloque por imagen, de la {first} a la {last}: faltan "
                     "{missing}, repetidas {repeated}, no mandadas {extra}",
    "gemini.reason.not_json": "la respuesta no es JSON",
    "gemini.reason.no_answer": "sin respuesta ({kind})",
    "gemini.over_budget": "se frenó antes de mandar {what}: ese pedido podía costar hasta US${worst:.2f}, y con unos "
                          "US${spent:.2f} ya gastados podía pasar el techo de US${budget:.2f}; no se escribió nada"
                          "{refused}",
    "gemini.estimate_short": "se frenó{unsent}: la respuesta a {after} usó más tokens de los que se estimaba que usaría "
                             "su pedido, y costó US${cost:.4f} contra los US${estimated:.4f} estimados, así que la "
                             "estimación no es confiable y en esta corrida no se manda nada más. Lo que ya se "
                             "respondió queda guardado{refused}",
    "gemini.estimate_short.before": " antes de mandar {what}",
    "gemini.estimate_short.end": " al terminar la corrida, antes de escribir nada",
    "gemini.before.no_answer": " (el intento anterior no tuvo respuesta[[: {reason}]])",
    "gemini.before.refused": " (la respuesta anterior se rechazó: {error})",
    "gemini.refused": "Gemini rechazó el pedido (HTTP {status}); si dice que la clave no sirve, guardala de nuevo en "
                      "Ajustes[[: {reason}]]",
    "gemini.no_answer": "Gemini no respondió {what} después de {retries} reintentos ({label}[[: {reason}]]); no se "
                        "escribió nada: probá de nuevo en unos minutos",
    "gemini.bad_key": "la clave guardada tiene caracteres que una clave de Gemini nunca tiene; guardala de nuevo",
    "gemini.inside_repository": "la carpeta {folder} está dentro del repositorio git {work_tree}; las imágenes y lo "
                                "que muestran tienen que quedar fuera de cualquier repositorio",
    "gemini.what.frames": "las imágenes {first} a {last}",
    "gemini.no_frames": "no hay ninguna frame_*.jpg en {folder}",
    "gemini.chunk_too_small": "el tamaño de cada tanda tiene que ser al menos 1",

    # ── El resumen (meetingtool.summary.writer) ─────────────────────────────
    "language.es": "castellano",
    "language.en": "inglés",
    "summary.what": "el resumen",
    "summary.subject": "el resumen",
    "summary.retired.discovery": "tanto la preventa como el relevamiento",
    "summary.wrong_language": "{subject} no está en {language} ({wanted} palabras comunes de ese idioma, {other} del "
                              "otro, sin contar citas ni código)",
    "summary.section_wrong_language": "la sección «{heading}» no está en {language} ({wanted} palabras comunes de ese "
                                      "idioma, {other} del otro, sin contar citas, código ni tablas)",
    "summary.frames_missing": "el resumen nombra imágenes que no están en la carpeta: {names}",
    "summary.frame_range": "el resumen nombra un rango de imágenes en vez de cada imagen por separado: {text}",
    "summary.frame_unbracketed": "el resumen menciona una imagen sin su nombre de archivo entre corchetes: {text}",
    "summary.unfinished": "el resumen de Gemini no terminó bien (finishReason {finish})",
    "summary.section_count": "el resumen tiene la sección «{heading}» {count} veces, no una",
    "summary.order": "las secciones del resumen no están en el orden pedido",
    "summary.no_key_points": "la sección «{heading}» del resumen no tiene ningún punto",
    "summary.empty_sections": "el resumen no tiene nada bajo estas secciones: {headings}",
    "summary.not_read": "las imágenes de {folder} todavía no se leyeron: corré python -m meetingtool.reading read "
                        "--frames <carpeta> antes",
    "summary.retired_type": "el tipo de reunión {meeting_type!r} ya no se usa: cubría {covered}; usá {use}",
    "summary.unknown_type": "no hay un tipo de reunión {meeting_type!r}; puede ser {options}",
    "summary.unknown_language": "no hay un idioma {language!r}; puede ser {options}",
    "summary.needs_title_and_date": "una reunión que se agrega a un proyecto necesita --title y --date",
    "summary.project": "no se pudo leer lo que sabe el proyecto {project}[[: {error}]]",
    "summary.not_added": "se escribió {output}, pero la reunión no se pudo agregar al proyecto {project}[[: {error}]]",

    # ── Preguntas y respuestas (meetingtool.summary.qa) ─────────────────────
    "qa.what.register": "registro",
    "qa.what.screen_reading": "lectura de la pantalla",
    "qa.what.register_part": "el registro (parte {part} de {parts})",
    "qa.subject.register": "el registro",
    "qa.where.question": "la pregunta {number}",
    "qa.where.knowledge": "el conocimiento «{group}»",
    "qa.where.seen": "lo que se vio en pantalla",
    "qa.unfinished": "el {what} de Gemini no terminó bien (finishReason {finish})",
    "qa.not_json": "el {what} de Gemini no es JSON",
    "qa.not_object": "el {what} de Gemini no es un objeto JSON",
    "qa.not_text": "{where}: «{key}» no es texto",
    "qa.mentions_frame": "{where} menciona una imagen",
    "qa.invented_date": "{where} escribe una fecha que la transcripción no dice ({dates})",
    "qa.invented_year": "{where} escribe un año que la transcripción no dice ({years})",
    "qa.invented_figure": "{where} escribe una cifra que nadie dijo en la reunión ({figures})",
    "qa.question_not_object": "{where} no es un objeto JSON",
    "qa.no_question": "{where} no tiene la pregunta",
    "qa.bad_status": "{where}: el estado {status!r} no es uno de {options}",
    "qa.bad_minutes": "{where}: sus minutos no son H:MM:SS",
    "qa.ends_before": "{where}: su respuesta termina ({end}) antes de empezar ({start})",
    "qa.after_end": "{where}: el minuto {end} es posterior al último turno de la reunión ({last})",
    "qa.answers_not_list": "{where}: «answers» no es una lista",
    "qa.answer_not_object": "{where}: una respuesta no es un objeto JSON",
    "qa.answer_no_text": "{where}: una respuesta no tiene texto",
    "qa.answer_stranger": "{where}: la respuesta se le da a {speaker!r}, que no habló en la reunión",
    "qa.no_answer_status": "{where}: no tiene respuesta, y sin embargo su estado es {status}",
    "qa.asker_stranger": "{where}: la plantea {speaker!r}, que no habló en la reunión",
    "qa.quote_missing": "{where}: su fragmento textual no está en la transcripción entre {start} y {end} (o tiene "
                        "menos de {words} palabras)",
    "qa.screen_not_bool": "{where}: «screen» no es verdadero ni falso",
    "qa.screen_quote_missing": "{where} está marcada en pantalla, pero las palabras que lo muestran no están en la "
                               "transcripción entre {start} y {end}",
    "qa.no_questions_list": "el registro no trae la lista de preguntas",
    "qa.refused": "{count} pregunta(s) rechazada(s): {refusals}{more}",
    "qa.no_knowledge": "el registro no trae «knowledge»",
    "qa.knowledge_not_list": "el conocimiento «{group}» del registro no es una lista de textos",
    "qa.seen_no_list": "lo que se vio en pantalla no trae la lista de respuestas",
    "qa.seen_not_object": "lo que se vio en pantalla: una respuesta no es un objeto JSON",
    "qa.seen_stranger": "lo que se vio en pantalla se le da a {identifier!r}, que no es una respuesta en pantalla con "
                        "imágenes",
    "qa.seen_twice": "lo que se vio en pantalla se le da dos veces a {identifier}",
    "qa.seen_empty": "{identifier}: no se dice nada de lo que se vio",
    "qa.seen_names_frame": "{identifier}: lo que se vio nombra una imagen en su texto",
    "qa.seen_frames_not_list": "{identifier}: «frames» no es una lista de nombres de archivo",
    "qa.seen_frames_outside": "{identifier}: imágenes fuera de su tramo o no leídas: {names}",
    "qa.seen_missing": "falta lo que se vio en pantalla para {identifiers}",
    "qa.stage.register": "registro {part}/{parts}",
    "qa.stage.kept": "{stage} (guardado de una corrida anterior)",
    "qa.stage.frames": "imágenes",
    "qa.stage.seen": "lo visto en pantalla",
    "qa.stage_cost": "{stage} US${cost:.3f}",
    "qa.stopped": "{error}{before} [se frenó en {stage} después de {attempts} intento(s); unos US${spent:.3f} "
                  "gastados en total{done}; el registro no se escribió]",
    "qa.stopped.before": "; la respuesta anterior también se rechazó: {refusal:.300}",
    "qa.stopped.done": ", de los cuales {stages}",
    "qa.no_folder": "la carpeta {folder} no existe",
    "qa.needs_speakers": "la transcripción {path} no dice quién habla, y el registro de preguntas y respuestas "
                         "necesita saber quién preguntó y quién respondió: escribí el resumen en su lugar (formato "
                         "resumen)",

    # ── Paquetes de Word (meetingtool.word_package) ─────────────────────────
    "package.too_many_entries": "el archivo trae {count} partes, y uno de Word puede traer {limit} como máximo",
    "package.part_too_big": "la parte {part} ocupa más de {limit} MB una vez expandida, el máximo para una parte",
    "package.total_too_big": "las partes juntas ocupan más de {limit} MB una vez expandidas, el máximo para un "
                             "archivo de Word (se pasó en {part})",
    "package.unreadable_part": "la parte {part} está comprimida de una manera que los archivos de Word no usan, o "
                               "está cifrada, y el programa no la lee",

    # ── El informe en Word (meetingtool.report) ─────────────────────────────
    "layout.marker_not_alone": "{{informe}} tiene que estar solo en su línea, sin nada más",
    "layout.toc_unreadable": "el índice no se puede leer: insertalo de nuevo en Word (Referencias, Tabla de "
                             "contenido) y guardá la plantilla",
    "layout.marker_misplaced": "{{informe}} tiene que estar solo en su línea en el cuerpo, no en una tabla, un "
                               "encabezado o un pie",
    "layout.unknown_fields": "la plantilla tiene {unknown}, que no es un dato que conozca; los datos son {{cliente}} "
                             "{{proyecto}} {{reunion}} {{fecha}} {{tipo}} (o {{client}} {{project}} {{meeting}} "
                             "{{date}} {{type}})",
    "layout.toc_no_result": "el índice no se puede leer: su campo no tiene resultado",
    "report.active.unreadable": "{part}: no es XML legible, así que no se sabe qué contiene[[ ({detail})]]",
    "report.active.external": "{part}: un {kind} externo ({target})",
    "report.active.embedded": "{part}: un {kind} ({target})",
    "report.active.field": "{part}: un campo {field}",
    "report.active.unnamed_field": "{part}: un campo cuyo nombre no está escrito completo en el archivo (lo arma otro campo), así que no se sabe qué es",
    "report.active.compat_unknown": "{part}: {name}, que no es una parte conocida de Markup Compatibility, así que no se sabe qué leería Word",
    "report.active.compat_structure": "{part}: {name} no está armado como Markup Compatibility lo define (una lista de alternativas, cada una con los espacios de nombres que requiere, y un solo respaldo al final), así que no se sabe qué leería Word",
    "report.active.compat_prefix": "{part}: Markup Compatibility nombra {name}, que no es un prefijo declarado en el archivo o es uno que Word entiende, así que no se sabe qué leería Word",
    "report.active.hyperlink": "{part}: un hipervínculo a {target}, que no es una página web (http, https), una dirección de correo ni un lugar del documento",
    "report.active.macros": "un tipo de contenido con macros, o un proyecto de macros",
    "report.macro_extension": "la plantilla {name} puede llevar macros ({suffix}); guardala en Word como .docx o .dotx",
    "report.not_word": "la plantilla {name} no es un documento ni una plantilla de Word (.docx o .dotx)",
    "report.cannot_open": "la plantilla {name} no se puede abrir: fijate que sea un archivo de Word[[: {detail}]]",
    "report.macros": "la plantilla {name} lleva macros; guardala en Word como .docx o .dotx",
    "report.active": "la plantilla {name} tiene contenido que Word cargaría o ejecutaría desde afuera al abrir un "
                     "informe, o un campo que una plantilla no puede tener, y cada informe se lo llevaría al "
                     "cliente:\n  {items}\nSacalo en Word y guardá la plantilla de nuevo (adjuntá la plantilla "
                     "Normal, insertá las imágenes en vez de vincularlas, borrá los campos vinculados y los objetos "
                     "incrustados). Los únicos campos que una plantilla puede tener son {allowed}.",
    "report.active_in_report": "no se escribió el informe: llevaría contenido que Word cargaría o ejecutaría desde "
                               "afuera cuando el cliente lo abra, o un campo que una plantilla no puede tener:\n"
                               "  {items}\nHay que corregir la plantilla que lo dio. Los únicos campos que una "
                               "plantilla puede tener son {allowed}.",
    "report.not_a_document": "la plantilla {name} no se puede abrir como documento de Word[[: {detail}]]",
    "report.template_too_big": "la plantilla {name} no se puede usar: {reason}",
    "report.too_big": "no se escribió el informe: {reason}",
    "report.template_unusable": "la plantilla {name} no se puede usar: {error}",
    "report.problem.range": "línea {line}: un rango de imágenes; nombrá cada imagen por separado: {text}",
    "report.problem.missing": "línea {line}: {name} no está en {folder}",
    "report.problem.unnamed": "línea {line}: una mención de imagen que no nombra ningún archivo (se espera "
                              "[frame_NNN_tHH-MM-SS.jpg]): {text}",
    "report.not_built": "el informe no se armó:\n  {problems}",
    "report.missing_sections": "al documento de Word le faltan las secciones {missing}; no se entregó",
    "report.toc_mismatch": "el índice del documento de Word no lista exactamente sus secciones; no se entregó",
    "report.fields_left": "el documento de Word todavía tiene {fields} sin llenar; no se entregó",
    "report.images_mismatch": "al documento de Word le faltan {lacking} imagen(es) y le sobran {extra}; no se entregó",
    "report.inside_repository": "la carpeta {folder} está dentro del repositorio git {work_tree}; el informe es un "
                                "dato del cliente y tiene que quedar fuera de cualquier repositorio",
    "report.no_summary": "no hay un {summary} en {folder}: escribí el resumen antes con python -m meetingtool.summary",
    "report.no_heading": "{path} no tiene ningún título de sección; no parece un resumen",
    "report.unread_headings": "las líneas {lines} de {path} empiezan con # pero no son títulos que el informe pueda "
                              "leer (un título empieza la línea con 1 a 6 # y tiene texto); el informe no se armó",
    "report.frame_unembeddable": "la imagen {name} no se puede poner en el informe[[ ({detail})]]; el informe no se "
                                 "armó",
    "report.cannot_write": "el informe no se pudo escribir en {folder}[[: {detail}]]",
    "report.cannot_replace": "{path} no se pudo reemplazar[[ ({detail})]]{hint}",
    "report.close_word": "; si está abierto en Word, cerralo y probá de nuevo",
    "report.no_project": "no hay un proyecto {project!r}; la lista sale con python -m meetingtool.projects",
    "report.example_exists": "{path} ya existe; poné otro nombre",

    # ── La aplicación (meetingtool.app): sus pantallas ──────────────────────
    "app.nav.projects": "Proyectos",
    "app.nav.settings": "Ajustes",
    "app.footer": "Esta página la sirve tu propia máquina: nada de lo que ves sale de ella, salvo lo que se manda a "
                  "Gemini al procesar.",
    "app.detail": "Detalle: {detail}",
    "app.day": "{day}/{month}/{year}",
    "app.error.cannot_show": "No se puede mostrar",
    "app.col.project": "Proyecto",
    "app.col.client": "Cliente",
    "app.col.folder": "Carpeta",
    "app.col.format": "Formato",
    "app.col.cost": "Costo",
    "app.col.date": "Fecha",
    "app.col.meeting": "Reunión",
    "app.col.type": "Tipo",
    "app.col.stage": "Etapa",
    "app.col.state": "Estado",
    "app.col.time": "Tiempo",
    "app.col.paid": "Pagado",
    "app.projects.title": "Proyectos",
    "app.projects.none": "Todavía no hay proyectos.",
    "app.projects.new": "Proyecto nuevo",
    "app.projects.name": "Nombre",
    "app.projects.client": "Cliente",
    "app.projects.create": "Crear el proyecto",
    "app.loose.title": "Resultados sin proyecto",
    "app.loose.hint": "Carpetas de tu carpeta de datos con un resumen hecho desde la terminal, fuera de un proyecto. "
                      "Se muestran como están; la aplicación no las cambia.",
    "app.project.client": "Cliente: {client}",
    "app.project.new_meeting": "Reunión nueva",
    "app.project.meetings": "Reuniones",
    "app.project.no_meetings": "Todavía no hay reuniones.",
    "app.project.knowledge": "Lo que el proyecto ya sabe",
    "app.project.knowledge_hint": "Lo que cada reunión deja y la próxima lee.",
    "app.kept.title": "Guardado de corridas que fallaron",
    "app.kept.hint": "Lo que se pagó en una corrida que falló queda acá, para que procesar de nuevo la misma "
                     "reunión (la misma transcripción y el mismo formato) no lo vuelva a pagar. Descartarlo no "
                     "se puede deshacer.",
    "app.kept.discard": "Descartar",
    "app.kept.confirm": "¿Descartar lo guardado de «{title}»? Procesarla de nuevo lo volvería a pagar.",
    "app.type.presale": "Preventa",
    "app.type.negotiation": "Venta o negociación",
    "app.type.requirements": "Relevamiento",
    "app.type.kickoff": "Inicio de proyecto",
    "app.type.status": "Seguimiento",
    "app.type.technical": "Técnica",
    "app.type.training": "Capacitación",
    "app.type.discovery": "Descubrimiento (tipo anterior)",
    "app.format.summary": "Resumen",
    "app.format.qa": "Preguntas y respuestas",
    "app.language.es": "Castellano",
    "app.language.en": "Inglés",
    "app.stage.frames": "Imágenes del video",
    "app.stage.reading": "Lectura de las imágenes",
    "app.stage.summary": "Resumen",
    "app.stage.qa": "Preguntas y respuestas",
    "app.stage.report": "Informe en Word",
    "app.stage.preparing": "Preparación",
    "app.stage.saving": "Guardar la reunión en el proyecto",
    "app.state.pending": "en espera",
    "app.state.running": "en curso",
    "app.state.done": "listo",
    "app.state.skipped": "no hace falta",
    "app.state.failed": "falló",
    "app.cost.title": "Lo que costó",
    "app.cost.total_html": "<strong>{spent}</strong> de un techo estimado de {ceiling} (con precios de lista; un pedido "
                           "ya mandado se paga aunque se rechace su respuesta), en {seconds} s.",
    "app.frame.mention": "imagen {clock}",
    "app.frame.caption": "Minuto {clock}",
    "app.result.open_word": "Abrir el Word",
    "app.result.download_word": "Descargar el Word",
    "app.result.images": "{shown} imágenes en el informe, de {total} que quedaron del video.",
    "app.result.from_terminal": "Esta reunión se cargó desde la terminal: su carpeta no quedó registrada en el "
                                "proyecto, así que acá se ve lo que el proyecto guardó de ella.",
    "app.result.no_summary": "(sin resumen)",
    "app.result.key_points": "Puntos clave",
    "app.new.title": "Reunión nueva",
    "app.new.meeting_title": "Título",
    "app.new.date": "Fecha",
    "app.new.transcript": "Transcripción",
    "app.new.transcript_hint": "(el .docx de Teams, o un .txt con líneas [HH:MM:SS])",
    "app.new.recording": "Video",
    "app.new.recording_hint": "(opcional: sin video sólo se puede hacer preguntas y respuestas)",
    "app.new.type": "Tipo de reunión",
    "app.new.no_type": "Sin tipo",
    "app.new.language": "Idioma del resultado",
    "app.new.meeting_language": "El de la reunión",
    "app.new.qa_hint": "(cada pregunta con su respuesta completa)",
    "app.new.ceiling": "Techo de gasto estimado en dólares",
    "app.new.ceiling_hint": "(es una estimación con precios de lista: un pedido ya mandado se paga aunque se rechace "
                            "su respuesta, y la corrida se frena si una respuesta costó más de lo estimado)",
    "app.new.process": "Procesar",
    "app.job.title": "Procesando",
    "app.job.loading": "Cargando…",
    "app.job.hint": "Podés dejar esta página abierta; si la cerrás, el trabajo sigue mientras la ventana de "
                    "MeetingTool siga abierta.",
    "app.settings.title": "Ajustes",
    "app.settings.language": "Idioma de la aplicación",
    "app.settings.language_hint": "Cambia todo lo que dice la aplicación. El idioma de cada resumen se elige aparte, "
                                  "al procesar la reunión.",
    "app.settings.language_save": "Guardar el idioma",
    "app.company.title": "Empresa",
    "app.company.hint": "El nombre y el logo aparecen arriba en todas las pantallas y en el nombre de la pestaña. El "
                        "logo: PNG o JPG, hasta 1 MB (un SVG no se acepta: puede llevar código).",
    "app.company.name": "Nombre de la empresa",
    "app.company.name_hint": "(dejalo vacío para no mostrar ninguno)",
    "app.company.save_name": "Guardar el nombre",
    "app.company.logo": "Logo",
    "app.company.logo_current": "El logo actual:",
    "app.company.no_logo": "Sin logo.",
    "app.company.use_logo": "Usar este logo",
    "app.company.remove_logo": "Quitar el logo",
    "app.key.title": "Clave de Gemini",
    "app.key.saved": "Hay una clave guardada ({length} caracteres). No se muestra nunca.",
    "app.key.none": "No hay una clave guardada: sin ella no se puede procesar.",
    "app.key.hint": "Tiene que ser de un proyecto de Google Cloud con facturación activa: en el nivel gratuito Google "
                    "puede usar lo que se le manda, y las reuniones son datos del cliente. Se guarda en el "
                    "Administrador de credenciales de Windows.",
    "app.key.new": "Clave nueva",
    "app.key.save": "Guardar la clave",
    "app.key.delete_confirm": "¿Borrar la clave guardada?",
    "app.key.delete": "Borrar la clave",
    "app.template.title": "Plantilla de Word de la empresa",
    "app.template.unusable": "La plantilla guardada ya no se puede usar: {problem}",
    "app.template.unusable_hint": "Cargá otra, o dejá de usarla para que los informes salgan con el diseño neutro.",
    "app.template.none": "Sin plantilla: los informes salen con un diseño neutro.",
    "app.template.named_html": "La empresa usa la plantilla <strong>{name}</strong>, cargada el {day}.",
    "app.template.unnamed": "La empresa usa una plantilla cargada antes de que se guardara su nombre: para verlo acá, "
                            "cargala de nuevo.",
    "app.field.client": "el cliente",
    "app.field.project": "el proyecto",
    "app.field.meeting": "el título de la reunión",
    "app.field.date": "la fecha",
    "app.field.type": "el tipo de reunión",
    "app.template.fields": "En la portada va a poner: {fields}.",
    "app.template.no_fields": "No tiene datos para llenar en la portada (se escriben entre llaves, por ejemplo "
                              "{{cliente}}).",
    "app.template.toc": "Tiene índice: cada informe pone ahí sus secciones, sin números de página (en Word, clic "
                        "derecho sobre el índice y «Actualizar campos» los agrega).",
    "app.template.no_toc": "No tiene índice.",
    "app.template.dropped_index_one": "Lo que tiene después del índice es un modelo y no entra en los informes: 1 "
                                      "párrafo con texto.",
    "app.template.dropped_index": "Lo que tiene después del índice es un modelo y no entra en los informes: {count} "
                                  "párrafos con texto.",
    "app.template.dropped_marker_one": "Lo que tiene después de {{informe}} es un modelo y no entra en los informes: 1 "
                                       "párrafo con texto.",
    "app.template.dropped_marker": "Lo que tiene después de {{informe}} es un modelo y no entra en los informes: "
                                   "{count} párrafos con texto.",
    "app.template.all_cover": "Todo lo que tiene escrito en la hoja sale como portada de cada informe.",
    "app.template.hint": "Un .docx o .dotx (nunca uno con macros) con el logo, el encabezado, los colores y las letras "
                         "de la empresa. Lo que tenga escrito en su hoja es la portada de cada informe; donde escriba "
                         "{{cliente}}, {{proyecto}}, {{reunion}}, {{fecha}} o {{tipo}}, entre llaves, va ese dato de "
                         "la reunión. Si tiene un índice de Word, se llena con las secciones de cada informe, y lo que "
                         "esté después del índice (o de {{informe}}, sola en su línea) es un modelo que no entra.",
    "app.template.example": "Bajar una plantilla de ejemplo",
    "app.template.example_after": " para empezar.",
    "app.template.example_file": "plantilla-de-ejemplo.docx",
    "app.template.file": "Plantilla",
    "app.template.use": "Usar esta plantilla",
    "app.template.remove": "Dejar de usar la plantilla",

    # ── La aplicación: lo que rechaza o avisa ───────────────────────────────
    "app.not_found": "no hay nada en esta dirección",
    "app.unexpected": "falló algo inesperado[[: {detail}]]",
    "app.refused.not_local": "sólo se atienden pedidos de esta misma máquina",
    "app.refused.not_this_app": "el pedido no es para esta aplicación",
    "app.refused.other_site": "un pedido de otro sitio no se atiende",
    "app.refused.session": "abrí la aplicación desde MeetingTool (la sesión no es válida)",
    "app.refused.change_page": "un cambio sólo se acepta desde la página de la aplicación",
    "app.refused.json_only": "un cambio sólo se acepta en JSON",
    "app.refused.method": "método no admitido",
    "app.refused.stale_link": "esta dirección ya no es válida: abrí la aplicación de nuevo desde MeetingTool",
    "app.refused.no_length": "falta el largo del pedido",
    "app.refused.too_big": "el pedido es demasiado grande",
    "app.refused.not_json": "el pedido no es JSON válido",
    "app.refused.not_object": "el pedido no es un objeto JSON",
    "app.refused.bad_file": "ese archivo no sirve: se acepta {kinds}",
    "app.refused.no_file_length": "falta el largo del archivo",
    "app.refused.empty_or_big": "el archivo está vacío o es demasiado grande",
    "app.refused.cut": "el archivo llegó cortado",
    "app.request.bad_date": "la fecha {value!r} no es una fecha AAAA-MM-DD válida",
    "app.request.not_text": "el campo {name} no es texto",
    "app.request.no_project": "no hay un proyecto {project!r}",
    "app.request.needs_title": "la reunión necesita un título",
    "app.request.no_type": "no hay un tipo de reunión {value!r}",
    "app.request.no_language": "no hay un idioma {value!r}",
    "app.request.no_format": "no hay un formato {value!r}",
    "app.request.no_transcript": "falta la transcripción (un .docx de Teams o un .txt con líneas [HH:MM:SS])",
    "app.request.video_gone": "el video subido ya no está: subilo de nuevo",
    "app.request.qa_needs_speakers": "el registro de preguntas y respuestas necesita saber quién preguntó y quién "
                                     "respondió, y esta transcripción no dice quién habla (cada hora está sola en "
                                     "su renglón): elegí el formato resumen",
    "app.request.summary_needs_video": "el resumen necesita el video, para leer lo que se mostró; sin video, elegí el "
                                       "formato preguntas y respuestas",
    "app.request.bad_ceiling": "el techo de gasto tiene que ser un número de dólares mayor que 0 y hasta 5",
    "app.request.project_not_text": "el nombre y el cliente son texto",
    "app.run.no_key": "no hay una clave de Gemini guardada: guardala en Ajustes",
    "app.run.busy": "ya hay una reunión procesándose: esperá a que termine",
    "app.run.folder_taken": "ya hay una carpeta {folder} en el proyecto",
    "app.key.paste": "pegá la clave antes de guardarla",
    "app.open.windows_only": "abrir el Word desde acá sólo funciona en Windows: descargalo",
    "app.data_folder_in_use": "MeetingTool ya está abierto sobre {folder}: usá esa ventana",
    "app.settings.unknown_language": "no hay un idioma {value!r} para la aplicación",
    "app.company.name_not_text": "el nombre de la empresa es texto",
    "app.company.name_too_long": "el nombre de la empresa puede tener hasta {limit} caracteres",
    "app.company.name_unprintable": "el nombre de la empresa tiene caracteres que no se pueden mostrar",
    "app.logo.svg": "un logo SVG no se acepta, porque puede llevar código que se ejecutaría dentro de la aplicación: "
                    "guardalo como PNG o JPG",
    "app.logo.kind": "el logo tiene que ser un PNG o un JPG",
    "app.logo.too_big": "el logo pesa más de 1 MB: achicalo o guardalo como JPG",
    "app.logo.too_many_pixels": "el logo es demasiado grande: hasta {limit} píxeles de lado",
    "app.logo.not_image": "el archivo no es una imagen PNG o JPG que se pueda leer[[: {detail}]]",
    "app.console.open": "MeetingTool está abierto en tu navegador ({url}); sólo esta máquina puede entrar.",
    "app.console.paste": "Si no se abrió, pegá esta dirección en el navegador: {url}",
    "app.console.keep": "Dejá esta ventana abierta mientras lo uses; para cerrarlo, cerrá esta ventana o apretá "
                        "Ctrl+C.",
    "app.console.error": "error: {error}",

    # ── El script de la página (static/app.js), que pone él mismo los {datos}
    "js.unreadable": "la respuesta no se pudo leer",
    "js.failed": "no se pudo",
    "js.upload_failed": "no se pudo subir",
    "js.connection_lost": "se cortó la conexión con MeetingTool",
    "js.wait": "Un momento…",
    "js.opening": "Abriendo el Word…",
    "js.choose_template": "Elegí la plantilla.",
    "js.checking_template": "Revisando la plantilla…",
    "js.choose_logo": "Elegí el logo.",
    "js.checking_logo": "Revisando el logo…",
    "js.missing_transcript": "Falta la transcripción.",
    "js.summary_needs_video": "El resumen necesita el video. Sin video, elegí preguntas y respuestas.",
    "js.uploading_transcript": "Subiendo la transcripción…",
    "js.uploading_video": "Subiendo el video… {percent} %",
    "js.starting": "Empezando…",
    "js.col.stage": "Etapa",
    "js.col.state": "Estado",
    "js.col.time": "Tiempo",
    "js.col.cost": "Costo",
    "js.state.pending": "en espera",
    "js.state.running": "en curso…",
    "js.state.done": "listo",
    "js.state.skipped": "no hace falta",
    "js.state.failed": "falló",
    "js.spent": "Gastado: {spent} de un techo estimado de {ceiling} · {seconds} s",
    "js.see_meeting": "Ver la reunión",
    "js.failed_at": "Falló en «{stage}»: {error}. La reunión no se agregó al proyecto y no quedó nada a medias.",
    "js.detail": "Detalle: {detail}",
    "js.retry": "Volver a intentar",
    "js.connection_job": "Se cortó la conexión con MeetingTool: fijate que su ventana siga abierta.",
    "js.running": "Se está procesando «{title}»: ver el avance",
    "js.kept": "Lo que Gemini ya respondió para esta reunión quedó guardado (lleva pagado {paid}): procesarla "
               "de nuevo con la misma transcripción no lo vuelve a pagar. Hasta entonces, figura en el proyecto.",
    "js.discard": "Descartar lo guardado",
    "js.discard_confirm": "¿Descartar lo guardado? Procesar de nuevo esta reunión lo volvería a pagar.",
    "js.discarded": "Descartado.",
}
