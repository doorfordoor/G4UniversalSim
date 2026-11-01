"""J2 finite NIST catalog, real editor/writer/parser/project and Qt checks.

Optional actual Geant4 construction: --backend (requires G4USIM_EXE).
No backend is inferred from a build directory.
"""
from __future__ import annotations

import argparse
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'gui'))
from g4usim_gui.core.nist_elements import NIST_ELEMENTS, NIST_MATERIALS, custom_elements, search_elements
from g4usim_gui.core.project import G4USimProject, save_project, load_project
from g4usim_gui.editors.material_editor_model import (
    MaterialDocument, MaterialRow, component_source, generate_materials_ini_text,
    material_document_from_summary, validate_material_document)
from g4usim_gui.parsers.materials_parser import parse_materials, parse_materials_text
from g4usim_gui.writers.materials_ini_writer import write_materials_ini

CUSTOM = '[isotope.Si30]\nsymbol = Si\nz = 14\nn = 30\na = 29.97377 g/mol\n\n[element.Si]\nsymbol = enrichedSi\nisotopes = Si30:1\n'


def doc(mode='atom_count', components='H:2, G4_O:1', density='1 g/cm3'):
    return MaterialDocument(rows=[MaterialRow(name='J2Water', mode=mode,
        density=density, components_text=components)], is_dirty=True)


def density_checks(work):
    from g4usim_gui.editors.material_editor_model import density_internal_value
    units = ['g/cm3', 'g/cm^3', 'kg/m3', 'kg/m^3', 'mg/cm3', 'mg/cm^3']
    for unit in units:
        for number in ['1', '2.7', '.5', '+1.25e-3', '0x1.4p+1']:
            for separator in [' ', '*', ' * ', '  *\t']:
                density = number + separator + unit.upper()
                original = '[material.Probe]\nmode=mass_fraction\ndensity=' + density + '\ncomponents=O:1\n'
                model = material_document_from_summary(parse_materials_text(original, source_path='density.ini'))
                assert not model.errors, (density, model.errors)
                text = write_materials_ini(work / 'density.ini', model)
                assert 'density = ' + density in text
                reloaded = material_document_from_summary(parse_materials(work / 'density.ini'))
                assert not reloaded.errors and reloaded.rows[0].density == density
    for unit in units:
        # All three units overflow their internal mass multiplication here.
        for number in ['1e308', '1e999', '1e-999', '0x1p-2000', '0', '-1']:
            bad = doc(density=number + ' * ' + unit)
            assert validate_material_document(bad).errors, bad.rows[0].density
            assert density_internal_value(bad.rows[0].density) is None
    for text in ['1 ** g/cm3', '1 g / cm3', '1e g/cm3', '1_0 g/cm3', 'nan g/cm3', 'inf g/cm3']:
        assert density_internal_value(text) is None, text
    # Would be finite if a pre-divided unit factor were used; C++ multiplies first.
    assert density_internal_value('1e287 g/cm3') is None
    assert density_internal_value('1e283 kg/m3') is not None
    assert density_internal_value('1e-300 mg/cm3') is not None


