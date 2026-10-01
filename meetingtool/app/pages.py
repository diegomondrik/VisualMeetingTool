"""The screens, as HTML. Everything that comes from a file (a summary written
by Gemini from a client's meeting, a project's name, the company's name) is
escaped before it is placed; the pages carry no inline script, and the
actions are done by static/app.js.

Every text of a screen is an entry of meetingtool.texts, in the language the
application is set to (INGOL D-188, WI17): a View says them. The texts the
page's script needs (those whose key starts with "js.") travel with the page,
in the data-texts attribute of its body."""

import html
import json
import re
from urllib.parse import quote

from meetingtool import texts
from meetingtool.app.jobs import STAGE_KEYS
from meetingtool.summary import writer

EXAMPLE_NAME = "plantilla-de-ejemplo.docx"
BRAND = "MeetingTool"
FIELD_KEYS = {"client": "app.field.client", "project": "app.field.project", "meeting": "app.field.meeting",
              "date": "app.field.date", "type": "app.field.type"}
TYPE_KEYS = {"presale": "app.type.presale", "negotiation": "app.type.negotiation",
             "requirements": "app.type.requirements", "kickoff": "app.type.kickoff", "status": "app.type.status",
             "technical": "app.type.technical", "training": "app.type.training", "discovery": "app.type.discovery"}
FORMAT_KEYS = {"summary": "app.format.summary", "qa": "app.format.qa"}
STATE_KEYS = {"pending": "app.state.pending", "running": "app.state.running", "done": "app.state.done",
              "skipped": "app.state.skipped", "failed": "app.state.failed"}
LANGUAGE_KEYS = {"es": "app.language.es", "en": "app.language.en"}
DROPPED_KEYS = {("index", True): "app.template.dropped_index_one", ("index", False): "app.template.dropped_index",
                ("marker", True): "app.template.dropped_marker_one", ("marker", False): "app.template.dropped_marker"}

_HEADING = re.compile(r"^(#{1,6})\s*(\S.*?)\s*#*\s*$")
_BULLET = re.compile(r"^(\s*)[-*+]\s+(.*)$")
_NUMBERED = re.compile(r"^(\s*)\d+[.)]\s+(.*)$")
_RULE = re.compile(r"^\s*([-*_])(\s*\1){2,}\s*$")
_SEPARATOR = re.compile(r"^\s*\|?[\s:|-]+\|?\s*$")
_FRAME = re.compile(r"\[(frame_\d+_t(\d{2})-(\d{2})-(\d{2})\.jpg)\]")


def e(value):
    return html.escape(str(value), quote=True)


class View:
    """What every screen needs: the language it speaks and the company it
    shows (a name, and whether there is a logo)."""

    def __init__(self, language=texts.DEFAULT_LANGUAGE, company_name="", has_logo=False):
        self.language = language if language in texts.LANGUAGES else texts.DEFAULT_LANGUAGE
        self.company_name = company_name or ""
        self.has_logo = has_logo

    def say(self, key, **params):
        """An entry as plain text, not escaped."""
        return texts.Message(key, **params).text(self.language)

    def t(self, key, **params):
        """An entry, escaped for a page."""
        return e(self.say(key, **params))

    def markup(self, key, **params):
        """An entry that holds markup of its own: the data is escaped, the
        entry is not."""
        return self.say(key, **{name: _Markup(e(value)) for name, value in params.items()})

    def name(self, keys, value, fallback="—"):
        """The name of a known value (a type, a format...), or the fallback."""
        return self.say(keys[value]) if value in keys else fallback

    def money(self, value):
        text = f"US${value:,.3f}"
        if self.language == "es":
            text = text.replace(",", "_").replace(".", ",").replace("_", ".")
        return text

    def day(self, utc):
        """'2026-09-30T12:57:00Z' as its language writes a day; '?' for a
        record edited by hand."""
        try:
            year, month, day = (int(part) for part in utc[:10].split("-"))
        except ValueError:
            return "?"
        return self.say("app.day", day=day, month=month, year=year)

    def script_texts(self):
        """The entries the page's script says, as they are written: it puts
        their data in ({percent}...) itself."""
        return json.dumps({key: text for key, text in texts.catalog(self.language).items() if key.startswith("js.")},
                          ensure_ascii=False)


