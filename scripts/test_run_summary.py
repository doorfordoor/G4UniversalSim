"""M0-2 black-box tests for final run summaries."""

from __future__ import annotations

import csv
import os
import subprocess
import shutil
import tempfile
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EXE = ROOT / "build_vs2026" / "Release" / "G4UniversalSim.exe"
TEST_CWD = ROOT


def run(executable: Path, args: list[str], expected: int = 0) -> str:
    result = subprocess.run(
        [str(executable), *args],
        cwd=TEST_CWD,
        text=True,
        capture_output=True,
        timeout=120,
    )
    output = result.stdout + result.stderr
    if result.returncode != expected:
        raise AssertionError(
            f"Unexpected exit code for {' '.join(args)}: "
            f"expected {expected}, got {result.returncode}\n{output}"
        )
    return output


def read_summary(directory: Path) -> tuple[dict[str, str], list[str]]:
    summary = directory / "run_summary.txt"
    if not summary.is_file():
        raise AssertionError(f"run_summary.txt was not created: {summary}")
    values: dict[str, str] = {}
    generated: list[str] = []
    section = ""
    for line in summary.read_text(encoding="utf-8").splitlines():
        if line.startswith("[") and line.endswith("]"):
            section = line
            continue
        if section in {"[Values]", "[Runs]"} and " = " in line:
            key, value = line.split(" = ", 1)
            values[key] = value
        elif section == "[GeneratedFiles]" and line.startswith("- "):
            generated.append(line[2:])
    return values, generated


def read_generated_file_schemas(directory: Path) -> dict[str, str]:
    entries: dict[str, str] = {}
    section = ""
    indexed: dict[str, dict[str, str]] = {}
    for line in (directory / "run_summary.txt").read_text(encoding="utf-8").splitlines():
        if line.startswith("[") and line.endswith("]"):
            section = line
            continue
        if section != "[GeneratedFileSchemas]" or " = " not in line:
            continue
        key, value = line.split(" = ", 1)
        index, field = key.rsplit("_", 1)
        indexed.setdefault(index, {})[field] = value
    for pair in indexed.values():
        assert set(pair) == {"path", "schema"}, pair
        entries[pair["path"]] = pair["schema"]
    return entries


def normalize(path: str) -> str:
    return os.path.normcase(os.path.abspath(path))


