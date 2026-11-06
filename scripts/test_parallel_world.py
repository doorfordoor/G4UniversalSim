"""Roadmap H3-2: parallel scoring world backend regression.

Runs the real Geant4 backend against isolated fixtures:

* default-off behaviour (no [parallel_world] -> legacy output, no parallel keys);
* one box volume and one regular grid, including dose/fluence normalisation;
* material aliases resolved through the material manager;
* Stage A rejection matrix (structure, keys, combinations);
* R-RUNTIME: mass layer insensitive, hits/event_edep enabled; the parallel
  routing must not touch hits or the per-event Edep accumulation;
* R-SAME: mass layer and parallel copy both sensitive in one run; parallel
  steps must not leak into the mass hits collection;
* Case M: two threads, two runs in one process.

Not covered here (H3-4): the pre-registered statistical batches and Case C.
Stage B invariants (actual mass/solid containment) are exercised by every
enabled run; producing an inconsistent kernel geometry through supported
inputs is not possible, so no synthetic fault injection is added.

Not part of H3-2: GUI, ROOT output, biasing or field combinations.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXE = Path(os.environ.get("G4USIM_EXE", ROOT / "build_vs2026/Release/G4UniversalSim.exe"))
DOSE_NAME = re.compile(r"dose_volume_summary_t(\d+)(?:_r(\d+))?\.csv$")
FLUENCE_NAME = re.compile(r"fluence_volume_summary_t(\d+)(?:_r(\d+))?\.csv$")
EVENT_NAME = re.compile(r"event_edep_t(\d+)(?:_r(\d+))?\.csv$")
HITS_NAME = re.compile(r"hits_t(\d+)(?:_r(\d+))?\.csv$")

MATERIALS = """[world]
material = G4_Galactic

[water]
material = G4_WATER
"""

GEOMETRY = """[world]
shape = box
size = 100, 100, 100
material = G4_Galactic

[volume.Slab]
parent = world
shape = box
size = 20, 20, 2
position = 0, 0, 0
material = G4_WATER
sensitive = false
"""

PARALLEL = """[world]
material = G4_Galactic

[volume.Slab]
parent = world
shape = box
size = 20, 20, 2
position = 0, 0, 0
material = G4_WATER
sensitive = true
"""

PARALLEL_ALIAS = PARALLEL.replace("material = G4_WATER", "material = water")

GEOMETRY_VACUUM = """[world]
shape = box
size = 100, 100, 100
material = G4_Galactic
"""

# Navigation-envelope regression (grid fix r3): 2e-7 mm thick 4x4 grid in a
# vacuum mass world. Before the envelope a track running exactly along the
# shared cell faces was never limited by the kernel and the grid produced no
# ghost row at all. The envelope must restore one real step (the full 2e-7 mm
# thickness) and attribute it to the real cell.
PARALLEL_THIN_GRID = """[world]
material = G4_Galactic

[grid.GhostThin]
parent = world
size = 20, 20, 0.0000002
position = 0, 0, 0
material = G4_Galactic
bins = 4, 4, 1
sensitive = true
"""

PHOTON_SOURCE = """[source]
particle = gamma
energy = 1 MeV
position_type = point
position = 0, 0, -20
direction = 0, 0, 1
"""

PARALLEL_GRID = """[world]
material = G4_Galactic

[grid.SlabGrid]
parent = world
size = 20, 20, 2
position = 0, 0, 0
material = G4_WATER
bins = 2, 2, 1
sensitive = true
"""

PROTON_SOURCE = """[source]
particle = proton
energy = 10 MeV
position_type = point
position = 0, 0, -20
direction = 0, 0, 1
"""

BASE_MAIN = """[run]
threads = {threads}
seed = {seed}

[output]
dir = output
{output_extra}

[materials]
file = materials.ini

[geometry]
template = hierarchical
config = geometry.ini

[physics]
reference = FTFP_BERT

[scoring]
enabled = true
dose = true
fluence = true
auto_create_default_scorers = true
{scoring_extra}

