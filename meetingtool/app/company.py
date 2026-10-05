"""The installation's own settings of the application (INGOL D-188, WI17):
the language it speaks, and the company that owns it, with its name and
logo. They are kept in the data folder, next to the company's Word template:
app-settings.json, and the logo as company-logo.png or company-logo.jpg.

A logo is a PNG or a JPG of at most 1 MB, and a real one: the file is decoded,
whatever its name says, and what is kept is the image written again, so that
nothing else the file carried (text appended to it, metadata) is kept or
served. An SVG is refused whatever its name: it can carry a script, which
would run inside the application.
"""

import dataclasses
import io
import json
import re
import unicodedata
from pathlib import Path

from PIL import Image

from meetingtool import disk, texts
from meetingtool.projects import store

SETTINGS_NAME = "app-settings.json"
LOGO_NAMES = {"PNG": "company-logo.png", "JPEG": "company-logo.jpg"}
LOGO_TYPES = {"company-logo.png": "image/png", "company-logo.jpg": "image/jpeg"}
LOGO_SUFFIXES = (".png", ".jpg", ".jpeg")
LOGO_LIMIT = 1024 * 1024
LOGO_SIDE = 4000
NAME_LIMIT = 80


class SettingsError(texts.Failure):
    """A setting that cannot be kept; nothing was changed."""


@dataclasses.dataclass
class Company:
    name: str
    logo: Path | None
    NAME_LIMIT = NAME_LIMIT


def _read(data_dir):
    try:
        with open(Path(data_dir) / SETTINGS_NAME, encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _write(data_dir, settings):
    folder = store.check_data_dir(Path(data_dir))
    disk.write_text(folder / SETTINGS_NAME, json.dumps(settings, ensure_ascii=False, indent=2) + "\n")


def _change(data_dir, change):
    """Read the settings, change them and write them back holding the data
    folder's lock, so two changes at once keep both (WI20, R01)."""
    folder = store.check_data_dir(Path(data_dir))
    with store.data_lock(folder):
        settings = _read(folder)
        change(settings)
        _write(folder, settings)


def language(data_dir):
    """The application's language; the default one if none was chosen or the
    record was edited by hand into something else."""
    chosen = _read(data_dir).get("language")
    return chosen if chosen in texts.LANGUAGES else texts.DEFAULT_LANGUAGE


def set_language(data_dir, code):
    if code not in texts.LANGUAGES:
        raise SettingsError("app.settings.unknown_language", value=code)
    _change(data_dir, lambda settings: settings.update(language=code))


def logo_path(data_dir):
    for name in LOGO_NAMES.values():
        path = Path(data_dir) / name
        if path.is_file():
            return path
    return None


def company(data_dir):
    name = _read(data_dir).get("company_name")
    return Company(name if isinstance(name, str) else "", logo_path(data_dir))


def check_name(name):
    """The company's name as it is kept: its spaces collapsed; SettingsError
    for one that is not text, too long, or holds characters that cannot be
    shown (control characters)."""
    if not isinstance(name, str):
        raise SettingsError("app.company.name_not_text")
    name = " ".join(name.split())
    if len(name) > NAME_LIMIT:
        raise SettingsError("app.company.name_too_long", limit=NAME_LIMIT)
    if any(unicodedata.category(char) in ("Cc", "Cf", "Co", "Cs") for char in name):
        raise SettingsError("app.company.name_unprintable")
    return name


def set_company_name(data_dir, name):
    """Keep the company's name; an empty one removes it."""
    name = check_name(name)

    def change(settings):
        if name:
            settings["company_name"] = name
        else:
            settings.pop("company_name", None)

    _change(data_dir, change)
    return name


def _looks_like_svg(data):
    head = data[:2048].lstrip(b"\xef\xbb\xbf \t\r\n").lower()
    return head.startswith(b"<?xml") or head.startswith(b"<svg") or b"<svg" in head


def check_logo(data, name=""):
    """(file name to keep it as, the image written again) for a logo, or
    SettingsError saying why it cannot be one."""
    suffix = Path(name).suffix.lower()
    if suffix == ".svg" or _looks_like_svg(data):
        raise SettingsError("app.logo.svg")
    if suffix not in LOGO_SUFFIXES:
        raise SettingsError("app.logo.kind")
    if len(data) > LOGO_LIMIT:
        raise SettingsError("app.logo.too_big")
    try:
        with Image.open(io.BytesIO(data)) as image:
            kind = image.format
            if kind not in LOGO_NAMES:
                raise SettingsError("app.logo.kind")
            if max(image.size) > LOGO_SIDE or min(image.size) < 1:
                raise SettingsError("app.logo.too_many_pixels", limit=LOGO_SIDE)
            image.verify()  # the structure and, in a PNG, every chunk's checksum
        with Image.open(io.BytesIO(data)) as image:
            image.load()  # every pixel: a cut image fails here
            out = io.BytesIO()
            # Only the pixels travel: no colour profile, text or metadata of the file (review P2-4).
            transparency = image.info.get("transparency")
            image.info.clear()
            if transparency is not None:
                image.info["transparency"] = transparency
            if kind == "PNG":
                image.save(out, "PNG", icc_profile=None)
            else:
                (image if image.mode in ("RGB", "L", "CMYK") else image.convert("RGB")).save(
                    out, "JPEG", quality=92, icc_profile=None)
    except SettingsError:
        raise
    except (OSError, SyntaxError, ValueError, Image.DecompressionBombError) as error:
        said = re.sub(r"\s*<[^<>]* object at 0x[0-9A-Fa-f]+>", "", str(error))  # no memory address (review P3)
        raise SettingsError("app.logo.not_image", detail=texts.External(said)) from None
    return LOGO_NAMES[kind], out.getvalue()


def set_logo(data_dir, data, name=""):
    target_name, clean = check_logo(data, name)
    folder = store.check_data_dir(Path(data_dir))
    with store.data_lock(folder):
        disk.write_bytes(folder / target_name, clean)
        for other in LOGO_NAMES.values():
            if other != target_name:
                (folder / other).unlink(missing_ok=True)
    return folder / target_name


def remove_logo(data_dir):
    """Remove the logo; True if there was one."""
    removed = False
    with store.data_lock(store.check_data_dir(Path(data_dir))):
        for name in LOGO_NAMES.values():
            path = Path(data_dir) / name
            if path.is_file():
                path.unlink()
                removed = True
    return removed
