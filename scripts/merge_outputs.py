#!/usr/bin/env python3
import argparse
import csv
from pathlib import Path


def resolve_files(input_dir, pattern, files):
    resolved = [Path(item) for item in files]
    if input_dir:
        root = Path(input_dir)
        if not root.is_dir():
            raise FileNotFoundError(f"Input directory does not exist: {root}")
        resolved.extend(sorted(root.glob(pattern)))
    if not resolved:
        raise RuntimeError("No input files found")
    return resolved


def merge(files, output):
    output = Path(output)
    if output.parent:
        output.parent.mkdir(parents=True, exist_ok=True)

    header = None
    with output.open("w", newline="") as out_handle:
        writer = None
        for file_path in files:
            with Path(file_path).open(newline="") as in_handle:
                reader = csv.reader(in_handle)
                try:
                    current_header = next(reader)
                except StopIteration:
                    continue
                if header is None:
                    header = current_header
                    writer = csv.writer(out_handle)
                    writer.writerow(header)
                elif current_header != header:
                    raise RuntimeError(f"Header mismatch in {file_path}")
                for row in reader:
                    if row:
                        writer.writerow(row)


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
