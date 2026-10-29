"""Independent E6 probes for dormant grammar, disabled rules and case/defaults."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--executable", default=os.environ.get("G4USIM_EXE"))
    parser.add_argument("--baseline", default=os.environ.get("G4USIM_BASELINE_EXE"))
    parser.add_argument("--evidence", type=Path)
    args = parser.parse_args()
    assert args.executable, "G4USIM_EXE or --executable is required"
    executable = Path(args.executable).resolve(strict=True)
    baseline = Path(args.baseline).resolve(strict=True) if args.baseline else None
    probes = (
        ("dormant-malformed-grammar", "[biasing.xs.proton.h.Ioni]\nfactor=nan\n", True),
        ("auto-activates-malformed-grammar", "[modules]\nbiasing=auto\n[biasing.xs.proton.h.Ioni]\nfactor=nan\n", False),
        ("disabled-rule-still-parses-number", "[biasing]\nenabled=true\n[biasing.xs.proton.hIoni]\nenabled=false\nfactor=nan\nvolumes=Target\n", False),
        ("mixed-case-and-derived-precedence", "[FiElD.Coil]\nVoLuMeS=Target\nMaGnEtIc=0,0,0.001 T\nMin_Step=0.001 cm\n[BIASING]\nEnAbLeD=YES\n[BIASING.XS.proton.hIoni]\nVoLuMeS=Target\nFaCtOr=1\nOnLy_PrImArY=YES\nApPlY_To_SeCoNdArIeS=ON\n", True),
    )
    facts = []
    with tempfile.TemporaryDirectory(prefix="g4usim-e6-independent-schema-") as directory:
        work = Path(directory)
        geometry = work / "geometry.ini"
        geometry.write_text("[world]\nshape=box\nsize=100 mm,100 mm,100 mm\nmaterial=G4_Galactic\n[volume.Target]\nparent=world\nshape=box\nsize=20 mm,20 mm,20 mm\nmaterial=G4_WATER\nbias=true\n", encoding="utf-8")
        base = (f"[run]\nthreads=1\n[geometry]\ntemplate=hierarchical\nconfig={geometry.as_posix()}\n"
                "[physics]\nreference=\nmodules=G4EmStandardPhysics_option4\n[source]\npreset=mono_proton\nenergy=2 MeV\nposition=0,0,0 mm\n")
        for name, body, accepted in probes:
            config = work / f"{name}.ini"
            config.write_text(base + body, encoding="utf-8")
            projected = {}
            for label, binary in (("candidate", executable), ("baseline", baseline)):
                if binary is None:
                    continue
                result = subprocess.run([str(binary), "--config", str(config), "--dump-effective-config", "-"],
                                        cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=90)
                combined = result.stdout + result.stderr
                if args.evidence:
                    args.evidence.mkdir(parents=True, exist_ok=True)
                    (args.evidence / f"{name}-{label}.log").write_text(combined, encoding="utf-8", newline="\n")
                assert (result.returncode == 0) == accepted, (label, name, combined[-5000:])
                if not accepted:
                    phrase = "must be [biasing.xs.<particle>.<process>]" if name.startswith("auto-") else "not a finite"
                    assert phrase in combined, (label, name, combined[-3000:])
                    continue
                fields = {item["path"]: item for item in json.loads(result.stdout)["fields"]
                          if item["path"].startswith(("/field/", "/biasing/"))}
                projected[label] = fields
                if name.startswith("dormant"):
                    assert fields["/biasing/enabled"]["resolved"] is False
                    assert not any(path.startswith("/biasing/objects/") for path in fields)
                else:
                    for key, expected in (("min_step", .01), ("delta_chord", .25), ("delta_one_step", .01), ("delta_intersection", .001)):
                        item = fields[f"/field/objects/Coil/{key}"]
                        assert item["unit"] == "mm" and math.isclose(item["resolved"], expected, rel_tol=1e-14)
                    process = next(item for path, item in fields.items() if path.startswith("/biasing/objects/") and path.endswith("/process"))
                    assert process["resolved"] == "hIoni"
                    prefix = process["path"].rsplit("/", 1)[0]
                    assert fields[prefix + "/only_primary"]["resolved"] is False
                    assert fields[prefix + "/apply_to_secondaries"]["resolved"] is True
                    assert fields[prefix + "/max_interactions"]["resolved"] == 5
                    assert fields[prefix + "/min_weight"]["resolved"] == .05
            if accepted and baseline:
                assert projected["candidate"] == projected["baseline"], name
            facts.append({"case": name, "accepted": accepted})
    record = {"candidate_sha256": hashlib.sha256(executable.read_bytes()).hexdigest(),
              "baseline_sha256": hashlib.sha256(baseline.read_bytes()).hexdigest() if baseline else None,
              "cases": facts, "scope": "Configure-only parser/schema compatibility; no transport or physics claim"}
    if args.evidence:
        (args.evidence / "review.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(record, indent=2))


if __name__ == "__main__":
    main()
