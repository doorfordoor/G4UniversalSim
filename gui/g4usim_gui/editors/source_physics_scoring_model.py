from __future__ import annotations

import math
import re
from dataclasses import asdict, dataclass, field

from g4usim_gui.core.capability_messages import capability_message
from g4usim_gui.core.diagnostics import EditorLocation, emit_diagnostic, reset_diagnostics
from g4usim_gui.core.config_schema import check_value, spec, quantity
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


def _record_model(model, editor: str, code: str, severity: str, message: str, field: str) -> None:
    value = getattr(model, field, None)
    if isinstance(value, float) and not math.isfinite(value):
        value = {"invalid_float": repr(value)}
    related = ()
    if code == "hist_range.order":
        related = (EditorLocation("scoring", "hist_min"),)
    elif code == "histogram.output_required":
        related = (EditorLocation("scoring", "weighted_histogram"),)
    emit_diagnostic(model, f"{editor}.{code}", severity, message,
                    origin=f"{editor}.editor", editor=editor, field=field,
                    identity_parameters={"value": value}, related_locations=related)


def validate_source_model(model: SourceEditableModel) -> SourceEditableModel:
    reset_diagnostics(model)
    model.errors = []
    model.warnings = []
    _sync_source_legacy_fields(model)
    if not model.enabled:
        _record_model(model, 'source', 'disabled', 'warning', "Source is disabled in the editor, but G4UniversalSim still requires a primary source.", 'enabled')
    if not model.preset.strip():
        _record_model(model, 'source', 'preset.required', 'error', "preset is required", 'preset')
    elif model.preset not in SOURCE_PRESETS:
        _record_model(model, 'source', 'preset.unknown', 'warning', f"preset '{model.preset}' is not in the GUI quick list; final validation happens in C++", 'preset')
    if not model.particle.strip():
        _record_model(model, 'source', 'particle.required', 'error', "particle is required", 'particle')
    if not model.energy.strip():
        _record_model(model, 'source', 'energy.required', 'error', "energy is required", 'energy')
    else:
        problem = check_value("source", "energy", model.energy)
        if problem:
            _record_model(model, 'source', 'energy.invalid', 'error', problem, 'energy')
    for name, text in (("energy", model.energy), ("position", model.position),
                       ("direction", model.direction), ("radius", model.radius),
                       ("halfx", model.halfx), ("halfy", model.halfy)):
        if _contains_nonfinite_number(text):
            _record_model(model, 'source', 'value.nonfinite', 'error', f"{name} must contain only finite numeric values", name)
    mode = model.position_mode.strip().lower()
    shape = model.source_shape.strip().lower() or ("point" if mode == "point" else "circle")
    angular = model.angular_mode.strip().lower()
    if mode not in {"point", "plane"}:
        _record_model(model, 'source', 'position_mode.unsupported', 'error', "position mode must be point or plane in this GUI MVP", 'position_mode')
    if shape not in {"point", "circle", "rectangle", "square", "annulus"}:
        _record_model(model, 'source', 'shape.unknown', 'error', "source shape must be point, circle, rectangle, square, or annulus", 'source_shape')
    if not _has_three_components(model.position):
        _record_model(model, 'source', 'position.components', 'error', "position should contain at least 3 components", 'position')
    if mode == "point" and shape != "point":
        _record_model(model, 'source', 'shape.ignored', 'warning', "point source mode ignores source_shape; it will be treated as a point", 'source_shape')
    if mode == "plane":
        if shape == "circle" and model.radius.strip():
            problem = check_value("source", "radius", model.radius)
            if problem:
                _record_model(model, 'source', 'radius.invalid', 'error', problem, 'radius')
        if not _has_three_components(model.normal):
            _record_model(model, 'source', 'normal.components', 'error', "plane normal should contain 3 components", 'normal')
        elif not _direction_is_nonzero(model.normal):
            _record_model(model, 'source', 'normal.zero', 'error', "plane normal cannot be all zero", 'normal')
        if shape in {"circle", "annulus"} and not model.radius.strip():
            _record_model(model, 'source', 'radius.required', 'error', "plane circle/annulus source requires radius", 'radius')
        if shape == "annulus" and not model.inner_radius.strip():
            _record_model(model, 'source', 'inner_radius.required', 'error', "annulus source requires inner_radius", 'inner_radius')
        if shape in {"rectangle", "square"}:
            if not model.halfx.strip():
                _record_model(model, 'source', 'halfx.required', 'error', "rectangle/square source requires halfx", 'halfx')
            elif shape == "rectangle" and not _is_positive_length(model.halfx):
                _record_model(model, 'source', 'halfx.positive', 'error', "rectangle source halfx must be a finite positive length (nm/um/mm/cm/m)", 'halfx')
            if shape == "rectangle" and not model.halfy.strip():
                _record_model(model, 'source', 'halfy.required', 'error', "rectangle source requires halfy", 'halfy')
            elif shape == "rectangle" and not _is_positive_length(model.halfy):
                _record_model(model, 'source', 'halfy.positive', 'error', "rectangle source halfy must be a finite positive length (nm/um/mm/cm/m)", 'halfy')
        if shape == "rectangle" and model.normal.replace(" ", "") != "0,0,1":
            _record_model(model, 'source', 'normal.xy_only', 'error', "plane rectangle currently uses the XY plane; normal must be 0,0,1", 'normal')
        if shape in {"square", "annulus"}:
            _record_model(model, 'source', 'shape.preview_only', 'error', f"plane {shape} source is preview-only in this GUI; the backend supports it via [source] shape = {shape} in a hand-written main INI", 'source_shape')
    if not _has_three_components(model.direction):
        _record_model(model, 'source', 'direction.components', 'error', "direction should contain at least 3 components", 'direction')
    elif not _direction_is_nonzero(model.direction):
        _record_model(model, 'source', 'direction.zero', 'error', "direction cannot be all zero", 'direction')
    if angular == "beam":
        model.angular_mode = "fixed"
        angular = "fixed"
    if angular not in {"fixed", "isotropic", "cone", "cosine", "focused"}:
        _record_model(model, 'source', 'angular_mode.unknown', 'error', "angular mode must be fixed, isotropic, cone, cosine, or focused", 'angular_mode')
    for label, value in [
        ("theta_min", model.theta_min),
        ("theta_max", model.theta_max),
        ("phi_min", model.phi_min),
        ("phi_max", model.phi_max),
    ]:
        if value.strip() and not _looks_like_angle(value):
            _record_model(model, 'source', 'angle.invalid', 'error', f"{label} should be an angle such as '0 deg' or '0 rad'", label)
    if angular == "cone":
        if not model.cone_half_angle.strip():
            _record_model(model, 'source', 'cone_half_angle.required', 'error', "cone angular mode requires cone_half_angle", 'cone_half_angle')
        elif not _looks_like_angle(model.cone_half_angle):
            _record_model(model, 'source', 'cone_half_angle.invalid', 'error', "cone_half_angle should be an angle such as '5 deg'", 'cone_half_angle')
        _record_model(model, 'source', 'cone.preview_only', 'error', "cone angular mode is preview-only in this GUI; the backend supports it via [source] angular = isotropic with max_theta in a hand-written main INI", 'angular_mode')
    if angular in {"cosine", "focused"}:
        _record_model(model, 'source', 'angular_mode.preview_only', 'error', f"{angular} angular mode is preview-only in this GUI; the backend supports [source] angular = {'cos' if angular == 'cosine' else angular} in a hand-written main INI", 'angular_mode')
    if angular == "focused" and not _has_three_components(model.focus_point):
        _record_model(model, 'source', 'focus.components', 'error', "focused angular mode requires focus_point with 3 components", 'focus_point')
    if model.preview_ray_count <= 0:
        _record_model(model, 'source', 'preview_rays.positive', 'error', "preview_ray_count must be > 0", 'preview_ray_count')
    if model.confine_volume.strip():
        _record_model(model, 'source', 'confine.not_generated', 'warning', "confine_volume is not generated by this GUI; the backend supports [source] confine with position_type = volume in a hand-written main INI", 'confine_volume')
    if mode == "plane" and shape == "circle":
        _record_model(model, 'source', 'plane.limited', 'warning', "plane circle source is generated as position_type=plane + radius; plane orientation is limited by the C++ backend", 'normal')
    return model


