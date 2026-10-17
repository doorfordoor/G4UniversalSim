"""The exported macro plan must be the recursive backend preflight result."""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXE = Path(os.environ.get("G4USIM_EXE", ROOT / "build_vs2026/Release/G4UniversalSim.exe"))


def inspect(macro: Path, *extra: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(EXE), "--inspect-macro", "--macro", str(macro), *extra],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8", timeout=30,
    )


def main() -> int:
    if not EXE.is_file():
        raise FileNotFoundError(EXE)
    with tempfile.TemporaryDirectory(prefix="g4usim-macro-plan-") as raw:
        temporary = Path(raw)
        nested = temporary / "嵌套 #1.mac"
        nested.write_text('/AIHL/geometry/setTemplate hierarchical\n/run/beamOn 3\n', encoding="utf-8")
        top = temporary / "top.mac"
        top.write_text(
            '/AIHL/material/add demo # comment\n'
            '/control/execute "嵌套 #1.mac"\n'
            '/AIHL/output/setDir output-plan\n',
            encoding="utf-8",
        )
        result = inspect(top)
        assert result.returncode == 0, result.stderr
        plan = json.loads(result.stdout)
        assert plan["schema"] == "G4UniversalSimMacroPlan"
        assert plan["version"] == 1
        assert plan["configuration_evaluated"] is False
        assert plan["runtime_command_validation_required"] is True
        assert [entry["category"] for entry in plan["commands"]] == [
            "materials", "geometry", "beam_on", "output",
        ]
        assert [entry["line"] for entry in plan["commands"]] == [1, 1, 2, 3]
        assert [Path(entry["file"]) for entry in plan["commands"]] == [top, nested, nested, top]
        assert not list(temporary.glob("run_summary.txt"))

        locked = inspect(top, "--output", str(temporary / "output"))
        assert locked.returncode != 0
        assert "conflicts with an explicit CLI lock" in locked.stderr
        assert not locked.stdout.strip()

        combined = inspect(top, "--config", str(temporary / "main.ini"))
        assert combined.returncode != 0
        assert "does not evaluate --config" in combined.stderr

        dynamic = temporary / "dynamic.mac"
        dynamic.write_text('/control/alias x /run/beamOn 3\n', encoding="utf-8")
        refused = inspect(dynamic)
        assert refused.returncode != 0
        assert "not supported by preflight" in refused.stderr
        assert not refused.stdout.strip()

        safe_nested = temporary / "执行子文件.mac"
        safe_nested.write_text("/control/echo UTF8_NESTED_EXECUTED\n", encoding="utf-8")
        safe_top = temporary / "safe-top.mac"
        safe_top.write_text('/control/execute "执行子文件.mac"\n', encoding="utf-8")
        actual = subprocess.run(
            [str(EXE), "--macro", str(safe_top), "--output", str(temporary / "actual-output")],
            cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120,
        )
        assert actual.returncode == 0, actual.stdout + actual.stderr
        assert "UTF8_NESTED_EXECUTED" in actual.stdout
        assert (temporary / "actual-output" / "run_summary.txt").is_file()

        config = temporary / "主配置.ini"
        config.write_text(
            f"[run]\nthreads = 2\nseed = 57\nmacro = {safe_top.as_posix()}\n"
            f"[output]\ndir = {(temporary / 'config-output').as_posix()}\n",
            encoding="utf-8",
        )
        query_output = temporary / "inspection-output"
        inspected = subprocess.run(
            [str(EXE), "--inspect-run", "--config", str(config),
             "--output", str(query_output), "--threads", "3"],
            cwd=temporary, capture_output=True, text=True, encoding="utf-8", timeout=30,
        )
        assert inspected.returncode == 0, inspected.stdout + inspected.stderr
        run_plan = json.loads(inspected.stdout)
        assert run_plan["schema"] == "G4UniversalSimRunPlan"
        assert run_plan["execution_performed"] is False
        assert run_plan["configuration_phase"] == "before_macro"
        facts = {item["name"]: item for item in run_plan["initial_configuration"]}
        assert Path(facts["main_config"]["value"]) == config
        assert Path(facts["seed"]["file"]) == config
        assert facts["threads"]["value"] == "3" and facts["threads"]["source"] == "cli"
        assert facts["seed"]["value"] == "57" and facts["seed"]["source"] == "main_ini"
        assert facts["seed"]["line"] == 3
        assert facts["macro_file"]["source"] == "main_ini"
        assert run_plan["macro_plan"]["commands"][0]["text"] == "/control/echo UTF8_NESTED_EXECUTED"
        assert not query_output.exists()
        assert not (temporary / "config-output").exists()

    print("test_macro_plan: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
