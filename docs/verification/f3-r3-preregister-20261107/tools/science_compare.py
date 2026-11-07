#!/usr/bin/env python3
"""Read-only science comparison for F3 baseline / candidate measurement runs.

Implements the frozen F3 comparison semantics (``docs/collab/decisions/
20261107-f3-contract-freeze.md``).  This tool never runs Geant4: it reads only
the files the backend registered in ``run_metadata.json`` for one run, so it can
be reviewed and exercised against existing outputs before any formal measurement.

Rounding rule: numeric values are compared after normalising to 12 significant
digits (the printed backend precision).  Integral columns accept integral
doubles (ROOT stores some counters as ``double``) but reject fractional or
non-finite values instead of truncating them.

Usage:
    python science_compare.py describe --run DIR --workload hits --format csv --out JSON
    python science_compare.py compare --baseline DIR --candidate DIR \
        --workload hits --format root --out JSON

Exit codes: 0 = pass / described, 1 = scientific difference (report written when
``--out`` is given), 2 = usage / unreadable / unclassifiable input.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
import sys

REL_TOL = 1e-9
EVENTS = 1000
MESH_BINS = 24
MESH_QUANTITIES = {"edep": "MeV", "dose": "Gy", "flux": "percm2"}
MESH_NAME = "benchmarkMesh"

TEXT_COLUMNS = {"particle", "process", "volume", "volume_path", "volume_name",
                "scorer", "quantity", "key", "name", "unit", "estimator",
                "uncertainty_estimator", "uncertainty_status", "mesh",
                "particles", "study", "label"}

HITS_COLUMNS = ["runID", "eventID", "trackID", "parentID", "particle", "edep_MeV", "ndep_MeV",
                "stepLength_mm", "x0_mm", "y0_mm", "z0_mm", "x1_mm", "y1_mm", "z1_mm",
                "px", "py", "pz", "kineticEnergy_MeV", "process", "volume", "weight"]
EVENT_COLUMNS = ["runID", "eventID", "raw_edep_MeV", "weighted_edep_MeV"]
MESH_COLUMNS = ["runID", "mesh", "quantity", "unit", "i0", "i1", "i2", "sum", "sum_sq",
                "entries", "n_events", "rel_error", "uncertainty_estimator", "uncertainty_status"]
STATISTICS_COLUMNS = ["runID", "scorer", "quantity", "key", "name", "unit", "estimator",
                      "n_events", "entries", "value", "mean_per_event", "std_error", "rel_error",
                      "fom_per_s", "run_wall_time_s", "sum", "sum_sq", "uncertainty_estimator",
                      "uncertainty_status"]
STATISTICS_EVIDENCE = {"fom_per_s", "run_wall_time_s"}

EDEP_SUMMARY_COLUMNS = ["name", "raw_edep_MeV", "weighted_edep_MeV",
                        "raw_edep_sum_sq_MeV2", "weighted_edep_sum_sq_MeV2", "n_events"]
EDEP_SUMMARY_SUM = ["raw_edep_MeV", "weighted_edep_MeV",
                    "raw_edep_sum_sq_MeV2", "weighted_edep_sum_sq_MeV2"]
DOSE_SUMMARY_COLUMNS = ["runID", "volume_path", "volume_name", "mass_kg",
                        "raw_edep_MeV", "weighted_edep_MeV", "raw_dose_Gy", "weighted_dose_Gy",
                        "raw_edep_sum_sq_MeV2", "weighted_edep_sum_sq_MeV2", "n_events"]
DOSE_SUMMARY_SUM = ["raw_edep_MeV", "weighted_edep_MeV", "raw_dose_Gy", "weighted_dose_Gy",
                    "raw_edep_sum_sq_MeV2", "weighted_edep_sum_sq_MeV2"]
DOSE_SUMMARY_KEYS = ["runID", "volume_path", "volume_name"]
FLUENCE_SUMMARY_COLUMNS = ["runID", "volume_path", "volume_name", "volume_mm3",
                           "raw_track_length_mm", "weighted_track_length_mm",
                           "raw_fluence_mm-2", "weighted_fluence_mm-2",
                           "raw_track_length_sum_sq_mm2",
                           "weighted_track_length_sum_sq_mm2", "n_events"]
FLUENCE_SUMMARY_SUM = ["raw_track_length_mm", "weighted_track_length_mm",
                       "raw_fluence_mm-2", "weighted_fluence_mm-2",
                       "raw_track_length_sum_sq_mm2",
                       "weighted_track_length_sum_sq_mm2"]
FLUENCE_SUMMARY_KEYS = ["runID", "volume_path", "volume_name"]
HISTOGRAM_COLUMNS = ["bin", "low_edge_MeV", "high_edge_MeV", "center_MeV", "count"]

SUMMARIES = {
    "edep_volume_summary": ("csv", EDEP_SUMMARY_COLUMNS, EDEP_SUMMARY_SUM,
                            ["name"], []),
    "edep_particle_summary": ("csv", EDEP_SUMMARY_COLUMNS, EDEP_SUMMARY_SUM,
                              ["name"], []),
    "dose_volume_summary": ("csv", DOSE_SUMMARY_COLUMNS, DOSE_SUMMARY_SUM,
                            DOSE_SUMMARY_KEYS, ["mass_kg"]),
    "fluence_volume_summary": ("csv", FLUENCE_SUMMARY_COLUMNS, FLUENCE_SUMMARY_SUM,
                               FLUENCE_SUMMARY_KEYS, ["volume_mm3"]),
}
UNSUPPORTED_SUMMARIES = ("let_volume_summary", "displacement_volume_summary")

ROOT_OBJECTS = {
    "hits": HITS_COLUMNS + ["threadID"],
    "events": EVENT_COLUMNS + ["threadID"],
    "mesh": ["runID", "threadID", "mesh", "quantity", "unit", "i0", "i1", "i2",
             "sum", "sum_sq", "entries", "n_events"],
    "edep_volume": ["runID", "threadID", "name", "raw_edep_MeV", "weighted_edep_MeV",
                    "raw_edep_sum_sq_MeV2", "weighted_edep_sum_sq_MeV2", "n_events"],
    "edep_particle": ["runID", "threadID", "name", "raw_edep_MeV", "weighted_edep_MeV",
                      "raw_edep_sum_sq_MeV2", "weighted_edep_sum_sq_MeV2", "n_events"],
    "dose": ["runID", "threadID", "volume_path", "volume_name", "mass_kg", "raw_edep_MeV",
             "weighted_edep_MeV", "raw_dose_Gy", "weighted_dose_Gy",
             "raw_edep_sum_sq_MeV2", "weighted_edep_sum_sq_MeV2", "n_events"],
    "fluence": ["runID", "threadID", "volume_path", "volume_name", "volume_mm3",
                "raw_track_length_mm", "weighted_track_length_mm",
                "raw_fluence_mm-2", "weighted_fluence_mm-2",
                "raw_track_length_sum_sq_mm2", "weighted_track_length_sum_sq_mm2",
                "n_events"],
    "let": ["runID", "threadID", "volume_path", "volume_name", "particles", "steps",
            "sum_wl_mm", "sum_wSl_MeV", "sum_wS2l_MeV2_per_mm", "let_t_keV_per_um",
            "let_d_keV_per_um", "sum_sq_wl_mm2", "sum_sq_wSl_MeV2",
            "sum_sq_wS2l_MeV4_per_mm2", "sum_wl_x_wSl_MeV_mm",
            "sum_wSl_x_wS2l_MeV3_per_mm", "n_events"],
}
HISTOGRAM_OBJECTS = {"edep_raw", "edep_weighted"}

SUM_COLUMNS = {"raw_edep_MeV", "weighted_edep_MeV", "raw_edep_sum_sq_MeV2",
               "weighted_edep_sum_sq_MeV2", "raw_dose_Gy", "weighted_dose_Gy",
               "raw_track_length_mm", "weighted_track_length_mm", "raw_fluence_mm-2",
               "weighted_fluence_mm-2", "raw_track_length_sum_sq_mm2",
               "weighted_track_length_sum_sq_mm2", "sum_wl_mm", "sum_wSl_MeV",
               "sum_wS2l_MeV2_per_mm", "sum_sq_wl_mm2", "sum_sq_wSl_MeV2",
               "sum_sq_wS2l_MeV4_per_mm2", "sum_wl_x_wSl_MeV_mm",
               "sum_wSl_x_wS2l_MeV3_per_mm"}
CONSTANT_COLUMNS = {"mass_kg", "volume_mm3"}
RATIO_COLUMNS = {"let_t_keV_per_um", "let_d_keV_per_um"}
MOMENT_KEY_COLUMNS = {"runID", "volume_path", "volume_name", "name", "particles"}
MOMENT_LABEL_COLUMNS = {"particles", "name", "unit", "estimator", "uncertainty_estimator"}

INTEGRAL_COLUMNS = {"runID", "eventID", "trackID", "parentID", "threadID", "i0", "i1", "i2",
                    "entries", "n_events", "steps", "bin"}

# Metadata keys that are evidence (paths, ids, clocks, identity) rather than
# science configuration.  They are recorded, not compared for equality.  Any
# key not matched here is compared, so a new science-relevant field can never be
# silently dropped by an over-broad prefix rule.
VARIABLE_METADATA = {
    "execution_id", "summary_generated_at", "generated_file_count",
    "main_config", "output_dir", "actual_output_dir", "planned_output_dir",
    "initial_engine_seed", "build_git_commit", "build_git_source_state",
    "source_fingerprint", "git_dirty", "output_failure_message",
}
EVIDENCE_SUFFIXES = ("_dir", "_file", "_path", "_utc", "_at")


class CompareError(RuntimeError):
    pass


def is_evidence_metadata(key):
    if key in VARIABLE_METADATA:
        return True
    if key.endswith(EVIDENCE_SUFFIXES):
        return True
    return False


def canon_float(text):
    try:
        value = float(text)
    except (TypeError, ValueError) as error:
        raise CompareError(f"not a number: {text!r}") from error
    if not math.isfinite(value):
        raise CompareError(f"non-finite value: {text!r}")
    if value == 0.0:
        return "0"
    return format(value, ".12g")


def canon_integral(text):
    try:
        numeric = float(text)
    except (TypeError, ValueError) as error:
        raise CompareError(f"not an integer: {text!r}") from error
    if not math.isfinite(numeric) or not numeric.is_integer():
        raise CompareError(f"not an integer: {text!r}")
    return str(int(numeric))


def canon_value(column, raw):
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8")
    if column in TEXT_COLUMNS:
        return str(raw)
    text = raw if isinstance(raw, str) else str(raw)
    if column in INTEGRAL_COLUMNS:
        return canon_integral(text)
    return canon_float(text)


def read_csv(path, expected_columns, *, allow_evidence=()):
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        header = reader.fieldnames or []
        if header != expected_columns:
            raise CompareError(f"{path.name}: header differs from frozen schema\n"
                               f"  expected: {expected_columns}\n  actual:   {header}")
        rows = list(reader)
    for row in rows:
        for name in header:
            if name in allow_evidence:
                continue
            canon_value(name, row[name])
    return rows


def metadata_of(output_dir):
    path = Path(output_dir) / "run_metadata.json"
    if not path.is_file():
        raise CompareError(f"{output_dir}: run_metadata.json is missing")
    return json.loads(path.read_bytes())


def registered_names(metadata):
    rows = metadata.get("generated_files")
    if not isinstance(rows, list):
        raise CompareError("run_metadata.json: generated_files is missing")
    return [Path(str(row["path"])).name for row in rows]


def classify(filename):
    if filename.startswith("hits_t") and filename.endswith(".csv"):
        return "hits_csv"
    if filename.startswith("event_edep_t") and filename.endswith(".csv"):
        return "event_csv"
    if filename.startswith("scoring_mesh") and filename.endswith(".csv"):
        return "mesh_csv"
    if filename.startswith("scorer_statistics") and filename.endswith(".csv"):
        return "statistics_csv"
    if filename == "hist_edep_raw" or (
            filename.startswith("hist_edep_raw_t") and filename.endswith(".csv")):
        return "histogram_raw_csv"
    if filename == "hist_edep_weighted" or (
            filename.startswith("hist_edep_weighted_t") and filename.endswith(".csv")):
        return "histogram_weighted_csv"
    for role in SUMMARIES:
        if filename.startswith(role + "_t") and filename.endswith(".csv"):
            return role
    for role in UNSUPPORTED_SUMMARIES:
        if filename.startswith(role + "_t") and filename.endswith(".csv"):
            return role
    if filename.startswith("spectrum_") and filename.endswith(".csv"):
        return "spectrum_csv"
    if filename == "g4usim.root":
        return "root"
    if filename in {"run_metadata.json", "run_summary.txt"} or filename.startswith("effective_config"):
        return "evidence"
    return "unknown"


class RunData:
    def __init__(self, output_dir):
        self.output_dir = Path(output_dir)
        self.metadata = metadata_of(self.output_dir)
        self.names = registered_names(self.metadata)
        self.paths = [self.output_dir / name for name in self.names]
        roles = defaultdict(list)
        for name, path in zip(self.names, self.paths):
            role = classify(name)
            if role == "unknown":
                raise CompareError(f"{self.output_dir}: registered file {name!r} has no frozen "
                                   "scientific role; an unclassified scientific output cannot be "
                                   "silently ignored")
            if role in UNSUPPORTED_SUMMARIES:
                raise CompareError(f"{self.output_dir}: {name!r} is a {role} output; the frozen "
                                   "F3 loads disable LET/DDD and a non-empty consumer needs an "
                                   "explicit contract decision")
            if role == "spectrum_csv":
                raise CompareError(f"{self.output_dir}: {name!r} is a phase-space/spectrum output; "
                                   "the frozen F3 loads do not enable it and no comparison rule "
                                   "exists")
            roles[role].append(path)
        self.roles = dict(roles)
        self.runs = self.metadata.get("runs") or []
        self.completed_events = (self.runs[0]["completed_events"]
                                 if len(self.runs) == 1 else None)
        self.csv_cache = {}
        self.root_cache = None

    def files(self, role):
        return self.roles.get(role, [])

    def csv_rows(self, role, expected_columns, *, allow_evidence=()):
        key = (role, tuple(expected_columns), tuple(allow_evidence))
        if key not in self.csv_cache:
            rows = []
            for path in self.files(role):
                rows.extend(read_csv(path, expected_columns, allow_evidence=allow_evidence))
            self.csv_cache[key] = rows
        return self.csv_cache[key]

    def metrics(self):
        return {"registered_files": len(self.names),
                "registered_bytes": sum(path.stat().st_size for path in self.paths),
                "roles": {role: len(paths) for role, paths in sorted(self.roles.items())},
                "completed_events": self.completed_events}

    def root(self):
        if not self.files("root"):
            raise CompareError(f"{self.output_dir}: no registered g4usim.root")
        if self.root_cache is None:
            import uproot
            self.root_cache = uproot.open(self.files("root")[0])
        return self.root_cache


def similarity_check(label, left, right, failures):
    if not (math.isfinite(left) and math.isfinite(right)):
        failures.append({"check": label, "left": left, "right": right,
                         "reason": "non-finite value"})
        return
    if left == right:
        return
    tolerance = REL_TOL * max(abs(left), abs(right))
    if abs(left - right) <= tolerance:
        return
    failures.append({"check": label, "left": left, "right": right,
                     "difference": left - right, "tolerance": tolerance})


def compare_multiset(label, left_rows, right_rows, failures):
    left = Counter(left_rows)
    right = Counter(right_rows)
    if left == right:
        return {"check": label, "rows": sum(left.values()), "status": "match"}
    only_left = list((left - right).items())[:5]
    only_right = list((right - left).items())[:5]
    failures.append({"check": label, "left_rows": sum(left.values()),
                     "right_rows": sum(right.values()),
                     "count_difference": sum((left - right).values()),
                     "only_left_sample": only_left, "only_right_sample": only_right})
    return {"check": label, "rows": sum(left.values()), "status": "differs"}


def compare_metadata(left, right, failures):
    left_values = left.metadata.get("values") or {}
    right_values = right.metadata.get("values") or {}
    compared = {}
    unclassified = []
    for key in sorted(set(left_values) | set(right_values)):
        if is_evidence_metadata(key):
            continue
        if key not in left_values or key not in right_values:
            unclassified.append({"key": key, "reason": "present on only one side"})
            continue
        a, b = left_values[key], right_values[key]
        if key == "effective_geometry_config" or key == "geometry_config":
            a, b = Path(str(a)).name, Path(str(b)).name
        compared[key] = {"left": a, "right": b}
        if a != b:
            failures.append({"check": f"metadata:{key}", "left": a, "right": b})
    if unclassified:
        failures.extend({"check": "metadata:unclassified", **item} for item in unclassified)
    return compared


def require_completed(run, workload, fmt):
    values = run.metadata.get("values") or {}
    if values.get("status") != "completed":
        raise CompareError(f"{run.output_dir}: run status is {values.get('status')!r}, expected 'completed'")
    if values.get("output_failure_status") not in (None, "none"):
        raise CompareError(f"{run.output_dir}: output_failure_status is "
                           f"{values.get('output_failure_status')!r}")
    if len(run.runs) != 1:
        raise CompareError(f"{run.output_dir}: expected exactly one run, found {len(run.runs)}")
    record = run.runs[0]
    if record.get("run_id") != 0:
        raise CompareError(f"{run.output_dir}: run_id {record.get('run_id')!r}, expected 0")
    if record.get("planned_events") != EVENTS or record.get("completed_events") != EVENTS:
        raise CompareError(f"{run.output_dir}: planned/completed events "
                           f"{record.get('planned_events')!r}/{record.get('completed_events')!r}, "
                           f"expected {EVENTS}/{EVENTS}")
    allowed = {"evidence", "statistics_csv", "histogram_raw_csv", "histogram_weighted_csv"}
    if fmt == "root":
        if not run.files("root"):
            raise CompareError(f"{run.output_dir}: root format run registered no g4usim.root")
        for role in ("hits_csv", "event_csv", "mesh_csv"):
            if run.files(role):
                raise CompareError(f"{run.output_dir}: root format run registered {role}; the "
                                   "frozen matrix keeps CSV scoring files out of root runs")
    else:
        if run.files("root"):
            raise CompareError(f"{run.output_dir}: csv format run registered g4usim.root")
        if workload == "hits":
            if not run.files("hits_csv") or not run.files("event_csv"):
                raise CompareError(f"{run.output_dir}: hits load needs hits and event_edep CSV files")
            if run.files("mesh_csv"):
                raise CompareError(f"{run.output_dir}: hits load must not write mesh CSV")
        else:
            if not run.files("mesh_csv"):
                raise CompareError(f"{run.output_dir}: mesh load needs a scoring_mesh CSV file")
            if run.files("hits_csv") or run.files("event_csv"):
                raise CompareError(f"{run.output_dir}: mesh load must not write hits/event CSV")
    extras = set(run.roles) - allowed - {"root", "hits_csv", "event_csv", "mesh_csv"} - set(SUMMARIES)
    if extras:
        raise CompareError(f"{run.output_dir}: unexpected frozen-role outputs {sorted(extras)}")


def hits_tuples(rows):
    return [tuple(canon_value(column, row[column]) for column in HITS_COLUMNS) for row in rows]


def event_tuples(rows):
    return [tuple(canon_value(column, row[column]) for column in EVENT_COLUMNS) for row in rows]


def merge_mesh_rows(rows, global_events, *, from_root, failures):
    merged = {}
    seen = set()
    worker_events = {}
    for row in rows:
        key = (canon_integral(str(row["runID"])), str(row["mesh"]), str(row["quantity"]),
               canon_integral(str(row["i0"])), canon_integral(str(row["i1"])),
               canon_integral(str(row["i2"])))
        thread = canon_integral(str(row["threadID"])) if from_root else None
        if (key, thread) in seen:
            raise CompareError(f"mesh: duplicate worker row for key {key}, thread {thread}")
        seen.add((key, thread))
        quantity = key[2]
        if quantity not in MESH_QUANTITIES:
            raise CompareError(f"mesh: quantity {quantity!r} is not one of "
                               f"{sorted(MESH_QUANTITIES)}")
        if str(row["unit"]) != MESH_QUANTITIES[quantity]:
            raise CompareError(f"mesh: quantity {quantity!r} unit {row['unit']!r}, expected "
                               f"{MESH_QUANTITIES[quantity]!r}")
        if key[1] != MESH_NAME:
            raise CompareError(f"mesh: mesh name {key[1]!r}, expected {MESH_NAME!r}")
        for axis, value in zip(("i0", "i1", "i2"), key[3:]):
            index = int(value)
            if not 0 <= index < MESH_BINS:
                raise CompareError(f"mesh: {axis}={index} outside 0..{MESH_BINS - 1}")
        events = int(canon_integral(str(row["n_events"])))
        if not 0 <= events <= global_events:
            raise CompareError(f"mesh: n_events={events} outside 0..{global_events}")
        if from_root:
            if thread in worker_events and worker_events[thread] != events:
                raise CompareError(f"mesh: inconsistent local n_events for thread {thread}")
            worker_events[thread] = events
        total = float(row["sum"])
        total_sq = float(row["sum_sq"])
        entries = int(canon_integral(str(row["entries"])))
        if not math.isfinite(total) or not math.isfinite(total_sq):
            raise CompareError(f"mesh: non-finite moments for key {key}")
        if entries < 0:
            raise CompareError(f"mesh: negative entries {entries} for key {key}")
        entry = merged.setdefault(key, {"unit": str(row["unit"]), "sum": 0.0, "sum_sq": 0.0,
                                        "entries": 0, "n_events": 0, "workers": [],
                                        "rel_error": set(), "estimator": set(),
                                        "status": set()})
        entry["sum"] += total
        entry["sum_sq"] += total_sq
        entry["entries"] += entries
        entry["n_events"] += events
        entry["workers"].append(thread if thread is not None else "csv")
        if not from_root:
            entry["rel_error"].add(canon_float(str(row.get("rel_error", ""))))
            entry["estimator"].add(str(row.get("uncertainty_estimator", "")))
            entry["status"].add(str(row.get("uncertainty_status", "")))
    if from_root and sum(worker_events.values()) > global_events:
        raise CompareError("mesh: observed worker event totals exceed the global run N")
    for key, entry in merged.items():
        if from_root:
            entry["n_events"] = global_events
        elif entry["n_events"] != global_events:
            failures.append({"check": "mesh:n_events", "key": key,
                             "merged": entry["n_events"], "expected": global_events})
    return merged


def compare_mesh(label, left_rows, right_rows, global_events, failures, *, from_root):
    left = merge_mesh_rows(left_rows, global_events, from_root=from_root, failures=failures)
    right = merge_mesh_rows(right_rows, global_events, from_root=from_root, failures=failures)
    keys = set(left) | set(right)
    for key in sorted(keys):
        a, b = left.get(key), right.get(key)
        if a is None or b is None:
            failures.append({"check": f"{label}:key", "key": key,
                             "left": "present" if a else "absent",
                             "right": "present" if b else "absent"})
            continue
        if a["unit"] != b["unit"]:
            failures.append({"check": f"{label}:unit", "key": key,
                             "left": a["unit"], "right": b["unit"]})
        similarity_check(f"{label}:sum", a["sum"], b["sum"], failures)
        similarity_check(f"{label}:sum_sq", a["sum_sq"], b["sum_sq"], failures)
        if a["entries"] != b["entries"]:
            failures.append({"check": f"{label}:entries", "key": key,
                             "left": a["entries"], "right": b["entries"]})
        if not from_root:
            for field in ("rel_error", "estimator", "status"):
                if a[field] != b[field]:
                    failures.append({"check": f"{label}:{field}", "key": key,
                                     "left": sorted(a[field]), "right": sorted(b[field])})
    for side, table in (("left", left), ("right", right)):
        quantities = {key[2] for key in table}
        if quantities and quantities != set(MESH_QUANTITIES):
            failures.append({"check": f"{label}:{side}:quantities",
                             "quantities": sorted(quantities)})
    return {"check": label, "keys": len(keys)}


def merge_summary_rows(columns, sum_columns, key_columns, constant_columns, rows):
    merged = {}
    for row in rows:
        key = tuple(canon_value(column, row[column]) for column in key_columns)
        entry = merged.setdefault(key, {"sums": {column: 0.0 for column in sum_columns},
                                        "constants": {}, "n_events": []})
        for column in sum_columns:
            entry["sums"][column] += float(canon_float(row[column]))
        for column in constant_columns:
            if column not in entry["constants"]:
                entry["constants"][column] = float(canon_float(row[column]))
        entry["n_events"].append(int(canon_integral(str(row["n_events"]))))
    return merged


def compare_summary(role, columns, sum_columns, key_columns, constant_columns,
                    left_rows, right_rows, global_events, failures):
    for side, rows in (("left", left_rows), ("right", right_rows)):
        for row in rows:
            events = int(canon_integral(str(row["n_events"])))
            if not 0 <= events <= global_events:
                raise CompareError(f"{role}: {side} n_events={events} outside 0..{global_events}")
    left = merge_summary_rows(columns, sum_columns, key_columns, constant_columns, left_rows)
    right = merge_summary_rows(columns, sum_columns, key_columns, constant_columns, right_rows)
    if set(left) != set(right):
        failures.append({"check": f"csv:{role}:keys",
                         "only_left": sorted(map(str, set(left) - set(right)))[:5],
                         "only_right": sorted(map(str, set(right) - set(left)))[:5]})
    for key in sorted(set(left) & set(right)):
        a, b = left[key], right[key]
        for column in sum_columns:
            similarity_check(f"csv:{role}:{column}", a["sums"][column], b["sums"][column],
                             failures)
        for column in constant_columns:
            similarity_check(f"csv:{role}:{column}", a["constants"][column],
                             b["constants"][column], failures)
    return {"check": f"csv:{role}", "keys": len(left)}


def merge_histogram(rows):
    edges = {}
    counts = defaultdict(float)
    for row in rows:
        index = int(canon_integral(str(row["bin"])))
        low = float(canon_float(row["low_edge_MeV"]))
        high = float(canon_float(row["high_edge_MeV"]))
        center = float(canon_float(row["center_MeV"]))
        count = float(canon_float(row["count"]))
        if count < 0 or high <= low:
            raise CompareError(f"histogram: invalid bin {index}")
        boundary = (low, high, center)
        if index in edges and edges[index] != boundary:
            raise CompareError(f"histogram: inconsistent worker boundaries for bin {index}")
        if abs((low + high) / 2.0 - center) > 1e-9 * max(1.0, abs(center)):
            raise CompareError(f"histogram: bin {index} centre is not the edge midpoint")
        edges[index] = boundary
        counts[index] += count
    if not edges or sorted(edges) != list(range(len(edges))):
        raise CompareError("histogram: empty or non-contiguous bins")
    for index in range(1, len(edges)):
        if edges[index - 1][1] != edges[index][0]:
            raise CompareError(f"histogram: discontinuous boundaries at bin {index}")
    return {"counts": dict(counts), "edges": edges}

def compare_histogram_csv(left_rows, right_rows, failures, label="csv:histogram"):
    left = merge_histogram(left_rows)
    right = merge_histogram(right_rows)
    if set(left["counts"]) != set(right["counts"]):
        failures.append({"check": label + ":bins"})
    for index in sorted(set(left["counts"]) & set(right["counts"])):
        for position, field in enumerate(("low", "high", "center")):
            similarity_check(f"{label}:bin{index}:{field}", left["edges"][index][position],
                             right["edges"][index][position], failures)
        similarity_check(f"{label}:bin{index}", left["counts"][index], right["counts"][index], failures)
    return {"check": label, "bins": len(left["counts"]), "entries": sum(left["counts"].values())}

def compare_statistics(run_left, run_right, failures):
    left = run_left.csv_rows("statistics_csv", STATISTICS_COLUMNS,
                             allow_evidence=STATISTICS_EVIDENCE)
    right = run_right.csv_rows("statistics_csv", STATISTICS_COLUMNS,
                               allow_evidence=STATISTICS_EVIDENCE)
    if not left and not right:
        return
    if not left or not right:
        failures.append({"check": "statistics", "left_rows": len(left),
                         "right_rows": len(right)})
        return
    key_columns = ["runID", "scorer", "quantity", "key"]
    numeric = ["n_events", "entries", "value", "mean_per_event", "std_error", "rel_error",
               "sum", "sum_sq"]
    labels = ["name", "unit", "estimator", "uncertainty_estimator", "uncertainty_status"]
    left_table = {tuple(row[c] for c in key_columns): row for row in left}
    right_table = {tuple(row[c] for c in key_columns): row for row in right}
    if len(left_table) != len(left) or len(right_table) != len(right):
        raise CompareError("statistics: duplicate (runID,scorer,quantity,key) rows")
    if set(left_table) != set(right_table):
        failures.append({"check": "statistics:keys",
                         "only_left": sorted(map(str, set(left_table) - set(right_table)))[:5],
                         "only_right": sorted(map(str, set(right_table) - set(left_table)))[:5]})
    for key in sorted(set(left_table) & set(right_table), key=str):
        a, b = left_table[key], right_table[key]
        for column in labels:
            if a[column] != b[column]:
                failures.append({"check": f"statistics:{key}:{column}",
                                 "left": a[column], "right": b[column]})
        for column in numeric:
            similarity_check(f"statistics:{key}:{column}", float(a[column]),
                             float(b[column]), failures)


def compare_csv(run_left, run_right, workload, failures):
    if workload == "hits":
        left_hits = run_left.csv_rows("hits_csv", HITS_COLUMNS)
        right_hits = run_right.csv_rows("hits_csv", HITS_COLUMNS)
        if not left_hits or not right_hits:
            failures.append({"check": "csv:hits", "left_rows": len(left_hits),
                             "right_rows": len(right_hits)})
        else:
            compare_multiset("csv:hits", hits_tuples(left_hits), hits_tuples(right_hits), failures)
            for side, rows in (("left", left_hits), ("right", right_hits)):
                for row in rows:
                    event = int(canon_integral(str(row["eventID"])))
                    if not 0 <= event < EVENTS:
                        raise CompareError(f"csv:hits: eventID {event} outside 0..{EVENTS - 1}")
        left_events = run_left.csv_rows("event_csv", EVENT_COLUMNS)
        right_events = run_right.csv_rows("event_csv", EVENT_COLUMNS)
        if not left_events or not right_events:
            failures.append({"check": "csv:events", "left_rows": len(left_events),
                             "right_rows": len(right_events)})
        else:
            compare_multiset("csv:events", event_tuples(left_events),
                             event_tuples(right_events), failures)
            for side, rows in (("left", left_events), ("right", right_events)):
                events = sorted(int(canon_integral(str(row["eventID"]))) for row in rows)
                if events != list(range(EVENTS)):
                    failures.append({"check": f"csv:events:{side}:event_set",
                                     "rows": len(rows)})
        mesh_rows = run_left.files("mesh_csv") + run_right.files("mesh_csv")
        if mesh_rows:
            failures.append({"check": "csv:mesh_unexpected", "files": len(mesh_rows)})
    else:
        left_mesh = run_left.csv_rows("mesh_csv", MESH_COLUMNS)
        right_mesh = run_right.csv_rows("mesh_csv", MESH_COLUMNS)
        compare_mesh("csv:mesh", left_mesh, right_mesh, EVENTS, failures, from_root=False)
    for role, (_, columns, sum_columns, key_columns, constants) in SUMMARIES.items():
        left_rows = run_left.csv_rows(role, columns) if run_left.files(role) else []
        right_rows = run_right.csv_rows(role, columns) if run_right.files(role) else []
        if bool(left_rows) != bool(right_rows):
            failures.append({"check": f"csv:{role}", "left_rows": len(left_rows),
                             "right_rows": len(right_rows)})
        elif left_rows:
            compare_summary(role, columns, sum_columns, key_columns, constants,
                            left_rows, right_rows, EVENTS, failures)
    for role in ("histogram_raw_csv", "histogram_weighted_csv"):
        left_hist = run_left.csv_rows(role, HISTOGRAM_COLUMNS) if run_left.files(role) else []
        right_hist = run_right.csv_rows(role, HISTOGRAM_COLUMNS) if run_right.files(role) else []
        if bool(left_hist) != bool(right_hist):
            failures.append({"check": "csv:histogram:" + role})
        elif left_hist:
            compare_histogram_csv(left_hist, right_hist, failures, "csv:histogram:" + role)
    compare_statistics(run_left, run_right, failures)


def root_branches(tree):
    return list(tree.keys())


def tree_entries(tree, name):
    raw = tree.num_entries
    if isinstance(raw, bool):
        raise CompareError(f"root:{name}: invalid num_entries {raw!r}")
    numeric = float(raw)
    if not math.isfinite(numeric) or not numeric.is_integer():
        raise CompareError(f"root:{name}: non-integral num_entries {raw!r}")
    return int(numeric)


def tree_rows(tree, branches, name):
    entries = tree_entries(tree, name)
    data = tree.arrays(branches, library="np")
    for branch in branches:
        array = data[branch]
        try:
            length = len(array)
        except TypeError as error:
            raise CompareError(f"root:{name}.{branch}: read as a scalar, expected an array") from error
        if length != entries:
            raise CompareError(f"root:{name}.{branch}: array length {length} differs from "
                               f"num_entries {entries}")
    return [{branch: data[branch][index] for branch in branches} for index in range(entries)]


def root_tuples(rows, columns):
    integral = {"runID", "eventID", "trackID", "parentID"}
    canonical = []
    for row in rows:
        item = []
        for column in columns:
            if column == "threadID":
                continue
            value = row[column]
            if column in integral:
                item.append(canon_integral(str(value)))
            elif column in TEXT_COLUMNS:
                item.append(str(value))
            else:
                item.append(canon_float(str(float(value))))
        canonical.append(tuple(item))
    return canonical


def compare_root(run_left, run_right, workload, failures):
    left = run_left.root()
    right = run_right.root()
    keys_left = {key.split(";")[0] for key in left.keys()}
    keys_right = {key.split(";")[0] for key in right.keys()}
    allowed = set(ROOT_OBJECTS) | HISTOGRAM_OBJECTS
    for side, keys in (("left", keys_left), ("right", keys_right)):
        if keys - allowed:
            failures.append({"check": f"root:{side}:unclassified-objects",
                             "objects": sorted(keys - allowed)})
        if allowed - keys:
            failures.append({"check": f"root:{side}:missing-objects",
                             "objects": sorted(allowed - keys)})
    for name in sorted(set(ROOT_OBJECTS) & keys_left & keys_right):
        tree_left, tree_right = left[name], right[name]
        branches_left = root_branches(tree_left)
        branches_right = root_branches(tree_right)
        if sorted(branches_left) != sorted(ROOT_OBJECTS[name]):
            failures.append({"check": f"root:{name}:branches",
                             "expected": ROOT_OBJECTS[name], "actual": branches_left})
            continue
        if sorted(branches_right) != sorted(branches_left):
            failures.append({"check": f"root:{name}:branches-right",
                             "left": branches_left, "right": branches_right})
            continue
        if name in {"hits", "events"}:
            rows_left = tree_rows(tree_left, ROOT_OBJECTS[name], name)
            rows_right = tree_rows(tree_right, ROOT_OBJECTS[name], name)
            compare_multiset(f"root:{name}", root_tuples(rows_left, ROOT_OBJECTS[name]),
                             root_tuples(rows_right, ROOT_OBJECTS[name]), failures)
            if workload == "hits":
                for side, rows in (("left", rows_left), ("right", rows_right)):
                    ids = [int(canon_integral(str(row["eventID"]))) for row in rows]
                    valid = (sorted(ids) == list(range(EVENTS)) if name == "events" else
                             len(rows) >= EVENTS and all(0 <= value < EVENTS for value in ids))
                    if not valid or any(canon_integral(str(row["runID"])) != "0" for row in rows):
                        failures.append({"check": f"root:{name}:{side}:qualification", "rows": len(rows)})
        elif name == "mesh":
            compare_mesh("root:mesh",
                         tree_rows(tree_left, ROOT_OBJECTS[name], name),
                         tree_rows(tree_right, ROOT_OBJECTS[name], name),
                         EVENTS, failures, from_root=True)
        else:
            compare_moment_tree(name, tree_left, tree_right, failures)
    for name in sorted(HISTOGRAM_OBJECTS & keys_left & keys_right):
        histogram_compare(name, left[name], right[name], failures)
    if workload == "hits":
        for side, root in (("left", left), ("right", right)):
            if "mesh" in root and tree_entries(root["mesh"], "mesh") != 0:
                failures.append({"check": f"root:{side}:mesh_in_hits_load",
                                 "entries": tree_entries(root["mesh"], "mesh")})
        for name in ("dose", "fluence"):
            for side, root in (("left", left), ("right", right)):
                if name in root and tree_entries(root[name], name) != 0:
                    raise CompareError(f"root:{name}: F3 hits load keeps dose/fluence empty; a "
                                       "non-empty tree needs an explicit contract decision")
    if workload == "mesh":
        for side, root in (("left", left), ("right", right)):
            for name in ("hits", "events"):
                if name in root and tree_entries(root[name], name) != 0:
                    failures.append({"check": f"root:{side}:{name}_in_mesh_load",
                                     "entries": tree_entries(root[name], name)})
            for name in ("dose", "fluence", "let"):
                if name in root and tree_entries(root[name], name) != 0:
                    raise CompareError(f"root:{name}: F3 mesh load keeps dose/fluence/LET empty; "
                                       "a non-empty tree needs an explicit contract decision")
    compare_statistics(run_left, run_right, failures)


def compare_moment_tree(name, tree_left, tree_right, failures):
    branches = ROOT_OBJECTS[name]
    left = merge_moment_rows(name, branches,
                             tree_rows(tree_left, branches, name))
    right = merge_moment_rows(name, branches,
                              tree_rows(tree_right, branches, name))
    keys = set(left) | set(right)
    for key in sorted(keys, key=str):
        a, b = left.get(key), right.get(key)
        if a is None or b is None:
            failures.append({"check": f"root:{name}:key", "key": key,
                             "left": "present" if a else "absent",
                             "right": "present" if b else "absent"})
            continue
        for column in sorted(a["sums"]):
            similarity_check(f"root:{name}:{column}", a["sums"][column], b["sums"][column],
                             failures)
        for column in sorted(a["constants"]):
            similarity_check(f"root:{name}:{column}", a["constants"][column],
                             b["constants"][column], failures)
        for column in sorted(a["labels"]):
            if a["labels"][column] != b["labels"][column]:
                failures.append({"check": f"root:{name}:{column}", "key": key,
                                 "left": a["labels"][column], "right": b["labels"][column]})


def merge_moment_rows(name, branches, rows):
    merged = {}
    for row in rows:
        key = tuple((column, canon_value(column, row[column])) for column in branches
                    if column in MOMENT_KEY_COLUMNS or column in {"name", "particles"})
        thread = canon_integral(str(row["threadID"]))
        entry = merged.setdefault(key, {"sums": {}, "constants": {}, "labels": {},
                                        "threads": set(), "n_events": 0})
        if thread in entry["threads"]:
            raise CompareError(f"root:{name}: duplicate worker row for key {key}, thread {thread}")
        entry["threads"].add(thread)
        local_events = int(canon_integral(str(row["n_events"])))
        if not 0 <= local_events <= EVENTS:
            raise CompareError(f"root:{name}: local n_events={local_events} outside 0..{EVENTS}")
        entry["n_events"] += local_events
        for column in branches:
            if column in ("threadID", "runID", "volume_path", "volume_name", "name",
                          "particles", "n_events"):
                continue
            value = canon_value(column, row[column])
            if column in SUM_COLUMNS:
                entry["sums"].setdefault(column, 0.0)
                entry["sums"][column] += float(value)
            elif column in CONSTANT_COLUMNS:
                entry["constants"].setdefault(column, float(value))
            elif column in RATIO_COLUMNS:
                raise CompareError(f"root:{name}: ratio column {column} is not part of the frozen "
                                   "F3 loads (LET/DDD disabled); explain the consumer before "
                                   "comparing")
            elif column in MOMENT_LABEL_COLUMNS:
                entry["labels"].setdefault(column, value)
    for key, entry in merged.items():
        if entry["n_events"] > EVENTS:
            raise CompareError(f"root:{name}: worker n_events sum {entry['n_events']} for key "
                               f"{key} exceeds the run's {EVENTS} events once")
    return merged


def histogram_entries(hist):
    try:
        return int(round(float(hist.member("fEntries"))))
    except Exception:
        return int(round(float(sum(hist.values(flow=True)))))


def histogram_compare(name, left_hist, right_hist, failures):
    left_edges = list(left_hist.axis().edges())
    right_edges = list(right_hist.axis().edges())
    if len(left_edges) != len(right_edges) or any(
            not (math.isfinite(a) and math.isfinite(b)) or a != b
            for a, b in zip(left_edges, right_edges)):
        failures.append({"check": f"root:{name}:edges", "left": len(left_edges),
                         "right": len(right_edges)})
        return
    left_entries, right_entries = histogram_entries(left_hist), histogram_entries(right_hist)
    if left_entries != right_entries:
        failures.append({"check": f"root:{name}:entries", "left": left_entries,
                         "right": right_entries})
    left_values = list(left_hist.values(flow=False))
    right_values = list(right_hist.values(flow=False))
    if len(left_values) != len(right_values):
        failures.append({"check": f"root:{name}:bins", "left": len(left_values),
                         "right": len(right_values)})
        return
    for index, (a, b) in enumerate(zip(left_values, right_values)):
        similarity_check(f"root:{name}:bin{index}", float(a), float(b), failures)


def compare_runs(baseline_dir, candidate_dir, workload, fmt):
    if fmt not in {"csv", "root"}:
        raise CompareError("F3 matrix uses csv and root only; 'both' is optional debug and "
                           "not part of the frozen matrix")
    if workload not in {"hits", "mesh"}:
        raise CompareError("F3 matrix uses hits and mesh workloads only")
    left = RunData(baseline_dir)
    right = RunData(candidate_dir)
    require_completed(left, workload, fmt)
    require_completed(right, workload, fmt)
    failures = []
    compared_metadata = compare_metadata(left, right, failures)
    if fmt == "csv":
        compare_csv(left, right, workload, failures)
    else:
        compare_root(left, right, workload, failures)
    return {
        "schema": "g4usim_f3_science_comparison_v1",
        "workload": workload, "format": fmt,
        "baseline": {"output_dir": str(left.output_dir), **left.metrics()},
        "candidate": {"output_dir": str(right.output_dir), **right.metrics()},
        "metadata_compared": compared_metadata,
        "failures": failures,
        "status": "pass" if not failures else "fail",
    }


def describe_run(output_dir, workload, fmt):
    run = RunData(output_dir)
    require_completed(run, workload, fmt)
    roles = {role: [path.name for path in paths] for role, paths in sorted(run.roles.items())}
    description = {"schema": "g4usim_f3_science_describe_v1", "output_dir": str(run.output_dir),
                   "metrics": run.metrics(), "roles": roles, "workload": workload,
                   "format": fmt}
    if fmt == "csv":
        counts = {}
        for role in ("hits_csv", "event_csv", "mesh_csv", "histogram_csv"):
            counts[f"{role}_rows"] = len(run.csv_rows(role, {
                "hits_csv": HITS_COLUMNS, "event_csv": EVENT_COLUMNS,
                "mesh_csv": MESH_COLUMNS, "histogram_csv": HISTOGRAM_COLUMNS}[role]))
        description["csv"] = counts
    else:
        root = run.root()
        keys = sorted(key.split(";")[0] for key in root.keys())
        description["root_objects"] = keys
        description["root_entries"] = {name: tree_entries(root[name], name) for name in keys
                                       if hasattr(root[name], "num_entries")}
    return description


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    compare = sub.add_parser("compare")
    compare.add_argument("--baseline", type=Path, required=True)
    compare.add_argument("--candidate", type=Path, required=True)
    compare.add_argument("--workload", choices=("hits", "mesh"), required=True)
    compare.add_argument("--format", choices=("csv", "root"), required=True)
    compare.add_argument("--out", type=Path)
    describe = sub.add_parser("describe")
    describe.add_argument("--run", type=Path, required=True)
    describe.add_argument("--workload", choices=("hits", "mesh"), required=True)
    describe.add_argument("--format", choices=("csv", "root"), required=True)
    describe.add_argument("--out", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "compare":
            report = compare_runs(args.baseline, args.candidate, args.workload, args.format)
        else:
            report = describe_run(args.run, args.workload, args.format)
    except (CompareError, KeyError, OSError) as error:
        print(f"science_compare: {error}", file=sys.stderr)
        return 2
    text = json.dumps(report, indent=2) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_bytes(text.encode("utf-8"))
    else:
        print(text, end="")
    if args.command == "compare" and report["status"] != "pass":
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
