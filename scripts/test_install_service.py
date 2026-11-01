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


def main():
    with tempfile.TemporaryDirectory(prefix="g4usim-install-service-") as temp:
        root = Path(temp)
        catalog = fixture(root)
        args = arguments(catalog, root)
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
        assert not inspected["resumable"] and inspected["recovery_actions"] == ["discard"] and inspected["plan"] is None
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
        with patch.object(service, "_safe_remove_tree", side_effect=OSError("injected cleanup failure")):
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
    print("I2 installation transactions passed")


if __name__ == "__main__":
    main()
