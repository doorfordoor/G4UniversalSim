from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path


def duplicate_package(old_package_dir: str, new_runs_root: str) -> str:
    old = Path(old_package_dir)
    runs_root = Path(new_runs_root)
    run_name = old.name.split("_", 2)[-1] if "_" in old.name else old.name
    target = _allocate(runs_root, f"{run_name}_copy")
    for name in ["config", "macros"]:
        src = old / name
        if src.exists():
            shutil.copytree(src, target / name)
    (target / "logs").mkdir(parents=True, exist_ok=True)
    (target / "output").mkdir(parents=True, exist_ok=True)
    for name in ["project_snapshot.json", "validation_report.txt"]:
        src = old / name
        if src.is_file():
            shutil.copyfile(src, target / name)
    _append_duplication_note(target / "validation_report.txt", old)
    _update_snapshot_for_duplicate(target / "project_snapshot.json", target)
    return str(target)


def _allocate(runs_root: Path, suffix: str) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base = f"{timestamp}_{_safe(suffix)}"
    target = runs_root / base
    index = 1
    while target.exists():
        target = runs_root / f"{base}_{index}"
        index += 1
    target.mkdir(parents=True, exist_ok=False)
    return target


def _safe(text: str) -> str:
    return "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in text).strip("._") or "run_copy"


def _append_duplication_note(path: Path, source: Path) -> None:
    try:
        with path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(f"\n[duplication]\nduplicated_from = {source}\n")
    except Exception:
        pass


def _update_snapshot_for_duplicate(path: Path, package: Path) -> None:
    if not path.is_file():
        return
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
        data["configPath"] = str(package / "config" / "main.ini")
        data["macroPath"] = str(package / "macros" / "run.mac")
        data["outputDir"] = str(package / "output")
        data["runPackage"] = {
            **data.get("runPackage", {}),
            "package_dir": str(package),
            "config_dir": str(package / "config"),
            "macro_dir": str(package / "macros"),
            "logs_dir": str(package / "logs"),
            "output_dir": str(package / "output"),
            "main_ini_path": str(package / "config" / "main.ini"),
            "run_macro_path": str(package / "macros" / "run.mac"),
            "validation_report_path": str(package / "validation_report.txt"),
            "project_snapshot_path": str(package / "project_snapshot.json"),
        }
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    except Exception:
        pass
