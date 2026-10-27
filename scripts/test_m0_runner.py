"""Static checks for source identity and non-green missing prerequisites."""

from __future__ import annotations

import json
import hashlib
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

from run_m0_tests import (
    ASSERT_PROBE,
    ROOT,
    count_assert_sites,
    executable_freshness,
    merge_executable_freshness,
    parse_assert_marker,
    tests_content_fingerprint,
    untracked_source_files,
    workspace_source_fingerprint,
)


def run_probe(directory: Path, name: str, source: str) -> subprocess.CompletedProcess[str]:
    script = directory / name
    script.write_text(source, encoding="utf-8")
    return subprocess.run(
        [sys.executable, "-B", str(ASSERT_PROBE), str(script)],
        capture_output=True, text=True, encoding="utf-8", errors="replace", check=False,
    )


def main() -> int:
    fingerprint = workspace_source_fingerprint()
    assert len(fingerprint) == 64
    assert len(tests_content_fingerprint()) == 64
    missing_sources = untracked_source_files()
    assert missing_sources == sorted(set(missing_sources))
    assert all((ROOT / source).is_file() for source in missing_sources)
    with tempfile.TemporaryDirectory(prefix="g4usim-runner-") as directory:
        workspace = Path(directory)
        executable = workspace / "G4UniversalSim.exe"
        assert "missing" in executable_freshness(executable)
        executable.write_bytes(b"test placeholder")
        result = type("Result", (), {"returncode": 0, "stdout": json.dumps({"source_fingerprint": fingerprint})})()
        with patch("run_m0_tests.subprocess.run", return_value=result):
            assert executable_freshness(executable) == ""
        result.stdout = json.dumps({"source_fingerprint": "0" * 64})
        with patch("run_m0_tests.subprocess.run", return_value=result):
            assert "differs" in executable_freshness(executable)
        merger = workspace / "mergeHistograms.exe"
        assert "missing" in merge_executable_freshness(merger)
        merger.write_bytes(b"test placeholder")
        merge_sha = hashlib.sha256((ROOT / "tools/mergeHistograms.cc").read_bytes()).hexdigest()
        result.stdout = merge_sha + "\n"
        with patch("run_m0_tests.subprocess.run", return_value=result):
            assert merge_executable_freshness(merger) == ""
        result.stdout = "0" * 64
        with patch("run_m0_tests.subprocess.run", return_value=result):
            assert "differs" in merge_executable_freshness(merger)

        # Assertion probe: counts executed asserts and forwards exit behaviour unchanged.
        clean = run_probe(
            workspace, "clean_case.py",
            "assert 1 == 1\n"
            "for _ in range(3):\n"
            "    assert True\n"
            "print('done')\n",
        )
        assert clean.returncode == 0
        assert parse_assert_marker(clean.stdout) == 4, clean.stdout
        assert count_assert_sites(workspace / "clean_case.py") == 2
        numbered = run_probe(
            workspace, "numbered_exit.py",
            "assert True\n"
            "raise SystemExit(7)\n",
        )
        assert numbered.returncode == 7
        assert parse_assert_marker(numbered.stdout) == 1
        message_exit = run_probe(
            workspace, "message_exit.py",
            "assert True\n"
            "raise SystemExit('prerequisite missing')\n",
        )
        assert message_exit.returncode == 1
        assert "prerequisite missing" in message_exit.stderr
        assert parse_assert_marker(message_exit.stdout) == 1
        crashing = run_probe(
            workspace, "crashing_case.py",
            "assert True\n"
            "raise RuntimeError('boom')\n",
        )
        assert crashing.returncode != 0
        assert "boom" in crashing.stderr
        assert parse_assert_marker(crashing.stdout) == 1
        broken = workspace / "broken_syntax.py"
        broken.write_text("def broken(:\n", encoding="utf-8")
        assert count_assert_sites(broken) == 0

    assert parse_assert_marker("no marker here\n") is None
    assert parse_assert_marker("G4USIM_ASSERTS=not-a-number\n") is None
    help_text = subprocess.run(
        [sys.executable, "-B", str(ROOT / "scripts/run_m0_tests.py"), "--help"],
        capture_output=True, text=True, encoding="utf-8", errors="replace", check=False,
    )
    assert help_text.returncode == 0
    assert "--fail-on-skip" in help_text.stdout
    assert "--no-assert-probe" in help_text.stdout
    assert "out" in help_text.stdout and "verification" in help_text.stdout
    print("test_m0_runner: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
