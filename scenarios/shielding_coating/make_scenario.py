"""Generates a runnable shielding / composite-coating scenario (roadmap Phase B2).

Command line wrapper over ``scenario_model.ShieldingSpec``: the same generator the GUI
uses, so the CLI and the GUI cannot drift apart.  Port of D:\\Geant4\\CoatingSimulation
to G4UniversalSim configuration files: a stack of coating layers (beam-facing layer
first) in front of a silicon device, irradiated at normal incidence by a square plane
source with a mono-energetic or tabulated (integral-flux) spectrum.  Optional interface
("junction") layers of reduced density and spherical vacuum pores in one layer
reproduce the original /cfg/openJunction and /cfg/openBubble options.

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
import sys
from pathlib import Path

# The sibling scenario generators (detector_response, semiconductor) import helpers
# from this module, so keep the historical names importable here even though the
# implementation now lives in scenario_model.
from scenario_model import (  # noqa: F401  (re-exported for make_detector/make_device)
    CUSTOM,
    ENVIRONMENT,
    NIST_DENSITY,
    UNITS,
    ScenarioError,
    ShieldingSpec,
    density,
    length_mm,
    pore_centres,
    spectrum_from_integral_flux,
    spectrum_points,
)

__all__ = ["CUSTOM", "ENVIRONMENT", "NIST_DENSITY", "UNITS", "ScenarioError", "ShieldingSpec",
           "build_spec", "density", "length_mm", "main", "parse_args", "pore_centres",
           "spectrum_from_integral_flux", "spectrum_points"]


def build_spec(args: argparse.Namespace) -> ShieldingSpec:
    return ShieldingSpec(
        layers=args.layers,
        size=args.size,
        device_thickness=args.device_thickness,
        source_half=args.source_half,
        particle=args.particle,
        energy_MeV=args.energy,
        proton_spectrum=args.proton_spectrum,
        electron_spectrum=args.electron_spectrum,
        mode=args.mode,
        junction_density=args.junction_density,
        pores_layer=args.pores_layer,
        pore_radius=args.pore_radius,
        pore_fraction=args.pore_fraction,
        niel=tuple(args.niel),
        physics=args.physics,
        em=args.em,
        coating_cut=args.coating_cut,
        coating_max_step=args.coating_max_step,
        device_cut=args.device_cut,
        events=args.events,
        threads=args.threads,
        seed=args.seed,
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
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
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    spec = build_spec(args)
    try:
        result = spec.generate(args.out, run_from=args.run_from or None)
    except ScenarioError as exc:
        raise SystemExit(str(exc)) from exc
    meta = result["meta"]
    print(f"scenario written to {result['out']} ({meta['coating_volumes']} coating volumes, {meta['pores']} pores)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
