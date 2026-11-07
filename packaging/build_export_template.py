"""Copy the standalone-export template into a frozen package directory.

The template is data only: C++ sources, CMake files, config/macros, schema,
licenses and a few documents.  This builder copies exactly the members listed
in ``packaging/export_template_manifest.json`` (single source of truth), checks
that no member is a link, and verifies the copied tree identity before it is
shipped inside the package.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import stat
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
GUI_ROOT = REPO_ROOT / "gui"
for _path in (str(REPO_ROOT), str(GUI_ROOT)):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from g4usim_gui.core import export_project as _export  # noqa: E402

TEMPLATE_DIRECTORY = "export-template"


def _is_link(path: Path) -> bool:
    if path.is_symlink():
        return True
    try:
        attributes = getattr(path.stat(follow_symlinks=False), "st_file_attributes", 0)
    except FileNotFoundError:
        # A not-yet-created path is not a link; callers create it afterwards.
        return False
    except OSError as exc:
        # Permission or I/O failures are refusals, never evidence of "no link".
        raise _export.ExportError(
            "write_failed",
            f"cannot inspect template path {path}: {exc}") from exc
    return bool(attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT)


def _check_parents(path: Path, root: Path) -> None:
    current = path
    while True:
        if _is_link(current):
            raise _export.ExportError(
                "linked_or_ambiguous_path",
                f"template path contains a link: {current}")
        if current == root or current.parent == current:
            return
        current = current.parent


def _guard(path: Path, label: str) -> Path:
    try:
        return Path(_export._bundle._no_links(path))  # type: ignore[attr-defined]
    except ValueError as exc:
        raise _export.ExportError(
            "linked_or_ambiguous_path", f"{label}: {path}: {exc}") from exc


def build_export_template(package_dir: str | Path, *, repo_root: str | Path | None = None,
                          manifest_path: str | Path | None = None) -> dict:
    # Keep the caller's spelling until the shared guard has inspected every
    # lexical component; resolve() would silently drop link/../ segments.
    root = _guard(Path(repo_root or REPO_ROOT), "template repository root")
    manifest_file = _guard(
        Path(manifest_path or (root / "packaging" / _export.TEMPLATE_MANIFEST_NAME)),
        "template manifest")
    if not manifest_file.is_file():
        raise _export.ExportError("export_template_unavailable",
                                  f"template manifest is missing: {manifest_file}")
    try:
        manifest_raw = manifest_file.read_bytes()
        manifest = json.loads(manifest_raw.decode("utf-8"))
    except (OSError, ValueError) as exc:
        raise _export.ExportError("export_template_unavailable",
                                  f"template manifest is unreadable: {exc}") from exc
    declared = _export._validate_manifest(manifest, manifest_file)
    declared_identity = manifest.get("identity", {})
    package_root = _guard(Path(package_dir), "package directory")
    if not package_root.is_dir():
        raise _export.ExportError("destination_parent_missing",
                                  f"package directory is missing: {package_root}")
    target_root = package_root / TEMPLATE_DIRECTORY
    if target_root.exists() or target_root.is_symlink():
        raise _export.ExportError("destination_exists",
                                  f"export template target already exists: {target_root}")
    staging_parent = Path(tempfile.mkdtemp(
        prefix=f".{TEMPLATE_DIRECTORY}.k2-", dir=package_root))
    staging = staging_parent / TEMPLATE_DIRECTORY
    try:
        staging.mkdir(parents=True)
    except OSError as exc:
        shutil.rmtree(staging_parent, ignore_errors=True)
        raise _export.ExportError("write_failed",
                                  f"cannot create template staging: {exc}") from exc
    try:
        _copy_declared_template(root, declared, manifest_file, manifest_raw, staging)
        _export._bundle._publish_directory(staging, target_root)  # type: ignore[attr-defined]
    except _export.ExportError:
        shutil.rmtree(staging_parent, ignore_errors=True)
        raise
    except OSError as exc:
        shutil.rmtree(staging_parent, ignore_errors=True)
        raise _export.ExportError("write_failed",
                                  f"cannot publish export template: {exc}") from exc
    except BaseException:
        shutil.rmtree(staging_parent, ignore_errors=True)
        raise
    return {
        "status": "built",
        "template_root": str(target_root),
        "members": len(declared),
        "identity": _export.template_identity(declared),
        "manifest": str(target_root / _export.TEMPLATE_MANIFEST_NAME),
    }


def _copy_declared_template(root: Path, declared: list, manifest_file: Path,
                            manifest_raw: bytes, staging: Path) -> None:
    for member in declared:
        source = root / member.source_path
        if not source.is_file():
            raise _export.ExportError("export_template_unavailable",
                                      f"template source is missing: {member.path}")
        _check_parents(source, root)
        raw = _export.read_template_member_bytes(
            source, kind="export_template_unavailable", label="template source")
        if len(raw) != member.bytes or _export.sha256_bytes(raw) != member.sha256:
            raise _export.ExportError("template_identity_mismatch",
                                      f"template source changed: {member.path}")
        target = staging / member.path
        _check_parents(target.parent, staging)
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            raise _export.ExportError("write_failed",
                                      f"refusing to overwrite template file: {target}")
        target.write_bytes(raw)
    manifest_target = staging / _export.TEMPLATE_MANIFEST_NAME
    if _is_link(manifest_file):
        raise _export.ExportError("linked_or_ambiguous_path",
                                  f"template manifest is a link: {manifest_file}")
    current = manifest_file.read_bytes()
    if current != manifest_raw:
        raise _export.ExportError(
            "input_changed_during_export",
            "template manifest changed while the package was being built")
    manifest_target.write_bytes(manifest_raw)
    copied: list[_export.TemplateMember] = []
    for member in declared:
        target = staging / member.path
        raw = target.read_bytes()
        if len(raw) != member.bytes or _export.sha256_bytes(raw) != member.sha256:
            raise _export.ExportError("template_identity_mismatch",
                                      f"copied template file differs: {member.path}")
        copied.append(_export.TemplateMember(member.path, member.path, member.role,
                                             member.sha256, member.bytes))
    identity = _export.template_identity(copied)
    expected = _export.template_identity(declared)
    if identity["value"] != expected["value"]:
        raise _export.ExportError("template_identity_mismatch",
                                  "copied template identity differs from the manifest")


def _print(payload: dict) -> None:
    json.dump(payload, sys.stdout, ensure_ascii=False, sort_keys=True, indent=2)
    sys.stdout.write("\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="copy the standalone-export template into a package")
    parser.add_argument("--package", required=True,
                        help="package directory that receives export-template/")
    parser.add_argument("--repo-root", default=str(REPO_ROOT))
    parser.add_argument("--manifest", default=None)
    args = parser.parse_args(argv)
    try:
        result = build_export_template(args.package, repo_root=args.repo_root,
                                       manifest_path=args.manifest)
    except _export.ExportError as exc:
        _print({"status": "error", "kind": exc.kind, "message": exc.message})
        return 2
    _print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
