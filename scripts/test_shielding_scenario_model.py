"""Regression for the shielding scenario model shared by the CLI and the GUI (2B-1).

The scenario used to be generated only by ``make_scenario.py``; the GUI (stage 2B)
imports the same model.  This test pins the file contract, the determinism, the
validation messages (which scripts match on) and the CLI/model parity, so a refactor
cannot quietly change the generated configuration or the errors.

Static layer: no Qt, no backend executable needed.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCENARIO = ROOT / "scenarios" / "shielding_coating"
sys.path.insert(0, str(SCENARIO))

import make_scenario  # noqa: E402  (import after sys.path setup)
import scenario_model  # noqa: E402

FILES_DEFAULT = {"materials.ini", "geometry.ini", "main.ini", "run.mac", "scenario.json", "spectrum_proton.csv"}
LEN_START = "bad length '"


def make_dir() -> Path:
    return Path(tempfile.mkdtemp(prefix="g4usim-scenario-"))


def read(path: Path) -> str:
    assert path.is_file(), f"missing generated file {path.name}"
    return path.read_text(encoding="utf-8")


def main() -> int:
    tmp = make_dir()
    try:
        # 1. Default spec: the same file set as the CLI, meta and INI contract.
        spec = scenario_model.ShieldingSpec(events=20)
        result = spec.generate(tmp / "default")
        assert set(result["files"]) == FILES_DEFAULT, set(result["files"])
        main_ini = read(result["files"]["main.ini"])
        assert "[run]\nthreads = 4\nseed = 12345\nmacro = run.mac" in main_ini
        assert "[output]\ndir = output\nformat = csv" in main_ini
        assert "[materials]\nfile = materials.ini" in main_ini
        assert "[geometry]\ntemplate = hierarchical\nconfig = geometry.ini" in main_ini
        assert "energy_type = histogram\nspectrum_file = spectrum_proton.csv" in main_ini
        assert "position_type = plane\nshape = square\nhalfx = 4 mm" in main_ini
        assert "[phase_space]\nvolume = BackPlane_PV\nparticles = all\nkill = false" in main_ini
        assert "dose = true\nfluence = true" in main_ini
        assert "displacement" not in main_ini
        assert "check_overlaps" not in main_ini
        meta = json.loads(read(result["files"]["scenario.json"]))
        assert meta["mode"] == "transmission" and meta["particle"] == "proton"
        assert meta["events"] == 20
        assert abs(meta["source_area_cm2"] - 0.64) < 1e-12
        assert meta["sampled_integral_flux_cm2_s"]["proton"] > 0
        assert meta["unsampled_flux_above_last_energy_cm2_s"]["proton"] > 0
        assert meta["layers"] == [
            {"material": "B4C", "thickness_mm": 0.3},
            {"material": "G4_W", "thickness_mm": 0.1},
            {"material": "G4_Al", "thickness_mm": 0.3},
        ]
        assert meta["pores"] == 0 and meta["displacement"] is False
        assert "coating_volumes" in meta
        geometry = read(result["files"]["geometry.ini"])
        assert "[volume.Device]" in geometry and "sensitive = true" in geometry
        assert "shape = orb" not in geometry

        # 2. Determinism: same seed, byte identical output (pores use the seed).
        first = scenario_model.ShieldingSpec(events=20, pores_layer=2, seed=7).generate(tmp / "pores_a")
        second = scenario_model.ShieldingSpec(events=20, pores_layer=2, seed=7).generate(tmp / "pores_b")
        for name in first["files"]:
            assert first["files"][name].read_bytes() == second["files"][name].read_bytes(), name
        pores_meta = first["meta"]
        assert pores_meta["pores"] > 0
        assert "check_overlaps = false" in read(first["files"]["main.ini"])
        pores_csv = read(first["files"]["pores.csv"])
        assert pores_csv.splitlines()[0] == "# pore centres in the layer frame"
        assert pores_csv.splitlines()[1] == "x_mm,y_mm,z_mm"
        rows = [line for line in pores_csv.splitlines()[2:] if line]
        assert len(rows) == pores_meta["pores"]
        assert len(rows[0].split(",")) == 3
        coords = [float(value) for value in rows[0].split(",")]
        assert all(abs(value) <= 5.0 for value in coords)   # 10 mm lateral size, centred

        # 3. A different seed changes the pore positions but not the geometry otherwise.
        third = scenario_model.ShieldingSpec(events=20, pores_layer=2, seed=8).generate(tmp / "pores_c")
        assert read(first["files"]["pores.csv"]) != read(third["files"]["pores.csv"])
        assert read(first["files"]["geometry.ini"]) == read(third["files"]["geometry.ini"])

        # 4. Mono-energetic source, NIEL tables, albedo mode, junction layers.
        spec = scenario_model.ShieldingSpec(events=5, energy_MeV=100.0, mode="albedo",
                                            junction_density=0.5, niel=("proton=niel.csv",))
        result = spec.generate(tmp / "mono")
        main_ini = read(result["files"]["main.ini"])
        assert "energy = 100.0 MeV" in main_ini
        assert "spectrum_file" not in main_ini
        assert "volume = FrontPlane_PV" in main_ini and "kill = true" in main_ini
        assert "displacement = true" in main_ini
        assert "displacement]\nproton = " in main_ini and "niel.csv" in main_ini
        assert "check_overlaps" not in main_ini
        materials = read(result["files"]["materials.ini"])
        assert "[material.Junction" not in materials  # junction copies use the _J suffix
        assert "_J]" in materials
        assert result["meta"]["displacement"] is True

        # 6. scenario.json records which NIEL table fed the DDD numbers, with its digest.
        niel_path = tmp / "si_niel.csv"
        niel_path.write_text("energy_MeV,niel_MeV_cm2_g" + chr(10) + "1,0.1" + chr(10), encoding="utf-8")
        spec = scenario_model.ShieldingSpec(events=5, niel=(f"proton={niel_path}",))
        meta = spec.generate(tmp / "niel")["meta"]
        assert meta["niel"] == [{"particle": "proton", "path": niel_path.resolve().as_posix(),
                                 "sha256": hashlib.sha256(niel_path.read_bytes()).hexdigest()}], meta["niel"]

        # 5. run_from: the generated paths are relative to the backend working directory.
        spec = scenario_model.ShieldingSpec(events=5)
        result = spec.generate(tmp / "nested" / "case", run_from=tmp)
        main_ini = read(result["files"]["main.ini"])
        assert "dir = nested/case/output" in main_ini
        assert "file = nested/case/materials.ini" in main_ini

        # 6. Validation messages are stable (scripts and users match on them).
        problems = scenario_model.ShieldingSpec().problems()
        assert problems == []
        assert scenario_model.ShieldingSpec(layers="B4C:0um").problems() == ["length must be > 0: '0um'"]
        assert scenario_model.ShieldingSpec(size="10").problems() == ["bad length '10' (use e.g. 300um, 0.1mm)"]
        assert "unknown layer material 'Unobtainium'" in scenario_model.ShieldingSpec(
            layers="Unobtainium:1mm").problems()[0]
        assert scenario_model.ShieldingSpec(junction_density=1.0).problems() == [
            "--junction-density must be in [0, 1)"]
        assert scenario_model.ShieldingSpec(particle="mixed", energy_MeV=1.0).problems() == [
            "--particle mixed needs the spectra (no --energy)"]
        assert scenario_model.ShieldingSpec(niel=("proton",)).problems() == [
            "--niel needs PARTICLE=TABLE.csv, got 'proton'"]
        assert scenario_model.ShieldingSpec(pores_layer=3).problems() == [
            "--pores-layer 3 is outside the 3 layer stack"]
        assert scenario_model.ShieldingSpec(events=0).problems() == ["--events must be > 0, got 0"]
        # A NIEL table that does not exist is not a parameter problem: the backend
        # reports a missing table when the run starts, so validation must pass here.
        assert scenario_model.ShieldingSpec(layers="B4C:1mm").with_niel("e-=missing.csv").validate()

        # 7. CLI parity: the wrapper writes exactly what the model renders.
        cli_dir = tmp / "cli"
        code = make_scenario.main(["--out", str(cli_dir), "--events", "20"])
        assert code == 0
        model_dir = tmp / "model"
        model = scenario_model.ShieldingSpec(events=20).generate(model_dir)
        for name in sorted(FILES_DEFAULT):
            assert (cli_dir / name).read_bytes() == model["files"][name].read_bytes(), name

        # 8. CLI errors keep the same text and the script keeps exiting non-zero.
        try:
            make_scenario.main(["--out", str(tmp / "bad"), "--layers", "G4_Al:0um"])
            raise AssertionError("the CLI must reject a zero thickness")
        except SystemExit as exc:
            assert str(exc) == "length must be > 0: '0um'"
        assert not (tmp / "bad").exists() or not (tmp / "bad" / "main.ini").exists()

        print("test_shielding_scenario_model: OK")
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
