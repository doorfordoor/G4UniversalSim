"""Independent read-only copy / existing archive-engine compatibility check."""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[2]
COLLAB = ROOT / "out/collab"
PACKAGE = COLLAB / "f4-qt-dependency-evidence-20261030"


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


spec = importlib.util.spec_from_file_location("f4_dependency_archive_input_check", COLLAB / "prepare-f4-archive.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
manifest = read(PACKAGE / "manifest.json")
argv = read(COLLAB / "f4-qt-dependency-include-file-argv.json")
assert len(argv) % 2 == 0
assert argv[::2] == ["--include-file"] * (len(argv) // 2)
paths = [Path(item) for item in argv[1::2]]
assert len(set(paths)) == len(paths)
assert set(paths) == {path for path in PACKAGE.rglob("*") if path.is_file()}
for row in manifest["files"]:
    source = Path(row["source_absolute_path"])
    target = PACKAGE / row["copied_relative_path"]
    assert source.read_bytes() == target.read_bytes()
    assert sha(source) == sha(target) == row["source_sha256"] == row["copied_sha256"]
    assert source.stat().st_size == target.stat().st_size == row["source_bytes"] == row["copied_bytes"]
for path in paths:
    assert module.under_workspace(path) == path.resolve()
    assert path.suffix in module.engine.TEXT_SUFFIXES | module.engine.EXPLICIT_SOURCE_SUFFIXES
    module.engine.check_text(path.read_bytes(), path)
    assert not any(part.lower() in module.engine.FORBIDDEN_COMPONENTS for part in path.relative_to(PACKAGE).parts)
for row in read(PACKAGE / "archive-inputs.json")["inputs"]:
    path = PACKAGE / row["collection_relative_path"]
    assert str(path) == row["source_absolute_path"]
    assert sha(path) == row["sha256"]
    assert path.stat().st_size == row["bytes"]
receipt = {
    "verified_utc": datetime.now(timezone.utc).isoformat(),
    "scope": "read-only collection integrity and actual prepare-f4-archive engine input-policy check; no publication or formal runner invocation",
    "copied_originals_checked": len(manifest["files"]),
    "archive_input_files_checked": len(paths),
    "all_copy_sha_bytes_equal": True,
    "exact_package_file_set": True,
    "all_inputs_accepted_by_existing_suffix_workspace_and_text_policy": True,
    "argv_windows_command_line_chars_excluding_other_parent_args": len(subprocess.list2cmdline(argv)),
    "manifest_sha256": sha(PACKAGE / "manifest.json"),
    "archive_helper_sha256": sha(COLLAB / "prepare-f4-archive.py"),
    "archive_copy_engine_sha256": sha(COLLAB / "archive-f1.py"),
    "root_tracked_changes": "Parent's authorized dependency/test/workflow edits are separate; this verifier does not write tracked files.",
}
target = COLLAB / "f4-qt-dependency-archive-input-review.json"
with target.open("xb") as handle:
    handle.write((json.dumps(receipt, indent=2) + "\n").encode())
print(json.dumps(receipt, indent=2))
