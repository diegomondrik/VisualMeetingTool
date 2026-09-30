"""The screens, as HTML. Everything that comes from a file (a summary written
by Gemini from a client's meeting, a project's name) is escaped before it is
placed; the pages carry no inline script, and the actions are done by
static/app.js."""

import html
import re
from urllib.parse import quote

from meetingtool.summary import writer

STATE_NAMES = {"pending": "en espera", "running": "en curso", "done": "listo", "skipped": "no hace falta",
               "failed": "falló"}
FORMAT_NAMES = {"summary": "Resumen", "qa": "Preguntas y respuestas", "": "—"}
TYPE_NAMES = {"presale": "Preventa", "negotiation": "Venta o negociación", "requirements": "Relevamiento",
              "kickoff": "Inicio de proyecto", "status": "Seguimiento", "technical": "Técnica",
              "training": "Capacitación", "discovery": "Descubrimiento (tipo anterior)"}
LANGUAGE_NAMES = {"es": "Castellano", "en": "Inglés"}

_HEADING = re.compile(r"^(#{1,6})\s*(\S.*?)\s*#*\s*$")
_BULLET = re.compile(r"^(\s*)[-*+]\s+(.*)$")
_NUMBERED = re.compile(r"^(\s*)\d+[.)]\s+(.*)$")
_RULE = re.compile(r"^\s*([-*_])(\s*\1){2,}\s*$")
_SEPARATOR = re.compile(r"^\s*\|?[\s:|-]+\|?\s*$")
_FRAME = re.compile(r"\[(frame_\d+_t(\d{2})-(\d{2})-(\d{2})\.jpg)\]")


def e(value):
    return html.escape(str(value), quote=True)


def money(value):
    return f"US${value:,.3f}".replace(",", "_").replace(".", ",").replace("_", ".")


def clock(hours, minutes, seconds):
    hours = int(hours)
    return f"{hours}:{minutes}:{seconds}" if hours else f"{int(minutes)}:{seconds}"


def _inline(text, frame_url, seen):
    escaped = e(text)
    escaped = re.sub(r"\*\*(.+?)\*\*|__(.+?)__", lambda m: f"<strong>{m.group(1) or m.group(2)}</strong>", escaped)
    escaped = re.sub(r"(?<![\w*])\*(?!\s)([^*]+?)\*(?!\w)", r"<em>\1</em>", escaped)
    escaped = re.sub(r"`([^`]+)`", r"<code>\1</code>", escaped)

    def frame(match):
        name = match.group(1)
        if frame_url is None or name not in frame_url:
            return match.group(0)
        if name not in seen:
            seen.append(name)
        return f'<span class="frame-ref">[imagen {clock(*match.groups()[1:])}]</span>'

    return _FRAME.sub(frame, escaped)


