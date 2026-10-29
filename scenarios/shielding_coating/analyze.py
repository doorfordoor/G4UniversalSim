"""Summarises a shielding / coating scenario run (output of make_scenario.py).

    python scenarios/shielding_coating/analyze.py <scenario>/output

Reads scenario.json next to the output directory, run_summary.txt (completed
events), run_metadata.json (generated files), the merged scorer_statistics.csv and
the phase-space files, and writes <output>/shielding_report.json and
<output>/spectra.csv:

  - TID: device dose per primary, per unit incident fluence (Gy cm2) and, for a
    spectrum source, the dose rate obtained by multiplying with the sampled integral
    flux of the spectrum file(s), with the A3 relative statistical error;
  - DDD (when [scoring] displacement was enabled): the same for the displacement
    damage dose (MeV/g), as good as the supplied NIEL tables;
  - counts per primary, mean energy and log-binned energy spectra per particle of
    everything that entered BackPlane (transmission, moving +z) or FrontPlane
    (albedo, moving -z); for transmission also the fraction of primaries that
    crossed the whole stack.

The rates assume the environment flux arrives at normal incidence on the stack (as
in the original CoatingSimulation); they are not omnidirectional shielding results.

Evidence rules (2026-10-28)
---------------------------
A missing file is not a zero result. The analyser refuses to run when the run
itself is not a completed, positive-event run, and it uses the generated_files list
of run_metadata.json to tell "the run scored nothing" (the statistics file was never
written, so a zero TID is a real zero) from "the statistics file was written and is
now missing" (deleted or misplaced evidence, exit code 3, no report written).
Every quantity in the report carries an evidence label for the same reason.
"""

from __future__ import annotations

import csv
import json
import math
import re
import sys
from collections import defaultdict
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "gui"))
from g4usim_gui.output.provenance import output_evidence, output_files, ProvenanceError

SECONDS_PER_YEAR = 365.25 * 86400
BINS_PER_DECADE = 5
E_MIN, E_MAX = 1e-3, 1e4   # MeV
RUN_METADATA_SCHEMA = "run_metadata_json_v1"
STATISTICS_NAME = "scorer_statistics.csv"


class EvidenceError(Exception):
    """The output directory does not contain the evidence this analysis needs."""


def fail(message: str):
    raise EvidenceError(message)


def parse_summary(output: Path) -> dict[str, str]:
    path = output / "run_summary.txt"
    if not path.is_file():
        fail(f"{path} is missing; the run summary is required to analyse a run")
    summary: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if " = " in line:
            key, value = line.split(" = ", 1)
            summary[key] = value
    return summary


def load_metadata(output: Path) -> dict:
    path = output / "run_metadata.json"
    if not path.is_file():
        fail(f"{path} is missing; without it a missing statistics file cannot be "
             "told apart from a run that scored nothing")
    metadata = json.loads(path.read_text(encoding="utf-8"))
    if metadata.get("schema") != RUN_METADATA_SCHEMA:
        fail(f"{path} has schema {metadata.get('schema')!r}, expected {RUN_METADATA_SCHEMA!r}")
    return metadata


def check_run(summary: dict[str, str], metadata: dict) -> tuple[int, list[str]]:
    """Validate the run before any number is derived from it."""
    warnings: list[str] = []
    status = summary.get("status")
    if status != "completed":
        fail(f"run_summary.txt reports status = {status!r}; only a completed run can be analysed")
    summary_write = summary.get("summary_write_status")
    if summary_write not in (None, "completed"):
        fail(f"the run summary itself is {summary_write!r}; its numbers cannot be trusted")
    failure = summary.get("output_failure_status")
    if failure not in (None, "none", "not_applicable"):
        message = summary.get("output_failure_message", "not_applicable")
        fail(f"the run recorded an output failure ({failure}: {message})")
    if summary.get("run_count", "1") != "1":
        fail("analyze.py expects exactly one run per output directory; "
             f"run_summary.txt reports run_count = {summary.get('run_count')}")
    runs = metadata.get("runs") or []
    if len(runs) != 1:
        fail(f"run_metadata.json lists {len(runs)} runs; exactly one is expected")
    run = runs[0]
    try:
        planned = int(run["planned_events"])
        completed = int(run["completed_events"])
    except (KeyError, TypeError, ValueError):
        fail(f"run_metadata.json run entry is malformed: {run!r}")
    if completed <= 0:
        fail(f"the run completed {completed} events; no rate can be derived from an empty run")
    if completed != planned:
        fail(f"the run completed {completed} of {planned} planned events; "
             "a truncated run is not analysable")
    summary_completed = summary.get("run_0_completed_events")
    if summary_completed is not None and summary_completed != str(completed):
        fail(f"run_summary.txt reports {summary_completed} completed events but "
             f"run_metadata.json reports {completed}; the files are inconsistent")
    return completed, warnings


