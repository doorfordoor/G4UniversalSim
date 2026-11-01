"""I2 installation UI; installation receipts and I1 readiness remain separate."""
from __future__ import annotations

import copy
import json
import platform
import threading
from pathlib import Path

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Qt, Signal, Slot
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QFileDialog, QFormLayout, QGridLayout, QHBoxLayout,
    QLabel, QLineEdit, QMessageBox, QPlainTextEdit, QPushButton, QVBoxLayout,
)

from g4usim_gui.core import environment_install as installation
from g4usim_gui.core.install_layout import application_root
from g4usim_gui.core.i18n import ui_format, ui_text


class _Signals(QObject):
    progress = Signal(object)
    completed = Signal(object)
    failed = Signal(str)


class _Task(QRunnable):
    def __init__(self, action):
        super().__init__()
        self.action = action
        self.signals = _Signals()

    def run(self):
        try:
            result = self.action(self.signals.progress.emit)
        except Exception as error:
            self.signals.failed.emit(str(error))
        else:
            self.signals.completed.emit(result)


class InstallDialog(QDialog):
    """No simulation owner; explicit planning, execution and read-only reprobe."""
    installation_published = Signal(str)

    def __init__(self, parent=None, *, facts=None, catalog=None):
        super().__init__(parent)
        self.setWindowTitle(ui_text("Install a Geant4 environment"))
        self.resize(840, 680)
        self.facts = copy.deepcopy(facts)
        self.catalog = None
        self.plan = None
        self.receipt = None
        self._recovery_plan = None
        self._recovery_target = None
        self.busy = False
        self._task = None
        self._close_pending = False
        self._cancel = threading.Event()
        self._platform = "windows" if platform.system() == "Windows" else "linux" if platform.system() == "Linux" else platform.system().lower()
        self._architecture = {"amd64": "x86_64", "arm64": "aarch64"}.get(platform.machine().lower(), platform.machine().lower())
        layout = QVBoxLayout(self)
        self.boundary = QLabel(ui_text(
            "Choose an installation plan and a new folder. Existing environments are not overwritten. Installation does not run a simulation."))
        self.boundary.setWordWrap(True)
        self.boundary.setProperty("i18nSource_labelText", "Choose an installation plan and a new folder. Existing environments are not overwritten. Installation does not run a simulation.")
        layout.addWidget(self.boundary)
        form = QFormLayout()
        self.profile = QComboBox()
        self.profile.addItem(ui_text("Run simulations (no compiler required)"), "runtime")
        self.profile.addItem(ui_text("Develop Geant4 projects (SDK)"), "sdk")
        form.addRow(ui_text("Purpose"), self.profile)
        self.version = QComboBox()
        form.addRow(ui_text("Release package version"), self.version)
        self.root = QLineEdit(str(Path.home()))
        self.root.setReadOnly(True)
        root_row = QHBoxLayout()
        root_row.addWidget(self.root, 1)
        self.browse_root = QPushButton(ui_text("Choose parent folder…"))
        self.browse_root.clicked.connect(self._choose_root)
        root_row.addWidget(self.browse_root)
        form.addRow(ui_text("Install inside"), root_row)
        self.folder = QLineEdit("G4UniversalSim-environment")
        form.addRow(ui_text("New folder name"), self.folder)
        for index, key in enumerate(("Purpose", "Release package version", "Install inside", "New folder name")):
            form.itemAt(index, QFormLayout.LabelRole).widget().setProperty("i18nSource_labelText", key)
        layout.addLayout(form)
        self.catalog_button = QPushButton(ui_text("Load an installation catalog…"))
        self.catalog_button.clicked.connect(self._choose_catalog)
        layout.addWidget(self.catalog_button)
        self.downloads = QCheckBox(ui_text("Allow downloading the files listed in this plan"))
        layout.addWidget(self.downloads)
        self.summary = QPlainTextEdit()
        self.summary.setReadOnly(True)
        self.summary.setAccessibleName(ui_text("Installation plan and progress"))
        layout.addWidget(self.summary, 1)
        self.status = QLabel(ui_text("Select a plan before installing."))
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        actions = QGridLayout()
        self.plan_button = QPushButton(ui_text("Check installation plan"))
        self.install_button = QPushButton(ui_text("Install this plan"))
        self.cancel_button = QPushButton(ui_text("Cancel installation"))
        self.export_button = QPushButton(ui_text("Save installation report…"))
        self.close_button = QPushButton(ui_text("Close"))
        self.resume_button = QPushButton(ui_text("Resume previous installation"))
        self.discard_button = QPushButton(ui_text("Discard previous temporary files…"))
        for index, button in enumerate((self.plan_button, self.install_button, self.cancel_button,
                                        self.resume_button, self.discard_button, self.export_button, self.close_button)):
            actions.addWidget(button, index // 3, index % 3)
        layout.addLayout(actions)
        for control, key in ((self.browse_root, "Choose parent folder…"),
                             (self.catalog_button, "Load an installation catalog…"),
                             (self.downloads, "Allow downloading the files listed in this plan"),
                             (self.plan_button, "Check installation plan"),
                             (self.install_button, "Install this plan"),
                             (self.cancel_button, "Cancel installation"),
                             (self.export_button, "Save installation report…"),
                             (self.close_button, "Close"),
                             (self.resume_button, "Resume previous installation"),
                             (self.discard_button, "Discard previous temporary files…")):
            control.setProperty("i18nSource_buttonText", key)
        self.plan_button.clicked.connect(self.prepare_plan)
        self.install_button.clicked.connect(self.install)
        self.cancel_button.clicked.connect(self._cancel.set)
        self.export_button.clicked.connect(self._export)
        self.close_button.clicked.connect(self.reject)
        self.resume_button.clicked.connect(self.resume_installation)
        self.discard_button.clicked.connect(self._discard)
        self.profile.currentIndexChanged.connect(self._versions)
        self.version.currentIndexChanged.connect(self._invalidate)
        self.folder.textChanged.connect(self._invalidate)
        self.root.textChanged.connect(self._invalidate)
        if catalog is not None:
            self.set_catalog(catalog)
        else:
            for candidate in (application_root() / "install" / "catalog.json",
                              application_root() / "packaging" / "manifests" / "catalog.json"):
                if candidate.is_file():
                    try:
                        self.set_catalog(installation.load_catalog(candidate))
                    except (OSError, ValueError) as error:
                        self.status.setText(ui_format("Installation plan could not be loaded: {error}", error=str(error)))
                    break
            else:
                self.status.setText(ui_text("No installation catalog is bundled here. Load a catalog supplied with a release package."))
        self._controls()

    def retranslate_ui(self):
        from g4usim_gui.core.i18n import apply_language, current_language
        apply_language(self, current_language())
        self.setWindowTitle(ui_text("Install a Geant4 environment"))
        self.profile.setItemText(0, ui_text("Run simulations (no compiler required)"))
        self.profile.setItemText(1, ui_text("Develop Geant4 projects (SDK)"))
        self.summary.setAccessibleName(ui_text("Installation plan and progress"))

    def set_catalog(self, catalog):
        if self.busy:
            return
        self.catalog = copy.deepcopy(catalog)
        self._versions()

    def _versions(self):
        self.version.blockSignals(True)
        self.version.clear()
        releases = (self.catalog or {}).get("releases", [])
        if isinstance(releases, list):
            versions = sorted({release["version"] for release in releases if isinstance(release, dict)
                               and isinstance(release.get("version"), str)
                               and release.get("profile") == self.profile.currentData()
                               and release.get("platform") == self._platform
                               and release.get("architecture") == self._architecture})
            self.version.addItems(versions)
        self.version.blockSignals(False)
        self._invalidate()

    def _invalidate(self, *_):
        self.plan = None
        if hasattr(self, "install_button"):
            self._controls()

    def _controls(self):
        for control in (self.profile, self.version, self.folder, self.browse_root, self.catalog_button, self.downloads):
            control.setEnabled(not self.busy)
        self.plan_button.setEnabled(not self.busy and self.catalog is not None and self.version.count() > 0)
        self.install_button.setEnabled(not self.busy and bool(self.plan and self.plan.get("executable")))
        self.cancel_button.setEnabled(self.busy)
        self.export_button.setEnabled(not self.busy and bool(self.receipt or self.plan))
        recoverable = bool(self._recovery_target and self.receipt)
        self.resume_button.setEnabled(not self.busy and recoverable and self._recovery_plan is not None)
        self.discard_button.setEnabled(not self.busy and recoverable)

    def _choose_root(self):
        path = QFileDialog.getExistingDirectory(self, ui_text("Choose parent folder…"), self.root.text())
        if path:
            self.root.setText(path)

    def _choose_catalog(self):
        path, _ = QFileDialog.getOpenFileName(self, ui_text("Load an installation catalog…"), "", "JSON (*.json)")
        if path:
            try:
                self.set_catalog(installation.load_catalog(path))
            except (OSError, ValueError) as error:
                self._invalidate()
                self.status.setText(ui_format("Installation plan could not be loaded: {error}", error=str(error)))

    def _start(self, action, completed):
        self.busy = True
        self._cancel.clear()
        self._controls()
        task = _Task(action)
        task.signals.progress.connect(self._progress, Qt.QueuedConnection)
        task.signals.completed.connect(completed, Qt.QueuedConnection)
        task.signals.failed.connect(self._failed, Qt.QueuedConnection)
        self._task = task
        QThreadPool.globalInstance().start(task)

    @Slot()
    def prepare_plan(self):
        if self.busy or self.catalog is None:
            return
        name = self.folder.text().strip()
        if not name or name in {".", ".."} or any(c in name for c in "/\\:"):
            self._invalidate()
            self.status.setText(ui_text("Enter a new folder name without a path."))
            return
        root = self.root.text()
        arguments = dict(profile=self.profile.currentData(), platform=self._platform,
                         architecture=self._architecture, version=self.version.currentText(),
                         prefix=str(Path(root) / name), allowed_root=root, facts=copy.deepcopy(self.facts))
        catalog = copy.deepcopy(self.catalog)
        self.receipt = None
        self._invalidate()
        self.status.setText(ui_text("Checking installation files, space and destination…"))
        def work(progress):
            plan = installation.create_plan(catalog, **arguments)
            if any(item.get("code") == "transaction_exists" for item in plan.get("diagnostics", [])):
                try:
                    plan["_recovery"] = installation.inspect_transaction(
                        arguments["prefix"], allowed_root=arguments["allowed_root"])
                except (OSError, ValueError) as error:
                    plan["diagnostics"].append({"code": "recovery_unavailable", "message": str(error)})
            return plan
        self._start(work, self._planned)

    @Slot(object)
    def _planned(self, plan):
        recovery = plan.pop("_recovery", None)
        self._recovery_plan = recovery.get("plan") if recovery else None
        self._recovery_target = ({"prefix": recovery["prefix"], "allowed_root": recovery["allowed_root"]}
                                 if recovery else None)
        self.receipt = recovery.get("receipt") if recovery else None
        self.plan = plan
        lines = [ui_format("Destination: {path}", path=plan.get("prefix", ""))]
        lines.append(ui_format("Release package version: {version}",
                               version=plan.get("release", {}).get("version", ui_text("Unknown"))))
        lines.append(ui_format("Geant4 version declared by this release: {version}",
                               version=plan.get("geant4_version") or ui_text("Unknown")))
        for dependency in plan.get("dependencies", []):
            if dependency.get("id") in ("compiler", "cmake"):
                name = "C++ compiler" if dependency["id"] == "compiler" else "CMake"
                lines.append(ui_format("Required development tool (checked separately): {tool}",
                                       tool=ui_text(name)))
        for artifact in plan.get("artifacts", []):
            lines.append(ui_format("Component: {name}", name=artifact.get("id", "")))
            source = artifact.get("source", {})
            lines.append(ui_format("Source: {location}", location=source.get("url") or source.get("path", "")))
            lines.append(ui_format("Download or copy size: {bytes} bytes", bytes=artifact.get("size_bytes", ui_text("Unknown"))))
            lines.append(ui_format("License: {license}", license=artifact.get("license", {}).get("expression", ui_text("Unknown"))))
        space = plan.get("space", {})
        lines.append(ui_format("Required staging space: {bytes} bytes", bytes=space.get("required_bytes") if space.get("required_bytes") is not None else ui_text("Unknown")))
        for diagnostic in plan.get("diagnostics", []):
            lines.append(str(diagnostic.get("message", "")))
        self.summary.setPlainText("\n".join(lines))
        self.status.setText(ui_text("Plan checked. Review the listed files before installing.") if plan.get("executable")
                            else ui_text("This plan cannot be installed. See the reasons above."))
        if recovery:
            self.status.setText(ui_text("An interrupted installation was found. Resume it or discard its temporary files."))
        self._finish()

    @Slot()
    def install(self):
        if self.busy or not self.plan or not self.plan.get("executable"):
            return
        plan = copy.deepcopy(self.plan)
        self._recovery_plan = copy.deepcopy(plan)
        self._recovery_target = {"prefix": plan["prefix"], "allowed_root": plan["allowed_root"]}
        downloads = self.downloads.isChecked()
        self.status.setText(ui_text("Installing into the selected new folder…"))
        self._start(lambda progress: installation.execute_plan(
            plan, allow_download=downloads, cancel=self._cancel.is_set, progress=progress), self._installed)

    @Slot()
    def resume_installation(self):
        if not self.resume_button.isEnabled():
            return
        plan = copy.deepcopy(self._recovery_plan)
        self.plan = plan
        downloads = self.downloads.isChecked()
        self.status.setText(ui_format("Resuming installation at {path}", path=plan["prefix"]))
        self._start(lambda progress: installation.execute_plan(
            plan, allow_download=downloads, cancel=self._cancel.is_set, progress=progress, resume=True), self._installed)

    def _discard(self):
        if not self.discard_button.isEnabled():
            return
        plan = copy.deepcopy(self._recovery_target)
        answer = QMessageBox.question(self, ui_text("Discard previous temporary files…"),
                                      ui_format("Remove the temporary files from the installation at {path}? Installed files and other environments will be kept.", path=plan["prefix"]))
        if answer != QMessageBox.Yes:
            return
        self._start(lambda progress: installation.recover_installation(
            plan["prefix"], allowed_root=plan["allowed_root"], action="discard"), self._recovered)

    @Slot(object)
    def _recovered(self, receipt):
        self.receipt = receipt
        self._recovery_plan = None
        self._recovery_target = None
        self.plan = None
        self._finish()
        self.status.setText(ui_text("Temporary installation files removed. Check a new plan to try again."))

    @Slot(object)
    def _progress(self, event):
        stages = {"acquire": "Obtain files", "extract": "Extract and verify files", "verify_payload": "Verify installed contents",
                  "publish": "Publish installation"}
        statuses = {"copied_verified": "Copied and verified", "downloaded_verified": "Downloaded and verified",
                    "verified_cache": "Verified cached copy", "verified": "Verified", "published": "Published"}
        self.summary.appendPlainText(ui_format("Installation step: {stage} — {status}",
                                              stage=ui_text(stages.get(event.get("stage"), event.get("stage", ""))),
                                              status=ui_text(statuses.get(event.get("status"), event.get("status", "")))))

    @Slot(object)
    def _installed(self, receipt):
        self.receipt = receipt
        plan = self.plan
        self.plan = None  # Published/failed destinations always need a fresh plan.
        self._finish()
        status = receipt.get("status", "failed")
        messages = {
            "published": "Files installed. Refresh environment discovery to check readiness.",
            "published_with_warning": "Files installed with a warning. See the report and refresh environment discovery.",
            "cancelled": "Installation cancelled. The report records any recoverable files.",
            "failed": "Installation failed. Existing environments were not replaced; see the report.",
        }
        self.status.setText(ui_text(messages.get(status, messages["failed"])))
        for diagnostic in receipt.get("diagnostics", []):
            self.summary.appendPlainText(str(diagnostic.get("message", "")))
        if status in {"published", "published_with_warning"} and plan:
            self._recovery_target = None
            self._controls()
            entrypoint = plan.get("release", {}).get("entrypoints", {}).get("backend")
            if entrypoint:
                self.installation_published.emit(str(Path(receipt["prefix"]) / entrypoint))

    def _finish(self):
        self.busy = False
        self._task = None
        self._controls()
        if self._close_pending:
            super().reject()

    @Slot(str)
    def _failed(self, error):
        self.plan = None
        self._finish()
        self.status.setText(ui_format("Installation operation failed: {error}", error=error))

    def _export(self):
        report = self.receipt or self.plan
        if not report or self.busy:
            return
        filename, _ = QFileDialog.getSaveFileName(self, ui_text("Save installation report…"), "installation-report.json", "JSON (*.json)")
        if filename:
            try:
                # Never overwrite evidence silently, including a hard-linked file.
                with Path(filename).open("x", encoding="utf-8", newline="\n") as stream:
                    json.dump({"schema": "g4usim_install_dialog_report_v1",
                               "plan": self.plan or self._recovery_plan,
                               "receipt": self.receipt}, stream, ensure_ascii=False, indent=2)
                    stream.write("\n")
            except (OSError, ValueError) as error:
                self.status.setText(ui_format("Installation report could not be saved: {error}", error=str(error)))

    def reject(self):
        if self.busy:
            self._close_pending = True
            self._cancel.set()
            self.status.setText(ui_text("Cancelling installation before closing…"))
            return
        super().reject()

    def closeEvent(self, event):
        if self.busy:
            self.reject()
            event.ignore()
        else:
            super().closeEvent(event)
