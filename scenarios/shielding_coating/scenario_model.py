"""Shielding / composite-coating scenario model (roadmap Phase B2, GUI stage 2B).

The scenario files used to be written only by the ``make_scenario.py`` command line
tool.  The GUI needs the same generator as a library: a typed ``ShieldingSpec`` that
can be validated field by field, rendered into the files of a run directory, and
shown to the user before anything is written.  ``make_scenario.py`` is now a thin
argument parser over this module, so both entry points produce byte identical output.

Geometry along +z (all lateral sizes ``size``, default 10 mm)::

    FrontPlane (vacuum, 10 um) | source plane | layer 0 ... layer n-1 | gap | BackPlane
    (vacuum, 10 um) | gap | Device (G4_Si, device_thickness)

``mode = transmission`` records every particle entering BackPlane (phase space,
kill = false) and scores dose (TID), fluence and, with NIEL tables, displacement
damage dose in the device.  ``mode = albedo`` records particles leaving the stack
backwards through FrontPlane (kill = true); the source sits between FrontPlane and
layer 0 so primaries never cross it.

The validation errors keep the exact messages of the original CLI, so scripts and
tests that match on them keep working; they are raised as ``ScenarioError`` and the
command line wrapper turns that into the same ``SystemExit`` text as before.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import random
import re
from dataclasses import dataclass, field, replace
from pathlib import Path

HERE = Path(__file__).resolve().parent
ENVIRONMENT = HERE / "environment"
PROTON_SPECTRUM = ENVIRONMENT / "proton_integral_flux.txt"
ELECTRON_SPECTRUM = ENVIRONMENT / "electron_integral_flux.txt"

# Densities (g/cm3) of the Geant4 NIST materials usable as layers, and of the custom
# coating materials defined in the generated materials file.
NIST_DENSITY = {"G4_Galactic": 1e-25, "G4_Al": 2.699, "G4_W": 19.3, "G4_Si": 2.33, "G4_Ti": 4.54, "G4_Cu": 8.96, "G4_Ta": 16.654,
                "G4_Pb": 11.35, "G4_Fe": 7.874, "G4_KAPTON": 1.42, "G4_POLYETHYLENE": 0.94,
                "G4_ALUMINUM_OXIDE": 3.97, "G4_SILICON_DIOXIDE": 2.32}
CUSTOM = {  # name: (density g/cm3, atom-count components) as in CoatingSimulation/materials.ini
    "B4C": (2.52, "G4_B:4, G4_C:1"),
    "HEB": (8.97, "G4_Zr:1, G4_Ta:1, G4_Ti:1, G4_Hf:1, G4_W:1, G4_B:10"),
    "ZnO": (5.61, "G4_Zn:1, G4_O:1"),
    "Si3N4": (3.17, "G4_Si:3, G4_N:4"),
}
UNITS = {"nm": 1e-6, "um": 1e-3, "mm": 1.0, "cm": 10.0, "m": 1000.0}
PARTICLES = ("proton", "e-", "mixed")
MODES = ("transmission", "albedo")
LAYER_MATERIALS = tuple(sorted(NIST_DENSITY)) + tuple(sorted(CUSTOM))


class ScenarioError(ValueError):
    """A scenario parameter is inconsistent or a generated file cannot be written."""


def length_mm(text: str) -> float:
    """Length in mm from a text like ``300um`` (nm, um, mm, cm, m)."""
    match = re.fullmatch(r"\s*([0-9.eE+-]+)\s*(nm|um|mm|cm|m)\s*", text)
    if not match:
        raise ScenarioError(f"bad length '{text}' (use e.g. 300um, 0.1mm)")
    value = float(match.group(1)) * UNITS[match.group(2)]
    if not value > 0:
        raise ScenarioError(f"length must be > 0: '{text}'")
    return value


def density(material: str) -> float:
    if material in NIST_DENSITY:
        return NIST_DENSITY[material]
    if material in CUSTOM:
        return CUSTOM[material][0]
    raise ScenarioError(f"unknown layer material '{material}'; known: {sorted(NIST_DENSITY) + sorted(CUSTOM)}")


def spectrum_points(source: Path) -> list[tuple[float, float]]:
    """Energy / integral-flux points of a table (first column energy in MeV)."""
    source = Path(source)
    try:
        text = source.read_text(encoding="utf-8-sig")
    except OSError as exc:
        raise ScenarioError(f"cannot read the integral flux table {source}: {exc}") from exc
    points = []
    for line in text.splitlines()[1:]:
        parts = line.split()
        if len(parts) >= 2:
            points.append((float(parts[0]), float(parts[1])))
    if len(points) < 2 or any(b[0] <= a[0] or b[1] > a[1] for a, b in zip(points, points[1:])):
        raise ScenarioError(f"{source}: energies must increase and the integral flux must not increase")
    return points


def histogram_text(source: Path) -> tuple[str, tuple[float, float]]:
    """The histogram CSV of a table, plus (sampled flux, flux above the last energy)."""
    source = Path(source)
    points = spectrum_points(source)
    lines = [f"# histogram from {source.name}: weight = integral flux F(E_low) - F(E_high) [cm-2 s-1]",
             "e_low_MeV,e_high_MeV,weight"]
    lines += [f"{a[0]:g},{b[0]:g},{a[1] - b[1]:.6g}" for a, b in zip(points, points[1:])]
    return "\n".join(lines) + "\n", (points[0][1] - points[-1][1], points[-1][1])


def spectrum_from_integral_flux(source: Path, target: Path) -> tuple[float, float]:
    """Write the histogram CSV of an integral-flux table and return its flux summary."""
    text, sampled = histogram_text(source)
    Path(target).write_text(text, encoding="utf-8")
    return sampled


def pore_centres(rng: random.Random, half_xy: float, thickness: float, radius: float, fraction: float):
    """Non-overlapping sphere centres: one sphere per randomly chosen grid cell."""
    cell = 2.2 * radius
    nx, nz = int(2 * half_xy / cell), int(thickness / cell)
    count = round(fraction * (2 * half_xy) ** 2 * thickness / (4.0 / 3.0 * math.pi * radius ** 3))
    if nx < 1 or nz < 1:
        raise ScenarioError("pore radius too large for the layer")
    if count > nx * nx * nz:
        raise ScenarioError(f"{count} pores do not fit ({nx * nx * nz} cells); use larger pores or a lower fraction")
    margin = cell / 2 - radius
    cells = rng.sample(range(nx * nx * nz), count)
    for index in cells:
        i, rest = divmod(index, nx * nz)
        j, k = divmod(rest, nz)
        yield (-half_xy + (i + 0.5) * cell + rng.uniform(-margin, margin),
               -half_xy + (j + 0.5) * cell + rng.uniform(-margin, margin),
               -thickness / 2 + (k + 0.5) * cell + rng.uniform(-margin, margin))


@dataclass(frozen=True)
class ShieldingSpec:
    """All parameters of the shielding / coating scenario, with CLI compatible defaults."""

    layers: str = "B4C:300um,G4_W:100um,G4_Al:300um"
    size: str = "10mm"
    device_thickness: str = "300um"
    source_half: str = "4mm"
    particle: str = "proton"
    energy_MeV: float = 0.0                      # 0 = sample the tabulated spectrum
    proton_spectrum: str = str(PROTON_SPECTRUM)
    electron_spectrum: str = str(ELECTRON_SPECTRUM)
    mode: str = "transmission"
    junction_density: float = 0.0
    pores_layer: int = -1
    pore_radius: str = "20um"
    pore_fraction: float = 0.01
    niel: tuple[str, ...] = ()                   # "particle=table.csv" entries
    physics: str = "QGSP_BERT_HP"
    em: str = "option4"
    coating_cut: str = "2 um"
    coating_max_step: str = "10 um"
    device_cut: str = "10 um"
    events: int = 1000
    threads: int = 4
    seed: int = 12345

    # -- validation ---------------------------------------------------------

    def parsed_layers(self) -> list[tuple[str, float]]:
        layers = []
        for item in self.layers.split(","):
            material, _, thickness = item.strip().partition(":")
            density(material)
            layers.append((material, length_mm(thickness)))
        if not layers:
            raise ScenarioError("--layers is empty")
        return layers

    def parsed_niel(self) -> dict[str, str]:
        tables: dict[str, str] = {}
        for item in self.niel:
            particle, _, table = item.partition("=")
            if not particle or not table:
                raise ScenarioError(f"--niel needs PARTICLE=TABLE.csv, got '{item}'")
            tables[particle.strip()] = str(Path(table).resolve().as_posix())
        return tables

    def problems(self) -> list[str]:
        """Every parameter problem, in the order the CLI would report them."""
        found: list[str] = []
        try:
            self.parsed_layers()
        except ScenarioError as exc:
            found.append(str(exc))
        for name in ("size", "device_thickness", "source_half", "pore_radius"):
            try:
                length_mm(getattr(self, name))
            except ScenarioError as exc:
                found.append(str(exc))
        if self.particle not in PARTICLES:
            found.append(f"--particle must be one of {list(PARTICLES)}, got '{self.particle}'")
        if self.mode not in MODES:
            found.append(f"--mode must be one of {list(MODES)}, got '{self.mode}'")
        if not 0 <= self.junction_density < 1:
            found.append("--junction-density must be in [0, 1)")
        if not 0 <= self.pore_fraction < 1:
            found.append("--pore-fraction must be in [0, 1)")
        if self.energy_MeV < 0:
            found.append(f"--energy must be >= 0, got {self.energy_MeV}")
        if self.particle == "mixed" and self.energy_MeV > 0:
            found.append("--particle mixed needs the spectra (no --energy)")
        if self.events <= 0:
            found.append(f"--events must be > 0, got {self.events}")
        if self.threads <= 0:
            found.append(f"--threads must be > 0, got {self.threads}")
        try:
            self.parsed_niel()
        except ScenarioError as exc:
            found.append(str(exc))
        if self.pores_layer >= 0:
            try:
                layers = self.parsed_layers()
            except ScenarioError:
                layers = []
            if self.pores_layer >= len(layers):
                found.append(f"--pores-layer {self.pores_layer} is outside the {len(layers)} layer stack")
        return found

    def validate(self) -> "ShieldingSpec":
        problems = self.problems()
        if problems:
            raise ScenarioError(problems[0])
        return self

    # -- rendering ----------------------------------------------------------

    def render(self, out: str | Path, *, run_from: str | Path | None = None) -> dict[str, str]:
        """The files of the scenario as ``{relative name: text}``; nothing is written."""
        self.validate()
        out_path = Path(out).resolve()
        base = Path(run_from).resolve() if run_from else out_path
        prefix = Path(os.path.relpath(out_path, base)).as_posix()

        def rel(name: str) -> str:
            return name if prefix == "." else f"{prefix}/{name}"

        files: dict[str, str] = {}
        layers = self.parsed_layers()
        half = length_mm(self.size) / 2

        # Materials: NIST layers, custom coatings and reduced-density junction copies.
        used = {material for material, _ in layers}
        lines = ["# generated by make_scenario.py", "[nist]",
                 "materials = " + ", ".join(sorted({"G4_Galactic", "G4_Si"} | {m for m in used if m.startswith("G4_")}))]
        for name in sorted(m for m in used if m in CUSTOM):
            rho, components = CUSTOM[name]
            lines += ["", f"[material.{name}]", "mode = atom_count", f"density = {rho} g/cm3",
                      f"components = {components}", "state = solid"]
        if self.junction_density:
            for name in sorted(used):
                lines += ["", f"[material.{name.replace('G4_', '')}_J]", "mode = mass_fraction",
                          f"density = {density(name) * self.junction_density:.6g} g/cm3",
                          f"components = {name}:1.0", "state = solid"]
        files["materials.ini"] = "\n".join(lines) + "\n"

        # Geometry.
        geo = ["# generated by make_scenario.py", "[world]", "shape = box", "size = 20 cm, 20 cm, 20 cm",
               "material = G4_Galactic"]
        z = 0.0
        coating_volumes = []

        def box(name, material, thickness, z_centre, extra=()):
            geo.extend(["", f"[volume.{name}]", "parent = world", "shape = box",
                        f"size = {2 * half:g} mm, {2 * half:g} mm, {thickness:.6g} mm", f"material = {material}",
                        f"position = 0 mm, 0 mm, {z_centre:.6g} mm", *extra])

        pores: list[tuple[float, float, float]] = []
        for index, (material, thickness) in enumerate(layers):
            tag = material.replace("G4_", "")
            if self.junction_density and index > 0:
                junction = min(0.010 if material == "G4_W" else 0.030, thickness / 2)
                name = f"Junction{index}_{tag}"
                box(name, f"{tag}_J", junction, z + junction / 2, ["region = Coating"])
                coating_volumes.append(name)
                z += junction
                thickness -= junction
            name = f"Layer{index}_{tag}"
            box(name, material, thickness, z + thickness / 2, ["region = Coating"])
            coating_volumes.append(name)
            if index == self.pores_layer:
                radius = length_mm(self.pore_radius)
                pores = list(pore_centres(random.Random(self.seed), half, thickness, radius, self.pore_fraction))
                files["pores.csv"] = ("# pore centres in the layer frame\nx_mm,y_mm,z_mm\n" +
                                      "".join(f"{x:.6f},{y:.6f},{zz:.6f}\n" for x, y, zz in pores))
                geo.extend(["", "[volume.Pore]", f"parent = {name}", "shape = orb", f"parameters = {radius:g} mm",
                            "material = G4_Galactic", "placement = parameterised", "copies_file = pores.csv"])
            z += thickness
        stack_end = z
        device = length_mm(self.device_thickness)
        box("FrontPlane", "G4_Galactic", 0.010, -2.005)
        box("BackPlane", "G4_Galactic", 0.010, stack_end + 0.505)
        box("Device", "G4_Si", device, stack_end + 1.010 + device / 2, ["sensitive = true", "region = Device"])
        files["geometry.ini"] = "\n".join(geo) + "\n"

        # Source.
        def source_block(header, particle, intensity=None):
            block = [header, f"particle = {particle}"]
            if intensity is not None:
                block.append(f"intensity = {intensity:.6g}")
            if self.energy_MeV > 0:
                block.append(f"energy = {self.energy_MeV} MeV")
                sampled = None
            else:
                name = "proton" if particle == "proton" else "electron"
                table = Path(self.proton_spectrum if particle == "proton" else self.electron_spectrum)
                label = f"spectrum_{name}.csv"
                files[label], sampled = histogram_text(table)
                block += ["energy_type = histogram", f"spectrum_file = {label}"]
            source_half = length_mm(self.source_half)
            block += ["position_type = plane", "shape = square", f"halfx = {source_half:g} mm",
                      "center = 0 mm, 0 mm, -1 mm", "direction = 0, 0, 1"]
            return block, sampled

        if self.particle == "mixed":
            flux = {p: histogram_text(Path(s))[1][0]
                    for p, s in (("proton", self.proton_spectrum), ("e-", self.electron_spectrum))}
            proton_block, sampled_p = source_block("[source.protons]", "proton", flux["proton"])
            electron_block, sampled_e = source_block("[source.electrons]", "e-", flux["e-"])
            source = ["[source]", "verbose = 0", ""] + proton_block + [""] + electron_block
            sampled = {"proton": sampled_p, "e-": sampled_e}
        else:
            block, value = source_block("[source]", self.particle)
            source = block
            sampled = {self.particle: value}

        scoring = ["[scoring]", "enabled = true", "hits = false", "event_edep = false", "edep = false",
                   "dose = true", "fluence = true", "auto_create_default_scorers = true"]
        tables = self.parsed_niel()
        if tables:
            scoring.append("displacement = true")
            scoring += ["", "[scoring.displacement]"]
            scoring += [f"{particle} = {table}" for particle, table in tables.items()]
        phase_volume = "BackPlane_PV" if self.mode == "transmission" else "FrontPlane_PV"
        kill = "false" if self.mode == "transmission" else "true"
        physics = ["[physics]", f"reference = {self.physics}", f"em = {self.em}", "default_cut = 0.1 mm", "",
                   "[physics.region.Coating]"] + [f"{p} = {self.coating_cut}" for p in ("gamma", "e-", "e+")] + \
                  [f"max_step = {self.coating_max_step}", "", "[physics.region.Device]"] + \
                  [f"{p} = {self.device_cut}" for p in ("gamma", "e-", "e+")]

        settings = {
            "layers": self.layers, "size": self.size, "device_thickness": self.device_thickness,
            "source_half": self.source_half, "particle": self.particle, "energy": self.energy_MeV,
            "proton_spectrum": Path(self.proton_spectrum).name, "electron_spectrum": Path(self.electron_spectrum).name,
            "mode": self.mode, "junction_density": self.junction_density, "pores_layer": self.pores_layer,
            "pore_radius": self.pore_radius, "pore_fraction": self.pore_fraction, "physics": self.physics,
            "em": self.em, "coating_cut": self.coating_cut, "coating_max_step": self.coating_max_step,
            "device_cut": self.device_cut, "events": self.events, "threads": self.threads, "seed": self.seed,
        }
        main_ini = ["# generated by make_scenario.py: " + " ".join(f"{k}={v}" for k, v in settings.items()),
                    "[run]", f"threads = {self.threads}", f"seed = {self.seed}", f"macro = {rel('run.mac')}", "",
                    "[output]", f"dir = {rel('output')}", "format = csv", "", "[materials]",
                    f"file = {rel('materials.ini')}", "", "[geometry]", "template = hierarchical",
                    f"config = {rel('geometry.ini')}",
                    # Pores are non-overlapping by construction (one per grid cell); Geant4's
                    # overlap check of thousands of parameterised copies is quadratic.
                    *(["check_overlaps = false"] if pores else []), "", *physics, "",
                    *scoring, "", *source, "", "[phase_space]", f"volume = {phase_volume}", "particles = all",
                    f"kill = {kill}", ""]
        files["main.ini"] = "\n".join(main_ini)
        files["run.mac"] = f"/run/initialize\n/run/beamOn {self.events}\n"
        niel_meta = []
        for particle, table in tables.items():
            table_path = Path(table)
            digest = None
            try:
                digest = hashlib.sha256(table_path.read_bytes()).hexdigest()
            except OSError:
                digest = None   # the backend reports a missing table; keep the path here
            niel_meta.append({"particle": particle, "path": str(table), "sha256": digest})
        meta = {"mode": self.mode, "particle": self.particle, "events": self.events,
                "source_area_cm2": (2 * length_mm(self.source_half) / 10) ** 2,
                "sampled_integral_flux_cm2_s": {k: (v[0] if v else None) for k, v in sampled.items()},
                "unsampled_flux_above_last_energy_cm2_s": {k: (v[1] if v else None) for k, v in sampled.items()},
                "layers": [{"material": m, "thickness_mm": t} for m, t in layers], "pores": len(pores),
                "junction_density": self.junction_density, "device_thickness_mm": device,
                "displacement": bool(tables), "coating_volumes": len(coating_volumes),
                "niel": niel_meta}
        files["scenario.json"] = json.dumps(meta, indent=2)
        return files

    def generate(self, out: str | Path, *, run_from: str | Path | None = None) -> dict:
        """Write the scenario files into ``out`` and return the written paths plus meta."""
        out_path = Path(out).resolve()
        out_path.mkdir(parents=True, exist_ok=True)
        files = self.render(out_path, run_from=run_from)
        written = {}
        for name, text in files.items():
            path = out_path / name
            path.write_text(text, encoding="utf-8")
            written[name] = path
        return {"out": out_path, "files": written, "meta": json.loads(files["scenario.json"])}

    # -- convenience --------------------------------------------------------

    @property
    def is_spectrum(self) -> bool:
        return self.energy_MeV <= 0 and self.particle != "mixed"

    def with_niel(self, *tables: str) -> "ShieldingSpec":
        return replace(self, niel=tuple(self.niel) + tuple(tables))