def main() -> int:
    global TEST_CWD
    executable = Path(os.environ.get("G4USIM_EXE", str(DEFAULT_EXE)))
    if not executable.is_file():
        raise SystemExit(f"Executable not found: {executable}")

    with tempfile.TemporaryDirectory(prefix="g4usim-m02-") as temporary:
        temp = Path(temporary)
        TEST_CWD = temp
        shutil.copytree(ROOT / "config", temp / "config")
        dry_output = temp / "dry-output"
        single_output = temp / "single-output"
        multi_output = temp / "multi-output"
        multi_mt_output = temp / "multi-mt-output"
        manifest_output = temp / "manifest-output"
        event_fault_output = temp / "event-fault-output"
        finalize_fault_output = temp / "finalize-fault-output"
        failed_output = temp / "failed-output"
        no_run_output = temp / "no-run-output"
        scoring_off_output = temp / "scoring-off-output"
        changed_output = temp / "changed-output"
        locked_output = temp / "locked-output"
        write_failure_output = temp / "write-failure-output"
        csv_failure_output = temp / "csv-failure-output"
        second_run_csv_failure_output = temp / "second-run-csv-failure-output"
        dry_macro = temp / "dry.mac"
        single_macro = temp / "single.mac"
        multi_macro = temp / "multi.mac"
        manifest_macro = temp / "manifest.mac"
        failed_macro = temp / "failed.mac"
        preflight_macro = temp / "preflight-failed.mac"
        late_main_config_macro = temp / "late-main-config.mac"
        random_seed_macro = temp / "random-seed.mac"
        random_nonseed_macro = temp / "random-nonseed.mac"
        no_run_macro = temp / "no-run.mac"
        changed_macro = temp / "changed.mac"
        geometry_origin_macro = temp / "geometry-origin.mac"
        geometry_clear_macro = temp / "geometry-clear.mac"
        late_geometry_macro = temp / "geometry-after-init.mac"
        early_threads_macro = temp / "threads-before-init.mac"
        late_threads_macro = temp / "threads-after-init.mac"
        source_preset_macro = temp / "source-preset.mac"
        source_particle_macro = temp / "source-particle.mac"
        source_energy_macro = temp / "source-energy.mac"
        source_reset_macro = temp / "source-reset.mac"
        physics_reference_macro = temp / "physics-reference.mac"
        physics_base_macro = temp / "physics-base.mac"
        physics_em_macro = temp / "physics-em.mac"
        physics_clear_macro = temp / "physics-clear.mac"
        output_command_fault_macro = temp / "output-command-fault.mac"
        second_material_macro = temp / "second-material.mac"
        manual_material_macro = temp / "manual-material.mac"
        late_material_macro = temp / "late-material.mac"
        missing_initialize_macro = temp / "missing-initialize.mac"
        invalid_material_macro = temp / "invalid-material.mac"
        hit_macro = temp / "hit.mac"
        source_sampling_macro = temp / "source-sampling.mac"
        source_native_interleave_macro = temp / "source-native-interleave.mac"

        dry_macro.write_text(
            "/control/echo SHOULD_NOT_EXECUTE\n/run/beamOn 2\n", encoding="utf-8"
        )
        single_macro.write_text(
            "/run/initialize\n/run/beamOn 3\n", encoding="utf-8"
        )
        multi_macro.write_text(
            "/run/initialize\n/run/beamOn 2\n/run/beamOn 3\n", encoding="utf-8"
        )
        manifest_macro.write_text(
            "/run/initialize\n/run/beamOn 5000\n", encoding="utf-8"
        )
        scoring_off_config = temp / "scoring-off.ini"
        main_text = (temp / "config" / "main.ini").read_text(encoding="utf-8")
        # Manifest registration tests exercise output I/O rather than energy
        # deposition. Pin a beam directed away from the target so a corrected
        # +Z fixed-direction source cannot produce multi-GB hit output here.
        assert main_text.count("direction = 0,0,1") == 1
        manifest_config = temp / "manifest-source-away.ini"
        manifest_config.write_text(
            main_text.replace("direction = 0,0,1", "direction = 0,0,-1"), encoding="utf-8"
        )
        assert "[scoring]\nenabled = true" in main_text
        source_preset_only_config = temp / "source-preset-only.ini"
        assert "preset = proton_beam\nparticle = proton" in main_text
        source_preset_only_config.write_text(
            main_text.replace("preset = proton_beam\nparticle = proton", "preset = neutron_beam"),
            encoding="utf-8",
        )
        source_energy_override_config = temp / "source-energy-override.ini"
        source_energy_override_config.write_text(
            main_text.replace("energy = 10 MeV", "energy = 5 MeV"), encoding="utf-8"
        )
        physics_em_config = temp / "physics-em.ini"
        physics_em_config.write_text(
            main_text.replace("reference = FTFP_BERT_EMZ", "reference = FTFP_BERT\nem = option4"),
            encoding="utf-8",
        )
        scoring_off_config.write_text(
            main_text.replace("[scoring]\nenabled = true", "[scoring]\nenabled = false"), encoding="utf-8"
        )
        failed_macro.write_text(
            "/run/initialize\n/run/beamOn 2\n/random/showEngineStatus\n/does/not/exist\n", encoding="utf-8"
        )
        preflight_macro.write_text(
            "/AIHL/app/setSeed 88\n/control/echo SHOULD_NOT_RUN\n", encoding="utf-8"
        )
        late_main_config_macro.write_text(
            "/AIHL/app/setMainConfig config/main.ini\n/control/echo SHOULD_NOT_RUN\n",
            encoding="utf-8",
        )
        random_seed_macro.write_text(
            "/random/setSeeds 123 456\n/run/initialize\n/run/beamOn 1\n", encoding="utf-8"
        )
        random_nonseed_macro.write_text(
            f"/random/setDirectoryName {temp.as_posix()}/\n"
            "/random/setSavingFlag true\n/run/initialize\n/run/beamOn 1\n", encoding="utf-8"
        )
        no_run_macro.write_text("/control/echo NO_BEAMON\n", encoding="utf-8")
        changed_macro.write_text(
            f"/AIHL/output/setDir {changed_output.as_posix()}\n"
            "/run/initialize\n/run/beamOn 2\n",
            encoding="utf-8",
        )
        geometry_origin_macro.write_text(
            "/AIHL/geometry/setTemplate simple_box\n"
            "/AIHL/geometry/loadConfig config/geometry/simple_box.ini\n"
            "/AIHL/geometry/setDefaultWorldMaterial G4_Galactic\n"
            "/run/initialize\n/run/beamOn 1\n",
            encoding="utf-8",
        )
        geometry_clear_macro.write_text("/AIHL/geometry/clear\n", encoding="utf-8")
        late_geometry_macro.write_text(
            "/run/initialize\n/AIHL/geometry/setTemplate hierarchical\n"
            "/control/echo GEOMETRY_MUTATION_CONTINUED\n/run/beamOn 1\n",
            encoding="utf-8",
        )
        early_threads_macro.write_text(
            "/AIHL/app/setNumThreads 2\n/run/initialize\n/run/beamOn 3\n", encoding="utf-8",
        )
        late_threads_macro.write_text(
            "/run/initialize\n/AIHL/app/setNumThreads 3\n"
            "/control/echo THREAD_MUTATION_CONTINUED\n/run/beamOn 3\n", encoding="utf-8",
        )
        source_preset_macro.write_text(
            "/AIHL/source/preset gamma_beam\n/run/initialize\n/run/beamOn 1\n",
            encoding="utf-8",
        )
        source_particle_macro.write_text(
            "/AIHL/source/preset gamma_beam\n"
            "/AIHL/source/particle proton\n/run/initialize\n/run/beamOn 1\n",
            encoding="utf-8",
        )
        source_energy_macro.write_text(
            "/AIHL/source/preset gamma_beam\n"
            "/AIHL/source/energy 7 MeV\n/run/initialize\n/run/beamOn 1\n",
            encoding="utf-8",
        )
        source_reset_macro.write_text("/AIHL/source/reset\n", encoding="utf-8")
        physics_reference_macro.write_text(
            "/AIHL/physics/setReferenceList QGSP_BERT\n/run/initialize\n/run/beamOn 1\n",
            encoding="utf-8",
        )
        physics_base_macro.write_text(
            "/AIHL/physics/setBaseReferenceList QGSP_BERT\n/run/initialize\n/run/beamOn 1\n",
            encoding="utf-8",
        )
        physics_em_macro.write_text(
            "/AIHL/physics/setEM option4\n/run/initialize\n/run/beamOn 1\n",
            encoding="utf-8",
        )
        physics_clear_macro.write_text("/AIHL/physics/clearReferenceList\n", encoding="utf-8")
        output_command_fault_target = temp / "output-command-fault-target"
        output_command_rejected_target = temp / "__g4usim_inject_manager_set_dir__"
        output_command_fault_config = temp / "output-command-fault.ini"
        output_command_fault_config.write_text(
            main_text.replace("dir = output/simple_test", f"dir = {output_command_fault_target.as_posix()}"),
            encoding="utf-8",
        )
        output_command_fault_macro.write_text(
            f"/AIHL/output/setDir {output_command_rejected_target.as_posix()}\n"
            "/control/echo SHOULD_NOT_CONTINUE_OUTPUT_ERROR\n"
            "/run/initialize\n/run/beamOn 1\n",
            encoding="utf-8",
        )
        second_material_macro.write_text(
            "/AIHL/material/load config/materials/material.ini\n",
            encoding="utf-8",
        )
        manual_material_macro.write_text(
            "/AIHL/material/addNist nist=G4_Si name=macro_silicon\n",
            encoding="utf-8",
        )
        late_material_macro.write_text(
            "/run/initialize\n/AIHL/material/load config/materials/material.ini\n",
            encoding="utf-8",
        )
        missing_initialize_macro.write_text(
            "/run/beamOn 1\n"
            "/AIHL/material/load config/materials/material.ini\n"
            "/control/echo SHOULD_NOT_RUN_AFTER_BEAMON\n",
            encoding="utf-8",
        )
        invalid_material_macro.write_text(
            "/AIHL/material/addNist missing_required_nist=G4_Si\n"
            "/run/initialize\n/run/beamOn 1\n",
            encoding="utf-8",
        )
        hit_macro.write_text((ROOT / "macros" / "run_hit_smoke.mac").read_text(encoding="utf-8"), encoding="utf-8")
        source_sampling_macro.write_text(
            hit_macro.read_text(encoding="utf-8").replace(
                "/run/beamOn 100",
                "/run/beamOn 3\n"
                "/AIHL/source/particle proton\n"
                "/AIHL/source/energy 3 MeV\n"
                "/run/beamOn 3",
            ),
            encoding="utf-8",
        )
        source_native_interleave_macro.write_text(
            hit_macro.read_text(encoding="utf-8").replace(
                "/run/beamOn 100",
                "/run/beamOn 8\n"
                "/gps/ene/mono 2 MeV\n"
                "/run/beamOn 8\n"
                "/AIHL/source/particle proton\n"
                "/run/beamOn 8",
            ),
            encoding="utf-8",
        )

        # Invalid source geometry input used to be silently ignored: the
        # configured preset still ran two events at its old point position.
        # Reject it before kernel initialization and event transport.
        source_invalid_type_ini = temp / "source-invalid-position-type.ini"
        source_invalid_type_ini.write_text(
            main_text.replace("position_type = point", "position_type = unsupported_ellipsoid"),
            encoding="utf-8",
        )
        source_missing_point_ini = temp / "source-missing-point.ini"
        source_missing_point_ini.write_text(
            main_text.replace("position = 0,0,-1 mm", ""), encoding="utf-8",
        )
        # Explicit empty fields were marked consumed while silently falling
        # back to the preset. Absent keys remain valid for preset defaults.
        empty_source_fields = []
        for key, configured in (("preset", "proton_beam"),
                                ("particle", "proton"),
                                ("energy", "10 MeV")):
            original = f"{key} = {configured}"
            assert main_text.count(original) == 1, original
            path = temp / f"source-empty-{key}.ini"
            path.write_text(main_text.replace(original, f"{key} =   "), encoding="utf-8")
            empty_source_fields.append((path, f"[source]/{key} must not be empty"))
        # strtod accepts NaN/Inf, but they cannot represent a physical GPS
        # source. They previously passed --inspect-run without an error.
        invalid_numeric_sources = []
        for name, old, new in (
            ("direction-nan", "direction = 0,0,1", "direction = NaN,0,1"),
            ("direction-inf", "direction = 0,0,1", "direction = inf,0,1"),
            ("energy-nan", "energy = 10 MeV", "energy = NaN MeV"),
            ("position-inf", "position = 0,0,-1 mm", "position = inf,0,-1 mm"),
            ("radius-nan", "position_type = point\nposition = 0,0,-1 mm",
             "position_type = plane\ncenter = 0,0,-1 mm\nradius = NaN mm"),
        ):
            assert main_text.count(old) == 1, (name, old)
            path = temp / f"source-invalid-{name}.ini"
            path.write_text(main_text.replace(old, new), encoding="utf-8")
            invalid_numeric_sources.append(path)
        invalid_source_macro = temp / "source-invalid.mac"
        invalid_source_macro.write_text("/run/initialize\n/run/beamOn 2\n", encoding="utf-8")
        for bad_config, expected_error in (
            (source_invalid_type_ini, "unsupported [source]/position_type"),
            (source_missing_point_ini, "[source]/position_type=point requires"),
            *empty_source_fields,
            *((path, "Non-finite numeric value") for path in invalid_numeric_sources),
        ):
            invalid_source_output = temp / (bad_config.stem + "-output")
            output = run(executable, ["--config", str(bad_config),
                                     "--macro", str(invalid_source_macro),
                                     "--output", str(invalid_source_output)], expected=1)
            assert expected_error in output, output
            assert not list(invalid_source_output.glob("hits*.csv")), invalid_source_output

        # An explicit isotropic=false must not silently inherit the isotropic
        # direction from a preset. The original program completed real events
        # with random primary directions despite this request.
        assert main_text.count("preset = proton_beam") == 1
        assert main_text.count("direction = 0,0,1") == 1
        inherited_iso = main_text.replace("preset = proton_beam", "preset = isotropic_neutron")
        source_disabled_isotropic_ini = temp / "source-disable-isotropic-without-direction.ini"
        source_disabled_isotropic_ini.write_text(
            inherited_iso.replace("direction = 0,0,1", "isotropic = false"), encoding="utf-8")
        source_disabled_isotropic_output = temp / "source-disable-isotropic-without-direction-output"
        output = run(executable, ["--config", str(source_disabled_isotropic_ini),
                                  "--macro", str(invalid_source_macro),
                                  "--output", str(source_disabled_isotropic_output)], expected=1)
        assert "isotropic=false cannot disable an isotropic preset" in output, output
        assert not list(source_disabled_isotropic_output.glob("hits*.csv"))

        # Providing a fixed direction resolves the contradictory preset.
        source_explicit_direction_ini = temp / "source-disable-isotropic-with-direction.ini"
        source_explicit_direction_ini.write_text(
            inherited_iso.replace("direction = 0,0,1", "isotropic = false\ndirection = 0,0,1"),
            encoding="utf-8",
        )
        explicit_direction_macro = temp / "source-disable-isotropic-direction.mac"
        explicit_direction_macro.write_text(
            "/AIHL/geometry/loadConfig config/geometry/hit_smoke_box.ini\n"
            "/run/initialize\n/run/beamOn 6\n", encoding="utf-8",
        )
        explicit_direction_output = temp / "source-disable-isotropic-with-direction-output"
        run(executable, ["--config", str(source_explicit_direction_ini),
                         "--macro", str(explicit_direction_macro),
                         "--output", str(explicit_direction_output), "--threads", "1"])
        direction_summary, _ = read_summary(explicit_direction_output)
        assert direction_summary["status"] == "completed", direction_summary
        assert direction_summary["actual_completed_event_count"] == "6", direction_summary
        with (explicit_direction_output / "hits_t0.csv").open(newline="", encoding="utf-8") as stream:
            first_directions = {}
            for hit in csv.DictReader(stream):
                if hit["trackID"] == "1" and hit["parentID"] == "0":
                    first_directions.setdefault(int(hit["eventID"]), hit)
        assert set(first_directions) == set(range(6)), first_directions.keys()
        for hit in first_directions.values():
            assert abs(float(hit["px"])) < 1e-6, hit
            assert abs(float(hit["py"])) < 1e-6, hit
            assert abs(float(hit["pz"]) - 1.0) < 1e-6, hit

        # The old beam1d angular type emitted -Z regardless of the requested
        # fixed vector; also verify a reverse and a non-axis-aligned beam.
        for label, configured_direction, expected_vector in (
            ("reverse-z", "0,0,-1", (0.0, 0.0, -1.0)),
            ("diagonal", "1,0,1", (2 ** -0.5, 0.0, 2 ** -0.5)),
        ):
            directional_ini = temp / f"source-fixed-{label}.ini"
            directional_ini.write_text(
                main_text.replace("direction = 0,0,1", f"direction = {configured_direction}"),
                encoding="utf-8",
            )
            directional_output = temp / f"source-fixed-{label}-output"
            run(executable, ["--config", str(directional_ini),
                             "--macro", str(explicit_direction_macro),
                             "--output", str(directional_output), "--threads", "1"])
            directional_summary, _ = read_summary(directional_output)
            assert directional_summary["status"] == "completed", directional_summary
            assert directional_summary["actual_completed_event_count"] == "6", directional_summary
            with (directional_output / "hits_t0.csv").open(newline="", encoding="utf-8") as stream:
                first_vectors = {}
                for hit in csv.DictReader(stream):
                    if hit["trackID"] == "1" and hit["parentID"] == "0":
                        first_vectors.setdefault(int(hit["eventID"]), hit)
            assert set(first_vectors) == set(range(6)), first_vectors.keys()
            for hit in first_vectors.values():
                for column, expected in zip(("px", "py", "pz"), expected_vector):
                    assert abs(float(hit[column]) - expected) < 1e-6, hit

        # The plane center must reach GPS in all three dimensions. Previously
        # SourceManager parsed center x/y but silently reset both to zero;
        # Geant4 still ran successfully and the hit positions were wrong.
        plane_config = temp / "source-plane-offset.ini"
        plane_fixture = "position_type = point\nposition = 0,0,-1 mm"
        assert main_text.count(plane_fixture) == 1, "plane test input fixture changed"
        plane_config.write_text(
            main_text.replace(
                plane_fixture,
                "position_type = plane\ncenter = 4 mm, 0 mm, -9 mm\nradius = 0.05 mm",
            ),
            encoding="utf-8",
        )
        plane_macro = temp / "source-plane-offset.mac"
        plane_macro.write_text(
            "/AIHL/geometry/loadConfig config/geometry/hit_smoke_box.ini\n"
            "/run/initialize\n/run/beamOn 12\n",
            encoding="utf-8",
        )
        plane_output = temp / "source-plane-offset-output"
        run(executable, ["--config", str(plane_config), "--macro", str(plane_macro),
                         "--output", str(plane_output), "--threads", "1"])
        plane_values, _ = read_summary(plane_output)
        assert plane_values["status"] == "completed", plane_values
        assert plane_values["actual_completed_event_count"] == "12", plane_values
        with (plane_output / "hits_t0.csv").open(newline="", encoding="utf-8") as stream:
            first_steps = {}
            for hit in csv.DictReader(stream):
                if hit["trackID"] == "1" and hit["parentID"] == "0":
                    first_steps.setdefault(int(hit["eventID"]), hit)
        assert set(first_steps) == set(range(12)), first_steps.keys()
        for hit in first_steps.values():
            assert abs(float(hit["x0_mm"]) - 4.0) < 0.051, hit
            assert abs(float(hit["y0_mm"])) < 0.051, hit
            assert abs(float(hit["z0_mm"]) + 9.0) < 1e-6, hit

        # dry-run produces a summary but never creates simulation output.
        dry_text = run(
            executable,
            ["--macro", str(dry_macro), "--output", str(dry_output), "--dry-run"],
        )
        if "SHOULD_NOT_EXECUTE" in dry_text:
            raise AssertionError("dry-run executed the macro")
        dry_values, dry_files = read_summary(dry_output)
        assert dry_values["status"] == "dry_run"
        assert dry_values["run_summary_schema_version"] == "1"
        assert dry_values["actual_completed_event_count"] == "0"
        assert dry_values["run_count"] == "0"
        assert dry_values["actual_threads"] == "not_executed"
        assert dry_values["macro_execution_status"] == "skipped_dry_run"
        assert dry_values["effective_config_snapshot_version"] == "1"
        assert dry_values["effective_config_snapshot_scope"] == "manager_state_subset"
        assert dry_values["effective_config_macro_execution_status"] == "skipped_dry_run"
        assert dry_values["effective_config_geant4_applied"] == "unknown"
        assert any(Path(file).name == "run_summary.txt" for file in dry_files)
        assert read_generated_file_schemas(dry_output) == {
            file: "run_summary_v1" for file in dry_files
        }

        # A single real run reports completed events and generated files.
        run(executable, ["--config", "config/main.ini", "--macro", str(single_macro), "--output", str(single_output), "--seed", "77"])
        single_values, single_files = read_summary(single_output)
        assert single_values["status"] == "completed"
        assert single_values["output_csv_schema_version"] == "3"
        assert single_values["run_count"] == "1"
        assert single_values["planned_event_count"] == "3"
        assert single_values["actual_completed_event_count"] == "3"
        assert single_values["initial_seed"] == "77"
        assert single_values["macro_seed_modified"] == "false"
        assert single_values["program_exit_code"] == "0"
        assert single_values["effective_config_snapshot_stage"] == "finalization"
        assert single_values["effective_config_source_coverage"] == "startup_geometry_source_and_physics_reference"
        assert single_values["effective_output_dir_origin_kind"] == "cli"
        assert single_values["effective_seed_origin_kind"] == "cli"
        assert single_values["effective_threads_origin_kind"] == "main_ini"
        assert single_values["effective_threads_origin_section"] == "run"
        assert single_values["effective_threads_origin_key"] == "threads"
        assert int(single_values["effective_threads_origin_line"]) > 0
        assert single_values["effective_check_overlaps_origin_kind"] == "main_ini"
        assert single_values["effective_check_overlaps_origin_section"] == "geometry"
        assert single_values["effective_requested_threads"] == "1"
        assert single_values["effective_configured_seed"] == "77"
        assert single_values["effective_geometry_template"] == "simple_box"
        for field, key in (
            ("geometry_template", "template"),
            ("geometry_config", "config"),
            ("geometry_default_world_material", "default_world_material"),
        ):
            assert single_values[f"effective_{field}_origin_kind"] == "main_ini"
            assert single_values[f"effective_{field}_origin_section"] == "geometry"
            assert single_values[f"effective_{field}_origin_key"] == key
            assert int(single_values[f"effective_{field}_origin_line"]) > 0
        assert single_values["effective_geometry_default_world_material"] == "G4_AIR"
        assert single_values["effective_source_particle"] == "proton"
        assert single_values["effective_source_particle_origin_kind"] == "main_ini"
        assert single_values["effective_source_particle_origin_section"] == "source"
        assert single_values["effective_source_particle_origin_key"] == "particle"
        assert int(single_values["effective_source_particle_origin_line"]) > 0
        assert float(single_values["effective_source_energy_MeV"]) == 10.0
        assert single_values["effective_source_energy_origin_kind"] == "main_ini"
        assert single_values["effective_source_energy_origin_section"] == "source"
        assert single_values["effective_source_energy_origin_key"] == "energy"
        assert int(single_values["effective_source_energy_origin_line"]) > 0
        assert single_values["effective_physics_reference"] == "FTFP_BERT_EMZ"
        assert single_values["effective_physics_reference_origin_kind"] == "main_ini"
        assert single_values["effective_physics_reference_origin_section"] == "physics"
        assert single_values["effective_physics_reference_origin_key"] == "reference"
        assert int(single_values["effective_physics_reference_origin_line"]) > 0
        assert single_values["effective_materials_source_status"] == "single_file"
        assert single_values["effective_materials_loaded_file_count"] == "1"
        assert normalize(single_values["effective_materials_file"]) == normalize(
            str(temp / "config" / "materials" / "material.ini")
        )
        assert any(Path(file).name == "event_edep_t0.csv" for file in single_files)
        geometry_origin_output = temp / "geometry-origin-output"
        run(executable, ["--config", "config/main.ini", "--macro", str(geometry_origin_macro),
                         "--output", str(geometry_origin_output)])
        geometry_origin_values, _ = read_summary(geometry_origin_output)
        assert geometry_origin_values["status"] == "completed"
        assert geometry_origin_values["actual_completed_event_count"] == "1"
        assert geometry_origin_values["effective_geometry_default_world_material"] == "G4_Galactic"
        for field, command, line in (
            ("geometry_template", "/aihl/geometry/settemplate", 1),
            ("geometry_config", "/aihl/geometry/loadconfig", 2),
            ("geometry_default_world_material", "/aihl/geometry/setdefaultworldmaterial", 3),
        ):
            assert geometry_origin_values[f"effective_{field}_origin_kind"] == "macro"
            assert geometry_origin_values[f"effective_{field}_origin_key"] == command
            assert geometry_origin_values[f"effective_{field}_origin_line"] == str(line)
            assert normalize(geometry_origin_values[f"effective_{field}_origin_file"]) == normalize(str(geometry_origin_macro))

        # Clearing the live geometry invalidates the earlier config-file provenance.
        geometry_clear_output = temp / "geometry-clear-output"
        run(executable, ["--config", "config/main.ini", "--macro", str(geometry_clear_macro),
                         "--output", str(geometry_clear_output)])
        geometry_clear_values, _ = read_summary(geometry_clear_output)
        assert geometry_clear_values["effective_geometry_config"] == ""
        assert geometry_clear_values["effective_geometry_config_origin_kind"] == "macro"
        assert geometry_clear_values["effective_geometry_config_origin_key"] == "/aihl/geometry/clear"
        assert geometry_clear_values["effective_geometry_config_origin_line"] == "1"

        # A post-initialization Manager mutation previously returned success
        # and let beamOn run with an already-constructed Geant4 world.
        late_geometry_output = temp / "geometry-after-init-output"
        late_geometry_log = run(
            executable, ["--config", "config/main.ini", "--macro", str(late_geometry_macro),
                         "--output", str(late_geometry_output)], expected=1,
        )
        late_geometry_values, _ = read_summary(late_geometry_output)
        assert "GEOMETRY_MUTATION_CONTINUED" not in late_geometry_log
        assert "G4UImanager status=200" in late_geometry_log, late_geometry_log[-4000:]
        assert late_geometry_values["status"] == "failed", late_geometry_values
        assert late_geometry_values["macro_execution_status"] == "failed", late_geometry_values
        assert late_geometry_values["macro_failure_command"] == "/AIHL/geometry/setTemplate hierarchical"
        assert late_geometry_values["run_count"] == "0", late_geometry_values
        assert late_geometry_values["effective_geometry_template"] != "hierarchical", late_geometry_values
        assert late_geometry_values["effective_geometry_template_origin_kind"] == "main_ini"
        # The kernel previously rejected a post-init thread-count change while
        # the manager and summary falsely claimed that the macro applied it.
        early_threads_output = temp / "threads-before-init-output"
        run(executable, ["--config", "config/main.ini", "--macro", str(early_threads_macro),
                         "--output", str(early_threads_output)])
        early_threads_values, _ = read_summary(early_threads_output)
        assert early_threads_values["status"] == "completed", early_threads_values
        assert early_threads_values["actual_threads"] == "2", early_threads_values
        assert early_threads_values["effective_threads_origin_kind"] == "macro", early_threads_values

        late_threads_output = temp / "threads-after-init-output"
        late_threads_log = run(
            executable, ["--config", "config/main.ini", "--macro", str(late_threads_macro),
                         "--output", str(late_threads_output)], expected=1,
        )
        late_threads_values, _ = read_summary(late_threads_output)
        assert "THREAD_MUTATION_CONTINUED" not in late_threads_log
        assert "G4UImanager status=200" in late_threads_log, late_threads_log[-4000:]
        assert late_threads_values["status"] == "failed", late_threads_values
        assert late_threads_values["macro_failure_command"] == "/AIHL/app/setNumThreads 3"
        assert late_threads_values["run_count"] == "0", late_threads_values
        assert late_threads_values["effective_threads_origin_kind"] == "main_ini", late_threads_values
        assert late_threads_values["num_threads"] == "1", late_threads_values
        preset_only_output = temp / "source-preset-only-output"
        run(executable, ["--config", str(source_preset_only_config), "--macro", str(single_macro),
                         "--output", str(preset_only_output)])
        preset_only_values, _ = read_summary(preset_only_output)
        assert preset_only_values["status"] == "completed"
        assert preset_only_values["effective_source_particle"] == "neutron"
        assert preset_only_values["effective_source_particle_origin_kind"] == "main_ini"
        assert preset_only_values["effective_source_particle_origin_key"] == "preset"
        assert int(preset_only_values["effective_source_particle_origin_line"]) > 0
        assert float(preset_only_values["effective_source_energy_MeV"]) == 10.0
        assert preset_only_values["effective_source_energy_origin_key"] == "energy"
        source_energy_preset_config = temp / "source-energy-preset.ini"
        source_energy_preset_config.write_text(
            source_preset_only_config.read_text(encoding="utf-8").replace("energy = 10 MeV\n", ""),
            encoding="utf-8",
        )
        energy_preset_output = temp / "source-energy-preset-output"
        run(executable, ["--config", str(source_energy_preset_config), "--macro", str(single_macro),
                         "--output", str(energy_preset_output)])
        energy_preset_values, _ = read_summary(energy_preset_output)
        assert float(energy_preset_values["effective_source_energy_MeV"]) == 1.0
        assert energy_preset_values["effective_source_energy_origin_key"] == "preset"
        energy_override_output = temp / "source-energy-override-output"
        run(executable, ["--config", str(source_energy_override_config), "--macro", str(single_macro),
                         "--output", str(energy_override_output)])
        energy_override_values, _ = read_summary(energy_override_output)
        assert float(energy_override_values["effective_source_energy_MeV"]) == 5.0
        assert energy_override_values["effective_source_energy_origin_key"] == "energy"
        for source_macro, expected_particle, expected_command, expected_line, run_count in (
            (source_preset_macro, "gamma", "/aihl/source/preset", 1, "1"),
            (source_particle_macro, "proton", "/aihl/source/particle", 2, "1"),
            (source_reset_macro, "", "/aihl/source/reset", 1, "0"),
        ):
            output = temp / f"{source_macro.stem}-output"
            run(executable, ["--config", "config/main.ini", "--macro", str(source_macro),
                             "--output", str(output)])
            values, _ = read_summary(output)
            assert values["effective_source_particle"] == expected_particle
            assert values["run_count"] == run_count
            assert values["effective_source_particle_origin_kind"] == "macro"
            assert values["effective_source_particle_origin_key"] == expected_command
            assert values["effective_source_particle_origin_line"] == str(expected_line)
            assert normalize(values["effective_source_particle_origin_file"]) == normalize(str(source_macro))
            expected_energy = 0.0 if source_macro == source_reset_macro else 1.0
            assert float(values["effective_source_energy_MeV"]) == expected_energy
            assert values["effective_source_energy_origin_kind"] == "macro"
            assert values["effective_source_energy_origin_key"] == (
                "/aihl/source/reset" if source_macro == source_reset_macro else "/aihl/source/preset"
            )
            assert values["effective_source_energy_origin_line"] == "1"
            assert normalize(values["effective_source_energy_origin_file"]) == normalize(str(source_macro))
        energy_macro_output = temp / "source-energy-macro-output"
        run(executable, ["--config", "config/main.ini", "--macro", str(source_energy_macro),
                         "--output", str(energy_macro_output)])
        energy_macro_values, _ = read_summary(energy_macro_output)
        assert energy_macro_values["status"] == "completed"
        assert energy_macro_values["actual_completed_event_count"] == "1"
        assert float(energy_macro_values["effective_source_energy_MeV"]) == 7.0
        assert energy_macro_values["effective_source_energy_origin_kind"] == "macro"
        assert energy_macro_values["effective_source_energy_origin_key"] == "/aihl/source/energy"
        assert energy_macro_values["effective_source_energy_origin_line"] == "2"
        assert normalize(energy_macro_values["effective_source_energy_origin_file"]) == normalize(str(source_energy_macro))
        assert energy_macro_values["effective_source_particle_origin_key"] == "/aihl/source/preset"
        physics_em_config_output = temp / "physics-em-config-output"
        run(executable, ["--config", str(physics_em_config), "--macro", str(single_macro),
                         "--output", str(physics_em_config_output)])
        physics_em_config_values, _ = read_summary(physics_em_config_output)
        assert physics_em_config_values["status"] == "completed"
        assert physics_em_config_values["effective_physics_reference"].startswith("FTFP_BERT")
        assert physics_em_config_values["effective_physics_reference_origin_kind"] == "main_ini"
        assert physics_em_config_values["effective_physics_reference_origin_key"] == "em"
        for macro, reference, command, run_count in (
            (physics_reference_macro, "QGSP_BERT", "/aihl/physics/setreferencelist", "1"),
            (physics_base_macro, "QGSP_BERT", "/aihl/physics/setbasereferencelist", "1"),
            (physics_em_macro, "FTFP_BERT", "/aihl/physics/setem", "1"),
            (physics_clear_macro, "", "/aihl/physics/clearreferencelist", "0"),
        ):
            physics_output = temp / f"{macro.stem}-output"
            run(executable, ["--config", "config/main.ini", "--macro", str(macro),
                             "--output", str(physics_output)])
            values, _ = read_summary(physics_output)
            assert values["run_count"] == run_count
            if reference in ("", "QGSP_BERT"):
                assert values["effective_physics_reference"] == reference
            else:
                assert values["effective_physics_reference"].startswith(reference)
            assert values["effective_physics_reference_origin_kind"] == "macro"
            assert values["effective_physics_reference_origin_key"] == command
            assert values["effective_physics_reference_origin_line"] == "1"
            assert normalize(values["effective_physics_reference_origin_file"]) == normalize(str(macro))
        single_schemas = read_generated_file_schemas(single_output)
        assert set(single_schemas) == set(single_files)
        assert single_schemas[str((single_output / "event_edep_t0.csv").resolve())] == "event_edep_csv_v3"
        second_material_output = temp / "second-material-output"
        run(executable, ["--config", "config/main.ini", "--macro", str(second_material_macro),
                         "--output", str(second_material_output)])
        second_material_values, _ = read_summary(second_material_output)
        assert second_material_values["effective_materials_source_status"] == "multiple_files"
        assert second_material_values["effective_materials_loaded_file_count"] == "2"
        assert second_material_values["effective_materials_file"] == "unknown"
        for index in range(2):
            assert normalize(second_material_values[f"effective_materials_loaded_file_{index}"]) == normalize(
                str(temp / "config" / "materials" / "material.ini")
            )
        manual_material_output = temp / "manual-material-output"
        run(executable, ["--config", "config/main.ini", "--macro", str(manual_material_macro),
                         "--output", str(manual_material_output)])
        manual_material_values, _ = read_summary(manual_material_output)
        assert manual_material_values["effective_materials_source_status"] == "non_file_mutation"
        assert manual_material_values["effective_materials_loaded_file_count"] == "1"
        assert manual_material_values["effective_materials_file"] == "unknown"
        late_material_output = temp / "late-material-output"
        late_material_log = run(
            executable,
            ["--config", "config/main.ini", "--macro", str(late_material_macro),
             "--output", str(late_material_output)],
            expected=1,
        )
        late_material_values, _ = read_summary(late_material_output)
        assert "Material macro command after kernel initialization" in late_material_log
        assert late_material_values["status"] == "failed"
        assert late_material_values["macro_execution_status"] == "failed"
        assert late_material_values["macro_failure_line"] == "2"
        assert late_material_values["macro_failure_code_available"] == "false"
        assert late_material_values["effective_materials_loaded_file_count"] == "1"
        missing_initialize_output = temp / "missing-initialize-output"
        missing_initialize_log = run(
            executable,
            ["--config", "config/main.ini", "--macro", str(missing_initialize_macro),
             "--output", str(missing_initialize_output)],
            expected=1,
        )
        missing_initialize_values, _ = read_summary(missing_initialize_output)
        assert "add /run/initialize before /run/beamOn" in missing_initialize_log
        assert "SHOULD_NOT_RUN_AFTER_BEAMON" not in missing_initialize_log
        assert missing_initialize_values["status"] == "failed"
        assert missing_initialize_values["macro_failure_command"] == "/run/beamOn 1"
        assert missing_initialize_values["macro_failure_line"] == "1"
        assert missing_initialize_values["macro_failure_code_available"] == "false"
        assert missing_initialize_values["run_count"] == "0"
        assert missing_initialize_values["actual_completed_event_count"] == "0"
        assert missing_initialize_values["effective_materials_loaded_file_count"] == "1"
        invalid_material_output = temp / "invalid-material-output"
        invalid_material_log = run(
            executable,
            ["--config", "config/main.ini", "--macro", str(invalid_material_macro),
             "--output", str(invalid_material_output)],
            expected=1,
        )
        invalid_material_values, _ = read_summary(invalid_material_output)
        assert "Material command failed" in invalid_material_log
        assert invalid_material_values["status"] == "failed"
        assert invalid_material_values["macro_execution_status"] == "failed"
        assert invalid_material_values["macro_failure_line"] == "1"
        assert invalid_material_values["macro_failure_code_available"] == "false"
        assert invalid_material_values["run_count"] == "0"
        with (single_output / "event_edep_t0.csv").open(newline="", encoding="utf-8") as stream:
            assert next(csv.reader(stream)) == ["runID", "eventID", "raw_edep_MeV", "weighted_edep_MeV"]

        unicode_output = temp / "中文输出"
        unicode_config = temp / "中文主配置.ini"
        unicode_macro = temp / "中文运行.mac"
        unicode_config.write_text(main_text, encoding="utf-8")
        unicode_macro.write_text(single_macro.read_text(encoding="utf-8"), encoding="utf-8")
        run(executable, ["--config", str(unicode_config), "--macro", str(unicode_macro), "--output", str(unicode_output)])
        unicode_values, _ = read_summary(unicode_output)
        assert unicode_values["actual_completed_event_count"] == "3"
        assert unicode_values["main_config"] == str(unicode_config)
        assert unicode_values["macro_file"] == str(unicode_macro)
        assert unicode_values["actual_output_dir"] == str(unicode_output)
        assert read_generated_file_schemas(unicode_output)[
            str((unicode_output / "event_edep_t0.csv").resolve())
        ] == "event_edep_csv_v3"

        hit_output = temp / "hit-output"
        run(executable, ["--macro", str(hit_macro), "--output", str(hit_output), "--threads", "1"])
        hit_values, _ = read_summary(hit_output)
        assert hit_values["actual_completed_event_count"] == "100"
        hit_schemas = read_generated_file_schemas(hit_output)
        hit_file = hit_output / "hits_t0.csv"
        assert hit_schemas[str(hit_file.resolve())] == "hits_csv_v3", hit_schemas
        with hit_file.open(newline="", encoding="utf-8") as stream:
            hit_reader = csv.DictReader(stream)
            assert hit_reader.fieldnames == [
                "runID", "eventID", "trackID", "parentID", "particle", "edep_MeV", "ndep_MeV",
                "stepLength_mm", "x0_mm", "y0_mm", "z0_mm", "x1_mm", "y1_mm", "z1_mm",
                "px", "py", "pz", "kineticEnergy_MeV", "process", "volume", "weight",
            ]
            assert next(hit_reader, None) is not None

        # Compare source Manager provenance with the primary particles actually
        # transported by Geant4. The source changes between two beamOn calls;
        # the first sensitive pre-step occurs at the injection point in silicon.
        source_sampling_output = temp / "source-sampling-output"
        run(executable, ["--macro", str(source_sampling_macro),
                         "--output", str(source_sampling_output), "--threads", "1"])
        sampled_values, _ = read_summary(source_sampling_output)
        assert sampled_values["status"] == "completed", sampled_values
        assert sampled_values["run_count"] == "2", sampled_values
        assert sampled_values["actual_completed_event_count"] == "6", sampled_values
        assert sampled_values["effective_source_particle"] == "proton", sampled_values
        assert float(sampled_values["effective_source_energy_MeV"]) == 3.0, sampled_values
        assert sampled_values["effective_source_particle_origin_key"] == "/aihl/source/particle", sampled_values
        assert sampled_values["effective_source_energy_origin_key"] == "/aihl/source/energy", sampled_values
        for run_id, particle, energy in ((0, "e-", 1.0), (1, "proton", 3.0)):
            suffix = "_t0" if run_id == 0 else f"_t0_r{run_id}"
            with (source_sampling_output / f"hits{suffix}.csv").open(newline="", encoding="utf-8") as stream:
                primary_first_steps = {}
                for hit in csv.DictReader(stream):
                    if hit["trackID"] == "1" and hit["parentID"] == "0":
                        primary_first_steps.setdefault(int(hit["eventID"]), hit)
            assert set(primary_first_steps) == {0, 1, 2}, (run_id, primary_first_steps)
            for event_id, hit in primary_first_steps.items():
                assert int(hit["runID"]) == run_id, (event_id, hit)
                assert hit["particle"] == particle, (event_id, hit)
                assert abs(float(hit["kineticEnergy_MeV"]) - energy) < 1e-9, (event_id, hit)
                assert abs(float(hit["z0_mm"]) + 9.0) < 1e-9, (event_id, hit)

        # The single-thread check above does not show that *both* MT workers
        # observe a source change between runs. Verify actual primary steps in
        # each worker output, not just the final SourceManager summary.
        source_sampling_mt_macro = temp / "source-sampling-mt.mac"
        source_sampling_mt_macro.write_text(
            source_sampling_macro.read_text(encoding="utf-8").replace(
                "/run/beamOn 3", "/run/beamOn 8"
            ),
            encoding="utf-8",
        )
        source_sampling_mt_output = temp / "source-sampling-mt-output"
        run(executable, ["--macro", str(source_sampling_mt_macro),
                         "--output", str(source_sampling_mt_output), "--threads", "2"])
        mt_values, _ = read_summary(source_sampling_mt_output)
        assert mt_values["status"] == "completed", mt_values
        assert mt_values["run_count"] == "2", mt_values
        assert mt_values["actual_completed_event_count"] == "16", mt_values
        for run_id, particle, energy in ((0, "e-", 1.0), (1, "proton", 3.0)):
            suffix = "" if run_id == 0 else f"_r{run_id}"
            worker_files = [
                source_sampling_mt_output / f"hits_t{thread}{suffix}.csv"
                for thread in (0, 1)
            ]
            assert all(file.is_file() for file in worker_files), worker_files
            primary_first_steps = {}
            for file in worker_files:
                with file.open(newline="", encoding="utf-8") as stream:
                    for hit in csv.DictReader(stream):
                        if hit["trackID"] == "1" and hit["parentID"] == "0":
                            event_id = int(hit["eventID"])
                            primary_first_steps.setdefault(event_id, hit)
            assert set(primary_first_steps) == set(range(8)), (run_id, primary_first_steps)
            for event_id, hit in primary_first_steps.items():
                assert int(hit["runID"]) == run_id, (event_id, hit)
                assert hit["particle"] == particle, (event_id, hit)
                assert abs(float(hit["kineticEnergy_MeV"]) - energy) < 1e-9, (event_id, hit)
                assert abs(float(hit["z0_mm"]) + 9.0) < 1e-9, (event_id, hit)

        # After a native GPS energy change, a particle-only AIHL command must
        # not silently replay the cached mono energy. Verify all three runs
        # using transported primary first steps from both Geant4 MT workers.
        interleave_output = temp / "source-native-interleave-output"
        run(executable, ["--macro", str(source_native_interleave_macro),
                         "--output", str(interleave_output), "--threads", "2"])
        interleave_values, _ = read_summary(interleave_output)
        assert interleave_values["status"] == "completed", interleave_values
        assert interleave_values["run_count"] == "3", interleave_values
        assert interleave_values["actual_completed_event_count"] == "24", interleave_values
        for run_id, particle, energy in ((0, "e-", 1.0), (1, "e-", 2.0), (2, "proton", 2.0)):
            suffix = "" if run_id == 0 else f"_r{run_id}"
            workers = [interleave_output / f"hits_t{thread}{suffix}.csv" for thread in (0, 1)]
            assert all(path.is_file() for path in workers), workers
            primary_steps = {}
            for path in workers:
                with path.open(newline="", encoding="utf-8") as stream:
                    for hit in csv.DictReader(stream):
                        if hit["trackID"] == "1" and hit["parentID"] == "0":
                            primary_steps.setdefault(int(hit["eventID"]), hit)
            assert set(primary_steps) == set(range(8)), (run_id, primary_steps)
            for event_id, hit in primary_steps.items():
                assert int(hit["runID"]) == run_id, (event_id, hit)
                assert hit["particle"] == particle, (event_id, hit)
                assert abs(float(hit["kineticEnergy_MeV"]) - energy) < 1e-9, (event_id, hit)

        with (single_output / "event_edep_t0.csv").open(newline="", encoding="utf-8") as stream:
            assert sum(1 for _ in csv.reader(stream)) - 1 == 3
        run(executable, ["--config", "config/main.ini", "--macro", str(single_macro), "--output", str(single_output), "--seed", "77"])
        _, repeated_files = read_summary(single_output)
        assert any(Path(file).name == "event_edep_t0.csv" for file in repeated_files)

        # These command names are present in the installed Geant4 examples.
        run(executable, ["--config", "config/main.ini", "--macro", str(random_seed_macro), "--output", str(temp / "random-seed-output")])
        random_seed_values, _ = read_summary(temp / "random-seed-output")
        assert random_seed_values["macro_execution_status"] == "completed"
        assert random_seed_values["macro_seed_modified"] == "true"
        run(executable, ["--config", "config/main.ini", "--macro", str(random_nonseed_macro), "--output", str(temp / "random-nonseed-output")])
        random_nonseed_values, _ = read_summary(temp / "random-nonseed-output")
        assert random_nonseed_values["macro_seed_modified"] == "false"

        # Multiple beamOn calls retain every run and aggregate all events.
        run(executable, ["--config", "config/main.ini", "--macro", str(multi_macro), "--output", str(multi_output)])
        multi_values, multi_files = read_summary(multi_output)
        assert multi_values["run_count"] == "2"
        assert multi_values["planned_event_count"] == "5"
        assert multi_values["actual_completed_event_count"] == "5"
        assert multi_values["run_0_id"] == "0"
        assert multi_values["run_0_planned_events"] == "2"
        assert multi_values["run_0_completed_events"] == "2"
        assert multi_values["run_1_id"] == "1"
        assert multi_values["run_1_planned_events"] == "3"
        assert multi_values["run_1_completed_events"] == "3"
        for run_id, expected_events in ((0, 2), (1, 3)):
            suffix = "_t0" if run_id == 0 else f"_t0_r{run_id}"
            event_file = multi_output / f"event_edep{suffix}.csv"
            assert any(Path(file).name == event_file.name for file in multi_files)
            with event_file.open(newline="", encoding="utf-8") as stream:
                event_rows = list(csv.DictReader(stream))
            assert len(event_rows) == expected_events, event_rows
            assert [row["runID"] for row in event_rows] == [str(run_id)] * expected_events
            assert [row["eventID"] for row in event_rows] == [str(index) for index in range(expected_events)]
            with (multi_output / f"hist_edep_raw{suffix}.csv").open(newline="", encoding="utf-8") as stream:
                histogram_rows = list(csv.DictReader(stream))
            assert sum(float(row["count"]) for row in histogram_rows) == expected_events
        multi_schemas = read_generated_file_schemas(multi_output)
        assert set(multi_schemas) == set(multi_files)
        assert multi_schemas[str((multi_output / "event_edep_t0_r1.csv").resolve())] == "event_edep_csv_v3"
        assert multi_schemas[str((multi_output / "hist_edep_raw_t0_r1.csv").resolve())] == "histogram1d_csv_v3"
        with (multi_output / "hist_edep_raw_t0_r1.csv").open(newline="", encoding="utf-8") as stream:
            assert next(csv.reader(stream)) == ["bin", "low_edge_MeV", "high_edge_MeV", "center_MeV", "count"]

        # Worker contexts may be recreated between runs; filenames still retain
        # both run IDs and no thread file may replace the previous run's data.
        run(executable, ["--config", "config/main.ini", "--macro", str(multi_macro), "--output", str(multi_mt_output), "--threads", "2"])
        mt_values, mt_files = read_summary(multi_mt_output)
        assert mt_values["run_count"] == "2"
        assert mt_values["actual_completed_event_count"] == "5"
        mt_event_files = sorted(multi_mt_output.glob("event_edep_t*.csv"))
        assert len(mt_event_files) >= 2, mt_event_files
        mt_counts = {0: 0, 1: 0}
        for event_file in mt_event_files:
            with event_file.open(newline="", encoding="utf-8") as stream:
                rows = list(csv.DictReader(stream))
            expected_run = 1 if "_r1.csv" in event_file.name else 0
            assert all(int(row["runID"]) == expected_run for row in rows), event_file
            mt_counts[expected_run] += len(rows)
            assert any(Path(file).name == event_file.name for file in mt_files)
        assert mt_counts == {0: 2, 1: 3}, mt_counts
        histogram_counts = {0: 0.0, 1: 0.0}
        for histogram_file in multi_mt_output.glob("hist_edep_raw_t*.csv"):
            with histogram_file.open(newline="", encoding="utf-8") as stream:
                rows = list(csv.DictReader(stream))
            run_id = 1 if "_r1.csv" in histogram_file.name else 0
            histogram_counts[run_id] += sum(float(row["count"]) for row in rows)
        assert histogram_counts == {0: 2.0, 1: 3.0}, histogram_counts

        # A failure in BeginOfRunAction on the second run must not escape a
        # Geant4 worker or overwrite the first run's completed output.
        # SetRunId can itself throw during the previous run's file close;
        # scoring initialization can also throw before any second-run event.
        for fault, expected_stage in (
            ("begin_set_run_id_t0", "run_begin_set_run_id"),
            ("begin_scoring_t0", "scoring_begin_run"),
        ):
            target = temp / f"{fault}-output"
            environment = os.environ.copy()
            environment["G4USIM_TEST_OUTPUT_FAULT"] = fault
            result = subprocess.run(
                [str(executable), "--config", "config/main.ini", "--macro", str(multi_macro),
                 "--output", str(target), "--threads", "2"],
                cwd=TEST_CWD, capture_output=True, text=True, timeout=120, env=environment,
            )
            log = result.stdout + result.stderr
            assert result.returncode != 0, log[-2500:]
            values, generated = read_summary(target)
            assert values["status"] == "failed", values
            assert values["program_exit_code"] != "0", values
            assert values["output_failure_status"] == "failed", values
            assert values["output_failure_stage"] == expected_stage, values
            assert values["output_failure_run_id"] == "1", values
            assert values["run_0_id"] == "0", values
            assert values["run_0_planned_events"] == "2", values
            assert values["run_0_completed_events"] == "2", values
            assert values["summary_write_status"] == "completed", values
            assert values["macro_failure_command"] == "/run/beamOn 3", values
            assert "[OutputFailure]" in log, log[-2500:]
            previous_files = list(target.glob("event_edep_t*.csv"))
            assert previous_files, values
            with previous_files[0].open(newline="", encoding="utf-8") as stream:
                assert all(row["runID"] == "0" for row in csv.DictReader(stream))
            assert any("event_edep_t" in Path(file).name for file in generated), generated

        # A file written by a different process during beamOn must not be
        # mistaken for a worker output just because its mtime is recent.
        manifest_process = subprocess.Popen(
            [str(executable), "--config", str(manifest_config), "--macro", str(manifest_macro),
             "--output", str(manifest_output), "--threads", "2"],
            cwd=TEST_CWD, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True,
        )
        active_worker_file = manifest_output / "event_edep_t0.csv"
        deadline = time.monotonic() + 90
        while not active_worker_file.exists() and manifest_process.poll() is None and time.monotonic() < deadline:
            time.sleep(0.005)
        if not active_worker_file.exists() or manifest_process.poll() is not None:
            manifest_process.kill()
            _, stderr = manifest_process.communicate()
            raise AssertionError(f"Could not inject an in-run unrelated file: {stderr[-2000:]}")
        foreign_file = manifest_output / "unrelated_file.txt"
        foreign_file.write_text("not a simulation output\n", encoding="utf-8")
        try:
            _, stderr = manifest_process.communicate(timeout=120)
        except subprocess.TimeoutExpired as error:
            manifest_process.kill()
            _, stderr = manifest_process.communicate()
            raise AssertionError(f"Manifest registration run exceeded 120 seconds: {stderr[-2000:]}") from error
        assert manifest_process.returncode == 0, stderr[-2000:]
        manifest_values, manifest_files = read_summary(manifest_output)
        assert manifest_values["actual_completed_event_count"] == "5000", manifest_values
        assert str(foreign_file.resolve()) not in manifest_files, manifest_files
        for actual_output in manifest_output.glob("event_edep_t*.csv"):
            assert str(actual_output.resolve()) in manifest_files, actual_output

        # Inject faults inside real Geant4 worker callbacks (after beamOn has
        # started), not via the pre-run path/directory collision check.
        for fault, target, expected_stage, failed_file in (
            ("event_row_t0", event_fault_output, "event_edep_write", "event_edep_t0.csv"),
            ("summary_close_t0", finalize_fault_output, "scoring_write_all", "edep_volume_summary_t0.csv"),
        ):
            environment = os.environ.copy()
            environment["G4USIM_TEST_OUTPUT_FAULT"] = fault
            worker_failure = subprocess.run(
                [str(executable), "--config", str(manifest_config), "--macro", str(manifest_macro),
                 "--output", str(target), "--threads", "2"],
                cwd=TEST_CWD, capture_output=True, text=True, timeout=120, env=environment,
            )
            failure_log = worker_failure.stdout + worker_failure.stderr
            assert worker_failure.returncode != 0, failure_log[-2500:]
            fault_values, fault_files = read_summary(target)
            assert fault_values["status"] == "failed", fault_values
            assert fault_values["program_exit_code"] != "0", fault_values
            assert fault_values["output_failure_status"] == "failed", fault_values
            assert fault_values["output_failure_stage"] == expected_stage, fault_values
            assert fault_values["output_failure_thread_id"] == "0", fault_values
            assert fault_values["macro_failure_command"] == "/run/beamOn 5000", fault_values
            assert fault_values["macro_failure_code_available"] == "false", fault_values
            assert not any(Path(file).name == failed_file for file in fault_files), fault_files
            assert "Worker output failure" in failure_log, failure_log[-2500:]

        # A failure discovered by the main thread during final Flush/Close
        # must still produce a failed summary and a nonzero process result.
        for fault, expected_stage in (
            ("final_flush_master", "final_flush"),
            ("final_close_master", "final_close"),
        ):
            target = temp / f"{fault}-output"
            environment = os.environ.copy()
            environment["G4USIM_TEST_OUTPUT_FAULT"] = fault
            result = subprocess.run(
                [str(executable), "--config", "config/main.ini", "--macro", str(single_macro),
                 "--output", str(target), "--threads", "2"],
                cwd=TEST_CWD, capture_output=True, text=True, timeout=120, env=environment,
            )
            log = result.stdout + result.stderr
            assert result.returncode != 0, log[-2500:]
            values, _ = read_summary(target)
            assert values["status"] == "failed", values
            assert values["program_exit_code"] != "0", values
            assert values["output_failure_status"] == "failed", values
            assert values["output_failure_stage"] == expected_stage, values
            assert values["output_failure_thread_id"] == "0", values
            assert "Injected main-thread" in values["output_failure_message"], values
            assert values["run_count"] == "1", values
            assert values["actual_completed_event_count"] == "3", values
            assert values["summary_write_status"] == "completed", values
            assert "summary failure" not in log.lower(), log[-2500:]

        run(executable, ["--config", str(scoring_off_config), "--macro", str(single_macro), "--output", str(scoring_off_output)])
        scoring_off_values, scoring_off_files = read_summary(scoring_off_output)
        assert scoring_off_values["actual_completed_event_count"] == "3"
        assert scoring_off_values["scoring_enabled"] == "false"
        assert not list(scoring_off_output.glob("event_edep*.csv"))
        assert not list(scoring_off_output.glob("hits*.csv"))
        assert not list(scoring_off_output.glob("hist_*.csv"))
        assert all(not file.endswith(".csv") for file in scoring_off_files), scoring_off_files

        # A later command failure preserves the completed run and failure location.
        failure_text = run(executable, ["--config", "config/main.ini", "--macro", str(failed_macro), "--output", str(failed_output)], expected=1)
        failed_values, _ = read_summary(failed_output)
        assert failed_values["status"] == "failed"
        assert failed_values["macro_execution_status"] == "failed"
        assert failed_values["actual_completed_event_count"] == "2"
        assert failed_values["macro_failure_line"] == "3"
        assert failed_values["macro_failure_command"] == "/random/showEngineStatus"
        assert failed_values["macro_failure_code"] != "0"
        assert failed_values["macro_seed_modified"] == "false"
        assert failed_values["effective_config_macro_execution_status"] == "failed"
        assert normalize(failed_values["effective_output_dir"]) == normalize(str(failed_output))
        if "summary failure" in failure_text.lower():
            raise AssertionError("failed macro could not write its summary")

        preflight_output = temp / "preflight-output"
        preflight_text = run(
            executable,
            ["--config", "config/main.ini", "--macro", str(preflight_macro), "--output", str(preflight_output), "--seed", "77"],
            expected=1,
        )
        preflight_values, _ = read_summary(preflight_output)
        assert preflight_values["macro_execution_status"] == "preflight_failed"
        assert preflight_values["macro_failure_phase"] == "preflight"
        assert preflight_values["macro_failure_line"] == "1"
        assert preflight_values["macro_failure_command"] == "/AIHL/app/setSeed 88"
        assert preflight_values["macro_failure_code"] == "0"
        assert preflight_values["macro_failure_code_available"] == "false"
        assert preflight_values["effective_config_macro_execution_status"] == "preflight_failed"
        assert preflight_values["effective_seed_origin_kind"] == "cli"
        if "SHOULD_NOT_RUN" in preflight_text:
            raise AssertionError("preflight-failed macro executed")

        # Main INI switching after Configure() cannot be allowed to leave
        # already-configured managers inconsistent with the final snapshot.
        late_main_output = temp / "late-main-config-output"
        late_main_text = run(
            executable,
            ["--macro", str(late_main_config_macro), "--output", str(late_main_output)],
            expected=1,
        )
        late_main_values, _ = read_summary(late_main_output)
        assert late_main_values["macro_execution_status"] == "preflight_failed"
        assert late_main_values["macro_failure_line"] == "1"
        assert late_main_values["macro_failure_code_available"] == "false"
        assert late_main_values["macro_failure_command"].startswith("/AIHL/app/setMainConfig ")
        assert late_main_values["effective_macro_file_origin_kind"] == "cli"
        assert "--config" in late_main_text
        assert "SHOULD_NOT_RUN" not in late_main_text

        # A macro without beamOn completes with zero actual events.
        run(executable, ["--macro", str(no_run_macro), "--output", str(no_run_output)])
        no_run_values, _ = read_summary(no_run_output)
        assert no_run_values["status"] == "completed"
        assert no_run_values["run_count"] == "0"
        assert no_run_values["actual_completed_event_count"] == "0"

        # A legal macro output switch changes the final summary location.
        run(executable, ["--config", "config/main.ini", "--macro", str(changed_macro)])
        changed_values, _ = read_summary(changed_output)
        assert normalize(changed_values["actual_output_dir"]) == normalize(str(changed_output))
        assert normalize(changed_values["effective_output_dir"]) == normalize(str(changed_output))
        assert normalize(changed_values["planned_output_dir"]) != normalize(str(changed_output))
        assert changed_values["effective_config_macro_execution_status"] == "completed"
        assert changed_values["effective_output_dir_origin_kind"] == "macro"
        assert changed_values["effective_output_dir_origin_key"] == "/aihl/output/setdir"
        assert changed_values["effective_output_dir_origin_line"] == "1"
        assert normalize(changed_values["effective_output_dir_origin_file"]) == normalize(str(changed_macro))
        if (locked_output / "run_summary.txt").exists():
            raise AssertionError("summary remained in the pre-macro output directory")

        # Workers force _tN filenames. Previously the pre-init command accepted
        # false but affected only the master, silently ignoring user intent.
        for threads in (1, 2):
            suffix_output = temp / f"suffix-disabled-{threads}"
            suffix_macro = temp / f"suffix-disabled-{threads}.mac"
            suffix_macro.write_text(
                "/AIHL/output/setThreadSuffix false\n"
                "/control/echo UNSAFE_SUFFIX_COMMAND_CONTINUED\n"
                "/run/initialize\n/run/beamOn 4\n",
                encoding="utf-8",
            )
            suffix_log = run(
                executable,
                ["--config", "config/main.ini", "--macro", str(suffix_macro),
                 "--output", str(suffix_output), "--threads", str(threads)],
                expected=1,
            )
            suffix_values, suffix_generated = read_summary(suffix_output)
            assert "disabling worker _tN suffix is unsupported" in suffix_log
            assert "UNSAFE_SUFFIX_COMMAND_CONTINUED" not in suffix_log
            assert suffix_values["status"] == "failed", suffix_values
            assert suffix_values["macro_failure_command"] == "/AIHL/output/setThreadSuffix false"
            assert suffix_values["macro_failure_line"] == "1"
            assert suffix_values["macro_failure_code_available"] == "false"
            assert suffix_values["run_count"] == "0"
            assert all(Path(path).name == "run_summary.txt" for path in suffix_generated), suffix_generated

        suffix_true_output = temp / "suffix-enabled-two-workers"
        suffix_true_macro = temp / "suffix-enabled-two-workers.mac"
        suffix_true_macro.write_text(
            "/AIHL/output/setThreadSuffix true\n/run/initialize\n/run/beamOn 4\n",
            encoding="utf-8",
        )
        run(executable, ["--config", "config/main.ini", "--macro", str(suffix_true_macro),
                         "--output", str(suffix_true_output), "--threads", "2"])
        suffix_true_values, _ = read_summary(suffix_true_output)
        assert suffix_true_values["status"] == "completed", suffix_true_values
        assert suffix_true_values["run_0_completed_events"] == "4", suffix_true_values
        assert (suffix_true_output / "event_edep_t0.csv").is_file()
        assert (suffix_true_output / "event_edep_t1.csv").is_file()
        assert not (suffix_true_output / "event_edep.csv").exists()

        # Scoring settings are copied to MT workers during /run/initialize.
        # A post-initialize master-only change previously exited successfully
        # while both workers continued writing the supposedly disabled CSV.
        scoring_early_output = temp / "scoring-before-init"
        scoring_early_macro = temp / "scoring-before-init.mac"
        scoring_early_macro.write_text(
            "/AIHL/scoring/eventEdep false\n/run/initialize\n/run/beamOn 4\n",
            encoding="utf-8",
        )
        run(executable, ["--config", "config/main.ini", "--macro", str(scoring_early_macro),
                         "--output", str(scoring_early_output), "--threads", "2"])
        scoring_early_values, scoring_early_generated = read_summary(scoring_early_output)
        assert scoring_early_values["status"] == "completed", scoring_early_values
        assert scoring_early_values["run_0_completed_events"] == "4", scoring_early_values
        assert scoring_early_values["scoring_event_edep_enabled"] == "true", scoring_early_values
        assert scoring_early_values["effective_scoring_event_edep_enabled"] == "false", scoring_early_values
        assert not list(scoring_early_output.glob("event_edep*.csv"))
        assert not any("event_edep" in file for file in scoring_early_generated)

        for completed_run in (False, True):
            for label, rejected_command in (
                ("event", "/AIHL/scoring/eventEdep false"),
                ("histogram", "/AIHL/scoring/setEdepHistogram bins=10 min=0 eV max=2 MeV"),
                ("autocreate", "/AIHL/scoring/autoCreateScorers false"),
            ):
                tag = f"scoring-{label}-{'after-run' if completed_run else 'after-init'}"
                target = temp / tag
                macro = temp / f"{tag}.mac"
                lines = ["/run/initialize"]
                if completed_run:
                    lines.append("/run/beamOn 2")
                lines.extend((rejected_command, "/control/echo UNSAFE_SCORING_CONTINUED", "/run/beamOn 3"))
                macro.write_text("\n".join(lines) + "\n", encoding="utf-8")
                failure_log = run(
                    executable,
                    ["--config", "config/main.ini", "--macro", str(macro),
                     "--output", str(target), "--threads", "2"], expected=1,
                )
                values, generated = read_summary(target)
                assert "G4UImanager status=200" in failure_log, failure_log[-3000:]
                assert "UNSAFE_SCORING_CONTINUED" not in failure_log, failure_log[-3000:]
                assert values["status"] == "failed", values
                assert values["effective_scoring_event_edep_enabled"] == "true", values
                assert values["macro_failure_command"] == rejected_command, values
                assert values["macro_failure_line"] == ("3" if completed_run else "2"), values
                assert values["run_count"] == ("1" if completed_run else "0"), values
                if completed_run:
                    assert values["run_0_completed_events"] == "2", values
                    assert any("event_edep_t0.csv" in path for path in generated), generated
                    assert (target / "event_edep_t0.csv").is_file(), target
                assert not any("_r1.csv" in path for path in generated), generated

        # Real MT workers retain their initial output directory. Previously a
        # later master-only switch succeeded, sending the final summary to a
        # different directory while both runs' CSV files stayed in the first.
        for label, command in (
            ("output", "/AIHL/output/setDir"),
            ("app", "/AIHL/app/setOutputDir"),
            ("suffix", "/AIHL/output/setThreadSuffix"),
        ):
            for completed_run in (False, True):
                tag = f"late-{label}-{'after-run' if completed_run else 'after-init'}"
                original_dir = temp / f"{tag}-original"
                rejected_dir = temp / f"{tag}-rejected"
                rejected_command = (f"{command} false" if label == "suffix"
                                    else f"{command} {rejected_dir.as_posix()}")
                lines = [f"/AIHL/output/setDir {original_dir.as_posix()}", "/run/initialize"]
                if completed_run:
                    lines.append("/run/beamOn 2")
                lines.extend((rejected_command, "/control/echo UNSAFE_OUTPUT_CHANGE_CONTINUED", "/run/beamOn 3"))
                macro = temp / f"{tag}.mac"
                macro.write_text("\n".join(lines) + "\n", encoding="utf-8")
                failure_log = run(executable, ["--config", "config/main.ini", "--macro", str(macro)], expected=1)
                values, generated = read_summary(original_dir)
                assert values["status"] == "failed", values
                assert values["macro_failure_command"] == rejected_command, values
                assert values["macro_failure_line"] == str(4 if completed_run else 3), values
                assert values["run_count"] == ("1" if completed_run else "0"), values
                assert values["effective_output_dir_origin_line"] == "1", values
                assert normalize(values["effective_output_dir"]) == normalize(str(original_dir)), values
                assert not rejected_dir.exists(), rejected_dir
                assert "UNSAFE_OUTPUT_CHANGE_CONTINUED" not in failure_log, failure_log[-2500:]
                if completed_run:
                    assert values["run_0_completed_events"] == "2", values
                    assert any("event_edep_t0.csv" in filename for filename in generated), generated
                    assert (original_dir / "event_edep_t0.csv").is_file(), original_dir

        # A Messenger exception and a failure *inside* OutputManager's setter
        # must both stop the macro, without selecting the rejected path or
        # recording the attempted command as a successful EffectiveConfig origin.
        for fault_mode, error_message in (
            ("messenger_set_dir", "Injected /AIHL/output/setDir handler failure"),
            ("manager_set_dir", "Injected OutputManager::SetOutputDir failure"),
        ):
            existing_summary = output_command_fault_target / "run_summary.txt"
            if existing_summary.exists():
                existing_summary.unlink()
            output_command_environment = os.environ.copy()
            output_command_environment["G4USIM_TEST_OUTPUT_FAULT"] = fault_mode
            output_command_process = subprocess.run(
                [str(executable), "--config", str(output_command_fault_config),
                 "--macro", str(output_command_fault_macro)],
                cwd=TEST_CWD, text=True, capture_output=True, timeout=120,
                env=output_command_environment,
            )
            output_command_log = output_command_process.stdout + output_command_process.stderr
            assert output_command_process.returncode != 0, output_command_log[-3000:]
            assert error_message in output_command_log
            assert "SHOULD_NOT_CONTINUE_OUTPUT_ERROR" not in output_command_log
            output_command_values, _ = read_summary(output_command_fault_target)
            assert output_command_values["status"] == "failed", output_command_values
            assert output_command_values["macro_failure_command"].startswith("/AIHL/output/setDir ")
            assert output_command_values["macro_failure_line"] == "1"
            assert output_command_values["macro_failure_code_available"] == "false"
            assert output_command_values["run_count"] == "0"
            assert output_command_values["effective_output_dir_origin_kind"] == "main_ini"
            assert normalize(output_command_values["effective_output_dir"]) == normalize(
                str(output_command_fault_target)
            )
            assert not (output_command_rejected_target / "run_summary.txt").exists()

        # Explicit CLI output remains locked and the preflight rejects the conflict.
        run(
            executable,
            ["--config", "config/main.ini", "--macro", str(changed_macro), "--output", str(locked_output)],
            expected=1,
        )

        # An event CSV path occupied by a directory must not be reported as a successful run.
        csv_failure_output.mkdir()
        (csv_failure_output / "event_edep_t0.csv").mkdir()
        csv_failure_process = subprocess.run(
            [str(executable), "--config", "config/main.ini", "--macro", str(single_macro),
             "--output", str(csv_failure_output)],
            cwd=TEST_CWD, text=True, capture_output=True, timeout=120,
        )
        assert csv_failure_process.returncode != 0, csv_failure_process.stdout + csv_failure_process.stderr
        assert (csv_failure_output / "run_summary.txt").is_file(), (
            f"exit={csv_failure_process.returncode}; "
            f"stderr={csv_failure_process.stderr[-1500:]}; "
            f"stdout_tail={csv_failure_process.stdout[-500:]}"
        )
        csv_failure_values, _ = read_summary(csv_failure_output)
        assert csv_failure_values["status"] == "failed", csv_failure_values
        assert csv_failure_values["run_count"] == "0", csv_failure_values
        assert csv_failure_values["macro_failure_command"] == "/run/beamOn 3", csv_failure_values
        assert csv_failure_values["macro_failure_code_available"] == "false", csv_failure_values

        # The second run uses the _r1 filename; the first completed run remains recorded.
        second_run_csv_failure_output.mkdir()
        (second_run_csv_failure_output / "event_edep_t0_r1.csv").mkdir()
        second_run_failure = subprocess.run(
            [str(executable), "--config", "config/main.ini", "--macro", str(multi_macro),
             "--output", str(second_run_csv_failure_output)],
            cwd=TEST_CWD, text=True, capture_output=True, timeout=120,
        )
        assert second_run_failure.returncode != 0, second_run_failure.stdout + second_run_failure.stderr
        second_run_values, second_run_files = read_summary(second_run_csv_failure_output)
        assert second_run_values["status"] == "failed", second_run_values
        assert second_run_values["run_count"] == "1", second_run_values
        assert second_run_values["actual_completed_event_count"] == "2", second_run_values
        assert second_run_values["macro_failure_command"] == "/run/beamOn 3", second_run_values
        assert any(Path(file).name == "event_edep_t0.csv" for file in second_run_files)

        # Summary write failures are reported instead of being swallowed.
        write_failure_output.mkdir(parents=True, exist_ok=True)
        (write_failure_output / "run_summary.txt").mkdir()
        write_failure_text = run(
            executable,
            ["--macro", str(no_run_macro), "--output", str(write_failure_output)],
            expected=1,
        )
        if "summary failure" not in write_failure_text.lower():
            raise AssertionError(f"summary write failure was not reported:\n{write_failure_text}")

    print("M0-2 run summary regression tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
