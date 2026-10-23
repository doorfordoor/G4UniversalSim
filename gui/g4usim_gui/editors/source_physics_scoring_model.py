from __future__ import annotations

import math
import re
from dataclasses import asdict, dataclass, field

from g4usim_gui.core.capability_messages import capability_message
from g4usim_gui.core.config_schema import check_value, spec
from g4usim_gui.models.physics_model import PhysicsSettings
from g4usim_gui.models.scoring_model import ScoringSettings
from g4usim_gui.models.source_model import SourceSettings


REFERENCE_LIST_CANDIDATES = [
    "FTFP_BERT",
    "FTFP_BERT_EMZ",
    "FTFP_BERT_EMY",
    "FTFP_BERT_HP",
    "QGSP_BERT",
    "QGSP_BIC",
    "Shielding",
]


SOURCE_PRESETS = [
    "proton_beam",
    "mono_proton",
    "neutron_beam",
    "gamma_beam",
    "isotropic_neutron",
    "plane_proton_beam",
]


@dataclass
class SourceEditableModel:
    preset: str = "proton_beam"
    particle: str = "proton"
    energy: str = "10 MeV"
    position_mode: str = "point"
    position_type: str = "point"
    position: str = "0,0,-1 mm"
    direction: str = "0,0,1"
    source_shape: str = "point"
    radius: str = ""
    inner_radius: str = ""
    halfx: str = ""
    halfy: str = ""
    halfz: str = ""
    normal: str = "0,0,1"
    rotation1: str = "1,0,0"
    rotation2: str = "0,1,0"
    confine_volume: str = ""
    center: str = ""
    angular_mode: str = "fixed"
    theta_min: str = "0 deg"
    theta_max: str = "180 deg"
    phi_min: str = "0 deg"
    phi_max: str = "360 deg"
    cone_half_angle: str = "5 deg"
    focus_point: str = "0,0,0 mm"
    random_seed_preview: int = 12345
    preview_ray_count: int = 12
    enabled: bool = True
    is_dirty: bool = False
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @classmethod
    def from_settings(cls, settings: SourceSettings) -> "SourceEditableModel":
        model = cls(
            preset=settings.preset,
            particle=settings.particle,
            energy=settings.energy,
            position_mode="point",
            position=settings.position,
            direction=settings.direction,
        )
        validate_source_model(model)
        return model

    def to_settings(self) -> SourceSettings:
        return SourceSettings(
            preset=self.preset,
            particle=self.particle,
            energy=self.energy,
            position=self.position,
            direction=self.direction,
        )


@dataclass
class PhysicsEditableModel:
    mode: str = "reference"
    reference_list: str = "FTFP_BERT_EMZ"
    default_cut: str = "1 mm"
    enable_biasing_physics: bool = False
    extra_modules: list[str] = field(default_factory=list)
    manual_modules: list[str] = field(default_factory=list)
    particle_cuts: dict[str, str] = field(default_factory=dict)
    is_dirty: bool = False
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @classmethod
    def from_settings(cls, settings: PhysicsSettings) -> "PhysicsEditableModel":
        model = cls(
            reference_list=settings.reference,
            default_cut=settings.default_cut,
            enable_biasing_physics=settings.enable_biasing,
        )
        validate_physics_model(model)
        return model

    def to_settings(self) -> PhysicsSettings:
        return PhysicsSettings(
            reference=self.reference_list,
            default_cut=self.default_cut,
            enable_biasing=self.enable_biasing_physics,
        )


@dataclass
class ScoringEditableModel:
    enabled: bool = True
    hits: bool = True
    event_edep: bool = True
    edep: bool = True
    raw_histogram: bool = True
    weighted_histogram: bool = True
    hist_bins: int = 100
    hist_min: str = "0 eV"
    hist_max: str = "10 MeV"
    volume_summary: bool = True
    particle_summary: bool = True
    let: bool = False
    dose: bool = False
    fluence: bool = False
    trajectory_events: int = 0     # [output] trajectories (0 = off)
    auto_create_default_scorers: bool = True
    verbose: int = 1
    is_dirty: bool = False
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @classmethod
    def from_settings(cls, settings: ScoringSettings) -> "ScoringEditableModel":
        model = cls(
            enabled=settings.enabled,
            hits=settings.hits,
            event_edep=settings.event_edep,
            edep=settings.edep,
            dose=settings.dose,
            fluence=settings.fluence,
            trajectory_events=settings.trajectory_events,
            hist_bins=settings.hist_bins,
            hist_min=settings.hist_min,
            hist_max=settings.hist_max,
        )
        validate_scoring_model(model)
        return model

    def to_settings(self) -> ScoringSettings:
        return ScoringSettings(
            enabled=self.enabled,
            hits=self.hits,
            event_edep=self.event_edep,
            edep=self.edep,
            dose=self.dose,
            fluence=self.fluence,
            trajectory_events=self.trajectory_events,
            hist_bins=self.hist_bins,
            hist_min=self.hist_min,
            hist_max=self.hist_max,
        )


