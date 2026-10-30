"""Out-only, exclusive, byte-preserving Qt dependency evidence collection.

Fetches fresh official metadata, checks retained wheels without copying them,
and preserves selected historical/final receipts without correcting their bytes.
It does not run tests, install packages, edit tracked files, or publish docs.
"""
from __future__ import annotations

import concurrent.futures
import hashlib
import json
from pathlib import Path
import stat
import urllib.request
from datetime import datetime, timezone
import zipfile

ROOT = Path(__file__).resolve().parents[2]
COLLAB = ROOT / "out/collab"
SOURCE = COLLAB / "f4-qt-dependency-validation"
OFFICIAL = COLLAB / "f4-qt-official-metadata-20261030"
DEST = COLLAB / "f4-qt-dependency-evidence-20261030"
CI = ROOT / "out/verification/f4-ci-5d6f008"
OLD_REPORT = CI / "linux-evidence-11.4.3/linux-integration/20261030-113427-a2f80f69/report.json"
VERSIONS = ("6.11.1", "6.11.3")
EXPECTED = {"binding": 8, "gui_f4_inspect_backend": 45, "gui_run_inputs": 103, "gui_f4_layout": 257}
TARGETS = {
    "binding": COLLAB / "smoke_qt_binding_lifetime_candidate.py",
    "gui_f4_inspect_backend": ROOT / "gui/smoke_tests/smoke_f4_inspect_backend.py",
    "gui_run_inputs": ROOT / "gui/smoke_tests/smoke_run_input_modes.py",
    "gui_f4_layout": ROOT / "gui/smoke_tests/smoke_f4_layout.py",
}


def utc():
    return datetime.now(timezone.utc).isoformat()


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def digest_file(path):
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_new(path, raw):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write(raw)


def write_json(path, value):
    write_new(path, (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))


