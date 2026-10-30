"""Strict data-only GUI drafts shared by project save and recovery.

Binding names are opaque machine identifiers. The UI must additionally check
them against its capture registry before projecting them onto widgets.
"""
from __future__ import annotations

import copy
import json
import re
from typing import Any

EDIT_STATE_VERSION = 1
MAX_EDIT_STATE_BYTES = 16 * 1024 * 1024
MAX_SOURCE_TEXT_BYTES = 4 * 1024 * 1024
MAX_BINDINGS = 4096
MAX_TABLE_CELLS = 100000
_BINDING = re.compile(r"[A-Za-z_][A-Za-z0-9_.:/-]{0,159}\Z")
_STATE_KEYS = {"version", "drafts", "tables", "selections", "sources"}
_SOURCE_KEYS = {"path", "text", "read_success", "template"}


def empty_editing_state() -> dict[str, Any]:
    return {"version": EDIT_STATE_VERSION, "drafts": {}, "tables": {}, "selections": {}, "sources": {}}


def _binding(value: Any, path: str) -> None:
    if type(value) is not str or not _BINDING.fullmatch(value):
        raise ValueError(f"Invalid editing binding: {path}")


def validate_editing_state(value: Any, path: str = "project.editingState") -> None:
    if type(value) is not dict:
        raise ValueError(f"Expected editing state object: {path}")
    if set(value) != _STATE_KEYS:
        unknown = sorted(set(value) - _STATE_KEYS)
        missing = sorted(_STATE_KEYS - set(value))
        raise ValueError(f"Invalid editing state fields at {path}: unknown={unknown}, missing={missing}")
    if type(value["version"]) is not int or value["version"] != EDIT_STATE_VERSION:
        raise ValueError(f"Unsupported editing state version at {path}.version")
    for name in ("drafts", "tables", "selections", "sources"):
        if type(value[name]) is not dict or len(value[name]) > MAX_BINDINGS:
            raise ValueError(f"Invalid editing state collection: {path}.{name}")
    for name, raw in value["drafts"].items():
        _binding(name, f"{path}.drafts.{name}")
        if type(raw) not in (str, bool, int):
            raise ValueError(f"Invalid raw draft type: {path}.drafts.{name}")
        if type(raw) is int and abs(raw) > 2**63 - 1:
            raise ValueError(f"Draft integer outside supported range: {path}.drafts.{name}")
    cells = 0
    for name, rows in value["tables"].items():
        _binding(name, f"{path}.tables.{name}")
        if type(rows) is not list or len(rows) > MAX_TABLE_CELLS:
            raise ValueError(f"Invalid draft table: {path}.tables.{name}")
        for index, row in enumerate(rows):
            if type(row) is not list or any(type(cell) is not str for cell in row):
                raise ValueError(f"Invalid draft table row: {path}.tables.{name}[{index}]")
            cells += len(row)
            if cells > MAX_TABLE_CELLS:
                raise ValueError("Editing table cell limit exceeded")
    for name, index in value["selections"].items():
        _binding(name, f"{path}.selections.{name}")
        if type(index) is not int or not -1 <= index <= MAX_TABLE_CELLS:
            raise ValueError(f"Invalid selection hint: {path}.selections.{name}")
    for kind, source in value["sources"].items():
        if kind not in {"materials", "geometry"} or type(source) is not dict or set(source) != _SOURCE_KEYS:
            raise ValueError(f"Invalid source snapshot fields: {path}.sources.{kind}")
        for key in ("path", "text", "template"):
            if type(source[key]) is not str:
                raise ValueError(f"Invalid source snapshot text: {path}.sources.{kind}.{key}")
        if type(source["read_success"]) is not bool:
            raise ValueError(f"Invalid source read status: {path}.sources.{kind}.read_success")
        if len(source["text"].encode("utf-8")) > MAX_SOURCE_TEXT_BYTES:
            raise ValueError(f"Source snapshot exceeds limit: {path}.sources.{kind}")
    raw = json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode("utf-8")
    if len(raw) > MAX_EDIT_STATE_BYTES:
        raise ValueError("Editing state exceeds size limit")


def copy_editing_state(value: dict[str, Any] | None) -> dict[str, Any]:
    state = empty_editing_state() if value is None else value
    validate_editing_state(state)
    return copy.deepcopy(state)
