from __future__ import annotations

import sys
from pathlib import Path


def _bootstrap_import_path() -> None:
    root = Path(__file__).resolve().parent
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))


def main() -> int:
    _bootstrap_import_path()
    from g4usim_gui.app import run_app

    return run_app(sys.argv)


if __name__ == "__main__":
    raise SystemExit(main())
