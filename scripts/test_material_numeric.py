"""Material numeric fail-fast regression; --baseline records historical behavior."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile

from test_material_config_schema import main_config

ROOT = Path(__file__).resolve().parents[1]
BASE = "[NIST]\nmaterials = G4_AIR,G4_Si\n"
CASES = {
    "element_z_nan": "[element.Bad]\nsymbol = B\nz = nan\na = 10 g/mol\n",
    "element_a_nan": "[element.Bad]\nsymbol = B\nz = 1\na = nan g/mol\n",
    "element_a_inf": "[element.Bad]\nsymbol = B\nz = 1\na = inf g/mol\n",
    "element_a_overflow": "[element.Bad]\nsymbol = B\nz = 1\na = 1e999 g/mol\n",
    "element_z_finite_huge": "[element.Bad]\nsymbol = B\nz = 1e20\na = 1e21 g/mol\n",
    "element_z_intmax": "[element.Bad]\nsymbol = B\nz = 2147483647\na = 2147483647 g/mol\n",
    "element_z105": "[element.Bad]\nsymbol = B\nz = 105\na = 260 g/mol\n",
    "element_z_rounds_zero": "[element.Bad]\nsymbol = B\nz = 0.1\na = 1 g/mol\n",
    "element_a_below_z": "[element.Bad]\nsymbol = B\nz = 2\na = 1 g/mol\n",
    "element_mass_unit_overflow": "[element.Bad]\nsymbol = B\nz = 1\na = 1e308 kg/mol\n",
    "isotope_z_overflow": "[isotope.Bad]\nsymbol = B\nz = 4294967297\nn = 2\na = 2 g/mol\n",
    "isotope_n_overflow": "[isotope.Bad]\nsymbol = B\nz = 1\nn = 999999999999999999999\na = 2 g/mol\n",
    "abundance_nan": "[isotope.X]\nsymbol = X\nz = 1\nn = 1\na = 1 g/mol\n"
                     "[element.Bad]\nsymbol = B\nisotopes = X:nan\n",
    "mass_nan": "[material.Bad]\ndensity = 1 g/cm3\nmode = mass_fraction\ncomponents = Si:nan\n",
    "mass_inf": "[material.Bad]\ndensity = 1 g/cm3\nmode = mass_fraction\ncomponents = Si:inf\n",
    "atom_overflow": "[material.Bad]\ndensity = 1 g/cm3\nmode = atom_count\ncomponents = Si:4294967297\n",
    "atom_repeated_overflow": "[material.Bad]\ndensity = 1 g/cm3\nmode = atom_count\ncomponents = Si:2147483647,Si:1\n",
    "atom_mass_overflow": "[element.Heavy]\nsymbol = H\nz = 1\na = 1e280 kg/mol\n"
                          "[material.Bad]\ndensity = 1 g/cm3\nmode = atom_count\ncomponents = Heavy:2147483647\n",
    "density_inf": "[material.Bad]\ndensity = inf g/cm3\nmode = mass_fraction\ncomponents = Si:1\n",
    "density_conversion_overflow": "[material.Bad]\ndensity = 1e308 g/cm3\nmode = mass_fraction\ncomponents = Si:1\n",
    "isotope_n_lt_z": "[isotope.Bad]\nsymbol = B\nz = 2\nn = 1\na = 2 g/mol\n",
    "isotope_intmax_element": "[isotope.X]\nsymbol = X\nz = 2147483647\nn = 2147483647\na = 2147483647 g/mol\n"
                              "[element.Bad]\nsymbol = B\nisotopes = X:1\n",
    "element_mixed_isotope_z": "[isotope.X]\nsymbol = X\nz = 1\nn = 2\na = 2 g/mol\n"
                               "[isotope.Y]\nsymbol = Y\nz = 2\nn = 4\na = 4 g/mol\n"
                               "[element.Bad]\nsymbol = B\nisotopes = X:.5,Y:.5\n",
}


def run_cases(exe: Path, work: Path, baseline: bool) -> None:
    receipts = []
    valid_cases = {
        "valid": "[element.Good]\nsymbol = G\nz = 1\na = 1 g/mol\n",
        "valid_shell104": "[element.Good]\nsymbol = G\nz = 104\na = 260 g/mol\n",
        "valid_isotope_intmax": "[isotope.Good]\nsymbol = G\nz = 2147483647\nn = 2147483647\na = 2147483647 g/mol\n",
        "valid_isotope_shell104": "[isotope.X]\nsymbol = X\nz = 104\nn = 260\na = 260 g/mol\n[element.Good]\nsymbol = G\nisotopes = X:1\n",
    }
    for name, body in {**valid_cases, **CASES}.items():
        material = work / f"{name}_material.ini"
        material.write_text(BASE + body, encoding="utf-8")
        config = work / f"{name}.ini"
        config.write_text(main_config(material, work / f"{name}_out"), encoding="utf-8")
        result = subprocess.run([str(exe), "--config", str(config), "--dry-run"], cwd=ROOT,
                                capture_output=True, text=True, errors="replace", timeout=45)
        log = result.stdout + result.stderr
        (work / f"{name}.log").write_text(log, encoding="utf-8")
        receipts.append({"case": name, "exit_code": result.returncode,
                         "accepted": result.returncode == 0})
        if name in valid_cases:
            assert result.returncode == 0, log[-3000:]
        elif not baseline:
            assert result.returncode == 1, f"Invalid material must fail normally, not abort: {name}, exit={result.returncode}"
            assert any(word in log.lower() for word in ("finite", "range", "overflow", "integer")), log[-3000:]
    (work / "receipts.json").write_text(json.dumps(receipts, indent=2), encoding="utf-8")
    print(json.dumps(receipts))
    if not baseline:
        material = work / "macro_material.ini"
        material.write_text(BASE, encoding="utf-8")
        config = work / "macro.ini"
        config.write_text(main_config(material, work / "macro_out").replace("dry_run = true", "dry_run = false"), encoding="utf-8")
        for index, command in enumerate((
            "/AIHL/material/addElement name=Bad symbol=B z=1 a=nan g/mol",
            "/AIHL/material/addIsotope name=Bad symbol=B z=4294967297 n=2 a=2 g/mol",
            "/AIHL/material/addIsotope name=Bad symbol=B z=1 n=999999999999999999999 a=2 g/mol",
            "/AIHL/material/addElement name=Bad symbol=B z=105 a=260 g/mol",
            "/AIHL/material/addElement name=Bad symbol=B z=2 a=1 g/mol",
        )):
            macro = work / f"invalid{index}.mac"
            macro.write_text(command + "\n/run/initialize\n/run/beamOn 1\n", encoding="utf-8")
            output = work / f"macro_out_{index}"
            result = subprocess.run([str(exe), "--config", str(config), "--macro", str(macro), "--output", str(output)],
                                    cwd=ROOT, capture_output=True, text=True, errors="replace", timeout=45)
            log = result.stdout + result.stderr
            (work / f"macro{index}.log").write_text(log, encoding="utf-8")
            assert result.returncode == 1, (result.returncode, log[-3000:])
            assert any(marker in log.lower() for marker in ("finite", "range")), log[-3000:]
            summary = (output / "run_summary.txt").read_text(encoding="utf-8")
            assert "status = failed" in summary and "run_count = 0" in summary, summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", action="store_true")
    parser.add_argument("--work", type=Path)
    args = parser.parse_args()
    exe = Path(os.environ.get("G4USIM_EXE", ROOT / "out/build-effective/Release/G4UniversalSim.exe"))
    assert exe.is_file(), exe
    if args.work:
        args.work.mkdir(parents=True, exist_ok=True)
        run_cases(exe, args.work.resolve(), args.baseline)
    else:
        with tempfile.TemporaryDirectory(prefix="g4usim-material-numeric-") as temp:
            run_cases(exe, Path(temp), args.baseline)


if __name__ == "__main__":
    main()