{source_section}
{parallel_section}
{main_extra}
"""


class Case:
    def __init__(self, root: Path, name: str, *, parallel: str | None = PARALLEL,
                 main_extra: str = "", scoring_extra: str = "", output_extra: str = "",
                 seed: int = 20261400, threads: int = 1, section: str | None = None,
                 geometry: str = GEOMETRY,
                 source_section: str = PROTON_SOURCE):
        self.path = root / name
        self.path.mkdir(parents=True, exist_ok=True)
        (self.path / "materials.ini").write_text(MATERIALS, encoding="utf-8")
        (self.path / "geometry.ini").write_text(geometry, encoding="utf-8")
        if parallel is not None:
            (self.path / "parallel.ini").write_text(parallel, encoding="utf-8")
        if section is None:
            section = ""
            if parallel is not None:
                section = ("[parallel_world]\n"
                           "enabled = true\n"
                           "name = ScoringWorld\n"
                           "geometry_config = parallel.ini\n")
        text = BASE_MAIN.format(threads=threads, seed=seed, output_extra=output_extra,
                                scoring_extra=scoring_extra, parallel_section=section,
                                source_section=source_section, main_extra=main_extra)
        (self.path / "main.ini").write_text(text, encoding="utf-8")

    def run(self, macro: str, *, threads: int = 1, expected: int = 0, tag: str = "run") -> Path:
        mac = self.path / f"{tag}.mac"
        mac.write_text(macro, encoding="utf-8")
        output = self.path / "output" / tag
        proc = subprocess.run([str(EXE), "--config", "main.ini", "--macro", mac.name,
                               "--output", str(output), "--threads", str(threads)],
                              cwd=self.path, capture_output=True, text=True, errors="replace",
                              timeout=900)
        (self.path / f"{tag}.log").write_text(proc.stdout + proc.stderr, encoding="utf-8")
        assert proc.returncode == expected, (
            f"{self.path.name}/{tag}: exit={proc.returncode}, expected={expected}\n"
            f"{(proc.stdout + proc.stderr)[-3000:]}")
        return output

    def run_expect_failure(self, text: str, *, macro: str | None = None,
                           dry_run: bool = True) -> None:
        if dry_run:
            command = [str(EXE), "--config", "main.ini", "--dry-run"]
            tag = "reject"
        else:
            mac = self.path / "reject.mac"
            mac.write_text(macro or "/run/initialize\n", encoding="utf-8")
            command = [str(EXE), "--config", "main.ini", "--macro", mac.name]
            tag = "stage_b"
        proc = subprocess.run(command, cwd=self.path, capture_output=True, text=True,
                              errors="replace", timeout=600)
        blob = proc.stdout + proc.stderr
        (self.path / f"{tag}.log").write_text(blob, encoding="utf-8")
        assert proc.returncode != 0, f"{self.path.name}: invalid configuration was accepted\n{blob[-2000:]}"
        assert text in blob, f"{self.path.name}: expected {text!r} in\n{blob[-3000:]}"


def rows(output: Path, pattern: re.Pattern[str]) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    for path in sorted(output.glob("*.csv")):
        if pattern.fullmatch(path.name):
            with path.open(newline="", encoding="utf-8") as stream:
                result.extend(csv.DictReader(stream))
    return result


def summary(output: Path) -> str:
    return (output / "run_summary.txt").read_text(encoding="utf-8")


def value(text: str, key: str) -> str:
    match = re.search(rf"^{re.escape(key)} = (.*)$", text, re.MULTILINE)
    assert match, f"missing summary key {key}\n{text[-3000:]}"
    return match.group(1).strip()



FIX_R1_MATERIALS = """[world]
material = G4_Galactic

[water]
material = G4_WATER

[copper]
material = G4_Cu
"""

FIX_R1_GRID_PLUS_CELL = """[world]
material = G4_Galactic

[grid.G]
parent = world
size = 20, 20, 2
position = 0, 0, 0
material = G4_WATER
bins = 1, 1, 1
sensitive = true

[volume.G_0_0_0]
parent = world
shape = box
size = 5, 5, 1
position = 0, 0, 5
material = G4_WATER
sensitive = true
"""

FIX_R1_OVERLAP = """[world]
material = G4_Galactic

[volume.Slab]
parent = world
shape = box
size = 20, 20, 2
position = 0, 0, 0
material = G4_WATER
sensitive = true

[volume.Overlap]
parent = world
shape = box
size = 20, 20, 2
position = 0, 0, 0
material = G4_WATER
sensitive = true
"""

FIX_R1_FACE_CONTACT = """[world]
material = G4_Galactic

[volume.Slab]
parent = world
shape = box
size = 20, 20, 2
position = 0, 0, 0
material = G4_WATER
sensitive = true

[volume.Neighbour]
parent = world
shape = box
size = 20, 20, 2
position = 0, 0, 2
material = G4_WATER
sensitive = true
"""

FIX_R1_TWO_GRIDS = """[world]
material = G4_Galactic

[grid.Big]
parent = world
size = 20, 20, 2
position = 0, 0, 0
material = G4_WATER
bins = 64, 64, 1
sensitive = true

[grid.Small]
parent = world
size = 2, 2, 1
position = 0, 0, 5
material = G4_WATER
bins = 1, 1, 1
sensitive = true
"""

FIX_R1_BAD_NAME = """[world]
material = G4_Galactic

[volume.-bad]
parent = world
shape = box
size = 5, 5, 1
material = G4_WATER
sensitive = true
"""

FIX_R1_HUGE = """[world]
material = G4_Galactic

[volume.Huge]
parent = world
shape = box
size = 1e308, 1e308, 1e308
material = G4_WATER
sensitive = true
"""

FIX_R1_PLATE_WITH_DAUGHTER = """[world]
shape = box
size = 100, 100, 100
material = G4_Galactic

[volume.WaterBox]
parent = world
shape = box
size = 40, 40, 2
position = 0, 0, 0
material = water
sensitive = false

[volume.CuBox]
parent = WaterBox
shape = box
size = 10, 10, 0.5
position = 0, 0, 0
material = copper
sensitive = false
"""

FIX_R1_PARALLEL_WATER_BOX = """[world]
material = G4_Galactic

[volume.WaterBox]
parent = world
shape = box
size = 40, 40, 2
position = 0, 0, 0
material = water
sensitive = true
"""

FIX_R1_TRANSLATED_GEOMETRY = """[world]
shape = box
size = 100, 100, 100
material = G4_Galactic

[volume.Plate]
parent = world
shape = box
size = 40, 40, 2
position = 0, 0, 10
material = water
sensitive = false

[volume.WaterBox]
parent = Plate
shape = box
size = 20, 20, 1
position = 0, 0, 0
material = water
sensitive = false
"""

FIX_R1_TRANSLATED_PARALLEL = """[world]
material = G4_Galactic

