"""Bounded, Qt-free reader for the optional stdout progress protocol."""
from __future__ import annotations

import json
import math

PREFIX = "[G4USimProgress] "
SCHEMA = "g4usim_progress_v1"


def _reject_constant(value):
    raise ValueError("Non-finite JSON constant")


class ProgressParser:
    MAX_LINE = 16384

    def __init__(self):
        self._buffer = ""
        self._discard = False
        self.latest = None
        self._last_sequence = None

    def feed(self, text: str, *, final: bool = False) -> list[dict]:
        messages = []
        # Split incoming chunks without retaining an unbounded partial line.
        for part in text.splitlines(keepends=True):
            ended = part.endswith(("\n", "\r"))
            if not self._discard:
                if len(self._buffer) + len(part) > self.MAX_LINE:
                    self._buffer = ""
                    self._discard = True
                else:
                    self._buffer += part
            if ended:
                if not self._discard:
                    message = self._parse(self._buffer.rstrip("\r\n"))
                    if message is not None:
                        messages.append(message)
                self._buffer = ""
                self._discard = False
        if final:
            if self._buffer and not self._discard:
                message = self._parse(self._buffer)
                if message is not None:
                    messages.append(message)
            self._buffer = ""
            self._discard = False
        return messages

    def _parse(self, line):
        marker = line.find(PREFIX)
        if marker < 0:
            return None
        try:
            data = json.loads(line[marker + len(PREFIX):], parse_constant=_reject_constant)
            if not isinstance(data, dict) or data.get("schema") != SCHEMA:
                return None
            run = data.get("run_id")
            if type(run) is not int or run < 0:
                return None
            if data.get("phase") not in {"begin", "running", "end", "aborted"}:
                return None
            # Optional process-wide sequence: when emitted it must be a
            # non-negative integer that strictly increases, so a chunked pipe or a
            # duplicated line can be rejected instead of rewinding the display.
            sequence = data.get("sequence")
            if sequence is not None:
                if type(sequence) is not int or sequence < 0:
                    return None
                if self._last_sequence is not None and sequence <= self._last_sequence:
                    return None
            for key in ("planned_events", "completed_events"):
                value = data[key]
                if value is not None and (type(value) is not int or value < 0):
                    return None
            for key in ("elapsed_s", "rate_eps", "eta_s"):
                value = data[key]
                if value is not None and (type(value) not in (int, float) or not math.isfinite(value) or value < 0):
                    return None
            planned, completed = data["planned_events"], data["completed_events"]
            if planned is not None and completed is not None and completed > planned:
                return None
            old = self.latest
            if old:
                if run < old["run_id"]:
                    return None
                if run == old["run_id"]:
                    if old["phase"] in {"end", "aborted"} or data["phase"] == "begin":
                        return None
                    for key in ("completed_events", "elapsed_s"):
                        if old[key] is not None and (data[key] is None or data[key] < old[key]):
                            return None
                    if old["planned_events"] is not None and planned != old["planned_events"]:
                        return None
            if sequence is not None:
                self._last_sequence = sequence
            self.latest = data
            return data
        except (ValueError, KeyError, TypeError, OverflowError, RecursionError):
            return None
