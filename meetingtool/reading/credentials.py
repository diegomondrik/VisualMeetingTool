"""The user's Gemini key in the Windows Credential Manager.

Each user brings their own key from a Google project with billing enabled
(INGOL D-173). It is kept as a generic credential named TARGET, the same
place the owner's key-saving helper used, and is never written to a file or
printed: callers get it as a string and show at most its length.
"""

import ctypes
import sys

TARGET = "VisualMeetingTool/gemini"
_GENERIC = 1
_PERSIST_LOCAL_MACHINE = 2
_ERROR_NOT_FOUND = 1168


class CredentialError(Exception):
    """The credential store cannot be used or refused an operation."""


def _api():
    if sys.platform != "win32":
        raise CredentialError("the Gemini key is kept in the Windows Credential Manager; this system is not Windows")
    from ctypes import wintypes

    class Credential(ctypes.Structure):
        _fields_ = [
            ("Flags", wintypes.DWORD), ("Type", wintypes.DWORD), ("TargetName", wintypes.LPWSTR),
            ("Comment", wintypes.LPWSTR), ("LastWritten", wintypes.FILETIME),
            ("CredentialBlobSize", wintypes.DWORD), ("CredentialBlob", ctypes.c_void_p),
            ("Persist", wintypes.DWORD), ("AttributeCount", wintypes.DWORD), ("Attributes", ctypes.c_void_p),
            ("TargetAlias", wintypes.LPWSTR), ("UserName", wintypes.LPWSTR),
        ]

    advapi = ctypes.WinDLL("advapi32", use_last_error=True)
    advapi.CredReadW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                                 ctypes.POINTER(ctypes.POINTER(Credential))]
    advapi.CredReadW.restype = wintypes.BOOL
    advapi.CredWriteW.argtypes = [ctypes.POINTER(Credential), wintypes.DWORD]
    advapi.CredWriteW.restype = wintypes.BOOL
    advapi.CredDeleteW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD]
    advapi.CredDeleteW.restype = wintypes.BOOL
    advapi.CredFree.argtypes = [ctypes.c_void_p]
    advapi.CredFree.restype = None
    return advapi, Credential


def read_key(target=TARGET):
    """The saved key, or None when there is none."""
    advapi, Credential = _api()
    pointer = ctypes.POINTER(Credential)()
    if not advapi.CredReadW(target, _GENERIC, 0, ctypes.byref(pointer)):
        error = ctypes.get_last_error()
        if error == _ERROR_NOT_FOUND:
            return None
        raise CredentialError(f"the Windows Credential Manager could not be read (error {error})")
    try:
        credential = pointer.contents
        size = credential.CredentialBlobSize
        if not size:
            return None
        return ctypes.wstring_at(credential.CredentialBlob, size // 2).strip() or None
    finally:
        advapi.CredFree(pointer)


def save_key(key, target=TARGET):
    """Save the key, replacing any saved before."""
    key = key.strip()
    if not key:
        raise CredentialError("the key is empty; nothing was saved")
    advapi, Credential = _api()
    blob = ctypes.create_unicode_buffer(key, len(key))
    credential = Credential()
    credential.Type = _GENERIC
    credential.TargetName = target
    credential.UserName = "gemini"
    credential.CredentialBlobSize = len(key) * 2
    credential.CredentialBlob = ctypes.cast(blob, ctypes.c_void_p)
    credential.Persist = _PERSIST_LOCAL_MACHINE
    if not advapi.CredWriteW(ctypes.byref(credential), 0):
        raise CredentialError(f"the Windows Credential Manager refused to save the key (error {ctypes.get_last_error()})")


def delete_key(target=TARGET):
    """Delete the saved key; True if there was one."""
    advapi, _ = _api()
    if advapi.CredDeleteW(target, _GENERIC, 0):
        return True
    error = ctypes.get_last_error()
    if error == _ERROR_NOT_FOUND:
        return False
    raise CredentialError(f"the Windows Credential Manager could not delete the key (error {error})")
