from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from g4usim_gui.core.run_result import evaluate_run_result, summary_fingerprint


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        summary = Path(tmp) / "run_summary.txt"

        def write(*, status="completed", macro="completed", runs=1, planned=3, completed=3,
                  exit_code=0, executed="true", write_status="completed",
                  run_records: tuple[tuple[int, int], ...] | None = None) -> None:
            records = run_records if run_records is not None else (
                ((planned, completed),) if runs == 1 else ()
            )
            run_lines = "".join(
                f"run_{index}_id = {index}\nrun_{index}_planned_events = {run_planned}\n"
                f"run_{index}_completed_events = {run_completed}\n"
                for index, (run_planned, run_completed) in enumerate(records)
            )
            summary.write_text(
                f"status = {status}\nprogram_exit_code = {exit_code}\n"
                f"summary_write_status = {write_status}\nmacro_execution_status = {macro}\n"
                f"run_count = {runs}\nplanned_event_count = {planned}\n"
                f"actual_completed_event_count = {completed}\nsimulation_executed = {executed}\n"
                f"[Runs]\n{run_lines}",
                encoding="utf-8",
            )

        def state(**kwargs) -> str:
            return evaluate_run_result(summary, exit_code=0, summary_fresh=True, **kwargs).state

        assert state() == "incomplete"  # Exit zero without a summary is not success.
        write()
        assert state() == "success"
        write(runs=2, planned=3, completed=3, run_records=((2, 1), (1, 2)))
        assert state() == "incomplete"  # Equal totals cannot hide an incomplete run.
        write(runs=2, planned=3, completed=3, run_records=((1, 1), (2, 2)))
        assert state() == "success"
        write(runs=2, planned=3, completed=3, run_records=((3, 3),))
        assert state() == "incomplete"  # Every reported run needs a record.
        write()
        assert evaluate_run_result(summary, exit_code=0, summary_fresh=False).state == "incomplete"
        assert evaluate_run_result(summary, exit_code=1, summary_fresh=True).state == "failed"
        assert evaluate_run_result(summary, exit_code=0, crashed=True, summary_fresh=True).state == "failed"
        assert evaluate_run_result(summary, exit_code=0, requested_state="stopped", summary_fresh=True).state == "stopped"
        assert evaluate_run_result(summary, exit_code=0, requested_state="killed", summary_fresh=True).state == "killed"
        before = summary_fingerprint(summary)
        assert before is not None

        write(runs=0, planned=0, completed=0, executed="false")
        assert state() == "no_run"
        write(status="interactive_no_run", runs=0, planned=0, completed=0, executed="false")
        assert state() == "interactive_no_run"
        write(status="dry_run", macro="skipped_dry_run", runs=0, planned=0,
              completed=0, executed="false")
        assert state() == "dry_run"
        write(completed=2)
        assert state() == "incomplete"
        write(status="aborted", completed=2)
        assert state() == "failed"
        write(macro="failed")
        assert state() == "failed"
        write(exit_code=1)
        assert state() == "incomplete"
        write(write_status="failed")
        assert state() == "incomplete"
        summary.write_text("status = completed\n", encoding="utf-8")
        assert state() == "incomplete"
    print("smoke_run_result: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
