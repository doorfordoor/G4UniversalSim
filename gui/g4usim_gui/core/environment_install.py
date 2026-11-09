"""Explicit, user-prefix installation transactions (no Qt or SDK import required).

Catalogs are trusted installation inputs, not an authenticity mechanism.  SHA256
checks byte identity only.  Planning never downloads, creates directories or
executes a command.  Execution never changes PATH, registry or an existing prefix.
"""
from __future__ import annotations

import copy
import ctypes
import errno
import hashlib
import json
import os
import platform as host_platform
import re
import shutil
import stat
import subprocess
import tarfile
import time
import urllib.parse
import urllib.request
import uuid
import zipfile
from contextlib import contextmanager
from pathlib import Path, PurePosixPath

CATALOG_SCHEMA = "g4usim_install_catalog_v1"
PLAN_SCHEMA = "g4usim_install_plan_v1"
RECEIPT_SCHEMA = "g4usim_install_receipt_v1"
MARKER = ".g4usim-install.json"
JOURNAL = "transaction.json"
MAX_CATALOG_BYTES = 128 * 1024 * 1024
CHUNK = 1024 * 1024
_SHA = re.compile(r"^[0-9a-f]{64}$")
_RESERVED = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)),
             *(f"LPT{i}" for i in range(1, 10))}


class InstallError(ValueError):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def _fail(code, message):
    raise InstallError(code, message)


def _json(value):
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _digest(value):
    return hashlib.sha256(_json(value).encode("utf-8")).hexdigest()


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            _fail("duplicate_key", f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def load_catalog(path):
    path = Path(path)
    _no_links(path)
    if path.stat().st_size > MAX_CATALOG_BYTES:
        _fail("catalog_size", "Catalog exceeds the size limit")
    value = json.loads(path.read_text(encoding="utf-8-sig"), object_pairs_hook=_pairs,
                       parse_constant=lambda value: _fail("nonfinite", value))
    if isinstance(value, dict) and value.get("schema") == CATALOG_SCHEMA:
        for release in value.get("releases", []):
            for artifact in release.get("artifacts", []):
                source = artifact.get("source", {})
                if source.get("kind") == "local" and isinstance(source.get("path"), str) and not Path(source["path"]).is_absolute():
                    reference = _relative(source["path"])
                    anchored = path.absolute().parent / reference
                    _no_links(anchored)
                    source["catalog_reference"] = reference
                    source["path"] = str(anchored)
    return value


def _no_links(path):
    """Check lexical ancestors before any canonicalization, including junctions."""
    path = Path(path)
    for item in reversed((path, *path.parents)):
        try:
            info = item.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            _fail("linked_path", f"Links and reparse points are not installation paths: {item}")


def _absolute(value):
    path = Path(value)
    if not path.is_absolute() or ".." in path.parts:
        _fail("absolute_path_required", f"An absolute path without '..' is required: {value}")
    _no_links(path)
    return path


def _host_tool(value):
    """Resolve an explicit host-tool alias, never an installation/artifact path.

    Linux compiler selections commonly use /usr/bin/c++ -> alternatives -> g++.
    Record the selection separately and execute the actual resolved file.
    """
    selected = Path(value)
    if not selected.is_absolute() or ".." in selected.parts:
        _fail("absolute_path_required", "Select an absolute existing host-tool path")
    executable = selected.resolve(strict=True)
    if not executable.is_file() or not os.access(executable, os.X_OK):
        _fail("host_tool", f"Selected host tool is not an executable file: {selected}")
    return executable


def _prefix(prefix, allowed_root, *, occupied=False):
    root = _absolute(allowed_root)
    path = _absolute(prefix)
    if not root.is_dir():
        _fail("root_missing", f"Allowed root must already exist: {root}")
    try:
        relative = path.relative_to(root)
    except ValueError:
        _fail("outside_root", f"Prefix is outside the selected root: {path}")
    if not relative.parts:
        _fail("root_prefix", "The selected root itself cannot be the installation prefix")
    for part in relative.parts:
        _relative(part)
    if not path.parent.is_dir():
        _fail("parent_missing", f"Prefix parent must already exist: {path.parent}")
    if not occupied and path.exists():
        _fail("prefix_occupied", f"Existing prefixes are never overwritten: {path}")
    return path, root


def _relative(value, *, empty=False):
    if not isinstance(value, str) or "\\" in value or "\x00" in value:
        _fail("archive_path", f"Invalid portable relative path: {value!r}")
    if empty and not value:
        return ""
    path = PurePosixPath(value)
    if not value or value.startswith("/") or path.as_posix() != value:
        _fail("archive_path", f"Non-normal relative path: {value!r}")
    for part in path.parts:
        if part in (".", "..") or any(c in part for c in ':<>"|?*') or part.endswith((".", " ")) \
                or part.split(".")[0].upper() in _RESERVED or any(ord(c) < 32 for c in part):
            _fail("archive_path", f"Unsafe portable path: {value!r}")
    if path.parts[0].casefold() == MARKER.casefold():
        _fail("reserved_path", f"Installer metadata name is reserved: {value}")
    return path.as_posix()


def _integer(value, label, *, positive=False):
    if type(value) is not int or value < (1 if positive else 0):
        _fail("invalid_size", f"{label} must be a nonnegative integer")
    return value


def _sha(value):
    if not isinstance(value, str) or not _SHA.fullmatch(value):
        _fail("invalid_sha256", "SHA256 must contain exactly 64 lowercase hexadecimal characters")
    return value


def _file_hash(path, cancel=None):
    _no_links(path)
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        while chunk := stream.read(CHUNK):
            _cancel(cancel)
            digest.update(chunk)
    return digest.hexdigest()


def _cancel(cancel):
    if cancel is not None and cancel():
        _fail("cancelled", "Installation cancelled; the transaction can be recovered")


def _inventory_executable(file):
    """Legacy omission means non-executable; never normalize a stored receipt."""
    value = file.get("executable", False)
    if type(value) is not bool:
        _fail("file_mode", "Executable flags must be boolean")
    return value


def _verify_file_mode(target, file, code):
    declared = _inventory_executable(file)
    if os.name != "nt" and bool(target.stat().st_mode & 0o111) != declared:
        _fail(code, f"Executable mode differs from inventory: {file['path']}")


def _artifact(value):
    if not isinstance(value, dict):
        _fail("artifact_type", "Artifact must be an object")
    result = copy.deepcopy(value)
    if not isinstance(result.get("id"), str) or not re.fullmatch(r"[A-Za-z0-9_.-]+", result["id"]):
        _fail("artifact_id", "Artifact id must be a portable identifier")
    _sha(result.get("sha256"))
    _integer(result.get("size_bytes"), "size_bytes", positive=True)
    _integer(result.get("unpacked_size_bytes"), "unpacked_size_bytes")
    if result.get("format") not in ("zip", "tar.gz"):
        _fail("archive_format", "Only zip and tar.gz archives are supported")
    result["target"] = _relative(result.get("target", ""), empty=True)
    source = result.get("source", {})
    if source.get("kind") == "local":
        _absolute(source.get("path", ""))
    elif source.get("kind") == "https":
        url = urllib.parse.urlparse(source.get("url", ""))
        if url.scheme != "https" or not url.netloc or url.username or url.password or url.fragment:
            _fail("source_url", "Download sources must be credential-free HTTPS URLs")
    else:
        _fail("source_missing", "Artifact needs an explicit local or HTTPS source")
    if not isinstance(source.get("origin"), str) or not source["origin"].strip():
        _fail("source_provenance", "Source provenance must be recorded")
    license_record = result.get("license", {})
    if not all(isinstance(license_record.get(key), str) and license_record[key].strip()
               for key in ("expression", "source", "path")):
        _fail("license_missing", "License expression, source and bundled text path are required")
    _relative(license_record["path"])
    _sha(license_record.get("sha256"))
    files = result.get("files")
    if not isinstance(files, list) or not files:
        _fail("file_inventory", "A nonempty per-file inventory is required")
    names = set()
    size = 0
    for file in files:
        name = _relative(file.get("path"))
        if name.casefold() in names:
            _fail("duplicate_path", f"Duplicate archive path: {name}")
        names.add(name.casefold())
        size += _integer(file.get("size_bytes"), "file size")
        _sha(file.get("sha256"))
        _inventory_executable(file)
    if size != result["unpacked_size_bytes"]:
        _fail("inventory_size", "Unpacked size does not match the per-file inventory")
    licensed = next((file for file in files if file["path"] == license_record["path"]), None)
    if licensed is None or licensed["sha256"] != license_record["sha256"]:
        _fail("license_inventory", "Bundled license text must match its file inventory")
    return result


def _select(catalog, profile, platform, architecture, version):
    if not isinstance(catalog, dict) or catalog.get("schema") != CATALOG_SCHEMA:
        _fail("catalog_schema", "Unsupported installation catalog")
    if catalog.get("reviewed") is not True:
        _fail("catalog_unreviewed", "An explicitly reviewed artifact catalog is required")
    if profile not in ("runtime", "sdk"):
        _fail("profile", "Select runtime or sdk")
    if platform not in ("windows", "linux") or architecture not in ("x86_64", "aarch64"):
        _fail("platform", "Unsupported platform or architecture")
    if not isinstance(version, str) or not re.fullmatch(r"[0-9]+(?:\.[0-9]+){1,3}(?:[-+][A-Za-z0-9.-]+)?", version):
        _fail("version", "An exact release version is required")
    releases = catalog.get("releases")
    if not isinstance(releases, list):
        _fail("catalog_releases", "Catalog releases must be an array")
    matches = [release for release in releases if all(release.get(key) == value for key, value in (
        ("profile", profile), ("platform", platform), ("architecture", architecture), ("version", version)))]
    if len(matches) != 1:
        _fail("release_unavailable", "Exactly one reviewed release must match profile/platform/architecture/version")
    release = copy.deepcopy(matches[0])
    if release.get("geant4_version") is not None and (not isinstance(release["geant4_version"], str) or
                                                     not re.fullmatch(r"\d+\.\d+\.\d+", release["geant4_version"])):
        _fail("geant4_version", "Declared Geant4 version must be an exact major.minor.patch")
    if not isinstance(release.get("artifacts"), list) or not release["artifacts"]:
        _fail("artifacts_missing", "The selected release has no artifacts")
    release["artifacts"] = [_artifact(value) for value in release["artifacts"]]
    ids = [artifact["id"] for artifact in release["artifacts"]]
    if len(set(ids)) != len(ids):
        _fail("artifact_id", "Artifact ids must be unique")
    paths = {}
    for artifact in release["artifacts"]:
        for file in artifact["files"]:
            name = "/".join(filter(None, (artifact["target"], file["path"])))
            key = name.casefold()
            if key in paths:
                _fail("artifact_collision", f"Artifacts collide at {name}")
            paths[key] = name
    for name in paths.values():
        parts = PurePosixPath(name).parts
        for count in range(1, len(parts)):
            if "/".join(parts[:count]).casefold() in paths:
                _fail("artifact_collision", f"File/directory collision: {name}")
    dependencies = release.get("dependencies", [])
    if not isinstance(dependencies, list) or any(not isinstance(item, dict) or not item.get("id") for item in dependencies):
        _fail("dependencies", "Dependencies must be identified objects")
    if profile == "runtime" and any(item["id"] in ("compiler", "cmake") and item.get("required", True)
                                    for item in dependencies):
        _fail("runtime_compiler", "Runtime installation cannot require build tools")
    if profile == "sdk" and not all(any(item["id"] == key and item.get("required", True)
                                       for item in dependencies) for key in ("compiler", "cmake")):
        _fail("sdk_dependencies", "SDK releases must explicitly declare compiler and CMake requirements")
    release.setdefault("entrypoints", {})
    for value in release["entrypoints"].values():
        if _relative(value).casefold() not in paths:
            _fail("entrypoint_missing", f"Entrypoint is absent from the artifact inventory: {value}")
    configuration = release.get("configuration", {})
    if configuration:
        if not isinstance(configuration, dict) or set(configuration) != {"data_root", "data_pointer"}:
            _fail("installation_configuration", "Only an explicit bundled-data pointer configuration is supported")
        data_root = _relative(configuration["data_root"])
        pointer = _relative(configuration["data_pointer"])
        if pointer.casefold() not in paths or not any(name.startswith(data_root.casefold() + "/") for name in paths):
            _fail("installation_configuration", "Data pointer and actual data payload must be in the reviewed inventory")
    if profile == "sdk":
        sdk = release.get("sdk")
        if not isinstance(sdk, dict):
            _fail("sdk_probe_missing", "SDK catalogs must identify bundled Geant4 development files and a compile probe")
        for key, required in (("geant4_dir", "Geant4Config.cmake"), ("probe_source", "CMakeLists.txt")):
            directory = _relative(sdk.get(key))
            if f"{directory}/{required}".casefold() not in paths:
                _fail("sdk_probe_missing", f"SDK validation input is missing: {directory}/{required}")
        if "application_source" in sdk and f"{_relative(sdk['application_source'])}/CMakeLists.txt".casefold() not in paths:
            _fail("sdk_probe_missing", "Bundled application source is missing its CMake project")
        for directory in sdk.get("dependency_prefixes", []):
            _relative(directory)
        for key, value in sdk.get("cmake_paths", {}).items():
            if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", key):
                _fail("sdk_configuration", "Invalid CMake SDK dependency key")
            _relative(value)
    return release


def _path_inventory(files, platform):
    files = set(files)
    directories = {parent.as_posix() for name in files for parent in PurePosixPath(name).parents
                   if parent.as_posix() != "."}
    folded_files = {}
    for name in sorted(files):
        key = name.casefold()
        if key in folded_files:
            _fail("artifact_collision", f"File spelling collision: {name}")
        folded_files[key] = name
    folded_dirs = {}
    for name in sorted(directories):
        key = name.casefold()
        if key in folded_files:
            _fail("artifact_collision", f"File/directory collision: {name}")
        if platform == "windows" and key in folded_dirs and folded_dirs[key] != name:
            _fail("catalog_path_ambiguity", f"Directory has multiple spellings: {name}")
        folded_dirs[key] = name

    def resolve(value, kind, code):
        value = _relative(value)
        choices = files if kind == "file" else directories if kind == "directory" else files | directories
        if platform == "windows":
            candidate = (folded_files if kind == "file" else folded_dirs if kind == "directory"
                         else folded_files | folded_dirs).get(value.casefold())
        else:
            candidate = value if value in choices else None
        if candidate is None:
            _fail(code, f"Inventory has no {kind}: {value}")
        return candidate

    return files, directories, resolve


def _sdk_search_paths(sdk, files, platform):
    _, directories, resolve = _path_inventory(files, platform)
    records = []
    for kind, value in [("bin", "bin"), *[(kind, f"{prefix}/{kind}")
                          for prefix in sdk.get("dependency_prefixes", []) for kind in ("bin", "lib")]]:
        value = _relative(value)
        exists = value in directories if platform != "windows" else any(
            name.casefold() == value.casefold() for name in directories)
        records.append({"kind": kind, "path": resolve(value, "directory", "sdk_configuration") if exists else value,
                        "status": "inventory_directory" if exists else "absent_search_path"})
    return records


def _normalize_new_release(release, platform):
    """Only new plans: canonicalize the selected deep copy before either view/digest."""
    for artifact in release["artifacts"]:
        for file in artifact["files"]:
            file.setdefault("executable", False)
    files, directories, resolve = _path_inventory(
        [file["path"] for file in _inventory(release["artifacts"])], platform)
    for key, value in release["entrypoints"].items():
        release["entrypoints"][key] = resolve(value, "file", "entrypoint_missing")
    configuration = release.get("configuration", {})
    if configuration:
        configuration["data_root"] = resolve(configuration["data_root"], "directory", "installation_configuration")
        configuration["data_pointer"] = resolve(configuration["data_pointer"], "file", "installation_configuration")
    facts = {"cmake_paths": {}, "search_paths": []}
    if release["profile"] == "sdk":
        sdk = release["sdk"]
        for key, required in (("geant4_dir", "Geant4Config.cmake"), ("probe_source", "CMakeLists.txt"),
                              ("application_source", "CMakeLists.txt")):
            if key == "application_source" and key not in sdk:
                continue
            sdk[key] = resolve(sdk[key], "directory", "sdk_probe_missing")
            if f"{sdk[key]}/{required}" not in files:
                _fail("sdk_probe_missing", f"SDK requires exact filename: {sdk[key]}/{required}")
        sdk["dependency_prefixes"] = [resolve(value, "directory", "sdk_configuration")
                                      for value in sdk.get("dependency_prefixes", [])]
        for key, value in sdk.get("cmake_paths", {}).items():
            canonical = resolve(value, "file_or_directory", "sdk_configuration")
            sdk["cmake_paths"][key] = canonical
            facts["cmake_paths"][key] = {"path": canonical, "kind": "file" if canonical in files else "directory"}
        facts["search_paths"] = _sdk_search_paths(sdk, files, platform)
    return facts


def _txn_path(prefix):
    return prefix.parent / f".{prefix.name}.g4usim-install"


def _unlock_prefix_descriptor(descriptor):
    os.lseek(descriptor, 0, os.SEEK_SET)
    if os.name == "nt":
        import msvcrt
        msvcrt.locking(descriptor, msvcrt.LK_UNLCK, 1)
    else:
        import fcntl
        fcntl.flock(descriptor, fcntl.LOCK_UN)


def _close_prefix_descriptor(descriptor):
    os.close(descriptor)


@contextmanager
def _prefix_lock(prefix, *, create=True, cleanup_errors=None):
    """One stable inode and OS byte/flock lock across every prefix mutation.

    The small sibling lock remains after uninstall. Unlinking a lock file would
    let another process lock a different inode while the first still owns it.
    """
    path = prefix.parent / f".{prefix.name}.g4usim-lock"
    _no_links(path)
    flags = os.O_RDWR | (os.O_CREAT if create else 0) | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0)
    try:
        descriptor = os.open(path, flags, 0o600)
    except OSError as exc:
        _fail("lock_path", f"Cannot open the prefix operation lock: {exc}")
    acquired = False
    body_error = None
    try:
        if os.name == "nt":
            import msvcrt
            try:
                msvcrt.locking(descriptor, msvcrt.LK_NBLCK, 1)
            except OSError:
                _fail("operation_busy", "Another process is operating on this installation prefix")
        else:
            import fcntl
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                _fail("operation_busy", "Another process is operating on this installation prefix")
        acquired = True
        _no_links(path)
        lexical = path.stat()
        opened = os.fstat(descriptor)
        if (lexical.st_dev, lexical.st_ino) != (opened.st_dev, opened.st_ino) or not stat.S_ISREG(opened.st_mode):
            _fail("lock_identity", "Prefix lock identity changed")
        magic = b"g4usim_install_lock_v1\n"
        os.lseek(descriptor, 0, os.SEEK_SET)
        existing = os.read(descriptor, len(magic) + 1)
        if not existing and create:
            os.lseek(descriptor, 0, os.SEEK_SET)
            os.write(descriptor, magic)
            os.fsync(descriptor)
        elif existing != magic:
            _fail("lock_identity", "Existing prefix lock has unknown ownership")
        yield
    except BaseException as exc:
        body_error = exc
        raise
    finally:
        errors = []
        if acquired:
            try:
                _unlock_prefix_descriptor(descriptor)
            except BaseException as exc:
                errors.append(("lock_unlock", exc))
        try:
            _close_prefix_descriptor(descriptor)  # single attempt, never retry a possibly reused fd
        except BaseException as exc:
            errors.append(("lock_close_unknown", exc))
        if cleanup_errors is not None:
            cleanup_errors.extend(errors)
        elif errors and body_error is not None:
            for stage, error in errors:
                body_error.add_note(f"Secondary {stage}: {error}")
        if body_error is None and errors:
            cancellation = next((error for _, error in errors if not isinstance(error, Exception)), None)
            if cleanup_errors is None or cancellation is not None:
                raise cancellation or errors[0][1]


