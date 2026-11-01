"""Frozen Python helper for trusted package scripts and scientific data tools.

This is an interpreter-like execution helper, not an execution sandbox. It supports
script.py, -c, -m and --version so the I1 Python probe and installed tools share the
same actual Python/numpy/uproot runtime. No simulation is started automatically.
"""
from __future__ import annotations

import runpy
import sys
from pathlib import Path


def main():
    # Runtime imports must not add unmanaged __pycache__ files to a read-only or
    # independently uninstallable installation prefix.
    sys.dont_write_bytecode = True
    arguments = sys.argv[1:]
    root = Path(sys.executable).resolve().parents[1] if getattr(sys, "frozen", False) else Path(__file__).resolve().parents[1]
    sys.path[:0] = [str(root), str(root / "python_modules")]
    if not arguments or arguments[0] in ("--version", "-V"):
        print("Python " + sys.version.split()[0] + " (G4UniversalSim packaged helper)")
        return 0
    if arguments[0] == "-c":
        if len(arguments) < 2:
            raise SystemExit("-c requires Python source")
        sys.argv = ["-c", *arguments[2:]]
        exec(compile(arguments[1], "<string>", "exec"), {"__name__": "__main__", "__builtins__": __builtins__})
    elif arguments[0] == "-m":
        if len(arguments) < 2:
            raise SystemExit("-m requires a module name")
        sys.argv = arguments[1:]
        runpy.run_module(arguments[1], run_name="__main__", alter_sys=True)
    else:
        script = Path(arguments[0]).absolute()
        sys.argv = [str(script), *arguments[1:]]
        sys.path.insert(0, str(script.parent))
        runpy.run_path(str(script), run_name="__main__")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
