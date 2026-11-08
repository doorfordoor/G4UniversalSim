"""Strict single-run semiconductor dose/displacement analysis (schema 2).

    python scenarios/semiconductor/analyze_device.py <scenario>/output

Missing required tallies produce null/partial and exit 2. Input/identity/schema
errors reject publication. These estimates are not scientific validation.
"""
from __future__ import annotations

import argparse
import csv
import io
from pathlib import Path
import re
import sys
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from analysis_evidence import (AnalysisEvidence, integer, json_bytes, number, publish,
                               quantity, require)

NIEL_1MEV_NEUTRON_SI = 95e-27 * 6.02214076e23 / 28.0855
SECONDS_PER_YEAR = 365.25 * 86400


def statistics(evidence):
    if 'scorer_statistics.csv' not in evidence.content:
        return {}
    fields = ('runID', 'scorer', 'quantity', 'key', 'unit', 'estimator', 'n_events', 'entries',
              'value', 'rel_error', 'uncertainty_estimator', 'uncertainty_status', 'sum', 'sum_sq')
    result = {}
    for row in evidence.csv('scorer_statistics.csv', fields, 'scorer_statistics_csv_v2'):
        require(integer(row['runID'], 'statistics runID') == 0, 'statistics run mismatch')
        key = (row['scorer'], row['quantity'], row['key'])
        require(key not in result, 'duplicate statistics run/scorer/quantity/key')
        require(integer(row['n_events'], 'statistics n_events') == evidence.events, 'statistics event coverage mismatch')
        require(integer(row['entries'], 'statistics entries') <= evidence.events, 'statistics entries exceed events')
        value = number(row['value'], 'statistics value')
        rel = number(row['rel_error'], 'statistics relative error')
        for field in ('std_error', 'fom_per_s', 'run_wall_time_s', 'mean_per_event', 'sum', 'sum_sq'):
            if row.get(field):
                number(row[field], field)
        if key[:2] in (('dose', 'weighted_dose'), ('displacement', 'ddd_total')):
            require(row['unit'] == ('Gy' if key[0] == 'dose' else 'MeV/g'), 'statistics unit mismatch')
            require(row['estimator'] == 'total' and row['uncertainty_estimator'] == 'uncorrected_event_moments_v1',
                    'statistics estimator mismatch')
            require(number(row['sum'], 'statistics sum') == value, 'total/sum mismatch')
            expected = 'insufficient_events' if evidence.events < 2 else ('zero_total' if value == 0 else 'approximate')
            require(row['uncertainty_status'] == expected, 'statistics uncertainty status mismatch')
            if value == 0:
                require(number(row['sum_sq'], 'sum_sq') == 0 and row['entries'] == '0', 'inconsistent explicit zero')
            else:
                require(integer(row['entries'], 'entries') > 0 and number(row['sum_sq'], 'sum_sq') > 0,
                        'positive total without contributing events/moments')
            row['_value'] = value
            row['_error'] = rel if expected == 'approximate' else None
        result[key] = row
    return result


