"""Primary-reviewer-only native consumption checks AFTER source/binary freeze.

Consumes test_ar1_generators.py --out artifacts plus the optional original before/
capture. Never builds, uses a formal runner, or BeamOn. Each case is a fresh native
process executing /run/initialize only, with a dedicated output directory.
The reviewer must separately verify the executable's build-to-source identity;
an executable SHA is identity evidence, not proof of which source built it.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess

from test_ar1_generators import ROOT, digest, fingerprints, require, write_json


def backend_sources():
    paths = ["src/Geometry/GeometryManager.cc", "src/Geometry/GeometryConfig.cc",
             "src/Geometry/VolumeBuilder.cc", "include/Geometry/GeometryManager.hh", "main.cc",
             "scripts/test_ar1_generator_native.py"]
    return {p: digest(ROOT / p) for p in paths}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", required=True, type=Path, help="static suite output directory")
    parser.add_argument("--baseline", type=Path, help="original before/ evidence; includes expected legacy failures")
    parser.add_argument("--exe", required=True, type=Path)
    parser.add_argument("--expected-exe-sha256", required=True)
    parser.add_argument("--out", required=True, type=Path, help="fresh directory for native logs and summaries")
    parser.add_argument("--timeout", type=int, default=180)
    args = parser.parse_args()
    exe = args.exe.resolve()
    require(digest(exe) == args.expected_exe_sha256.lower(), "executable SHA mismatch")
    cases = args.cases.resolve()
    static = json.loads((cases / "results.json").read_text(encoding="utf-8"))
    require(not static["failed"], "static suite has failures")
    source_before = fingerprints()
    require(static["source_after"] == source_before, "static artifacts do not match current generator/test sources")
    manifest = json.loads((cases / "manifest.json").read_text(encoding="utf-8"))
    for name, expected in manifest.items():
        require(digest(cases / name) == expected, f"static artifact drift: {name}")
    baseline = args.baseline.resolve() if args.baseline else None
    baseline_manifest = json.loads((baseline / "manifest.json").read_text(encoding="utf-8")) if baseline else {}
    for name, expected in baseline_manifest.items():
        require(digest(baseline / name) == expected, f"baseline artifact drift: {name}")
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    macro = out / "initialize_only.mac"
    macro.write_text("/run/initialize\n", encoding="utf-8")
    geometry_before = backend_sources()
    identity = {"exe": str(exe), "exe_sha256": digest(exe), "generator_sources": source_before,
                "backend_sources": geometry_before, "static_manifest_sha256": digest(cases / "manifest.json"),
                "macro_sha256": digest(macro), "boundary": "initialization only; no events or physics validation"}
    write_json(out / "identity-before.json", identity)
    jobs = [(r["case"], cases / r["case"], None) for r in static["cases"]
            if r["passed"] and (cases / r["case"] / "main.ini").is_file()]
    if baseline:
        # These must remain rejected by the backend. Match the specific reason,
        # not merely any nonzero process exit (DLL/data/setup failure cannot pass).
        jobs += [(f"legacy_{name}", baseline / name, message) for name, message in [
            ("zero", "contains no copies"), ("tiny", "contains no copies"),
            ("slices_7", "replica_count * replica_width"), ("slices_11", "replica_count * replica_width")]]
    records = []
    for label, cwd, rejection in jobs:
        target = out / label
        target.mkdir()
        cmd = [str(exe), "--config", "main.ini", "--macro", str(macro),
               "--output", str(target / "output"), "--threads", "1"]
        record = {"case": label, "argv": cmd, "cwd": str(cwd), "expected_rejection": rejection}
        write_json(target / "command.json", record)
        try:
            proc = subprocess.run(cmd, cwd=cwd, capture_output=True, timeout=args.timeout)
            (target / "stdout.log").write_bytes(proc.stdout)
            (target / "stderr.log").write_bytes(proc.stderr)
            log = (proc.stdout + proc.stderr).decode("utf-8", errors="replace")
            summary_path = target / "output/run_summary.txt"
            summary = {}
            if summary_path.is_file():
                for line in summary_path.read_text(encoding="utf-8-sig").splitlines():
                    if "=" in line:
                        key, value = line.split("=", 1)
                        summary[key.strip()] = value.strip()
            if rejection:
                passed = proc.returncode != 0 and rejection in log
            else:
                passed = (proc.returncode == 0 and "G4Exception-START" not in log
                          and summary.get("status") == "completed"
                          and summary.get("initialized") == "true"
                          and summary.get("macro_execution_status") == "completed"
                          and summary.get("run_count") == "0")
            record.update(exit_code=proc.returncode, passed=passed, summary=summary,
                          stdout_sha256=digest(target / "stdout.log"), stderr_sha256=digest(target / "stderr.log"))
        except subprocess.TimeoutExpired as exc:
            (target / "stdout.log").write_bytes(exc.stdout or b"")
            (target / "stderr.log").write_bytes(exc.stderr or b"")
            record.update(passed=False, error="native process timeout; original logs retained")
        records.append(record)
        write_json(out / "results.json", {"scope": "native initialization only", "cases": records})
        print(f"{'PASS' if record['passed'] else 'FAIL'} {label}", flush=True)
    unchanged = (fingerprints() == source_before and backend_sources() == geometry_before
                 and digest(exe) == identity["exe_sha256"])
    for name, expected in manifest.items():
        unchanged = unchanged and digest(cases / name) == expected
    for name, expected in baseline_manifest.items():
        unchanged = unchanged and digest(baseline / name) == expected
    write_json(out / "identity-after.json", {"sources_and_inputs_unchanged": unchanged, "generator_sources": fingerprints(),
                                             "backend_sources": backend_sources(), "exe_sha256": digest(exe)})
    write_json(out / "results.json", {"scope": "native initialization only; no physics validation", "cases": records,
                                      "sources_and_inputs_unchanged": unchanged})
    return 0 if unchanged and all(r["passed"] for r in records) else 1


if __name__ == "__main__":
    raise SystemExit(main())
