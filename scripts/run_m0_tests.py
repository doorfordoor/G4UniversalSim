"""Layered M0 regression entrypoint with explicit pass/fail/skip evidence."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import platform
import subprocess
import sys
import tempfile
import time
import uuid
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIRECTORIES = ("src", "include", "gui/g4usim_gui", "gui/smoke_tests", "scripts", "tools")
SOURCE_SUFFIXES = (".py", ".cc", ".hh", ".h", ".in")


@dataclass(frozen=True)
class Case:
    name: str
    script: str
    layer: str
    requirements: tuple[str, ...] = ()
    timeout: int = 600
    args: tuple[str, ...] = ()


CASES = (
    Case("merge_outputs", "scripts/test_merge_outputs.py", "static"),
    Case("output_extensions", "scripts/test_output_extensions.py", "static"),
    Case("runner_contract", "scripts/test_m0_runner.py", "static"),
    Case("merge_histograms", "scripts/test_merge_histograms.py", "backend", ("merge",)),
    Case("gui_parsers", "gui/smoke_tests/smoke_parsers.py", "gui", ("qt",)),
    Case("gui_materials", "gui/smoke_tests/smoke_materials_editor.py", "gui", ("qt",)),
    Case("gui_geometry", "gui/smoke_tests/smoke_geometry_editor.py", "gui", ("qt",)),
    Case("gui_preview", "gui/smoke_tests/smoke_preview3d.py", "gui", ("qt",)),
    Case("gui_preview_primitives", "gui/smoke_tests/smoke_preview3d_primitives.py", "gui", ("qt",)),
    Case("gui_project_io", "gui/smoke_tests/smoke_project_io.py", "gui", ("qt",)),
    Case("gui_source", "gui/smoke_tests/smoke_source_editor_v2.py", "gui", ("qt",)),
    Case("gui_run_config", "gui/smoke_tests/smoke_run_config_editors.py", "gui", ("qt",)),
    Case("gui_dose_results", "gui/smoke_tests/smoke_dose_results.py", "gui", ("qt",)),
    Case("gui_plots", "gui/smoke_tests/smoke_plots.py", "gui", ("qt",)),
    Case("gui_new_simulation_wizard", "gui/smoke_tests/smoke_new_simulation_wizard.py", "gui", ("qt",)),
    Case("gui_fluence_results", "gui/smoke_tests/smoke_fluence_results.py", "gui", ("qt",)),
    Case("gui_output_extensions", "gui/smoke_tests/smoke_output_extensions_gui.py", "gui", ("qt",)),
    Case("gui_output", "gui/smoke_tests/smoke_output_tools.py", "gui", ("qt",)),
    Case("gui_history", "gui/smoke_tests/smoke_history.py", "gui", ("qt",)),
    Case("gui_run_result", "gui/smoke_tests/smoke_run_result.py", "gui", ("qt",)),
    Case("gui_main_window", "gui/smoke_tests/smoke_main_window_ui.py", "gui", ("qt",)),
    Case("gui_unsupported_features", "scripts/test_unsupported_features.py", "gui", ("qt",), args=("--layer", "gui")),
    Case("gui_geometry_safety", "scripts/test_geometry_safety_contract.py", "gui", ("qt",), args=("--layer", "gui")),
    Case("gui_geometry_diagnostics", "scripts/test_geometry_config_diagnostics.py", "gui", ("qt",), args=("--layer", "gui")),
    Case("backend_capabilities", "scripts/test_backend_capabilities.py", "backend", ("exe",)),
    Case("config_precedence", "scripts/test_config_precedence.py", "backend", ("exe",)),
    Case("run_summary", "scripts/test_run_summary.py", "backend", ("exe",)),
    Case("dose_scoring", "scripts/test_dose_scoring.py", "backend", ("exe",)),
    Case("fluence_scoring", "scripts/test_fluence_scoring.py", "backend", ("exe",)),
    Case("root_output", "scripts/test_root_output.py", "backend", ("exe", "uproot")),
    Case("scoring_mesh", "scripts/test_scoring_mesh.py", "backend", ("exe", "uproot")),
    Case("let_scoring", "scripts/test_let_scoring.py", "backend", ("exe", "uproot")),
    Case("statistical_uncertainty", "scripts/test_statistical_uncertainty.py", "backend", ("exe", "uproot")),
    Case("gps_sources", "scripts/test_gps_sources.py", "backend", ("exe",)),
    Case("geometry_a5", "scripts/test_geometry_a5.py", "backend", ("exe",)),
    Case("physics_a6", "scripts/test_physics_a6.py", "backend", ("exe",)),
    Case("fields_a7", "scripts/test_fields_a7.py", "backend", ("exe",)),
    Case("displacement_damage", "scripts/test_displacement_damage.py", "backend", ("exe",)),
    Case("shielding_coating", "scripts/test_shielding_coating.py", "backend", ("exe",)),
    Case("semiconductor_device", "scripts/test_semiconductor_device.py", "backend", ("exe",)),
    Case("detector_response", "scripts/test_detector_response.py", "backend", ("exe",)),
    Case("benchmarks", "scripts/run_benchmarks.py", "backend", ("exe",), args=("--quick",)),
    Case("interactive_commands", "scripts/test_interactive_commands.py", "backend", ("exe",)),
    Case("unsupported_features", "scripts/test_unsupported_features.py", "backend", ("exe",), args=("--layer", "backend")),
    Case("unconsumed_config", "scripts/test_unconsumed_config.py", "backend", ("exe",)),
    Case("material_schema", "scripts/test_material_config_schema.py", "backend", ("exe",)),
    Case("geometry_safety", "scripts/test_geometry_safety_contract.py", "backend", ("exe",), args=("--layer", "backend")),
    Case("geometry_diagnostics", "scripts/test_geometry_config_diagnostics.py", "backend", ("exe",), args=("--layer", "backend")),
    Case("macro_plan", "scripts/test_macro_plan.py", "backend", ("exe",)),
    Case("default_geometry", "scripts/test_default_geometry_batch.py", "backend", ("exe",)),
    Case("geometry_roundtrip", "scripts/test_geometry_roundtrip_backend.py", "integration", ("exe", "qt")),
    Case("biasing_targets", "scripts/test_biasing_target_contract.py", "backend", ("exe",)),
    Case("gui_run_inputs", "gui/smoke_tests/smoke_run_input_modes.py", "integration", ("exe", "qt")),
    Case("gui_backend_geometry", "gui/smoke_tests/smoke_backend_geometry.py", "integration", ("exe", "qt")),
    Case("gui_backend_package", "gui/smoke_tests/smoke_geometry_backend_package.py", "integration", ("exe", "qt")),
    Case("gui_plots_backend", "gui/smoke_tests/smoke_plots_backend.py", "integration", ("exe", "qt")),
    Case("gui_new_simulation_backend", "gui/smoke_tests/smoke_new_simulation_backend.py", "integration",
         ("exe", "qt")),
)


def git_value(*arguments: str) -> str:
    result = subprocess.run(["git", *arguments], cwd=ROOT, capture_output=True, text=True, check=False)
    return result.stdout.strip() if result.returncode == 0 else "unavailable"


def untracked_source_files() -> list[str]:
    """Find local runtime/test sources absent from Git's index, including ignored files."""
    result = subprocess.run(
        ["git", "ls-files", "--cached", "-z", "--", *SOURCE_DIRECTORIES],
        cwd=ROOT, capture_output=True, check=False,
    )
    if result.returncode != 0:
        raise RuntimeError("cannot inspect Git index for source inventory")
    tracked = {Path(os.fsdecode(item)).as_posix() for item in result.stdout.split(b"\0") if item}
    missing = []
    for directory in SOURCE_DIRECTORIES:
        for path in (ROOT / directory).rglob("*"):
            if not path.is_file() or path.suffix not in SOURCE_SUFFIXES or "__pycache__" in path.parts:
                continue
            relative = path.relative_to(ROOT).as_posix()
            if relative not in tracked:
                missing.append(relative)
    return sorted(missing)


