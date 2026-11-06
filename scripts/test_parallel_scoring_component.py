"""H3-2 component regression: the dedicated parallel-scoring entry point.

The C++ helper builds the real ScoringManager/DoseScorer/FluenceScorer/
OutputManager and checks R-COMP without running transport: a parallel hit
reaches dose and fluence exactly once with the declared reference
normalisation, never accumulates the event Edep and never writes a hits row,
while a mass-world ScoreHit still does both.
"""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
EXE = Path(os.environ.get("G4USIM_EXE", ROOT / "build_vs2026/Release/G4UniversalSim.exe"))

EXPECTED_CHECKS = 21


def main() -> None:
    assert EXE.is_file(), EXE
    helper = EXE.with_name("parallelScoringCheck" + EXE.suffix)
    assert helper.is_file(), f"build the BUILD_TESTING parallelScoringCheck target: {helper}"
    with tempfile.TemporaryDirectory(prefix="g4usim_parallel_component_") as temp:
        work = Path(temp)
        result = subprocess.run([str(helper), str(work)], capture_output=True, text=True, timeout=120)
        assert result.returncode == 0, result.stdout + result.stderr
        checks = result.stdout.count("ok: ")
        assert checks == EXPECTED_CHECKS, f"component ran {checks} checks, expected {EXPECTED_CHECKS}"
        assert "PASS: H3-2 component checks" in result.stdout, result.stdout
        # The helper writes the real scorer CSVs; keep the evidence in the test log
        # instead of asserting on their private layout twice.
        for name in ("dose_volume_summary_t0.csv", "fluence_volume_summary_t0.csv"):
            path = work / "parallel_entry" / name
            assert path.is_file(), path
        assert not list((work / "parallel_entry").glob("hits_*.csv"))
    print(f"parallel_scoring_component: OK ({EXPECTED_CHECKS} checks)")


if __name__ == "__main__":
    main()
