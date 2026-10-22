"""M0-3B1 regression tests for main-INI field consumption warnings."""

from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EXE = ROOT / "build_vs2026" / "Release" / "G4UniversalSim.exe"


def run(executable: Path, config: Path, expected: int) -> str:
    result = subprocess.run(
        [str(executable), "--config", str(config)], cwd=ROOT,
        text=True, capture_output=True, timeout=120,
    )
    output = result.stdout + result.stderr
    if result.returncode != expected:
        raise AssertionError(f"Unexpected exit code: expected {expected}, got {result.returncode}\n{output}")
    return output


def make_config(output: Path, geometry: Path, materials: Path, extra: str = "") -> str:
    return f"""[run]
name = m03b1
threads = 1
seed = 12345
interactive = false
verbose = 0
check_overlaps = false
dry_run = true

[output]
dir = {output}

[materials]
file = {materials}

[geometry]
template = simple_box
config = {geometry}
check_overlaps = false
default_world_material = G4_AIR

[physics]
reference = FTFP_BERT_EMZ
default_cut = 1 mm
biasing = false
verbose = 0

[source]
preset = proton_beam
particle = proton
energy = 10 MeV
position_type = point
position = 0,0,-1 mm
direction = 0,0,1

[scoring]
enabled = true
hits = false
event_edep = false
edep = true
let = false
dose = false
fluence = false
auto_create_default_scorers = true
verbose = 0
{extra}
"""


def write_config(temp: Path, name: str, text: str) -> Path:
    path = temp / f"{name}.ini"
    path.write_text(text, encoding="utf-8")
    return path


def main() -> int:
    executable = Path(os.environ.get("G4USIM_EXE", str(DEFAULT_EXE)))
    if not executable.is_file():
        raise SystemExit(f"Executable not found: {executable}")

    materials = ROOT / "config" / "materials" / "material.ini"
    geometry = ROOT / "config" / "geometry" / "simple_box.ini"
    with tempfile.TemporaryDirectory(prefix="g4usim-m03b1-") as temporary:
        temp = Path(temporary)

        valid = write_config(temp, "valid", make_config(temp / "valid-output", geometry, materials))
        text = run(executable, valid, 0)
        if "[ConfigWarning]" in text:
            raise AssertionError(f"Valid main config produced a warning:\n{text}")
        summary = (temp / "valid-output" / "run_summary.txt").read_text(encoding="utf-8")
        if "config_warning_count = 0" not in summary:
            raise AssertionError(f"Valid summary has unexpected warning count:\n{summary}")

        typo = write_config(temp, "typo", make_config(temp / "typo-output", geometry, materials, "[run]\nthreds = 2\n"))
        text = run(executable, typo, 0)
        if text.count("[ConfigWarning] unconsumed field") != 1 or "threds" not in text:
            raise AssertionError(f"run/threds warning was not stable and singular:\n{text}")

        output_typo = write_config(temp, "output-typo", make_config(temp / "output-typo-output", geometry, materials, "[output]\ndiretory = x\n"))
        text = run(executable, output_typo, 0)
        if "diretory" not in text or "did you mean 'dir'" not in text:
            raise AssertionError(f"output/diretory warning lacks suggestion:\n{text}")

        unknown = write_config(temp, "unknown-section", make_config(temp / "unknown-output", geometry, materials, "[mystery]\nvalue = 1\n"))
        text = run(executable, unknown, 0)
        if "unknown section" not in text or "mystery" not in text:
            raise AssertionError(f"Unknown section was not reported:\n{text}")

        global_typo = write_config(temp, "global-typo", "threds = 99\n" + make_config(temp / "global-output", geometry, materials))
        text = run(executable, global_typo, 0)
        if "[global]/threds" not in text or "config_warning_count = 1" not in (temp / "global-output" / "run_summary.txt").read_text(encoding="utf-8"):
            raise AssertionError(f"Implicit global field was not reported:\n{text}")

        cuts_typo = write_config(temp, "cuts-typo", make_config(temp / "cuts-typo-output", geometry, materials, "[physics.cuts_typo]\ngamma = 1 mm\n"))
        text = run(executable, cuts_typo, 0)
        if "unknown section" not in text or "physics.cuts_typo" not in text:
            raise AssertionError(f"Malformed dynamic section was accepted silently:\n{text}")

        dynamic = write_config(temp, "dynamic", make_config(temp / "dynamic-output", geometry, materials, "[physics.cuts]\ngamma = 1 mm\n"))
        text = run(executable, dynamic, 0)
        if "[ConfigWarning]" in text:
            raise AssertionError(f"Supported dynamic section produced a warning:\n{text}")

        legacy = write_config(temp, "legacy", make_config(temp / "legacy-output", geometry, materials, "[general]\nrandomSeed = 456\nverbose = 0\n"))
        text = run(executable, legacy, 0)
        if "[ConfigWarning]" in text:
            raise AssertionError(f"Legacy compatibility fields produced a warning:\n{text}")

        warning_summary = (temp / "typo-output" / "run_summary.txt").read_text(encoding="utf-8")
        if "config_warning_count = 1" not in warning_summary or "threds" not in warning_summary:
            raise AssertionError(f"Summary did not preserve warning count/details:\n{warning_summary}")

        unsupported = write_config(temp, "unsupported", make_config(temp / "unsupported-output", geometry, materials, "[physics.region.NoSuchRegion]\ne- = 1 mm\n"))
        text = run(executable, unsupported, 1)
        # Roadmap A6: region physics is supported; an unknown region must still fail, not warn.
        if "region 'NoSuchRegion' does not exist in the geometry" not in text:
            raise AssertionError(f"Unknown physics region was downgraded to a warning:\n{text}")

    print("M0-3B1 unconsumed main-config field tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