def create_plan(catalog, *, profile, platform, architecture, version, prefix, allowed_root, facts=None):
    """Return either a fully described plan or structured rejection, without writes."""
    result = {"schema": PLAN_SCHEMA, "status": "rejected", "executable": False,
              "profile": profile, "platform": platform, "architecture": architecture,
              "version": version, "prefix": str(prefix), "allowed_root": str(allowed_root),
              "diagnostics": [], "artifacts": [], "dependencies": [], "steps": [],
              "space": {"required_bytes": None, "available_bytes": None},
              "environment_facts": copy.deepcopy(facts), "capability_status": "not_probed"}
    try:
        release = _select(catalog, profile, platform, architecture, version)
        path_validation = _normalize_new_release(release, platform)
        target, root = _prefix(prefix, allowed_root)
        _no_links(_txn_path(target))
        if _txn_path(target).exists():
            _fail("transaction_exists", "An existing transaction must be recovered or resumed explicitly")
        required = sum(item["size_bytes"] + item["unpacked_size_bytes"] for item in release["artifacts"])
        available = shutil.disk_usage(target.parent).free
        result["space"] = {"required_bytes": required, "available_bytes": available,
                           "scope": "archives_plus_payload_without_filesystem_overhead"}
        if available < required:
            _fail("space", "Insufficient free space for staging archives and payload")
        for item in release["artifacts"]:
            if item["source"]["kind"] == "local":
                source = Path(item["source"]["path"])
                if not source.is_file() or source.stat().st_size != item["size_bytes"]:
                    _fail("local_artifact_missing", f"Local artifact is missing or has the wrong size: {source}")
        result.update(prefix=str(target), allowed_root=str(root), release=release, path_validation=path_validation,
                      geant4_version=release.get("geant4_version"),
                      artifacts=copy.deepcopy(release["artifacts"]), dependencies=copy.deepcopy(release.get("dependencies", [])),
                      steps=[{"id": value, "status": "planned"} for value in
                             ("acquire", "verify_archives", "extract", "verify_payload", "publish", "rediscover_I1")],
                      catalog_sha256=_digest(catalog), status="planned", executable=True)
        if profile == "sdk":
            result["steps"].append({"id": "sdk_compile_probe", "status": "planned"})
        result["plan_sha256"] = _digest({key: value for key, value in result.items() if key != "space"})
    except (InstallError, OSError, TypeError, ValueError, KeyError) as exc:
        result["diagnostics"].append({"code": getattr(exc, "code", "invalid_input"), "message": str(exc)})
    return result


