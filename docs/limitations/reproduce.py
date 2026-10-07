"""Reproduces every entry of the limitations register (REGISTER.md).

Run from the repository root:

    python docs/limitations/reproduce.py                        # every project entry
    python docs/limitations/reproduce.py WI05-P3-2 WI02-P3-E    # some entries
    python docs/limitations/reproduce.py --ingol-repo C:/path/to/ingol   # INGOL's too

Each entry's claim is read from the first words of its State cell in the
register: `open` (the limitation reproduces), `fixed` (it no longer does) or
`not reproducible` (it cannot be reproduced here; the entry says why). The
script keeps no copy of the claims. It runs each reproduction, prints what it
saw, and exits 1 when a result differs from the register's claim, so the
register cannot go stale in silence when a limitation is fixed, nor state
something the reproduction does not show. Before running anything it checks
that the register's entries and its own reproductions are the same set,
each state readable, and exits 1 if not. `--flip ID` inverts one claim on purpose, to see the
check fail.

Nothing is written inside the repository (not even Python's bytecode cache)
and nothing goes to the network (Go builds with GOPROXY=off and
GOTOOLCHAIN=local): every file is made in a temporary folder. The INGOL entries (H1, H3, H4,
H6) need a local clone of INGOL and Go; the script builds INGOL at the
revision this project's wrapper pins and runs INGOL's own commands against
copies of this project. Without --ingol-repo they are reported as skipped.
"""

import argparse
import contextlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parents[2]
REGISTER = REPO / "docs" / "limitations" / "REGISTER.md"
sys.path.insert(0, str(REPO))
sys.dont_write_bytecode = True  # no __pycache__ inside the repository

from meetingtool import repository_guard  # noqa: E402
from meetingtool.frames import extract as extract_module  # noqa: E402
from meetingtool.frames import transcript as transcript_module  # noqa: E402
from meetingtool.frames.extract import extract_frames  # noqa: E402
from meetingtool.projects import store  # noqa: E402
from tests import test_frames as frames_fixture  # noqa: E402

ENTRIES = []


def entry(identifier, needs_ingol=False):
    def register(function):
        ENTRIES.append((identifier, needs_ingol, function))
        return function
    return register


def git(*args, cwd=None, check=True):
    return subprocess.run(["git", *args], cwd=cwd, check=check, capture_output=True, text=True)


def run_python(args, cwd, env=None):
    env = {**(os.environ if env is None else env), "PYTHONDONTWRITEBYTECODE": "1"}
    return subprocess.run([sys.executable, *args], cwd=cwd, capture_output=True, text=True, env=env)


def ignored(path, repository=REPO):
    """Whether .gitignore ignores path with Linux's case-exact matching."""
    result = subprocess.run(["git", "-C", str(repository), "-c", "core.ignorecase=false", "check-ignore", "-q",
                             "--no-index", path], capture_output=True)
    return result.returncode == 0


def kept_slides(result, out):
    return [frames_fixture.which_slide(out / name) for name in result.kept]


@contextlib.contextmanager
def workspace():
    with tempfile.TemporaryDirectory(prefix="vmt-limitations-", ignore_cleanup_errors=True) as name:
        yield Path(name)


# --- A clone of this repository at HEAD, for mutations -----------------------------------------

class Clone:
    """A throwaway clone of the committed HEAD. mutate() applies exact text
    replacements (each must match exactly once), runs a test selection, and
    restores the files. The unmutated selection must pass first, so a
    surviving mutation is never an artefact of a broken copy."""

    _baseline = {}

    def __init__(self, root):
        self.path = root / "clone"
        git("clone", "-q", str(REPO), str(self.path))
        git("checkout", "-q", git("rev-parse", "HEAD", cwd=REPO).stdout.strip(), cwd=self.path)

    def tests(self, selection):
        result = run_python(["-m", "unittest", *selection], cwd=self.path)
        return result.returncode, (result.stderr.strip().splitlines() or ["(no output)"])[-1]

    def mutate(self, replacements, selection):
        key = tuple(selection)
        if key not in self._baseline:
            self._baseline[key] = self.tests(selection)
            if self._baseline[key][0] != 0:
                raise RuntimeError(f"the unmutated tests fail in the clone: {self._baseline[key][1]}")
        touched = set()
        try:
            for relative, old, new in replacements:
                target = self.path / relative
                text = target.read_bytes().decode("utf-8")
                if text.count(old) != 1:
                    raise RuntimeError(f"mutation text found {text.count(old)} times in {relative}, expected once")
                target.write_bytes(text.replace(old, new).encode("utf-8"))
                touched.add(relative)
            return self.tests(selection)
        finally:
            for relative in touched:
                git("checkout", "--", relative, cwd=self.path)


FRAMES_TESTS = ["tests.test_frames"]
_clone = None


def clone(root):
    global _clone
    if _clone is None:
        _clone = Clone(root)
    return _clone


def survives(root, replacements, selection=FRAMES_TESTS):
    code, last = clone(root).mutate(replacements, selection)
    return code == 0, f"mutated suite exit {code} ({last})"


# --- INGOL -------------------------------------------------------------------------------------

WRAPPER = REPO / ".github" / "workflows" / "ingol-bootstrap.yml"
INGOL_URL = "https://github.com/diegomondrik/ingol.git"
PROJECT_URL = "https://github.com/diegomondrik/VisualMeetingTool.git"
# The last integrated pull request (WI05, PR #6): base and head, both in this repository's history.
PR6_BASE = "8bd99e240cc0b83cd7f01fb1816805ef8a1be7d0"
PR6_HEAD = "6835fcbedaef773489f2b4b41e7a5bbfef04bd0c"
PR6_WORK_ITEM = "01M3CSRVTHE26R86125VY676EJ"
# What a protected run on GitHub provides; the local replica sets it, and says so.
REPLICA_ENV = {"GITHUB_ACTIONS": "true", "GITHUB_RUN_ID": "1", "GITHUB_RUN_ATTEMPT": "1",
               "RUNNER_NAME": "local-replica", "RUNNER_OS": "Windows" if os.name == "nt" else "Linux",
               "RUNNER_ARCH": "X64"}


class Ingol:
    def __init__(self, repository, root):
        pin = re.search(r"repository: diegomondrik/ingol\s+ref: ([0-9a-f]{40})", WRAPPER.read_text(encoding="utf-8"))
        self.revision = pin.group(1)
        self.root = root / "ingol"
        self.installation = self.root / "installation"
        git("clone", "-q", str(repository), str(self.installation))
        git("checkout", "-q", self.revision, cwd=self.installation)
        git("remote", "set-url", "origin", INGOL_URL, cwd=self.installation)
        suffix = ".exe" if os.name == "nt" else ""
        self.cli = self.root / f"ingol{suffix}"
        self.checker = self.root / f"bootstrap-check{suffix}"
        for binary, package in ((self.cli, "./cmd/ingol"), (self.checker, "./cmd/bootstrap-check")):
            # No module download and no toolchain switch: a cold cache fails here instead of reaching the network.
            subprocess.run(["go", "build", "-o", str(binary), package], cwd=self.installation, check=True,
                           capture_output=True, env={**os.environ, "GOPROXY": "off", "GOTOOLCHAIN": "local"})

    def run(self, *args, cwd=None, env=None):
        return subprocess.run([str(self.cli), *args], cwd=cwd, capture_output=True, text=True, env=env)

    def project_clone(self, name, commit):
        path = self.root / name
        git("clone", "-q", str(REPO), str(path))
        git("checkout", "-q", commit, cwd=path)
        git("remote", "set-url", "origin", PROJECT_URL, cwd=path)
        return path

    def protected_check(self, baseline, candidate, base, head, body):
        event = self.root / f"event-{head[:7]}.json"
        repo = {"full_name": "diegomondrik/VisualMeetingTool"}
        event.write_text(json.dumps({"pull_request": {"body": body, "base": {"sha": base, "repo": repo},
                                                      "head": {"sha": head, "repo": repo}}}), encoding="utf-8")
        shutil.rmtree(candidate / ".ingol" / "generated", ignore_errors=True)
        result = subprocess.run([str(self.checker), "--installation-root", ".", "--baseline-root", str(baseline),
                                 "--candidate-root", str(candidate), "--event-file", str(event)],
                                cwd=self.installation, capture_output=True, text=True,
                                env={**os.environ, **REPLICA_ENV})
        shutil.rmtree(candidate / ".ingol" / "generated", ignore_errors=True)
        return result


_ingol = None


def ingol(args, root):
    global _ingol
    if _ingol is None:
        _ingol = Ingol(args.ingol_repo, root)
    return _ingol


