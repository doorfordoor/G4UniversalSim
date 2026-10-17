"""M0-4 black-box check against the actual five-column backend histogram CSV."""

from __future__ import annotations

import argparse
import csv
import subprocess
import tempfile
from pathlib import Path

from plot_hist import read_histogram


def run(executable: Path, output: Path, files: list[Path], expected: int = 0) -> str:
    result = subprocess.run(
        [str(executable), "--output", str(output), *(str(file) for file in files)],
        capture_output=True, text=True, timeout=20,
    )
    message = result.stdout + result.stderr
    assert result.returncode == expected, message
    return message


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--executable", required=True)
    executable = Path(parser.parse_args().executable)
    assert executable.is_file(), executable
    with tempfile.TemporaryDirectory(prefix="g4usim-hist-merge-") as temporary:
        root = Path(temporary)
        first = root / "hist_edep_raw_t0.csv"
        second = root / "hist_edep_raw_t1.csv"
        header = "bin,low_edge_MeV,high_edge_MeV,center_MeV,count\n"
        first.write_text(header + "0,0,0.5,0.25,2\n1,0.5,1,0.75,3\n", encoding="utf-8")
        second.write_text(header + "0,0,0.5,0.25,5\n1,0.5,1,0.75,7\n", encoding="utf-8")
        assert read_histogram(first) == ([0.0, 0.5], [0.5, 1.0], [2.0, 3.0])
        merged = root / "hist_edep_raw_merged.csv"
        run(executable, merged, [first, second])
        with merged.open(newline="", encoding="utf-8") as stream:
            rows = list(csv.DictReader(stream))
        assert read_histogram(merged) == ([0.0, 0.5], [0.5, 1.0], [7.0, 10.0])
        assert [(float(row["bin_low_MeV"]), float(row["bin_high_MeV"]), float(row["sum"])) for row in rows] == [
            (0.0, 0.5, 7.0), (0.5, 1.0, 10.0),
        ], rows
        original = merged.read_bytes()
        assert "already exists" in run(executable, merged, [first, second], expected=1)
        assert merged.read_bytes() == original
        assert not list(root.glob("*.tmp.*")), "Temporary histogram output was not removed"

        incompatible = root / "incompatible.csv"
        incompatible.write_text(header + "0,0,0.6,0.3,5\n1,0.6,1,0.8,7\n", encoding="utf-8")
        rejected = root / "rejected.csv"
        assert "Bin edge mismatch" in run(executable, rejected, [first, incompatible], expected=1)
        assert not rejected.exists()

        invalid = root / "invalid.csv"
        invalid.write_text(header + "0,0,0.5,0.25,nan\n", encoding="utf-8")
        invalid_output = root / "invalid-result.csv"
        assert "expected numeric CSV field" in run(executable, invalid_output, [first, invalid], expected=1)
        assert not invalid_output.exists()

        legacy = root / "legacy.csv"
        legacy.write_text("bin_low,bin_high,count\n0,0.5,4\n0.5,1,6\n", encoding="utf-8")
        legacy_output = root / "legacy-merged.csv"
        run(executable, legacy_output, [first, legacy])
        with legacy_output.open(newline="", encoding="utf-8") as stream:
            reader = csv.DictReader(stream)
            assert reader.fieldnames == ["bin_low", "bin_high", "sum", "mean", "stddev", "n_files"]
            assert [float(row["sum"]) for row in reader] == [6.0, 9.0]

        previous = root / "previous-v2.csv"
        previous.write_text("bin,low_edge,high_edge,center,count\n0,0,0.5,0.25,4\n1,0.5,1,0.75,6\n", encoding="utf-8")
        assert read_histogram(previous) == ([0.0, 0.5], [0.5, 1.0], [4.0, 6.0])
        mixed_output = root / "mixed-v2-v3.csv"
        run(executable, mixed_output, [first, previous])
        with mixed_output.open(newline="", encoding="utf-8") as stream:
            assert next(csv.reader(stream))[:2] == ["bin_low", "bin_high"]

    print("test_merge_histograms: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
