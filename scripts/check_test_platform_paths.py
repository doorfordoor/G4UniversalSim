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
import ast
import io
import json
import subprocess
import tokenize
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DIRECTORIES = ("scripts", "gui/smoke_tests")
# These files deliberately contain path literals as data for their own checks.
ALLOWED_DRIVE_LETTER = {"scripts/check_doc_links.py"}
DRIVE_LETTER = re.compile(r'"([A-Za-z]:[\/][^"\n]{2,})"')
FIXTURE_POLICY = ROOT / "tools" / "platform_path_fixtures.json"


def fixture_policy(path: Path = FIXTURE_POLICY) -> list[dict[str, str]]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if set(value) != {"schema", "fixtures"} or value["schema"] != "g4usim_platform_path_fixtures_v1":
        raise ValueError("Unknown platform-path fixture policy")
    rows, seen = value["fixtures"], set()
    if not isinstance(rows, list):
        raise ValueError("Fixture policy must contain a list")
    for row in rows:
        if not isinstance(row, dict) or set(row) != {"file", "constant", "value", "reason"}:
            raise ValueError("Invalid fixture policy entry")
        if any(not isinstance(field, str) or not field or "\n" in field or "\r" in field for field in row.values()):
            raise ValueError("Fixture policy fields must be nonempty single-line strings")
        if (not row["file"].startswith(("scripts/", "gui/smoke_tests/")) or "\\" in row["file"]
                or any(part in ("", ".", "..") for part in row["file"].split("/"))
                or not row["file"].endswith(".py")
                or not re.fullmatch(r"[A-Z][A-Z0-9_]*_FIXTURE", row["constant"])):
            raise ValueError("Fixture policy must name an exact test file and fixture constant")
        key = row["file"], row["constant"]
        if key in seen:
            raise ValueError("Duplicate fixture declaration in policy")
        seen.add(key)
    return rows


def _mask_fixture_declarations(relative: str, text: str, policy: list[dict[str, str]]) -> str:
    approved = [row for row in policy if row["file"] == relative]
    if not approved:
        return text
    tree = ast.parse(text)
    lines = text.splitlines(keepends=True)
    for row in approved:
        declarations = [node for node in tree.body if isinstance(node, ast.Assign)
                        and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name)
                        and node.targets[0].id == row["constant"]]
        if len(declarations) != 1:
            continue
        value = declarations[0].value
        if (not isinstance(value, ast.Constant) or not isinstance(value.value, str)
                or value.value != row["value"] or value.lineno != value.end_lineno):
            continue
        # Only the one complete literal token is exempt. Adjacent strings,
        # expressions, assignments on other lines and all comments remain checked.
        segment = ast.get_source_segment(text, value)
        tokens = [token for token in tokenize.generate_tokens(io.StringIO(segment).readline)
                  if token.type not in (tokenize.NEWLINE, tokenize.NL, tokenize.ENDMARKER)]
        if len(tokens) != 1 or tokens[0].type != tokenize.STRING:
            continue
        index = value.lineno - 1
        line = lines[index]
        marker = "# platform-path-fixture: " + row["reason"]
        if line[value.end_col_offset:].strip() != marker:
            continue
        lines[index] = line[:value.col_offset] + " " * (value.end_col_offset - value.col_offset) + line[value.end_col_offset:]
    return "".join(lines)


def source_problems(relative: str, text: str, policy: list[dict[str, str]]) -> list[str]:
    checked = _mask_fixture_declarations(relative, text, policy)
    problems = []
    if "build_vs2026" in checked and "G4USIM_EXE" not in text:
        problems.append(f"{relative}: mentions build_vs2026 but never reads G4USIM_EXE")
    if relative not in ALLOWED_DRIVE_LETTER:
        for literal in DRIVE_LETTER.findall(checked):
            problems.append(f"{relative}: hard-coded drive-letter path {literal!r}")
    return problems


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
    policy = fixture_policy()
    for path in files:
        rel = path.relative_to(ROOT).as_posix()
        text = path.read_text(encoding="utf-8", errors="replace")
        checked += 1
        problems.extend(source_problems(rel, text, policy))
    assert checked > 0, "no files were checked"
    assert not problems, "platform assumptions found:\n" + "\n".join(problems)
    print(f"test platform paths: OK ({checked} scripts, no platform assumptions)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
