#!/usr/bin/env python3
import argparse
import csv
import os
import tempfile
import sys
from pathlib import Path


def resolve_files(input_dir, pattern, files):
    resolved = [Path(item) for item in files]
    if input_dir:
        root = Path(input_dir)
        if not root.is_dir():
            raise FileNotFoundError(f"Input directory does not exist: {root}")
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "gui"))
        from g4usim_gui.output.provenance import output_evidence
        evidence = output_evidence(root)
        for message in evidence.warnings:
            print(message, file=sys.stderr)
        resolved.extend(evidence.matching(pattern))
    if not resolved:
        raise RuntimeError("No input files found")
    return sorted(resolved, key=lambda path: str(path.resolve()))


def merge(files, output):
    output = Path(output)
    inputs = sorted((Path(file_path) for file_path in files), key=lambda path: str(path.resolve()))
    if not inputs:
        raise RuntimeError("No input files found")
    canonical = [path.resolve() for path in inputs]
    if len(set(canonical)) != len(canonical):
        raise RuntimeError("Duplicate input file")
    if output.resolve() in canonical:
        raise RuntimeError("Output file must not also be an input file")
    if output.exists():
        raise FileExistsError(f"Output file already exists: {output}")

    header = None
    for file_path in inputs:
        with file_path.open(newline="", encoding="utf-8-sig") as in_handle:
            reader = csv.reader(in_handle)
            try:
                current_header = next(reader)
            except StopIteration as exc:
                raise RuntimeError(f"Empty CSV input: {file_path}") from exc
            if not current_header or any(not name for name in current_header):
                raise RuntimeError(f"Invalid CSV header in {file_path}")
            if header is None:
                header = current_header
            elif current_header != header:
                raise RuntimeError(f"Header mismatch in {file_path}")
            for line_number, row in enumerate(reader, start=2):
                if len(row) != len(header):
                    raise RuntimeError(f"Column count mismatch in {file_path}:{line_number}")

    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", newline="", encoding="utf-8", dir=output.parent,
            prefix=f".{output.name}.", suffix=".tmp", delete=False,
        ) as out_handle:
            temporary = Path(out_handle.name)
            writer = csv.writer(out_handle)
            writer.writerow(header)
            for file_path in inputs:
                with file_path.open(newline="", encoding="utf-8-sig") as in_handle:
                    reader = csv.reader(in_handle)
                    if next(reader, None) != header:
                        raise RuntimeError(f"Header changed while merging: {file_path}")
                    for line_number, row in enumerate(reader, start=2):
                        if len(row) != len(header):
                            raise RuntimeError(f"Column count changed while merging in {file_path}:{line_number}")
                        writer.writerow(row)
        # Hard-link publishing refuses an existing target on both Windows and POSIX.
        # The temporary file is complete before it becomes visible as the result.
        os.link(temporary, output)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description="Merge G4UniversalSim CSV outputs.")
    parser.add_argument("--input", help="Input directory")
    parser.add_argument("--pattern", default="event_edep_t*.csv", help="Glob pattern inside --input")
    parser.add_argument("--output", required=True, help="Merged output CSV")
    parser.add_argument("files", nargs="*", help="Explicit input files")
    args = parser.parse_args()

    files = resolve_files(args.input, args.pattern, args.files)
    merge(files, args.output)
    print(f"Merged {len(files)} files into {args.output}")


if __name__ == "__main__":
    main()
