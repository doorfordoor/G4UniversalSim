"""Regression: detector/seed commands are pre-initialisation only.

Before this guard, ``/AIHL/detector/enableSD`` and ``/AIHL/detector/setSDName`` only warned
when the world already existed: they changed the DetectorConstruction cache while the kernel
kept the old sensitive detector, and the batch returned 0. ``/AIHL/app/setSeed`` after
``/run/initialize`` re-seeded only the master engine, so the run was neither reproducible nor
described by the summary's ``configured_seed``. All three are now refused by the Geant4 state
gate (``G4State_PreInit``) plus an explicit ``SimulationManager::SetSeed`` guard.

The sensitive-detector factory also receives the configured name, so a custom
``setSDName`` value is the name actually registered instead of a hard-coded
``AIHLParticleSD`` (which made re-initialisation register a second detector).
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EXE = ROOT / "build_vs2026" / "Release" / "G4UniversalSim.exe"


def run(executable: Path, args: list[str], cwd: Path, expected: int = 0) -> str:
    result = subprocess.run(
        [str(executable), *args],
        cwd=cwd,
        text=True,
        capture_output=True,
        timeout=300,
    )
    output = result.stdout + result.stderr
    assert result.returncode == expected, (
        f"Unexpected exit code for {' '.join(args)}: expected {expected}, "
        f"got {result.returncode}\n{output}"
    )
    return output


def read_summary(output_dir: Path) -> dict[str, str]:
    summary = output_dir / "run_summary.txt"
    assert summary.is_file(), f"run_summary.txt was not created: {summary}"
    values: dict[str, str] = {}
    in_values = False
    for line in summary.read_text(encoding="utf-8").splitlines():
        if line.strip() == "[Values]":
            in_values = True
            continue
        if in_values and " = " in line:
            key, value = line.split(" = ", 1)
            values[key] = value
    return values


# Verification helpers use assert so tools/test_assert_probe.py counts every check.
def require(text: str, expected: str) -> None:
    assert expected in text, f"Expected marker not found: {expected}\n{text}"


def write_macro(path: Path, body: str) -> Path:
    path.write_text(body.strip() + "\n", encoding="utf-8")
    return path


def main() -> int:
    executable = Path(os.environ.get("G4USIM_EXE", str(DEFAULT_EXE)))
    if not executable.is_file():
        raise SystemExit(f"Executable not found: {executable}")

    with tempfile.TemporaryDirectory(prefix="g4usim-state-gate-") as temporary:
        temp = Path(temporary)
        shutil.copytree(ROOT / "config", temp / "config")
        config = temp / "config" / "main.ini"

        # A) Pre-initialisation values are accepted and reach the kernel summary. The default
        #    config marks its Target sensitive, so the custom SD name must be attached.
        pre_init_output = temp / "out-pre-init"
        pre_init_text = run(
            executable,
            [
                "--config",
                str(config),
                "--macro",
                str(
                    write_macro(
                        temp / "pre_init.mac",
                        """
/AIHL/detector/setSDName SensorA
/AIHL/app/setSeed 4242
/run/initialize
/run/beamOn 1
""",
                    )
                ),
                "--output",
                str(pre_init_output),
            ],
            cwd=temp,
        )
        require(pre_init_text, "Attached sensitive detector 'SensorA'")
        pre_init_values = read_summary(pre_init_output)
        assert pre_init_values.get("configured_seed") == "4242", (
            f"pre-initialisation seed not applied, configured_seed="
            f"{pre_init_values.get('configured_seed')!r}"
        )
        assert pre_init_values.get("status") == "completed", (
            f"pre-initialisation run failed, status={pre_init_values.get('status')!r}"
        )

        # B) The same commands after /run/initialize must fail the batch and the summary.
        for command, output_suffix in (
            ("/AIHL/app/setSeed 7", "seed"),
            ("/AIHL/detector/setSDName LateSD", "sd-name"),
            ("/AIHL/detector/enableSD false", "enable-sd"),
        ):
            output_dir = temp / f"out-late-{output_suffix}"
            text = run(
                executable,
                [
                    "--config",
                    str(config),
                    "--macro",
                    str(
                        write_macro(
                            temp / f"late_{output_suffix}.mac",
                            f"""
/run/initialize
{command}
/run/beamOn 1
""",
                        )
                    ),
                    "--output",
                    str(output_dir),
                ],
                cwd=temp,
                expected=1,
            )
            # The state gate makes G4UImanager refuse the command with status 200; the batch
            # must turn that into a fatal, non-zero result instead of continuing.
            require(text, "fatal error: Failed to execute macro command")
            require(text, "G4UImanager status=200")
            require(text, command)
            values = read_summary(output_dir)
            assert values.get("status") == "failed", (
                f"{command!r} after /run/initialize did not fail the run, "
                f"status={values.get('status')!r}\n{text}"
            )

    print("test_command_state_gating: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
