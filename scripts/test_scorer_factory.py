"""AR2 real scorer reconstruction component; no transport/science claim."""
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
    probe = Path(os.environ.get("G4USIM_SCORER_FACTORY_EXE",
                 str(backend.with_name("scorerFactoryCheck" + backend.suffix)))).resolve()
    evidence = Path(os.environ["G4USIM_TEST_EVIDENCE_DIR"])
    evidence.mkdir(parents=True, exist_ok=True)
    output = Path(tempfile.mkdtemp(prefix="scorer-factory-", dir=evidence))
    assert probe.is_file(), probe
    binary_before = sha(probe)
    source_before = workspace_source_fingerprint()
    probe_source = ROOT / "tools/scorerFactoryCheck.cc"
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
    counts = re.findall(rb"^AR2 scorer factory component: (\d+) checks passed; no transport\r?$",
                        run.stdout, re.MULTILINE)
    receipt = {"argv": run.args, "cwd": str(output.resolve()), "exit_code": run.returncode,
               "identity": identity, "binary_sha256": binary_before,
               "binary_sha256_after": sha(probe), "stdout_sha256": sha(stdout),
               "stderr_sha256": sha(stderr), "native_check_counts": [int(x) for x in counts],
               "scope": "component reconstruction and selectors; no transport"}
    (output / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    assert run.returncode == 0, run.stdout + run.stderr
    assert len(counts) == 1, run.stdout
    assert int(counts[0]) > 0, run.stdout
    assert receipt["binary_sha256_after"] == binary_before, receipt
    assert sha(probe_source) == probe_sha
    assert workspace_source_fingerprint() == source_before
    print(f"Scorer factory native component: {int(counts[0])} checks; wrapper identity passed")


if __name__ == "__main__":
    main()