def safe_source(path):
    path = path.absolute()
    assert path.resolve().is_relative_to(ROOT.resolve()), path
    for item in (path, *path.parents):
        if item == ROOT:
            break
        assert not item.is_symlink(), item
        assert not (getattr(item.lstat(), "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 1024)), item
    assert path.is_file(), path
    return path


def fetch_official_metadata():
    # This is a new corroborating receipt, not a retroactively invented record
    # of the earlier downloader's metadata response.
    OFFICIAL.mkdir(exist_ok=False)
    downloaded = read_json(SOURCE / "wheelhouse-downloads.json")
    assert len(downloaded) == 8

    def fetch(row):
        url = f"https://pypi.org/pypi/{row['package']}/{row['version']}/json"
        started = utc()
        with urllib.request.urlopen(url, timeout=40) as response:
            raw = response.read()
            response_url = response.url
            response_status = response.status
        metadata = json.loads(raw)
        wheel = next(item for item in metadata["urls"] if item["filename"] == row["filename"])
        assert wheel["digests"]["sha256"] == row["sha256"]
        assert wheel["url"] == row["url"]
        actual_wheel = safe_source(SOURCE / "wheelhouse" / row["filename"])
        actual_hash = digest_file(actual_wheel)
        assert actual_hash == row["sha256"]
        assert actual_wheel.stat().st_size == row["bytes"] == wheel["size"]
        target = OFFICIAL / (row["package"] + "-" + row["version"] + ".json")
        write_new(target, raw)
        return {
            "package": row["package"], "version": row["version"],
            "requested_url": url, "response_url": response_url, "http_status": response_status,
            "request_started_utc": started, "completed_utc": utc(),
            "raw_metadata_path": str(target), "raw_metadata_sha256": sha(raw),
            "raw_metadata_bytes": len(raw), "wheel_filename": row["filename"],
            "official_wheel_url": wheel["url"], "official_wheel_sha256": wheel["digests"]["sha256"],
            "retained_original_wheel_path": str(actual_wheel), "actual_wheel_sha256": actual_hash,
            "wheel_bytes": actual_wheel.stat().st_size, "wheel_copied": False,
            "requires_python": metadata["info"].get("requires_python"),
            "requires_dist": metadata["info"].get("requires_dist"),
            "meaning": "fresh official metadata corroborates the original download receipt and retained wheel bytes",
        }

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(fetch, downloaded))
    results.sort(key=lambda row: (row["version"], row["package"]))
    write_json(OFFICIAL / "official-metadata-receipt.json", {"created_utc": utc(), "results": results})
    return results


def checks():
    final = []
    for version in VERSIONS:
        folder = SOURCE / ("validation-" + version + "-rpath-data")
        results = read_json(folder / "results.json")
        assert {row["name"] for row in results} == set(EXPECTED)
        for row in results:
            assert row["exit_code"] == 0
            assert row["assert_markers"] == [f"G4USIM_ASSERTS={EXPECTED[row['name']]}"]
            assert digest_file(folder / (row["name"] + ".log")) == row["log_sha256"]
            assert digest_file(TARGETS[row["name"]]) == row["script_sha256"]
        identity = read_json(folder / "identity.json")
        assert identity["pyside"] == identity["shiboken"] == identity["qt"] == version
        assert identity["python"].startswith("3.11.18")
        discovery = read_json(folder / "data-discovery.json")
        assert discovery["required_complete"] is True
        assert len(read_json(folder / "data-environment.json")) == 12
        assert "real generated QProcess run completed 3/3 events" in (folder / "gui_run_inputs.log").read_text()
        final.append({"version": version, "cases": 4, "assertions": 413, "natural_exit_zero": True,
                      "script_and_log_hashes_match": True, "required_data_complete": True})

    report = read_json(OLD_REPORT)
    old = [row for row in report["results"] if row["name"] in ("gui_f4_inspect_backend", "gui_run_inputs")]
    assert len(old) == 2
    for row in old:
        assert row["exit_code"] == -6 and row["status"] == "fail"
        assert row["assertions_executed"] == EXPECTED[row["name"]]
        log = OLD_REPORT.parent / (row["name"] + ".log")
        assert digest_file(log) == row["log_sha256"]
        assert "none_dealloc" in log.read_text()
    artifact = next(row for row in read_json(CI / "41047666520-artifacts-api.json")["artifacts"]
                    if row["name"] == "linux-evidence-11.4.3")
    archive = CI / "linux-evidence-11.4.3.zip"
    assert "sha256:" + digest_file(archive) == artifact["digest"]
    archive_members = []
    with zipfile.ZipFile(archive) as bundle:
        for path in (OLD_REPORT, *(OLD_REPORT.parent / (row["name"] + ".log") for row in old)):
            member = path.relative_to(CI / "linux-evidence-11.4.3").as_posix()
            assert bundle.read(member) == path.read_bytes()
            archive_members.append({"member": member, "sha256": digest_file(path)})

    for version in VERSIONS:
        loader = SOURCE / ("validation-" + version)
        for row in read_json(loader / "results.json"):
            assert row["exit_code"] == 1 and row["assert_markers"] == ["G4USIM_ASSERTS=0"]
            raw = (loader / (row["name"] + ".log")).read_bytes()
            assert sha(raw) == row["log_sha256"]
            assert b"libQt6DBus.so.6" in raw and b"undefined symbol" in raw
        data = SOURCE / ("validation-" + version + "-rpath")
        failed = next(row for row in read_json(data / "results.json") if row["name"] == "gui_run_inputs")
        assert failed["exit_code"] == 1 and failed["assert_markers"] == ["G4USIM_ASSERTS=75"]
        assert digest_file(data / "gui_run_inputs.log") == failed["log_sha256"]
    debug = SOURCE / "runner-debug-state/runner-signal-capture.jsonl"
    assert "G4ENSDFSTATEDATA environment variable must be set" in debug.read_text()
    assert "none_dealloc" in (COLLAB / "f4-product-refcount-independent.log").read_text()
    assert '"none_ref_delta": -100' in (SOURCE / "linux-6120-binding-negative.log").read_text()
    return {"final_versions": final, "old_ci_negative": {
        "run": 41047666520, "job": 124035633907, "head": report["git_head"],
        "artifact_id": artifact["id"], "official_digest": artifact["digest"],
        "original_archive_path": str(archive), "archive_bytes_sha256_verified": True,
        "selected_extracted_members_byte_equal": archive_members,
        "cases": [{key: row[key] for key in ("name", "exit_code", "assertions_executed", "log_sha256")} for row in old],
        "original_ci_pyside_version": "not directly recorded by quiet pip log; 6.12.0 confirmed only for local reproduction",
    }, "loader_negatives_checked": 8, "missing_data_negatives_checked": 2,
        "backend_data_error_captured": True, "local_612_none_negative_confirmed": True}


def collect():
    assert not DEST.exists(), "Exclusive new directory required"
    validation = checks()
    official = fetch_official_metadata()
    selection = []

    def add(source, target, category):
        selection.append((safe_source(source), target, category))

    # All immediate files are small textual receipts; never descend into wheels,
    # Matplotlib caches, QSettings/history, generated test packages, or venv/build.
    for path in sorted(SOURCE.iterdir()):
        if path.is_file():
            assert path.suffix in {".json", ".log", ".md", ".patch"}, path
            add(path, "receipts/" + path.name, "original_dependency_receipt")
    for version in VERSIONS:
        for suffix, category in (("", "negative/loader"), ("-rpath", "negative/missing-data"), ("-rpath-data", "final")):
            folder = SOURCE / ("validation-" + version + suffix)
            for path in sorted(folder.iterdir()):
                if path.is_file():
                    add(path, f"{category}/{version}/{path.name}", category)
    add(SOURCE / "runner-debug-state/runner-signal-capture.jsonl",
        "negative/missing-data/runner-signal-capture.jsonl.txt", "raw_jsonl_kept_as_text")
    for path in sorted(OFFICIAL.iterdir()):
        add(path, "official-metadata/" + path.name, "fresh_primary_metadata_corroboration")

    logs = ["f4-product-refcount-independent.log", "f4-property-missing.log", "f4-property-guarded.log", "f4-property-present.log",
            "f4-qt-return-dynamic_names.log", "f4-qt-return-object_name.log", "f4-qt-return-property_bool.log",
            "f4-qt-return-property_none.log", "f4-qt-return-style_polish.log", "f4-qt-return-void_update.log", "f4-pyside-pip-index.log"]
    for name in logs:
        add(COLLAB / name, "negative/refcount/" + name, "independent_refcount_original")
    scripts = ["f4-property-refcount-independent.py", "f4-product-refcount-independent.py", "f4-qt-return-control-independent.py",
               "smoke_qt_binding_lifetime_candidate.py", "f4-create-qt-environments.py", "f4-download-linux-wheels.py",
               "f4-isolate-qt-env-data.py", "f4-stop-owned-slow-pip.py", "f4-build-linux-qtvalidation.py",
               "f4-run-qt-version-validation.py", "f4-qt-test-wrapper.py", "f4-qt-run-capture-wrapper.py",
               "f4-write-qt-dependency-proposal.py", Path(__file__).name]
    for name in scripts:
        add(COLLAB / name, "scripts/" + name, "current_used_probe_launcher_or_collector")
    for name in ("f4-ci-independent-diagnosis.md", "f4-ci-independent-scope.md", "f4-ci-failure-notification.md", "f4-ci-checkpoint.md"):
        add(COLLAB / name, "context/" + name, "original_analysis_context")
    for name in ("41047666520-artifacts-api.json", "41047666520-run.json", "41047666520-jobs-api.json", "job-124035633907.log"):
        add(CI / name, "negative/ci/" + name, "original_ci_api_or_job_log")
    for path in (OLD_REPORT, OLD_REPORT.parent / "gui_f4_inspect_backend.log", OLD_REPORT.parent / "gui_run_inputs.log"):
        add(path, "negative/ci/integration/" + path.name, "original_failed_ci_case")
    for name, path in TARGETS.items():
        if name != "binding":
            add(path, "validated-test-snapshots/" + path.name, "script_sha_matches_both_final_results")
    add(ROOT / "tools/test_assert_probe.py", "scripts/test_assert_probe.py", "current_v3_assertion_probe_snapshot")

    assert len({name.casefold() for _, name, _ in selection}) == len(selection)
    DEST.mkdir(exist_ok=False)
    rows = []
    for source, relative, category in selection:
        raw = source.read_bytes()
        target = DEST / relative
        assert target.resolve().is_relative_to(DEST.resolve())
        assert target.suffix not in {".whl", ".part", ".zip", ".exe", ".dll", ".so"}
        write_new(target, raw)
        copied = target.read_bytes()
        assert copied == raw == source.read_bytes(), source
        rows.append({"source_absolute_path": str(source), "copied_relative_path": relative,
                     "source_bytes": len(raw), "source_sha256": sha(raw), "copied_bytes": len(copied),
                     "copied_sha256": sha(copied), "source_unchanged_after_copy": True, "category": category})
    exclusions = [
        {"source": str(SOURCE / "wheelhouse"), "reason": "wheel payloads omitted; each retained official wheel freshly SHA-verified in official receipt"},
        {"source": str(SOURCE / "numerical-wheelhouse"), "reason": "large dependency wheels omitted; original pip reports retain public download hashes and install metadata"},
        {"source": "/home/u123/g4-f4-qt-validation-build114-20261030", "reason": "build tree and executables omitted; build receipt/capabilities/executable hash retained"},
        *({"source": f"/home/u123/venvs/g4-f4-qt-{version}-20261030", "reason": "venv omitted; identity/pip receipts retained"} for version in VERSIONS),
        {"source": str(CI / "linux-evidence-11.4.3.zip"), "reason": "original retained and checked against official digest; selected report/log bytes verified equal to ZIP members; parent historical CI archive owns original container"},
        {"source": str(SOURCE / "validation-*/*/"), "reason": "only immediate result files selected; state/history/generated packages/font caches omitted, except explicit raw backend error capture"},
    ]
    manifest = {"schema": "f4_qt_dependency_evidence_manifest_v1", "created_utc": utc(), "root": str(DEST),
                "scope": "Targeted dependency evidence, not formal new-freeze matrix, CI acceptance, or F4 closure",
                "copied_files": len(rows), "copied_bytes_total": sum(row["copied_bytes"] for row in rows),
                "hash_algorithm": "sha256_raw_file_bytes", "files": rows, "excluded_sources": exclusions,
                "official_wheel_hashes_verified": len(official), "evidence_semantic_checks": validation,
                "boundaries": ["Original CI quiet pip did not directly record its installed PySide6 version.",
                    "Fresh official metadata fetched during collection is corroboration, not the original download response.",
                    "Scripts preserve their final used/current state; earlier launcher revisions were not separately frozen.",
                    "Backend Git identity remains unknown; GUI native Git receipt is separately 096f4b3.",
                    "Old dependency proposal wording is retained as historical proposal; parent owns final scoped implementation."]}
    write_json(DEST / "manifest.json", manifest)
    write_new(DEST / "manifest.sha256.txt", (digest_file(DEST / "manifest.json") + "  manifest.json\n").encode())

    # Second pass reopens both source and destination after all copies finished.
    for row in rows:
        assert digest_file(Path(row["source_absolute_path"])) == row["source_sha256"]
        target = DEST / row["copied_relative_path"]
        assert target.stat().st_size == row["copied_bytes"]
        assert digest_file(target) == row["source_sha256"] == row["copied_sha256"]
    write_json(DEST / "copy-verification.json", {"verified_utc": utc(), "manifest_sha256": digest_file(DEST / "manifest.json"),
               "files_checked": len(rows), "source_still_equal": True, "destination_equal": True,
               "bytes_checked": manifest["copied_bytes_total"], "all_passed": True})

    text = """# F4 Qt dependency evidence collection

This is an out-only byte-copy evidence collection, not new-freeze acceptance or phase closure.

- `final/6.11.1` and `final/6.11.3`: four original cases each, 8 + 45 + 103 + 257 = 413 assertions, all natural exit 0. Both original test sources are unchanged and their SHA matches each result receipt. The run-input case records a real 3/3-event backend run.
- `negative/ci`: original 5d6f008 CI report/logs with 45/103 assertions followed by none_dealloc and -6. Selected bytes were compared with official artifact 12974006530. Its original ZIP remains at the absolute path recorded in manifest, with the official digest verified. Exact PySide version was not directly logged by that old quiet-pip CI step.
- `negative/refcount` and `receipts/linux-6120-binding-negative.log`: independent local CPython 3.11.18 / PySide6-shiboken6 6.12.0 defect controls, including ordinary void calls and actual product functions. This evidence is scoped to that verified combination.
- `negative/loader`: a separate libQt6DBus symbol mismatch caused by globally injecting the Geant4 conda lib directory. These are import failures, not the None defect.
- `negative/missing-data`: the subsequent run-input failures at 75 assertions. Captured stderr identifies missing G4ENSDFSTATEDATA; final data-discovery receipts show required data complete. The `.jsonl.txt` file keeps its original JSONL bytes.
- `official-metadata`: fresh raw official PyPI responses for both matching Qt quartets and new receipt cross-checking the 8 retained wheel SHA values. These requests occurred during evidence collection, not at original installation time. No wheel payload is copied.
- `receipts`: original download/installation/pip-check/build/identity logs and earlier proposal. Early canceled downloads and inherited-package conflict attempts remain historical, not final install proof.
- `scripts`: current key probes/install/build/test launchers and the collector. Final scripts are preserved; superseded early launcher revisions were not separately frozen. `validated-test-snapshots` contains original target scripts with SHA proven equal to final receipts.

`manifest.json` maps every copied payload to its original absolute path, raw SHA, bytes and category. `copy-verification.json` records a second source/destination hash pass. Original files, environments, wheelhouse and backend builds are retained; no cleanup occurred. The backend accurately reports Git identity unknown for the WSL-mounted Windows worktree; GUI Git 096f4b3 is a separate native receipt.

Parent archive input: append the flat JSON argv array in the sibling `f4-qt-dependency-include-file-argv.json` to `prepare-f4-archive.py` arguments. The helper accepts repeated `--include-file <path>` and assigns `additional/<index>-<basename>`; its own generated plan maps paths. No invented colon syntax or `--include-root` is used. The included `archive-inputs.json` maps collection-relative paths to stable argv order. The helper preserves Markdown bytes as `.md.txt` by design. This input does not request publication, a new matrix, or stage closure.
"""
    write_new(DEST / "README.md", text.encode("utf-8"))
    # Index itself is included last; avoid a recursively self-hashed manifest.
    include_files = sorted(path for path in DEST.rglob("*") if path.is_file())
    input_rows = [{"include_order": index, "collection_relative_path": path.relative_to(DEST).as_posix(),
                   "source_absolute_path": str(path), "sha256": digest_file(path), "bytes": path.stat().st_size}
                  for index, path in enumerate(include_files, 1)]
    write_json(DEST / "archive-inputs.json", {"schema": "f4_qt_dependency_archive_inputs_v1",
               "helper": str(COLLAB / "prepare-f4-archive.py"), "option": "--include-file",
               "note": "Order is local to this list; parent additions can shift helper's final additional/ numbering. This file is included last; no recursive self-hash.",
               "inputs": input_rows})
    include_files.append(DEST / "archive-inputs.json")
    argv = [item for path in include_files for item in ("--include-file", str(path))]
    write_json(COLLAB / "f4-qt-dependency-include-file-argv.json", argv)
    write_json(COLLAB / "f4-qt-dependency-collection-receipt.json", {
        "completed_utc": utc(), "collection_root": str(DEST), "original_copies": len(rows),
        "copied_bytes": manifest["copied_bytes_total"], "include_file_count": len(include_files),
        "manifest_sha256": digest_file(DEST / "manifest.json"),
        "argv_file": str(COLLAB / "f4-qt-dependency-include-file-argv.json"),
        "argv_sha256": digest_file(COLLAB / "f4-qt-dependency-include-file-argv.json"),
        "verification": "all original/source/copy hashes and selected semantic checks passed",
    })
    print(json.dumps(read_json(COLLAB / "f4-qt-dependency-collection-receipt.json"), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    collect()
