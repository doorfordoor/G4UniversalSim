"""Regression: repeated [section] headers and keys in the main INI must be reported.

The parser keeps its historical last-value-wins behavior, so a repeated declaration used to
drop the earlier value silently. Every repetition is now reported as
``[ConfigWarning] duplicate declaration`` and counted in ``run_summary.txt`` as
``config_duplicate_count``; a configuration without repetitions must still report 0 so the
new count cannot hide a detector failure.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EXE = ROOT / "build_vs2026" / "Release" / "G4UniversalSim.exe"


def run(executable: Path, args: list[str], cwd: Path, expected: int = 0) -> str:
    result = subprocess.run(
        [str(executable), *args],
        cwd=cwd,
        text=True,
        capture_output=True,
        timeout=180,
    )
    output = result.stdout + result.stderr
    assert result.returncode == expected, (
        f"Unexpected exit code for {' '.join(args)}: expected {expected}, "
        f"got {result.returncode}\n{output}"
    )
    return output


def read_summary(output_dir: Path) -> dict[str, str]:
    summary = output_dir / "run_summary.txt"
    assert summary.is_file(), f"run_summary.txt was not created: {summary}"
    values: dict[str, str] = {}
    in_values = False
    for line in summary.read_text(encoding="utf-8").splitlines():
        if line.strip() == "[Values]":
            in_values = True
            continue
        if in_values and " = " in line:
            key, value = line.split(" = ", 1)
            values[key] = value
    return values


# Verification helpers use assert so tools/test_assert_probe.py counts every check.
def require(text: str, expected: str) -> None:
    assert expected in text, f"Expected marker not found: {expected}\n{text}"


def require_absent(text: str, unexpected: str) -> None:
    assert unexpected not in text, f"Unexpected marker found: {unexpected}\n{text}"


def main() -> int:
    executable = Path(os.environ.get("G4USIM_EXE", str(DEFAULT_EXE)))
    if not executable.is_file():
        raise SystemExit(f"Executable not found: {executable}")

    with tempfile.TemporaryDirectory(prefix="g4usim-dup-ini-") as temporary:
        temp = Path(temporary)
        config_dir = temp / "config"
        shutil.copytree(ROOT / "config", config_dir)
        main_ini = config_dir / "main.ini"
        original = main_ini.read_text(encoding="utf-8")

        # 1) A repeated [run] header plus a repeated key inside it: the section header and the
        #    key are both declarations of the same name, so both must be reported.
        duplicated = original + "\n[run]\nname = duplicate_should_win\n"
        dup_ini = config_dir / "duplicate.ini"
        dup_ini.write_text(duplicated, encoding="utf-8")
        dup_output = temp / "out-duplicate"
        text = run(
            executable,
            ["--config", str(dup_ini), "--dry-run", "--output", str(dup_output)],
            cwd=temp,
        )
        require(text, "[ConfigWarning] duplicate declaration")
        require(text, "repeated section header")
        require(text, "[run]/name = duplicate_should_win")
        require(text, "earlier declaration at line")
        require(text, "is overridden by this one; remove one of the declarations")
        values = read_summary(dup_output)
        count = int(values.get("config_duplicate_count", "-1"))
        assert count == 2, (
            f"expected 2 duplicate declarations (repeated section + repeated key), got {count}"
        )
        # The earlier value really is dropped: the later declaration wins for consumers.
        assert values.get("run_name") == "duplicate_should_win", (
            f"later duplicate value did not win, run_name={values.get('run_name')!r}"
        )

        # 2) No repetition: the count must be 0 and no duplicate warning may be printed.
        clean_output = temp / "out-clean"
        clean_text = run(
            executable,
            ["--config", str(main_ini), "--dry-run", "--output", str(clean_output)],
            cwd=temp,
        )
        require_absent(clean_text, "duplicate declaration")
        clean_values = read_summary(clean_output)
        assert clean_values.get("config_duplicate_count") == "0", (
            f"expected config_duplicate_count=0 without repetitions, "
            f"got {clean_values.get('config_duplicate_count')!r}"
        )

        # 3) A duplicate inside a section only (no repeated header) is still reported once.
        key_only = original.replace("[output]", "[output]", 1)  # keep file untouched
        key_only = original + "\n"
        assert "[output]" in key_only, "fixture main.ini has no [output] section"
        key_only = key_only.replace(
            "[output]\ndir = output/simple_test",
            "[output]\ndir = output/simple_test\ndir = output/duplicate_key_should_win",
            1,
        )
        assert key_only != original + "\n", "could not build the duplicate-key fixture"
        key_ini = config_dir / "duplicate_key.ini"
        key_ini.write_text(key_only, encoding="utf-8")
        key_output = temp / "out-duplicate-key"
        key_text = run(
            executable,
            ["--config", str(key_ini), "--dry-run", "--output", str(key_output)],
            cwd=temp,
        )
        require(key_text, "[ConfigWarning] duplicate declaration")
        require(key_text, "[output]/dir = output/duplicate_key_should_win")
        require_absent(key_text, "repeated section header")
        key_values = read_summary(key_output)
        assert key_values.get("config_duplicate_count") == "1", (
            f"expected 1 duplicate declaration, got {key_values.get('config_duplicate_count')!r}"
        )
        assert key_values.get("actual_output_dir") != "", "summary does not report actual_output_dir"

    print("test_config_duplicate_declarations: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
