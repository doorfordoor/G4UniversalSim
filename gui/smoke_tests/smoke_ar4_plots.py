"""Finite synthetic AR4 plots: real Qt canvas, CSV/ROOT readers and exports.

No backend, native runtime or science validation. Artifacts are retained explicitly.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import itertools
import json
import os
from pathlib import Path
import shutil
import sys

if not __debug__:
    raise RuntimeError("AR4 plot checks require assertions enabled; -O is refused")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
import uproot
from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtWidgets import QApplication
from matplotlib.container import BarContainer

from async_wait import wait_for_idle
from g4usim_gui.output import plot_data
from g4usim_gui.widgets.plot_panel import PlotPanel

STATS = "runID scorer quantity key name unit estimator n_events entries value mean_per_event std_error rel_error fom_per_s run_wall_time_s sum sum_sq".split()
MESH = "runID mesh quantity unit i0 i1 i2 sum sum_sq entries n_events rel_error".split()


def write_csv(path, header, rows):
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(header)
        writer.writerows(rows)


def manifest(root, values=None, runs=(0,)):
    (root / "run_summary.txt").write_text("".join(
        f"run_{run}_completed_events = 10\n" for run in runs), encoding="utf-8")
    path = root / "run_metadata.json"
    path.write_text(json.dumps({"schema": "run_metadata_json_v1",
        "synthetic_fixture": True, "values": values or {},
        "runs": [{"run_id": run, "completed_events": 10} for run in runs],
        "generated_files": [{"path": p.name, "schema": "synthetic_fixture"}
                            for p in sorted(root.iterdir()) if p.is_file() and p != path]
                           + [{"path": path.name, "schema": "run_metadata_json_v1"}]}), encoding="utf-8")


def stats_fixture(root, items):
    root.mkdir(parents=True)
    write_csv(root / "scorer_statistics.csv", STATS,
              [[0, "dose", "weighted_dose", name, name, "Gy", "total", 10, 10,
                value, value / 10, .1, .1, 0, 0, value, value * value] for name, value in items])
    manifest(root)


def mesh_fixture(root, bins, *, physical=True, runs=(0,), low_count=False):
    root.mkdir(parents=True)
    for run in runs:
        suffix = "" if run == 0 else f"_r{run}"
        rows = []
        for i, k, z in itertools.product(*(range(n) for n in bins)):
            value = 0. if (i, k, z) == (0, 0, 0) else float(1 + 100 * i + 10 * k + z)
            value += run * 1000
            n = 1 if low_count else 10
            rows.append([run, "m", "dose", "Gy", i, k, z, value,
                         value * value * (.01 + 1 / n), 1, n, .1])
        write_csv(root / f"scoring_mesh{suffix}.csv", MESH, rows)
        types = {name: ("string" if name in {"mesh", "quantity", "unit"}
                        else "int32" if name in {"runID", "i0", "i1", "i2", "entries", "n_events"}
                        else "float64") for name in MESH if name != "rel_error"}
        types["threadID"] = "int32"
        arrays = {name: [row[MESH.index(name)] for row in rows] for name in types if name != "threadID"}
        arrays["threadID"] = [0] * len(rows)
        with uproot.recreate(root / f"g4usim{suffix}.root") as out:
            out.mktree("mesh", types).extend(arrays)
    values = {"scoring_mesh_m_bins": ",".join(map(str, bins)), "scoring_mesh_m_axes": "X,Y,Z"}
    if physical:
        values.update(scoring_mesh_m_shape="box", scoring_mesh_m_size_mm="10,20,3",
                      scoring_mesh_m_center_mm="7,5,9")
    manifest(root, values, runs)
    if low_count:
        meta = json.loads((root / "run_metadata.json").read_text())
        for run in meta["runs"]:
            run["completed_events"] = 1
        (root / "run_metadata.json").write_text(json.dumps(meta), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence-dir", type=Path,
                        default=os.environ.get("G4USIM_TEST_EVIDENCE_DIR"),
                        required=not os.environ.get("G4USIM_TEST_EVIDENCE_DIR"))
    parser.add_argument("--observe-before", action="store_true")
    args = parser.parse_args()
    out = args.evidence_dir.resolve()
    out.mkdir(parents=True, exist_ok=False)
    failures, records = [], []
    checks = 0

    def check(condition, label):
        nonlocal checks
        checks += 1
        if not bool(condition):
            failures.append(label)
            if not args.observe_before:
                raise RuntimeError(label)
        if not args.observe_before:
            assert condition, label

    app = QApplication.instance() or QApplication([])
    panel = PlotPanel()
    panel.resize(900, 650)
    panel.show()

    def settle():
        wait_for_idle(panel)
        panel.canvas.draw()

    def capture(name):
        image = out / f"{name}.png"
        data = out / f"{name}.csv"
        panel.export_png(str(image))
        panel.export_csv(str(data))
        rows = list(csv.DictReader(data.open(encoding="utf-8")))
        axes = panel.figure.axes[0]
        record = {"name": name, "selected_key": panel.current_dataset().key,
                  "plot_run_id": getattr(panel.current_plot(), "run_id", None),
                  "xlabel": axes.get_xlabel(), "ylabel": axes.get_ylabel(),
                  "xlim": list(axes.get_xlim()), "ylim": list(axes.get_ylim()),
                  "images": [{"array": np.asarray(im.get_array()).tolist(), "extent": list(im.get_extent())}
                             for im in axes.images],
                  "bars": [{"series": c.get_label(), "xyheight": [[p.get_x() + p.get_width()/2, p.get_height()]
                              for p in c.patches]} for c in axes.containers if isinstance(c, BarContainer)],
                  "csv": rows}
        records.append(record)
        check(image.stat().st_size > 1000, name + ": actual figure image")
        return record, rows

    try:
        # Actual CSV input order is reversed for the same-set positive control.
        cases = [("reordered", [("a", 1), ("b", 2)], [("b", 20), ("a", 10)]),
                 ("partial", [("a", 1), ("b", 2)], [("b", 20), ("c", 0)]),
                 ("disjoint", [("a", 1), ("b", 2)], [("c", 30), ("d", 40)])]
        for name, left, right in cases:
            root, other = out / name / "left", out / name / "right"
            stats_fixture(root, left)
            stats_fixture(other, right)
            panel.clear_comparisons(); settle()
            panel.set_output_dir(str(root)); settle()
            panel.select("scorer/dose/weighted_dose/r0"); settle()
            panel.add_comparison(str(other)); settle()
            record, rows = capture("compare_" + name)
            actual = {(r["series"], r["label"]): float(r["value"]) for r in rows}
            expected = {(side, key): value for side, values in [("left", left), ("right", right)] for key, value in values}
            check(actual == expected and len(rows) == len(expected), "AUD12 " + name + ": sparse CSV association")
            categories = panel.current_plot().categories
            for bar in record["bars"]:
                values = dict(left if bar["series"] == "left" else right)
                n = 0 if bar["series"] == "left" else 1
                observed = {categories[round(x - (n - .5) * .4)]: y for x, y in bar["xyheight"]}
                check(observed == values, "AUD12 " + name + ": actual rendered bars")
            for row in rows:
                check(row["error"] == ("" if float(row["value"]) == 0 else "0.1"),
                      name + ": masked/available scorer errors unchanged")

        panel.clear_comparisons(); settle()
        # The model must also preserve an arbitrary in-memory category order;
        # scorer CSV sorting must not accidentally hide index-based export bugs.
        if not args.observe_before:
            a = plot_data.Plot("bar", "volume", "Gy", "bar", categories=["a", "b"],
                series=[plot_data.Series("a", np.arange(2), np.array([1., 2.]), np.ma.array([.1, .2]))])
            b = plot_data.Plot("bar", "volume", "Gy", "bar", categories=["b", "a"],
                series=[plot_data.Series("b", np.arange(2), np.array([20., 10.]), np.ma.array([.2, .1]))])
            combined = plot_data.combine_bars([a, b])
            path = out / "model_reordered.csv"
            plot_data.write_plot_csv(combined, path)
            rows = list(csv.DictReader(path.open(encoding="utf-8")))
            check({(r["series"], r["label"]): float(r["value"]) for r in rows} ==
                  {("a", "a"): 1, ("a", "b"): 2, ("b", "b"): 20, ("b", "a"): 10},
                  "model reordered keys remain attached")
            check(list(combined.series[1].x) == [1, 0], "model screen positions share export mapping")
        for case, bins in [("single_x", (1, 2, 1)), ("single_y", (2, 1, 1)),
                           ("both_single", (1, 1, 1)), ("multi", (2, 3, 1)),
                           ("covariance", (2, 2, 2)), ("low_count", (1, 2, 1)),
                           ("index", (1, 2, 1))]:
            root = out / "meshes" / case
            mesh_fixture(root, bins, physical=case != "index", low_count=case == "low_count")
            panel.set_output_dir(str(root)); settle()
            snapshots = []
            for source in ("csv", "root"):
                ds = plot_data.DataSet("mesh", "mesh/m/dose/r0", "", 0, ("m", "dose", source))
                data = plot_data.load_mesh(root, ds)
                snapshots.append(data)
                expected_values = np.array([0. if idx == (0, 0, 0) else 1 + 100*idx[0] + 10*idx[1] + idx[2]
                                            for idx in itertools.product(*(range(n) for n in bins))]).reshape(bins)
                check(np.array_equal(data.value, expected_values), case + source + ": stored values")
                expected_mask = np.ones(bins, dtype=bool) if case == "low_count" else data.value == 0
                check(np.array_equal(np.ma.getmaskarray(data.error), expected_mask), case + source + ": error availability")
                for ax, ay in [(0, 1), (1, 0), (2, 0)]:
                    plot = plot_data.mesh_map(data, ax, ay)
                    limits = [(-3., 17.), (-15., 25.), (6., 12.)] if case != "index" else [(-.5, n-.5) for n in bins]
                    check(np.allclose(plot.extent, (*limits[ax], *limits[ay])), "R201 " + case + source + f": extent {ax},{ay}")
                    other_axis = ({0, 1, 2} - {ax, ay}).pop()
                    oracle = np.zeros((bins[ay], bins[ax]))
                    for idx in itertools.product(*(range(n) for n in bins)):
                        oracle[idx[ay], idx[ax]] += expected_values[idx]
                    check(np.array_equal(plot.image, oracle), case + source + ": image direction")
                    check((plot.image_error is None) == (bins[other_axis] > 1), case + source + ": covariance unchanged")
            check(np.allclose(snapshots[0].error.compressed(), snapshots[1].error.compressed()), case + ": CSV ROOT errors")
            panel.select("mesh/m/dose/r0"); settle()
            panel.select_view("map:0:1"); settle()
            record, rows = capture("mesh_" + case)
            expected_extent = (-.5, bins[0]-.5, -.5, bins[1]-.5) if case == "index" else (-3., 17., -15., 25.)
            check(np.allclose(record["images"][0]["extent"], expected_extent), "R201 " + case + ": rendered extent")
            check(record["xlabel"] == ("X [bin]" if case == "index" else "X [mm]"), case + ": physical label")
            check(record["ylabel"] == ("Y [bin]" if case == "index" else "Y [mm]"), case + ": vertical label")
            check(np.allclose([float(r["value"]) for r in rows], panel.current_plot().image.ravel()), case + ": exported cells")
            if case == "single_x":
                panel.select_view("map:2:0"); settle()
                swapped, swapped_rows = capture("mesh_single_x_swapped_csv")
                check(swapped["images"][0]["extent"] == [6., 12., -3., 17.], "swapped CSV rendered physical extent")
                check(swapped["images"][0]["array"] == [[11.]], "swapped CSV actual direction/sum")
                check(swapped["xlabel"] == "Z [mm]" and swapped["ylabel"] == "X [mm]", "swapped CSV labels")
                check(swapped_rows[0]["error"] == "", "swapped CSV projection covariance unavailable")
            # Exercise the actual ROOT-only discovery -> Qt image -> export path,
            # retaining both reader inputs, not substituting an injected plot.
            root_only = out / "root_only" / case
            root_only.mkdir(parents=True)
            shutil.copyfile(root / "g4usim.root", root_only / "g4usim.root")
            meta = json.loads((root / "run_metadata.json").read_text())
            manifest(root_only, meta["values"])
            if case == "low_count":
                meta = json.loads((root_only / "run_metadata.json").read_text())
                meta["runs"][0]["completed_events"] = 1
                (root_only / "run_metadata.json").write_text(json.dumps(meta), encoding="utf-8")
            panel.set_output_dir(str(root_only)); settle()
            panel.select("mesh/m/dose/r0"); settle()
            check(panel.current_dataset().detail[-1] == "root", case + ": actual ROOT discovery")
            panel.select_view("map:0:1"); settle()
            root_record, root_rows = capture("mesh_" + case + "_root")
            check(np.allclose(root_record["images"][0]["extent"], expected_extent), case + ": ROOT rendered extent")
            check(root_record["images"][0]["array"] == record["images"][0]["array"], case + ": ROOT CSV actual image equality")
            check(root_record["xlabel"] == record["xlabel"] and root_record["ylabel"] == record["ylabel"], case + ": ROOT CSV physical labels")
            check([r["error"] == "" for r in rows] == [r["error"] == "" for r in root_rows], case + ": ROOT CSV exported error availability")
            if case == "single_x":
                panel.select_view("map:2:0"); settle()
                root_swapped, root_swapped_rows = capture("mesh_single_x_swapped_root")
                check(root_swapped["images"] == swapped["images"], "swapped ROOT CSV actual images")
                check(root_swapped["xlabel"] == swapped["xlabel"] and root_swapped["ylabel"] == swapped["ylabel"], "swapped ROOT CSV actual labels")
                check(root_swapped_rows == swapped_rows, "swapped ROOT CSV exports including uncertainty availability")

        root = out / "overlay"
        mesh_fixture(root, (1, 2, 1), runs=(0, 1))
        panel.set_output_dir(str(root)); settle()
        panel.select("mesh/m/dose/r1"); settle()
        panel.select_view("map:0:1"); settle()
        for n, enabled in enumerate([False, True, False]):
            panel.all_runs.setChecked(enabled); settle()
            record, rows = capture(f"overlay_{n}_{enabled}")
            check(record["selected_key"] == "mesh/m/dose/r1", "AUD13 selected run1")
            check(record["images"][0]["array"] == [[1000.], [1011.]], "AUD13 actual image run1")
            check([float(r["value"]) for r in rows] == [1000., 1011.], "AUD13 exported run1 values")
            check(record["plot_run_id"] == 1 and all(r.get("run_id") == "1" for r in rows), "AUD13 explicit plot/export run identity")
        panel.select_view("profile:1"); settle()
        panel.all_runs.setChecked(True); settle()
        check(len(panel.current_plot().series) == 2, "profile overlay remains available")
        capture("profile_overlay")
    finally:
        panel.close(); panel.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        app.processEvents()
        report = {"synthetic_fixture": True, "observe_before": args.observe_before,
                  "checks": checks, "failures": failures, "figures": records}
        (out / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        files = {p.relative_to(out).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                 for p in sorted(out.rglob("*")) if p.is_file()}
        (out / "sha256.json").write_text(json.dumps(files, indent=2), encoding="utf-8")
    print(f"AR4 plots: checks={checks} failures={len(failures)} synthetic_fixture=true")
    if failures:
        print("\n".join(failures))
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
