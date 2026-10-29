"""R26 real batch/csh rejection, native RNG state round-trip, and CLI precedence."""
from __future__ import annotations

import contextlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
EXE = Path(os.environ.get("G4USIM_EXE", ROOT / "build_vs2026/Release/G4UniversalSim.exe"))


def run_case(root: Path, name: str, commands: str, *, threads=1, ui=False, cli_seed=False):
    folder = root / name
    folder.mkdir()
    geom = folder / "geometry.ini"
    geom.write_text("[world]\nshape=box\nsize=100 mm,100 mm,100 mm\nmaterial=G4_Galactic\n"
                    "[volume.Target]\nparent=world\nshape=box\nsize=20 mm,20 mm,20 mm\n"
                    "material=G4_WATER\nsensitive=true\n", encoding="utf-8")
    ini = folder / "main.ini"
    ini.write_text(f"[run]\nthreads={threads}\nseed=93\n[output]\nformat=csv\n"
                   f"[geometry]\ntemplate=hierarchical\nconfig={geom.as_posix()}\n"
                   "[physics]\nem=option4\n[scoring]\nenabled=true\nhits=true\nevent_edep=true\n"
                   "[source]\nparticle=e-\nenergy=1 MeV\nposition=0,0,0 mm\ndirection=+z\n",
                   encoding="utf-8")
    macro = folder / "run.mac"
    macro.write_text(commands, encoding="utf-8")
    args = [str(EXE), "--config", str(ini), "--output", str(folder / "output")]
    args += ["--ui", "--ui-session", "csh"] if ui else ["--macro", str(macro)]
    if cli_seed:
        args += ["--seed", "94"]
    result = subprocess.run(args, cwd=folder, input=commands + "\nexit\n" if ui else None,
                            capture_output=True, text=True, errors="replace", timeout=120)
    log = result.stdout + result.stderr
    (folder / "run.log").write_text(log, encoding="utf-8", newline="\n")
    summary = folder / "output/run_summary.txt"
    assert summary.is_file(), (name, result.returncode, log[-2000:])
    facts = {k.strip(): v.strip() for line in summary.read_text(encoding="utf-8").splitlines()
             if "=" in line for k, v in [line.split("=", 1)]}
    return result, facts, folder


TAIL = "/control/echo RNG_COMMAND_CONTINUED\n/run/initialize\n/run/beamOn 4\n"


def rejected(result, facts, *, ui=False):
    assert result.returncode != 0 and facts["status"] == "failed", (result.returncode, facts)
    assert facts["actual_completed_event_count"] == "0", facts
    assert facts["macro_seed_modified"] == "false", facts
    assert "RNG_COMMAND_CONTINUED" not in result.stdout, result.stdout[-2000:]
    if ui:
        assert facts["interactive_command_failure_kind"] == "random_command_validation", facts
    else:
        assert facts["macro_failure_line"] == "1", facts
        assert facts["macro_failure_code_available"] == "false", facts


