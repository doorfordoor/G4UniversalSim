"""Examples gallery of the Start page, without Qt.

Each example is a new-simulation wizard spec (core/wizard.py) plus results the
backend produced for it, bundled under examples/gallery/<id>/:
  output/          the run's output files (hits and ROOT files left out), for
                   Results / Plots
  scan/scan.json   a parameter scan instead (points' summaries and statistics),
                   for Parameter Scans; paths in it are relative to scan/
  thumbnail.png    a plot of the bundled results
Opening an example puts its spec into the project like the wizard does (so Generate
& Run reruns it into the runs folder) and shows the bundled results; the bundled
files are never written to. examples/gallery/build_gallery.py regenerates them with
the real backend.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from pathlib import Path

from g4usim_gui.core import install_layout
from g4usim_gui.core import wizard


@dataclass(frozen=True)
class Example:
    id: str
    title: str
    summary: str
    tags: tuple[str, ...]
    scenario: str
    overrides: dict = field(default_factory=dict)
    plot: str = ""                         # Results / Plots data set key shown first
    scan_parameter: str = ""               # scan examples: core.scan parameter key
    scan_values: str = ""                  # and values (core.scan.expand_values text)
    scan_quantity: tuple[str, str] = ("", "")   # (scorer, quantity) plotted first

    def spec(self) -> wizard.WizardSpec:
        return replace(wizard.default_spec(self.scenario), project_name=self.id, **self.overrides)

    def folder(self, root: Path | None = None) -> Path:
        return (root or gallery_root()) / self.id

    def output_dir(self, root: Path | None = None) -> Path:
        return self.folder(root) / "output"

    def scan_dir(self, root: Path | None = None) -> Path:
        return self.folder(root) / "scan"

    def thumbnail(self, root: Path | None = None) -> Path:
        return self.folder(root) / "thumbnail.png"

    @property
    def is_scan(self) -> bool:
        return bool(self.scan_parameter)

    def has_results(self, root: Path | None = None) -> bool:
        if self.is_scan:
            return (self.scan_dir(root) / "scan.json").is_file()
        return (self.output_dir(root) / "run_summary.txt").is_file()


EXAMPLES: tuple[Example, ...] = (
    Example("bragg_peak", "Proton Bragg peak",
            "150 MeV protons in a water phantom cut into 40 slabs: the dose per slab rises to the "
            "Bragg peak near 158 mm and falls to almost zero behind it.",
            ("proton", "dose", "water"), "depth_dose", {"events": 2000},
            plot="scorer/dose/raw_dose/r0"),
    Example("shielding_slab", "Shielding slab",
            "70 MeV protons slowed down in 10 mm of aluminium: the 300 um silicon detector behind "
            "the shield sees a larger, broadened deposit; dose and track-length fluence are scored too.",
            ("proton", "shielding", "fluence"), "shielding",
            {"events": 5000, "energy_MeV": 70.0, "thickness_mm": 10.0},
            plot="event_edep/r0"),
    Example("silicon_landau", "Silicon Landau distribution",
            "100 MeV protons crossing a 300 um silicon pad: the per-event energy deposit follows "
            "the asymmetric Landau-Vavilov distribution with its long high-energy tail.",
            ("proton", "silicon", "spectrum"), "silicon_detector", {"events": 20000},
            plot="event_edep/r0"),
    Example("nai_gamma", "NaI gamma spectrum",
            "662 keV photons (the Cs-137 line) from an isotropic point source on a 3 in x 3 in NaI "
            "crystal: photopeak, Compton continuum and edge, without detector resolution.",
            ("gamma", "spectrum", "NaI"), "gamma_spectrometer", {"events": 20000},
            plot="event_edep/r0"),
    Example("energy_scan", "Proton energy scan",
            "A parameter scan of the proton energy from 20 to 200 MeV on a 300 um silicon pad: the "
            "mean deposit falls with energy as the stopping power does.",
            ("scan", "proton", "silicon"), "silicon_detector", {"events": 2000},
            scan_parameter="source.energy", scan_values="20, 35, 50, 100, 200 MeV",
            scan_quantity=("edep", "raw_edep")),
)


def gallery_root() -> Path:
    return install_layout.application_root() / "examples" / "gallery"


def find(example_id: str) -> Example | None:
    return next((example for example in EXAMPLES if example.id == example_id), None)
