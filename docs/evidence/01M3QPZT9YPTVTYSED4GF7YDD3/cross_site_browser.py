"""WI15-AC02 in a real browser: a page of another site, open in the same
browser as the application, tries to read it and to change it.

Starts the application over an invented data folder, and a second server on
another origin (http://localhost:<other port>) with an attacking page. A
headless Microsoft Edge with a profile of its own (never the user's) opens,
through its debugging port, first the launch address (so the browser holds
the session cookie, as the user's does) and then the attacking page, which
reports what each attempt obtained. The application's side is then checked:
nothing was created, the key was not touched.

    python docs/evidence/01M3QPZT9YPTVTYSED4GF7YDD3/cross_site_browser.py
"""

import http.server
import json
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPOSITORY))

from meetingtool.app import server  # noqa: E402
from meetingtool.projects import store  # noqa: E402

EDGE = Path("C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe")
ATTACKS = """
const APP = "__APP__";
const results = {};
async function attempt(name, run) {
  try { results[name] = await run(); } catch (error) { results[name] = "blocked: " + error.name; }
}
function report() {
  return fetch("/report", {method: "POST", body: JSON.stringify(results)});
}
(async () => {
  await attempt("read the projects page with fetch", async () => {
    const r = await fetch(APP + "/", {credentials: "include"});
    return "READ " + r.status + " " + (await r.text()).slice(0, 40);
  });
  await attempt("read the running job with fetch", async () => {
    const r = await fetch(APP + "/api/running", {credentials: "include"});
    return "READ " + r.status;
  });
  await attempt("create a project with JSON and the header", async () => {
    const r = await fetch(APP + "/api/projects", {method: "POST", credentials: "include",
      headers: {"Content-Type": "application/json", "X-MeetingTool": "1"}, body: JSON.stringify({name: "Intruso JSON"})});
    return "SENT " + r.status;
  });
  await attempt("create a project without reading the answer (no-cors)", async () => {
    await fetch(APP + "/api/projects", {method: "POST", mode: "no-cors", credentials: "include",
      headers: {"Content-Type": "text/plain"}, body: JSON.stringify({name: "Intruso no-cors"})});
    return "sent, answer unreadable (checked on the server)";
  });
  await attempt("save a key without reading the answer (no-cors)", async () => {
    await fetch(APP + "/api/key", {method: "POST", mode: "no-cors", credentials: "include",
      headers: {"Content-Type": "text/plain"}, body: JSON.stringify({key: "AIzaINTRUSO"})});
    return "sent, answer unreadable (checked on the server)";
  });
  await attempt("create a project with a form", () => new Promise((resolve) => {
    const frame = document.createElement("iframe");
    frame.name = "sink";
    document.body.appendChild(frame);
    const form = document.createElement("form");
    form.method = "POST"; form.action = APP + "/api/projects"; form.target = "sink";
    const input = document.createElement("input");
    input.name = "name"; input.value = "Intruso formulario";
    form.appendChild(input);
    document.body.appendChild(form);
    frame.onload = () => resolve("submitted (checked on the server)");
    form.submit();
    setTimeout(() => resolve("submitted, no load event (checked on the server)"), 3000);
  }));
  await attempt("load a frame of a meeting as an image", () => new Promise((resolve) => {
    const image = new Image();
    image.onload = () => resolve("LOADED " + image.width + "x" + image.height);
    image.onerror = () => resolve("blocked: the image did not load");
    image.src = APP + "/r/suelta/f/frame_001_t00-00-10.jpg";
  }));
  await attempt("load the application's script", () => new Promise((resolve) => {
    const script = document.createElement("script");
    script.onload = () => resolve("LOADED");
    script.onerror = () => resolve("blocked: the script did not load");
    script.src = APP + "/static/app.js";
    document.body.appendChild(script);
  }));
  await report();
})();
"""


class Attacker(http.server.BaseHTTPRequestHandler):
    results = None
    page = b""

    def log_message(self, *args):
        pass

    def do_GET(self):
        body = Attacker.page
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        Attacker.results = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        self.send_response(204)
        self.end_headers()


def free_port():
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def devtools(port, method, path):
    request = urllib.request.Request(f"http://127.0.0.1:{port}{path}", method=method)
    with urllib.request.urlopen(request, timeout=10) as response:
        return json.loads(response.read() or b"null")


def main():
    if not EDGE.is_file():
        print("Microsoft Edge is not installed here: the check was not run")
        return 2
    tmp = Path(tempfile.mkdtemp(prefix="vmt-cross-site-"))
    data = tmp / "data"
    store.create_project(data, "Proyecto del cliente", "Cliente")
    loose = data / "suelta"
    loose.mkdir()
    (loose / "summary.md").write_text("## Resumen\n\n[frame_001_t00-00-10.jpg]\n", encoding="utf-8")
    from PIL import Image
    Image.new("RGB", (64, 36), (20, 90, 200)).save(loose / "frame_001_t00-00-10.jpg")
    keys = {"key": "AIzaDELOWNER"}
    app = server.App(data, read_key=lambda: keys["key"], save_key=lambda k: keys.update(key=k),
                     delete_key=lambda: keys.pop("key", None) is not None, opener=lambda path: None).start()
    Attacker.page = (f"<!doctype html><title>otro sitio</title><body><script>"
                     f"{ATTACKS.replace('__APP__', app.url)}</script></body>").encode("utf-8")
    other = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Attacker)
    threading.Thread(target=other.serve_forever, daemon=True).start()
    attacker_url = f"http://localhost:{other.server_address[1]}/"
    debug = free_port()
    edge = subprocess.Popen([str(EDGE), "--headless=new", f"--remote-debugging-port={debug}",
                             f"--user-data-dir={tmp / 'edge-profile'}", "--no-first-run",
                             "--no-default-browser-check", "--disable-background-networking",
                             "--disable-component-update", "--disable-sync", "about:blank"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(100):
            try:
                devtools(debug, "GET", "/json/version")
                break
            except OSError:
                time.sleep(0.2)
        devtools(debug, "PUT", f"/json/new?{app.launch_url}")
        own_title = ""
        for _ in range(50):
            tabs = devtools(debug, "GET", "/json/list")
            own_title = next((t["title"] for t in tabs if t["url"].startswith(app.url)), "")
            if "MeetingTool" in own_title:
                break
            time.sleep(0.2)
        print(f"the application's own tab opened with its session: {'yes' if 'MeetingTool' in own_title else 'NO'}"
              f" (title {own_title!r})")
        devtools(debug, "PUT", f"/json/new?{attacker_url}")
        for _ in range(100):
            if Attacker.results is not None:
                break
            time.sleep(0.2)
        results = Attacker.results or {}
        print(f"page of another site: {attacker_url} (the application is at {app.url})")
        for name, outcome in results.items():
            print(f"- {name}: {outcome}")
        projects = [p["name"] for p in store.list_projects(data)]
        print(f"projects after the attempts: {projects}")
        print(f"key after the attempts: {'unchanged' if keys.get('key') == 'AIzaDELOWNER' else 'CHANGED'}")
        leaked = [name for name, outcome in results.items() if outcome.startswith(("READ", "SENT", "LOADED"))]
        ok = ("MeetingTool" in own_title and len(results) == 8 and not leaked
              and projects == ["Proyecto del cliente"] and keys.get("key") == "AIzaDELOWNER")
        print("RESULT: every attempt of the other site failed" if ok else f"RESULT: FAILED {leaked}")
        return 0 if ok else 1
    finally:
        edge.kill()
        edge.wait()
        other.shutdown()
        app.stop()
        time.sleep(1)
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
