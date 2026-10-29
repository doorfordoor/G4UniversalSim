from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from g4usim_gui.output.csv_preview import read_csv_preview
from g4usim_gui.output.file_classifier import OutputFileType, classify_files
from g4usim_gui.output.merge_plan import build_merge_plan, find_merge_histograms


def main() -> int:
    root = Path(__file__).resolve().parents[2]
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "output"
        out.mkdir()
        (out / "hits_t0.csv").write_text("a,b\n1,2\n", encoding="utf-8")
        (out / "event_edep_t0.csv").write_text("runID,eventID,raw_edep,weighted_edep\n0,0,1,1\n", encoding="utf-8")
        (out / "event_edep_t0_r1.csv").write_text("runID,eventID,raw_edep,weighted_edep\n1,0,2,2\n", encoding="utf-8")
        (out / "hist_edep_raw_t0.csv").write_text("bin_low,bin_high,count\n0,1,2\n", encoding="utf-8")
        (out / "hist_edep_weighted_t0.csv").write_text("bin_low,bin_high,count\n0,1,2\n", encoding="utf-8")
        (out / "run_summary.txt").write_text("threads = 1\n", encoding="utf-8")

        types = {Path(info.path).name: info.file_type for info in classify_files(out)}
        assert types["hits_t0.csv"] == OutputFileType.HITS_THREAD_CSV
        assert types["event_edep_t0_r1.csv"] == OutputFileType.EVENT_EDEP_THREAD_CSV
        assert types["run_summary.txt"] == OutputFileType.RUN_SUMMARY

        preview = read_csv_preview(out / "hits_t0.csv", max_rows=1)
        assert preview.header == ["a", "b"]
        assert preview.rows == [["1", "2"]]

        plan = build_merge_plan(str(out), str(root))
        assert len(plan.tasks) == 4
        assert any(task.kind == "hits" for task in plan.tasks)
        event_task = next(task for task in plan.tasks if task.kind == "event_edep")
        assert len(event_task.matched_files) == 2
        custom = Path(tmp) / "custom backend"
        custom.mkdir()
        backend = custom / "G4UniversalSim.exe"
        backend.touch()
        (custom / "unrelated.exe").touch()
        fallback = find_merge_histograms(root)
        assert find_merge_histograms(root, str(backend)) == fallback
        sibling = custom / "mergeHistograms.exe"
        sibling.touch()
        assert find_merge_histograms(root, str(backend)) == sibling
        adjacent = build_merge_plan(str(out), str(root), backend_executable=str(backend))
        assert all(t.command_program == str(sibling) and t.available for t in adjacent.tasks if t.kind.startswith("hist"))
        explicit = Path(tmp) / "manual.exe"
        explicit.touch()
        manual = build_merge_plan(str(out), str(root), str(explicit), backend_executable=str(backend))
        assert all(t.command_program == str(explicit) for t in manual.tasks if t.kind.startswith("hist"))
        explicit.unlink()
        invalid = build_merge_plan(str(out), str(root), str(explicit), backend_executable=str(backend))
        assert all(not t.available and t.command_program == str(explicit) for t in invalid.tasks if t.kind.startswith("hist"))
        linux_backend = custom / "G4UniversalSim"
        linux_backend.touch()
        assert find_merge_histograms(root, str(linux_backend)) == fallback
        linux_merge = custom / "mergeHistograms"
        linux_merge.touch()
        assert find_merge_histograms(root, str(linux_backend)) == linux_merge

    print("smoke_output_tools: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
