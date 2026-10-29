"""Plan or publish a new, byte-verified E6 evidence archive. No network access.

Default is planning only. --execute requires passing final Windows/CI evidence.
An existing destination is never written; --verify-existing audits it in place.
Build binaries, ZIP containers, image/media files, credentials and CI selfchecks
are excluded. Official ZIP digests remain in the copied CI metadata; original
ZIP bytes are checked before publication and stay in the source evidence root.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[2]
TEXT_SUFFIXES = {".json", ".md", ".log", ".txt", ".csv", ".ini", ".mac", ".py", ".yml", ".yaml"}
FORBIDDEN_COMPONENTS = {".git", ".ssh", ".codex", "credentials", "secrets", "__pycache__"}
HISTORY_ROOTS = (
    "e6-backend-first", "e6-backend-second", "e6-foundation", "e6-specialized", "e6-full-windows",
    "e6-independent", "e6-independent-schema-baseline", "e6-independent-schema-candidate",
    "e6-main-review", "e6-schema-baseline04", "e6-schema-candidate", "e6-startpage-modal", "e6-final-review",
)
SECRET_PATTERNS = {
    "bearer authorization": re.compile(r"Authorization\s*[:=]\s*[\"']?Bearer\s+[A-Za-z0-9._~+/=-]{12,}", re.I),
    "API credential": re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    "assigned credential": re.compile(r"\b(?:OPENAI_API_KEY|ANTHROPIC_API_KEY|DEEPSEEK_API_KEY|GITHUB_TOKEN|GH_TOKEN)[\"']?\s*[:=]\s*[\"']?[A-Za-z0-9_-]{16,}", re.I),
    "signed download URL": re.compile(r"(?:X-Amz-Signature|X-Goog-Signature|[?&]sig)=[A-Za-z0-9%+/=_-]{12,}", re.I),
    "private key": re.compile(r"-----BEGIN (?:[A-Z ]+ )?PRIVATE KEY-----"),
}


def utc():
    return datetime.now(timezone.utc).isoformat()


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_new(path, raw):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def safe_relative(root, value):
    relative = PurePosixPath(value)
    if relative.is_absolute() or not relative.parts or any(part in {"..", "."} for part in relative.parts):
        raise ValueError("Unsafe archive member path")
    path = root.joinpath(*relative.parts)
    if not path.resolve().is_relative_to(root.resolve()):
        raise ValueError("Archive member escapes destination")
    return path


def check_text(raw, path):
    if b"\x00" in raw:
        raise ValueError(f"Binary or NUL content refused: {path}")
    text = raw.decode("utf-8")
    for label, pattern in SECRET_PATTERNS.items():
        if pattern.search(text):
            # Never include matched secret content in diagnostics.
            raise ValueError(f"Potential {label} refused in {path}")


def build_plan(options):
    target = options.destination.absolute()
    selected, excluded, missing, blockers = {}, [], [], []
    roots = []
    required_reports = []
    plain_markdown = {path.absolute() for path in options.plain_markdown_source}
    plain_markdown_seen = set()

    def add_file(source, relative, category):
        source = Path(source).absolute()
        if not source.is_file():
            missing.append(str(source)); return
        # The authorized workspace itself lives below .codex; evaluate only
        # selected archive members, never trusted ancestor folder names.
        member_parts = PurePosixPath(str(relative).replace("\\", "/")).parts
        if source.is_symlink() or any(part.lower() in FORBIDDEN_COMPONENTS or "selfcheck" in part.lower() for part in member_parts):
            excluded.append({"path": str(source), "reason": "link, private, or historical selfcheck path"}); return
        if source.suffix.lower() not in TEXT_SUFFIXES:
            excluded.append({"path": str(source), "reason": "binary/media/container or unapproved extension"}); return
        raw = source.read_bytes()
        check_text(raw, source)
        key = PurePosixPath(relative).as_posix()
        original_key = None
        if source in plain_markdown:
            if source.suffix.lower() != ".md" or not key.endswith(".md"):
                raise ValueError("Plain Markdown mapping requires a selected .md source/member")
            original_key = key
            key += ".txt"
            plain_markdown_seen.add(source)
        safe_relative(target, key)
        item = {"source": str(source), "archive_path": key, "size": len(raw), "sha256": digest(raw), "category": category}
        if original_key is not None:
            item.update(original_archive_path=original_key, rendering="literal_text",
                        archive_path_reason="Preserve original evidence bytes; embedded links assume its original publication location")
        if key in selected and selected[key] != item:
            raise ValueError(f"Conflicting archive destination: {key}")
        selected[key] = item

    def add_tree(source, relative, category, *, required=False):
        source = Path(source).absolute()
        if not source.is_dir():
            if required: missing.append(str(source))
            return
        if target.resolve().is_relative_to(source.resolve()) or source.resolve().is_relative_to(target.resolve()):
            raise ValueError("Archive destination and selected source tree must not contain one another")
        roots.append({"source": str(source), "archive_prefix": relative, "category": category})
        for path in sorted(source.rglob("*")):
            if path.is_file():
                add_file(path, str(PurePosixPath(relative) / path.relative_to(source).as_posix()), category)

    for index, report in enumerate(options.windows_report, 1):
        report = report.absolute()
        if report.name != "report.json":
            raise ValueError("Windows report argument must name the original report.json")
        prefix = f"windows/final-{index}"
        required_reports.append(f"{prefix}/{report.name}")
        if not report.is_file():
            missing.append(str(report))
        add_tree(report.parent, prefix, "accepted_windows", required=True)
    add_tree(options.ci_root, "ci", "accepted_ci", required=True)
    for name in HISTORY_ROOTS:
        add_tree(ROOT / "out/verification" / name, f"history/{name}", "historical")
    old_ci = ROOT / "out/verification/e6-ci"
    if old_ci.resolve() != options.ci_root.resolve():
        add_tree(old_ci, "history/cb837e6-ci", "historical")
    historical_rounds = []
    for index, source in enumerate(options.historical_ci_root, 1):
        if source.resolve() == options.ci_root.resolve():
            raise ValueError("A final CI root cannot simultaneously be a historical CI round")
        prefix = f"history/ci-round-{index}-{source.name}"
        add_tree(source, prefix, "historical_ci", required=True)
        summary = source / "ci-evidence.json"
        record = read_json(summary) if summary.is_file() else {}
        historical_rounds.append({"source": str(source.absolute()), "category": "historical_ci", "archive_prefix": prefix,
                                  "recorded_head": record.get("head_sha"), "recorded_status": record.get("status"),
                                  "recorded_complete": record.get("complete"), "reports": len(record.get("reports", []))})
        if not summary.is_file():
            blockers.append("Historical CI round has no collected summary: " + str(source))
    for index, source in enumerate(options.historical_windows_root, 1):
        if any(report.absolute().is_relative_to(source.absolute()) for report in options.windows_report):
            raise ValueError("Final Windows report cannot also belong to a historical Windows round")
        prefix = f"history/windows-round-{index}-{source.name}"
        add_tree(source, prefix, "historical_windows", required=True)
        records = []
        for report in sorted(source.rglob("report.json")) if source.is_dir() else []:
            value = read_json(report)
            records.append({"report": str(report), "head": value.get("git_head"), "profile": value.get("profile"),
                            "statuses": [case.get("status") for case in value.get("results", [])]})
        historical_rounds.append({"source": str(source.absolute()), "category": "historical_windows", "archive_prefix": prefix,
                                  "reports": records})
        if not records:
            blockers.append("Historical Windows round is still awaiting its terminal report: " + str(source))
    for index, report in enumerate(options.historical_report, 1):
        add_tree(report.absolute().parent, f"history/explicit-report-{index}", "historical", required=True)
    for index, source in enumerate(options.include_root, 1):
        add_tree(source, f"additional/{index}-{source.name}", "additional", required=True)
    for index, source in enumerate(options.include_file, 1):
        add_file(source, f"additional-files/{index}-{source.name}", "additional")
    if options.root_readme is not None:
        add_file(options.root_readme, "README.md", "active_index")
    add_file(ROOT / "out/collab/e6-startpage-blocked-process.json", "history/startpage-blocked-process.json", "historical")
    add_file(ROOT / "out/collab/e6-deepseek-design.json", "design/deepseek-response.json", "design")
    add_file(ROOT / "docs/collab/outbox/20261029-deepseek-e6-design.md", "design/deepseek-outbox-receipt.md", "design")
    add_file(ROOT / "scripts/check_report_evidence.py", "tools/check_report_evidence.py", "verification_tool")
    for index, report in enumerate(options.baseline_report, 1):
        add_tree(report.absolute().parent, f"baseline/{index}", "baseline", required=True)

    ci_file = options.ci_root / "ci-evidence.json"
    frozen_file = options.ci_root / "frozen-case-manifest.json"
    ci = read_json(ci_file) if ci_file.is_file() else {}
    frozen = read_json(frozen_file) if frozen_file.is_file() else {}
    if not ci_file.is_file(): blockers.append("Final CI evidence summary does not exist")
    if ci.get("status") != "passed" or not ci.get("complete"):
        blockers.append("Final CI evidence is not complete/passed")
    if len(ci.get("artifacts", [])) != 4 or len(ci.get("reports", [])) != 12:
        blockers.append("Final CI must contain four artifact identities and twelve report gates")
    if not frozen: blockers.append("Final frozen case manifest is absent")
    expected_head = options.expected_head or frozen.get("head_sha")
    if not expected_head or frozen.get("head_sha") != expected_head:
        blockers.append("Final frozen head does not match the requested final identity")
    elif not ci:
        blockers.append("Final CI identity is unavailable until its summary is collected")
    elif ci.get("head_sha") != expected_head:
        blockers.append("Final CI head does not match the requested final identity")
    for report in options.windows_report:
        if not report.is_file():
            continue
        windows = read_json(report)
        if windows.get("profile") != "all" or windows.get("git_dirty") is not False:
            blockers.append("Final Windows report must be clean profile=all")
        if any(item.get("status") != "pass" for item in windows.get("results", [])):
            blockers.append("Final Windows report contains failed/skipped cases")
        if windows.get("git_head") != expected_head:
            blockers.append("Final Windows report head mismatch")
        for key in ("source_fingerprint", "tests_content_fingerprint"):
            if windows.get(key) != frozen.get(key):
                blockers.append("Final Windows " + key + " mismatch")
    artifact_checks = []
    for item in ci.get("artifacts", []):
        archive = options.ci_root / (item["name"] + ".zip")
        actual = "sha256:" + digest(archive.read_bytes()) if archive.is_file() else None
        match = actual == item.get("official_digest") == item.get("sha256")
        artifact_checks.append({"name": item["name"], "official_digest": item.get("official_digest"), "source_zip_digest": actual, "matches": match})
        if not match: blockers.append(f"Source ZIP official digest mismatch: {item['name']}")
        if match:
            checked_members = 0
            with zipfile.ZipFile(archive) as bundle:
                for member in bundle.infolist():
                    if member.is_dir(): continue
                    extracted = safe_relative(options.ci_root / item["name"], member.filename)
                    if not extracted.is_file() or digest(extracted.read_bytes()) != digest(bundle.read(member)):
                        blockers.append("CI extracted bytes differ from original ZIP: " + item["name"] + "/" + member.filename)
                    checked_members += 1
            artifact_checks[-1]["extracted_members_checked"] = checked_members
    if plain_markdown_seen != plain_markdown:
        raise ValueError("Plain Markdown mapping names a source not selected in the archive")
    return {"format": "e6_evidence_archive_plan_v1", "created_utc": utc(), "destination": str(target),
            "repository_head_at_plan": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
            "expected_head": expected_head, "frozen": frozen, "source_roots": roots,
            "required_windows_reports": required_reports,
            "baseline_reports": [f"baseline/{index}/{path.name}" for index, path in enumerate(options.baseline_report, 1)],
            "files": sorted(selected.values(), key=lambda item: item["archive_path"]),
            "historical_rounds": historical_rounds,
            "excluded": excluded, "missing_sources": sorted(set(missing)), "preflight_blockers": blockers,
            "artifact_zip_digest_checks": artifact_checks,
            "policy": "Byte copies, exclusive new destination, no source edits; ZIP bytes stay at source, official identities are retained; archival does not establish physics or visible UI completion"}


def report_gates(folder, plan, *, publish_logs=False):
    gate_tool = folder / "tools/check_report_evidence.py"
    required = set(plan["required_windows_reports"])
    reports = [item for item in plan["files"] if PurePosixPath(item["archive_path"]).name == "report.json"]
    results = []
    found = set()
    for index, item in enumerate(reports):
        relative = item["archive_path"]
        report = safe_relative(folder, relative)
        data = read_json(report)
        release = item["category"] in {"accepted_windows", "accepted_ci"}
        if release: found.add(relative)
        for case in data.get("results", []):
            log = case.get("log")
            if not log:
                if case.get("status") == "pass": raise ValueError(f"Passing archived case has no log: {relative}/{case['name']}")
                continue
            # Require an archive-local copy: never let the checker silently
            # succeed using the original absolute log reference.
            name = str(log).replace("\\", "/").rsplit("/", 1)[-1]
            choices = [report.parent / name, report.parent / "logs" / name]
            local = next((path for path in choices if path.is_file()), None)
            if local is None or digest(local.read_bytes()) != case.get("log_sha256"):
                raise ValueError(f"Missing or modified archive-local log: {relative}/{case['name']}")
        command = [sys.executable, "-B", str(gate_tool), "--report", str(report)]
        gate = subprocess.run(command, cwd=folder, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
        logname = f"verification/gate-{index:03d}.log"
        if publish_logs: write_new(folder / logname, (gate.stdout + gate.stderr).encode("utf-8"))
        if release:
            if gate.returncode: raise ValueError(f"Release report strict gate failed: {relative}")
            for key in ("source_fingerprint", "tests_content_fingerprint"):
                if data.get(key) != plan["frozen"].get(key): raise ValueError(f"Release {key} mismatch: {relative}")
            if data.get("git_head") != plan["expected_head"] or data.get("tracked_source_gate") != "pass":
                raise ValueError(f"Release head/tracked-source identity mismatch: {relative}")
            if item["category"] == "accepted_windows":
                if data.get("profile") != "all" or data.get("git_dirty") is not False:
                    raise ValueError(f"Final Windows report must be clean profile=all: {relative}")
                expected_cases = {case for cases in plan["frozen"].get("profiles", {}).values() for case in cases}
            else:
                expected_cases = set(plan["frozen"].get("profiles", {}).get(data.get("profile"), []))
            if {case["name"] for case in data["results"]} != expected_cases:
                raise ValueError(f"Release case set differs from freeze: {relative}")
        results.append({"report": relative, "category": item["category"], "strict_gate_exit_code": gate.returncode,
                        "all_pass": all(case["status"] == "pass" for case in data.get("results", [])),
                        "gate_log": logname if publish_logs else None,
                        "meaning": "release evidence" if release else "retained original history, not release acceptance"})
    if not required <= found: raise ValueError("Requested final Windows report is absent from archive")
    if len([item for item in results if item["category"] == "accepted_ci"]) != 12:
        raise ValueError("Archive must contain exactly twelve final CI reports")
    baseline_results = []
    for index, windows in enumerate(plan["required_windows_reports"]):
        for baseline in plan["baseline_reports"]:
            command = [sys.executable, "-B", str(gate_tool), "--report", str(folder / windows), "--baseline", str(folder / baseline)]
            gate = subprocess.run(command, cwd=folder, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
            if gate.returncode: raise ValueError("Final Windows same-probe baseline gate failed")
            name = f"verification/baseline-{index:03d}-{len(baseline_results):03d}.log"
            if publish_logs: write_new(folder / name, (gate.stdout + gate.stderr).encode("utf-8"))
            baseline_results.append({"report": windows, "baseline": baseline, "exit_code": gate.returncode})
    return {"reports": results, "baseline_comparisons": baseline_results}


def verify_existing(folder):
    if not (folder / "archive-complete.json").is_file():
        raise ValueError("Existing archive has no completion marker; it may be partial and will not be overwritten")
    plan = read_json(folder / "archive-manifest.json")
    completion = read_json(folder / "archive-complete.json")
    if digest((folder / "archive-manifest.json").read_bytes()) != completion["manifest_sha256"]:
        raise ValueError("Archive manifest digest mismatch")
    if digest((folder / "archive-verification.json").read_bytes()) != completion["verification_sha256"]:
        raise ValueError("Archive verification record digest mismatch")
    for item in plan["files"]:
        path = safe_relative(folder, item["archive_path"])
        if path.is_symlink() or not path.is_file() or path.stat().st_size != item["size"] or digest(path.read_bytes()) != item["sha256"]:
            raise ValueError(f"Archive byte mismatch: {item['archive_path']}")
    verified = report_gates(folder, plan)
    return {"status": "verified", "files": len(plan["files"]), "report_gates": verified}


def execute(plan):
    target = Path(plan["destination"])
    if target.exists() or os.path.lexists(target): raise FileExistsError("Archive destination already exists; use --verify-existing; no overwrite")
    if plan["missing_sources"] or plan["preflight_blockers"]:
        raise ValueError("Archive preflight incomplete; review the plan's missing_sources/preflight_blockers")
    # Exclusive directory creation is the reservation point. A failure leaves
    # an explicitly incomplete new directory, never overwrites or deletes data.
    target.mkdir(parents=False, exist_ok=False)
    write_new(target / "archive-started.json", json_bytes({"started_utc": utc(), "expected_head": plan["expected_head"]}))
    write_new(target / "archive-manifest.json", json_bytes(plan))
    for item in plan["files"]:
        source = Path(item["source"])
        raw = source.read_bytes()
        if len(raw) != item["size"] or digest(raw) != item["sha256"]:
            raise ValueError(f"Evidence source changed after plan: {source}")
        destination = safe_relative(target, item["archive_path"])
        write_new(destination, raw)
        if digest(destination.read_bytes()) != item["sha256"] or digest(source.read_bytes()) != item["sha256"]:
            raise ValueError(f"Byte-copy/source stability check failed: {item['archive_path']}")
    gates = report_gates(target, plan, publish_logs=True)
    verification = {"verified_utc": utc(), "files_sha256_matched": len(plan["files"]), **gates}
    write_new(target / "archive-verification.json", json_bytes(verification))
    write_new(target / "archive-complete.json", json_bytes({"completed_utc": utc(),
              "manifest_sha256": digest((target / "archive-manifest.json").read_bytes()),
              "verification_sha256": digest((target / "archive-verification.json").read_bytes())}))
    return verify_existing(target)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--windows-report", type=Path, action="append", default=[])
    parser.add_argument("--ci-root", type=Path)
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--expected-head")
    parser.add_argument("--baseline-report", type=Path, action="append", default=[])
    parser.add_argument("--historical-report", type=Path, action="append", default=[])
    parser.add_argument("--historical-ci-root", type=Path, action="append", default=[])
    parser.add_argument("--historical-windows-root", type=Path, action="append", default=[])
    parser.add_argument("--include-root", type=Path, action="append", default=[])
    parser.add_argument("--include-file", type=Path, action="append", default=[])
    parser.add_argument("--plain-markdown-source", type=Path, action="append", default=[])
    parser.add_argument("--root-readme", type=Path)
    parser.add_argument("--plan-output", type=Path)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--execute", action="store_true")
    mode.add_argument("--verify-existing", action="store_true")
    options = parser.parse_args()
    if options.verify_existing:
        print(json.dumps(verify_existing(options.destination.absolute()), ensure_ascii=False, indent=2)); return
    if not options.windows_report or options.ci_root is None:
        parser.error("--windows-report and --ci-root are required to plan or publish")
    plan = build_plan(options)
    if options.plan_output:
        write_new(options.plan_output, json_bytes(plan))
    if options.execute:
        result = execute(plan)
    else:
        result = {"mode": "plan_only", "destination": plan["destination"], "file_count": len(plan["files"]),
                  "source_roots": plan["source_roots"], "excluded_files": len(plan["excluded"]),
                  "missing_sources": plan["missing_sources"], "preflight_blockers": plan["preflight_blockers"],
                  "plan_output": str(options.plan_output) if options.plan_output else None,
                  "notice": "No evidence archive created. --execute never overwrites an existing destination."}
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
