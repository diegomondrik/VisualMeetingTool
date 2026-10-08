"""Builds VisualMeetingTool-Setup-<version>.exe from the code (WI18).

Run it with the Python of the build environment, from the repository's root:

    <build environment>\\Scripts\\python packaging\\build.py

It refuses to build when a tool is not at the version pinned in
packaging/requirements-build.txt, when Inno Setup's compiler is not found, or
when the working tree has changes that are not committed (--allow-dirty, only
while trying things out), so that an installer always comes from one commit and
the same tools. PyInstaller makes the program's folder (meetingtool.spec), and
Inno Setup wraps it in the installer (installer.iss). What it prints at the end
(commit, tools, size, SHA-256) is the evidence of the build.
"""

import argparse
import hashlib
import importlib.metadata
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PACKAGING = ROOT / "packaging"
REQUIREMENTS = PACKAGING / "requirements-build.txt"
SPEC = PACKAGING / "meetingtool.spec"
INSTALLER = PACKAGING / "installer.iss"
DIST, WORK = ROOT / "dist", ROOT / "build"
ISCC_PLACES = ("Inno Setup 6/ISCC.exe",)


def pins(path=REQUIREMENTS):
    """{name: version} of the pinned tools; every line is name==version."""
    found = {}
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        name, separator, version = line.partition("==")
        if separator != "==" or not name.strip() or not version.strip():
            raise ValueError(f"{path.name}, line {number}: not name==version: {line!r}")
        found[name.strip().lower()] = version.strip()
    return found


def tool_problems(pinned, installed=None):
    """What differs from the pins, one line each."""
    def version_of(name):
        if installed is not None:
            return installed.get(name)
        try:
            return importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            return None

    problems = []
    for name, version in sorted(pinned.items()):
        have = version_of(name)
        if have != version:
            problems.append(f"{name}: pinned {version}, installed {have or 'nothing'}")
    return problems


def find_iscc(environ=os.environ):
    """Inno Setup's compiler: ISCC in the environment, on the PATH, or where its installer puts it."""
    if environ.get("ISCC"):
        return Path(environ["ISCC"]) if Path(environ["ISCC"]).is_file() else None
    on_path = shutil.which("ISCC", path=environ.get("PATH"))
    if on_path:
        return Path(on_path)
    for base in ("ProgramFiles(x86)", "ProgramFiles", "LOCALAPPDATA"):
        folder = environ.get(base)
        if not folder:
            continue
        for place in ISCC_PLACES:
            for candidate in (Path(folder) / place, Path(folder) / "Programs" / place):
                if candidate.is_file():
                    return candidate
    return None


def git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()


PACKED = ("meetingtool", "packaging")


def stray_files(status):
    """The files git ignores inside what is packed, from `git status --porcelain
    --ignored`: PyInstaller would put them in the installer whatever git
    says, and .gitignore ignores client data on purpose (review P2-2).
    Python's own caches are not data."""
    stray = []
    for line in status.splitlines():
        if line.startswith("!! "):
            path = line[3:].strip().strip('"')
            if "__pycache__" not in path.split("/") and not path.endswith((".pyc", ".pyo")):
                stray.append(path)
    return stray


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def version():
    sys.path.insert(0, str(ROOT))
    import meetingtool

    return meetingtool.__version__


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--allow-dirty", action="store_true",
                        help="build even with changes that are not committed (never for a release)")
    args = parser.parse_args(argv)

    if not REQUIREMENTS.is_file():
        print(f"{REQUIREMENTS.relative_to(ROOT)} is missing: install the tools of requirements-build.in and "
              "freeze them into it", file=sys.stderr)
        return 2
    problems = tool_problems(pins())
    if problems:
        print("The build tools are not the pinned ones:", file=sys.stderr)
        for problem in problems:
            print(f"  {problem}", file=sys.stderr)
        print(f"Install them with: python -m pip install -r {REQUIREMENTS.relative_to(ROOT)}", file=sys.stderr)
        return 2
    changes = git("status", "--porcelain")
    if changes and not args.allow_dirty:
        print("The working tree has changes that are not committed; commit them first:", file=sys.stderr)
        print(changes, file=sys.stderr)
        return 2
    stray = stray_files(git("-c", "core.quotePath=false", "status", "--porcelain", "--ignored", "--", *PACKED))
    if stray:  # even with --allow-dirty: they would be published
        print("Files that git ignores are inside what is packed; move them out first:", file=sys.stderr)
        for path in stray:
            print(f"  {path}", file=sys.stderr)
        return 2
    iscc = find_iscc()
    if iscc is None:
        print("Inno Setup's compiler (ISCC.exe) was not found; install Inno Setup 6 or set ISCC.", file=sys.stderr)
        return 2

    number = version()
    program = DIST / "pyinstaller"
    subprocess.run([sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--distpath", str(program),
                    "--workpath", str(WORK / "pyinstaller"), str(SPEC)], cwd=ROOT, check=True)
    subprocess.run([str(iscc), "/Q", f"/DVersion={number}", f"/DSource={program / 'MeetingTool'}",
                    f"/O{DIST}", str(INSTALLER)], cwd=ROOT, check=True)
    installer = DIST / f"VisualMeetingTool-Setup-{number}.exe"
    if not installer.is_file():
        print(f"Inno Setup ended without {installer.name}", file=sys.stderr)
        return 1

    print()
    print(f"installer: {installer.relative_to(ROOT)}")
    print(f"version:   {number}")
    print(f"commit:    {git('rev-parse', 'HEAD')}{' (with changes not committed)' if changes else ''}")
    print(f"python:    {sys.version.split()[0]}")
    for name, pinned in sorted(pins().items()):
        print(f"tool:      {name}=={pinned}")
    print(f"inno:      {iscc}")
    print(f"size:      {installer.stat().st_size} bytes ({installer.stat().st_size / 1e6:.1f} MB)")
    print(f"sha256:    {sha256(installer)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