def validate_physics_model(model: PhysicsEditableModel) -> PhysicsEditableModel:
    reset_diagnostics(model)
    model.errors = []
    model.warnings = []
    if model.mode != "reference":
        _record_model(model, 'physics', 'mode.unsupported', 'error', "manual physics mode is not generated by this GUI MVP", 'mode')
    if not model.reference_list.strip():
        _record_model(model, 'physics', 'reference.required', 'error', "reference list is required", 'reference_list')
    elif model.reference_list not in REFERENCE_LIST_CANDIDATES:
        _record_model(model, 'physics', 'reference.unknown', 'warning', "reference list is not in the GUI quick list; Geant4 validates it at initialization", 'reference_list')
    if not model.default_cut.strip():
        _record_model(model, 'physics', 'cut.required', 'error', "default cut is required", 'default_cut')
    elif check_value("physics", "default_cut", model.default_cut):
        _record_model(model, 'physics', 'cut.invalid', 'error', check_value("physics", "default_cut", model.default_cut), 'default_cut')
    elif not _looks_like_value_with_unit(model.default_cut):
        _record_model(model, 'physics', 'cut.unit_hint', 'warning', "default cut should include a value and unit, for example '1 mm'", 'default_cut')
    if model.enable_biasing_physics:
        _record_model(model, 'physics', 'biasing.not_editable', 'error', "Biasing rules cannot be edited or generated here. Disable the hook for generated packages, or use external config/macro with explicit process-level rules.", 'enable_biasing_physics')
    if model.extra_modules:
        _record_model(model, 'physics', 'extra_modules.not_editable', 'warning', "extra modules are preserved in the model but not edited by this MVP", 'extra_modules')
    if model.manual_modules:
        _record_model(model, 'physics', 'manual_modules.not_generated', 'warning', "manual modules are preserved in the model but not generated by this MVP", 'manual_modules')
    return model


