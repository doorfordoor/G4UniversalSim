"""Real Geant4 checks for M0-3E target-process and lifecycle contracts."""

from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EXE = ROOT / "build_vs2026" / "Release" / "G4UniversalSim.exe"
SOURCE = ROOT / "macros" / "run_biasing_process_level_smoke.mac"
LEGACY = ROOT / "macros" / "run_biasing.mac"


def facts(output: Path) -> dict[str, str]:
    summary = output / "run_summary.txt"
    assert summary.is_file(), f"Missing summary: {summary}"
    values: dict[str, str] = {}
    for line in summary.read_text(encoding="utf-8").splitlines():
        if " = " in line:
            key, value = line.split(" = ", 1)
            values[key] = value
    return values


def main() -> int:
    executable = Path(os.environ.get("G4USIM_EXE", str(DEFAULT_EXE)))
    if not executable.is_file():
        raise SystemExit(f"Executable not found: {executable}")
    source = SOURCE.read_text(encoding="utf-8")
    with tempfile.TemporaryDirectory(prefix="g4usim-m03e-") as directory:
        temp = Path(directory)

        def run(label: str, macro_text: str, threads: int = 1,
                interactive: bool = False) -> tuple[int, str, dict[str, str]]:
            macro = temp / f"{label}.mac"
            macro.write_text(macro_text, encoding="utf-8")
            output = temp / label
            command = [str(executable), "--macro", str(macro), "--output", str(output),
                       "--threads", str(threads)]
            if interactive:
                command.append("--ui")
            completed = subprocess.run(
                command,
                cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace",
                timeout=120, check=False,
            )
            log = completed.stdout + completed.stderr
            if not (output / "run_summary.txt").is_file():
                raise AssertionError(f"{label} did not produce a summary (exit={completed.returncode}):\n{log[-6000:]}")
            return completed.returncode, log, facts(output)

        code, log, result = run("valid", source)
        assert code == 0, log[-6000:]
        assert result["status"] == "completed" and result["actual_completed_event_count"] == "20", result
        assert result["biasing_process_match_status"] == "validated", result
        assert result["biasing_matched_process_rule_count"] == "1", result
        assert result["biasing_effect_observed"] == "unknown", result

        code, log, result = run("invalid", source.replace("eIoni", "notARealProcess"))
        assert code != 0, "Invalid target process was accepted"
        assert "notARealProcess" in log and "particle 'e-'" in log and "eIoni" in log, log[-6000:]
        assert result["status"] == "failed" and result["run_count"] == "0", result
        assert result["macro_failure_command"] == "/run/initialize", result
        assert result["macro_failure_code_available"] == "false", result
        assert result["biasing_matched_process_rule_count"] == "0", result

        code, log, result = run("implicit_initialize", source.replace("/run/initialize\n", ""))
        assert code == 0 and result["biasing_process_match_status"] == "validated", log[-6000:]
        assert result["actual_completed_event_count"] == "20", result

        code, log, result = run("mt", source, threads=2)
        assert code == 0 and result["biasing_matched_process_rule_count"] == "1", log[-6000:]
        assert result["actual_completed_event_count"] == "20", result

        multiple = source.replace("/run/beamOn 20", "/run/beamOn 2\n/run/beamOn 3")
        code, log, result = run("two_runs", multiple)
        assert code == 0, log[-6000:]
        assert (result["run_count"], result["planned_event_count"], result["actual_completed_event_count"]) == ("2", "5", "5"), result
        assert result["biasing_matched_process_rule_count"] == "1", result

        rebuilt = source.replace("/run/beamOn 20", "/run/physicsModified\n/run/initialize\n/run/beamOn 3")
        code, log, result = run("reinitialize_physics", rebuilt)
        assert code == 0, log[-6000:]
        assert result["biasing_process_match_status"] == "validated", result
        assert result["actual_completed_event_count"] == "3", result

        unsafe_rebuild = source.replace("/run/beamOn 20", "/run/reinitializeGeometry\n/run/initialize\n/run/beamOn 3")
        code, log, result = run("reinitialize_geometry", unsafe_rebuild)
        assert code != 0 and "not safe in this lifecycle" in log, log[-6000:]
        assert result["status"] == "failed" and result["run_count"] == "0", result
        assert result["macro_failure_command"] == "/run/reinitializeGeometry", result
        assert result["macro_failure_code_available"] == "false", result

        code, log, result = run("interactive_bias_macro", source, interactive=True)
        assert code != 0 and "Interactive XS biasing macro mutation" in log, log[-6000:]
        assert result["status"] == "failed" and result["run_count"] == "0", result
        assert result["macro_execution_status"] == "preflight_failed", result
        assert result["macro_failure_command"] == "/AIHL/biasing/enable true", result

        interactive_config = temp / "interactive_bias.ini"
        interactive_config.write_text(
            (ROOT / "config" / "main.ini").read_text(encoding="utf-8").replace(
                "[biasing]\nenabled = false", "[biasing]\nenabled = true"),
            encoding="utf-8",
        )
        assert "[biasing]\nenabled = true" in interactive_config.read_text(encoding="utf-8")
        config_output = temp / "interactive_bias_config"
        completed = subprocess.run(
            [str(executable), "--config", str(interactive_config), "--ui",
             "--output", str(config_output)],
            cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=120, check=False,
        )
        assert completed.returncode != 0, completed.stdout + completed.stderr
        assert "XS biasing is not supported in an interactive session" in completed.stdout + completed.stderr
        config_result = facts(config_output)
        assert config_result["status"] == "failed" and config_result["run_count"] == "0", config_result

        for particle, process in (("proton", "protonInelastic"), ("neutron", "neutronInelastic")):
            variant = source.replace("eIoni", process).replace("e-", particle)
            code, log, result = run(particle, variant)
            assert code == 0, f"{particle}/{process}:\n{log[-6000:]}"
            assert result["biasing_process_match_status"] == "validated", result
            assert result["actual_completed_event_count"] == "20", result

        late_change = source.replace("/run/beamOn 20", "/AIHL/biasing/xs/addRule e- eBrem\n/run/beamOn 20")
        code, log, result = run("late_mutation", late_change)
        assert code != 0 and "after kernel initialization" in log, log[-6000:]
        assert result["status"] == "failed" and result["run_count"] == "0", result
        assert result["macro_failure_code_available"] == "false", result

        legacy = LEGACY.read_text(encoding="utf-8").replace("/run/beamOn 100", "/run/beamOn 3")
        code, log, result = run("legacy", legacy)
        assert code == 0, log[-6000:]
        assert result["biasing_matched_process_rule_count"] == "1", result
        assert log.count("Legacy particle-level XS bias syntax is used") == 1, log[-6000:]
        assert log.count("[BiasingMessenger] Biasing configuration changed") == 1, log[-6000:]

        # R14: omitted particle/process keys use the original section spelling,
        # including case-sensitive Geant4 process names (the documented syntax).
        for particle, process in (("proton", "hIoni"), ("proton", "protonInelastic"), ("e-", "eIoni")):
            for explicit_bad in (False, True):
                label = f"section_{particle}_{process}_{explicit_bad}"
                ini = temp / f"{label}.ini"
                ini.write_text(
                    "[run]\nthreads=2\n[output]\nformat=csv\n"
                    f"[geometry]\ntemplate=simple_box\nconfig={(ROOT / 'config/geometry/hit_smoke_box.ini').as_posix()}\n"
                    "[physics]\nreference=FTFP_BERT_EMZ\n[scoring]\nenabled=false\n"
                    f"[source]\nparticle={particle}\nenergy=1 MeV\nposition=0,0,-9 mm\ndirection=+z\n"
                    f"[biasing]\nenabled=true\n[biasing.xs.{particle}.{process}]\nfactor=2\nvolumes=Target\n"
                    + ("process=notARealProcess\n" if explicit_bad else ""), encoding="utf-8")
                macro = temp / f"{label}.mac"
                macro.write_text("/run/initialize\n/run/beamOn 2\n", encoding="utf-8")
                output = temp / label
                result = subprocess.run([str(executable), "--config", str(ini), "--macro", str(macro),
                                         "--output", str(output)], cwd=ROOT, capture_output=True,
                                        text=True, errors="replace", timeout=120)
                summary = facts(output)
                if explicit_bad:
                    assert result.returncode != 0 and summary["status"] == "failed"
                    assert "notARealProcess" in result.stdout + result.stderr
                else:
                    assert result.returncode == 0, result.stdout + result.stderr
                    assert summary["status"] == "completed" and summary["actual_completed_event_count"] == "2"
                    assert summary["biasing_process_match_status"] == "validated"

    print("M0-3E biasing target contract regression passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
