from __future__ import annotations

import copy
import json
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PySide6.QtWidgets import QApplication, QPushButton
from PySide6.QtCore import Qt
from g4usim_gui.core.effective_config import parse_snapshot, SnapshotError, load_snapshot, MAX_BYTES
from g4usim_gui.core.i18n import set_application_language
from g4usim_gui.widgets.effective_config_page import EffectiveConfigPage


def main():
    field = dict(path="/source/objects/a~1b/energy", requested=None, resolved=None,
                 unit="MeV", application_status="unknown", evidence_level="manager_accepted",
                 reason="", evidence_source="", revision=1, applied_revision=None,
                 origins=[dict(kind="main_ini", file="中文.ini", line=2, raw="null")])
    data = dict(schema="g4usim_effective_config_v1", stage="configure", revision=1,
                run_id=None, scope="manager_state_subset", fields=[field])
    wire = json.dumps(data, ensure_ascii=False)
    assert parse_snapshot(wire)["fields"][0]["resolved"] is None
    bad = []
    for key, value in (("schema", "future"), ("revision", True), ("stage", "later"), ("stage", []), ("run_id", -1)):
        candidate = copy.deepcopy(data)
        candidate[key] = value
        bad.append(json.dumps(candidate))
    candidate = copy.deepcopy(data)
    candidate["fields"].append(copy.deepcopy(field))
    bad.append(json.dumps(candidate))
    for key, value in (("resolved", float("nan")), ("resolved", float("inf")),
                       ("path", "/bad/~x"), ("application_status", "valid"),
                       ("application_status", []), ("evidence_level", {}),
                       ("applied_revision", 1), ("revision", 2)):
        candidate = copy.deepcopy(data)
        candidate["fields"][0][key] = value
        bad.append(json.dumps(candidate))
    bad.extend(['{"schema":"x","schema":"y"}', wire.replace('"resolved": null', '"resolved": 1e999')])
    for text in bad:
        try:
            parse_snapshot(text)
        except SnapshotError:
            pass
        else:
            assert False, text
    app = QApplication.instance() or QApplication([])
    page = EffectiveConfigPage()
    assert page.snapshot is None and page.details.isReadOnly() and page.raw.isReadOnly()
    assert len(page.findChildren(QPushButton)) == 2
    with tempfile.TemporaryDirectory() as temp:
        path = Path(temp) / "快照.json"
        path.write_text(wire, encoding="utf-8")
        assert page.load_file(path)
        page.search.setText("a/b")
        assert page.tree.topLevelItemCount() == 1
        page.search.setText("a~1b")
        assert page.tree.topLevelItemCount() == 1
        page.search.clear()
        first = page.snapshot
        root = page.tree.topLevelItem(0)
        leaf = root.child(0).child(0).child(0)
        page.tree.setCurrentItem(leaf)
        assert "null" in page.details.toPlainText() and "中文.ini" in page.details.toPlainText()
        set_application_language(app, "zh_CN")
        page.refresh_language()
        assert page.tree.currentItem().data(0, Qt.UserRole)["path"] == field["path"]
        assert "请求值: null" in page.details.toPlainText() and "中文.ini" in page.details.toPlainText()
        set_application_language(app, "en")
        page.refresh_language()
        assert "requested: null" in page.details.toPlainText()
        path.write_text("{", encoding="utf-8")
        assert not page.load_file(path) and page.stale and page.snapshot is first
        assert page.raw.toPlainText() == wire and "Stale" in page.status.text()
        path.write_text(wire, encoding="utf-8")
        assert page.load_file(path) and not page.stale
        candidate = copy.deepcopy(data)
        del candidate["fields"][0]["resolved"]
        path.write_text(json.dumps(candidate), encoding="utf-8")
        assert page.load_file(path)
        assert page._value(page.snapshot["fields"][0], "resolved") != "null"
        # Missing requested is independently unknown even when application is known.
        candidate["fields"][0]["application_status"] = "not_applied"
        candidate["fields"][0]["resolved"] = None
        del candidate["fields"][0]["requested"]
        path.write_text(json.dumps(candidate), encoding="utf-8")
        assert page.load_file(path)
        page.unknown_only.setChecked(True)
        assert page.tree.topLevelItemCount() == 1
        assert page._value(page.snapshot["fields"][0], "requested") == "Unknown (not provided)"
        assert page._value(page.snapshot["fields"][0], "resolved") == "null"
        page.search.setText("unmatched")
        assert page.tree.topLevelItemCount() == 0
        page.search.clear()
        set_application_language(app, "zh_CN")
        page.refresh_language()
        assert "只读" in page.title.text()
        path.write_bytes(b" " * (MAX_BYTES + 1))
        assert not page.load_file(path) and page.stale
    page.close()
    page.deleteLater()
    app.processEvents()
    print("PASS: EffectiveConfig strict reader, null/missing, stale atomic reload, read-only Qt and Chinese")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
