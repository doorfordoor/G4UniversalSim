"""R29: same-run native mesh / project tallies use the same pre-step weight."""
from __future__ import annotations

import argparse
import contextlib
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
EXE = Path(os.environ.get("G4USIM_EXE", ROOT / "out/build-effective/Release/G4UniversalSim.exe"))


def rows(path: Path):
    with path.open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def total(records, column: str, scale: float = 1.0):
    values = [float(row[column]) * scale for row in records]
    # All compared outputs use setprecision(12). For each nonzero value,
    # half a unit in its twelfth significant digit bounds decimal rounding.
    decimal_error = math.fsum(0.5 * 10.0 ** (math.floor(math.log10(abs(value))) - 11)
                             for value in values if value)
    accumulation_error = 32 * sys.float_info.epsilon * max(1, len(values)) * math.fsum(abs(v) for v in values)
    return math.fsum(values), decimal_error + accumulation_error


def run_case(work: Path, threads: int, factor: float, baseline: bool):
    folder = work / f"threads{threads}-factor{factor}"
    folder.mkdir()
    geometry = folder / "geometry.ini"
    geometry.write_text("[world]\nshape=box\nsize=100 mm,100 mm,100 mm\nmaterial=G4_Galactic\n"
                        "[volume.Target]\nparent=world\nshape=box\nsize=10 mm,10 mm,10 mm\n"
                        "material=G4_Pb\nsensitive=true\nbias=true\n", encoding="utf-8")
    config = folder / "main.ini"
    config.write_text(f"[run]\nthreads={threads}\nseed=74123\n[output]\nformat=csv\n"
                      f"[geometry]\ntemplate=hierarchical\nconfig={geometry.as_posix()}\n"
                      "[physics]\nreference=FTFP_BERT\nbiasing=true\ndefault_cut=0.1 mm\n"
                      "[scoring]\nenabled=true\nhits=true\nevent_edep=true\nedep=true\ndose=true\n"
                      "fluence=true\nauto_create_default_scorers=true\n"
                      "[source.electron]\nparticle=e-\nenergy=10 MeV\nposition_type=point\nposition=0,0,0 mm\ndirection=+z\n"
                      "[source.photon]\nparticle=gamma\nenergy=5 MeV\nposition_type=point\nposition=1,0,0 mm\ndirection=+z\n"
                      f"[biasing]\nenabled=true\n[biasing.xs.e-.eBrem]\nfactor={factor}\nvolumes=Target\n",
                      encoding="utf-8")
    macro = folder / "run.mac"
    macro.write_text("/score/create/boxMesh native\n/score/mesh/boxSize 5 5 5 mm\n/score/mesh/nBin 1 1 1\n"
                     "/score/quantity/energyDeposit edep MeV\n/score/quantity/cellFlux flux\n/score/close\n"
                     "/gps/source/multiplevertex true\n/run/initialize\n/run/beamOn 40\n", encoding="utf-8")
    output = folder / "output"
    completed = subprocess.run([str(EXE), "--config", str(config), "--macro", str(macro), "--output", str(output)],
                               cwd=folder, capture_output=True, text=True, errors="replace", timeout=240)
    log = completed.stdout + completed.stderr
    (folder / "run.log").write_text(log, encoding="utf-8")
    assert completed.returncode == 0, (completed.returncode, log[-4000:])
    facts = dict(line.split(" = ", 1) for line in (output / "run_summary.txt").read_text(encoding="utf-8").splitlines() if " = " in line)
    assert facts["status"] == "completed" and facts["actual_completed_event_count"] == "40", facts
    assert facts["biasing_worker_validation_status"] == "validated", facts
    hits = [row for path in output.glob("hits_t*.csv") for row in rows(path)]
    doses = [row for path in output.glob("dose_volume_summary_t*.csv") for row in rows(path)]
    fluences = [row for path in output.glob("fluence_volume_summary_t*.csv") for row in rows(path)]
    events = [row for path in output.glob("event_edep_t*.csv") for row in rows(path)]
    mesh = rows(output / "scoring_mesh.csv")
    native_edep = [row for row in mesh if row["mesh"] == "native" and row["quantity"] == "edep"]
    native_flux = [row for row in mesh if row["mesh"] == "native" and row["quantity"] == "flux"]
    assert hits and doses and fluences and native_edep and native_flux
    assert all(row["volume"] == "Target_PV" for row in hits), {r["volume"] for r in hits}
    assert any(int(row["parentID"]) > 0 for row in hits), "secondary track coverage missing"
    proposals = sum(int(value) for key, value in facts.items() if key.startswith("biasing_worker_") and key.endswith("_proposals"))
    assert proposals > 0, facts
    if factor != 1:
        assert any(not math.isclose(float(row["weight"]), 1.0, rel_tol=1e-12) for row in hits), "nonunit biased weights missing"
    else:
        assert all(math.isclose(float(row["weight"]), 1.0, rel_tol=1e-12) for row in hits)
    raw_length = total(fluences, "raw_track_length_mm")
    positive_step_length = total(hits, "stepLength_mm")
    assert raw_length[0] > positive_step_length[0] + raw_length[1] + positive_step_length[1], "zero-deposition transport branch not exercised"
    hit_products = [dict(weighted=str(float(row["edep_MeV"]) * float(row["weight"]))) for row in hits]
    comparisons = {
        "weighted_edep_vs_native": (total(doses, "weighted_edep_MeV"), total(native_edep, "sum")),
        "weighted_fluence_vs_native": (total(fluences, "weighted_fluence_mm-2"), total(native_flux, "sum", .01)),
        "event_edep_vs_dose": (total(events, "weighted_edep_MeV"), total(doses, "weighted_edep_MeV")),
        "hits_vs_dose": (total(hit_products, "weighted"), total(doses, "weighted_edep_MeV")),
    }
    mismatches = []
    receipt = {"threads": threads, "factor": factor, "proposals": proposals,
               "secondary_hit_rows": sum(int(row["parentID"]) > 0 for row in hits), "comparisons": {}}
    for label, (project, reference) in comparisons.items():
        # Two independently rounded input fields enter each reconstructed hit
        # product, in addition to its displayed product's own rounding budget.
        tolerance = project[1] + reference[1]
        if label == "hits_vs_dose":
            tolerance += 1e-11 * abs(project[0])
        difference = abs(project[0] - reference[0])
        receipt["comparisons"][label] = {"project": project[0], "reference": reference[0],
                                           "difference": difference, "rounding_bound": tolerance}
        if difference > tolerance:
            mismatches.append(label)
        if not baseline or "native" not in label:
            assert difference <= tolerance, (label, receipt["comparisons"][label])
    receipt["mismatches"] = mismatches
    (folder / "receipt.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    print(f"threads={threads} factor={factor}: mismatches={mismatches}")
    return receipt


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", action="store_true")
    parser.add_argument("--work", type=Path)
    args = parser.parse_args()
    assert EXE.is_file(), EXE
    with contextlib.ExitStack() as stack:
        work = args.work.resolve() if args.work else Path(stack.enter_context(tempfile.TemporaryDirectory(prefix="g4usim-step-weight-")))
        work.mkdir(parents=True, exist_ok=True)
        receipts = [run_case(work, threads, factor, args.baseline) for threads in (1, 2) for factor in (.1, 1.0, 10.0)]
        if args.baseline:
            assert any(row["mismatches"] for row in receipts if row["factor"] != 1), "baseline did not reproduce the weight mismatch"
        report = {"executable": str(EXE.resolve()), "exe_sha256": hashlib.sha256(EXE.read_bytes()).hexdigest(),
                  "baseline": args.baseline, "cases": receipts}
        (work / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("biasing step weight: completed (same-run native primitive comparison; not a global unbiasedness benchmark)")


if __name__ == "__main__":
    main()
