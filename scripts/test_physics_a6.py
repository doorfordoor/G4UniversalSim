"""Real Geant4 regression for roadmap A6 physics options.

Checks:
  1. EM presets (standard, option3, option4, livermore, penelope on FTFP_BERT): the
     process dump shows the matching EM constructor and Compton/msc models, and the
     narrow-beam transmission of 1 MeV photons through 10 cm of water equals NIST XCOM
     (mu/rho = 0.07072 cm2/g, T = 0.4930) within 5 sigma for every preset;
  2. region physics ([physics.region.<name>]): range cuts and their energy thresholds in
     the dump; 1 um e- cuts produce delta rays that the 1 mm default suppresses; max_step
     bounds every proton step; min_kinetic_energy and max_track_length stop tracks; a
     region can be created from volumes = ...;
  3. radioactive decay: with Geant4's default time threshold (1 year) Co-60 (mean life
     7.6 y) does not decay; with time_threshold = 1000 y 99.9 % of decays feed the
     2505.7 keV Ni-60 level and the mean beta energy is 95.8 keV (NNDC); enabled = true
     on a list that already has radioactive decay registers it only once;
  4. failures: unknown region, conflict with geometry cut.*, unsupported keys, the world
     region, unknown volumes, time_threshold without radioactive decay, and a process dump
     before /run/initialize (a dump right after /run/initialize is complete).
Tolerances are 5 standard errors (seeds fixed).
"""

from __future__ import annotations

import csv
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXE = Path(os.environ.get("G4USIM_EXE", ROOT / "build_vs2026/Release/G4UniversalSim.exe"))

MAIN = """
[run]
threads = 2
seed = {seed}
[output]
format = csv
[materials]
file = {root}/config/materials/material.ini
[geometry]
template = hierarchical
config = {geometry}
[physics]
reference = {reference}
default_cut = 1 mm
{physics}
[scoring]
enabled = true
hits = {hits}
event_edep = false
edep = false
auto_create_default_scorers = true
{extra}
"""

WORLD = "[world]\nshape = box\nsize = 2 m, 2 m, 2 m\nmaterial = G4_Galactic\n"


def volume(name: str, body: str, material: str = "G4_WATER", sensitive: bool = True, parent: str = "world") -> str:
    return (f"\n[volume.{name}]\nparent = {parent}\nmaterial = {material}\n"
            f"sensitive = {'true' if sensitive else 'false'}\n{body}\n")


class Runner:
    def __init__(self, work: Path):
        self.work = work
        self.count = 0

    def run(self, geometry: str, extra: str, events: int, *, physics: str = "", reference: str = "FTFP_BERT",
            hits: bool = False, seed: int = 4242, macro: str | None = None, expect_ok: bool = True):
        self.count += 1
        name = f"case{self.count:02d}"
        geo = self.work / f"{name}_geometry.ini"
        geo.write_text(geometry, encoding="utf-8")
        ini = self.work / f"{name}.ini"
        ini.write_text(MAIN.format(seed=seed, root=ROOT.as_posix(), geometry=geo.as_posix(), reference=reference,
                                   physics=physics, hits="true" if hits else "false", extra=extra), encoding="utf-8")
        dump = self.work / f"{name}_dump.json"
        mac = self.work / f"{name}.mac"
        mac.write_text(macro if macro is not None else
                       f"/run/initialize\n/run/beamOn {events}\n/AIHL/physics/dumpProcesses {dump.as_posix()}\n",
                       encoding="utf-8")
        output = self.work / name
        result = subprocess.run([str(EXE), "--config", str(ini), "--macro", str(mac), "--output", str(output)],
                                cwd=self.work, capture_output=True, text=True, errors="replace", timeout=1800)
        log = result.stdout + result.stderr
        if expect_ok:
            assert result.returncode == 0, f"{name} failed:\n{log[-3000:]}"
        else:
            assert result.returncode != 0, f"{name} unexpectedly succeeded"
        data = json.loads(dump.read_text(encoding="utf-8")) if dump.is_file() else None
        return output, data, log


def rows(output: Path, stem: str):
    pattern = re.compile(rf"{stem}_t(\d+)\.csv$")
    for path in sorted(output.glob(f"{stem}_t*.csv")):
        if not pattern.fullmatch(path.name):
            continue
        with path.open(newline="", encoding="utf-8") as handle:
            yield from csv.DictReader(handle)


def first_steps(output: Path, select):
    first = {}
    for row in rows(output, "hits"):
        if select(row):
            first.setdefault((row["eventID"], row["trackID"], row["runID"]), row)
    return list(first.values())