@entry("H1", needs_ingol=True)
def h1(args, root):
    ing = ingol(args, root)
    target = root / "h1-existing-project"
    target.mkdir()
    (target / "main.py").write_text("print('an existing project')\n", encoding="utf-8")
    result = ing.run("init", str(target))
    refused = result.returncode != 0 and "is not empty" in result.stderr
    return refused, f"ingol init on a folder with one file: exit {result.returncode}: {result.stderr.strip()}"


@entry("H2")
def h2(args, root):
    return None, ("needs a private repository on GitHub's free plan; the owner's account has Pro, where the "
                  "protection exists. Source: GitHub's plans documentation, read 2026-09-25 (INGOL D-162)")


@entry("H3", needs_ingol=True)
def h3(args, root):
    ing = ingol(args, root)
    body = f"INGOL-Work-Item: {PR6_WORK_ITEM}"
    baseline = ing.project_clone("h3-baseline", PR6_BASE)
    candidate = ing.project_clone("h3-candidate", PR6_HEAD)
    control = ing.protected_check(baseline, candidate, PR6_BASE, PR6_HEAD, body)
    if control.returncode != 0:
        raise RuntimeError(f"positive control failed, the replica is broken: {control.stderr.strip()[-300:]}")
    # The same pull request on a protected main that also runs the project's own tests.
    workflow = baseline / ".github" / "workflows" / "tests.yml"
    workflow.write_text("name: tests\non: pull_request\npermissions:\n  contents: read\njobs:\n  tests:\n"
                        "    runs-on: ubuntu-latest\n    steps:\n      - uses: actions/checkout@v4\n"
                        "      - run: python -m unittest discover -s tests -v\n", encoding="utf-8")
    git("add", "-A", cwd=baseline)
    git("-c", "user.name=lab", "-c", "user.email=lab@example.invalid", "commit", "-q", "-m", "tests", cwd=baseline)
    base = git("rev-parse", "HEAD", cwd=baseline).stdout.strip()
    git("fetch", "-q", str(baseline), "HEAD", cwd=candidate)
    git("-c", "user.name=lab", "-c", "user.email=lab@example.invalid", "rebase", "-q", "--onto", "FETCH_HEAD",
        PR6_BASE, cwd=candidate)
    head = git("rev-parse", "HEAD", cwd=candidate).stdout.strip()
    variant = ing.protected_check(baseline, candidate, base, head, body)
    failed = sorted(set(re.findall(r'"predicate": "([^"]+)",\s+"status": "failed"', variant.stdout)))
    reason = "workflow set must contain only ingol-bootstrap.yml" in variant.stdout
    return (variant.returncode != 0 and reason,
            f"PR #6 in the local replica: exit {control.returncode}; the same PR with tests.yml on main: exit "
            f"{variant.returncode}, failed {', '.join(failed)}: \"workflow set must contain only "
            f"ingol-bootstrap.yml\" {'named' if reason else 'NOT named'}")


@entry("H4", needs_ingol=True)
def h4(args, root):
    ing = ingol(args, root)
    project = root / "h4-new"
    init = ing.run("init", str(project))
    if init.returncode != 0:
        raise RuntimeError(f"ingol init failed: {init.stderr.strip()}")
    missing = [name for name in (".git", ".gitignore", ".gitattributes") if not (project / name).exists()]
    audit = ing.run("audit", str(project))
    tp09 = next((line for line in audit.stdout.splitlines() if "\tTP-09\t" in line), "")
    git("-c", "init.defaultBranch=main", "init", "-q", cwd=project)
    git("add", "-A", cwd=project)
    git("-c", "user.name=lab", "-c", "user.email=lab@example.invalid", "-c", "core.autocrlf=true",
        "commit", "-q", "-m", "ingol init", cwd=project)
    exits, blocked = {}, {}
    for autocrlf in ("false", "true"):
        checkout = root / f"h4-autocrlf-{autocrlf}"
        git("-c", f"core.autocrlf={autocrlf}", "clone", "-q", str(project), str(checkout))
        report = root / f"h4-doctor-{autocrlf}.json"
        exits[autocrlf] = ing.run("doctor", "--report", str(report), str(checkout)).returncode
        surfaces = json.loads(report.read_text(encoding="utf-8"))["surfaces"]
        blocked[autocrlf] = (sum(s["status"] == "blocked" for s in surfaces), len(surfaces))
    reproduced = (missing == [".git", ".gitignore", ".gitattributes"] and tp09.startswith("unproven")
                  and exits["false"] == 0 and exits["true"] != 0)
    return reproduced, (f"ingol init writes none of {missing}; audit: {tp09.split(chr(9))[0]} TP-09. "
                        f"ingol doctor on a clone with core.autocrlf=false: exit {exits['false']}, blocked "
                        f"{blocked['false'][0]} of {blocked['false'][1]}; with core.autocrlf=true (Windows' "
                        f"default): exit {exits['true']}, blocked {blocked['true'][0]} of {blocked['true'][1]} "
                        f"(\"not byte-identical to this installation's own copy\")")


@entry("H5")
def h5(args, root):
    wrapper = WRAPPER.read_text(encoding="utf-8")
    backend = (REPO / ".ingol" / "backends" / "github.yaml").read_text(encoding="utf-8")
    trigger = "pull_request_target:" in wrapper
    secret = "secrets.INGOL_TRUSTED_READ_TOKEN" in wrapper
    public = re.search(r"^\s*target_visibility:\s*public\s*$", backend, re.MULTILINE) is not None
    return (trigger and secret and public,
            f"preconditions, read from this repository: pull_request_target trigger {trigger}, the read token "
            f"of the private installation used {secret}, target_visibility public {public}. Extracting the "
            "token was not attempted: that would be an attack, not a reproduction")


@entry("H6", needs_ingol=True)
def h6(args, root):
    ing = ingol(args, root)
    project = ing.project_clone("h6-project", "HEAD")
    before = next(line for line in ing.run("audit", str(project)).stdout.splitlines() if "\tTP-09\t" in line)
    gitignore = project / ".gitignore"
    text = gitignore.read_bytes().decode("utf-8")
    if text.count("\ngenerated/\n") != 1:
        raise RuntimeError(".gitignore no longer has the unanchored generated/ line")
    gitignore.write_bytes(text.replace("\ngenerated/\n", "\n/generated/\n").encode("utf-8"))
    after = next(line for line in ing.run("audit", str(project)).stdout.splitlines() if "\tTP-09\t" in line)
    still_ignored = ignored("generated/state.json", project)
    return (before.startswith("proven") and after.startswith("blocked") and still_ignored,
            f"audit with generated/: {before.split(chr(9))[0]}; with /generated/: {after.split(chr(9))[0]} "
            f"({after.split(chr(9))[-1]}); yet git still ignores generated/state.json: {still_ignored}")


# --- Work item 1, the skeleton (01M3C5MCNJ0FQJW936SZYSNPS6) -----------------------------------

@entry("WI01-P2-1")
def wi01_p2_1(args, root):
    paths = ["a.mp3", "a.mkv", "a.webm", "transcript.txt", "report_acme.md", "handoff_1.json", "frames/f1.jpg"]
    missed = [p for p in paths if not repository_guard.is_meeting_data(p)]
    return bool(missed), f"guard misses {missed or 'none'} of {paths} (widened by a977049, WI02)"


@entry("WI01-P2-2")
def wi01_p2_2(args, root):
    code = ["meetingtool/projects/store.py", "meetingtool/frames/extract.py", "tests/frames/x.py"]
    wrongly = [p for p in code if ignored(p)]
    return bool(wrongly), f"code paths ignored by .gitignore: {wrongly or 'none'} (anchored by ba02528; generated/ is H6)"


@entry("WI01-P2-3")
def wi01_p2_3(args, root):
    tested, integrated = "165cfff6a3b35fb7006c800afebbbe0dd7fa4d9b", "37294079a15dd4690cd9977a71f511d76221f204"
    changed = git("diff", "--name-only", tested, integrated, cwd=REPO).stdout.split()
    allowed = all(p.startswith(f"docs/evidence/{PR6_WORK_ITEM}/") or f"{PR6_WORK_ITEM}/approvals/" in p for p in changed)
    return (bool(changed) and allowed,
            f"WI05: the tested commit 165cfff and the integrated 3729407 differ in {len(changed)} files, "
            f"all evidence or approval: {allowed}")


@entry("WI01-P3-1")
def wi01_p3_1(args, root):
    upper = ["a.MP4", "deep/B.DOCX", "c.Mp3"]
    missed = [p for p in upper if not ignored(p)]
    return bool(missed), f"upper-case extensions not ignored on Linux matching: {missed or 'none'} (ba02528)"


