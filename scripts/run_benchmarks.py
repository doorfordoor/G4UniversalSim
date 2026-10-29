"""Physics benchmarks against reference data (roadmap Phase B).

Runs the packs in scenarios/benchmarks with the real backend and compares the
results with NIST reference data:

  csda_range         mean path length of protons (PSTAR) and electrons (ESTAR) that
                     stop in water, EM-only physics (G4EmStandardPhysics_option4)
  bragg_peak         distal 80 % depth (R80) of a 150 MeV proton pencil beam in water
                     (QGSP_BIC_EMZ, native energyDeposit scoring mesh, 1 mm bins)
                     against PSTAR CSDA range x detour factor
  gamma_attenuation  narrow-beam transmission of photons, mu/rho = -ln(T) / (rho x),
                     against NIST XCOM (FTFP_BERT_EMZ)
  shielding_range    CSDA ranges of protons and electrons in Al and Si (PSTAR/ESTAR) and
                     the mean energy of protons behind Al/Si slabs against the PSTAR
                     projected-range inversion (EM-only, G4EmStandardPhysics_option4)
  device_dose        dose per unit proton fluence in a thin Si slab in delta-electron
                     equilibrium against the PSTAR Si electronic stopping power, and the
                     displacement damage dose per unit fluence against the SR-NIEL tables
  detector_response  Compton edges and pair-production escape lines of gamma pulse-height
                     spectra (kinematics) and the most probable deposit in 300 um Si
                     against the PDG Landau-Vavilov-Bichsel formula

A case passes when |simulated - reference| <= tolerance * reference + 3 sigma
(sigma = statistical standard error of the simulated value). Writes
benchmark_report.json and benchmark_report.md to --output and exits 1 when any
case fails.

    python scripts/run_benchmarks.py [--quick] [--only csda_range,...] [--output DIR]
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "gui"))
from g4usim_gui.output.provenance import output_files
PACKS = ROOT / "scenarios" / "benchmarks"
EXE = Path(os.environ.get("G4USIM_EXE", ROOT / "build_vs2026/Release/G4UniversalSim.exe"))

MAIN = """
[run]
threads = {threads}
seed = {seed}
[output]
format = csv
[materials]
file = {root}/config/materials/material.ini
[geometry]
template = hierarchical
config = {geometry}
[physics]
{physics}
default_cut = {cut}
[scoring]
enabled = true
hits = {hits}
event_edep = false
edep = false
auto_create_default_scorers = true
{extra}
"""


def reference(pack: str) -> list[dict[str, str]]:
    with (PACKS / pack / "reference.csv").open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(line for line in handle if not line.startswith("#")))


class Backend:
    def __init__(self, work: Path, threads: int):
        self.work = work
        self.threads = threads
        self.count = 0

    def run(self, geometry: str, physics: str, extra: str, events: int, *, hits: bool, cut: str = "0.7 mm") -> Path:
        self.count += 1
        name = f"run{self.count:02d}"
        geo = self.work / f"{name}_geometry.ini"
        geo.write_text(geometry, encoding="utf-8")
        ini = self.work / f"{name}.ini"
        ini.write_text(MAIN.format(threads=self.threads, seed=1000 + self.count, root=ROOT.as_posix(),
                                   geometry=geo.as_posix(), physics=physics, cut=cut,
                                   hits="true" if hits else "false", extra=extra), encoding="utf-8")
        mac = self.work / f"{name}.mac"
        mac.write_text(f"/run/initialize\n/run/beamOn {events}\n", encoding="utf-8")
        output = self.work / name
        result = subprocess.run([str(EXE), "--config", str(ini), "--macro", str(mac), "--output", str(output)],
                                cwd=self.work, capture_output=True, text=True, errors="replace", timeout=7200)
        if result.returncode != 0:
            raise RuntimeError(f"{name} failed:\n{(result.stdout + result.stderr)[-3000:]}")
        return output


def worker_rows(output: Path, stem: str):
    for path in sorted(output_files(output, f"{stem}_t*.csv")):
        if re.fullmatch(rf"{stem}_t\d+\.csv", path.name):
            with path.open(newline="", encoding="utf-8") as handle:
                yield from csv.DictReader(handle)


def verdict(simulated: float, sigma: float, expected: float, tolerance: float) -> dict:
    allowed = tolerance * abs(expected) + 3.0 * sigma
    deviation = simulated - expected
    return {"simulated": simulated, "sigma": sigma, "reference": expected, "deviation": deviation,
            "relative_deviation": deviation / expected if expected else 0.0, "tolerance": tolerance,
            "allowed": allowed, "passed": abs(deviation) <= allowed}


WORLD = "[world]\nshape = box\nsize = 3 m, 3 m, 3 m\nmaterial = G4_Galactic\n"


def csda_range(backend: Backend, quick: bool) -> list[dict]:
    """Mean path length of primaries that stop in water vs the CSDA range."""
    geometry = WORLD + ("[volume.Water]\nparent = world\nshape = box\nsize = 80 cm, 80 cm, 80 cm\n"
                        "material = G4_WATER\nposition = 0 mm, 0 mm, 0 mm\nsensitive = true\n")
    results = []
    for row in reference("csda_range"):
        energy = float(row["energy_MeV"])
        if quick and energy not in (10.0, 100.0, 200.0, 1.0):
            continue
        events = (200 if quick else 1000) if row["particle"] == "proton" else (300 if quick else 2000)
        extra = (f"[source]\nparticle = {row['particle']}\nenergy = {energy} MeV\nposition_type = point\n"
                 "position = 0,0,0 mm\ndirection = +z\n")
        # CSDA range excludes nuclear interactions: EM-only physics.
        output = backend.run(geometry, "em = option4", extra, events, hits=True)
        path = defaultdict(float)
        for hit in worker_rows(output, "hits"):
            if hit["trackID"] == "1":
                path[(hit["runID"], hit["eventID"])] += float(hit["stepLength_mm"])
        values = [v / 10.0 for v in path.values()]   # cm = g/cm2 in water (rho = 1 g/cm3)
        mean = sum(values) / len(values)
        sigma = math.sqrt(sum((v - mean) ** 2 for v in values) / (len(values) - 1) / len(values))
        tolerance = 0.015 if row["particle"] == "proton" else 0.03
        result = verdict(mean, sigma, float(row["csda_range_g_cm2"]), tolerance)
        result.update(case=f"{row['particle']} {energy:g} MeV in water", quantity="CSDA range [g/cm2]",
                      source=row["source"], events=len(values))
        results.append(result)
    return results


def bragg_peak(backend: Backend, quick: bool) -> list[dict]:
    """Distal R80 of the laterally integrated depth-dose curve."""
    results = []
    for row in reference("bragg_peak"):
        energy = float(row["energy_MeV"])
        geometry = WORLD + ("[volume.Phantom]\nparent = world\nshape = box\nsize = 40 cm, 40 cm, 40 cm\n"
                            "material = G4_WATER\nposition = 0 mm, 0 mm, 200 mm\n")
        extra = (f"[source]\nparticle = proton\nenergy = {energy} MeV\nposition_type = point\n"
                 "position = 0,0,-10 mm\ndirection = +z\n"
                 "[scoring.mesh.depth]\nshape = box\nsize = 100 mm, 100 mm, 150 mm\nbins = 1, 1, 300\n"
                 "center = 0 mm, 0 mm, 150 mm\n"
                 "[scoring.mesh.depth.edep]\ntype = energyDeposit\nunit = MeV\n")
        events = 1000 if quick else 5000
        output = backend.run(geometry, "reference = QGSP_BIC_EMZ", extra, events, hits=False)
        depth = [0.0] * 300
        with (output / "scoring_mesh.csv").open(newline="", encoding="utf-8") as handle:
            for cell in csv.DictReader(handle):
                depth[int(cell["i2"])] += float(cell["sum"])
        peak_index = max(range(300), key=lambda i: depth[i])
        peak = depth[peak_index]
        r80 = None
        for i in range(peak_index, 299):
            if depth[i] >= 0.8 * peak > depth[i + 1]:
                # bin centres at (i + 0.5) mm from the phantom surface
                r80 = (i + 0.5) + (depth[i] - 0.8 * peak) / (depth[i] - depth[i + 1])
                break
        if r80 is None:
            raise RuntimeError("bragg_peak: no distal 80 % point found")
        expected = float(row["csda_range_g_cm2"]) * float(row["detour_factor"]) * 10.0   # mm
        result = verdict(r80, 0.1, expected, 0.01)   # sigma: 0.1 mm interpolation/statistics
        result.update(case=f"proton {energy:g} MeV pencil beam in water", quantity="R80 [mm]",
                      source=row["source"], events=events, peak_depth_mm=peak_index + 0.5,
                      peak_to_entrance=peak / (sum(depth[:10]) / 10.0))
        results.append(result)
    return results


def gamma_attenuation(backend: Backend, quick: bool) -> list[dict]:
    """Narrow-beam transmission T of unscattered photons: mu/rho = -ln T / (rho x)."""
    results = []
    for row in reference("gamma_attenuation"):
        thickness = float(row["thickness_mm"])
        energy = float(row["energy_MeV"])
        geometry = WORLD + (f"[volume.Slab]\nparent = world\nshape = box\nsize = 30 cm, 30 cm, {thickness} mm\n"
                            f"material = {row['material']}\nposition = 0 mm, 0 mm, {thickness / 2} mm\n"
                            "[volume.Plane]\nparent = world\nshape = box\nsize = 30 cm, 30 cm, 1 mm\n"
                            f"material = G4_Galactic\nposition = 0 mm, 0 mm, {thickness + 50} mm\n")
        extra = (f"[source]\nparticle = gamma\nenergy = {energy} MeV\nposition_type = point\n"
                 "position = 0,0,-100 mm\ndirection = +z\n"
                 "[phase_space]\nvolume = Plane_PV\nparticles = gamma\nkill = true\n")
        events = 4000 if quick else 20000
        output = backend.run(geometry, "reference = FTFP_BERT_EMZ", extra, events, hits=False)
        unscattered = sum(1 for p in worker_rows(output, "phase_space")
                          if p["trackID"] == "1" and abs(float(p["kineticEnergy_MeV"]) - energy) < 1e-9 * energy
                          and float(p["w"]) > 1 - 1e-9)
        transmission = unscattered / events
        rho_x = float(row["density_g_cm3"]) * thickness / 10.0
        mu = -math.log(transmission) / rho_x
        sigma = math.sqrt(transmission * (1 - transmission) / events) / transmission / rho_x
        result = verdict(mu, sigma, float(row["mu_rho_cm2_g"]), 0.02)
        result.update(case=f"{energy:g} MeV photons through {thickness:g} mm {row['material']}",
                      quantity="mu/rho [cm2/g]", source=row["source"], events=events, transmission=transmission)
        results.append(result)
    return results


def shielding_range(backend: Backend, quick: bool) -> list[dict]:
    """CSDA ranges in Al/Si and residual proton energy behind slabs (shielding pack)."""
    results = []
    for row in reference("shielding_range"):
        particle, material = row["particle"], row["material"]
        energy = float(row["energy_MeV"])
        density = float(row["density_g_cm3"])
        expected = float(row["reference"])
        source = (f"[source]\nparticle = {particle}\nenergy = {energy} MeV\nposition_type = point\n"
                  "position = 0,0,0 mm\ndirection = +z\n")
        if row["kind"] == "csda_range":
            if quick and (particle, energy) not in (("proton", 100.0), ("e-", 1.0)):
                continue
            geometry = WORLD + ("[volume.Block]\nparent = world\nshape = box\nsize = 80 cm, 80 cm, 80 cm\n"
                                f"material = {material}\nposition = 0 mm, 0 mm, 0 mm\nsensitive = true\n")
            events = (150 if quick else 1000) if particle == "proton" else (300 if quick else 2000)
            output = backend.run(geometry, "em = option4", source, events, hits=True)
            path = defaultdict(float)
            for hit in worker_rows(output, "hits"):
                if hit["trackID"] == "1":
                    path[(hit["runID"], hit["eventID"])] += float(hit["stepLength_mm"])
            values = [v / 10.0 * density for v in path.values()]    # g/cm2
            tolerance = 0.015 if particle == "proton" else 0.03
            case, quantity = f"{particle} {energy:g} MeV in {material}", "CSDA range [g/cm2]"
        else:
            thickness = float(row["thickness_mm"])
            if quick and thickness not in (5.0, 2.0):
                continue
            geometry = WORLD + (f"[volume.Slab]\nparent = world\nshape = box\nsize = 30 cm, 30 cm, {thickness} mm\n"
                                f"material = {material}\nposition = 0 mm, 0 mm, {10 + thickness / 2} mm\n"
                                "[volume.Plane]\nparent = world\nshape = box\nsize = 30 cm, 30 cm, 1 mm\n"
                                f"material = G4_Galactic\nposition = 0 mm, 0 mm, {thickness + 20.5} mm\n")
            extra = source + "[phase_space]\nvolume = Plane_PV\nparticles = proton\nkill = true\n"
            events = 300 if quick else 2000
            output = backend.run(geometry, "em = option4", extra, events, hits=False)
            values = [float(p["kineticEnergy_MeV"]) for p in worker_rows(output, "phase_space") if p["trackID"] == "1"]
            if len(values) < 0.99 * events:
                raise RuntimeError(f"shielding_range: only {len(values)} of {events} protons crossed the slab")
            tolerance = 0.01
            case, quantity = f"proton {energy:g} MeV behind {thickness:g} mm {material}", "mean exit energy [MeV]"
        mean = sum(values) / len(values)
        sigma = math.sqrt(sum((v - mean) ** 2 for v in values) / (len(values) - 1) / len(values))
        result = verdict(mean, sigma, expected, tolerance)
        result.update(case=case, quantity=quantity, source=row["source"], events=len(values))
        results.append(result)
    return results


def device_dose(backend: Backend, quick: bool) -> list[dict]:
    """TID and DDD per unit fluence in a thin Si slab embedded in Si (semiconductor pack)."""
    niel_dir = ROOT / "scenarios" / "semiconductor" / "niel"
    source_area_cm2 = 1.2 ** 2          # square source, half side 6 mm, covers the 10 mm slab
    results = []
    for row in reference("device_dose"):
        kind, particle = row["kind"], row["particle"]
        energy, buildup, slab = float(row["energy_MeV"]), float(row["buildup_mm"]), float(row["slab_mm"])
        if quick and (kind, particle, energy) not in (("tid", "proton", 10.0), ("tid", "proton", 100.0),
                                                      ("ddd", "proton", 100.0)):
            continue
        block = 2 * buildup + slab
        geometry = WORLD + (f"[volume.Block]\nparent = world\nshape = box\nsize = 40 mm, 40 mm, {block:g} mm\n"
                            f"material = G4_Si\nposition = 0 mm, 0 mm, {block / 2:g} mm\n"
                            f"[volume.Slab]\nparent = Block\nshape = box\nsize = 10 mm, 10 mm, {slab:g} mm\n"
                            "material = G4_Si\nposition = 0 mm, 0 mm, 0 mm\nsensitive = true\n")
        extra = "dose = true\n"
        if kind == "ddd":
            extra += (f"displacement = true\n[scoring.displacement]\n"
                      f"{particle} = {(niel_dir / f'si_{particle}.csv').as_posix()}\n")
        extra += (f"[source]\nparticle = {particle}\nenergy = {energy} MeV\nposition_type = plane\nshape = square\n"
                  "halfx = 6 mm\ncenter = 0 mm, 0 mm, -1 mm\ndirection = 0, 0, 1\n")
        events = 4000 if quick else 20000
        # Protons: EM-only (PSTAR excludes nuclear reactions); neutrons need hadronic physics.
        physics = "em = option4" if particle == "proton" else "reference = QGSP_BIC_HP"
        output = backend.run(geometry, physics, extra, events, hits=False, cut="10 um")
        scorer, quantity = ("dose", "weighted_dose") if kind == "tid" else ("displacement", f"ddd_{particle}")
        with (output / "scorer_statistics.csv").open(newline="", encoding="utf-8") as handle:
            stat = next(r for r in csv.DictReader(handle)
                        if r["scorer"] == scorer and r["quantity"] == quantity and "Slab_PV" in r["key"])
        per_fluence = float(stat["value"]) / events * source_area_cm2
        sigma = per_fluence * float(stat["rel_error"])
        result = verdict(per_fluence, sigma, float(row["reference"]), 0.02 if kind == "tid" else 0.01)
        label = "TID / fluence [Gy cm2]" if kind == "tid" else "DDD / fluence [MeV cm2/g]"
        result.update(case=f"{particle} {energy:g} MeV, {1000 * slab:g} um Si slab behind {1000 * buildup:g} um Si",
                      quantity=label, source=row["source"], events=events,
                      mean_energy_MeV=float(row["mean_energy_MeV"]))
        results.append(result)
    return results


def detector_response(backend: Backend, quick: bool) -> list[dict]:
    """Pulse-height features against analytic references (detector response pack)."""
    pack = ROOT / "scenarios" / "detector_response"
    runs: dict[tuple, dict] = {}
    results = []
    for row in reference("detector_response"):
        kind, detector, particle = row["kind"], row["detector"].split(), row["particle"]
        energy, expected = float(row["energy_MeV"]), float(row["reference_MeV"])
        if quick and (kind, energy) not in (("compton_edge", 0.662), ("single_escape", 4.44),
                                            ("landau_mpv", 4000.0)):
            continue
        key = (tuple(detector), particle, energy)
        if key not in runs:
            backend.count += 1
            out = backend.work / f"run{backend.count:02d}"
            if detector[0] == "Si":
                options = ["--kind", "silicon", "--thickness", detector[1]]
                events = 40000 if quick else 200000     # the mode of a Landau is a noisy estimate
            else:
                options = ["--kind", "gamma", "--crystal", detector[0], "--radius", detector[1], "--length", detector[2]]
                events = 30000 if quick else 100000
            subprocess.run([sys.executable, str(pack / "make_detector.py"), "--out", str(out), *options,
                            "--particle", particle, "--energy", str(energy), "--events", str(events),
                            "--threads", str(backend.threads), "--seed", str(1000 + backend.count)],
                           check=True, capture_output=True, text=True)
            result = subprocess.run([str(EXE), "--config", "main.ini"], cwd=out, capture_output=True, text=True,
                                    errors="replace", timeout=7200)
            if result.returncode != 0:
                raise RuntimeError(f"detector_response run failed:\n{(result.stdout + result.stderr)[-3000:]}")
            subprocess.run([sys.executable, str(pack / "analyze_detector.py"), str(out / "output")],
                           check=True, capture_output=True, text=True)
            report = json.loads((out / "output" / "detector_report.json").read_text(encoding="utf-8"))
            report["events"] = events
            runs[key] = report
        report = runs[key]
        if kind == "landau_mpv":
            simulated, sigma, tolerance = report["mpv_MeV"], report["mpv_error_MeV"], 0.03
            quantity = "most probable deposit [MeV]"
        else:
            # positions from 1 keV bins: sigma = bin / sqrt(12); edges also carry the smoothing
            field = "compton_edge_MeV" if kind == "compton_edge" else None
            if field:
                simulated, tolerance = report[field], 0.01
            else:
                line = report[f"{kind}_MeV"]
                if report[f"{kind}_per_primary"] <= 0:
                    raise RuntimeError(f"detector_response: no {kind} counts")
                simulated, tolerance = line, 0.0
                # the line itself: verify the deposit histogram peaks there (within 1 keV)
                with (backend.work / f"run{backend.count:02d}" / "output" / "pulse_height.csv").open(
                        newline="", encoding="utf-8") as handle:
                    bins = [(float(r["e_low_MeV"]), float(r["deposit_per_primary"])) for r in csv.DictReader(handle)
                            if abs(float(r["e_low_MeV"]) + 0.0005 - line) <= 0.010]
                simulated = max(bins, key=lambda b: b[1])[0] + 0.0005
            sigma = 0.001 / math.sqrt(12)
            quantity = "Compton edge [MeV]" if field else "escape peak [MeV]"
        result = verdict(simulated, sigma, expected, tolerance)
        result.update(case=f"{particle} {energy:g} MeV, {' '.join(detector)}", quantity=quantity, source=row["source"],
                      events=report["events"])
        results.append(result)
    return results

BENCHMARKS = {"csda_range": csda_range, "bragg_peak": bragg_peak, "gamma_attenuation": gamma_attenuation,
              "shielding_range": shielding_range, "device_dose": device_dose,
              "detector_response": detector_response}


def write_report(output: Path, report: dict) -> None:
    output.mkdir(parents=True, exist_ok=True)
    (output / "benchmark_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    lines = ["# G4UniversalSim benchmark report", "",
             f"- Geant4 backend: `{report['executable']}`", f"- mode: {'quick' if report['quick'] else 'full'}",
             f"- result: {report['passed']} passed, {report['failed']} failed", "",
             "| benchmark | case | quantity | simulated | reference | deviation | allowed | result |",
             "| --- | --- | --- | --- | --- | --- | --- | --- |"]
    for name, results in report["benchmarks"].items():
        for r in results:
            lines.append(f"| {name} | {r['case']} | {r['quantity']} | {r['simulated']:.5g} ± {r['sigma']:.2g} | "
                         f"{r['reference']:.5g} ({r['source']}) | {100 * r['relative_deviation']:+.2f} % | "
                         f"± {r['allowed']:.3g} | {'pass' if r['passed'] else 'FAIL'} |")
    (output / "benchmark_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--quick", action="store_true", help="fewer cases and events (regression suite)")
    parser.add_argument("--only", default="", help="comma-separated benchmark names")
    parser.add_argument("--output", default="", help="report directory (default: a temporary directory)")
    parser.add_argument("--threads", type=int, default=4)
    args = parser.parse_args()
    if not EXE.is_file():
        print(f"backend executable missing: {EXE}")
        return 1
    selected = [n.strip() for n in args.only.split(",") if n.strip()] or list(BENCHMARKS)
    unknown = set(selected) - set(BENCHMARKS)
    if unknown:
        print(f"unknown benchmarks: {sorted(unknown)}; available: {list(BENCHMARKS)}")
        return 2
    work = Path(tempfile.mkdtemp(prefix="g4usim_bench_"))
    output = Path(args.output) if args.output else work / "report"
    report = {"executable": str(EXE), "quick": args.quick, "benchmarks": {}}
    try:
        backend = Backend(work, args.threads)
        for name in selected:
            start = time.time()
            results = BENCHMARKS[name](backend, args.quick)
            report["benchmarks"][name] = results
            for r in results:
                print(f"{'pass' if r['passed'] else 'FAIL'}  {name:18s} {r['case']:45s} {r['quantity']:20s} "
                      f"{r['simulated']:.5g} +- {r['sigma']:.2g}  ref {r['reference']:.5g}  "
                      f"({100 * r['relative_deviation']:+.2f} %, allowed +-{r['allowed']:.3g})")
            print(f"      {name}: {time.time() - start:.0f} s")
        everything = [r for results in report["benchmarks"].values() for r in results]
        report["passed"] = sum(r["passed"] for r in everything)
        report["failed"] = len(everything) - report["passed"]
        write_report(output, report)
        print(f"report: {output / 'benchmark_report.md'}")
        failed = [(name, r) for name, results in report["benchmarks"].items() for r in results if not r["passed"]]
        assert not failed, "benchmark failures: " + "; ".join(
            f"{name} {r['case']} {r['quantity']} = {r['simulated']:.5g} +- {r['sigma']:.2g}, "
            f"reference {r['reference']:.5g}, deviation {100 * r['relative_deviation']:+.2f} %, "
            f"allowed +-{r['allowed']:.3g}" for name, r in failed)
    finally:
        if not args.output:
            print("(temporary report removed; pass --output to keep it)")
        shutil.rmtree(work, ignore_errors=True)
    return 0 if report.get("failed", 1) == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
