"""Summarises a shielding / coating scenario run (output of make_scenario.py).

    python scenarios/shielding_coating/analyze.py <scenario>/output

Reads scenario.json next to the output directory, run_summary.txt (completed
events), the merged scorer_statistics.csv and the phase-space files, and writes <output>/shielding_report.json and
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
"""

from __future__ import annotations

import csv
import json
import math
import re
import sys
from collections import defaultdict
from pathlib import Path

SECONDS_PER_YEAR = 365.25 * 86400
BINS_PER_DECADE = 5
E_MIN, E_MAX = 1e-3, 1e4   # MeV


def statistics(output: Path) -> dict[tuple[str, str], dict[str, str]]:
    # The backend writes no statistics file when nothing was scored.
    if not (output / "scorer_statistics.csv").is_file():
        return {}
    with (output / "scorer_statistics.csv").open(newline="", encoding="utf-8") as handle:
        return {(r["scorer"], r["quantity"]): r for r in csv.DictReader(handle) if "Device" in r["key"]}


def phase_space(output: Path):
    for path in sorted(output.glob("phase_space_t*.csv")):
        if re.fullmatch(r"phase_space_t\d+\.csv", path.name):
            with path.open(newline="", encoding="utf-8") as handle:
                yield from csv.DictReader(handle)


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    output = Path(sys.argv[1]).resolve()
    meta = json.loads((output.parent / "scenario.json").read_text(encoding="utf-8"))
    # Completed events of the (single) run, not the planned count in scenario.json.
    summary = dict(line.split(" = ", 1) for line in
                   (output / "run_summary.txt").read_text(encoding="utf-8").splitlines() if " = " in line)
    if summary.get("run_count", "1") != "1":
        raise SystemExit("analyze.py expects one run per output directory")
    events = int(summary["run_0_completed_events"])
    area = meta["source_area_cm2"]
    flux = sum(v for v in meta["sampled_integral_flux_cm2_s"].values() if v) or None
    stats = statistics(output)
    report: dict = {"scenario": meta, "events": events}

    def quantity(key, unit, enabled):
        if not enabled:
            return None
        row = stats.get(key)   # missing: nothing reached the device
        total = float(row["value"]) if row else 0.0
        per_primary = total / events
        result = {"total": total, "unit": unit, "rel_error": float(row["rel_error"]) if row else None,
                  "per_primary": per_primary, f"per_fluence_{unit}_cm2": per_primary * area}
        if flux:
            result[f"rate_{unit}_per_s"] = per_primary * area * flux
            result[f"per_year_{unit}"] = per_primary * area * flux * SECONDS_PER_YEAR
        return result

    report["tid"] = quantity(("dose", "weighted_dose"), "Gy", True)
    report["ddd"] = quantity(("displacement", "ddd_total"), "MeV_g", meta.get("displacement", False))

    direction = 1.0 if meta["mode"] == "transmission" else -1.0
    edges = [E_MIN * 10 ** (i / BINS_PER_DECADE) for i in range(int(BINS_PER_DECADE * math.log10(E_MAX / E_MIN)) + 1)]
    counts = defaultdict(lambda: [0.0] * (len(edges) - 1))
    totals = defaultdict(lambda: [0.0, 0.0])
    primaries = set()
    for p in phase_space(output):
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
    with (output / "spectra.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["particle", "e_low_MeV", "e_high_MeV", "count_per_primary"])
        for name in sorted(counts):
            for i, value in enumerate(counts[name]):
                if value:
                    writer.writerow([name, f"{edges[i]:.6g}", f"{edges[i + 1]:.6g}", f"{value / events:.6g}"])
    (output / "shielding_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(f"{meta['mode']} run, {events} primaries ({meta['particle']}), layers "
          + ", ".join(f"{l['material']} {1000 * l['thickness_mm']:g} um" for l in meta["layers"]))
    for key, label in (("tid", "TID"), ("ddd", "DDD")):
        q = report[key]
        if q:
            unit = q["unit"].replace("_", "/")
            error = "n/a, nothing scored" if q["rel_error"] is None else f"{q['rel_error']:.2g}"
            line = (f"  {label}: {q['per_primary']:.4g} {unit} per primary, "
                    f"{q['per_fluence_' + q['unit'] + '_cm2']:.4g} {unit} cm2 per unit fluence "
                    f"(rel. error {error})")
            if flux:
                line += f", {q['per_year_' + q['unit']]:.4g} {unit}/year at normal incidence"
            print(line)
    if "primary_transmission" in report:
        print(f"  primaries crossing the stack: {report['primary_transmission']:.4g}")
    for name, value in report["particles"].items():
        print(f"  {name}: {value['per_primary']:.4g} per primary, mean {value['mean_energy_MeV']:.4g} MeV")
    print(f"report: {output / 'shielding_report.json'}, spectra: {output / 'spectra.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
