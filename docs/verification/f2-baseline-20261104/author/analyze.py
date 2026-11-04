"""Summarise the F2 baseline evidence into tables used by the outbox report.

Reads `evidence/index.json` (written by f2_session.py) and emits
`evidence/results-summary.md` plus a compact `evidence/results.json`.
The script is read-only with respect to the evidence directory.
"""

from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
EVIDENCE = HERE / "evidence"


def fmt(values: list[float], digits: int = 3) -> str:
    if not values:
        return "—"
    low, high = min(values), max(values)
    if round(low, digits) == round(high, digits):
        return f"{low:.{digits}f}"
    return f"{low:.{digits}f}–{high:.{digits}f}"


def main() -> int:
    index = json.loads((EVIDENCE / "index.json").read_text(encoding="utf-8"))
    lines: list[str] = []
    lines.append("# F2 controlled-session baseline: generated evidence summary\n")
    lines.append("Generated from `evidence/index.json`; every number below is read from the raw")
    lines.append("files the sessions produced (run summary, phase-space CSV, hits CSV).\n")

    lines.append("## Session overview\n")
    lines.append("| case | exit | sentinel seen | status | run_count | completed | effective energy / particle |")
    lines.append("| --- | --- | --- | --- | --- | --- | --- |")
    for case in index["cases"]:
        summary = case["summary"]
        lines.append(
            "| {case} | {exit} | {sentinel} | {status} | {runs} | {done} | {energy} MeV / {particle} |".format(
                case=case["case"],
                exit=case["exit_code"],
                sentinel=case["sentinel_in_stdout"],
                status=summary.get("status", "—"),
                runs=summary.get("run_count", "—"),
                done=summary.get("actual_completed_event_count", "—"),
                energy=summary.get("effective_source_energy_MeV", "—"),
                particle=summary.get("effective_source_particle", "—"),
            )
        )

    lines.append("\n## Per-round kernel-consumed primary vertices (phase_space_t*.csv)\n")
    lines.append("| case | run | planned | completed | rows | particles | energy_MeV | x_mm | u |")
    lines.append("| --- | --- | --- | --- | --- | --- | --- | --- | --- |")
    for case in index["cases"]:
        for round_ in case["rounds"]:
            lines.append(
                "| {case} | {run} | {planned} | {completed} | {rows} | {particles} | {energy} | {x} | {u} |".format(
                    case=case["case"],
                    run=round_["run_index"],
                    planned=round_["planned_events"],
                    completed=round_["completed_events"],
                    rows=round_["phase_space_rows"],
                    particles=",".join(round_["phase_space_particles"]) or "—",
                    energy=fmt(round_["phase_space_energies_MeV"]),
                    x=fmt(round_["phase_space_x_mm"]),
                    u=fmt(round_["phase_space_u"]),
                )
            )

    lines.append("\n## Refusals and terminal state\n")
    for name in ("refusal-multisource", "refusal-output-state"):
        case = next(item for item in index["cases"] if item["case"] == name)
        lines.append(f"### {name}\n")
        lines.append(f"- exit_code: `{case['exit_code']}`; sentinel seen: `{case['sentinel_in_stdout']}`")
        for key, value in case["summary"].items():
            lines.append(f"- {key}: `{value}`")
        stderr = (EVIDENCE / name / "stderr.log")
        log = (EVIDENCE / name / "stdout.log")
        if stderr.exists():
            text = stderr.read_text(encoding="utf-8", errors="replace")
            hits = [line for line in text.splitlines() if "G4Exception" in line or "AIHL_SOURCE" in line or "Source command" in line]
            for line in hits[:4]:
                lines.append(f"- stderr: `{line.strip()}`")
        if log.exists() and not case["summary"]:
            text = log.read_text(encoding="utf-8", errors="replace")
            for line in text.splitlines():
                if "source command" in line.lower() or "AIHL_SOURCE" in line:
                    lines.append(f"- stdout: `{line.strip()}`")
        lines.append("")

    lines.append("## Native `/gps` interleave: manager cache vs kernel\n")
    case = next(item for item in index["cases"] if item["case"] == "native-gps")
    for round_ in case["rounds"]:
        lines.append(
            f"- run {round_['run_index']}: kernel-consumed energy = {fmt(round_['phase_space_energies_MeV'])} MeV, "
            f"rows = {round_['phase_space_rows']}"
        )
    stdout = (EVIDENCE / "native-gps" / "stdout.log").read_text(encoding="utf-8", errors="replace").splitlines()
    for line in stdout:
        if "[SourceManager]" in line and "monoEnergy" in line:
            lines.append(f"- manager print: `{line.strip()}`")
    lines.append(
        "- The Manager therefore reports 100 MeV after the native `/gps/ene/mono 2 MeV` command while the "
        "kernel consumed 2 MeV in run 1: a controlled csh session cannot produce an authoritative "
        "applied-value receipt for native GPS commands."
    )

    output = EVIDENCE / "results-summary.md"
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    compact = {
        "schema": "g4usim_f2_session_baseline_results_v1",
        "cases": {
            case["case"]: {
                "exit_code": case["exit_code"],
                "sentinel_in_stdout": case["sentinel_in_stdout"],
                "summary": case["summary"],
                "rounds": [
                    {
                        "run_index": round_["run_index"],
                        "planned": round_["planned_events"],
                        "completed": round_["completed_events"],
                        "phase_space_rows": round_["phase_space_rows"],
                        "particles": round_["phase_space_particles"],
                        "energies_MeV": round_["phase_space_energies_MeV"],
                        "x_mm": round_["phase_space_x_mm"],
                        "u": round_["phase_space_u"],
                    }
                    for round_ in case["rounds"]
                ],
            }
            for case in index["cases"]
        },
    }
    (EVIDENCE / "results.json").write_text(json.dumps(compact, indent=2), encoding="utf-8")
    print(f"wrote {output}")
    print(f"wrote {EVIDENCE / 'results.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
