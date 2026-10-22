"""Regenerates the Start-page examples gallery with the real backend.

    gui\\.venv\\Scripts\\python.exe examples\\gallery\\build_gallery.py [example id ...]

For every example of gui/g4usim_gui/core/examples.py (or the ids given): the wizard
spec goes through the GUI's generated-package path (core.wizard.build ->
create_run_package), the package runs in Geant4 under out/gallery_build/, and the
outputs are copied to examples/gallery/<id>/output/ without hits and ROOT files
(the bundle stays small). A scan example creates its points with core.scan and runs
each one with its own seed; scan/scan.json and the points' run_summary.txt,
run_metadata.json and scorer_statistics.csv are bundled with paths relative to scan/. thumbnail.png plots the bundled results
with the same loaders as Results / Plots.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GALLERY = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "gui"))

import matplotlib   # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt   # noqa: E402
import matplotlib.ticker   # noqa: E402
import numpy as np   # noqa: E402

from g4usim_gui.core import examples, scan   # noqa: E402
from g4usim_gui.core import wizard as wz   # noqa: E402
from g4usim_gui.core.project import G4USimProject   # noqa: E402
from g4usim_gui.models.package_model import PathSettings   # noqa: E402
from g4usim_gui.output import plot_data   # noqa: E402
from g4usim_gui.writers.package_writer import create_run_package   # noqa: E402

EXE = Path(os.environ.get("G4USIM_EXE", ROOT / "build_vs2026/Release/G4UniversalSim.exe"))
BUILD = ROOT / "out" / "gallery_build"
ACCENT, MUTED = "#2f9c8a", "#7d8c93"   # readable on light and dark cards


def project_for(spec: wz.WizardSpec, runs: Path):
    runs.mkdir(parents=True, exist_ok=True)
    result = wz.build(spec)
    project = G4USimProject()
    project.pathSettings = PathSettings(executable=str(EXE), workspace_root=str(ROOT), runs_root=str(runs),
                                        materials_config=str(ROOT / "config/materials/material.ini"),
                                        geometry_config=str(ROOT / "test/geometry/hierarchical_test.ini"))
    wz.apply_to_project(project, result)
    return project, result


def run_backend(main_ini: str, macro: str, output: str, cwd: str, seed: int | None = None) -> None:
    command = [str(EXE), "--config", main_ini, "--macro", macro, "--output", output]
    if seed is not None:
        command += ["--seed", str(seed)]
    process = subprocess.run(command, cwd=cwd, capture_output=True, text=True, errors="replace", timeout=3600)
    if process.returncode != 0:
        raise SystemExit((process.stdout + process.stderr)[-3000:])
    summary = (Path(output) / "run_summary.txt").read_text(encoding="utf-8")
    if "status = completed" not in summary:
        raise SystemExit(f"{output}: run did not complete")


def copy_output(source: Path, target: Path, only: tuple[str, ...] = ()) -> None:
    target.mkdir(parents=True, exist_ok=True)
    for path in sorted(source.iterdir()):
        if only and path.name not in only:
            continue
        if path.is_file() and not path.name.startswith("hits_") and path.suffix != ".root":
            shutil.copy2(path, target / path.name)


def style(axes) -> None:
    for side in ("top", "right"):
        axes.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        axes.spines[side].set_color(MUTED)
    axes.tick_params(colors=MUTED, labelsize=7, length=2)
    axes.set_facecolor("none")


def thumbnail(example: examples.Example, path: Path) -> None:
    figure = plt.figure(figsize=(4.0, 2.5), dpi=100)
    figure.patch.set_alpha(0)
    axes = figure.add_axes((0.11, 0.14, 0.86, 0.80))
    style(axes)
    if example.is_scan:
        manifest = scan.load_manifest(example.scan_dir())
        results = scan.collect(manifest)
        xs, ys = [], []
        for result in results:
            metric = next((v for k, v in result.metrics.items() if k[:2] == example.scan_quantity), None)
            if metric and result.completed_events:
                xs.append(scan.numeric_value(result.value))
                ys.append(metric[0] / result.completed_events)
        axes.plot(xs, ys, "o-", color=ACCENT, lw=1.6, ms=4)
        axes.set_xscale("log")
        axes.set_xticks(xs, [f"{x:g}" for x in xs], minor=False)
        axes.xaxis.set_minor_locator(matplotlib.ticker.NullLocator())
    else:
        output = example.output_dir()
        dataset = next(d for d in plot_data.discover(output) if d.key == example.plot)
        options = {}
        if dataset.kind == "pulse" and example.id != "nai_gamma":   # cut the long Landau tail
            values = []
            for worker in sorted(output.glob("event_edep_t*.csv")):
                values += [float(r["raw_edep_MeV"]) for r in plot_data._read_csv(worker)]
            options["top"] = 3.0 * float(np.median([v for v in values if v > 0]))
        plot = plot_data.build_plot(output, dataset, **options)
        series = plot.series[0]
        if plot.kind == "bar":
            axes.bar(series.x, series.y, width=0.85, color=ACCENT)
        else:
            axes.stairs(series.y, series.x, color=ACCENT, fill=True, alpha=0.35)
            axes.stairs(series.y, series.x, color=ACCENT, lw=1.2)
        if example.id == "nai_gamma":
            axes.set_yscale("log")
    axes.yaxis.get_offset_text().set_visible(False)
    figure.savefig(path, transparent=True)
    plt.close(figure)


def build_run(example: examples.Example) -> None:
    runs = BUILD / example.id
    project, result = project_for(example.spec(), runs)
    package, _ = create_run_package(
        project=project, paths=project.pathSettings, run=result.run, geometry=project.geometrySettings,
        source=project.sourceSettings, physics=project.physicsSettings, scoring=project.scoringSettings,
        geometry_document=result.geometry, source_model=result.source, physics_model=result.physics,
        scoring_model=result.scoring)
    run_backend(package.main_ini_path, package.run_macro_path, package.output_dir, package.package_dir)
    target = example.output_dir()
    if target.exists():
        shutil.rmtree(target)
    copy_output(Path(package.output_dir), target)


def build_scan(example: examples.Example) -> None:
    runs = BUILD / example.id
    project, result = project_for(example.spec(), runs)
    base = scan.ScanBase(project=project, paths=project.pathSettings, run=result.run,
                         geometry_settings=project.geometrySettings, geometry=result.geometry,
                         source=result.source, physics=result.physics, scoring=result.scoring)
    parameter = next(p for p in scan.parameters(base) if p.key == example.scan_parameter)
    manifest = scan.create_scan(base, parameter, scan.expand_values(example.scan_values), example.id, runs)
    for point in manifest.points:
        run_backend(point.main_ini, point.macro, point.output_dir, point.package_dir, point.seed)
    target = example.scan_dir()
    if target.exists():
        shutil.rmtree(target)
    data = json.loads(manifest.path.read_text(encoding="utf-8"))
    data["scan_dir"] = "."
    for point in data["points"]:
        folder = f"points/p{point['index']:03d}"
        copy_output(Path(point["output_dir"]), target / folder / "output",
                    ("run_summary.txt", "run_metadata.json", "scorer_statistics.csv"))
        point.update(package_dir=folder, output_dir=f"{folder}/output", main_ini="", macro="")
    (target / "scan.json").write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    if not EXE.is_file():
        print(f"backend executable missing: {EXE}")
        return 1
    chosen = [examples.find(name) for name in sys.argv[1:]] or list(examples.EXAMPLES)
    if None in chosen:
        print(f"unknown example; known: {[e.id for e in examples.EXAMPLES]}")
        return 1
    for example in chosen:
        print(f"{example.id}: running", flush=True)
        (build_scan if example.is_scan else build_run)(example)
        thumbnail(example, example.thumbnail())
        size = sum(p.stat().st_size for p in example.folder().rglob("*") if p.is_file())
        print(f"{example.id}: {size / 1024:.0f} KiB bundled", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
