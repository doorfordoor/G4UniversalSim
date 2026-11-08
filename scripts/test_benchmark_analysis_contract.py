"""Nullable analysis consumer checks; synthetic reports, no backend execution."""
import json
from pathlib import Path
import tempfile

from run_benchmarks import comparison_text, detector_feature, verdict, write_report


def main():
    with tempfile.TemporaryDirectory(prefix="g4usim-benchmark-contract-") as folder:
        root = Path(folder)
        pulse = root / "pulse.csv"
        pulse.write_text("e_low_MeV,deposit_per_primary\n0.9995,0.4\n", encoding="utf-8")
        base = {"analysis_schema_version": 2, "analysis_status": "completed", "run_status": "completed",
                "quantities": {}, "events": 20}
        cases = [
            ({**base, "mpv_MeV": 0.1, "mpv_error_MeV": None}, "landau_mpv", False),
            ({**base, "mpv_MeV": None, "mpv_error_MeV": None}, "landau_mpv", False),
            ({**base, "mpv_MeV": 1.0, "mpv_error_MeV": 0.01}, "landau_mpv", True),
            ({**base, "compton_edge_MeV": None}, "compton_edge", False),
            ({**base, "compton_edge_MeV": 1.0}, "compton_edge", True),
            ({**base, "analysis_status": "partial", "compton_edge_MeV": 1.0}, "compton_edge", False),
            ({**base, "run_status": "failed", "compton_edge_MeV": 1.0}, "compton_edge", False),
            ({**base, "analysis_schema_version": 1, "compton_edge_MeV": 1.0}, "compton_edge", False),
            ({**base, "single_escape_MeV": 1.0, "single_escape_per_primary": 0}, "single_escape", False),
            ({**base, "single_escape_MeV": 1.0, "single_escape_per_primary": .4}, "single_escape", True),
        ]
        results = []
        for report, kind, evaluable in cases:
            simulated, sigma, tolerance, quantity, reason = detector_feature(report, kind, pulse)
            result = verdict(simulated, sigma, 1.0, tolerance, reason)
            assert (result["status"] == "evaluated") == evaluable
            assert result["passed"] == evaluable
            if not evaluable:
                assert result["allowed"] is None and result["relative_deviation"] is None
                assert "not_evaluable" in comparison_text(result)
            result.update(case=kind, quantity=quantity, source="synthetic fixture")
            results.append(result)
        for content in ("e_low_MeV,deposit_per_primary\n", "e_low_MeV,deposit_per_primary\n0.9995,0\n"):
            pulse.write_text(content, encoding="utf-8")
            simulated, sigma, tolerance, _, reason = detector_feature(cases[-1][0], "single_escape", pulse)
            assert not verdict(simulated, sigma, 1., tolerance, reason)["passed"]
            assert reason and simulated is None
        for simulated, sigma in ((None, 0), (1., None), (float("nan"), .1), (1., float("inf")), (1., -.1)):
            result = verdict(simulated, sigma, 1., .01)
            assert not result["passed"] and result["status"] == "not_evaluable"
        normal = verdict(1., .01, 1., .01)
        assert normal["allowed"] == .04 and normal["deviation"] == 0 and normal["passed"]
        write_report(root, {"executable": "not_executed", "quick": True,
                           "passed": sum(r["passed"] for r in results),
                           "failed": sum(not r["passed"] for r in results),
                           "benchmarks": {"detector_response": results}})
        data = json.loads((root / "benchmark_report.json").read_text(encoding="utf-8"))
        assert data["benchmarks"]["detector_response"][0]["sigma"] is None
        assert "not_evaluable" in (root / "benchmark_report.md").read_text(encoding="utf-8")
    print("benchmark nullable analysis contract: passed (synthetic only)")


if __name__ == "__main__":
    main()
