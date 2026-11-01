"""Capability-dependent GDML evidence: unavailable is a tested refusal, never a skip."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path


def gdml_runtime_available(executable: Path) -> bool:
    result = subprocess.run([str(executable), "--capabilities"], capture_output=True,
                            text=True, errors="replace", timeout=30)
    assert result.returncode == 0, (result.returncode, result.stdout, result.stderr)
    templates = json.loads(result.stdout)["templates"]
    gdml = [item for item in templates if item["id"] == "gdml"]
    assert len(gdml) == 1 and type(gdml[0]["runtime"]) is bool, gdml
    print("G4USIM_GDML_TEST_SCOPE=" + json.dumps({
        "runtime": gdml[0]["runtime"],
        "scope": "supported GDML checks" if gdml[0]["runtime"] else
                 "actual early capability refusal; no GDML identity, fields or physics validation",
    }), flush=True)
    return gdml[0]["runtime"]


def assert_gdml_unavailable_rejection(output: Path, log: str, returncode: int | None = None) -> None:
    if returncode is not None:
        assert returncode != 0, (returncode, log[-3000:])
    assert "Geometry capability 'GDML' is not available" in log, log[-3000:]
    products = [path for path in output.rglob("*") if path.is_file() and (
        path.suffix.lower() in (".csv", ".root", ".gdml") or path.name.startswith("trajectories"))]
    assert not products, products
    summary = output / "run_summary.txt"
    if summary.is_file():
        facts = dict(line.split(" = ", 1) for line in summary.read_text(encoding="utf-8").splitlines()
                     if " = " in line)
        assert facts["status"] == "failed", facts
        assert facts["run_count"] == "0", facts
        assert facts["actual_completed_event_count"] == "0", facts
    # A preflight capability refusal may precede summary creation. Its absence
    # is recorded explicitly; it is not invented as a successful zero-event run.
    print("G4USIM_GDML_REFUSAL=" + json.dumps({"output": str(output), "summary_present": summary.is_file(),
                                             "simulation_products": len(products)}), flush=True)