[volume.WaterBox]
parent = world
shape = box
size = 20, 20, 1
position = 0, 0, 10
material = water
sensitive = true
"""


def custom_case(root: Path, name: str, materials: str, geometry: str,
                parallel: str | None = None, *, scoring_extra: str = "",
                main_extra: str = "", output_extra: str = "",
                seed: int = 20261400, threads: int = 1) -> Case:
    """Build a case whose material/geometry/parallel files differ from the fixtures."""
    case = Case(root, name, parallel=None, section="")
    (case.path / "materials.ini").write_text(materials, encoding="utf-8")
    (case.path / "geometry.ini").write_text(geometry, encoding="utf-8")
    section = ""
    if parallel is not None:
        (case.path / "parallel.ini").write_text(parallel, encoding="utf-8")
        section = ("[parallel_world]\nenabled = true\nname = ScoringWorld\n"
                   "geometry_config = parallel.ini\n")
    (case.path / "main.ini").write_text(
        BASE_MAIN.format(threads=threads, seed=seed, output_extra=output_extra,
                         scoring_extra=scoring_extra, parallel_section=section,
                         source_section=PROTON_SOURCE, main_extra=main_extra), encoding="utf-8")
    return case


def expect_dry_ok(case: Case) -> None:
    proc = subprocess.run([str(EXE), "--config", "main.ini", "--dry-run"], cwd=case.path,
                          capture_output=True, text=True, errors="replace", timeout=600)
    (case.path / "dry_run.log").write_text(proc.stdout + proc.stderr, encoding="utf-8")
    assert proc.returncode == 0, (
        f"{case.path.name}: dry-run rejected a supported geometry\n"
        f"{(proc.stdout + proc.stderr)[-2500:]}")


def finalization(output: Path) -> dict:
    path = output / "effective_config_finalization.json"
    assert path.is_file(), path
    return json.loads(path.read_text(encoding="utf-8"))


def resolved_field(document: dict, suffix: str) -> object:
    for field in document.get("fields", []):
        if str(field.get("path", "")).endswith(suffix):
            return field.get("resolved")
    raise AssertionError(f"field {suffix!r} not found in finalization snapshot")


def run_validated_evidence(document: dict) -> dict:
    for entry in document.get("evidence", []):
        if entry.get("evidence_level") == "run_validated":
            return entry
    raise AssertionError("no run_validated receipt in the finalization snapshot")



# Exact bytes of the two legal negative inputs from the H3-2 fix-r1 independent
# review (out/collab/h3-independent-r2/material-negative-repro). The hashes are the
# ones recorded in out/collab/h3-independent-r2/supervisor-material-verified.json;
# a mismatch here means the reproduction input drifted, not that the product changed.
R2_INPUT_SHA256 = {
    'self_rotated_water_box': {
        'main.ini': 'c70337a2d9b3837e532eff88a1cad8c2b571bc7b128e490ad313b1ae0d0e8e68',
        'geometry.ini': '4ec7e1372ffeff26018341c59a6ed07d36f438899c72a816553113ab9806edd9',
        'parallel.ini': '2d5e63f273362fbdd08cd576a9bba53fd4521302d75d223812bb3c8803374b11',
        'materials.ini': '89968dd7cb612de9ab87e024969440b183c8e1b1afac544f1d531178902102f8',
    },
    'copper_sphere_descendant': {
        'main.ini': 'c70337a2d9b3837e532eff88a1cad8c2b571bc7b128e490ad313b1ae0d0e8e68',
        'geometry.ini': 'b20f33a6f08eb35431c11f4380874ce894bab0aed19e3ecba9cc55e16c56d357',
        'parallel.ini': '27283525a21ef3275ee8c939d3df49c0afa0dd400ab961d91fca5740c5ee5a8d',
        'materials.ini': '89968dd7cb612de9ab87e024969440b183c8e1b1afac544f1d531178902102f8',
    },
}

R2_INPUTS = {
    'self_rotated_water_box': {
        'main.ini': '[run]\nthreads = 1\nseed = 20261400\n[output]\ndir = output\n[materials]\nfile = materials.ini\n[geometry]\ntemplate = hierarchical\nconfig = geometry.ini\n[physics]\nreference = FTFP_BERT\n[scoring]\nenabled = true\ndose = true\nfluence = true\nauto_create_default_scorers = true\n[source]\nparticle = proton\nenergy = 10 MeV\nposition_type = point\nposition = 0, 0, -20\ndirection = 0, 0, 1\n[parallel_world]\nenabled = true\nname = ScoringWorld\ngeometry_config = parallel.ini',
        'geometry.ini': '[world]\nshape = box\nsize = 100, 100, 100\nmaterial = G4_Galactic\n[volume.WaterBox]\nparent = world\nshape = box\nsize = 20, 2, 2\nposition = 0, 0, 0\nrotation = 0 deg, 0 deg, 90 deg\nmaterial = water\nsensitive = false',
        'parallel.ini': '[world]\nmaterial = G4_Galactic\n[volume.WaterBox]\nparent = world\nshape = box\nsize = 20, 2, 2\nposition = 0, 0, 0\nmaterial = water\nsensitive = true',
        'materials.ini': '[world]\nmaterial = G4_Galactic\n[water]\nmaterial = G4_WATER\n[copper]\nmaterial = G4_Cu',
    },
    'copper_sphere_descendant': {
        'main.ini': '[run]\nthreads = 1\nseed = 20261400\n[output]\ndir = output\n[materials]\nfile = materials.ini\n[geometry]\ntemplate = hierarchical\nconfig = geometry.ini\n[physics]\nreference = FTFP_BERT\n[scoring]\nenabled = true\ndose = true\nfluence = true\nauto_create_default_scorers = true\n[source]\nparticle = proton\nenergy = 10 MeV\nposition_type = point\nposition = 0, 0, -20\ndirection = 0, 0, 1\n[parallel_world]\nenabled = true\nname = ScoringWorld\ngeometry_config = parallel.ini',
        'geometry.ini': '[world]\nshape = box\nsize = 100, 100, 100\nmaterial = G4_Galactic\n[volume.WaterBox]\nparent = world\nshape = box\nsize = 40, 40, 2\nposition = 0, 0, 0\nmaterial = water\nsensitive = false\n[volume.CuSphere]\nparent = WaterBox\nshape = sphere\nparameters = 0 mm, 0.5 mm, 0 deg, 360 deg, 0 deg, 180 deg\nposition = 0, 0, 0\nmaterial = copper\nsensitive = false',
        'parallel.ini': '[world]\nmaterial = G4_Galactic\n[volume.WaterBox]\nparent = world\nshape = box\nsize = 40, 40, 2\nposition = 0, 0, 0\nmaterial = water\nsensitive = true',
        'materials.ini': '[world]\nmaterial = G4_Galactic\n[water]\nmaterial = G4_WATER\n[copper]\nmaterial = G4_Cu',
    },
}


def ingest_reviewed_case(root: Path, name: str) -> Case:
    """Materialize the reviewer's exact legal input bytes and verify their hashes."""
    assert name in R2_INPUTS, name
    case = Case(root, "r2_" + name, parallel=None, section="")
    for filename, expected in R2_INPUT_SHA256[name].items():
        data = R2_INPUTS[name][filename].encode("utf-8")
        assert hashlib.sha256(data).hexdigest() == expected, (name, filename)
        (case.path / filename).write_bytes(data)
    return case


