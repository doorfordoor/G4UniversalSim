"""Late changed() receipt must not replace a newer pending recovery snapshot."""
import json
import os
from pathlib import Path
import sys
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "gui"))
from PySide6.QtWidgets import QApplication, QWidget
from g4usim_gui.core.edit_snapshot import WorkspaceSnapshot, project_for_snapshot
from g4usim_gui.core.project import G4USimProject, project_to_dict
from g4usim_gui.editors.material_editor_model import MaterialDocument
from g4usim_gui.window.recovery import RecoveryController


def payload(name):
    project = G4USimProject(projectName=name)
    project.materialEditor = MaterialDocument()
    return project_to_dict(project_for_snapshot(WorkspaceSnapshot(project)))


def main():
    app = QApplication.instance() or QApplication([])
    owner = QWidget()
    with tempfile.TemporaryDirectory(prefix="f5-recovery-stale-notice-") as folder:
        controller = RecoveryController(owner, restore=lambda value: True, root=folder)
        controller.changed(payload("newer edit revision 2"), 2)
        controller.changed(payload("late edit revision 1"), 1)
        assert controller.flush()
        actual = json.loads(controller.session.path.read_bytes())
        facts = {"latest_requested_revision": 2, "last_arriving_old_revision": 1,
                 "published_revision": actual["revision"], "published_project": actual["payload"]["projectName"],
                 "status": controller.status,
                 "scope": "public RecoveryController.changed API; synthetic delayed notification, no claim normal current UI emits it"}
        # Assert the observed issue so this script is repeatable at the reviewed revision.
        assert actual["revision"] == 1 and actual["payload"]["projectName"] == "late edit revision 1"
        assert controller.close(keep=True)
        app.processEvents()
    owner.close()
    (ROOT / "out/collab/f5-recovery-controller-review-repro.json").write_text(
        json.dumps(facts, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(facts, ensure_ascii=False))


if __name__ == "__main__":
    main()
