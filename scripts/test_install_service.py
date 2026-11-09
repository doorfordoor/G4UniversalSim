"""I2 controlled install, tamper rejection, cancellation, resume and recovery."""
from __future__ import annotations

import copy
import json
import os
import sys
import tempfile
import zipfile
import subprocess
import time
from pathlib import Path
from unittest.mock import patch
from concurrent.futures import ThreadPoolExecutor

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from test_install_plan import arguments, fixture, service


def expect_error(call, code):
    try:
        call()
    except service.InstallError as exc:
        assert exc.code == code, (exc.code, str(exc))
    else:
        assert False, f"Expected {code}"


def ar5_service_contract(catalog, args, root):
    # Construct the historical v1 wire form once. Verification/execution must
    # retain these signed bytes rather than upgrading/re-signing the old plan.
    legacy = service.create_plan(catalog, **args)
    legacy.pop("path_validation")
    for artifacts in (legacy["artifacts"], legacy["release"]["artifacts"]):
        for artifact in artifacts:
            for file in artifact["files"]:
                file.pop("executable", None)
    legacy["plan_sha256"] = service._digest({k: v for k, v in legacy.items() if k not in ("space", "plan_sha256")})
    frozen = service._json(legacy)
    prefix = Path(args["prefix"])
    writer = service._write_json
    def fail_final_marker(path, value, **kwargs):
        if Path(path) == prefix / service.MARKER:
            raise OSError("AR5 A prepared legacy receipt fixture")
        return writer(path, value, **kwargs)
    with patch.object(service, "_write_json", side_effect=fail_final_marker):
        receipt = service.execute_plan(legacy)
    assert receipt["status"] == "published_with_warning", receipt
    marker = prefix / service.MARKER
    old_inventory = service.load_catalog(marker)["files"]
    assert all("executable" not in file for file in old_inventory)
    assert service.recover_installation(prefix, allowed_root=root)["published_prefix_preserved"]
    raw = marker.read_bytes()
    assert service.verify_installation(prefix)["receipt"]["files"] == old_inventory
    assert marker.read_bytes() == raw and service._json(legacy) == frozen
    assert service.load_catalog(marker)["plan_sha256"] == legacy["plan_sha256"]
    for invalid in (None, 0, "false"):
        changed = json.loads(raw)
        changed["files"][0]["executable"] = invalid
        marker.write_text(json.dumps(changed), encoding="utf-8")
        expect_error(lambda: service.verify_installation(prefix), "file_mode")
        expect_error(lambda: service.uninstall_installation(prefix), "file_mode")
        marker.write_bytes(raw)
    assert service.uninstall_installation(prefix)["status"] == "uninstalled"
    assert service._json(legacy) == frozen
    # Explicit false is symmetric with the missing legacy flag, and no
    # verification path silently chmods mismatches back to the declaration.
    plan = service.create_plan(catalog, **args)
    assert service.execute_plan(plan)["status"] == "published"
    target = prefix / "bin/backend"
    if os.name != "nt":
        target.chmod(0o744)
        expect_error(lambda: service.verify_installation(prefix), "installed_file_mode")
        expect_error(lambda: service.uninstall_installation(prefix), "installed_file_mode")
        assert target.stat().st_mode & 0o111
        target.chmod(0o644)
    service.uninstall_installation(prefix)
    # A tiny real archive exercises declared-true as well as false/omitted.
    from test_install_plan import builder
    archive = root / "modes.zip"
    with zipfile.ZipFile(archive, "w") as output:
        for name, mode in (("tool", 0o100755), ("LICENSE", 0o100644)):
            entry = zipfile.ZipInfo(name)
            entry.create_system = 3
            entry.external_attr = mode << 16
            output.writestr(entry, b"mode fixture, not an executable SDK")
    modes = builder.catalog_from_archive(archive, profile=args["profile"], platform=args["platform"],
        architecture=args["architecture"], version=args["version"], origin="local mode fixture",
        license_path="LICENSE", license_expression="LicenseRef-TestFixture", license_source="local mode fixture")
    mode_plan = service.create_plan(modes, **args)
    assert service.execute_plan(mode_plan)["status"] == "published"
    assert service.verify_installation(prefix)["status"] == "verified"
    if os.name != "nt":
        target = prefix / "tool"
        target.chmod(0o644)
        expect_error(lambda: service.verify_installation(prefix), "installed_file_mode")
        assert not target.stat().st_mode & 0o111
        target.chmod(0o701)  # any-x, not owner-only or os.access semantics
        assert service.verify_installation(prefix)["status"] == "verified"
    service.uninstall_installation(prefix)
    if os.name != "nt":
        for chosen, mode in ((plan, 0o744), (mode_plan, 0o644)):
            name = "bin/backend" if chosen is plan else "tool"
            def tamper_mode(event):
                if event["stage"] == "extract":
                    (service._txn_path(prefix) / "payload" / name).chmod(mode)
            failed = service.execute_plan(chosen, progress=tamper_mode)
            assert failed["status"] == "failed" and failed["diagnostics"][0]["code"] == "staged_file_mode", failed
            assert not prefix.exists()
            service.recover_installation(prefix, allowed_root=root)
        print("AR5 A POSIX real any-x staged/installed positive and negative controls passed")
    else:
        print("AR5 A POSIX mode controls NOT EXECUTED on Windows; require independent Linux execution")
    # Real private-prefix installation, then a mock configure boundary ONLY:
    # inspect actual argv/env construction without invoking a compiler or SDK.
    archive = root / "sdk-paths.zip"
    with zipfile.ZipFile(archive, "w") as output:
        for name in ("Bin/tool", "Dev/Geant4/Geant4Config.cmake", "Dev/Probe/CMakeLists.txt",
                     "Deps/Bin/library", "Deps/Lib/library", "HeaderOnly/include/a.h", "LICENSE"):
            output.writestr(name, b"SDK path fixture, not a development kit")
    windows = args["platform"] == "windows"
    sdk = {"geant4_dir": "dev/geant4" if windows else "Dev/Geant4",
           "probe_source": "dev/probe" if windows else "Dev/Probe",
           "dependency_prefixes": ["deps", "headeronly"] if windows else ["Deps", "HeaderOnly"],
           "cmake_paths": {"CustomFile": "deps/lib/library" if windows else "Deps/Lib/library"}}
    catalog_sdk = builder.catalog_from_archive(archive, profile="sdk", platform=args["platform"],
        architecture=args["architecture"], version=args["version"], origin="local SDK path fixture",
        license_path="LICENSE", license_expression="LicenseRef-TestFixture", license_source="local fixture",
        sdk=sdk, dependencies=[{"id": "compiler"}, {"id": "cmake"}])
    sdk_plan = service.create_plan(catalog_sdk, **(args | {"profile": "sdk"}))
    assert sdk_plan["status"] == "planned", sdk_plan
    assert service.execute_plan(sdk_plan)["status"] == "published"
    raw = (prefix / service.MARKER).read_bytes()
    captured = []
    def configure_boundary(report, installed, selected_prefix, build, stage, argv, env, timeout):
        captured.append((argv, env))
        report["commands"].append({"stage": stage, "argv": argv, "cwd": str(build), "exit_code": 1})
        service._append_failure(report, stage, service.InstallError("sdk_command", "controlled configure boundary"))
        return False  # wiring-only fixture, deliberately never invokes the owned SDK adapter
    with patch.object(service, "_run_sdk_command", side_effect=configure_boundary):
        probe = service.probe_sdk(prefix, build_directory=root / "path-probe", cmake=sys.executable)
    assert probe["status"] == "failed" and probe["diagnostics"][0]["code"] == "sdk_command", probe
    assert len(captured) == 1 and len(probe["commands"]) == 1
    argv, env = captured[0]
    assert argv[argv.index("-S") + 1] == str(prefix / "Dev/Probe")
    assert f"-DGeant4_DIR={prefix / 'Dev/Geant4'}" in argv
    assert f"-DCustomFile={prefix / 'Deps/Lib/library'}" in argv
    assert f"-DCMAKE_PREFIX_PATH={prefix / 'Deps'};{prefix / 'HeaderOnly'}" in argv
    expected_bins = ["Bin", "Deps/Bin", "HeaderOnly/bin"] if windows else ["bin", "Deps/bin", "HeaderOnly/bin"]
    assert probe["sdk_process_search_paths"] == [str(prefix / name) for name in expected_bins]
    assert env["PATH"].split(os.pathsep)[:3] == probe["sdk_process_search_paths"]
    assert not (prefix / "HeaderOnly/bin").exists() and not (prefix / "HeaderOnly/lib").exists()
    if not windows:
        assert env["LD_LIBRARY_PATH"].split(os.pathsep)[:2] == [str(prefix / 'Deps/lib'), str(prefix / 'HeaderOnly/lib')]
        assert not (prefix / "bin").exists() and not (prefix / "Deps/lib").exists()
    assert (prefix / service.MARKER).read_bytes() == raw
    assert service.uninstall_installation(prefix)["status"] == "uninstalled"
    print("AR5 A real fixture inventory / mocked SDK configure argv-env binding passed (no SDK executed)")
    print("AR5 A legacy plan/receipt verify/recover/uninstall passed without normalization")


