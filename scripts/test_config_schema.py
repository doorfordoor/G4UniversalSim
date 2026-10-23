"""The configuration schema must say what the backend does (roadmap E2).

1. The generated files (C++ key table, GUI data module, support-matrix tables) are up to
   date with schema/config_schema.json.
2. For every field of the migrated sections, and every alias, a set of values derived
   from its type and limits (valid ones, boundary ones, and wrong ones: bad syntax, out
   of range, unknown unit, not allowed) goes through the GUI's schema check
   (g4usim_gui.core.config_schema.check_value) and through the backend
   (G4UniversalSim --config <main.ini> --inspect-run, which runs the real Configure);
   the two verdicts must agree.
3. A valid value of every field and alias is consumed by the backend (no "unconsumed
   field" warning), and an unknown key in each migrated section is reported, so the key
   lists cannot drift.
4. Defaults: with the field absent, the backend's inspected value equals the schema's
   default (for the fields --inspect-run reports), and with only an alias present the
   alias is used; when the canonical name and an alias are both given, the canonical
   name wins.
5. The GUI uses the schema: the run-settings and Run Config validators reject what the
   backend rejects (seed out of range, a run name on two lines, too many trajectory
   events), and the controls' tooltips are the schema's hints in the current language.

    gui\\.venv\\Scripts\\python.exe scripts\\test_config_schema.py [-v]
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "gui"))
EXE = Path(os.environ.get("G4USIM_EXE", ROOT / "build_vs2026/Release/G4UniversalSim.exe"))

from g4usim_gui.core.config_schema import SCHEMA, check_value, spec   # noqa: E402

# --inspect-run reports these fields in initial_configuration (name -> (section, key))
INSPECTED = {"threads": ("run", "threads"), "seed": ("run", "seed"), "run_name": ("run", "name"),
             "dry_run": ("run", "dry_run"), "interactive": ("run", "interactive"),
             "check_overlaps": ("run", "check_overlaps"), "macro_file": ("run", "macro"),
             "output_dir": ("output", "dir")}


def candidates(data: dict, work: Path) -> list[str]:
    kind = data["type"]
    low, high = data.get("min"), data.get("max")
    if kind == "int":
        values = ["0", "1", "+3", " 7 ", "-1", "abc", "1.5", "1e3", "0x10", "", "2147483647", "2147483648",
                  "-2147483649", "99999999999"]
        values += [str(v) for v in (low, high) if v is not None]
        values += [str(low - 1)] if low is not None and low > -2147483648 else []
        values += [str(high + 1)] if high is not None and high < 2147483647 else []
        return values
    if kind == "bool":
        return ["true", "YES", "on", "1", "False", "no", "OFF", "0", "maybe", "2", ""]
    if kind == "enum":
        return [*data["allowed"], *(v.upper() for v in data["allowed"]), *data.get("value_aliases", {}),
                "xml", ""]
    if kind == "energy":
        return ["5", "5 GeV", "5*keV", "0 MeV", "1e-3 MeV", "0x10 MeV", ".5 eV", "-1 MeV", "5 kg", "5 Me V",
                "nan MeV", "inf", "", "1 TeV", "5 mev"]
    if kind == "existing_file":
        existing = work / "exists.mac"
        existing.write_text("# empty\n", encoding="utf-8")
        return ["", existing.as_posix(), "test/macros/run_hierarchical_batch.mac", (work / "missing.mac").as_posix()]
    return ["abc", "", "with space", "中文名"]


def inspect(work: Path, name: str, body: str) -> tuple[bool, str, dict]:
    """(accepted, stderr, the inspected configuration) for a main INI with this body."""
    main = work / f"{name}.ini"
    main.write_text(body, encoding="utf-8")
    process = subprocess.run([str(EXE), "--config", str(main), "--inspect-run"], cwd=str(ROOT),
                             capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
    values = {}
    if process.returncode == 0:
        plan = json.loads(process.stdout)
        values = {item["name"]: item for item in plan.get("initial_configuration", [])}
    return process.returncode == 0, process.stderr, values


def check_gui(failures: list[str]) -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication   # noqa: PLC0415
    from g4usim_gui.core.i18n import apply_language   # noqa: PLC0415
    from g4usim_gui.editors.source_physics_scoring_model import (   # noqa: PLC0415
        ScoringEditableModel, validate_scoring_model)
    from g4usim_gui.models.package_model import GeometrySettings, PathSettings   # noqa: PLC0415
    from g4usim_gui.models.physics_model import PhysicsSettings   # noqa: PLC0415
    from g4usim_gui.models.run_model import RunSettings   # noqa: PLC0415
    from g4usim_gui.models.scoring_model import ScoringSettings   # noqa: PLC0415
    from g4usim_gui.models.source_model import SourceSettings   # noqa: PLC0415
    from g4usim_gui.validators.config_validator import validate_config_builder   # noqa: PLC0415
    from g4usim_gui.widgets.config.setup_panel import SetupPanel   # noqa: PLC0415

    def run_errors(run: RunSettings) -> list[str]:
        report = validate_config_builder(
            paths=PathSettings(executable=str(EXE), workspace_root=str(ROOT), runs_root=str(ROOT)),
            run=run, geometry=GeometrySettings(), source=SourceSettings(), physics=PhysicsSettings(),
            scoring=ScoringSettings())
        return [e for e in report.errors if e.startswith("[run]")]

    for run, bad in ((RunSettings(seed=99999999999), True), (RunSettings(seed=-5), True),
                     (RunSettings(run_name="a\nb"), True), (RunSettings(seed=2147483647), False)):
        if bool(run_errors(run)) != bad:
            failures.append(f"GUI run settings {run.seed!r}/{run.run_name!r}: expected {'an error' if bad else 'none'}")
    model = validate_scoring_model(ScoringEditableModel(trajectory_events=1001))
    if not any("trajectories" in e for e in model.errors):
        failures.append("GUI: 1001 trajectory events (above the schema's GUI maximum) is not refused")
    app = QApplication.instance() or QApplication([])
    panel = SetupPanel(lambda: None, lambda: None)
    english = panel.seed.toolTip()
    apply_language(panel, "zh_CN")
    chinese = panel.seed.toolTip()
    apply_language(panel, "en")
    if not english.startswith("[run] seed: Random seed") or "随机数种子" not in chinese or panel.seed.toolTip() != english:
        failures.append(f"GUI tooltips: {english!r} / {chinese!r}")
    panel.deleteLater()
    app.processEvents()
    print("GUI: validators and tooltips follow the schema")


def main() -> int:
    verbose = "-v" in sys.argv
    failures: list[str] = []
    check_gui(failures)
    generated = subprocess.run([sys.executable, str(ROOT / "scripts/generate_config_schema.py"), "--check"],
                               capture_output=True, text=True)
    if generated.returncode != 0:
        failures.append(generated.stdout.strip())
    print(f"generated files: {'up to date' if generated.returncode == 0 else 'OUT OF DATE'}")
    if not EXE.is_file():
        print(f"SKIP backend part: {EXE} missing")
        return 1 if failures else 0

    with tempfile.TemporaryDirectory(prefix="g4usim-schema-") as temp:
        work = Path(temp)
        jobs = []          # (label, section, key, value)
        for section, section_spec in SCHEMA["main_ini"].items():
            for key, data in section_spec["keys"].items():
                for name in [key, *data.get("aliases", [])]:
                    for value in candidates(data, work):
                        jobs.append((f"[{section}]/{name} = {value!r}", section, name, value))

        def run(index_job):
            index, (label, section, name, value) = index_job
            out = work / "out"
            body = f"[{section}]\n{name} = {value}\n"
            if section != "output":
                body += f"\n[output]\ndir = {out.as_posix()}\n"
            accepted, stderr, _ = inspect(work, f"case{index:04d}", body)
            gui = check_value(section, name, value, base_dir=ROOT)
            return label, accepted, gui, stderr

        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(run, enumerate(jobs)))
        agree = 0
        for label, accepted, gui, stderr in results:
            if accepted == (gui is None):
                agree += 1
                if verbose:
                    print(f"  ok {label}: {'accept' if accepted else 'reject'}")
            else:
                reason = stderr.strip().splitlines()[-1] if stderr.strip() else ""
                failures.append(f"{label}: backend {'accepts' if accepted else 'rejects'}, schema "
                                f"{'accepts' if gui is None else 'rejects (' + gui + ')'}; backend says: {reason}")
        print(f"values: {agree} of {len(results)} verdicts agree")

        # 3. every field and alias is consumed; unknown keys are reported
        consumed = 0
        for section, section_spec in SCHEMA["main_ini"].items():
            for key, data in section_spec["keys"].items():
                value = next(v for v in candidates(data, work) if v and check_value(section, key, v, base_dir=ROOT) is None)
                for name in [key, *data.get("aliases", [])]:
                    accepted, stderr, _ = inspect(work, "consumed", f"[{section}]\n{name} = {value}\n")
                    if not accepted or "unconsumed field" in stderr:
                        failures.append(f"[{section}]/{name} = {value}: not consumed by the backend ({stderr.strip()[:200]})")
                    else:
                        consumed += 1
            accepted, stderr, _ = inspect(work, "unknown", f"[{section}]\nnot_a_field = 1\n")
            if f"[{section}]/not_a_field" not in stderr:
                failures.append(f"[{section}]/not_a_field: the backend does not report an unknown key")
        print(f"keys: {consumed} fields and aliases consumed; unknown keys reported in {len(SCHEMA['main_ini'])} sections")

        # 4. defaults and alias precedence, where --inspect-run reports the value
        accepted, _, defaults = inspect(work, "defaults", "[run]\n")
        for name, (section, key) in INSPECTED.items():
            default = spec(section, key).default
            got = defaults.get(name, {}).get("value")
            if default is None:
                if got not in ("", "unset", None, "unknown"):
                    print(f"  note: {name} has no schema default; the backend reports {got!r}")
                continue
            if got != default:
                failures.append(f"default of [{section}]/{key}: schema {default!r}, backend {got!r}")
        for section, key, alias, name in (("run", "name", "run_name", "run_name"), ("run", "seed", "randomSeed", "seed"),
                                          ("output", "dir", "outputDir", "output_dir")):
            _, _, only_alias = inspect(work, "alias", f"[{section}]\n{alias} = 42\n")
            _, _, both = inspect(work, "both", f"[{section}]\n{alias} = 41\n{key} = 43\n")
            if only_alias.get(name, {}).get("value") != "42" or both.get(name, {}).get("value") != "43":
                failures.append(f"[{section}]/{alias}: alias alone gives {only_alias.get(name, {}).get('value')!r}, "
                                f"with {key} it gives {both.get(name, {}).get('value')!r} (expected 42 and 43)")
        print("defaults and alias precedence checked")

    if failures:
        print("\nFAILURES:")
        for line in failures:
            print("  " + line)
        return 1
    print("test_config_schema: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