def fix_r2_checks(root: Path) -> None:
    # B follow-up: a mass-world box that is itself rotated, or a mass-world box
    # with an unprojectable different-material daughter inside it, never proves
    # material correspondence. Both were reported as `true` before this fix.
    for name in R2_INPUTS:
        case = ingest_reviewed_case(root, name)
        expect_dry_ok(case)
        document = finalization(case.path / "output")
        resolved = resolved_field(document, "volume:WaterBox/material_matches_mass_world")
        assert resolved == "unknown", (name, resolved)

# Exact bytes of the two legal negative inputs from the H3-2 fix-r2 independent
# review (out/collab/h3-independent-r3). The hashes are the ones recorded in the
# reviewer's results.json; a mismatch here means the reproduction input drifted.
R3_LIFECYCLE_SHA256 = {'main.ini': '72bd7665ab22fd9450ff26ca60f3d59be8379ac32cb7353e72333bce3544afb1', 'geometry_water.ini': 'c4be1aece35ca9c6e26ed599bf242acc15eeb50572674477051e76e3b3860d8f', 'geometry_copper.ini': '2b30e82f95469e2d34d5adbc4daa14a8a82a575e919435009bfe7155eb46eb81', 'parallel.ini': '846bac0faf802c49303891abf919e056857baae381a3597d3444f1dde1b1979b', 'materials.ini': '89968dd7cb612de9ab87e024969440b183c8e1b1afac544f1d531178902102f8', 'switch.mac': '19a80672f35623eeb07576d9051e2f676b2e0550418f92f6d9bc003a8b55123a'}
R3_LIFECYCLE_INPUTS = {'main.ini': '[run]\nthreads = 1\nseed = 20261400\n[output]\ndir = output\n[materials]\nfile = materials.ini\n[geometry]\ntemplate = hierarchical\nconfig = geometry_water.ini\n[physics]\nreference = FTFP_BERT\n[scoring]\nenabled = true\ndose = true\nfluence = true\nauto_create_default_scorers = true\n[source]\nparticle = proton\nenergy = 10 MeV\nposition_type = point\nposition = 0, 0, -20\ndirection = 0, 0, 1\n[parallel_world]\nenabled = true\nname = ScoringWorld\ngeometry_config = parallel.ini', 'geometry_water.ini': '[world]\nshape = box\nsize = 100, 100, 100\nmaterial = G4_Galactic\n[volume.Slab]\nparent = world\nshape = box\nsize = 20, 20, 2\nposition = 0, 0, 0\nmaterial = water\nsensitive = false', 'geometry_copper.ini': '[world]\nshape = box\nsize = 100, 100, 100\nmaterial = G4_Galactic\n[volume.Slab]\nparent = world\nshape = box\nsize = 20, 20, 2\nposition = 0, 0, 0\nmaterial = copper\nsensitive = false', 'parallel.ini': '[world]\nmaterial = G4_Galactic\n[volume.Slab]\nparent = world\nshape = box\nsize = 20, 20, 2\nposition = 0, 0, 0\nmaterial = water\nsensitive = true', 'materials.ini': '[world]\nmaterial = G4_Galactic\n[water]\nmaterial = G4_WATER\n[copper]\nmaterial = G4_Cu', 'switch.mac': '/AIHL/geometry/loadConfig geometry_copper.ini\n/run/initialize\n/run/beamOn 20'}
R3_OVERLAP_SHA256 = {'main.ini': 'c70337a2d9b3837e532eff88a1cad8c2b571bc7b128e490ad313b1ae0d0e8e68', 'geometry.ini': '497ae74afab736a1e01c83b234ad1fa4c40fb4093475c0bdb3512400c8e95cb0', 'parallel.ini': 'f1694376ce20722edd98238f909e642a5cf2ca7149875d62f2af9e52a4ff1b1a', 'materials.ini': '89968dd7cb612de9ab87e024969440b183c8e1b1afac544f1d531178902102f8'}
R3_OVERLAP_INPUTS = {'main.ini': '[run]\nthreads = 1\nseed = 20261400\n[output]\ndir = output\n[materials]\nfile = materials.ini\n[geometry]\ntemplate = hierarchical\nconfig = geometry.ini\n[physics]\nreference = FTFP_BERT\n[scoring]\nenabled = true\ndose = true\nfluence = true\nauto_create_default_scorers = true\n[source]\nparticle = proton\nenergy = 10 MeV\nposition_type = point\nposition = 0, 0, -20\ndirection = 0, 0, 1\n[parallel_world]\nenabled = true\nname = ScoringWorld\ngeometry_config = parallel.ini', 'geometry.ini': '[world]\nshape = box\nsize = 2100000, 100, 100\nmaterial = G4_Galactic\n[volume.WaterBox]\nparent = world\nshape = box\nsize = 20, 2, 2\nposition = 0, 0, 0\nmaterial = water\nsensitive = false', 'parallel.ini': '[world]\nmaterial = G4_Galactic\n[volume.A]\nparent = world\nshape = box\nsize = 2, 2, 2\nposition = 1000000, 0, 0\nmaterial = water\nsensitive = true\n[volume.B]\nparent = world\nshape = box\nsize = 2, 2, 2\nposition = 1000001.9995, 0, 0\nmaterial = water\nsensitive = true', 'materials.ini': '[world]\nmaterial = G4_Galactic\n[water]\nmaterial = G4_WATER\n[copper]\nmaterial = G4_Cu'}


