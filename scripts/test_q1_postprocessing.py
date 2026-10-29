"""Q1 R-05/R-07 synthetic evidence: event normalization and sparse ROOT workers."""
from pathlib import Path
import csv
import json
import sys
import shutil
import tempfile
import warnings

import numpy as np
import uproot

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "scripts"), str(ROOT / "gui")]
import g4usim_io
import math
from g4usim_gui.output import plot_data


def rejects(operation, text):
    try:
        operation()
    except ValueError as error:
        assert text in str(error), str(error)
    else:
        assert False, "invalid evidence accepted"


def root_file(path, populated=True, events=False, worker_events=2):
    with uproot.recreate(path) as out:
        tree = out.mktree("edep_volume", {"name": "string", "threadID": "int32", "n_events": "float64",
            "raw_edep_MeV": "float64", "weighted_edep_MeV": "float64",
            "raw_edep_sum_sq_MeV2": "float64", "weighted_edep_sum_sq_MeV2": "float64"})
        if populated:
            tree.extend({"name": ["target"], "threadID": [0], "n_events": [worker_events],
                "raw_edep_MeV": [2.], "weighted_edep_MeV": [2.],
                "raw_edep_sum_sq_MeV2": [4.], "weighted_edep_sum_sq_MeV2": [4.]})
        if events:
            out.mktree("events", {"threadID": "int32"}).extend({"threadID": [0, 0, 1, 1]})
        mesh = out.mktree("mesh", {"mesh": "string", "quantity": "string", "unit": "string",
            "threadID": "int32", "n_events": "float64", "i0": "int32", "i1": "int32", "i2": "int32",
            "sum": "float64", "sum_sq": "float64", "entries": "int32"})
        if populated:
            mesh.extend({"mesh": ["m"], "quantity": ["dose"], "unit": ["Gy"], "threadID": [0],
                "n_events": [worker_events], "i0": [0], "i1": [0], "i2": [0], "sum": [2.], "sum_sq": [4.], "entries": [1]})


