"""Closed standard GUI package duplication: real writer, safe paths and runs."""
from __future__ import annotations
import argparse
from contextlib import ExitStack
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "gui"))
from g4usim_gui.core.project import G4USimProject
from g4usim_gui.history.run_package_actions import duplicate_package, read_generated_run_settings
from g4usim_gui.models.package_model import GeometrySettings, PathSettings
from g4usim_gui.models.run_model import RunSettings
from g4usim_gui.models.source_model import SourceSettings
from g4usim_gui.models.physics_model import PhysicsSettings
from g4usim_gui.models.scoring_model import ScoringSettings
from g4usim_gui.writers.package_writer import create_run_package


def tree_hashes(path):
    return {p.relative_to(path).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in path.rglob("*") if p.is_file()}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--component", action="store_true")
    args = parser.parse_args()
    executable = Path(sys.executable) if args.component else Path(os.environ["G4USIM_EXE"]).resolve()
    assert executable.is_file(), executable
    with ExitStack() as stack:
        requested = os.environ.get("G4USIM_TEST_WORK")
        folder = Path(requested).resolve() if requested else Path(stack.enter_context(tempfile.TemporaryDirectory(prefix="e6-duplicate-")))
        folder.mkdir(parents=True, exist_ok=True)
        material = folder / "selected-material.ini"
        material.write_bytes((ROOT / "config/materials/material.ini").read_bytes())
        geometry = folder / "selected-geometry.ini"
        geometry.write_text("[world]\nshape=box\nsize=100 mm,100 mm,100 mm\nmaterial=G4_AIR\n[volume.Target]\nparent=world\nshape=box\nsize=10 mm,10 mm,10 mm\nmaterial=G4_Si\nsensitive=true\n", encoding="utf-8")
        paths = PathSettings(executable=str(executable), workspace_root=str(ROOT), runs_root=str(folder / "packages"),
                             materials_config=str(material), geometry_config=str(geometry))
        package, _ = create_run_package(project=G4USimProject(), paths=paths,
            run=RunSettings(threads=1, seed=43, beam_on=2), geometry=GeometrySettings(template="hierarchical", config_path=str(geometry)),
            source=SourceSettings(), physics=PhysicsSettings(), scoring=ScoringSettings())
        original = Path(package.package_dir)
        (original / "output/run_summary.txt").write_text("status=completed\nactual_completed_event_count=99\n", encoding="utf-8")
        (original / "logs/run_status.json").write_text('{"state":"success","exitCode":0}', encoding="utf-8")
        main_path = Path(package.main_ini_path)
        main_text = main_path.read_text(encoding="utf-8")
        comment = "# Keep this historical path only as a comment: " + package.materials_ini_path
        main_path.write_text(main_text + "\n" + comment + "\n", encoding="utf-8")
        expected_hashes = tree_hashes(original)
        copy = Path(duplicate_package(str(original), str(folder / "copies")))
        assert tree_hashes(original) == expected_hashes
        assert not list((copy / "output").iterdir()) and not list((copy / "logs").iterdir())
        duplicated_main = (copy / "config/main.ini").read_text(encoding="utf-8")
        assert f"file = {copy / 'config/materials/material.ini'}" in duplicated_main
        assert f"config = {copy / 'config/geometry/geometry.ini'}" in duplicated_main
        assert f"dir = {copy / 'output'}" in duplicated_main
        assert comment in duplicated_main  # no whole-file replacement
        snapshot = json.loads((copy / "project_snapshot.json").read_text(encoding="utf-8"))
        assert snapshot["runPackage"]["materials_ini_path"] == str(copy / "config/materials/material.ini")
        assert snapshot["runPackage"]["geometry_ini_path"] == str(copy / "config/geometry/geometry.ini")
        assert snapshot["geometrySettings"]["config_path"] == snapshot["runPackage"]["geometry_ini_path"]
        assert snapshot["pathSettings"]["materials_config"] == snapshot["runPackage"]["materials_ini_path"]
        for relative in ("config/materials/material.ini", "config/geometry/geometry.ini", "macros/run.mac"):
            assert (copy / relative).read_bytes() == (original / relative).read_bytes()

        snapshot_path = Path(package.project_snapshot_path)
        original_snapshot = snapshot_path.read_bytes()
        original_main = main_path.read_bytes()
        read_before = tree_hashes(original)
        identity = read_generated_run_settings(original)
        assert (identity.threads, identity.seed, identity.run_name) == (1, 43, "gui_run")
        assert tree_hashes(original) == read_before, "The run-settings helper must be read-only"
        # Current main values are authoritative even when snapshot runSettings
        # and its flat mirrors retain the original producer values.
        updated_main = original_main.replace(b"threads = 1", b"threads = +2", 1).replace(b"seed = 43", b"seed = +007", 1).replace(b"name = gui_run", b"name = handwritten current name ; retain comment", 1)
        main_path.write_bytes(updated_main)
        identity = read_generated_run_settings(original)
        assert (identity.threads, identity.seed, identity.run_name) == (2, 7, "handwritten current name")
        assert json.loads(snapshot_path.read_bytes())["runSettings"]["threads"] == 1
        current_copy = Path(duplicate_package(str(original), str(folder / "copies")))
        assert read_generated_run_settings(current_copy) == identity
        exact_name = "named\u00a0run\u00a0"
        main_path.write_bytes(original_main.replace(b"name = gui_run", ("name = " + exact_name + " ; comment").encode("utf-8"), 1))
        assert read_generated_run_settings(original).run_name == exact_name
        for raw, expected in ((b"0", 0), (b"-0", 0), (b"2147483647", 2147483647), (b"0" * 5000 + b"1", 1)):
            main_path.write_bytes(original_main.replace(b"seed = 43", b"seed = " + raw, 1))
            assert read_generated_run_settings(original).seed == expected
        # Missing optional values must not inherit either current UI state or
        # stale snapshot values; an explicitly empty seed is invalid below.
        stripped_main = original_main.replace(b"seed = 43\r\n", b"").replace(b"seed = 43\n", b"").replace(b"name = gui_run\r\n", b"").replace(b"name = gui_run\n", b"")
        main_path.write_bytes(stripped_main)
        missing = read_generated_run_settings(original)
        assert missing.seed is None and missing.run_name == ""
        optional_copy = Path(duplicate_package(str(original), str(folder / "copies")))
        assert read_generated_run_settings(optional_copy).seed is None
        main_path.write_bytes(original_main)
        macro_path = Path(package.run_macro_path)
        original_macro = macro_path.read_bytes()
        geometry_path = Path(package.geometry_ini_path)
        original_geometry = geometry_path.read_bytes()
        rejected_cases = []

        def reject(name, mutate, restore):
            mutate()
            changed_source_hashes = tree_hashes(original)
            roots = set((folder / "copies").iterdir())
            try:
                duplicate_package(str(original), str(folder / "copies"))
            except (ValueError, UnicodeError, OSError) as error:
                assert str(error), name
                rejected_cases.append(dict(name=name, error=str(error)))
            else:
                assert False, f"Unsafe package accepted: {name}"
            assert set((folder / "copies").iterdir()) == roots, name
            assert tree_hashes(original) == changed_source_hashes, name
            restore()

        reject("bad-json", lambda: snapshot_path.write_bytes(b"{"), lambda: snapshot_path.write_bytes(original_snapshot))
        reject("duplicate-json-key", lambda: snapshot_path.write_bytes(b'{"runPackage":{},"runPackage":{}}'), lambda: snapshot_path.write_bytes(original_snapshot))
        assert original_main.count(b"schema_version = 1") == 1
        reject("future-main-format", lambda: main_path.write_bytes(original_main.replace(b"schema_version = 1", b"schema_version = 999", 1)), lambda: main_path.write_bytes(original_main))
        for value in (b"", b"0", b"-1", b"1.0", b"1e2", b"2147483648", b"1\xc2\xa0"):
            reject("invalid-threads-" + repr(value), lambda value=value: main_path.write_bytes(original_main.replace(b"threads = 1", b"threads = " + value, 1)), lambda: main_path.write_bytes(original_main))
        for value in (b"", b"-1", b"1.0", b"0x10", b"2147483648", b"1\xc2\xa0"):
            reject("invalid-seed-" + repr(value), lambda value=value: main_path.write_bytes(original_main.replace(b"seed = 43", b"seed = " + value, 1)), lambda: main_path.write_bytes(original_main))
        reject("missing-required-threads", lambda: main_path.write_bytes(original_main.replace(b"threads = 1\r\n", b"").replace(b"threads = 1\n", b"")), lambda: main_path.write_bytes(original_main))
        reject("duplicate-run-name", lambda: main_path.write_bytes(original_main.replace(b"name = gui_run", b"name=first\nname=second", 1)), lambda: main_path.write_bytes(original_main))
        reject("duplicate-path-key", lambda: main_path.write_bytes(original_main.replace(b"[materials]", b"[materials]\nfile = ignored")), lambda: main_path.write_bytes(original_main))
        reject("duplicate-path-section", lambda: main_path.write_bytes(original_main + b"\n[materials]\n"), lambda: main_path.write_bytes(original_main))
        reject("external-material-path", lambda: main_path.write_bytes(original_main.replace(package.materials_ini_path.encode(), str(material).encode())), lambda: main_path.write_bytes(original_main))
        reject("external-geometry-path", lambda: main_path.write_bytes(original_main.replace(package.geometry_ini_path.encode(), str(geometry).encode())), lambda: main_path.write_bytes(original_main))
        reject("external-output-path", lambda: main_path.write_bytes(original_main.replace(package.output_dir.encode(), str(folder / "other-output").encode())), lambda: main_path.write_bytes(original_main))
        reject("relative-material-path", lambda: main_path.write_bytes(original_main.replace(package.materials_ini_path.encode(), b"materials/material.ini")), lambda: main_path.write_bytes(original_main))
        reject("extra-resource-section", lambda: main_path.write_bytes(original_main + b"\n[field]\n"), lambda: main_path.write_bytes(original_main))
        reject("dynamic-macro", lambda: macro_path.write_bytes(original_macro + b"\n/control/execute other.mac\n"), lambda: macro_path.write_bytes(original_macro))
        reject("geometry-sidecar", lambda: geometry_path.write_bytes(original_geometry + b"\n[gdml]\nfile=outside.gdml\n"), lambda: geometry_path.write_bytes(original_geometry))
        def wrong_snapshot():
            data = json.loads(original_snapshot)
            data["runPackage"]["geometry_ini_path"] = str(geometry)
            snapshot_path.write_text(json.dumps(data), encoding="utf-8")
        reject("snapshot-path-mismatch", wrong_snapshot, lambda: snapshot_path.write_bytes(original_snapshot))
        def unknown_nested_snapshot():
            data = json.loads(original_snapshot)
            data["materialsSummary"]["materials"][0]["unknown_metadata"] = True
            snapshot_path.write_text(json.dumps(data), encoding="utf-8")
        reject("unknown-nested-metadata", unknown_nested_snapshot, lambda: snapshot_path.write_bytes(original_snapshot))
        extra = original / "config/untracked.csv"
        reject("additional-file", lambda: extra.write_text("extra", encoding="utf-8"), lambda: extra.unlink())
        reject("missing-material", lambda: Path(package.materials_ini_path).unlink(),
               lambda: Path(package.materials_ini_path).write_bytes((copy / "config/materials/material.ini").read_bytes()))
        assert tree_hashes(original) == expected_hashes
        assert (copy / "config/main.ini").read_bytes().count(b"schema_version = 1") == 1
        newline = b"\r\n" if b"\r\n" in original_main else b"\n"
        legacy_main = original_main.replace(b"[general]" + newline + b"schema_version = 1" + newline + newline, b"", 1)
        assert b"schema_version" not in legacy_main
        main_path.write_bytes(legacy_main)
        legacy_copy = Path(duplicate_package(str(original), str(folder / "copies")))
        assert b"schema_version" not in (legacy_copy / "config/main.ini").read_bytes()
        main_path.write_bytes(original_main)
        saved_open = Path.open
        def fail_new_write(path, mode="r", *positional, **keyword):
            if mode == "xb":
                raise OSError("injected new-package write failure")
            return saved_open(path, mode, *positional, **keyword)
        with patch.object(Path, "open", fail_new_write):
            try:
                duplicate_package(str(original), str(folder / "write-failure"))
            except OSError as error:
                assert "injected" in str(error)
            else:
                assert False, "A failed write must not report duplication success"
        assert tree_hashes(original) == expected_hashes
        try:
            duplicate_package(str(original), str(original / "output"))
        except ValueError as error:
            assert "outside the source package" in str(error)
        else:
            assert False, "Duplication must not write inside the source package"
        assert tree_hashes(original) == expected_hashes
        (folder / "rejected-cases.json").write_text(json.dumps(rejected_cases, indent=2) + "\n", encoding="utf-8")

        if not args.component:
            moved = folder / "old-package-moved"
            assert original.resolve().is_relative_to(folder.resolve()) and moved.resolve().is_relative_to(folder.resolve())
            original.rename(moved)
            material.write_text("selected source changed and is invalid", encoding="utf-8")
            geometry.write_text("selected geometry changed and is invalid", encoding="utf-8")
            assert tree_hashes(moved) == expected_hashes
            for action, arguments in (("inspect", ["--inspect-run"]), ("run", ["--macro", str(copy / "macros/run.mac")])):
                result = subprocess.run([str(executable), "--config", str(copy / "config/main.ini"), *arguments],
                                        cwd=copy, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
                (folder / (action + ".log")).write_text(result.stdout + result.stderr, encoding="utf-8")
                assert result.returncode == 0, (action, result.stdout[-1500:], result.stderr[-1500:])
            summary = {k.strip(): v.strip() for line in (copy / "output/run_summary.txt").read_text(encoding="utf-8").splitlines()
                       if "=" in line for k, v in [line.split("=", 1)]}
            assert summary["status"] == "completed" and summary["actual_completed_event_count"] == "2", summary
            assert tree_hashes(moved) == expected_hashes
            assert not (copy / "logs/run_status.json").exists(), "Old success status must not be inherited"
        print(f"Generated package duplication passed: {len(rejected_cases)} rejected cases; " + ("component" if args.component else "real Inspect and 2 completed events"))


if __name__ == "__main__":
    main()
