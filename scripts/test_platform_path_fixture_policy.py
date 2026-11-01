"""Exact fixture declarations never exempt another runtime path or comment."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import tempfile

import check_test_platform_paths as checker


def declaration(row):
    return (row["constant"] + " = " + json.dumps(row["value"]) +
            "  # platform-path-fixture: " + row["reason"] + "\n")


def main():
    rows = checker.fixture_policy()
    assert len(rows) == 4 and len({row["file"] for row in rows}) == 3
    for row in rows:
        source = declaration(row)
        assert checker.source_problems(row["file"], source, rows) == []
        literal = json.dumps(row["value"])
        bad_sources = [
            source.split("  #", 1)[0] + "\n",
            source.replace(row["reason"], "unapproved reason"),
            source.replace(row["constant"], "ACTUAL_RUNTIME_PATH", 1),
            source.replace(literal, json.dumps(row["value"] + "/runtime"), 1),
            source + source,
            source + "RUNTIME_PATH = " + literal + "\n",
            "def local_fixture():\n    " + source,
            # A complete literal is mandatory, even when adjacent string
            # tokens would evaluate to the same approved value.
            source.replace(literal, json.dumps(row["value"][:-1]) + " " + json.dumps(row["value"][-1:]), 1),
        ]
        for bad in bad_sources:
            assert checker.source_problems(row["file"], bad, rows), (row["constant"], bad)
        assert checker.source_problems("scripts/test_unlisted_runtime.py", source, rows)

    layout = next(row for row in rows if "LAYOUT" in row["constant"])
    fallback = 'EXE = Path(os.environ.get("G4USIM_EXE", ' + json.dumps(layout["value"]) + '))\n'
    assert checker.source_problems("scripts/test_real_backend.py", fallback, rows) == []
    assert checker.source_problems(layout["file"], declaration(layout) + fallback, rows) == []
    without_environment = 'EXE = Path(' + json.dumps(layout["value"]) + ')\n'
    assert checker.source_problems("scripts/test_real_backend.py", without_environment, rows)
    # Comments are never masked, including a comment in the approved file.
    comment = "# " + layout["value"] + "\n"
    assert checker.source_problems(layout["file"], declaration(layout) + comment, rows)
    drive = next(row for row in rows if ":" in row["value"])
    actual_drive = drive["value"] + "/real_backend.exe"
    drive_fallback = 'EXE = Path(os.environ.get("G4USIM_EXE", ' + json.dumps(actual_drive) + '))\n'
    assert checker.source_problems(drive["file"], declaration(drive) + drive_fallback, rows)
    assert checker.source_problems(drive["file"], declaration(drive) + "# " + json.dumps(actual_drive), rows)
    assert checker.ALLOWED_DRIVE_LETTER == {"scripts/check_doc_links.py"}

    with tempfile.TemporaryDirectory(prefix="g4usim-path-policy-") as directory:
        path = Path(directory) / "policy.json"
        normal = {"schema": "g4usim_platform_path_fixtures_v1", "fixtures": rows}
        invalid = [dict(normal, schema="unknown"), dict(normal, fixtures={}),
                   dict(normal, fixtures=rows + [rows[0]])]
        for field, value in (("file", "../outside.py"), ("constant", "RUNTIME_PATH"),
                             ("reason", "multiline\nreason")):
            changed = copy.deepcopy(normal)
            changed["fixtures"][0][field] = value
            invalid.append(changed)
        for item in invalid:
            path.write_text(json.dumps(item), encoding="utf-8")
            try:
                checker.fixture_policy(path)
            except ValueError:
                pass
            else:
                assert False, "invalid or ambiguous fixture policy must reject"

    for relative in {row["file"] for row in rows}:
        source = (checker.ROOT / relative).read_text(encoding="utf-8")
        assert checker.source_problems(relative, source, rows) == []
    print("platform-path fixture policy: exact declarations, runtime negatives, comments and fallback guard passed")


if __name__ == "__main__":
    main()
