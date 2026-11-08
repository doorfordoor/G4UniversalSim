"""Permanent runner entry for generator artifacts and real backend consumption."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def run(root, native):
    static = root / "static"
    argv = [sys.executable, "-B", str(ROOT / "scripts/test_ar1_generators.py"), "--out", str(static)]
    result = subprocess.run(argv, capture_output=True, timeout=180)
    (root / "static.stdout.log").write_bytes(result.stdout)
    (root / "static.stderr.log").write_bytes(result.stderr)
    assert result.returncode == 0, (result.stdout, result.stderr)
    report = json.loads((static / "results.json").read_text(encoding="utf-8"))
    assert report["passed"] == 19 and not report["failed"], report
    for row in report["cases"]:
        assert row["passed"], row
    if native:
        exe = Path(os.environ["G4USIM_EXE"]).resolve()
        sha = hashlib.sha256(exe.read_bytes()).hexdigest()
        argv = [sys.executable, "-B", str(ROOT / "scripts/test_ar1_generator_native.py"),
                "--cases", str(static), "--exe", str(exe), "--expected-exe-sha256", sha,
                "--out", str(root / "native")]
        result = subprocess.run(argv, capture_output=True, timeout=600)
        (root / "native.stdout.log").write_bytes(result.stdout)
        (root / "native.stderr.log").write_bytes(result.stderr)
        report = json.loads((root / "native/results.json").read_text(encoding="utf-8"))
        assert result.returncode == 0, (report, result.stdout, result.stderr)
        assert report["sources_and_inputs_unchanged"]
        assert len(report["cases"]) == 16, report
        for row in report["cases"]:
            assert row["passed"], row
            assert row["summary"]["initialized"] == "true", row
            assert row["summary"]["run_count"] == "0", row
        assert hashlib.sha256(exe.read_bytes()).hexdigest() == sha
    print("AR1 generator pipeline: passed " + ("native initialization" if native else "static generation"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--native", action="store_true")
    args = parser.parse_args()
    evidence = os.environ.get("G4USIM_TEST_EVIDENCE_DIR")
    if evidence:
        root = Path(evidence).resolve() / "pipeline"
        root.mkdir(parents=True, exist_ok=False)
        run(root, args.native)
    else:
        with tempfile.TemporaryDirectory(prefix="ar1-generators-") as directory:
            run(Path(directory), args.native)


if __name__ == "__main__":
    main()