def model_checks(work):
    assert len(NIST_ELEMENTS) == 107 and 'Si' in NIST_ELEMENTS and 'G4_Si' in NIST_MATERIALS
    assert search_elements('14')[0].name == 'Si'
    d = doc()
    assert not validate_material_document(d).errors, d.errors
    assert component_source('H', 'atom_count', d).kind == 'nist_element'
    assert component_source('G4_O', 'atom_count', d).name == 'O'
    assert component_source('si', 'atom_count', d).kind == 'missing'
    for mode, components in [('atom_count', 'Sii:1'), ('mass_fraction', 'G4_Sii:1'),
                             ('atom_count', 'G4_WATER:1'), ('volume_fraction', 'Si:1')]:
        invalid = doc(mode, components, 'auto' if mode == 'volume_fraction' else '1 g/cm3')
        assert validate_material_document(invalid).errors, (mode, components)
        try:
            generate_materials_ini_text(invalid)
        except ValueError:
            pass
        else:
            assert False, (mode, components)
    for density in ['nan g/cm3', 'inf g/cm3', '1e999 g/cm3', '0 g/cm3', '1 wrong', '1']:
        assert validate_material_document(doc(density=density)).errors, density
    for value in ['nan', 'inf', '1e999', '2147483648', '1.5', '1_0']:
        assert validate_material_document(doc(components='Si:' + value)).errors, value
    assert not validate_material_document(doc('mass_fraction', 'Si:50%; O:50%')).errors
    assert not validate_material_document(doc('volume_fraction', 'G4_Si:1', 'auto')).errors
    d.preserved_sections = [CUSTOM]
    d.rows[0].components_text = 'si:1'
    assert not validate_material_document(d).errors, d.errors
    assert component_source('si', 'atom_count', d).kind == 'custom_element'
    assert component_source('G4_Si', 'atom_count', d).kind == 'nist_element'
    assert [s.kind for s in search_elements('Si', elements=custom_elements(d.preserved_sections)) if s.name == 'Si'] == ['custom_element']
    assert [(s.kind, s.name) for s in search_elements('G4_Si', elements=custom_elements(d.preserved_sections))] == [('nist_element', 'G4_Si')]
    target = work / 'materials.ini'
    text = write_materials_ini(target, d)
    assert CUSTOM.rstrip() in text and not target.read_bytes().startswith(b'\xef\xbb\xbf')
    loaded = material_document_from_summary(parse_materials(target))
    assert not loaded.errors, loaded.errors
    assert component_source('si', 'atom_count', loaded).kind == 'custom_element'
    assert '[isotope.Si30]' in generate_materials_ini_text(loaded)
    project = G4USimProject(materialEditor=d)
    save_project(project, work / 'project.json')
    restored = load_project(work / 'project.json').materialEditor
    assert restored.source_path == '' and restored.raw_source_text == '' and restored.is_dirty
    assert restored.preserved_sections == d.preserved_sections
    assert generate_materials_ini_text(restored) == text
    from g4usim_gui.core import wizard
    from g4usim_gui.models.package_model import PathSettings
    from g4usim_gui.writers.package_writer import create_run_package
    project = G4USimProject(executable=sys.executable, workspaceRoot=str(work), runsRoot=str(work / 'runs'))
    project.pathSettings = PathSettings(executable=sys.executable, workspace_root=str(work), runs_root=project.runsRoot)
    wizard.apply_to_project(project, wizard.blank_result())
    project.materialEditor = restored
    project.geometryEditor.volumes[0].material = 'J2Water'
    package, report = create_run_package(project=project, paths=project.pathSettings, run=project.runSettings,
        geometry=project.geometrySettings, source=project.sourceSettings, physics=project.physicsSettings,
        scoring=project.scoringSettings, material_document=project.materialEditor, geometry_document=project.geometryEditor,
        source_model=project.sourceEditor, physics_model=project.physicsEditor, scoring_model=project.scoringEditor)
    package_doc = material_document_from_summary(parse_materials(package.materials_ini_path))
    assert not package_doc.errors and component_source('si', 'atom_count', package_doc).kind == 'custom_element'
    assert '[isotope.Si30]' in Path(package.materials_ini_path).read_text(encoding='utf-8')
    nist = material_document_from_summary(parse_materials_text('[NIST]\nmaterials=G4_WATER\n', source_path='nist.ini'))
    assert component_source('g4_water', 'volume_fraction', nist).kind == 'nist_material'
    assert parse_materials_text('[NIST]\nmaterials=G4_WATERR\n', source_path='bad.ini').errors
    assert not validate_material_document(MaterialDocument(is_dirty=True)).errors
    assert generate_materials_ini_text(MaterialDocument(is_dirty=True))
    bad = material_document_from_summary(parse_materials_text('[element.Si]\nsymbol=Si\nsymbol=xx\n', source_path='bad.ini'))
    assert bad.source_errors
    validate_material_document(bad)
    assert bad.source_errors and bad.errors
    # A material declaration must not masquerade as an element in atom_count.
    material = doc('mass_fraction', 'Si:1')
    material.rows[0].name = 'Base'
    material.rows.append(MaterialRow(name='Child', mode='atom_count', density='1 g/cm3', components_text='Base:1'))
    assert validate_material_document(material).errors