def models(data, particle: str, process: str):
    proc = next(p for p in next(x for x in data["particles"] if x["name"] == particle)["processes"]
                if p["name"] == process)
    return [m["name"] for m in proc["models"]]


def gamma_submodels(data, sub: str):
    gamma = next(x for x in data["particles"] if x["name"] == "gamma")
    for proc in gamma["processes"]:
        if proc["name"] == "GammaGeneralProc":
            return [m["name"] for m in next(s for s in proc["sub_processes"] if s["name"] == sub)["models"]]
        if proc["name"] == sub:
            return [m["name"] for m in proc["models"]]
    raise KeyError(sub)


def em_preset_cases(r: Runner) -> None:
    print("EM presets: models and 1 MeV photon transmission through 10 cm water (NIST XCOM)")
    geometry = WORLD + volume("Slab", "shape = box\nsize = 30 cm, 30 cm, 10 cm\nposition = 0 mm, 0 mm, 0 mm",
                              sensitive=False) + \
        volume("Plane", "shape = box\nsize = 20 cm, 20 cm, 1 mm\nposition = 0 mm, 0 mm, 100 mm",
               material="G4_Galactic", sensitive=False)
    source = ("[source]\nparticle = gamma\nenergy = 1 MeV\nposition_type = point\nposition = 0,0,-200 mm\n"
              "direction = +z\n[phase_space]\nvolume = Plane_PV\nparticles = gamma\nkill = true\n")
    n = 4000
    expected = math.exp(-0.07072 * 1.0 * 10.0)
    sigma = math.sqrt(expected * (1 - expected) / n)
    presets = {
        "standard": ("G4EmStandard", "Klein-Nishina", "UrbanMsc"),
        "option3": ("G4EmStandard_opt3", "KleinNishina", "UrbanMsc"),
        "option4": ("G4EmStandard_opt4", "LowEPComptonModel", "GoudsmitSaunderson"),
        "livermore": ("G4EmLivermore", "LivermoreCompton", "GoudsmitSaunderson"),
        "penelope": ("G4EmPenelope", "PenCompton", "GoudsmitSaunderson"),
    }
    for em, (constructor, compton, msc) in presets.items():
        output, data, _ = r.run(geometry, source, n, physics=f"em = {em}")
        assert data["physics_list"]["constructors"][0] == constructor, data["physics_list"]
        assert compton in gamma_submodels(data, "compt"), (em, gamma_submodels(data, "compt"))
        assert msc in models(data, "e-", "msc"), (em, models(data, "e-", "msc"))
        unscattered = sum(1 for row in rows(output, "phase_space")
                          if row["trackID"] == "1" and abs(float(row["kineticEnergy_MeV"]) - 1.0) < 1e-9
                          and float(row["w"]) > 0.999999)
        transmission = unscattered / n
        print(f"  {em:9s}: {constructor:18s} Compton {compton:18s} T = {transmission:.4f} "
              f"(XCOM {expected:.4f} +- {sigma:.4f})")
        assert abs(transmission - expected) < 5 * sigma, (em, transmission, expected)