def markdown(text, frame_url=None):
    """A summary's Markdown as HTML: headings, lists, tables, rules and
    paragraphs, with each named frame after the block that first names it
    (as in the Word report). `frame_url` maps a frame's name to its address;
    a frame not in it stays as text."""
    out, paragraph, lists, table, shown = [], [], [], [], []

    def figures(names):
        placed = []
        for name in names:
            if name not in shown:
                shown.append(name)
                minute = clock(*_FRAME.fullmatch(f"[{name}]").groups()[1:])
                placed.append(f'<figure><img src="{e(frame_url[name])}" alt="imagen {minute}" loading="lazy">'
                              f"<figcaption>Minuto {minute}</figcaption></figure>")
        return "".join(placed)

    def block(open_tag, inner_lines, close_tag, joiner="<br>"):
        seen = []
        inner = joiner.join(_inline(line, frame_url, seen) for line in inner_lines)
        return f"{open_tag}{inner}{close_tag}", figures(seen)

    def close_paragraph():
        if paragraph:
            html_block, placed = block("<p>", paragraph, "</p>")
            out.append(html_block + placed)
            paragraph.clear()

    def close_lists(depth=0):
        while len(lists) > depth:
            out.append(f"</{lists.pop()}>")

    def close_table():
        if not table:
            return
        header = len(table) > 1 and _SEPARATOR.fullmatch(table[1])
        rows = [row for row in table if not _SEPARATOR.fullmatch(row)]
        seen, cells_html = [], []
        for number, row in enumerate(rows):
            tag = "th" if number == 0 and header else "td"
            cells = [cell.strip() for cell in row.strip().strip("|").split("|")]
            cells_html.append("<tr>" + "".join(f"<{tag}>{_inline(c, frame_url, seen)}</{tag}>" for c in cells)
                              + "</tr>")
        out.append('<div class="table"><table>' + "".join(cells_html) + "</table></div>" + figures(seen))
        table.clear()

    for line in text.splitlines():
        if line.strip().startswith("|"):
            close_paragraph()
            close_lists()
            table.append(line)
            continue
        close_table()
        heading, bullet, numbered = _HEADING.match(line), _BULLET.match(line), _NUMBERED.match(line)
        if not line.strip():
            close_paragraph()
        elif heading and not line.startswith(" "):
            close_paragraph()
            close_lists()
            level = min(len(heading.group(1)) + 1, 6)
            html_block, placed = block(f"<h{level}>", [heading.group(2)], f"</h{level}>")
            out.append(html_block + placed)
        elif _RULE.fullmatch(line):
            close_paragraph()
            close_lists()
            out.append("<hr>")
        elif bullet or numbered:
            close_paragraph()
            match = bullet or numbered
            tag = "ul" if bullet else "ol"
            depth = min(len(match.group(1).expandtabs(4)) // 2, 3) + 1
            close_lists(depth)
            if len(lists) == depth and lists[-1] != tag:
                close_lists(depth - 1)
            while len(lists) < depth:
                out.append(f"<{tag}>")
                lists.append(tag)
            html_block, placed = block("<li>", [match.group(2)], "")
            out.append(html_block + placed + "</li>")
        else:
            close_lists()
            paragraph.append(line.strip())
    close_paragraph()
    close_table()
    close_lists()
    return "\n".join(out)


def layout(title, body, active=""):
    nav = "".join(f'<a href="{href}"{" class=active" if active == key else ""}>{label}</a>'
                  for key, href, label in (("projects", "/", "Proyectos"), ("settings", "/settings", "Ajustes")))
    return ("<!doctype html>\n<html lang=\"es\"><head><meta charset=\"utf-8\">"
            "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
            f"<title>{e(title)} · MeetingTool</title><link rel=\"stylesheet\" href=\"/static/style.css\">"
            "<script src=\"/static/app.js\" defer></script></head><body>"
            f"<header><a class=\"brand\" href=\"/\">MeetingTool</a><nav>{nav}</nav></header>"
            "<div id=\"running\" class=\"banner\" hidden></div>"
            f"<main>{body}</main><footer>Esta página la sirve tu propia máquina: nada de lo que ves sale de ella, "
            "salvo lo que se manda a Gemini al procesar.</footer></body></html>")


def _result_cells(result):
    if not result:
        return "<td>—</td><td>—</td>"
    run = result.get("run") or {}
    cost = money(run["cost_usd"]) if isinstance(run.get("cost_usd"), (int, float)) else "—"
    return f"<td>{e(FORMAT_NAMES.get(result['format'], '—'))}</td><td>{cost}</td>"


def projects_page(projects, loose):
    rows = "".join(
        f'<tr><td><a href="/p/{quote(p["id"])}">{e(p["name"])}</a></td><td>{e(p.get("client") or "—")}</td></tr>'
        for p in projects) or '<tr><td colspan="2" class="empty">Todavía no hay proyectos.</td></tr>'
    body = (f"<h1>Proyectos</h1><table class=\"list\"><tr><th>Proyecto</th><th>Cliente</th></tr>{rows}</table>"
            "<section class=\"card\"><h2>Proyecto nuevo</h2>"
            "<form data-api=\"/api/projects\" data-then=\"project\">"
            "<label>Nombre <input name=\"name\" required maxlength=\"120\"></label>"
            "<label>Cliente <input name=\"client\" maxlength=\"120\"></label>"
            "<button type=\"submit\">Crear el proyecto</button><p class=\"message\" role=\"status\"></p></form>"
            "</section>")
    if loose:
        items = "".join(
            f'<tr><td><a href="/r/{quote(item["name"])}">{e(item["name"])}</a></td>{_result_cells(item["result"])}'
            "</tr>" for item in loose)
        body += ("<section><h2>Resultados sin proyecto</h2><p class=\"hint\">Carpetas de tu carpeta de datos con un "
                 "resumen hecho desde la terminal, fuera de un proyecto. Se muestran como están; la aplicación no las "
                 "cambia.</p><table class=\"list\"><tr><th>Carpeta</th><th>Formato</th><th>Costo</th></tr>"
                 f"{items}</table></section>")
    return layout("Proyectos", body, "projects")


def project_page(project, meetings, knowledge):
    pid = quote(project["id"])
    rows = "".join(
        f'<tr><td>{e(m["record"]["date"])}</td><td><a href="/p/{pid}/m/{quote(m["record"]["id"])}">'
        f'{e(m["record"]["title"])}</a></td><td>{e(TYPE_NAMES.get(m["record"].get("meeting_type"), "—"))}</td>'
        f'{_result_cells(m["result"])}</tr>' for m in meetings) \
        or '<tr><td colspan="5" class="empty">Todavía no hay reuniones.</td></tr>'
    body = (f"<p class=\"crumbs\"><a href=\"/\">Proyectos</a> ›</p><h1>{e(project['name'])}</h1>"
            f"<p class=\"hint\">Cliente: {e(project.get('client') or '—')}</p>"
            f"<p><a class=\"button\" href=\"/p/{pid}/new\">Reunión nueva</a></p>"
            "<h2>Reuniones</h2><table class=\"list\"><tr><th>Fecha</th><th>Reunión</th><th>Tipo</th><th>Formato</th>"
            f"<th>Costo</th></tr>{rows}</table>"
            "<section><h2>Lo que el proyecto ya sabe</h2><p class=\"hint\">Lo que cada reunión deja y la próxima lee. "
            f"</p><div class=\"summary knowledge\">{markdown(knowledge)}</div></section>")
    return layout(project["name"], body, "projects")


def _cost_block(run):
    if not run:
        return ""
    stages = "".join(
        f"<tr><td>{e(stage.get('label', stage.get('name', '')))}</td><td>{e(STATE_NAMES.get(stage.get('state'), ''))}"
        f"</td><td>{float(stage.get('seconds', 0)):.0f} s</td><td>{money(float(stage.get('cost_usd', 0)))}</td></tr>"
        for stage in run.get("stages", []) if isinstance(stage, dict))
    return (f"<section class=\"card\"><h2>Lo que costó</h2><p><strong>{money(float(run.get('cost_usd', 0)))}</strong>"
            f" de un techo de {money(float(run.get('max_cost_usd', 0)))}, en {float(run.get('seconds', 0)):.0f} s."
            "</p><table class=\"list\"><tr><th>Etapa</th><th>Estado</th><th>Tiempo</th><th>Costo</th></tr>"
            f"{stages}</table></section>")


def result_page(title, crumbs, record, result, file_base, open_target):
    """A meeting's screen: `record` is its project record (None for a loose
    result), `result` what its folder holds (None when it has no folder)."""
    parts = [f"<p class=\"crumbs\">{crumbs}</p><h1>{e(title)}</h1>"]
    if record is not None:
        facts = [record.get("date", ""), TYPE_NAMES.get(record.get("meeting_type"), "")]
        if result:
            facts.append(FORMAT_NAMES.get(result["format"], ""))
        parts.append(f"<p class=\"hint\">{e(' · '.join(fact for fact in facts if fact))}</p>")
    if result and result["report"]:
        parts.append(
            f"<p class=\"actions\"><button type=\"button\" data-open=\"{e(open_target)}\">Abrir el Word</button> "
            f"<a class=\"button secondary\" href=\"{e(file_base)}summary.docx\" download>Descargar el Word</a>"
            "<span class=\"message\" role=\"status\"></span></p>")
    if result:
        parts.append(_cost_block(result.get("run")))
        frame_url = {name: f"{file_base}{name}" for name in result["frames"]}
        if result["summary"]:
            parts.append(f"<section class=\"summary\">{markdown(result['summary'], frame_url)}</section>")
        parts.append(f"<p class=\"hint\">{len(result['frames'])} imágenes en el informe, de "
                     f"{result['frames_total']} que quedaron del video.</p>")
    elif record is not None:
        points = "".join(f"<li>{e(point)}</li>" for point in record.get("key_points", []))
        parts.append("<p class=\"hint\">Esta reunión se cargó desde la terminal: su carpeta no quedó registrada en el "
                     "proyecto, así que acá se ve lo que el proyecto guardó de ella.</p>"
                     f"<section class=\"summary\"><p>{e(record.get('summary') or '(sin resumen)')}</p>"
                     + (f"<h3>Puntos clave</h3><ul>{points}</ul>" if points else "") + "</section>")
    return layout(title, "".join(parts), "projects")


def new_meeting_page(project, meeting_types, languages, max_cost):
    pid = e(project["id"])
    types = "".join(f'<option value="{e(t)}">{e(TYPE_NAMES.get(t, t))}</option>' for t in meeting_types)
    langs = "".join(f'<option value="{e(code)}">{e(LANGUAGE_NAMES.get(code, code))}</option>' for code in languages)
    body = (f"<p class=\"crumbs\"><a href=\"/\">Proyectos</a> › <a href=\"/p/{quote(project['id'])}\">"
            f"{e(project['name'])}</a> ›</p><h1>Reunión nueva</h1>"
            f"<form id=\"process\" class=\"card\" data-project=\"{pid}\">"
            "<label>Título <input name=\"title\" required maxlength=\"160\"></label>"
            "<label>Fecha <input name=\"date\" type=\"date\" required></label>"
            "<label>Transcripción <small>(el .docx de Teams, o un .txt con líneas [HH:MM:SS])</small>"
            "<input name=\"transcript\" type=\"file\" accept=\".docx,.txt\" required></label>"
            "<label>Video <small>(opcional: sin video sólo se puede hacer preguntas y respuestas)</small>"
            "<input name=\"recording\" type=\"file\" accept=\"video/*,.mp4,.mov,.mkv,.webm,.avi,.wmv,.m4v\"></label>"
            f"<label>Tipo de reunión <select name=\"meeting_type\"><option value=\"\">Sin tipo</option>{types}"
            "</select></label>"
            f"<label>Idioma del resultado <select name=\"language\"><option value=\"\">El de la reunión</option>"
            f"{langs}</select></label>"
            "<fieldset><legend>Formato</legend>"
            "<label class=\"inline\"><input type=\"radio\" name=\"format\" value=\"summary\" checked> Resumen</label>"
            "<label class=\"inline\"><input type=\"radio\" name=\"format\" value=\"qa\"> Preguntas y respuestas "
            "<small>(cada pregunta con su respuesta completa)</small></label></fieldset>"
            f"<label>Techo de gasto en dólares <input name=\"max_cost\" type=\"number\" min=\"0.01\" max=\"5\" "
            f"step=\"0.01\" value=\"{max_cost:.2f}\" required> <small>(si una etapa pudiera pasarlo, no se "
            "manda)</small></label>"
            "<button type=\"submit\">Procesar</button><p class=\"message\" role=\"status\"></p></form>")
    return layout("Reunión nueva", body, "projects")


def job_page(job_id):
    body = ("<h1>Procesando</h1>"
            f"<div id=\"job\" data-job=\"{e(job_id)}\" class=\"card\"><p class=\"hint\">Cargando…</p></div>"
            "<p class=\"hint\">Podés dejar esta página abierta; si la cerrás, el trabajo sigue mientras la ventana de "
            "MeetingTool siga abierta.</p>")
    return layout("Procesando", body, "projects")


def settings_page(key_length, template_name):
    key = (f"Hay una clave guardada ({key_length} caracteres). No se muestra nunca." if key_length
           else "No hay una clave guardada: sin ella no se puede procesar.")
    template = (f"La empresa usa la plantilla <strong>{e(template_name)}</strong>." if template_name
                else "Sin plantilla: los informes salen con un diseño neutro.")
    body = ("<h1>Ajustes</h1>"
            "<section class=\"card\"><h2>Clave de Gemini</h2>"
            f"<p id=\"key-status\">{e(key)}</p>"
            "<p class=\"hint\">Tiene que ser de un proyecto de Google Cloud con facturación activa: en el nivel gratuito "
            "Google puede usar lo que se le manda, y las reuniones son datos del cliente. Se guarda en el Administrador "
            "de credenciales de Windows.</p>"
            "<form data-api=\"/api/key\" data-then=\"reload\"><label>Clave nueva "
            "<input name=\"key\" type=\"password\" autocomplete=\"off\" required></label>"
            "<button type=\"submit\">Guardar la clave</button><p class=\"message\" role=\"status\"></p></form>"
            + ("<form data-api=\"/api/key/delete\" data-then=\"reload\" data-confirm=\"¿Borrar la clave guardada?\">"
               "<button type=\"submit\" class=\"secondary\">Borrar la clave</button>"
               "<p class=\"message\" role=\"status\"></p></form>" if key_length else "")
            + "</section><section class=\"card\"><h2>Plantilla de Word de la empresa</h2>"
            f"<p>{template}</p><p class=\"hint\">Un .docx o .dotx (nunca uno con macros) con el logo, el encabezado, "
            "los colores y las letras de la empresa; lo que tenga escrito en su hoja es la portada de cada informe."
            "</p><form id=\"template\"><label>Plantilla <input name=\"template\" type=\"file\" accept=\".docx,.dotx\" "
            "required></label><button type=\"submit\">Usar esta plantilla</button>"
            "<p class=\"message\" role=\"status\"></p></form>"
            + ("<form data-api=\"/api/template/remove\" data-then=\"reload\"><button type=\"submit\" "
               "class=\"secondary\">Dejar de usar la plantilla</button><p class=\"message\" role=\"status\"></p>"
               "</form>" if template_name else "")
            + "</section>")
    return layout("Ajustes", body, "settings")


def message_page(title, text, status_hint=""):
    body = f"<h1>{e(title)}</h1><p>{e(text)}</p>" + (f"<p class=\"hint\">{e(status_hint)}</p>" if status_hint else "")
    return layout(title, body)


def meeting_types():
    return list(writer.MEETING_TYPES)


def languages():
    return list(writer.SECTIONS)
