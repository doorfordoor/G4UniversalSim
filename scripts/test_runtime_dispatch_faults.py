"""Actual application main exception/finalization paths; no transport claim."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import sys

from run_m0_tests import workspace_source_fingerprint
from test_config_precedence import read_summary

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "gui"))
from g4usim_gui.output.provenance import output_evidence


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_command_cases(executable, evidence, binary_before, source_before):
    """Real Messenger rejection, not injected dispatch; batch and audited csh only."""
    for mode in ("batch", "csh"):
        for reject in (True, False):
            work = evidence / f"source-{mode}-{'reject' if reject else 'positive'}"
            work.mkdir()
            geometry = work / "geometry.ini"
            geometry.write_text("[world]\nshape=box\nsize=1 m,1 m,1 m\nmaterial=G4_Galactic\n", encoding="utf-8")
            source = ("[source.low]\nparticle=proton\nenergy=1 MeV\nposition=0,0,0 mm\ndirection=+z\n"
                      "[source.high]\nparticle=proton\nenergy=3 MeV\nposition=0,0,0 mm\ndirection=+z\n" if reject else
                      "[source]\nparticle=proton\nenergy=1 MeV\nposition=0,0,0 mm\ndirection=+z\n")
            ini = work / "main.ini"
            ini.write_text("[run]\nthreads=1\nseed=123\n[geometry]\ntemplate=hierarchical\nconfig=geometry.ini\n"
                           "[physics]\nreference=FTFP_BERT\n[output]\nformat=csv\n[scoring]\nenabled=false\n" + source, encoding="utf-8")
            commands = "/run/initialize\n/AIHL/source/energy 2 MeV\n/control/echo G4USIM_AFTER_SOURCE_COMMAND\n/run/beamOn 1\n"
            macro = work / "source.mac"
            macro.write_text(commands, encoding="utf-8")
            stdin = work / "stdin.txt"
            stdin.write_text(commands + "exit\n", encoding="utf-8")
            output = work / "output"
            argv = [str(executable), "--config", str(ini), "--output", str(output)]
            argv += ["--macro", str(macro)] if mode == "batch" else ["--ui", "--ui-session", "csh"]
            env = dict(os.environ)
            env.pop("G4USIM_TEST_OUTPUT_FAULT", None)
            env.pop("G4USIM_TEST_RUNTIME_FAULT", None)
            primaries_path = work / "primaries.jsonl"
            env["G4USIM_TEST_PRIMARY_VERTICES"] = str(primaries_path)
            receipt = {"argv": argv, "cwd": str(work), "pid": None, "exit_code": None,
                       "binary_sha256": binary_before, "source_fingerprint": source_before,
                       "inputs_sha256": {f.name: sha(f) for f in (geometry, ini, macro, stdin)},
                       "scope": "real SourceMessenger batch/csh; positive one event, rejection no run"}
            try:
                with stdin.open("rb") as input_stream, (work / "stdout.log").open("wb") as stdout, (work / "stderr.log").open("wb") as stderr:
                    process = subprocess.Popen(argv, cwd=work, env=env, stdin=input_stream if mode == "csh" else subprocess.DEVNULL,
                                               stdout=stdout, stderr=stderr)
                    receipt["pid"] = process.pid
                    (work / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
                    try:
                        process.wait(timeout=180)
                    except subprocess.TimeoutExpired:
                        receipt["timeout"] = True
                        process.kill()
                        process.wait()
                        raise
                    finally:
                        receipt["exit_code"] = process.returncode
            finally:
                receipt["binary_sha256_after"] = sha(executable)
                receipt["artifacts_sha256"] = {p.relative_to(work).as_posix(): sha(p) for p in sorted(work.rglob("*")) if p.is_file() and p.name != "receipt.json"}
                (work / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
            assert receipt["binary_sha256_after"] == binary_before
            assert process.returncode == (1 if reject else 0)
            summary = read_summary(output)
            assert summary["source_fingerprint"] == source_before
            assert summary["program_exit_code"] == str(process.returncode)
            assert summary["summary_write_status"] == "completed"
            stdout = (work / "stdout.log").read_text(encoding="utf-8", errors="replace")
            stderr = (work / "stderr.log").read_text(encoding="utf-8", errors="replace")
            assert "FatalException" not in stdout + stderr and "core dump" not in (stdout + stderr).lower()
            assert ("G4USIM_AFTER_SOURCE_COMMAND" in stdout) == (not reject)
            primary_rows = [json.loads(line) for line in primaries_path.read_text(encoding="utf-8").splitlines()] if primaries_path.exists() else []
            if reject:
                assert not primary_rows
                assert summary["status"] == "failed" and summary["run_count"] == "0"
                assert summary["actual_completed_event_count"] == "0"
                assert "several [source.<name>] sources" in stdout + stderr
                if mode == "batch":
                    assert summary["macro_execution_status"] == "failed"
                    assert Path(summary["macro_failure_file"]).resolve() == macro.resolve()
                    assert summary["macro_failure_line"] == "2"
                    assert summary["macro_failure_command"] == "/AIHL/source/energy 2 MeV"
                    assert summary["macro_failure_code"] == "0" and summary["macro_failure_code_available"] == "false"
                else:
                    assert summary["interactive_command_failure_kind"] == "source"
                    assert "/AIHL/source/energy" in summary["interactive_command_failure_message"]
            else:
                assert summary["status"] == "completed" and summary["run_count"] == "1"
                assert summary["actual_completed_event_count"] == "1"
                assert len(primary_rows) == 1
                assert primary_rows[0]["pdg"] == 2212 and primary_rows[0]["energy_MeV"] == 2
                assert primary_rows[0]["event"] == 0 and primary_rows[0]["vertex_count"] == 1
            record = output_evidence(output)
            assert record.status == "verified"
            assert record.require("run_summary.txt").read_bytes() == (output / "run_summary.txt").read_bytes()


def main():
    executable = Path(os.environ["G4USIM_EXE"]).resolve()
    evidence_root = Path(os.environ["G4USIM_TEST_EVIDENCE_DIR"])
    evidence_root.mkdir(parents=True, exist_ok=True)
    evidence = Path(tempfile.mkdtemp(prefix="runtime-dispatch-", dir=evidence_root))
    binary_before, source_before = sha(executable), workspace_source_fingerprint()
    for mode in ("none", "throw_std", "throw_nonstd"):
        work = evidence / mode
        work.mkdir()
        macro = work / "fault.mac"
        macro.write_text("/control/echo G4USIM_BEFORE_RUNTIME_FAULT\n"
                         "/control/echo G4USIM_TEST_RUNTIME_DISPATCH\n"
                         "/control/echo G4USIM_AFTER_RUNTIME_FAULT\n", encoding="utf-8")
        output = work / "output"
        env = dict(os.environ)
        env.pop("G4USIM_TEST_OUTPUT_FAULT", None)
        env.pop("G4USIM_TEST_RUNTIME_FAULT", None)
        if mode != "none":
            env["G4USIM_TEST_RUNTIME_FAULT"] = mode
        command = [str(executable), "--macro", str(macro), "--output", str(output), "--threads", "1", "--seed", "123"]
        run = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, timeout=120)
        (work / "stdout.log").write_bytes(run.stdout)
        (work / "stderr.log").write_bytes(run.stderr)
        (work / "receipt.json").write_text(json.dumps({"argv": command, "cwd": str(ROOT),
            "fault": mode, "exit_code": run.returncode, "binary_sha256": binary_before,
            "source_fingerprint": source_before, "macro_sha256": sha(macro),
            "stdout_sha256": sha(work / "stdout.log"), "stderr_sha256": sha(work / "stderr.log"),
            "scope": "actual main dispatch exception and finalization; zero transport"}, indent=2), encoding="utf-8")
        assert run.returncode == (0 if mode == "none" else 1), run.stdout + run.stderr
        summary = read_summary(output)
        assert summary["source_fingerprint"] == source_before
        assert summary["program_exit_code"] == str(run.returncode)
        assert b"G4USIM_BEFORE_RUNTIME_FAULT" in run.stdout
        assert (b"G4USIM_AFTER_RUNTIME_FAULT" in run.stdout) == (mode == "none")
        assert summary["macro_execution_status"] == ("completed" if mode == "none" else "failed")
        assert summary["summary_write_status"] == "completed"
        if mode != "none":
            assert summary["status"] == "failed"
            assert Path(summary["macro_failure_file"]).resolve() == macro.resolve()
            assert summary["macro_failure_line"] == "2"
            assert summary["macro_failure_command"] == "/control/echo G4USIM_TEST_RUNTIME_DISPATCH"
            assert summary["macro_failure_code"] == "0"
            assert summary["macro_failure_code_available"] == "false"
            marker = b"Injected runtime dispatch exception" if mode == "throw_std" else b"fatal error: unknown exception"
            assert marker in run.stderr
        # Independently read final artifact registration/hashes after actual process exit.
        record = output_evidence(output)
        assert record.status == "verified"
        assert record.require("run_summary.txt").read_bytes() == (output / "run_summary.txt").read_bytes()
    source_command_cases(executable, evidence, binary_before, source_before)
    assert sha(executable) == binary_before
    assert workspace_source_fingerprint() == source_before
    print("runtime main dispatch/finalization: three dispatch paths and four SourceMessenger batch/csh paths passed")


if __name__ == "__main__":
    main()
