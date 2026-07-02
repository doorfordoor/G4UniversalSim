from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSplitter,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from g4usim_gui.core.project import G4USimProject
from g4usim_gui.widgets.ui_helpers import create_hint_label, make_path_row


class ProjectPage(QWidget):
    projectChanged = Signal()
    saveProjectRequested = Signal()
    loadProjectRequested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._building = False

        self.project_name = QLineEdit()
        self.executable = QLineEdit()
        self.workspace_root = QLineEdit()
        self.config_path = QLineEdit()
        self.macro_path = QLineEdit()
        self.output_dir = QLineEdit()
        self.runs_root = QLineEdit()
        self.threads = QSpinBox()
        self.threads.setRange(1, 1024)
        self.seed = QLineEdit()
        self.run_name = QLineEdit()

        self.save_button = QPushButton("Save project")
        self.load_button = QPushButton("Load project")
        self.save_button.clicked.connect(self.saveProjectRequested.emit)
        self.load_button.clicked.connect(self.loadProjectRequested.emit)
        buttons = QHBoxLayout()
        buttons.addWidget(self.save_button)
        buttons.addWidget(self.load_button)
        buttons.addStretch(1)

        self.status_summary = QLabel()
        self.status_summary.setWordWrap(True)
        self.status_summary.setMinimumHeight(120)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)
        layout.addWidget(create_hint_label(
            "Step 1: choose executable. Step 2: choose config/macro here or generate a run package in Config Builder. "
            "Project JSON stores GUI state only; simulation inputs remain config and macro files."
        ))

        setup_group = QGroupBox("Project Setup")
        setup_form = QFormLayout(setup_group)
        setup_form.addRow("Project name", self.project_name)
        setup_form.addRow("G4UniversalSim executable", make_path_row(self.executable, "Browse", self._browse_executable))
        setup_form.addRow("Workspace root", make_path_row(self.workspace_root, "Browse", self._browse_workspace))
        setup_form.addRow("Runs root", make_path_row(self.runs_root, "Browse", self._browse_runs_root))
        setup_form.addRow("", QWidget())
        setup_form.addRow(buttons)

        run_group = QGroupBox("Current Run Defaults")
        run_form = QFormLayout(run_group)
        run_form.addRow("Config file", make_path_row(self.config_path, "Browse", self._browse_config))
        run_form.addRow("Macro file", make_path_row(self.macro_path, "Browse", self._browse_macro))
        run_form.addRow("Output directory", make_path_row(self.output_dir, "Browse", self._browse_output))
        run_form.addRow("Threads", self.threads)
        run_form.addRow("Seed", self.seed)
        run_form.addRow("Run name", self.run_name)
        run_form.addRow("Status", self.status_summary)

        splitter = QSplitter()
        splitter.addWidget(setup_group)
        splitter.addWidget(run_group)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([560, 760])
        layout.addWidget(splitter, 1)

        for widget in [
            self.project_name,
            self.executable,
            self.workspace_root,
            self.config_path,
            self.macro_path,
            self.output_dir,
            self.runs_root,
            self.seed,
            self.run_name,
        ]:
            widget.textChanged.connect(self._emit_changed)
        self.threads.valueChanged.connect(self._emit_changed)

    def set_project(self, project: G4USimProject) -> None:
        self._building = True
        self.project_name.setText(project.projectName)
        self.executable.setText(project.executable)
        self.workspace_root.setText(project.workspaceRoot)
        self.config_path.setText(project.configPath)
        self.macro_path.setText(project.macroPath)
        self.output_dir.setText(project.outputDir)
        self.runs_root.setText(project.runsRoot)
        self.threads.setValue(max(1, int(project.threads)))
        self.seed.setText(str(project.seed) if project.seed else "")
        self.run_name.setText(project.runName)
        self._building = False
        self._update_status_summary()

    def to_project(self) -> G4USimProject:
        return G4USimProject(
            projectName=self.project_name.text().strip() or "demo",
            executable=self.executable.text().strip(),
            workspaceRoot=self.workspace_root.text().strip(),
            configPath=self.config_path.text().strip(),
            macroPath=self.macro_path.text().strip(),
            outputDir=self.output_dir.text().strip(),
            runsRoot=self.runs_root.text().strip(),
            threads=self.threads.value(),
            seed=self.seed.text().strip(),
            runName=self.run_name.text().strip(),
        )

    def set_inputs_enabled(self, enabled: bool) -> None:
        for widget in [
            self.project_name,
            self.executable,
            self.workspace_root,
            self.config_path,
            self.macro_path,
            self.output_dir,
            self.runs_root,
            self.threads,
            self.seed,
            self.run_name,
            self.save_button,
            self.load_button,
        ]:
            widget.setEnabled(enabled)

    def _with_browse(self, line_edit: QLineEdit, callback) -> QWidget:
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        button = QPushButton("Browse")
        button.clicked.connect(callback)
        layout.addWidget(line_edit, 1)
        layout.addWidget(button)
        return container

    def _browse_executable(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Select G4UniversalSim executable")
        if path:
            self.executable.setText(path)
            if not self.workspace_root.text().strip():
                self.workspace_root.setText(str(Path(path).resolve().parents[2]) if len(Path(path).resolve().parents) > 2 else str(Path(path).resolve().parent))

    def _browse_workspace(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Select workspace root")
        if path:
            self.workspace_root.setText(path)

    def _browse_config(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Select main config", filter="INI files (*.ini);;All files (*)")
        if path:
            self.config_path.setText(path)

    def _browse_macro(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Select macro", filter="Macro files (*.mac);;All files (*)")
        if path:
            self.macro_path.setText(path)

    def _browse_output(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Select output directory")
        if path:
            self.output_dir.setText(path)

    def _browse_runs_root(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Select runs root")
        if path:
            self.runs_root.setText(path)

    def _emit_changed(self) -> None:
        if not self._building:
            self._update_status_summary()
            self.projectChanged.emit()

    def _update_status_summary(self) -> None:
        def status_for_file(value: str, *, required: bool) -> str:
            text = value.strip()
            if not text:
                return "missing" if required else "not set"
            return "ok" if Path(text).expanduser().exists() else "missing"

        output_text = self.output_dir.text().strip()
        if not output_text:
            output_status = "missing"
        else:
            output = Path(output_text).expanduser()
            output_status = "ok" if output.exists() and output.is_dir() else "creatable" if output.parent.exists() else "missing parent"
        lines = [
            f"Executable: {status_for_file(self.executable.text(), required=True)}",
            f"Config: {status_for_file(self.config_path.text(), required=False)}",
            f"Macro: {status_for_file(self.macro_path.text(), required=True)}",
            f"Output: {output_status}",
            f"Workspace: {'ok' if self.workspace_root.text().strip() and Path(self.workspace_root.text().strip()).expanduser().is_dir() else 'not set/missing'}",
        ]
        self.status_summary.setText("\n".join(lines))
