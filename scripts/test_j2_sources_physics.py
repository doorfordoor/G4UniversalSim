"""J2 real primary-vertex/constructor/process regression; requires G4USIM_EXE.

Observes G4Event immediately after generation through the test-only environment
hook; transported sensitive hits are never substituted for primary vertices.
No build is started here. A stale executable fails before any simulation.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
import math
import os
from pathlib import Path
from phase_space_test_fixture import synthetic_default_fixture
import subprocess
import sys
from uuid import uuid4

from run_m0_tests import workspace_source_fingerprint

ROOT = Path(__file__).resolve().parents[1]
WORLD = "[world]\nshape=box\nsize=2 m,2 m,2 m\nmaterial=G4_Galactic\n"
DETECTOR = ("[volume.Det]\nparent=world\nshape=box\nsize=20 mm,20 mm,20 mm\n"
            "material=G4_Galactic\nsensitive=false\nregion=DetRegion\n")
POINT = "[source]\nparticle=proton\nenergy=1 MeV\nposition_type=point\nposition=0,0,0 mm\ndirection=+x\n"


def write(path: Path, text: str) -> None:
    path.write_bytes(text.encode("utf-8"))


def values(path: Path) -> dict[str, str]:
    return {k.strip(): v.strip() for line in path.read_text(encoding="utf-8").splitlines()
            if "=" in line for k, v in [line.split("=", 1)]}


def invoke(exe: Path, directory: Path, args: list[str], env: dict | None = None):
    result = subprocess.run([str(exe), *args], cwd=directory, env=env,
                            capture_output=True, timeout=240)
    (directory / "stdout.log").write_bytes(result.stdout)
    (directory / "stderr.log").write_bytes(result.stderr)
    return result, (result.stdout + result.stderr).decode("utf-8", errors="replace")


class Cases:
    def __init__(self, exe: Path, root: Path):
        self.exe, self.root = exe, root
        self.receipts = []

    def run(self, name: str, source: str = POINT, *, physics: str = "reference=FTFP_BERT\n",
            events: int = 8, threads: int = 2, extra: str = "", detector: bool = False,
            reject: str | None = None, files: dict[str, str] | None = None,
            commands: str = "", runs: int = 1, macro_text: str | None = None):
        directory = self.root / name
        directory.mkdir()
        for key, text in (files or {}).items():
            write(directory / key, text)
        write(directory / "geometry.ini", WORLD + (DETECTOR if detector else ""))
        ini = (f"[run]\nthreads={threads}\nseed=1731\n[output]\nformat=csv\n"
               f"trajectories={events if detector else 0}\n[materials]\n"
               f"file={(ROOT / 'config/materials/material.ini').as_posix()}\n"
               "[geometry]\ntemplate=hierarchical\nconfig=geometry.ini\n"
               f"[physics]\n{physics}[scoring]\nenabled=false\n{source}{extra}")
        write(directory / "main.ini", ini)
        write(directory / "run.mac", macro_text if macro_text is not None else "/run/initialize\n" + commands +
              "".join(f"/run/beamOn {events}\n" for _ in range(runs)) +
              "/AIHL/physics/dumpProcesses processes.json\n")
        diagnostic = directory / "primaries.jsonl"
        env = dict(os.environ, G4USIM_TEST_PRIMARY_VERTICES=str(diagnostic))
        result, log = invoke(self.exe, directory,
                             ["--config", "main.ini", "--macro", "run.mac", "--output", "output"], env)
        rows = [json.loads(line) for line in diagnostic.read_text(encoding="utf-8").splitlines()] if diagnostic.exists() else []
        self.receipts.append({"name": name, "exit_code": result.returncode,
                              "expect_rejection": reject, "observed_primaries": len(rows),
                              "stdout_sha256": hashlib.sha256(result.stdout).hexdigest(),
                              "stderr_sha256": hashlib.sha256(result.stderr).hexdigest()})
        self.save()
        if reject is not None:
            assert result.returncode not in (0, -11, -6, 3221225477, -1073741819), (name, result.returncode, log[-3000:])
            assert reject.lower() in log.lower(), (name, reject, log[-3000:])
            assert not rows, (name, "Rejected configuration emitted primaries")
            summary = directory / "output/run_summary.txt"
            if summary.exists():
                data = values(summary)
                assert data.get("status") == "failed", (name, data)
                assert int(data.get("actual_completed_event_count", "0")) == 0, (name, data)
            return directory, rows, None
        assert result.returncode == 0, (name, result.returncode, log[-4000:])
        summary = values(directory / "output/run_summary.txt")
        assert summary["status"] == summary["macro_execution_status"] == "completed", (name, summary)
        assert summary["summary_write_status"] == "completed", (name, summary)
        assert summary["output_failure_status"] == "none", (name, summary)
        assert int(summary["run_count"]) == runs, (name, summary)
        assert int(summary["planned_event_count"]) == int(summary["actual_completed_event_count"]) == events * runs
        event_keys = {(r["run"], r["event"]) for r in rows}
        assert event_keys == {(run, event) for run in range(runs) for event in range(events)}, (name, event_keys)
        assert all(all(math.isfinite(float(value)) for value in row.values()) for row in rows), name
        dump = json.loads((directory / "processes.json").read_text(encoding="utf-8"))
        assert dump["schema"] == "g4usim_process_dump_v1", name
        print(name, "OK", len(rows), "primaries", flush=True)
        return directory, rows, dump

    def save(self):
        write(self.root / "case-receipts.json", json.dumps(self.receipts, indent=2) + "\n")


def mean(values):
    values = list(values)
    return sum(values) / len(values)


def process_names(dump, particle):
    return {p["name"] for row in dump["particles"] if row["name"] == particle for p in row["processes"]}


def constructors(dump):
    details = dump["physics_list"]["constructor_details"]
    assert [x["name"] for x in details] == dump["physics_list"]["constructors"]
    return details


def sources(c: Cases):
    n = 2048
    surface = ("[source]\nparticle=proton\nenergy=3 MeV\nposition_type=surface\nshape=sphere\n"
               "center=13,-7,5 mm\nradius=10 mm\nangular=isotropic\n")
    _, rows, _ = c.run("surface-sphere", surface, events=n)
    centered = [[row[k] - center for k, center in zip(("x_mm", "y_mm", "z_mm"), (13, -7, 5))] for row in rows]
    assert all(abs(math.sqrt(sum(x*x for x in p)) - 10) < 1e-10 for p in centered)
    for axis in range(3):
        assert abs(mean(p[axis] for p in centered)) < 6 * 10 / math.sqrt(3*n)
        assert abs(mean((p[axis]/10)**2 for p in centered) - 1/3) < 6*math.sqrt(4/(45*n))
    assert all(row["vertex_count"] == 1 and row["pdg"] == 2212 and abs(row["energy_MeV"]-3) < 1e-12 for row in rows)
    assert all(abs(row["u"]**2+row["v"]**2+row["w"]**2-1) < 1e-12 for row in rows)
    _, inside, _ = c.run("volume-sphere-control", surface.replace("position_type=surface", "position_type=volume"), events=n)
    radii = [math.dist((r["x_mm"], r["y_mm"], r["z_mm"]), (13, -7, 5)) for r in inside]
    assert all(r <= 10+1e-10 for r in radii) and any(r < 5 for r in radii)
    assert abs(mean((r/10)**3 for r in radii)-0.5) < 6/math.sqrt(12*n)

    named = ("[source.Low]\nparticle=proton\nenergy=2 MeV\nposition=-5,0,0 mm\ndirection=+x\nintensity=1\n"
             "[source.High]\nparticle=gamma\nenergy=7 MeV\nposition=5,0,0 mm\ndirection=-x\nintensity=3\n")
    _, selected, _ = c.run("named-selection", named, events=n)
    assert len(selected) == n and all(r["vertex_count"] == 1 for r in selected)
    count = Counter(r["pdg"] for r in selected)
    assert abs(count[2212]/n-0.25) < 6*math.sqrt(0.25*0.75/n), count
    for row in selected:
        assert (row["pdg"], row["x_mm"], row["energy_MeV"], row["u"]) in ((2212, -5, 2, 1), (22, 5, 7, -1)), row
        assert abs(row["primary_weight"]*row["vertex_weight"]-1) < 1e-12, row
    _, together, _ = c.run("named-simultaneous", "[source]\nmultiple_vertex=true\n"+named, events=32, runs=2)
    groups = defaultdict(list)
    for row in together:
        groups[row["run"], row["event"]].append(row)
    assert len(groups) == 64
    for particles in groups.values():
        assert len(particles) == 2 and {r["pdg"] for r in particles} == {2212, 22}, particles
        assert all(r["vertex_count"] == 2 for r in particles)
        # With flat_sampling=false native GPS intensity weights are one even
        # in simultaneous mode: intensity changes neither multiplicity nor weight.
        assert all(abs(r["primary_weight"]*r["vertex_weight"]-1) < 1e-12 for r in particles)
    c.receipts[-1]["weights_by_pdg"] = {str(pdg): sorted({r["primary_weight"]*r["vertex_weight"] for r in together if r["pdg"] == pdg}) for pdg in (2212, 22)}
    c.save()
    _, single, _ = c.run("single-named-intensity", named.split("[source.High]")[0], events=8)
    assert all(r["pdg"] == 2212 and r["energy_MeV"] == 2 for r in single)

    _, spectral, _ = c.run("named-surface-spectrum-ion", "[source]\nmultiple_vertex=true\n" +
        "[source.spectrum]\nparticle=gamma\nenergy_type=histogram\nspectrum_file=spectrum.csv\n"
        "position_type=surface\nshape=sphere\nradius=2 mm\ndirection=+z\nintensity=2\n" +
        "[source.carbon]\nparticle=ion\nion=6 12 2\nenergy=12 MeV\nposition=0,0,0 mm\ndirection=+z\nintensity=1\n",
        events=64, files={"spectrum.csv": "e_low_MeV,e_high_MeV,weight\n1,2,1\n2,3,1\n"})
    ions = [r for r in spectral if r["pdg"] == 1000060120]
    photons = [r for r in spectral if r["pdg"] == 22]
    assert len(ions) == len(photons) == 64
    assert all(r["energy_MeV"] == 12 and abs(r["charge_eplus"]-2) < 1e-12 for r in ions)
    assert all(1 <= r["energy_MeV"] <= 3 and abs(math.hypot(r["x_mm"],r["y_mm"],r["z_mm"])-2) < 1e-10 for r in photons)

    header = "runID,eventID,trackID,parentID,particle,pdg,x_mm,y_mm,z_mm,u,v,w,kineticEnergy_MeV,time_ns,weight\n"
    histories = "".join(f"0,{e},1,0,proton,2212,0,0,0,1,0,0,{e+1},0,0.5\n0,{e},2,0,gamma,22,5,0,0,0,0,1,7,0,0.25\n" for e in range(3))
    _, replay, _ = c.run("phase-space-reuse", "[source]\nphase_space_file=history.csv\nphase_space_recycle=true\n",
                         events=6, files={"history.csv": synthetic_default_fixture(header+histories,
                             purpose="j2-sources-physics", evidence=c.root / "fixture-evidence", backend=c.exe)})
    assert len(replay) == 12
    assert all(r["vertex_count"] == 2 for r in replay)
    for r in replay:
        assert (r["energy_MeV"], r["primary_weight"]) == ((r["event"]%3+1, 0.5) if r["pdg"] == 2212 else (7,0.25))
    for name, text, message in (
        ("bad-surface-shape", surface.replace("shape=sphere", "shape=cylinder"), "requires shape = sphere"),
        ("bad-surface-zero", surface.replace("radius=10 mm", "radius=0 mm"), "positive length"),
        ("bad-surface-halfz", surface+"halfz=1 mm\n", "Surface Sphere"),
        ("bad-surface-position", surface+"position=0,0,0 mm\n", "use center"),
        ("bad-surface-nan", surface.replace("radius=10 mm", "radius=nan mm"), "finite"),
        ("bad-surface-confine", surface+"confine=Det_PV\n", "requires position_type = volume"),
        ("bad-single-multiple", POINT+"multiple_vertex=true\n", "requires [source.<name>]"),
        ("bad-named-global", "[source]\nparticle=gamma\n"+named, "cannot be combined"),
        ("bad-named-intensity", named.replace("intensity=1", "intensity=0"), "positive number"),
        ("bad-named-overflow", named.replace("intensity=1", "intensity=1.7e308").replace("intensity=3", "intensity=1.7e308"), "intensity sum"),
        ("bad-named-phase-space", "[source]\nphase_space_file=history.csv\n"+named, "cannot be combined"),
        ("bad-named-key", named+"multiple_vertex=true\n", "unknown key"),
    ):
        c.run(name, text, reject=message)
    c.run("bad-multiple-boolean", "[source]\nmultiple_vertex=invalid\n"+named, reject="bool")


def physics(c: Cases):
    _, _, baseline = c.run("reference-baseline")
    _, _, replacement = c.run("reference-replace-em", physics="reference=FTFP_BERT\nreplace_modules=livermore\nextra_modules=optical\n")
    before, after = constructors(baseline), constructors(replacement)
    old_em = next(x for x in before if "G4EmStandardPhysics" in x["cpp_type"])
    new_em = next(x for x in after if "G4EmLivermorePhysics" in x["cpp_type"])
    assert old_em["physics_type"] == new_em["physics_type"] > 0
    assert all(x["cpp_type"] != old_em["cpp_type"] and x["name"] != old_em["name"] for x in after)
    assert any("G4OpticalPhysics" in x["cpp_type"] for x in after)
    assert {"Cerenkov", "Scintillation"} <= process_names(replacement, "e-")
    def compton_models(dump):
        # Standard EM also uses Livermore photoelectric/Rayleigh models. Only
        # Compton distinguishes this replacement; support both Geant4 layouts.
        gamma = next(x for x in dump["particles"] if x["name"] == "gamma")
        processes = [p for top in gamma["processes"] for p in (top, *top.get("sub_processes", []))]
        return {model["name"] for process in processes if process["name"] == "compt" for model in process["models"]}
    assert "LivermoreCompton" in compton_models(replacement)
    assert "LivermoreCompton" not in compton_models(baseline)

    _, _, hadronic = c.run("reference-replace-hadronic", physics="reference=FTFP_BERT\nreplace_modules=qgsp_bic\n")
    old_h = next(x for x in before if "G4HadronPhysicsFTFP_BERT" in x["cpp_type"])
    new_h = next(x for x in constructors(hadronic) if "G4HadronPhysicsQGSP_BIC" in x["cpp_type"])
    assert old_h["physics_type"] == new_h["physics_type"] > 0
    assert all(x["cpp_type"] != old_h["cpp_type"] and x["name"] != old_h["name"] for x in constructors(hadronic))
    assert "protonInelastic" in process_names(hadronic, "proton")
    proton_before = next(x for x in baseline["particles"] if x["name"] == "proton")
    proton_after = next(x for x in hadronic["particles"] if x["name"] == "proton")
    assert "Binary" in json.dumps(proton_after) and json.dumps(proton_after) != json.dumps(proton_before)

    manual = "reference=\nmodules=G4EmLivermorePhysics,decay,optical\n"
    _, _, manual_dump = c.run("manual-composition", physics=manual)
    assert any("G4EmLivermorePhysics" in x["cpp_type"] for x in constructors(manual_dump))
    assert {"Cerenkov", "Scintillation"} <= process_names(manual_dump, "e-")
    for mode, config in (("manual", manual), ("reference", "reference=FTFP_BERT\nreplace_modules=livermore\n")):
        for particle in ("proton", "gamma"):
            directory, _, dump = c.run(f"region-{mode}-{particle}", POINT.replace("particle=proton", f"particle={particle}"),
                physics=config, events=4, detector=True, extra="[physics.region.DetRegion]\nmax_step=1 mm\n")
            names = process_names(dump, particle)
            assert ("StepLimiter" in names) == (particle == "proton"), names
            observed = 0
            for path in (directory / "output").glob("trajectories_t*.json"):
                for event in json.loads(path.read_text(encoding="utf-8"))["events"]:
                    track = next(t for t in event["tracks"] if t["parent"] == 0)
                    points = track["points"]
                    lengths = [math.dist(a[:3], b[:3]) for a,b in zip(points, points[1:]) if event["volumes"][int(b[4])] == "Det_PV"]
                    assert lengths
                    if particle == "proton":
                        assert len(lengths) >= 10 and max(lengths) <= 1+1e-6, lengths
                    else:
                        assert len(lengths) == 1 and abs(lengths[0]-10) < 1e-6, lengths
                    observed += 1
            assert observed == 4
    for name, config, message in (
        ("bad-extra-elastic", "reference=FTFP_BERT\nextra_modules=elastic\n", "constructor conflict"),
        ("bad-extra-hadronic", "reference=FTFP_BERT\nextra_modules=qgsp_bic\n", "constructor conflict"),
        ("bad-extra-em", "reference=FTFP_BERT\nextra_modules=livermore\n", "suffix"),
        ("bad-manual-types", "reference=\nmodules=elastic,elastichp\n", "constructor conflict"),
        ("bad-manual-em", "reference=\nem=option4\nmodules=livermore\n", "conflicting manual EM"),
        ("bad-manual-replace", "reference=\nreplace_modules=livermore\n", "requires reference mode"),
        ("bad-replace-twice", "reference=FTFP_BERT\nreplace_modules=livermore,penelope\n", "unique nonzero"),
        ("bad-replace-em-conflict", "reference=FTFP_BERT\nem=option4\nreplace_modules=livermore\n", "conflicts"),
        ("bad-replace-absent", "reference=FTFP_BERT\nreplace_modules=optical\n", "replace_modules"),
        ("bad-replace-biasing", "reference=FTFP_BERT\nreplace_modules=generic_biasing\n", "does not support"),
        ("bad-replace-microelec", "reference=FTFP_BERT\nreplace_modules=microelec\n", "does not support"),
        ("bad-replace-unknown", "reference=FTFP_BERT\nreplace_modules=not_a_constructor\n", "unknown"),
        ("bad-region-step", "reference=FTFP_BERT\n", "must be > 0"),
    ):
        c.run(name, physics=config, detector=True, extra="[physics.region.DetRegion]\nmax_step=-1 mm\n" if name == "bad-region-step" else "", reject=message)


def replacement_macro_cases(c: Cases):
    """P1: reject conflicting later selectors before state/origins can change."""
    em_plan = "reference=FTFP_BERT\nreplace_modules=penelope\n"
    hadron_plan = "reference=FTFP_BERT\nreplace_modules=qgsp_bic\n"
    conflicts = [
        ("set-em", em_plan, "/AIHL/physics/setEM livermore"),
        ("add-module-em", em_plan, "/AIHL/physics/addModule G4EmLivermorePhysics"),
        ("add-hadronic-em", em_plan, "/AIHL/physics/addHadronic livermore"),
        ("add-other-em", em_plan, "/AIHL/physics/addOther livermore"),
        ("add-extra-em", em_plan, "/AIHL/physics/addExtraModule livermore"),
        ("set-reference", em_plan, "/AIHL/physics/setReferenceList FTFP_BERT_LIV"),
        ("set-base-reference", em_plan, "/AIHL/physics/setBaseReferenceList FTFP_BERT_LIV"),
        ("clear-reference", em_plan, "/AIHL/physics/clearReferenceList"),
        ("add-module-hadronic", hadron_plan, "/AIHL/physics/addModule ftfp_bert"),
        ("add-hadronic", hadron_plan, "/AIHL/physics/addHadronic ftfp_bert"),
        ("add-other-hadronic", hadron_plan, "/AIHL/physics/addOther ftfp_bert"),
        ("add-extra-hadronic", hadron_plan, "/AIHL/physics/addExtraModule ftfp_bert"),
    ]
    tail = "/run/initialize\n/run/beamOn 8\n/AIHL/physics/dumpProcesses processes.json\n"
    for name, plan, command in conflicts:
        directory, rows, _ = c.run("replacement-macro-reject-"+name, physics=plan,
            macro_text=command+"\n"+tail, reject="conflicts with configured [physics]/replace_modules")
        # An ordinary command rejection must produce the controlled failure
        # summary; neither native abort nor a warning followed by events passes.
        assert c.receipts[-1]["exit_code"] == 1, c.receipts[-1]
        summary = values(directory / "output/run_summary.txt")
        assert summary["status"] == summary["macro_execution_status"] == "failed", summary
        assert summary["summary_write_status"] == "completed", summary
        assert int(summary["actual_completed_event_count"]) == int(summary["run_count"]) == 0
        assert summary["macro_failure_command"] == command, summary
        assert int(summary["macro_failure_line"]) == 1 and summary["macro_failure_code_available"] == "true"
        assert int(summary["macro_failure_code"]) != 0
        assert summary["effective_physics_reference"] == "FTFP_BERT", summary
        assert summary["effective_physics_reference_origin_kind"] == "main_ini", summary
        assert not rows and not (directory / "processes.json").exists()
        before = json.loads((directory / "output/effective_config_configure.json").read_text(encoding="utf-8"))
        after = json.loads((directory / "output/effective_config_finalization.json").read_text(encoding="utf-8"))
        def physics_values(snapshot):
            return {f["path"]: {k: f[k] for k in ("resolved", "requested", "revision", "origins") if k in f}
                    for f in snapshot["fields"] if f["path"].startswith("/physics/")}
        assert before["revision"] == after["revision"], (name, before["revision"], after["revision"])
        assert physics_values(before) == physics_values(after), name
        print("replacement-macro-reject-"+name, "controlled rejection; prior physics/origins unchanged", flush=True)

    _, _, normal = c.run("replacement-macro-control-no-plan", macro_text="/AIHL/physics/setEM livermore\n"+tail)
    assert any("G4EmLivermorePhysics" in x["cpp_type"] for x in constructors(normal))
    _, _, cuts = c.run("replacement-macro-control-cuts", physics=em_plan,
                       macro_text="/AIHL/physics/setDefaultCut 0.5 mm\n"+tail)
    assert any("G4EmPenelopePhysics" in x["cpp_type"] for x in constructors(cuts))
    assert "PenCompton" in json.dumps(next(x for x in cuts["particles"] if x["name"] == "gamma"))
    _, _, other_category = c.run("replacement-macro-control-other-category", physics=hadron_plan,
                                macro_text="/AIHL/physics/setEM livermore\n"+tail)
    assert any("G4EmLivermorePhysics" in x["cpp_type"] for x in constructors(other_category))
    assert any("G4HadronPhysicsQGSP_BIC" in x["cpp_type"] for x in constructors(other_category))
    _, _, optical = c.run("replacement-macro-control-optical", physics=em_plan,
                         macro_text="/AIHL/physics/addOther optical\n"+tail)
    assert any("G4EmPenelopePhysics" in x["cpp_type"] for x in constructors(optical))
    assert {"Cerenkov", "Scintillation"} <= process_names(optical, "e-")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence-dir", type=Path)
    parser.add_argument("--only-replacement-macros", action="store_true",
                        help="Run the permanent P1 cross-entry regression and controls only")
    args = parser.parse_args()
    executable = os.environ.get("G4USIM_EXE")
    assert executable, "Set G4USIM_EXE to the freshly built backend; no fallback to historical binaries"
    exe = Path(executable).resolve()
    assert exe.is_file(), exe
    root = args.evidence_dir or Path(os.environ.get("G4USIM_TEST_EVIDENCE_DIR", ROOT / "out/collab/j2-sources-physics-runs")) / uuid4().hex
    root = root.resolve()
    root.mkdir(parents=True, exist_ok=False)
    print("J2 evidence:", root, flush=True)
    result, log = invoke(exe, root, ["--capabilities"])
    assert result.returncode == 0, log
    capabilities = json.loads(result.stdout)
    expected = workspace_source_fingerprint()
    write(root / "identity.json", json.dumps({"executable": str(exe), "source_fingerprint": expected,
          "capabilities": capabilities, "executable_sha256": hashlib.sha256(exe.read_bytes()).hexdigest()}, indent=2)+"\n")
    assert capabilities.get("source_fingerprint") == expected, "Stale backend: rebuild current sources before running J2"
    cases = Cases(exe, root)
    if not args.only_replacement_macros:
        sources(cases)
        physics(cases)
    replacement_macro_cases(cases)
    assert workspace_source_fingerprint() == expected, "Source changed during evidence collection; freeze and rerun"
    write(root / "complete.json", json.dumps({"status": "passed", "cases": len(cases.receipts), "source_fingerprint": expected}, indent=2)+"\n")
    print("test_j2_sources_physics: OK", len(cases.receipts), "cases", root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
