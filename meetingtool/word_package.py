"""How the program reads a Word package (WI29; the external review of
2026-10-02, R08).

A .docx or .dotx is a ZIP. The upload limit counts its compressed bytes, so
a package of a few kilobytes can expand to tens of megabytes or more. Every
package the program reads (a transcript, a template, the report's last check)
is read here, and refused, before any part is parsed, when it holds more
entries than MAX_ENTRIES, when a part expands to more than MAX_PART_BYTES, or
when the parts read expand to more than MAX_PACKAGE_BYTES together.

The bytes are counted as they are decompressed, in chunks, and the reading
stops as soon as a limit is passed: the size the package's directory states
is not trusted (it can say less than the part holds), and the rest of a part
that is over the limit is never decompressed.

Only the standard library is used, and the program's list of messages.
"""

import zipfile

from meetingtool import texts

MAX_ENTRIES = 4000
MAX_PART_BYTES = 32 * 1024 * 1024
MAX_PACKAGE_BYTES = 256 * 1024 * 1024
MEGABYTE = 1024 * 1024
CHUNK = 64 * 1024


class PackageError(texts.Failure):
    """A Word package that expands to more than the limits allow."""


def read_parts(path, names=None):
    """{name: bytes} of the parts of the package at path: those in `names`
    (KeyError for one the package lacks), or every one. PackageError when
    the package, or what is read of it, is over a limit; zipfile.BadZipFile
    and OSError as zipfile raises them."""
    with zipfile.ZipFile(path) as archive:
        present = archive.namelist()
        if len(present) > MAX_ENTRIES:
            raise PackageError("package.too_many_entries", count=len(present), limit=MAX_ENTRIES)
        wanted = list(dict.fromkeys(present if names is None else names))
        parts = {}
        total = 0
        for name in wanted:
            chunks = []
            size = 0
            with archive.open(name) as part:  # KeyError here when the package lacks it
                while chunk := part.read(CHUNK):
                    size += len(chunk)
                    total += len(chunk)
                    if size > MAX_PART_BYTES:
                        raise PackageError("package.part_too_big", part=name, limit=MAX_PART_BYTES // MEGABYTE)
                    if total > MAX_PACKAGE_BYTES:
                        raise PackageError("package.total_too_big", part=name, limit=MAX_PACKAGE_BYTES // MEGABYTE)
                    chunks.append(chunk)
            parts[name] = b"".join(chunks)
    return parts
