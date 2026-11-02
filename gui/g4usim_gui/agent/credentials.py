"""Explicit OS vault or process-memory credentials, never a settings/file backend."""
from __future__ import annotations

import ctypes
from ctypes import wintypes
from contextlib import closing, contextmanager
import re
import sys
import threading

_SERVICE = "G4UniversalSim.Agent"
_IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}\Z")


class CredentialError(Exception):
    """Machine code only: OS/library exceptions may contain a secret."""
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)

    def to_record(self) -> dict:
        return {"code": self.code}


def _identifier(value):
    if not isinstance(value, str) or not _IDENTIFIER.fullmatch(value):
        raise CredentialError("credential.invalid_id")
    return value


class _Credential(ctypes.Structure):
    _fields_ = [("Flags", wintypes.DWORD), ("Type", wintypes.DWORD),
        ("TargetName", wintypes.LPWSTR), ("Comment", wintypes.LPWSTR),
        ("LastWritten", wintypes.FILETIME), ("CredentialBlobSize", wintypes.DWORD),
        ("CredentialBlob", ctypes.POINTER(ctypes.c_ubyte)), ("Persist", wintypes.DWORD),
        ("AttributeCount", wintypes.DWORD), ("Attributes", ctypes.c_void_p),
        ("TargetAlias", wintypes.LPWSTR), ("UserName", wintypes.LPWSTR)]


class _WindowsVault:
    def __init__(self):
        api = ctypes.WinDLL("Advapi32.dll", use_last_error=True)
        pointer = ctypes.POINTER(_Credential)
        api.CredWriteW.argtypes = [pointer, wintypes.DWORD]
        api.CredWriteW.restype = wintypes.BOOL
        api.CredReadW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.POINTER(pointer)]
        api.CredReadW.restype = wintypes.BOOL
        api.CredDeleteW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD]
        api.CredDeleteW.restype = wintypes.BOOL
        api.CredFree.argtypes = [ctypes.c_void_p]
        api.CredFree.restype = None
        self.api = api

    def put(self, name, secret):
        data = secret.encode("utf-8")
        blob = (ctypes.c_ubyte * len(data)).from_buffer_copy(data)
        item = _Credential(Type=1, TargetName=_SERVICE + "/" + name,
            CredentialBlobSize=len(data), CredentialBlob=blob, Persist=2, UserName=_SERVICE)
        try:
            if not self.api.CredWriteW(ctypes.byref(item), 0):
                raise CredentialError("credential.system_write_failed")
        finally:
            ctypes.memset(blob, 0, len(data))

    def get(self, name):
        pointer = ctypes.POINTER(_Credential)()
        if not self.api.CredReadW(_SERVICE + "/" + name, 1, 0, ctypes.byref(pointer)):
            if ctypes.get_last_error() == 1168:
                return None
            raise CredentialError("credential.system_read_failed")
        try:
            item = pointer.contents
            if item.CredentialBlobSize > 2560:
                raise CredentialError("credential.invalid_system_value")
            return ctypes.string_at(item.CredentialBlob, item.CredentialBlobSize).decode("utf-8")
        finally:
            self.api.CredFree(pointer)

    def delete(self, name):
        if not self.api.CredDeleteW(_SERVICE + "/" + name, 1, 0):
            if ctypes.get_last_error() != 1168:
                raise CredentialError("credential.system_delete_failed")


class _SecretServiceVault:
    def __init__(self):
        # Direct Secret Service API: no auto-selected keyring plugin, plaintext
        # backend, default-collection creation or implicit unlocking prompt.
        import secretstorage
        self.module = secretstorage

    @contextmanager
    def _collection(self):
        with closing(self.module.dbus_init()) as connection:
            collection = self.module.Collection(connection)
            collection.ensure_not_locked()
            yield collection

    @staticmethod
    def _attributes(name):
        return {"application": _SERVICE, "service": _SERVICE, "username": name}

    def put(self, name, secret):
        with self._collection() as collection:
            collection.create_item(_SERVICE + "/" + name, self._attributes(name), secret.encode("utf-8"), replace=True)

    def get(self, name):
        with self._collection() as collection:
            items = list(collection.search_items(self._attributes(name)))
            if len(items) > 1:
                raise CredentialError("credential.ambiguous_system_value")
            if not items:
                return None
            items[0].ensure_not_locked()
            raw = items[0].get_secret()
            if len(raw) > 2560:
                raise CredentialError("credential.invalid_system_value")
            return raw.decode("utf-8")

    def delete(self, name):
        with self._collection() as collection:
            for item in collection.search_items(self._attributes(name)):
                item.ensure_not_locked()
                item.delete()


class CredentialStore:
    """Session values die with this instance; system values require explicit use.

    Python strings cannot promise secure memory erasure. Nothing in this class
    serializes credentials, falls back to disk, or inherits environment API keys.
    """
    def __init__(self):
        self._session = {}
        self._lock = threading.RLock()

    def __repr__(self):
        return "CredentialStore(<redacted>)"

    def _vault(self):
        try:
            if sys.platform == "win32":
                return _WindowsVault()
            if sys.platform.startswith("linux"):
                return _SecretServiceVault()
        except Exception:
            raise CredentialError("credential.system_unavailable") from None
        raise CredentialError("credential.system_unavailable")

    def _operation(self, operation, name, storage, secret=None):
        _identifier(name)
        if not isinstance(storage, str) or storage not in {"system", "session"}:
            raise CredentialError("credential.invalid_storage")
        if storage == "session":
            with self._lock:
                if operation == "put":
                    self._session[name] = secret
                elif operation == "delete":
                    self._session.pop(name, None)
                else:
                    return self._session.get(name)
                return None
        # Do not hold the session lock across an OS/DBus operation: closing an
        # explicit memory-only session must not wait for a system-vault dialog.
        try:
            vault = self._vault()
            if operation == "put":
                vault.put(name, secret)
            elif operation == "delete":
                vault.delete(name)
            else:
                value = vault.get(name)
                if value is not None and (not isinstance(value, str) or not value):
                    raise CredentialError("credential.invalid_system_value")
                return value
        except CredentialError:
            raise
        except Exception:
            raise CredentialError("credential.system_operation_failed") from None

    def put(self, credential_id: str, secret: str, *, storage: str = "system") -> None:
        try:
            valid = isinstance(secret, str) and 0 < len(secret.encode("utf-8")) <= 2560 and "\0" not in secret
        except UnicodeError:
            valid = False
        if not valid:
            raise CredentialError("credential.invalid_secret")
        if isinstance(credential_id, str) and secret in credential_id:
            raise CredentialError("credential.invalid_id")
        self._operation("put", credential_id, storage, secret)

    def get(self, credential_id: str, *, storage: str = "system") -> str | None:
        return self._operation("get", credential_id, storage)

    def delete(self, credential_id: str, *, storage: str = "system") -> None:
        self._operation("delete", credential_id, storage)

    def clear_session(self) -> None:
        with self._lock:
            self._session.clear()
