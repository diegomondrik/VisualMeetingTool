"""Checks that every file, function, constant and command the maintainer guide names exists (WI31-AC02).

    python docs/evidence/01M4CM3YV9HEAHSW5V5ER4V8W7/check_guide.py [guide [repository]]

The guide is docs/MAINTAINING.md and the repository is the one the script sits in, unless given. Each name between
backticks is classified by its shape and looked up in the code:

- a path with a slash (`tests/test_texts.py`, `.github/workflows/tests.yml`, `docs/evidence/<id>/`): the part before
  the first `<` must exist in the repository (a folder of the data or of a run, `<data>/...`, is not in it: skipped);
- a name made of dots and words whose first word is the name of a module (`jobs.Runner._run`, `qa.LABELS`): that
  module's file must define every other word (def, class or assignment);
- a file name without a folder (`constraints.txt`, `kept.json`): it exists in the repository, or the code says it
  (the files a run writes are not in the repository);
- a command (`python -m meetingtool.frames`): the module exists.

Everything else (a flag, a snippet, an example) is counted as not checked. The exit status is 1 when anything named
is missing. Reads files only; writes nothing.
"""

import re
import sys
from pathlib import Path

SKIP_FOLDERS = {".git", "__pycache__", "build", "dist", ".venv", "node_modules"}
DATA_PREFIXES = ("<data>", "work-item/", "processing/", "results/", "paid-answers/", "qa-parts/")
FILE_SUFFIXES = (".py", ".md", ".txt", ".json", ".yaml", ".yml", ".docx", ".js", ".jpg", ".png", ".toml")
CODE_SUFFIXES = (".py", ".js", ".css", ".html")


def repository_files(root):
    return [path for path in root.rglob("*") if path.is_file()
            and not SKIP_FOLDERS.intersection(path.relative_to(root).parts)]


def defines(text, name):
    pattern = rf"(?m)^\s*(?:async\s+)?(?:def|class)\s+{re.escape(name)}\b|^\s*{re.escape(name)}\s*(?::[^=\n]+)?=[^=]"
    return re.search(pattern, text) is not None


def check_token(token, root, files, modules, code_text):
    """None when the token is not something to look up; otherwise (found, what was looked up)."""
    command = re.match(r"python -m ([A-Za-z_][\w.]*)", token)
    if command:
        module = command.group(1)
        if module in ("pip", "unittest"):
            return True, f"module {module} (standard)"
        relative = Path(*module.split("."))
        found = any((root / relative).with_suffix(".py").exists() or (root / relative / name).exists()
                    for name in ("__main__.py", "__init__.py"))
        if not found:
            found = (root / relative).with_suffix(".py").exists()
        return found, f"module {module}"
    if token.startswith(DATA_PREFIXES) or " " in token or token.startswith("-"):
        return None
    if "/" in token:
        prefix = token.split("<", 1)[0]
        if not prefix:
            return None
        target = prefix[:-1] if prefix.endswith("/") else prefix
        if target.startswith("texts/"):
            target = "meetingtool/" + target
        if target.endswith("*") or "*" in target:
            target = target.split("*", 1)[0].rstrip("/") or "."
            found = (root / target).exists() or any(str(path.relative_to(root)).replace("\\", "/").startswith(target)
                                                    for path in files)
            return found, f"path {token}"
        return (root / target).exists(), f"path {token}"
    if token.endswith(FILE_SUFFIXES) and re.fullmatch(r"[\w.-]+", token):
        name = token
        if name.startswith("."):
            return None
        in_repository = any(path.name == name for path in files)
        return in_repository or name in code_text, f"file {name}"
    parts = token.split(".")
    if len(parts) >= 2 and all(re.fullmatch(r"[A-Za-z_]\w*", part) for part in parts) and parts[0] in modules:
        texts = [path.read_text(encoding="utf-8", errors="replace") for path in modules[parts[0]]]
        missing = [part for part in parts[1:] if not any(defines(text, part) for text in texts)]
        return not missing, f"{token}" + (f" (not defined in {parts[0]}: {', '.join(missing)})" if missing else "")
    return None


def main(argv):
    root = Path(argv[1]) if len(argv) > 1 else Path(__file__).resolve().parents[3]
    guide = Path(argv[0]) if argv else root / "docs" / "MAINTAINING.md"
    files = repository_files(root)
    modules = {}
    for path in files:
        if path.suffix == ".py" and path.relative_to(root).parts[0] in ("meetingtool", "tests"):
            modules.setdefault(path.stem, []).append(path)
    code_text = "\n".join(path.read_text(encoding="utf-8", errors="replace") for path in files
                          if path.suffix in CODE_SUFFIXES and path.relative_to(root).parts[0] == "meetingtool")
    tokens = sorted(set(re.findall(r"`([^`\n]+)`", guide.read_text(encoding="utf-8"))))
    missing, checked, skipped = [], 0, []
    for token in tokens:
        verdict = check_token(token, root, files, modules, code_text)
        if verdict is None:
            skipped.append(token)
            continue
        checked += 1
        found, what = verdict
        if not found:
            missing.append(what)
    print(f"guide {guide.name}: {len(tokens)} names between backticks, {checked} looked up, {len(skipped)} not checked "
          f"(flags, snippets, examples, runtime files)")
    for what in missing:
        print(f"MISSING: {what}")
    print("every name the guide looks up exists" if not missing else f"{len(missing)} NAME(S) THE GUIDE USES DO NOT EXIST")
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
