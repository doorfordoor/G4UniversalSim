"""Source and payload receipts for reuse of a locally frozen application."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

RECEIPT = "g4usim-freeze.json"


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def source_identity(root: Path, kind: str) -> dict[str, str]:
    if kind == "gui":
        sources = [root / "gui/main.py", *(root / "gui/g4usim_gui").rglob("*.py")]
    elif kind == "python":
        sources = [root / "packaging/python_helper.py"]
    else:
        raise ValueError("Unknown frozen application kind")
    return {p.relative_to(root).as_posix(): digest(p) for p in sorted(sources)}


def payload_identity(folder: Path) -> dict:
    root = folder.resolve(strict=True)
    result = {}
    for path in sorted(root.rglob("*")):
        if path == root / RECEIPT:
            continue
        if path.is_symlink() and (path.is_dir() or not path.resolve(strict=True).is_relative_to(root)):
            raise ValueError(f"Frozen payload contains an unsupported link: {path}")
        if path.is_file():
            result[path.relative_to(root).as_posix()] = {"size": path.stat().st_size, "sha256": digest(path)}
        elif not path.is_dir():
            raise ValueError(f"Frozen payload contains a special file: {path}")
    if not result:
        raise ValueError("Frozen payload is empty")
    return result


def seal(folder: Path, *, kind: str, sources: dict, with_3d: bool = False) -> None:
    receipt = {"schema": "g4usim_frozen_payload_v1", "kind": kind, "platform": sys.platform,
               "sources": sources, "with_3d": with_3d, "files": payload_identity(folder)}
    with (folder / RECEIPT).open("x", encoding="utf-8") as stream:
        json.dump(receipt, stream, indent=2)


def verify(folder: Path, *, root: Path, kind: str, with_3d: bool = False) -> dict:
    with (folder / RECEIPT).open(encoding="utf-8") as stream:
        receipt = json.load(stream)
    if (receipt.get("schema") != "g4usim_frozen_payload_v1" or receipt.get("kind") != kind
            or receipt.get("platform") != sys.platform or receipt.get("with_3d") is not with_3d):
        raise ValueError("Frozen application kind, platform or 3D profile does not match")
    if receipt.get("sources") != source_identity(root, kind):
        raise ValueError("Frozen application source is stale; freeze the current source first")
    if receipt.get("files") != payload_identity(folder):
        raise ValueError("Frozen application payload differs from its recorded bytes")
    return receipt


def reject_overlap(source: Path, destinations: list[Path]) -> None:
    resolved = source.resolve(strict=True)
    for path in destinations:
        destination = path.resolve()
        if resolved.is_relative_to(destination) or destination.is_relative_to(resolved):
            raise ValueError(f"Reused application overlaps a build destination: {source} / {path}")
