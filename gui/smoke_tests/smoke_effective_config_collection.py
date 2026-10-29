"""Collection review regression: no backend execution or success inference."""
from __future__ import annotations
import copy
import json
import os
import sys
import tempfile
from pathlib import Path
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from g4usim_gui.core.effective_config import MAX_BYTES, SnapshotError, parse_snapshot, snapshot_diff
from g4usim_gui.core.i18n import set_application_language
from g4usim_gui.core.theme import apply_theme
from g4usim_gui.widgets.effective_config_page import EffectiveConfigPage

def main():
    app = QApplication.instance() or QApplication([])
    # Windows offscreen plugin may not enumerate system font files itself.
    for name in ('segoeui.ttf', 'msyh.ttc'):
        font_path = Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Fonts' / name
        if font_path.exists():
            assert QFontDatabase.addApplicationFont(str(font_path)) >= 0
    page = EffectiveConfigPage()
    field = dict(path='/source/objects/a~1b~0c/energy', requested=None, resolved=None,
                 application_status='not_applied', evidence_level='manager_accepted', revision=1,
                 origins=[dict(kind='main_ini', file='中文.ini', line=3, raw='null')])
    data = dict(schema='g4usim_effective_config_v1', stage='configure', revision=1,
                run_id=None, scope='manager_state_subset', fields=[field])
    def changed(value):
        result = copy.deepcopy(data)
        result['fields'][0]['resolved'] = value
        return result
    for a, b in ((None, False), (False, 0), (0, 0.0), ({'x': False}, {'x': 0})):
        assert snapshot_diff(changed(a), changed(b))[0]['keys'] == ['resolved']
    missing = copy.deepcopy(data)
    del missing['fields'][0]['resolved']
    assert snapshot_diff(missing, data)[0]['keys'] == ['resolved']
    assert not snapshot_diff(data, copy.deepcopy(data))
    for invalid in (-1, True, 1.5, '2', None):
        bad_generation = copy.deepcopy(data)
        bad_generation['fields'][0]['configuration_generation'] = invalid
        try:
            parse_snapshot(json.dumps(bad_generation))
        except SnapshotError:
            pass
        else:
            assert False, invalid
    for valid in (0, 1, 12):
        generation = copy.deepcopy(data)
        generation['fields'][0]['configuration_generation'] = valid
        assert parse_snapshot(json.dumps(generation))['fields'][0]['configuration_generation'] == valid
    added = copy.deepcopy(data)
    added['fields'].append(dict(field, path='/physics/reference'))
    assert snapshot_diff(data, added)[0]['kind'] == 'added'
    assert snapshot_diff(added, data)[0]['kind'] == 'removed'
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        a, b, bad = [root / name for name in ('a.json','b.json','bad.json')]
        wire = json.dumps(data, ensure_ascii=False)
        a.write_text(wire, encoding='utf-8')
        b.write_text(wire, encoding='utf-8')
        bad.write_text('{', encoding='utf-8')
        assert page.load_files([a,b]) and len(page._snapshots) == 2
        page.baseline_combo.setCurrentIndex(1)
        page.snapshot_combo.setCurrentIndex(1)
        assert 'No differences' in page.diff.toPlainText()
        assert page._baseline == 0 and page._current == 1
        old_set, old_snapshot = page._snapshots, page.snapshot
        assert not page.load_files([a,bad])
        assert page._snapshots is old_set and page.snapshot is old_snapshot and page.stale
        assert not page.load_files([]) and not page.load_files([a] * 65)
        assert page._snapshots is old_set
        # Reload must preserve the WHOLE old collection if another member fails.
        a.write_text('{', encoding='utf-8')
        page._reload()
        assert page._snapshots is old_set and page.stale
        a.write_text(wire, encoding='utf-8')
        page._reload()
        assert not page.stale and page._baseline == 0 and page._current == 1
        huge = root / 'huge.json'
        huge.write_bytes(b' ' * (MAX_BYTES + 1))
        assert not page.load_file(huge) and '4 MiB' in page.status.text()
        # Actual bytes: each valid padded document is 4 MiB; eight fit, nine fail.
        padded = wire.encode('utf-8')
        huge.write_bytes(padded + b' ' * (MAX_BYTES-len(padded)))
        assert page.load_files([huge]*8)
        old_set = page._snapshots
        assert not page.load_files([huge]*9) and '32 MiB' in page.status.text()
        assert page._snapshots is old_set and page.stale
        assert page.load_files([a]*64) and len(page._snapshots) == 64
        assert page.load_files([a,b])
        page.search.setText('a/b~c')
        assert page.tree.topLevelItemCount() == 1
        leaf = page.tree.topLevelItem(0).child(0).child(0).child(0)
        assert leaf.toolTip(0) == field['path']
        page.tree.setCurrentItem(leaf)
        out = Path('out/collab/full2c-frontend-review')
        out.mkdir(parents=True, exist_ok=True)
        for lang in ('zh_CN','en'):
            set_application_language(app,lang)
            page.refresh_language()
            assert page.tree.currentItem().data(0,Qt.UserRole)['path'] == field['path']
            assert '中文.ini' in page.details.toPlainText()
            for theme in ('light','dark'):
                apply_theme(app,theme)
                page.resize(820,680)
                page.show()
                app.processEvents()
                assert page.width() <= 820, page.minimumSizeHint().width()
                assert page.grab().save(str(out/f'{lang}-{theme}-820.png'))
        assert 'simulation success' in page.boundary.text()
        assert page.details.isReadOnly() and page.raw.isReadOnly() and page.diff.isReadOnly()
    page.close()
    page.deleteLater()
    app.processEvents()
    print('PASS: collection atomic reload, limits, identity, typed diff, language, theme, narrow layout')
    return 0
if __name__ == '__main__':
    raise SystemExit(main())
