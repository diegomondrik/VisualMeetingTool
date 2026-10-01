"""The web server of the application: only this machine, and only its own page.

- It listens on 127.0.0.1 only, and refuses a request whose peer is not a
  loopback address.
- Every request needs the session cookie. The server makes a random token at
  each start and opens the browser on /open?token=...; that address sets the
  cookie (SameSite=Strict, HttpOnly), so a page of another site, which cannot
  know the token, never has it, and the browser does not send it with a
  request that page makes.
- A request whose Host is not the server's own address (a DNS rebinding), whose
  Origin is another, or whose Sec-Fetch-Site says another site made it, is
  refused before anything is read.
- A change is accepted only with the X-MeetingTool header and, for POST, a JSON
  body: a form of another site can send neither, and a script of another site
  cannot send them without a CORS permission the server never gives.
- Pages forbid being framed and run no inline script (Content-Security-Policy).

Every refusal happens in `refusal`, before any route runs. Everything the
server says is an entry of meetingtool.texts, in the application's language
(INGOL D-188, WI17).
"""

import hmac
import http.cookies
import http.server
import ipaddress
import json
import os
import secrets
import socket
import sys
import threading
import time
import webbrowser
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote, urlsplit

from meetingtool import texts
from meetingtool.app import company, jobs, library, pages
from meetingtool.projects import store
from meetingtool.reading import gemini

HOST = "127.0.0.1"
COOKIE = "meetingtool_session"
STATIC = Path(__file__).resolve().parent / "static"
STATIC_TYPES = {"app.js": "text/javascript; charset=utf-8", "style.css": "text/css; charset=utf-8"}
JSON_LIMIT = 1_000_000
DOCX_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
EXAMPLE_NAME = pages.EXAMPLE_NAME
UPLOAD_LIMITS = {"transcript": 50_000_000, "recording": 16_000_000_000, "template": 50_000_000,
                 "logo": company.LOGO_LIMIT}
UPLOAD_SUFFIXES = {"transcript": jobs.TRANSCRIPT_SUFFIXES, "recording": jobs.RECORDING_SUFFIXES,
                   "template": (".docx", ".dotx"), "logo": company.LOGO_SUFFIXES}
# Uploads of the settings, each to its own address; a meeting's go to /api/upload.
SETTING_UPLOADS = {"/api/template": "template", "/api/logo": "logo"}
CHUNK = 1 << 20
# A logo refused for being over 1 MB is still read up to this, so that the page says why.
LOGO_DROP_LIMIT = 32 * CHUNK
SECURITY_HEADERS = {
    "Content-Security-Policy": "default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self'; "
                               "connect-src 'self'; form-action 'self'; frame-ancestors 'none'; base-uri 'none'",
    "X-Frame-Options": "DENY",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "Cache-Control": "no-store",
    "Cross-Origin-Resource-Policy": "same-origin",
    "Cross-Origin-Opener-Policy": "same-origin",
}
CHANGES = ("POST", "PUT", "DELETE")


class Refused(texts.Failure):
    def __init__(self, status, key, **params):
        super().__init__(key, **params)
        self.status = status


def refusal(app, peer, method, path, headers):
    """Why the request is refused, as (status, the key of its message), or
    None."""
    try:
        if not ipaddress.ip_address(peer).is_loopback:
            return 403, "app.refused.not_local"
    except ValueError:
        return 403, "app.refused.not_local"
    if headers.get("Host", "") not in app.hosts:
        return 403, "app.refused.not_this_app"
    origin = headers.get("Origin")
    if origin is not None and origin not in app.origins:
        return 403, "app.refused.other_site"
    site = headers.get("Sec-Fetch-Site")
    if site is not None and site not in ("same-origin", "none"):
        return 403, "app.refused.other_site"
    if path == "/open" and method == "GET":
        return None
    cookie = http.cookies.SimpleCookie()
    try:
        cookie.load(headers.get("Cookie", ""))
    except http.cookies.CookieError:
        return 403, "app.refused.session"
    session = cookie.get(COOKIE)
    if session is None or not hmac.compare_digest(session.value.encode(), app.token.encode()):
        return 403, "app.refused.session"
    if method in CHANGES:
        if headers.get("X-MeetingTool") != "1":
            return 403, "app.refused.change_page"
        if method == "POST" and headers.get("Content-Type", "").split(";")[0].strip().lower() != "application/json":
            return 415, "app.refused.json_only"
    elif method not in ("GET", "HEAD"):
        return 405, "app.refused.method"
    return None


