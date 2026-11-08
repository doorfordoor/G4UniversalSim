"""AR1 real INI/direct/boolean solid probe, run only against a frozen candidate."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess

from run_m0_tests import workspace_source_fingerprint

ROOT = Path(__file__).resolve().parents[1]


def main():
    backend = Path(os.environ["G4USIM_EXE"])
    probe = Path(os.environ.get("G4USIM_GEOMETRY_SHAPES_EXE",
                 str(backend.with_name("geometryShapesCheck" + backend.suffix))))
    output = Path(os.environ["G4USIM_TEST_EVIDENCE_DIR"])
    output.mkdir(parents=True, exist_ok=True)
    assert probe.is_file(), probe
    identity_run = subprocess.run([str(probe), "--identity"], capture_output=True,
                                  text=True, encoding="utf-8", timeout=30)
    assert identity_run.returncode == 0, identity_run.stdout + identity_run.stderr
    identity = json.loads(identity_run.stdout)
    assert identity["source_fingerprint"] == workspace_source_fingerprint(), identity
    assert identity["probe_sha256"] == hashlib.sha256(
        (ROOT / "tools/geometryShapesCheck.cc").read_bytes()).hexdigest(), identity
    # A separate directory prevents old results from satisfying a failed new run.
    import tempfile
    run_dir = Path(tempfile.mkdtemp(prefix="shapes-", dir=output))
    run = subprocess.run([str(probe), str(run_dir)], capture_output=True,
                         text=True, encoding="utf-8", timeout=120)
    (run_dir / "probe.log").write_text(run.stdout + run.stderr, encoding="utf-8")
    receipt = {"command": run.args, "exit_code": run.returncode, "identity": identity,
               "binary_sha256": hashlib.sha256(probe.read_bytes()).hexdigest()}
    (run_dir / "receipt.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    assert run.returncode == 0, run.stdout + run.stderr
    report = json.loads((run_dir / "results.json").read_text(encoding="utf-8"))
    assert report["source_fingerprint"] == identity["source_fingerprint"], report
    assert report["probe_sha256"] == identity["probe_sha256"], report
    assert len(report["checks"]) >= 100, report
    assert report["failed_checks"] == 0, report
    for check in report["checks"]:
        assert check["passed"], check
    names = {check["name"] for check in report["checks"]}
    for required in {"direct_box", "direct_box_after_edit", "direct_tubs_parameters_win",
                     "direct_tubs_extra_ignored", "direct_shorthand_4", "boolean_box",
                     "boolean_tubs_extra_ignored", "boolean_no_shorthand:rejected",
                     "ini_cube", "ini_cylinder", "ini_boolean_composed_tube",
                     "ini_tubs_size:rejected", "ini_boolean_tubs_long:rejected",
                     "legacy_orb", "legacy_boolean_a5_refused:rejected"}:
        assert required in names, required
    print(f"Real geometry shape probe: {len(report['checks'])} checks passed")


if __name__ == "__main__":
    main()
