"""Summarises a semiconductor device run (output of make_device.py).

    python scenarios/semiconductor/analyze_device.py <scenario>/output

For the gate oxide, the active layer and every substrate slice: TID (Gy of the layer
material) and displacement damage dose DDD (MeV/g, from the Si NIEL tables) per
primary and per unit incident fluence, the 1 MeV neutron-equivalent fluence
Phi_eq = DDD / NIEL_ref with the ASTM E722 reference NIEL_ref = 95 MeV mb =
2.037e-3 MeV cm2/g for silicon, and, for spectrum sources, the rates obtained with
the sampled integral flux (normal incidence, as in make_device.py). Writes
<output>/device_report.json and <output>/depth_profile.csv, and warns when a
tabulated particle spent track length outside its NIEL table.
"""

from __future__ import annotations

import csv
import json
import re
import sys
from collections import defaultdict
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "gui"))
from g4usim_gui.output.provenance import output_evidence, output_files

NIEL_1MEV_NEUTRON_SI = 95e-27 * 6.02214076e23 / 28.0855   # MeV cm2/g (ASTM E722: 95 MeV mb)
SECONDS_PER_YEAR = 365.25 * 86400


def worker_rows(output: Path, stem: str):
    for path in sorted(output_files(output, f"{stem}_t*.csv")):
        if re.fullmatch(rf"{stem}_t\d+\.csv", path.name):
            with path.open(newline="", encoding="utf-8") as handle:
                yield from csv.DictReader(handle)


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    output = Path(sys.argv[1]).resolve()
    meta = json.loads((output.parent / "scenario.json").read_text(encoding="utf-8"))
    summary = dict(line.split(" = ", 1) for line in
                   (output / "run_summary.txt").read_text(encoding="utf-8").splitlines() if " = " in line)
    if summary.get("run_count", "1") != "1":
        raise SystemExit("analyze_device.py expects one run per output directory")
    events = int(summary["run_0_completed_events"])
    area = meta["source_area_cm2"]
    flux = sum(v for v in meta["sampled_integral_flux_cm2_s"].values() if v) or None
    stats = {}
    if output / "scorer_statistics.csv" in output_evidence(output).files:
        with (output / "scorer_statistics.csv").open(newline="", encoding="utf-8") as handle:
            stats = {(r["scorer"], r["quantity"], r["key"]): r for r in csv.DictReader(handle)}

    def value(scorer, quantity, key):
        row = stats.get((scorer, quantity, key))
        return (float(row["value"]), float(row["rel_error"])) if row else (0.0, None)

    regions = [(l["name"], f"/world_PV#0/{l['name']}_PV#0", l) for l in meta["layers"]]
    regions += [(f"Slice{s['copy']}", f"/world_PV#0/Substrate_PV#0/Slice_PV#{s['copy']}", s) for s in meta["slices"]]
    report = {"provenance": output_evidence(output).status, "scenario": meta, "events": events, "niel_1MeV_neutron_MeV_cm2_g": NIEL_1MEV_NEUTRON_SI, "regions": {}}
    for name, key, info in regions:
        dose, dose_err = value("dose", "weighted_dose", key)
        ddd, ddd_err = value("displacement", "ddd_total", key)
        entry = {"depth_mm": info["depth_mm"], "thickness_mm": info["thickness_mm"],
                 "tid_Gy_per_primary": dose / events, "tid_Gy_cm2": dose / events * area, "tid_rel_error": dose_err,
                 "ddd_MeV_g_per_primary": ddd / events, "ddd_MeV_g_cm2": ddd / events * area,
                 "ddd_rel_error": ddd_err, "phi_eq_per_unit_fluence": ddd / events * area / NIEL_1MEV_NEUTRON_SI}
        if flux:
            entry["tid_Gy_per_year"] = entry["tid_Gy_cm2"] * flux * SECONDS_PER_YEAR
            entry["ddd_MeV_g_per_year"] = entry["ddd_MeV_g_cm2"] * flux * SECONDS_PER_YEAR
            entry["phi_eq_cm2_per_year"] = entry["phi_eq_per_unit_fluence"] * flux * SECONDS_PER_YEAR
        report["regions"][name] = entry

    outside = defaultdict(lambda: [0.0, 0.0])
    for row in worker_rows(output, "displacement_volume_summary"):
        outside[row["particle"]][0] += float(row["track_length_mm"])
        outside[row["particle"]][1] += float(row["out_of_range_track_length_mm"])
    report["out_of_range_fraction"] = {p: (o / (i + o) if i + o else 0.0) for p, (i, o) in outside.items()}

    with (output / "depth_profile.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["region", "depth_mm", "thickness_mm", "tid_Gy_cm2", "tid_rel_error", "ddd_MeV_g_cm2",
                         "ddd_rel_error", "phi_eq_per_unit_fluence"])
        for name, entry in report["regions"].items():
            writer.writerow([name, f"{entry['depth_mm']:.6g}", f"{entry['thickness_mm']:.6g}",
                             f"{entry['tid_Gy_cm2']:.6g}", entry["tid_rel_error"], f"{entry['ddd_MeV_g_cm2']:.6g}",
                             entry["ddd_rel_error"], f"{entry['phi_eq_per_unit_fluence']:.6g}"])
    (output / "device_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")

    energy = f"{meta['energy_MeV']:g} MeV" if meta["energy_MeV"] else "spectrum"
    print(f"{events} primaries ({meta['particle']}, {energy}), per unit incident fluence (1 cm-2):")
    print(f"  {'region':10s} {'depth_um':>9s} {'TID Gy cm2':>11s} {'err':>6s} {'DDD MeV/g cm2':>14s} {'err':>6s} "
          f"{'Phi_eq':>8s}" + ("  TID Gy/year" if flux else ""))
    for name, e in report["regions"].items():
        err = lambda x: "  n/a" if x is None else f"{x:6.3f}"   # noqa: E731
        line = (f"  {name:10s} {1000 * e['depth_mm']:9.2f} {e['tid_Gy_cm2']:11.4g} {err(e['tid_rel_error'])} "
                f"{e['ddd_MeV_g_cm2']:14.4g} {err(e['ddd_rel_error'])} {e['phi_eq_per_unit_fluence']:8.4g}")
        if flux:
            line += f"  {e['tid_Gy_per_year']:.4g}"
        print(line)
    for particle, fraction in sorted(report["out_of_range_fraction"].items()):
        if fraction > 0.01:
            print(f"  warning: {100 * fraction:.1f} % of the {particle} track length is outside its NIEL table")
    print(f"report: {output / 'device_report.json'}, profile: {output / 'depth_profile.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
