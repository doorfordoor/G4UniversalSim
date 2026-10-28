"""Qt-only regression for the shielding scenario page (roadmap 2B).

No backend is executed here: the page is instantiated with the real field list, its
validation and generation paths are exercised against a temporary directory and the
result table is filled with hand-made rows so the evidence column and the language
switch can be checked. The real end-to-end run lives in smoke_scenario_backend.py.
"""

from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "gui") not in sys.path:
    sys.path.insert(0, str(ROOT / "gui"))

from PySide6.QtWidgets import QApplication  # noqa: E402

from g4usim_gui.core import scenario_shielding as shielding  # noqa: E402
from g4usim_gui.core.i18n import apply_language  # noqa: E402
from g4usim_gui.widgets.scenario_page import ScenarioPage  # noqa: E402


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv[:1])
    workdir = Path(tempfile.mkdtemp(prefix="g4usim-scenario-page-"))
    page = ScenarioPage()
    try:
        assert page.values().keys() == {field.key for field in shielding.FIELDS}
        assert len(shielding.visible_fields()) == 7
        assert len(shielding.visible_fields(advanced=True)) == 8
        assert page.advanced_group.isHidden()

        page.advanced_check.setChecked(True)
        app.processEvents()
        assert not page.advanced_group.isHidden()
        page.advanced_check.setChecked(False)

        # Defaults are valid and generation produces the documented file set.
        assert page.validate_form() == []
        page.set_directory(workdir / "case")
        generated = page.generate_scenario()
        assert generated is not None and generated.main_ini_path.is_file()
        assert (generated.directory / "scenario.json").is_file()
        assert (generated.directory / "run.mac").is_file()
        assert "Scenario files written to" in page.status_text(), page.status_text()

        # Invalid input blocks the run and is shown to the user.
        page.set_values({"energy": "1e308 GeV"})
        problems = page.validate_form()
        assert problems, "non-finite energy must be rejected"
        assert not page.run_button.isEnabled()
        assert "Fix the validation messages first." in page.status_text()
        page.set_values({"energy": ""})
        assert page.validate_form() == []
        assert page.run_button.isEnabled()

        # Result rows keep the evidence label of every number.
        page._rows = [
            {"group": "TID", "label": "Total", "value": "1.088e-09", "unit": "Gy",
             "evidence": "scorer_statistics.csv"},
            {"group": "Transmission", "label": "Primary transmission", "value": "0.9971",
             "unit": "fraction", "evidence": "phase_space"},
        ]
        page._fill_rows()
        assert page.results_table.rowCount() == 2
        assert page.results_table.item(0, 4).text() == "scorer_statistics.csv"
        assert page.results_table.item(1, 4).text() == "phase_space"
        assert page.results_table.horizontalHeaderItem(4).text() == "Evidence"

        # Language switch retranslates labels, headers and the status chip.
        apply_language(page, "zh_CN")
        page.refresh_language()
        app.processEvents()
        assert page.field_labels["mode"].text() == "模式", page.field_labels["mode"].text()
        assert page.field_labels["layers"].text() == "层（材料:厚度，逗号分隔）"
        assert page.basic_group.title() == "场景"
        assert page.results_table.horizontalHeaderItem(4).text() == "证据"
        assert page._title_label.text() == "屏蔽与涂层场景"
        apply_language(page, "en")
        page.refresh_language()
        assert page.field_labels["mode"].text() == "Mode"
        assert page.results_table.horizontalHeaderItem(4).text() == "Evidence"

        # A missing backend is reported instead of starting nothing silently.
        page.set_executable(workdir / "missing-backend.exe")
        assert page.start_run() is False
        assert not page.is_running
        assert "was not found" in " ".join(page._parse_problems), page._parse_problems

        # A directory that is not a scenario folder is refused instead of being wiped.
        foreign = workdir / "foreign"
        foreign.mkdir()
        (foreign / "keep.txt").write_text("keep", encoding="utf-8")
        page.set_directory(foreign)
        assert page.generate_scenario() is None
        assert (foreign / "keep.txt").read_text(encoding="utf-8") == "keep"

        print("PASS: scenario page fields, validation, generation, evidence column and i18n")
        return 0
    finally:
        page.close()
        page.deleteLater()
        app.processEvents()
        shutil.rmtree(workdir, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
