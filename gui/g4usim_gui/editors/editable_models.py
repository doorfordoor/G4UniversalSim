from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class EditableState(str, Enum):
    CLEAN = "clean"
    DIRTY = "dirty"
    INVALID = "invalid"


class ValidationSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


@dataclass
class ValidationMessage:
    severity: ValidationSeverity
    message: str
    location: str = ""


@dataclass
class EditableDocument:
    source_path: str = ""
    generated_path: str = ""
    is_dirty: bool = False
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def state(self) -> EditableState:
        if self.errors:
            return EditableState.INVALID
        if self.is_dirty:
            return EditableState.DIRTY
        return EditableState.CLEAN
