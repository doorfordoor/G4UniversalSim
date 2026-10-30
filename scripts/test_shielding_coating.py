"""Real Geant4 regression for the shielding / coating scenario pack (roadmap B2).

Generates scenarios with scenarios/shielding_coating/make_scenario.py, runs them and
checks physical or exact properties:
  1. spectrum sources through a vacuum layer: with the mixed source the electron
     share of primaries is F_e / (F_e + F_p) (source intensities = integral fluxes);
     with the proton spectrum the share above 10 MeV equals
     [F(10) - F(400)] / [F(0.1) - F(400)] of the integral-flux file;
  2. 1 MeV electron albedo (FrontPlane, kill): thick W backscatters far more
     primary electrons than thick B4C;
  3. pores: the Geant4 world (exportMesh) contains every generated pore copy inside
     the layer, and the mean energy loss of 20 MeV protons in a B4C layer with
     20 % porosity is 0.80 of the dense layer (energy loss ~ areal density);
  4. junction layers have the requested thickness, material and density;
  5. analyze.py writes TID/DDD per primary and per fluence consistently;
  6. analyze.py never turns missing evidence into a zero result: a statistics file
     that run_metadata.json lists but that is gone, a failed summary, a zero-event
     run and stale phase-space rows are all rejected with exit code 3 and no
     report, while a run that genuinely scored nothing is accepted with an explicit
     evidence label on every quantity.
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT / "scenarios" / "shielding_coating"
EXE = Path(os.environ.get("G4USIM_EXE", ROOT / "build_vs2026/Release/G4UniversalSim.exe"))


def generate(out: Path, *options: str) -> dict:
    subprocess.run([sys.executable, str(PACK / "make_scenario.py"), "--out", str(out), "--threads", "2",
                    "--physics", "FTFP_BERT", *options], check=True, capture_output=True, text=True)
    return json.loads((out / "scenario.json").read_text(encoding="utf-8"))


def run(out: Path, macro: str | None = None) -> str:
    args = [str(EXE), "--config", "main.ini"]
    if macro:
        (out / "extra.mac").write_text(macro, encoding="utf-8")
        args += ["--macro", "extra.mac"]
    result = subprocess.run(args, cwd=out, capture_output=True, text=True, errors="replace", timeout=1800)
    log = result.stdout + result.stderr
    assert result.returncode == 0, log[-3000:]
    assert "G4Exception-START" not in log, log[log.index("G4Exception-START") - 200:][:2000]
    return log


def phase_space(out: Path):
    for path in sorted((out / "output").glob("phase_space_t*.csv")):
        if re.fullmatch(r"phase_space_t\d+\.csv", path.name):
            with path.open(newline="", encoding="utf-8") as handle:
                yield from csv.DictReader(handle)


def integral_flux(name: str) -> list[tuple[float, float]]:
    lines = (PACK / "environment" / name).read_text(encoding="utf-8-sig").splitlines()[1:]
    return [(float(a), float(b)) for a, b in (line.split()[:2] for line in lines if line.strip())]


def check(label, got, expected, tolerance):
    print(f"  {label}: {got:.5g} (expected {expected:.5g} +- {tolerance:.3g})")
    assert abs(got - expected) <= tolerance, (label, got, expected, tolerance)


def mean_exit_energy(out: Path) -> float:
    energies = [float(p["kineticEnergy_MeV"]) for p in phase_space(out) if p["trackID"] == "1"]
    assert len(energies) > 0.99 * json.loads((out / "scenario.json").read_text())["events"]
    return sum(energies) / len(energies)


def main() -> int:
    if not EXE.is_file():
        print(f"backend executable missing: {EXE}")
        return 1
    work = Path(tempfile.mkdtemp(prefix="g4usim_shield_"))
    try:
        print("mixed spectrum source")
        out = work / "mixed"
        events = 4000
        meta = generate(out, "--layers", "G4_Galactic:1um", "--particle", "mixed", "--events", str(events))
        run(out)
        primaries = [p for p in phase_space(out) if p["trackID"] == "1" and float(p["w"]) > 0]
        assert len(primaries) > 0.99 * events, len(primaries)
        electrons = sum(1 for p in primaries if p["particle"] == "e-")
        flux = meta["sampled_integral_flux_cm2_s"]
        share = flux["e-"] / (flux["e-"] + flux["proton"])
        n = len(primaries)
        check("electron share", electrons / n, share, 4 * (share * (1 - share) / n) ** 0.5)
        out = work / "protons"
        generate(out, "--layers", "G4_Galactic:1um", "--particle", "proton", "--events", str(events))
        run(out)
        protons = [float(p["kineticEnergy_MeV"]) for p in phase_space(out) if p["trackID"] == "1"]
        assert len(protons) > 0.99 * events, len(protons)
        table = dict(integral_flux("proton_integral_flux.txt"))
        above = (table[10.0] - table[400.0]) / (table[0.1] - table[400.0])
        fraction = sum(1 for e in protons if e > 10.0) / len(protons)
        check("proton share above 10 MeV", fraction, above, 4 * (above * (1 - above) / len(protons)) ** 0.5 + 0.01)

        print("electron albedo")
        albedo = {}
        # single-material stacks thicker than the 1 MeV electron range; primaries only
        for name, layers in (("W", "G4_W:1mm"), ("B4C", "B4C:5mm")):
            out = work / f"albedo_{name}"
            generate(out, "--layers", layers, "--particle", "e-", "--energy", "1", "--mode", "albedo",
                     "--events", "2000")
            run(out)
            albedo[name] = sum(1 for p in phase_space(out) if p["trackID"] == "1" and float(p["w"]) < 0) / 2000
            print(f"  {name}-faced stack: {albedo[name]:.4f} backscattered electrons per primary")
        assert albedo["W"] > 3 * albedo["B4C"] and albedo["W"] > 0.2, albedo

        print("pores")
        dense, porous = work / "dense", work / "porous"
        common = ("--layers", "B4C:300um", "--size", "2mm", "--source-half", "0.8mm", "--particle", "proton",
                  "--energy", "20", "--em", "option4", "--events", "3000")
        generate(dense, *common)
        meta = generate(porous, *common, "--pores-layer", "0", "--pore-radius", "20um", "--pore-fraction", "0.2")
        run(dense)
        log = run(porous, "/run/initialize\n/AIHL/geometry/exportMesh mesh.json\n/run/beamOn 3000\n")
        mesh = json.loads((porous / "mesh.json").read_text(encoding="utf-8"))
        pores = [v for v in mesh["volumes"] if v["name"] == "Pore_PV"]
        print(f"  {len(pores)} pore copies in the Geant4 world (generated {meta['pores']})")
        assert len(pores) == meta["pores"] > 5000, (len(pores), meta["pores"])
        assert all(v["material"] == "G4_Galactic" and v["path"].startswith("/world_PV#0/Layer0_B4C_PV#0/")
                   for v in pores)
        loss_dense = 20.0 - mean_exit_energy(dense)
        loss_porous = 20.0 - mean_exit_energy(porous)
        pore_volume = sum(v["cubic_volume_mm3"] for v in pores)
        material_fraction = 1 - pore_volume / (2.0 * 2.0 * 0.3)
        check("porous / dense energy loss", loss_porous / loss_dense, material_fraction, 0.03)

        print("junction layers")
        out = work / "junction"
        generate(out, "--layers", "B4C:300um,G4_W:100um,G4_Al:300um", "--junction-density", "0.8",
                 "--particle", "proton", "--energy", "50", "--events", "10")
        run(out, "/run/initialize\n/AIHL/geometry/exportMesh mesh.json\n")
        volumes = {v["name"]: v for v in json.loads((out / "mesh.json").read_text(encoding="utf-8"))["volumes"]}
        for name, material, thickness in (("Junction1_W_PV", "W_J", 0.010), ("Layer1_W_PV", "G4_W", 0.090),
                                          ("Junction2_Al_PV", "Al_J", 0.030), ("Layer2_Al_PV", "G4_Al", 0.270)):
            v = volumes[name]
            assert v["material"] == material, v
            check(f"{name} thickness [mm]", v["cubic_volume_mm3"] / 100.0, thickness, 1e-9)
        materials = (out / "materials.ini").read_text(encoding="utf-8")
        assert "[material.W_J]\nmode = mass_fraction\ndensity = 15.44 g/cm3\ncomponents = G4_W:1.0" in materials

        print("analysis")
        out = work / "analysis"
        niel = work / "flat.csv"
        niel.write_text("energy_MeV,niel_MeV_cm2_g\n0.001,1e-3\n1e4,1e-3\n", encoding="utf-8")
        meta = generate(out, "--particle", "proton", "--energy", "100", "--events", "200", "--niel", f"proton={niel}")
        run(out)
        result = subprocess.run([sys.executable, str(PACK / "analyze.py"), str(out / "output")],
                                capture_output=True, text=True, check=True)
        print("  " + result.stdout.strip().replace("\n", "\n  "))
        report = json.loads((out / "output" / "shielding_report.json").read_text(encoding="utf-8"))
        for key in ("tid", "ddd"):
            q = report[key]
            check(f"{key} per primary x events / total", q["per_primary"] * 200 / q["total"], 1.0, 1e-12)
            check(f"{key} per fluence / per primary", q[f"per_fluence_{q['unit']}_cm2"] / q["per_primary"],
                  meta["source_area_cm2"], 1e-12)
        assert report["primary_transmission"] > 0.95, report["primary_transmission"]
        assert (out / "output" / "spectra.csv").stat().st_size > 0
        assert report["evidence"]["scorer_statistics"] == "scorer_statistics.csv", report["evidence"]
        assert report["tid"]["evidence"] == "scorer_statistics.csv", report["tid"]["evidence"]

        print("analysis evidence controls")

        def copy_case(name):
            target = work / name
            shutil.copytree(out, target)
            for stale in ("shielding_report.json", "spectra.csv"):
                (target / "output" / stale).unlink(missing_ok=True)
            return target

        def analyze(case):
            return subprocess.run([sys.executable, str(PACK / "analyze.py"), str(case / "output")],
                                  capture_output=True, text=True, errors="replace")

        def expect_evidence_error(case, fragment):
            result = analyze(case)
            assert result.returncode == 3, (case.name, result.returncode, result.stderr[-800:])
            assert fragment in result.stderr, (case.name, fragment, result.stderr[-800:])
            assert not (case / "output" / "shielding_report.json").exists(), \
                f"{case.name}: a report was written for missing evidence"
            print(f"  {case.name}: rejected")

        def metadata_of(case):
            return json.loads((case / "output" / "run_metadata.json").read_text(encoding="utf-8"))

        def reseal_synthetic_summary(case, metadata):
            # This is a deliberately modified temporary COPY for a semantic test,
            # never the backend's original evidence and never a validation bypass.
            if "provenance" not in metadata:
                return
            assert case != out and case.parent == work
            path = case / "output" / "run_summary.txt"
            data = path.read_bytes()
            records = [entry for entry in metadata["generated_files"] if entry["path"].endswith("run_summary.txt")]
            assert len(records) == 1
            records[0].update(sha256=hashlib.sha256(data).hexdigest(), size_bytes=len(data), integrity_status="hashed")

        def write_metadata(case, metadata):
            reseal_synthetic_summary(case, metadata)
            (case / "output" / "run_metadata.json").write_text(
                json.dumps(metadata, indent=2), encoding="utf-8")

        def edit_summary(case, edits):
            path = case / "output" / "run_summary.txt"
            lines = path.read_text(encoding="utf-8").splitlines()
            for index, line in enumerate(lines):
                for old, new in edits.items():
                    if line.startswith(old + " = "):
                        lines[index] = f"{old} = {new}"
            newline = chr(10)
            path.write_text(newline.join(lines) + newline, encoding="utf-8")

        # 1. the statistics file that the run listed is gone: missing evidence, not zero
        case = copy_case("evidence_missing_statistics")
        assert "scorer_statistics.csv" in (case / "output" / "run_metadata.json").read_text(encoding="utf-8")
        (case / "output" / "scorer_statistics.csv").unlink()
        expect_evidence_error(case, "was listed in run_metadata.json generated_files but is missing")

        # 2. a failed run summary
        case = copy_case("evidence_failed_run")
        edit_summary(case, {"status": "failed"})
        write_metadata(case, metadata_of(case))
        expect_evidence_error(case, "only a completed run can be analysed")

        # 3. a run that completed no events
        case = copy_case("evidence_zero_events")
        edit_summary(case, {"run_0_completed_events": 0})
        metadata = metadata_of(case)
        metadata["runs"][0]["completed_events"] = 0
        metadata["runs"][0]["planned_events"] = 0
        write_metadata(case, metadata)
        expect_evidence_error(case, "no rate can be derived from an empty run")

        # 4. stale phase-space rows from a longer earlier run
        case = copy_case("evidence_stale_phase_space")
        edit_summary(case, {"run_0_completed_events": 10})
        metadata = metadata_of(case)
        metadata["runs"][0]["completed_events"] = 10
        metadata["runs"][0]["planned_events"] = 10
        write_metadata(case, metadata)
        expect_evidence_error(case, "the files look stale")

        # 5. a run that genuinely wrote no statistics: zero is accepted, but labelled
        case = copy_case("evidence_zero_deposition")
        (case / "output" / "scorer_statistics.csv").unlink()
        metadata = metadata_of(case)
        metadata["generated_files"] = [entry for entry in metadata["generated_files"]
                                       if not entry["path"].endswith("scorer_statistics.csv")]
        write_metadata(case, metadata)
        result = analyze(case)
        assert result.returncode == 0, result.stderr[-800:]
        zero_report = json.loads((case / "output" / "shielding_report.json").read_text(encoding="utf-8"))
        assert zero_report["tid"]["total"] == 0.0, zero_report["tid"]
        assert zero_report["tid"]["evidence"] == "no_statistics_file_zero_deposition", zero_report["tid"]
        assert zero_report["evidence"]["scorer_statistics"] == "no_statistics_file_zero_deposition"
        print("  evidence_zero_deposition: accepted with an explicit evidence label")
    finally:
        shutil.rmtree(work, ignore_errors=True)
    print("test_shielding_coating: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
