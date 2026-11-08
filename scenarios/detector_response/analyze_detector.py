"""Pulse-height analysis of a verified single detector run (schema 2).

    python scenarios/detector_response/analyze_detector.py <scenario>/output [--fwhm a,b,c] [--bin keV]

Unavailable derived estimates are null with explicit quantity status. Complete
low-count event input may still yield completed/exit 0; this is not physics validation.
"""
from __future__ import annotations

import argparse
import csv
import io
import math
import random
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from analysis_evidence import (AnalysisEvidence, integer, json_bytes, number, publish,
                               quantity, require)
sys.path.insert(0, str(Path(__file__).resolve().parent))
import response_physics as rp


def deposits(evidence):
    values = []; seen = set(); workers = set()
    for name in sorted(evidence.content):
        match = re.fullmatch(r'event_edep_t(\d+)\.csv', name)
        if not match:
            continue
        workers.add(int(match[1]))
        for row in evidence.csv(name, ('runID', 'eventID', 'raw_edep_MeV', 'weighted_edep_MeV'), 'event_edep_csv_v3'):
            require(integer(row['runID'], 'event runID') == 0, 'event run mismatch')
            event = integer(row['eventID'], 'eventID')
            require(event < evidence.events and event not in seen, 'duplicate/out-of-range event ID')
            seen.add(event)
            values.append(number(row['raw_edep_MeV'], 'raw deposit'))
            number(row['weighted_edep_MeV'], 'weighted deposit')
    require(workers == evidence.workers, 'event worker coverage mismatch')
    require(len(seen) == evidence.events, 'incomplete event coverage')
    return values


def histogram(values, width, top):
    require(math.isfinite(width) and width > 0 and math.isfinite(top) and top > 0, 'invalid histogram dimensions')
    bins = max(1, int(math.ceil(top / width)))
    require(bins <= 5_000_000, 'histogram exceeds finite analysis allocation limit')
    counts = [0] * bins
    for v in values:
        require(math.isfinite(v), 'non-finite histogram input')
        i = int(v / width)
        if 0 <= i < bins:
            counts[i] += 1
    return counts


def fwhm_of(counts, width, start=0):
    """Original bin-centre interpolation, requiring both half-height crossings."""
    require(math.isfinite(width) and width > 0, 'invalid FWHM bin width')
    require(all(math.isfinite(v) and v >= 0 for v in counts), 'invalid histogram counts')
    require(isinstance(start, int) and start >= 0, 'invalid peak start')
    if start >= len(counts) or not any(counts[start:]):
        return None, None
    peak = max(range(start, len(counts)), key=lambda i: counts[i])
    half = counts[peak] / 2
    lo = hi = peak
    while lo > 0 and counts[lo - 1] > half:
        lo -= 1
    while hi < len(counts) - 1 and counts[hi + 1] > half:
        hi += 1
    position = (peak + .5) * width
    if lo == 0 or hi == len(counts) - 1:
        return None, position
    def cross(i, j):
        return (i + .5 + (counts[i] - half) / (counts[i] - counts[j]) * (j - i)) * width if counts[i] != counts[j] else (i + .5) * width
    return cross(hi, hi + 1) - cross(lo, lo - 1), position


def compton_measurement(counts, width, energy):
    masked = list(counts)
    for line in ([energy - rp.ME, energy - 2 * rp.ME] if energy > 2 * rp.ME else []):
        i0 = max(0, int((line - .005) / width))
        i1 = min(len(masked) - 1, int((line + .005) / width) + 1)
        for i in range(i0 + 1, i1):
            masked[i] = masked[i0] + (masked[i1] - masked[i0]) * (i - i0) / (i1 - i0)
    k = max(3, int(.02 * energy / width))
    lo, hi = max(k, int(.3 * energy / width)), min(len(masked) - k + 1, int((energy - .03) / width) - k)
    if hi <= lo:
        return None, 'empty_search_window'
    prefix = [0]
    for n in masked:
        prefix.append(prefix[-1] + n)
    def step(i):
        return (prefix[i] - prefix[i - k]) - (prefix[i + k] - prefix[i])
    edge = max(range(lo, hi), key=step)
    if step(edge) <= 0:
        return None, 'no_supported_compton_step'
    return edge * width, ''