@entry("WI01-P3-2")
def wi01_p3_2(args, root):
    repository = root / "p3-2"
    repository.mkdir()
    git("init", "-q", cwd=repository)
    (repository / "meeting.mp4").write_text("not real\n")
    git("add", "-f", "meeting.mp4", cwd=repository)
    git("-c", "user.name=lab", "-c", "user.email=lab@example.invalid", "commit", "-q", "-m", "add", cwd=repository)
    git("rm", "-q", "meeting.mp4", cwd=repository)
    git("-c", "user.name=lab", "-c", "user.email=lab@example.invalid", "commit", "-q", "-m", "remove", cwd=repository)
    in_history = "meeting.mp4" in git("log", "--all", "--name-only", "--format=", cwd=repository).stdout
    now = repository_guard.check_repository(repository)
    zipped = repository_guard.is_meeting_data("recording.mp4.zip")
    return (in_history and now == [] and not zipped,
            f"a recording committed then removed: in history {in_history}, guard reports {now}; "
            f"recording.mp4.zip flagged: {zipped}")


@entry("WI01-P3-3")
def wi01_p3_3(args, root):
    env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    result = run_python(["-m", "unittest", "discover", "-s", str(REPO / "tests")], cwd=root, env=env)
    cannot_import = result.returncode != 0 and "No module named 'meetingtool'" in result.stderr
    return cannot_import, (f"suite started from outside the repository root: exit {result.returncode}, "
                           f"\"No module named 'meetingtool'\" {'shown' if cannot_import else 'not shown'}")


# --- Work item 2, the guard (01M3CG1XGTT95MT2WNTMH1TXR2) --------------------------------------

@entry("WI02-P2-A")
def wi02_p2_a(args, root):
    fixtures = ["tests/fixtures/slide.png", "tests/fixtures/sample.mp4", "tests/fixtures/transcript_sample.txt"]
    flagged = [p for p in fixtures if repository_guard.is_meeting_data(p)]
    return flagged == fixtures, f"test fixtures rejected by the guard: {flagged}"


@entry("WI02-P2-B")
def wi02_p2_b(args, root):
    path = "meetingtool/projects/acme/memory.json"
    guard, gitignore = repository_guard.is_meeting_data(path), ignored(path)
    return (not guard and not gitignore, f"{path}: guard flags it {guard}, .gitignore ignores it {gitignore}")


@entry("WI02-P3-A")
def wi02_p3_a(args, root):
    paths = ["report_acme.md", "handoff_1.json", "transcript.txt", "Frames/x/f.json", "MEETINGS/a/b.json"]
    not_ignored = [p for p in paths if not ignored(p)]
    guarded = [p for p in paths if repository_guard.is_meeting_data(p)]
    return (not_ignored == paths and guarded == paths,
            f"not ignored by .gitignore on Linux matching: {not_ignored}; all caught by the guard: {guarded == paths}")


@entry("WI02-P3-B")
def wi02_p3_b(args, root):
    result = run_python(["-m", "unittest", "tests.test_repository_guard.GitignoreTest"], cwd=REPO)
    upper = ignored("Frames/x/file.json")
    return (result.returncode == 0 and not upper,
            f"GitignoreTest exit {result.returncode} while Frames/x/file.json is ignored: {upper}")


@entry("WI02-P3-C")
def wi02_p3_c(args, root):
    env = {**os.environ, "GIT_DIR": str(root / "no-such-git-dir")}
    broken = subprocess.run(["git", "-C", str(REPO), "check-ignore", "-q", "--no-index", "x.mp4"],
                            capture_output=True, env=env).returncode
    name = "tests.test_repository_guard.GitignoreTest.test_a_code_folder_named_projects_below_the_root_is_not_ignored"
    result = run_python(["-m", "unittest", name], cwd=REPO, env=env)
    return (broken not in (0, 1) and result.returncode == 0,
            f"with git broken (check-ignore exit {broken}) the \"not ignored\" test exits {result.returncode}")


@entry("WI02-P3-D")
def wi02_p3_d(args, root):
    paths = ["export.zip", "attendees.csv", "slides.ppt", "budget.xls", "notas-reunion.txt"]
    missed = [p for p in paths if not repository_guard.is_meeting_data(p)]
    return missed == paths, f"not flagged by the guard: {missed}"


@entry("WI02-P3-E")
def wi02_p3_e(args, root):
    return (repository_guard.is_meeting_data("transcription.md"),
            f"transcription.md flagged as meeting data: {repository_guard.is_meeting_data('transcription.md')}")


# --- Work item 3, projects and meeting memory (01M3CGKPV51VTTK3S8V1JEF4HW) ----------------------
# The review lists its P3 findings unnumbered; they are numbered here in the review's order.

@entry("WI03-P2-1")
def wi03_p2_1(args, root):
    data = root / "wi03-p2-1"
    store.create_project(data, "Acme", "Acme")
    try:
        store.add_meeting(data, "../repo/x", "Kickoff", "2026-09-25")
    except store.ProjectError as error:
        return False, f"a path as project id is refused: {error} (91231a1)"
    return True, "a path as project id was accepted"


@entry("WI03-P2-2")
def wi03_p2_2(args, root):
    name = "tests.test_projects.CommandLineTest.test_non_ansi_characters_survive_redirected_output"
    result = run_python(["-m", "unittest", name], cwd=REPO)
    return result.returncode != 0, f"redirected output with Łódź, ✓, →: test exit {result.returncode} (91231a1)"


@entry("WI03-P2-3")
def wi03_p2_3(args, root):
    pyproject = (REPO / "pyproject.toml").read_text(encoding="utf-8")
    declared = 'include = ["meetingtool", "meetingtool.*"]' in pyproject
    result = run_python(["-m", "unittest", "tests.test_frames.PackagingTest"], cwd=REPO)
    return (not (declared and result.returncode == 0),
            f"subpackages declared in pyproject.toml: {declared}; PackagingTest exit {result.returncode} "
            "(c38353c; building a wheel would need setuptools, not installed here)")


@entry("WI03-P3-1")
def wi03_p3_1(args, root):
    slugs = {text: store.slugify(text, fallback="project") for text in ("Łódź", "Straße", "Søren", "東京", "Москва")}
    data = root / "wi03-p3-1"
    store.create_project(data, "東京", "c")
    try:
        store.create_project(data, "Москва", "c")
        collided = False
    except store.ProjectError:
        collided = True
    return collided and slugs["Łódź"] == "odz", f"slugs {slugs}; a second non-Latin name collides: {collided}"


@entry("WI03-P3-2")
def wi03_p3_2(args, root):
    try:
        store.create_project(root / "wi03-p3-2", "x" * 300, "c")
    except store.ProjectError as error:
        return False, f"ProjectError: {error}"
    except OSError as error:
        return True, f"a 300-character title raises a raw {type(error).__name__}, not ProjectError"
    return False, "a 300-character title was accepted"


@entry("WI03-P3-3")
def wi03_p3_3(args, root):
    data = root / "wi03-p3-3"
    store.create_project(data, "Acme", "c")
    store.add_meeting(data, "acme", "Kickoff", "2026-09-25", summary="line one\r\nline two")
    returned, read = store.rebuild_knowledge(data, "acme"), store.knowledge_context(data, "acme")
    return returned != read, f"rebuild_knowledge's return equals knowledge_context's read: {returned == read}"


@entry("WI03-P3-4")
def wi03_p3_4(args, root):
    data = root / "wi03-p3-4"
    store.create_project(data, "Acme", "c")
    (data / "acme" / "knowledge.md").unlink()
    try:
        store.knowledge_context(data, "acme")
    except store.ProjectError:
        return False, "ProjectError"
    except FileNotFoundError:
        return True, "a missing knowledge.md raises FileNotFoundError, not ProjectError"
    return False, "no error: the knowledge is made from the records (ef0abc5)"


@entry("WI03-P3-5")
def wi03_p3_5(args, root):
    with mock.patch.dict(os.environ, {store.DATA_DIR_ENV: "~/vmt-data"}):
        folder = store.default_data_dir()
    return str(folder).startswith("~"), f"{store.DATA_DIR_ENV}=~/vmt-data gives the folder {folder}"


@entry("WI03-P3-6")
def wi03_p3_6(args, root):
    data = root / "wi03-p3-6"
    store.create_project(data, "Acme", "c")
    with mock.patch.object(store, "_now_utc", lambda: "2026-09-25T12:00:00Z"):
        store.add_meeting(data, "acme", "Zeta review", "2026-09-25")
        store.add_meeting(data, "acme", "Alpha review", "2026-09-25")
    order = [m["title"] for m in store.list_meetings(data, "acme")]
    return order == ["Alpha review", "Zeta review"], f"added Zeta then Alpha in the same second, listed {order}"


