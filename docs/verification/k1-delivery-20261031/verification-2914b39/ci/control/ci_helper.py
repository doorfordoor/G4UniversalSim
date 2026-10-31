"""Offline CI evidence preparation, collection and byte/baseline auditing.

Only writes below this file's directory. No downloads, environment credentials,
GitHub operations, artifact code execution, or changes to source evidence.
The self-test uses F5 originals; it cannot establish a K1 CI result.
"""
from __future__ import annotations

import argparse
import copy
import ctypes
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import re
import shutil
import stat
import sys
import tempfile
import zipfile

sys.dont_write_bytecode = True
BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[3]
F5 = ROOT / "docs/verification/f5-final-20261031/ci"
PROFILES = ("static", "gui", "backend", "integration")
DEFAULT_MATRIX = {
    "linux-evidence-11.3.2": {"platform": "Linux", "geant4_version_number": 1132, "profiles": list(PROFILES)},
    "linux-evidence-11.4.3": {"platform": "Linux", "geant4_version_number": 1143, "profiles": list(PROFILES)},
    "m0-report-windows-latest": {"platform": "Windows", "geant4_version_number": None, "profiles": ["static", "gui"]},
    "m0-report-ubuntu-latest": {"platform": "Linux", "geant4_version_number": None, "profiles": ["static", "gui"]},
}
LIMIT_ZIP = 512 * 1024 * 1024
LIMIT_MEMBER = 128 * 1024 * 1024
LIMIT_EXPANDED = 1024 * 1024 * 1024
HEX = re.compile(r"[0-9a-f]{64}\Z")
HEAD = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})\Z")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True, indent=2) + "\n").encode("utf-8")


def decode(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, "Duplicate JSON object key")
            result[key] = value
        return result
    def invalid(value):
        raise ValueError("Non-finite JSON number")
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=invalid)


def no_links(path):
    path = Path(path).absolute()
    for part in (path, *path.parents):
        require(not part.is_symlink(), f"Linked evidence path is unsupported: {part}")
        require(not (hasattr(part, "is_junction") and part.is_junction()), f"Junction evidence path: {part}")
        if part.exists():
            require(not getattr(part.lstat(), "st_file_attributes", 0) & 0x400, f"Reparse evidence path: {part}")
    return Path(os.path.abspath(path))


def read(path, limit=LIMIT_MEMBER):
    path = no_links(path)
    require(path.is_file() and path.stat().st_size <= limit, f"Missing/oversize evidence: {path}")
    with path.open("rb") as handle:
        raw = handle.read(limit + 1)
    require(len(raw) <= limit, f"Oversize evidence: {path}")
    return raw


def load(path):
    return decode(read(path))


def writable(path):
    path = no_links(path)
    require(path.is_relative_to(BASE) and path != BASE, "All output must stay below out/collab/k1-ci")
    return path


def save(path, raw):
    path = writable(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())


def save_json(path, value):
    save(path, json_bytes(value))


def safe_member(name):
    require(isinstance(name, str) and name and "\\" not in name and ":" not in name,
            "Ambiguous ZIP member name")
    require(not any(ord(c) < 32 for c in name), "Control character in ZIP member")
    require(not PurePosixPath(name).is_absolute() and not PureWindowsPath(name).drive,
            "Absolute ZIP member")
    value = name[:-1] if name.endswith("/") else name
    parts = value.split("/")
    reserved = {"CON", "PRN", "AUX", "NUL", *{f"COM{i}" for i in range(10)}, *{f"LPT{i}" for i in range(10)}}
    require(all(p not in {"", ".", ".."} and not p.endswith((" ", ".")) and p.split(".")[0].upper() not in reserved for p in parts),
            "Unsafe/escaping ZIP member")
    return value