def ar5_recovery_contract(root):
    evidence = Path(os.environ.get("G4USIM_TEST_EVIDENCE_DIR", str(root))) / "B-recovery"
    evidence.mkdir(parents=True, exist_ok=True)
    cases = []

    def setup(name, published=False):
        folder = root / name
        folder.mkdir()
        catalog = fixture(folder)
        args = arguments(catalog, folder)
        plan = service.create_plan(catalog, **args)
        prefix = Path(args["prefix"])
        if published:
            writer = service._write_json
            def fail_marker(path, value, **kwargs):
                if Path(path) == prefix / service.MARKER:
                    raise OSError("B fixture interruption before published marker")
                return writer(path, value, **kwargs)
            with patch.object(service, "_write_json", side_effect=fail_marker):
                receipt = service.execute_plan(plan)
            assert receipt["status"] == "published_with_warning", receipt
        else:
            receipt = service.execute_plan(plan, cancel=lambda: True)
            assert receipt["status"] == "cancelled", receipt
        txn = service._txn_path(prefix)
        journal = service.load_catalog(txn / service.JOURNAL)
        return folder, prefix, txn, journal, plan

    def write(path, value):
        path.write_text(json.dumps(value), encoding="utf-8")

    def raw_state(folder):
        return {p.relative_to(folder).as_posix(): service._file_hash(p) if p.is_file() else "directory"
                for p in folder.rglob("*")}

    def save(name, folder, result):
        record = {"case": name, "result": result, "remaining": raw_state(folder)}
        cases.append(record)
        (evidence / "results.json").write_text(json.dumps(cases, indent=2), encoding="utf-8")
        print("B_RECOVERY", name, result, flush=True)

    def blocked(name, folder, call, code):
        before = raw_state(folder)
        # Keep exact original JSON inputs as well as a whole-tree hash list.
        dest = evidence / name
        dest.mkdir()
        for p in folder.rglob("*"):
            if p.is_file() and (p.name.endswith(".json") or p.name.endswith(".new")):
                target = dest / p.relative_to(folder)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(p.read_bytes())
        (dest / "before.json").write_text(json.dumps(before, indent=2))
        expect_error(call, code)
        assert raw_state(folder) == before, name
        save(name, folder, "blocked_zero_write:" + code)

    # Forward staging and failure updates; never auto-publish an unpublished payload.
    folder, prefix, txn, journal, plan = setup("staging-update")
    journal["status"] = "staging"
    write(txn / service.JOURNAL, journal)
    newer = copy.deepcopy(journal)
    newer["events"].append({"stage": "extract", "status": "verified", "time_ns": 1})
    write(txn / (service.JOURNAL + ".new"), newer)
    assert service.recover_installation(prefix, allowed_root=folder)["status"] == "recovered"
    assert not prefix.exists() and not txn.exists()
    save("staging-update", folder, "discarded_without_publication")

    folder, prefix, txn, journal, plan = setup("failure-update")
    journal["status"] = "staging"
    write(txn / service.JOURNAL, journal)
    newer = copy.deepcopy(journal)
    newer["status"] = "failed"
    newer["diagnostics"].append({"code": "test_first_cause", "message": "retained"})
    write(txn / (service.JOURNAL + ".new"), newer)
    result = service.execute_plan(plan, resume=True)
    assert result["status"] == "published" and result["diagnostics"] == newer["diagnostics"], result
    service.uninstall_installation(prefix)
    save("failure-update", folder, "resumed_preserving_diagnostics")

    folder, prefix, txn, journal, plan = setup("resume-only")
    newer = copy.deepcopy(journal)
    newer["status"] = "staging"
    write(txn / (service.JOURNAL + ".new"), newer)
    blocked("resume-only-discard", folder, lambda: service.recover_installation(prefix, allowed_root=folder), "unsupported_recovery_state")
    assert service.execute_plan(plan, resume=True)["status"] == "published"
    service.uninstall_installation(prefix)
    save("resume-only", folder, "explicit_resume_accepted")

    # Both exact temporaries must pass before either one is promoted.
    for broken in ("journal", "marker", "both-valid"):
        folder, prefix, txn, journal, plan = setup("dual-" + broken, published=True)
        marker = service.load_catalog(prefix / service.MARKER)
        marker["status"] = "published"
        newer = copy.deepcopy(journal)
        if broken == "journal":
            newer["transaction_id"] = "f" * 32
        if broken == "marker":
            marker["files"][0]["sha256"] = "0" * 64
        write(prefix / (service.MARKER + ".new"), marker)
        write(txn / (service.JOURNAL + ".new"), newer)
        if broken != "both-valid":
            blocked("dual-" + broken, folder, lambda: service.recover_installation(prefix, allowed_root=folder),
                    "recovery_identity" if broken == "journal" else "recovery_inventory")
        else:
            result = service.recover_installation(prefix, allowed_root=folder, transaction_id=journal["transaction_id"])
            assert result["published_prefix_preserved"]
            assert not txn.exists() and not (prefix / (service.MARKER + ".new")).exists()
            frozen = raw_state(folder)
            again = service.recover_installation(prefix, allowed_root=folder, transaction_id=journal["transaction_id"])
            assert again["status"] == "already_recovered" and raw_state(folder) == frozen
            expect_error(lambda: service.recover_installation(prefix, allowed_root=folder), "recovery_identity_missing")
            expect_error(lambda: service.recover_installation(prefix, allowed_root=folder, transaction_id="0" * 32), "recovery_identity")
            assert raw_state(folder) == frozen
            service.uninstall_installation(prefix)
            save("dual-valid", folder, "both_promoted_verified_and_idempotent_with_explicit_id")

    for name, raw, code in (("empty", "", None), ("truncated", "{", None),
                            ("duplicate", '{"x":1,"x":2}', "duplicate_key"),
                            ("nonfinite", '{"x":NaN}', "nonfinite")):
        folder, prefix, txn, journal, plan = setup("json-" + name)
        (txn / (service.JOURNAL + ".new")).write_text(raw)
        if code is not None:
            blocked("json-" + name, folder, lambda: service.recover_installation(prefix, allowed_root=folder), code)
        else:
            before = raw_state(folder)
            try:
                service.recover_installation(prefix, allowed_root=folder)
            except json.JSONDecodeError:
                pass
            else:
                assert False, name
            assert raw_state(folder) == before
            save("json-" + name, folder, "invalid_json_zero_write")

    for name in ("prepared-journal", "published-without-prefix", "unknown-new", "unknown-payload",
                 "changed-plan", "lost-first-cause", "failed-after-publication"):
        folder, prefix, txn, journal, plan = setup(name, published=name == "failed-after-publication")
        code = "unsupported_recovery_state"
        if name == "prepared-journal":
            journal["status"] = "prepared";write(txn / service.JOURNAL, journal)
        elif name == "published-without-prefix":
            journal.update(service._publication_fields(plan), status="published")
            write(txn / service.JOURNAL, journal);code = "recovery_identity"
        elif name in ("unknown-new", "unknown-payload"):
            (txn / ("unrelated.new" if name == "unknown-new" else "payload/unknown")).write_bytes(b"do not delete")
            code = "recovery_unknown_member"
        else:
            newer = copy.deepcopy(journal)
            if name == "changed-plan":
                newer["plan"]["version"] = "9.9.9";code = "transaction_plan"
            elif name == "lost-first-cause":
                newer["diagnostics"] = [];code = "recovery_history"
            else:
                newer["status"] = "failed"
            write(txn / (service.JOURNAL + ".new"), newer)
        blocked(name, folder, lambda: service.recover_installation(prefix, allowed_root=folder), code)

    # Mutual agreement is not proof: marker/journal cannot invent file hashes.
    folder, prefix, txn, journal, plan = setup("mutually-forged", published=True)
    marker = service.load_catalog(prefix / service.MARKER)
    for value in (journal, marker):
        value["files"][0]["sha256"] = "0" * 64
    write(txn / service.JOURNAL, journal);write(prefix / service.MARKER, marker)
    blocked("mutually-forged", folder, lambda: service.recover_installation(prefix, allowed_root=folder), "recovery_inventory")

    # Exact .part uses Path.with_suffix, and partial cleanup keeps journal last.
    for point in ("data", "before-journal", "after-journal", "rmdir"):
        folder, prefix, txn, journal, plan = setup("partial-" + point)
        archive = txn / "archives" / plan["artifacts"][0]["id"]
        part = archive.with_suffix(".part")
        part.write_bytes(b"incomplete archive")
        original = service._remove_observed_member
        journal_path = txn / service.JOURNAL
        fired = []
        def interrupt(path, snapshot):
            if point != "rmdir" and not fired and ((point == "data" and path == part) or (point != "data" and path == journal_path)):
                fired.append(str(path))
                if point != "before-journal":
                    original(path, snapshot)
                raise OSError("B injected cleanup interruption " + point)
            return original(path, snapshot)
        original_rmdir = Path.rmdir
        def interrupt_rmdir(path):
            if point == "rmdir" and path == txn:
                fired.append(str(path))
                raise OSError("B injected cleanup interruption rmdir")
            return original_rmdir(path)
        with patch.object(service, "_remove_observed_member", side_effect=interrupt), \
                patch.object(Path, "rmdir", interrupt_rmdir):
            try:
                service.recover_installation(prefix, allowed_root=folder)
            except OSError as exc:
                assert "B injected cleanup" in str(exc)
            else:
                assert False, point
        assert fired
        if point not in ("after-journal", "rmdir"):
            assert journal_path.is_file()
            assert service.recover_installation(prefix, allowed_root=folder)["status"] == "recovered"
            assert not txn.exists()
        else:
            assert txn.is_dir() and not list(txn.iterdir())
            for requested in (None, journal["transaction_id"], "0" * 32):
                blocked("orphan-" + point + "-" + str(requested), folder,
                        lambda: service.recover_installation(prefix, allowed_root=folder, transaction_id=requested),
                        "recovery_identity_missing")
        save("partial-" + point, folder, "bounded_reentry" if point in ("data", "before-journal") else "lost_identity_blocked")

    folder, prefix, txn, journal, plan = setup("published-orphan", published=True)
    (txn / service.JOURNAL).unlink()  # simulate old rmtree / host death, not service authorization
    blocked("published-orphan", folder,
            lambda: service.recover_installation(prefix, allowed_root=folder, transaction_id=journal["transaction_id"]),
            "recovery_identity_missing")

    folder, prefix, txn, journal, plan = setup("same-bytes-new-identity")
    prepared = service._prepare_recovery(txn, prefix, folder)
    path = txn / service.JOURNAL
    replacement = folder / "replacement.json"
    replacement.write_bytes(path.read_bytes())
    os.replace(replacement, path)
    blocked("same-bytes-new-identity", folder, lambda: service._apply_recovery_updates(prepared), "recovery_changed")

    folder, prefix, txn, journal, plan = setup("promotion-race", published=True)
    marker = service.load_catalog(prefix / service.MARKER)
    marker["status"] = "published"
    write(prefix / (service.MARKER + ".new"), marker)
    write(txn / (service.JOURNAL + ".new"), journal)
    original_replace = os.replace
    fired = []
    def replace_then_exchange(source, target):
        original_replace(source, target)
        if Path(target) == prefix / service.MARKER and not fired:
            fired.append(True)
            replacement = folder / "external-exchange"
            replacement.write_bytes(Path(target).read_bytes())
            original_replace(replacement, target)
    with patch.object(service.os, "replace", side_effect=replace_then_exchange):
        expect_error(lambda: service.recover_installation(prefix, allowed_root=folder), "recovery_changed")
    assert fired and (txn / (service.JOURNAL + ".new")).is_file() and (txn / service.JOURNAL).is_file()
    assert (prefix / "bin/backend").is_file()
    save("promotion-race", folder, "stopped_after_external_identity_exchange_no_journal_promotion_or_cleanup")

    folder, prefix, txn, journal, plan = setup("changed-observation")
    prepared = service._prepare_recovery(txn, prefix, folder)
    (txn / "payload" / "bin").mkdir()
    (txn / "payload" / "bin/backend").write_bytes(b"arrived after snapshot")
    blocked("changed-observation", folder, lambda: service._apply_recovery_updates(prepared), "recovery_changed")

    # Interrupt the real writer before its first marker replace, leaving a
    # staging journal and a genuinely published tree with a prepared marker.
    class WriterBoundary(BaseException):
        pass

    for fault in ("none", "marker-replace", "strict-prefix", "marker-exchange"):
        name = "generated-marker-" + fault
        folder = root / name
        folder.mkdir()
        catalog = fixture(folder)
        args = arguments(catalog, folder)
        plan = service.create_plan(catalog, **args)
        prefix = Path(args["prefix"])
        txn = service._txn_path(prefix)
        marker, journal_path = prefix / service.MARKER, txn / service.JOURNAL
        marker_temp = marker.with_name(marker.name + ".new")
        journal_temp = journal_path.with_name(journal_path.name + ".new")
        replace, verify = os.replace, service._verify_installation

        def interrupt_writer(source, target):
            if Path(target) == marker:
                assert Path(source) == marker_temp
                raise WriterBoundary()
            return replace(source, target)

        with patch.object(service.os, "replace", side_effect=interrupt_writer):
            try:
                service.execute_plan(plan)
            except WriterBoundary:
                pass
            else:
                raise AssertionError("Writer did not reach real marker replace")
        write(journal_temp, dict(service.load_catalog(marker_temp), plan=plan))
        marker_temp.unlink()
        assert service.load_catalog(marker)["status"] == "prepared"
        assert service.load_catalog(journal_path)["status"] == "staging"
        base_raw, temp_raw = journal_path.read_bytes(), journal_temp.read_bytes()
        trace = []
        payload = prefix / "bin/backend"
        payload_raw = payload.read_bytes()

        def observe_replace(source, target):
            target = Path(target)
            if target == marker:
                trace.append("marker")
                assert journal_path.read_bytes() == base_raw and journal_temp.read_bytes() == temp_raw
                if fault == "marker-replace":
                    raise OSError("B2 marker replace fault")
                replace(source, target)
                if fault == "marker-exchange":
                    other = folder / "external-marker"
                    other.write_bytes(target.read_bytes())
                    replace(other, target)
                return
            if target == journal_path:
                trace.append("journal")
            return replace(source, target)

        def observe_verify(path, **kwargs):
            if not kwargs.get("_prepared"):
                trace.append("strict")
                assert service.load_catalog(marker)["status"] == "published"
                assert journal_path.read_bytes() == base_raw and journal_temp.read_bytes() == temp_raw
                if fault == "strict-prefix":
                    payload.write_bytes(b"late foreign payload bytes")
            return verify(path, **kwargs)

        def recover():
            return service.recover_installation(prefix, allowed_root=folder)

        with patch.object(service.os, "replace", side_effect=observe_replace), \
                patch.object(service, "_verify_installation", side_effect=observe_verify):
            if fault == "none":
                assert recover()["status"] == "recovered"
                assert trace == ["marker", "strict", "journal"] and not txn.exists()
            elif fault == "marker-replace":
                try:
                    recover()
                except OSError as exc:
                    assert str(exc) == "B2 marker replace fault"
                else:
                    raise AssertionError("Marker replace fault was not observed")
                assert trace == ["marker"] and marker_temp.is_file()
                assert service.load_catalog(marker)["status"] == "prepared"
            else:
                expect_error(recover, "installed_file_changed" if fault == "strict-prefix" else "recovery_changed")
                assert trace == (["marker", "strict"] if fault == "strict-prefix" else ["marker"])
        records = evidence / name
        records.mkdir()
        (records / "journal-base.before").write_bytes(base_raw)
        (records / "journal-temp.before").write_bytes(temp_raw)
        (records / "trace.json").write_text(json.dumps(trace), encoding="utf-8")
        if fault != "none":
            assert journal_path.read_bytes() == base_raw and journal_temp.read_bytes() == temp_raw
            (records / "journal-base.after").write_bytes(journal_path.read_bytes())
            (records / "journal-temp.after").write_bytes(journal_temp.read_bytes())
            if fault == "strict-prefix":
                payload.write_bytes(payload_raw)
            assert recover()["status"] == "recovered" and not txn.exists()
        save(name, folder, "marker_then_strict_then_journal" if fault == "none" else "journal_retained_and_reentered")

    for late in ("bytes", "inode", "ancestor", "unknown-child", "prefix"):
        name = "member-late-" + late
        folder, prefix, txn, journal, plan = setup(name)
        archives = txn / "archives"
        member = (archives / plan["artifacts"][0]["id"]).with_suffix(".part")
        raw = b"staged incomplete bytes"
        member.write_bytes(raw)
        original_identity = member.stat().st_ino
        remove = service._remove_observed_member
        journal_path = txn / service.JOURNAL
        journal_raw = journal_path.read_bytes()
        fired = []

        def change_before_remove(path, snapshot):
            if path == member and late in ("bytes", "inode", "ancestor"):
                if late == "bytes":
                    member.write_bytes(b"changed incomplete bytes")
                    assert member.stat().st_ino == original_identity
                elif late == "inode":
                    other = folder / "external-file"
                    other.write_bytes(raw)
                    os.replace(other, member)
                    assert member.stat().st_ino != original_identity and member.read_bytes() == raw
                else:
                    moved = folder / "external-directory"
                    archives.rename(moved)
                    archives.mkdir()
                    (moved / member.name).rename(member)
                    assert member.stat().st_ino == original_identity and member.read_bytes() == raw
                fired.append(True)
            if path == archives and late == "unknown-child":
                (archives / "foreign").write_bytes(b"foreign bytes")
                fired.append(True)
            result = remove(path, snapshot)
            if path == archives and late == "prefix":
                prefix.mkdir()
                (prefix / "foreign").write_bytes(b"foreign bytes")
                fired.append(True)
            return result

        with patch.object(service, "_remove_observed_member", side_effect=change_before_remove):
            if late == "unknown-child":
                try:
                    service.recover_installation(prefix, allowed_root=folder)
                except OSError as exc:
                    assert Path(exc.filename) == archives
                else:
                    raise AssertionError("Nonempty directory unexpectedly removed")
            else:
                expect_error(lambda: service.recover_installation(prefix, allowed_root=folder), "recovery_changed")
        assert fired == [True] and journal_path.read_bytes() == journal_raw
        if late in ("bytes", "inode", "ancestor"):
            assert member.read_bytes() == (b"changed incomplete bytes" if late == "bytes" else raw)
        else:
            assert ((archives if late == "unknown-child" else prefix) / "foreign").read_bytes() == b"foreign bytes"
        save(name, folder, "changed_or_unknown_member_and_journal_retained")
    print("AR5 B recovery contracts passed", len(cases), "finite outcomes; isolated snapshot only")