def _segments(path):
    parts = [unquote(part) for part in path.split("/")[1:]]
    if any(part in ("", ".", "..") or "/" in part or "\\" in part for part in parts) and path != "/":
        raise library.NotFound(path)
    return parts if path != "/" else []


class Handler(http.server.BaseHTTPRequestHandler):
    server_version = "MeetingTool"
    sys_version = ""

    def log_message(self, *args):
        pass

    @property
    def app(self):
        return self.server.app

    def view(self, session=True):
        """What every screen needs from the settings: the application's
        language and, for a request of the session, the company (a request
        refused before the session is checked learns nothing of the data
        folder but its language)."""
        if not session:
            return pages.View(company.language(self.app.data_dir))
        owner = company.company(self.app.data_dir)
        return pages.View(company.language(self.app.data_dir), owner.name, owner.logo is not None)

    # ── Answers ──────────────────────────────────────────────────────────────

    def _send(self, status, body, content_type, extra=()):
        self.send_response(status)
        for name, value in SECURITY_HEADERS.items():
            self.send_header(name, value)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        for name, value in extra:
            self.send_header(name, value)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _html(self, text, status=200, extra=()):
        self._send(status, text.encode("utf-8"), "text/html; charset=utf-8", extra)

    def _json(self, data, status=200):
        self._send(status, json.dumps(data, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")

    def _error(self, status, message, session=True):
        """Answer with what failed, in the application's language: `message`
        is a texts.Message (what came from outside it goes as `detail`), or
        text said as it is."""
        view = self.view(session)
        text, details = texts.said(message, view.language)
        if self.path.startswith("/api/"):
            self._json({"error": text, "detail": details}, status)
        else:
            self._html(pages.message_page(view, view.say("app.error.cannot_show"), text, details), status)

    def _file(self, path):
        if path.name in company.LOGO_TYPES:
            self._send(200, path.read_bytes(), company.LOGO_TYPES[path.name])
        elif path.suffix == ".docx":
            self._send(200, path.read_bytes(), DOCX_TYPE,
                       [("Content-Disposition", "attachment; filename=\"summary.docx\"")])
        else:
            self._send(200, path.read_bytes(), "image/jpeg")

    # ── Dispatch ─────────────────────────────────────────────────────────────

    def _handle(self):
        self._body_read = False
        address = urlsplit(self.path)
        refused = refusal(self.app, self.client_address[0], self.command, address.path, self.headers)
        if refused is not None:
            self._discard_body()
            return self._error(refused[0], texts.Message(refused[1]), session=False)
        try:
            if self.command in ("GET", "HEAD"):
                self._get(address)
            elif self.command == "POST":
                self._post(address.path, self._read_json())
            elif self.command == "PUT":
                self._put(address.path, parse_qs(address.query))
            else:
                raise library.NotFound(address.path)
        except library.NotFound:
            self._error(404, texts.Message("app.not_found"))
        except Refused as error:
            self._discard_body()
            self._error(error.status, error.message)
        except texts.Failure as error:
            self._error(400, error.message)
        except Exception as error:  # the page says what failed; the server keeps running
            self._error(500, texts.Message("app.unexpected", detail=texts.External(str(error))))

    do_GET = do_HEAD = do_POST = do_PUT = do_DELETE = do_OPTIONS = do_PATCH = _handle

    def _discard_body(self):
        """Read and drop what a refused request sent, when it is small, so the
        answer arrives instead of a reset connection; a bigger one is not read,
        and the connection is closed after the answer."""
        self.close_connection = True
        if getattr(self, "_body_read", False):
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            return
        if 0 < length <= JSON_LIMIT:
            self.rfile.read(length)
        self._body_read = True

    def _drop(self, length):
        """Read and drop a body that is refused for its size but not huge, so
        that the page gets the reason instead of a cut connection (a reset on
        Windows, the independent review of 5d4c63a, P1-1)."""
        left = length
        while left:
            chunk = self.rfile.read(min(CHUNK, left))
            if not chunk:
                break
            left -= len(chunk)
        self._body_read = True

    def _read_json(self):
        self._body_read = True
        try:
            length = int(self.headers.get("Content-Length", ""))
        except ValueError:
            raise Refused(411, "app.refused.no_length") from None
        if not 0 <= length <= JSON_LIMIT:
            raise Refused(413, "app.refused.too_big")
        try:
            data = json.loads(self.rfile.read(length) or b"{}")
        except ValueError:
            raise Refused(400, "app.refused.not_json") from None
        if not isinstance(data, dict):
            raise Refused(400, "app.refused.not_object")
        return data

    # ── GET ──────────────────────────────────────────────────────────────────

    def _get(self, address):
        app, data_dir = self.app, self.app.data_dir
        path = address.path
        if path == "/open":
            token = parse_qs(address.query).get("token", [""])[0]
            if not hmac.compare_digest(token.encode(), app.token.encode()):
                return self._error(403, texts.Message("app.refused.stale_link"), session=False)
            cookie = f"{COOKIE}={app.token}; Path=/; HttpOnly; SameSite=Strict"
            return self._send(303, b"", "text/plain", [("Location", "/"), ("Set-Cookie", cookie)])
        parts = _segments(path)
        view = self.view()
        if not parts:
            return self._html(pages.projects_page(view, library.projects(data_dir), library.loose(data_dir)))
        head = parts[0]
        if head == "static" and len(parts) == 2 and parts[1] in STATIC_TYPES:
            return self._send(200, (STATIC / parts[1]).read_bytes(), STATIC_TYPES[parts[1]])
        if head == "company" and parts[1:] == ["logo"]:
            logo = company.logo_path(data_dir)
            if logo is None:
                raise library.NotFound(path)
            return self._file(logo)
        if head == "settings" and len(parts) == 1:
            saved = app.read_key()
            try:
                template, problem = app.template_info(data_dir), ""
            except app.report_error as error:
                template, problem = None, error.text(view.language)
            return self._html(pages.settings_page(view, len(saved) if saved else 0, company.company(data_dir),
                                                  template, problem))
        if path == "/" + EXAMPLE_NAME:
            name = view.say("app.template.example_file")
            return self._send(200, app.example_template(), DOCX_TYPE,
                              [("Content-Disposition", f"attachment; filename=\"{name}\"")])
        if head == "job" and len(parts) == 2 and parts[1] in app.runner.jobs:
            return self._html(pages.job_page(view, parts[1]))
        if head == "api" and parts[1:2] == ["jobs"] and len(parts) == 3 and parts[2] in app.runner.jobs:
            return self._json(app.runner.jobs[parts[2]].as_dict(view.language))
        if head == "api" and parts[1:] == ["running"]:
            job = app.runner.running()
            return self._json({"job": job.as_dict(view.language) if job else None})
        if head == "p" and len(parts) >= 2:
            project_id = parts[1]
            project = library.project(data_dir, project_id)
            if len(parts) == 2:
                return self._html(pages.project_page(view, project, library.meetings(data_dir, project_id),
                                                     library.knowledge(data_dir, project_id)))
            if parts[2:] == ["new"]:
                return self._html(pages.new_meeting_page(view, project, pages.meeting_types(), pages.languages(),
                                                         jobs.DEFAULT_MAX_COST_USD))
            if parts[2] == "m" and len(parts) == 4:
                entry = library.meeting(data_dir, project_id, parts[3])
                record = entry["record"]
                base = f"/p/{quote(project_id)}/m/{quote(record['id'])}/f/"
                return self._html(pages.result_page(view, record["title"], pages.project_crumbs(view, project),
                                                    record, entry["result"], base, f"{project_id}/{record['id']}"))
            if parts[2] == "m" and len(parts) == 6 and parts[4] == "f":
                return self._file(library.meeting_file(data_dir, project_id, parts[3], parts[5]))
        if head == "r" and len(parts) >= 2:
            if len(parts) == 2:
                entry = library.loose_result(data_dir, parts[1])
                return self._html(pages.result_page(view, parts[1], pages.loose_crumbs(view), None, entry["result"],
                                                    f"/r/{quote(parts[1])}/f/", parts[1]))
            if len(parts) == 4 and parts[2] == "f":
                return self._file(library.loose_file(data_dir, parts[1], parts[3]))
        raise library.NotFound(path)

    # ── POST ─────────────────────────────────────────────────────────────────

    def _post(self, path, data):
        app, data_dir = self.app, self.app.data_dir
        if path == "/api/projects":
            name, client = data.get("name", ""), data.get("client", "")
            if not isinstance(name, str) or not isinstance(client, str):
                raise jobs.JobError("app.request.project_not_text")
            record = store.create_project(data_dir, name, client)
            return self._json({"id": record["id"]})
        if path == "/api/key":
            key = data.get("key", "")
            if not isinstance(key, str) or not key.strip():
                raise jobs.JobError("app.key.paste")
            gemini.check_key(key.strip())
            app.save_key(key.strip())
            return self._json({"saved": True})
        if path == "/api/key/delete":
            return self._json({"deleted": bool(app.delete_key())})
        if path == "/api/template/remove":
            return self._json({"removed": app.remove_template(data_dir)})
        if path == "/api/company":
            return self._json({"name": company.set_company_name(data_dir, data.get("name", ""))})
        if path == "/api/logo/remove":
            return self._json({"removed": company.remove_logo(data_dir)})
        if path == "/api/language":
            company.set_language(data_dir, data.get("language"))
            return self._json({"language": data["language"]})
        if path == "/api/process":
            try:
                request = jobs.check_request(data, data_dir, app.uploads, pages.meeting_types(), pages.languages())
                job = app.runner.start(request)
            except jobs.JobError:
                app.uploads.discard([data.get("transcript"), data.get("recording")])
                raise
            return self._json({"job": job.id})
        if path == "/api/open":
            target = data.get("target", "")
            if not isinstance(target, str):
                raise library.NotFound(path)
            parts = target.split("/")
            report = (library.meeting_file(data_dir, parts[0], parts[1], library.REPORT_NAME) if len(parts) == 2
                      else library.loose_file(data_dir, parts[0], library.REPORT_NAME))
            app.opener(report)
            return self._json({"opened": True})
        raise library.NotFound(path)

    # ── PUT ──────────────────────────────────────────────────────────────────

    def _put(self, path, query):
        app = self.app
        kind = SETTING_UPLOADS[path] if path in SETTING_UPLOADS else (
            query.get("kind", [""])[0] if path == "/api/upload" else None)
        if kind not in UPLOAD_LIMITS or (path == "/api/upload" and kind in SETTING_UPLOADS.values()):
            raise library.NotFound(path)
        name = query.get("name", [""])[0]
        suffix = Path(name).suffix.lower()
        if kind == "logo" and suffix == ".svg":
            raise Refused(415, "app.logo.svg")
        if suffix not in UPLOAD_SUFFIXES[kind]:
            raise Refused(415, "app.refused.bad_file", kinds=", ".join(UPLOAD_SUFFIXES[kind]))
        try:
            length = int(self.headers.get("Content-Length", ""))
        except ValueError:
            raise Refused(411, "app.refused.no_file_length") from None
        if kind == "logo" and length > UPLOAD_LIMITS[kind]:
            if length <= LOGO_DROP_LIMIT:
                self._drop(length)
            raise Refused(413, "app.logo.too_big")
        if not 0 < length <= UPLOAD_LIMITS[kind]:
            raise Refused(413, "app.refused.empty_or_big")
        target = app.uploads.new_path(suffix)
        self._body_read = True  # from here on, a failure closes the connection
        try:
            with open(target, "wb") as handle:
                left = length
                while left:
                    chunk = self.rfile.read(min(CHUNK, left))
                    if not chunk:
                        raise Refused(400, "app.refused.cut")
                    handle.write(chunk)
                    left -= len(chunk)
            if kind == "template":
                app.set_template(target, app.data_dir, name=name)
                return self._json({"template": Path(name).name})
            if kind == "logo":
                company.set_logo(app.data_dir, target.read_bytes(), name)
                return self._json({"logo": True})
        except BaseException:
            target.unlink(missing_ok=True)
            raise
        finally:
            if kind in SETTING_UPLOADS.values():
                target.unlink(missing_ok=True)
        return self._json({"upload": target.name})


class Server(http.server.ThreadingHTTPServer):
    """No other process may take the same port while this one holds it
    (Windows lets one with SO_REUSEADDR do so)."""

    allow_reuse_address = False
    daemon_threads = True

    def server_bind(self):
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


class DataFolderInUse(texts.Failure):
    """Another MeetingTool application holds this data folder."""


class DataFolderLock:
    """One application per data folder: the lock is held by an open file for
    the life of the process, and the system drops it when the process ends,
    however it ends."""

    NAME = ".meetingtool-app.lock"

    def __init__(self, data_dir):
        self.path = Path(data_dir) / self.NAME
        self.handle = None

    def acquire(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        handle = open(self.path, "a+b")
        try:
            if os.name == "nt":
                import msvcrt

                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            handle.close()
            raise DataFolderInUse("app.data_folder_in_use", folder=str(self.path.parent)) from None
        self.handle = handle
        return self

    def release(self):
        if self.handle is not None:
            self.handle.close()
            self.handle = None


class App:
    """The server and what it needs. Everything that touches the key, Gemini or
    the machine can be replaced, so the tests need no key and no network."""

    def __init__(self, data_dir, *, port=0, token=None, read_key=None, save_key=None, delete_key=None,
                 endpoint=gemini.ENDPOINT, sleep=time.sleep, retry_delays=None, opener=None):
        from meetingtool.reading import credentials
        from meetingtool.report import document

        self.data_dir = store.check_data_dir(Path(data_dir))
        self.token = token or secrets.token_urlsafe(32)
        self.read_key = read_key or credentials.read_key
        self.save_key = save_key or credentials.save_key
        self.delete_key = delete_key or credentials.delete_key
        self.report_error = document.ReportError
        self.template_info, self.set_template = document.template_info, document.set_template
        self.remove_template, self.example_template = document.remove_template, document.example_template
        self.opener = opener or open_with_the_system
        self.uploads = jobs.Uploads(self.data_dir)
        self.runner = jobs.Runner(self.data_dir, self.read_key, endpoint=endpoint, sleep=sleep,
                                  retry_delays=retry_delays)
        self.httpd = Server((HOST, port), Handler)
        self.httpd.app = self
        self.port = self.httpd.server_address[1]
        self.hosts = {f"{HOST}:{self.port}", f"localhost:{self.port}"}
        self.origins = {f"http://{host}" for host in self.hosts}
        self.thread = None

    @property
    def url(self):
        return f"http://{HOST}:{self.port}"

    @property
    def launch_url(self):
        return f"{self.url}/open?token={self.token}"

    def start(self):
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()
        return self

    def stop(self):
        self.httpd.shutdown()
        self.httpd.server_close()


def open_with_the_system(path):
    if not hasattr(os, "startfile"):
        raise jobs.JobError("app.open.windows_only")
    os.startfile(str(path))  # nosec: a report of the data folder, found by identifiers


def serve(data_dir=None, port=0, open_browser=True):
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    data_dir = Path(data_dir or store.default_data_dir())
    language = company.language(data_dir)  # the application's window speaks the application's language

    def say(key, **params):
        return texts.Message(key, **params).text(language)

    def fail(error):
        text, details = texts.said(texts.outside(error), language)
        print(say("app.console.error", error=text), file=sys.stderr)
        for detail in details:
            print(say("app.detail", detail=detail), file=sys.stderr)
        return 2

    try:
        store.check_data_dir(data_dir)
        lock = DataFolderLock(data_dir).acquire()
    except (store.ProjectError, DataFolderInUse, OSError) as error:
        return fail(error)
    try:
        # What a session closed during a run, or its unused uploads, left.
        jobs.clear_leftovers(data_dir)
        app = App(data_dir, port=port)
    except (store.ProjectError, OSError) as error:
        lock.release()
        return fail(error)
    print(say("app.console.open", url=app.url))
    print(say("app.console.paste", url=app.launch_url))
    print(say("app.console.keep"), flush=True)  # a console that is not a terminal would keep them
    if open_browser:
        webbrowser.open(app.launch_url)
    try:
        app.httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        app.httpd.server_close()
        lock.release()
    return 0