def zip_contents(raw):
    seen, result, files = set(), {}, set()
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        infos = archive.infolist()
        require(len(infos) <= 100000 and sum(item.file_size for item in infos) <= LIMIT_EXPANDED,
                "ZIP expansion limit exceeded")
        for item in infos:
            name = safe_member(item.filename)
            folded = name.casefold()
            require(folded not in seen, "Duplicate/case-colliding ZIP member")
            seen.add(folded)
            mode = item.external_attr >> 16
            require(not stat.S_ISLNK(mode), "ZIP symlink is unsupported")
            require(not stat.S_IFMT(mode) or stat.S_ISREG(mode) or stat.S_ISDIR(mode), "Non-file ZIP entry")
            require(not item.flag_bits & 1, "Encrypted ZIP is unsupported")
            require(item.file_size <= LIMIT_MEMBER, "ZIP member size limit exceeded")
            if item.is_dir():
                continue
            require(not any('/'.join(name.split('/')[:i]).casefold() in files for i in range(1, len(name.split('/')))),
                    "ZIP file/directory collision")
            payload = archive.read(item)
            require(len(payload) == item.file_size, "ZIP expanded size mismatch")
            result[name] = payload
            files.add(folded)
        for name in result:
            require(not any(other.casefold().startswith(name.casefold() + "/") for other in result),
                    "ZIP file/directory collision")
    return result


def frozen_contract(path, head):
    frozen = load(path)
    require(HEAD.fullmatch(head or "") and frozen.get("head_sha") == head, "Frozen manifest/head mismatch")
    for key in ("source_fingerprint", "tests_content_fingerprint"):
        require(HEX.fullmatch(frozen.get(key, "")), "Missing frozen fingerprint: " + key)
    profiles = frozen.get("profiles")
    require(isinstance(profiles, dict) and set(profiles) == set(PROFILES), "Frozen profile coverage mismatch")
    names = []
    for profile, cases in profiles.items():
        require(isinstance(cases, list) and cases and all(isinstance(c, str) and c for c in cases), "Invalid frozen case list")
        names.extend(cases)
    require(len(names) == len(set(names)), "Duplicate frozen case name")
    return {key: frozen[key] for key in ("head_sha", "source_fingerprint", "tests_content_fingerprint", "profiles")}


def metadata_artifacts(paths, head, matrix):
    found, sources = {}, []
    for index, path in enumerate(paths):
        raw = read(path)
        metadata = decode(raw)
        items = metadata.get("artifacts")
        require(isinstance(items, list) and type(metadata.get("total_count")) is int
                and metadata["total_count"] == len(items), "Artifact metadata is incomplete/paginated")
        source = {"path": str(no_links(path)), "sha256": sha(raw), "copy": f"artifact-metadata-{index}.json"}
        sources.append(source)
        for item in items:
            name = item.get("name")
            if name not in matrix:
                continue
            require(name not in found, "Duplicate official artifact name")
            require(item.get("expired") is False and re.fullmatch(r"sha256:[0-9a-f]{64}", item.get("digest", "")),
                    "Missing official artifact digest/expiry declaration")
            require(type(item.get("size_in_bytes")) is int and 0 < item["size_in_bytes"] <= LIMIT_ZIP,
                    "Invalid official artifact size")
            run = item.get("workflow_run", {})
            require(run.get("head_sha") == head and type(run.get("id")) is int and type(item.get("id")) is int,
                    "Official artifact belongs to a different head/run")
            found[name] = {"name": name, "official_digest": item["digest"], "bytes": item["size_in_bytes"],
                           "artifact_id": item["id"], "run_id": run["id"], "head_sha": head,
                           "official_metadata_sha256": source["sha256"], **matrix[name]}
    require(set(found) == set(matrix), "Missing required official artifacts")
    return [found[name] for name in matrix], sources


def prepare(*, head, artifact_root, frozen, baseline_root, metadata, output, purpose="candidate_ci_preparation", matrix=None):
    matrix = copy.deepcopy(matrix or DEFAULT_MATRIX)
    require(len(matrix) == 4 and sum(len(row["profiles"]) for row in matrix.values()) == 12,
            "This CI contract requires four artifacts and twelve report/profile pairs")
    for name, row in matrix.items():
        require(safe_member(name) == name and '/' not in name, "Invalid artifact name")
        require(row["platform"] in {"Linux", "Windows"} and set(row["profiles"]) <= set(PROFILES)
                and len(row["profiles"]) == len(set(row["profiles"])), "Invalid artifact matrix")
    contract = frozen_contract(frozen, head)
    artifacts, sources = metadata_artifacts(metadata, head, matrix)
    for artifact in artifacts:
        artifact["archive"] = str(no_links(Path(artifact_root) / (artifact["name"] + ".zip")))
        artifact["baseline_artifact"] = artifact.pop("baseline_artifact", artifact["name"])
    baseline_root = no_links(baseline_root)
    evidence_path = baseline_root / "ci-evidence.json"
    evidence_raw = read(evidence_path)
    evidence = decode(evidence_raw)
    require(evidence.get("status") == "passed" and evidence.get("report_count") == 12,
            "F5 baseline receipt is not complete/passed")
    plan = {"schema": "k1_offline_ci_plan_v1", "purpose": purpose, "frozen": contract,
            "frozen_source": {"path": str(no_links(frozen)), "sha256": sha(read(frozen))},
            "baseline_root": str(baseline_root), "baseline_evidence_sha256": sha(evidence_raw),
            "baseline_head": evidence["head_sha"], "artifacts": artifacts, "metadata_sources": sources,
            "scope": "Offline byte, head, profile and same-generation F5 assertion checks; stage acceptance is separate."}
    save_json(output, plan)
    return plan


