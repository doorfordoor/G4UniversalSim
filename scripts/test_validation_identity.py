"""Exercise runner identity using real Git repos, native fixtures and a wait barrier.

No Geant4 process is used. Set G4USIM_TEST_EVIDENCE_DIR to retain every fixture,
command, log and report. --runner can exercise an archived, unmodified runner.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import runpy
import shlex
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content.encode("utf-8"))


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def invoke(command: list[str], cwd: Path, commands: list[dict]) -> str:
    process = subprocess.run(command, cwd=cwd, capture_output=True, text=True,
                             encoding="utf-8", errors="replace", timeout=60)
    commands.append({"command": command, "cwd": str(cwd), "exit_code": process.returncode,
                     "stdout": process.stdout, "stderr": process.stderr})
    assert process.returncode == 0, commands[-1]
    return process.stdout.strip()


WAIT_CASE = '''import json
import os
from pathlib import Path
import subprocess
import time

root = Path(__file__).resolve().parents[2]
result = subprocess.run([os.environ["G4USIM_EXE"], "--capabilities"],
                        capture_output=True, text=True, check=True)
assert len(json.loads(result.stdout)["source_fingerprint"]) == 64
control = root / "out/control"
control.mkdir(parents=True, exist_ok=True)
(control / "ready").write_text("test reached after preflight", encoding="utf-8")
deadline = time.monotonic() + 30
while not (control / "release").exists():
    if time.monotonic() > deadline:
        raise RuntimeError("identity fixture release timed out")
    time.sleep(0.02)
evidence = Path(os.environ["G4USIM_TEST_EVIDENCE_DIR"])
evidence.mkdir(parents=True, exist_ok=True)
(evidence / "ordinary-output.json").write_text('{"events": 0}', encoding="utf-8")
assert (evidence / "ordinary-output.json").is_file()
print("controlled fixture completed")
'''


def exercise(base: Path, runner: Path, mutation: str) -> dict:
    root = base / mutation / "repo with spaces"
    root.mkdir(parents=True)
    commands: list[dict] = []
    receipt: dict = {"mutation": mutation, "commands": commands, "repo": str(root)}
    try:
        write(root / ".gitignore", "out/\nbuild/\n")
        write(root / ".gitattributes", "* text eol=lf\n")
        write(root / "main.cc", "int source_version = 1;\n")
        write(root / "CMakeLists.txt", "# isolated identity fixture\n")
        write(root / "include/Core/BuildInfo.hh.in", "// fixture\n")
        write(root / "tools/mergeHistograms.cc", "// merge fixture source\n")
        write(root / "gui/smoke_tests/smoke_agent_session.py", WAIT_CASE)
        target = root / "scripts/run_m0_tests.py"
        target.parent.mkdir(parents=True)
        shutil.copyfile(runner, target)
        shutil.copyfile(ROOT / "tools/test_assert_probe.py", root / "tools/test_assert_probe.py")
        module = runpy.run_path(str(target))
        source_hash = module["workspace_source_fingerprint"]()
        merge_hash = sha(root / "tools/mergeHistograms.cc")
        # A real native executable serves both query protocols. It is deliberately
        # tiny and contains no Geant4 code or dependency.
        write(root / "build/fixture.c", '''#include <stdio.h>
#include <string.h>
int main(int argc, char **argv) {
  if (argc > 1 && strcmp(argv[1], "--source-fingerprint") == 0)
    puts("''' + merge_hash + '''");
  else puts("{\\"source_fingerprint\\":\\"''' + source_hash + '''\\"}");
  return 0;
}
''')
        configured = os.environ.get("CXX")
        compiler = (shlex.split(configured, posix=os.name != "nt") if configured else
                    [shutil.which("gcc") or shutil.which("clang") or shutil.which("cl") or ""])
        assert compiler[0] and shutil.which(compiler[0]), "C compiler required for native identity fixtures"
        backend = root / "build" / ("backend.exe" if os.name == "nt" else "backend")
        merge = backend.with_name("merge.exe" if os.name == "nt" else "merge")
        if Path(compiler[0]).stem.lower() == "cl":
            compile_command = compiler + ["/nologo", str(root / "build/fixture.c"), f"/Fe:{backend}"]
        else:
            compile_command = compiler + [str(root / "build/fixture.c"), "-o", str(backend)]
        invoke(compile_command, root / "build", commands)
        shutil.copy2(backend, merge)
        invoke(["git", "init"], root, commands)
        invoke(["git", "config", "user.name", "Identity fixture"], root, commands)
        invoke(["git", "config", "user.email", "identity@example.invalid"], root, commands)
        invoke(["git", "config", "commit.gpgsign", "false"], root, commands)
        invoke(["git", "add", "."], root, commands)
        invoke(["git", "commit", "-m", "initial fixture"], root, commands)
        start_head = invoke(["git", "rev-parse", "HEAD"], root, commands)
        command = [sys.executable, "-B", str(target), "--profile", "static", "--case", "agent_session",
                   "--executable", str(backend), "--merge-executable", str(merge),
                   "--report-root", str(root / "out/reports"), "--fail-on-skip",
                   "--require-tracked-sources"]
        log_path = root.parent / "runner.log"
        environment = os.environ.copy()
        environment.pop("G4USIM_TEST_EVIDENCE_DIR", None)
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        with log_path.open("wb") as stream:
            process = subprocess.Popen(command, cwd=root, env=environment, stdout=stream,
                                       stderr=subprocess.STDOUT)
            ready = root / "out/control/ready"
            try:
                deadline = time.monotonic() + 30
                while not ready.exists() and process.poll() is None and time.monotonic() < deadline:
                    time.sleep(0.02)
                assert ready.exists(), f"runner did not reach wait barrier: {log_path.read_text(errors='replace')}"
                receipt["barrier_reached"] = True
                if mutation == "source":
                    write(root / "main.cc", "int source_version = 2;\n")
                elif mutation == "test":
                    with (root / "gui/smoke_tests/smoke_agent_session.py").open("ab") as script:
                        script.write(b"\n# changed during real execution\n")
                elif mutation == "head":
                    invoke(["git", "commit", "--allow-empty", "-m", "head drift"], root, commands)
                elif mutation in ("backend_binary", "merge_binary"):
                    binary = backend if mutation == "backend_binary" else merge
                    replacement = binary.with_suffix(".replacement")
                    replacement.write_bytes(binary.read_bytes() + b"\nidentity drift\n")
                    shutil.copymode(binary, replacement)
                    os.replace(replacement, binary)
                elif mutation == "source_deleted":
                    (root / "main.cc").unlink()
                elif mutation == "backend_removed":
                    backend.unlink()
                elif mutation == "normal_output":
                    write(root / "out/generated.csv", "ordinary,output\n1,2\n")
                    write(root / "run-output.csv", "untracked ordinary output\n")
            finally:
                write(root / "out/control/release", "continue\n")
                try:
                    process.wait(timeout=40)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=10)
                    raise
        receipt.update(command=command, exit_code=process.returncode, log=str(log_path),
                       log_sha256=sha(log_path), start_head=start_head)
        reports = list((root / "out/reports").glob("*/report.json"))
        assert len(reports) == 1, f"expected one actual report; got {reports}; see {log_path}"
        report_path = reports[0]
        report = json.loads(report_path.read_text(encoding="utf-8"))
        receipt.update(report=str(report_path), report_sha256=sha(report_path),
                       candidate_identity=report.get("candidate_identity"))
        positive = mutation in ("no_drift", "normal_output")
        assert process.returncode == (0 if positive else 1), f"actual runner exit {process.returncode}, mutation={mutation}"
        assert report["version"] == 2
        assert report["results"][0]["status"] == "pass", "keep the actual successful test outcome"
        case = report["results"][0]
        assert sha(Path(case["log"])) == case["log_sha256"]
        assert case["assertions_executed"] >= 2
        identity = report["candidate_identity"]
        assert identity["version"] == 1
        assert identity["start"]["git_head"] == start_head
        assert report["git_head"] == identity["start"]["git_head"]
        assert report["source_fingerprint"] == identity["start"]["source_fingerprint"]
        assert report["tests_content_fingerprint"] == identity["start"]["tests_content_fingerprint"]
        assert identity["start"]["backend_executable"]["sha256"]
        assert identity["start"]["merge_executable"]["sha256"]
        assert report["backend_provenance"] == "source_sha256_manifest_matches_executable"
        if positive:
            assert identity["status"] == "stable"
            assert identity["start"] == identity["end"]
            assert not identity["drift_fields"] and not identity["errors"]
            if mutation == "normal_output":
                assert report["git_dirty"], "normal untracked output may dirty Git without changing candidate"
        else:
            expected = {"source": "source_fingerprint", "test": "tests_content_fingerprint",
                        "head": "git_head", "backend_binary": "backend_executable",
                        "merge_binary": "merge_executable", "source_deleted": "source_fingerprint",
                        "backend_removed": "backend_executable"}[mutation]
            assert expected in identity["drift_fields"], identity
            assert identity["status"] in ("drifted", "unverifiable"), identity
            assert "FAIL candidate identity" in log_path.read_text(encoding="utf-8")
            if mutation == "source_deleted":
                assert identity["errors"], identity
        receipt["status"] = "pass"
    except (AssertionError, KeyError, OSError, ValueError, subprocess.SubprocessError) as error:
        receipt.update(status="fail", error=f"{type(error).__name__}: {error}")
    write(root.parent / "receipt.json", json.dumps(receipt, indent=2, ensure_ascii=False) + "\n")
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runner", type=Path, default=ROOT / "scripts/run_m0_tests.py")
    args = parser.parse_args()
    evidence = os.environ.get("G4USIM_TEST_EVIDENCE_DIR")
    temporary = None if evidence else tempfile.TemporaryDirectory(prefix="g4usim-validation-identity-")
    base = Path(evidence if evidence else temporary.name).resolve()
    # Reusing an evidence path must never overwrite earlier failures or receipts.
    base = base / f"identity-{time.time_ns()}"
    base.mkdir(parents=True)
    scenarios = ("source", "test", "head", "backend_binary", "merge_binary", "no_drift",
                 "normal_output", "source_deleted", "backend_removed")
    try:
        results = [exercise(base, args.runner.resolve(), name) for name in scenarios]
        summary = {"runner": str(args.runner.resolve()), "runner_sha256": sha(args.runner),
                   "scenarios": results, "passed": sum(row["status"] == "pass" for row in results)}
        write(base / "summary.json", json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
        for row in results:
            print(f"{row['status'].upper()} {row['mutation']}: exit={row.get('exit_code')} {row.get('error', '')}")
        print(f"Identity receipts: {base}")
        assert summary["passed"] == len(scenarios), f"{summary['passed']}/{len(scenarios)} identity scenarios passed"
        print("test_validation_identity: OK")
    finally:
        if temporary:
            temporary.cleanup()


if __name__ == "__main__":
    main()