def validate_source_model(model: SourceEditableModel) -> SourceEditableModel:
    model.errors = []
    model.warnings = []
    _sync_source_legacy_fields(model)
    if not model.enabled:
        model.warnings.append("Source is disabled in the editor, but G4UniversalSim still requires a primary source.")
    if not model.preset.strip():
        model.errors.append("preset is required")
    elif model.preset not in SOURCE_PRESETS:
        model.warnings.append(f"preset '{model.preset}' is not in the GUI quick list; final validation happens in C++")
    if not model.particle.strip():
        model.errors.append("particle is required")
    if not model.energy.strip():
        model.errors.append("energy is required")
    for name, text in (("energy", model.energy), ("position", model.position),
                       ("direction", model.direction), ("radius", model.radius),
                       ("halfx", model.halfx), ("halfy", model.halfy)):
        if _contains_nonfinite_number(text):
            model.errors.append(f"{name} must contain only finite numeric values")
    mode = model.position_mode.strip().lower()
    shape = model.source_shape.strip().lower() or ("point" if mode == "point" else "circle")
    angular = model.angular_mode.strip().lower()
    if mode not in {"point", "plane"}:
        model.errors.append("position mode must be point or plane in this GUI MVP")
    if shape not in {"point", "circle", "rectangle", "square", "annulus"}:
        model.errors.append("source shape must be point, circle, rectangle, square, or annulus")
    if not _has_three_components(model.position):
        model.errors.append("position should contain at least 3 components")
    if mode == "point" and shape != "point":
        model.warnings.append("point source mode ignores source_shape; it will be treated as a point")
    if mode == "plane":
        if not _has_three_components(model.normal):
            model.errors.append("plane normal should contain 3 components")
        elif not _direction_is_nonzero(model.normal):
            model.errors.append("plane normal cannot be all zero")
        if shape in {"circle", "annulus"} and not model.radius.strip():
            model.errors.append("plane circle/annulus source requires radius")
        if shape == "annulus" and not model.inner_radius.strip():
            model.errors.append("annulus source requires inner_radius")
        if shape in {"rectangle", "square"}:
            if not model.halfx.strip():
                model.errors.append("rectangle/square source requires halfx")
            elif shape == "rectangle" and not _is_positive_length(model.halfx):
                model.errors.append("rectangle source halfx must be a finite positive length (nm/um/mm/cm/m)")
            if shape == "rectangle" and not model.halfy.strip():
                model.errors.append("rectangle source requires halfy")
            elif shape == "rectangle" and not _is_positive_length(model.halfy):
                model.errors.append("rectangle source halfy must be a finite positive length (nm/um/mm/cm/m)")
        if shape == "rectangle" and model.normal.replace(" ", "") != "0,0,1":
            model.errors.append("plane rectangle currently uses the XY plane; normal must be 0,0,1")
        if shape in {"square", "annulus"}:
            model.errors.append(f"plane {shape} source is preview-only in this GUI; the backend supports it via [source] shape = {shape} in a hand-written main INI")
    if not _has_three_components(model.direction):
        model.errors.append("direction should contain at least 3 components")
    elif not _direction_is_nonzero(model.direction):
        model.errors.append("direction cannot be all zero")
    if angular == "beam":
        model.angular_mode = "fixed"
        angular = "fixed"
    if angular not in {"fixed", "isotropic", "cone", "cosine", "focused"}:
        model.errors.append("angular mode must be fixed, isotropic, cone, cosine, or focused")
    for label, value in [
        ("theta_min", model.theta_min),
        ("theta_max", model.theta_max),
        ("phi_min", model.phi_min),
        ("phi_max", model.phi_max),
    ]:
        if value.strip() and not _looks_like_angle(value):
            model.errors.append(f"{label} should be an angle such as '0 deg' or '0 rad'")
    if angular == "cone":
        if not model.cone_half_angle.strip():
            model.errors.append("cone angular mode requires cone_half_angle")
        elif not _looks_like_angle(model.cone_half_angle):
            model.errors.append("cone_half_angle should be an angle such as '5 deg'")
        model.errors.append("cone angular mode is preview-only in this GUI; the backend supports it via [source] angular = isotropic with max_theta in a hand-written main INI")
    if angular in {"cosine", "focused"}:
        model.errors.append(f"{angular} angular mode is preview-only in this GUI; the backend supports [source] angular = {'cos' if angular == 'cosine' else angular} in a hand-written main INI")
    if angular == "focused" and not _has_three_components(model.focus_point):
        model.errors.append("focused angular mode requires focus_point with 3 components")
    if model.preview_ray_count <= 0:
        model.errors.append("preview_ray_count must be > 0")
    if model.confine_volume.strip():
        model.warnings.append("confine_volume is not generated by this GUI; the backend supports [source] confine with position_type = volume in a hand-written main INI")
    if mode == "plane" and shape == "circle":
        model.warnings.append("plane circle source is generated as position_type=plane + radius; plane orientation is limited by the C++ backend")
    return model


