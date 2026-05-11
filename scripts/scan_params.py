#!/usr/bin/env python3
import argparse
import shutil
import subprocess
from pathlib import Path


def split_values(text):
    return [item.strip() for item in text.split(",") if item.strip()]


def update_ini_value(path, dotted_key, value):
    if "." not in dotted_key:
        raise ValueError("--key must be in section.key form, for example source.energy")
    section, key = dotted_key.split(".", 1)
    lines = path.read_text(encoding="utf-8").splitlines()
    out = []
    current_section = None
    replaced = False
    inserted = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            if current_section == section and not replaced:
                out.append(f"{key} = {value}")
                replaced = True
                inserted = True
            current_section = stripped[1:-1].strip()
            out.append(line)
            continue
        if current_section == section and stripped and not stripped.startswith(("#", ";")):
            lhs = stripped.split("=", 1)[0].strip() if "=" in stripped else ""
            if lhs.lower() == key.lower():
                out.append(f"{key} = {value}")
                replaced = True
                continue
        out.append(line)

    if not inserted and current_section == section and not replaced:
        out.append(f"{key} = {value}")
        replaced = True
    if not replaced:
        out.extend([f"", f"[{section}]", f"{key} = {value}"])
    path.write_text("\n".join(out) + "\n", encoding="utf-8")


def safe_name(value):
    return "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in value)


def main():
    parser = argparse.ArgumentParser(description="Run a simple one-parameter G4UniversalSim scan.")
    parser.add_argument("--exe", required=True, help="G4UniversalSim executable")
    parser.add_argument("--config", required=True, help="Template main.ini")
    parser.add_argument("--key", required=True, help="section.key to modify, e.g. source.energy")
    parser.add_argument("--values", required=True, help="Comma-separated values")
    parser.add_argument("--out", required=True, help="Output scan directory")
    parser.add_argument("--macro", help="Optional macro passed with -m")
    parser.add_argument("--dry-run", action="store_true", help="Prepare configs but do not execute")
    args = parser.parse_args()

    root = Path(args.out)
    root.mkdir(parents=True, exist_ok=True)
    log_path = root / "scan_results.csv"

    with log_path.open("w", encoding="utf-8") as log:
        log.write("value,config,return_code\n")
        for value in split_values(args.values):
            run_dir = root / safe_name(value)
            run_dir.mkdir(parents=True, exist_ok=True)
            run_config = run_dir / "main.ini"
            shutil.copyfile(args.config, run_config)
            update_ini_value(run_config, args.key, value)
            update_ini_value(run_config, "output.dir", str(run_dir / "output"))

            command = [args.exe, "-c", str(run_config)]
            if args.macro:
                command.extend(["-m", args.macro])
            if args.dry_run:
                print("DRY:", " ".join(command))
                return_code = 0
            else:
                completed = subprocess.run(command, cwd=Path.cwd())
                return_code = completed.returncode
            log.write(f'"{value}","{run_config}",{return_code}\n')


if __name__ == "__main__":
    main()