def qt_checks(work, preview=None):
    from PySide6.QtWidgets import QApplication
    from g4usim_gui.core.i18n import set_application_language
    from g4usim_gui.widgets.config_builder_page import ConfigBuilderPage
    app = QApplication.instance() or QApplication([])
    app.setStyle('Fusion')
    if preview and os.name == 'nt':
        from PySide6.QtGui import QFontDatabase
        for font in ('msyh.ttc', 'segoeui.ttf'):
            path = Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Fonts' / font
            if path.is_file():
                QFontDatabase.addApplicationFont(str(path))
    from g4usim_gui.core.theme import apply_theme
    apply_theme(app, 'light')
    page = ConfigBuilderPage()
    page._backend_timer.stop()
    page.material_document = doc(components='H:2')
    page.materials_config.clear()
    page._selected_material_row = 0
    page._populate_material_editor()
    page.materials_table.selectRow(0)
    page.element_search.setText('G4_O')
    assert page.element_choices.currentText() == 'O'
    assert page.insert_element_button.isEnabled()
    page.insert_element_button.click()
    assert 'O:1' in page.material_document.rows[0].components_text
    before = copy.deepcopy(page.material_document)
    page.reload_materials()
    assert page.material_document == before
    assert 'memory' in page.materials_messages.toPlainText()
    page.revert_materials_button.click()
    assert page.material_document == before
    assert 'automatic' in page.material_notes.toPlainText()
    page.element_search.setText('Typoooo')
    assert page.element_choices.count() == 0 and not page.insert_element_button.isEnabled()
    # File import really rereads the file and retains its source errors.
    source = work / 'import.ini'
    source.write_text('[material.Imported]\nmode=atom_count\ndensity=1 g/cm3\ncomponents=Sii:1\n', encoding='utf-8')
    page.materials_config.setText(str(source))
    page.reload_materials()
    assert page.material_document.rows[0].name == 'Imported' and page.material_document.errors
    source.write_text('[material.Imported]\nmode=atom_count\ndensity=1 g/cm3\ncomponents=Si:1\n', encoding='utf-8')
    page.reload_materials()
    assert not page.material_document.errors, page.material_document.errors
    page.material_document.rows[0].mode = 'volume_fraction'
    page._select_material_row(0)
    assert not page.insert_element_button.isEnabled()
    set_application_language(app, 'zh_CN')
    page.refresh_language()
    from g4usim_gui.core.i18n import ZH_CN
    if 'Insert element component' in ZH_CN:
        assert page.insert_element_button.text() == ZH_CN['Insert element component']
    page.material_document.rows[0].mode = 'atom_count'
    page._select_material_row(0)
    if 'NIST element {name} (automatic; no declaration required)' in ZH_CN:
        assert ZH_CN['NIST element {name} (automatic; no declaration required)'].format(name='Si') in page.material_notes.toPlainText()
    if preview:
        page.element_search.setText('Si')
        from g4usim_gui.core.i18n import apply_language
        apply_language(page, 'zh_CN')
        page.refresh_language()
        # Render this actual editor and source resolution state, without desktop automation.
        page.materials_editor.setParent(None)
        page.materials_editor.resize(1100, 900)
        page.materials_editor.show()
        app.processEvents()
        preview.parent.mkdir(parents=True, exist_ok=True)
        assert page.materials_editor.grab().save(str(preview))
        page.materials_editor.close()
        page.materials_editor.setParent(page)
    set_application_language(app, 'en')
    page._backend_timer.stop()
    page.close()
    page.deleteLater()
    app.processEvents()


