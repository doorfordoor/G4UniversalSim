"""External Inspect uses original inputs; generated captures stay guarded.

Permanent regression candidate. Run from the checkout via test_assert_probe.
The OUT overlay harness supplies the checkout import paths during review.
"""
from pathlib import Path
import copy
import hashlib
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
if not (ROOT / "gui/g4usim_gui/__init__.py").is_file():
    ROOT = Path.cwd().resolve()
sys.path[:0] = [str(ROOT / "gui"), str(ROOT / "scripts")]

from test_f5_transactions_backend import initial_state
from g4usim_gui.core.edit_snapshot import WorkspaceSnapshot, snapshot_to_dict
from g4usim_gui.core.experiment_workflow import _field_report, _original_inspection_identity
from g4usim_gui.core.experiment_bundle import collect_bundle_resources
from g4usim_gui.core.run_editor_model import GPSDefinition


def changed_sources(snapshot):
    return {record.raw_message for record in _field_report(snapshot).diagnostics
            if record.code == "experiment.captured_source.changed"}


def main():
    with tempfile.TemporaryDirectory(prefix="external-source-scope-") as raw:
        folder = Path(raw)
        generated, paths = initial_state(folder, Path(sys.executable))
        generated.project.runInputMode = "generated"
        assert _field_report(generated).can_run
        assert not changed_sources(generated)
        external = copy.deepcopy(generated)
        external.project.runInputMode = "external"
        main_file = folder / "main.ini"
        macro_file = folder / "top.mac"
        nested = folder / "nested.mac"
        main_file.write_text("[run]\nseed = 17\n", encoding="utf-8")
        macro_file.write_text('/control/execute "nested.mac"\n', encoding="utf-8")
        nested.write_text('# retained nested macro; no execution\n', encoding="utf-8")
        external.project.configPath = str(main_file)
        external.project.macroPath = str(macro_file)
        external.project.outputDir = str(folder / "not-created")
        # Retain old documents and captured text, including unavailable sources.
        external.project.pathSettings.materials_config = ""
        external.project.geometrySettings.config_path = ""
        external.project.pathSettings.geometry_config = ""
        original = snapshot_to_dict(external)
        assert _field_report(external).can_run
        assert snapshot_to_dict(external) == original
        assert external.state["sources"] == generated.state["sources"]
        assert external.project.materialEditor.source_path
        assert external.project.geometryEditor.source_path
        # Still perform full retained-editor closure for offline editable export.
        bundle = collect_bundle_resources(external)
        assert {"materials", "geometry"} <= {row["role"] for row in bundle["resources"]}
        policy = {str(main_file.resolve()): {"distribution": "restricted"}}
        try:
            collect_bundle_resources(external, resource_policy=policy)
        except ValueError as error:
            assert "Restricted resource requires explicit redistribution policy" in str(error)
        else:
            assert False, "A user's restricted decision must block export"
        policy[str(main_file.resolve())]["allow_redistribution"] = True
        assert collect_bundle_resources(external, resource_policy=policy)["resources"]
        # Generated path changes and failed reads reject even with files intact.
        for kind in ("materials", "geometry"):
            changed = copy.deepcopy(generated)
            changed.state["sources"][kind]["read_success"] = False
            assert kind in changed_sources(changed)
            changed = copy.deepcopy(generated)
            if kind == "materials":
                changed.project.pathSettings.materials_config = ""
            else:
                changed.project.geometrySettings.config_path = ""
            assert kind in changed_sources(changed)
        # Explicit dormant generated selections are still not external inputs.
        selected = copy.deepcopy(external)
        selected.project.pathSettings.materials_config = str(paths[0])
        selected.project.geometrySettings.config_path = str(paths[1])
        paths[0].write_text("# changed after capture\n", encoding="utf-8")
        paths[1].unlink()
        assert _field_report(external).can_run
        assert _field_report(selected).can_run
        assert changed_sources(generated) == {"materials", "geometry"}
        assert not _field_report(generated).can_run
        # Empty/changed selected generated paths cannot wash out lost sources.
        for kind in ("materials", "geometry"):
            candidate = copy.deepcopy(generated)
            if kind == "materials":
                candidate.project.pathSettings.materials_config = ""
            else:
                candidate.project.geometrySettings.config_path = ""
            assert kind in changed_sources(candidate)
        # Identity still hashes the real external main/macro, never the editors.
        identity = _original_inspection_identity(external, 0)
        receipts = identity["declared_source_receipts"]
        assert set(receipts) == {str(main_file.resolve()), str(macro_file.resolve())}
        assert receipts[str(main_file.resolve())]["sha256"] == hashlib.sha256(main_file.read_bytes()).hexdigest()
        assert identity["recursive_closure"] == "unobserved"
        main_file.write_text("[run]\nseed = 18\n", encoding="utf-8")
        assert _original_inspection_identity(external, 0)["fingerprint"] != identity["fingerprint"]
        missing = copy.deepcopy(external)
        missing.project.configPath = str(folder / "missing-main.ini")
        assert not _field_report(missing).can_run
        missing = copy.deepcopy(external)
        missing.project.macroPath = str(folder / "missing-macro.mac")
        assert not _field_report(missing).can_run
        # Complete offline edit bundles retain strict dormant resource closure.
        # A named source's inactive spectrum is retained, not silently discarded.
        retained = copy.deepcopy(external)
        retained.project.sourceEditor.gps_sources = [GPSDefinition(
            name="retained", energy_type="mono", spectrum_file=str(folder / "missing-inactive-spectrum.txt"))]
        try:
            collect_bundle_resources(retained)
        except ValueError as error:
            assert "Complete editable export requires every retained resource" in str(error)
            assert "spectrum_file" in str(error)
        else:
            assert False, "Missing retained spectrum must block complete editable export"
        assert snapshot_to_dict(external) == original
        assert not Path(external.project.outputDir).exists()
    print("external Inspect source scope: OK (history retained; generated and bundle guards preserved)")


if __name__ == "__main__":
    main()
