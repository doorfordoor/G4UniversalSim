"""GUI Fluence parsing, worker aggregation, editor and Results smoke."""

from __future__ import annotations

import csv
import math
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtWidgets import QApplication

from g4usim_gui.core.project import G4USimProject, load_project, save_project
from g4usim_gui.editors.source_physics_scoring_model import (
    PhysicsEditableModel, ScoringEditableModel, SourceEditableModel,
    validate_scoring_model,
)
from g4usim_gui.models.package_model import GeometrySettings, RunPackage
from g4usim_gui.models.run_model import RunSettings
from g4usim_gui.output.file_classifier import OutputFileType, classify_file
from g4usim_gui.output.fluence_summary import COLUMNS, read_fluence_summaries
from g4usim_gui.widgets.config_builder_page import ConfigBuilderPage
from g4usim_gui.widgets.output_page import OutputPage
from g4usim_gui.writers.main_ini_writer import build_main_ini_text


HEADER = ["runID", "volume_path", "volume_name", "volume_mm3", "raw_track_length_mm",
          "weighted_track_length_mm", "raw_fluence_mm-2", "weighted_fluence_mm-2"]
PATH = "/world_PV#0/Target_PV#0"


def row(run: int, length: float, weighted: float, volume: float = 100.0) -> dict:
    return dict(zip(HEADER, [run, PATH, "Target", volume, length, weighted,
                             length / volume if volume else 0,
                             weighted / volume if volume else 0]))


def write(root: Path, name: str, rows: list[dict]) -> Path:
    file = root / name
    with file.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, HEADER)
        writer.writeheader()
        writer.writerows(rows)
    return file


def main() -> None:
    app = QApplication.instance() or QApplication([])
    with tempfile.TemporaryDirectory(prefix="g4usim-fluence-gui-") as tmp:
        root = Path(tmp)
        first = write(root, "fluence_volume_summary_t0.csv", [row(0, 10, 9)])
        write(root, "fluence_volume_summary_t1.csv", [row(0, 20, 21)])
        write(root, "fluence_volume_summary_t0_r1.csv", [row(1, 7, 8)])
        assert set(HEADER) == COLUMNS
        assert classify_file(first).file_type == OutputFileType.FLUENCE_VOLUME_THREAD_CSV
        records, warnings = read_fluence_summaries(root)
        assert len(warnings) == 1 and "Legacy/unverified" in warnings[0] and len(records) == 2, warnings
        assert records[0].thread_ids == {0, 1} and records[0].volume_mm3 == 100
        assert records[0].raw_track_length_mm == 30
        assert math.isclose(records[0].weighted_fluence_mm2, .30)
        assert records[1].thread_ids == {0} and records[1].raw_fluence_mm2 == .07

        # A malformed second row discards the entire file, even its first row.
        write(root, "fluence_volume_summary_t2.csv", [row(0, 100, 100), row(0, 1, 1, volume=0)])
        write(root, "fluence_volume_summary_t3.csv", [row(0, 1, 1, volume=200)])
        write(root, "fluence_volume_summary_t4.csv", [row(0, 2, 2)])
        invalid = row(0, 3, 3)
        invalid["raw_fluence_mm-2"] = "nan"
        write(root, "fluence_volume_summary_t5.csv", [invalid])
        write(root, "fluence_volume_summary_t6_r1.csv", [row(0, 1, 1)])
        write(root, "fluence_volume_summary_t7.csv", [row(0, 1, 1), row(0, 2, 2)])
        records, warnings = read_fluence_summaries(root)
        assert len(warnings) == 6, warnings
        assert records[0].raw_track_length_mm == 32
        assert records[0].volume_mm3 == 100

        # Both CSV rows are individually finite; adding the second worker
        # overflows. Its complete file must be rejected before mutating totals.
        overflow = root / "overflow"
        overflow.mkdir()
        write(overflow, "fluence_volume_summary_t0.csv", [row(0, 1e308, 1e308)])
        write(overflow, "fluence_volume_summary_t1.csv", [row(0, 1e308, 1e308)])
        records_overflow, warnings_overflow = read_fluence_summaries(overflow)
        assert len(records_overflow) == 1 and records_overflow[0].thread_ids == {0}
        assert records_overflow[0].raw_track_length_mm == 1e308
        assert len(warnings_overflow) == 2 and "Nonfinite accumulated" in warnings_overflow[1]
        bad_ratio = row(0, 1, 1)
        bad_ratio.update(volume_mm3=1e-308, raw_track_length_mm=1e308,
                         weighted_track_length_mm=1e308)
        write(overflow, "fluence_volume_summary_t2.csv", [bad_ratio])
        _, warnings_overflow = read_fluence_summaries(overflow)
        assert any("Nonfinite derived fluence" in warning for warning in warnings_overflow)

        page = OutputPage()
        page.set_output_dir(str(root))
        assert page.data_tabs.tabText(1) == "Dose (Gy)"
        assert page.data_tabs.tabText(2) == "Fluence (mm^-2)"
        assert page.fluence_table.rowCount() == 2
        assert float(page.fluence_table.item(0, 4).text()) == 32
        assert float(page.fluence_table.item(0, 3).text()) == 100
        assert "Skipped fluence_volume_summary_t2.csv" in page.fluence_message.toPlainText()
        assert "未证明线程文件完整" in page.fluence_message.toPlainText()
        page.set_output_dir(str(root / "missing"))
        assert page.fluence_table.rowCount() == 0
        page.close()

        scorer = ScoringEditableModel(fluence=True, hits=False, event_edep=False, edep=False)
        assert not validate_scoring_model(scorer).errors
        assert scorer.to_settings().fluence
        assert ScoringEditableModel.from_settings(scorer.to_settings()).fluence
        scorer.auto_create_default_scorers = False
        assert any("auto-create" in err for err in validate_scoring_model(scorer).errors)
        scorer.auto_create_default_scorers = True

        package = RunPackage(
            package_dir=str(root), config_dir=str(root / "config"), macro_dir=str(root / "macros"),
            logs_dir=str(root / "logs"), output_dir=str(root / "output"),
            main_ini_path=str(root / "config/main.ini"), run_macro_path=str(root / "macros/run.mac"),
            validation_report_path=str(root / "validation_report.txt"),
            project_snapshot_path=str(root / "project_snapshot.json"),
            materials_ini_path=str(root / "config/materials/material.ini"),
            geometry_ini_path=str(root / "config/geometry/geometry.ini"))
        text = build_main_ini_text(package=package, run=RunSettings(),
                                   geometry=GeometrySettings(), source=SourceEditableModel().to_settings(),
                                   physics=PhysicsEditableModel().to_settings(), scoring=scorer.to_settings(),
                                   scoring_model=scorer)
        assert "fluence = true" in text
        assert "dose = false" in text

        editor = ConfigBuilderPage()
        assert not editor.scoring_editor_fluence.isChecked()
        editor.scoring_editor_fluence.setChecked(True)
        assert editor.scoring_editor.fluence
        editor.close()

        project = G4USimProject()
        old_snapshot = root / "project.json"
        save_project(project, old_snapshot)
        assert not load_project(old_snapshot).scoringEditor.fluence
    print("smoke_fluence_results: ok")


if __name__ == "__main__":
    main()
