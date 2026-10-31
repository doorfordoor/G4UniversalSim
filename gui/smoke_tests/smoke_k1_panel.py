from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QSignalSpy, QTest
from PySide6.QtWidgets import QApplication, QLabel

from g4usim_gui.core.i18n import ZH_CN, current_language, set_application_language, ui_format, ui_text
from g4usim_gui.widgets.experiment_panel import (
    ACTION_TEXT, ACTION_TOKENS, EXPORT_NOTE, LEVEL_TEXT, LEVEL_TOKENS,
    STATUS_TEXT, ExperimentPanel,
)


def check_producer_pending(panel, app):
    """Use the real producer projection; this fixture owns no run or eligibility."""
    from copy import deepcopy
    from types import SimpleNamespace
    from g4usim_gui.core.experiment_workflow import ExperimentWorkflow

    previous_language = current_language()
    try:
        for level, status, freshness, busy in (
                ('fields', 'passed', 'checking', False),
                ('execution', 'pending', 'as_observed', True)):
            records = [dict(record_id='pending-view-fixture', run_id='view-run', revision=7,
                            level=level, status=status, stale=False)]
            observation = SimpleNamespace(session=SimpleNamespace(revision=7),
                busy=busy, _freshness=freshness, records=lambda: deepcopy(records))
            payload = ExperimentWorkflow._state(observation)
            assert payload['status'] == 'pending'
            assert next(row for row in payload['levels'] if row['level'] == level)['status'] == 'pending'
            original = deepcopy(payload)
            for language, expected in (('en', 'In progress'), ('zh_CN', '进行中')):
                set_application_language(app, language)
                panel.set_state(payload)
                panel.retranslate_ui()
                assert panel._level_labels[level].text() == expected
                assert expected in panel._summary_label.text()
                assert panel._history_table.item(0, 1).text() == (
                    ('Passed' if language == 'en' else '通过') if status == 'passed' else expected)
                assert panel._level_labels['physics'].text() == (
                    'Unobserved' if language == 'en' else '未观测')
                assert payload == original
    finally:
        set_application_language(app, previous_language)
        panel.set_state({})
        panel.retranslate_ui()


