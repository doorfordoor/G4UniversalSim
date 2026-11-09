"""Persistent process evidence service; synthetic records, no backend claims."""
import json
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "gui"))
from g4usim_gui.core.persisted_run_evidence import read_persisted_run_evidence
from g4usim_gui.core.run_result import summary_fingerprint
from g4usim_gui.history.run_history_scanner import scan_package


TEXT = ("[Values]\nstatus = completed\nprogram_exit_code = 0\nsummary_write_status = completed\n"
        "macro_execution_status = completed\nrun_count = 1\nplanned_event_count = 3\n"
        "actual_completed_event_count = 3\nsimulation_executed = true\n[Runs]\n"
        "run_0_id = 0\nrun_0_planned_events = 3\nrun_0_completed_events = 3\n")


def main():
    with tempfile.TemporaryDirectory(prefix="g4usim-persisted-evidence-") as directory:
        root = Path(directory)
        (root / "output").mkdir(); (root / "logs").mkdir()
        summary, status = root / "output/run_summary.txt", root / "logs/run_status.json"
        summary.write_text(TEXT, encoding="utf-8")
        good = {"resultVersion": 1, "summaryFresh": True, "summaryFingerprint": list(summary_fingerprint(summary)),
                "exitCode": 0, "exitStatus": "normal", "state": "success"}
        cases = [({}, "success"), ({"exitCode": 1}, "failed"), ({"exitStatus": "crashed"}, "failed"),
                 ({"exitStatus": None}, "incomplete"), ({"summaryFresh": False}, "incomplete"),
                 ({"summaryFingerprint": [0, 0]}, "incomplete"), ({"resultVersion": True}, "incomplete"),
                 ({"resultVersion": 99}, "incomplete"), ({"exitCode": False}, "incomplete"),
                 ({"exitCode": "0"}, "incomplete"), ({"state": "error"}, "failed"),
                 ({"state": "failed"}, "incomplete"), ({"state": "running"}, "incomplete"),
                 ({"state": []}, "incomplete"), ({"state": "stopped"}, "stopped"),
                 ({"state": "killed"}, "killed"), ({"state": "finished"}, "success")]
        for changes, expected in cases:
            record = {**good, **changes}
            status.write_text(json.dumps(record), encoding="utf-8")
            # The completion evaluator consumes the captured text, never reopens it.
            with patch("g4usim_gui.core.run_result.parse_run_summary", side_effect=AssertionError("second summary read")):
                evidence = read_persisted_run_evidence(summary, status)
            assert evidence.result.state == expected, (changes, evidence)
            entry = scan_package(root)
            assert entry.status == evidence.result.state
            assert entry.result_trust_level == evidence.trust_level
        for bad in ('{"exitCode":0,"exitCode":1}', '{broken', '[]', '[1]', '1', 'true', '"text"'):
            status.write_text(bad, encoding="utf-8")
            evidence = read_persisted_run_evidence(summary, status)
            assert evidence.result.state == "incomplete" and evidence.trust_level == "invalid_process_record"
            entry = scan_package(root)
            assert entry.status == evidence.result.state and entry.result_trust_level == evidence.trust_level
        status.unlink()
        evidence = read_persisted_run_evidence(summary, status)
        assert evidence.result.state == "incomplete" and evidence.trust_level == "summary_only"
        assert evidence.exit_code is None and evidence.summary_claimed_status == "completed"
        status.write_text(json.dumps(good), encoding="utf-8")
        summary.write_text(TEXT + "\n# replaced summary\n", encoding="utf-8")
        assert read_persisted_run_evidence(summary, status).result.state == "incomplete"
        for extra in ("status = completed\n", "run_0_completed_events = 3\n", "status: completed\n", "run_0_completed_events: 3\n"):
            summary.write_text(TEXT + extra, encoding="utf-8")
            status.write_text(json.dumps({**good, "summaryFingerprint": list(summary_fingerprint(summary))}), encoding="utf-8")
            evidence = read_persisted_run_evidence(summary, status)
            assert evidence.result.state == "incomplete" and evidence.summary_warnings
            assert scan_package(root).status == "incomplete"
        summary.unlink()
        assert read_persisted_run_evidence(summary, status).result.state == "incomplete"
    print("persisted process evidence: judgement and history agreement passed")


if __name__ == "__main__":
    main()