def analyze(output, *, fwhm='', bin_keV=None, seed=1):
    if bin_keV is not None:
        number(bin_keV, 'bin width', positive=True)
    coefficients = None
    if fwhm:
        parts = fwhm.split(',')
        require(len(parts) == 3, '--fwhm requires a,b,c')
        coefficients = [float(v) for v in parts]
        require(all(math.isfinite(v) for v in coefficients), 'non-finite resolution parameter')
    evidence = AnalysisEvidence(output); evidence.bind_scenario(detector=True)
    meta = evidence.meta; events = evidence.events; energy = number(meta['energy_MeV'], 'energy', positive=True)
    values = deposits(evidence)
    resolution = None; smeared = None
    if coefficients is not None:
        a, b, c = coefficients
        def model(v):
            radicand = v + c * v * v
            require(math.isfinite(radicand) and radicand >= 0, 'invalid resolution radicand')
            result = a + b * math.sqrt(radicand)
            return number(result, 'resolution FWHM')
        model_energy = model(energy)
        # Validate every actual width before consuming the deterministic RNG stream.
        widths = [model(v) for v in values]
        rng = random.Random(seed)
        smeared = [max(0., v + rng.gauss(0., w / 2.3548)) if v > 0 else 0. for v, w in zip(values, widths)]
        require(all(math.isfinite(v) for v in smeared), 'non-finite smeared energy')
        resolution = dict(a_MeV=a, b_MeV_sqrt=b, c_per_MeV=c)
    report = evidence.report_header(); report.update(resolution=resolution, quantities={})
    def put(key, value, reason='', count=events, uncertainty='not_estimated', model=False):
        report[key] = value
        report['quantities'][key] = quantity(value, reason, count, uncertainty, model=model)
    if meta['kind'] == 'gamma':
        width = (bin_keV if bin_keV is not None else 1.) / 1000
        top = energy * 1.1 + .05
        detected = [v for v in values if v > 1e-3]
        fep = [v for v in values if abs(v - energy) <= 1e-3]
        cone = meta['cone_fraction_of_4pi']
        counts = histogram(values, width, top)
        edge, reason = compton_measurement(counts, width, energy)
        put('detection_efficiency_intrinsic', len(detected) / events)
        put('detection_efficiency_absolute', len(detected) / events * cone)
        put('fep_efficiency_intrinsic', len(fep) / events)
        put('fep_efficiency_absolute', len(fep) / events * cone)
        put('peak_to_total', len(fep) / len(detected) if detected else None, '' if detected else 'undefined_denominator', len(detected))
        put('compton_edge_MeV', edge, reason)
        put('compton_edge_klein_nishina_MeV', rp.compton_edge(energy), model=True)
        if energy > 2 * rp.ME:
            for name, line in (('single_escape', energy - rp.ME), ('double_escape', energy - 2 * rp.ME)):
                put(f'{name}_MeV', line, model=True)
                put(f'{name}_per_primary', sum(1 for v in values if abs(v - line) <= 1e-3) / events)
        if smeared is not None:
            peak = [m for v, m in zip(values, smeared) if abs(v - energy) <= 1e-3]
            n = len(peak); mean = sum(peak) / n if n else None
            put('photopeak_position_MeV', mean, '' if n else 'no_peak_samples', n)
            measured = 2.3548 * math.sqrt(sum((m - mean) ** 2 for m in peak) / (n - 1)) if n >= 2 else None
            put('photopeak_fwhm_MeV', measured, '' if n >= 2 else ('no_peak_samples' if n == 0 else 'insufficient_peak_samples'), n,
                'sample_standard_deviation_n_minus_1' if n >= 2 else 'unavailable')
            put('photopeak_fwhm_model_MeV', model_energy, model=True)
    else:
        width = (bin_keV if bin_keV is not None else .5) / 1000
        positive = [v for v in values if v > 0]; n = len(positive)
        mode, mode_error = rp.mode_with_error(positive)
        top = 5 * sorted(positive)[n // 2] if n else max(width, energy)
        counts = histogram(positive, width, top)
        measured, _ = fwhm_of(counts, width)
        mpv, xi = rp.landau_mpv(meta['particle'], energy, meta['thickness_mm'])
        reason = '' if n else 'no_positive_deposits'
        put('mpv_MeV', mode, reason, n)
        put('mpv_error_MeV', mode_error, reason or ('insufficient_fixed_batches' if n < 20 else ''), n,
            'fixed_20_batches' if n >= 20 else 'unavailable')
        put('mean_MeV', sum(positive) / n if n else None, reason, n)
        put('fwhm_MeV', measured, reason or ('missing_half_height_crossings' if measured is None else 'empirical_histogram_bin_interpolation'), n)
        put('pdg_mpv_MeV', mpv, model=True); put('pdg_xi_MeV', xi, model=True)
        put('detected_fraction', n / events)
    stream = io.StringIO(newline=''); writer = csv.writer(stream)
    writer.writerow(['e_low_MeV', 'e_high_MeV', 'deposit_per_primary', 'smeared_per_primary'])
    raw = histogram(values, width, top)
    sm = histogram(smeared, width, top) if smeared is not None else [0] * len(raw)
    for i, (n, m) in enumerate(zip(raw, sm)):
        if n or m:
            writer.writerow([f'{i * width:.6g}', f'{(i + 1) * width:.6g}', f'{n / events:.6g}',
                             f'{m / events:.6g}' if smeared is not None else ''])
    publish(evidence.root, {'pulse_height.csv': stream.getvalue().encode('utf-8'), 'detector_report.json': json_bytes(report)})
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('output'); parser.add_argument('--fwhm', default='')
    parser.add_argument('--bin', type=float, default=None, help='bin width in keV (positive; default 1 gamma, 0.5 Si)')
    parser.add_argument('--seed', type=int, default=1)
    args = parser.parse_args()
    try:
        report = analyze(Path(args.output), fwhm=args.fwhm, bin_keV=args.bin, seed=args.seed)
    except (ValueError, OSError, KeyError, TypeError, OverflowError, ZeroDivisionError) as error:
        print(f'analysis rejected: {error}', file=sys.stderr)
        return 1
    print('analysis_schema_version=2 analysis_status=completed run_status=completed')
    print(f"{report['events']} primaries; evidence=verified_output_completion_summary (not science validation)")
    for key, state in report['quantities'].items():
        value = 'n/a' if report[key] is None else f'{report[key]:.6g}'
        print(f"  {key}: {value} [{state['status']}, n={state['sample_count']}] {state['reason']}")
    print(f"report: {Path(args.output).resolve() / 'detector_report.json'}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