class _Markup(texts.External):
    """Escaped data for an entry that holds markup: placed as it is."""


def clock(hours, minutes, seconds):
    hours = int(hours)
    return f"{hours}:{minutes}:{seconds}" if hours else f"{int(minutes)}:{seconds}"


def _inline(view, text, frame_url, seen):
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
        return f'<span class="frame-ref">[{view.t("app.frame.mention", clock=clock(*match.groups()[1:]))}]</span>'

    return _FRAME.sub(frame, escaped)


def markdown(view, text, frame_url=None):
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
                placed.append(f'<figure><img src="{e(frame_url[name])}" '
                              f'alt="{view.t("app.frame.mention", clock=minute)}" loading="lazy">'
                              f"<figcaption>{view.t('app.frame.caption', clock=minute)}</figcaption></figure>")
        return "".join(placed)

    def block(open_tag, inner_lines, close_tag, joiner="<br>"):
        seen = []
        inner = joiner.join(_inline(view, line, frame_url, seen) for line in inner_lines)
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
            cells_html.append("<tr>" + "".join(f"<{tag}>{_inline(view, c, frame_url, seen)}</{tag}>" for c in cells)
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


def layout_page(view, title, body, active=""):
    nav = "".join(f'<a href="{href}"{" class=active" if active == key else ""}>{view.t(label)}</a>'
                  for key, href, label in (("projects", "/", "app.nav.projects"),
                                           ("settings", "/settings", "app.nav.settings")))
    company = ""
    if view.has_logo:
        company += '<img class="logo" src="/company/logo" alt="">'
    if view.company_name:
        company += f'<span class="company">{e(view.company_name)}</span>'
    brand = f'<span class="product">{BRAND}</span>' if company else BRAND
    tab = " · ".join(part for part in (title, view.company_name, BRAND) if part)
    return (f"<!doctype html>\n<html lang=\"{view.language}\"><head><meta charset=\"utf-8\">"
            "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
            f"<title>{e(tab)}</title><link rel=\"stylesheet\" href=\"/static/style.css\">"
            "<script src=\"/static/app.js\" defer></script></head>"
            f"<body data-texts=\"{e(view.script_texts())}\">"
            f"<header><a class=\"brand\" href=\"/\">{company}{brand}</a><nav>{nav}</nav></header>"
            "<div id=\"running\" class=\"banner\" hidden></div>"
            f"<main>{body}</main><footer>{view.t('app.footer')}</footer></body></html>")


def _result_cells(view, result):
    if not result:
        return "<td>—</td><td>—</td>"
    run = result.get("run") or {}
    cost = view.money(run["cost_usd"]) if isinstance(run.get("cost_usd"), (int, float)) else "—"
    return f"<td>{e(view.name(FORMAT_KEYS, result['format']))}</td><td>{cost}</td>"


def projects_page(view, projects, loose):
    rows = "".join(
        f'<tr><td><a href="/p/{quote(p["id"])}">{e(p["name"])}</a></td><td>{e(p.get("client") or "—")}</td></tr>'
        for p in projects) or f'<tr><td colspan="2" class="empty">{view.t("app.projects.none")}</td></tr>'
    body = (f"<h1>{view.t('app.projects.title')}</h1><table class=\"list\"><tr><th>{view.t('app.col.project')}</th>"
            f"<th>{view.t('app.col.client')}</th></tr>{rows}</table>"
            f"<section class=\"card\"><h2>{view.t('app.projects.new')}</h2>"
            "<form data-api=\"/api/projects\" data-then=\"project\">"
            f"<label>{view.t('app.projects.name')} <input name=\"name\" required maxlength=\"120\"></label>"
            f"<label>{view.t('app.projects.client')} <input name=\"client\" maxlength=\"120\"></label>"
            f"<button type=\"submit\">{view.t('app.projects.create')}</button>"
            "<p class=\"message\" role=\"status\"></p></form></section>")
    if loose:
        items = "".join(
            f'<tr><td><a href="/r/{quote(item["name"])}">{e(item["name"])}</a></td>'
            f'{_result_cells(view, item["result"])}</tr>' for item in loose)
        body += (f"<section><h2>{view.t('app.loose.title')}</h2><p class=\"hint\">{view.t('app.loose.hint')}</p>"
                 f"<table class=\"list\"><tr><th>{view.t('app.col.folder')}</th><th>{view.t('app.col.format')}</th>"
                 f"<th>{view.t('app.col.cost')}</th></tr>{items}</table></section>")
    return layout_page(view, view.say("app.projects.title"), body, "projects")


def project_page(view, project, meetings, knowledge):
    pid = quote(project["id"])
    rows = "".join(
        f'<tr><td>{e(m["record"]["date"])}</td><td><a href="/p/{pid}/m/{quote(m["record"]["id"])}">'
        f'{e(m["record"]["title"])}</a></td><td>{e(view.name(TYPE_KEYS, m["record"].get("meeting_type")))}</td>'
        f'{_result_cells(view, m["result"])}</tr>' for m in meetings) \
        or f'<tr><td colspan="5" class="empty">{view.t("app.project.no_meetings")}</td></tr>'
    body = (f"<p class=\"crumbs\"><a href=\"/\">{view.t('app.nav.projects')}</a> ›</p><h1>{e(project['name'])}</h1>"
            f"<p class=\"hint\">{view.t('app.project.client', client=project.get('client') or '—')}</p>"
            f"<p><a class=\"button\" href=\"/p/{pid}/new\">{view.t('app.project.new_meeting')}</a></p>"
            f"<h2>{view.t('app.project.meetings')}</h2><table class=\"list\"><tr><th>{view.t('app.col.date')}</th>"
            f"<th>{view.t('app.col.meeting')}</th><th>{view.t('app.col.type')}</th>"
            f"<th>{view.t('app.col.format')}</th><th>{view.t('app.col.cost')}</th></tr>{rows}</table>"
            f"<section><h2>{view.t('app.project.knowledge')}</h2>"
            f"<p class=\"hint\">{view.t('app.project.knowledge_hint')}</p>"
            f"<div class=\"summary knowledge\">{markdown(view, knowledge)}</div></section>")
    return layout_page(view, project["name"], body, "projects")


def stage_label(view, stage):
    """A stage's name in the page's language; a stage the application does not
    know keeps the label its record has."""
    name = stage.get("name")
    return view.say(STAGE_KEYS[name]) if name in STAGE_KEYS else str(stage.get("label", name or ""))


def _cost_block(view, run):
    if not run:
        return ""
    stages = "".join(
        f"<tr><td>{e(stage_label(view, stage))}</td><td>{e(view.name(STATE_KEYS, stage.get('state'), ''))}</td>"
        f"<td>{float(stage.get('seconds', 0)):.0f} s</td><td>{view.money(float(stage.get('cost_usd', 0)))}</td></tr>"
        for stage in run.get("stages", []) if isinstance(stage, dict))
    total = view.markup("app.cost.total_html", spent=view.money(float(run.get("cost_usd", 0))),
                        ceiling=view.money(float(run.get("max_cost_usd", 0))),
                        seconds=f"{float(run.get('seconds', 0)):.0f}")
    return (f"<section class=\"card\"><h2>{view.t('app.cost.title')}</h2><p>{total}</p>"
            f"<table class=\"list\"><tr><th>{view.t('app.col.stage')}</th><th>{view.t('app.col.state')}</th>"
            f"<th>{view.t('app.col.time')}</th><th>{view.t('app.col.cost')}</th></tr>{stages}</table></section>")


def project_crumbs(view, project):
    return (f"<a href=\"/\">{view.t('app.nav.projects')}</a> › <a href=\"/p/{quote(project['id'])}\">"
            f"{e(project['name'])}</a> ›")


def loose_crumbs(view):
    return f"<a href=\"/\">{view.t('app.nav.projects')}</a> › {view.t('app.loose.title')} ›"


def result_page(view, title, crumbs, record, result, file_base, open_target):
    """A meeting's screen: `record` is its project record (None for a loose
    result), `result` what its folder holds (None when it has no folder)."""
    parts = [f"<p class=\"crumbs\">{crumbs}</p><h1>{e(title)}</h1>"]
    if record is not None:
        facts = [record.get("date", ""), view.name(TYPE_KEYS, record.get("meeting_type"), "")]
        if result:
            facts.append(view.name(FORMAT_KEYS, result["format"], ""))
        parts.append(f"<p class=\"hint\">{e(' · '.join(fact for fact in facts if fact))}</p>")
    if result and result["report"]:
        parts.append(
            f"<p class=\"actions\"><button type=\"button\" data-open=\"{e(open_target)}\">"
            f"{view.t('app.result.open_word')}</button> "
            f"<a class=\"button secondary\" href=\"{e(file_base)}summary.docx\" download>"
            f"{view.t('app.result.download_word')}</a><span class=\"message\" role=\"status\"></span></p>")
    if result:
        parts.append(_cost_block(view, result.get("run")))
        frame_url = {name: f"{file_base}{name}" for name in result["frames"]}
        if result["summary"]:
            parts.append(f"<section class=\"summary\">{markdown(view, result['summary'], frame_url)}</section>")
        shown = view.t("app.result.images", shown=len(result["frames"]), total=result["frames_total"])
        parts.append(f"<p class=\"hint\">{shown}</p>")
    elif record is not None:
        points = "".join(f"<li>{e(point)}</li>" for point in record.get("key_points", []))
        parts.append(f"<p class=\"hint\">{view.t('app.result.from_terminal')}</p>"
                     f"<section class=\"summary\"><p>{e(record.get('summary') or view.say('app.result.no_summary'))}"
                     "</p>" + (f"<h3>{view.t('app.result.key_points')}</h3><ul>{points}</ul>" if points else "")
                     + "</section>")
    return layout_page(view, title, "".join(parts), "projects")


def new_meeting_page(view, project, meeting_types, languages, max_cost):
    pid = e(project["id"])
    types = "".join(f'<option value="{e(t)}">{e(view.name(TYPE_KEYS, t, t))}</option>' for t in meeting_types)
    langs = "".join(f'<option value="{e(code)}">{e(view.name(LANGUAGE_KEYS, code, code))}</option>'
                    for code in languages)
    body = (f"<p class=\"crumbs\">{project_crumbs(view, project)}</p><h1>{view.t('app.new.title')}</h1>"
            f"<form id=\"process\" class=\"card\" data-project=\"{pid}\">"
            f"<label>{view.t('app.new.meeting_title')} <input name=\"title\" required maxlength=\"160\"></label>"
            f"<label>{view.t('app.new.date')} <input name=\"date\" type=\"date\" required></label>"
            f"<label>{view.t('app.new.transcript')} <small>{view.t('app.new.transcript_hint')}</small>"
            "<input name=\"transcript\" type=\"file\" accept=\".docx,.txt\" required></label>"
            f"<label>{view.t('app.new.recording')} <small>{view.t('app.new.recording_hint')}</small>"
            "<input name=\"recording\" type=\"file\" accept=\"video/*,.mp4,.mov,.mkv,.webm,.avi,.wmv,.m4v\"></label>"
            f"<label>{view.t('app.new.type')} <select name=\"meeting_type\"><option value=\"\">"
            f"{view.t('app.new.no_type')}</option>{types}</select></label>"
            f"<label>{view.t('app.new.language')} <select name=\"language\"><option value=\"\">"
            f"{view.t('app.new.meeting_language')}</option>{langs}</select></label>"
            f"<fieldset><legend>{view.t('app.col.format')}</legend>"
            "<label class=\"inline\"><input type=\"radio\" name=\"format\" value=\"summary\" checked> "
            f"{view.t('app.format.summary')}</label>"
            "<label class=\"inline\"><input type=\"radio\" name=\"format\" value=\"qa\"> "
            f"{view.t('app.format.qa')} <small>{view.t('app.new.qa_hint')}</small></label></fieldset>"
            f"<label>{view.t('app.new.ceiling')} <input name=\"max_cost\" type=\"number\" min=\"0.01\" max=\"5\" "
            f"step=\"0.01\" value=\"{max_cost:.2f}\" required> <small>{view.t('app.new.ceiling_hint')}</small></label>"
            f"<button type=\"submit\">{view.t('app.new.process')}</button><p class=\"message\" role=\"status\"></p>"
            "</form>")
    return layout_page(view, view.say("app.new.title"), body, "projects")


def job_page(view, job_id):
    body = (f"<h1>{view.t('app.job.title')}</h1>"
            f"<div id=\"job\" data-job=\"{e(job_id)}\" class=\"card\"><p class=\"hint\">{view.t('app.job.loading')}</p>"
            f"</div><p class=\"hint\">{view.t('app.job.hint')}</p>")
    return layout_page(view, view.say("app.job.title"), body, "projects")


def _template_block(view, info, problem):
    if problem:
        return (f"<p>{view.t('app.template.unusable', problem=problem)}</p>"
                f"<p class=\"hint\">{view.t('app.template.unusable_hint')}</p>")
    if info is None:
        return f"<p>{view.t('app.template.none')}</p>"
    if info.name:
        named = view.markup("app.template.named_html", name=info.name, day=view.day(info.set_utc or ""))
    else:
        named = view.t("app.template.unnamed")
    fields = texts.Joined([texts.Message(FIELD_KEYS[kind]) for kind in info.fields], ", ")
    understood = [view.t("app.template.fields", fields=fields) if info.fields else view.t("app.template.no_fields")]
    understood.append(view.t("app.template.toc" if info.tables_of_contents else "app.template.no_toc"))
    if info.start and info.dropped:
        where = "index" if info.start == "index" else "marker"
        understood.append(view.t(DROPPED_KEYS[where, info.dropped == 1], count=info.dropped))
    elif not info.start:
        understood.append(view.t("app.template.all_cover"))
    return f"<p>{named}</p><ul class=\"understood\">" + "".join(f"<li>{item}</li>" for item in understood) + "</ul>"


def _company_block(view, company):
    logo = (f"<p>{view.t('app.company.logo_current')} <img class=\"logo-preview\" src=\"/company/logo\" alt=\"\"></p>"
            if company.logo else f"<p>{view.t('app.company.no_logo')}</p>")
    return (f"<section class=\"card\"><h2>{view.t('app.company.title')}</h2>"
            f"<p class=\"hint\">{view.t('app.company.hint')}</p>"
            "<form data-api=\"/api/company\" data-then=\"reload\"><label>"
            f"{view.t('app.company.name')} <input name=\"name\" maxlength=\"{company.NAME_LIMIT}\" "
            f"value=\"{e(company.name)}\"> <small>{view.t('app.company.name_hint')}</small></label>"
            f"<button type=\"submit\">{view.t('app.company.save_name')}</button>"
            "<p class=\"message\" role=\"status\"></p></form>"
            f"{logo}<form id=\"logo\"><label>{view.t('app.company.logo')} "
            "<input name=\"logo\" type=\"file\" accept=\".png,.jpg,.jpeg\" required></label>"
            f"<button type=\"submit\">{view.t('app.company.use_logo')}</button>"
            "<p class=\"message\" role=\"status\"></p></form>"
            + ("<form data-api=\"/api/logo/remove\" data-then=\"reload\"><button type=\"submit\" class=\"secondary\">"
               f"{view.t('app.company.remove_logo')}</button><p class=\"message\" role=\"status\"></p></form>"
               if company.logo else "")
            + "</section>")


def _language_block(view):
    options = "".join(f'<option value="{code}"{" selected" if code == view.language else ""}>'
                      f'{e(view.name(LANGUAGE_KEYS, code, code))}</option>' for code in texts.LANGUAGES)
    return (f"<section class=\"card\"><h2>{view.t('app.settings.language')}</h2>"
            f"<p class=\"hint\">{view.t('app.settings.language_hint')}</p>"
            f"<form data-api=\"/api/language\" data-then=\"reload\"><label>{view.t('app.settings.language')} "
            f"<select name=\"language\">{options}</select></label>"
            f"<button type=\"submit\">{view.t('app.settings.language_save')}</button>"
            "<p class=\"message\" role=\"status\"></p></form></section>")


def settings_page(view, key_length, company, template_info=None, template_problem=""):
    key = (view.t("app.key.saved", length=key_length) if key_length else view.t("app.key.none"))
    template = _template_block(view, template_info, template_problem)
    kept = template_info is not None or bool(template_problem)
    body = (f"<h1>{view.t('app.settings.title')}</h1>"
            + _language_block(view) + _company_block(view, company)
            + f"<section class=\"card\"><h2>{view.t('app.key.title')}</h2>"
            f"<p id=\"key-status\">{key}</p><p class=\"hint\">{view.t('app.key.hint')}</p>"
            f"<form data-api=\"/api/key\" data-then=\"reload\"><label>{view.t('app.key.new')} "
            "<input name=\"key\" type=\"password\" autocomplete=\"off\" required></label>"
            f"<button type=\"submit\">{view.t('app.key.save')}</button><p class=\"message\" role=\"status\"></p></form>"
            + ("<form data-api=\"/api/key/delete\" data-then=\"reload\" "
               f"data-confirm=\"{view.t('app.key.delete_confirm')}\">"
               f"<button type=\"submit\" class=\"secondary\">{view.t('app.key.delete')}</button>"
               "<p class=\"message\" role=\"status\"></p></form>" if key_length else "")
            + f"</section><section class=\"card\"><h2>{view.t('app.template.title')}</h2>"
            f"{template}<p class=\"hint\">{view.t('app.template.hint')} "
            f"<a href=\"/{e(EXAMPLE_NAME)}\" download>{view.t('app.template.example')}</a>"
            f"{view.t('app.template.example_after')}</p>"
            f"<form id=\"template\"><label>{view.t('app.template.file')} <input name=\"template\" type=\"file\" "
            f"accept=\".docx,.dotx\" required></label><button type=\"submit\">{view.t('app.template.use')}</button>"
            "<p class=\"message\" role=\"status\"></p></form>"
            + ("<form data-api=\"/api/template/remove\" data-then=\"reload\"><button type=\"submit\" "
               f"class=\"secondary\">{view.t('app.template.remove')}</button><p class=\"message\" role=\"status\"></p>"
               "</form>" if kept else "")
            + "</section>")
    return layout_page(view, view.say("app.settings.title"), body, "settings")


def message_page(view, title, text, details=()):
    body = (f"<h1>{e(title)}</h1><p>{e(text)}</p>"
            + "".join(f"<p class=\"hint detail\">{view.t('app.detail', detail=detail)}</p>" for detail in details))
    return layout_page(view, title, body)


def meeting_types():
    return list(writer.MEETING_TYPES)


def languages():
    return list(writer.SECTIONS)
