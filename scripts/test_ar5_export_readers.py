"""AR5 real public-reader probe wrapper. Default is plan-only, never a native pass."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
PROBE_SOURCE = ROOT / "tools" / "iniReaderContractCheck.cc"


def require(condition, message):
    if not condition:
        raise RuntimeError(message)
    assert condition, message


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2) + "\n", encoding="utf-8")


def validate_result(result, identity):
    require(type(result) is dict, "probe result must be an object")
    for key in ("source_fingerprint", "probe_sha256", "geant4_version_number", "compiler", "compiler_version"):
        require(result.get(key) == identity[key], f"result identity mismatch: {key}")
    checks = result.get("checks")
    require(type(checks) is list and len(checks) > 100, "missing finite reader checks")
    require(type(result.get("check_count")) is int and result["check_count"] == len(checks), "canonical check count mismatch")
    require(result.get("failed_checks") == 0 and type(result.get("failed_checks")) is int, "probe reported failures")
    for check in checks:
        require(type(check) is dict and type(check.get("name")) is str and check["name"], "invalid check record")
        require(check.get("passed") is True, f"failed check: {check['name']}")
    names = {check["name"] for check in checks}
    require(len(names) == len(checks), "duplicate canonical check names")
    for name in ("nist_target", "alias_case", "modern_duplicates_preserved", "cross_file_load_preserved", "direct_add_preserved", "point_positive", "first_field_raw_BOM"):
        require(name in names, f"missing required observation: {name}")
    require(result.get("no_transport") is True, "probe must declare no transport")
    require(type(result.get("observations")) is list and result["observations"], "missing actual observations")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true", help="explicitly launch the native component; no backend BeamOn")
    parser.add_argument("--probe", default=os.environ.get("G4USIM_INI_READER_PROBE", ""))
    parser.add_argument("--expected-source", default=os.environ.get("G4USIM_EXPECTED_SOURCE_FINGERPRINT", ""))
    parser.add_argument("--evidence-dir", default=os.environ.get("G4USIM_TEST_EVIDENCE_DIR", ""))
    parser.add_argument("--timeout", type=float, default=120)
    args = parser.parse_args(argv)
    plan = {"schema": "ar5_export_readers_plan_v1", "status": "plan_only", "execute": args.execute,
            "probe": args.probe, "expected_source": args.expected_source,
            "probe_sha256": sha(PROBE_SOURCE), "no_transport": True,
            "native_acceptance": False, "cli": "--execute --probe ABS_PATH --expected-source SHA --evidence-dir NEW_DIR"}
    if not args.execute:
        print(json.dumps(plan, indent=2))
        return 0
    require(args.probe and Path(args.probe).is_file(), "--probe must identify a real component executable")
    require(len(args.expected_source) == 64 and all(c in "0123456789abcdef" for c in args.expected_source), "explicit 64-character candidate source SHA required")
    require(args.evidence_dir, "--evidence-dir (or G4USIM_TEST_EVIDENCE_DIR) is required")
    require(args.timeout > 0 and args.timeout <= 300, "finite timeout must be in (0,300]")
    evidence = Path(args.evidence_dir).resolve()
    # Never overwrite prior receipts; runner-owned evidence roots may already exist.
    evidence.mkdir(parents=True, exist_ok=True)
    import tempfile
    work = Path(tempfile.mkdtemp(prefix="ar5-readers-", dir=evidence))
    executable = Path(args.probe).resolve()
    receipt = {**plan, "status": "running", "work": str(work), "processes": [], "binary_sha256_before": sha(executable),
               "wrapper_sha256": sha(__file__), "started": time.time()}
    write_json(work / "plan.json", plan)
    def run(label, arguments):
        record = {"label": label, "argv": [str(executable), *arguments], "cwd": str(work), "started": time.time()}
        receipt["processes"].append(record)
        with (work / (label + ".stdout.log")).open("wb") as stdout, (work / (label + ".stderr.log")).open("wb") as stderr:
            process = subprocess.Popen(record["argv"], cwd=work, stdout=stdout, stderr=stderr)
            record["pid"] = process.pid
            try:
                record["exit_code"] = process.wait(timeout=args.timeout)
            except subprocess.TimeoutExpired:
                record["timeout"] = True
                process.kill()
                record["exit_code"] = process.wait()
                raise
            finally:
                record["ended"] = time.time()
        require(record["exit_code"] == 0, f"{label} exit={record['exit_code']}; see raw logs")
        return (work / (label + ".stdout.log")).read_text(encoding="utf-8")
    try:
        identity = json.loads(run("identity", ["--identity"]))
        require(identity.get("source_fingerprint") == args.expected_source, "candidate source fingerprint mismatch")
        require(identity.get("probe_sha256") == plan["probe_sha256"], "probe source SHA mismatch")
        require(type(identity.get("geant4_version_number")) is int and identity["geant4_version_number"] > 0, "missing SDK identity")
        require(bool(identity.get("compiler")) and bool(identity.get("compiler_version")), "missing build identity")
        receipt["identity"] = identity
        log = run("probe", [str(work / "native")])
        result = json.loads((work / "native" / "results.json").read_text(encoding="utf-8"))
        validate_result(result, identity)
        require(f"{result['check_count']} checks; 0 failed" in log, "raw count marker mismatch")
        receipt["check_count"] = result["check_count"]
        receipt["status"] = "component_pass"
        return_code = 0
    except Exception as error:
        receipt["status"] = "failed"
        receipt["error"] = f"{type(error).__name__}: {error}"
        return_code = 1
    finally:
        # Identity errors must not prevent raw-file enumeration and final receipt.
        try:
            receipt["binary_sha256_after"] = sha(executable)
            require(receipt["binary_sha256_after"] == receipt["binary_sha256_before"], "binary changed during probe")
            require(sha(PROBE_SOURCE) == plan["probe_sha256"], "probe source changed during probe")
            require(sha(__file__) == receipt["wrapper_sha256"], "wrapper changed during probe")
        except Exception as error:
            receipt.setdefault("finalization_errors", []).append(str(error))
            receipt["status"] = "failed"
            return_code = 1
        files = {}
        for path in sorted(work.rglob("*")):
            if path.is_file() and path.name != "receipt.json":
                try: files[path.relative_to(work).as_posix()] = {"sha256": sha(path), "bytes": path.stat().st_size}
                except OSError as error:
                    receipt.setdefault("finalization_errors", []).append(str(error))
                    receipt["status"] = "failed"
                    return_code = 1
        receipt["files"] = files
        receipt["ended"] = time.time()
        write_json(work / "receipt.json", receipt)
        print(json.dumps({"status": receipt["status"], "receipt": str(work / "receipt.json")}, ensure_ascii=False))
    return return_code


if __name__ == "__main__":
    raise SystemExit(main())
