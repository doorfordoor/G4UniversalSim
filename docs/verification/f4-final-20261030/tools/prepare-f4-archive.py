"""F4 evidence planning/review; publication is a separate, explicit operation.

Reuses the independently reviewed F1 topology, local-log gate and exclusive-copy
engine. No network, Git staging, source editing or phase-closure assertion.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import stat
import subprocess
import sys
import zipfile


ROOT = next(parent for parent in Path(__file__).resolve().parents
            if (parent / "CMakeLists.txt").is_file() and (parent / "scripts/check_report_evidence.py").is_file())
ENGINE_PATH = Path(__file__).with_name("archive-f4.py")
spec = importlib.util.spec_from_file_location("f4_archive_copy_engine", ENGINE_PATH)
engine = importlib.util.module_from_spec(spec)
spec.loader.exec_module(engine)
engine.ROOT = ROOT
BASELINE = ROOT / "docs/verification/f1-automated-20261030/windows/final-1/report.json"
FORMAT = "f4_evidence_archive_plan_v1"


def under_workspace(path: Path) -> Path:
    path = path.absolute()
    if not path.resolve().is_relative_to(ROOT.resolve()):
        raise ValueError("Archive input/output must stay within this workspace")
    for ancestor in (path, *path.parents):
        if ancestor == ROOT:
            break
        if ancestor.exists() and (ancestor.is_symlink() or
                getattr(ancestor.lstat(), "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 1024)):
            raise ValueError("Linked/reparse archive input/output refused")
    # Later checks use lexical is_relative_to(out); normalize traversal only
    # after rejecting links so out/../docs cannot pass as an out-only output.
    return path.resolve()


def destination(path: Path, *, existing=False) -> Path:
    path = under_workspace(path)
    if not path.name.lower().startswith("f4-"):
        raise ValueError("New archive root must be explicitly named f4-...")
    if not (path.parent == ROOT / "docs/verification" or path.is_relative_to(ROOT / "out")):
        raise ValueError("Destination must be a new docs/verification/f4-* or out/f4-* root")
    if not existing and os.path.lexists(path):
        raise FileExistsError("Destination already exists; no overwrite or automatic cleanup")
    return path


def write_out(path: Path, value) -> None:
    path = under_workspace(path)
    if not path.is_relative_to(ROOT / "out"):
        raise ValueError("Plans/reviews must be written under out; use explicit publish for docs")
    engine.write_new(path, engine.json_bytes(value))


def check_baseline(path: Path) -> dict:
    data = engine.read_json(path)
    if (data.get("profile") != "all" or len(data.get("results", ())) != 143 or
            data.get("assertions_executed_total") != 48511 or
            data.get("assert_probe") != "settrace_assert_lines_v3" or
            data.get("git_head") != "f176d0ed4cea60b7ca5a80ed81017c9404ec1257"):
        raise ValueError("F4 baseline must be the original F1 all/143/48511/v3 report")
    return {"path": str(path), "sha256": engine.file_digest(path), "cases": 143,
            "assertions": 48511, "probe": data["assert_probe"], "head": data["git_head"]}


def source_zip_checks(ci_root: Path, ci: dict) -> list[dict]:
    checked = []
    for artifact in ci.get("artifacts", []):
        name = artifact.get("name")
        if name not in engine.CI_TOPOLOGY:
            raise ValueError("Unknown artifact identity; ZIP path not read")
        archive = under_workspace(ci_root / (name + ".zip"))
        official = artifact.get("official_digest")
        actual = "sha256:" + engine.file_digest(archive)
        if actual != official or actual != artifact.get("sha256"):
            raise ValueError("Official ZIP digest differs: " + name)
        extracted = ci_root / name
        members = set()
        folded = set()
        with zipfile.ZipFile(archive) as bundle:
            for info in bundle.infolist():
                if stat.S_ISLNK(info.external_attr >> 16):
                    raise ValueError("Symlink ZIP member refused")
                if info.is_dir():
                    continue
                path = engine.safe_relative(extracted, info.filename)
                key = path.relative_to(extracted).as_posix()
                if key.casefold() in folded:
                    raise ValueError("Duplicate/case-colliding ZIP member refused")
                folded.add(key.casefold())
                members.add(key)
                under_workspace(path)
                if not path.is_file() or engine.digest(bundle.read(info)) != engine.file_digest(path):
                    raise ValueError("Extracted bytes differ from ZIP: " + name + "/" + key)
        actual_members = {path.relative_to(extracted).as_posix()
                          for path in extracted.rglob("*") if path.is_file()}
        if actual_members != members:
            raise ValueError("Extracted file set differs from ZIP: " + name)
        checked.append({"name": name, "zip_source": str(archive), "official_digest": official,
                        "source_zip_digest": actual, "matches": True,
                        "extracted_members_checked": len(members), "exact_member_set": True})
    if len(checked) != 4:
        raise ValueError("Exactly four original ZIP containers required")
    return checked


def history_record(source: Path, kind: str) -> dict:
    """Inventory a historical round without treating its completeness as success."""
    result = {"recorded_status": "retained_unassessed", "release_accepted": False,
              "meaning": "retained original history, not release acceptance", "reports": []}
    for path in sorted(source.rglob("report.json")):
        data = engine.read_json(path)
        result["reports"].append({"path": path.relative_to(source).as_posix(),
            "head": data.get("git_head"), "profile": data.get("profile"),
            "statuses": sorted({case.get("status", "missing") for case in data.get("results", [])})})
    if kind == "windows" and not result["reports"]:
        path = source / "interruption.json"
        value = engine.read_json(path)
        if (value.get("schema") != "g4usim_interrupted_validation_v1" or
                value.get("normal_completion") is not False or
                value.get("report_json_exists") is not False or
                type(value.get("process_exit_code")) is not int or
                not value.get("termination_reason")):
            raise ValueError("Historical Windows without report needs a terminal interruption receipt")
        for row in value.get("case_logs", []):
            log = under_workspace(engine.safe_relative(source, row["path"]))
            if engine.file_digest(log) != row["sha256"]:
                raise ValueError("Interrupted Windows case log changed: " + row["path"])
        result.update(recorded_status="interrupted", recorded_complete=False,
            recorded_head=value.get("commit"), interruption_receipt="interruption.json",
            process_exit_code=value["process_exit_code"], case_logs_checked=len(value.get("case_logs", [])),
            expected_runner_log_sha256=value.get("runner_log_sha256"))
    if kind == "ci":
        # Old CI may have only a subset of artifacts. Keep that fact rather than
        # requiring twelve old reports or silently promoting them to this release.
        receipt = source / "ci-evidence.json"
        if (source / "round-summary.json").is_file():
            data = engine.read_json(source / "round-summary.json")
            result.update(recorded_status=data.get("status", "unknown"),
                          recorded_head=data.get("head_sha"), summary_file="round-summary.json",
                          recorded_complete=data.get("evidence_collection_complete"),
                          profile_coverage_complete=data.get("report_profile_coverage_complete"),
                          missing_profiles=data.get("missing_profiles", []))
        elif receipt.is_file():
            data = engine.read_json(receipt)
            result.update(recorded_status="collector_receipt_retained",
                          recorded_head=data.get("head_sha"))
        else:
            result.update(recorded_status="incomplete_collection_retained", recorded_complete=False)
        result["zip_sources"] = [{"name": path.name, "source": str(path),
            "sha256": engine.file_digest(path), "official_identity_checked": False,
            "meaning": "retained historical container bytes; not final topology evidence"}
            for path in sorted(source.glob("*.zip"))]
    if kind == "visible":
        result.update(recorded_status="historical_native_records_retained", visual_acceptance=False)
    return result


def make_plan(args) -> dict:
    target = destination(args.destination)
    ci_root = under_workspace(args.ci_receipt).parent
    if args.ci_receipt.name != "ci-evidence.json":
        raise ValueError("--ci-receipt must identify the collector's original ci-evidence.json")
    windows = under_workspace(args.windows_report)
    if windows.name != "report.json":
        raise ValueError("--windows-report must identify the original report.json")
    baseline = under_workspace(args.baseline_report)
    baseline_identity = check_baseline(baseline)
    ci_expected_head = getattr(args, "ci_head", None) or args.expected_head
    mapping_path = getattr(args, "identity_map", None)
    if ci_expected_head != args.expected_head and mapping_path is None:
        raise ValueError("Mixed product/CI heads require --identity-map; no implicit SHA exception")
    if ci_expected_head == args.expected_head and mapping_path is not None:
        raise ValueError("Same-head evidence must not supply a cross-commit identity map")
    files, folded, roots, excluded = {}, {}, [], []

    def add_file(source: Path, relative: str, category: str, *, active_markdown=False):
        source = under_workspace(source)
        if not source.is_file():
            raise FileNotFoundError(source)
        member = PurePosixPath(relative)
        if any(part.lower() in engine.FORBIDDEN_COMPONENTS for part in member.parts):
            raise ValueError("Private path component refused")
        suffix = source.suffix.lower()
        media_format = None
        if suffix == ".zip" and category != "historical_ci":
            excluded.append({"source": str(source), "reason": "official ZIP checked at source; container not copied, matching F1 archive policy"})
            return
        if suffix in {".png", ".jpg", ".jpeg"}:
            if category not in {"visible", "historical_visible"}:
                excluded.append({"source": str(source), "reason": "non-native/debug media not selected as visible evidence"})
                return
            raw = source.read_bytes()
            media_format = "png" if raw.startswith(b"\x89PNG\r\n\x1a\n") else "jpeg" if raw.startswith(b"\xff\xd8\xff") else None
            if media_format is None:
                raise ValueError("Visible image must contain PNG or JPEG bytes")
        elif suffix == ".zip" and category == "historical_ci":
            # An incomplete old CI round cannot supply final topology proof.
            # Preserve the original container itself as history, without
            # claiming its official identity or extracting executable content.
            raw = source.read_bytes()
        elif (suffix in engine.TEXT_SUFFIXES or suffix in engine.EXPLICIT_SOURCE_SUFFIXES or
              category in {"visible", "historical_visible"} and suffix in {".jsonl", ".stdout", ".stderr"}):
            raw = source.read_bytes()
            engine.check_text(raw, source)
        else:
            excluded.append({"source": str(source), "reason": "binary or unapproved extension; no implicit executable/media archive"})
            return
        original = relative
        if suffix == ".md" and not active_markdown:
            relative += ".txt"
        engine.safe_relative(target, relative)
        key = relative.casefold()
        if key in folded:
            raise ValueError("Duplicate/case-colliding archive member: " + relative)
        folded[key] = relative
        row = {"source": str(source), "archive_path": relative, "size": len(raw),
               "sha256": engine.digest(raw), "category": category}
        if media_format:
            row.update(detected_media_format=media_format,
                       suffix_matches_media=(suffix == ".png" if media_format == "png" else suffix in {".jpg", ".jpeg"}),
                       media_policy="Preserve original bytes and name; no transcoding or historical correction")
        if relative != original:
            row.update(original_archive_path=original, rendering="literal_text",
                       archive_path_reason="Original Markdown evidence bytes preserved without rewriting historical links")
        files[relative] = row

    def add_tree(source: Path, relative: str, category: str):
        source = under_workspace(source)
        if not source.is_dir():
            raise FileNotFoundError(source)
        if source.resolve().is_relative_to(target.resolve()) or target.resolve().is_relative_to(source.resolve()):
            raise ValueError("Selected source and destination must not contain each other")
        roots.append({"source": str(source), "archive_prefix": relative, "category": category})
        for path in sorted(source.rglob("*")):
            # Check directory junctions as well as files before selecting contents.
            under_workspace(path)
            if path.is_file():
                add_file(path, str(PurePosixPath(relative) / path.relative_to(source).as_posix()), category)

    add_tree(windows.parent, "windows/final-1", "accepted_windows")
    add_tree(ci_root, "ci", "accepted_ci")
    add_tree(baseline.parent, "baseline/1", "baseline")
    add_file(args.readme, "README.md", "active_index", active_markdown=True)
    for index, path in enumerate(args.build_root, 1):
        add_tree(path, f"build/{index}-{path.name}", "build")
    for index, path in enumerate(args.visible_root, 1):
        identity_file = under_workspace(path) / "identity.json"
        if identity_file.is_file():
            visible_identity = engine.identity.read_json(identity_file)
            if "gui_head" in visible_identity and visible_identity["gui_head"] != args.expected_head:
                raise ValueError("Accepted native GUI head must remain the product head; CI exception is not a GUI relabel")
        add_tree(path, f"visible/{index}-{path.name}", "visible")
    historical_rounds = []
    accepted_roots = [windows.parent.resolve(), ci_root.resolve(),
                      *(under_workspace(path).resolve() for path in args.visible_root)]
    history_roots = []
    for kind in ("windows", "ci", "visible"):
        for index, path in enumerate(getattr(args, "historical_" + kind + "_root", []), 1):
            source = under_workspace(path)
            resolved = source.resolve()
            if any(resolved.is_relative_to(root) or root.is_relative_to(resolved)
                   for root in accepted_roots + history_roots):
                raise ValueError("Accepted and historical roots must be disjoint; duplicate history refused")
            history_roots.append(resolved)
            prefix = f"history/{kind}-round-{index}-{source.name}"
            add_tree(source, prefix, "historical_" + kind)
            historical_rounds.append({"source": str(source), "archive_prefix": prefix,
                "category": "historical_" + kind, **history_record(source, kind)})
    for index, path in enumerate(args.review_file, 1):
        add_file(path, f"review/{index}-{path.name}", "review")
    for index, path in enumerate(args.include_file, 1):
        add_file(path, f"additional/{index}-{path.name}", "additional")
    for name, path in (("design-response", args.deepseek_response), ("design-receipt", args.deepseek_receipt)):
        if path is not None:
            add_file(path, f"design/{name}{path.suffix}", "design")
    for name, path in (("check_report_evidence.py", ROOT / "scripts/check_report_evidence.py"),
                       ("check_doc_links.py", ROOT / "scripts/check_doc_links.py"),
                       ("archive-f4.py", ENGINE_PATH),
                       ("f4_archive_identity.py", Path(__file__).with_name("f4_archive_identity.py")),
                       ("prepare-f4-archive.py", Path(__file__))):
        add_file(path, "tools/" + name, "verification_tool")

    ci = engine.read_json(args.ci_receipt)
    frozen = engine.read_json(ci_root / "frozen-case-manifest.json")
    current = engine.read_json(windows)
    if frozen.get("head_sha") != ci_expected_head:
        raise ValueError("CI frozen case manifest HEAD differs from requested CI identity")
    if current.get("git_head") != args.expected_head or current.get("git_dirty") is not False or current.get("profile") != "all":
        raise ValueError("Windows report must be clean all at the requested product HEAD")
    for key in ("source_fingerprint", "tests_content_fingerprint"):
        if current.get(key) != frozen.get(key) or ci.get(key) != frozen.get(key):
            raise ValueError("Windows/CI/frozen identity mismatch: " + key)
    actual_paths = [row["archive_path"][3:] for row in files.values()
                    if row["category"] == "accepted_ci" and row["archive_path"].endswith("/report.json")]
    mapping = None
    if mapping_path is not None:
        mapping_path = under_workspace(mapping_path)
        mapping = engine.identity.verify_live(ROOT, mapping_path, args.expected_head, ci_expected_head, frozen)
        for name in engine.identity.FILES:
            add_file(mapping_path.parent / name, "identity/" + name, "product_ci_identity")
    topology = engine.validate_ci_topology(ci_root, ci_expected_head, actual_paths)
    checks = source_zip_checks(ci_root, ci)
    plan = {"format": FORMAT, "stage": "F4", "created_utc": engine.utc(), "destination": str(target),
            "repository_head_at_plan": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
            "expected_head": args.expected_head, "frozen": frozen, "source_roots": roots,
            "ci_expected_head": ci_expected_head, "identity_mapping": mapping,
            "identity_mapping_path": "identity/identity-map.json" if mapping is not None else None,
            "required_windows_reports": ["windows/final-1/report.json"], "baseline_reports": ["baseline/1/report.json"],
            "f1_baseline_identity": baseline_identity, "files": sorted(files.values(), key=lambda row: row["archive_path"]),
            "excluded": excluded, "missing_sources": [], "preflight_blockers": [], "historical_rounds": historical_rounds,
            "artifact_zip_digest_checks": checks, "historical_zip_digest_checks": [], "performance_checks": [],
            "expected_ci_reports": 12, "expected_ci_artifacts": 4, "ci_topology_check": topology,
            "visible_acceptance": "not_asserted_by_archive_tool", "phase_complete": False,
            "policy": "Original bytes only; explicit inputs; exclusive new root. F4 has no F1 performance experiment requirement. ZIP containers retained at source with official digests. Copy/gates do not certify native UI or physics."}
    if not args.review_file:
        plan["preflight_blockers"].append("No explicit independent review selected")
    if bool(args.deepseek_response) != bool(args.deepseek_receipt):
        plan["preflight_blockers"].append("DeepSeek response/receipt must be selected together")
    for row in historical_rounds:
        expected = row.get("expected_runner_log_sha256")
        if expected and not any(item["sha256"] == expected for item in plan["files"]):
            plan["preflight_blockers"].append("Select original interrupted runner log with --include-file: " + row["source"])
    plan["link_check"] = engine.link_check(plan)
    if plan["link_check"]["broken_links"]:
        plan["preflight_blockers"].append("Active archive README has broken/nonportable links")
    if target.parent == ROOT / "docs/verification":
        member = (target / "windows/final-1/report.json").relative_to(ROOT).as_posix()
        attr = subprocess.check_output(["git", "check-attr", "text", "--", member], cwd=ROOT, text=True).strip()
        if not attr.endswith(": text: unset"):
            raise ValueError("docs/verification must preserve original bytes with -text")
        plan["git_text_attribute"] = attr
    return plan


def load_plan(path: Path) -> dict:
    plan = engine.read_json(under_workspace(path))
    if plan.get("format") != FORMAT or plan.get("stage") != "F4":
        raise ValueError("Only an explicit F4 plan is accepted")
    destination(Path(plan["destination"]))
    return plan


def stage_commands(folder: Path) -> dict:
    folder = destination(folder, existing=True)
    manifest = engine.read_json(folder / "archive-manifest.json")
    if manifest.get("format") != FORMAT:
        raise ValueError("Only the newly published F4 root can generate staging commands")
    verify_f4_archive(folder)
    relative = folder.relative_to(ROOT).as_posix()
    logs = [under_workspace(path).relative_to(ROOT).as_posix()
            for path in sorted(folder.rglob("*.log")) if path.is_file()]
    return {"cwd": str(ROOT), "executed": False, "archive_root": relative,
            "normal_add_argv": ["git", "add", "--", relative],
            "exact_log_force_add_argv": [["git", "add", "-f", "--", *logs[i:i+60]]
                                        for i in range(0, len(logs), 60)],
            "scope": "Only exact files below this new root; never force-add docs/verification or old archives globally"}


def verify_f4_archive(folder: Path) -> dict:
    result = engine.verify_existing(folder)
    plan = engine.read_json(folder / "archive-manifest.json")
    verification = engine.read_json(folder / "archive-verification.json")
    expected = {row["archive_path"] for row in plan["files"]}
    expected.update(row["path"] for row in verification.get("generated_verification_files", []))
    expected.update({"archive-started.json", "archive-manifest.json", "archive-verification.json", "archive-complete.json"})
    actual = set()
    for path in folder.rglob("*"):
        under_workspace(path)
        if path.is_file():
            actual.add(path.relative_to(folder).as_posix())
    if actual != expected:
        raise ValueError("Archive file set differs from manifest/generated evidence")
    result["exact_file_set"] = True
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--review-plan", type=Path)
    modes.add_argument("--publish-plan", type=Path)
    modes.add_argument("--verify-existing", type=Path)
    modes.add_argument("--stage-commands", type=Path)
    parser.add_argument("--windows-report", type=Path)
    parser.add_argument("--ci-receipt", type=Path)
    parser.add_argument("--destination", type=Path)
    parser.add_argument("--expected-head", help="explicit newly frozen product HEAD; no historical default")
    parser.add_argument("--ci-head", help="CI commit, defaults strictly to product HEAD")
    parser.add_argument("--identity-map", type=Path, help="required exact Git-bound apt-only proof if CI HEAD differs")
    parser.add_argument("--baseline-report", type=Path, default=BASELINE)
    parser.add_argument("--readme", type=Path)
    for name in ("build-root", "visible-root", "review-file", "include-file",
                 "historical-windows-root", "historical-ci-root", "historical-visible-root"):
        parser.add_argument("--" + name, type=Path, action="append", default=[])
    parser.add_argument("--deepseek-response", type=Path)
    parser.add_argument("--deepseek-receipt", type=Path)
    parser.add_argument("--output", type=Path, required=True, help="exclusive new plan/receipt file under out")
    args = parser.parse_args()
    # Reserve no destination. Even dry-run output collisions fail before copying.
    output = under_workspace(args.output)
    if not output.is_relative_to(ROOT / "out"):
        raise ValueError("Output plans/receipts must be under out before any publication")
    if os.path.lexists(output):
        raise FileExistsError("Output receipt already exists; use a fresh filename")
    if args.stage_commands:
        result = stage_commands(args.stage_commands)
    elif args.verify_existing:
        folder = destination(args.verify_existing, existing=True)
        if engine.read_json(folder / "archive-manifest.json").get("format") != FORMAT:
            raise ValueError("Not an F4 archive")
        result = verify_f4_archive(folder)
    elif args.review_plan:
        result = engine.review_plan(load_plan(args.review_plan))
    elif args.publish_plan:
        plan = load_plan(args.publish_plan)
        engine.execute(plan)
        result = verify_f4_archive(Path(plan["destination"]))
    else:
        if any(value is None for value in (args.windows_report, args.ci_receipt, args.destination, args.readme, args.expected_head)):
            parser.error("Planning requires --windows-report, --ci-receipt, --destination, --readme, --expected-head")
        result = make_plan(args)
    write_out(output, result)
    file_count = result.get("files", ())
    file_count = file_count if type(file_count) is int else len(file_count)
    print(json.dumps({"output": str(output), "mode": "publish" if args.publish_plan else "read_only_or_plan",
                      "status": result.get("status", "plan_written"), "files": file_count,
                      "preflight_blockers": result.get("preflight_blockers", [])}, ensure_ascii=False))
    return 2 if result.get("preflight_blockers") or result.get("status") == "blocked_plan_review" else 0


if __name__ == "__main__":
    raise SystemExit(main())
