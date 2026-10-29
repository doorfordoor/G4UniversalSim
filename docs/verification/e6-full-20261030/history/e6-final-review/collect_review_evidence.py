"""Read existing E6 evidence; write only this final-review directory."""
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path.cwd()
OUT = Path(__file__).resolve().parent


def read(path):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


frozen = read("out/verification/e6-ci/frozen-case-manifest.json")
reports = []
for name in ("e6-foundation", "e6-backend-first", "e6-backend-second", "e6-specialized"):
    for path in (ROOT / "out/verification" / name).glob("*/report.json"):
        report = json.loads(path.read_text(encoding="utf-8"))
        hashes = []
        for case in report["results"]:
            if case.get("log"):
                logfile = ROOT / case["log"]
                hashes.append({"case": case["name"], "sha256_matches": logfile.is_file() and sha(logfile) == case.get("log_sha256")})
        gate = subprocess.run([sys.executable, "-B", "scripts/check_report_evidence.py", "--report", str(path)],
                              cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
        (OUT / f"{name}-gate.log").write_text(gate.stdout + gate.stderr, encoding="utf-8", newline="\n")
        reports.append({"path": str(path.relative_to(ROOT)), "git_head": report["git_head"], "git_dirty": report["git_dirty"],
                        "source_matches_frozen": report["source_fingerprint"] == frozen["source_fingerprint"],
                        "tests_match_frozen": report["tests_content_fingerprint"] == frozen["tests_content_fingerprint"],
                        "statuses": dict(Counter(case["status"] for case in report["results"])),
                        "assertions_executed_total": report["assertions_executed_total"],
                        "cases_with_zero_assertions": report["cases_with_zero_assertions"],
                        "raw_log_hash_checks": hashes, "strict_gate_exit_code": gate.returncode})
types_review = read("out/verification/e6-independent/types-fix-review.json")
schema_review = read("out/verification/e6-independent-schema-candidate/review.json")
case_reports = {}
for name in ("e6-schema-baseline04", "e6-schema-candidate"):
    value = read(f"out/verification/{name}/cases.json")
    case_reports[name] = {"case_count": len(value["cases"]), "executable": value["executable"], "baseline": value["baseline"]}
result = {
    "audited_at_utc": datetime.now(timezone.utc).isoformat(),
    "git_head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
    "tracked_status": subprocess.check_output(["git", "status", "--short", "--untracked-files=no"], cwd=ROOT, text=True).strip(),
    "frozen": {"head": frozen["head_sha"], "source_fingerprint": frozen["source_fingerprint"],
               "tests_content_fingerprint": frozen["tests_content_fingerprint"],
               "case_counts": {key: len(value) for key, value in frozen["profiles"].items()}},
    "reports": reports,
    "schema_differential_records": case_reports,
    "independent_schema_probes": schema_review,
    "independent_type_review": {"original_cases_rejected": sum(bool(fact.get("now_rejected")) for fact in types_review["facts"]),
                                 "old_format_combinations_checked": sum("input_version" in fact for fact in types_review["facts"])},
    "ci_checkpoint_at_review": read("out/verification/e6-ci/checkpoint.json"),
    "scope": "Read-only scope/evidence review; not a new whole-stage test run or stage-closure decision",
}
(OUT / "evidence-summary.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"head": result["git_head"], "tracked_status": result["tracked_status"],
                  "reports": [{"path": item["path"], "statuses": item["statuses"], "gate": item["strict_gate_exit_code"]} for item in reports]}, indent=2))