@entry("WI03-P3-7")
def wi03_p3_7(args, root):
    text = (REPO / "docs/evidence/01M3CGKPV51VTTK3S8V1JEF4HW/owner-machine-run.txt").read_text(encoding="utf-8")
    held = [flag for flag in ("--context", "--summary", "--key-point") if flag in text]
    return len(held) == 3, f"the WI03-AC05 evidence holds, besides titles: {held} (synthetic values)"


# --- Work item 4, frames (01M3CGKPVGGAAK06A1RD5C3XWZ) ------------------------------------------

@entry("WI04-P2-1")
def wi04_p2_1(args, root):
    name = "tests.test_frames.SelectionTest.test_among_equal_scores_the_budget_keeps_the_earliest_as_the_original_did"
    result = run_python(["-m", "unittest", name], cwd=REPO)
    return result.returncode != 0, f"tie-break test exit {result.returncode} (5f20bf7)"


@entry("WI04-P3-1")
def wi04_p3_1(args, root):
    mutations = {
        "zone weight 0.4 -> 0.5": [("meetingtool/frames/signals.py", "W_ZONE = 0.4", "W_ZONE = 0.5")],
        "minimum score 0.15 -> 0.2": [("meetingtool/frames/extract.py", "min_score=0.15,", "min_score=0.2,")],
        "duration from the stream, not the container": [
            ("meetingtool/frames/extract.py", "    if container.duration:\n", "    if False:\n")],
        "coverage ignores earlier candidates": [
            ("meetingtool/frames/extract.py", "composite_score(prev_gray, gray, timestamp, duration, budget, candidate_times)",
             "composite_score(prev_gray, gray, timestamp, duration, budget, [])")],
    }
    outcome = {name: survives(root, change)[0] for name, change in mutations.items()}
    return all(outcome.values()), f"mutations surviving the frames tests: {outcome}"


