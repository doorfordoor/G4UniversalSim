#!/usr/bin/env python3
"""E6 main INI format: transactional component and real backend boundaries."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def component() -> None:
    configured = os.environ.get("CXX")
    compiler = shlex.split(configured, posix=os.name != "nt") if configured else []
    if not compiler:
        found = next((shutil.which(name) for name in ("g++", "clang++", "cl") if shutil.which(name)), None)
        assert found, "C++17 compiler required"
        compiler = [found]
    source = r'''
#include "Config/ConfigManager.hh"
#include <iostream>
#include <stdexcept>
int main() {
    auto check=[](bool ok) { if (!ok) throw std::runtime_error("version invariant failed"); };
    ConfigManager manager;
    manager.LoadMainConfigBytes("legacy.ini", "[run]\nname=old\n");
    check(manager.GetString("run","name")=="old");
    manager.LoadMainConfigBytes("accepted.ini", "[general]\nschema_version=1\n[run]\nname=accepted\n");
    const auto hash=manager.GetMainReader().GetInputSha256();
    check(manager.GetUnconsumedWarnings().size()==1); // run/name deliberately unread
    for (const std::string bad : {"", "0", "2", "999999999999999999", "01", "+1", "1.0", "nan", "future"}) {
        bool rejected=false;
        try { manager.LoadMainConfigBytes("rejected.ini", "[general]\nschema_version="+bad+"\n"); }
        catch (const std::runtime_error& error) {
            rejected=true;
            check(std::string(error.what()).find("rejected.ini:2")!=std::string::npos);
        }
        check(rejected && manager.GetMainConfigPath()=="accepted.ini");
        check(manager.GetMainReader().GetInputSha256()==hash);
        check(manager.GetString("run","name")=="accepted");
    }
    manager.LoadMainConfigBytes("duplicate.ini", "[general]\nschema_version=2\nschema_version=1\n");
    check(manager.GetDuplicateWarnings().size()==1);
    check(manager.GetUnconsumedWarnings().empty());
    check(manager.GetMainReader().GetDeclarations().size()==2);
    check(manager.GetMainReader().GetDeclarations().back().consumed);
    manager.LoadGeometryConfigBytes("geometry.ini", "[general]\nschema_version=2\n[global]\nversion=1\n");
    check(manager.GetString("general","schema_version")=="2");
    std::cout << "transactional version checks passed\n";
}
'''
    with tempfile.TemporaryDirectory(prefix="g4usim-e6-version-component-") as temp:
        folder = Path(temp)
        test = folder / "check.cc"
        test.write_text(source, encoding="utf-8")
        executable = folder / ("check.exe" if os.name == "nt" else "check")
        inputs = [str(test)] + [str(ROOT / f"src/{name}.cc") for name in (
            "Config/ConfigManager", "Config/ConfigValue", "Config/IniReader",
            "Config/InputProvenance", "Utils/StringUtils")]
        if Path(compiler[0]).stem.lower() in ("cl", "clang-cl"):
            cmd = compiler + ["/nologo", "/std:c++17", "/utf-8", "/EHsc", "/I" + str(ROOT / "include")]
            cmd += inputs + ["/Fe:" + str(executable)]
        else:
            cmd = compiler + ["-std=c++17", "-I", str(ROOT / "include")] + inputs + ["-o", str(executable)]
        built = subprocess.run(cmd, cwd=folder, capture_output=True, text=True, timeout=120)
        assert built.returncode == 0, built.stdout + built.stderr
        result = subprocess.run([str(executable)], cwd=folder, capture_output=True, text=True, timeout=30)
        assert result.returncode == 0, result.stdout + result.stderr
        assert "transactional version checks passed" in result.stdout


def backend() -> None:
    selected = os.environ.get("G4USIM_EXE")
    assert selected, "G4USIM_EXE must identify the candidate backend"
    executable = Path(selected).resolve()
    assert executable.is_file(), executable
    with tempfile.TemporaryDirectory(prefix="g4usim-e6-version-") as temp:
        folder = Path(temp)
        config = folder / "版本.ini"
        output = folder / "never-created"
        base = f"[run]\nthreads=1\n[output]\ndir={output.as_posix()}\n[source]\nparticle=proton\nenergy=2 MeV\n"

        def run(version: str, mode: str = "--dump-effective-config"):
            config.write_text(base + version, encoding="utf-8")
            args = [str(executable), "--config", str(config), mode]
            if mode == "--dump-effective-config":
                args.append("-")
            return subprocess.run(args, cwd=folder, capture_output=True, text=True,
                                  encoding="utf-8", errors="replace", timeout=90)

        def accepted(raw: str):
            result = run(raw)
            assert result.returncode == 0, result.stdout + result.stderr
            snapshot = json.loads(result.stdout)
            assert snapshot["stage"] == "configure" and not snapshot["execution_performed"]
            assert not output.exists(), "Read-only version check created run output"
            fields = {item["path"]: item for item in snapshot["fields"]}
            fmt = fields["/configuration/main_ini_schema_version"]
            assert fmt["resolved"] == 1 and fmt["application_status"] == "not_applied"
            return fields, fmt

        legacy, absent = accepted("")
        assert "requested" not in absent
        current, explicit = accepted("[general]\nschema_version=1\n")
        assert explicit["requested"] == "1"
        origin = explicit["origins"][-1]
        assert origin["kind"] == "main_ini" and origin["line"] == 9
        assert origin["key"] == "schema_version" and len(origin["input_sha256"]) == 64
        # Version tagging cannot change physical/configuration values.
        assert {p: f["resolved"] for p, f in legacy.items()} == {p: f["resolved"] for p, f in current.items()}
        accepted("[General]\nSchema_Version = 1 ; current format\n")
        _, duplicate = accepted("[general]\nschema_version=2\nschema_version=1\n")
        declarations = [o for o in duplicate["origins"] if o["kind"] == "main_ini"]
        assert [o["disposition"] for o in declarations] == ["shadowed", "accepted"]
        duplicate_inspect = run("[general]\nschema_version=2\nschema_version=1\n", "--inspect-run")
        assert duplicate_inspect.returncode == 0
        assert "duplicate declaration" in duplicate_inspect.stderr

        for bad in ("", "0", "2", "999999999999999999", "01", "+1", "1.0", "nan", "future", "1\u00a0"):
            result = run(f"[general]\nschema_version={bad}\n")
            assert result.returncode != 0, bad
            assert "Main INI schema version rejected" in result.stderr, result.stderr
            assert f"{config}:9" in result.stderr, result.stderr
            assert "[general]/schema_version" in result.stderr
            assert not output.exists()
        future_last = run("[general]\nschema_version=1\nschema_version=2\n", "--inspect-run")
        assert future_last.returncode != 0 and f"{config}:10" in future_last.stderr
        # An unrelated independent geometry version must not opt into main INI format rules.
        accepted("[general]\nversion=2\n")
        from test_geometry_config_diagnostics import SIMPLE
        geometry = folder / "independent-geometry.ini"
        geometry.write_text(SIMPLE + "\n[general]\nschema_version=2\n", encoding="utf-8")
        config.write_text(base + "[geometry]\ntemplate=simple_box\nconfig=" + geometry.as_posix() + "\n", encoding="utf-8")
        independent = subprocess.run([str(executable), "--config", str(config), "--inspect-run"],
                                     cwd=folder, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=90)
        assert independent.returncode == 0, independent.stdout + independent.stderr
        assert "[GeometryConfigWarning]" in independent.stderr
        assert "Main INI schema version rejected" not in independent.stderr
    print("E6 main INI backend version checks passed")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--component", action="store_true")
    options = parser.parse_args()
    component() if options.component else backend()
