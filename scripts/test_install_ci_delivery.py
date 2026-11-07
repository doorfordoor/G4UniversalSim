"""CI source closure and preservation of this flow's exact freeze/SDK evidence."""
from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packaging"))
import ci_delivery


def main():
    with tempfile.TemporaryDirectory(prefix="g4usim-ci-delivery-") as temp:
        root = Path(temp)
        origin = root / "origin"
        for relative in ci_delivery.REQUIRED_PRODUCT_PATHS:
            file = origin / relative
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_text("# actual fixture module " + relative + "\n", encoding="utf-8")
        # The export-template identity declares CMakePresets.json as a root
        # member, so the native snapshot must copy it byte for byte and list it.
        presets_fixture = origin / "CMakePresets.json"
        presets_fixture.write_text(
            '{"version": 3, "configurePresets": [{"name": "fixture"}]}\n',
            encoding="utf-8")
        other = origin / "packaging/freeze_identity.py"
        other.parent.mkdir(parents=True)
        other.write_text("# fixture packaging source\n", encoding="utf-8")
        for relative in ("docs/verification/receipt.json", "test/output/generated.root", "gui/.venv/ignored.py"):
            file = origin / relative
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_text("generated fixture\n", encoding="utf-8")
        destination = root / "native-snapshot"
        with patch.object(ci_delivery, "ROOT", origin):
            snapshot = ci_delivery.snapshot_sources(destination)
        for relative in ci_delivery.REQUIRED_PRODUCT_PATHS:
            assert (destination / relative).read_bytes() == (origin / relative).read_bytes()
            assert relative in snapshot["files"]
        assert (destination / "packaging/freeze_identity.py").is_file()
        assert (destination / "CMakePresets.json").read_bytes() == presets_fixture.read_bytes()
        assert "CMakePresets.json" in snapshot["files"]
        assert snapshot["files"]["CMakePresets.json"] == ci_delivery._file_hash(presets_fixture)
        assert not (destination / "gui/.venv").exists()
        assert not (destination / "docs/verification").exists()
        assert not (destination / "test/output").exists()
        work = root / "work"
        source = work / "source"
        files = {
            source / "out/package-build/freeze.log": b"actual freeze log\r\n",
            source / "out/package-build/binary-sources.json": b'{"source":"observed"}\n',
            source / "out/package-build/source-identity.json": b'{"source_hashes":{}}\n',
            source / "out/package/application/gui/g4usim-freeze.json": b'{"kind":"gui","files":{}}\n',
            source / "out/package/application/python/g4usim-freeze.json": b'{"kind":"python","files":{}}\n',
        }
        for kind in ("consumer", "application"):
            for name in ("configure.log", "build.log", "run.log", "sdk-probe-receipt.json"):
                files[work / "environments" / ("sdk-" + kind + "-build") / name] = (kind + " " + name + "\n").encode()
        for file, raw in files.items():
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_bytes(raw)
        archived = ci_delivery.archive_validation_evidence(work, source)
        assert len(archived) == len(files), archived
        for record in archived:
            copied = work / record["path"]
            assert copied.read_bytes() == files[Path(record["source"])], record
            assert ci_delivery._file_hash(copied) == record["sha256"] and record["source_stable_during_copy"]
        assert len(ci_delivery.archive_validation_evidence(work, source)) == len(files)
        changed = source / "out/package-build/freeze.log"
        changed.write_bytes(b"later observed failure log\n")
        newer = ci_delivery.archive_validation_evidence(work, source)
        assert len(newer) == len(files) + 1
        old = next(record for record in archived if record["source"] == str(changed))
        assert (work / old["path"]).read_bytes() == files[changed]
        assert len(json.loads((work / "evidence/index.json").read_text())) == len(newer)
        actual_host = Path(getattr(sys, "_base_executable", sys.executable))
        tools = ci_delivery.describe_host_tools(actual_host)
        assert Path(tools["cmake"]["resolved"]) == actual_host.resolve()
        assert tools["cmake"]["sha256"] == ci_delivery._file_hash(actual_host.resolve())
        missing_tool = root / "absent-cmake"
        try:
            ci_delivery.describe_host_tools(missing_tool)
        except OSError:
            assert not missing_tool.exists()
        else:
            assert False, "Missing selected host tool passed delivery preflight"
    print("I2 CI snapshot closure and evidence archival passed")


if __name__ == "__main__":
    main()
