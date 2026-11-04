"""Disposable driver for the F2 controlled-session baseline evidence.

This is NOT part of the product.  It runs the existing real backend through the
audited `--ui --ui-session csh` path and records the raw evidence the F2
protocol decision needs:

* stdin/stdout/stderr of one process and its exit code,
* one `run_summary.txt` per session (run ids, planned/completed events, status,
  failure kinds),
* the per-run `phase_space_t*.csv` rows (the kernel-consumed primary vertex at
  the Target entry boundary) and `hits_t*.csv` primary rows,
* for every multi-run session, the per-round comparison of what the kernel
  actually consumed against the Manager's own `/AIHL/source/print` output.

Usage (from the repository root):

    python out/collab/f2-session-baseline-20261104/f2_session.py --case three-round
    python out/collab/f2-session-baseline-20261104/f2_session.py --case fields
    python out/collab/f2-session-baseline-20261104/f2_session.py --case native-gps
    python out/collab/f2-session-baseline-20261104/f2_session.py --case preinit-cache
    python out/collab/f2-session-baseline-20261104/f2_session.py --case refusal-multisource
    python out/collab/f2-session-baseline-20261104/f2_session.py --case refusal-output-state

The script only writes below this directory's `evidence/` tree and never
modifies the product, its tests, or its git state.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
CONFIG_DIR = HERE / "config"
MAIN_INI = CONFIG_DIR / "main.ini"
MULTI_INI = CONFIG_DIR / "main_multisource.ini"
DEFAULT_EXE = REPO / "build_vs2026" / "Release" / "G4UniversalSim.exe"
DEFAULT_DATA = Path("D:/ProgramFiles/Geant4/share/Geant4/data")

SENTINEL = "F2_REFUSAL_SENTINEL_DID_NOT_RUN"

CASES = {
    "three-round": {
        "config": MAIN_INI,
        "why": "A/B/A source-energy rounds in one live process (single source, 1 thread).",
        "commands": [
            "/run/initialize",
            "/AIHL/source/print",
            "/run/beamOn 10",
            "/AIHL/source/energy 200 MeV",
            "/AIHL/source/print",
            "/run/beamOn 10",
            "/AIHL/source/energy 100 MeV",
            "/AIHL/source/print",
            "/run/beamOn 10",
            "exit",
        ],
    },
    "fields": {
        "config": MAIN_INI,
        "why": "Per-field setters after /run/initialize: particle, energy, point, direction, planeBeam.",
        "commands": [
            "/run/initialize",
            "/AIHL/source/particle e-",
            "/AIHL/source/print",
            "/run/beamOn 10",
            "/AIHL/source/energy 50 MeV",
            "/run/beamOn 10",
            "/AIHL/source/point 5 0 -50 mm",
            "/run/beamOn 10",
            "/AIHL/source/direction 0.1 0 0.995",
            "/run/beamOn 10",
            "/AIHL/source/planeBeam radius=5 mm z=-50 mm direction=+z",
            "/run/beamOn 10",
            "exit",
        ],
    },
    "native-gps": {
        "config": MAIN_INI,
        "why": "Un-audited native /gps command interleave: kernel vs Manager cache divergence.",
        "commands": [
            "/run/initialize",
            "/AIHL/source/print",
            "/run/beamOn 5",
            "/gps/ene/mono 2 MeV",
            "/AIHL/source/print",
            "/run/beamOn 5",
            "exit",
        ],
    },
    "preinit-cache": {
        "config": MAIN_INI,
        "why": "PreInit single-field setters are cached and replayed when GPS is created.",
        "commands": [
            "/AIHL/source/energy 300 MeV",
            "/AIHL/source/particle e-",
            "/run/initialize",
            "/run/beamOn 5",
            "exit",
        ],
    },
    "refusal-multisource": {
        "config": MULTI_INI,
        "why": "Single-source command against two named sources: rejected, later commands must not run.",
        "commands": [
            "/run/initialize",
            "/AIHL/source/energy 200 MeV",
            "/control/echo " + SENTINEL,
            "/run/beamOn 4",
            "exit",
        ],
    },
    "refusal-output-state": {
        "config": MAIN_INI,
        "why": "Output dir change after /run/initialize: Geant4 state gate rejection, later commands must not run.",
        "commands": [
            "/run/initialize",
            "/AIHL/output/setDir " + str(HERE / "evidence" / "must-not-be-used"),
            "/control/echo " + SENTINEL,
            "/run/beamOn 4",
            "exit",
        ],
    },
}

PHASE_SPACE_RE = re.compile(r"^phase_space_t(\d+)(?:_r(\d+))?\.csv$")
HITS_RE = re.compile(r"^hits_t(\d+)(?:_r(\d+))?\.csv$")


def read_summary(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if "=" not in line or line.startswith("#"):
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def run_index(name: str, pattern: re.Pattern[str]) -> int | None:
    match = pattern.match(name)
    if not match:
        return None
    return int(match.group(2) or 0)


def number(row: dict[str, str], key: str, default: float = float("nan")) -> float:
    try:
        return float(row.get(key, ""))
    except (TypeError, ValueError):
        return default


def collect_rounds(summary: dict[str, str], out_dir: Path) -> list[dict]:
    files = sorted(path.name for path in out_dir.iterdir() if path.is_file()) if out_dir.exists() else []
    phase: dict[int, list[dict[str, str]]] = {}
    hits: dict[int, list[dict[str, str]]] = {}
    for name in files:
        index = run_index(name, PHASE_SPACE_RE)
        if index is not None:
            phase[index] = read_csv(out_dir / name)
        index = run_index(name, HITS_RE)
        if index is not None:
            hits[index] = read_csv(out_dir / name)

    count = int(summary.get("run_count", "0") or 0)
    rounds = []
    for index in range(count):
        planned = summary.get(f"run_{index}_planned_events")
        completed = summary.get(f"run_{index}_completed_events")
        phase_rows = phase.get(index, [])
        primary_rows = []
        for row in hits.get(index, []):
            if row.get("trackID") == "1" and row.get("parentID") == "0":
                primary_rows.append(
                    {
                        "eventID": row.get("eventID"),
                        "particle": row.get("particle"),
                        "x0_mm": number(row, "x0_mm"),
                        "z0_mm": number(row, "z0_mm"),
                        "px": number(row, "px"),
                        "pz": number(row, "pz"),
                        "kineticEnergy_MeV": number(row, "kineticEnergy_MeV"),
                    }
                )
        rounds.append(
            {
                "run_index": index,
                "planned_events": planned,
                "completed_events": completed,
                "phase_space_rows": len(phase_rows),
                "phase_space_energies_MeV": [number(row, "kineticEnergy_MeV") for row in phase_rows],
                "phase_space_particles": sorted({row.get("particle", "") for row in phase_rows}),
                "phase_space_x_mm": [number(row, "x_mm") for row in phase_rows],
                "phase_space_u": [number(row, "u") for row in phase_rows],
                "phase_space_first": phase_rows[:3],
                "hits_primary_rows": primary_rows,
            }
        )
    return rounds


def summary_facts(summary: dict[str, str]) -> dict[str, str]:
    wanted = [
        "status",
        "run_count",
        "actual_completed_event_count",
        "macro_execution_status",
        "interactive_command_failure_kind",
        "interactive_command_failure_message",
        "output_failure_stage",
        "effective_source_energy_MeV",
        "effective_source_particle",
        "effective_config_source_coverage",
    ]
    return {key: summary.get(key, "") for key in wanted if summary.get(key, "") != ""}


def run_case(name: str, exe: Path, timeout: float) -> dict:
    spec = CASES[name]
    evidence_dir = HERE / "evidence" / name
    if evidence_dir.exists():
        shutil.rmtree(evidence_dir)
    output_dir = evidence_dir / "output"
    output_dir.mkdir(parents=True)
    commands = list(spec["commands"])
    stdin_text = "\n".join(commands) + "\n"
    (evidence_dir / "stdin.txt").write_text(stdin_text, encoding="utf-8")

    env = dict(os.environ)
    env.setdefault("G4USIM_GEANT4_DATA", str(DEFAULT_DATA).replace("\\", "/"))
    args = [
        str(exe),
        "--ui",
        "--ui-session",
        "csh",
        "--config",
        spec["config"].name,
        "--output",
        str(output_dir),
    ]
    started = time.monotonic()
    timed_out = False
    try:
        process = subprocess.run(
            args,
            cwd=str(CONFIG_DIR),
            input=stdin_text,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
        )
        code = process.returncode
        stdout = process.stdout or ""
        stderr = process.stderr or ""
    except subprocess.TimeoutExpired as expired:
        timed_out = True
        code = -1
        stdout = (expired.stdout or "") if isinstance(expired.stdout, str) else ""
        stderr = (expired.stderr or "") if isinstance(expired.stderr, str) else ""
    duration = time.monotonic() - started

    (evidence_dir / "stdout.log").write_text(stdout, encoding="utf-8")
    (evidence_dir / "stderr.log").write_text(stderr, encoding="utf-8")
    summary_path = output_dir / "run_summary.txt"
    summary = read_summary(summary_path)
    if summary_path.exists():
        shutil.copyfile(summary_path, evidence_dir / "run_summary.txt")

    files = sorted(path.name for path in output_dir.iterdir() if path.is_file()) if output_dir.exists() else []
    rounds = collect_rounds(summary, output_dir)
    result = {
        "schema": "g4usim_f2_session_baseline_case_v1",
        "case": name,
        "why": spec["why"],
        "config": spec["config"].name,
        "argv": args,
        "cwd": str(CONFIG_DIR),
        "commands": commands,
        "sentinel": SENTINEL,
        "sentinel_in_stdout": SENTINEL in stdout,
        "exit_code": code,
        "timed_out": timed_out,
        "duration_s": round(duration, 3),
        "output_files": files,
        "summary": summary_facts(summary),
        "summary_all": summary,
        "rounds": rounds,
        "captured_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    }
    (evidence_dir / "session.json").write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    return result


def describe(result: dict) -> None:
    print(f"== {result['case']}: exit={result['exit_code']} duration={result['duration_s']}s sentinel_seen={result['sentinel_in_stdout']}")
    for key, value in result["summary"].items():
        print(f"   summary {key} = {value}")
    for round_ in result["rounds"]:
        energies = round_["phase_space_energies_MeV"]
        print(
            f"   run {round_['run_index']}: planned={round_['planned_events']} completed={round_['completed_events']}"
            f" phase_rows={round_['phase_space_rows']} particles={round_['phase_space_particles']}"
            f" energy_MeV={[round(value, 4) for value in energies[:4]]}"
            f" x_mm={[round(value, 3) for value in round_['phase_space_x_mm'][:4]]}"
            f" u={[round(value, 4) for value in round_['phase_space_u'][:4]]}"
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--case", choices=sorted(CASES))
    parser.add_argument("--exe", default=os.environ.get("G4USIM_EXE", str(DEFAULT_EXE)))
    parser.add_argument("--timeout", type=float, default=600.0)
    parser.add_argument("--all", action="store_true", help="run every case in a stable order")
    args = parser.parse_args(argv)
    if not args.case and not args.all:
        parser.error("--case is required unless --all is given")

    exe = Path(args.exe)
    if not exe.exists():
        print(f"backend executable not found: {exe}", file=sys.stderr)
        return 2

    results = []
    names = sorted(CASES) if args.all else [args.case]
    for name in names:
        try:
            result = run_case(name, exe, args.timeout)
        except Exception as error:  # keep the failure visible, never fake success
            print(f"== {name}: driver failure: {type(error).__name__}: {error}", file=sys.stderr)
            return 3
        results.append(result)
        describe(result)

    index = HERE / "evidence" / "index.json"
    index.write_text(json.dumps({"schema": "g4usim_f2_session_baseline_index_v1", "cases": results}, indent=2, sort_keys=True), encoding="utf-8")
    print(f"wrote {index}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
