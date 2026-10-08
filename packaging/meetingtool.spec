# PyInstaller's recipe for the installed program (WI18), run by packaging/build.py.
# One folder, not one file: it starts faster, and antivirus programs distrust a
# single file that unpacks itself less often. No console: the program is a window.

import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files

ROOT = Path(SPECPATH).parent
sys.path.insert(0, str(ROOT))
from meetingtool import texts  # noqa: E402

analysis = Analysis(
    [str(ROOT / "packaging" / "launcher.py")],
    pathex=[str(ROOT)],
    # The page's script and style, and python-docx's own blank document.
    datas=collect_data_files("meetingtool") + collect_data_files("docx"),
    # The languages are imported by name (meetingtool.texts.catalog), which PyInstaller cannot see.
    hiddenimports=[f"meetingtool.texts.{language}" for language in texts.LANGUAGES],
    excludes=["tkinter", "unittest", "pytest", "tests"],
    noarchive=False,
)
pyz = PYZ(analysis.pure)
exe = EXE(
    pyz,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name="MeetingTool",
    console=False,
    upx=False,
)
COLLECT(exe, analysis.binaries, analysis.datas, name="MeetingTool", upx=False)
