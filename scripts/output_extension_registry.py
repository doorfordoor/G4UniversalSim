"""M5 prototype: explicit, versioned Python output postprocessor registration.

This interface postprocesses existing files. It cannot register Geant4 C++
scorers, mutate a live run, or claim physical validation of the input data.
"""
from __future__ import annotations

import importlib.util
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

API_VERSION = 1
IDENTIFIER = re.compile(r"[a-z][a-z0-9_]*\Z")
VERSION = re.compile(r"[0-9]+\.[0-9]+\.[0-9]+\Z")


@dataclass(frozen=True)
class OutputExtension:
    id: str
    version: str
    description: str
    process: Callable[[Path], dict]


class OutputExtensionRegistry:
    def __init__(self) -> None:
        self._extensions: dict[str, OutputExtension] = {}

    def register(self, metadata: dict, process: Callable[[Path], dict]) -> None:
        if not isinstance(metadata, dict) or metadata.get("api_version") != API_VERSION:
            raise ValueError("Unsupported output extension API version")
        identifier = metadata.get("id")
        version = metadata.get("version")
        description = metadata.get("description")
        if (not isinstance(identifier, str) or not IDENTIFIER.fullmatch(identifier)
                or not isinstance(version, str) or not VERSION.fullmatch(version)
                or not isinstance(description, str) or not description.strip()
                or not callable(process)):
            raise ValueError("Invalid output extension metadata or process entry")
        if identifier in self._extensions:
            raise ValueError(f"Duplicate output extension: {identifier}")
        self._extensions[identifier] = OutputExtension(identifier, version, description, process)

    def load_module(self, path: str | Path) -> None:
        """Execute an explicitly supplied, trusted Python module to register it."""
        source = Path(path).resolve()
        if not source.is_file() or source.suffix.lower() != ".py":
            raise ValueError(f"Output extension module is not a Python file: {source}")
        module_spec = importlib.util.spec_from_file_location(
            f"g4usim_output_ext_{len(self._extensions)}", source)
        if module_spec is None or module_spec.loader is None:
            raise ValueError(f"Cannot import output extension: {source}")
        module = importlib.util.module_from_spec(module_spec)
        module_spec.loader.exec_module(module)
        self.register(getattr(module, "EXTENSION", None), getattr(module, "process", None))

    def list_extensions(self) -> list[dict]:
        return [{"id": value.id, "version": value.version,
                 "api_version": API_VERSION, "description": value.description}
                for value in sorted(self._extensions.values(), key=lambda item: item.id)]

    def run(self, identifier: str, input_dir: str | Path) -> tuple[OutputExtension, dict]:
        if identifier not in self._extensions:
            raise ValueError(f"Output extension not registered: {identifier}")
        directory = Path(input_dir).resolve()
        if not directory.is_dir():
            raise ValueError(f"Input directory does not exist: {directory}")
        extension = self._extensions[identifier]
        data = extension.process(directory)
        if not isinstance(data, dict):
            raise ValueError(f"Output extension {identifier} must return a JSON object")
        return extension, data
