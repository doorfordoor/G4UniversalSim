"""Real archive -> recoverable install -> probe/run -> verify -> uninstall gate.

Use with the reviewed offline distribution catalog produced by the packaging
commands. This script does not equate a clean process environment with a fresh
OS image; a CI job supplies that independent host boundary.
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
import sys
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "gui"))
from g4usim_gui.core.environment_install import (  # noqa: E402
    _no_links, create_plan, execute_plan, inspect_transaction, load_catalog,
    probe_sdk, uninstall_installation, verify_installation,
)
from g4usim_gui.core.run_result import evaluate_run_result  # noqa: E402


def verify_flow(*, catalog, profile, version, prefix, allowed_root, evidence_root,
                cmake=None, compiler=None, generator=None, application_build=False,
                allow_download=False, exercise_recovery=True):
    evidence = Path(evidence_root).absolute()
    _no_links(evidence)
    evidence.mkdir(parents=True, exist_ok=False)
    report = {"schema": "g4usim_installation_flow_v1", "status": "failed", "profile": profile,
              "commands": [], "scope": "Actual installation/files/runtime on the caller's host; fresh-OS/CI identity is supplied separately"}
    def save(name, value):
        (evidence / name).write_text(json.dumps(value, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    try:
        host = "windows" if os.name == "nt" else platform.system().lower()
        architecture = {"amd64": "x86_64", "arm64": "aarch64"}.get(platform.machine().lower(), platform.machine().lower())
        plan = create_plan(load_catalog(catalog), profile=profile, platform=host, architecture=architecture,
                           version=version, prefix=prefix, allowed_root=allowed_root)
        save("plan.json", plan)
        assert plan["executable"], plan["diagnostics"]
        assert plan.get("geant4_version"), "A real declared Geant4 version is required for this integration gate"
        if profile == "runtime":
            assert plan["release"].get("configuration", {}).get("data_root"), "Runtime acceptance requires bundled matching data"
            assert all(key in plan["release"]["entrypoints"] for key in ("backend", "gui", "python")), "Full runtime entrypoints are required"
        if exercise_recovery:
            cancel = threading.Event()
            first = execute_plan(plan, allow_download=allow_download, cancel=cancel.is_set,
                                 progress=lambda event: cancel.set() if event["stage"] == "acquire" else None)
            save("cancel-receipt.json", first)
            assert first["status"] == "cancelled", first["diagnostics"]
            transaction = inspect_transaction(prefix, allowed_root=allowed_root)
            assert transaction["resumable"] and transaction["plan"]["plan_sha256"] == plan["plan_sha256"]
            command = [getattr(sys, "_base_executable", sys.executable), str(ROOT / "packaging/install_plan.py"),
                       "--output", str(evidence / "restarted-inspection.json"), "inspect", "--prefix", str(prefix),
                       "--allowed-root", str(allowed_root)]
            inspection = subprocess.run(command, capture_output=True, text=True, timeout=120)
            assert inspection.returncode == 0, inspection.stderr
            restarted = json.loads((evidence / "restarted-inspection.json").read_text(encoding="utf-8"))
            assert restarted["resumable"] and restarted["plan"]["plan_sha256"] == plan["plan_sha256"]
            plan = restarted["plan"]
            report["restart_recovery_inspection"] = {"resumable": True, "transaction_id": transaction["receipt"]["transaction_id"],
                                                       "argv": command, "exit_code": inspection.returncode}
        with (evidence / "installation-progress.jsonl").open("w", encoding="utf-8") as progress_log:
            def progress(event):
                progress_log.write(json.dumps(event, ensure_ascii=True) + "\n")
                progress_log.flush()
            installed = execute_plan(plan, allow_download=allow_download, resume=exercise_recovery, progress=progress)
        save("install-receipt.json", installed)
        assert installed["status"] == "published", installed["diagnostics"]
        report["transaction_id"] = installed["transaction_id"]
        report["geant4_version"] = installed["geant4_version"]
        path = Path(prefix)
        if profile == "sdk":
            assert cmake, "Select an actual CMake executable for SDK acceptance"
            sdk = probe_sdk(path, build_directory=Path(allowed_root) / (path.name + "-consumer-build"),
                            cmake=cmake, compiler=compiler, generator=generator, timeout=600)
            save("sdk-consumer.json", sdk)
            assert sdk["status"] == "verified", sdk["diagnostics"]
            if application_build:
                sdk_app = probe_sdk(path, build_directory=Path(allowed_root) / (path.name + "-application-build"),
                                    cmake=cmake, compiler=compiler, generator=generator, timeout=1200, kind="application")
                save("sdk-application.json", sdk_app)
                assert sdk_app["status"] == "verified", sdk_app["diagnostics"]
        else:
            env = {key: value for key, value in os.environ.items() if not key.startswith("G4") and key not in
                   {"GEANT4_DATA_DIR", "LD_LIBRARY_PATH", "PYTHONPATH", "PYTHONHOME", "QT_PLUGIN_PATH", "QT_QPA_PLATFORM_PLUGIN_PATH"}}
            if os.name == "nt":
                system = Path(os.environ.get("SystemRoot", r"C:\Windows"))
                env["PATH"] = os.pathsep.join(map(str, (system / "System32", system)))
            else:
                env["PATH"] = "/usr/bin:/bin"
            env.update(QT_QPA_PLATFORM="offscreen", G4USIM_RECOVERY_DIR=str(evidence / "gui-recovery"))
            def run(stage, argv, timeout=300):
                record = {"stage": stage, "argv": list(map(str, argv)), "cwd": str(evidence), "exit_code": None}
                report["commands"].append(record)
                log = evidence / (stage + ".log")
                with log.open("wb") as stream:
                    result = subprocess.run(record["argv"], cwd=evidence, env=env, stdin=subprocess.DEVNULL,
                                            stdout=stream, stderr=subprocess.STDOUT, timeout=timeout,
                                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                record.update(exit_code=result.returncode, log=str(log))
                assert result.returncode == 0, record
                return log
            backend = path / plan["release"]["entrypoints"]["backend"]
            data_log = run("data-discovery", [backend, "--check-geant4-data"])
            data = json.loads(data_log.read_text(encoding="utf-8"))
            assert data["required_complete"] and all(item["found"] for item in data["datasets"])
            assert Path(data["geant4_data_dir"]) == path / plan["release"]["configuration"]["data_root"]
            (evidence / "geometry.ini").write_text("[world]\nshape=box\nsize=1 m,1 m,1 m\nmaterial=G4_Galactic\n"
                "[volume.Target]\nparent=world\nshape=box\nsize=10 cm,10 cm,1 cm\nmaterial=G4_WATER\nposition=0,0,0\nsensitive=true\n", encoding="utf-8")
            (evidence / "main.ini").write_text("[run]\nthreads=2\nseed=123\n[output]\nformat=both\n[materials]\nfile=" +
                str(path / "config/materials/material.ini") + "\n[geometry]\ntemplate=hierarchical\nconfig=" +
                str(evidence / "geometry.ini") + "\n[physics]\nreference=QGSP_BIC_HP\n[scoring]\nenabled=true\nhits=true\ndose=true\n"
                "[source]\nparticle=neutron\nenergy=2 MeV\nposition_type=point\nposition=0,0,-10 mm\ndirection=+z\n", encoding="utf-8")
            (evidence / "run.mac").write_text("/run/initialize\n/run/beamOn 5\n", encoding="utf-8")
            run("simulation", [backend, "--working-directory", evidence, "--config", evidence / "main.ini",
                               "--macro", evidence / "run.mac", "--output", evidence / "result"], timeout=900)
            outcome = evaluate_run_result(evidence / "result/run_summary.txt", exit_code=0, summary_fresh=True)
            assert outcome.state == "success" and outcome.planned_events == outcome.completed_events == 5, outcome
            helper = path / plan["release"]["entrypoints"]["python"]
            run("root-csv", [helper, path / "scripts/compare_root_csv.py", "--dir", evidence / "result"])
            root_file = evidence / "helper-roundtrip.root"
            source = "import numpy as n,uproot; p=" + repr(str(root_file)) + "; f=uproot.recreate(p); f['probe']={'x':n.array([1.,2.,3.])}; f.close(); r=uproot.open(p); assert list(r['probe']['x'].array(library='np'))==[1.,2.,3.]; r.close()"
            run("root-roundtrip", [helper, "-c", source])
            gui = path / plan["release"]["entrypoints"]["gui"]
            sys.path.insert(0, str(ROOT / "packaging"))
            import freeze_identity
            freeze_identity.verify(gui.parent, root=ROOT, kind="gui", with_3d=True)
            freeze_identity.verify(helper.parent, root=ROOT, kind="python")
            run("frozen-gui", [gui, "--self-test", evidence / "gui-self-test.json"])
            gui_report = json.loads((evidence / "gui-self-test.json").read_text(encoding="utf-8"))
            assert gui_report["ok"] and gui_report["frozen"] and gui_report["plots"] and gui_report["preview3d"], gui_report
            assert Path(gui_report["default_backend"]) == backend
            report["completed_events"] = 5
        verified = verify_installation(path)
        report["verified_files"] = verified["file_count"]
        uninstalled = uninstall_installation(path)
        save("uninstall-receipt.json", uninstalled)
        assert uninstalled["status"] == "uninstalled" and not path.exists(), uninstalled
        report["status"] = "verified"
    except Exception as exc:
        report["error"] = {"type": type(exc).__name__, "code": getattr(exc, "code", None), "message": str(exc)}
    save("flow-report.json", report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--catalog", required=True)
    parser.add_argument("--profile", choices=("runtime", "sdk"), required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--prefix", required=True)
    parser.add_argument("--allowed-root", required=True)
    parser.add_argument("--evidence-root", required=True)
    parser.add_argument("--cmake")
    parser.add_argument("--compiler")
    parser.add_argument("--generator")
    parser.add_argument("--application-build", action="store_true")
    parser.add_argument("--allow-download", action="store_true")
    parser.add_argument("--no-recovery-check", dest="exercise_recovery", action="store_false", default=True)
    report = verify_flow(**vars(parser.parse_args()))
    print(json.dumps({"status": report["status"], "profile": report["profile"], "error": report.get("error")}, ensure_ascii=True))
    return 0 if report["status"] == "verified" else 1


if __name__ == "__main__":
    raise SystemExit(main())
