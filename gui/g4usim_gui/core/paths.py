from __future__ import annotations

import os
from pathlib import Path


def normalize_path(path: str) -> str:
    """Return a stable display string for a possibly empty path."""
    if not path:
        return ""
    return str(Path(path).expanduser())


def ensure_directory(path: str) -> Path:
    if not path:
        raise ValueError("Output directory is empty")
    directory = Path(path).expanduser()
    directory.mkdir(parents=True, exist_ok=True)
    if not directory.is_dir():
        raise ValueError(f"Path is not a directory: {directory}")
    return directory


def open_directory(path: str) -> None:
    directory = Path(path).expanduser()
    if not directory.exists():
        raise FileNotFoundError(f"Directory does not exist: {directory}")
    os.startfile(str(directory))  # type: ignore[attr-defined]


def format_size(num_bytes: int) -> str:
    units = ["B", "KB", "MB", "GB", "TB"]
    value = float(num_bytes)
    for unit in units:
        if value < 1024 or unit == units[-1]:
            return f"{value:.1f} {unit}" if unit != "B" else f"{int(value)} B"
        value /= 1024
    return f"{num_bytes} B"
