#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
EXE="${1:-}"

if [[ -z "$EXE" ]]; then
  for candidate in \
    "$ROOT/out/build/G4UniversalSim" \
    "$ROOT/out/build/x64-Release/G4UniversalSim" \
    "$ROOT/out/build/x64-Debug/G4UniversalSim" \
    "$ROOT/out/build_vs/x64-Release/G4UniversalSim" \
    "$ROOT/out/build_vs/x64-Debug/G4UniversalSim" \
    "$ROOT/build_vs2026/Release/G4UniversalSim" \
    "$ROOT/build_vs2026/Debug/G4UniversalSim" \
    "$ROOT/build_vs2026/RelWithDebInfo/G4UniversalSim" \
    "$ROOT/build_vs2026/MinSizeRel/G4UniversalSim"; do
    if [[ -x "$candidate" ]]; then
      EXE="$candidate"
      break
    fi
  done
fi

if [[ -z "$EXE" || ! -x "$EXE" ]]; then
  echo "G4UniversalSim executable not found. Pass it as the first argument." >&2
  exit 1
fi

cd "$ROOT"

mkdir -p test/output/layered_device
echo "Running layered_device..."
"$EXE" --config test/main_layered_device.ini --macro test/macros/test_layered_device_full.mac --output test/output/layered_device --run-name test_layered_device 2>&1 | tee test/output/layered_device/run.log

mkdir -p test/output/hierarchical
echo "Running hierarchical..."
"$EXE" --config test/main_hierarchical.ini --macro test/macros/test_hierarchical_full.mac --output test/output/hierarchical --run-name test_hierarchical 2>&1 | tee test/output/hierarchical/run.log

echo "All G4UniversalSim end-to-end tests completed."
