"""I1 contract/negative tests; optional real executable via G4USIM_EXE/--executable."""
from __future__ import annotations

import argparse
import copy
import json
import os
import struct
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "gui"))
from g4usim_gui.core import environment_discovery as discovery
from g4usim_gui.core.backend_capabilities import CAPABILITY_GROUPS


def capability_fixture():
    data = {"schema": "G4UniversalSimCapabilities", "version": 1,
            "compiler_id": "FixtureCompiler", "compiler_version": "1.0", "geant4_version_number": 1132}
    for group in CAPABILITY_GROUPS:
        data[group] = [{"id": "fixture", "runtime": True}]
    data["templates"] = [{"id": "gdml", "runtime": False}]
    return data


def data_fixture(complete=True):
    return {"schema": "g4usim_geant4_data_v1", "geant4_version": "fixture",
            "required_complete": complete, "datasets": [
                {"env": "G4FIXTUREDATA", "folder": "Fixture1", "required": True,
                 "found": complete, "path": "/fixture/data" if complete else None},
                {"env": "G4OPTIONALDATA", "folder": "Optional1", "required": False,
                 "found": False, "path": None}]}


def exponent_regression():
    """Every JSON nesting level rejects numeric syntax that overflows float."""
    for location in ("top", "dataset", "nested"):
        for number in ("1e999", "-1e999"):
            data = data_fixture()
            if location == "top":
                data["extra"] = "OVERFLOW"
            elif location == "dataset":
                data["datasets"][0]["extra"] = "OVERFLOW"
            else:
                data["extra"] = {"items": [{"number": "OVERFLOW"}]}
            text = json.dumps(data).replace('"OVERFLOW"', number)
            rejected = False
            try:
                discovery._data_report(text)
            except ValueError:
                rejected = True
            assert rejected, (location, number, "non-finite JSON accepted")

            def response(argv, **kwargs):
                return {"status": "completed", "exit_code": 0}, (
                    json.dumps(capability_fixture()) if argv[-1] == "--capabilities" else text)
            with patch.object(discovery, "_command", side_effect=response):
                facts = discovery.probe_environment(sys.executable)
            assert facts["status"] == "partial"
            assert facts["data"]["status"] == "protocol_error"
            assert facts["data"]["required_complete"] is None
            assert facts["data"]["report"] is None
            assert json.loads(json.dumps(facts, allow_nan=False)) == facts
    finite = discovery._json('{"nested":[1e308,-1e308,1e-999],"text":"1e999"}')
    assert finite["nested"] == [1e308, -1e308, 0.0]
    assert finite["text"] == "1e999"


