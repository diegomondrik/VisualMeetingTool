"""WI14-AC01: without --format qa, the summary's request is exactly as before.

Builds the request of every meeting type (and none), in Spanish and in
English, with and without a project's knowledge, from the working tree and
from a base commit (extracted with git archive into a folder outside the
repository), and compares them byte for byte. The transcript and the frames
reading are invented here; only digests are printed.

    python docs/evidence/01M3Q46RMB70H2F5NE56SVQD5M/prompts_unchanged.py <repository> <base commit> <empty folder>

The output of the recorded run is prompts-unchanged.txt next to this file.
"""

import io
import json
import subprocess
import sys
import tarfile
from pathlib import Path

BUILD = r"""
import hashlib, json, sys
sys.path.insert(0, sys.argv[1])
from meetingtool.summary import writer
turns = [(4, "Ana Pérez", "Buen día, revisamos el costo de proceso."), (82, "Juan Gómez", "Fijate el total."),
         (3723, "Ana Pérez", "Queda acordado: Juan manda el detalle el viernes.")]
reading = "# What each frame shows\n\n- FRAME 1: frame_001_t00-01-22.jpg\n\n[FRAME 1]\n- Key Data: total 1.250\n"
knowledge = "### 2026-09-14 Primera reunión (discovery)\n- El costo se mide por kilo"
digests = {}
for language in ("es", "en"):
    for meeting_type in [None, *writer.MEETING_TYPES]:
        for known in ("", knowledge):
            prompt = writer.build_prompt(turns, reading, language, meeting_type, known, "Reunión de prueba")
            key = f"{language}/{meeting_type or 'none'}/{'knowledge' if known else 'no knowledge'}"
            digests[key] = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
print(json.dumps(digests))
"""


def digests(tree):
    run = subprocess.run([sys.executable, "-c", BUILD, str(tree)], capture_output=True, text=True, encoding="utf-8",
                         cwd=tree, check=True)
    return json.loads(run.stdout)


def main(repository, base, work):
    repository, work = Path(repository).resolve(), Path(work).resolve()
    work.mkdir(parents=True, exist_ok=False)
    archive = subprocess.run(["git", "-C", str(repository), "archive", base], capture_output=True, check=True).stdout
    with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
        tar.extractall(work, filter="data")
    before, after = digests(work), digests(repository)
    print(f"WI14-AC01: the summary's request of every type and language, base {base} against the working tree")
    same = before == after
    for key in sorted(before):
        print(f"- {key}: {'identical' if before[key] == after.get(key) else 'DIFFERENT'} ({before[key][:16]})")
    print(f"{len(before)} requests compared: " + ("all identical" if same else "SOME DIFFER"))
    return 0 if same else 1


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:4]))
