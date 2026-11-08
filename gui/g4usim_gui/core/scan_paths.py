"""Prepare the reachable scan input graph, never historical receipts.

INI roles and /control/execute edges define traversal, not directories or
filename extensions. External inputs are read-only; required relocation of
an external input is rejected instead of silently executing against A.
"""
from pathlib import Path
import re
from g4usim_gui.core.scan import _rebase

PATH_KEYS = {"dir", "outputdir", "file", "materialfile", "config", "configfile",
             "geometry_config", "macro", "copies_file", "phase_space_file",
             "spectrum_file", "magnetic_map", "electric_map"}


def _owned(path: Path, root: Path) -> Path:
    resolved = path.resolve()
    if not resolved.is_relative_to(root.resolve()):
        raise ValueError(f"Scan writable/input path is outside its copied package: {path}")
    return resolved


def _role(section, key):
    if key in {"dir", "outputdir"}:
        return "output"
    if key == "macro":
        return "macro"
    if section == "materials" and key in {"file", "materialfile", "config", "configfile"}:
        return "materials"
    if key == "geometry_config" or section == "geometry" and key in {"config", "configfile"}:
        return "geometry"
    if key in {"config", "configfile"}:
        return "ini"
    return "resource"


def _macro_path(value, path):
    # Match MacroPreflight: # comments respect quotes; aliases are unsupported.
    quote, comment = "", ""
    for index, char in enumerate(value):
        if quote:
            if char == quote:
                quote = ""
        elif char in "\"'":
            quote = char
        elif char == "#":
            value, comment = value[:index], value[index:]
            break
    value = value.strip()
    quoting = value[:1] if value[:1] in {"'", '"'} else ""
    if quoting:
        closing = value.find(quoting, 1)
        if closing < 0 or value[closing + 1:].strip():
            raise ValueError(f"Invalid quoted /control/execute path: {path}")
        value = value[1:closing]
    if not value or any(char in value for char in "{}$"):
        raise ValueError(f"Empty or dynamic /control/execute path: {path}")
    return value, comment, quoting


def prepare_scan_inputs(manifest) -> list[str]:
    """Discover/validate all points before writes. Leaves are never parsed.

    Main INI links use backend cwd; geometry/source/map resources use their
    configuration directory; nested macros use the emitting macro directory.
    Shared acyclic inputs are valid. Cycles/missing targets reject before writes.
    """
    root = Path(manifest.scan_dir).resolve()
    origin = getattr(manifest, "_origin_dir", None) or root
    edits, originals, rendered = {}, {}, {}
    external, visited, active = set(), set(), set()

    def resolve(value, base, *, writable=False, readonly_parent=False):
        raw = Path(value)
        actual = (raw if raw.is_absolute() else base / raw).absolute()
        target = Path(_rebase(str(actual), origin, root))
        internal = target.is_relative_to(root)
        target = _owned(target, root) if internal else target.resolve()
        if readonly_parent and target != actual.resolve():
            raise ValueError(f"External scan input requires relocation; copy it into the scan first: {actual}")
        if writable:
            if not internal:
                raise ValueError(f"Scan output must remain inside its scan: {target}")
        else:
            if not target.is_file():
                kind = "copied" if internal else "external"
                raise ValueError(f"Missing {kind} scan dependency: {target}")
            if not internal:
                external.add(str(target))
        return target

    def visit(path, kind, package):
        key = (path, kind, package)
        if path in active:
            raise ValueError(f"Cyclic scan input dependency: {path}")
        if key in visited:
            return
        if len(active) >= 64 or len(visited) >= 10000:
            raise ValueError("Scan input dependency limit exceeded")
        if kind == "resource":
            visited.add(key)
            return
        active.add(path)
        readonly = not path.is_relative_to(root)
        raw_bytes = path.read_bytes()
        original = raw_bytes.decode("utf-8-sig")
        if path in originals and originals[path] != raw_bytes:
            raise ValueError(f"Scan input changed during preparation: {path}")
        originals[path] = raw_bytes
        section, lines = "", []
        for line in original.splitlines(keepends=True):
            heading = re.match(r"^\s*\[([^]]+)\]", line)
            if heading:
                section = heading[1].strip().lower()
            match = (re.match(r"^(\s*([^#;=]+?)\s*=\s*)(.*?)(\r?\n)?$", line)
                     if kind != "macro" else None)
            macro = (re.match(r"^([ \t]*/+control/+execute)(?=[ \t\r\n]|$)[ \t]*(.*?)(\r?\n)?$", line, re.I)
                     if kind == "macro" else None)
            if match and match[2].strip().lower() in PATH_KEYS:
                prefix, value, ending = match[1], match[3], match[4] or ""
                field = match[2].strip().lower()
                child_kind = _role(section, field)
            elif macro:
                prefix, value, ending = macro[1] + " ", macro[2], macro[3] or ""
                field, child_kind = "macro", "macro"
            else:
                lines.append(line)
                continue
            quoting = ""
            if kind == "macro":
                value, suffix, quoting = _macro_path(value, path)
            else:
                value, sep, comment = value.partition("#")
                value, semi, rest = value.partition(";")
                suffix = semi + rest + sep + comment
            parts = value.strip().split(",") if field == "phase_space_file" else [value.strip()]
            relocated = []
            for part in parts:
                if not part:
                    if macro:
                        raise ValueError(f"Empty /control/execute in scan input: {path}")
                    relocated.append(part)
                    continue
                base = (path.parent if kind in {"macro", "geometry"} or field in
                        {"phase_space_file", "spectrum_file", "magnetic_map", "electric_map"} else package)
                target = resolve(part, base, writable=child_kind == "output", readonly_parent=readonly)
                if child_kind != "output":
                    visit(target, child_kind, package)
                text = str(target)
                if macro and (quoting or "#" in text):
                    delimiter = quoting or '"'
                    text = delimiter + text + delimiter
                relocated.append(text)
            lines.append(line if readonly else
                         prefix + ",".join(relocated) + (" " if suffix else "") + suffix + ending)
        active.remove(path)
        visited.add(key)
        updated = "".join(lines)
        if not readonly:
            if path in rendered and rendered[path] != updated:
                raise ValueError(f"Shared scan input has conflicting working directories: {path}")
            rendered[path] = updated
            if updated != original:
                edits[path] = updated

    for point in manifest.points:
        package = _owned(Path(point.package_dir), root)
        if package == root:
            raise ValueError("Scan point must have its own package directory")
        for name in ("main_ini", "macro", "output_dir"):
            _owned(Path(getattr(point, name)), package)
        _owned(package / "logs", package)
        for path, kind in ((Path(point.main_ini), "ini"), (Path(point.macro), "macro")):
            visit(_owned(path, package), kind, package)
    for path, raw in originals.items():
        if path.read_bytes() != raw:
            raise ValueError(f"Scan input changed during preparation: {path}")
    for path, text in edits.items():
        path.write_text(text, encoding="utf-8", newline="\n")
    return sorted(external)