def validate_scoring_model(model: ScoringEditableModel) -> ScoringEditableModel:
    reset_diagnostics(model)
    model.errors = []
    model.warnings = []
    if model.enabled and not any([model.hits, model.event_edep, model.edep, model.dose, model.fluence]):
        _record_model(model, 'scoring', 'output.required', 'error', "enabled scoring requires at least one of hits/event_edep/edep/dose/fluence", 'enabled')
    if model.hist_bins <= 0:
        _record_model(model, 'scoring', 'hist_bins.positive', 'error', "histogram bins must be > 0", 'hist_bins')
    if not model.hist_min.strip():
        _record_model(model, 'scoring', 'hist_min.required', 'error', "histogram min is required", 'hist_min')
    if not model.hist_max.strip():
        _record_model(model, 'scoring', 'hist_max.required', 'error', "histogram max is required", 'hist_max')
    for key, value in (("bins", str(model.hist_bins)), ("min", model.hist_min), ("max", model.hist_max)):
        if value.strip():
            problem = check_value("scoring.edep", key, value)
            if problem:
                _record_model(model, 'scoring', 'hist_value.invalid', 'error', problem, 'hist_' + key)
    low, high = quantity(model.hist_min, "energy"), quantity(model.hist_max, "energy")
    if low is not None and high is not None and high <= low:
        _record_model(model, 'scoring', 'hist_range.order', 'error', "histogram max must be greater than min", 'hist_max')
    if not model.edep and (model.raw_histogram or model.weighted_histogram):
        _record_model(model, 'scoring', 'histogram.edep_disabled', 'warning', "edep scorer is disabled; edep histogram settings will not produce output", 'edep')
    if model.edep and not (model.raw_histogram or model.weighted_histogram):
        _record_model(model, 'scoring', 'histogram.output_required', 'error', "edep histogram output requires raw_histogram or weighted_histogram", 'raw_histogram')
    if model.let:
        _record_model(model, 'scoring', 'let.unsupported', 'error', capability_message("scoring.let.unsupported"), 'let')
    if model.dose and not model.auto_create_default_scorers:
        _record_model(model, 'scoring', 'dose.requires_default', 'error', "Dose requires auto-create default scorers", 'auto_create_default_scorers')
    if model.fluence and not model.auto_create_default_scorers:
        _record_model(model, 'scoring', 'fluence.requires_default', 'error', "Fluence requires auto-create default scorers", 'auto_create_default_scorers')
    # the backend's limits come from the configuration schema; the GUI keeps its own lower maximum
    trajectories = spec("output", "trajectories")
    gui_max = trajectories.data.get("gui", {}).get("max")
    problem = (check_value("output", "trajectories", str(model.trajectory_events))
               if isinstance(model.trajectory_events, int) else "[output]/trajectories must be an integer")
    if problem or (gui_max is not None and model.trajectory_events > gui_max):
        _record_model(model, 'scoring', 'trajectories.range', 'error', f"trajectories must be 0 (off) to {gui_max} events", 'trajectory_events')
    elif model.trajectory_events > 100:
        _record_model(model, 'scoring', 'trajectories.size_hint', 'warning', "trajectory files grow quickly with secondaries; use a few events", 'trajectory_events')
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
    return check_value("source", "halfx", value) is None


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