def ingest_r3_case(root: Path, name: str, inputs: dict[str, str],
                   hashes: dict[str, str]) -> Case:
    """Materialize one reviewed input set byte-for-byte after re-hashing it."""
    case = Case(root, name, parallel=None, section="")
    for filename, expected in hashes.items():
        data = inputs[filename].encode("utf-8")
        assert hashlib.sha256(data).hexdigest() == expected, (name, filename)
        (case.path / filename).write_bytes(data)
    return case


def fix_r3_checks(root: Path) -> None:
    # B/E lifecycle: a PreInit /AIHL/geometry/loadConfig replaces the mass-world
    # tree after Configure(). The 20-event run must complete on the new copper
    # geometry, and the material proof must be rebound to that tree (unknown)
    # instead of carrying the Configure-time water==water answer.
    lifecycle = ingest_r3_case(root, "r3_lifecycle", R3_LIFECYCLE_INPUTS,
                               R3_LIFECYCLE_SHA256)
    output = lifecycle.path / "output" / "run"
    proc = subprocess.run([str(EXE), "--config", "main.ini", "--macro", "switch.mac",
                           "--output", str(output)], cwd=lifecycle.path,
                          capture_output=True, text=True, errors="replace", timeout=900)
    (lifecycle.path / "run.log").write_text(proc.stdout + proc.stderr, encoding="utf-8")
    assert proc.returncode == 0, (lifecycle.path.name, proc.returncode,
                                  (proc.stdout + proc.stderr)[-3000:])
    text = summary(output)
    assert value(text, "status") == "completed", text[-2500:]
    assert value(text, "run_0_completed_events") == "20", text[-2500:]
    assert value(text, "effective_geometry_config") == "geometry_copper.ini", text[-2500:]
    document = finalization(output)
    assert resolved_field(document, "/geometry/objects/Slab/material") == "copper"
    assert resolved_field(document, "volume:Slab/material") == "water"
    assert resolved_field(document, "volume:Slab/material_matches_mass_world") == "unknown"
    # The old Configure-time proof may not leak into the run-begin snapshot either.
    run_begin = json.loads((output / "effective_config_run_0_t0.json").read_text(encoding="utf-8"))
    assert resolved_field(run_begin, "volume:Slab/material_matches_mass_world") == "unknown"

    # A: a representable 0.0005 mm interior overlap at 1,000,000 mm must be
    # rejected before construction; a 1e-9 relative slack used to swallow it.
    overlap = ingest_r3_case(root, "r3_overlap", R3_OVERLAP_INPUTS, R3_OVERLAP_SHA256)
    proc = subprocess.run([str(EXE), "--config", "main.ini", "--dry-run"],
                          cwd=overlap.path, capture_output=True, text=True,
                          errors="replace", timeout=600)
    blob = proc.stdout + proc.stderr
    (overlap.path / "dry_run.log").write_text(blob, encoding="utf-8")
    assert proc.returncode != 0, f"{overlap.path.name}: near-boundary overlap accepted\n{blob[-2500:]}"
    assert "overlap in their interior" in blob, blob[-2500:]

