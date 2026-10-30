"""Kill an actual edited MainWindow process, then restore in a fresh process.

This exercises real Qt/transaction/recovery code with offscreen widgets. It is
not a native visible-window observation and is not a physical simulation test.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import queue
import subprocess
import sys
import tempfile
import threading

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "gui"))


def child(mode, work):
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication, QMessageBox
    from g4usim_gui.core.diagnostics import collect_diagnostics
    from g4usim_gui.core.i18n import set_application_language
    from g4usim_gui.history import run_history_store
    from g4usim_gui.main_window import MainWindow

    app = QApplication.instance() or QApplication([])
    app.setQuitOnLastWindowClosed(False)
    set_application_language(app, "en")
    run_history_store.STATE_PATH = work / f"{mode}-state.json"
    window = MainWindow(recovery_root=work / "recovery", offer_recovery=False)
    page = window.config_builder_page
    page.preview3d_auto_backend.setChecked(False)
    source = work / "materials.ini"
    if mode == "writer":
        page.materials_config.setText(str(source))
        page.reload_materials()
        page._add_material("mass_fraction")
        page.material_name.selectAll()
        QTest.keyClicks(page.material_name, "RecoveredMix")
        page.material_components.selectAll()
        page.material_components.insertPlainText("G4_Si: 0.5\nG4_O: 0.5")
        page.material_enabled.setChecked(False)
        page.seed.selectAll()
        QTest.keyClicks(page.seed, "bad-seed")
        page.source_editor_energy.selectAll()
        QTest.keyClicks(page.source_editor_energy, "bad-energy")
        app.processEvents()
        window.flush_pending_edit()
        assert window._edit_session.is_modified and window.project_file is None
        assert window._recovery.flush(), window._recovery.status
        receipt = window._recovery.last_receipt
        expected = dict(material_name=page.material_document.rows[-1].name,
                        material_components=page.material_document.rows[-1].components_text,
                        material_enabled=page.material_document.rows[-1].enabled,
                        source_text=page.material_document.raw_source_text,
                        seed=page.seed.text(), energy=page.source_editor_energy.text(),
                        source_path=str(source), recovery_path=str(receipt.path),
                        raw_sha256=receipt.raw_sha256)
        (work / "expected.json").write_text(json.dumps(expected, ensure_ascii=False), encoding="utf-8")
        print(json.dumps({"ready": True, "pid": os.getpid(), "revision": receipt.revision,
                          "raw_sha256": receipt.raw_sha256}), flush=True)
        sys.stdin.readline()  # Parent kills us. No closeEvent or recovery cleanup runs.
        assert False, "Crash writer was expected to be killed"
    else:
        expected = json.loads((work / "expected.json").read_text(encoding="utf-8"))
        candidates = window._recovery.store.discover()
        assert len(candidates) == 1
        assert candidates[0].raw_sha256 == expected["raw_sha256"]
        assert window._recovery.restore_candidate(candidates[0]), window._recovery.status
        assert window.project_file is None and window._edit_session.is_modified
        assert not window._edit_session.can_undo and not window._edit_session.can_redo
        assert page.material_document.rows[-1].name == expected["material_name"]
        assert page.material_document.rows[-1].components_text == expected["material_components"]
        assert page.material_document.rows[-1].enabled is expected["material_enabled"]
        assert page.material_document.raw_source_text == expected["source_text"]
        assert page.seed.text() == expected["seed"] == "bad-seed"
        assert page.source_editor_energy.text() == expected["energy"] == "bad-energy"
        assert page.material_document.raw_source_text != source.read_text(encoding="utf-8")
        assert window._generated_package_stale and not window._generated_package_dir
        assert not window.runner.is_running()
        report = page.validate_current(window.project)
        codes = [item.code for item in collect_diagnostics(report)]
        assert "config.source.materials.changed" in codes, codes
        assert not Path(expected["recovery_path"]).exists(), "Predecessor not retired after successor publication"
        window._choose_unsaved_action = lambda: QMessageBox.Discard
        assert window.close()
        app.processEvents()
        assert window._recovery._closed
        assert not window._recovery.store.discover()
        print(json.dumps({"restored": True, "pid": os.getpid(), "seed": expected["seed"],
                          "source_conflict": True, "normal_close": True}), flush=True)


def start(mode, work):
    executable = getattr(sys, "_base_executable", sys.executable) if os.name == "nt" else sys.executable
    env = os.environ.copy()
    # The directly owned Windows base interpreter needs the selected venv's
    # dependencies, without introducing a venv redirector process to kill.
    env["PYTHONPATH"] = os.pathsep.join(str(Path(item).absolute()) for item in sys.path if item)
    process = subprocess.Popen([executable, str(Path(__file__).resolve()), "--child", mode, str(work)],
                               env=env, cwd=ROOT, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, encoding="utf-8", text=True)
    return process


def receipt(process):
    responses = queue.Queue()
    def read():
        for line in process.stdout:
            try:
                item = json.loads(line)
            except (ValueError, TypeError):
                continue
            if isinstance(item, dict) and "pid" in item:
                responses.put(item)
                return
        responses.put(None)
    threading.Thread(target=read, daemon=True).start()
    try:
        result = responses.get(timeout=45)
    except queue.Empty:
        process.kill(); process.wait(timeout=10)
        assert False, "MainWindow child did not reach its recovery receipt"
    assert result is not None, f"MainWindow child failed: {process.poll()}: {process.stderr.read()}"
    assert result["pid"] == process.pid, "Receipt came from a process other than the owned interpreter"
    return result


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--child":
        child(sys.argv[2], Path(sys.argv[3])); return
    with tempfile.TemporaryDirectory(prefix="f5-real-window-crash-") as temporary:
        work = Path(temporary)
        source = work / "materials.ini"
        source.write_text("[NIST]\nmaterials = G4_AIR, G4_Si\n", encoding="utf-8")
        original = source.read_bytes()
        original_project = work / "untouched-project.json"
        original_project.write_bytes(b"original project bytes\r\n")
        original_project_sha = hashlib.sha256(original_project.read_bytes()).hexdigest()
        writer = start("writer", work)
        reader = None
        try:
            written = receipt(writer)
            assert written["ready"]
            writer.kill()
            writer_code = writer.wait(timeout=10)
            assert writer_code != 0
            assert source.read_bytes() == original
            assert hashlib.sha256(original_project.read_bytes()).hexdigest() == original_project_sha
            source.write_text("[NIST]\nmaterials = G4_AIR, G4_Si, G4_WATER\n", encoding="utf-8")
            changed = source.read_bytes()
            reader = start("reader", work)
            restored = receipt(reader)
            reader_code = reader.wait(timeout=15)
            assert reader_code == 0, reader.stderr.read()
            assert restored["restored"] and restored["normal_close"] and restored["source_conflict"]
            assert source.read_bytes() == changed
            assert hashlib.sha256(original_project.read_bytes()).hexdigest() == original_project_sha
            print(json.dumps({"actual_mainwindow_crash_exit": writer_code,
                              "normal_recovery_process_exit": reader_code,
                              "published_recovery_sha256": written["raw_sha256"],
                              "source_conflict_preserved": True, "raw_drafts_restored": True}))
        finally:
            for process in (writer, reader):
                if process is None:
                    continue
                if process.poll() is None:
                    process.kill(); process.wait(timeout=10)
                for stream in (process.stdin, process.stdout, process.stderr):
                    stream.close()
    print("F5 actual MainWindow abnormal-exit recovery: passed")


if __name__ == "__main__":
    main()
