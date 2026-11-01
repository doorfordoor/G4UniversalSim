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
        if type(file.get("executable", False)) is not bool:
            _fail("file_mode", "Executable flags must be boolean")
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


def _txn_path(prefix):
    return prefix.parent / f".{prefix.name}.g4usim-install"


@contextmanager
def _prefix_lock(prefix, *, create=True):
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
    finally:
        if acquired:
            os.lseek(descriptor, 0, os.SEEK_SET)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(descriptor, msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)


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
        result.update(prefix=str(target), allowed_root=str(root), release=release,
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
            if file is None or size != file["size_bytes"] or executable != file.get("executable", False):
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


def _execute_plan_unlocked(plan, *, allow_download=False, cancel=None, progress=None, resume=False):
    """Install reviewed bytes; return real receipts, never an inferred capability pass."""
    receipt = {"schema": RECEIPT_SCHEMA, "status": "staging", "events": [],
               "capability_status": "not_probed", "diagnostics": [], "prefix": plan.get("prefix"),
               "plan_sha256": plan.get("plan_sha256"), "transaction_id": uuid.uuid4().hex}
    transaction = None
    published = False
    try:
        if plan.get("schema") != PLAN_SCHEMA or not plan.get("executable") or plan.get("status") != "planned":
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
            previous = _read_transaction(transaction, target, root)
            if previous["plan_sha256"] != plan["plan_sha256"]:
                _fail("resume_plan", "Transaction belongs to a different plan")
            receipt["transaction_id"] = previous["transaction_id"]
            receipt["events"] = previous.get("events", [])
        else:
            transaction.mkdir()
            _write_json(transaction / JOURNAL, dict(receipt, allowed_root=str(root), plan=plan), exclusive=True)
        receipt["transaction_path"] = str(transaction)
        archives = transaction / "archives"
        archives.mkdir(exist_ok=True)
        payload = transaction / "payload"
        if payload.exists():
            _safe_remove_tree(payload)
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
        _safe_remove_tree(transaction)
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


def _read_transaction(transaction, prefix, root):
    _no_links(transaction)
    value = load_catalog(transaction / JOURNAL)
    if value.get("schema") != RECEIPT_SCHEMA or value.get("prefix") != str(prefix) \
            or value.get("allowed_root") != str(root) or not re.fullmatch(r"[0-9a-f]{32}", value.get("transaction_id", "")):
        _fail("transaction_identity", "Transaction does not belong to the selected prefix and root")
    return value


def _verify_installation(prefix, *, _original_prefix=None, _prepared=False):
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
    value = _read_transaction(transaction, path, root)
    if path.exists():
        installed = _verify_installation(path, _prepared=True)
        if installed["transaction_id"] != value["transaction_id"]:
            _fail("recovery_identity", "Published prefix belongs to another transaction")
        if installed["receipt"]["status"] == "prepared":
            committed = installed["receipt"]
            committed["status"] = "published"
            _event(committed, "publish", "recovered_published", None)
            _write_json(path / MARKER, committed)
    _safe_remove_tree(transaction)
    return {"schema": "g4usim_install_recovery_v1", "status": "recovered", "prefix": str(path),
            "published_prefix_preserved": path.exists(), "transaction_id": value["transaction_id"]}


def _probe_sdk_unlocked(prefix, *, build_directory, cmake, generator=None, compiler=None, timeout=180, kind="consumer"):
    """Compile and run the catalog's real Geant4 consumer in an isolated new tree.

    This checks a development toolchain, not G4UniversalSim physics. The install
    receipt stays unchanged; the separate probe receipt records actual commands.
    """
    report = {"schema": "g4usim_sdk_probe_v1", "status": "failed", "commands": [], "diagnostics": []}
    try:
        verified = _verify_installation(prefix)
        receipt = verified["receipt"]
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
        if generator:
            command += ["-G", str(generator)]
        if compiler:
            command += [f"-DCMAKE_CXX_COMPILER={_host_tool(compiler)}"]
        dependencies = [str(path / value) for value in sdk.get("dependency_prefixes", [])]
        if dependencies:
            command.append("-DCMAKE_PREFIX_PATH=" + ";".join(dependencies))
        for key, relative in sdk.get("cmake_paths", {}).items():
            command.append(f"-D{key}={path / relative}")
        build.mkdir()
        env = os.environ.copy()
        tool_paths = [str(path / "bin"), *(str(path / value / "bin") for value in sdk.get("dependency_prefixes", []))]
        env["PATH"] = os.pathsep.join(tool_paths) + os.pathsep + env.get("PATH", "")
        if os.name != "nt":
            libraries = [str(path / value / "lib") for value in sdk.get("dependency_prefixes", [])]
            env["LD_LIBRARY_PATH"] = os.pathsep.join(libraries) + os.pathsep + env.get("LD_LIBRARY_PATH", "")
        report.update(prefix=str(path), build_directory=str(build), transaction_id=receipt["transaction_id"])
        report["kind"] = kind
        report["host_tools"] = {"cmake": {"requested": str(cmake), "selected": str(cmake), "resolved": str(executable),
                                          "sha256": _file_hash(executable)}}
        if compiler:
            resolved_compiler = _host_tool(compiler)
            report["host_tools"]["compiler"] = {"requested": str(compiler), "selected": str(compiler),
                                                  "resolved": str(resolved_compiler), "sha256": _file_hash(resolved_compiler)}
        report["sdk_process_search_paths"] = tool_paths
        runtime_env = {key: value for key, value in env.items() if not key.startswith("G4") and key != "GEANT4_DATA_DIR"}
        system_root = os.environ.get("SystemRoot", r"C:\Windows")
        system_paths = [str(Path(system_root) / "System32"), system_root] if os.name == "nt" else ["/usr/bin", "/bin"]
        runtime_env["PATH"] = os.pathsep.join(tool_paths + system_paths)
        if os.name != "nt":
            runtime_env["LD_LIBRARY_PATH"] = os.pathsep.join(libraries)
        def run(stage, argv):
            log = build / f"{stage}.log"
            record = {"stage": stage, "argv": list(map(str, argv)), "cwd": str(build), "log": str(log), "exit_code": None}
            report["commands"].append(record)
            with log.open("xb") as output:
                try:
                    process = subprocess.run(argv, cwd=build, env=runtime_env if stage == "run" else env, stdin=subprocess.DEVNULL,
                                             stdout=output, stderr=subprocess.STDOUT, timeout=timeout,
                                             creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                    record["exit_code"] = process.returncode
                except subprocess.TimeoutExpired:
                    _fail("sdk_timeout", f"SDK {stage} timed out; see {log}")
            if record["exit_code"] != 0:
                _fail("sdk_command", f"SDK {stage} failed; see {log}")
        run("configure", command)
        for compiler_record in (build / "CMakeFiles").glob("*/CMakeCXXCompiler.cmake"):
            match = re.search(r'set\(CMAKE_CXX_COMPILER "([^"]+)"\)', compiler_record.read_text(encoding="utf-8", errors="replace"))
            if match:
                actual_compiler = _host_tool(match.group(1))
                report["configured_compiler"] = {"resolved": str(actual_compiler), "sha256": _file_hash(actual_compiler),
                                                 "source_record": str(compiler_record)}
                break
        run("build", [str(executable), "--build", str(build), "--config", "Release", "--parallel", "2"])
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
    except Exception as exc:
        report["diagnostics"].append({"code": getattr(exc, "code", "io_error"), "message": str(exc)})
    if report.get("build_directory"):
        _write_json(Path(report["build_directory"]) / "sdk-probe-receipt.json", report, exclusive=True)
    return report


def execute_plan(plan, *, allow_download=False, cancel=None, progress=None, resume=False):
    try:
        if plan.get("schema") != PLAN_SCHEMA or plan.get("status") != "planned" or plan.get("executable") is not True:
            return _execute_plan_unlocked(plan, allow_download=allow_download, cancel=cancel, progress=progress, resume=resume)
        prefix, _ = _prefix(plan["prefix"], plan["allowed_root"], occupied=True)
        with _prefix_lock(prefix):
            return _execute_plan_unlocked(plan, allow_download=allow_download, cancel=cancel, progress=progress, resume=resume)
    except (InstallError, OSError, ValueError, TypeError, KeyError) as exc:
        return {"schema": RECEIPT_SCHEMA, "status": "failed", "prefix": plan.get("prefix"), "events": [],
                "capability_status": "not_probed", "transaction_path": None,
                "diagnostics": [{"code": getattr(exc, "code", "invalid_input"), "message": str(exc)}]}


def verify_installation(prefix):
    with _prefix_lock(_absolute(prefix), create=False):
        return _verify_installation(prefix)


def uninstall_installation(prefix):
    with _prefix_lock(_absolute(prefix), create=False):
        return _uninstall_installation_unlocked(prefix)


def recover_installation(prefix, *, allowed_root, action="discard", transaction_id=None):
    path, _ = _prefix(prefix, allowed_root, occupied=True)
    with _prefix_lock(path, create=False):
        return _recover_installation_unlocked(path, allowed_root=allowed_root, action=action, transaction_id=transaction_id)


def inspect_transaction(prefix, *, allowed_root):
    """Read a prior transaction after restart; never create, resume or discard it.

    Older journals without the validated plan remain explicitly discard-only.
    The OS lock rejects observing a concurrently mutating transaction.
    """
    path, root = _prefix(prefix, allowed_root, occupied=True)
    with _prefix_lock(path, create=False):
        receipt = _read_transaction(_txn_path(path), path, root)
        plan = receipt.pop("plan", None)
        result = {"schema": "g4usim_install_transaction_v1", "prefix": str(path),
                  "allowed_root": str(root), "receipt": receipt, "plan": None,
                  "resumable": False, "recovery_actions": ["discard"]}
        if plan is None:
            result["diagnostics"] = [{"code": "legacy_transaction_no_plan", "message": "This older transaction can only be discarded"}]
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
        return result


def probe_sdk(prefix, *, build_directory, cmake, generator=None, compiler=None, timeout=180, kind="consumer"):
    try:
        with _prefix_lock(_absolute(prefix), create=False):
            return _probe_sdk_unlocked(prefix, build_directory=build_directory, cmake=cmake,
                                       generator=generator, compiler=compiler, timeout=timeout, kind=kind)
    except (InstallError, OSError) as exc:
        return {"schema": "g4usim_sdk_probe_v1", "status": "failed", "commands": [],
                "diagnostics": [{"code": getattr(exc, "code", "io_error"), "message": str(exc)}]}
