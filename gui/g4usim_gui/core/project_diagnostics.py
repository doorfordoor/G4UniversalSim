"""Project/runner validation records shared by GUI actions; no widgets created."""
from __future__ import annotations

from pathlib import Path

from g4usim_gui.core.diagnostics import emit_diagnostic, semantic_snapshot
from g4usim_gui.core.i18n import ui_format, ui_text
from g4usim_gui.core.project import G4USimProject, RUN_INPUT_MODES
from g4usim_gui.validators.config_validator import ValidationReport


def project_diagnostic_snapshot(project: G4USimProject) -> str:
    return semantic_snapshot({key: getattr(project, key) for key in (
        'projectName', 'runInputMode', 'executable', 'workspaceRoot', 'configPath',
        'macroPath', 'outputDir', 'runsRoot', 'threads', 'seed', 'runName')})


def validate_project_report(project: G4USimProject, *, ready_to_run: bool = False) -> ValidationReport:
    """Keep the runner's original rules, ordering and text, with producer locations."""
    report = ValidationReport()
    report.snapshot_id = project_diagnostic_snapshot(project)

    def error(code: str, field: str, message: str, *, key: str = '', **params) -> None:
        emit_diagnostic(report, 'project.' + code, 'error', message,
                        origin='project_validation', editor='project', field=field,
                        message_key=key or message, params=params)

    if project.runInputMode not in RUN_INPUT_MODES:
        error('input_mode', 'run_input_mode', ui_text('Unsupported run input mode.'),
              key='Unsupported run input mode.')
    if ready_to_run and project.runInputMode == 'generated' and (
            not project.configPath or not project.macroPath):
        error('package_required', 'run_input_mode',
              ui_text('Generate a run package before starting generated input.'),
              key='Generate a run package before starting generated input.')

    executable = Path(project.executable).expanduser() if project.executable else None
    if not project.executable:
        error('executable_required', 'executable', 'Executable path is required.')
    elif not executable or not executable.exists():
        error('executable_missing', 'executable', f'Executable does not exist: {project.executable}',
              key='Executable does not exist: {path}', path=project.executable)
    elif not executable.is_file():
        error('executable_not_file', 'executable', f'Executable path is not a file: {project.executable}',
              key='Executable path is not a file: {path}', path=project.executable)

    if project.runInputMode == 'external' and not project.configPath and not project.macroPath:
        error('external_input_required', 'config_path',
              'External input mode requires a config file, a macro file, or both.')
    if project.macroPath and not Path(project.macroPath).expanduser().exists():
        error('macro_missing', 'macro_path', f'Macro file does not exist: {project.macroPath}',
              key='Macro file does not exist: {path}', path=project.macroPath)
    elif project.macroPath and not Path(project.macroPath).expanduser().is_file():
        error('macro_not_file', 'macro_path', ui_format('Macro path is not a file: {path}', path=project.macroPath),
              key='Macro path is not a file: {path}', path=project.macroPath)
    if project.configPath and not Path(project.configPath).expanduser().exists():
        error('config_missing', 'config_path', f'Config file does not exist: {project.configPath}',
              key='Config file does not exist: {path}', path=project.configPath)
    elif project.configPath and not Path(project.configPath).expanduser().is_file():
        error('config_not_file', 'config_path', ui_format('Config path is not a file: {path}', path=project.configPath),
              key='Config path is not a file: {path}', path=project.configPath)
    if project.workspaceRoot and not Path(project.workspaceRoot).expanduser().is_dir():
        error('workspace_missing', 'workspace_root', f'Workspace root does not exist: {project.workspaceRoot}',
              key='Workspace root does not exist: {path}', path=project.workspaceRoot)
    if not project.outputDir:
        error('output_required', 'output_dir', 'Output directory is required.')
    else:
        output_dir = Path(project.outputDir).expanduser()
        if output_dir.exists() and not output_dir.is_dir():
            error('output_not_directory', 'output_dir', f'Output path exists but is not a directory: {project.outputDir}',
                  key='Output path exists but is not a directory: {path}', path=project.outputDir)
        else:
            existing_parent = output_dir
            while not existing_parent.exists() and existing_parent.parent != existing_parent:
                existing_parent = existing_parent.parent
            if not existing_parent.exists():
                error('output_parent_missing', 'output_dir', f'Output directory has no existing parent: {project.outputDir}',
                      key='Output directory has no existing parent: {path}', path=project.outputDir)
    if project.threads <= 0:
        error('threads', 'threads', 'Threads must be a positive integer.')
    if project.seed:
        try:
            int(project.seed)
        except ValueError:
            error('seed', 'seed', 'Seed must be an integer when provided.')
    return report
