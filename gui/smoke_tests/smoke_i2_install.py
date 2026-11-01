"""I2 dialog uses real owned files; installation is not simulation readiness."""
from pathlib import Path
import copy
import os
import sys
import tempfile
import time
import threading
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "gui"), str(ROOT / "scripts")]
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtCore import QThreadPool
from PySide6.QtWidgets import QApplication
from g4usim_gui.core.environment_install import verify_installation
from g4usim_gui.core import environment_install as service
from g4usim_gui.core import environment_discovery as discovery
from g4usim_gui.core.i18n import set_application_language
from g4usim_gui.widgets.install_dialog import InstallDialog
from g4usim_gui.widgets.environment_dialog import EnvironmentDialog
from test_install_plan import fixture


def wait(app, predicate, timeout=12):
    deadline = time.monotonic() + timeout
    while not predicate() and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(.01)
    assert predicate(), "GUI action did not reach a terminal state"


def main():
    app = QApplication.instance() or QApplication([])
    app.setOrganizationName("G4UniversalSim-I2-Test")
    app.setApplicationName("I2 installation test")
    set_application_language(app, "zh_CN")
    with tempfile.TemporaryDirectory(prefix="g4-i2-gui-") as directory:
        root = Path(directory)
        catalog = fixture(root)
        catalog["releases"][0]["geant4_version"] = "11.4.3"
        facts = {"example": {"status": "not_probed"}}
        original = copy.deepcopy(facts)
        window = InstallDialog(catalog=catalog, facts=facts)
        window.root.setText(str(root))
        window.folder.setText("installed")
        publications = []
        window.installation_published.connect(publications.append)
        assert window.profile.currentData() == "runtime"
        assert window.version.currentText() == "1.2.3"
        assert not window.install_button.isEnabled()
        before = sorted(str(p.relative_to(root)) for p in root.rglob("*"))
        window.prepare_plan()
        wait(app, lambda: not window.busy)
        assert window.plan["executable"]
        assert str(root / "runtime.zip") in window.summary.toPlainText()
        assert "发布包版本：1.2.3" in window.summary.toPlainText()
        assert "Geant4 版本：11.4.3" in window.summary.toPlainText()
        assert "方案检查通过" in window.status.text()
        assert before == sorted(str(p.relative_to(root)) for p in root.rglob("*"))
        assert window.install_button.isEnabled()
        window.folder.setText("changed")
        assert window.plan is None and not window.install_button.isEnabled()
        window.folder.setText("installed")
        window.prepare_plan()
        wait(app, lambda: not window.busy)
        window.install()
        wait(app, lambda: not window.busy)
        assert window.receipt["status"] == "published", window.receipt
        assert window.receipt["capability_status"] == "not_probed"
        assert verify_installation(root / "installed")["status"] == "verified"
        assert publications == [str(root / "installed/bin/backend")]
        assert facts == original
        assert window.plan is None and not window.install_button.isEnabled()
        window.prepare_plan()
        wait(app, lambda: not window.busy)
        assert window.plan["executable"] is False
        assert window.plan["diagnostics"][0]["code"] == "prefix_occupied"
        assert len(publications) == 1
        window.folder.setText("resume-install")
        window.prepare_plan()
        wait(app, lambda: not window.busy)
        acquire = service._acquire
        def cancel_after_archive(*args, **kwargs):
            result = acquire(*args, **kwargs)
            window._cancel.set()
            return result
        with patch.object(service, "_acquire", side_effect=cancel_after_archive):
            window.install()
            wait(app, lambda: not window.busy)
        assert window.receipt["status"] == "cancelled", window.receipt
        assert window.resume_button.isEnabled() and window.discard_button.isEnabled()
        assert not (root / "resume-install").exists()
        window.prepare_plan()
        wait(app, lambda: not window.busy)
        assert window.resume_button.isEnabled() and window.discard_button.isEnabled()
        reopened = InstallDialog(catalog=catalog)
        reopened.root.setText(str(root))
        reopened.folder.setText("resume-install")
        reopened.prepare_plan()
        wait(app, lambda: not reopened.busy)
        assert reopened.resume_button.isEnabled() and reopened.discard_button.isEnabled()
        assert reopened._recovery_plan["plan_sha256"] == window._recovery_plan["plan_sha256"]
        reopened.close()
        window.resume_installation()
        wait(app, lambda: not window.busy)
        assert window.receipt["status"] == "published", window.receipt
        assert not window.resume_button.isEnabled()
        assert verify_installation(root / "resume-install")["status"] == "verified"
        assert publications == [str(root / "installed/bin/backend"), str(root / "resume-install/bin/backend")]
        window.folder.setText("../outside")
        window.prepare_plan()
        assert not window.busy and window.plan is None
        window.profile.setCurrentIndex(1)
        assert window.version.count() == 0 and not window.plan_button.isEnabled()
        window.close()
        # Publication causes a fresh discovery request but no auto-selection.
        environment = EnvironmentDialog(candidates=[], auto_discover=False)
        selected = []
        environment.environment_selected.connect(selected.append)
        with patch.object(environment, "refresh") as refresh:
            environment._installed_candidate(str(root / "installed/bin/backend"))
            assert refresh.call_count == 1
            assert environment._candidates == [str(root / "installed/bin/backend")]
        assert selected == []
        assert environment.install_button.text() == "安装运行环境…"
        environment._busy = True
        with patch.object(environment, "refresh") as refresh:
            environment._installed_candidate(str(root / "resume-install/bin/backend"))
            assert refresh.call_count == 0 and environment._rediscovery_pending
            assert len(environment._candidates) == 2
            environment._completed(environment._generation, {"environments": []})
            assert refresh.call_count == 1 and not environment._rediscovery_pending
        environment._busy = True
        with patch.object(environment, "refresh") as refresh:
            environment._installed_candidate(str(root / "third/bin/backend"))
            environment._failed(environment._generation, "old discovery failure")
            assert refresh.call_count == 1 and len(environment._candidates) == 3
        assert selected == []
        environment.close()
        # Installing while automatic discovery is active must not discard the
        # prior automatic candidates. Exercise real worker completion ordering.
        started, release = threading.Event(), threading.Event()
        original_discover = discovery.discover_environments
        observations = []
        old_backend = str(root / "installed/bin/backend")
        new_backend = str(root / "resume-install/bin/backend")
        def discover_with_delay(candidates, **options):
            if not observations:
                started.set()
                assert release.wait(5), "first discovery was not released"
            facts = original_discover(candidates, **options)
            observations.append(facts)
            return facts
        with patch("g4usim_gui.widgets.environment_dialog.discover_environments", side_effect=discover_with_delay), \
                patch.object(discovery, "probe_environment", side_effect=lambda path, **kw: {"executable": str(path), "status": "not_probed"}), \
                patch.object(discovery, "_host_facts", return_value={}), \
                patch.object(discovery, "_sdk_facts", return_value={}):
            automatic = EnvironmentDialog(auto_discover=False, env={"G4USIM_EXE": old_backend, "PATH": ""})
            automatic.refresh()
            wait(app, started.is_set)
            automatic._installed_candidate(new_backend)
            assert automatic._candidates is None and automatic._rediscovery_pending
            release.set()
            wait(app, lambda: len(observations) == 2 and not automatic.busy)
            assert {item["executable"] for item in automatic.facts["environments"]} == {old_backend, new_backend}
            assert automatic._additional_candidates == [new_backend]
            automatic.close()
        # Closing an active task requests cancellation, then closes after it ends.
        cancelled = InstallDialog(catalog=catalog)
        cancelled.show()
        def action(progress):
            deadline = time.monotonic() + 5
            while not cancelled._cancel.is_set() and time.monotonic() < deadline:
                time.sleep(.01)
            return {"status": "cancelled", "diagnostics": []}
        cancelled._start(action, cancelled._installed)
        cancelled.reject()
        assert cancelled._cancel.is_set() and cancelled.busy
        wait(app, lambda: not cancelled.busy)
        assert cancelled.receipt["status"] == "cancelled" and not cancelled.isVisible()
        QThreadPool.globalInstance().waitForDone(10000)
        app.processEvents()
    print("I2 install GUI: planned, installed, reprobed, rejected and cancelled paths passed")


if __name__ == "__main__":
    previous_hook = sys.excepthook
    uncaught = []
    sys.excepthook = lambda kind, value, trace: uncaught.append((kind.__name__, str(value)))
    try:
        main()
        assert not uncaught, uncaught
    finally:
        sys.excepthook = previous_hook
