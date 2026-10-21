"""M1-0 executable metadata and conservative GUI consumption regression."""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "gui"))
from g4usim_gui.core.backend_capabilities import BackendCapabilities, query_backend_capabilities


def main() -> int:
    exe = Path(os.environ.get("G4USIM_EXE", ROOT / "build_vs2026/Release/G4UniversalSim.exe")).resolve()
    with tempfile.TemporaryDirectory() as tmp:
        # Introspection must work without runtime config or creating output files.
        result = subprocess.run([str(exe), "--capabilities"], cwd=tmp, capture_output=True, text=True, timeout=30)
        assert result.returncode == 0, result.stderr
        capabilities = BackendCapabilities.from_json(result.stdout)
        assert not list(Path(tmp).iterdir())
        repeated = subprocess.run([str(exe), "--capabilities"], cwd=tmp, capture_output=True, text=True, timeout=30)
        assert result.stdout == repeated.stdout
    assert capabilities.runtime_ids("solids") == {"box", "tubs", "sphere", "orb", "cone", "trd", "trap"}
    assert capabilities.runtime_ids("placements") == {"normal"}
    assert "gdml" not in capabilities.runtime_ids("templates")
    assert "temperature" not in capabilities.runtime_ids("materials")
    assert "physics_region_cuts" not in capabilities.runtime_ids("physics")
    assert capabilities.runtime_ids("scorers") == {"hits", "edep", "dose", "fluence", "let"}
    assert "let" in capabilities.runtime_ids("scorers")
    assert re.fullmatch(r"[0-9a-f]{64}", capabilities.data["source_fingerprint"])
    assert capabilities.data["build_configuration"] in {"Debug", "Release", "RelWithDebInfo", "MinSizeRel"}
    assert capabilities.data["compiler_id"]
    assert capabilities.data["compiler_version"]
    assert isinstance(capabilities.data["geant4_version_number"], int)
    assert capabilities.data["outputs"]["schema_version"] == 3
    assert capabilities.data["outputs"]["subsequent_run_suffix"] == "_rR"
    assert capabilities.data["outputs"]["csv_units_in_header"] is True
    assert capabilities.editable_shapes({"box", "tubs", "gdml", "made_up"}) == {"box", "tubs"}
    assert query_backend_capabilities(exe).data == capabilities.data
    for mutate in (
        lambda data: data.update(version=999),
        lambda data: data["solids"].append(data["solids"][0]),
        lambda data: data["placements"][0].update(runtime="true"),
    ):
        data = json.loads(result.stdout)
        mutate(data)
        try:
            BackendCapabilities.from_json(json.dumps(data))
        except ValueError:
            pass
        else:
            raise AssertionError("Malformed capabilities accepted")
    print("test_backend_capabilities: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
