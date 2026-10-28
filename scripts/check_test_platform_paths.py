"""Fail when a test script assumes one platform's build or install paths.

Discovered on 2026-10-28: ``scripts/test_scenario_shielding_core.py`` looked for
``build_vs2026/Release/G4UniversalSim.exe`` directly, so the Linux CI backend
profile failed with ``backend executable not found`` even though the runner
exports ``G4USIM_EXE`` and passes ``--executable``.  The rule is simple: a test
may mention the Windows default build directory only as a fallback after
``G4USIM_EXE`` (the runner-provided executable), and it must not hard-code a
drive-letter path.

This is a static check: it inspects the tracked test entry points only.  It does
not prove that a test behaves correctly on either platform; it only removes one
known class of platform assumption.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DIRECTORIES = ("scripts", "gui/smoke_tests")
# These files deliberately contain path literals as data for their own checks.
ALLOWED_DRIVE_LETTER = {"scripts/check_doc_links.py"}
DRIVE_LETTER = re.compile(r'"([A-Za-z]:[\/][^"\n]{2,})"')


def tracked_files() -> list[Path]:
    listing = subprocess.run(
        ["git", "ls-files", "-z", "--", *DIRECTORIES],
        cwd=ROOT,
        check=True,
        capture_output=True,
    ).stdout
    return [ROOT / name.decode("utf-8") for name in listing.split(b"\0") if name]


def main() -> int:
    files = [path for path in tracked_files() if path.suffix == ".py"]
    assert files, "no tracked python test entry points were found"
    checked = 0
    problems: list[str] = []
    for path in files:
        rel = path.relative_to(ROOT).as_posix()
        text = path.read_text(encoding="utf-8", errors="replace")
        checked += 1
        if "build_vs2026" in text and "G4USIM_EXE" not in text:
            problems.append(f"{rel}: mentions build_vs2026 but never reads G4USIM_EXE")
        if rel not in ALLOWED_DRIVE_LETTER:
            for literal in DRIVE_LETTER.findall(text):
                problems.append(f"{rel}: hard-coded drive-letter path {literal!r}")
    assert checked > 0, "no files were checked"
    assert not problems, "platform assumptions found:\n" + "\n".join(problems)
    print(f"test platform paths: OK ({checked} scripts, no platform assumptions)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