def region_cases(r: Runner) -> None:
    print("region physics")
    det = volume("Det", "shape = box\nsize = 10 cm, 10 cm, 20 cm\nposition = 0 mm, 0 mm, 0 mm\nregion = DetRegion")
    beam = ("[source]\nparticle = proton\nenergy = 100 MeV\nposition_type = point\nposition = 0,0,-200 mm\n"
            "direction = +z\n")
    n = 200
    fine = "[physics.region.DetRegion]\ne- = 1 um\ngamma = 10 um\nmax_step = 0.2 mm\n"
    out_fine, dump, _ = r.run(WORLD + det, beam + fine, n, hits=True)
    out_ref, dump_ref, _ = r.run(WORLD + det, beam, n, hits=True)
    region = next(x for x in dump["regions"] if x["name"] == "DetRegion")
    assert region["production_cuts_mm"]["e-"] == 0.001 and region["production_cuts_mm"]["gamma"] == 0.01
    assert region["production_cuts_mm"]["e+"] == 1 and region["user_limits"]["max_step_mm"] == 0.2
    couple = next(c for c in dump["couples"] if c["region"] == "DetRegion" and c["material"] == "G4_WATER")
    print(f"  DetRegion cuts e- 1 um -> {couple['energy_cuts_MeV']['e-'] * 1e6:.0f} eV, "
          f"e+ 1 mm -> {couple['energy_cuts_MeV']['e+'] * 1e3:.1f} keV in water")
    assert abs(couple["energy_cuts_MeV"]["e-"] - 990e-6) < 1e-9          # Geant4 lower edge
    assert 0.3 < couple["energy_cuts_MeV"]["e+"] < 0.4                    # 1 mm in water
    assert "stepLimiter" in dump["physics_list"]["constructors"]
    assert "stepLimiter" not in dump_ref["physics_list"]["constructors"]

    deltas_fine = len(first_steps(out_fine, lambda x: x["particle"] == "e-" and x["parentID"] == "1"))
    deltas_ref = len(first_steps(out_ref, lambda x: x["particle"] == "e-" and x["parentID"] == "1"))
    print(f"  delta electrons from the primaries: {deltas_fine} with 1 um cut, {deltas_ref} with 1 mm cut")
    assert deltas_ref == 0 and deltas_fine > 50 * n, (deltas_fine, deltas_ref)

    longest = max(float(x["stepLength_mm"]) for x in rows(out_fine, "hits") if x["trackID"] == "1")
    longest_ref = max(float(x["stepLength_mm"]) for x in rows(out_ref, "hits") if x["trackID"] == "1")
    print(f"  longest primary step: {longest:.4f} mm with max_step = 0.2 mm ({longest_ref:.2f} mm without)")
    assert longest <= 0.2 + 1e-9 and longest_ref > 1.0

    limits = "[physics.region.DetRegion]\nmin_kinetic_energy = 50 MeV\n"
    out, _, _ = r.run(WORLD + det, beam + limits, 50, hits=True)
    # G4UserSpecialCuts checks the energy at the start of a step: a track that
    # fell below 50 MeV (slowing down, or a large elastic transfer) is killed by
    # a zero-length UserSpecialCut step and never transported further.
    below = [x for x in rows(out, "hits") if x["trackID"] == "1" and float(x["kineticEnergy_MeV"]) < 50.0]
    kills = sum(1 for x in rows(out, "hits") if x["trackID"] == "1" and x["process"] == "UserSpecialCut")
    transported = [x for x in below if x["process"] != "UserSpecialCut" or float(x["stepLength_mm"]) > 0.0]
    lowest_ref = min(float(x["kineticEnergy_MeV"]) for x in rows(out_ref, "hits") if x["trackID"] == "1")
    print(f"  min_kinetic_energy = 50 MeV: {kills} primaries killed by UserSpecialCut, {len(transported)} "
          f"steps transported below 50 MeV (without the limit primaries reach {lowest_ref:.3f} MeV)")
    assert not transported and kills > 40 and lowest_ref < 5.0, transported[:3]

    # max_track_length limits the total track length since creation, so the
    # protons start inside the region here.
    limits = "[physics.region.DetRegion]\nmax_track_length = 30 mm\n"
    inside = beam.replace("position = 0,0,-200 mm", "position = 0,0,-90 mm")
    out, _, _ = r.run(WORLD + det, inside + limits, 50, hits=True)
    length = defaultdict(float)
    for x in rows(out, "hits"):
        if x["trackID"] == "1":
            length[x["eventID"]] += float(x["stepLength_mm"])
    print(f"  max_track_length = 30 mm: primary path in the region {min(length.values()):.2f}-{max(length.values()):.2f} mm")
    assert max(length.values()) <= 30.0 + 1e-6 and min(length.values()) > 29.0

    plain = volume("Det", "shape = box\nsize = 10 cm, 10 cm, 20 cm\nposition = 0 mm, 0 mm, 0 mm")
    _, dump, _ = r.run(WORLD + plain, beam + "[physics.region.MadeHere]\nvolumes = Det\ne- = 5 um\n", 1)
    region = next(x for x in dump["regions"] if x["name"] == "MadeHere")
    assert region["root_volumes"] == ["Det_LV"] and region["production_cuts_mm"]["e-"] == 0.005
    print("  volumes = Det creates region MadeHere with Det_LV as root")


