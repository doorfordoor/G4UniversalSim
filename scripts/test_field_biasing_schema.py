"""E6 field/biasing inventory and compatibility with the pre-E6 backend.

--component checks the schema API without Geant4. The backend mode executes real
Configure() for positive/negative cases and snapshots, with optional --baseline
comparing the same inputs. --runtime also compares two workers/two real runs.
The transport/physical contracts stay in test_fields_a7 and biasing specialities.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "gui"))
from g4usim_gui.core.config_schema import SCHEMA, check_value, section_spec, spec

SECTIONS = {
    "field": {"magnetic", "electric", "magnetic_map", "electric_map", "min_step", "delta_chord", "delta_one_step", "delta_intersection"},
    "field.<name>": {"magnetic", "electric", "magnetic_map", "electric_map", "volumes", "min_step", "delta_chord", "delta_one_step", "delta_intersection"},
    "biasing": {"enabled"},
    "biasing.xs": {"particles", "processes", "volumes", "factor", "only_primary", "apply_to_secondaries", "min_weight", "max_interactions"},
    "biasing.xs.<particle>.<process>": {"particle", "process", "name", "enabled", "factor", "only_primary", "apply_to_secondaries", "min_weight", "max_interactions", "volumes"},
}


def component() -> None:
    source = json.loads((ROOT / "schema/config_schema.json").read_text(encoding="utf-8"))
    assert source["schema"] == "g4usim_config_schema_v1"
    for section, keys in SECTIONS.items():
        descriptor = SCHEMA["main_ini"][section]
        assert set(descriptor["keys"]) == keys, section
        assert descriptor["migrated"] and not descriptor["independent"], section
        assert descriptor["gui"]["editable"] == "external_only", section
        assert descriptor["parser"] and descriptor["validation"] and descriptor["rules"], section
        assert section not in source["excluded"]["main_ini"], section
    assert spec("field.Magnet", "volumes").type == "structured"
    assert spec("field", "volumes") is None
    assert not section_spec("field.a.b")
    assert not section_spec("biasing.xs.proton.hIoni.extra")
    assert spec("biasing.xs.proton.hIoni", "factor").default == "1.0"
    assert spec("biasing.xs.proton.hIoni", "name").default is None
    assert spec("biasing", "enabled").default == "false"
    for key, default in (("min_step", "0.01"), ("delta_chord", "0.25"), ("delta_one_step", "0.01"), ("delta_intersection", "0.001")):
        assert spec("field", key).default == default
        assert check_value("field", key, "1 um") is None
        for bad in ("0", "-1 mm", "nan", "inf", "1e308 m", ""):
            assert check_value("field", key, bad) is not None, (key, bad)
    for section in ("biasing.xs", "biasing.xs.proton.hIoni"):
        for key, good, bad in (("factor", "0.001", "0"), ("min_weight", "0", "-1"), ("max_interactions", "-1", "-2")):
            assert check_value(section, key, good) is None
            assert check_value(section, key, bad) is not None
            for nonfinite in ("nan", "inf", "1e999"):
                assert check_value(section, key, nonfinite) is not None
        assert check_value(section, "only_primary", "YES") is None
        assert check_value(section, "apply_to_secondaries", "maybe") is not None
    for section, key in (("field", "magnetic"), ("field.Magnet", "volumes"), ("biasing.xs", "particles")):
        rejected = False
        try:
            check_value(section, key, "unvalidated contextual text")
        except ValueError:
            rejected = True
        assert rejected, (section, key)
    version = spec("general", "schema_version")
    assert version.default == "1" and version.data["allowed"] == ["1"]
    assert version.data["gui"]["editable"] == "external_only"
    assert check_value("general", "schema_version", "1") is None
    for bad in ("", "01", "+1", "1.0", "2", "version1"):
        assert check_value("general", "schema_version", bad) is not None
    generated = subprocess.run([sys.executable, "-B", str(ROOT / "scripts/generate_config_schema.py"), "--check"],
                               cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
    assert generated.returncode == 0, generated.stdout + generated.stderr
    print("component: field/biasing scalar, contextual and inventory boundaries passed")


def cases() -> list[tuple[str, str, bool, str]]:
    gate = "[biasing]\nenabled=true\n"
    process = "[biasing.xs.proton.hIoni]\nvolumes=Target\n"
    legacy = "[biasing.xs]\nparticles=proton\nprocesses=hIoni\nvolumes=Target\n"
    result = [
        ("absent", "", True, ""),
        ("uniform-b", "[field]\nmagnetic=0,0,1 T\n", True, ""),
        ("uniform-e-b", "[field]\nelectric=1,0,0 V/cm\nmagnetic=0 mT,0,1 T\n", True, ""),
        ("field-map", "[field]\nmagnetic_map=field.csv\n", True, ""),
        ("electric-map", "[field]\nelectric_map=electric.csv\n", True, ""),
        ("local", "[field.Magnet]\nvolumes=Target\nmagnetic=0,0,1 T\n", True, ""),
        ("precision", "[field]\nmagnetic=0,0,1 T\nmin_step=1 um\ndelta_chord=.2 mm\ndelta_one_step=.02 mm\ndelta_intersection=.002 mm\n", True, ""),
        ("field-both-map", "[field]\nmagnetic=0,0,1 T\nmagnetic_map=field.csv\n", False, "not both"),
        ("field-global-volumes", "[field]\nmagnetic=0,0,1 T\nvolumes=Target\n", False, "only valid in [field.<name>]"),
        ("field-no-volumes", "[field.Local]\nelectric=1,0,0 V/m\n", False, "local fields need volumes"),
        ("field-empty-volumes", "[field.Local]\nelectric=1,0,0 V/m\nvolumes= , \n", False, "local fields need volumes"),
        ("field-missing-volume", "[field.Local]\nelectric=1,0,0 V/m\nvolumes=Missing\n", False, "not a volume"),
        ("field-no-source", "[field]\nmin_step=1 mm\n", False, "needs magnetic"),
        ("field-bad-name", "[field.a.b]\nelectric=1,0,0 V/m\nvolumes=Target\n", False, "must be [field.<name>]"),
        ("field-unit-case", "[field]\nmagnetic=0,0,1 Tesla\n", False, "unknown magnetic field unit"),
        ("field-short-vector", "[field]\nmagnetic=0,1 T\n", False, "expected 3 field components"),
        ("field-unknown", "[field]\nmagnetic=0,0,1 T\nstrength=2\n", False, "unknown key [field]/strength"),
        ("bias-defaults", gate + process, True, ""),
        ("bias-boundaries", gate + process + "factor=.001\nmin_weight=0\nmax_interactions=-1\n", True, ""),
        ("bias-secondary-precedence", gate + process + "only_primary=true\napply_to_secondaries=true\n", True, ""),
        ("bias-name-empty", gate + process + "name=\n", True, ""),
        ("bias-overrides", gate + "[biasing.xs.A.a]\nparticle=proton\nprocess=hIoni\nvolumes=Target\n", True, "overrides"),
        ("bias-legacy", gate + legacy, True, ""),
        ("bias-dormant-absent", "[biasing.xs.proton.hIoni]\nfactor=nan\n", True, ""),
        ("bias-dormant-false", "[biasing]\nenabled=false\n[biasing.xs.proton.hIoni]\nfactor=nan\n", True, ""),
        ("bias-unknown-warning", gate + process + "faktor=2\n", True, "faktor"),
        ("bias-bad-section", gate + "[biasing.xs.proton.h.Ioni]\nfactor=1\n", False, "must be [biasing.xs.<particle>.<process>]"),
        ("bias-particle-empty", gate + process + "particle=\n", False, "particleName"),
        ("bias-process-empty", gate + process + "process=\n", False, "processName"),
        ("bias-auto", "[modules]\nbiasing=auto\n" + process, True, ""),
        ("bias-on", "[modules]\nbiasing=on\n" + process, True, ""),
        ("bias-auto-false", "[modules]\nbiasing=auto\n[biasing]\nenabled=false\n" + process, False, ""),
        ("bias-off-active", "[modules]\nbiasing=off\n" + gate + process, False, ""),
        ("bias-auto-incomplete", "[modules]\nbiasing=auto\n[biasing.xs]\nparticles=proton\n", False, "complete legacy"),
    ]
    for key in ("min_step", "delta_chord", "delta_one_step", "delta_intersection"):
        for value in ("0", "-1 mm", "nan", "1e308 m"):
            result.append((f"field-{key}-{value}", f"[field]\nmagnetic=0,0,1 T\n{key}={value}\n", False, ""))
    for key, values in (("factor", ("0", "-1", "inf", "nan", "1e999")), ("min_weight", ("-1", "nan")), ("max_interactions", ("-2", "1.0", "2147483648"))):
        for value in values:
            result.append((f"bias-{key}-{value}", gate + process + f"{key}={value}\n", False, ""))
    return result


def backend(exe: Path, baseline: Path | None, runtime: bool, evidence: Path | None) -> None:
    assert exe.is_file(), exe
    if baseline:
        assert baseline.is_file(), baseline
    records = []
    with tempfile.TemporaryDirectory(prefix="g4usim-e6-schema-") as temp:
        work = Path(temp)
        geometry = work / "geometry.ini"
        geometry.write_text("[world]\nshape=box\nsize=100 mm,100 mm,100 mm\nmaterial=G4_Galactic\n[volume.Target]\nparent=world\nshape=box\nsize=20 mm,20 mm,20 mm\nmaterial=G4_WATER\nbias=true\n", encoding="utf-8")
        for filename, kind, field_units in (("field.csv", "B", "T"), ("electric.csv", "E", "V/m")):
            lines = [f"x_mm,y_mm,z_mm,{kind}x_{field_units},{kind}y_{field_units},{kind}z_{field_units}"]
            lines += [f"{x},{y},{z},0,0,1" for x in (-50, 50) for y in (-50, 50) for z in (-50, 50)]
            (work / filename).write_text("\n".join(lines) + "\n", encoding="utf-8")
        base = (f"[run]\nthreads=2\nseed=12345\n[geometry]\ntemplate=hierarchical\nconfig={geometry.as_posix()}\n"
                "[physics]\nreference=\nmodules=G4EmStandardPhysics_option4\n[source]\npreset=mono_proton\nenergy=2 MeV\nposition=0,0,0 mm\n")

        def invoke(binary: Path, ini: Path, args: list[str]):
            completed = subprocess.run([str(binary), "--config", str(ini), *args], cwd=ROOT, capture_output=True,
                                       text=True, encoding="utf-8", errors="replace", timeout=120)
            return completed, completed.stdout + completed.stderr

        def save_log(name: str, label: str, log: str) -> None:
            if evidence:
                folder = evidence.parent / "logs"
                folder.mkdir(parents=True, exist_ok=True)
                safe = re.sub(r"[^A-Za-z0-9_.-]", "_", name)
                (folder / f"{safe}-{label}.log").write_text(log, encoding="utf-8", newline="\n")

        def diagnostics(log: str) -> list[str]:
            # Stream interleaving changes line placement, not the diagnostic facts.
            return sorted(line.strip() for line in log.splitlines()
                          if "[ConfigWarning]" in line or "[BiasingManager] warning:" in line
                          or "fatal error:" in line)

        for index, (name, body, accepted, expected) in enumerate(cases()):
            ini = work / f"case-{index}.ini"
            ini.write_text(base + body, encoding="utf-8")
            result, log = invoke(exe, ini, ["--inspect-run"])
            save_log(name, "candidate", log)
            assert (result.returncode == 0) == accepted, (name, result.returncode, log[-3000:])
            assert not expected or expected in log, (name, expected, log[-3000:])
            if baseline:
                old, old_log = invoke(baseline, ini, ["--inspect-run"])
                save_log(name, "baseline", old_log)
                assert old.returncode == result.returncode, (name, old.returncode, result.returncode)
                assert diagnostics(old_log) == diagnostics(log), (name, diagnostics(old_log), diagnostics(log))
                if accepted:
                    assert json.loads(old.stdout)["initial_configuration"] == json.loads(result.stdout)["initial_configuration"], name
            if accepted:
                dump, dump_log = invoke(exe, ini, ["--dump-effective-config", "-"])
                assert dump.returncode == 0, (name, dump_log[-3000:])
                fields = {f["path"]: f for f in json.loads(dump.stdout)["fields"]
                          if f["path"].startswith(("/field/", "/biasing/"))}
                assert fields, name
                if baseline:
                    old_dump, old_dump_log = invoke(baseline, ini, ["--dump-effective-config", "-"])
                    assert old_dump.returncode == 0, (name, old_dump_log[-3000:])
                    old_fields = {f["path"]: f for f in json.loads(old_dump.stdout)["fields"]
                                  if f["path"].startswith(("/field/", "/biasing/"))}
                    assert old_fields == fields, (name, old_fields, fields)
            records.append(dict(name=name, accepted=accepted, exit_code=result.returncode, diagnostics=diagnostics(log)))
        if runtime:
            macro = work / "runs.mac"
            macro.write_text("/run/beamOn 4\n/run/beamOn 4\n", encoding="utf-8")
            ini = work / "runtime.ini"
            runtime_base = base.replace("preset=mono_proton", "particle=e-")
            ini.write_text(runtime_base + "direction=+x\n[output]\nformat=csv\n[field]\nmagnetic=0,0,0.01 T\n[biasing]\nenabled=true\n[biasing.xs.e-.eIoni]\nfactor=2\nvolumes=Target\nonly_primary=false\napply_to_secondaries=true\nmin_weight=0\nmax_interactions=-1\n", encoding="utf-8")
            summaries = []
            for label, binary in (("candidate", exe), *(([("baseline", baseline)]) if baseline else [])):
                output = work / label
                result, log = invoke(binary, ini, ["--macro", str(macro), "--output", str(output)])
                save_log("runtime", label, log)
                assert result.returncode == 0, (label, log[-3000:])
                summary = {key.strip(): value.strip()
                           for line in (output / "run_summary.txt").read_text(encoding="utf-8").splitlines()
                           if "=" in line for key, value in [line.split("=", 1)]}
                assert summary["status"] == "completed" and summary["run_count"] == "2", (label, summary)
                assert summary["actual_completed_event_count"] == "8", (label, summary)
                assert summary["biasing_worker_coverage_complete"] == "true", (label, summary)
                assert summary["biasing_worker_evidence_count"] == summary["biasing_expected_worker_evidence_count"] == "4", (label, summary)
                receipts = [json.loads(line.split("[G4USimBiasing] ", 1)[1]) for line in log.splitlines()
                            if "[G4USimBiasing] " in line]
                assert len(receipts) == 4, (label, receipts)
                assert {(r["run_id"], r["thread_id"]) for r in receipts} == {(run, thread) for run in range(2) for thread in range(2)}, receipts
                assert all(r["operators"] == r["matched_rules"] == 1 and r["tls_verified"]
                           and r["end_run_completed"] and not r["failed"] for r in receipts), receipts
                assert sum(r["proposals"] for r in receipts) > 0, receipts
                # Worker event distribution is intentionally unconstrained. Compare
                # the completed binding receipts, not schedule-dependent counters.
                stable = ("run_id", "thread_id", "operators", "matched_rules", "tls_verified", "end_run_completed", "failed")
                facts = sorted([{k: r[k] for k in stable} for r in receipts], key=lambda r: (r["run_id"], r["thread_id"]))
                summaries.append(facts)
            if baseline:
                assert summaries[0] == summaries[1], summaries
            records.append(dict(name="runtime-two-workers-two-runs", completed_events=8, biasing_facts=summaries[0]))
        if evidence:
            evidence.parent.mkdir(parents=True, exist_ok=True)
            evidence.write_text(json.dumps(dict(executable=str(exe), baseline=str(baseline) if baseline else None,
                                                cases=records), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            assert evidence.is_file()
    print(f"backend: {len(records)} field/biasing cases passed" + (" with pre-E6 differential comparison" if baseline else ""))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--component", action="store_true")
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--runtime", action="store_true")
    parser.add_argument("--evidence", type=Path)
    args = parser.parse_args()
    component()
    if not args.component:
        exe = Path(os.environ["G4USIM_EXE"]).resolve()
        backend(exe, args.baseline.resolve() if args.baseline else None, args.runtime, args.evidence)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