def candidate_resolution_regression():
    """Exercise real collection/probe paths with deterministic PATH lookup only."""
    original_cwd, original_env = Path.cwd(), dict(os.environ)
    with tempfile.TemporaryDirectory(prefix="i1 PATH 中文 ") as tmp:
        root = Path(tmp)
        work, prefix = root / "work", root / "path"
        work.mkdir()
        prefix.mkdir()
        name = "G4UniversalSim.exe"
        path_exe, local_exe = prefix / name, work / name
        path_exe.write_bytes(b"PATH backend fixture")
        isolated = {"PATH": str(prefix), "G4USIM_EXE": None, "Geant4_DIR": None,
                    "Geant4_ROOT": None, "GEANT4_ROOT": None, "CMAKE_PREFIX_PATH": None}
        observed = []

        def lookup(raw, *, path):
            # Model platforms that search PATH rather than implicitly preferring cwd.
            return str(Path(path) / raw) if (Path(path) / raw).is_file() else None

        def response(argv, *, env, **kwargs):
            observed.append((argv[0], env.get("I1_ENV")))
            return {"status": "completed", "exit_code": 0}, json.dumps(
                capability_fixture() if argv[-1] == "--capabilities" else data_fixture())

        try:
            os.chdir(work)
            with patch.object(discovery.shutil, "which", side_effect=lookup), \
                    patch.object(discovery, "_command", side_effect=response), \
                    patch.object(discovery, "_host_facts", return_value={}):
                for local_exists in (False, True):
                    if local_exists:
                        local_exe.write_bytes(b"explicit cwd backend fixture")
                    for candidates in ([name, local_exe], [local_exe, name]):
                        rows = discovery.discover_environments(candidates, env=isolated)["environments"]
                        assert len(rows) == 2, (local_exists, candidates, rows)
                        expected = [str(path_exe if item == name else local_exe) for item in candidates]
                        assert [row["executable"] for row in rows] == expected
                        for row in rows:
                            assert row["status"] == ("not_found" if row["executable"] == str(local_exe) and not local_exists else "ready")
                aliases = discovery.discover_environments([name, prefix / "." / name], env=isolated)["environments"]
                assert len(aliases) == 1
                assert aliases[0]["executable"] == str(path_exe)
                distinct_env = discovery.discover_environments([
                    {"executable": name, "env": {"I1_ENV": "first"}},
                    {"executable": path_exe, "env": {"I1_ENV": "second"}},
                ], env=isolated)["environments"]
                assert len(distinct_env) == 2
                assert observed[-4:] == [(str(path_exe), "first")] * 2 + [(str(path_exe), "second")] * 2
                invalid = discovery.discover_environments([None, name], env=isolated)["environments"]
                assert len(invalid) == 2
                assert invalid[0]["status"] == "error" and invalid[1]["status"] == "ready"
        finally:
            os.chdir(original_cwd)
    assert dict(os.environ) == original_env


