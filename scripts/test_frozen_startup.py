"""Package startup failures must be noninteractive and dependency origins explicit."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packaging"))
from windows_freeze import audit_binary_sources, freeze_environment
import freeze_identity
import build_package


def directory_alias(link: Path, target: Path) -> None:
    """Use unprivileged Windows junctions; POSIX directory symlinks otherwise."""
    link.parent.mkdir(parents=True, exist_ok=True)
    if os.name == "nt":
        result = subprocess.run([os.environ.get("COMSPEC", "cmd.exe"), "/c", "mklink", "/J",
                                 str(link), str(target)], capture_output=True, text=True, timeout=15)
        assert result.returncode == 0, (result.stdout, result.stderr)
    else:
        link.symlink_to(target, target_is_directory=True)
    assert link.is_dir()


def cleanup_alias_regressions(root: Path) -> None:
    private_root = root.resolve(strict=True)
    for case in ("output-root-alias", "intermediate-alias"):
        checkout = private_root / case
        checkout.mkdir()
        if case == "output-root-alias":
            retained = checkout / "keep-source"
            alias = checkout / "out"
        else:
            retained = checkout / "out" / "retained-cache"
            alias = checkout / "out" / "stage" / "alias"
        valuable = retained / "valuable"
        valuable.mkdir(parents=True)
        marker = valuable / "source.py"
        original = b"# preserve this fixture\n"
        marker.write_bytes(original)
        assert alias.absolute().is_relative_to(private_root)
        assert retained.resolve(strict=True).is_relative_to(private_root)
        directory_alias(alias, retained)
        target = alias / "valuable"
        with patch.object(build_package, "ROOT", checkout), patch.object(build_package.shutil, "rmtree") as remove:
            try:
                build_package.clean_output_directory(target)
            except ValueError as error:
                assert "linked directories" in str(error), str(error)
            else:
                assert False, "output-root and intermediate aliases must reject before deletion"
            assert remove.call_count == 0
        assert marker.read_bytes() == original

    # The guard must still permit real cleanup of a plain, strictly contained
    # output directory. These are only files created in this private temp root.
    checkout = private_root / "normal-checkout"
    target = checkout / "out" / "cache"
    (target / "nested").mkdir(parents=True)
    (target / "nested" / "temporary.bin").write_bytes(b"ordinary output")
    assert target.resolve(strict=True).is_relative_to(private_root)
    with patch.object(build_package, "ROOT", checkout):
        build_package.clean_output_directory(target)
    assert not target.exists()
    assert (checkout / "out").is_dir()


def main():
    with patch.dict(os.environ, {"PATH": "unrelated-application-dlls", "PYTHONPATH": "unrelated-modules",
                                 "QT_PLUGIN_PATH": "unrelated-qt"}):
        clean = freeze_environment()
        assert "unrelated" not in clean["PATH"]
        assert "PYTHONPATH" not in clean and "QT_PLUGIN_PATH" not in clean
        assert os.environ["PATH"] == "unrelated-application-dlls"
    with tempfile.TemporaryDirectory(prefix="g4usim-freeze-test-") as folder:
        root = Path(folder)
        cleanup_alias_regressions(root)
        source_root = root / "source"
        (source_root / "gui/g4usim_gui").mkdir(parents=True)
        main_source = source_root / "gui/main.py"
        main_source.write_text("# first source", encoding="utf-8")
        frozen = root / "package-build/dist/G4UniversalSimGUI"
        frozen.mkdir(parents=True)
        binary = frozen / "GUI.exe"
        binary.write_bytes(b"test artifact bytes, not an executable")
        freeze_identity.seal(frozen, kind="gui", sources=freeze_identity.source_identity(source_root, "gui"), with_3d=True)
        assert freeze_identity.verify(frozen, root=source_root, kind="gui", with_3d=True)["kind"] == "gui"
        # The ordinary previous work/dist source may be reused, but never
        # from any tree that will be cleaned or built in the same invocation.
        freeze_identity.reject_overlap(frozen, [root / "package/new", root / "helper-build"])
        for destination in (root / "package-build", frozen, frozen / "nested-output"):
            try:
                freeze_identity.reject_overlap(frozen, [destination])
            except ValueError:
                pass
            else:
                assert False, "overlapping reuse and output must reject before cleanup"
        assert binary.is_file()
        main_source.write_text("# changed source", encoding="utf-8")
        try:
            freeze_identity.verify(frozen, root=source_root, kind="gui", with_3d=True)
        except ValueError as error:
            assert "source is stale" in str(error)
        else:
            assert False, "a self-test-compatible old build must not stand in for the current source"
        main_source.write_text("# first source", encoding="utf-8")
        binary.write_bytes(b"tampered binary")
        try:
            freeze_identity.verify(frozen, root=source_root, kind="gui", with_3d=True)
        except ValueError as error:
            assert "recorded bytes" in str(error)
        else:
            assert False, "matching source receipt must not conceal modified artifact bytes"
        with patch.object(build_package, "ROOT", source_root):
            outside = root / "keep"
            outside.mkdir()
            try:
                build_package.clean_output_directory(outside)
            except ValueError:
                pass
            else:
                assert False, "cleanup outside the output tree must reject"
            assert outside.is_dir()
        work = root / "freeze"
        toc = work / "build" / "Test" / "Analysis-00.toc"
        toc.parent.mkdir(parents=True)
        toc.write_text(repr([[("core.dll", str(work / "core.dll"), "BINARY")]]), encoding="utf-8")
        assert audit_binary_sources(work, "Test")["ok"]
        toc.write_text(repr([[("icuuc.dll", str(root / "foreign" / "icuuc.dll"), "BINARY")]]), encoding="utf-8")
        try:
            audit_binary_sources(work, "Test")
        except RuntimeError:
            pass
        else:
            assert False, "unrelated DLL source must reject packaging"
        sources = json.loads((work / "binary-sources.json").read_text(encoding="utf-8"))
        assert not sources["ok"] and not sources["binaries"][0]["allowed"]
        report = root / "failed-startup.json"
        code = (
            "import importlib.abc,sys,runpy\n"
            "class BrokenQt(importlib.abc.MetaPathFinder):\n"
            " def find_spec(self, fullname, path=None, target=None):\n"
            "  if fullname == 'g4usim_gui.app': raise ImportError('QtCore startup failure fixture')\n"
            "sys.meta_path.insert(0,BrokenQt())\n"
            f"sys.argv={[str(ROOT / 'gui/main.py'), '--self-test', str(report)]!r}\n"
            f"runpy.run_path({str(ROOT / 'gui/main.py')!r},run_name='__main__')\n"
        )
        result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=30)
        assert result.returncode == 1
        receipt = json.loads(report.read_text(encoding="utf-8"))
        assert receipt["ok"] is False and receipt["stage"] == "startup"
        assert "QtCore startup failure fixture" in receipt["error"]
        assert "ImportError" in receipt["traceback"]
        original = report.read_bytes()
        result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=30)
        assert result.returncode == 1 and report.read_bytes() == original
        # Normal user launches still propagate their actual startup failure.
        code = code.replace(repr([str(ROOT / "gui/main.py"), "--self-test", str(report)]), repr([str(ROOT / "gui/main.py")]))
        result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=30)
        assert result.returncode != 0 and "QtCore startup failure fixture" in result.stderr
    print("frozen startup: import failure, old evidence and dependency origins checked")


if __name__ == "__main__":
    main()