def main() -> int:
    app = QApplication.instance() or QApplication([])
    old_language = current_language()
    panel = None
    try:
        set_application_language(app, "en")
        panel = ExperimentPanel()
        panel.resize(640, 300)
        panel.show()
        app.processEvents()
        assert panel.maximumHeight() == 300
        assert not panel._summary_label.isVisible()
        assert not panel._history_group.isVisible()
        assert panel._levels_group.isVisible()
        assert not panel.styleSheet()
        assert all(not child.styleSheet() for child in panel.findChildren(QLabel))
        for level in LEVEL_TOKENS:
            assert panel._level_names[level].text() == ui_text(LEVEL_TEXT[level])
            assert panel._level_labels[level].text() == ui_text("Unverified")

        check_producer_pending(panel, app)

        spy = QSignalSpy(panel.action_requested)
        for token in ACTION_TOKENS:
            panel._actions[token].click()
        assert spy.count() == len(ACTION_TOKENS)
        assert [spy.at(i)[0] for i in range(spy.count())] == list(ACTION_TOKENS)
        assert {"import", "environment", "cancel"} <= set(ACTION_TOKENS)
        panel.set_busy(True)
        for token in ACTION_TOKENS:
            assert panel._actions[token].isEnabled() == (token == "cancel")
            panel._actions[token].click()
        assert spy.count() == len(ACTION_TOKENS) + 1
        assert spy.at(spy.count() - 1)[0] == "cancel"
        panel._emit_action("run")
        panel._emit_action("future-action")
        assert spy.count() == len(ACTION_TOKENS) + 1
        panel.set_state({"status": "passed"})
        panel.retranslate_ui()
        assert not panel._actions["run"].isEnabled()
        panel._cancel_button.setFocus()
        QTest.keyClick(panel._cancel_button, Qt.Key_Space)
        assert spy.at(spy.count() - 1)[0] == "cancel"
        panel.set_busy(False)
        assert all(button.isEnabled() for button in panel._actions.values())
        QTest.mouseClick(panel._actions["run"], Qt.LeftButton)
        assert spy.at(spy.count() - 1)[0] == "run"

        # Each of the four layers can pass alone; execution never promotes physics.
        for selected in LEVEL_TOKENS:
            panel.set_state({"levels": [{"level": selected, "status": "passed"}]})
            for level in LEVEL_TOKENS:
                expected = "Passed" if level == selected else "Unverified"
                assert panel._level_labels[level].text() == ui_text(expected)
        for status, source in STATUS_TEXT.items():
            panel.set_state({"levels": [{"level": "fields", "status": status}]})
            assert panel._level_labels["fields"].text() == ui_text(source)
        state = {
            "revision": 17, "fingerprint": "0123456789abcdef" * 4, "run_id": "run-17",
            "status": "future-success",
            "levels": [
                {"level": "fields", "status": "passed", "detail": "<b>raw diagnostic</b>"},
                {"level": "initialization", "status": "failed"},
                {"level": "execution", "status": "stale"},
                {"level": "physics", "status": ["passed"]},
                {"level": "future", "status": "passed"},
            ],
            "history": [
                {"level": "fields", "status": "passed"},
                {"level": "initialization", "status": "failed", "record_id": "r1"},
                {"level": "execution", "status": "stale", "record_id": "r2"},
                {"level": "future", "status": "future-success"},
                None,
            ],
        }
        panel.set_state(state)
        state["levels"][0]["status"] = "failed"
        assert panel._level_labels["fields"].text() == ui_text("Passed")
        assert panel._level_labels["physics"].text() == ui_text("Unobserved")
        assert "raw diagnostic" in panel._level_labels["fields"].accessibleDescription()
        assert panel._level_labels["fields"].textFormat() == Qt.PlainText
        assert "future-success" not in panel._summary_label.text()
        assert "0123456789ab…" in panel._summary_label.text()
        assert "run-17" in panel._summary_label.text()
        assert state["fingerprint"] in panel._summary_label.toolTip()
        assert panel._history_table.rowCount() == 4
        assert panel._history_table.item(3, 0).text() == ui_text("Unknown")
        assert panel._history_table.item(3, 1).text() == ui_text("Unobserved")

        for language in ("zh_CN", "en", "zh_CN", "en"):
            set_application_language(app, language)
            panel.retranslate_ui()
            for token in ACTION_TOKENS:
                assert panel._actions[token].text() == ui_text(ACTION_TEXT[token])
            assert panel._summary_group.title() == ui_text("Trusted experiment")
            assert panel._history_toggle.text() == ui_text("Validation history")
            assert panel._history_table.horizontalHeaderItem(0).text() == ui_text("Level")
            assert panel._history_table.item(1, 1).text() == ui_text("Failed")
            assert panel._history_table.item(2, 1).text() == ui_text("Stale")
            assert panel._actions["export"].toolTip() == ui_text(EXPORT_NOTE)
            for level in LEVEL_TOKENS:
                assert panel._level_names[level].text() == ui_text(LEVEL_TEXT[level])
            assert panel._level_labels["fields"].accessibleName() == ui_format(
                "{level}: {status}", level=ui_text(LEVEL_TEXT["fields"]), status=ui_text("Passed"))
            if language == "zh_CN":
                assert panel._actions["run"].text() != "Run"
                # Do not count English fallback as Chinese layout coverage.
                sources = (
                    *ACTION_TEXT.values(), *LEVEL_TEXT.values(), *STATUS_TEXT.values(),
                    "Trusted experiment", "Snapshot details", "Validation history",
                    "Level", "Status", "Record", "Unknown", EXPORT_NOTE,
                )
                for source in sources:
                    assert source in ZH_CN, source
                    assert ui_text(source) != source, source
                    assert any("\u4e00" <= ch <= "\u9fff" for ch in ui_text(source)), source
                for level in LEVEL_TOKENS:
                    assert any("\u4e00" <= ch <= "\u9fff" for ch in panel._level_names[level].text())
                    assert any("\u4e00" <= ch <= "\u9fff" for ch in panel._level_labels[level].text())
            # Offscreen geometry checks, not actual desktop/window observation.
            for width in (640, 480, 360, 480, 640, 360):
                panel.resize(width, 300)
                app.processEvents()
                assert panel.height() <= 300
                viewport = panel._scroll.viewport()
                assert panel._scroll.widget().width() == viewport.width()
                assert panel._actions_group.minimumSizeHint().width() <= viewport.width()
                for level in LEVEL_TOKENS:
                    for label in (panel._level_names[level], panel._level_labels[level]):
                        assert label.isVisible()
                        assert label.text()
                        top = label.mapTo(viewport, QPoint(0, 0))
                        assert top.y() >= 0
                        assert top.y() + label.height() <= viewport.height()
                        assert top.x() + label.width() <= viewport.width()
                        assert label.height() >= label.fontMetrics().height()
                assert panel._level_labels["physics"].text() == ui_text("Unobserved")

        panel._summary_toggle.click()
        panel._history_toggle.click()
        app.processEvents()
        assert panel._summary_label.isVisible()
        assert panel._history_group.isVisible()
        assert panel.height() <= 300
        assert panel._summary_toggle.arrowType() == Qt.DownArrow
        assert panel._history_toggle.arrowType() == Qt.DownArrow
        panel._scroll.ensureWidgetVisible(panel._history_table)
        app.processEvents()
        assert panel._history_table.isVisible()
        panel._history_toggle.click()
        panel._summary_toggle.click()
        panel.set_state({"history": []})
        assert panel._history_table.rowCount() == 0
        panel.set_state({"history": "bad", "levels": "bad"})
        assert panel._history_table.rowCount() == 0
        for level in LEVEL_TOKENS:
            assert panel._level_labels[level].text() == ui_text("Unverified")
        panel.set_state(None)
        assert panel._history_table.rowCount() == 0
        print(f"Qt platform={app.platformName()}; widths=640,480,360,480,640,360; maximum_height=300")
        print("PASS: K1 panel pure-Qt signals, independent layers, fallback, history, busy/cancel, i18n and offscreen geometry")
        return 0
    finally:
        if panel is not None:
            panel.close()
            panel.deleteLater()
            app.processEvents()
        set_application_language(app, old_language)


if __name__ == "__main__":
    raise SystemExit(main())
