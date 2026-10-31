"""Plan backend process creation without changing the host's working directory.

Windows CreateProcess has a cwd limit independent of the child's long-path
manifest. Start in a short existing ancestor and let the backend restore its
logical cwd before doing any work. This module owns no process or resources.
"""
from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import re
import shutil
from typing import Sequence

WINDOWS = os.name == "nt"
# Reserve the final backslash and terminating NUL from MAX_PATH (260).
MAX_LAUNCH_CWD_UNITS = 258
WORKING_DIRECTORY_OPTION = "--working-directory"
# Match main.cc ParseCommandLine: each of these consumes its next token even
# when that value looks like an option. Unknown options remain backend errors.
_VALUE_OPTIONS = frozenset({
    "--dump-effective-config", WORKING_DIRECTORY_OPTION,
    "--config", "-c", "--macro", "-m", "--output", "-o", "--run-name",
    "--ui-session", "--threads", "-t", "--seed", "--check-overlaps",
})


class BackendLaunchError(ValueError):
    def __init__(self, code: str, detail: str = "") -> None:
        self.code = code
        self.detail = detail
        super().__init__(code + (": " + detail if detail else ""))


def utf16_units(value: str) -> int:
    return len(value.encode("utf-16-le")) // 2


@dataclass(frozen=True)
class BackendLaunch:
    program: str
    arguments: tuple[str, ...]
    logical_cwd: str
    launch_cwd: str
    route: str

    @property
    def command(self) -> list[str]:
        return [self.program, *self.arguments]

    @property
    def requires_working_directory(self) -> bool:
        return self.route == "restore_working_directory"

    def to_dict(self) -> dict:
        return {"program": self.program, "arguments": list(self.arguments),
                "working_directory": self.logical_cwd,
                "launch_working_directory": self.launch_cwd,
                "launch_route": self.route,
                "logical_cwd_utf16_units": utf16_units(self.logical_cwd),
                "launch_cwd_utf16_units": utf16_units(self.launch_cwd)}


def _directory(value: str | os.PathLike | None) -> Path:
    try:
        path = Path(value if value else Path.cwd()).expanduser().resolve(strict=True)
        if not path.is_dir():
            raise BackendLaunchError("backend_launch.cwd_not_directory", str(path))
        return path
    except OSError as error:
        raise BackendLaunchError("backend_launch.cwd_unavailable", str(error)) from error


def _program(value: str) -> str:
    path = Path(value).expanduser()
    # Match the established explicit-file entry point before searching PATH;
    # either resolution is made now, before selecting a launch ancestor.
    if not path.is_absolute() and path.parent == Path(".") and not path.is_file():
        located = shutil.which(value)
        if located is None:
            raise BackendLaunchError("backend_launch.program_not_found", value)
        path = Path(located)
    try:
        path = path.resolve(strict=True)
        if not path.is_file():
            raise BackendLaunchError("backend_launch.program_not_file", str(path))
    except OSError as error:
        raise BackendLaunchError("backend_launch.program_unavailable", str(error)) from error
    return str(path)


def prepare_backend_launch(command: Sequence[str], cwd: str | os.PathLike | None) -> BackendLaunch:
    if isinstance(command, (str, bytes)) or not command:
        raise BackendLaunchError("backend_launch.invalid_command")
    try:
        values = [os.fspath(value) for value in command]
    except TypeError as error:
        raise BackendLaunchError("backend_launch.invalid_command") from error
    if any(type(value) is not str or "\x00" in value for value in values) or not values[0]:
        raise BackendLaunchError("backend_launch.invalid_command")
    program = _program(values[0])
    logical = _directory(cwd)
    arguments = values[1:]
    indexes = []
    index = 0
    while index < len(arguments):
        option = arguments[index]
        if option.startswith(WORKING_DIRECTORY_OPTION + "="):
            raise BackendLaunchError("backend_launch.invalid_working_directory_option")
        if option == WORKING_DIRECTORY_OPTION:
            indexes.append(index)
        index += 2 if option in _VALUE_OPTIONS else 1
    if len(indexes) > 1:
        raise BackendLaunchError("backend_launch.duplicate_working_directory")
    if indexes:
        index = indexes[0]
        if index + 1 >= len(arguments) or not arguments[index + 1]:
            raise BackendLaunchError("backend_launch.missing_working_directory")
        declared = Path(arguments[index + 1])
        if not declared.is_absolute():
            raise BackendLaunchError("backend_launch.relative_working_directory")
        if os.path.normcase(str(_directory(declared))) != os.path.normcase(str(logical)):
            raise BackendLaunchError("backend_launch.conflicting_working_directory")
    if not WINDOWS or utf16_units(str(logical)) <= MAX_LAUNCH_CWD_UNITS:
        return BackendLaunch(program, tuple(arguments), str(logical), str(logical), "direct")
    launch = None
    for ancestor in logical.parents:
        if utf16_units(str(ancestor)) <= MAX_LAUNCH_CWD_UNITS and ancestor.is_dir():
            launch = ancestor
            break
    if launch is None:
        raise BackendLaunchError("backend_launch.unsupported_cwd", str(logical))
    if not indexes:
        arguments = [WORKING_DIRECTORY_OPTION, str(logical), *arguments]
    return BackendLaunch(program, tuple(arguments), str(logical), str(launch), "restore_working_directory")


def unsupported_working_directory(stderr: str) -> bool:
    """Recognize an old backend's explicit option refusal, never generic errors."""
    return re.search(r"(?:unknown|unrecognized|unsupported)[^\r\n]{0,48}"
                     r"(?:option|argument|command[- ]line)[^\r\n]{0,48}"
                     r"--working-directory\b", stderr, re.IGNORECASE) is not None
