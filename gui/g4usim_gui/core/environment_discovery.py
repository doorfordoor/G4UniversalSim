"""Read-only environment facts. Importable without Qt, Geant4 or an SDK.

No shell activation, simulation, installer, project mutation or global env writes.
Only explicitly supplied backends (or G4USIM_EXE/PATH candidates) are executed.
"""
from __future__ import annotations

import hashlib
import importlib.metadata
import importlib.util
import json
import math
import os
import platform
import shutil
import struct
import subprocess
import tempfile
import time
from collections.abc import Iterable, Mapping
from pathlib import Path

from .backend_capabilities import BackendCapabilities

SCHEMA = "g4usim_environment_v1"
DISCOVERY_SCHEMA = "g4usim_environment_discovery_v1"
OUTPUT_LIMIT = 4 * 1024 * 1024


def _timeout(value: float) -> float:
    value = float(value)
    if not math.isfinite(value) or value <= 0:
        raise ValueError("timeout must be finite and positive")
    return value


def _environment(env):
    result = os.environ.copy()
    if env is not None:
        for key, value in env.items():
            if value is None:
                result.pop(key, None)
            else:
                result[key] = str(value)
    return result


def _command(argv, *, timeout, env, cwd=None):
    """Bound execution and returned output; temp streams avoid inherited pipe hangs."""
    start = time.monotonic()
    record = {"argv": list(map(str, argv)), "status": "unknown", "exit_code": None,
              "elapsed_seconds": 0.0, "stderr": ""}
    working_directory = str(Path(cwd).resolve()) if cwd is not None else str(Path(argv[0]).parent.resolve())
    record["working_directory"] = working_directory
    text = ""
    try:
        with tempfile.TemporaryFile() as stdout, tempfile.TemporaryFile() as stderr:
            try:
                completed = subprocess.run(
                    record["argv"], cwd=working_directory, env=env,
                    stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr,
                    timeout=timeout, shell=False,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                record["exit_code"] = completed.returncode
                record["status"] = "completed" if completed.returncode == 0 else "nonzero_exit"
            except subprocess.TimeoutExpired:
                record["status"] = "timeout"
            size = stdout.tell()
            stdout.seek(0)
            raw = stdout.read(OUTPUT_LIMIT + 1)
            stderr.seek(0)
            record["stderr"] = stderr.read(8192).decode("utf-8", errors="replace")
            record["stdout_bytes"] = size
            if len(raw) > OUTPUT_LIMIT:
                record["status"] = "output_limit" if record["status"] != "timeout" else "timeout"
            else:
                try:
                    text = raw.decode("utf-8-sig", errors="strict")
                except UnicodeError as exc:
                    if record["status"] in ("completed", "nonzero_exit"):
                        record["status"] = "invalid_encoding"
                    record["error"] = str(exc)
    except OSError as exc:
        record.update(status="spawn_error", error=str(exc), errno=exc.errno,
                      winerror=getattr(exc, "winerror", None))
    code = record["exit_code"]
    if code is not None and code & 0xFFFFFFFF == 0xC0000135:
        record["status"] = "missing_library"
    elif code is not None and code & 0xFFFFFFFF == 0xC000007B:
        record["status"] = "loader_error"
    elif record["status"] == "nonzero_exit" and any(
            token in record["stderr"].lower() for token in
            ("error while loading shared libraries", "library not loaded", "cannot open shared object file")):
        record["status"] = "missing_library"
    record["elapsed_seconds"] = round(time.monotonic() - start, 4)
    return record, text


def _json(text):
    def reject(value):
        raise ValueError(f"Non-finite JSON value: {value}")
    def finite_float(value):
        number = float(value)
        if not math.isfinite(number):
            reject(value)
        return number
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError(f"Duplicate JSON key: {key}")
            result[key] = value
        return result
    return json.loads(text, parse_constant=reject, parse_float=finite_float, object_pairs_hook=pairs)


def _resolve_executable(executable, env):
    """One path identity for collection and probing, using the same child PATH."""
    raw = os.fspath(executable)
    located = shutil.which(raw, path=env.get("PATH", "")) if Path(raw).name == raw else None
    return Path(located or raw).expanduser().resolve()


def _data_report(text):
    data = _json(text)
    if not isinstance(data, dict) or data.get("schema") != "g4usim_geant4_data_v1":
        raise ValueError("Unsupported Geant4 data report schema")
    rows = data.get("datasets")
    if not isinstance(rows, list) or not rows or type(data.get("required_complete")) is not bool:
        raise ValueError("Invalid Geant4 dataset report")
    names = set()
    for row in rows:
        if not isinstance(row, dict) or not all(isinstance(row.get(k), str) and row[k] for k in ("env", "folder")):
            raise ValueError("Invalid dataset identity")
        if row["env"] in names or type(row.get("required")) is not bool or type(row.get("found")) is not bool:
            raise ValueError("Invalid or duplicate dataset state")
        names.add(row["env"])
        if (row["found"] and (not isinstance(row.get("path"), str) or not row["path"])) or (
                not row["found"] and row.get("path") is not None):
            raise ValueError("Dataset path contradicts found state")
    if not any(row["required"] for row in rows):
        raise ValueError("Dataset report has no required datasets")
    if data["required_complete"] != all(row["found"] for row in rows if row["required"]):
        raise ValueError("Dataset completeness contradicts individual states")
    return data


def _sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _architecture(path):
    result = {"format": "unknown", "machine": "unknown", "bits": None,
              "evidence": "binary_header"}
    try:
        with path.open("rb") as stream:
            header = stream.read(64)
            if header[:2] == b"MZ" and len(header) >= 64:
                offset = struct.unpack_from("<I", header, 60)[0]
                stream.seek(offset)
                pe = stream.read(6)
                if pe[:4] == b"PE\0\0" and len(pe) == 6:
                    machine = struct.unpack_from("<H", pe, 4)[0]
                    name, bits = {0x8664: ("x86_64", 64), 0x14C: ("x86", 32),
                                  0xAA64: ("aarch64", 64)}.get(machine, ("unknown", None))
                    result.update(format="PE", machine=name, bits=bits)
            elif header[:4] == b"\x7fELF" and len(header) >= 20 and header[5] in (1, 2):
                machine = struct.unpack_from("<H" if header[5] == 1 else ">H", header, 18)[0]
                result.update(format="ELF", bits={1: 32, 2: 64}.get(header[4]),
                              machine={3: "x86", 62: "x86_64", 183: "aarch64", 40: "arm"}.get(machine, "unknown"))
    except OSError as exc:
        result["error"] = str(exc)
    return result


def _sdk_facts(roots, env):
    """File presence is an SDK candidate, never a successful CMake/link test."""
    candidates = [(str(root), "explicit") for root in roots]
    for key in ("Geant4_DIR", "Geant4_ROOT", "GEANT4_ROOT", "CMAKE_PREFIX_PATH"):
        for value in env.get(key, "").split(";" if ";" in env.get(key, "") else os.pathsep):
            if value:
                candidates.append((value, key))
    result, seen = [], set()
    for value, source in candidates:
        try:
            path = Path(value).expanduser().resolve()
            key = os.path.normcase(str(path))
            if key in seen:
                continue
            seen.add(key)
            options = [path / "Geant4Config.cmake", path / "lib/cmake/Geant4/Geant4Config.cmake",
                       path / "lib64/cmake/Geant4/Geant4Config.cmake"]
            # Versioned share directories, bounded and only beneath an explicit prefix.
            options += sorted(path.glob("share/Geant4*/Geant4Config.cmake"))[:32]
            configs = [str(p) for p in options if p.is_file()]
            headers = [str(p) for p in (path / "include/Geant4/G4Version.hh", path / "include/G4Version.hh") if p.is_file()]
            result.append({"path": str(path), "source": source, "exists": path.exists(),
                           "config_files": configs, "headers": headers,
                           "status": "candidate" if configs or headers else "not_found",
                           "build_verified": False})
        except (OSError, ValueError) as exc:
            result.append({"path": value, "source": source, "status": "error", "error": str(exc),
                           "build_verified": False})
    return result


def _host_facts(env, timeout):
    tools = {}
    for name in ("cmake", "cl", "c++", "g++", "clang++"):
        path = shutil.which(name, path=env.get("PATH", ""))
        if path:
            path = str(Path(path).resolve())
            command, text = _command([path, *([] if name == "cl" else ["--version"])], timeout=timeout, env=env)
            tools[name] = {"path": path, "status": "observed" if command["status"] == "completed" else "candidate", "probe": command,
                           "version_output": (text or command["stderr"])[:4096], "build_verified": False}
        else:
            tools[name] = {"path": None, "status": "not_found", "build_verified": False}
    optional = {}
    for name in ("PySide6", "pyvista", "vtk", "uproot", "numpy", "matplotlib"):
        try:
            found = importlib.util.find_spec(name) is not None
            try:
                version = importlib.metadata.version(name) if found else None
            except importlib.metadata.PackageNotFoundError:
                version = None
            optional[name] = {"status": "candidate" if found else "not_found", "version": version,
                              "import_tested": False}
        except (ImportError, ValueError, OSError) as exc:
            optional[name] = {"status": "unknown", "error": str(exc), "import_tested": False}
    return {"system": platform.system(), "machine": platform.machine(),
            "python_bits": struct.calcsize("P") * 8, "tools": tools, "optional_components": optional}


def probe_environment(executable: str | Path, *, timeout: float = 5.0, cwd: str | Path | None = None,
                      env: Mapping[str, str | None] | None = None,
                      sdk_roots: Iterable[str | Path] = ()) -> dict:
    """Return JSON facts; timeout is per command, env overrides apply only to children.

    `ready` means protocols answered and required dataset directories were found.
    It does not prove initialization, dataset contents, simulation or physics.
    """
    timeout = _timeout(timeout)
    child_env = _environment(env)
    result = {"schema": SCHEMA, "executable": str(executable), "status": "unknown",
              "capabilities": {"status": "not_probed", "data": None},
              "data": {"status": "not_probed", "required_complete": None, "report": None},
              "identity": {"sha256": None, "stable": None},
              "architecture": {"format": "unknown", "machine": "unknown", "bits": None},
              "build": {"compiler_id": None, "compiler_version": None, "geant4_version_number": None},
              "sdk": _sdk_facts(sdk_roots, child_env), "diagnostics": []}
    try:
        # A bare name follows the supplied child PATH. Explicit relative paths follow cwd.
        raw = os.fspath(executable)
        path = _resolve_executable(executable, child_env)
        result["executable"] = str(path)
        if not raw or not path.is_file():
            result["status"] = "not_found"
            return result
        result["architecture"] = _architecture(path)
        initial_hash = _sha256(path)
        result["identity"]["sha256"] = initial_hash
        for field, flag in (("capabilities", "--capabilities"), ("data", "--check-geant4-data")):
            command, text = _command([str(path), flag], timeout=timeout, env=child_env,
                                     **({"cwd": cwd} if cwd is not None else {}))
            target = result[field]
            target["probe"] = command
            target["status"] = command["status"]
            accepted = command["status"] == "completed" or (
                field == "data" and command["status"] == "nonzero_exit" and command["exit_code"] == 1)
            if accepted:
                try:
                    if field == "capabilities":
                        data = _json(text)
                        checked = BackendCapabilities.from_json(json.dumps(data, allow_nan=False))
                        target.update(status="available", data=checked.data)
                        for key in result["build"]:
                            result["build"][key] = checked.data.get(key)
                    else:
                        data = _data_report(text)
                        if command["exit_code"] != (0 if data["required_complete"] else 1):
                            raise ValueError("Dataset exit status contradicts completeness")
                        target.update(status="available" if data["required_complete"] else "incomplete",
                                      required_complete=data["required_complete"], report=data)
                except (ValueError, TypeError, KeyError) as exc:
                    target.update(status="protocol_error", error=str(exc), stdout_excerpt=text[:2048])
            if target["status"] not in ("available", "incomplete"):
                result["diagnostics"].append({"stage": field, "code": target["status"]})
        result["identity"]["stable"] = _sha256(path) == initial_hash
        if not result["identity"]["stable"]:
            result["status"] = "changed_during_probe"
        elif result["capabilities"]["status"] != "available":
            result["status"] = "unavailable"
        elif result["data"]["status"] == "available":
            result["status"] = "ready"
        elif result["data"]["status"] == "incomplete":
            result["status"] = "data_incomplete"
        else:
            result["status"] = "partial"
    except (OSError, ValueError, TypeError) as exc:
        result.update(status="error")
        result["diagnostics"].append({"stage": "executable", "code": "path_error", "message": str(exc)})
    return result


def discover_environments(candidates=None, *, timeout: float = 5.0, env=None,
                          sdk_roots: Iterable[str | Path] = ()) -> dict:
    """Ordered, de-duplicated candidates; [] explicitly disables automatic discovery.

    A candidate is a path or {executable, label?, env? , sdk_roots?}. Candidate env
    overrides are per child and allow two backends to use different library/data roots.
    None discovers G4USIM_EXE and named G4UniversalSim executables on PATH only.
    """
    timeout = _timeout(timeout)
    effective = _environment(env)
    sdk_roots = tuple(sdk_roots)
    if candidates is None:
        candidates = []
        if effective.get("G4USIM_EXE"):
            candidates.append({"executable": effective["G4USIM_EXE"], "source": "G4USIM_EXE"})
        for name in ("G4UniversalSim", "G4UniversalSim.exe"):
            path = shutil.which(name, path=effective.get("PATH", ""))
            if path:
                candidates.append({"executable": path, "source": "PATH"})
    elif isinstance(candidates, (str, Path, Mapping)):
        candidates = [candidates]
    environments, seen = [], set()
    for candidate in candidates:
        item = dict(candidate) if isinstance(candidate, Mapping) else {"executable": candidate}
        if "executable" not in item:
            environments.append({"schema": SCHEMA, "status": "invalid_candidate", "executable": "",
                                 "diagnostics": [{"code": "missing_executable"}]})
            continue
        overrides = dict(env or {})
        overrides.update(item.get("env") or {})
        candidate_roots = tuple(item.get("sdk_roots", sdk_roots))
        executable = item["executable"]
        try:
            executable = _resolve_executable(executable, _environment(overrides))
        except (OSError, ValueError, TypeError):
            # Probe preserves each unresolved candidate's own diagnostic. It must
            # not hide a later valid candidate behind a speculative dedup key.
            pass
        else:
            # Dedup only after PATH resolution; pass that exact path to the probe.
            # Different activation facts remain distinct environments.
            key = (os.path.normcase(str(executable)), tuple(sorted(overrides.items())),
                   tuple(map(str, candidate_roots)))
            if key in seen:
                continue
            seen.add(key)
        facts = probe_environment(executable, timeout=timeout, env=overrides, sdk_roots=candidate_roots)
        facts["candidate"] = {"source": str(item.get("source", "explicit")), "label": str(item.get("label", ""))}
        environments.append(facts)
    return {"schema": DISCOVERY_SCHEMA, "environments": environments,
            "host": _host_facts(effective, timeout), "sdk": _sdk_facts(sdk_roots, effective)}
