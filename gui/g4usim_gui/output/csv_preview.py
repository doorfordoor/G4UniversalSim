from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class CsvPreview:
    path: str
    exists: bool
    too_large: bool = False
    size: int = 0
    header: list[str] = field(default_factory=list)
    rows: list[list[str]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def read_csv_preview(path: str | Path, max_rows: int = 200, max_bytes: int = 50 * 1024 * 1024) -> CsvPreview:
    source = Path(path)
    preview = CsvPreview(path=str(source), exists=source.exists())
    if not source.exists():
        preview.warnings.append("CSV file does not exist.")
        return preview
    preview.size = source.stat().st_size
    if preview.size > max_bytes:
        preview.too_large = True
        preview.warnings.append("CSV is larger than preview limit.")
        return preview
    try:
        with source.open("r", encoding="utf-8", errors="replace", newline="") as handle:
            reader = csv.reader(handle)
            for index, row in enumerate(reader):
                if index == 0:
                    preview.header = row
                    continue
                if len(preview.rows) >= max_rows:
                    preview.warnings.append(f"Preview truncated at {max_rows} rows.")
                    break
                preview.rows.append(row)
    except Exception as exc:  # noqa: BLE001
        preview.warnings.append(f"CSV preview failed: {exc}")
        try:
            with source.open("r", encoding="utf-8", errors="replace") as handle:
                lines = []
                for _, line in zip(range(max_rows), handle):
                    lines.append([line.rstrip("\n")])
                preview.header = ["raw"]
                preview.rows = lines
        except Exception as raw_exc:  # noqa: BLE001
            preview.warnings.append(f"Raw preview fallback failed: {raw_exc}")
    if not preview.header and not preview.rows:
        preview.warnings.append("CSV is empty.")
    elif preview.header and not preview.rows:
        preview.warnings.append("CSV contains header only.")
    return preview