def decay_cases(r: Runner) -> None:
    print("radioactive decay")
    box = volume("Box", "shape = box\nsize = 40 cm, 40 cm, 40 cm\nposition = 0 mm, 0 mm, 0 mm")
    source = ("[source]\nparticle = ion\nion = 27 60\nenergy = 0 keV\nposition_type = point\nposition = 0,0,0 mm\n"
              "angular = isotropic\n")
    n = 1000
    out, dump, _ = r.run(WORLD + box, source, n, hits=True, physics="[physics.radioactive_decay]\nenabled = true\n")
    assert dump["radioactive_decay"]["geant4_default"] is True
    betas = first_steps(out, lambda x: x["particle"] == "e-" and x["parentID"] == "1")
    print(f"  Geant4 default threshold: {len(betas)} Co-60 decays in {n} events")
    assert not betas

    physics = "[physics.radioactive_decay]\nenabled = true\ntime_threshold = 1000 y\n"
    out, dump, _ = r.run(WORLD + box, source, n, hits=True, physics=physics)
    assert abs(dump["radioactive_decay"]["time_threshold_years"] - 1000) < 1e-6
    daughters = [x["particle"] for x in first_steps(out, lambda x: x["parentID"] == "1" and x["particle"].startswith("Ni60"))]
    level = sum(name == "Ni60[2505.753]" for name in daughters)
    betas = [float(x["kineticEnergy_MeV"]) for x in first_steps(out, lambda x: x["particle"] == "e-" and x["parentID"] == "1")]
    mean_beta = sum(betas) / len(betas)
    print(f"  time_threshold = 1000 y: {len(daughters)} Ni-60 recoils, {level} in the 2505.7 keV level; "
          f"mean beta {mean_beta * 1000:.1f} keV (NNDC 95.8 keV)")
    assert len(daughters) > 0.98 * n and level > 0.99 * len(daughters)
    assert abs(mean_beta - 0.0958) < 0.05 * 0.0958

    _, dump, _ = r.run(WORLD + box, source, 1, reference="Shielding", physics="[physics.radioactive_decay]\nenabled = true\n")
    radioactive = [c for c in dump["physics_list"]["constructors"] if "Radioactive" in c]
    assert len(radioactive) == 1, dump["physics_list"]["constructors"]
    print(f"  Shielding + enabled = true: one radioactive-decay constructor ({radioactive[0]})")


def failure_cases(r: Runner) -> None:
    print("failures")
    beam = "[source]\nparticle = geantino\nenergy = 1 MeV\nposition = 0,0,-200 mm\ndirection = +z\n"
    det = volume("Det", "shape = box\nsize = 1 cm, 1 cm, 1 cm\nposition = 0 mm, 0 mm, 0 mm\nregion = DetRegion")
    det_cut = volume("Det", "shape = box\nsize = 1 cm, 1 cm, 1 cm\nposition = 0 mm, 0 mm, 0 mm\nregion = DetRegion\n"
                            "cut.e- = 1 mm")
    cases = [
        (WORLD + det, "[physics.region.Missing]\ne- = 1 um\n", "", "region 'Missing' does not exist"),
        (WORLD + det_cut, "[physics.region.DetRegion]\ne- = 1 um\n", "", "already has production cuts"),
        (WORLD + det, "[physics.region.DetRegion]\nalpha = 1 um\n", "", "unknown key [physics.region."),
        (WORLD + det, "[physics.region.DetRegion]\nmax_step = -1 mm\n", "", "must be > 0"),
        (WORLD + det, "[physics.region.DefaultRegionForTheWorld]\ne- = 1 um\n", "", "not allowed"),
        (WORLD + det, "[physics.region.NewOne]\nvolumes = Nope\ne- = 1 um\n", "", "unknown logical volume 'Nope'"),
        (WORLD + det, "", "[physics.radioactive_decay]\ntime_threshold = 10 y\nenabled = false\n", "has no effect"),
        (WORLD + det, "", "[physics.radioactive_decay]\nhalf_life = 1 y\n", "unknown key [physics.radioactive_decay]"),
    ]
    for geometry, extra, physics, message in cases:
        _, _, log = r.run(geometry, beam + extra, 1, physics=physics, expect_ok=False)
        assert message in log, (message, log[-2000:])
    # Read-only, but only after /run/initialize (Geant4 refuses it in PreInit).
    _, _, log = r.run(WORLD + det, beam, 1, expect_ok=False,
                      macro=f"/AIHL/physics/dumpProcesses {(r.work / 'early.json').as_posix()}\n/run/initialize\n")
    assert "dumpProcesses" in log and "status=" in log, log[-2000:]
    early = r.work / "after_init.json"
    r.run(WORLD + det, beam, 1, macro=f"/run/initialize\n/AIHL/physics/dumpProcesses {early.as_posix()}\n")
    assert json.loads(early.read_text(encoding="utf-8"))["couples"], "dump after /run/initialize has no couples"
    print(f"  {len(cases) + 1} invalid physics settings rejected")


def main() -> int:
    assert EXE.is_file(), f"backend executable missing: {EXE}"
    work = Path(tempfile.mkdtemp(prefix="g4usim_a6_"))
    try:
        r = Runner(work)
        em_preset_cases(r)
        region_cases(r)
        decay_cases(r)
        failure_cases(r)
    finally:
        shutil.rmtree(work, ignore_errors=True)
    print("test_physics_a6: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
