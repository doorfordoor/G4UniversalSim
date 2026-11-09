#!/usr/bin/env python3
"""Carry exact CI evidence in the job log when artifact storage is unavailable."""

import argparse
import base64
from datetime import datetime, timedelta
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import sys
import zipfile


MARK = "G4USIM_CI_EVIDENCE_"
SCHEMA = "g4usim_ci_log_evidence_v1"
MANIFEST = "g4usim-evidence-manifest.json"
CHUNK_BYTES = 6144
MAX_ARCHIVE = 32 * 1024 * 1024
MAX_MEMBER = 96 * 1024 * 1024
MAX_TOTAL = 512 * 1024 * 1024
MAX_MEMBERS = 20000


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def ordinary(path):
    status = path.lstat()
    return not path.is_symlink() and not getattr(status, "st_file_attributes", 0) & 0x400


def inventory(root, patterns):
    files = {}
    for pattern in patterns:
        value = PurePosixPath(pattern)
        require(not value.is_absolute() and ".." not in value.parts and "\\" not in pattern,
                "Invalid evidence selection")
        for item in root.glob(pattern):
            relative = item.relative_to(root)
            if any(part.startswith(".") for part in relative.parts) or item.is_dir():
                continue
            require(item.is_file() and item.resolve(strict=True) == item and ordinary(item)
                    and all(ordinary(folder) for folder in item.parents if folder.is_relative_to(root)),
                    f"Not an ordinary evidence file: {relative}")
            files[relative.as_posix()] = item
    require(0 < len(files) <= MAX_MEMBERS and MANIFEST not in files and len(files) == len({p.casefold() for p in files}),
            "Empty, colliding, or reserved evidence inventory")
    return files


def emit(root, name, include):
    require(re.fullmatch(r"[a-zA-Z0-9_.-]+", name), "Invalid evidence name")
    root = root.resolve(strict=True)
    require(root.is_dir(), "Evidence root is not a directory")
    files = inventory(root, include)
    context = {key: os.environ.get(key) for key in ("GITHUB_SHA", "GITHUB_RUN_ID", "GITHUB_RUN_ATTEMPT", "GITHUB_JOB")}
    buffer = io.BytesIO()
    members = {}
    size = 0
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for relative, path in sorted(files.items()):
            declared = path.stat().st_size
            require(declared <= MAX_MEMBER and size + declared <= MAX_TOTAL, "Evidence member exceeds raw size budget")
            with path.open("rb") as stream:
                raw = stream.read(declared + 1)
            require(len(raw) == declared, "Evidence member changed while being read")
            size += len(raw)
            archive.writestr(relative, raw)
            members[relative] = {"bytes": len(raw), "sha256": sha(raw)}
            require(buffer.tell() <= MAX_ARCHIVE, "Evidence exceeds job log transport budget")
        manifest = {"schema": SCHEMA, "name": name, "context": context, "files": members}
        archive.writestr(MANIFEST, json.dumps(manifest, sort_keys=True, separators=(",", ":")))
    raw = buffer.getvalue()
    require(0 < len(raw) <= MAX_ARCHIVE, "Evidence exceeds job log transport budget")
    chunks = (len(raw) + CHUNK_BYTES - 1) // CHUNK_BYTES
    header = {"schema": SCHEMA, "name": name, "context": context,
              "bytes": len(raw), "sha256": sha(raw), "chunks": chunks}
    print(MARK + "BEGIN " + json.dumps(header, separators=(",", ":")))
    for i in range(chunks):
        value = base64.b64encode(raw[i * CHUNK_BYTES:(i + 1) * CHUNK_BYTES]).decode("ascii")
        print(f"{MARK}CHUNK {i:06d} {value}")
    print(MARK + "END " + header["sha256"], flush=True)


def timestamp(raw):
    value = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    require(value.tzinfo is not None, "Missing timestamp timezone")
    return value