def contract_tests():
    results = []
    isolated = {"PATH": "", "G4USIM_EXE": None, "Geant4_DIR": None, "Geant4_ROOT": None,
                "GEANT4_ROOT": None, "CMAKE_PREFIX_PATH": None}
    original_env = dict(os.environ)
    with tempfile.TemporaryDirectory(prefix="i1 中文 paths ") as tmp:
        root = Path(tmp)
        exe = root / "后端 fixture.exe"
        header = bytearray(128)
        header[:2] = b"MZ"
        struct.pack_into("<I", header, 60, 80)
        header[80:86] = b"PE\0\0\x64\x86"
        exe.write_bytes(header)
        second = root / "other.exe"
        second.write_bytes(header + b"different")
        sdk = root / "sdk 空间"
        (sdk / "lib/cmake/Geant4").mkdir(parents=True)
        (sdk / "lib/cmake/Geant4/Geant4Config.cmake").write_text("# fixture; never executed", encoding="utf-8")
        calls = []

        def responder(argv, *, timeout, env):
            calls.append((argv, env.get("I1_ENV")))
            complete = env.get("I1_ENV") != "missing-data"
            code = 0 if argv[-1] == "--capabilities" or complete else 1
            return {"argv": argv, "status": "completed" if code == 0 else "nonzero_exit",
                    "exit_code": code, "stderr": "", "elapsed_seconds": 0.0}, json.dumps(
                        capability_fixture() if argv[-1] == "--capabilities" else data_fixture(complete))

        with patch.object(discovery, "_command", side_effect=responder):
            facts = discovery.probe_environment(exe, env=isolated, sdk_roots=[sdk])
            assert facts["status"] == "ready"
            assert facts["architecture"] == {"format": "PE", "machine": "x86_64", "bits": 64, "evidence": "binary_header"}
            assert facts["identity"]["stable"] is True
            assert len(facts["identity"]["sha256"]) == 64
            assert facts["build"]["compiler_id"] == "FixtureCompiler"
            assert facts["capabilities"]["data"]["templates"][0]["runtime"] is False
            assert facts["data"]["report"]["datasets"][1]["found"] is False
            assert facts["sdk"][0]["status"] == "candidate" and not facts["sdk"][0]["build_verified"]
            assert facts["sdk"][0]["config_files"]
            assert json.loads(json.dumps(facts, allow_nan=False)) == facts
            collection = discovery.discover_environments([
                exe, exe, second, {"executable": exe, "env": {"I1_ENV": "missing-data"}}], env=isolated)
            assert len(collection["environments"]) == 3
            assert collection["environments"][0]["status"] == "ready"
            assert collection["environments"][2]["status"] == "data_incomplete"
            assert collection["host"]["tools"]["cmake"]["status"] == "not_found"
            assert collection["host"]["optional_components"]["PySide6"]["import_tested"] is False
            assert all(argv[-1] in {"--capabilities", "--check-geant4-data"} for argv, _ in calls)
        results.append("unicode-space paths / multi-environment / per-child activation / SDK evidence / JSON")

        with patch.object(discovery, "_command") as command:
            missing = discovery.probe_environment(root / "absent", env=isolated)
            assert missing["status"] == "not_found"
            assert missing["data"]["required_complete"] is None
            assert not command.called
            empty = discovery.discover_environments([], env=isolated)
            assert empty["environments"] == []
            assert json.loads(json.dumps(empty))["schema"] == discovery.DISCOVERY_SCHEMA
            assert not command.called
        results.append("no backend / no Geant4 / diagnostic-only import and host facts")

        def bad_response(argv, *, timeout, env):
            if argv[-1] == "--capabilities":
                return {"status": "completed", "exit_code": 0}, '{"schema":"wrong"}'
            return {"status": "completed", "exit_code": 0}, json.dumps(data_fixture())
        with patch.object(discovery, "_command", side_effect=bad_response):
            bad = discovery.probe_environment(exe, env=isolated)
            assert bad["status"] == "unavailable"
            assert bad["capabilities"]["status"] == "protocol_error"
            assert bad["data"]["status"] == "available"

        for mutate in (lambda d: d.update(required_complete=False),
                       lambda d: d["datasets"][0].update(found=1),
                       lambda d: d["datasets"][0].update(path=None),
                       lambda d: d["datasets"].append(copy.deepcopy(d["datasets"][0])),
                       lambda d: d.update(datasets=[]),
                       lambda d: [row.update(required=False) for row in d["datasets"]]):
            data = data_fixture()
            mutate(data)
            rejected = False
            try:
                discovery._data_report(json.dumps(data))
            except ValueError:
                rejected = True
            assert rejected
        for text in ('{"a":1,"a":2}', '{"a":NaN}', '{"a":Infinity}', '[]'):
            rejected = False
            try:
                discovery._data_report(text)
            except ValueError:
                rejected = True
            assert rejected
        results.append("invalid capability/data schema / contradictions / duplicate keys / nonfinite JSON")

        for failure in ("timeout", "missing_library", "spawn_error", "invalid_encoding", "output_limit"):
            def fail_capability(argv, *, timeout, env):
                if argv[-1] == "--capabilities":
                    return {"status": failure, "exit_code": None, "stderr": "fixture"}, ""
                return responder(argv, timeout=timeout, env=env)
            with patch.object(discovery, "_command", side_effect=fail_capability):
                unavailable = discovery.probe_environment(exe, env=isolated)
                assert unavailable["status"] == "unavailable"
                assert unavailable["capabilities"]["status"] == failure
                assert unavailable["data"]["status"] == "available"
        for data_status, code, text in (("completed", 0, json.dumps(data_fixture(False))),
                                         ("nonzero_exit", 1, json.dumps(data_fixture())),
                                         ("timeout", None, "")):
            def fail_data(argv, *, timeout, env):
                if argv[-1] == "--capabilities":
                    return responder(argv, timeout=timeout, env=env)
                return {"status": data_status, "exit_code": code}, text
            with patch.object(discovery, "_command", side_effect=fail_data):
                partial = discovery.probe_environment(exe, env=isolated)
                assert partial["status"] == "partial"
                assert partial["data"]["required_complete"] is None
                assert partial["data"]["status"] == ("timeout" if data_status == "timeout" else "protocol_error")
        with patch.object(discovery, "_command", side_effect=responder):
            automatic_env = {**isolated, "G4USIM_EXE": str(exe)}
            automatic = discovery.discover_environments(env=automatic_env)
            assert len(automatic["environments"]) == 1
            assert automatic["environments"][0]["candidate"]["source"] == "G4USIM_EXE"
        assert discovery.probe_environment(None, env=isolated)["status"] == "error"
        results.append("independent failed probes / missing-library and timeout remain failures / default discovery")

        def changed(argv, *, timeout, env):
            if argv[-1] == "--check-geant4-data":
                exe.write_bytes(exe.read_bytes() + b"changed")
            return responder(argv, timeout=timeout, env=env)
        with patch.object(discovery, "_command", side_effect=changed):
            stale = discovery.probe_environment(exe, env=isolated)
            assert stale["status"] == "changed_during_probe"
            assert stale["identity"]["stable"] is False
        results.append("binary changed while probing cannot be selected")

        elf = root / "elf"
        raw = bytearray(32)
        raw[:6] = b"\x7fELF\x02\x01"
        struct.pack_into("<H", raw, 18, 183)
        elf.write_bytes(raw)
        assert discovery._architecture(elf)["machine"] == "aarch64"
        assert discovery._architecture(elf)["bits"] == 64
        for timeout in (0, -1, float("inf"), float("nan")):
            rejected = False
            try:
                discovery.probe_environment(exe, timeout=timeout)
            except ValueError:
                rejected = True
            assert rejected
        assert discovery.discover_environments([{}], env=isolated)["environments"][0]["status"] == "invalid_candidate"
        results.append("PE/ELF architecture / timeout argument rejection / invalid candidate")

    # Actual child processes exercise capture, killing/reaping, loader diagnostics and spaces.
    env = os.environ.copy()
    record, text = discovery._command([sys.executable, "-c", "print('中文 path')"], timeout=5, env=env)
    assert record["status"] == "completed" and "path" in text
    start = time.monotonic()
    record, _ = discovery._command([sys.executable, "-c", "import time; time.sleep(20)"], timeout=0.1, env=env)
    assert record["status"] == "timeout" and record["exit_code"] is None
    assert time.monotonic() - start < 5
    record, _ = discovery._command([sys.executable, "-c",
        "import sys; sys.stderr.write('error while loading shared libraries: libFixture.so'); sys.exit(127)"], timeout=5, env=env)
    assert record["status"] == "missing_library" and record["exit_code"] == 127
    assert "libFixture.so" in record["stderr"]
    record, _ = discovery._command([sys.executable, "-c", "print('x' * 4200000)"], timeout=5, env=env)
    assert record["status"] == "output_limit"
    record, _ = discovery._command([str(ROOT / "out/i1-nonexistent-executable")], timeout=1, env=env)
    assert record["status"] == "spawn_error"
    for code, expected in ((0xC0000135, "missing_library"), (0xC000007B, "loader_error")):
        with patch.object(subprocess, "run", return_value=subprocess.CompletedProcess([], code)):
            record, _ = discovery._command([sys.executable], timeout=1, env=env)
            assert record["status"] == expected
    assert dict(os.environ) == original_env
    results.append("actual child success / timeout / loader stderr / output cap / spawn error; Windows loader codes injected")
    exponent_regression()
    results.append("JSON exponent overflow at top/dataset/nested levels remains protocol_error")
    candidate_resolution_regression()
    results.append("PATH identity before dedup / both orders / missing and present cwd / aliases / isolated env")
    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--executable", default=os.environ.get("G4USIM_EXE"))
    parser.add_argument("--component", action="store_true", help="Run diagnostic contracts without a Geant4 backend")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    if args.component:
        args.executable = None
    report = {"contract_cases": contract_tests(), "real_backend": None,
              "validation_scope": "diagnostic protocols only; no initialization, events or physics"}
    if args.executable:
        facts = discovery.probe_environment(args.executable)
        assert facts["capabilities"]["status"] == "available", facts
        assert facts["identity"]["stable"] is True
        assert facts["data"]["status"] in {"available", "incomplete"}, facts
        report["real_backend"] = facts
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_bytes((json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8"))
    print("PASS I1", len(report["contract_cases"]), "contract groups; real backend:",
          report["real_backend"]["status"] if report["real_backend"] else "not requested")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
