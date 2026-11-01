"""Installed/source path discovery must respect native platform layouts."""
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "gui"))
from g4usim_gui.core import install_layout

WINDOWS_LAYOUT_FIXTURE = "build_vs2026/Release/G4UniversalSim.exe"  # platform-path-fixture: Temporary layout placeholder; never executed


def main():
    with tempfile.TemporaryDirectory(prefix="g4-install-layout-") as directory:
        # Windows TEMP may use an 8.3 alias; workspace discovery returns
        # canonical paths, so compare against the canonical fixture root.
        root = Path(directory).resolve()
        native_name = "G4UniversalSim.exe" if sys.platform == "win32" else "G4UniversalSim"
        other_name = "G4UniversalSim" if sys.platform == "win32" else "G4UniversalSim.exe"
        binary = root / "bin" / native_name
        binary.parent.mkdir()
        foreign = binary.with_name(other_name)
        foreign.write_bytes(b"foreign platform placeholder")
        with patch.object(install_layout, "application_root", return_value=root):
            assert install_layout.default_backend_executable() == ""
            binary.write_bytes(b"native path fixture, not a compatibility probe")
            assert install_layout.default_backend_executable() == str(binary)
            helper = root / "python" / ("G4USimPython.exe" if sys.platform == "win32" else "G4USimPython")
            helper.parent.mkdir()
            helper.write_bytes(b"bundled interpreter fixture")
            with patch.object(install_layout, "is_frozen", return_value=True), \
                    patch.dict(install_layout.os.environ, {"G4USIM_PYTHON": ""}), \
                    patch.object(install_layout.shutil, "which", side_effect=AssertionError("PATH must not be needed")):
                assert install_layout.script_python() == str(helper)
        assert install_layout.workspace_for_executable(binary) == root
        repo = root / "repository"
        (repo / "config").mkdir(parents=True)
        (repo / "CMakeLists.txt").write_text("# fixture\n", encoding="utf-8")
        for relative in ("build_linux/G4UniversalSim", WINDOWS_LAYOUT_FIXTURE,
                         "out/custom/build/Release/G4UniversalSim.exe"):
            source_binary = repo / relative
            source_binary.parent.mkdir(parents=True, exist_ok=True)
            source_binary.write_bytes(b"fixture")
            assert install_layout.workspace_for_executable(source_binary) == repo
        loose = root / "loose" / native_name
        assert install_layout.workspace_for_executable(loose) == loose.parent
        assert install_layout.workspace_for_executable(root / "project/build_linux" / native_name) == root / "project"
    print("platform install layout: native discovery and workspace anchors passed")


if __name__ == "__main__":
    main()