def fix_r1_checks(root: Path) -> None:
    """Focused regressions for the independent review fix round (A-I)."""
    # A: expanded names are unique, the global cap covers every grid, and only
    # a positive-volume interior intersection is rejected.
    derived = custom_case(root, "fix_derived_name", MATERIALS, GEOMETRY, FIX_R1_GRID_PLUS_CELL)
    derived.run_expect_failure("is not unique")

    overlap = custom_case(root, "fix_overlap", MATERIALS, GEOMETRY, FIX_R1_OVERLAP)
    overlap.run_expect_failure("overlap in their interior")

    contact = custom_case(root, "fix_face_contact", MATERIALS, GEOMETRY, FIX_R1_FACE_CONTACT)
    expect_dry_ok(contact)

    over_cap = custom_case(root, "fix_over_cap", MATERIALS, GEOMETRY, FIX_R1_TWO_GRIDS)
    over_cap.run_expect_failure("engineering cap is 4096")

    bad_name = custom_case(root, "fix_bad_name", MATERIALS, GEOMETRY, FIX_R1_BAD_NAME)
    bad_name.run_expect_failure("must start with a letter, digit or '_'")

    # C: a derived box that cannot fit the declared mass world is refused
    # before any Geant4 geometry object exists.
    huge = custom_case(root, "fix_non_finite", MATERIALS, GEOMETRY, FIX_R1_HUGE)
    huge.run_expect_failure("volume overflows")

    # F/H: the ghost leaf copy number is 0 at every level, including grid cells.
    copy0 = Case(root, "fix_copy0", parallel=PARALLEL_GRID)
    out = copy0.run("/run/initialize\n/run/beamOn 20\n")
    paths = {row["volume_path"] for row in rows(out, DOSE_NAME)
             if "ScoringWorld" in row["volume_path"]}
    assert paths, paths
    assert all(path.startswith("/ScoringWorld#0/") and path.endswith("#0")
               for path in paths), paths

    # D: per-run receipt names that run's completed events and the real bytes.
    receipt = Case(root, "fix_receipt")
    out = receipt.run("/run/initialize\n/run/beamOn 20\n")
    observed = run_validated_evidence(finalization(out))["observed"]
    assert observed["completed_events"] == 20, observed
    files = observed["output_sha256"]["files"]
    assert files, observed
    for item in files:
        digest = hashlib.sha256(Path(item["path"]).read_bytes()).hexdigest()
        assert item["sha256"] == digest, (item, digest)

    # B: material correspondence is proven for a plain leaf and for a
    # translated ancestor, and unknown when an alien daughter covers the box.
    unknown = custom_case(root, "fix_material_unknown", FIX_R1_MATERIALS,
                          FIX_R1_PLATE_WITH_DAUGHTER, FIX_R1_PARALLEL_WATER_BOX)
    out = unknown.run("/run/initialize\n/run/beamOn 20\n")
    assert resolved_field(finalization(out), "volume:WaterBox/material_matches_mass_world") == "unknown"
    paths = {row["volume_path"] for row in rows(out, DOSE_NAME)
             if "ScoringWorld" in row["volume_path"]}
    assert "/ScoringWorld#0/WaterBox#0" in paths, paths

    proven = custom_case(root, "fix_material_proven", MATERIALS, GEOMETRY, PARALLEL)
    out = proven.run("/run/initialize\n/run/beamOn 20\n")
    assert resolved_field(finalization(out), "volume:Slab/material_matches_mass_world") is True

    translated = custom_case(root, "fix_material_translated", FIX_R1_MATERIALS,
                             FIX_R1_TRANSLATED_GEOMETRY, FIX_R1_TRANSLATED_PARALLEL)
    out = translated.run("/run/initialize\n/run/beamOn 20\n")
    assert resolved_field(finalization(out), "volume:WaterBox/material_matches_mass_world") is True

    # E: forbidden combinations introduced after Configure are refused before
    # /run/initialize reaches the kernel.
    biasing = Case(root, "fix_biasing")
    biasing.run("/AIHL/biasing/enable true\n/run/initialize\n/run/beamOn 5\n", expected=1)
    assert "[biasing] enabled is not supported" in (biasing.path / "run.log").read_text(encoding="utf-8")

    mesh = Case(root, "fix_mesh")
    mesh.run("/score/create/boxMesh m1\n/run/initialize\n/run/beamOn 5\n", expected=1)
    assert "native /score mesh" in (mesh.path / "run.log").read_text(encoding="utf-8")

    root_format = Case(root, "fix_root")
    root_format.run("/AIHL/output/setFormat root\n/run/initialize\n/run/beamOn 5\n", expected=1)
    assert "ROOT output is not supported" in (root_format.path / "run.log").read_text(encoding="utf-8")