def ar5_strict_plan_executable(root):
    """Malformed signed envelopes never enter unlocked work or acquire a lock."""
    root.mkdir(parents=True, exist_ok=False)
    catalog = fixture(root); args = arguments(catalog, root)
    plan = service.create_plan(catalog, **args)
    assert plan["executable"] is True
    prefix = Path(args["prefix"]); guard = service._sdk_guard_path(prefix)
    guard.write_bytes(b"private exact guard fixture")
    original_guard = guard.read_bytes()
    results = []
    def inventory():
        return {str(p.relative_to(root)): ("directory" if p.is_dir() else service._file_hash(p))
                for p in root.rglob("*")}
    for label, value in (("int-one",1),("int-zero",0),("null",None),("string","true"),("false",False)):
        malformed = copy.deepcopy(plan);malformed["executable"] = value
        malformed["plan_sha256"] = service._digest({k:v for k,v in malformed.items() if k not in ("space","plan_sha256")})
        before = inventory()
        with patch.object(service,"_prefix_lock",side_effect=AssertionError("invalid plan acquired lock")), \
                patch.object(service,"_execute_plan_unlocked",side_effect=AssertionError("invalid plan reached unlocked work")):
            report = service.execute_plan(malformed)
        assert report["status"] == "failed" and report["diagnostics"][0]["code"] == "plan_rejected", report
        assert inventory() == before and guard.read_bytes() == original_guard
        # The private executor independently rejects the same malformed shape.
        with patch.object(service,"_prefix",side_effect=AssertionError("invalid internal plan touched paths")):
            inner = service._execute_plan_unlocked(malformed)
        assert inner["status"] == "failed" and inner["diagnostics"][0]["code"] == "plan_rejected", inner
        assert inventory() == before and not prefix.exists() and not service._txn_path(prefix).exists()
        results.append({"case":label,"value":value,"public":report,"internal":inner,"zero_file_mutation":True})
    lock = service._prefix_lock
    with patch.object(service,"_prefix_lock",wraps=lock) as observed:
        blocked = service.execute_plan(plan)
    assert observed.call_count == 1 and blocked["diagnostics"][0]["code"] == "sdk_operation_pending", blocked
    assert guard.read_bytes() == original_guard and not prefix.exists() and not service._txn_path(prefix).exists()
    guard.unlink()  # fixture-owned guard removal, never production recovery
    with patch.object(service,"_prefix_lock",side_effect=service.InstallError("fixture_lock_denied","lock refusal")):
        locked = service.execute_plan(plan)
    assert locked["diagnostics"][0]["code"] == "fixture_lock_denied" and not prefix.exists()
    with patch.object(service,"_prefix_lock",wraps=lock) as observed:
        accepted = service.execute_plan(plan)
    assert observed.call_count == 1 and accepted["status"] == "published", accepted
    results.append({"case":"true","guard_rejection":blocked,"lock_rejection":locked,"accepted":accepted})
    (root/"strict-plan-results.json").write_text(json.dumps(results,indent=2),encoding="utf-8")
    print("C4 strict executable 1/0/null/string/false rejected before writes; True lock+guard+publish passed")