def validate_plan(plan, head):
    require(plan.get("schema") == "k1_offline_ci_plan_v1" and plan["frozen"]["head_sha"] == head
            and HEAD.fullmatch(head or ""), "Plan/head mismatch")
    require(plan["purpose"] in {"candidate_ci_preparation", "local_f5_originals_self_test"}, "Unknown plan purpose")
    require(len(plan["artifacts"]) == 4 and sum(len(a["profiles"]) for a in plan["artifacts"]) == 12,
            "Incomplete four-artifact/twelve-profile plan")
    require(len({a["name"] for a in plan["artifacts"]}) == 4, "Duplicate planned artifact")
    require(sha(read(plan["frozen_source"]["path"])) == plan["frozen_source"]["sha256"], "Frozen source changed")
    require(frozen_contract(plan["frozen_source"]["path"], head) == plan["frozen"], "Frozen contract changed")
    matrix = {a["name"]: {k: a[k] for k in ("platform", "geant4_version_number", "profiles")} for a in plan["artifacts"]}
    paths = []
    for source in plan["metadata_sources"]:
        require(sha(read(source["path"])) == source["sha256"], "Official metadata source changed")
        paths.append(source["path"])
    official, _ = metadata_artifacts(paths, head, matrix)
    by_name = {item["name"]: item for item in official}
    for artifact in plan["artifacts"]:
        for key, value in by_name[artifact["name"]].items():
            require(artifact[key] == value, "Plan differs from saved official metadata: " + key)


def archive_bytes(artifact, path=None):
    raw = read(path or artifact["archive"], LIMIT_ZIP)
    require(len(raw) == artifact["bytes"] and "sha256:" + sha(raw) == artifact["official_digest"],
            "Official ZIP digest/size mismatch: " + artifact["name"])
    return raw


def publish_directory(source, destination):
    if sys.platform == "win32":
        os.rename(source, destination)
    elif sys.platform.startswith("linux"):
        lib = ctypes.CDLL(None, use_errno=True)
        rename = getattr(lib, "renameat2", None)
        require(rename is not None, "Exclusive directory publication unsupported")
        rename.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
        rename.restype = ctypes.c_int
        if rename(-100, os.fsencode(source), -100, os.fsencode(destination), 1):
            code = ctypes.get_errno()
            raise OSError(code, os.strerror(code), str(destination))
    else:
        raise ValueError("Exclusive directory publication unsupported on this OS")


def collect(plan_path, destination, head):
    plan_raw = read(plan_path)
    plan = decode(plan_raw)
    validate_plan(plan, head)
    destination = writable(destination)
    require(not os.path.lexists(destination), "Collection destination already exists; choose a new directory")
    destination.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=".collect-", dir=destination.parent))
    committed = False
    try:
        save(stage / "plan.json", plan_raw)
        for source in plan["metadata_sources"]:
            raw = read(source["path"])
            require(sha(raw) == source["sha256"], "Official metadata changed during collection")
            save(stage / "metadata" / source["copy"], raw)
        frozen_raw = read(plan["frozen_source"]["path"])
        require(sha(frozen_raw) == plan["frozen_source"]["sha256"], "Frozen manifest changed during collection")
        save(stage / "metadata/frozen-case-manifest.json", frozen_raw)
        members, archives = [], []
        for artifact in plan["artifacts"]:
            raw = archive_bytes(artifact)
            files = zip_contents(raw)
            save(stage / "archives" / (artifact["name"] + ".zip"), raw)
            for name, payload in files.items():
                save(stage / "artifacts" / artifact["name"] / name, payload)
                members.append({"artifact": artifact["name"], "member": name, "bytes": len(payload), "sha256": sha(payload)})
            archives.append({"name": artifact["name"], "official_digest": artifact["official_digest"],
                             "bytes": len(raw), "file_members": len(files)})
        receipt = {"schema": "k1_offline_collection_v1", "purpose": plan["purpose"], "head_sha": head,
                   "plan_sha256": sha(plan_raw), "archives": archives, "members": members,
                   "network_access": False, "stage_acceptance": "not_decided"}
        save_json(stage / "collection.json", receipt)
        publish_directory(stage, destination)
        committed = True
        return receipt
    finally:
        if not committed and stage.exists():
            require(stage.resolve().is_relative_to(BASE), "Cleanup target escaped helper workspace")
            shutil.rmtree(stage)


