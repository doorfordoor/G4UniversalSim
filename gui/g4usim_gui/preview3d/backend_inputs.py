"""What the backend needs to build the Geant4 world for the 3D view (roadmap G1), without Qt.

"Show Backend Geometry" no longer needs a generated run package. The inputs follow the
package writer's choice of files, but nothing is copied, so files a geometry refers to
(STL, GDML) keep resolving next to it:
  geometry   edited in the Geometry Editor -> the editor's generated text (it must pass
             the editor's validation, as for a package); otherwise the source file as
             is, also when the editor cannot write it (the backend decides)
  materials  edited -> the generated text; otherwise the source file
  external   the project's own main INI
A key hashes everything that decides the world (template, file contents, files the
geometry refers to, the backend executable), so an unchanged world is shown from the
cache instead of running Geant4 again.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

from g4usim_gui.editors.geometry_editor_model import EDITABLE_GEOMETRY_MODES, GeometryDocument
from g4usim_gui.editors.material_editor_model import MaterialDocument, generate_materials_ini_text
from g4usim_gui.writers.geometry_ini_writer import generate_geometry_ini_text

FILE_KEY = re.compile(r"^\s*file\s*=\s*(.+?)\s*$", re.IGNORECASE | re.MULTILINE)


@dataclass(frozen=True)
class GeometryInputs:
    key: str
    template: str = ""
    geometry_path: str = ""     # source geometry file, used when geometry_text is None
    materials_path: str = ""
    geometry_text: str | None = None    # editor-generated, written next to the export
    materials_text: str | None = None
    main_ini: str = ""          # external mode: the project's main INI, used as is

    @property
    def edited(self) -> bool:
        return self.geometry_text is not None or self.materials_text is not None


def _digest(*parts: object) -> str:
    sha = hashlib.sha256()
    for part in parts:
        sha.update(str(part).encode("utf-8", errors="replace"))
        sha.update(b"\0")
    return sha.hexdigest()[:20]


def _file_state(path: str | Path) -> str:
    path = Path(path)
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return f"missing:{path}"


def _executable_state(executable: str) -> str:
    try:
        stat = Path(executable).stat()
        return f"{Path(executable).resolve()}:{stat.st_size}:{stat.st_mtime_ns}"
    except OSError:
        return f"missing:{executable}"


def _referenced_files(text: str, base: Path) -> list[str]:
    """States of the files a geometry refers to with file = ... (STL, GDML), relative to it."""
    states = []
    for value in FILE_KEY.findall(text):
        target = Path(value.strip().strip('"'))
        states.append(_file_state(target if target.is_absolute() else base / target))
    return states


def generated_inputs(*, template: str, geometry_config: str, geometry: GeometryDocument,
                     materials_config: str, materials: MaterialDocument, executable: str) -> GeometryInputs:
    """Inputs for generated mode; raises ValueError (with the editor's messages) when they cannot be built."""
    geometry_text = None
    if geometry.is_dirty and geometry.mode in EDITABLE_GEOMETRY_MODES and not geometry.source_copy_mode:
        blocking = [e for e in geometry.errors]
        if blocking:
            raise ValueError("\n".join(["The edited geometry has errors; fix them to see the Geant4 geometry:",
                                        *blocking[:8]]))
        geometry_text = generate_geometry_ini_text(geometry)
    elif not geometry_config or not Path(geometry_config).is_file():
        raise ValueError(f"Geometry file not found: {geometry_config or '<none>'}")
    materials_text = None
    if materials.is_dirty:
        if materials.errors:
            raise ValueError("\n".join(["The edited materials have errors; fix them to see the Geant4 geometry:",
                                        *materials.errors[:8]]))
        materials_text = generate_materials_ini_text(materials)
    elif not materials_config or not Path(materials_config).is_file():
        raise ValueError(f"Materials file not found: {materials_config or '<none>'}")

    geometry_state = geometry_text if geometry_text is not None else _file_state(geometry_config)
    base = Path(geometry_config).parent if geometry_config else Path.cwd()
    references = _referenced_files(geometry_text if geometry_text is not None
                                   else Path(geometry_config).read_text(encoding="utf-8", errors="replace"), base)
    key = _digest("generated", template, geometry_state, *references,
                  materials_text if materials_text is not None else _file_state(materials_config),
                  _executable_state(executable))
    return GeometryInputs(key=key, template=template, geometry_path=str(geometry_config),
                          materials_path=str(materials_config), geometry_text=geometry_text,
                          materials_text=materials_text)


def external_inputs(main_ini: str, executable: str) -> GeometryInputs:
    if not main_ini or not Path(main_ini).is_file():
        raise ValueError("Backend geometry in external mode needs a main INI: choose one on the Project page.")
    text = Path(main_ini).read_text(encoding="utf-8", errors="replace")
    base = Path(main_ini).parent
    referenced = [_file_state(p if Path(p).is_absolute() else base / p)
                  for p in re.findall(r"^\s*(?:file|config)\s*=\s*(.+?)\s*$", text, re.IGNORECASE | re.MULTILINE)]
    return GeometryInputs(key=_digest("external", text, *referenced, _executable_state(executable)),
                          main_ini=str(main_ini))


def write_main_ini(inputs: GeometryInputs, directory: str | Path) -> Path:
    """The main INI of the export run (generated mode): only what builds the world."""
    if inputs.main_ini:
        return Path(inputs.main_ini)
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    geometry, materials = Path(inputs.geometry_path), Path(inputs.materials_path)
    if inputs.geometry_text is not None:
        geometry = directory / "editor_geometry.ini"
        geometry.write_text(inputs.geometry_text, encoding="utf-8", newline="\n")
    if inputs.materials_text is not None:
        materials = directory / "editor_materials.ini"
        materials.write_text(inputs.materials_text, encoding="utf-8", newline="\n")
    main = directory / "main.ini"
    main.write_text("\n".join([
        "# Show Backend Geometry: initialise Geant4 and export the world, no events.",
        "[run]", "threads = 1", "check_overlaps = false", "",
        "[materials]", f"file = {materials.as_posix()}", "",
        "[geometry]", f"template = {inputs.template}", f"config = {geometry.as_posix()}",
        "check_overlaps = false", ""]), encoding="utf-8", newline="\n")
    return main


def backend_failure(stderr: str, stdout: str, directory: str | Path) -> str:
    """The backend's own reason, with the export folder's editor files named as such."""
    text = stderr.strip() or stdout.strip()
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    reason = next((line for line in lines if "fatal error" in line.lower()),
                  next((line for line in reversed(lines) if "error" in line.lower()), lines[-1] if lines else ""))
    folder = Path(directory).as_posix()
    for name, label in (("editor_geometry.ini", "<geometry from the editor>"),
                        ("editor_materials.ini", "<materials from the editor>")):
        reason = reason.replace(f"{folder}/{name}", label).replace(str(Path(directory) / name), label)
    return reason
