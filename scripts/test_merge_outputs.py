"""M0-4 regression checks for deterministic, all-or-nothing CSV concatenation."""

from __future__ import annotations

import csv
import tempfile
from pathlib import Path
from unittest.mock import patch

from merge_outputs import merge, resolve_files


def expect_failure(files: list[Path], output: Path, expected: str) -> None:
    try:
        merge(files, output)
    except (RuntimeError, FileExistsError) as exc:
        assert expected in str(exc), str(exc)
    else:
        raise AssertionError(f"Merge unexpectedly succeeded: {expected}")


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="g4usim-output-merge-") as directory:
        root = Path(directory)
        first = root / "event_edep_t0.csv"
        second = root / "event_edep_t1.csv"
        first.write_text("runID,eventID,raw_edep,weighted_edep\n0,0,1,1\n", encoding="utf-8")
        second.write_text("runID,eventID,raw_edep,weighted_edep\n0,1,2,2\n", encoding="utf-8")
        output = root / "event_edep_merged.csv"
        assert resolve_files(root, "event_edep_t*.csv", []) == [first, second]
        merge([second, first], output)
        with output.open(newline="", encoding="utf-8") as stream:
            assert list(csv.reader(stream)) == [
                ["runID", "eventID", "raw_edep", "weighted_edep"], ["0", "0", "1", "1"], ["0", "1", "2", "2"],
            ]
        original = output.read_bytes()
        expect_failure([first, second], output, "already exists")
        assert output.read_bytes() == original
        expect_failure([first, first], root / "duplicate.csv", "Duplicate input")
        expect_failure([first, output], output, "also be an input")

        bad_header = root / "bad-header.csv"
        bad_header.write_text("eventID,raw_edep\n0,1\n", encoding="utf-8")
        mismatch_output = root / "mismatch.csv"
        expect_failure([first, bad_header], mismatch_output, "Header mismatch")
        assert not mismatch_output.exists()

        current_a = root / "event_edep_t0_r1.csv"
        current_b = root / "event_edep_t1_r1.csv"
        current_header = "runID,eventID,raw_edep_MeV,weighted_edep_MeV\n"
        current_a.write_text(current_header + "1,0,3,3\n", encoding="utf-8")
        current_b.write_text(current_header + "1,1,4,4\n", encoding="utf-8")
        current_output = root / "current-merged.csv"
        merge([current_b, current_a], current_output)
        with current_output.open(newline="", encoding="utf-8") as stream:
            assert list(csv.reader(stream)) == [
                ["runID", "eventID", "raw_edep_MeV", "weighted_edep_MeV"],
                ["1", "0", "3", "3"], ["1", "1", "4", "4"],
            ]
        expect_failure([first, current_a], root / "mixed-version.csv", "Header mismatch")

        malformed = root / "malformed.csv"
        malformed.write_text("runID,eventID,raw_edep,weighted_edep\n0,1\n", encoding="utf-8")
        malformed_output = root / "malformed-result.csv"
        expect_failure([first, malformed], malformed_output, "Column count mismatch")
        assert not malformed_output.exists()

        empty = root / "empty.csv"
        empty.write_text("", encoding="utf-8")
        empty_output = root / "empty-result.csv"
        expect_failure([first, empty], empty_output, "Empty CSV input")
        assert not empty_output.exists()

        publish_failure = root / "publish-failure.csv"
        with patch("merge_outputs.os.link", side_effect=OSError("injected publish failure")):
            try:
                merge([first, second], publish_failure)
            except OSError as exc:
                assert "injected publish failure" in str(exc)
            else:
                raise AssertionError("Publish failure was not reported")
        assert not publish_failure.exists(), "Failed publication left a visible result"
        assert not list(root.glob(".publish-failure.csv.*.tmp")), "Failed publication left a temporary file"

        assert not list(root.glob(".*.tmp")), "Temporary result was not removed"

    print("test_merge_outputs: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
