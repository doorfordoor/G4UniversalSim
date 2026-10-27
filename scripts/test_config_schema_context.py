"""E2 contextual contracts. Scalar checks do not replace real Configure().

The cases assert acceptance independently of the schema, in valid surrounding
configurations. Optional --baseline compares the same files with the pre-migration
binary, including consumed-field diagnostics and inspected configuration values.
Transport/physics contracts remain in the GPS/A5/A6/scorer and E1 integration tests.
"""
from __future__ import annotations

import argparse
import copy
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "gui"))
from g4usim_gui.core.config_schema import check_value, quantity, section_spec, spec  # noqa: E402


def check_api() -> None:
    assert spec("source.Alpha", "intensity").type == "number"
    assert spec("source.a.b", "intensity") is None
    assert spec("physics.region.Sensor", "max_time").type == "time"
    assert spec("scoring.mesh.m.d", "energy_min").type == "energy"
    assert spec("material.Water", "mode", "materials_ini").type == "enum"
    assert spec("volume.part.boolean.1", "parent", "geometry_hierarchical_ini") is None
    assert section_spec("source.a")["rules"]
    assert check_value("volume.a", "file_unit", "mm", file="geometry_hierarchical_ini") is None
    assert check_value("volume.a", "file_unit", "MM", file="geometry_hierarchical_ini") is not None
    assert quantity("1e308 GeV", "energy") is None
    assert quantity("0x1p+1024", "number") is None
    assert quantity("1*", "number") is None
    assert quantity("1 year", "time") == 365 * 86400e9
    assert check_value("source", "radius", "0 mm") is not None
    assert check_value("source", "radius", "1 mm") is None
    try:
        check_value("source", "direction", "not a vector")
    except ValueError:
        pass
    else:
        raise AssertionError("structured values must not silently pass scalar validation")


def run_case(case: dict, exe: Path, baseline: Path | None) -> list[str]:
    errors = []
    with tempfile.TemporaryDirectory(prefix="g4usim-e2-") as temp:
        work = Path(temp)

        def expand(value):
            return value.replace("@WORK@", work.as_posix()).replace("@ROOT@", ROOT.as_posix())

        for name, source in case.get("copies", {}).items():
            shutil.copyfile(ROOT / source, work / name)
        for name, body in case.get("files", {}).items():
            (work / name).write_text(expand(body), encoding="utf-8")
        body = "\n".join("[" + section + "]\n" + "\n".join(key + "=" + expand(value) for key, value in keys.items())
                         for section, keys in case["sections"].items())
        main = work / "main.ini"
        main.write_text(body, encoding="utf-8")

        def inspect(binary):
            result = subprocess.run([str(binary), "--config", str(main), "--inspect-run"], cwd=ROOT,
                                    capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
            warnings = [line for line in result.stderr.splitlines()
                        if "[ConfigWarning]" in line or "[GeometryConfigWarning]" in line]
            plan = json.loads(result.stdout).get("initial_configuration", []) if result.returncode == 0 else []
            return result, warnings, plan

        result, warnings, plan = inspect(exe)
        accepted = result.returncode == 0
        if case.get("accept") is not None and accepted != case["accept"]:
            errors.append(f"{case['name']}: expected accept={case['accept']}, got {result.returncode}: {result.stderr[-800:]}")
        for expected in case.get("warnings", []):
            if expected not in result.stderr:
                errors.append(f"{case['name']}: missing diagnostic {expected}")
        if case.get("scalar"):
            section, key, value, *file = case["scalar"]
            if (check_value(section, key, value, file=file[0] if file else "main_ini") is None) != accepted:
                errors.append(f"{case['name']}: schema scalar verdict differs from backend")
        if case.get("scalar_necessary") and accepted:
            section, key, value = case["scalar_necessary"]
            if check_value(section, key, value, base_dir=ROOT) is not None:
                errors.append(f"{case['name']}: schema rejects a scalar accepted in this valid backend context")
        if baseline:
            old, old_warnings, old_plan = inspect(baseline)
            if (old.returncode == 0) != accepted or old_warnings != warnings or old_plan != plan:
                errors.append(f"{case['name']}: changed acceptance/warnings/inspected configuration from baseline\n"
                              f"old warnings={old_warnings}\nnew warnings={warnings}")
    return errors


def scalar_probes(cases: list[dict]) -> list[dict]:
    """Mutate consumed scalars in valid contexts, without inventing independent defaults.

    Both binaries must agree. A scalar validator may accept a value rejected by a
    contextual constraint, but must not reject a value the backend accepts here.
    """
    seen = set()
    result = []
    for case in cases:
        if not case["accept"]:
            continue
        for section, fields in case["sections"].items():
            for key in fields:
                field = spec(section, key)
                if field is None or field.type == "structured" or (section, key) in seen:
                    continue
                seen.add((section, key))
                values = {
                    "bool": ["true", "false", "maybe", ""],
                    "int": ["0", "-1", "2147483648", ""],
                    "energy": ["1 eV", "0", "-1 MeV", "nan", "1e308 GeV", ""],
                    "length": ["1 um", "0", "-1 mm", "nan", "1e308 m", ""],
                    "time": ["1 year", "0", "-1 ns", "nan", ""],
                    "angle": ["1 deg", "0", "-1 rad", "nan", ""],
                    "number": ["1", "0", "-1", "nan", ""],
                    "string": ["", "abc"],
                    "existing_file": ["", "@WORK@/missing.ini"],
                    "enum": [*field.data.get("allowed", []), "unknown", ""],
                }[field.type]
                for value in values:
                    probe = copy.deepcopy(case)
                    probe.update(name=f"probe-{section}-{key}-{value!r}", accept=None, scalar=None, warnings=[],
                                 scalar_necessary=[section, key, value])
                    probe["sections"][section][key] = value
                    result.append(probe)
    return result


def check_contexts(exe: Path, baseline: Path | None = None, probes: bool = False) -> list[str]:
    check_api()
    cases = json.loads((ROOT / "scripts/fixtures/config_schema_context.json").read_text(encoding="utf-8"))
    if probes:
        if baseline is None:
            raise ValueError("scalar migration probes require --baseline")
        cases += scalar_probes(cases)
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda case: run_case(case, exe, baseline), cases))
    errors = [error for group in results for error in group]
    print(f"contextual schema: {len(cases) - sum(bool(r) for r in results)}/{len(cases)} cases pass"
          + (" (also compared with pre-migration backend)" if baseline else ""))
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--probe-scalars", action="store_true")
    args = parser.parse_args()
    exe = Path(os.environ.get("G4USIM_EXE", ROOT / "build_vs2026/Release/G4UniversalSim.exe"))
    if not exe.is_file():
        raise SystemExit(f"backend required: {exe}")
    errors = check_contexts(exe.resolve(), args.baseline.resolve() if args.baseline else None, args.probe_scalars)
    for error in errors:
        print(error)
    return int(bool(errors))


if __name__ == "__main__":
    raise SystemExit(main())