def main():
    assert EXE.is_file(), EXE
    with contextlib.ExitStack() as stack:
        root = Path(os.environ["G4USIM_TEST_WORK"]).resolve() if os.environ.get("G4USIM_TEST_WORK") else Path(
            stack.enter_context(tempfile.TemporaryDirectory(prefix="g4usim-rng-command-")))
        root.mkdir(parents=True, exist_ok=True)
        helper = EXE.with_name("randomCommandGuardCheck" + EXE.suffix)
        assert helper.is_file(), helper
        checked = subprocess.run([str(helper)], cwd=root, capture_output=True, text=True, errors="replace", timeout=30)
        assert checked.returncode == 0, checked.stdout + checked.stderr
        assert "checks=" in checked.stdout, checked.stdout
        (root / "component.log").write_text(checked.stdout + checked.stderr, encoding="utf-8", newline="\n")
        invalid = ["123", "123 abc", "123 4junk", "123 0", "0 456",
                   "123 999999999999999999999999999999", " ".join(["123"] * 100)]
        for threads in (1, 2):
            for i, seeds in enumerate(invalid):
                r, facts, _ = run_case(root, f"bad-{threads}-{i}", "/random/setSeeds " + seeds + "\n" + TAIL,
                                       threads=threads)
                rejected(r, facts)
            r, facts, _ = run_case(root, f"valid-{threads}", "/random/setSeeds 123 456\n" + TAIL, threads=threads)
            assert r.returncode == 0 and facts["status"] == "completed", (facts, r.stderr)
            assert facts["macro_seed_modified"] == "true" and facts["actual_completed_event_count"] == "4"
            r, facts, _ = run_case(root, f"csh-bad-{threads}", "/random/setSeeds 123\n" + TAIL,
                                   threads=threads, ui=True)
            rejected(r, facts, ui=True)
            r, facts, _ = run_case(root, f"cli-lock-{threads}", "/random/setSeeds 123 456\n" + TAIL,
                                   threads=threads, cli_seed=True)
            rejected(r, facts)

        r, facts, _ = run_case(root, "csh-alias-bad",
                               "/control/alias seedCommand /random/setSeeds\n{seedCommand} 123\n" + TAIL, ui=True)
        rejected(r, facts, ui=True)
        r, facts, _ = run_case(root, "csh-alias-valid",
                               "/control/alias seedCommand /random/setSeeds\n{seedCommand} 123 456\n" + TAIL, ui=True)
        assert r.returncode == 0 and facts["macro_seed_modified"] == "true", facts
        r, facts, _ = run_case(root, "csh-cli-lock", "/random/setSeeds 123 456\n" + TAIL,
                               ui=True, cli_seed=True)
        rejected(r, facts, ui=True)
        nested = root / "nested.mac"
        nested.write_text("# nested source location\n/random/setSeeds 123\n", encoding="utf-8")
        r, facts, _ = run_case(root, "nested-location", f"/control/execute {nested.as_posix()}\n" + TAIL)
        assert r.returncode != 0 and facts["status"] == "failed", facts
        assert facts["macro_failure_line"] == "2" and Path(facts["macro_failure_file"]) == nested, facts
        assert facts["macro_seed_modified"] == "false" and facts["actual_completed_event_count"] == "0", facts
        r, facts, _ = run_case(root, "csh-nested-refused", f"/control/execute {nested.as_posix()}\n" + TAIL, ui=True)
        rejected(r, facts, ui=True)

        for ui in (False, True):
            r, facts, _ = run_case(root, f"double-slash-{ui}", "//random///setSeeds 123\n" + TAIL, ui=ui)
            rejected(r, facts, ui=ui)

        for kind in ("if", "doif", "strif", "strdoif"):
            for ui in (False, True):
                operand = "x" if kind.startswith("str") else "1"
                command = f"/control/{kind} {operand} == {operand} /random/setSeeds 123 456\n"
                r, facts, _ = run_case(root, f"conditional-{kind}-{ui}", command + TAIL, ui=ui)
                rejected(r, facts, ui=ui)

        bad_files = root / "bad-state"
        bad_files.mkdir()
        for name, text in (("empty.rndm", ""), ("junk.rndm", "not a random engine\n"),
                           ("truncated.rndm", "mixmax state, file version 1.0\n")):
            (bad_files / name).write_text(text, encoding="utf-8")
        for i, name in enumerate(("missing.rndm", "empty.rndm", "junk.rndm", "truncated.rndm")):
            command = f"/random/resetEngineFrom {(bad_files / name).as_posix()}\n"
            r, facts, _ = run_case(root, f"restore-bad-{i}", command + TAIL)
            rejected(r, facts)
            r, facts, _ = run_case(root, f"restore-csh-bad-{i}", command + TAIL, ui=True)
            rejected(r, facts, ui=True)

        for threads in (1, 2):
            states = root / f"saved-{threads}"
            states.mkdir()
            r, facts, _ = run_case(root, f"save-{threads}",
                                   f"/random/setDirectoryName {states.as_posix()}/\n/random/setSavingFlag true\n"
                                   "/run/initialize\n/run/beamOn 4\n", threads=threads)
            assert r.returncode == 0 and facts["status"] == "completed", (facts, r.stderr)
            candidates = sorted(states.glob("*currentRun.rndm"))
            master = next((p for p in candidates if "Master" in p.name),
                          next((p for p in candidates if p.name == "currentRun.rndm"), None))
            assert master is not None, list(states.iterdir())
            # Copying the original engine file also exercises paths with spaces.
            portable = states / "saved state.rndm"
            shutil.copyfile(master, portable)
            for ui in (False, True):
                r, facts, _ = run_case(root, f"restore-{threads}-{ui}",
                                       f'/random/resetEngineFrom "{portable.as_posix()}"\n' + TAIL,
                                       threads=threads, ui=ui)
                assert r.returncode == 0 and facts["status"] == "completed", (facts, r.stderr[-2000:])
                assert facts["macro_seed_modified"] == "true" and facts["actual_completed_event_count"] == "4"
        r, facts, _ = run_case(root, "per-event-refused", "/random/resetEngineFromEachEvent true\n" + TAIL)
        rejected(r, facts)
        r, facts, _ = run_case(root, "per-event-off", "/random/resetEngineFromEachEvent false\n" + TAIL)
        assert r.returncode == 0 and facts["macro_seed_modified"] == "false", facts
        print("random command semantics: PASS; master state only, no full-worker replay claim")


if __name__ == "__main__":
    main()
