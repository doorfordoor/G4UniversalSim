"""Dose CSV aggregation and Results-page smoke with isolated worker fixtures."""

from __future__ import annotations

import csv
import math
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtWidgets import QApplication

from g4usim_gui.output.dose_summary import MEV_IN_JOULES, read_dose_summaries
from g4usim_gui.output.file_classifier import OutputFileType, classify_file
from g4usim_gui.widgets.output_page import OutputPage


HEADER = ["runID", "volume_path", "volume_name", "mass_kg", "raw_edep_MeV",
          "weighted_edep_MeV", "raw_dose_Gy", "weighted_dose_Gy"]
MASS = 0.000233
VOLUME = "/world_PV#0/Target_PV#0"


def dose_row(run: int, raw: float, weighted: float, mass: float = MASS) -> dict:
    return dict(zip(HEADER, [run, VOLUME, "Target", mass, raw, weighted,
                             raw * MEV_IN_JOULES / mass if mass else 0.0,
                             weighted * MEV_IN_JOULES / mass if mass else 0.0]))


def write_csv(root: Path, name: str, rows: list[dict]) -> Path:
    path = root / name
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=HEADER)
        writer.writeheader()
        writer.writerows(rows)
    return path


def main() -> None:
    app = QApplication.instance() or QApplication([])
    with tempfile.TemporaryDirectory(prefix="g4usim-dose-gui-") as temp:
        root = Path(temp)
        first = write_csv(root, "dose_volume_summary_t0.csv", [dose_row(0, 100, 70)])
        write_csv(root, "dose_volume_summary_t1.csv", [dose_row(0, 200, 220)])
        write_csv(root, "dose_volume_summary_t0_r1.csv", [dose_row(1, 50, 51)])
        assert classify_file(first).file_type == OutputFileType.DOSE_VOLUME_THREAD_CSV

        records, warnings = read_dose_summaries(root)
        assert not warnings, warnings
        assert len(records) == 2
        run_zero, run_one = records
        assert run_zero.run_id == 0 and run_zero.thread_ids == {0, 1}
        assert run_zero.mass_kg == MASS
        assert run_zero.raw_edep_MeV == 300
        assert run_zero.weighted_edep_MeV == 290
        assert math.isclose(run_zero.raw_dose_Gy, 300 * MEV_IN_JOULES / MASS)
        assert run_one.run_id == 1 and run_one.thread_ids == {0}

        # A file whose second row is malformed must contribute no first-row data.
        write_csv(root, "dose_volume_summary_t2.csv", [dose_row(0, 800, 800),
                  dose_row(0, 25, 25, mass=0)])
        write_csv(root, "dose_volume_summary_t3.csv", [dose_row(0, 10, 10, mass=0.0001)])
        write_csv(root, "dose_volume_summary_t4.csv", [dose_row(0, 10, 10)])
        write_csv(root, "dose_volume_summary_t5.csv", [dose_row(0, 4, 4)])
        # Filename runID and row runID must agree.
        write_csv(root, "dose_volume_summary_t6_r1.csv", [dose_row(0, 999, 999)])
        # A repeated volume row in one file is invalid.
        write_csv(root, "dose_volume_summary_t7.csv", [dose_row(0, 1, 1), dose_row(0, 2, 2)])
        invalid = dose_row(0, 123, 123)
        invalid["raw_dose_Gy"] = "nan"
        write_csv(root, "dose_volume_summary_t8.csv", [invalid])

        records, warnings = read_dose_summaries(root)
        assert len(warnings) == 5, warnings
        assert records[0].raw_edep_MeV == 314  # Valid workers 0, 1, 4, 5.
        assert records[1].raw_edep_MeV == 50
        assert records[0].mass_kg == MASS

        page = OutputPage()
        page.set_output_dir(str(root))
        assert page.tabs.tabText(4) == "Dose (Gy)"
        assert page.dose_table.rowCount() == 2
        assert float(page.dose_table.item(0, 4).text()) == 314
        assert float(page.dose_table.item(0, 3).text()) == MASS
        assert "Skipped dose_volume_summary_t2.csv" in page.dose_message.toPlainText()
        assert "未证明线程文件完整" in page.dose_message.toPlainText()
        page.set_output_dir(str(root / "missing"))
        assert page.dose_table.rowCount() == 0
        page.set_output_dir("")
        assert page.dose_table.rowCount() == 0
        page.close()
    print("smoke_dose_results: ok")


if __name__ == "__main__":
    main()
