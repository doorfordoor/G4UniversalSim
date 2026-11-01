from __future__ import annotations

import sys
from pathlib import Path


def _bootstrap_import_path() -> None:
    root = Path(__file__).resolve().parent
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))


def main() -> int:
    _bootstrap_import_path()
    try:
        from g4usim_gui.app import run_app
        return run_app(sys.argv)
    except Exception as error:
        if "--self-test" not in sys.argv:
            raise
        # Qt itself may fail to import, before app.self_test can write its report.
        # Keep automated package checks noninteractive and explicitly unsuccessful.
        import json
        import traceback
        index = sys.argv.index("--self-test")
        report_path = Path(sys.argv[index + 1]) if index + 1 < len(sys.argv) else Path("gui_self_test.json")
        report = {"schema": "g4usim_gui_self_test_v1", "ok": False,
                  "frozen": bool(getattr(sys, "frozen", False)), "stage": "startup",
                  "error": f"{type(error).__name__}: {error}", "traceback": traceback.format_exc()}
        try:
            with report_path.open("x", encoding="utf-8", newline="\n") as stream:
                json.dump(report, stream, ensure_ascii=False, indent=2)
                stream.write("\n")
        except OSError:
            if sys.stderr is not None:
                traceback.print_exc()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
