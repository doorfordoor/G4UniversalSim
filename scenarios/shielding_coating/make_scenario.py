"""Generates a runnable shielding / composite-coating scenario (roadmap Phase B2).

Port of D:\\Geant4\\CoatingSimulation to G4UniversalSim configuration files: a stack
of coating layers (beam-facing layer first) in front of a silicon device, irradiated
at normal incidence by a square plane source with a mono-energetic or tabulated
(integral-flux) spectrum. Optional interface ("junction") layers of reduced density
and spherical vacuum pores in one layer reproduce the original /cfg/openJunction and
/cfg/openBubble options.

    python scenarios/shielding_coating/make_scenario.py --out work/shield \\
        --layers B4C:300um,G4_W:100um,G4_Al:300um --particle proton --events 2000
    G4UniversalSim.exe --config work/shield/main.ini
    python scenarios/shielding_coating/analyze.py work/shield/output

Geometry along +z (all lateral sizes --size, default 10 mm):
  FrontPlane (vacuum, 10 um) | source plane | layer 0 ... layer n-1 | gap | BackPlane
  (vacuum, 10 um) | gap | Device (G4_Si, --device-thickness)
--mode transmission records every particle entering BackPlane (phase space,
kill = false) and scores dose (TID), fluence and, with --niel, displacement damage
dose in the device. --mode albedo records particles leaving the stack backwards
through FrontPlane (kill = true); the source sits between FrontPlane and layer 0 so
primaries never cross it.
"""

from __future__ import annotations

import argparse
import math
import random
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
ENVIRONMENT = HERE / "environment"

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


def length_mm(text: str) -> float:
    match = re.fullmatch(r"\s*([0-9.eE+-]+)\s*(nm|um|mm|cm|m)\s*", text)
    if not match:
        raise SystemExit(f"bad length '{text}' (use e.g. 300um, 0.1mm)")
    value = float(match.group(1)) * UNITS[match.group(2)]
    if not value > 0:
        raise SystemExit(f"length must be > 0: '{text}'")
    return value


def density(material: str) -> float:
    if material in NIST_DENSITY:
        return NIST_DENSITY[material]
    if material in CUSTOM:
        return CUSTOM[material][0]
    raise SystemExit(f"unknown layer material '{material}'; known: {sorted(NIST_DENSITY) + sorted(CUSTOM)}")


def spectrum_from_integral_flux(source: Path, target: Path) -> tuple[float, float]:
    """Histogram bins (weight = F(E_i) - F(E_i+1)) from an integral-flux table.

    Returns (flux sampled between the first and last energy, flux above the last
    energy, which is not sampled), both in the table's units (cm-2 s-1).
    """
    points = []
    for line in source.read_text(encoding="utf-8-sig").splitlines()[1:]:
        parts = line.split()
        if len(parts) >= 2:
            points.append((float(parts[0]), float(parts[1])))
    if len(points) < 2 or any(b[0] <= a[0] or b[1] > a[1] for a, b in zip(points, points[1:])):
        raise SystemExit(f"{source}: energies must increase and the integral flux must not increase")
    lines = [f"# histogram from {source.name}: weight = integral flux F(E_low) - F(E_high) [cm-2 s-1]",
             "e_low_MeV,e_high_MeV,weight"]
    lines += [f"{a[0]:g},{b[0]:g},{a[1] - b[1]:.6g}" for a, b in zip(points, points[1:])]
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return points[0][1] - points[-1][1], points[-1][1]