def generated_names(metadata: dict) -> set[str]:
    names: set[str] = set()
    for entry in metadata.get("generated_files") or []:
        path = entry.get("path") if isinstance(entry, dict) else None
        if path:
            names.add(Path(str(path).replace("\\", "/")).name)
    return names


def statistics(output: Path, metadata: dict) -> tuple[dict[tuple[str, str], dict[str, str]], str]:
    """Return the device statistics rows and an evidence label.

    A missing file is only a zero result when the run never generated one; a file
    that the run metadata lists as generated but that is absent is missing evidence.
    """
    path = output / STATISTICS_NAME
    listed = STATISTICS_NAME in generated_names(metadata)
    if path in output_evidence(output).files:
        with path.open(newline="", encoding="utf-8") as handle:
            rows = {(r["scorer"], r["quantity"]): r for r in csv.DictReader(handle) if "Device" in r["key"]}
        return rows, STATISTICS_NAME
    if listed:
        fail(f"{path} was listed in run_metadata.json generated_files but is missing; "
             "the statistics evidence was removed or moved, refusing to report zero")
    stale = sorted(p.name for p in output_files(output, "scorer_statistics_r*.csv"))
    if stale:
        fail(f"found statistics of another run ({', '.join(stale)}) but no {STATISTICS_NAME}; "
             "the output directory mixes runs")
    return {}, "no_statistics_file_zero_deposition"


def phase_space(output: Path, completed: int) -> tuple[list[dict[str, str]], list[str]]:
    paths = sorted(p for p in output_files(output, "phase_space_t*.csv")
                   if re.fullmatch(r"phase_space_t\d+\.csv", p.name))
    if not paths:
        fail("no phase_space_t*.csv files were found; make_scenario always requests a "
             "phase space, so the transmission/albedo evidence is missing")
    rows: list[dict[str, str]] = []
    for path in paths:
        with path.open(newline="", encoding="utf-8") as handle:
            rows.extend(csv.DictReader(handle))
    if not rows:
        fail(f"the phase-space files ({', '.join(p.name for p in paths)}) contain no rows")
    for row in rows:
        try:
            event = int(row["eventID"])
            run_id = int(row["runID"])
        except (KeyError, TypeError, ValueError):
            fail(f"a phase-space row is malformed: {row!r}")
        if run_id != 0:
            fail(f"a phase-space row belongs to run {run_id}; only run 0 is analysable")
        if event >= completed:
            fail(f"a phase-space row refers to event {event}, outside the {completed} completed "
                 "events; the files look stale")
    return rows, [p.name for p in paths]


def _build_report(output: Path) -> tuple[dict, dict[str, list[float]], list[float]]:
    """Read one output directory and build the report plus the spectra accumulator.

    Nothing is written here; evidence failures raise EvidenceError. The CLI serialises
    the report and writes the spectrum rows, library callers use analyze() and ignore
    the spectrum accumulator.
    """
    scenario_path = output.parent / "scenario.json"
    if not scenario_path.is_file():
        fail(f"{scenario_path} is missing")
    meta = json.loads(scenario_path.read_text(encoding="utf-8"))
    summary = parse_summary(output)
    metadata = load_metadata(output)
    events, warnings = check_run(summary, metadata)
    if meta.get("events") not in (None, events):
        warnings.append(f"scenario.json planned {meta.get('events')} events, "
                        f"the run completed {events}")
    stats, stats_evidence = statistics(output, metadata)
    phase_rows, phase_files = phase_space(output, events)
    area = float(meta["source_area_cm2"])
    flux = sum(v for v in meta.get("sampled_integral_flux_cm2_s", {}).values() if v) or None
    report: dict = {"scenario": meta, "events": events}

    def quantity(key, unit, enabled):
        if not enabled:
            return None
        row = stats.get(key)
        if row is None:
            if stats_evidence == STATISTICS_NAME:
                label = f"no_device_row_for_{key[0]}_{key[1]}"
                warnings.append(f"scorer_statistics.csv has no Device row for {key}; "
                                "the quantity is reported as zero with that evidence label")
            else:
                label = stats_evidence
            total = 0.0
            rel_error = None
        else:
            total = float(row["value"])
            rel_error = float(row["rel_error"])
            label = stats_evidence
        per_primary = total / events
        result = {"total": total, "unit": unit, "rel_error": rel_error, "evidence": label,
                  "per_primary": per_primary, f"per_fluence_{unit}_cm2": per_primary * area}
        if flux:
            result[f"rate_{unit}_per_s"] = per_primary * area * flux
            result[f"per_year_{unit}"] = per_primary * area * flux * SECONDS_PER_YEAR
        return result

    report["tid"] = quantity(("dose", "weighted_dose"), "Gy", True)
    report["ddd"] = quantity(("displacement", "ddd_total"), "MeV_g", meta.get("displacement", False))

    direction = 1.0 if meta["mode"] == "transmission" else -1.0
    edges = [E_MIN * 10 ** (i / BINS_PER_DECADE)
             for i in range(int(BINS_PER_DECADE * math.log10(E_MAX / E_MIN)) + 1)]
    counts = defaultdict(lambda: [0.0] * (len(edges) - 1))
    totals = defaultdict(lambda: [0.0, 0.0])
    primaries = set()
    for p in phase_rows:
        if float(p["w"]) * direction <= 0:
            continue
        name, energy, weight = p["particle"], float(p["kineticEnergy_MeV"]), float(p["weight"])
        totals[name][0] += weight
        totals[name][1] += weight * energy
        if p["trackID"] == "1":
            primaries.add((p["runID"], p["eventID"]))
        if E_MIN <= energy < E_MAX:
            counts[name][int(BINS_PER_DECADE * math.log10(energy / E_MIN))] += weight
    report["particles"] = {name: {"per_primary": n / events, "mean_energy_MeV": e / n if n else 0.0}
                           for name, (n, e) in sorted(totals.items())}
    if meta["mode"] == "transmission":
        report["primary_transmission"] = len(primaries) / events
    report["evidence"] = {
        "run_summary": "run_summary.txt",
        "run_status": "completed",
        "run_count": 1,
        "planned_events": int(meta.get("events") or events),
        "completed_events": events,
        "run_metadata_schema": RUN_METADATA_SCHEMA,
        "scorer_statistics": stats_evidence,
        "phase_space_files": phase_files,
        "niel_tables": meta.get("niel") or [],
        "warnings": warnings,
    }
    return report, counts, edges


