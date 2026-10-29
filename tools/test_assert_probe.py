"""Run a test script as ``__main__`` while counting executed ``assert`` statements.

Usage::

    python -B tools/test_assert_probe.py <test script> [args...]

The probe executes the target script with :func:`runpy.run_path`, installs a line
tracer restricted to the target file, and counts how many lines that hold an
``assert`` statement are actually executed. Threads started by the script are traced
too (:func:`threading.settrace`), so assertions that run inside a
``ThreadPoolExecutor`` worker are counted; threads that existed before the probe
installed the tracer are not. After the script returns (or raises ``SystemExit``) it
prints exactly one marker line::

    G4USIM_ASSERTS=<n>

The probe never changes the observable behaviour of the script: arguments, exit
status, ``SystemExit`` strings and uncaught exceptions are forwarded unchanged.
Only the standard library is used, so the probe needs no extra dependency.

The counter is a conservative lower bound of assert-line entries, not a count
of independent facts or elements inspected inside expressions. Expression-only
frames are excluded; real assertions in named generator functions still count.
Multiple assertions sharing a line count at most once per line entry; ambiguous
inline compound statements are omitted. An assert inside a normal multiline
loop counts once per iteration. Scripts that
verify through ``if ...: raise SystemExit(...)`` instead of ``assert`` report 0
here; the runner surfaces that as ``cases_with_zero_assertions`` instead of
pretending the case verified nothing.
"""

from __future__ import annotations

import ast
import os
import runpy
import sys
import threading
from pathlib import Path

MARKER = "G4USIM_ASSERTS="
PROBE_ID = "settrace_assert_lines_v3"
EXPRESSION_FRAMES = frozenset(("<genexpr>", "<listcomp>", "<setcomp>", "<dictcomp>", "<lambda>"))


def collect_assert_lines(path: Path) -> set[int]:
    """Return the 1-based line numbers that start an ``assert`` statement."""
    tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"), filename=str(path))
    return {node.lineno for node in ast.walk(tree) if isinstance(node, ast.Assert)}


def collect_assert_scopes(path: Path) -> dict[tuple[str, int], dict[int, int]]:
    """Map real statement scopes to Assert start/end lines.

    A file-global line set would also count a one-line function's definition in
    its caller, or a comprehension's expression evaluation, as an assertion.
    """
    scopes = {}
    current = {"asserts": [], "statements": []}
    scopes[("<module>", 1)] = current

    class Collector(ast.NodeVisitor):
        def visit(self, node):
            if isinstance(node, ast.stmt) and not isinstance(node, ast.Assert):
                current["statements"].append((node.lineno, node.col_offset))
            return super().visit(node)

        def visit_Assert(self, node):
            current["asserts"].append(node)

        def statement_scope(self, node):
            nonlocal current
            previous = current
            current = {"asserts": [], "statements": []}
            first = min([node.lineno] + [d.lineno for d in node.decorator_list])
            scopes[(node.name, first)] = current
            scopes[(node.name, node.lineno)] = current
            for statement in node.body:
                self.visit(statement)
            current = previous

        visit_FunctionDef = statement_scope
        visit_AsyncFunctionDef = statement_scope
        visit_ClassDef = statement_scope

    Collector().visit(ast.parse(path.read_text(encoding="utf-8", errors="replace"), filename=str(path)))
    result = {}
    for key, scope in scopes.items():
        lines = {}
        for node in scope["asserts"]:
            # if False: assert False (and similar inline compound statements)
            # has a line event for the condition, even though assert never runs.
            if any(line == node.lineno and column < node.col_offset for line, column in scope["statements"]):
                continue
            lines[node.lineno] = max(lines.get(node.lineno, 0), node.end_lineno or node.lineno)
        if lines:
            result[key] = lines
    return result


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("usage: test_assert_probe.py <test script> [args...]", file=sys.stderr)
        return 2
    target = Path(argv[1]).resolve()
    if not target.is_file():
        print(f"test assert probe: target script not found: {target}", file=sys.stderr)
        return 2
    assert_scopes = collect_assert_scopes(target)
    target_name = os.path.normcase(str(target))
    executed = [0]
    counter_lock = threading.Lock()

    def tracer(frame, event, arg):
        if event != "call" or os.path.normcase(frame.f_code.co_filename) != target_name:
            return None
        code = frame.f_code
        if code.co_name in EXPRESSION_FRAMES:
            return None
        lines = assert_scopes.get((code.co_name, code.co_firstlineno))
        if not lines:
            return None
        active_span = None

        def local_tracer(current_frame, kind, value):
            nonlocal active_span
            if kind == "line":
                line = current_frame.f_lineno
                if active_span and not active_span[0] <= line <= active_span[1]:
                    active_span = None
                if line in lines and active_span is None:
                    active_span = (line, lines[line])
                    with counter_lock:
                        executed[0] += 1
            return local_tracer

        return local_tracer

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
    # Worker threads would otherwise be invisible to the probe; only threads that
    # the script starts after this point are traced.
    threading.settrace(tracer)
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
        threading.settrace(None)
        print(f"{MARKER}{executed[0]}", flush=True)
        raise
    finally:
        sys.settrace(None)
        threading.settrace(None)
    print(f"{MARKER}{executed[0]}", flush=True)
    if message is not None:
        print(message, file=sys.stderr, flush=True)
    return status


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