def main():
    # Match the backend's equivalent division order for representable large moments.
    assert math.isclose(g4usim_io._rel_error(2e154, 1e308, 8), math.sqrt(0.125))
    assert math.isclose(g4usim_io._ratio_rel_error(2e154, 1e308, 2e154, 1e308, 5e307), 0.5)
    with tempfile.TemporaryDirectory(prefix="q1-post-") as temp:
        work = Path(temp)
        metadata = work / "run_metadata.json"
        def record(count=4):
            (work / "run_summary.txt").write_text("status = completed\n", encoding="utf-8")
            names = ["run_metadata.json", "run_summary.txt"] + [p.name for p in work.glob("g4usim*.root")]
            metadata.write_text(json.dumps({"schema": "run_metadata_json_v1", "runs": [
                {"run_id": 0, "completed_events": count}, {"run_id": 1, "completed_events": 8}],
                "generated_files": [{"path": name, "schema": "fixture"} for name in names]}), encoding="utf-8")
        for event_table in (False, True):
            path = work / "g4usim.root"
            root_file(path, events=event_table)
            record()
            values = g4usim_io.load_scorer_statistics(path)
            assert len(values) == 2 and all(v.n_events == 4 and v.value == 2 for v in values)
            assert np.isclose(values[0].rel_error, np.sqrt(.75))
            mesh = g4usim_io.load_mesh(path, "m", "dose")
            assert mesh.n_events == 4 and np.isclose(mesh.rel_error.item(), np.sqrt(.75))
            assert mesh.mean_per_event.item() == .5
            for invalid in (True, False, 4.5, -1, "4"):
                rejects(lambda: g4usim_io.load_scorer_statistics(path, invalid), "non-negative integer")
            rejects(lambda: g4usim_io.load_scorer_statistics(path, 5), "conflicts")
            rejects(lambda: g4usim_io.load_mesh(path, "m", "dose", n_events=5), "conflicts")
            metadata.unlink()
            rejects(lambda: g4usim_io.load_scorer_statistics(path), "no reliable")
            rejects(lambda: g4usim_io.load_mesh(path, "m", "dose"), "no reliable")
            assert g4usim_io.load_scorer_statistics(path, np.int64(4))[0].n_events == 4
            rejects(lambda: g4usim_io.load_scorer_statistics(path, 1), "smaller")
            metadata.write_text("{broken", encoding="utf-8")
            rejects(lambda: g4usim_io.load_scorer_statistics(path, 4), "Invalid output provenance")
            record(4.5)
            rejects(lambda: g4usim_io.load_scorer_statistics(path), "invalid completed event count")
        record()
        second = work / "g4usim_r1.root"
        root_file(second)
        record()
        assert g4usim_io.load_scorer_statistics(second)[0].n_events == 8
        rejects(lambda: g4usim_io.load_scorer_statistics(second, 4), "conflicts")
        root_file(path, worker_events=1)
        record(1)
        one = g4usim_io.load_scorer_statistics(path)
        assert one and all(not r.uncertainty_available and r.uncertainty_status == "insufficient_events" for r in one)
        assert not g4usim_io.load_mesh(path,"m","dose").uncertainty_available.item()
        record()
        root_file(path, populated=False)
        assert g4usim_io.load_scorer_statistics(path) == []
        record(0)
        assert g4usim_io.load_scorer_statistics(path) == []
        root_file(path)
        rejects(lambda: g4usim_io.load_scorer_statistics(path), "smaller")
        # Values represent variable primary multiplicities within four histories.
        with (work / "scorer_statistics.csv").open("w", newline="", encoding="utf-8") as stream:
            writer = csv.writer(stream)
            writer.writerow(["scorer", "quantity", "key", "unit", "value", "std_error", "n_events", "estimator"])
            for scorer, quantity, unit in (("edep", "raw_edep", "MeV"), ("dose", "raw_dose", "Gy"), ("fluence", "raw_fluence", "mm-2")):
                writer.writerow([scorer, quantity, "target", unit, 12, 2, 4, "total"])
        (work / "run_summary.txt").write_text("run_0_completed_events = 4\n", encoding="utf-8")
        (work / "run_metadata.json").write_text(json.dumps({
            "schema":"run_metadata_json_v1", "runs":[{"run_id":0,"completed_events":4}],
            "generated_files":[{"path":name,"schema":"fixture"} for name in
                               ("run_metadata.json","run_summary.txt","scorer_statistics.csv")]}), encoding="utf-8")
        for dataset in plot_data.discover(work):
            if dataset.kind != "scorer":
                continue
            normalized = plot_data.build_plot(work, dataset, normalization="per_event")
            assert normalized.series[0].y.item() == 3 and normalized.series[0].yerr.item() == .5
            assert normalized.ylabel.endswith(" / event")
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                old = plot_data.build_plot(work, dataset, per_primary=True)
            assert caught and caught[0].category is DeprecationWarning
            assert np.array_equal(old.series[0].y, normalized.series[0].y)
            rejects(lambda: plot_data.build_plot(work, dataset, per_primary=True, normalization="total"), "conflicts")
            plot_data.write_plot_csv(normalized, work / "plot.csv")
            with (work / "plot.csv").open(encoding="utf-8") as stream:
                row = next(csv.DictReader(stream))
            assert row["normalization"] == "per_event" and row["value_label"].endswith(" / event")
        (work / "run_summary.txt").unlink()
        rejects(lambda: plot_data.build_plot(work, dataset, normalization="per_event"), "registered file is missing")
        (work / "run_metadata.json").unlink()
        rejects(lambda: plot_data.build_plot(work, dataset, normalization="per_event"), "no positive")
    # V01 keeps old numbers while explicitly marking unavailable uncertainty.
    for count in (0, 1, 2):
        for ratio in (False, True):
            item = g4usim_io.ScorerStatistic("let" if ratio else "edep", "q", "k", "k", "u",
                "ratio" if ratio else "total", count, 3., .25, ratio_denominator=2. if ratio else None)
            expected = "insufficient_events" if count < 2 else "approximate"
            assert item.uncertainty_status == expected
            assert item.uncertainty_available == (count >= 2) and item.std_error == .75
            assert item.uncertainty_estimator == ("uncorrected_delta_ratio_v1" if ratio else "uncorrected_event_moments_v1")
            for explicit in (False, True):
                row = {"n_events": str(count), "value": "3", "estimator": item.estimator}
                if explicit:
                    row.update(uncertainty_status=expected, uncertainty_estimator=item.uncertainty_estimator)
                assert plot_data.uncertainty(row) == (item.uncertainty_estimator, expected)
        empty_ratio = g4usim_io.ScorerStatistic("let","q","k","k","u","ratio",count,0,0,ratio_denominator=0)
        assert empty_ratio.uncertainty_status == ("insufficient_events" if count < 2 else "undefined_ratio")
    with tempfile.TemporaryDirectory(prefix="q1-small-n-") as temp:
        folder = Path(temp)
        dataset = plot_data.DataSet("scorer", "x", "x", 0, ("dose", "raw_dose"))
        for count in (0, 1, 2):
            for explicit in (False, True):
                row = {"scorer":"dose", "quantity":"raw_dose", "key":"k", "unit":"Gy", "value":"3",
                       "std_error":"0", "n_events":str(count), "estimator":"total"}
                if explicit:
                    row.update(uncertainty_estimator="uncorrected_event_moments_v1",
                               uncertainty_status="insufficient_events" if count < 2 else "approximate")
                with (folder/"scorer_statistics.csv").open("w",newline="",encoding="utf-8") as stream:
                    writer = csv.DictWriter(stream,fieldnames=list(row)); writer.writeheader();writer.writerow(row)
                plotted = plot_data.build_plot(folder,dataset)
                assert np.ma.is_masked(plotted.series[0].yerr[0]) == (count < 2)
                plot_data.write_plot_csv(plotted,folder/"plot.csv")
                with (folder/"plot.csv").open(encoding="utf-8") as stream:
                    exported = next(csv.DictReader(stream))
                assert (exported["error"] == "") == (count < 2)
        zero = {"n_events":"2","value":"0","estimator":"total"}
        assert plot_data.uncertainty(zero)[1] == "zero_total"
        assert plot_data.uncertainty({**zero,"estimator":"ratio"})[1] == "undefined_ratio"
        assert plot_data.uncertainty({**zero,"estimator":"ratio","uncertainty_status":"zero_total"})[1] == "zero_total"

    with tempfile.TemporaryDirectory(prefix="q1-root-provenance-") as temp:
        folder = Path(temp)
        path = folder / "g4usim.root"
        root_file(path, worker_events=2)
        (folder / "run_summary.txt").write_text("status = completed\n", encoding="utf-8")
        doc = {"schema": "run_metadata_json_v1", "runs": [{"run_id": 0, "completed_events": 100}],
               "generated_files": [{"path": name, "schema": "fixture"} for name in
                                   ("run_metadata.json", "run_summary.txt")]}
        doc["values"] = {"scoring_mesh_m_bins": "2,2,2"}
        manifest = folder / "run_metadata.json"
        manifest.write_text(json.dumps(doc), encoding="utf-8")
        rejects(lambda: g4usim_io.load_scorer_statistics(path), "no reliable")
        rejects(lambda: g4usim_io.load_mesh(path, "m", "dose"), "no reliable")
        assert all(v.n_events == 2 for v in g4usim_io.load_scorer_statistics(path, 2))
        independent_mesh = g4usim_io.load_mesh(path, "m", "dose", n_events=2)
        assert independent_mesh.n_events == 2 and independent_mesh.bins == (1, 1, 1)
        doc["generated_files"].append({"path": path.name, "schema": "fixture"})
        manifest.write_text(json.dumps(doc), encoding="utf-8")
        assert g4usim_io.load_scorer_statistics(path)[0].n_events == 100
        rejects(lambda: g4usim_io.load_scorer_statistics(path, 2), "conflicts")
        assert g4usim_io.load_mesh(path, "m", "dose").bins == (2, 2, 2)
        # Absolute recorded paths relocate through the manifest's own anchor.
        copied = folder / "copied"
        absolute_doc = {**doc, "generated_files": [
            {**row, "path": str(folder / row["path"])} for row in doc["generated_files"]]}
        manifest.write_text(json.dumps(absolute_doc), encoding="utf-8")
        copied.mkdir()
        for name in ("g4usim.root", "run_metadata.json", "run_summary.txt"):
            shutil.copy2(folder / name, copied / name)
        assert g4usim_io.load_scorer_statistics(copied / path.name)[0].n_events == 100
        assert g4usim_io.load_mesh(copied / path.name, "m", "dose").bins == (2, 2, 2)
        # Canonical filename run must match a registered run; explicit N cannot
        # disguise a malformed manifest referencing a nonexistent run.
        doc["runs"][0]["run_id"] = 1
        manifest.write_text(json.dumps(doc), encoding="utf-8")
        rejects(lambda: g4usim_io.load_scorer_statistics(path, 2), "absent run 0")
        manifest.write_text("{broken", encoding="utf-8")
        rejects(lambda: g4usim_io.load_scorer_statistics(path, 2), "Invalid output provenance")
        rejects(lambda: g4usim_io.load_mesh(path, "m", "dose", n_events=2), "Invalid output provenance")

    print("test_q1_postprocessing: OK")


if __name__ == "__main__":
    main()