def main() -> None:
    assert EXE.is_file(), EXE
    with tempfile.TemporaryDirectory(prefix="g4usim-parallel-") as tmp:
        root = Path(tmp)

        # ---------------------------------------------------------- default off
        off = Case(root, "off", parallel=None)
        out = off.run("/run/initialize\n/run/beamOn 30\n")
        text = summary(out)
        assert "parallel_world_enabled" not in text, text[-2500:]
        assert all("ScoringWorld" not in row["volume_path"] for row in rows(out, DOSE_NAME))

        # ---------------------------------------------------------- one box
        box = Case(root, "box")
        out = box.run("/run/initialize\n/run/beamOn 200\n")
        text = summary(out)
        assert value(text, "status") == "completed", text[-2500:]
        assert value(text, "parallel_world_enabled") == "true"
        assert value(text, "parallel_world_name") == "ScoringWorld"
        assert value(text, "parallel_world_physics_constructor") == "G4ParallelWorldPhysics"
        assert value(text, "parallel_world_process") == "G4ParallelWorldProcess"
        assert value(text, "parallel_world_step_source") == "ghost_step"
        assert value(text, "parallel_world_dose_normalization") == "declared_material_reference_mass"
        assert re.fullmatch(r"[0-9a-f]{64}", value(text, "parallel_world_geometry_sha256"))
        assert value(text, "parallel_world_volume_count") == "1"
        assert math.isclose(float(value(text, "parallel_world_total_mass_kg")), 0.0008, rel_tol=1e-9)
        # The new section must be consumed: no unknown-section warning, no
        # unconsumed-key warning for [parallel_world].
        assert value(text, "config_warning_count") == "0", text[-2500:]
        assert value(text, "geometry_config_warning_count") == "0", text[-2500:]

        box_log = (box.path / "run.log").read_text(encoding="utf-8")
        for marker in ("[ConfigWarning]", "unconsumed field", "unknown section"):
            assert marker not in box_log, f"{marker} in backend log"

        dose = [row for row in rows(out, DOSE_NAME) if "ScoringWorld" in row["volume_path"]]
        assert len(dose) == 1, dose
        assert dose[0]["volume_path"] == "/ScoringWorld#0/Slab#0", dose[0]
        assert math.isclose(float(dose[0]["mass_kg"]), 0.0008, rel_tol=1e-9), dose[0]
        weighted = float(dose[0]["weighted_dose_Gy"])
        assert weighted > 0.0 and math.isfinite(weighted), dose[0]
        assert int(dose[0]["n_events"]) == 200, dose[0]
        energy = float(dose[0]["weighted_edep_MeV"])
        assert energy > 0.0
        joule = energy * 1.602176634e-13
        assert math.isclose(weighted, joule / 0.0008, rel_tol=1e-6), (weighted, energy)

        fluence = [row for row in rows(out, FLUENCE_NAME) if "ScoringWorld" in row["volume_path"]]
        assert len(fluence) == 1, fluence
        assert math.isclose(float(fluence[0]["volume_mm3"]), 800.0, rel_tol=1e-12), fluence[0]
        assert float(fluence[0]["weighted_fluence_mm-2"]) > 0.0, fluence[0]
        assert int(fluence[0]["n_events"]) == 200, fluence[0]

        # ---------------------------------------------------------- material alias
        alias = Case(root, "alias", parallel=PARALLEL_ALIAS)
        alias_out = alias.run("/run/initialize\n/run/beamOn 20\n")
        alias_dose = [row for row in rows(alias_out, DOSE_NAME) if "ScoringWorld" in row["volume_path"]]
        assert len(alias_dose) == 1, alias_dose
        assert math.isclose(float(alias_dose[0]["mass_kg"]), 0.0008, rel_tol=1e-9), alias_dose

        # ---------------------------------------------------------- regular grid
        grid = Case(root, "grid", parallel=PARALLEL_GRID)
        grid_out = grid.run("/run/initialize\n/run/beamOn 200\n")
        grid_text = summary(grid_out)
        assert value(grid_text, "parallel_world_volume_count") == "4", grid_text[-2000:]
        assert math.isclose(float(value(grid_text, "parallel_world_total_mass_kg")), 0.0008, rel_tol=1e-9)
        grid_dose = [row for row in rows(grid_out, DOSE_NAME) if "ScoringWorld" in row["volume_path"]]
        assert len(grid_dose) == 4, grid_dose
        expected_names = {f"SlabGrid_{ix}_{iy}_0" for ix in range(2) for iy in range(2)}
        assert {row["volume_name"] for row in grid_dose} == expected_names, grid_dose
        for row in grid_dose:
            assert row["volume_path"].startswith(f"/ScoringWorld#0/SlabGrid#0/{row['volume_name']}#"), row
        for row in grid_dose:
            assert math.isclose(float(row["mass_kg"]), 0.0002, rel_tol=1e-9), row
            assert int(row["n_events"]) == 200, row
        assert sum(float(row["weighted_dose_Gy"]) for row in grid_dose) > 0.0

        # ---------------------------------------------------------- thin grid (r3)
        # The frozen thin-grid counterexample carries the defect that motivated
        # the navigation envelope. One 1 MeV photon traverses the whole 2e-7 mm
        # grid: the kernel must limit one real step at the grid boundary and the
        # envelope detector must attribute it to the real cell (full thickness,
        # real cell volume). No proportion of the 70 mm vacuum step is clipped
        # into the score: exactly one step length of 2e-7 mm is counted.
        thin = Case(root, "thin_grid", parallel=PARALLEL_THIN_GRID,
                    geometry=GEOMETRY_VACUUM, source_section=PHOTON_SOURCE)
        thin_out = thin.run("/run/initialize" + chr(10) + "/run/beamOn 1" + chr(10))
        thin_fluence = [row for row in rows(thin_out, FLUENCE_NAME) if "ScoringWorld" in row["volume_path"]]
        assert thin_fluence, "thin grid produced no ghost fluence row"
        assert all(row["volume_path"].startswith("/ScoringWorld#0/GhostThin#0/GhostThin_") for row in thin_fluence)
        for row in thin_fluence:
            assert math.isclose(float(row["volume_mm3"]), 5e-06, rel_tol=1e-6), row
            assert math.isclose(float(row["weighted_track_length_mm"]), 2.0e-07, rel_tol=1e-5), row
        thin_dose = [row for row in rows(thin_out, DOSE_NAME)]
        assert thin_dose == [], "G4_Galactic grid must not deposit dose"

        # ---------------------------------------------------------- Stage A rejects
        missing = Case(root, "reject_missing_geometry", section="[parallel_world]\nenabled = true\n")
        missing.run_expect_failure("geometry_config")

        Case(root, "reject_bad_grid", parallel=PARALLEL_GRID.replace("bins = 2, 2, 1", "bins = 64, 64, 2")
             ).run_expect_failure("4096")
        Case(root, "reject_bad_material", parallel=PARALLEL.replace("G4_WATER", "G4_Unobtainium")
             ).run_expect_failure("G4_Unobtainium")
        Case(root, "reject_nested", parallel=PARALLEL.replace("parent = world", "parent = Slab")
             ).run_expect_failure("parent")
        Case(root, "reject_not_sensitive", parallel=PARALLEL.replace("sensitive = true", "sensitive = false")
             ).run_expect_failure("sensitive")
        Case(root, "reject_shape", parallel=PARALLEL.replace("shape = box", "shape = sphere")
             ).run_expect_failure("shape")
        Case(root, "reject_world_material", parallel=PARALLEL.replace(
            "[world]\nmaterial = G4_Galactic", "[world]\nmaterial = G4_WATER")
             ).run_expect_failure("G4_Galactic")
        Case(root, "reject_root", output_extra="format = root").run_expect_failure("ROOT")
        Case(root, "reject_biasing", main_extra="[biasing]\nenabled = true\n").run_expect_failure("biasing")
        Case(root, "reject_let", scoring_extra="let = true").run_expect_failure("let is not supported")
        Case(root, "reject_displacement", scoring_extra="displacement = true").run_expect_failure(
            "displacement")
        unknown = Case(root, "reject_unknown_key",
                       section="[parallel_world]\nenabled = true\nmystery = 1\n")
        unknown.run_expect_failure("unsupported [parallel_world] key")
        disabled = Case(root, "reject_disabled_with_config",
                        section="[parallel_world]\nenabled = false\nname = ScoringWorld\n")
        disabled.run_expect_failure("disabled")

        # ---------------------------------------------------------- R-RUNTIME
        runtime = Case(root, "r_runtime", scoring_extra="hits = true\nevent_edep = true")
        runtime_out = runtime.run("/run/initialize\n/run/beamOn 2000\n")
        runtime_text = summary(runtime_out)
        assert value(runtime_text, "status") == "completed", runtime_text[-2000:]
        event_rows = rows(runtime_out, EVENT_NAME)
        assert len(event_rows) == 2000, len(event_rows)
        assert all(math.isclose(float(row["weighted_edep_MeV"]), 0.0, abs_tol=1e-12) for row in event_rows)
        hit_files = [path for path in runtime_out.glob("*.csv") if HITS_NAME.fullmatch(path.name)]
        assert len(hit_files) == 1, hit_files
        hit_path = hit_files[0]
        assert hit_path.stat().st_size > 0, hit_path
        with hit_path.open(newline="", encoding="utf-8") as stream:
            hit_reader = csv.DictReader(stream)
            assert hit_reader.fieldnames, hit_path
            assert len(list(hit_reader)) == 0, hit_path
        registered = [line for line in runtime_text.splitlines()
                      if line.startswith("file_")
                      and line.rstrip().endswith("= " + str(hit_path))]
        assert registered, "hits_t0.csv must be registered in the run summary"
        runtime_dose = [row for row in rows(runtime_out, DOSE_NAME) if "ScoringWorld" in row["volume_path"]]
        assert len(runtime_dose) == 1 and float(runtime_dose[0]["weighted_dose_Gy"]) > 0.0, runtime_dose

        # ---------------------------------------------------------- R-SAME
        same = Case(root, "r_same", main_extra="", scoring_extra="hits = true\nevent_edep = true")
        (same.path / "geometry.ini").write_text(GEOMETRY.replace("sensitive = false", "sensitive = true"),
                                                encoding="utf-8")
        same_out = same.run("/run/initialize\n/run/beamOn 200\n")
        same_hits = rows(same_out, HITS_NAME)
        assert same_hits, "mass hits expected when the mass layer is sensitive"
        parallel_paths = {row["volume_path"] for row in rows(same_out, DOSE_NAME)
                          if "ScoringWorld" in row["volume_path"]}
        assert parallel_paths, "parallel dose rows expected"
        for row in same_hits:
            assert "ScoringWorld" not in row.get("volume", ""), row
            assert "ScoringWorld" not in row.get("volume_name", ""), row
        mass_dose = [row for row in rows(same_out, DOSE_NAME) if "ScoringWorld" not in row["volume_path"]]
        assert mass_dose, "mass dose rows expected"

        # ---------------------------------------------------------- Case M (MT)
        mt = Case(root, "case_m", threads=2, seed=20261466)
        mt_out = mt.run("/run/initialize\n/run/beamOn 200\n/run/beamOn 50\n", threads=2)
        mt_text = summary(mt_out)
        assert value(mt_text, "actual_threads") == "2", mt_text[-2500:]
        assert value(mt_text, "status") == "completed"
        dose_files = [path for path in mt_out.glob("*.csv") if DOSE_NAME.fullmatch(path.name)]
        assert dose_files, list(mt_out.iterdir())
        total_events = 0
        used_threads = set()
        for path in dose_files:
            with path.open(newline="", encoding="utf-8") as stream:
                file_rows = [row for row in csv.DictReader(stream) if "ScoringWorld" in row["volume_path"]]
            if not file_rows:
                continue
            assert len(file_rows) == 1, (path, file_rows)
            assert math.isclose(float(file_rows[0]["mass_kg"]), 0.0008, rel_tol=1e-9), file_rows
            total_events += int(file_rows[0]["n_events"])
            used_threads.add(DOSE_NAME.fullmatch(path.name).group(1))
        assert total_events == 250, (total_events, dose_files)
        assert used_threads <= {"0", "1"} and used_threads, (used_threads, dose_files)
        assert {DOSE_NAME.fullmatch(path.name).group(1) for path in dose_files} == {"0", "1"}, dose_files

        fix_r1_checks(root)
        fix_r2_checks(root)
        fix_r3_checks(root)

        evidence = os.environ.get("G4USIM_TEST_EVIDENCE_DIR")
        if evidence:
            destination = Path(evidence)
            destination.mkdir(parents=True, exist_ok=True)
            keep = ("run_summary.txt", "run_metadata.json")
            keep_prefix = ("dose_volume_summary", "fluence_volume_summary", "scorer_statistics")
            for case_name in ("off", "box", "alias", "grid", "r_runtime", "r_same", "case_m",
                              "fix_derived_name", "fix_overlap", "fix_face_contact", "fix_over_cap",
                              "fix_bad_name", "fix_non_finite", "fix_copy0", "fix_receipt",
                              "fix_material_unknown", "fix_material_proven",
                              "fix_material_translated", "fix_biasing", "fix_mesh", "fix_root",
                              "r3_lifecycle", "r3_overlap"):
                source = root / case_name
                if not source.is_dir():
                    continue
                target = destination / case_name
                target.mkdir(parents=True, exist_ok=True)
                for name in ("main.ini", "geometry.ini", "parallel.ini", "materials.ini"):
                    path = source / name
                    if path.is_file():
                        (target / name).write_bytes(path.read_bytes())
                for path in sorted((source / "output").rglob("*")):
                    if not path.is_file():
                        continue
                    if path.name not in keep and not path.name.startswith(keep_prefix):
                        continue
                    relative = path.relative_to(source / "output")
                    (target / "output" / relative).parent.mkdir(parents=True, exist_ok=True)
                    (target / "output" / relative).write_bytes(path.read_bytes())
                # Prove that R-RUNTIME kept the legacy event/hit files empty or
                # absent without copying megabytes of rows into the evidence tree.
                for pattern, name in ((EVENT_NAME, "event_rows.txt"), (HITS_NAME, "hit_rows.txt")):
                    counts = []
                    for path in sorted((source / "output").rglob("*.csv")):
                        if pattern.fullmatch(path.name):
                            with path.open(newline="", encoding="utf-8") as stream:
                                counts.append(f"{path.name}: {sum(1 for _ in csv.DictReader(stream))} rows")
                    if counts:
                        (target / name).write_text("\n".join(counts) + "\n", encoding="utf-8")

    print("test_parallel_world: OK")


if __name__ == "__main__":
    main()
