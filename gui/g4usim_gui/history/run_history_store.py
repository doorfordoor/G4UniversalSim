from __future__ import annotations

import json
from pathlib import Path


STATE_PATH = Path.home() / ".g4universalsim_gui_state.json"


def load_state() -> dict:
    if not STATE_PATH.is_file():
        return {}
    try:
        return json.loads(STATE_PATH.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return {}


def save_state(state: dict) -> None:
    try:
        STATE_PATH.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    except Exception:
        pass


def add_recent_project(path: str) -> None:
    if not path:
        return
    state = load_state()
    items = [item for item in state.get("recentProjects", []) if item != path and Path(item).exists()]
    items.insert(0, path)
    state["recentProjects"] = items[:10]
    save_state(state)


def clear_recent_projects() -> None:
    state = load_state()
    state["recentProjects"] = []
    save_state(state)


def get_recent_projects() -> list[str]:
    state = load_state()
    return [item for item in state.get("recentProjects", []) if Path(item).exists()]
