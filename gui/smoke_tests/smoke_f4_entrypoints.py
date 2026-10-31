"""F4 entrypoints: producer evidence, no-write navigation and package JSON."""
from __future__ import annotations

from dataclasses import asdict
import json
import os
from pathlib import Path
import sys
import tempfile

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from PySide6.QtCore import QCoreApplication, QEvent, QSettings
from PySide6.QtWidgets import QApplication, QMessageBox
from g4usim_gui.core import scan, wizard as wz
from g4usim_gui.core.diagnostics import diagnostics_from_json
from g4usim_gui.core.i18n import set_application_language
from g4usim_gui.core.project import G4USimProject
from g4usim_gui.core.project_diagnostics import validate_project_report
from g4usim_gui.core.runner import G4USimRunner
from gui_test_window import MainWindow
from g4usim_gui.editors.material_editor_model import MaterialDocument, MaterialRow
from g4usim_gui.validators.config_validator import validate_config_builder
from g4usim_gui.widgets.new_simulation_wizard import NewSimulationWizard
from g4usim_gui.widgets.scenario_page import ScenarioPage
from g4usim_gui.widgets.scan_page import ScanPage
from smoke_k1_workflow import wait_workflow, close_window
from smoke_scans import make_base


def main():
    app = QApplication.instance() or QApplication([])
    app.setOrganizationName('G4UniversalSimSmoke')
    app.setApplicationName('F4Entrypoints')
    QSettings().clear()
    set_application_language(app, 'en')
    boxes = []
    QMessageBox.warning = staticmethod(lambda *args: boxes.append(str(args[2])))
    QMessageBox.information = staticmethod(lambda *args: None)

    with tempfile.TemporaryDirectory(prefix='g4usim-f4-entries-') as temp:
        root = Path(temp)
        p = G4USimProject(runInputMode='external', executable='', configPath='', macroPath='', outputDir='', threads=0, seed='oops')
        report = validate_project_report(p)
        assert report.errors == G4USimRunner.validate_project(p)
        assert {d.location.field for d in report.diagnostics} >= {'executable', 'config_path', 'output_dir', 'threads', 'seed'}
        ids = [d.identity for d in report.diagnostics]
        set_application_language(app, 'zh_CN')
        assert ids == [d.identity for d in validate_project_report(p).diagnostics]
        set_application_language(app, 'en')

        w = MainWindow(); w.show(); app.processEvents()
        w.project_page.executable.setText('')
        w._validate_project_diagnostics()
        d = next(d for d in w.run_page.diagnostics_panel.records if d.location.field == 'executable')
        before = asdict(w.project)
        w.page_stack.setCurrentWidget(w.run_page)
        assert w._run_diagnostics.navigate(d)
        assert w.page_stack.currentWidget() is w.project_page
        assert w.project_page.executable.property('diagnosticFocus') is True
        assert asdict(w.project) == before
        old_report = w.runner.validation_report(w.project)
        w._run_diagnostics.set_report(old_report)
        w.project_page.executable.setText(sys.executable)
        assert not w._run_diagnostics.navigate(d)
        assert w.run_page.diagnostics_panel.stale
        w._run_diagnostics.set_report(old_report)
        assert w.run_page.diagnostics_panel.stale and not w._run_diagnostics.navigate(d)
        w.project_page.executable.setText('')
        w._run_diagnostics.set_report(old_report)
        assert w.run_page.diagnostics_panel.stale, 'reverting values must not revive old reports'
        w._validate_project_diagnostics()
        d = next(d for d in w.run_page.diagnostics_panel.records if d.location.field == 'executable')
        w.page_stack.setCurrentWidget(w.run_page)
        row = w.project_page.executable.parentWidget()
        row.hide()
        assert not w._run_diagnostics.navigate(d)
        assert w.page_stack.currentWidget() is w.run_page
        row.show()
        assert w._run_diagnostics.navigate(d)
        w._run_diagnostics.highlighter.timer.setInterval(30000)
        w._set_theme('dark')
        assert w._run_diagnostics.highlighter.target is None
        assert w._run_diagnostics.navigate(d)
        w._set_language('zh_CN', persist=False)
        assert w._run_diagnostics.highlighter.target is None
        assert w.run_page.diagnostics_panel.table.horizontalHeaderItem(0).text() == '严重度'
        assert '请填写可执行程序路径' in w.run_page.diagnostics_panel.table.item(0, 3).text()
        w._set_language('en', persist=False)
        w._present_raw_run_diagnostic('backend.test', 'raw backend refusal\nsecond line')
        raw = w.run_page.diagnostics_panel.records[0]
        assert raw.raw_message == 'raw backend refusal\nsecond line' and raw.location is None
        assert not w._run_diagnostics.navigate(raw)
        assert 'structured' in raw.unavailable_reason

        s = ScenarioPage(); s.show(); app.processEvents()
        s.set_values({'threads': 'oops'})
        assert s.validate_form()
        d = s.diagnostics_panel.records[0]
        assert d.location.field == 'threads'
        before = s.values()
        assert s.diagnostic_controller.navigate(d)
        assert s.values() == before
        s.set_values({'threads': '2'})
        assert not s.diagnostic_controller.navigate(d)
        s.set_values({'pore_fraction': '2'})
        s.validate_form()
        advanced = next(d for d in s.diagnostics_panel.records if d.location.field == 'pore_fraction')
        s.advanced_check.setChecked(False)
        before = s.values()
        assert s.diagnostic_controller.navigate(advanced)
        assert s.advanced_check.isChecked() and s.values() == before

        wizard = NewSimulationWizard(); wizard.show(); app.processEvents()
        for _ in range(3): wizard.next(); app.processEvents()
        assert wizard.currentId() == 3
        wizard.run_page.seed.setText('not-an-integer')
        app.processEvents()
        assert not wizard.run_page.isComplete()
        d = next(d for d in wizard.run_page.diagnostics_panel.records if d.code == 'wizard.seed_parse')
        before = (asdict(wizard.spec), wizard._diagnostic_values())
        assert wizard.diagnostic_controller.navigate(d)
        assert (asdict(wizard.spec), wizard._diagnostic_values()) == before
        # A real earlier-page validation failure, preserving the visible invalid
        # selection and the wizard model across the presentation-only jump.
        wizard.spec.target_material = 'unavailable-material'
        wizard.geometry_page.target_material.setCurrentIndex(-1)
        wizard.run_page._update()
        d = next(d for d in wizard.run_page.diagnostics_panel.records if d.location.field == 'target_material')
        before = (asdict(wizard.spec), wizard._diagnostic_values())
        assert wizard.diagnostic_controller.navigate(d)
        assert wizard.currentId() == 1
        assert (asdict(wizard.spec), wizard._diagnostic_values()) == before

        base = make_base(root / 'scans')
        param = next(p for p in scan.parameters(base) if p.key == 'source.energy')
        invalid = scan.validate_scan_report(base, param, ['lots', 'lots'])
        assert len(invalid.errors) == 2
        assert len({d.identity for d in invalid.diagnostics}) == 2
        assert all(d.location.field == 'values' for d in invalid.diagnostics)
        assert not (root / 'scans').exists()
        base.source.particle = ''
        derived = scan.validate_scan_report(base, param, ['1 MeV'])
        assert not derived.can_run
        assert all(d.location is None for d in derived.diagnostics)
        assert any(d.related_locations for d in derived.diagnostics)
        base = make_base(root / 'scans')
        base.materials = MaterialDocument(is_dirty=True, rows=[
            MaterialRow(name='same', density='bad', components_text='Si:1'),
            MaterialRow(name='same', density='bad', components_text='Si:1')])
        point = scan.apply_value(base, param, '1 MeV')
        expected = validate_config_builder(paths=point.paths, run=point.run,
            geometry=point.geometry_settings, source=point.source.to_settings(),
            physics=point.physics.to_settings(), scoring=point.scoring.to_settings(),
            material_document=point.materials, geometry_document=point.geometry,
            source_model=point.source, physics_model=point.physics, scoring_model=point.scoring)
        derived = scan.validate_scan_report(base, param, ['1 MeV'])
        assert derived.errors == ['1 MeV: ' + text for text in expected.errors]
        assert len(derived.errors) == 2 and len(derived.diagnostics) == 4
        assert len({record.identity for record in derived.diagnostics}) == 4
        assert diagnostics_from_json(json.dumps(derived.to_dict())).errors == tuple(derived.errors)
        base = make_base(root / 'scans')
        sp = ScanPage(); sp.set_base_provider(lambda: (base, str(root / 'scans'), sys.executable, str(root)))
        assert sp.refresh_base()
        sp.values.setText('')
        assert not sp.validate_inputs()
        d = sp.diagnostics_panel.records[0]
        assert d.location.field == 'values'
        sp.show(); app.processEvents()
        assert sp.diagnostic_controller.navigate(d)
        sp.refresh_base()
        assert not sp.diagnostic_controller.navigate(d)
        assert not (root / 'scans').exists()

        # Real writer route (wizard -> configuration -> package), with the old
        # human text and new strict machine report both retained.
        w.project.runsRoot = str(root / 'packages')
        w.project.executable = sys.executable
        w.project.pathSettings.executable = sys.executable
        w.project_page.set_project(w.project)
        assert w.apply_simulation_wizard(wz.default_spec('shielding'), run_after=False)
        w.generate_package(run_after_generate=False)
        wait_workflow(app, w)
        assert not boxes, boxes
        files = list((root / 'packages').rglob('validation_diagnostics.json'))
        assert len(files) == 1
        bundle = diagnostics_from_json(files[0].read_bytes())
        assert bundle.can_run and not bundle.errors
        human = files[0].with_name('validation_report.txt')
        assert human.is_file() and human.read_text(encoding='utf-8')
        assert json.loads(files[0].read_text(encoding='utf-8'))['schema'] == 'g4usim_diagnostics_v1'
        # Config report -> Project routes use the original valid Config report,
        # not a newly invented Project validation result.
        w.project_page.executable.setText('')
        report = w.config_builder_page.validate_current(w.project)
        w.config_builder_page.set_validation_report(report)
        d = next(record for record in w.config_builder_page.diagnostic_panel.records
                 if record.location and record.location.editor == 'setup' and record.location.field == 'executable')
        before = asdict(w.project)
        w.page_stack.setCurrentWidget(w.config_builder_page)
        assert w._navigate_config_project_diagnostic(d)
        assert w.page_stack.currentWidget() is w.project_page and asdict(w.project) == before
        w.project_page.executable.setText(sys.executable)
        assert not w._navigate_config_project_diagnostic(d)
        close_window(app, w)
        for widget in (sp, wizard, s, w):
            widget.close(); widget.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        app.processEvents()
    print('smoke_f4_entrypoints: OK')


if __name__ == '__main__':
    main()
