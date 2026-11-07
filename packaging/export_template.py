"""Write or verify the standalone-export template manifest.

The manifest is the only statement of which files form the downloadable
template tree.  ``core.export_project`` computes the same identity; this tool
keeps the manifest reproducible from a checkout (``--write``) or verifies that
a checkout still matches the committed manifest (``--check``).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
GUI_ROOT = REPO_ROOT / "gui"
for _path in (str(REPO_ROOT), str(GUI_ROOT)):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from g4usim_gui.core import export_project as _export  # noqa: E402


def _manifest_path(root: Path) -> Path:
    return root / "packaging" / _export.TEMPLATE_MANIFEST_NAME


def write_manifest(root: Path) -> dict:
    members = _export.collect_template_members(root)
    manifest = _export.template_manifest(members)
    target = _manifest_path(root)
    target.write_bytes(_export._json_bytes(manifest))
    return manifest


def check_manifest(root: Path) -> tuple[dict, list[str]]:
    target = _manifest_path(root)
    if not target.is_file():
        return {}, [f"missing manifest: {target}"]
    try:
        manifest = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return {}, [f"unreadable manifest: {exc}"]
    problems: list[str] = []
    try:
        declared = _export._validate_manifest(manifest, target)
    except _export.ExportError as exc:
        return manifest, [f"invalid manifest: {exc.message}"]
    current = _export.collect_template_members(root)
    declared_paths = {member.path for member in declared}
    current_paths = {member.path for member in current}
    for missing in sorted(declared_paths - current_paths):
        problems.append(f"missing from the checkout: {missing}")
    for extra in sorted(current_paths - declared_paths):
        problems.append(f"not declared in the manifest: {extra}")
    for member in sorted(current, key=lambda item: item.path):
        expected = next((item for item in declared if item.path == member.path), None)
        if expected is None:
            continue
        if expected.sha256 != member.sha256 or expected.bytes != member.bytes:
            problems.append(f"content changed: {member.path}")
    identity = _export.template_identity(current)
    if manifest.get("identity", {}).get("value") != identity["value"]:
        problems.append("identity differs from the committed manifest")
    return manifest, problems


def _print(payload: dict) -> None:
    json.dump(payload, sys.stdout, ensure_ascii=False, sort_keys=True, indent=2)
    sys.stdout.write("\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="write or verify packaging/export_template_manifest.json")
    parser.add_argument("--root", default=str(REPO_ROOT))
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--write", action="store_true",
                       help="rewrite the manifest from the checkout")
    group.add_argument("--check", action="store_true",
                       help="verify the checkout against the manifest")
    group.add_argument("--identity", action="store_true",
                       help="print the manifest identity")
    args = parser.parse_args(argv)
    root = Path(args.root).resolve()
    if not (root / "CMakeLists.txt").is_file():
        _print({"status": "error", "message": f"no checkout at {root}"})
        return 2
    if args.write:
        manifest = write_manifest(root)
        _print({"status": "written", "manifest_path": str(_manifest_path(root)),
                "identity": manifest["identity"]})
        return 0
    if args.check:
        manifest, problems = check_manifest(root)
        _print({"status": "ok" if not problems else "mismatch",
                "identity": manifest.get("identity"),
                "problems": problems})
        return 0 if not problems else 1
    manifest = json.loads(_manifest_path(root).read_text(encoding="utf-8"))
    _print({"identity": manifest.get("identity"), "members": len(manifest.get("members", []))})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
