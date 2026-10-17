"""Static checks for source identity and non-green missing prerequisites."""

from __future__ import annotations

import json
import hashlib
import tempfile
from pathlib import Path
from unittest.mock import patch

from run_m0_tests import ROOT, executable_freshness, merge_executable_freshness, untracked_source_files, workspace_source_fingerprint


def main() -> int:
    fingerprint = workspace_source_fingerprint()
    assert len(fingerprint) == 64
    missing_sources = untracked_source_files()
    assert missing_sources == sorted(set(missing_sources))
    assert all((ROOT / source).is_file() for source in missing_sources)
    with tempfile.TemporaryDirectory(prefix="g4usim-runner-") as directory:
        executable = Path(directory) / "G4UniversalSim.exe"
        assert "missing" in executable_freshness(executable)
        executable.write_bytes(b"test placeholder")
        result = type("Result", (), {"returncode": 0, "stdout": json.dumps({"source_fingerprint": fingerprint})})()
        with patch("run_m0_tests.subprocess.run", return_value=result):
            assert executable_freshness(executable) == ""
        result.stdout = json.dumps({"source_fingerprint": "0" * 64})
        with patch("run_m0_tests.subprocess.run", return_value=result):
            assert "differs" in executable_freshness(executable)
        merger = Path(directory) / "mergeHistograms.exe"
        assert "missing" in merge_executable_freshness(merger)
        merger.write_bytes(b"test placeholder")
        merge_sha = hashlib.sha256((ROOT / "tools/mergeHistograms.cc").read_bytes()).hexdigest()
        result.stdout = merge_sha + "\n"
        with patch("run_m0_tests.subprocess.run", return_value=result):
            assert merge_executable_freshness(merger) == ""
        result.stdout = "0" * 64
        with patch("run_m0_tests.subprocess.run", return_value=result):
            assert "differs" in merge_executable_freshness(merger)
    print("test_m0_runner: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