def workspace_source_fingerprint() -> str:
    source_paths = [ROOT / "main.cc", ROOT / "CMakeLists.txt", ROOT / "include/Core/BuildInfo.hh.in"]
    source_paths.extend((ROOT / "src").rglob("*.cc"))
    source_paths.extend((ROOT / "include").rglob("*.hh"))
    manifest = "".join(
        f"{path.relative_to(ROOT).as_posix()}:{hashlib.sha256(path.read_bytes()).hexdigest()}\n"
        for path in sorted(source_paths, key=lambda item: item.relative_to(ROOT).as_posix())
    )
    return hashlib.sha256(manifest.encode("utf-8")).hexdigest()


def executable_freshness(executable: Path) -> str:
    if not executable.is_file():
        return "backend executable is missing"
    current_fingerprint = workspace_source_fingerprint()
    try:
        result = subprocess.run(
            [str(executable), "--capabilities"], cwd=executable.parent,
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30,
            check=False,
        )
        embedded = json.loads(result.stdout).get("source_fingerprint") if result.returncode == 0 else None
    except (OSError, ValueError, subprocess.TimeoutExpired):
        embedded = None
    if embedded != current_fingerprint:
        return "backend source fingerprint is missing or differs from this worktree; rebuild"
    return ""


def merge_executable_freshness(executable: Path) -> str:
    if not executable.is_file():
        return "mergeHistograms executable is missing"
    source = ROOT / "tools" / "mergeHistograms.cc"
    expected = hashlib.sha256(source.read_bytes()).hexdigest()
    try:
        result = subprocess.run(
            [str(executable), "--source-fingerprint"], cwd=executable.parent,
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=10,
            check=False,
        )
        actual = result.stdout.strip() if result.returncode == 0 else ""
    except (OSError, subprocess.TimeoutExpired):
        actual = ""
    if actual != expected:
        return "mergeHistograms source fingerprint is missing or differs from this worktree; rebuild"
    return ""


