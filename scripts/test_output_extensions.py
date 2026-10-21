"""Contract smoke for the M5 postprocessing-extension prototype."""
from __future__ import annotations

import json
import math
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "scripts" / "run_output_extension.py"
sys.path.insert(0, str(ROOT))
from scripts.output_extension_registry import OutputExtensionRegistry  # noqa: E402


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="g4usim-output-extension-") as tmp:
        root = Path(tmp)
        input_dir = root / "run"
        input_dir.mkdir()
        header = ("runID,volume_path,volume_name,mass_kg,raw_edep_MeV,"
                  "weighted_edep_MeV,raw_dose_Gy,weighted_dose_Gy\n")
        for thread_id, edep in ((0, 2.0), (1, 3.0)):
            dose = edep * 1.602176634e-13
            (input_dir / f"dose_volume_summary_t{thread_id}.csv").write_text(
                header + f"0,/World/Target,Target,1,{edep},{edep},{dose},{dose}\n",
                encoding="utf-8")
        output = root / "dose-export.json"
        cmd = [sys.executable, "-B", str(CLI)]
        listed = subprocess.run(cmd + ["--list"], cwd=root, text=True, capture_output=True)
        assert listed.returncode == 0, listed.stderr
        assert any(item["id"] == "dose_json" for item in json.loads(listed.stdout))
        assert any(item["id"] == "fluence_json" for item in json.loads(listed.stdout))
        executed = subprocess.run(cmd + ["--run", "dose_json", "--input-dir", str(input_dir),
                                        "--output", str(output)], cwd=root, text=True, capture_output=True)
        assert executed.returncode == 0, executed.stderr
        content = json.loads(output.read_text(encoding="utf-8"))
        assert content["schema"] == "G4UniversalSimOutputExtensionResult"
        volume, = content["data"]["volumes"]
        assert volume["thread_ids"] == [0, 1]
        assert volume["mass_kg"] == 1  # mass must not be summed across workers
        assert volume["raw_edep_MeV"] == 5
        assert math.isclose(volume["raw_dose_Gy"], 5 * 1.602176634e-13)
        assert content["data"]["physical_validation"] == "not_established"
        again = subprocess.run(cmd + ["--run", "dose_json", "--input-dir", str(input_dir),
                                     "--output", str(output)], cwd=root, text=True, capture_output=True)
        assert again.returncode != 0 and output.read_text(encoding="utf-8") == json.dumps(
            content, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
        no_data = subprocess.run(cmd + ["--run", "dose_json", "--input-dir", str(root),
                                       "--output", str(root / "empty.json")], cwd=root,
                                 text=True, capture_output=True)
        assert no_data.returncode != 0 and not (root / "empty.json").exists()

        fluence_header = ("runID,volume_path,volume_name,volume_mm3,raw_track_length_mm,"
                          "weighted_track_length_mm,raw_fluence_mm-2,weighted_fluence_mm-2\n")
        for run_id in (0, 1):
            for thread, length in ((0, 2.0), (1, 3.0)):
                suffix = f"_r{run_id}" if run_id else ""
                (input_dir / f"fluence_volume_summary_t{thread}{suffix}.csv").write_text(
                    fluence_header +
                    f"{run_id},/World/Target,Target,100,{length},{length},{length / 100},{length / 100}\n",
                    encoding="utf-8")
        fluence_output = root / "fluence-export.json"
        fluence = subprocess.run(cmd + ["--run", "fluence_json", "--input-dir", str(input_dir),
                                    "--output", str(fluence_output)], cwd=root, text=True, capture_output=True)
        assert fluence.returncode == 0, fluence.stderr
        exported = json.loads(fluence_output.read_text(encoding="utf-8"))
        assert exported["extension_id"] == "fluence_json"
        assert exported["data"]["physical_validation"] == "not_established"
        assert len(exported["data"]["volumes"]) == 2
        for item in exported["data"]["volumes"]:
            assert item["thread_ids"] == [0, 1]
            assert item["volume_mm3"] == 100  # shared denominator, never summed
            assert item["raw_track_length_mm"] == 5
            assert math.isclose(item["weighted_fluence_mm-2"], 0.05)
        invalid = root / "invalid_fluence"
        invalid.mkdir()
        (invalid / "fluence_volume_summary_t0.csv").write_text(
            fluence_header + "0,/World/Target,Target,100,NaN,NaN,NaN,NaN\n", encoding="utf-8")
        rejected = subprocess.run(cmd + ["--run", "fluence_json", "--input-dir", str(invalid),
                                      "--output", str(root / "invalid.json")], cwd=root, text=True, capture_output=True)
        assert rejected.returncode != 0 and not (root / "invalid.json").exists()
        registry = OutputExtensionRegistry()
        registry.register({"id": "first", "version": "1.0.0", "api_version": 1,
                           "description": "test"}, lambda _: {})
        for info in ({"id": "first", "version": "1.0.0", "api_version": 1, "description": "duplicate"},
                     {"id": "second", "version": "1.0.0", "api_version": 2, "description": "wrong api"}):
            try:
                registry.register(info, lambda _: {})
            except ValueError:
                pass
            else:
                raise AssertionError(f"Invalid extension accepted: {info}")
    print("test_output_extensions: OK")


if __name__ == "__main__":
    main()
