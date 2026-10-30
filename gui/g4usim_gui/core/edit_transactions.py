"""Atomic configuration history with bounded encoded persistent payloads.

The byte budget counts encoded before/after states, not Python process RAM or
the separately retained transient parser context.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from g4usim_gui.core.edit_snapshot import (
    WorkspaceSnapshot, clone_snapshot, snapshot_fingerprint, snapshot_size,
)

ApplySnapshot = Callable[[WorkspaceSnapshot], None]


class TransactionError(ValueError):
    pass


class TransactionConflict(TransactionError):
    pass


class TransactionCapacityError(TransactionError):
    pass


class TransactionApplyError(TransactionError):
    def __init__(self, original: Exception, rollback: Exception | None = None) -> None:
        self.original = original
        self.rollback = rollback
        message = f"Workspace update failed: {original}"
        if rollback is not None:
            message += f"; restoring the previous workspace also failed: {rollback}"
        super().__init__(message)


@dataclass
class _Command:
    before: WorkspaceSnapshot
    after: WorkspaceSnapshot
    label: str
    merge_key: str | None
    merge_generation: int
    size: int


class EditSession:
    def __init__(self, initial: WorkspaceSnapshot, *, max_commands: int = 100,
                 max_bytes: int = 32 * 1024 * 1024, saved: bool = True) -> None:
        if type(max_commands) is not int or max_commands < 1 or type(max_bytes) is not int or max_bytes < 1:
            raise ValueError("History capacities must be positive integers")
        self.max_commands = max_commands
        self.max_bytes = max_bytes
        self._current = clone_snapshot(initial)
        fingerprint = snapshot_fingerprint(self._current)
        if snapshot_size(self._current) > max_bytes:
            raise TransactionCapacityError("Initial workspace exceeds history capacity")
        # Only cache our private, defensively cloned state. External candidates
        # still cross the complete snapshot validation/source-rebuild boundary.
        self._current_fingerprint = fingerprint
        self._saved_fingerprint = fingerprint if saved else None
        self._commands: list[_Command] = []
        self._cursor = 0
        self._revision = 0
        self._merge_generation = 0
        self._applying = False

    def current(self) -> WorkspaceSnapshot:
        return clone_snapshot(self._current)

    @property
    def revision(self) -> int:
        return self._revision

    @property
    def is_modified(self) -> bool:
        return self._current_fingerprint != self._saved_fingerprint

    @property
    def saved_fingerprint(self) -> str | None:
        return self._saved_fingerprint

    @property
    def can_undo(self) -> bool:
        return self._cursor > 0

    @property
    def can_redo(self) -> bool:
        return self._cursor < len(self._commands)

    @property
    def undo_label(self) -> str:
        return self._commands[self._cursor - 1].label if self.can_undo else ""

    @property
    def redo_label(self) -> str:
        return self._commands[self._cursor].label if self.can_redo else ""

    @property
    def history_count(self) -> int:
        return len(self._commands)

    @property
    def history_bytes(self) -> int:
        return sum(command.size for command in self._commands)

    def _check(self, expected_revision: int | None = None) -> None:
        if self._applying:
            raise TransactionError("Nested workspace publication is not allowed")
        if expected_revision is not None and (type(expected_revision) is not int or expected_revision != self._revision):
            raise TransactionConflict("Workspace changed before the transaction could be applied")

    def _apply(self, candidate: WorkspaceSnapshot, apply: ApplySnapshot | None) -> None:
        if apply is None:
            return
        self._applying = True
        try:
            try:
                apply(clone_snapshot(candidate))
            except Exception as original:
                try:
                    apply(self.current())
                except Exception as rollback:
                    raise TransactionApplyError(original, rollback) from original
                raise TransactionApplyError(original) from original
        finally:
            self._applying = False

    def break_merge(self) -> None:
        self._check()
        self._merge_generation += 1

    def mark_saved(self, snapshot: WorkspaceSnapshot | None = None) -> None:
        self._check()
        fingerprint = self._current_fingerprint if snapshot is None else snapshot_fingerprint(snapshot)
        self._saved_fingerprint = fingerprint
        self._merge_generation += 1

    def replace(self, label: str, after: WorkspaceSnapshot, *, merge_key: str | None = None,
                expected_revision: int | None = None, apply: ApplySnapshot | None = None) -> WorkspaceSnapshot:
        self._check(expected_revision)
        if type(label) is not str or not label or (merge_key is not None and type(merge_key) is not str):
            raise ValueError("Transaction label/key must be text")
        candidate = clone_snapshot(after)
        candidate_fingerprint = snapshot_fingerprint(candidate)
        if candidate_fingerprint == self._current_fingerprint:
            return self.current()
        commands = list(self._commands[:self._cursor])
        before = self._current
        if (commands and self._cursor == len(self._commands) and merge_key is not None
                and commands[-1].merge_key == merge_key
                and commands[-1].merge_generation == self._merge_generation):
            before = commands.pop().before
        size = snapshot_size(before) + snapshot_size(candidate)
        if size > self.max_bytes:
            raise TransactionCapacityError("One configuration transaction exceeds history capacity")
        if snapshot_fingerprint(before) != candidate_fingerprint:
            commands.append(_Command(clone_snapshot(before), clone_snapshot(candidate), label,
                                     merge_key, self._merge_generation, size))
        while len(commands) > self.max_commands or sum(command.size for command in commands) > self.max_bytes:
            commands.pop(0)
        self._apply(candidate, apply)
        self._commands = commands
        self._cursor = len(commands)
        self._current = candidate
        self._current_fingerprint = candidate_fingerprint
        self._revision += 1
        return self.current()

    def record(self, after: WorkspaceSnapshot, label: str, **kwargs) -> WorkspaceSnapshot:
        return self.replace(label, after, **kwargs)

    def transact(self, label: str, transform: Callable[[WorkspaceSnapshot], WorkspaceSnapshot | None],
                 *, merge_key: str | None = None, expected_revision: int | None = None,
                 apply: ApplySnapshot | None = None) -> WorkspaceSnapshot:
        self._check(expected_revision)
        candidate = self.current()
        starting_revision = self._revision
        self._applying = True
        try:
            result = transform(candidate)
        finally:
            self._applying = False
        if result is not None:
            candidate = result
        # Capture the starting revision as a guard against reentrant callers.
        return self.replace(label, candidate, merge_key=merge_key,
                            expected_revision=starting_revision, apply=apply)

    def undo(self, *, apply: ApplySnapshot | None = None) -> WorkspaceSnapshot:
        self._check()
        if not self.can_undo:
            return self.current()
        candidate = clone_snapshot(self._commands[self._cursor - 1].before)
        fingerprint = snapshot_fingerprint(candidate)
        self._apply(candidate, apply)
        self._current = candidate
        self._current_fingerprint = fingerprint
        self._cursor -= 1
        self._revision += 1
        self._merge_generation += 1
        return self.current()

    def redo(self, *, apply: ApplySnapshot | None = None) -> WorkspaceSnapshot:
        self._check()
        if not self.can_redo:
            return self.current()
        candidate = clone_snapshot(self._commands[self._cursor].after)
        fingerprint = snapshot_fingerprint(candidate)
        self._apply(candidate, apply)
        self._current = candidate
        self._current_fingerprint = fingerprint
        self._cursor += 1
        self._revision += 1
        self._merge_generation += 1
        return self.current()

    def reset(self, snapshot: WorkspaceSnapshot, *, saved: bool = True,
              apply: ApplySnapshot | None = None) -> WorkspaceSnapshot:
        self._check()
        candidate = clone_snapshot(snapshot)
        fingerprint = snapshot_fingerprint(candidate)
        if snapshot_size(candidate) > self.max_bytes:
            raise TransactionCapacityError("Workspace exceeds history capacity")
        self._apply(candidate, apply)
        self._current = candidate
        self._current_fingerprint = fingerprint
        self._commands = []
        self._cursor = 0
        self._saved_fingerprint = fingerprint if saved else None
        self._revision += 1
        self._merge_generation += 1
        return self.current()
