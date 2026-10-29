#!/usr/bin/env python3
"""E6 main INI copy migration preserves bytes/settings and rejects unsafe publication."""
from __future__ import annotations

import os
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "gui"))

from g4usim_gui.core.config_migration import publish_migration
from g4usim_gui.core.main_ini_migration import plan_main_ini_migration
from g4usim_gui.core.config_schema import check_value


def rejected(action, exception=ValueError):
    try:
        action()
    except exception as error:
        assert str(error)
    else:
        assert False, "Expected migration refusal"


def main():
    with tempfile.TemporaryDirectory(prefix="g4usim-e6-main-migration-") as temp:
        folder = Path(temp)
        source = folder / "主配置.ini"
        original = b"; keep comment\r\n[run]\r\nthreads=1\r\nthreads = 2 # last wins\r\n[source]\r\nspectrum_file=relative.csv\r\n[unknown]\r\ncustom = preserved\r\n"
        source.write_bytes(original)
        plan = plan_main_ini_migration(source)
        assert plan.input_version is None and plan.output_version == 1
        assert plan.payload == original + b"[general]\r\nschema_version = 1\r\n"
        assert len(plan.changes) == 1
        target = folder / "explicit.ini"
        published = publish_migration(plan, target)
        assert target.read_bytes() == plan.payload and source.read_bytes() == original
        assert published.destination == str(target)
        again = plan_main_ini_migration(target)
        assert again.payload == plan.payload and not again.changes
        rejected(lambda: publish_migration(plan, source), FileExistsError)
        rejected(lambda: publish_migration(plan, target), FileExistsError)
        alias = folder / "source-hardlink.ini"
        os.link(source, alias)
        rejected(lambda: publish_migration(plan, alias), FileExistsError)
        assert alias.read_bytes() == original
        other = folder / "elsewhere"
        other.mkdir()
        rejected(lambda: publish_migration(plan, other / "copy.ini"))
        assert not (other / "copy.ini").exists()
        source.write_bytes(original + b"; changed\n")
        rejected(lambda: publish_migration(plan, folder / "changed.ini"))
        assert not (folder / "changed.ini").exists()
        source.write_bytes(original)
        with patch("g4usim_gui.core.config_migration.os.link", side_effect=OSError("injected publish failure")):
            rejected(lambda: publish_migration(plan, folder / "failure.ini"), OSError)
        assert not (folder / "failure.ini").exists()
        assert not list(folder.glob(".failure.ini.*.tmp"))
        assert source.read_bytes() == original
        for text in ("[general]", "[general]\r\n; keep\r\nverbose=1", "[run]\nthreads=1\n[General]\nverbose=1\n"):
            source.write_text(text, encoding="utf-8", newline="")
            migrated = plan_main_ini_migration(source)
            assert b"schema_version = 1" in migrated.payload
            assert source.read_text(encoding="utf-8") == text.replace("\r\n", "\n")
        for text in ("[general]\nschema_version=1;inline", "[general]\nschema_version=2\nschema_version=1\n"):
            source.write_text(text, encoding="utf-8")
            migrated = plan_main_ini_migration(source)
            assert migrated.payload == source.read_bytes() and not migrated.changes
        for bad in ("", "0", "2", "01", "+1", "1.0", "nan", "1\u00a0", "\u00a01", "1\u2028"):
            assert check_value("general", "schema_version", bad) is not None
            source.write_text(f"[general]\nschema_version={bad}\n", encoding="utf-8")
            rejected(lambda: plan_main_ini_migration(source))
        for section, key, bad in (("field", "min_step", "1 mm\u00a0"),
                                  ("biasing.xs", "factor", "\u00a02"),
                                  ("biasing", "enabled", "true\u00a0")):
            assert check_value(section, key, bad) is not None
        for text in ("[general\u00a0]\nverbose=1\n", "[general]\nschema_version\u00a0=2\n"):
            source.write_text(text, encoding="utf-8")
            migrated = plan_main_ini_migration(source)
            assert migrated.input_version is None
            assert b"schema_version = 1" in migrated.payload
            assert text.encode("utf-8").replace(b"[general]\n", b"") in migrated.payload.replace(b"\r\n", b"\n")
        for invalid in ("[general\nschema_version=1", "[]=x", "[general]\n=1", "[general]\nnot-an-assignment",
                        "[general]\nschema_version=1\r[run]\nthreads=2"):
            source.write_text(invalid, encoding="utf-8")
            rejected(lambda: plan_main_ini_migration(source))
    print("E6 main INI migration checks passed")


if __name__ == "__main__":
    main()
