"""R2-02/R2-03 static generation regression; no backend, Qt or formal runner.

Use --out with a fresh evidence directory. All CLI inputs, logs and outputs remain
there. This checks serialization contracts only, not Geant4 consumption/physics.
"""
from __future__ import annotations

import argparse
import configparser
from dataclasses import asdict
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
SOURCES = ["scenarios/shielding_coating/scenario_model.py", "scenarios/semiconductor/make_device.py"]
sys.path.insert(0, str(ROOT / "scenarios/shielding_coating"))
from scenario_model import ShieldingSpec, length_mm  # noqa: E402


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def fingerprints():
    return {p: digest(ROOT / p) for p in [*SOURCES, "scripts/test_ar1_generators.py"]}


def require(condition, detail):
    # Remains active under python -O.
    if not condition:
        raise AssertionError(detail)


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding="utf-8")


def read_ini(path):
    ini = configparser.ConfigParser(interpolation=None)
    ini.read(path, encoding="utf-8")
    return ini


def mm(value):
    number, unit = value.strip().split()
    require(unit == "mm", value)
    return float(number)


def dimensions(value):
    return [mm(part) for part in value.split(",")]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    before = fingerprints()
    records = []
    failures = []

    def case(label, body):
        try:
            details = body()
            records.append({"case": label, "passed": True, **details})
            print(f"PASS {label}")
        except Exception as exc:
            failures.append(label)
            records.append({"case": label, "passed": False, "error": str(exc)})
            print(f"FAIL {label}: {exc}")

    def shield(label, fraction, layer, seed=12345, junction=0.0):
        spec = ShieldingSpec(pore_fraction=float(fraction), pores_layer=layer, seed=seed, junction_density=float(junction))
        target = out / label
        result = spec.generate(target)
        write_json(target / "input.json", asdict(spec))
        require(not spec.problems(), spec.problems())
        count = result["meta"]["pores"]
        geo = read_ini(target / "geometry.ini")
        expected = layer >= 0 and fraction > 1e-10
        require((count > 0) == expected, (label, count))
        require(geo.has_section("volume.Pore") == expected, label)
        require((target / "pores.csv").exists() == expected, label)
        require(("check_overlaps = false" in (target / "main.ini").read_text()) == expected, label)
        require(result["meta"]["pore_fraction_requested"] == fraction, label)
        realised = 0.0
        if expected:
            require(count == 90, count)
            require(len((target / "pores.csv").read_text().splitlines()[2:]) == count, label)
            parent = geo["volume.Pore"]["parent"]
            thickness = dimensions(geo[f"volume.{parent}"]["size"])[2]
            realised = count * (4 / 3 * math.pi * length_mm(spec.pore_radius) ** 3) / (length_mm(spec.size) ** 2 * thickness)
        require(result["meta"]["pore_fraction_realised"] == realised, label)
        # Rendering twice must preserve every byte, for zero and disabled too.
        rendered = spec.render(target)
        require(rendered == spec.render(target), label)
        require(all((target / name).read_text(encoding="utf-8") == text for name, text in rendered.items()), label)
        cli_target = out / f"{label}_cli"
        cmd = [sys.executable, "-B", str(ROOT / "scenarios/shielding_coating/make_scenario.py"),
               "--out", str(cli_target), "--pore-fraction", str(fraction), "--pores-layer", str(layer),
               "--seed", str(seed), "--junction-density", str(junction)]
        proc = subprocess.run(cmd, capture_output=True, text=True, env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
        require(proc.returncode == 0, proc.stderr)
        # Save receipts outside the generated pack so its file set stays comparable.
        write_json(out / f"{label}_cli_input.json", cmd)
        (out / f"{label}_cli.log").write_text(proc.stdout + proc.stderr, encoding="utf-8")
        require({p.name for p in cli_target.iterdir()} == set(rendered), label)
        require(all((cli_target / name).read_bytes() == (target / name).read_bytes() for name in rendered), label)
        return {"pores": count, "pore_volume": expected, "pore_fraction_realised": realised}

    for label, fraction, layer, seed, junction in [
        ("zero", 0, 0, 12345, 0), ("tiny", 1e-10, 0, 12345, 0),
        ("positive", 1e-4, 0, 12345, 0), ("disabled", .01, -1, 12345, 0),
        ("positive_seed", 1e-4, 0, 7, 0), ("junction_zero", 0, 2, 12345, .5),
    ]:
        case(label, lambda l=label, f=fraction, p=layer, s=seed, j=junction: shield(l, f, p, s, j))

    def pore_controls():
        require((out/"positive/pores.csv").read_bytes() != (out/"positive_seed/pores.csv").read_bytes(), "seed must change positions")
        for fraction in [-1e-10, 1.0]:
            spec = ShieldingSpec(pores_layer=0, pore_fraction=fraction)
            require(bool(spec.problems()), fraction)
            try:
                spec.render(out / "invalid_pore")
            except ValueError:
                continue
            raise AssertionError(f"accepted invalid fraction {fraction}")
        return {"invalid_fractions_rejected": [-1e-10, 1.0], "different_seed_changes_table": True}
    case("pore_controls", pore_controls)

    def device(label, substrate, slices):
        target = out / label
        options = ["--substrate", substrate]
        if slices is not None:
            options += ["--slices", str(slices)]
        if substrate != "300um":
            options += ["--die", "5.123456789123mm", "--oxide", "123.456789nm", "--active", "10.123456789um"]
        cmd = [sys.executable, "-B", str(ROOT / SOURCES[1]), "--out", str(target), *options]
        proc = subprocess.run(cmd, capture_output=True, text=True, env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
        target.mkdir(exist_ok=True)
        write_json(target / "input.json", cmd)
        (target / "cli.log").write_text(proc.stdout + proc.stderr, encoding="utf-8")
        if slices is not None and slices < 1:
            require(proc.returncode != 0 and "--slices must be >= 1" in proc.stderr, proc.stderr)
            require(not (target / "main.ini").exists(), label)
            return {"exit_code": proc.returncode, "expected_rejection": True}
        require(proc.returncode == 0, proc.stderr)
        ini = read_ini(target / "geometry.ini")
        mother = dimensions(ini["volume.Substrate"]["size"])
        child = dimensions(ini["volume.Slice"]["size"])
        width = mm(ini["volume.Slice"]["replica_width"])
        count = int(ini["volume.Slice"]["replica_count"])
        expected = length_mm(substrate)
        require(count == (10 if slices is None else slices), count)
        require(mother[2] == expected and width == expected / count, (mother, width, expected))
        require(child == [mother[0], mother[1], width], child)
        error = abs(count * width - mother[2])
        tolerance = 1e-9 * max(1, abs(count * width), abs(mother[2]))
        require(error <= tolerance, (label, error, tolerance))
        meta = json.loads((target / "scenario.json").read_text())
        require(all(item["thickness_mm"] == width for item in meta["slices"]), label)
        # Cross-check all computed layer lengths and positions against unrounded metadata.
        z = sum(item["thickness_mm"] for item in meta["lid"]) + 1.0
        for index, item in enumerate(meta["beol"]):
            section = ini[f"volume.Beol{index}_{item['material'].replace('G4_', '')}"]
            require(dimensions(section["position"])[2] == z + item["thickness_mm"] / 2, section["position"])
            require(dimensions(section["size"])[2] == item["thickness_mm"], section["size"])
            z += item["thickness_mm"]
        for item in meta["layers"]:
            section = ini[f"volume.{item['name']}"]
            require(dimensions(section["position"])[2] == z + item["thickness_mm"] / 2, section["position"])
            require(dimensions(section["size"])[2] == item["thickness_mm"], section["size"])
            z += item["thickness_mm"]
        require(dimensions(ini["volume.Substrate"]["position"])[2] == z + expected / 2, label)
        die = length_mm("5mm" if substrate == "300um" else "5.123456789123mm")
        require(mother[:2] == [die, die], mother)
        require(mm(read_ini(target / "main.ini")["source"]["halfx"]) == die / 2, label)
        return {"exit_code": proc.returncode, "count": count, "mother_mm": mother[2], "width_mm": width,
                "partition_error_mm": error, "original_tolerance_mm": tolerance}

    for substrate, prefix in [("300um", "slices"), ("301.23456789123um", "irregular")]:
        for count in [1, 5, 7, 11, None]:
            label = f"{prefix}_{count if count is not None else 'default'}"
            case(label, lambda l=label, t=substrate, n=count: device(l, t, n))
    for count in [0, -1]:
        case(f"invalid_slices_{count}", lambda n=count: device(f"invalid_slices_{n}", "300um", n))
    after = fingerprints()
    require(before == after, "source changed during static generation")
    write_json(out / "manifest.json", {str(p.relative_to(out)): digest(p) for p in out.rglob("*") if p.is_file()})
    write_json(out / "results.json", {"scope": "static generation only; native initialization pending", "source_before": before,
                                      "source_after": after, "cases": records, "passed": len(records)-len(failures), "failed": failures})
    print(f"{len(records)-len(failures)}/{len(records)} static cases passed; native initialization pending")
    return bool(failures)


if __name__ == "__main__":
    raise SystemExit(main())