def analyze(output):
    evidence = AnalysisEvidence(output)
    evidence.bind_scenario()
    meta = evidence.meta; events = evidence.events
    stats = statistics(evidence)
    area = number(meta['source_area_cm2'], 'source area', positive=True)
    flux_values = meta['sampled_integral_flux_cm2_s']
    flux = sum(number(v, 'scenario flux') for v in flux_values.values() if v is not None)
    report = evidence.report_header()
    report.update(niel_1MeV_neutron_MeV_cm2_g=NIEL_1MEV_NEUTRON_SI, regions={},
                  model_warnings=['DDD uses the selected NIEL tables; material applicability is not certified.',
                                  'GateOxide uses silicon NIEL tables despite its SiO2 material.'])
    regions = [(l['name'], f"/world_PV#0/{l['name']}_PV#0", l) for l in meta['layers']]
    regions += [(f"Slice{s['copy']}", f"/world_PV#0/Substrate_PV#0/Slice_PV#{s['copy']}", s) for s in meta['slices']]
    partial = False
    for name, key, info in regions:
        entry = dict(depth_mm=info['depth_mm'], thickness_mm=info['thickness_mm'], quantities={})
        for scorer, field, targets in (
            ('dose', 'weighted_dose', [('tid_Gy_per_primary', 1 / events), ('tid_Gy_cm2', area / events)]),
            ('displacement', 'ddd_total', [('ddd_MeV_g_per_primary', 1 / events), ('ddd_MeV_g_cm2', area / events),
                                           ('phi_eq_per_unit_fluence', area / events / NIEL_1MEV_NEUTRON_SI)])):
            row = stats.get((scorer, field, key))
            partial |= row is None
            reason = '' if row else 'missing_required_tally_evidence'
            uncertainty = row['uncertainty_status'] if row else 'unavailable'
            for target, scale in targets:
                entry[target] = row['_value'] * scale if row else None
                entry['quantities'][target] = quantity(entry[target], reason, events if row else None, uncertainty)
            error_key = 'tid_rel_error' if scorer == 'dose' else 'ddd_rel_error'
            entry[error_key] = row['_error'] if row else None
            entry['quantities'][error_key] = quantity(entry[error_key], reason or (uncertainty if entry[error_key] is None else ''),
                                                      events if row else None, uncertainty)
        if flux:
            partial |= not evidence.flux_bound
            for field, source_field in (('tid_Gy_per_year', 'tid_Gy_cm2'), ('ddd_MeV_g_per_year', 'ddd_MeV_g_cm2'),
                                        ('phi_eq_cm2_per_year', 'phi_eq_per_unit_fluence')):
                entry[field] = entry[source_field] * flux * SECONDS_PER_YEAR if evidence.flux_bound and entry[source_field] is not None else None
                reason = '' if entry[field] is not None else ('absolute_flux_not_bound_to_backend_input' if not evidence.flux_bound else 'missing_required_tally_evidence')
                entry['quantities'][field] = quantity(entry[field], reason, events)
        report['regions'][name] = entry

    outside = defaultdict(lambda: [0., 0.])
    seen = set(); track_workers = set()
    for name in sorted(evidence.content):
        match = re.fullmatch(r'displacement_volume_summary_t(\d+)\.csv', name)
        if not match:
            continue
        track_workers.add(int(match[1]))
        for row in evidence.csv(name, ('runID', 'volume_path', 'particle', 'niel_table', 'n_events', 'track_length_mm',
                                        'out_of_range_track_length_mm'), 'displacement_volume_csv_v1'):
            require(integer(row['runID'], 'displacement runID') == 0 and integer(row['n_events'], 'displacement n_events') <= events,
                    'displacement coverage mismatch')
            key = (name, row['volume_path'], row['particle'])
            require(key not in seen, 'duplicate displacement volume/particle'); seen.add(key)
            particle = row['particle']
            require(particle in meta['niel_tables'] and Path(row['niel_table']).name == Path(meta['niel_tables'][particle]).name,
                    'displacement NIEL identity mismatch')
            outside[particle][0] += number(row['track_length_mm'], 'in-range track length')
            outside[particle][1] += number(row['out_of_range_track_length_mm'], 'out-of-range track length')
            number(sum(outside[particle]), 'accumulated track length')
    complete_tracks = track_workers == evidence.workers
    report['out_of_range_fraction'] = {p: (outside[p][1] / sum(outside[p]) if complete_tracks and p in outside and sum(outside[p]) else None)
                                       for p in meta['niel_tables']}
    report['out_of_range_quantities'] = {p: quantity(v, '' if v is not None else (
                                        'incomplete_worker_track_evidence' if track_workers and not complete_tracks else
                                        'undefined_denominator' if p in outside else 'missing_track_length_evidence'))
                                        for p, v in report['out_of_range_fraction'].items()}
    report['analysis_status'] = 'partial' if partial else 'completed'
    stream = io.StringIO(newline=''); writer = csv.writer(stream)
    fields = ['depth_mm', 'thickness_mm', 'tid_Gy_cm2', 'tid_rel_error', 'ddd_MeV_g_cm2', 'ddd_rel_error', 'phi_eq_per_unit_fluence']
    writer.writerow(['region', *fields, 'tid_status', 'tid_reason', 'ddd_status', 'ddd_reason'])
    for name, entry in report['regions'].items():
        tq = entry['quantities']['tid_Gy_cm2']; dq = entry['quantities']['ddd_MeV_g_cm2']
        writer.writerow([name, *[entry[f] for f in fields], tq['status'], tq['reason'], dq['status'], dq['reason']])
    publish(evidence.root, {'depth_profile.csv': stream.getvalue().encode('utf-8'), 'device_report.json': json_bytes(report)})
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('output')
    args = parser.parse_args()
    try:
        report = analyze(Path(args.output))
    except (ValueError, OSError, KeyError, TypeError, OverflowError) as error:
        print(f'analysis rejected: {error}', file=sys.stderr)
        return 1
    print(f"analysis_schema_version=2 analysis_status={report['analysis_status']} run_status={report['run_status']}")
    print(f"{report['events']} primaries; evidence=verified_output_completion_summary (not science validation)")
    for name, entry in report['regions'].items():
        for field in ('tid_Gy_cm2', 'ddd_MeV_g_cm2', 'phi_eq_per_unit_fluence'):
            q = entry['quantities'][field]; value = 'n/a' if entry[field] is None else f'{entry[field]:.6g}'
            print(f"  {name} {field}: {value} [{q['status']}] {q['reason']}")
    print(f"report: {Path(args.output).resolve() / 'device_report.json'}")
    return 2 if report['analysis_status'] == 'partial' else 0


if __name__ == '__main__':
    raise SystemExit(main())
