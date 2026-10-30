"""Guided "new simulation" wizard model (roadmap C2), without Qt.

A WizardSpec (scenario -> materials/geometry -> source -> run) is turned into the
editor models the Configuration page already uses: a dirty hierarchical
GeometryDocument, SourceEditableModel, PhysicsEditableModel, ScoringEditableModel
and RunSettings. Package generation, validation and running then follow the normal
generated-mode path (validate_config_builder -> create_run_package -> backend), and
the full editors stay available as the advanced mode. The wizard only offers what
those editors can generate: NIST materials, box/tubs volumes, point (fixed or
isotropic) and rectangular plane sources, reference physics lists, and the
hits/Edep/Dose/Fluence scorers.

Scenarios (beam along +z, target face at z = 0, source 10 mm upstream):
  single_target       one sensitive box
  depth_dose          a phantom cut into N sensitive slabs (dose per slab = depth dose)
  shielding           a shield slab, 1 mm gap, sensitive detector slab behind it
  silicon_detector    a sensitive silicon pad (energy deposit spectrum)
  gamma_spectrometer  a sensitive scintillator cylinder, isotropic point source
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field, replace

from g4usim_gui.core.config_schema import check_value
from g4usim_gui.core.project import G4USimProject
from g4usim_gui.editors.geometry_editor_model import GeometryDocument, HierarchicalVolumeRow
from g4usim_gui.editors.source_physics_scoring_model import (
    PhysicsEditableModel,
    ScoringEditableModel,
    SourceEditableModel,
    validate_physics_model,
    validate_scoring_model,
    validate_source_model,
)
from g4usim_gui.models.run_model import RunSettings

SCENARIOS = ("single_target", "depth_dose", "shielding", "silicon_detector", "gamma_spectrometer")
# Geant4 NIST materials the backend builds without a materials file entry.
MATERIALS = ("G4_WATER", "G4_Si", "G4_Al", "G4_Cu", "G4_W", "G4_Pb", "G4_Fe", "G4_Ti", "G4_POLYETHYLENE",
             "G4_PLASTIC_SC_VINYLTOLUENE", "G4_SODIUM_IODIDE", "G4_CESIUM_IODIDE", "G4_BGO", "G4_Ge",
             "G4_SILICON_DIOXIDE", "G4_KAPTON", "G4_AIR", "G4_Galactic")
WORLD_MATERIALS = ("G4_Galactic", "G4_AIR")
PARTICLES = ("proton", "e-", "e+", "gamma", "neutron", "alpha", "mu-", "pi+")
SOURCE_KINDS = ("pencil", "broad", "isotropic")      # point fixed +z, rectangle plane +z, point isotropic
PHYSICS = ("FTFP_BERT_EMZ", "FTFP_BERT", "QGSP_BIC", "FTFP_BERT_HP", "Shielding", "QGSP_BERT")
SOURCE_GAP_MM = 10.0


@dataclass
class WizardSpec:
    scenario: str = "single_target"
    project_name: str = "new_simulation"
    world_material: str = "G4_Galactic"
    target_material: str = "G4_WATER"
    thickness_mm: float = 10.0          # target / phantom / shield / pad thickness (crystal length for gamma)
    lateral_mm: float = 50.0            # lateral size (crystal diameter for gamma)
    slabs: int = 20                     # depth_dose
    detector_material: str = "G4_Si"    # shielding
    detector_thickness_mm: float = 0.3  # shielding
    particle: str = "proton"
    energy_MeV: float = 100.0
    source_kind: str = "pencil"
    physics: str = "FTFP_BERT_EMZ"
    events: int = 1000
    threads: int = 2
    seed: int | None = 12345
    hits: bool = False
    event_edep: bool = True
    dose: bool = True
    fluence: bool = False


def default_spec(scenario: str) -> WizardSpec:
    base = WizardSpec(scenario=scenario, project_name=scenario)
    if scenario == "depth_dose":
        return replace(base, target_material="G4_WATER", thickness_mm=200.0, lateral_mm=100.0, slabs=40,
                       particle="proton", energy_MeV=150.0, physics="QGSP_BIC", source_kind="broad")
    if scenario == "shielding":
        return replace(base, target_material="G4_Al", thickness_mm=5.0, lateral_mm=100.0, particle="proton",
                       energy_MeV=100.0, source_kind="broad", fluence=True)
    if scenario == "silicon_detector":
        return replace(base, target_material="G4_Si", thickness_mm=0.3, lateral_mm=10.0, particle="proton",
                       energy_MeV=100.0)
    if scenario == "gamma_spectrometer":
        return replace(base, target_material="G4_SODIUM_IODIDE", thickness_mm=76.2, lateral_mm=76.2,
                       particle="gamma", energy_MeV=0.662, source_kind="isotropic", world_material="G4_AIR",
                       dose=False, events=10000)
    return replace(base, target_material="G4_WATER")


def validate_spec(spec: WizardSpec) -> list[tuple[str, dict]]:
    """Errors as (message template, values) pairs, translated by the GUI."""
    return [(template, values) for _field, _code, template, values in validate_spec_records(spec)]


def validate_spec_records(spec: WizardSpec) -> list[tuple[str, str, str, dict]]:
    """The same rules with producer-owned fields and language-independent codes."""
    errors: list[tuple[str, str, str, dict]] = []

    def positive(value: float, label: str, field_name: str) -> None:
        if not (isinstance(value, (int, float)) and math.isfinite(value) and value > 0):
            errors.append((field_name, "positive", "{field} must be a finite positive number.", {"field": label}))

    if spec.scenario not in SCENARIOS:
        errors.append(("scenario", "scenario", "Unknown scenario {scenario}.", {"scenario": spec.scenario}))
    if not spec.project_name.strip():
        errors.append(("project_name", "name", "A simulation name is required.", {}))
    for field_name, label, material, allowed in (("target_material", "target material", spec.target_material, MATERIALS),
                                     ("world_material", "world material", spec.world_material, WORLD_MATERIALS),
                                     ("detector_material", "detector material", spec.detector_material, MATERIALS)):
        if material not in allowed:
            errors.append((field_name, "material", "{field} {value} is not offered by the wizard.", {"field": label, "value": material}))
    positive(spec.thickness_mm, "thickness", "thickness_mm")
    positive(spec.lateral_mm, "lateral size", "lateral_mm")
    positive(spec.energy_MeV, "energy", "energy_MeV")
    if spec.scenario == "shielding":
        positive(spec.detector_thickness_mm, "detector thickness", "detector_thickness_mm")
    if spec.scenario == "depth_dose" and not (1 <= spec.slabs <= 200):
        errors.append(("slabs", "slabs", "The phantom needs 1 to 200 slabs.", {}))
    if spec.particle not in PARTICLES:
        errors.append(("particle", "particle", "Particle {value} is not offered by the wizard.", {"value": spec.particle}))
    if spec.source_kind not in SOURCE_KINDS:
        errors.append(("source_kind", "source_kind", "Source type {value} is not offered by the wizard.", {"value": spec.source_kind}))
    if spec.physics not in PHYSICS:
        errors.append(("physics", "physics", "Physics list {value} is not offered by the wizard.", {"value": spec.physics}))
    if spec.events < 1:
        errors.append(("events", "events", "At least one event is required.", {}))
    if spec.threads < 1:
        errors.append(("threads", "threads", "At least one thread is required.", {}))
    if spec.seed is not None and check_value("run", "seed", str(spec.seed)):
        errors.append(("seed", "seed", "The seed must be an integer from 0 to 2147483647.", {}))
    if not any((spec.hits, spec.event_edep, spec.dose, spec.fluence)):
        errors.append(("outputs", "outputs", "Choose at least one output.", {}))
    if spec.target_material == spec.world_material:
        errors.append(("target_material", "world_material_conflict", "The target material must differ from the world material.", {}))
    return errors


@dataclass
class WizardResult:
    geometry: GeometryDocument
    source: SourceEditableModel
    physics: PhysicsEditableModel
    scoring: ScoringEditableModel
    run: RunSettings
    sensitive_volumes: list[str] = field(default_factory=list)


def _box(name: str, material: str, x: float, y: float, z: float, z_centre: float, sensitive: bool) -> HierarchicalVolumeRow:
    return HierarchicalVolumeRow(name=name, parent="world", shape="box", size=f"{x:g} mm, {y:g} mm, {z:g} mm",
                                 material=material, position=f"0 mm, 0 mm, {z_centre:g} mm",
                                 rotation="0 deg, 0 deg, 0 deg", sensitive=sensitive)


def build(spec: WizardSpec) -> WizardResult:
    errors = validate_spec(spec)
    if errors:
        raise ValueError("; ".join(template.format(**values) for template, values in errors))
    side, t = spec.lateral_mm, spec.thickness_mm
    volumes: list[HierarchicalVolumeRow] = []
    if spec.scenario == "depth_dose":
        width = t / spec.slabs
        for i in range(spec.slabs):
            volumes.append(_box(f"Slab{i:03d}", spec.target_material, side, side, width, (i + 0.5) * width, True))
        extent_z = t
    elif spec.scenario == "shielding":
        volumes.append(_box("Shield", spec.target_material, side, side, t, t / 2, False))
        d = spec.detector_thickness_mm
        volumes.append(_box("Detector", spec.detector_material, side, side, d, t + 1.0 + d / 2, True))
        extent_z = t + 1.0 + d
    elif spec.scenario == "gamma_spectrometer":
        volumes.append(HierarchicalVolumeRow(
            name="Crystal", parent="world", shape="tubs",
            parameters=f"0 mm, {side / 2:g} mm, {t / 2:g} mm, 0 deg, 360 deg", material=spec.target_material,
            position=f"0 mm, 0 mm, {t / 2:g} mm", rotation="0 deg, 0 deg, 0 deg", sensitive=True))
        extent_z = t
    else:
        name = "Pad" if spec.scenario == "silicon_detector" else "Target"
        volumes.append(_box(name, spec.target_material, side, side, t, t / 2, True))
        extent_z = t
    world = 2 * max(side, extent_z + SOURCE_GAP_MM) + 200.0
    volumes.insert(0, HierarchicalVolumeRow(name="world", shape="box",
                                            size=f"{world:g} mm, {world:g} mm, {world:g} mm",
                                            material=spec.world_material))
    geometry = GeometryDocument(mode="hierarchical", volumes=volumes)
    geometry.is_dirty = True

    source = SourceEditableModel(preset="proton_beam", particle=spec.particle, energy=f"{spec.energy_MeV:g} MeV",
                                 position=f"0, 0, {-SOURCE_GAP_MM:g} mm", direction="0,0,1")
    if spec.source_kind == "broad":
        source.position_mode = source.position_type = "plane"
        source.source_shape = "rectangle"
        source.halfx = source.halfy = f"{0.4 * side:g} mm"   # inside the target face (no edge effects)
        source.normal = "0,0,1"
    elif spec.source_kind == "isotropic":
        source.angular_mode = "isotropic"
    validate_source_model(source)
    physics = PhysicsEditableModel(reference_list=spec.physics, default_cut="0.7 mm")
    validate_physics_model(physics)
    scoring = ScoringEditableModel(hits=spec.hits, event_edep=spec.event_edep, edep=True, dose=spec.dose,
                                   fluence=spec.fluence, hist_bins=200, hist_min="0 eV",
                                   hist_max=f"{max(spec.energy_MeV * 1.05, 0.01):g} MeV")
    validate_scoring_model(scoring)
    for model in (source, physics, scoring):
        model.is_dirty = True
        if model.errors:
            raise ValueError("; ".join(model.errors))
    run = RunSettings(run_name=spec.project_name.strip(), threads=spec.threads, seed=spec.seed,
                      beam_on=spec.events, check_overlaps=True, dry_run=False)
    return WizardResult(geometry, source, physics, scoring, run,
                        [v.name for v in volumes if v.sensitive])


def apply_to_project(project: G4USimProject, result: WizardResult) -> None:
    """Put the wizard result into the project in place (generated mode)."""
    project.projectName = result.run.run_name
    project.runName = result.run.run_name
    project.runInputMode = "generated"
    project.configPath = ""
    project.macroPath = ""
    project.threads = result.run.threads
    project.seed = "" if result.run.seed is None else str(result.run.seed)
    project.runSettings = result.run
    project.geometrySettings.template = "hierarchical"
    if not project.geometrySettings.config_path:   # source fallback the validator requires
        project.geometrySettings.config_path = project.pathSettings.geometry_config
    project.geometryEditor = result.geometry
    project.sourceEditor = result.source
    project.physicsEditor = result.physics
    project.scoringEditor = result.scoring
    project.sourceSettings = result.source.to_settings()
    project.physicsSettings = result.physics.to_settings()
    project.scoringSettings = result.scoring.to_settings()


def summary(spec: WizardSpec) -> list[tuple[str, dict]]:
    """What will be simulated and written, as (template, values) lines for the GUI."""
    lines: list[tuple[str, dict]] = [
        ("Scenario: {scenario}", {"scenario": spec.scenario}),
        ("World: {material}", {"material": spec.world_material}),
    ]
    if spec.scenario == "depth_dose":
        lines.append(("Phantom: {material}, {thickness} mm deep in {slabs} sensitive slabs, {side} mm wide",
                      {"material": spec.target_material, "thickness": f"{spec.thickness_mm:g}",
                       "slabs": spec.slabs, "side": f"{spec.lateral_mm:g}"}))
    elif spec.scenario == "shielding":
        lines.append(("Shield: {material}, {thickness} mm; detector: {detector}, {dthickness} mm, 1 mm behind",
                      {"material": spec.target_material, "thickness": f"{spec.thickness_mm:g}",
                       "detector": spec.detector_material, "dthickness": f"{spec.detector_thickness_mm:g}"}))
    elif spec.scenario == "gamma_spectrometer":
        lines.append(("Crystal: {material}, {diameter} mm diameter x {length} mm",
                      {"material": spec.target_material, "diameter": f"{spec.lateral_mm:g}",
                       "length": f"{spec.thickness_mm:g}"}))
    else:
        lines.append(("Target: {material}, {thickness} mm thick, {side} mm wide",
                      {"material": spec.target_material, "thickness": f"{spec.thickness_mm:g}",
                       "side": f"{spec.lateral_mm:g}"}))
    lines.append(("Source: {particle} {energy} MeV, {kind}, {gap} mm in front of the target",
                  {"particle": spec.particle, "energy": f"{spec.energy_MeV:g}", "kind": spec.source_kind,
                   "gap": f"{SOURCE_GAP_MM:g}"}))
    outputs = [name for name, on in (("hits", spec.hits), ("event_edep", spec.event_edep), ("Edep", True),
                                     ("Dose", spec.dose), ("Fluence", spec.fluence)) if on]
    lines.append(("Physics: {physics}; outputs: {outputs}", {"physics": spec.physics, "outputs": ", ".join(outputs)}))
    lines.append(("Run: {events} events, {threads} threads, seed {seed}",
                  {"events": spec.events, "threads": spec.threads, "seed": spec.seed}))
    return lines