@entry("WI04-P3-2")
def wi04_p3_2(args, root):
    class Nothing:
        duration = None
        time_base = None
    duration = extract_module._duration(Nothing(), Nothing())
    with workspace() as tmp:
        video, out = tmp / "v.mp4", tmp / "out"
        frames_fixture.write_video(video, [(frames_fixture.SLIDE_A, 6, False), (frames_fixture.SLIDE_B, 6, False)])
        out.mkdir()
        (out / "frame_999_t00-00-00.jpg").write_bytes(b"old")
        seen = []
        real = extract_module.composite_score

        def spy(*a):
            seen.append((out / "frame_999_t00-00-00.jpg").exists())
            return real(*a)
        with mock.patch.object(extract_module, "composite_score", spy):
            extract_frames(video, out)
        log = (out / "frames_discarded.log").read_text(encoding="utf-8").splitlines()
    old_during = bool(seen) and all(seen)
    english_utc = bool(log) and all(re.match(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ \| t\S+ \| [a-z_]+ ", line) for line in log)
    return (duration == 0.0 and old_during and english_utc,
            f"executed: no duration gives {duration}; the old frame still exists during the analysis {old_during}; "
            f"discard log in English with UTC times {english_utc}. Read from the code, not executed: SSIM on the "
            "decoded JPEG (extract.py, _content_gray_of_jpeg) and a shape mismatch skips the comparison")


@entry("WI04-P3-3")
def wi04_p3_3(args, root):
    result = run_python(["-m", "unittest", "tests.test_frames.NoNetworkTest.test_a_url_is_refused_before_anything_opens_it"],
                        cwd=REPO)
    return result.returncode != 0, f"URL refused before av.open: test exit {result.returncode} (5f20bf7)"


@entry("WI04-P3-4")
def wi04_p3_4(args, root):
    text = (REPO / "docs/evidence/01M3CGKPVGGAAK06A1RD5C3XWZ/real-recording-run.txt").read_text(encoding="utf-8")
    sourced = "the count of JPEG files in its own output folder" in text
    return not sourced, f"the 76-frame figure carries its source: {sourced} (67a6e4e)"


@entry("WI04-P3-5")
def wi04_p3_5(args, root):
    import heapq
    most = []

    class CountingHeap:
        heappush = staticmethod(heapq.heappush)

        @staticmethod
        def heappushpop(pool, entry):
            most.append(len(pool) + 1)
            return heapq.heappushpop(pool, entry)
    with workspace() as tmp:
        video = tmp / "v.mp4"
        frames_fixture.write_video(video, [(frames_fixture.SLIDE_A, 4, False), (frames_fixture.SLIDE_B, 4, False),
                                           (frames_fixture.SLIDE_C, 4, False)])
        scores = iter([0.2, 0.2, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 0.9, 0.9])
        with mock.patch.object(extract_module, "heapq", CountingHeap), \
                mock.patch.object(extract_module, "composite_score", lambda *a: next(scores, 0.1)), \
                mock.patch.object(extract_module, "_is_near_duplicate", lambda *a: False):
            extract_frames(video, tmp / "out", budget=2, fps_analyze=1.0, min_gap=0.0)
    return bool(most) and max(most) == 3, f"budget 2: JPEGs held at once during a replacement, at most {max(most, default=0)}"


@entry("WI04-P3-6")
def wi04_p3_6(args, root):
    with workspace() as tmp:
        video, out = tmp / "v.mp4", tmp / "out"
        frames_fixture.write_video(video, [(frames_fixture.SLIDE_A, 6, False), (frames_fixture.SLIDE_B, 6, False)])
        result = extract_frames(video, out)
    accounted = result.candidates + result.discards["low_score"] + result.discards["minimum_gap"]
    return result.samples == accounted + 1, (f"{result.samples} samples, {accounted} of them a candidate or a logged "
                                             "discard: the first one appears nowhere")


@entry("WI04-P3-7")
def wi04_p3_7(args, root):
    import av
    floor = re.search(r'"av>=(\d+)"', (REPO / "pyproject.toml").read_text(encoding="utf-8")).group(1)
    return (not av.__version__.startswith(f"{floor}."),
            f"declared floor av>={floor}; the only PyAV here, and in every recorded run, is {av.__version__}")


# --- Work item 5, frame selection (01M3CSRVTHE26R86125VY676EJ) ---------------------------------

@entry("WI05-P2-1")
def wi05_p2_1(args, root):
    kept = {}
    for order, check_before in (("new", True), ("old", False)):
        with workspace() as tmp:
            video, out = tmp / "v.mp4", tmp / "out"
            frames_fixture.write_video(video, [(frames_fixture.SLIDE_A, 3, False), (frames_fixture.SLIDE_B, 1, False),
                                               (frames_fixture.SLIDE_C, 2, False)])
            scores = iter([0.3, 0.9, 0.5, 0.5, 0.1])  # samples at 1, 2 (A, then A again), 3 (B), 4 (C), 5 s
            patches = [mock.patch.object(extract_module, "composite_score", lambda *a: next(scores))]
            if not check_before:
                patches.append(mock.patch.object(extract_module, "_is_near_duplicate", lambda *a: False))
            with contextlib.ExitStack() as stack:
                for patch in patches:
                    stack.enter_context(patch)
                result = extract_frames(video, out, budget=2, fps_analyze=1.0, min_gap=0.0)
            kept[order] = (result.kept_times, kept_slides(result, out))
    return ("A" not in kept["new"][1] and "A" in kept["old"][1],
            f"slide A scores 0.3 then 0.9 on its repeat, budget 2: kept {kept['new']} now, {kept['old']} "
            "with the previous order")


@entry("WI05-P3-1")
def wi05_p3_1(args, root):
    x = "meetingtool/frames/extract.py"
    mutations = {
        "compare with the previous candidate, not the previous distinct one": [
            (x, '                log_lines.append((timestamp, "near_duplicate (before the budget)"))\n                continue\n',
             '                log_lines.append((timestamp, "near_duplicate (before the budget)"))\n'
             '                last_distinct_gray = saved_gray\n                continue\n')],
        "<= becomes < at the window's +30 s edge": [
            ("meetingtool/frames/transcript.py", "self.times[index] <= timestamp + window",
             "self.times[index] < timestamp + window")],
        "boosted counted for every candidate": [
            (x, "            if score > base_score:\n                boosted += 1",
             "            if True:\n                boosted += 1")],
        "last distinct set only when the candidate enters the pool": [
            (x, '            last_distinct_gray = saved_gray\n            if len(pool) >= budget and score <= pool[0][0]:\n'
                '                discards["budget"] += 1\n'
                '                log_lines.append((timestamp, f"budget (score={score:.3f})"))\n                continue\n',
             '            if len(pool) >= budget and score <= pool[0][0]:\n                discards["budget"] += 1\n'
             '                log_lines.append((timestamp, f"budget (score={score:.3f})"))\n                continue\n'
             '            last_distinct_gray = saved_gray\n')],
    }
    outcome = {name: survives(root, change)[0] for name, change in mutations.items()}
    return all(outcome.values()), f"mutations surviving the frames tests: {outcome}"


@entry("WI05-P3-2")
def wi05_p3_2(args, root):
    with workspace() as tmp:
        two, one = tmp / "two.txt", tmp / "one.txt"
        two.write_text("[00:00:10] mirá esto\n[00:01:00] sigue\n", encoding="utf-8-sig")
        one.write_text("[00:00:10] mirá esto\nsin hora\n", encoding="utf-8-sig")
        blocks = transcript_module.read_blocks(two)
        try:
            transcript_module.read_blocks(one)
            refused = False
        except transcript_module.TranscriptError:
            refused = True
    return len(blocks) == 1 and refused, (f"a UTF-8 file with a BOM and two timed lines reads {len(blocks)} block(s); "
                                          f"with one timed line it is refused as having none: {refused}")


@entry("WI05-P3-3")
def wi05_p3_3(args, root):
    with workspace() as tmp:
        tab = tmp / "tab.txt"
        tab.write_text("[00:00:01] inicio\nAna\t1:22\nfijate el total\n", encoding="utf-8")
        tab_blocks = transcript_module.read_blocks(tab)
        spoken = tmp / "spoken.txt"
        spoken.write_text("[00:00:01] inicio\nwe meet tomorrow at  10:30\nok\n", encoding="utf-8")
        spoken_blocks = transcript_module.read_blocks(spoken)
    tab_missed = len(tab_blocks) == 1
    spoken_split = len(spoken_blocks) == 2 and spoken_blocks[1][0] == 630
    curly = not transcript_module.has_visual_reference("I\u2019m showing the total")
    filler = transcript_module.has_visual_reference("a ver, sigamos")
    return (tab_missed and spoken_split and curly and filler,
            f"speaker and time split by one tab not a new block {tab_missed}; spoken \"  10:30\" read as a block at "
            f"630 s {spoken_split}; curly apostrophe not matched {curly}; the filler \"a ver\" matched {filler}")


@entry("WI05-P3-4")
def wi05_p3_4(args, root):
    name = "tests.test_frames.SelectionTest.test_among_equal_scores_the_budget_keeps_the_earliest_as_the_original_did"
    change = [("tests/test_frames.py",
               '        with mock.patch.object(extract_module, "composite_score", lambda *args: next(scores)), \\\n'
               '                mock.patch.object(extract_module, "_is_near_duplicate", lambda *args: False):\n',
               '        with mock.patch.object(extract_module, "composite_score", lambda *args: next(scores)):\n')]
    passes, detail = survives(root, change, [name])
    return not passes, f"the tie-break test without its patch of _is_near_duplicate: {detail}"


@entry("WI05-P3-5")
def wi05_p3_5(args, root):
    x = "meetingtool/frames/extract.py"
    block = ("    references = None\n    if transcript is not None:\n        try:\n"
             "            references = VisualReferences.from_file(transcript)\n"
             "        except TranscriptError as error:\n            raise FramesError(str(error)) from error\n")
    opened = '        raise FramesError(f"cannot open recording {video_path}: {error}") from error\n'
    # The recording is closed when the moved read fails: a variant that leaves it open is caught on
    # Windows only because the test cannot delete a file still in use, not by what the test asserts.
    moved = block.replace("            raise FramesError", "            container.close()\n            raise FramesError")
    passes, detail = survives(root, [(x, block, ""), (x, opened, opened + moved)])
    return passes, f"transcript read moved after av.open, the recording closed if it fails: {detail}"


@entry("WI05-P3-6")
def wi05_p3_6(args, root):
    change = [("meetingtool/frames/extract.py",
               "    return previous_gray is not None and previous_gray.shape == gray.shape and ssim(previous_gray, gray) > threshold\n",
               "    if previous_gray is not None and previous_gray.shape != gray.shape:\n"
               "        raise AssertionError('shape mismatch reached')\n"
               "    return previous_gray is not None and ssim(previous_gray, gray) > threshold\n")]
    passes, detail = survives(root, change)
    return passes, f"the shape-mismatch branch made to raise: {detail}"


@entry("WI05-P3-7")
def wi05_p3_7(args, root):
    text = (REPO / "docs/evidence/01M3CSRVTHE26R86125VY676EJ/real-recording-run.txt").read_text(encoding="utf-8")
    unmeasured = "the internal gaps of 15 and 18 minutes seen before were not measured again" in text
    earlier = [p for p in REPO.glob("docs/evidence/*/*.txt") if PR6_WORK_ITEM not in str(p)
               and "210" in p.read_text(encoding="utf-8") and "115" in p.read_text(encoding="utf-8")]
    return (unmeasured and not earlier,
            f"the evidence says the 15- and 18-minute gaps were not measured again: {unmeasured}; "
            f"another evidence file carrying the before numbers: {[str(p.relative_to(REPO)) for p in earlier] or 'none'}")


@entry("WI05-P3-8")
def wi05_p3_8(args, root):
    size = 60 * 1024 * 1024
    with workspace() as tmp:
        docx = tmp / "big.docx"
        document = ('<?xml version="1.0" encoding="UTF-8"?><w:document xmlns:w="http://schemas.openxmlformats.org/'
                    'wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>Ana   0:04</w:t></w:r></w:p>'
                    '<w:p><w:r><w:t>' + "a" * size + '</w:t></w:r></w:p></w:body></w:document>')
        with zipfile.ZipFile(docx, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("word/document.xml", document)
        compressed = docx.stat().st_size
        blocks = transcript_module.read_blocks(docx)
    return (len(blocks) == 1 and len(blocks[0][1]) >= size,
            f"a {compressed // 1024} KB .docx is read whole: {len(blocks[0][1]) // (1024 * 1024)} MB of text, no limit")


# --- WI20: the project's data and what was paid ----------------------------------------------

def _wi20_folder(tmp):
    from tests.test_frames import write_teams_docx
    from tests import test_qa
    frames = tmp / "frames"
    frames.mkdir()
    write_teams_docx(tmp / "t.docx", test_qa.SPANISH)
    return frames


@entry("WI20-P3-1")
def wi20_p3_1(args, root):
    from meetingtool.summary import qa
    from tests import test_qa
    from tests.test_reading import KEY, FakeGemini
    with workspace() as tmp:
        frames = _wi20_folder(tmp)
        paid = []
        for model in ("gemini-flash-latest", "gemini-pro-latest"):
            with FakeGemini([test_qa.json_answer(test_qa.verbal())]) as fake:
                qa.write_register(frames, tmp / "t.docx", KEY, date="2026-09-25", language="es", model=model,
                                  endpoint=fake.endpoint, sleep=lambda s: None, retry_delays=())
                paid.append(len(fake.requests))
    return paid == [1, 0], f"the register's parts paid with one model, then with another: requests {paid}"


@entry("WI20-P3-2")
def wi20_p3_2(args, root):
    from unittest import mock
    from meetingtool import disk
    from meetingtool.report import document
    from tests import test_report
    with workspace() as tmp:
        data = tmp / "data"
        document.set_template(test_report.company_template(tmp / "a.docx"), data, name="la-de-antes.docx")
        real = disk.write_text

        def cut(path, *a, **k):
            if Path(path).name == document.TEMPLATE_RECORD:
                raise OSError(28, "No space left on device")
            return real(path, *a, **k)

        with mock.patch.object(disk, "write_text", cut):
            try:
                document.set_template(test_report.fields_template(tmp / "b.docx", ["{reunion}"]), data,
                                      name="la-nueva.docx")
            except OSError:
                pass
        info = document.template_info(data)
    new_template = bool(info.fields)  # the old template has no field, the new one has one
    return new_template and info.name == "la-de-antes.docx", (
        f"after a cut between the two files: the new template in place {new_template}, its name said {info.name!r}")


@entry("WI20-P3-3")
def wi20_p3_3(args, root):
    from unittest import mock
    from meetingtool.app import jobs
    with workspace() as tmp:
        data = tmp / "data"
        store.create_project(data, "Planta Demo", "c")
        with mock.patch.object(store, "rebuild_knowledge"):  # the process died before rewriting the copy
            store.add_meeting(data, "planta-demo", "Cierre", "2026-09-25", summary="La que no llego a la copia.")
        before = "La que no llego" in store.knowledge_context(data, "planta-demo")
        jobs.clear_leftovers(data)
        after = "La que no llego" in store.knowledge_context(data, "planta-demo")
    return not before and after, (f"knowledge read before the application starts again holds the meeting: {before}; "
                                  f"after it starts: {after}")


@entry("WI20-P3-4")
def wi20_p3_4(args, root):
    from meetingtool.summary import qa
    from tests import test_qa
    from tests.test_reading import KEY, FakeGemini
    with workspace() as tmp:
        frames = _wi20_folder(tmp)
        data = tmp / "data"
        store.create_project(data, "Planta Demo", "c")
        store.add_meeting(data, "planta-demo", "Relevamiento", "2026-09-10", summary="Antes.")
        record = next((data / "planta-demo" / "meetings").glob("*/meeting.json"))
        record.write_bytes(record.read_bytes()[:40])  # broken by hand
        with FakeGemini([test_qa.json_answer(test_qa.verbal())]) as fake:
            try:
                qa.write_register(frames, tmp / "t.docx", KEY, data_dir=data, project="planta-demo", title="Dudas",
                                  date="2026-09-25", language="es", endpoint=fake.endpoint, sleep=lambda s: None,
                                  retry_delays=())
                said = "saved"
            except qa.QAError as error:
                said = error.message.key
            paid = len(fake.requests)
    return paid == 1 and said == "summary.not_added", (
        f"with a record broken by hand: {paid} request(s) paid, then the meeting {said}")


@entry("WI20-P3-5")
def wi20_p3_5(args, root):
    from meetingtool.reading import gemini
    from meetingtool.summary import writer
    from tests import test_summary
    from tests.test_frames import write_teams_docx
    from tests.test_reading import KEY, FakeGemini
    with workspace() as tmp:
        frames = tmp / "frames"
        frames.mkdir()
        (frames / gemini.OUTPUT_NAME).write_text("# What each frame shows\n\n", encoding="utf-8")
        write_teams_docx(tmp / "t.docx", test_summary.SPANISH)
        text = test_summary.summary_text("es")
        with FakeGemini([test_summary.returning(text)] * 2) as fake:
            for _ in range(2):
                writer.write_summary(frames, tmp / "t.docx", KEY, language="es", endpoint=fake.endpoint,
                                     sleep=lambda s: None, retry_delays=())
            paid = len(fake.requests)
    return paid == 1, f"the same summary asked twice in one folder: {paid} request(s) paid"


@entry("WI20-P3-6")
def wi20_p3_6(args, root):
    env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    result = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_d1_*"],
                            cwd=REPO, capture_output=True, text=True, env=env, timeout=600)
    # six files: three need the kits and are skipped; WI21's (R05), WI22's (R02) and WI25's (R04) need none and run
    skipped = re.search(r"OK \(skipped=3\)", result.stderr)
    return bool(skipped) and "Ran 8 tests" in result.stderr, (
        f"without the kits: {result.stderr.strip().splitlines()[-1] if result.stderr.strip() else '?'}"
        f" ({result.stderr.count('Ran ')} run line)")


@entry("WI20-P3-7")
def wi20_p3_7(args, root):
    with workspace() as tmp:
        from tests.test_data_integrity import KeptRunTest
        import unittest
        test = KeptRunTest("test_a_report_that_fails_keeps_the_reading_and_the_summary_and_the_next_run_pays_nothing")
        kept = {}
        real = test.process

        def first_only(**fields):
            job = real(**fields)
            if not kept:
                folder = test.data / test.project / "processing" / job["kept"]["run"]
                kept["files"] = sorted(p.name for p in folder.iterdir())
            return job

        test.process = first_only
        result = unittest.TestResult()
        test.run(result)
    files = kept.get("files", [])
    return "transcript.docx" in files and any(n.startswith("frame_") for n in files), (
        f"a failed run that paid keeps, until it is processed again or discarded: {files}")


# --- WI21: reading to the end ------------------------------------------------------------------

OLD_TAIL = 120.0  # what WI10 added to the last line's start; the constant is gone, the number is the history


def _wi21_meeting(tmp, lines):
    """A 140 s synthetic recording (slide A to 10 s, B to 130 s, C after) and a transcript of `lines`."""
    video, transcript = tmp / "meeting.mp4", tmp / "meeting.txt"
    frames_fixture.write_video(video, [(frames_fixture.SLIDE_A, 10, False), (frames_fixture.SLIDE_B, 120, False),
                                       (frames_fixture.SLIDE_C, 10, False)])
    transcript.write_text(lines, encoding="utf-8")
    return video, transcript


@entry("WI21-P3-1")
def wi21_p3_1(args, root):
    with workspace() as tmp:
        video, transcript = _wi21_meeting(tmp, "[00:00:01] Ana:\nhola\n")
        result = extract_frames(video, tmp / "out", transcript=transcript)
    old_stop = 1 + OLD_TAIL
    would_have_read = int(old_stop * 2) + 1
    return result.samples > would_have_read, (
        f"a {result.duration:.0f} s recording whose transcript ends at 1 s: {result.samples} samples read, "
        f"about {would_have_read} if reading still stopped {OLD_TAIL:.0f} s after the last line")


@entry("WI21-P3-2")
def wi21_p3_2(args, root):
    with workspace() as tmp:
        video, transcript = _wi21_meeting(tmp, "[00:00:01] Ana:\nhola\n")
        result = extract_frames(video, tmp / "out", transcript=transcript)
        slides = kept_slides(result, tmp / "out")
    after = [(time, slide) for time, slide in zip(result.kept_times, slides) if time > 1 + OLD_TAIL]
    return bool(after), (f"the slide shown after the transcript's last line and the old stop time is kept: "
                         f"{[(round(time), slide) for time, slide in after]}")


@entry("WI21-P3-3")
def wi21_p3_3(args, root):
    with workspace() as tmp:
        video, transcript = _wi21_meeting(tmp, "[00:00:01] Ana:\nhola\n[00:10:00] Luis:\nchau\n")
        shown = run_python(["-m", "meetingtool.frames", "--video", str(video), "--out", str(tmp / "out"),
                            "--transcript", str(transcript)], cwd=REPO)
        usage = run_python(["-m", "meetingtool.frames", "--help"], cwd=REPO).stdout
    said = [line for line in shown.stdout.splitlines()
            if not line.startswith(("duration ", "discarded ", "candidates raised by the transcript"))]
    options = re.findall(r"^\s+(--[a-z-]+)", usage, flags=re.MULTILINE)
    return shown.returncode == 0 and not said and not {"--end", "--until", "--stop"} & set(options), (
        f"a transcript with a line at 10 min on a 140 s recording: exit {shown.returncode}, "
        f"{len(said)} lines about it; options {options}")


@entry("WI21-P3-4")
def wi21_p3_4(args, root):
    from meetingtool.summary import qa
    # An answer whose last turn begins at 0:20 and goes on explaining; a slide shown at 5:00 of that
    # explanation was extracted (WI21) but is not among the frames the register reads for the answer.
    frames = [Path(f"frame_001_t00-00-15.jpg"), Path(f"frame_002_t00-05-00.jpg")]
    span = [path.name for path in qa.span_frames(frames, 10, 20)]
    return "frame_002_t00-05-00.jpg" not in span, (
        f"an answer from 0:10 whose last turn begins at 0:20: the register reads {span}, not the slide at 5:00")


# --- WI22: the Word template's filter ---------------------------------------------------------

def _wi22_template(tmp, **edit):
    from tests import test_report
    return test_report.edit_package(test_report.company_template(tmp / "clean.docx"), tmp / "variant.docx", **edit)


def _wi22_accepted(path, tmp):
    """(whether the template is accepted, what is said: "accepted", or the refusal's items)."""
    from meetingtool.report import document
    try:
        document.set_template(path, tmp / "data")
    except document.ReportError as error:
        return False, " ".join(str(error).replace("\n  ", " | ").splitlines()[:1])
    return True, "accepted"


@entry("WI22-P3-1")
def wi22_p3_1(args, root):
    return None, ("needs Word: there is none here, as in the external review (contract WI22, not done). The forms "
                  "the filter refuses are shown to be real fields by a second reader of the XML "
                  "(tests/test_template_filter.py), not by Word")


@entry("WI22-P3-2")
def wi22_p3_2(args, root):
    with workspace() as tmp:
        part = b'<?xml version="1.0"?><a>' + b"x" * (40 * 1024 * 1024) + b"</a>"
        path = _wi22_template(tmp, add={"customXml/item2.xml": part})
        stored = path.stat().st_size
        accepted, said = _wi22_accepted(path, tmp)
    return accepted and stored < 1_000_000, (
        f"a package of {stored / 1024:.0f} KB holding one part of {len(part) / 2 ** 20:.0f} MB: {said}")


@entry("WI22-P3-3")
def wi22_p3_3(args, root):
    from meetingtool.report import document
    from tests import test_report, test_template_filter as forms
    first, second = b' QUOTE "INCLUDETE" ', b' QUOTE "XT" '
    built = forms.paragraph(forms.mark(b"begin"), forms.mark(b"begin"), forms.instruction(first), forms.mark(b"end"),
                            forms.mark(b"begin"), forms.instruction(second), forms.mark(b"end"),
                            forms.instruction(forms.TARGET), forms.mark(b"end"))
    with workspace() as tmp:
        path = _wi22_template(tmp, insert={"word/document.xml": (b"<w:sectPr", built)})
        accepted, said = _wi22_accepted(path, tmp)
        found = document.active_content(test_report.package_parts(path))
    return accepted and not found, (
        f"a field whose name is the result of two QUOTE fields (INCLUDETE + XT): {said}; the filter found {found}")


@entry("WI22-P3-4")
def wi22_p3_4(args, root):
    from tests import test_report
    from tests import test_template_filter as forms
    address = "file://inventado.invalid/share/x.docm"
    field = forms.complex_field(b' HYPERLINK "' + address.encode() + b'" ')
    with workspace() as tmp:
        path = _wi22_template(tmp, insert={
            "word/_rels/document.xml.rels": (b"</Relationships>", test_report.relationship("hyperlink", address)),
            "word/document.xml": (b"<w:sectPr", field)})
        accepted, said = _wi22_accepted(path, tmp)
    return accepted, f"a hyperlink (relationship and field) to {address}: {said}"


@entry("WI22-P3-5")
def wi22_p3_5(args, root):
    from tests import test_template_filter as forms
    field = forms.complex_field(b' FETCHREMOTE "https://example.invalid/x.png" ')
    with workspace() as tmp:
        path = _wi22_template(tmp, insert={"word/document.xml": (b"<w:sectPr", field)})
        accepted, said = _wi22_accepted(path, tmp)
    return accepted, f"a field named FETCHREMOTE (invented) with an address: {said}"


# --- WI23: the fields a template may hold -----------------------------------------------------

@entry("WI23-P3-1")
def wi23_p3_1(args, root):
    from tests import test_template_filter as forms
    field = forms.complex_field(b' ADDIN ZOTERO_ITEM CSL_CITATION {"citationID":"x"} ')
    with workspace() as tmp:
        path = _wi22_template(tmp, insert={"word/document.xml": (b"<w:sectPr", field)})
        accepted, said = _wi22_accepted(path, tmp)
        from meetingtool.report import document
        stored = document.stored_template(tmp / "data")
    return not accepted and "a ADDIN field" in said and stored is None, (
        f"a template with an ADDIN field (a citation manager's, made-up item): {said}; stored: {stored is not None}")


@entry("WI22-P3-6")
def wi22_p3_6(args, root):
    from meetingtool.report import document
    from tests import test_report
    font = b"\x00" * 32
    with workspace() as tmp:
        path = _wi22_template(tmp, add={
            "word/fonts/font1.odttf": font,
            "word/_rels/fontTable.xml.rels": test_report.RELATIONSHIPS % test_report.relationship(
                "font", "fonts/font1.odttf", external=False)},
            insert={"[Content_Types].xml": (b"</Types>", b'<Default Extension="odttf" ContentType="application/'
                                            b'vnd.openxmlformats-officedocument.obfuscatedFont"/>')})
        accepted, said = _wi22_accepted(path, tmp)
        frames = tmp / "frames"
        frames.mkdir()
        (frames / document.SUMMARY_NAME).write_text(test_report.summary_text(screen="Nada en pantalla."),
                                                    encoding="utf-8")
        document.build_report(frames, data_dir=tmp / "data")
        with zipfile.ZipFile(frames / document.OUTPUT_NAME) as report:
            arrived = "word/fonts/font1.odttf" in report.namelist()
    return accepted and arrived, f"a template with an embedded font part: {said}; the font is in the report: {arrived}"


@entry("WI22-P3-7")
def wi22_p3_7(args, root):
    part = '<?xml version="1.0" encoding="Shift_JIS"?><a>\u65e5\u672c\u8a9e</a>'.encode("shift_jis")
    with workspace() as tmp:
        path = _wi22_template(tmp, add={"customXml/item2.xml": part})
        accepted, said = _wi22_accepted(path, tmp)
    return not accepted and "customXml/item2.xml: is not readable XML" in said, (
        f"a customXml part in Shift_JIS: {said}")


@entry("WI23-P3-2")
def wi23_p3_2(args, root):
    from tests import test_markup_compatibility as compat
    from tests import test_template_filter as forms
    # Word reads one branch: with the Choice's namespace understood, only PAGE; the filter reads both.
    inside = compat.alternate(forms.complex_field(b" PAGE "), forms.complex_field(b" ADDIN x "))
    with workspace() as tmp:
        path = _wi22_template(tmp, insert={"word/document.xml": (b"<w:sectPr", inside)})
        accepted, said = _wi22_accepted(path, tmp)
    return not accepted and "a ADDIN field" in said, (
        f"an alternative with PAGE in its Choice and a whole ADDIN field in its Fallback: {said}")


@entry("WI23-P3-3")
def wi23_p3_3(args, root):
    from meetingtool.report import document
    from tests import test_markup_compatibility as compat
    from tests import test_template_filter as forms
    # The begin is in a branch of an alternative; the instruction, outside, is loose text joined with the one
    # before it, so only its first word (an allowed one) is read.
    arranged = (compat.alternate(forms.mark(b"begin"), forms.run(b"<w:t>y</w:t>"))
                + forms.paragraph(forms.instruction(b" PAGE "), forms.instruction(b" ADDIN x "), forms.mark(b"end")))
    with workspace() as tmp:
        path = _wi22_template(tmp, insert={"word/document.xml": (b"<w:sectPr", arranged)})
        accepted, said = _wi22_accepted(path, tmp)
        try:
            document.check_active_content(path)
            checked = True
        except document.ReportError:
            checked = False
    return accepted and checked, (
        f"a field whose begin is in a branch of an alternative and whose instruction is outside, an ADDIN field with "
        f"no address: the template is {said}; the report's last check lets it through: {checked}")


def _wi24_timed(tmp):
    """A transcript in the shape of the first real meeting, made up: a title, then each time alone on
    its line and the words after it."""
    path = tmp / "timed.docx"
    frames_fixture.write_timed_docx(path, frames_fixture.TIMED)
    return path


@entry("WI24-P3-1")
def wi24_p3_1(args, root):
    from meetingtool.summary import qa, writer
    from tests.test_reading import KEY, FakeGemini
    with workspace() as tmp:
        path = _wi24_timed(tmp)
        turns = transcript_module.read_turns(path)
        prompt = writer.build_prompt(turns, "", "es")
        folder = tmp / "frames"
        folder.mkdir()
        with FakeGemini() as fake:
            try:
                qa.write_register(folder, path, KEY, language="es", endpoint=fake.endpoint, sleep=lambda s: None)
                refused = ""
            except qa.QAError as error:
                refused = error.message.key
            sent = len(fake.requests)
    named = [speaker for _, speaker, _ in turns if speaker]
    return not named and refused == "qa.needs_speakers" and sent == 0 and "] Buen día" in prompt, (
        f"{len(turns)} turns, speakers named: {named}; the summary's request has the turns with no name; "
        f"the register: {refused or 'written'} after {sent} request(s)")


@entry("WI24-P3-2")
def wi24_p3_2(args, root):
    return None, ("needs the real Gemini and the owner's meeting: the tests here are synthetic (a reading of 141 "
                  "frames with Gemini faked), which show what the request says and what the check lets through, not "
                  "whether the real model now copies the names right. The owner's own run will show it")


@entry("WI24-P3-3")
def wi24_p3_3(args, root):
    with workspace() as tmp:
        spoken = tmp / "spoken.txt"
        spoken.write_text("Ana Pérez   0:04\nEl cierre es a las\n10:30\nsegún dijeron.\n", encoding="utf-8")
        turns = transcript_module.read_turns(spoken)
    split = [(start, speaker) for start, speaker, _ in turns]
    return split == [(4, "Ana Pérez"), (630, "")], (
        f"a line of someone's words that is only a time, in a transcript with speakers: blocks {split} (it "
        f"reproduces if the second block starts at 630 s with no speaker)")


@entry("WI24-P3-4")
def wi24_p3_4(args, root):
    from meetingtool.app import jobs
    from meetingtool.summary import writer
    with workspace() as tmp:
        data = tmp / "data"
        store.create_project(data, "Planta Demo", "c")
        uploads = jobs.Uploads(data)
        path = uploads.new_path(".docx")
        frames_fixture.write_timed_docx(path, frames_fixture.TIMED)
        try:
            request = jobs.check_request({"project": "planta-demo", "title": "Dudas", "date": "2026-10-06",
                                          "format": "qa", "transcript": path.name}, data, uploads,
                                         writer.MEETING_TYPES, ("es", "en"))
            said = f"accepted as a {request['format']} request"
        except jobs.JobError as error:
            request, said = None, f"refused: {error.message.key}"
    return request is not None, (
        f"the application's request for a register with a transcript that names no one: {said}")


def _wi25_register(tmp, said, data, date):
    """None if the register `data` is accepted over the Spanish test transcript with these lines more
    (said by Juan Gómez, after minute 2:30) and a meeting of `date`; otherwise the refusal's text."""
    from meetingtool.summary import qa
    from tests import test_qa
    from tests.test_reading import KEY, FakeGemini
    path = tmp / "t.docx"
    frames_fixture.write_teams_docx(path, test_qa.SPANISH[:4] + [("Juan Gómez", f"3:{10 + number}", line)
                                                                 for number, line in enumerate(said)]
                                    + test_qa.SPANISH[4:])
    folder = tmp / "frames"
    folder.mkdir()
    with FakeGemini([test_qa.json_answer(data)] * 2) as fake:
        try:
            qa.write_register(folder, path, KEY, date=date, language="es", endpoint=fake.endpoint,
                              sleep=lambda s: None, retry_delays=())
            return None
        except qa.QAError as error:
            return str(error)


def _wi25_shown(refusal):
    """What a refusal of the register says: the piece that names the date or the figure."""
    if refusal is None:
        return "accepted"
    found = re.search(r"writes a (?:date|figure)[^()]*\([^)]*\)", refusal)
    return f"refused ({found.group() if found else refusal[-80:]})"


@entry("WI25-P3-1")
def wi25_p3_1(args, root):
    from meetingtool.summary import writer
    from tests import test_summary
    headings = writer.required_headings("es")
    text = test_summary.summary_text("es", empty=headings[2], emptied="Se entrega el 25 de septiembre de 2030 por "
                                                                       "US$ 48.000.")
    try:
        writer.check_summary(test_summary.answer(text), headings, "es")
        said = "returned the summary"
    except writer.SummaryError as error:
        said = f"refused: {error.message.key}"
    return said == "returned the summary", (
        f"a summary that writes 25 de septiembre de 2030 and US$ 48.000, which no transcript said, in its "
        f"decisions: check_summary {said} (it has no transcript to compare with)")


@entry("WI25-P3-2")
def wi25_p3_2(args, root):
    from tests import test_qa
    with workspace() as tmp:
        refusal = _wi25_register(tmp, ["Lo mandamos el 15 de enero."],
                                 test_qa.changed(test_qa.verbal(), 2, deadline="el 15 de enero de 2027"), "2026-12-10")
    return refusal is not None and "15/1/2027" in refusal, (
        f"a meeting of 2026-12-10, a transcript that says 'el 15 de enero' and a deadline 'el 15 de enero de 2027': "
        f"{_wi25_shown(refusal)}")


@entry("WI25-P3-3")
def wi25_p3_3(args, root):
    from tests import test_qa
    figures = ["Se trabaja en 3 turnos."]
    data = test_qa.changed(test_qa.verbal(), knowledge=dict(test_qa.REGISTER["knowledge"], figures=figures))
    with workspace() as tmp:
        refusal = _wi25_register(tmp, ["Trabajamos en tres turnos."], data, "2026-09-25")
    return refusal is not None and "(3)" in refusal, (
        f"the transcript says 'tres turnos' and the figure is 'Se trabaja en 3 turnos.': {_wi25_shown(refusal)}")


@entry("WI25-P3-4")
def wi25_p3_4(args, root):
    from meetingtool.summary import writer
    from tests import test_summary
    headings = writer.required_headings("es")
    text = test_summary.summary_text("es", empty=headings[2], emptied="| Decisión | Responsable |\n|---|---|")
    try:
        writer.check_summary(test_summary.answer(text), headings, "es")
        said = "accepted"
    except writer.SummaryError as error:
        said = f"refused: {error.message.key}"
    return said == "accepted", f"the decisions are a table with its header row and no rows: the summary is {said}"


@entry("WI25-P3-5")
def wi25_p3_5(args, root):
    from tests import test_qa
    data = test_qa.changed(test_qa.verbal(), 2, deadline="el 25 de septiembre de 2030")
    with workspace() as tmp:
        refusal = _wi25_register(tmp, ["Son 2030 cajas."], data, "2026-09-25")
    return refusal is None, (
        f"the transcript says '2030 cajas' and 'el 25 de septiembre', a meeting of 2026, and the deadline is 'el 25 "
        f"de septiembre de 2030': {_wi25_shown(refusal)}")


@entry("WI25-P3-6")
def wi25_p3_6(args, root):
    from tests import test_qa
    data = test_qa.changed(test_qa.verbal(), knowledge=dict(test_qa.REGISTER["knowledge"],
                                                           figures=["Pesa 1,25 kilos."]))
    with workspace() as tmp:
        refusal = _wi25_register(tmp, ["La pieza pesa 1,250 kilos."], data, "2026-09-25")
    return refusal is not None and "(1,25)" in refusal, (
        f"the transcript says '1,250 kilos' (read as 1250) and the figure is 'Pesa 1,25 kilos': "
        f"{_wi25_shown(refusal)}")


# --- Running ---------------------------------------------------------------------------------

STATE_WORDS = (("not reproducible", "not-reproducible"), ("open", "open"), ("fixed", "fixed"))


def register_claims():
    """[(id, claim)] for every entry row of REGISTER.md. The claim is read from
    the first words of the row's State cell (the one before the last); the
    script keeps no copy of its own. None when the words are none of the three."""
    rows = []
    for line in REGISTER.read_text(encoding="utf-8").splitlines():
        match = re.match(r"^\| `([A-Z0-9-]+)` \|", line)
        if match:
            state = [cell.strip() for cell in line.strip().strip("|").split("|")][-2]
            rows.append((match.group(1), next((claim for words, claim in STATE_WORDS if state.startswith(words)), None)))
    return rows


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("ids", nargs="*", help="entries to run (default: all)")
    parser.add_argument("--ingol-repo", type=Path, help="local clone of INGOL, for H1, H3, H4 and H6")
    parser.add_argument("--flip", action="append", default=[], help="invert this entry's claim, to see the check fail")
    args = parser.parse_args(argv)
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8")  # entries print Ł, →; Windows' code page cannot

    rows = register_claims()
    in_register, in_script = [i for i, _ in rows], [identifier for identifier, *_ in ENTRIES]
    claims = dict(rows)
    duplicated = sorted({i for i in in_register if in_register.count(i) > 1})
    only_register = sorted(set(in_register) - set(in_script))
    only_script = sorted(set(in_script) - set(in_register))
    no_state = sorted(i for i, claim in rows if claim is None)
    if duplicated or only_register or only_script or no_state:
        print(f"REGISTER MISMATCH: duplicated {duplicated}, without a reproduction {only_register}, "
              f"without a register entry {only_script}, state not open/fixed/not reproducible {no_state}")
        return 1
    unknown = sorted(set(args.ids + args.flip) - set(in_script))
    if unknown:
        parser.error(f"unknown entries: {unknown}")

    head = git("rev-parse", "HEAD", cwd=REPO).stdout.strip()
    print(f"# limitations register reproduction\ncommit: {head}\npython: {sys.version.split()[0]}\n"
          f"ingol: {args.ingol_repo or 'not given, INGOL entries skipped'}\n")
    counts = {"MATCH": 0, "MISMATCH": 0, "SKIPPED": 0, "ERROR": 0}
    with workspace() as root:
        for identifier, needs_ingol, function in ENTRIES:
            if args.ids and identifier not in args.ids:
                continue
            claim = claims[identifier]
            if identifier in args.flip:
                claim = {"open": "fixed", "fixed": "open", "not-reproducible": "open"}[claim]
            if needs_ingol and args.ingol_repo is None:
                counts["SKIPPED"] += 1
                print(f"{identifier:10} claim={claim:16} SKIPPED (needs --ingol-repo)")
                continue
            started = time.monotonic()
            try:
                reproduced, observed = function(args, root)
            except Exception as error:  # a reproduction that cannot run is reported, never counted as a match
                counts["ERROR"] += 1
                print(f"{identifier:10} claim={claim:16} ERROR {type(error).__name__}: {error}")
                continue
            seen = {True: "open", False: "fixed", None: "not-reproducible"}[reproduced]
            verdict = "MATCH" if seen == claim else "MISMATCH"
            counts[verdict] += 1
            print(f"{identifier:10} claim={claim:16} seen={seen:16} {verdict} ({time.monotonic() - started:.1f}s)\n"
                  f"           {observed}")
    print(f"\n{counts}")
    return 0 if counts["MISMATCH"] == 0 and counts["ERROR"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
