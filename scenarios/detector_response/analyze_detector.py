"""Pulse-height analysis of a detector response run (output of make_detector.py).

    python scenarios/detector_response/analyze_detector.py <scenario>/output [--fwhm a,b,c] [--bin keV]

Reads the per-event energy deposits (event_edep_tN.csv, all workers), optionally
applies a Gaussian energy resolution with the MCNP "GEB" model
FWHM(E) = a + b sqrt(E + c E^2) (E, a in MeV, b in MeV^1/2, c in 1/MeV), and writes
<output>/pulse_height.csv (deposit and smeared spectra per primary) and
<output>/detector_report.json.

gamma detectors: detection efficiency (deposit > 1 keV), full-energy peak (FEP)
  efficiency (deposit within 1 keV of E), peak-to-total ratio, each intrinsic (per
  photon emitted into the simulated cone) and absolute (per photon emitted into
  4 pi, i.e. x cone fraction); the Compton edge of the deposit spectrum (largest
  step between the mean counts over 2 % of E below and above, under the photopeak)
  next to the Klein-Nishina value; single and double
  escape peak intensities above 1.022 MeV; with --fwhm, the position and FWHM of the
  smeared photopeak (full-energy events) next to the model value.
silicon detectors: most probable deposit (half-sample mode with batch error), mean,
  FWHM of the deposit distribution, and the Landau-Vavilov-Bichsel MPV of the PDG.
The resolution model is an analysis choice; its parameters must come from the user's
detector, the defaults apply no smearing.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import random
import re
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "gui"))
from g4usim_gui.output.provenance import output_evidence, output_files

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import response_physics as rp  # noqa: E402


def deposits(output: Path) -> list[float]:
    values = []
    for path in sorted(output_files(output, "event_edep_t*.csv")):
        if re.fullmatch(r"event_edep_t\d+\.csv", path.name):
            with path.open(newline="", encoding="utf-8") as handle:
                values.extend(float(r["raw_edep_MeV"]) for r in csv.DictReader(handle))
    return values


def histogram(values, width, top):
    bins = max(1, int(math.ceil(top / width)))
    counts = [0] * bins
    for v in values:
        i = int(v / width)
        if 0 <= i < bins:
            counts[i] += 1
    return counts


def fwhm_of(counts, width, start=0):
    """FWHM and position of the highest peak at or above bin `start`."""
    peak = max(range(start, len(counts)), key=lambda i: counts[i])
    half = counts[peak] / 2
    lo = peak
    while lo > 0 and counts[lo - 1] > half:
        lo -= 1
    hi = peak
    while hi < len(counts) - 1 and counts[hi + 1] > half:
        hi += 1

    def cross(i, j):   # interpolate between bin centres i (above half) and j (below)
        return (i + 0.5 + (counts[i] - half) / (counts[i] - counts[j]) * (j - i)) * width if counts[i] != counts[j] \
            else (i + 0.5) * width
    left = cross(lo, lo - 1) if lo > 0 else 0.0
    right = cross(hi, hi + 1) if hi < len(counts) - 1 else len(counts) * width
    return right - left, (peak + 0.5) * width


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("output")
    parser.add_argument("--fwhm", default="", help="a,b,c of FWHM(E) = a + b sqrt(E + c E^2) in MeV units")
    parser.add_argument("--bin", type=float, default=0.0, help="bin width in keV (default 1 keV gamma, 0.5 keV Si)")
    parser.add_argument("--seed", type=int, default=1)
    args = parser.parse_args()
    output = Path(args.output).resolve()
    meta = json.loads((output.parent / "scenario.json").read_text(encoding="utf-8"))
    summary = dict(line.split(" = ", 1) for line in
                   (output / "run_summary.txt").read_text(encoding="utf-8").splitlines() if " = " in line)
    if summary.get("run_count", "1") != "1":
        raise SystemExit("analyze_detector.py expects one run per output directory")
    events = int(summary["run_0_completed_events"])
    values = deposits(output)
    if len(values) != events:
        raise SystemExit(f"{len(values)} event rows for {events} completed events")
    energy = meta["energy_MeV"]

    smeared = None
    resolution = None
    if args.fwhm:
        a, b, c = (float(x) for x in args.fwhm.split(","))
        resolution = {"a_MeV": a, "b_MeV_sqrt": b, "c_per_MeV": c}
        rng = random.Random(args.seed)
        smeared = [max(0.0, v + rng.gauss(0.0, (a + b * math.sqrt(v + c * v * v)) / 2.3548)) if v > 0 else 0.0
                   for v in values]

    report = {"provenance": output_evidence(output).status, "scenario": meta, "events": events, "resolution": resolution}
    if meta["kind"] == "gamma":
        width = (args.bin or 1.0) / 1000.0
        top = energy * 1.1 + 0.05
        detected = [v for v in values if v > 1e-3]
        fep = [v for v in values if abs(v - energy) <= 1e-3]
        cone = meta["cone_fraction_of_4pi"]
        counts = histogram(values, width, top)
        # Compton edge: the step where the mean count over 2 % of E below the bin exceeds the mean
        # above it the most (between 0.3 E and the photopeak), with the escape peaks (+-5 keV)
        # replaced by the straight line between their neighbours
        masked = list(counts)
        for line in ([energy - rp.ME, energy - 2 * rp.ME] if energy > 2 * rp.ME else []):
            i0, i1 = max(0, int((line - 0.005) / width)), min(len(masked) - 1, int((line + 0.005) / width) + 1)
            for i in range(i0 + 1, i1):
                masked[i] = masked[i0] + (masked[i1] - masked[i0]) * (i - i0) / (i1 - i0)
        k = max(3, int(0.02 * energy / width))
        prefix = [0]
        for n in masked:
            prefix.append(prefix[-1] + n)
        lo, hi = max(k, int(0.3 * energy / width)), int((energy - 0.03) / width) - k
        edge_bin = max(range(lo, hi), key=lambda i: (prefix[i] - prefix[i - k]) - (prefix[i + k] - prefix[i]))
        report.update({
            "detection_efficiency_intrinsic": len(detected) / events,
            "detection_efficiency_absolute": len(detected) / events * cone,
            "fep_efficiency_intrinsic": len(fep) / events,
            "fep_efficiency_absolute": len(fep) / events * cone,
            "peak_to_total": len(fep) / len(detected) if detected else 0.0,
            "compton_edge_MeV": edge_bin * width,
            "compton_edge_klein_nishina_MeV": rp.compton_edge(energy),
        })
        if energy > 2 * rp.ME:
            for name, line in (("single_escape", energy - rp.ME), ("double_escape", energy - 2 * rp.ME)):
                report[f"{name}_MeV"] = line
                report[f"{name}_per_primary"] = sum(1 for v in values if abs(v - line) <= 1e-3) / events
        if smeared:
            # photopeak shape from the full-energy events: mean and 2.3548 x standard deviation
            peak = [m for v, m in zip(values, smeared) if abs(v - energy) <= 1e-3]
            mean = sum(peak) / len(peak)
            report["photopeak_position_MeV"] = mean
            report["photopeak_fwhm_MeV"] = 2.3548 * math.sqrt(sum((m - mean) ** 2 for m in peak) / (len(peak) - 1))
            report["photopeak_fwhm_model_MeV"] = a + b * math.sqrt(energy + c * energy * energy)
    else:
        width = (args.bin or 0.5) / 1000.0
        positive = [v for v in values if v > 0]
        mode, mode_error = rp.mode_with_error(positive)
        top = 5 * sorted(positive)[len(positive) // 2]
        counts = histogram(positive, width, top)
        fwhm, _ = fwhm_of(counts, width)
        mpv, xi = rp.landau_mpv(meta["particle"], energy, meta["thickness_mm"])
        report.update({"mpv_MeV": mode, "mpv_error_MeV": mode_error, "mean_MeV": sum(positive) / len(positive),
                       "fwhm_MeV": fwhm, "pdg_mpv_MeV": mpv, "pdg_xi_MeV": xi,
                       "detected_fraction": len(positive) / events})
    with (output / "pulse_height.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["e_low_MeV", "e_high_MeV", "deposit_per_primary", "smeared_per_primary"])
        raw = histogram(values, width, top)
        sm = histogram(smeared, width, top) if smeared else [0] * len(raw)
        for i, (n, m) in enumerate(zip(raw, sm)):
            if n or m:
                writer.writerow([f"{i * width:.6g}", f"{(i + 1) * width:.6g}", f"{n / events:.6g}",
                                 f"{m / events:.6g}" if smeared else ""])
    (output / "detector_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(f"{events} primaries: {meta['particle']} {energy:g} MeV, "
          + (f"{meta['crystal']} crystal" if meta["kind"] == "gamma" else f"{1000 * meta['thickness_mm']:g} um Si"))
    for key, value in report.items():
        if key not in ("scenario", "events", "resolution") and isinstance(value, float):
            print(f"  {key}: {value:.6g}")
    print(f"report: {output / 'detector_report.json'}, spectrum: {output / 'pulse_height.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