def pore_centres(rng: random.Random, half_xy: float, thickness: float, radius: float, fraction: float):
    """Non-overlapping sphere centres: one sphere per randomly chosen grid cell."""
    cell = 2.2 * radius
    nx, nz = int(2 * half_xy / cell), int(thickness / cell)
    count = round(fraction * (2 * half_xy) ** 2 * thickness / (4.0 / 3.0 * math.pi * radius ** 3))
    if nx < 1 or nz < 1:
        raise SystemExit("pore radius too large for the layer")
    if count > nx * nx * nz:
        raise SystemExit(f"{count} pores do not fit ({nx * nx * nz} cells); use larger pores or a lower fraction")
    margin = cell / 2 - radius
    cells = rng.sample(range(nx * nx * nz), count)
    for index in cells:
        i, rest = divmod(index, nx * nz)
        j, k = divmod(rest, nz)
        yield (-half_xy + (i + 0.5) * cell + rng.uniform(-margin, margin),
               -half_xy + (j + 0.5) * cell + rng.uniform(-margin, margin),
               -thickness / 2 + (k + 0.5) * cell + rng.uniform(-margin, margin))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", required=True, help="directory for the generated files")
    parser.add_argument("--layers", default="B4C:300um,G4_W:100um,G4_Al:300um",
                        help="material:thickness list, beam-facing layer first")
    parser.add_argument("--size", default="10mm", help="lateral size of layers and device")
    parser.add_argument("--device-thickness", default="300um")
    parser.add_argument("--source-half", default="4mm", help="half side of the square source")
    parser.add_argument("--particle", default="proton", choices=["proton", "e-", "mixed"])
    parser.add_argument("--energy", type=float, default=0.0, help="mono-energetic MeV (default: spectrum)")
    parser.add_argument("--proton-spectrum", default=str(ENVIRONMENT / "proton_integral_flux.txt"))
    parser.add_argument("--electron-spectrum", default=str(ENVIRONMENT / "electron_integral_flux.txt"))
    parser.add_argument("--mode", default="transmission", choices=["transmission", "albedo"])
    parser.add_argument("--junction-density", type=float, default=0.0,
                        help="density ratio of interface layers (0 = none); 10 um for W, 30 um otherwise")
    parser.add_argument("--pores-layer", type=int, default=-1, help="index of the layer with vacuum pores")
    parser.add_argument("--pore-radius", default="20um")
    parser.add_argument("--pore-fraction", type=float, default=0.01)
    parser.add_argument("--niel", action="append", default=[], metavar="PARTICLE=TABLE.csv",
                        help="enable displacement damage with a NIEL table (repeatable)")
    parser.add_argument("--physics", default="QGSP_BERT_HP")
    parser.add_argument("--em", default="option4")
    parser.add_argument("--coating-cut", default="2 um")
    parser.add_argument("--coating-max-step", default="10 um")
    parser.add_argument("--device-cut", default="10 um")
    parser.add_argument("--events", type=int, default=1000)
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--seed", type=int, default=12345)
    parser.add_argument("--run-from", default="",
                        help="directory the backend will be started from (default: --out); materials, "
                             "geometry, macro and output paths are written relative to it")
    args = parser.parse_args()

    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    half = length_mm(args.size) / 2
    layers = []
    for item in args.layers.split(","):
        material, _, thickness = item.strip().partition(":")
        density(material)
        layers.append((material, length_mm(thickness)))
    if not layers:
        raise SystemExit("--layers is empty")
    if not 0 <= args.junction_density < 1:
        raise SystemExit("--junction-density must be in [0, 1)")

    # Materials: NIST layers, custom coatings and reduced-density junction copies.
    used = {m for m, _ in layers}
    lines = ["# generated by make_scenario.py", "[nist]",
             "materials = " + ", ".join(sorted({"G4_Galactic", "G4_Si"} | {m for m in used if m.startswith("G4_")}))]
    for name in sorted(m for m in used if m in CUSTOM):
        rho, components = CUSTOM[name]
        lines += ["", f"[material.{name}]", "mode = atom_count", f"density = {rho} g/cm3",
                  f"components = {components}", "state = solid"]
    if args.junction_density:
        for name in sorted(used):
            lines += ["", f"[material.{name.replace('G4_', '')}_J]", "mode = mass_fraction",
                      f"density = {density(name) * args.junction_density:.6g} g/cm3",
                      f"components = {name}:1.0", "state = solid"]
    (out / "materials.ini").write_text("\n".join(lines) + "\n", encoding="utf-8")

    # Geometry.
    geo = ["# generated by make_scenario.py", "[world]", "shape = box", "size = 20 cm, 20 cm, 20 cm",
           "material = G4_Galactic"]
    z = 0.0
    coating_volumes = []

    def box(name, material, thickness, z_centre, extra=()):
        geo.extend(["", f"[volume.{name}]", "parent = world", "shape = box",
                    f"size = {2 * half:g} mm, {2 * half:g} mm, {thickness:.6g} mm", f"material = {material}",
                    f"position = 0 mm, 0 mm, {z_centre:.6g} mm", *extra])

    pores = []
    for index, (material, thickness) in enumerate(layers):
        tag = material.replace("G4_", "")
        if args.junction_density and index > 0:
            junction = min(0.010 if material == "G4_W" else 0.030, thickness / 2)
            name = f"Junction{index}_{tag}"
            box(name, f"{tag}_J", junction, z + junction / 2, ["region = Coating"])
            coating_volumes.append(name)
            z += junction
            thickness -= junction
        name = f"Layer{index}_{tag}"
        box(name, material, thickness, z + thickness / 2, ["region = Coating"])
        coating_volumes.append(name)
        if index == args.pores_layer:
            radius = length_mm(args.pore_radius)
            pores = list(pore_centres(random.Random(args.seed), half, thickness, radius, args.pore_fraction))
            (out / "pores.csv").write_text("# pore centres in the layer frame\nx_mm,y_mm,z_mm\n" +
                                           "".join(f"{x:.6f},{y:.6f},{zz:.6f}\n" for x, y, zz in pores),
                                           encoding="utf-8")
            geo.extend(["", "[volume.Pore]", f"parent = {name}", "shape = orb", f"parameters = {radius:g} mm",
                        "material = G4_Galactic", "placement = parameterised", "copies_file = pores.csv"])
        z += thickness
    stack_end = z
    device = length_mm(args.device_thickness)
    box("FrontPlane", "G4_Galactic", 0.010, -2.005)
    box("BackPlane", "G4_Galactic", 0.010, stack_end + 0.505)
    box("Device", "G4_Si", device, stack_end + 1.010 + device / 2, ["sensitive = true", "region = Device"])
    (out / "geometry.ini").write_text("\n".join(geo) + "\n", encoding="utf-8")

    # Source.
    def source_block(header, particle, intensity=None):
        block = [header, f"particle = {particle}"]
        if intensity is not None:
            block.append(f"intensity = {intensity:.6g}")
        if args.energy > 0:
            block.append(f"energy = {args.energy} MeV")
            sampled = None
        else:
            spectrum = Path(args.proton_spectrum if particle == "proton" else args.electron_spectrum)
            target = out / f"spectrum_{'proton' if particle == 'proton' else 'electron'}.csv"
            sampled = spectrum_from_integral_flux(spectrum, target)
            block += ["energy_type = histogram", f"spectrum_file = {target.name}"]
        source_half = length_mm(args.source_half)
        block += ["position_type = plane", "shape = square", f"halfx = {source_half:g} mm",
                  "center = 0 mm, 0 mm, -1 mm", "direction = 0, 0, 1"]
        return block, sampled

    if args.particle == "mixed":
        if args.energy > 0:
            raise SystemExit("--particle mixed needs the spectra (no --energy)")
        flux = {p: spectrum_from_integral_flux(Path(s), out / "tmp.csv")[0]
                for p, s in (("proton", args.proton_spectrum), ("e-", args.electron_spectrum))}
        (out / "tmp.csv").unlink()
        proton_block, sampled_p = source_block("[source.protons]", "proton", flux["proton"])
        electron_block, sampled_e = source_block("[source.electrons]", "e-", flux["e-"])
        source = ["[source]", "verbose = 0", ""] + proton_block + [""] + electron_block
        sampled = {"proton": sampled_p, "e-": sampled_e}
    else:
        block, value = source_block("[source]", args.particle)
        source = block
        sampled = {args.particle: value}

    scoring = ["[scoring]", "enabled = true", "hits = false", "event_edep = false", "edep = false",
               "dose = true", "fluence = true", "auto_create_default_scorers = true"]
    if args.niel:
        scoring.append("displacement = true")
        scoring += ["", "[scoring.displacement]"]
        for item in args.niel:
            particle, _, table = item.partition("=")
            if not particle or not table:
                raise SystemExit(f"--niel needs PARTICLE=TABLE.csv, got '{item}'")
            scoring.append(f"{particle.strip()} = {Path(table).resolve().as_posix()}")
    phase_volume = "BackPlane_PV" if args.mode == "transmission" else "FrontPlane_PV"
    kill = "false" if args.mode == "transmission" else "true"
    physics = ["[physics]", f"reference = {args.physics}", f"em = {args.em}", "default_cut = 0.1 mm", "",
               "[physics.region.Coating]"] + [f"{p} = {args.coating_cut}" for p in ("gamma", "e-", "e+")] + \
              [f"max_step = {args.coating_max_step}", "", "[physics.region.Device]"] + \
              [f"{p} = {args.device_cut}" for p in ("gamma", "e-", "e+")]
    import os
    base = Path(args.run_from).resolve() if args.run_from else out
    prefix = Path(os.path.relpath(out, base)).as_posix()

    def rel(name: str) -> str:
        return name if prefix == "." else f"{prefix}/{name}"

    settings = {k: v for k, v in vars(args).items() if k not in ("out", "niel", "run_from")}
    for key in ("proton_spectrum", "electron_spectrum"):
        settings[key] = Path(settings[key]).name
    main_ini = ["# generated by make_scenario.py: " + " ".join(f"{k}={v}" for k, v in settings.items()),
                "[run]", f"threads = {args.threads}", f"seed = {args.seed}", f"macro = {rel('run.mac')}", "",
                "[output]", f"dir = {rel('output')}", "format = csv", "", "[materials]",
                f"file = {rel('materials.ini')}", "", "[geometry]", "template = hierarchical",
                f"config = {rel('geometry.ini')}",
                # Pores are non-overlapping by construction (one per grid cell); Geant4's
                # overlap check of thousands of parameterised copies is quadratic.
                *(["check_overlaps = false"] if pores else []), "", *physics, "",
                *scoring, "", *source, "", "[phase_space]", f"volume = {phase_volume}", "particles = all",
                f"kill = {kill}", ""]
    (out / "main.ini").write_text("\n".join(main_ini), encoding="utf-8")
    (out / "run.mac").write_text(f"/run/initialize\n/run/beamOn {args.events}\n", encoding="utf-8")
    meta = {"mode": args.mode, "particle": args.particle, "events": args.events,
            "source_area_cm2": (2 * length_mm(args.source_half) / 10) ** 2,
            "sampled_integral_flux_cm2_s": {k: (v[0] if v else None) for k, v in sampled.items()},
            "unsampled_flux_above_last_energy_cm2_s": {k: (v[1] if v else None) for k, v in sampled.items()},
            "layers": [{"material": m, "thickness_mm": t} for m, t in layers], "pores": len(pores),
            "junction_density": args.junction_density, "device_thickness_mm": device,
            "displacement": bool(args.niel)}
    import json
    (out / "scenario.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(f"scenario written to {out} ({len(coating_volumes)} coating volumes, {len(pores)} pores)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
