"""WI15-AC04: the owner's data folder is shown as it is, with no migration.

Hashes every file of the data folder, runs the application over it with no
key (the Credential Manager is not read) and no network, requests every
screen and every file a screen names, and hashes again. Prints only counts
and the comparison: the folder holds client data.

    python docs/evidence/01M3QPZT9YPTVTYSED4GF7YDD3/existing_data_check.py C:/Users/Diego/VisualMeetingTool-data
"""

import hashlib
import http.client
import re
import sys
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPOSITORY))

from meetingtool.app import library, server  # noqa: E402


def fingerprint(folder):
    found = {}
    for path in sorted(folder.rglob("*")):
        if path.is_file():
            found[path.relative_to(folder).as_posix()] = (path.stat().st_size,
                                                          hashlib.sha256(path.read_bytes()).hexdigest())
    return found


def refuse(*args):
    raise AssertionError("the check must not save, delete or open anything")


def main(data_dir):
    data_dir = Path(data_dir)
    before = fingerprint(data_dir)
    app = server.App(data_dir, read_key=lambda: None, save_key=refuse, delete_key=refuse, opener=refuse,
                     endpoint="http://127.0.0.1:9/unreachable").start()
    statuses, pages_seen, files_seen = {}, 0, 0

    def get(path):
        connection = http.client.HTTPConnection(server.HOST, app.port, timeout=60)
        connection.request("GET", path, headers={"Cookie": f"{server.COOKIE}={app.token}"})
        response = connection.getresponse()
        body = response.read()
        connection.close()
        statuses[response.status] = statuses.get(response.status, 0) + 1
        return response.status, body

    try:
        paths = ["/", "/settings"]
        projects = library.projects(data_dir)
        meetings = 0
        for project in projects:
            paths += [f"/p/{project['id']}", f"/p/{project['id']}/new"]
            for entry in library.meetings(data_dir, project["id"]):
                meetings += 1
                paths.append(f"/p/{project['id']}/m/{entry['record']['id']}")
        loose = library.loose(data_dir)
        paths += [f"/r/{entry['name']}" for entry in loose]
        for path in paths:
            status, body = get(path)
            pages_seen += 1
            if status != 200:
                print(f"page answered {status}")
                continue
            text = body.decode("utf-8")
            for address in re.findall(r'(?:src|href)="(/(?:p|r)/[^"]+/f/[^"]+)"', text):
                file_status, _ = get(address)
                files_seen += 1
                if file_status != 200:
                    print(f"file answered {file_status}")
    finally:
        app.stop()
    after = fingerprint(data_dir)
    changed = sum(1 for name in before if name in after and before[name] != after[name])
    print(f"data folder: {len(before)} files, {sum(size for size, _ in before.values())} bytes")
    print(f"projects: {len(projects)}; meetings: {meetings}; loose results: {len(loose)}")
    print(f"screens requested: {pages_seen}; files requested from them: {files_seen}; "
          f"answers by status: {dict(sorted(statuses.items()))}")
    print(f"after: {len(after)} files; changed: {changed}; removed: {len(set(before) - set(after))}; "
          f"added: {len(set(after) - set(before))}")
    same = before == after and set(statuses) == {200}
    print("RESULT: the folder is identical and every screen answered 200" if same else "RESULT: FAILED")
    return 0 if same else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