def backend_checks(work):
    exe = Path(os.environ['G4USIM_EXE']).resolve()
    assert exe.is_file(), exe
    receipts = []
    fixtures = {
        'nist': ('[material.Probe]\nmode=atom_count\ndensity=1 g/cm3\ncomponents=H:2,G4_O:1\n', True),
        'custom': (CUSTOM + '\n[material.Probe]\nmode=atom_count\ndensity=1 g/cm3\ncomponents=si:1\n', True),
        'typo': ('[material.Probe]\nmode=atom_count\ndensity=1 g/cm3\ncomponents=Sii:1\n', False),
        'volume_element': ('[material.Probe]\nmode=volume_fraction\ndensity=auto\ncomponents=Si:1\n', False),
        'volume_material': ('[material.Probe]\nmode=volume_fraction\ndensity=auto\ncomponents=G4_Si:1\n', True),
    }
    for name, (body, valid) in fixtures.items():
        folder = work / name
        folder.mkdir(parents=True, exist_ok=True)
        material = folder / 'material.ini'
        material.write_text(body, encoding='utf-8')
        geometry = folder / 'geometry.ini'
        geometry.write_text('[world]\nsize=10 cm,10 cm,10 cm\nmaterial=G4_AIR\n[target]\nsize=1 cm,1 cm,1 cm\nmaterial=Probe\n', encoding='utf-8')
        config = folder / 'main.ini'
        config.write_text('[materials]\nfile=' + material.as_posix() + '\n[geometry]\ntemplate=simple_box\nconfig=' + geometry.as_posix() + '\n', encoding='utf-8')
        macro = folder / 'run.mac'
        macro.write_text('/run/initialize\n/run/beamOn 1\n', encoding='utf-8')
        output = folder / 'run'
        assert not output.exists(), 'Use a fresh evidence directory for backend runs'
        snapshot = output / 'effective_config_finalization.json'
        process = subprocess.run([str(exe), '--config', str(config), '--macro', str(macro), '--output', str(output), '--threads', '1'],
            cwd=folder, capture_output=True, text=True, errors='replace', timeout=90)
        log = process.stdout + process.stderr
        (folder / 'backend.log').write_text(log, encoding='utf-8')
        receipts.append({'case': name, 'exit_code': process.returncode, 'expected_valid': valid})
        if valid:
            assert process.returncode == 0 and snapshot.is_file(), log[-3000:]
            data = json.loads(snapshot.read_text(encoding='utf-8'))
            observed = [r for r in data.get('evidence', []) if r.get('path', '').endswith('material:Probe/composition_observed')]
            assert observed, data.keys()
            assert all(r.get('evidence_level') == 'kernel_constructed' for r in observed)
            summary = (output / 'run_summary.txt').read_text(encoding='utf-8')
            assert 'status = completed' in summary and 'completed_events = 1' in summary
            if name == 'nist':
                assert {e['element'] for e in observed[-1]['observed']} == {'H', 'O'}
            text = json.dumps(observed)
            assert ('Si' in text if name == 'custom' else True), observed
            if name == 'custom':
                isotopes = [r['observed'] for r in data['evidence'] if r['path'].endswith('element:Si/isotopes')]
                assert isotopes and isotopes[-1] == [{'name': 'Si30', 'abundance': 1.0}], isotopes
                masses = [r['observed'] for r in data['evidence'] if r['path'].endswith('element:Si/a')]
                assert masses and abs(masses[-1] - 29.97377) < 1e-5, masses
        else:
            assert process.returncode == 1, (process.returncode, log[-3000:])
            assert ('element' in log.lower() if name == 'volume_element' else 'element' in log.lower() or 'component' in log.lower()), log[-3000:]
    (work / 'receipts.json').write_text(json.dumps(receipts, indent=2), encoding='utf-8')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--backend', action='store_true')
    parser.add_argument('--density-only', action='store_true')
    parser.add_argument('--output', type=Path)
    parser.add_argument('--translations', type=Path)
    parser.add_argument('--preview', type=Path)
    args = parser.parse_args()
    if args.translations:
        from g4usim_gui.core.i18n import ZH_CN
        ZH_CN.update(json.loads(args.translations.read_text(encoding='utf-8')))
    if args.backend:
        if args.output is None:
            evidence = Path(tempfile.mkdtemp(prefix='g4usim-j2-materials-backend-')).resolve()
        else:
            evidence = args.output.resolve()
            evidence.mkdir(parents=True, exist_ok=False)
        print('J2 backend evidence: ' + str(evidence), flush=True)
        backend_checks(evidence)
    else:
        with tempfile.TemporaryDirectory(prefix='j2-materials-') as temp:
            density_checks(Path(temp))
            if not args.density_only:
                model_checks(Path(temp))
                qt_checks(Path(temp), args.preview)
    print('J2 density checks passed' if args.density_only else 'J2 materials checks passed'  + (' (actual backend construction)' if args.backend else ' (model/writer/parser/project/Qt)'))


if __name__ == '__main__':
    main()