def recover(log, out, name, commit, run_id, attempt, job, started_at, completed_at):
    """Verify bytes from a log the caller obtained from the authenticated job endpoint."""
    require(not out.exists(), "Recovered ZIP path already exists")
    started, completed = timestamp(started_at), timestamp(completed_at)
    require(started <= completed, "Invalid fallback step interval")
    header, ended, count = None, False, 0
    raw = bytearray()
    with log.open(encoding="utf-8", errors="strict") as stream:
        for line in stream:
            match = re.match(r"^(\S+)\s+" + MARK + r"(BEGIN|CHUNK|END) (.*)$", line.rstrip("\r\n"))
            if not match:
                continue
            at, tag, value = match.groups()
            require(len(value) <= 9000 and started <= timestamp(at) < completed + timedelta(seconds=1),
                    "Evidence record outside approved fallback step or too large")
            require(not ended, "Unexpected evidence after END")
            if tag == "BEGIN":
                require(header is None, "Duplicate evidence BEGIN")
                header = json.loads(value)
                context = header.get("context", {})
                require(header.get("schema") == SCHEMA and header.get("name") == name
                        and context.get("GITHUB_SHA") == commit and context.get("GITHUB_RUN_ID") == run_id
                        and context.get("GITHUB_RUN_ATTEMPT") == attempt and context.get("GITHUB_JOB") == job,
                        "Unexpected evidence run or job identity")
                require(type(header.get("bytes")) is int and 0 < header["bytes"] <= MAX_ARCHIVE
                        and header.get("chunks") == (header["bytes"] + CHUNK_BYTES - 1) // CHUNK_BYTES,
                        "Invalid evidence size")
            elif tag == "CHUNK":
                require(header is not None and count < header["chunks"], "Unexpected evidence chunk")
                index, data = value.split(" ", 1)
                require(index == f"{count:06d}", "Evidence chunk missing, duplicate, or out of order")
                decoded = base64.b64decode(data, validate=True)
                require(len(decoded) == min(CHUNK_BYTES, header["bytes"] - len(raw)), "Invalid evidence chunk length")
                raw.extend(decoded)
                count += 1
            else:
                require(header is not None and count == header["chunks"] and len(raw) == header["bytes"]
                        and value == header["sha256"] == sha(raw), "Evidence incomplete or digest mismatch")
                ended = True
    require(ended, "Missing complete evidence envelope")
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        entries = archive.infolist()
        require(1 < len(entries) <= MAX_MEMBERS + 1 and sum(x.file_size for x in entries) <= MAX_TOTAL + MAX_MEMBER
                and all(x.file_size <= MAX_MEMBER and x.compress_type == zipfile.ZIP_DEFLATED
                        and not x.is_dir() and (x.external_attr >> 16) & 0o170000 != 0o120000 for x in entries),
                "Recovered ZIP exceeds bounds or has unsupported members")
        names = archive.namelist()
        require(len(names) == len(set(names)) == len({p.casefold() for p in names}), "Colliding ZIP members")
        require(sum(x.file_size for x in entries if x.filename != MANIFEST) <= MAX_TOTAL,
                "Recovered evidence exceeds the raw size budget")
        manifest = json.loads(archive.read(MANIFEST))
        require(manifest["schema"] == SCHEMA and manifest["name"] == name
                and manifest["context"] == header["context"] and manifest["files"]
                and set(manifest["files"]) == set(names) - {MANIFEST}, "Wrong ZIP evidence manifest")
        for name, expected in manifest["files"].items():
            relative = PurePosixPath(name)
            require(not relative.is_absolute() and ".." not in relative.parts and "\\" not in name and ":" not in name,
                    "Unsafe evidence member name")
            contents = archive.read(name)
            require(expected == {"bytes": len(contents), "sha256": sha(contents)}, f"Evidence member changed: {name}")
    with out.open("xb") as stream:
        stream.write(raw)
    print(json.dumps({"scope": "recovered job log evidence", "name": header["name"],
                      "archive_sha256": header["sha256"], "bytes": len(raw), "files": len(manifest["files"])}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    encode = commands.add_parser("emit")
    encode.add_argument("--root", type=Path, required=True)
    encode.add_argument("--name", required=True)
    encode.add_argument("--include", action="append", required=True)
    decode = commands.add_parser("recover")
    for key in ("name", "commit", "run-id", "attempt", "job", "started-at", "completed-at"):
        decode.add_argument("--" + key, required=True)
    decode.add_argument("--log", type=Path, required=True)
    decode.add_argument("--out", type=Path, required=True)
    a = parser.parse_args()
    try:
        if a.command == "emit":
            emit(a.root, a.name, a.include)
        else:
            recover(a.log, a.out, a.name, a.commit, a.run_id, a.attempt, a.job, a.started_at, a.completed_at)
    except (ValueError, KeyError, OSError, zipfile.BadZipFile) as error:
        print(f"CI evidence transport failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
