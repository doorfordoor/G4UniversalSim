"""Keep a Windows freeze independent of unrelated applications on the host PATH."""
from __future__ import annotations

import ast
import json
import os
import sys
from pathlib import Path


def freeze_environment() -> dict[str, str]:
    env = {key: value for key, value in os.environ.items()
           if key.upper() not in {"PYTHONPATH", "PYTHONHOME", "QT_PLUGIN_PATH", "QT_QPA_PLATFORM_PLUGIN_PATH"}}
    system = Path(os.environ.get("SystemRoot", r"C:\Windows"))
    paths = (Path(sys.executable).parent, Path(sys.base_prefix),
             Path(sys.base_prefix) / "DLLs", system / "System32", system)
    env["PATH"] = os.pathsep.join(str(path) for path in paths)
    return env


def audit_binary_sources(work: Path, name: str) -> dict:
    """Fail before release if dependency collection escaped the selected runtime."""
    toc = work / "build" / name / "Analysis-00.toc"
    tree = ast.literal_eval(toc.read_text(encoding="utf-8"))
    roots = [Path(sys.prefix).resolve(), Path(sys.base_prefix).resolve(),
             Path(os.environ.get("SystemRoot", r"C:\Windows")).resolve(), work.resolve()]
    entries = []

    def visit(value):
        if isinstance(value, (list, tuple)):
            if len(value) == 3 and isinstance(value[0], str) and isinstance(value[1], str) \
                    and isinstance(value[2], str) and value[2] in {"BINARY", "EXTENSION"}:
                source = Path(value[1]).resolve()
                entries.append({"target": value[0], "source": str(source),
                                "allowed": any(source.is_relative_to(root) for root in roots)})
            else:
                for item in value:
                    visit(item)

    visit(tree)
    report = {"schema": "g4usim_windows_freeze_sources_v1", "allowed_roots": [str(p) for p in roots],
              "ok": bool(entries) and all(entry["allowed"] for entry in entries), "binaries": entries}
    (work / "binary-sources.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    if not report["ok"]:
        raise RuntimeError(f"Frozen dependency sources escaped the selected Python/Windows runtime: {work / 'binary-sources.json'}")
    return report