def main() -> int:
    # Failure tails may hold characters the console code page (e.g. GBK) cannot encode;
    # replace them instead of crashing the runner and hiding the failure.
    sys.stdout.reconfigure(errors="replace")
    parser = argparse.ArgumentParser(description="Run M0 tests by dependency layer; missing requirements are not green.")
    parser.add_argument("--profile", choices=("static", "gui", "backend", "integration", "all"), default="all")
    parser.add_argument("--case", action="append", choices=tuple(case.name for case in CASES),
                        help="Run only this named case within the selected profile (repeatable).")
    parser.add_argument("--executable", type=Path, default=ROOT / "build_vs2026/Release/G4UniversalSim.exe")
    parser.add_argument("--merge-executable", type=Path, default=ROOT / "build_vs2026/Release/mergeHistograms.exe")
    parser.add_argument("--report-root", type=Path, default=Path(tempfile.gettempdir()) / "g4usim-m0-tests")
    parser.add_argument("--require-tracked-sources", action="store_true",
                        help="Fail when runtime or test source files are absent from Git's index.")
    args = parser.parse_args()

    report_dir = args.report_root / f"{time.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:8]}"
    report_dir.mkdir(parents=True, exist_ok=False)
    requirements = {
        "qt": "" if importlib.util.find_spec("PySide6") else "PySide6 is unavailable",
        "uproot": "" if importlib.util.find_spec("uproot") else "uproot is unavailable (pip install uproot)",
        "exe": executable_freshness(args.executable.resolve()),
        "merge": merge_executable_freshness(args.merge_executable.resolve()),
    }
    backend_build_identity = None
    if not requirements["exe"]:
        capabilities_result = subprocess.run(
            [str(args.executable.resolve()), "--capabilities"],
            cwd=args.executable.resolve().parent, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=30, check=False,
        )
        capabilities = json.loads(capabilities_result.stdout)
        backend_build_identity = {
            key: capabilities.get(key) for key in
            ("build_configuration", "compiler_id", "compiler_version",
             "geant4_version_number", "multithreaded")
        }
    selected = [case for case in CASES if (args.profile == "all" or case.layer == args.profile)
                and (not args.case or case.name in args.case)]
    if not selected:
        parser.error("No cases match the selected profile and --case filters")
    results: list[dict] = []
    missing_tracked_sources = untracked_source_files()
    environment = os.environ.copy()
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment["QT_QPA_PLATFORM"] = "offscreen"
    environment["G4USIM_EXE"] = str(args.executable.resolve())
    environment["G4USIM_MERGE_EXE"] = str(args.merge_executable.resolve())

    for case in selected:
        source = ROOT / case.script
        record = {"name": case.name, "layer": case.layer, "script": case.script}
        missing = [requirements[requirement] for requirement in case.requirements if requirements[requirement]]
        if not source.is_file():
            record.update(status="fail", reason="test script is missing")
        elif missing:
            record.update(status="skip", reason="; ".join(missing))
        else:
            command = [sys.executable, "-B", str(source)]
            if case.name == "merge_histograms":
                command.extend(["--executable", str(args.merge_executable.resolve())])
            command.extend(case.args)
            start = time.monotonic()
            try:
                process = subprocess.run(
                    command, cwd=ROOT, env=environment, capture_output=True,
                    text=True, encoding="utf-8", errors="replace", timeout=case.timeout,
                    check=False,
                )
                record.update(
                    status="pass" if process.returncode == 0 else "fail",
                    exit_code=process.returncode,
                    duration_seconds=round(time.monotonic() - start, 3),
                )
                log = process.stdout + process.stderr
            except subprocess.TimeoutExpired as error:
                record.update(status="fail", reason=f"timeout after {case.timeout}s", duration_seconds=case.timeout)
                log = str(error)
            log_path = report_dir / f"{case.name}.log"
            log_path.write_text(log, encoding="utf-8")
            record["log"] = str(log_path)
            if record["status"] == "fail":
                record["tail"] = log[-1500:]
        results.append(record)
        print(f"{record['status'].upper():4} {case.name}: {record.get('reason', record.get('tail', ''))}", flush=True)

    report = {
        "schema": "G4UniversalSimM0TestReport", "version": 1,
        "profile": args.profile, "platform": platform.platform(),
        "python": sys.version.split()[0], "git_head": git_value("rev-parse", "HEAD"),
        "source_fingerprint": workspace_source_fingerprint(),
        "git_dirty": bool(git_value("status", "--porcelain")),
        "backend_executable": str(args.executable.resolve()),
        "backend_provenance": requirements["exe"] or "source_sha256_manifest_matches_executable",
        "backend_build_identity": backend_build_identity,
        "merge_executable": str(args.merge_executable.resolve()),
        "merge_source_fingerprint": hashlib.sha256((ROOT / "tools/mergeHistograms.cc").read_bytes()).hexdigest(),
        "merge_provenance": requirements["merge"] or "source_sha256_matches_executable",
        "optional_pyvista_coverage": "not_proven_by_this_runner",
        "untracked_source_files": missing_tracked_sources,
        "tracked_source_gate": "fail" if missing_tracked_sources else "pass",
        "results": results,
    }
    report_path = report_dir / "report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Report: {report_path}")
    if any(record["status"] == "fail" for record in results):
        return 1
    if args.require_tracked_sources and missing_tracked_sources:
        print(f"FAIL tracked source gate: {len(missing_tracked_sources)} source files are absent from Git's index")
        for source in missing_tracked_sources:
            print(f"  {source}")
        return 1
    return 2 if any(record["status"] == "skip" for record in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
