"""Reproduces every entry of the limitations register (REGISTER.md).

Run from the repository root:

    python docs/limitations/reproduce.py                        # every project entry
    python docs/limitations/reproduce.py WI05-P3-2 WI02-P3-E    # some entries
    python docs/limitations/reproduce.py --ingol-repo C:/path/to/ingol   # INGOL's too

Every entry carries the register's claim: `open` (the limitation reproduces),
`fixed` (it no longer does) or `not-reproducible` (it cannot be reproduced
here; the entry says why). The script runs each reproduction, prints what it
saw, and exits 1 when a result differs from the claim, so the register
cannot go stale in silence when a limitation is fixed. Before running
anything it compares the register's entry identifiers with its own and
exits 1 if they differ. `--flip ID` inverts one claim on purpose, to see the
check fail.

Nothing is written inside the repository and nothing goes to the network:
every file is made in a temporary folder. The INGOL entries (H1, H3, H4,
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

from meetingtool import repository_guard  # noqa: E402
from meetingtool.frames import extract as extract_module  # noqa: E402
from meetingtool.frames import transcript as transcript_module  # noqa: E402
from meetingtool.frames.extract import extract_frames  # noqa: E402
from meetingtool.projects import store  # noqa: E402
from tests import test_frames as frames_fixture  # noqa: E402

ENTRIES = []


def entry(identifier, claim, needs_ingol=False):
    def register(function):
        ENTRIES.append((identifier, claim, needs_ingol, function))
        return function
    return register


def git(*args, cwd=None, check=True):
    return subprocess.run(["git", *args], cwd=cwd, check=check, capture_output=True, text=True)


def run_python(args, cwd, env=None):
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
            subprocess.run(["go", "build", "-o", str(binary), package], cwd=self.installation, check=True,
                           capture_output=True)

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


@entry("H1", "open", needs_ingol=True)
def h1(args, root):
    ing = ingol(args, root)
    target = root / "h1-existing-project"
    target.mkdir()
    (target / "main.py").write_text("print('an existing project')\n", encoding="utf-8")
    result = ing.run("init", str(target))
    refused = result.returncode != 0 and "is not empty" in result.stderr
    return refused, f"ingol init on a folder with one file: exit {result.returncode}: {result.stderr.strip()}"


@entry("H2", "not-reproducible")
def h2(args, root):
    return None, ("needs a private repository on GitHub's free plan; the owner's account has Pro, where the "
                  "protection exists. Source: GitHub's plans documentation, read 2026-09-25 (INGOL D-162)")


@entry("H3", "open", needs_ingol=True)
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


@entry("H4", "open", needs_ingol=True)
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


@entry("H5", "open")
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


@entry("H6", "open", needs_ingol=True)
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

@entry("WI01-P2-1", "fixed")
def wi01_p2_1(args, root):
    paths = ["a.mp3", "a.mkv", "a.webm", "transcript.txt", "report_acme.md", "handoff_1.json", "frames/f1.jpg"]
    missed = [p for p in paths if not repository_guard.is_meeting_data(p)]
    return bool(missed), f"guard misses {missed or 'none'} of {paths} (widened by a977049, WI02)"


@entry("WI01-P2-2", "fixed")
def wi01_p2_2(args, root):
    code = ["meetingtool/projects/store.py", "meetingtool/frames/extract.py", "tests/frames/x.py"]
    wrongly = [p for p in code if ignored(p)]
    return bool(wrongly), f"code paths ignored by .gitignore: {wrongly or 'none'} (anchored by ba02528; generated/ is H6)"


@entry("WI01-P2-3", "open")
def wi01_p2_3(args, root):
    tested, integrated = "165cfff6a3b35fb7006c800afebbbe0dd7fa4d9b", "37294079a15dd4690cd9977a71f511d76221f204"
    changed = git("diff", "--name-only", tested, integrated, cwd=REPO).stdout.split()
    allowed = all(p.startswith(f"docs/evidence/{PR6_WORK_ITEM}/") or f"{PR6_WORK_ITEM}/approvals/" in p for p in changed)
    return (bool(changed) and allowed,
            f"WI05: the tested commit 165cfff and the integrated 3729407 differ in {len(changed)} files, "
            f"all evidence or approval: {allowed}")


@entry("WI01-P3-1", "fixed")
def wi01_p3_1(args, root):
    upper = ["a.MP4", "deep/B.DOCX", "c.Mp3"]
    missed = [p for p in upper if not ignored(p)]
    return bool(missed), f"upper-case extensions not ignored on Linux matching: {missed or 'none'} (ba02528)"


@entry("WI01-P3-2", "open")
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


@entry("WI01-P3-3", "open")
def wi01_p3_3(args, root):
    env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    result = run_python(["-m", "unittest", "discover", "-s", str(REPO / "tests")], cwd=root, env=env)
    cannot_import = result.returncode != 0 and "No module named 'meetingtool'" in result.stderr
    return cannot_import, (f"suite started from outside the repository root: exit {result.returncode}, "
                           f"\"No module named 'meetingtool'\" {'shown' if cannot_import else 'not shown'}")


# --- Work item 2, the guard (01M3CG1XGTT95MT2WNTMH1TXR2) --------------------------------------

@entry("WI02-P2-A", "open")
def wi02_p2_a(args, root):
    fixtures = ["tests/fixtures/slide.png", "tests/fixtures/sample.mp4", "tests/fixtures/transcript_sample.txt"]
    flagged = [p for p in fixtures if repository_guard.is_meeting_data(p)]
    return flagged == fixtures, f"test fixtures rejected by the guard: {flagged}"


@entry("WI02-P2-B", "open")
def wi02_p2_b(args, root):
    path = "meetingtool/projects/acme/memory.json"
    guard, gitignore = repository_guard.is_meeting_data(path), ignored(path)
    return (not guard and not gitignore, f"{path}: guard flags it {guard}, .gitignore ignores it {gitignore}")


@entry("WI02-P3-A", "open")
def wi02_p3_a(args, root):
    paths = ["report_acme.md", "handoff_1.json", "transcript.txt", "Frames/x/f.json", "MEETINGS/a/b.json"]
    not_ignored = [p for p in paths if not ignored(p)]
    guarded = [p for p in paths if repository_guard.is_meeting_data(p)]
    return (not_ignored == paths and guarded == paths,
            f"not ignored by .gitignore on Linux matching: {not_ignored}; all caught by the guard: {guarded == paths}")


@entry("WI02-P3-B", "open")
def wi02_p3_b(args, root):
    result = run_python(["-m", "unittest", "tests.test_repository_guard.GitignoreTest"], cwd=REPO)
    upper = ignored("Frames/x/file.json")
    return (result.returncode == 0 and not upper,
            f"GitignoreTest exit {result.returncode} while Frames/x/file.json is ignored: {upper}")


@entry("WI02-P3-C", "open")
def wi02_p3_c(args, root):
    env = {**os.environ, "GIT_DIR": str(root / "no-such-git-dir")}
    broken = subprocess.run(["git", "-C", str(REPO), "check-ignore", "-q", "--no-index", "x.mp4"],
                            capture_output=True, env=env).returncode
    name = "tests.test_repository_guard.GitignoreTest.test_a_code_folder_named_projects_below_the_root_is_not_ignored"
    result = run_python(["-m", "unittest", name], cwd=REPO, env=env)
    return (broken not in (0, 1) and result.returncode == 0,
            f"with git broken (check-ignore exit {broken}) the \"not ignored\" test exits {result.returncode}")


@entry("WI02-P3-D", "open")
def wi02_p3_d(args, root):
    paths = ["export.zip", "attendees.csv", "slides.ppt", "budget.xls", "notas-reunion.txt"]
    missed = [p for p in paths if not repository_guard.is_meeting_data(p)]
    return missed == paths, f"not flagged by the guard: {missed}"


@entry("WI02-P3-E", "open")
def wi02_p3_e(args, root):
    return (repository_guard.is_meeting_data("transcription.md"),
            f"transcription.md flagged as meeting data: {repository_guard.is_meeting_data('transcription.md')}")


# --- Work item 3, projects and meeting memory (01M3CGKPV51VTTK3S8V1JEF4HW) ----------------------
# The review lists its P3 findings unnumbered; they are numbered here in the review's order.

@entry("WI03-P2-1", "fixed")
def wi03_p2_1(args, root):
    data = root / "wi03-p2-1"
    store.create_project(data, "Acme", "Acme")
    try:
        store.add_meeting(data, "../repo/x", "Kickoff", "2026-09-25")
    except store.ProjectError as error:
        return False, f"a path as project id is refused: {error} (91231a1)"
    return True, "a path as project id was accepted"


@entry("WI03-P2-2", "fixed")
def wi03_p2_2(args, root):
    name = "tests.test_projects.CommandLineTest.test_non_ansi_characters_survive_redirected_output"
    result = run_python(["-m", "unittest", name], cwd=REPO)
    return result.returncode != 0, f"redirected output with Łódź, ✓, →: test exit {result.returncode} (91231a1)"


@entry("WI03-P2-3", "fixed")
def wi03_p2_3(args, root):
    pyproject = (REPO / "pyproject.toml").read_text(encoding="utf-8")
    declared = 'include = ["meetingtool", "meetingtool.*"]' in pyproject
    result = run_python(["-m", "unittest", "tests.test_frames.PackagingTest"], cwd=REPO)
    return (not (declared and result.returncode == 0),
            f"subpackages declared in pyproject.toml: {declared}; PackagingTest exit {result.returncode} "
            "(c38353c; building a wheel would need setuptools, not installed here)")


@entry("WI03-P3-1", "open")
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


@entry("WI03-P3-2", "open")
def wi03_p3_2(args, root):
    try:
        store.create_project(root / "wi03-p3-2", "x" * 300, "c")
    except store.ProjectError as error:
        return False, f"ProjectError: {error}"
    except OSError as error:
        return True, f"a 300-character title raises a raw {type(error).__name__}, not ProjectError"
    return False, "a 300-character title was accepted"


@entry("WI03-P3-3", "open")
def wi03_p3_3(args, root):
    data = root / "wi03-p3-3"
    store.create_project(data, "Acme", "c")
    store.add_meeting(data, "acme", "Kickoff", "2026-09-25", summary="line one\r\nline two")
    returned, read = store.rebuild_knowledge(data, "acme"), store.knowledge_context(data, "acme")
    return returned != read, f"rebuild_knowledge's return equals knowledge_context's read: {returned == read}"


@entry("WI03-P3-4", "open")
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
    return False, "no error"


@entry("WI03-P3-5", "open")
def wi03_p3_5(args, root):
    with mock.patch.dict(os.environ, {store.DATA_DIR_ENV: "~/vmt-data"}):
        folder = store.default_data_dir()
    return str(folder).startswith("~"), f"{store.DATA_DIR_ENV}=~/vmt-data gives the folder {folder}"


@entry("WI03-P3-6", "open")
def wi03_p3_6(args, root):
    data = root / "wi03-p3-6"
    store.create_project(data, "Acme", "c")
    with mock.patch.object(store, "_now_utc", lambda: "2026-09-25T12:00:00Z"):
        store.add_meeting(data, "acme", "Zeta review", "2026-09-25")
        store.add_meeting(data, "acme", "Alpha review", "2026-09-25")
    order = [m["title"] for m in store.list_meetings(data, "acme")]
    return order == ["Alpha review", "Zeta review"], f"added Zeta then Alpha in the same second, listed {order}"


@entry("WI03-P3-7", "open")
def wi03_p3_7(args, root):
    text = (REPO / "docs/evidence/01M3CGKPV51VTTK3S8V1JEF4HW/owner-machine-run.txt").read_text(encoding="utf-8")
    held = [flag for flag in ("--context", "--summary", "--key-point") if flag in text]
    return len(held) == 3, f"the WI03-AC05 evidence holds, besides titles: {held} (synthetic values)"


# --- Work item 4, frames (01M3CGKPVGGAAK06A1RD5C3XWZ) ------------------------------------------

@entry("WI04-P2-1", "fixed")
def wi04_p2_1(args, root):
    name = "tests.test_frames.SelectionTest.test_among_equal_scores_the_budget_keeps_the_earliest_as_the_original_did"
    result = run_python(["-m", "unittest", name], cwd=REPO)
    return result.returncode != 0, f"tie-break test exit {result.returncode} (5f20bf7)"


@entry("WI04-P3-1", "open")
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


@entry("WI04-P3-2", "open")
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


@entry("WI04-P3-3", "fixed")
def wi04_p3_3(args, root):
    result = run_python(["-m", "unittest", "tests.test_frames.NoNetworkTest.test_a_url_is_refused_before_anything_opens_it"],
                        cwd=REPO)
    return result.returncode != 0, f"URL refused before av.open: test exit {result.returncode} (5f20bf7)"


@entry("WI04-P3-4", "fixed")
def wi04_p3_4(args, root):
    text = (REPO / "docs/evidence/01M3CGKPVGGAAK06A1RD5C3XWZ/real-recording-run.txt").read_text(encoding="utf-8")
    sourced = "the count of JPEG files in its own output folder" in text
    return not sourced, f"the 76-frame figure carries its source: {sourced} (67a6e4e)"


@entry("WI04-P3-5", "open")
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


@entry("WI04-P3-6", "open")
def wi04_p3_6(args, root):
    with workspace() as tmp:
        video, out = tmp / "v.mp4", tmp / "out"
        frames_fixture.write_video(video, [(frames_fixture.SLIDE_A, 6, False), (frames_fixture.SLIDE_B, 6, False)])
        result = extract_frames(video, out)
    accounted = result.candidates + result.discards["low_score"] + result.discards["minimum_gap"]
    return result.samples == accounted + 1, (f"{result.samples} samples, {accounted} of them a candidate or a logged "
                                             "discard: the first one appears nowhere")


@entry("WI04-P3-7", "open")
def wi04_p3_7(args, root):
    import av
    floor = re.search(r'"av>=(\d+)"', (REPO / "pyproject.toml").read_text(encoding="utf-8")).group(1)
    return (not av.__version__.startswith(f"{floor}."),
            f"declared floor av>={floor}; the only PyAV here, and in every recorded run, is {av.__version__}")


# --- Work item 5, frame selection (01M3CSRVTHE26R86125VY676EJ) ---------------------------------

@entry("WI05-P2-1", "open")
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


@entry("WI05-P3-1", "open")
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


@entry("WI05-P3-2", "open")
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


@entry("WI05-P3-3", "open")
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


@entry("WI05-P3-4", "open")
def wi05_p3_4(args, root):
    name = "tests.test_frames.SelectionTest.test_among_equal_scores_the_budget_keeps_the_earliest_as_the_original_did"
    change = [("tests/test_frames.py",
               '        with mock.patch.object(extract_module, "composite_score", lambda *args: next(scores)), \\\n'
               '                mock.patch.object(extract_module, "_is_near_duplicate", lambda *args: False):\n',
               '        with mock.patch.object(extract_module, "composite_score", lambda *args: next(scores)):\n')]
    passes, detail = survives(root, change, [name])
    return not passes, f"the tie-break test without its patch of _is_near_duplicate: {detail}"


@entry("WI05-P3-5", "open")
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


@entry("WI05-P3-6", "open")
def wi05_p3_6(args, root):
    change = [("meetingtool/frames/extract.py",
               "    return previous_gray is not None and previous_gray.shape == gray.shape and ssim(previous_gray, gray) > threshold\n",
               "    if previous_gray is not None and previous_gray.shape != gray.shape:\n"
               "        raise AssertionError('shape mismatch reached')\n"
               "    return previous_gray is not None and ssim(previous_gray, gray) > threshold\n")]
    passes, detail = survives(root, change)
    return passes, f"the shape-mismatch branch made to raise: {detail}"


@entry("WI05-P3-7", "open")
def wi05_p3_7(args, root):
    text = (REPO / "docs/evidence/01M3CSRVTHE26R86125VY676EJ/real-recording-run.txt").read_text(encoding="utf-8")
    unmeasured = "the internal gaps of 15 and 18 minutes seen before were not measured again" in text
    earlier = [p for p in REPO.glob("docs/evidence/*/*.txt") if PR6_WORK_ITEM not in str(p)
               and "210" in p.read_text(encoding="utf-8") and "115" in p.read_text(encoding="utf-8")]
    return (unmeasured and not earlier,
            f"the evidence says the 15- and 18-minute gaps were not measured again: {unmeasured}; "
            f"another evidence file carrying the before numbers: {[str(p.relative_to(REPO)) for p in earlier] or 'none'}")


@entry("WI05-P3-8", "open")
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


# --- Running ---------------------------------------------------------------------------------

def register_ids():
    return re.findall(r"^\| `([A-Z0-9-]+)` \|", REGISTER.read_text(encoding="utf-8"), re.MULTILINE)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("ids", nargs="*", help="entries to run (default: all)")
    parser.add_argument("--ingol-repo", type=Path, help="local clone of INGOL, for H1, H3, H4 and H6")
    parser.add_argument("--flip", action="append", default=[], help="invert this entry's claim, to see the check fail")
    args = parser.parse_args(argv)
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8")  # entries print Ł, →; Windows' code page cannot

    in_register, in_script = register_ids(), [identifier for identifier, *_ in ENTRIES]
    duplicated = sorted({i for i in in_register if in_register.count(i) > 1})
    only_register = sorted(set(in_register) - set(in_script))
    only_script = sorted(set(in_script) - set(in_register))
    if duplicated or only_register or only_script:
        print(f"REGISTER MISMATCH: duplicated {duplicated}, without a reproduction {only_register}, "
              f"without a register entry {only_script}")
        return 1
    unknown = sorted(set(args.ids + args.flip) - set(in_script))
    if unknown:
        parser.error(f"unknown entries: {unknown}")

    head = git("rev-parse", "HEAD", cwd=REPO).stdout.strip()
    print(f"# limitations register reproduction\ncommit: {head}\npython: {sys.version.split()[0]}\n"
          f"ingol: {args.ingol_repo or 'not given, INGOL entries skipped'}\n")
    counts = {"MATCH": 0, "MISMATCH": 0, "SKIPPED": 0, "ERROR": 0}
    with workspace() as root:
        for identifier, claim, needs_ingol, function in ENTRIES:
            if args.ids and identifier not in args.ids:
                continue
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