def validate_physics_model(model: PhysicsEditableModel) -> PhysicsEditableModel:
    model.errors = []
    model.warnings = []
    if model.mode != "reference":
        model.errors.append("manual physics mode is not generated by this GUI MVP")
    if not model.reference_list.strip():
        model.errors.append("reference list is required")
    elif model.reference_list not in REFERENCE_LIST_CANDIDATES:
        model.warnings.append("reference list is not in the GUI quick list; Geant4 validates it at initialization")
    if not model.default_cut.strip():
        model.errors.append("default cut is required")
    elif not _looks_like_value_with_unit(model.default_cut):
        model.warnings.append("default cut should include a value and unit, for example '1 mm'")
    if model.enable_biasing_physics:
        model.errors.append("Biasing rules cannot be edited or generated here. Disable the hook for generated packages, or use external config/macro with explicit process-level rules.")
    if model.extra_modules:
        model.warnings.append("extra modules are preserved in the model but not edited by this MVP")
    if model.manual_modules:
        model.warnings.append("manual modules are preserved in the model but not generated by this MVP")
    return model


def validate_scoring_model(model: ScoringEditableModel) -> ScoringEditableModel:
    model.errors = []
    model.warnings = []
    if model.enabled and not any([model.hits, model.event_edep, model.edep, model.dose, model.fluence]):
        model.errors.append("enabled scoring requires at least one of hits/event_edep/edep/dose/fluence")
    if model.hist_bins <= 0:
        model.errors.append("histogram bins must be > 0")
    if not model.hist_min.strip():
        model.errors.append("histogram min is required")
    if not model.hist_max.strip():
        model.errors.append("histogram max is required")
    if not model.edep and (model.raw_histogram or model.weighted_histogram):
        model.warnings.append("edep scorer is disabled; edep histogram settings will not produce output")
    if model.edep and not (model.raw_histogram or model.weighted_histogram):
        model.errors.append("edep histogram output requires raw_histogram or weighted_histogram")
    if model.let:
        model.errors.append(capability_message("scoring.let.unsupported"))
    if model.dose and not model.auto_create_default_scorers:
        model.errors.append("Dose requires auto-create default scorers")
    if model.fluence and not model.auto_create_default_scorers:
        model.errors.append("Fluence requires auto-create default scorers")
    # the backend's limits come from the configuration schema; the GUI keeps its own lower maximum
    trajectories = spec("output", "trajectories")
    gui_max = trajectories.data.get("gui", {}).get("max")
    problem = (check_value("output", "trajectories", str(model.trajectory_events))
               if isinstance(model.trajectory_events, int) else "[output]/trajectories must be an integer")
    if problem or (gui_max is not None and model.trajectory_events > gui_max):
        model.errors.append(f"trajectories must be 0 (off) to {gui_max} events")
    elif model.trajectory_events > 100:
        model.warnings.append("trajectory files grow quickly with secondaries; use a few events")
    return model


def source_model_to_snapshot(model: SourceEditableModel) -> dict:
    return asdict(model)


def physics_model_to_snapshot(model: PhysicsEditableModel) -> dict:
    return asdict(model)


def scoring_model_to_snapshot(model: ScoringEditableModel) -> dict:
    return asdict(model)


def _has_three_components(value: str) -> bool:
    tokens = [token for token in re.split(r"[,\s]+", value.strip()) if token]
    return len(tokens) >= 3


def _contains_nonfinite_number(value: str) -> bool:
    if re.search(r"(?i)(?<![a-z_])[+-]?(?:nan|inf(?:inity)?)(?![a-z_])", value):
        return True
    for token in re.finditer(r"(?<![a-zA-Z_])[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?", value):
        if not math.isfinite(float(token.group())):
            return True
    return False


def _direction_is_nonzero(value: str) -> bool:
    tokens = [token for token in re.split(r"[,\s]+", value.strip()) if token]
    try:
        numeric = [float(token) for token in tokens[:3]]
    except ValueError:
        return True
    return any(abs(item) > 0 for item in numeric)


def _looks_like_value_with_unit(value: str) -> bool:
    return bool(re.search(r"\d", value)) and bool(re.search(r"[A-Za-z]", value))


def _is_positive_length(value: str) -> bool:
    # Match the C++ UnitParser length vocabulary before package generation.
    match = re.fullmatch(
        r"\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)\s*(?:\*\s*)?(?:nm|um|mm|cm|m)?\s*",
        value,
    )
    if not match:
        return False
    number = float(match.group(1))
    return math.isfinite(number) and number > 0.0


def _looks_like_angle(value: str) -> bool:
    return bool(re.fullmatch(r"\s*[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?(?:\s*\*?\s*(?:deg|degree|degrees|rad|radian|radians))?\s*", value, flags=re.IGNORECASE))


def _sync_source_legacy_fields(model: SourceEditableModel) -> None:
    if not model.position_mode.strip() and model.position_type.strip():
        model.position_mode = model.position_type
    if not model.position_type.strip() and model.position_mode.strip():
        model.position_type = model.position_mode
    if model.position_mode.strip():
        model.position_type = model.position_mode
    if not model.source_shape.strip():
        model.source_shape = "point" if model.position_mode.strip().lower() == "point" else "circle"
