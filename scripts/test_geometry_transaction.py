"""Real GeometryManager transaction probe; old implementation failures stay red."""
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
    probe = Path(os.environ.get("G4USIM_GEOMETRY_TRANSACTION_EXE",
                 str(backend.with_name("geometryTransactionCheck" + backend.suffix))))
    output = Path(os.environ["G4USIM_TEST_EVIDENCE_DIR"])
    output.mkdir(parents=True, exist_ok=True)
    assert probe.is_file(), probe
    identity_run = subprocess.run([str(probe), "--identity"], capture_output=True,
                                  text=True, encoding="utf-8", timeout=30)
    assert identity_run.returncode == 0, identity_run.stdout + identity_run.stderr
    identity = json.loads(identity_run.stdout)
    assert identity["source_fingerprint"] == workspace_source_fingerprint(), identity
    assert identity["probe_sha256"] == hashlib.sha256(
        (ROOT / "tools/geometryTransactionCheck.cc").read_bytes()).hexdigest(), identity
    run = subprocess.run([str(probe), str(output)], capture_output=True,
                         text=True, encoding="utf-8", timeout=120)
    (output / "probe.log").write_text(run.stdout + run.stderr, encoding="utf-8")
    receipt = {"command": run.args, "exit_code": run.returncode, "identity": identity,
               "binary_sha256": hashlib.sha256(probe.read_bytes()).hexdigest()}
    (output / "receipt.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    assert (output / "results.json").is_file(), run.stdout + run.stderr
    report = json.loads((output / "results.json").read_text(encoding="utf-8"))
    assert len(report["cases"]) == 8, report
    for case in report["cases"]:
        for check in case["checks"]:
            assert check["passed"], (case["case"], check, case["error"])
        before, after = case["before"], case["after"]
        assert before["registry_logical"] == after["registry_logical"] == [], case["case"]
        assert before["registry_physical"] == after["registry_physical"] == [], case["case"]
        fields = {field["path"]: field for field in json.loads(after["fields"])["fields"]}
        assert all(field["application_status"] == "not_applied" for field in fields.values())
        if case["threw"]:
            assert before == after, case["case"]
            assert after["dirty"] is False, case["case"]
            assert after["path"].endswith("A.ini"), case["case"]
            assert fields["/geometry/config_file"]["resolved"] == before["path"]
        else:
            assert after["path"] == case["target"], case["case"]
            assert fields["/geometry/config_file"]["resolved"] == case["target"]
            assert all(field["configuration_generation"] == after["generation"]
                       for field in fields.values()), case["case"]
            assert fields["/geometry/objects/world/size"]["resolved"] == [400, 200, 200]
            origins = fields["/geometry/objects/world/size"]["origins"]
            assert any(origin["input_sha256"] == after["reader"]["sha256"]
                       and origin["file"] == case["target"] for origin in origins)
            assert after["inputs"][0]["sha256"] == hashlib.sha256(
                Path(case["target"]).read_bytes()).hexdigest()
    assert run.returncode == 0, run.stdout + run.stderr
    assert report["failed_checks"] == 0, report["failed_checks"]
    print("Real GeometryManager transaction: 8 cases passed")


if __name__ == "__main__":
    main()
