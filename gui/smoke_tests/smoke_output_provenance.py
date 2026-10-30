"""R27: GUI sources, stale inputs, errors and merge plan use the common manifest."""
from async_wait import wait_for_idle
from pathlib import Path
import json
import os
import shutil
import sys
import tempfile
os.environ.setdefault("QT_QPA_PLATFORM","offscreen")
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"scripts"))
sys.path.insert(0,str(ROOT/"gui"))
from test_output_provenance import fixture
from PySide6.QtWidgets import QApplication
from g4usim_gui.widgets.output_page import OutputPage
from g4usim_gui.output import plot_data
from g4usim_gui.output.merge_runner import MergeRunner
from g4usim_gui.output.merge_plan import build_merge_plan
from PySide6.QtCore import QProcess


class StartProbe:
    """Observe the real runner startup guard without launching any executable."""
    def __init__(self):
        self.starts = 0
    def state(self): return QProcess.NotRunning
    def setProgram(self, value): self.program = value
    def setArguments(self, value): self.arguments = value
    def start(self): self.starts += 1


def startup_guards(work):
    for mode in ("unchanged", "deleted", "changed_run", "legacy", "explicit"):
        root = work / mode
        doc = fixture(root)
        if mode == "legacy":
            (root / "run_metadata.json").unlink()
        task = next(t for t in build_merge_plan(str(root), str(ROOT)).tasks if t.kind == "event_edep")
        if mode == "legacy":
            assert task.provenance_status == "legacy_unverified" and task.manifest_digest is None
            assert "Legacy/unverified" in task.reason
        else:
            assert task.provenance_status == "registered_manifest" and task.manifest_digest
        if mode == "explicit":
            task.automatic_inputs = False
            (root / "run_metadata.json").unlink()
        if mode == "deleted":
            (root / "run_metadata.json").unlink()
        elif mode == "changed_run":
            # A still-valid manifest and unchanged selected filenames, new run identity.
            doc["runs"].append({"run_id": 1, "completed_events": 0})
            (root / "run_metadata.json").write_text(json.dumps(doc))
        runner = MergeRunner()
        runner._process = probe = StartProbe()
        errors = []; finished = []; started = []
        runner.errorOccurred.connect(errors.append)
        runner.allFinished.connect(lambda: finished.append(True))
        runner.taskStarted.connect(started.append)
        runner.run_task(task, work / "guard_logs")
        if mode in ("unchanged", "legacy", "explicit"):
            assert probe.starts == 1 and started and not errors
        else:
            assert probe.starts == 0 and not started and finished
            assert errors and "provenance changed" in errors[0] and "refresh" in errors[0]
        runner._close_logs()


def main():
    app=QApplication.instance() or QApplication([])
    with tempfile.TemporaryDirectory(prefix="q1-gui-provenance-") as temp:
        startup_guards(Path(temp))
        root=Path(temp)/"results";fixture(root)
        shutil.copyfile(root/"event_edep_t0.csv",root/"event_edep_t9.csv")
        page=OutputPage();page.set_workspace_root(str(ROOT));page.set_output_dir(str(root))
        wait_for_idle(page)
        assert len(page.plot_panel.datasets())==1
        pulse=page.plot_panel.datasets()[0]
        assert any(a.get("events")==1 for _,a in plot_data.build_plot(root,pulse).notes)
        task=next(t for t in page._merge_plan.tasks if t.kind=="event_edep")
        assert len(task.matched_files)==1
        (root/"event_edep_t0.csv").unlink()
        runner=MergeRunner();errors=[];runner.errorOccurred.connect(errors.append)
        runner.run_task(task,Path(temp)/"logs")
        assert errors and "registered file is missing" in errors[0] and not runner.is_running()
        page.refresh()
        wait_for_idle(page)
        assert not page.plot_panel.datasets()
        assert "registered file is missing" in page.plot_panel.message.text()
        assert not any(t.available for t in page._merge_plan.tasks)
        (root/"run_metadata.json").write_text("broken")
        page.refresh()
        wait_for_idle(page)
        assert "Invalid output provenance" in page.plot_panel.message.text()
        page.close()
    print("smoke_output_provenance: OK")


if __name__=="__main__":main()
