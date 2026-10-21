"""Run an M5 prototype output extension against completed simulation outputs.

Example: python scripts/run_output_extension.py --run dose_json \
             --input-dir output --output report.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.output_extension_registry import OutputExtensionRegistry  # noqa: E402

BUILTINS = (
    ROOT / "scripts" / "extensions" / "dose_json_extension.py",
    ROOT / "scripts" / "extensions" / "fluence_json_extension.py",
)


def write_exclusive(output: Path, payload: dict) -> None:
    """Publish a complete JSON file, without replacing an existing result."""
    directory = output.parent.resolve()
    if not directory.is_dir():
        raise ValueError(f"Output directory does not exist: {directory}")
    content = (json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")
    temporary: Path | None = None
    try:
        handle, name = tempfile.mkstemp(prefix=".g4usim-extension-", suffix=".tmp", dir=directory)
        temporary = Path(name)
        with os.fdopen(handle, "wb") as stream:
            stream.write(content)
        os.link(temporary, output)  # atomic no-overwrite publication on supported filesystems
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Explicit, versioned output-extension prototype")
    parser.add_argument("--module", action="append", default=[], metavar="TRUSTED_PY",
                        help="explicitly load an additional trusted Python extension module")
    parser.add_argument("--list", action="store_true", help="print registered extension descriptors")
    parser.add_argument("--run", metavar="ID", help="registered extension to execute")
    parser.add_argument("--input-dir", type=Path, help="completed G4UniversalSim output directory")
    parser.add_argument("--output", type=Path, help="destination JSON, must not already exist")
    args = parser.parse_args()
    try:
        registry = OutputExtensionRegistry()
        for builtin in BUILTINS:
            registry.load_module(builtin)
        for module in args.module:
            registry.load_module(module)
        if args.list:
            print(json.dumps(registry.list_extensions(), ensure_ascii=False, indent=2))
            return 0
        if args.run is None or args.input_dir is None or args.output is None:
            parser.error("--run, --input-dir, and --output are required together")
        extension, data = registry.run(args.run, args.input_dir)
        write_exclusive(args.output.resolve(), {
            "schema": "G4UniversalSimOutputExtensionResult", "version": 1,
            "extension_id": extension.id, "extension_version": extension.version,
            "data": data,
        })
        print(args.output.resolve())
        return 0
    except (OSError, ValueError, TypeError) as error:
        print(f"Output extension failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