def main():
    if not __debug__:
        raise SystemExit("Install service tests require assertions; do not run with -O")
    with tempfile.TemporaryDirectory(prefix="g4usim-install-service-") as temp:
        root = Path(temp)
        catalog = fixture(root)
        args = arguments(catalog, root)
        ar5_recovery_contract(root)
        ar5_service_contract(catalog, args, root)
        plan = service.create_plan(catalog, **args)
        events = []
        result = service.execute_plan(plan, progress=events.append)
        assert result["status"] == "published", result
        assert result["capability_status"] == "not_probed"
        assert events[-1]["stage"] == "publish" and events[-1]["status"] == "published"
        prefix = Path(plan["prefix"])
        assert (prefix / "bin/backend").is_file()
        assert service.verify_installation(prefix)["file_count"] == 4
        assert not Path(root / ".installed.g4usim-install").exists()
        occupied = service.execute_plan(plan)
        assert occupied["status"] == "failed" and occupied["diagnostics"][0]["code"] == "prefix_occupied"
        (prefix / "user.txt").write_text("user file", encoding="utf-8")
        expect_error(lambda: service.uninstall_installation(prefix), "unknown_files")
        assert (prefix / "user.txt").read_text(encoding="utf-8") == "user file"
        (prefix / "user.txt").unlink()
        original = (prefix / "bin/backend").read_bytes()
        (prefix / "bin/backend").write_bytes(b"tampered")
        expect_error(lambda: service.uninstall_installation(prefix), "installed_file_changed")
        (prefix / "bin/backend").write_bytes(original)
        assert service.uninstall_installation(prefix)["status"] == "uninstalled"
        assert not prefix.exists()
        changed = copy.deepcopy(plan)
        changed["prefix"] = str(root / "arbitrary")
        assert service.execute_plan(changed)["diagnostics"][0]["code"] == "plan_changed"
        cancelled = service.execute_plan(plan, cancel=lambda: True)
        assert cancelled["status"] == "cancelled", cancelled
        assert not prefix.exists() and Path(cancelled["transaction_path"]).is_dir()
        inspected = service.inspect_transaction(prefix, allowed_root=root)
        assert inspected["resumable"] and inspected["plan"] == plan
        restart_code = ("import sys,json; " + f"sys.path.insert(0,{str(ROOT / 'gui')!r}); "
                        "from g4usim_gui.core.environment_install import inspect_transaction; "
                        "r=inspect_transaction(sys.argv[1],allowed_root=sys.argv[2]); "
                        "print(json.dumps({'resumable':r['resumable'],'hash':r['plan']['plan_sha256']}))")
        restarted = subprocess.run([sys.executable, "-c", restart_code, str(prefix), str(root)],
                                   capture_output=True, text=True, timeout=15)
        assert restarted.returncode == 0, restarted.stderr
        assert json.loads(restarted.stdout) == {"resumable": True, "hash": plan["plan_sha256"]}
        assert service.execute_plan(plan, resume=True)["status"] == "published"
        service.uninstall_installation(prefix)
        def tamper_staging(event):
            if event["stage"] == "extract":
                (root / ".installed.g4usim-install/payload/bin/backend").write_bytes(b"changed after extraction")
        tampered = service.execute_plan(plan, progress=tamper_staging)
        assert tampered["status"] == "failed" and tampered["diagnostics"][0]["code"] == "staged_file_changed", tampered
        assert not prefix.exists()
        service.recover_installation(prefix, allowed_root=root)
        # Real process owns the stable OS lock. Every shared mutation rejects it,
        # and killing that process releases the lock without deleting its inode.
        assert service.execute_plan(plan, cancel=lambda: True)["status"] == "cancelled"
        ready = root / "lock-ready"
        holder_code = ("import sys; from pathlib import Path; "
                       f"sys.path.insert(0,{str(ROOT / 'gui')!r}); "
                       "from g4usim_gui.core.environment_install import _prefix_lock; "
                       "lock=_prefix_lock(Path(sys.argv[1]),create=False); lock.__enter__(); "
                       "import os; Path(sys.argv[2]).write_text(str(os.getpid())); sys.stdin.read()")
        # Windows venv python.exe is a redirector process. Kill/wait must refer to
        # the actual CPython host that owns the OS lock, not just its launcher.
        holder_executable = getattr(sys, "_base_executable", sys.executable)
        holder = subprocess.Popen([holder_executable, "-c", holder_code, str(prefix), str(ready)], stdin=subprocess.PIPE)
        try:
            deadline = time.monotonic() + 10
            while not ready.exists() and time.monotonic() < deadline and holder.poll() is None:
                time.sleep(0.01)
            assert ready.exists() and holder.poll() is None
            assert int(ready.read_text()) == holder.pid, "Lock holder must be the actual interpreter process"
            busy = service.execute_plan(plan, resume=True)
            assert busy["status"] == "failed" and busy["diagnostics"][0]["code"] == "operation_busy", busy
            expect_error(lambda: service.recover_installation(prefix, allowed_root=root), "operation_busy")
            expect_error(lambda: service.uninstall_installation(prefix), "operation_busy")
            expect_error(lambda: service.verify_installation(prefix), "operation_busy")
            sdk_busy = service.probe_sdk(prefix, build_directory=root / "sdk-build", cmake=sys.executable)
            assert sdk_busy["diagnostics"][0]["code"] == "operation_busy"
        finally:
            holder.kill()
            holder.wait(timeout=10)
            holder.stdin.close()
        resumed_after_crash = service.execute_plan(plan, resume=True)
        assert resumed_after_crash["status"] == "published", resumed_after_crash
        assert service.verify_installation(prefix)["file_count"] == 4
        service.uninstall_installation(prefix)
        # Portable catalog relocated with its archive; original no longer exists.
        origin = root / "catalog-original"
        relocated = root / "catalog-relocated"
        origin.mkdir()
        relocated.mkdir()
        portable = copy.deepcopy(catalog)
        source_archive = Path(portable["releases"][0]["artifacts"][0]["source"]["path"])
        (origin / "runtime.zip").write_bytes(source_archive.read_bytes())
        portable["releases"][0]["artifacts"][0]["source"]["path"] = "runtime.zip"
        (origin / "catalog.json").write_text(json.dumps(portable), encoding="utf-8")
        (origin / "catalog.json").rename(relocated / "catalog.json")
        (origin / "runtime.zip").rename(relocated / "runtime.zip")
        origin.rmdir()
        moved = service.load_catalog(relocated / "catalog.json")
        assert moved["releases"][0]["artifacts"][0]["source"]["origin"] == portable["releases"][0]["artifacts"][0]["source"]["origin"]
        relocated_plan = service.create_plan(moved, **args)
        assert relocated_plan["executable"], relocated_plan
        assert service.execute_plan(relocated_plan)["status"] == "published"
        service.uninstall_installation(prefix)
        portable["releases"][0]["artifacts"][0]["source"]["path"] = "../runtime.zip"
        (relocated / "escape.json").write_text(json.dumps(portable), encoding="utf-8")
        expect_error(lambda: service.load_catalog(relocated / "escape.json"), "archive_path")
        # Generated absolute data pointer has distinct original/read and installed
        # byte identities; it must continue to verify and uninstall exactly.
        configured = copy.deepcopy(catalog)
        artifact = configured["releases"][0]["artifacts"][0]
        configured_archive = root / "configured.zip"
        with zipfile.ZipFile(configured_archive, "w") as output:
            output.writestr("bin/geant4-data.txt", "# original template\n")
            output.writestr("data/Dataset/file.dat", b"actual fixture data")
            output.writestr("licenses/LICENSE.txt", b"fixture terms\n")
        from test_install_plan import builder
        configured = builder.catalog_from_archive(configured_archive, profile=args["profile"], platform=args["platform"],
                                                  architecture=args["architecture"], version=args["version"],
                                                  origin="fixture data artifact", license_path="licenses/LICENSE.txt",
                                                  license_expression="LicenseRef-TestFixture", license_source="local fixture")
        configured["releases"][0]["configuration"] = {"data_root": "data", "data_pointer": "bin/geant4-data.txt"}
        if os.name == "nt":
            configured["releases"][0]["configuration"] = {"data_root": "DATA", "data_pointer": "BIN/GEANT4-DATA.TXT"}
        configured_plan = service.create_plan(configured, **args)
        assert configured_plan["executable"], configured_plan
        configured_receipt = service.execute_plan(configured_plan)
        assert configured_receipt["status"] == "published", configured_receipt
        assert (prefix / "bin/geant4-data.txt").read_text(encoding="utf-8").strip() == str(prefix / "data")
        assert configured_receipt["generated_files"][0]["source_sha256"] != configured_receipt["generated_files"][0]["sha256"]
        assert service.verify_installation(prefix)["file_count"] == 3
        service.uninstall_installation(prefix)
        cancelled = service.execute_plan(plan, cancel=lambda: True)
        journal_path = Path(cancelled["transaction_path"]) / service.JOURNAL
        legacy = service.load_catalog(journal_path)
        legacy.pop("plan")
        service._write_json(journal_path, legacy)
        inspected = service.inspect_transaction(prefix, allowed_root=root)
        assert not inspected["resumable"] and inspected["recovery_actions"] == [] and inspected["plan"] is None
        # D2: loss of the original plan means no bounded deletion authority.
        expect_error(lambda: service.recover_installation(prefix, allowed_root=root), "recovery_plan_missing")
        assert journal_path.exists()
        # Restore this test's retained original plan (not a production recovery).
        legacy["plan"] = plan
        service._write_json(journal_path, legacy)
        assert service.recover_installation(prefix, allowed_root=root)["status"] == "recovered"
        assert not Path(cancelled["transaction_path"]).exists()
        # Source mutation after planning: no prefix publication, recoverable owned staging.
        archive = Path(catalog["releases"][0]["artifacts"][0]["source"]["path"])
        original_archive = archive.read_bytes()
        archive.write_bytes(original_archive[:-1] + bytes([original_archive[-1] ^ 1]))
        failed = service.execute_plan(plan)
        assert failed["status"] == "failed" and failed["diagnostics"][0]["code"] == "archive_hash", failed
        assert not prefix.exists()
        service.recover_installation(prefix, allowed_root=root)
        archive.write_bytes(original_archive)
        # Publication conflict introduced after verification cannot replace an empty directory.
        publish = service._exclusive_publish
        def conflict(source, target):
            if Path(target) == prefix:
                prefix.mkdir()
            return publish(source, target)
        with patch.object(service, "_exclusive_publish", side_effect=conflict):
            failed = service.execute_plan(plan)
        assert failed["status"] == "failed" and prefix.is_dir(), failed
        assert list(prefix.iterdir()) == []
        prefix.rmdir()
        service.recover_installation(prefix, allowed_root=root)
        # Cleanup failure keeps a real published success; explicit recovery preserves it.
        remove = service._safe_remove_tree
        with patch.object(service, "_remove_owned_transaction", side_effect=OSError("injected cleanup failure")):
            committed = service.execute_plan(plan)
        assert committed["status"] == "published_with_warning", committed
        assert service.verify_installation(prefix)["status"] == "verified"
        recovered = service.recover_installation(prefix, allowed_root=root)
        assert recovered["published_prefix_preserved"] and prefix.is_dir()
        # Uninstall cleanup failure has an independent recoverable owned tomb.
        with patch.object(service, "_safe_remove_tree", side_effect=OSError("injected uninstall failure")):
            uninstall = service.uninstall_installation(prefix)
        assert uninstall["status"] == "cleanup_required" and not prefix.exists()
        receipt = service.load_catalog(Path(uninstall["recovery_path"]) / service.MARKER)
        recovered = service.recover_installation(prefix, allowed_root=root, action="uninstall",
                                                  transaction_id=receipt["transaction_id"])
        assert recovered["uninstalled"] and not Path(uninstall["recovery_path"]).exists()
        # Concurrent invocations cannot share staging or replace another winner.
        with ThreadPoolExecutor(max_workers=2) as pool:
            runs = list(pool.map(lambda _: service.execute_plan(plan), range(2)))
        assert sum(value["status"] == "published" for value in runs) == 1, runs
        assert sum(value["status"] == "failed" for value in runs) == 1, runs
        service.uninstall_installation(prefix)
        # A crash between atomic publication and final receipt update is recoverable.
        writer = service._write_json
        def marker_failure(path, value, **kwargs):
            if Path(path) == prefix / service.MARKER:
                raise OSError("injected final marker failure")
            return writer(path, value, **kwargs)
        with patch.object(service, "_write_json", side_effect=marker_failure):
            prepared = service.execute_plan(plan)
        assert prepared["status"] == "published_with_warning" and prefix.is_dir(), prepared
        assert service.load_catalog(prefix / service.MARKER)["status"] == "prepared"
        service.recover_installation(prefix, allowed_root=root)
        assert service.verify_installation(prefix)["status"] == "verified"
        service.uninstall_installation(prefix)
        # Archives never get an extractall traversal/link escape.
        for name in ("../escape", "/absolute", "NUL", "a\\b", "a/./b", "a/../b"):
            expect_error(lambda: service._relative(name), "archive_path")
            if os.name == "nt" and "\\" in name:
                continue  # Python's Windows ZIP reader canonicalizes separators.
            malformed = root / "unsafe.zip"
            with zipfile.ZipFile(malformed, "w") as output:
                entry = zipfile.ZipInfo("placeholder")
                entry.filename = name  # Do not let Windows ZipInfo normalize backslashes.
                output.writestr(entry, b"x")
            expect_error(lambda: service.inspect_archive(malformed, "zip"), "archive_path")
        linked = root / "linked.zip"
        with zipfile.ZipFile(linked, "w") as output:
            entry = zipfile.ZipInfo("link")
            entry.create_system = 3
            entry.external_attr = 0o120777 << 16
            output.writestr(entry, "../../outside")
        expect_error(lambda: service.inspect_archive(linked, "zip"), "archive_link")
        assert not (root.parent / "escape").exists()
    with tempfile.TemporaryDirectory(prefix="g4usim-c4-plan-") as temp:
        ar5_strict_plan_executable(Path(temp) / "strict-plan")
    print("I2 installation transactions passed")


if __name__ == "__main__":
    main()
