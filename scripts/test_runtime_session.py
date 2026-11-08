"""AR3 production runtime coordinator component; no transport/science claim."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile

from run_m0_tests import workspace_source_fingerprint

ROOT = Path(__file__).resolve().parents[1]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    backend = Path(os.environ["G4USIM_EXE"])
    probe = Path(os.environ.get("G4USIM_RUNTIME_SESSION_EXE",
                 str(backend.with_name("runtimeSessionCheck" + backend.suffix)))).resolve()
    evidence = Path(os.environ["G4USIM_TEST_EVIDENCE_DIR"])
    evidence.mkdir(parents=True, exist_ok=True)
    output = Path(tempfile.mkdtemp(prefix="runtime-session-", dir=evidence))
    assert probe.is_file(), probe
    binary_before = sha(probe)
    source_before = workspace_source_fingerprint()
    probe_source = ROOT / "tools/runtimeSessionCheck.cc"
    probe_sha = sha(probe_source)
    identity_run = subprocess.run([str(probe), "--identity"], capture_output=True, timeout=30)
    (output / "identity.stdout").write_bytes(identity_run.stdout)
    (output / "identity.stderr").write_bytes(identity_run.stderr)
    assert identity_run.returncode == 0, identity_run.stderr
    identity = json.loads(identity_run.stdout)
    assert identity["source_fingerprint"] == source_before, identity
    assert identity["probe_sha256"] == probe_sha, identity
    run = subprocess.run([str(probe)], cwd=output, capture_output=True, timeout=120)
    stdout, stderr = output / "probe.stdout", output / "probe.stderr"
    stdout.write_bytes(run.stdout)
    stderr.write_bytes(run.stderr)
    counts = re.findall(rb"^Runtime session component checks passed: (\d+)\r?$",
                        run.stdout, re.MULTILINE)
    receipt = {"argv": run.args, "cwd": str(output.resolve()), "exit_code": run.returncode,
               "identity": identity, "binary_sha256": binary_before,
               "binary_sha256_after": sha(probe), "stdout_sha256": sha(stdout),
               "stderr_sha256": sha(stderr), "native_check_counts": [int(x) for x in counts],
               "scope": "production batch coordinator with controlled execution port; no transport"}
    (output / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    assert run.returncode == 0, run.stdout + run.stderr
    assert len(counts) == 1, run.stdout
    assert int(counts[0]) > 0, run.stdout
    assert receipt["binary_sha256_after"] == binary_before, receipt
    assert sha(probe_source) == probe_sha
    assert workspace_source_fingerprint() == source_before
    print(f"Runtime session native component: {int(counts[0])} checks; wrapper identity passed")


if __name__ == "__main__":
    main()
