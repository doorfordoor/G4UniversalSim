"""Independent review probes for the schema writer's closed duplicate helper."""
import copy
import hashlib
import json
from pathlib import Path
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "out/verification/e6-duplicate-independent-review"
OUT.mkdir(exist_ok=False)
sys.path.insert(0, str(ROOT / "gui"))
sys.path.insert(0, str(ROOT / "scripts"))
from test_project_snapshot_compat import build_package_fixture
from g4usim_gui.core.project import load_project_snapshot
from g4usim_gui.history.run_package_actions import duplicate_package
from g4usim_gui.history.run_history_scanner import scan_runs_root

PRODUCT = ROOT / "gui/g4usim_gui/history/run_package_actions.py"
product_hash = hashlib.sha256(PRODUCT.read_bytes()).hexdigest()
fixture = OUT / "fixture"
fixture.mkdir()
package, _ = build_package_fixture(fixture)
old = Path(package.package_dir)
copies = OUT / "copies"
facts = []


def tree(root):
    return {str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest() for path in root.rglob("*") if path.is_file()}


def refusal(name, mutate, restore):
    mutate()
    before = tree(old)
    before_targets = set(copies.iterdir()) if copies.exists() else set()
    try:
        duplicate_package(str(old), str(copies))
    except (ValueError, OSError) as error:
        facts.append({"case": name, "refused": True, "error": str(error)})
    else:
        raise AssertionError("unsafe duplicate accepted: " + name)
    assert tree(old) == before
    assert (set(copies.iterdir()) if copies.exists() else set()) == before_targets
    restore()


(old / "output/run_summary.txt").write_text("status = completed\nactual_completed_event_count = 999\n", encoding="utf-8")
(old / "logs/run_status.json").write_text('{"state":"success","exitCode":0}', encoding="utf-8")
snapshot = old / "project_snapshot.json"
raw_snapshot = snapshot.read_bytes()
main = old / "config/main.ini"
raw_main = main.read_bytes()
# Three paths change, a current in-scope scalar edit and old-path comments stay.
marker = "# historical path comment: " + package.materials_ini_path + "\n"
main.write_bytes(raw_main.replace(b"energy = 5 MeV", b"energy = 6 MeV") + marker.encode())
before = tree(old)
new = Path(duplicate_package(str(old), str(copies)))
assert tree(old) == before and not list((new / "logs").iterdir()) and not list((new / "output").iterdir())
text = (new / "config/main.ini").read_text(encoding="utf-8")
assert f"file = {new / 'config/materials/material.ini'}" in text
assert f"config = {new / 'config/geometry/geometry.ini'}" in text
assert f"dir = {new / 'output'}" in text and "energy = 6 MeV" in text and marker in text
assert (new / "config/materials/material.ini").read_bytes() == (old / "config/materials/material.ini").read_bytes()
assert all(Path(item.path).is_relative_to(new) for item in load_project_snapshot(new / "project_snapshot.json").inputs)
facts.append({"case": "three-path-relocation-and-no-results", "source_unchanged": True, "preserved_nonpath_edit": True})
main.write_bytes(raw_main)

# The shared snapshot validator is used, including count/type checks rather
# than a top-level JSON-only check.
data = json.loads(raw_snapshot)
bad = copy.deepcopy(data); bad["materialDocument"]["rows"][0]["components"] = True
refusal("nested-envelope-type", lambda: snapshot.write_text(json.dumps(bad), encoding="utf-8"), lambda: snapshot.write_bytes(raw_snapshot))
extra = old / "config/geometry/nested/table.csv"
refusal("closed-nested-resource-set", lambda: (extra.parent.mkdir(), extra.write_text("asset", encoding="utf-8")), lambda: extra.unlink())
geometry = old / "config/geometry/geometry.ini"
raw_geometry = geometry.read_bytes()
refusal("known-sidecar-field", lambda: geometry.write_bytes(raw_geometry + b"\n[volume.Asset]\nfile=old.stl\n"), lambda: geometry.write_bytes(raw_geometry))
legacy = copy.deepcopy(data)
legacy["runPackage"]["materials_ini_path"] = str(OUT / "deleted-old/config/materials/material.ini")
legacy["runPackage"]["geometry_ini_path"] = str(OUT / "deleted-old/config/geometry/geometry.ini")
snapshot.write_text(json.dumps(legacy), encoding="utf-8")
assert load_project_snapshot(snapshot).package_root  # adapter deliberately understands this legacy pair
snapshot.write_bytes(raw_snapshot)
refusal("duplicate-does-not-silently-relax-legacy-path-contract", lambda: snapshot.write_text(json.dumps(legacy), encoding="utf-8"), lambda: snapshot.write_bytes(raw_snapshot))

# A late write failure cannot return a successful copy or inherit old status.
before = tree(old)
real_open = Path.open
def late_failure(path, mode="r", *args, **kwargs):
    if mode == "xb" and path.name == "validation_report.txt":
        raise OSError("independent late write failure")
    return real_open(path, mode, *args, **kwargs)
failed_root = OUT / "late-failure"
with patch.object(Path, "open", new=late_failure):
    try: duplicate_package(str(old), str(failed_root))
    except OSError: pass
    else: raise AssertionError("late failure falsely reported success")
assert tree(old) == before
entries = scan_runs_root(str(failed_root))
assert entries and all(entry.status != "success" for entry in entries)
assert not list(failed_root.rglob("run_status.json")) and not list(failed_root.rglob("run_summary.txt"))
facts.append({"case": "late-write-failure", "return_success": False, "history_statuses": [entry.status for entry in entries], "source_unchanged": True})
assert hashlib.sha256(PRODUCT.read_bytes()).hexdigest() == product_hash
(OUT / "review.json").write_text(json.dumps({"scope": "independent closed duplicate helper review; no frontend CLI/run claim",
                                             "product_sha256": product_hash, "product_unchanged": True, "facts": facts}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print("Independent duplicate review passed:", len(facts), "groups")