def gate_module():
    path = ROOT / "scripts/check_report_evidence.py"
    spec = importlib.util.spec_from_file_location("k1_readonly_report_gate", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module, {"path": str(path), "sha256": sha(read(path))}


def local_log(row, report_path):
    recorded = row.get("log")
    require(isinstance(recorded, str) and recorded, "Case log reference is missing")
    leaf = PurePosixPath(recorded.replace("\\", "/")).name
    safe_member(leaf)
    candidates = [p for p in (report_path.parent / leaf, report_path.parent / "logs" / leaf) if p.is_file()]
    require(len(candidates) == 1, "Case log must exist unambiguously beside its report; no original-path fallback")
    return no_links(candidates[0])


def raw_log_check(raw, row):
    require(sha(raw) == row.get("log_sha256"), "Case raw log SHA256 mismatch: " + row["name"])
    markers = re.findall(rb"^G4USIM_ASSERTS=(\d+)\r?$", raw, re.M)
    require(len(markers) == 1 and int(markers[0]) == row.get("assertions_executed"),
            "Case assertion marker missing/ambiguous/mismatched: " + row["name"])


def checked_report(path, module):
    raw = read(path)
    report = decode(raw)
    normalized = copy.deepcopy(report)
    logs, known = [], set()
    for row, normalized_row in zip(report.get("results", []), normalized.get("results", [])):
        require(row.get("layer") == report.get("profile"), "Case layer/profile mismatch")
        require(type(row.get("exit_code")) is int and type(row.get("assertions_executed")) is int
                and type(row.get("assert_sites")) is int, "Boolean/missing integer case evidence")
        log = local_log(row, path)
        require(log not in known, "Multiple cases reuse one log")
        known.add(log)
        payload = read(log)
        raw_log_check(payload, row)
        # Only an in-memory lookup projection is used for cross-OS basenames.
        # The original report/log bytes are neither edited nor reserialized.
        normalized_row["log"] = log.name
        logs.append({"case": row["name"], "path": str(log), "bytes": len(payload),
                     "sha256": sha(payload), "assertions": row["assertions_executed"]})
    module.validate_report(normalized, report_path=path)
    require(report.get("skip_policy") == "failure", "Report skip policy permits a false green")
    require(type(report.get("git_dirty")) is bool and type(report.get("git_status_porcelain")) is str
            and report["git_dirty"] == bool(report["git_status_porcelain"]), "git_dirty/porcelain inconsistency")
    require(report.get("tracked_source_gate") == "pass" and report.get("untracked_source_files") == [],
            "Tracked source gate did not pass")
    return report, normalized, logs, sha(raw)


def compare_baseline(candidate, baseline, module, report_path):
    require(candidate["profile"] == baseline["profile"], "Cross-profile baseline comparison")
    platform = lambda row: row["platform"].split("-", 1)[0]
    require(platform(candidate) == platform(baseline), "Cross-platform baseline comparison")
    if candidate["profile"] in {"backend", "integration"}:
        require(candidate["backend_build_identity"]["geant4_version_number"] == baseline["backend_build_identity"]["geant4_version_number"],
                "Cross-Geant4-version baseline comparison")
    module.validate_report(candidate, report_path=report_path, baseline=baseline)


def audit(plan_path, collection_root, head, output):
    plan_raw = read(plan_path)
    plan = decode(plan_raw)
    validate_plan(plan, head)
    collection_root = no_links(collection_root)
    require(read(collection_root / "plan.json") == plan_raw, "Collection belongs to a different plan")
    collection = load(collection_root / "collection.json")
    require(collection.get("plan_sha256") == sha(plan_raw) and collection.get("head_sha") == head,
            "Collection identity mismatch")
    frozen_raw = read(collection_root / "metadata/frozen-case-manifest.json")
    require(sha(frozen_raw) == plan["frozen_source"]["sha256"], "Collected frozen manifest differs")
    for source in plan["metadata_sources"]:
        require(sha(read(collection_root / "metadata" / source["copy"])) == source["sha256"], "Collected official metadata differs")
    baseline_root = no_links(plan["baseline_root"])
    baseline_raw = read(baseline_root / "ci-evidence.json")
    require(sha(baseline_raw) == plan["baseline_evidence_sha256"], "F5 baseline evidence receipt changed")
    baseline_evidence = decode(baseline_raw)
    require(baseline_evidence["head_sha"] == plan["baseline_head"], "F5 baseline head mismatch")
    baseline_audit_raw = read(baseline_root / baseline_evidence["audit_file"])
    require(sha(baseline_audit_raw) == baseline_evidence["audit_sha256"], "F5 baseline audit SHA mismatch")
    module, gate_identity = gate_module()
    baseline_index = {}
    for row in baseline_evidence["reports"]:
        key = row["artifact"], row["profile"]
        require(key not in baseline_index, "Duplicate baseline profile")
        baseline_index[key] = row
    pairs, reports, logs, zip_members = set(), [], [], []
    baseline_reads, archives = [], []
    for artifact in plan["artifacts"]:
        name = artifact["name"]
        archive_path = collection_root / "archives" / (name + ".zip")
        raw = archive_bytes(artifact, archive_path)
        files = zip_contents(raw)
        artifact_root = collection_root / "artifacts" / name
        actual = set()
        for directory, dirs, leaves in os.walk(artifact_root, followlinks=False):
            for leaf in dirs + leaves:
                no_links(Path(directory) / leaf)
            for leaf in leaves:
                actual.add((Path(directory) / leaf).relative_to(artifact_root).as_posix())
        require(actual == set(files), "Extracted ZIP members missing or extra: " + name)
        for member, payload in files.items():
            require(read(artifact_root / member) == payload, "Extracted bytes differ from official ZIP: " + member)
            zip_members.append({"artifact": name, "member": member, "sha256": sha(payload), "bytes": len(payload)})
        paths = [artifact_root / member for member in files if PurePosixPath(member).name == "report.json"]
        require(len(paths) == len(artifact["profiles"]), "Unexpected report count in artifact: " + name)
        for path in sorted(paths):
            report, normalized, case_logs, report_sha = checked_report(path, module)
            profile = report["profile"]
            key = name, profile
            require(profile in artifact["profiles"] and key not in pairs, "Duplicate/incorrect artifact profile")
            pairs.add(key)
            require(report["git_head"] == head, "Report is from a different head")
            require(report["platform"].startswith(artifact["platform"] + "-"), "Artifact/report OS mismatch")
            for field in ("source_fingerprint", "tests_content_fingerprint"):
                require(report[field] == plan["frozen"][field], "Report/frozen fingerprint mismatch: " + field)
            require([row["name"] for row in report["results"]] == plan["frozen"]["profiles"][profile],
                    "Report cases differ from actual frozen profile list")
            if profile in {"backend", "integration"}:
                require(report["backend_provenance"] == "source_sha256_manifest_matches_executable"
                        and report["merge_provenance"] == "source_sha256_matches_executable", "Backend/merge provenance mismatch")
                build = report["backend_build_identity"]
                require(build["geant4_version_number"] == artifact["geant4_version_number"]
                        and build["multithreaded"] is True and build["build_configuration"] == "Release",
                        "Backend build/version identity mismatch")
            base_key = artifact["baseline_artifact"], profile
            require(base_key in baseline_index, "Missing same-artifact/profile F5 baseline")
            base_receipt = baseline_index[base_key]
            base_path = baseline_root / safe_member(base_receipt["path"])
            require(sha(read(base_path)) == base_receipt["sha256"], "F5 baseline report SHA mismatch")
            base, normalized_base, base_logs, base_sha = checked_report(base_path, module)
            require(base["git_head"] == plan["baseline_head"], "F5 baseline report head mismatch")
            compare_baseline(normalized, normalized_base, module, path)
            require(base["assertions_executed_total"] == base_receipt["assertions"]
                    and len(base["results"]) == base_receipt["cases"], "F5 receipt/case count mismatch")
            baseline_reads.append({"artifact": base_key[0], "profile": profile, "report_sha256": base_sha,
                                   "case_logs": len(base_logs)})
            logs.extend({"artifact": name, "profile": profile, **row} for row in case_logs)
            reports.append({"artifact": name, "profile": profile,
                            "path": path.relative_to(collection_root).as_posix(), "sha256": report_sha,
                            "cases": len(report["results"]), "assertions": report["assertions_executed_total"],
                            "baseline_cases": len(base["results"]), "baseline_assertions": base["assertions_executed_total"],
                            "baseline_sha256": base_sha, "per_case_and_total_baseline": "passed",
                            "git_dirty": report["git_dirty"], "git_status_porcelain": report["git_status_porcelain"]})
        archives.append({"name": name, "official_digest": artifact["official_digest"], "bytes": len(raw),
                         "run_id": artifact["run_id"], "artifact_id": artifact["artifact_id"]})
    expected_pairs = {(a["name"], p) for a in plan["artifacts"] for p in a["profiles"]}
    require(pairs == expected_pairs and len(reports) == 12, "Twelve-report coverage is incomplete")
    receipt = {"schema": "k1_offline_ci_audit_v1", "purpose": plan["purpose"], "head_sha": head,
               "checks_passed": True, "stage_acceptance": "not_decided", "k1_ci_verified": False,
               "report_count": len(reports), "case_executions": len(logs),
               "assertions_executed_total": sum(r["assertions"] for r in reports),
               "plan_sha256": sha(plan_raw), "report_gate": gate_identity,
               "baseline_head": plan["baseline_head"], "baseline_evidence_sha256": sha(baseline_raw),
               "archives": archives, "reports": reports, "case_logs": logs, "zip_members": zip_members,
               "baseline_reports_verified": baseline_reads,
               "boundary": "Offline supplied official metadata/ZIP consistency and raw logs/F5 baselines only. No network source authentication, CI dispatch, K1 stage, native UI or physics acceptance."}
    save_json(output, receipt)
    return receipt


def cli():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    prepare_args = sub.add_parser("prepare")
    prepare_args.add_argument("--head", required=True)
    prepare_args.add_argument("--artifact-root", type=Path, required=True)
    prepare_args.add_argument("--frozen", type=Path, required=True)
    prepare_args.add_argument("--baseline-root", type=Path, default=F5)
    prepare_args.add_argument("--artifact-metadata", type=Path, action="append", required=True)
    prepare_args.add_argument("--matrix", type=Path)
    prepare_args.add_argument("--output", type=Path, required=True)
    for name in ("collect", "audit"):
        command = sub.add_parser(name)
        command.add_argument("--head", required=True)
        command.add_argument("--plan", type=Path, required=True)
        if name == "collect":
            command.add_argument("--destination", type=Path, required=True)
        else:
            command.add_argument("--collection", type=Path, required=True)
            command.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    require(__debug__, "Do not run the repository assert evidence gate with python -O")
    try:
        if args.command == "prepare":
            value = prepare(head=args.head, artifact_root=args.artifact_root, frozen=args.frozen,
                            baseline_root=args.baseline_root, metadata=args.artifact_metadata, output=args.output,
                            matrix=load(args.matrix) if args.matrix else None)
            result = {"prepared": True, "head_sha": value["frozen"]["head_sha"],
                      "profile_cases": {p: len(c) for p, c in value["frozen"]["profiles"].items()}, "k1_ci_verified": False}
        elif args.command == "collect":
            value = collect(args.plan, args.destination, args.head)
            result = {"collected": True, "archives": len(value["archives"]), "members": len(value["members"]), "k1_ci_verified": False}
        else:
            value = audit(args.plan, args.collection, args.head, args.output)
            result = {key: value[key] for key in ("purpose", "checks_passed", "head_sha", "report_count", "case_executions", "assertions_executed_total", "k1_ci_verified")}
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except (ValueError, OSError, AssertionError, zipfile.BadZipFile, KeyError, TypeError) as error:
        print(json.dumps({"checks_passed": False, "error": str(error), "k1_ci_verified": False}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(cli())
