from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PathSettings:
    executable: str = ""
    workspace_root: str = ""
    runs_root: str = ""
    materials_config: str = ""
    geometry_config: str = ""


@dataclass
class GeometrySettings:
    template: str = "simple_box"
    config_path: str = ""


@dataclass
class RunPackage:
    package_dir: str
    config_dir: str
    macro_dir: str
    logs_dir: str
    output_dir: str
    main_ini_path: str
    run_macro_path: str
    validation_report_path: str
    project_snapshot_path: str
    materials_ini_path: str
    geometry_ini_path: str