def analyze(output_dir: str | Path) -> dict:
    """Analyse one completed scenario output directory and return its report dict.

    Reads scenario.json, run_summary.txt, run_metadata.json, scorer_statistics.csv and
    the phase-space files under ``output_dir`` and returns exactly the dict the CLI
    writes to shielding_report.json. Nothing is written or printed by this function;
    evidence failures raise EvidenceError.
    """
    report, _counts, _edges = _build_report(Path(output_dir).resolve())
    return report


def main(argv: list[str] | None = None) -> int:
    """Command-line wrapper: ``main([output_dir])`` writes the report and spectra.

    ``argv`` is the argument list without the program name; ``None`` means
    ``sys.argv[1:]``. Returns the process exit code (0, 2 for usage, 3 for evidence).
    """
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1:
        print(__doc__)
        return 2
    output = Path(args[0]).resolve()
    try:
        report, counts, edges = _build_report(output)
        events = report["events"]
        with (output / "spectra.csv").open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(["particle", "e_low_MeV", "e_high_MeV", "count_per_primary"])
            for name in sorted(counts):
                for i, value in enumerate(counts[name]):
                    if value:
                        writer.writerow([name, f"{edges[i]:.6g}", f"{edges[i + 1]:.6g}",
                                         f"{value / events:.6g}"])
        (output / "shielding_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")

        meta = report["scenario"]
        warnings = report["evidence"]["warnings"]
        stats_evidence = report["evidence"]["scorer_statistics"]
        flux = sum(v for v in meta.get("sampled_integral_flux_cm2_s", {}).values() if v) or None
        print(f"{meta['mode']} run, {events} primaries ({meta['particle']}), layers "
              + ", ".join(f"{l['material']} {1000 * l['thickness_mm']:g} um" for l in meta["layers"]))
        if stats_evidence != STATISTICS_NAME:
            print(f"  note: {stats_evidence}; a zero here means the run wrote no statistics")
        for key, label in (("tid", "TID"), ("ddd", "DDD")):
            q = report[key]
            if q:
                unit = q["unit"].replace("_", "/")
                error = "n/a, nothing scored" if q["rel_error"] is None else f"{q['rel_error']:.2g}"
                line = (f"  {label}: {q['per_primary']:.4g} {unit} per primary, "
                        f"{q['per_fluence_' + q['unit'] + '_cm2']:.4g} {unit} cm2 per unit fluence "
                        f"(rel. error {error}, evidence {q['evidence']})")
                if flux:
                    line += f", {q['per_year_' + q['unit']]:.4g} {unit}/year at normal incidence"
                print(line)
        if "primary_transmission" in report:
            print(f"  primaries crossing the stack: {report['primary_transmission']:.4g}")
        for name, value in report["particles"].items():
            print(f"  {name}: {value['per_primary']:.4g} per primary, "
                  f"mean {value['mean_energy_MeV']:.4g} MeV")
        for warning in warnings:
            print(f"  warning: {warning}")
        print(f"report: {output / 'shielding_report.json'}, spectra: {output / 'spectra.csv'}")
        return 0
    except (EvidenceError, ProvenanceError) as error:
        print(f"analyze.py: evidence error: {error}", file=sys.stderr)
        print("analyze.py: no report was written; fix the run or its files instead of "
              "reading a zero from missing evidence", file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
