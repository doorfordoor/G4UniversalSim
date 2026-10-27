"""Run a test script as ``__main__`` while counting executed ``assert`` statements.

Usage::

    python -B tools/test_assert_probe.py <test script> [args...]

The probe executes the target script with :func:`runpy.run_path`, installs a line
tracer restricted to the target file, and counts how many lines that hold an
``assert`` statement are actually executed. After the script returns (or raises
``SystemExit``) it prints exactly one marker line::

    G4USIM_ASSERTS=<n>

The probe never changes the observable behaviour of the script: arguments, exit
status, ``SystemExit`` strings and uncaught exceptions are forwarded unchanged.
Only the standard library is used, so the probe needs no extra dependency.

The counter is a *lower bound* of checked facts, not a count of independent
claims: an ``assert`` inside a loop counts once per iteration. Scripts that
verify through ``if ...: raise SystemExit(...)`` instead of ``assert`` report 0
here; the runner surfaces that as ``cases_with_zero_assertions`` instead of
pretending the case verified nothing.
"""

from __future__ import annotations

import ast
import os
import runpy
import sys
from pathlib import Path

MARKER = "G4USIM_ASSERTS="


def collect_assert_lines(path: Path) -> set[int]:
    """Return the 1-based line numbers that start an ``assert`` statement."""
    tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"), filename=str(path))
    return {node.lineno for node in ast.walk(tree) if isinstance(node, ast.Assert)}


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("usage: test_assert_probe.py <test script> [args...]", file=sys.stderr)
        return 2
    target = Path(argv[1]).resolve()
    if not target.is_file():
        print(f"test assert probe: target script not found: {target}", file=sys.stderr)
        return 2
    assert_lines = collect_assert_lines(target)
    target_name = os.path.normcase(str(target))
    executed = [0]

    def local_tracer(frame, event, arg):
        if event == "line" and frame.f_lineno in assert_lines:
            executed[0] += 1
        return local_tracer

    def tracer(frame, event, arg):
        if event == "call" and os.path.normcase(frame.f_code.co_filename) == target_name:
            return local_tracer
        return None

    sys.argv = [str(target), *argv[2:]]
    # Mirror ``python <script>``: the script's own directory owns sys.path[0] so
    # sibling-module imports (for example ``from run_m0_tests import ROOT``) work.
    if sys.path:
        sys.path[0] = str(target.parent)
    else:
        sys.path.insert(0, str(target.parent))
    status = 0
    message: str | None = None
    sys.settrace(tracer)
    try:
        runpy.run_path(str(target), run_name="__main__")
    except SystemExit as error:
        if isinstance(error.code, int):
            status = error.code
        elif error.code is None:
            status = 0
        else:
            message = str(error.code)
            status = 1
    except BaseException:
        sys.settrace(None)
        print(f"{MARKER}{executed[0]}", flush=True)
        raise
    finally:
        sys.settrace(None)
    print(f"{MARKER}{executed[0]}", flush=True)
    if message is not None:
        print(message, file=sys.stderr, flush=True)
    return status


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