def _write_json(path, value, *, exclusive=False):
    _no_links(path)
    raw = (_json(value) + "\n").encode("utf-8")
    if exclusive:
        with path.open("xb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        return
    temporary = path.with_name(path.name + ".new")
    _no_links(temporary)
    with temporary.open("xb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def _exclusive_publish(source, target):
    """Directory rename that never replaces an empty directory on POSIX."""
    _no_links(source)
    _no_links(target)
    if os.name == "nt":
        os.rename(source, target)
    elif host_platform.system() == "Linux":
        libc = ctypes.CDLL(None, use_errno=True)
        rename = getattr(libc, "renameat2", None)
        if rename is None:
            _fail("exclusive_publish_unsupported", "Linux renameat2 is required for exclusive publication")
        rename.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
        rename.restype = ctypes.c_int
        if rename(-100, os.fsencode(source), -100, os.fsencode(target), 1) != 0:
            error = ctypes.get_errno()
            raise OSError(error, os.strerror(error), str(target))
    else:
        _fail("exclusive_publish_unsupported", "Exclusive publication is supported on Windows and Linux")


def _safe_remove_tree(path):
    """Only called for an owned, already validated transaction or uninstall tomb."""
    _no_links(path)
    if not path.is_dir():
        _fail("transaction_path", "Owned transaction directory is missing")
    for directory, folders, files in os.walk(path, followlinks=False):
        for name in folders + files:
            candidate = Path(directory) / name
            _no_links(candidate)
            if not candidate.is_dir() and not candidate.is_file():
                _fail("special_file", f"Special files cannot be removed: {candidate}")
    shutil.rmtree(path)


class _HTTPSOnlyRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        parsed = urllib.parse.urlparse(newurl)
        if parsed.scheme != "https" or parsed.username or parsed.password:
            _fail("download_redirect", "HTTPS downloads cannot redirect to insecure or credential-bearing URLs")
        return super().redirect_request(request, fp, code, msg, headers, newurl)


def _acquire(artifact, path, allow_download, cancel):
    if path.exists():
        if path.stat().st_size == artifact["size_bytes"] and _file_hash(path, cancel) == artifact["sha256"]:
            return "verified_cache"
        _fail("cached_artifact_changed", "Existing transaction archive failed verification")
    source = artifact["source"]
    temporary = path.with_suffix(".part")
    _no_links(temporary)
    # A partial file is owned by this exact transaction, never used as verification.
    if temporary.exists():
        temporary.unlink()
    if source["kind"] == "local":
        original = _absolute(source["path"])
        stream = original.open("rb")
    else:
        if not allow_download:
            _fail("download_not_authorized", "Explicitly enable downloads to use HTTPS artifacts")
        stream = urllib.request.build_opener(_HTTPSOnlyRedirect()).open(source["url"], timeout=30)
    digest = hashlib.sha256()
    count = 0
    with stream, temporary.open("xb") as output:
        while chunk := stream.read(CHUNK):
            _cancel(cancel)
            count += len(chunk)
            if count > artifact["size_bytes"]:
                _fail("archive_size", "Artifact is larger than its reviewed size")
            digest.update(chunk)
            output.write(chunk)
        output.flush()
        os.fsync(output.fileno())
    if count != artifact["size_bytes"] or digest.hexdigest() != artifact["sha256"]:
        _fail("archive_hash", f"Artifact byte identity failed: {artifact['id']}")
    _no_links(path)
    _exclusive_publish(temporary, path)
    return "downloaded_verified" if source["kind"] == "https" else "copied_verified"


def inspect_archive(path, archive_format):
    """Read a portable regular-file archive and return its exact file inventory."""
    files = []
    with _archive(path, archive_format) as archive:
        for name, size, executable, opener in _members(archive, archive_format):
            digest = hashlib.sha256()
            count = 0
            with opener() as stream:
                while chunk := stream.read(CHUNK):
                    count += len(chunk)
                    digest.update(chunk)
            if count != size:
                _fail("archive_size", f"Truncated member: {name}")
            files.append({"path": name, "size_bytes": size, "sha256": digest.hexdigest(), "executable": executable})
    if not files:
        _fail("archive_empty", "Archive contains no files")
    # Reuse the complete collision validation from catalog construction later.
    return sorted(files, key=lambda value: value["path"])


def _archive(path, archive_format):
    _no_links(path)
    return zipfile.ZipFile(path) if archive_format == "zip" else tarfile.open(path, "r:gz")


def _members(archive, archive_format):
    seen = set()
    values = archive.infolist() if archive_format == "zip" else archive.getmembers()
    for member in values:
        raw = member.filename if archive_format == "zip" else member.name
        directory = member.is_dir() if archive_format == "zip" else member.isdir()
        name = _relative(raw.rstrip("/") if directory else raw)
        if name.casefold() in seen:
            _fail("duplicate_path", f"Duplicate archive member: {name}")
        seen.add(name.casefold())
        mode = (member.external_attr >> 16) if archive_format == "zip" else member.mode
        kind = stat.S_IFMT(mode)
        if archive_format == "zip":
            if member.flag_bits & 1 or kind not in (0, stat.S_IFREG, stat.S_IFDIR) \
                    or (kind == stat.S_IFDIR) != directory and kind != 0:
                _fail("archive_link", f"Encrypted, linked or special archive member: {name}")
        elif not (member.isfile() or directory):
            _fail("archive_link", f"Linked or special archive member: {name}")
        if directory:
            continue
        size = member.file_size if archive_format == "zip" else member.size
        opener = ((lambda item=member: archive.open(item)) if archive_format == "zip"
                  else (lambda item=member: archive.extractfile(item)))
        yield name, size, bool(mode & 0o111), opener


def _extract(artifact, archive_path, payload, cancel, receipt=None, progress=None):
    expected = {file["path"]: file for file in artifact["files"]}
    observed = set()
    with _archive(archive_path, artifact["format"]) as archive:
        for name, size, executable, opener in _members(archive, artifact["format"]):
            _cancel(cancel)
            file = expected.get(name)
            if file is None or size != file["size_bytes"] or executable != _inventory_executable(file):
                _fail("archive_inventory", f"Archive member differs from reviewed inventory: {name}")
            observed.add(name)
            target = payload / artifact["target"] / name
            _no_links(target)
            target.parent.mkdir(parents=True, exist_ok=True)
            digest = hashlib.sha256()
            count = 0
            with opener() as stream, target.open("xb") as output:
                while chunk := stream.read(CHUNK):
                    _cancel(cancel)
                    count += len(chunk)
                    if count > size:
                        _fail("archive_size", f"Archive member exceeds reviewed size: {name}")
                    digest.update(chunk)
                    output.write(chunk)
            if count != size or digest.hexdigest() != file["sha256"]:
                _fail("payload_hash", f"Extracted file failed byte verification: {name}")
            target.chmod(0o755 if executable else 0o644)
            if receipt is not None and len(observed) % 1024 == 0:
                _event(receipt, "extract", "progress", progress, artifact_id=artifact["id"],
                       files_verified=len(observed), total_files=len(expected))
    if observed != set(expected):
        _fail("archive_inventory", "Archive is missing reviewed files")


def _inventory(artifacts):
    return sorted([dict(file, path="/".join(filter(None, (artifact["target"], file["path"]))))
                   for artifact in artifacts for file in artifact["files"]], key=lambda value: value["path"])


def _verify_staged(payload, files, cancel, receipt=None, progress=None):
    expected = {file["path"] for file in files}
    for index, file in enumerate(files, 1):
        _cancel(cancel)
        target = payload / file["path"]
        _no_links(target)
        if not target.is_file() or target.stat().st_size != file["size_bytes"] or _file_hash(target, cancel) != file["sha256"]:
            _fail("staged_file_changed", f"Staged file changed before publication: {file['path']}")
        _verify_file_mode(target, file, "staged_file_mode")
        if receipt is not None and index % 1024 == 0:
            _event(receipt, "verify_payload", "progress", progress, files_verified=index, total_files=len(files))
    observed = set()
    for directory, folders, names in os.walk(payload, followlinks=False):
        for name in folders + names:
            candidate = Path(directory) / name
            _no_links(candidate)
            if candidate.is_file():
                observed.add(candidate.relative_to(payload).as_posix())
            elif not candidate.is_dir():
                _fail("special_file", "Staged payload contains a special file")
    if observed != expected:
        _fail("staged_inventory", "Staged file inventory changed before publication")


def _event(receipt, stage, status, progress, **fields):
    event = {"stage": stage, "status": status, "time_ns": time.time_ns(), **fields}
    receipt["events"].append(event)
    if progress:
        progress(copy.deepcopy(event))


def _execute_plan_unlocked(plan, *, allow_download=False, cancel=None, progress=None, resume=False, _report=None):
    """Install reviewed bytes; return real receipts, never an inferred capability pass."""
    receipt = {"schema": RECEIPT_SCHEMA, "status": "staging", "events": [],
               "capability_status": "not_probed", "diagnostics": [], "prefix": plan.get("prefix"),
               "plan_sha256": plan.get("plan_sha256"), "transaction_id": uuid.uuid4().hex}
    if _report is not None:
        _report.update(receipt)
        receipt = _report
    transaction = None
    published = False
    try:
        if plan.get("schema") != PLAN_SCHEMA or plan.get("executable") is not True or plan.get("status") != "planned":
            _fail("plan_rejected", "A valid executable installation plan is required")
        expected = _digest({key: value for key, value in plan.items() if key not in ("space", "plan_sha256")})
        if expected != plan.get("plan_sha256"):
            _fail("plan_changed", "Plan content changed after validation")
        _select({"schema": CATALOG_SCHEMA, "reviewed": True, "releases": [plan["release"]]},
                plan["profile"], plan["platform"], plan["architecture"], plan["version"])
        target, root = _prefix(plan["prefix"], plan["allowed_root"])
        system = "windows" if os.name == "nt" else host_platform.system().lower()
        machine = {"amd64": "x86_64", "arm64": "aarch64"}.get(host_platform.machine().lower(), host_platform.machine().lower())
        if plan["platform"] != system or plan["architecture"] != machine:
            _fail("execution_platform", "The plan targets a different host platform or architecture")
        transaction = _txn_path(target)
        _no_links(transaction)
        if resume:
            prepared = _prepare_recovery(transaction, target, root, resume=True)
            previous = prepared["journal"]
            if previous["plan_sha256"] != plan["plan_sha256"]:
                _fail("resume_plan", "Transaction belongs to a different plan")
            _apply_recovery_updates(prepared)
            # Only the validated payload subset is discarded for a new attempt;
            # retain archives and journal identity, never recursive blind cleanup.
            payload_root = transaction / "payload"
            members = [path for path in prepared["snapshot"]["items"]
                       if path == payload_root or payload_root in path.parents]
            for member in sorted(members, key=lambda path: len(path.parts), reverse=True):
                _remove_observed_member(member, prepared["snapshot"])
            # Resume reuses the remaining archives and journal. Recheck them
            # and the complete remaining inventory before restarting work.
            _check_recovery_observation(prepared["snapshot"])
            receipt["transaction_id"] = previous["transaction_id"]
            receipt["events"] = previous.get("events", [])
            receipt["diagnostics"] = previous.get("diagnostics", [])
        else:
            transaction.mkdir()
            _write_json(transaction / JOURNAL, dict(receipt, allowed_root=str(root), plan=plan), exclusive=True)
        receipt["transaction_path"] = str(transaction)
        archives = transaction / "archives"
        archives.mkdir(exist_ok=True)
        payload = transaction / "payload"
        if payload.exists():
            _fail("recovery_changed", "Unexpected payload appeared after validated resume cleanup")
        payload.mkdir()
        for artifact in plan["artifacts"]:
            _cancel(cancel)
            _prefix(target, root)
            status = _acquire(artifact, archives / artifact["id"], allow_download, cancel)
            _event(receipt, "acquire", status, progress, artifact_id=artifact["id"], sha256=artifact["sha256"])
            _extract(artifact, archives / artifact["id"], payload, cancel, receipt, progress)
            _event(receipt, "extract", "verified", progress, artifact_id=artifact["id"])
            _write_json(transaction / JOURNAL, dict(receipt, allowed_root=str(root), plan=plan))
        installed_files = _inventory(plan["artifacts"])
        generated = []
        configuration = plan["release"].get("configuration", {})
        if configuration:
            relative = configuration["data_pointer"]
            pointer = payload / relative
            original = next(file for file in installed_files if file["path"] == relative)
            raw = (str(target / configuration["data_root"]) + "\n").encode("utf-8")
            _no_links(pointer)
            pointer.write_bytes(raw)
            generated.append({"path": relative, "kind": "bundled_data_pointer", "source_sha256": original["sha256"],
                              "sha256": hashlib.sha256(raw).hexdigest(), "size_bytes": len(raw)})
            original.update(sha256=generated[-1]["sha256"], size_bytes=len(raw))
            _event(receipt, "configure_data", "written_verified", progress, path=relative, sha256=generated[-1]["sha256"])
        _verify_staged(payload, installed_files, cancel, receipt, progress)
        receipt.update(files=installed_files, generated_files=generated, profile=plan["profile"], version=plan["version"],
                       geant4_version=plan["release"].get("geant4_version"),
                       platform=plan["platform"], architecture=plan["architecture"], allowed_root=str(root),
                       entrypoints=plan["release"].get("entrypoints", {}), dependencies=plan["dependencies"],
                       sdk=plan["release"].get("sdk"),
                       artifacts=[{key: copy.deepcopy(artifact[key]) for key in
                                   ("id", "source", "sha256", "size_bytes", "license")} for artifact in plan["artifacts"]],
                       catalog_sha256=plan["catalog_sha256"], status="prepared")
        _event(receipt, "verify_payload", "verified", progress, file_count=len(receipt["files"]))
        _write_json(payload / MARKER, receipt, exclusive=True)
        _cancel(cancel)
        _prefix(target, root)
        _exclusive_publish(payload, target)
        published = True
        receipt["status"] = "published"
        _event(receipt, "publish", "published", progress)
        # Publication succeeded. Later cleanup failure cannot reverse that fact.
        _write_json(target / MARKER, receipt)
        _write_json(transaction / JOURNAL, dict(receipt, plan=plan))
        cleanup = _prepare_recovery(transaction, target, root)
        _apply_recovery_updates(cleanup)
        _remove_owned_transaction(transaction, cleanup["journal"], cleanup["snapshot"])
        receipt["transaction_path"] = None
    except Exception as exc:
        receipt["status"] = "published_with_warning" if published else ("cancelled" if getattr(exc, "code", "") == "cancelled" else "failed")
        receipt["diagnostics"].append({"code": getattr(exc, "code", "io_error"), "message": str(exc)})
        if transaction is not None and transaction.is_dir():
            try:
                _no_links(transaction)
                # Only rewrite a marker owned by this invocation / validated resume.
                marker = transaction / JOURNAL
                if marker.is_file() and load_catalog(marker).get("transaction_id") == receipt["transaction_id"]:
                    _write_json(marker, dict(receipt, allowed_root=plan.get("allowed_root"), plan=plan))
                    receipt["transaction_path"] = str(transaction)
            except Exception as journal_error:
                receipt["diagnostics"].append({"code": "journal_write", "message": str(journal_error)})
    return receipt


def _observed_identity(path):
    _no_links(path)
    info = path.lstat()
    if not (stat.S_ISREG(info.st_mode) or stat.S_ISDIR(info.st_mode)):
        _fail("recovery_special_file", f"Not an ordinary recovery object: {path}")
    return info.st_dev, info.st_ino, info.st_mode


def _observed_item(path):
    identity = _observed_identity(path)
    return (*identity, _file_hash(path) if stat.S_ISREG(identity[2]) else None)


def _observe_recovery(roots, *, absent_prefix):
    if absent_prefix is not None:
        _no_links(absent_prefix)
        if absent_prefix.exists():
            _fail("recovery_changed", "Previously absent prefix appeared during recovery")
    items = {}
    for root in roots:
        items[root] = _observed_item(root)
        for directory, folders, files in os.walk(root, followlinks=False):
            for name in folders + files:
                path = Path(directory) / name
                items[path] = _observed_item(path)
    return {"roots": list(roots), "items": items, "absent_prefix": absent_prefix}


def _check_recovery_observation(snapshot):
    if _observe_recovery(snapshot["roots"], absent_prefix=snapshot["absent_prefix"]) != snapshot:
        _fail("recovery_changed", "Recovery objects changed after validation; nothing else may be removed")


def _recovery_json(path):
    if not stat.S_ISREG(path.lstat().st_mode):
        _fail("recovery_identity", f"Recovery record is not a regular file: {path}")
    value = load_catalog(path)
    if not isinstance(value, dict):
        _fail("recovery_identity", f"Recovery record must be an object: {path}")
    return value


def _recovery_plan(value, prefix, root):
    plan = value.get("plan")
    if not isinstance(plan, dict):
        _fail("recovery_plan_missing", "Cannot prove owned members without the original plan; preserve for manual recovery")
    if plan.get("schema") != PLAN_SCHEMA or plan.get("status") != "planned" or plan.get("executable") is not True \
            or plan.get("prefix") != str(prefix) or plan.get("allowed_root") != str(root):
        _fail("transaction_plan", "Stored plan identity is invalid")
    digest = _digest({key: item for key, item in plan.items() if key not in ("space", "plan_sha256")})
    if digest != plan.get("plan_sha256") or digest != value.get("plan_sha256"):
        _fail("transaction_plan", "Stored plan digest differs")
    _select({"schema": CATALOG_SCHEMA, "reviewed": True, "releases": [plan["release"]]},
            plan["profile"], plan["platform"], plan["architecture"], plan["version"])
    if plan["artifacts"] != plan["release"]["artifacts"]:
        _fail("transaction_plan", "Plan inventory views differ")
    return plan


def _publication_fields(plan):
    files = _inventory(plan["artifacts"])
    generated = []
    configuration = plan["release"].get("configuration", {})
    if configuration:
        relative = configuration["data_pointer"]
        original = next((file for file in files if file["path"] == relative), None)
        if original is None:
            _fail("recovery_inventory", "Data pointer is absent from the original exact inventory")
        raw = (str(Path(plan["prefix"]) / configuration["data_root"]) + "\n").encode("utf-8")
        generated.append({"path": relative, "kind": "bundled_data_pointer", "source_sha256": original["sha256"],
                          "sha256": hashlib.sha256(raw).hexdigest(), "size_bytes": len(raw)})
        original.update(sha256=generated[0]["sha256"], size_bytes=len(raw))
    return {"files": files, "generated_files": generated, "profile": plan["profile"], "version": plan["version"],
            "geant4_version": plan["release"].get("geant4_version"), "platform": plan["platform"],
            "architecture": plan["architecture"], "entrypoints": plan["release"].get("entrypoints", {}),
            "dependencies": plan["dependencies"], "sdk": plan["release"].get("sdk"),
            "artifacts": [{key: copy.deepcopy(artifact[key]) for key in
                           ("id", "source", "sha256", "size_bytes", "license")} for artifact in plan["artifacts"]],
            "catalog_sha256": plan["catalog_sha256"]}


def _validate_recovery_record(value, plan, transaction_id, *, journal, complete=False):
    if value.get("schema") != RECEIPT_SCHEMA or value.get("prefix") != plan["prefix"] \
            or value.get("allowed_root") != plan["allowed_root"] or value.get("transaction_id") != transaction_id \
            or value.get("plan_sha256") != plan["plan_sha256"]:
        _fail("recovery_identity", "Recovery record identity differs from the original transaction")
    if journal and value.get("plan") != plan:
        _fail("transaction_plan", "Temporary and base journals must contain the identical original plan")
    if not isinstance(value.get("events"), list) or not isinstance(value.get("diagnostics"), list):
        _fail("recovery_identity", "Recovery events/diagnostics must be arrays")
    if value.get("transaction_path") not in (None, str(_txn_path(Path(plan["prefix"])))):
        _fail("recovery_identity", "Recovery transaction path differs")
    fields = _publication_fields(plan)
    allowed = set(fields) | {"schema", "status", "events", "diagnostics", "prefix", "allowed_root",
                             "transaction_id", "plan_sha256", "transaction_path", "capability_status"}
    if journal:
        allowed.add("plan")
    if set(value) - allowed or value.get("capability_status") != "not_probed":
        _fail("recovery_identity", "Recovery record contains fields not produced by this installer")
    if complete or any(key in value for key in fields):
        if any(value.get(key) != expected for key, expected in fields.items()):
            _fail("recovery_inventory", "Publication fields do not derive from the original plan")


def _validate_transition(base, newer, *, marker, published, resume):
    old, new = base.get("status"), newer.get("status")
    if marker:
        allowed = (old == "prepared" and new == "published") or old == new == "published"
    else:
        allowed = (old == new or old == "staging" and new in ("failed", "cancelled")
                   or old in ("staging", "failed", "cancelled", "published", "published_with_warning")
                   and new in ("published", "published_with_warning")
                   or resume and old in ("failed", "cancelled") and new == "staging")
        allowed = allowed and (new in ("published", "published_with_warning") if published
                               else new in ("staging", "failed", "cancelled"))
    if not allowed:
        _fail("unsupported_recovery_state", f"Unsupported exact update: {old} -> {new}")
    for key in ("events", "diagnostics"):
        if newer[key][:len(base[key])] != base[key]:
            _fail("recovery_history", f"Temporary update loses the original {key}")
    # Apart from writer-owned progress/state fields, exact updates preserve all
    # base fields. Publication fields may be added only after plan derivation.
    mutable = {"status", "events", "diagnostics", "transaction_path"}
    if not marker:
        mutable |= set(_publication_fields(base["plan"]))
    if any(newer.get(key) != item for key, item in base.items() if key not in mutable):
        _fail("recovery_identity", "Temporary update alters immutable base fields")
    if marker and old == "published":
        if newer["diagnostics"] != base["diagnostics"] or any(
                event.get("stage") != "publish" or event.get("status") != "recovered_published"
                for event in newer["events"][len(base["events"]):]):
            _fail("recovery_history", "Published marker only admits an identical or recovery-event update")


def _transaction_members(transaction, plan, snapshot, journal):
    allowed = {JOURNAL, "payload/" + MARKER}
    if (transaction / (JOURNAL + ".new")) in snapshot["items"]:
        allowed.add(JOURNAL + ".new")  # validated separately, never a glob
    for artifact in plan["artifacts"]:
        archive = Path("archives") / artifact["id"]
        allowed.update((archive.as_posix(), archive.with_suffix(".part").as_posix()))
    allowed.update("payload/" + file["path"] for file in _inventory(plan["artifacts"]))
    directories = {"", "archives", "payload"} | {
        parent.as_posix() for name in allowed for parent in PurePosixPath(name).parents if parent.as_posix() != "."}
    for path, identity in snapshot["items"].items():
        if path == transaction or transaction not in path.parents:
            continue
        relative = path.relative_to(transaction).as_posix()
        if relative not in (directories if stat.S_ISDIR(identity[2]) else allowed):
            _fail("recovery_unknown_member", f"Unknown transaction member must be preserved: {path}")
    marker = transaction / "payload" / MARKER
    if marker in snapshot["items"]:
        value = _recovery_json(marker)
        _validate_recovery_record(value, plan, journal["transaction_id"], journal=False, complete=True)
        if value.get("status") != "prepared":
            _fail("unsupported_recovery_state", "Unpublished payload marker must be prepared")


def _prepare_recovery(transaction, prefix, root, *, resume=False):
    if not (transaction / JOURNAL).is_file():
        _fail("recovery_identity_missing", "Journal is missing; preserve even an empty residual directory for manual recovery")
    published = prefix.exists()
    snapshot = _observe_recovery([transaction] + ([prefix] if published else []),
                                 absent_prefix=None if published else prefix)
    base = _read_transaction(transaction, prefix, root)
    plan = _recovery_plan(base, prefix, root)
    txn = base["transaction_id"]
    states = ("staging", "failed", "cancelled", "published", "published_with_warning")
    if base.get("status") not in states:
        _fail("unsupported_recovery_state", "Journal state is not produced by this writer")
    _validate_recovery_record(base, plan, txn, journal=True,
                              complete=base["status"] in ("published", "published_with_warning"))
    updates = []
    journal = base
    temporary = transaction / (JOURNAL + ".new")
    if temporary in snapshot["items"]:
        journal = _recovery_json(temporary)
        _validate_recovery_record(journal, plan, txn, journal=True,
                                  complete=journal.get("status") in ("published", "published_with_warning"))
        _validate_transition(base, journal, marker=False, published=published, resume=resume)
        updates.append((temporary, transaction / JOURNAL))
    if not published and journal["status"] in ("published", "published_with_warning"):
        _fail("recovery_identity", "Published journal has no published prefix")
    marker_update = None
    if published:
        marker = prefix / MARKER
        installed = _recovery_json(marker)
        _validate_recovery_record(installed, plan, txn, journal=False, complete=True)
        if installed.get("status") not in ("prepared", "published"):
            _fail("unsupported_recovery_state", "Published prefix marker has an unsupported state")
        pending = prefix / (MARKER + ".new")
        if pending in snapshot["items"]:
            candidate = _recovery_json(pending)
            _validate_recovery_record(candidate, plan, txn, journal=False, complete=True)
            _validate_transition(installed, candidate, marker=True, published=True, resume=False)
            updates.insert(0, (pending, marker))
        elif installed["status"] == "prepared":
            marker_update = copy.deepcopy(installed)
            marker_update["status"] = "published"
            _event(marker_update, "publish", "recovered_published", None)
        _verify_installation(prefix, _prepared=True, _pending_marker=pending in snapshot["items"])
    _transaction_members(transaction, plan, snapshot, journal)
    _check_recovery_observation(snapshot)
    return {"journal": journal, "updates": updates, "marker_update": marker_update,
            "snapshot": snapshot, "prefix": prefix}


def _apply_recovery_updates(prepared):
    snapshot, prefix = prepared["snapshot"], prepared["prefix"]
    marker = prefix / MARKER
    updates = prepared["updates"]

    def promote(temporary, target):
        _check_recovery_observation(snapshot)
        promoted_identity = snapshot["items"][temporary]
        os.replace(temporary, target)
        del snapshot["items"][temporary]
        snapshot["items"][target] = promoted_identity
        _check_recovery_observation(snapshot)

    # The prefix marker must commit and pass strict verification before any
    # journal promotion, including when recovery has to generate the marker.
    if prepared["marker_update"] is not None:
        _check_recovery_observation(snapshot)
        temporary = marker.with_name(marker.name + ".new")
        _write_json(temporary, prepared["marker_update"], exclusive=True)
        identity = _observed_item(temporary)
        expected = hashlib.sha256((_json(prepared["marker_update"]) + "\n").encode("utf-8")).hexdigest()
        if identity[3] != expected:
            _fail("recovery_changed", "Recovery marker temporary changed before its publication")
        snapshot["items"][temporary] = identity
        promote(temporary, marker)
    elif updates and updates[0][1] == marker:
        promote(*updates[0])
        updates = updates[1:]
    if prefix in snapshot["roots"]:
        _verify_installation(prefix)
    for temporary, target in updates:
        promote(temporary, target)
    _check_recovery_observation(snapshot)


def _remove_observed_member(path, snapshot):
    items = snapshot["items"]
    expected = items[path]
    # Boundary checks cover the whole inventory; here check the known target
    # and its observed ancestors. rmdir never removes a late unknown child.
    chain = [item for item in reversed((path, *path.parents)) if item in items]

    def check_identities():
        for item in chain:
            try:
                identity = _observed_identity(item)
            except FileNotFoundError:
                _fail("recovery_changed", f"Recovery object disappeared before removal: {item}")
            if identity != items[item][:3]:
                _fail("recovery_changed", f"Recovery object identity changed before removal: {item}")

    check_identities()
    if stat.S_ISDIR(expected[2]):
        path.rmdir()
    else:
        if _file_hash(path) != expected[3]:
            _fail("recovery_changed", f"Recovery file bytes changed before removal: {path}")
        check_identities()
        path.unlink()
    del items[path]


def _remove_owned_transaction(transaction, verified_receipt, snapshot):
    """Validated bounded inventory only. Keep identity journal until all data is gone."""
    journal = transaction / JOURNAL
    if _recovery_json(journal) != verified_receipt:
        _fail("recovery_changed", "Cleanup journal differs from the validated receipt")
    members = [path for path in snapshot["items"] if transaction in path.parents and path != journal]
    for path in sorted(members, key=lambda item: len(item.parts), reverse=True):
        _remove_observed_member(path, snapshot)
    _check_recovery_observation(snapshot)
    if set(transaction.iterdir()) != {journal}:
        _fail("recovery_changed", "Only the validated journal may remain before final deletion")
    _remove_observed_member(journal, snapshot)
    # No recursive retry: after loss of journal, only this call's retained
    # directory identity can authorize the immediately following empty rmdir.
    _check_recovery_observation(snapshot)
    transaction.rmdir()
    snapshot["roots"].remove(transaction)
    del snapshot["items"][transaction]


def _read_transaction(transaction, prefix, root):
    _no_links(transaction)
    value = _recovery_json(transaction / JOURNAL)
    if value.get("schema") != RECEIPT_SCHEMA or value.get("prefix") != str(prefix) \
            or value.get("allowed_root") != str(root) or not re.fullmatch(r"[0-9a-f]{32}", value.get("transaction_id", "")):
        _fail("transaction_identity", "Transaction does not belong to the selected prefix and root")
    return value


def _verify_installation(prefix, *, _original_prefix=None, _prepared=False, _pending_marker=False):
    """Verify owned file identity and reject unknown files; this is not an I1 probe."""
    path = _absolute(prefix)
    receipt = load_catalog(path / MARKER)
    accepted_status = ("published", "prepared") if _prepared else ("published",)
    if receipt.get("schema") != RECEIPT_SCHEMA or receipt.get("status") not in accepted_status:
        _fail("receipt_schema", "Prefix lacks a published installation receipt")
    original = _absolute(_original_prefix) if _original_prefix is not None else path
    _prefix(original, receipt.get("allowed_root", ""), occupied=True)
    if receipt.get("prefix") != str(original):
        _fail("prefix_identity", "Installation receipt belongs to another prefix")
    files = receipt.get("files", [])
    if not files:
        _fail("receipt_inventory", "Installation receipt has no inventory")
    expected = {MARKER}
    if _pending_marker:
        expected.add(MARKER + ".new")  # private recovery planner has validated this exact file
    directories = {""}
    for file in files:
        name = _relative(file.get("path"))
        if name in expected:
            _fail("receipt_inventory", "Duplicate owned file")
        expected.add(name)
        target = path / name
        _no_links(target)
        if not target.is_file() or target.stat().st_size != file.get("size_bytes") or _file_hash(target) != file.get("sha256"):
            _fail("installed_file_changed", f"Installed file is missing or changed: {name}")
        _verify_file_mode(target, file, "installed_file_mode")
        directories.update(parent.as_posix() for parent in PurePosixPath(name).parents if parent.as_posix() != ".")
    actual = set()
    for directory, folders, names in os.walk(path, followlinks=False):
        for name in folders + names:
            item = Path(directory) / name
            _no_links(item)
            relative = item.relative_to(path).as_posix()
            if item.is_dir():
                if relative not in directories:
                    _fail("unknown_directory", f"Unowned directory prevents uninstall: {relative}")
            elif item.is_file():
                actual.add(relative)
            else:
                _fail("special_file", f"Special installed file: {relative}")
    if actual != expected:
        _fail("unknown_files", f"Unowned files prevent uninstall: {sorted(actual - expected)}")
    return {"schema": "g4usim_install_verification_v1", "status": "verified", "prefix": str(path),
            "file_count": len(files), "transaction_id": receipt["transaction_id"], "receipt": receipt,
            "capability_status": "not_probed"}


def _uninstall_installation_unlocked(prefix):
    report = _verify_installation(prefix)
    path = Path(prefix)
    receipt = report["receipt"]
    tomb = path.parent / f".{path.name}.g4usim-uninstall-{receipt['transaction_id']}"
    _no_links(tomb)
    if tomb.exists():
        _fail("uninstall_transaction", "An existing uninstall transaction requires recovery")
    _exclusive_publish(path, tomb)
    # If cleanup fails, retain the moved prefix and provide its exact path.
    try:
        _safe_remove_tree(tomb)
    except Exception as exc:
        return {"schema": "g4usim_uninstall_receipt_v1", "status": "cleanup_required",
                "prefix": str(path), "recovery_path": str(tomb), "diagnostic": str(exc),
                "transaction_id": receipt["transaction_id"]}
    return {"schema": "g4usim_uninstall_receipt_v1", "status": "uninstalled", "prefix": str(path),
            "transaction_id": receipt["transaction_id"], "removed_file_count": report["file_count"]}


def _recover_installation_unlocked(prefix, *, allowed_root, action="discard", transaction_id=None):
    path, root = _prefix(prefix, allowed_root, occupied=True)
    if action == "uninstall":
        if not isinstance(transaction_id, str) or not re.fullmatch(r"[0-9a-f]{32}", transaction_id):
            _fail("transaction_identity", "Uninstall recovery requires its transaction id")
        tomb = path.parent / f".{path.name}.g4usim-uninstall-{transaction_id}"
        if path.exists():
            _fail("prefix_occupied", "Cannot recover uninstall while the original prefix exists")
        verified = _verify_installation(tomb, _original_prefix=path)
        if verified["transaction_id"] != transaction_id:
            _fail("transaction_identity", "Uninstall transaction id does not match its receipt")
        _safe_remove_tree(tomb)
        return {"schema": "g4usim_install_recovery_v1", "status": "recovered",
                "prefix": str(path), "uninstalled": True, "transaction_id": transaction_id}
    if action != "discard":
        _fail("recovery_action", "Use execute_plan(resume=True) to resume; recovery supports explicit discard")
    transaction = _txn_path(path)
    if not transaction.exists():
        if not isinstance(transaction_id, str) or not re.fullmatch(r"[0-9a-f]{32}", transaction_id):
            _fail("recovery_identity_missing", "No transaction remains; an explicit published transaction id is required")
        installed = _verify_installation(path)
        if installed["transaction_id"] != transaction_id:
            _fail("recovery_identity", "Published prefix belongs to another transaction")
        return {"schema": "g4usim_install_recovery_v1", "status": "already_recovered", "prefix": str(path),
                "published_prefix_preserved": True, "transaction_id": transaction_id}
    prepared = _prepare_recovery(transaction, path, root)
    value = prepared["journal"]
    if transaction_id is not None and transaction_id != value["transaction_id"]:
        _fail("recovery_identity", "Requested transaction id differs from the original journal")
    _apply_recovery_updates(prepared)
    _remove_owned_transaction(transaction, value, prepared["snapshot"])
    return {"schema": "g4usim_install_recovery_v1", "status": "recovered", "prefix": str(path),
            "published_prefix_preserved": path.exists(), "transaction_id": value["transaction_id"]}


def _append_failure(report, stage, error):
    report.setdefault("diagnostics", []).append({"stage": stage, "code": getattr(error, "code", "io_error"),
                                                  "message": str(error), "type": type(error).__name__})
    report["status"] = "published_with_warning" if report.get("status") in ("published", "published_with_warning") else "failed"
    if report.get("persisted_receipt_sha256"):
        report["receipt_is_final"] = False


def _sdk_guard_path(prefix):
    return prefix.parent / f".{prefix.name}.g4usim-sdk-operation.json"


def _sdk_operation_pending(prefix):
    path = _sdk_guard_path(prefix)
    _no_links(path)
    _no_links(path.with_name(path.name + ".new"))
    return path.exists() or path.with_name(path.name + ".new").exists()


def _reject_sdk_operation(prefix):
    if _sdk_operation_pending(prefix):
        _fail("sdk_operation_pending", "Durable SDK operation evidence requires explicit recovery; PID disappearance is not clearance")


def _guard_update(path, guard, state, record):
    allowed = {"intent": {"intent", "owned_suspended", "running", "settling"},
               "owned_suspended": {"running", "settling"}, "running": {"settling"},
               "settling": {"settling", "settled"}, "settled": set()}
    if state not in allowed[guard["state"]]:
        _fail("sdk_guard_transition", f"Invalid owned guard transition: {guard['state']} -> {state}")
    candidate = copy.deepcopy(guard)
    candidate.update(state=state, record=copy.deepcopy(record), root_child=record.get("root_child"),
                     container=record.get("container"), cleanup_verified=record.get("cleanup_verified", False))
    _write_json(path, candidate)
    guard.clear()
    guard.update(candidate)


def _validate_sdk_guard(value, prefix, root, installed_transaction_id):
    required = {"schema", "operation_id", "prefix", "allowed_root", "installed_transaction_id", "build_directory",
                "build_identity", "stage", "state", "owner", "root_child", "container", "argv", "argv_sha256",
                "cleanup_verified", "record"}
    if not isinstance(value, dict) or set(value) != required or value.get("schema") != "g4usim_sdk_operation_v1":
        _fail("sdk_guard_invalid", "SDK guard schema/fields are invalid")
    if value["prefix"] != str(prefix) or value["allowed_root"] != str(root) \
            or value["installed_transaction_id"] != installed_transaction_id \
            or not isinstance(value["operation_id"], str) or not re.fullmatch(r"[0-9a-f]{32}", value["operation_id"]):
        _fail("sdk_guard_invalid", "SDK guard installation identity differs")
    if value["state"] not in ("intent", "owned_suspended", "running", "settling", "settled") \
            or value["stage"] not in ("configure", "build", "run") or type(value["cleanup_verified"]) is not bool:
        _fail("sdk_guard_invalid", "SDK guard stage/state is invalid")
    owner = value["owner"]
    if not isinstance(owner, dict) or type(owner.get("pid")) is not int or owner["pid"] <= 0 or not owner.get("creation"):
        _fail("sdk_guard_invalid", "SDK guard lacks the original host creation identity")
    argv = value["argv"]
    if not isinstance(argv, list) or not argv or any(not isinstance(x, str) for x in argv) or _digest(argv) != value["argv_sha256"]:
        _fail("sdk_guard_invalid", "SDK guard command identity differs")
    build, _ = _prefix(value["build_directory"], root, occupied=True)
    if prefix == build or prefix in build.parents or build in prefix.parents:
        _fail("sdk_guard_invalid", "SDK build must be outside the installed prefix")
    record = value["record"]
    if not isinstance(record, dict) or record.get("argv") != argv or record.get("cwd") != str(build) \
            or record.get("stage") != value["stage"] or record.get("operation_id") != value["operation_id"] \
            or record.get("owner") != owner:
        _fail("sdk_guard_invalid", "SDK record command/owner identity differs")
    for key in ("spawned", "root_waited", "container_empty", "handles_closed", "log_created",
                "log_handle_closed", "log_finalized", "cleanup_verified"):
        if type(record.get(key)) is not bool:
            _fail("sdk_guard_invalid", "SDK record lacks boolean observation: " + key)
    if record["cleanup_verified"] != value["cleanup_verified"]:
        _fail("sdk_guard_invalid", "SDK guard cleanup mirror differs from its record")
    if record.get("root_child") != value["root_child"] or record.get("container") != value["container"]:
        _fail("sdk_guard_invalid", "SDK record process observations differ from guard")
    if not record["spawned"] and (value["root_child"] is not None or record.get("exit_code") is not None
                                   or record.get("resumed") is True):
        _fail("sdk_guard_invalid", "No-spawn record contradicts child observations")
    # A Job may be created before CreateProcess fails; only an observed empty
    # container is acceptable in the no-spawn settled case.
    if not record["spawned"] and value["container"] is not None:
        container = value["container"]
        if not isinstance(container, dict) or container.get("kind") != "windows_job" \
                or container.get("limit_flags") != 0x2000 or not container.get("creation_id"):
            _fail("sdk_guard_invalid", "No-spawn container is not a pre-created Job")
        if value["state"] == "settled" and record.get("active_processes_after") != 0:
            _fail("sdk_guard_invalid", "Pre-created Job lacks empty observation")
    if record.get("log") != str(build / (value["stage"] + ".log")):
        _fail("sdk_guard_invalid", "SDK record log path differs")
    if record.get("exit_code") is not None and type(record["exit_code"]) is not int:
        _fail("sdk_guard_invalid", "SDK exit observation is not an integer")
    child = value["root_child"]
    if child is not None and (not isinstance(child, dict) or type(child.get("pid")) is not int
                              or child["pid"] <= 0 or not isinstance(child.get("creation"), str) or not child["creation"]):
        _fail("sdk_guard_invalid", "SDK child observation is malformed")
    if value["container"] is not None and (not isinstance(value["container"], dict)
            or value["container"].get("kind") not in ("windows_job", "posix_process_group")):
        _fail("sdk_guard_invalid", "SDK container observation is malformed")
    if value["state"] == "intent" and record["spawned"]:
        _fail("sdk_guard_invalid", "Intent cannot contain an already spawned child")
    if value["state"] in ("owned_suspended", "running"):
        if not record["spawned"] or child is None or value["container"] is None:
            _fail("sdk_guard_invalid", "Active guard lacks owned process identity")
        if (value["state"] == "running") != (record.get("resumed") is True):
            _fail("sdk_guard_invalid", "Active guard resume observation contradicts its state")
    if record["log_finalized"]:
        if not all(record[key] for key in ("root_waited", "container_empty", "handles_closed", "log_handle_closed")):
            _fail("sdk_guard_invalid", "Final log lacks writer cleanup proof")
        if record["log_created"]:
            _sha(record.get("log_sha256"))
    if not record["log_finalized"] and record.get("log_sha256") is not None:
        _fail("sdk_guard_invalid", "Unfinalized log advertises a final SHA")
    if record["cleanup_verified"] and not all(record[key] for key in
            ("root_waited", "container_empty", "handles_closed", "log_handle_closed", "log_finalized")):
        _fail("sdk_guard_invalid", "Cleanup claim contradicts individual observations")
    if value["state"] != "settled":
        return
    if not isinstance(record, dict) or not value["cleanup_verified"] or not all(record.get(key) is True for key in
            ("cleanup_verified", "root_waited", "container_empty", "handles_closed", "log_handle_closed", "log_finalized")):
        _fail("sdk_guard_invalid", "Settled guard lacks complete cleanup proof")
    if record.get("argv") != argv or record.get("cwd") != str(build) or record.get("stage") != value["stage"]:
        _fail("sdk_guard_invalid", "Settled command/cwd differs")
    if record.get("operation_id") != value["operation_id"] or record.get("owner") != value["owner"]:
        _fail("sdk_guard_invalid", "Settled record differs from its owning operation/host")
    identity = value["build_identity"]
    if identity is None:
        if build.exists() or record.get("spawned") or record.get("log_created"):
            _fail("sdk_guard_invalid", "Absent build identity contradicts execution")
    else:
        _no_links(build)
        info = build.stat()
        if not stat.S_ISDIR(info.st_mode) or identity != [info.st_dev, info.st_ino]:
            _fail("sdk_guard_invalid", "SDK build directory identity changed")
    if type(record.get("spawned")) is not bool:
        _fail("sdk_guard_invalid", "Child creation observation is missing")
    if record["spawned"]:
        child = value["root_child"]
        if not isinstance(child, dict) or type(child.get("pid")) is not int or child["pid"] <= 0 or not child.get("creation") \
                or type(record.get("exit_code")) is not int or not isinstance(value["container"], dict):
            _fail("sdk_guard_invalid", "Settled child/container identity is missing")
        if record.get("root_child") != child or record.get("container") != value["container"]:
            _fail("sdk_guard_invalid", "Settled process observation differs from guard identity")
        container = value["container"]
        if container.get("kind") == "windows_job":
            if container.get("limit_flags") != 0x2000 or record.get("active_processes_after") != 0 or not container.get("creation_id"):
                _fail("sdk_guard_invalid", "Settled Job lacks owned-empty observation")
        elif container.get("kind") == "posix_process_group":
            if container.get("pgid") != child["pid"] or container.get("session") != child["pid"] \
                    or container.get("creation") != child["creation"] or not container.get("boot_identity") \
                    or record.get("remaining_group_members") != [] or record.get("log_transport") != "parent_pipe" \
                    or record.get("pipe_eof") is not True or record.get("pipe_reader_closed") is not True \
                    or record.get("pipe_write_failed") is not False:
                _fail("sdk_guard_invalid", "Settled group lacks owned-empty observation")
        else:
            _fail("sdk_guard_invalid", "Unknown SDK process container")
    log = build / (value["stage"] + ".log")
    if record.get("log") != str(log) or type(record.get("log_created")) is not bool:
        _fail("sdk_guard_invalid", "SDK log path/creation observation differs")
    if record["log_created"]:
        _no_links(log)
        _sha(record.get("log_sha256"))
        if not log.is_file() or _file_hash(log) != record["log_sha256"]:
            _fail("sdk_guard_invalid", "Finalized SDK log changed")
    elif log.exists() or record.get("log_sha256") is not None:
        _fail("sdk_guard_invalid", "Uncreated SDK log contradicts its evidence")


def _recover_sdk_guard_unlocked(prefix, root):
    """Only durable settled proof; never query a PID to upgrade an old guard."""
    path = _sdk_guard_path(prefix)
    temporary = path.with_name(path.name + ".new")
    exact_members = (path, temporary)
    for item in exact_members:
        _no_links(item)
    existing = [item for item in exact_members if item.exists()]
    if not existing:
        return {"schema": "g4usim_install_recovery_v1", "status": "no_sdk_guard", "prefix": str(prefix)}
    installed_transaction_id = _verify_installation(prefix)["transaction_id"]
    observations = {item: _observed_item(item) for item in existing}
    values = {item: _recovery_json(item) for item in existing}
    for value in values.values():
        _validate_sdk_guard(value, prefix, root, installed_transaction_id)
    final = values.get(temporary, values.get(path))
    if final["state"] != "settled":
        _fail("sdk_guard_unsettled", "An old non-settled guard cannot be cleared by PID disappearance or a new host")
    if path in values and temporary in values:
        base = values[path]
        if base["state"] not in ("settling", "settled"):
            _fail("sdk_guard_transition", "Only settling->settled or settled same-state recovery is supported")
        mutable = {"state", "record", "cleanup_verified"}
        if any(base[key] != final[key] for key in base if key not in mutable):
            _fail("sdk_guard_invalid", "SDK guard temporary changes immutable operation identity")
        if base["state"] == "settled" and base != final:
            _fail("sdk_guard_invalid", "Settled duplicate guard must be identical")
    # Recheck finalized logs and exact record identities before each mutation.
    def recheck():
        _validate_sdk_guard(final, prefix, root, _verify_installation(prefix)["transaction_id"])
        # Read expensive prefix/log evidence first; check exact membership last,
        # immediately alongside the observed object identities before mutation.
        for item in exact_members:
            _no_links(item)
        if {item for item in exact_members if item.exists()} != set(observations):
            _fail("sdk_guard_changed", "SDK guard member set changed after validation")
        if any(_observed_item(item) != identity for item, identity in observations.items()):
            _fail("sdk_guard_changed", "SDK guard changed after validation")
    recheck()
    if temporary in values and path in values:
        os.replace(temporary, path)
        observations[path] = observations.pop(temporary)
        recheck()
    elif temporary in values:
        # A lone temp is acceptable only when it independently holds full
        # settled proof; no reconstruction of a missing non-settled base.
        path = temporary
    recheck()
    path.unlink()
    return {"schema": "g4usim_install_recovery_v1", "status": "sdk_guard_recovered", "prefix": str(prefix),
            "operation_id": final["operation_id"], "cleanup_verified": True}


def _close_sdk_log(output):
    output.close()


def _run_sdk_command(report, installed, prefix, build, stage, argv, env, timeout, *, msvc_auxiliary=None):
    from . import _install_sdk_process as adapter
    _reject_sdk_operation(prefix)
    _no_links(build)
    record = {"stage": stage, "argv": list(map(str, argv)), "cwd": str(build), "log": str(build / f"{stage}.log"),
              "exit_code": None, "spawned": False, "root_child": None, "container": None,
              "root_waited": True, "container_empty": True, "handles_closed": True, "cleanup_errors": [],
              "log_created": False, "log_handle_closed": False, "log_finalized": False, "log_sha256": None, "cleanup_verified": False}
    report["commands"].append(record)
    guard_path = _sdk_guard_path(prefix)
    record.update(operation_id=uuid.uuid4().hex, owner=adapter.owner_identity())
    guard = {"schema": "g4usim_sdk_operation_v1", "operation_id": record["operation_id"],
             "prefix": str(prefix), "allowed_root": installed["allowed_root"],
             "installed_transaction_id": installed["transaction_id"], "build_directory": str(build),
             "build_identity": None, "stage": stage, "state": "intent", "owner": record["owner"],
             "root_child": None, "container": None, "argv": record["argv"], "argv_sha256": _digest(record["argv"]),
             "cleanup_verified": False, "record": copy.deepcopy(record)}
    if build.exists():
        info = build.stat()
        guard["build_identity"] = [info.st_dev, info.st_ino]
    output = None
    created_guard = False
    interruption = None
    try:
        _write_json(guard_path, guard, exclusive=True)  # before build/log creation or any process launch
        created_guard = True
        report["pending_guard"] = str(guard_path)
        if not build.exists():
            build.mkdir()
            info = build.stat()
            guard["build_identity"] = [info.st_dev, info.st_ino]
            _guard_update(guard_path, guard, "intent", record)
        output = Path(record["log"]).open("xb")
        record["log_created"] = True
        options = {"msvc_auxiliary": msvc_auxiliary} if os.name == "nt" and stage in ("configure", "build") and msvc_auxiliary is not None else {}
        adapter.run_owned(record["argv"], cwd=build, env=env, output=output, timeout=timeout, record=record,
                          owned=lambda: _guard_update(guard_path, guard, "owned_suspended", record),
                          running=lambda: _guard_update(guard_path, guard, "running", record),
                          settling=lambda: _guard_update(guard_path, guard, "settling", record), **options)
        if record["exit_code"] != 0:
            _fail("sdk_command", f"SDK {stage} failed with exit {record['exit_code']}; see {record['log']}")
    except BaseException as exc:
        _append_failure(report, stage, exc)
        if not isinstance(exc, Exception):
            interruption = exc
    finally:
        for detail in record.get("cleanup_errors", []):
            error = InstallError(detail["code"], detail["message"])
            _append_failure(report, detail["stage"], error)
        try:
            if output is not None:
                _close_sdk_log(output)
            record["log_handle_closed"] = True
            # Closing our descriptor is not proof that inherited writers stopped.
            writer_proof = (record.get("log_transport") != "parent_pipe" or
                            (record.get("pipe_eof") is True and record.get("pipe_reader_closed") is True
                             and record.get("pipe_write_failed") is False))
            if writer_proof and all(record.get(key) is True for key in ("root_waited", "container_empty", "handles_closed")):
                if record["log_created"]:
                    _no_links(Path(record["log"]))
                    record["log_sha256"] = _file_hash(Path(record["log"]))
                record["log_finalized"] = True
        except BaseException as exc:
            _append_failure(report, "log_finalize", exc)
            if not isinstance(exc, Exception):
                interruption = interruption or exc
        record["cleanup_verified"] = all(record.get(key) is True for key in
                                          ("root_waited", "container_empty", "handles_closed", "log_handle_closed", "log_finalized"))
        if created_guard:
            try:
                if guard["state"] != "settling":
                    _guard_update(guard_path, guard, "settling", record)
                if record["cleanup_verified"]:
                    _guard_update(guard_path, guard, "settled", record)
            except BaseException as exc:
                _append_failure(report, "guard_finalize", exc)
                if not isinstance(exc, Exception):
                    interruption = interruption or exc
    if interruption is not None:
        raise interruption
    return not report["diagnostics"]


def _persist_sdk_report(report):
    path = Path(report["build_directory"]) / "sdk-probe-receipt.json"
    report["receipt_is_final"] = True
    payload = {key: value for key, value in report.items() if key not in ("persisted_receipt_sha256", "pending_guard")}
    # A replace may complete before a later write/hash error; an old SHA must
    # never be advertised as the current disk receipt during this attempt.
    report["persisted_receipt_sha256"] = None
    _write_json(path, payload, exclusive=not path.exists())
    report["persisted_receipt_sha256"] = _file_hash(path)


def _finish_sdk_operation(report, prefix):
    if any(item.get("stage") in ("probe_receipt", "guard_cleanup") for item in report["diagnostics"]):
        return  # one finalization attempt; do not retry a failed receipt/guard write
    if not report.get("build_directory") or not Path(report["build_directory"]).is_dir():
        return
    try:
        _persist_sdk_report(report)
    except Exception as exc:
        report["receipt_is_final"] = False
        _append_failure(report, "probe_receipt", exc)
        return  # leave any settled guard for explicit recovery, never lose commands
    if report.get("pending_guard"):
        try:
            _recover_sdk_guard_unlocked(prefix, Path(report["allowed_root"]))
            report["pending_guard"] = None
        except Exception as exc:
            _append_failure(report, "guard_cleanup", exc)


def _probe_sdk_unlocked(prefix, *, build_directory, cmake, generator=None, compiler=None, timeout=180, kind="consumer", _report=None):
    """Compile and run the catalog's real Geant4 consumer in an isolated new tree.

    This checks a development toolchain, not G4UniversalSim physics. The install
    receipt stays unchanged; the separate probe receipt records actual commands.
    """
    report = _report if _report is not None else {"schema": "g4usim_sdk_probe_v1", "status": "failed", "commands": [], "diagnostics": []}
    class StopSDK(Exception):
        pass
    try:
        receipt = _verify_installation(prefix)["receipt"]
        if receipt.get("profile") != "sdk" or not isinstance(receipt.get("sdk"), dict):
            _fail("sdk_profile", "A verified SDK installation with a compile probe is required")
        path = Path(prefix)
        build, _ = _prefix(build_directory, receipt["allowed_root"])
        if path == build or path in build.parents:
            _fail("sdk_build_prefix", "SDK probes must build outside the installed prefix")
        executable = _host_tool(cmake)
        if not executable.is_file():
            _fail("cmake_missing", "Select an existing CMake executable")
        if not isinstance(timeout, (int, float)) or not 0 < timeout <= 3600:
            _fail("timeout", "SDK probe timeout must be positive and at most 3600 seconds")
        sdk = receipt["sdk"]
        if kind not in ("consumer", "application") or kind == "application" and not sdk.get("application_source"):
            _fail("sdk_probe_kind", "Select consumer or a bundled application source build")
        source_key = "application_source" if kind == "application" else "probe_source"
        command = [str(executable), "-S", str(path / sdk[source_key]), "-B", str(build),
                   f"-DGeant4_DIR={path / sdk['geant4_dir']}", "-DCMAKE_BUILD_TYPE=Release"]
        if kind == "application":
            command += ["-DG4USIM_STANDALONE_EXPORT=ON", "-DBUILD_TESTING=ON"]
        if generator:
            command += ["-G", str(generator)]
        resolved_compiler = None
        if compiler:
            resolved_compiler = _host_tool(compiler)
            command += [f"-DCMAKE_CXX_COMPILER={resolved_compiler}"]
        dependencies = [str(path / value) for value in sdk.get("dependency_prefixes", [])]
        if dependencies:
            command.append("-DCMAKE_PREFIX_PATH=" + ";".join(dependencies))
        for key, relative in sdk.get("cmake_paths", {}).items():
            command.append(f"-D{key}={path / relative}")
        env = os.environ.copy()
        msvc_auxiliary = None
        if os.name == "nt" and resolved_compiler is not None and not env.get("CMAKE_TOOLCHAIN_FILE") and not (
                {"CMAKE_CXX_COMPILER", "CMAKE_TRY_COMPILE_CONFIGURATION", "CMAKE_TOOLCHAIN_FILE"}
                & sdk.get("cmake_paths", {}).keys()):
            from . import _install_msvc_auxiliary
            msvc_auxiliary = _install_msvc_auxiliary.prepare(resolved_compiler)
            if msvc_auxiliary is not None:
                command.append("-DCMAKE_TRY_COMPILE_CONFIGURATION=Release")
        search_paths = _sdk_search_paths(sdk, [file["path"] for file in receipt["files"]], receipt["platform"])
        tool_paths = [str(path / record["path"]) for record in search_paths if record["kind"] == "bin"]
        env["PATH"] = os.pathsep.join(tool_paths) + os.pathsep + env.get("PATH", "")
        if os.name != "nt":
            libraries = [str(path / record["path"]) for record in search_paths if record["kind"] == "lib"]
            env["LD_LIBRARY_PATH"] = os.pathsep.join(libraries) + os.pathsep + env.get("LD_LIBRARY_PATH", "")
        installed = {"allowed_root": receipt["allowed_root"], "transaction_id": receipt["transaction_id"]}
        # The guard needs identity only. Release the inventory before any
        # command or guard recovery can trigger another full verification.
        del sdk, receipt
        report.update(prefix=str(path), allowed_root=installed["allowed_root"], build_directory=str(build), transaction_id=installed["transaction_id"])
        report["kind"] = kind
        report["host_tools"] = {"cmake": {"requested": str(cmake), "selected": str(cmake), "resolved": str(executable),
                                          "sha256": _file_hash(executable)}}
        if compiler:
            report["host_tools"]["compiler"] = {"requested": str(compiler), "selected": str(compiler),
                                                  "resolved": str(resolved_compiler), "sha256": _file_hash(resolved_compiler)}
        report["sdk_process_search_paths"] = tool_paths
        report["sdk_search_path_inventory"] = search_paths
        runtime_env = {key: value for key, value in env.items() if not key.startswith("G4") and key != "GEANT4_DATA_DIR"}
        system_root = os.environ.get("SystemRoot", r"C:\Windows")
        system_paths = [str(Path(system_root) / "System32"), system_root] if os.name == "nt" else ["/usr/bin", "/bin"]
        runtime_env["PATH"] = os.pathsep.join(tool_paths + system_paths)
        if os.name != "nt":
            runtime_env["LD_LIBRARY_PATH"] = os.pathsep.join(libraries)
        def run(stage, argv, policy=None):
            # Every command has a separate irreversible guard lifecycle. The
            # preceding settled operation is receipted/cleared before a NEW
            # operation id may launch the next stage, all under the same lock.
            if report.get("pending_guard"):
                _finish_sdk_operation(report, path)
                if report["diagnostics"] or report.get("pending_guard"):
                    raise StopSDK()
            options = {"msvc_auxiliary": policy} if policy is not None else {}
            if not _run_sdk_command(report, installed, path, build, stage, argv,
                                    runtime_env if stage == "run" else env, timeout, **options):
                raise StopSDK()
        run("configure", command, msvc_auxiliary)
        compiler_records = list((build / "CMakeFiles").glob("*/CMakeCXXCompiler.cmake"))
        for compiler_record in compiler_records:
            match = re.search(r'set\(CMAKE_CXX_COMPILER "([^"]+)"\)', compiler_record.read_text(encoding="utf-8", errors="replace"))
            if match:
                actual_compiler = _host_tool(match.group(1))
                report["configured_compiler"] = {"resolved": str(actual_compiler), "sha256": _file_hash(actual_compiler),
                                                 "source_record": str(compiler_record)}
                break
        configured = report.get("configured_compiler", {})
        chosen = report["host_tools"].get("compiler", {})
        build_policy = msvc_auxiliary if (len(compiler_records) == 1 and configured.get("resolved") == chosen.get("resolved")
                                         and configured.get("sha256") == chosen.get("sha256")) else None
        run("build", [str(executable), "--build", str(build), "--config", "Release", "--parallel", "2"], build_policy)
        program = "G4UniversalSim" if kind == "application" else "g4usim_sdk_probe"
        name = program + (".exe" if os.name == "nt" else "")
        probe = build / "Release" / name if (build / "Release" / name).is_file() else build / name
        _no_links(probe)
        if not probe.is_file():
            _fail("sdk_probe_output", "SDK compile did not produce the declared consumer executable")
        run("run", [str(probe), *(["--capabilities"] if kind == "application" else [])])
        report["status"] = "verified"
        report["scope"] = ("G4UniversalSim bundled source configure/compile/link/capabilities execution" if kind == "application"
                           else "Geant4 consumer configure/compile/link/run") + "; no simulation or physics validation"
    except StopSDK:
        pass
    except BaseException as exc:
        _append_failure(report, "probe", exc)
        if not isinstance(exc, Exception):
            raise
    finally:
        _finish_sdk_operation(report, Path(prefix))
    return report


def execute_plan(plan, *, allow_download=False, cancel=None, progress=None, resume=False):
    report = {"schema": RECEIPT_SCHEMA, "status": "failed", "prefix": plan.get("prefix"), "events": [],
              "capability_status": "not_probed", "transaction_path": None, "diagnostics": []}
    cleanup = []
    try:
        if plan.get("schema") != PLAN_SCHEMA or plan.get("status") != "planned" or plan.get("executable") is not True:
            _fail("plan_rejected", "A valid executable installation plan with executable=true is required")
        else:
            prefix, _ = _prefix(plan["prefix"], plan["allowed_root"], occupied=True)
            with _prefix_lock(prefix, cleanup_errors=cleanup):
                _reject_sdk_operation(prefix)
                _execute_plan_unlocked(plan, allow_download=allow_download, cancel=cancel, progress=progress, resume=resume, _report=report)
                if report.get("status") in ("published", "published_with_warning") and (prefix / MARKER).is_file():
                    disk_receipt = load_catalog(prefix / MARKER)
                    if disk_receipt.get("transaction_id") == report.get("transaction_id"):
                        report["persisted_receipt_sha256"] = _file_hash(prefix / MARKER)
                        report["receipt_is_final"] = all(disk_receipt.get(key) == report.get(key)
                                                         for key in ("status", "diagnostics", "events"))
    except (InstallError, OSError, ValueError, TypeError, KeyError) as exc:
        _append_failure(report, "execute_plan", exc)
    finally:
        for stage, error in cleanup:
            _append_failure(report, stage, error)
    return report


def verify_installation(prefix):
    with _prefix_lock(_absolute(prefix), create=False):
        result = _verify_installation(prefix)
        result["operation_pending"] = _sdk_operation_pending(Path(prefix))
        return result


def uninstall_installation(prefix):
    with _prefix_lock(_absolute(prefix), create=False):
        _reject_sdk_operation(Path(prefix))
        return _uninstall_installation_unlocked(prefix)


def recover_installation(prefix, *, allowed_root, action="discard", transaction_id=None):
    path, root = _prefix(prefix, allowed_root, occupied=True)
    with _prefix_lock(path, create=False):
        if action == "recover_sdk_guard":
            return _recover_sdk_guard_unlocked(path, root)
        _reject_sdk_operation(path)
        return _recover_installation_unlocked(path, allowed_root=allowed_root, action=action, transaction_id=transaction_id)


def inspect_transaction(prefix, *, allowed_root):
    """Read a prior transaction after restart; never create, resume or discard it.

    Older journals without the validated plan remain read-only/manual recovery.
    The OS lock rejects observing a concurrently mutating transaction.
    """
    path, root = _prefix(prefix, allowed_root, occupied=True)
    with _prefix_lock(path, create=False):
        receipt = _read_transaction(_txn_path(path), path, root)
        plan = receipt.pop("plan", None)
        result = {"schema": "g4usim_install_transaction_v1", "prefix": str(path),
                  "allowed_root": str(root), "receipt": receipt, "plan": None,
                  "resumable": False, "recovery_actions": ["discard"]}
        result["operation_pending"] = _sdk_operation_pending(path)
        if plan is None:
            result["recovery_actions"] = []
            result["diagnostics"] = [{"code": "legacy_transaction_no_plan", "message": "The original plan is missing; preserve for manual recovery"}]
            return result
        if not isinstance(plan, dict) or plan.get("schema") != PLAN_SCHEMA or plan.get("status") != "planned" \
                or plan.get("executable") is not True or plan.get("prefix") != str(path) or plan.get("allowed_root") != str(root):
            _fail("transaction_plan", "Stored plan identity does not match the transaction")
        digest = _digest({key: value for key, value in plan.items() if key not in ("space", "plan_sha256")})
        if digest != plan.get("plan_sha256") or digest != receipt.get("plan_sha256"):
            _fail("transaction_plan", "Stored plan digest does not match the transaction")
        _select({"schema": CATALOG_SCHEMA, "reviewed": True, "releases": [plan["release"]]},
                plan["profile"], plan["platform"], plan["architecture"], plan["version"])
        result.update(plan=plan, resumable=not path.exists(),
                      recovery_actions=["discard"] if path.exists() else ["resume", "discard"], diagnostics=[])
        if result["operation_pending"]:
            result.update(resumable=False, recovery_actions=[])
        return result


def probe_sdk(prefix, *, build_directory, cmake, generator=None, compiler=None, timeout=180, kind="consumer"):
    report = {"schema": "g4usim_sdk_probe_v1", "status": "failed", "commands": [], "diagnostics": []}
    cleanup = []
    try:
        path = _absolute(prefix)
        with _prefix_lock(path, create=False, cleanup_errors=cleanup):
            _reject_sdk_operation(path)
            _probe_sdk_unlocked(path, build_directory=build_directory, cmake=cmake,
                                generator=generator, compiler=compiler, timeout=timeout, kind=kind, _report=report)
    except (InstallError, OSError) as exc:
        _append_failure(report, "probe_sdk", exc)
    finally:
        for stage, error in cleanup:
            _append_failure(report, stage, error)
    return report
