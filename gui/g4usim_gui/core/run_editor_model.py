"""J2 structured editing contract. Values are drafts, never runtime receipts.

No file is opened by this module. Resource identity/copying remains the package
service's responsibility; backend validation remains necessary for maps, spectra,
particle/process names and geometry bindings.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, fields, field
import math
import re
from uuid import uuid4

from g4usim_gui.core.config_schema import quantity
from g4usim_gui.core.i18n import ui_text


@dataclass
class GPSDefinition:
    # GUI identity is independent of editable INI section name and row order.
    # It never enters backend INI or claims a native GPS index.
    editor_id: str = field(default_factory=lambda: uuid4().hex)
    name: str = "beam"
    intensity: str = "1"
    particle: str = "proton"
    ion_z: str = "1"
    ion_a: str = "1"
    ion_charge: str = "1"
    ion_excitation: str = "0 keV"
    energy_type: str = "mono"
    energy: str = "10 MeV"
    energy_sigma: str = "1 MeV"
    energy_min: str = "1 MeV"
    energy_max: str = "10 MeV"
    alpha: str = "-2"
    ezero: str = "1 MeV"
    spectrum_file: str = ""
    position_type: str = "point"
    shape: str = "circle"
    center: str = "0,0,-1 mm"
    radius: str = "1 mm"
    inner_radius: str = "0.5 mm"
    halfx: str = "1 mm"
    halfy: str = "1 mm"
    halfz: str = "1 mm"
    beam_sigma: str = "1 mm"
    beam_sigma_x: str = "1 mm"
    beam_sigma_y: str = "1 mm"
    rot1: str = "1,0,0"
    rot2: str = "0,1,0"
    confine: str = ""
    angular: str = "fixed"
    direction: str = "0,0,1"
    min_theta: str = "0 deg"
    max_theta: str = "5 deg"
    angular_sigma: str = "1 deg"
    angular_sigma_x: str = "1 deg"
    angular_sigma_y: str = "1 deg"
    focus: str = "0,0,0 mm"


@dataclass
class RegionDefinition:
    name: str = "Target"
    volumes: str = ""
    gamma: str = ""
    electron: str = ""
    positron: str = ""
    proton: str = ""
    max_step: str = ""
    max_track_length: str = ""
    max_time: str = ""
    min_kinetic_energy: str = ""


@dataclass
class FieldDefinition:
    # Empty name is the single global field; named fields require volumes.
    name: str = ""
    volumes: str = ""
    magnetic: str = "0,0,1 T"
    electric: str = ""
    magnetic_map: str = ""
    electric_map: str = ""
    min_step: str = "0.01 mm"
    delta_chord: str = "0.25 mm"
    delta_one_step: str = "0.01 mm"
    delta_intersection: str = "0.001 mm"


@dataclass
class BiasRuleDefinition:
    particle: str = "proton"
    process: str = "hIoni"
    name: str = ""
    enabled: bool = True
    factor: str = "2"
    only_primary: bool = True
    apply_to_secondaries: bool = False
    min_weight: str = "0.05"
    max_interactions: str = "5"
    volumes: str = ""


# Exact constructor names accepted by PhysicsFactory. MicroElec/DNA/generic
# biasing are deliberately absent: they need separate lifecycle/region contracts.
MODULES = {
    "G4EmStandardPhysics": "em", "G4EmStandardPhysics_option1": "em",
    "G4EmStandardPhysics_option2": "em", "G4EmStandardPhysics_option3": "em",
    "G4EmStandardPhysics_option4": "em", "G4EmLivermorePhysics": "em",
    "G4EmPenelopePhysics": "em", "G4DecayPhysics": "decay",
    "G4RadioactiveDecayPhysics": "radioactive_decay", "G4IonPhysics": "ion",
    "G4HadronElasticPhysics": "elastic", "G4HadronElasticPhysicsHP": "elastic",
    "G4HadronPhysicsFTFP_BERT": "hadron", "G4HadronPhysicsFTFP_BERT_HP": "hadron",
    "G4HadronPhysicsQGSP_BERT": "hadron", "G4HadronPhysicsQGSP_BERT_HP": "hadron",
    "G4HadronPhysicsQGSP_BIC": "hadron", "G4HadronPhysicsFTF_BIC": "hadron",
    "G4HadronPhysicsQGSP_FTFP_BERT": "hadron", "G4HadronPhysicsFTFQGSP_BERT": "hadron",
    "G4StoppingPhysics": "stopping", "G4OpticalPhysics": "optical",
    "G4IonINCLXXPhysics": "ion", "G4IonQMDPhysics": "ion",
}

MODULE_ALIASES = {
    "g4emstandardphysics": "G4EmStandardPhysics",
    "em_standard": "G4EmStandardPhysics",
    "standard": "G4EmStandardPhysics",
    "g4emstandardphysics_option1": "G4EmStandardPhysics_option1",
    "em_option1": "G4EmStandardPhysics_option1",
    "option1": "G4EmStandardPhysics_option1",
    "g4emstandardphysics_option2": "G4EmStandardPhysics_option2",
    "em_option2": "G4EmStandardPhysics_option2",
    "option2": "G4EmStandardPhysics_option2",
    "g4emstandardphysics_option3": "G4EmStandardPhysics_option3",
    "em_option3": "G4EmStandardPhysics_option3",
    "option3": "G4EmStandardPhysics_option3",
    "g4emstandardphysics_option4": "G4EmStandardPhysics_option4",
    "em_option4": "G4EmStandardPhysics_option4",
    "option4": "G4EmStandardPhysics_option4",
    "em4": "G4EmStandardPhysics_option4",
    "g4emlivermorephysics": "G4EmLivermorePhysics",
    "livermore": "G4EmLivermorePhysics",
    "em_livermore": "G4EmLivermorePhysics",
    "g4empenelopephysics": "G4EmPenelopePhysics",
    "penelope": "G4EmPenelopePhysics",
    "em_penelope": "G4EmPenelopePhysics",
    "g4hadronphysicsftfp_bert": "G4HadronPhysicsFTFP_BERT",
    "ftfp_bert": "G4HadronPhysicsFTFP_BERT",
    "bert": "G4HadronPhysicsFTFP_BERT",
    "g4hadronphysicsftfp_bert_hp": "G4HadronPhysicsFTFP_BERT_HP",
    "ftfp_bert_hp": "G4HadronPhysicsFTFP_BERT_HP",
    "bert_hp": "G4HadronPhysicsFTFP_BERT_HP",
    "g4hadronphysicsqgsp_bert": "G4HadronPhysicsQGSP_BERT",
    "qgsp_bert": "G4HadronPhysicsQGSP_BERT",
    "g4hadronphysicsqgsp_bert_hp": "G4HadronPhysicsQGSP_BERT_HP",
    "qgsp_bert_hp": "G4HadronPhysicsQGSP_BERT_HP",
    "g4hadronphysicsqgsp_bic": "G4HadronPhysicsQGSP_BIC",
    "qgsp_bic": "G4HadronPhysicsQGSP_BIC",
    "g4hadronphysicsftf_bic": "G4HadronPhysicsFTF_BIC",
    "ftf_bic": "G4HadronPhysicsFTF_BIC",
    "g4hadronphysicsqgsp_ftfp_bert": "G4HadronPhysicsQGSP_FTFP_BERT",
    "qgsp_ftfp_bert": "G4HadronPhysicsQGSP_FTFP_BERT",
    "g4hadronphysicsftfqgsp_bert": "G4HadronPhysicsFTFQGSP_BERT",
    "ftfqgsp_bert": "G4HadronPhysicsFTFQGSP_BERT",
    "g4hadronelasticphysics": "G4HadronElasticPhysics",
    "elastic": "G4HadronElasticPhysics",
    "hel": "G4HadronElasticPhysics",
    "g4hadronelasticphysicshp": "G4HadronElasticPhysicsHP",
    "elastichp": "G4HadronElasticPhysicsHP",
    "helhp": "G4HadronElasticPhysicsHP",
    "g4ionphysics": "G4IonPhysics",
    "ion": "G4IonPhysics",
    "ionphysics": "G4IonPhysics",
    "g4ioninclxxphysics": "G4IonINCLXXPhysics",
    "ioninclxx": "G4IonINCLXXPhysics",
    "ionincl": "G4IonINCLXXPhysics",
    "g4ionqmdphysics": "G4IonQMDPhysics",
    "ionqmd": "G4IonQMDPhysics",
    "ionqmdphysics": "G4IonQMDPhysics",
    "g4decayphysics": "G4DecayPhysics",
    "decay": "G4DecayPhysics",
    "g4radioactivedecayphysics": "G4RadioactiveDecayPhysics",
    "radioactive_decay": "G4RadioactiveDecayPhysics",
    "rdm": "G4RadioactiveDecayPhysics",
    "g4stoppingphysics": "G4StoppingPhysics",
    "stopping": "G4StoppingPhysics",
    "g4opticalphysics": "G4OpticalPhysics",
    "optical": "G4OpticalPhysics"
}


def canonical_module(value: str) -> str | None:
    if any(c in value for c in "\r\n\x00;#[]"):
        return None
    return MODULE_ALIASES.get(value.strip().lower())


ENUMS = {
    "energy_type": ("mono", "gauss", "uniform", "power", "exp", "histogram", "points"),
    "position_type": ("point", "plane", "surface", "volume", "beam"),
    "shape": ("circle", "annulus", "ellipse", "rectangle", "square", "sphere", "cylinder", "box", "ellipsoid"),
    "angular": ("fixed", "isotropic", "cone", "cos", "beam1d", "beam2d", "focused"),
}


def problem(path: str, reason: str) -> str:
    return ui_text("J2 invalid field: {path} ({reason})").format(path=path, reason=ui_text(reason))


def number(value: str) -> float | None:
    try:
        result = float(value)
        return result if math.isfinite(result) else None
    except (ValueError, TypeError):
        return None


def vector(value: str, dimensional: bool = False) -> list[float] | None:
    # Mirrors comma-separated backend vectors, with a shared trailing unit.
    match = re.fullmatch(r"\s*([+-]?[\d.eE]+)\s*,\s*([+-]?[\d.eE]+)\s*,\s*([+-]?[\d.eE]+)\s*([A-Za-z/]+)?\s*", value)
    if not match or (dimensional and not match[4]) or (not dimensional and match[4]):
        return None
    result = [number(match[i]) for i in (1, 2, 3)]
    return result if all(x is not None for x in result) else None


def _safe_values(row, path: str, issues=None) -> list[str]:
    result = []
    for f in fields(row):
        if isinstance(getattr(row,f.name),str) and any(c in getattr(row,f.name) for c in "\r\n\x00;#[]"):
            item = (f"{path}.{f.name}","Single-line values are required")
            if issues is not None: issues.append(item)
            result.append(problem(*item))
    return result


def _name(value: str) -> bool:
    return bool(value.strip()) and value == value.strip() and not any(c in value for c in ".\r\n[];#=,\x00")


def _positive(value: str, dimension: str) -> bool:
    n = quantity(value, dimension)
    return n is not None and math.isfinite(n) and n > 0


def _vector_unit(value: str) -> str:
    match = re.search(r"([A-Za-z/]+)\s*$", value)
    return match[1] if match else ""


def length_vector(value: str) -> list[float] | None:
    components = vector(value,True)
    scale = quantity("1 "+_vector_unit(value),"length")
    if components is None or scale is None:
        return None
    result = [component*scale for component in components]
    return result if all(math.isfinite(x) for x in result) else None


def length_vector_text(value: str) -> str:
    # C++ comma vectors parse units per component. Normalize to base mm so a
    # shared display unit (1,2,3 cm) cannot silently scale only the final axis.
    components = length_vector(value)
    return ",".join(format(x,".17g") for x in components)+" mm" if components is not None else value


def unit_vector(value: list[float]) -> list[float] | None:
    scale = max(abs(x) for x in value)
    if not scale: return None
    scaled = [x/scale for x in value]
    norm = math.hypot(*scaled)
    return [x/norm for x in scaled]


def direction_text(value: str) -> str:
    components = vector(value)
    normalized = unit_vector(components) if components is not None else None
    return ",".join(format(x,".17g") for x in normalized) if normalized is not None else value


def source_values(row: GPSDefinition, *, named: bool = True) -> dict[str, str]:
    """Only active parameters are emitted; inactive drafts are retained in JSON."""
    result = {"particle": row.particle, "energy_type": row.energy_type,
              "position_type": row.position_type}
    if named:
        result["intensity"] = row.intensity
    if row.particle == "ion":
        # Backend accepts excitation as one token (e.g. 0keV).
        result["ion"] = " ".join((row.ion_z, row.ion_a, row.ion_charge, row.ion_excitation.replace(" ", "")))
    if row.energy_type in ("mono", "gauss"):
        result["energy"] = row.energy
    if row.energy_type == "gauss":
        result["energy_sigma"] = row.energy_sigma
    if row.energy_type in ("uniform", "power", "exp"):
        result.update(energy_min=row.energy_min, energy_max=row.energy_max)
    if row.energy_type == "power":
        result["alpha"] = row.alpha
    if row.energy_type == "exp":
        result["ezero"] = row.ezero
    if row.energy_type in ("histogram", "points"):
        result["spectrum_file"] = row.spectrum_file
    result["position" if row.position_type == "point" else "center"] = length_vector_text(row.center)
    if row.position_type != "point":
        result.update(shape=row.shape, rot1=direction_text(row.rot1), rot2=direction_text(row.rot2))
        keys = {
            "circle": ("radius",), "annulus": ("radius", "inner_radius"),
            "ellipse": ("halfx", "halfy"), "rectangle": ("halfx", "halfy"),
            "square": ("halfx",), "sphere": ("radius",),
            "cylinder": ("radius", "halfz"), "box": ("halfx", "halfy", "halfz"),
            "ellipsoid": ("halfx", "halfy", "halfz"),
        }.get(row.shape, ())
        if row.position_type == "beam":
            keys = ("beam_sigma",) if row.shape == "circle" else ("beam_sigma_x", "beam_sigma_y")
        result.update({key: getattr(row, key) for key in keys})
    if row.confine:
        result["confine"] = row.confine
    result["angular"] = "isotropic" if row.angular == "cone" else row.angular
    if row.angular not in ("isotropic", "focused"):
        result["direction"] = direction_text(row.direction)
    if row.angular in ("cone", "cos"):
        result.update(min_theta=row.min_theta, max_theta=row.max_theta)
    if row.angular in ("beam1d", "beam2d"):
        keys = ("angular_sigma",) if row.angular == "beam1d" else ("angular_sigma_x", "angular_sigma_y")
        result.update({key: getattr(row, key) for key in keys})
    if row.angular == "focused":
        result["focus"] = length_vector_text(row.focus)
    return result


def validate_gps(row: GPSDefinition, path: str = "source", *, issues=None) -> list[str]:
    """Optional issues receives (machine path, reason key), never parsed prose."""
    errors = _safe_values(row, path, issues)
    def fail(key, reason):
        item = (f"{path}.{key}",reason)
        if issues is not None: issues.append(item)
        errors.append(problem(*item))
    if not re.fullmatch(r"[0-9a-f]{32}",row.editor_id): fail("editor_id", "Invalid editor identity")
    if not _name(row.name): fail("name", "A unique name without dots is required")
    n = number(row.intensity)
    if n is None or n <= 0: fail("intensity", "A finite positive value is required")
    if not row.particle.strip(): fail("particle", "A value is required")
    for key in ("energy_type", "position_type", "angular"):
        if getattr(row, key) not in ENUMS[key]: fail(key, "Unsupported selection")
    shapes = {"point": ENUMS["shape"], "plane": ("circle", "annulus", "ellipse", "rectangle", "square"),
              "surface": ("sphere",), "volume": ("sphere", "cylinder", "box", "ellipsoid"), "beam": ("circle", "ellipse")}
    if row.shape not in shapes.get(row.position_type, ()): fail("shape", "Unsupported selection")
    if length_vector(row.center) is None:
        fail("center", "A finite three-component length vector is required")
    active = source_values(row)
    for key in ("energy", "energy_sigma", "energy_min", "energy_max", "ezero"):
        if key in active:
            v = quantity(active[key], "energy")
            zero = key == "energy_min" and row.energy_type != "power" or key == "energy" and row.particle == "ion"
            if v is None or not math.isfinite(v) or (v < 0 if zero else v <= 0): fail(key, "Energy is outside the supported range")
    if "energy_min" in active:
        low, high = quantity(row.energy_min, "energy"), quantity(row.energy_max, "energy")
        if low is not None and high is not None and high <= low: fail("energy_max", "The upper bound must exceed the lower bound")
    if row.energy_type == "power" and number(row.alpha) is None: fail("alpha", "A finite value is required")
    if "spectrum_file" in active and not row.spectrum_file.strip(): fail("spectrum_file", "A value is required")
    for key in ("radius", "inner_radius", "halfx", "halfy", "halfz", "beam_sigma", "beam_sigma_x", "beam_sigma_y"):
        if key in active and not _positive(active[key], "length"): fail(key, "A finite positive length is required")
    if row.shape == "annulus" and row.position_type == "plane":
        a, b = quantity(row.inner_radius, "length"), quantity(row.radius, "length")
        if a is not None and b is not None and a >= b: fail("inner_radius", "The inner radius must be smaller than the radius")
    if row.confine and row.position_type != "volume": fail("confine", "Confinement requires a volume source")
    if row.position_type != "point":
        a, b = vector(row.rot1), vector(row.rot2)
        a = unit_vector(a) if a is not None else None
        b = unit_vector(b) if b is not None else None
        if a is None or b is None: fail("rot1", "Nonzero independent rotation vectors are required")
        elif abs(sum(x*y for x,y in zip(a,b))) > 1-1e-9: fail("rot2", "Nonzero independent rotation vectors are required")
    if "direction" in active:
        d = vector(row.direction)
        if d is None or not any(d): fail("direction", "A finite nonzero direction is required")
    if row.angular == "focused" and length_vector(row.focus) is None: fail("focus", "A finite three-component length vector is required")
    if row.angular in ("cone", "cos"):
        a, b = quantity(row.min_theta, "angle"), quantity(row.max_theta, "angle")
        # config_schema quantity returns radians for angles.
        limit = quantity("90 deg" if row.angular == "cos" else "180 deg", "angle")
        if a is None or b is None or limit is None or not 0 <= a < b <= limit: fail("max_theta", "Invalid angular range")
    for key in ("angular_sigma", "angular_sigma_x", "angular_sigma_y"):
        if key in active and not _positive(active[key], "angle"): fail(key, "A finite positive angle is required")
    if row.particle == "ion":
        try:
            z, a = int(row.ion_z), int(row.ion_a)
            if str(z) != row.ion_z or str(a) != row.ion_a or not 1 <= z <= a <= 300: raise ValueError()
        except ValueError: fail("ion_z", "Ion requires integers 1 <= Z <= A <= 300")
        if number(row.ion_charge) is None: fail("ion_charge", "A finite value is required")
        e = quantity(row.ion_excitation, "energy")
        if e is None or e < 0: fail("ion_excitation", "Energy is outside the supported range")
    return errors


def section(name: str, values: dict) -> str:
    def text(value): return str(value).lower() if isinstance(value, bool) else str(value)
    return "[" + name + "]\n" + "\n".join(f"{key} = {text(value)}" for key, value in values.items() if value != "")


def region_values(row: RegionDefinition) -> dict:
    return {({"electron": "e-", "positron": "e+"}.get(k, k)): v for k,v in asdict(row).items() if k != "name" and v}


def validate_physics_extensions(model, *, issues=None) -> list[str]:
    errors = _safe_values(model,"physics",issues)
    def fail(path, reason):
        if issues is not None: issues.append((path,reason))
        errors.append(problem(path, reason))
    if model.mode not in ("reference", "manual"): fail("physics.mode", "Unsupported selection")
    if model.mode == "manual" and not model.manual_modules: fail("physics.manual_modules", "A value is required")
    if model.mode == "reference" and model.manual_modules: fail("physics.manual_modules", "Manual modules conflict with reference mode")
    if model.mode == "manual" and (model.extra_modules or model.replace_modules): fail("physics.extra_modules", "Reference modules conflict with manual mode")
    for key in ("extra_modules", "manual_modules", "replace_modules"):
        categories = set()
        for module in getattr(model, key):
            canonical = canonical_module(module)
            if canonical is None: fail("physics." + key, "Unsupported physics constructor")
            else:
                category = MODULES[canonical]
                if category in categories: fail("physics." + key, "Physics constructors of the same type conflict")
                categories.add(category)
                if key == "extra_modules" and category == "em": fail("physics.extra_modules", "EM constructors require replacement in reference mode")
                if key == "replace_modules" and canonical == "G4RadioactiveDecayPhysics":
                    fail("physics.replace_modules", "Constructors with physics type zero cannot be replaced")
                if key == "extra_modules" and model.reference_list in ("FTFP_BERT", "FTFP_BERT_EMZ", "FTFP_BERT_EMY", "FTFP_BERT_HP", "QGSP_BERT", "QGSP_BIC", "Shielding") and category in ("decay", "hadron", "elastic", "stopping", "ion"):
                    fail("physics.extra_modules", "The reference list already contains this physics type; use replacement")
    if {canonical_module(x) for x in model.extra_modules} & {canonical_module(x) for x in model.replace_modules}: fail("physics.replace_modules", "A constructor cannot be added and replaced together")
    if {MODULES.get(canonical_module(x)) for x in model.extra_modules} & {MODULES.get(canonical_module(x)) for x in model.replace_modules}:
        fail("physics.replace_modules", "Physics constructors of the same type conflict")
    for key, value in model.particle_cuts.items():
        if key not in ("gamma", "e-", "e+", "proton") or not _positive(value, "length"): fail("physics.cuts." + key, "A finite positive length is required")
    explicit_field_volumes = set()
    for group, rows in (("regions", model.regions), ("fields", model.fields)):
        names = set()
        for index,row in enumerate(rows):
            path = f"physics.{group}[{index}]"
            errors.extend(_safe_values(row, path, issues))
            name = row.name.lower()
            if name in names or not (group == "fields" and row.name == "" or _name(row.name)): fail(path+".name", "A unique name without dots is required")
            names.add(name)
            if group == "regions":
                for key,value in region_values(row).items():
                    dimension = "energy" if key == "min_kinetic_energy" else "time" if key == "max_time" else "length"
                    if key != "volumes" and not _positive(value, dimension): fail(path+"."+{"e-":"electron","e+":"positron"}.get(key,key), "A finite positive value with units is required")
            else:
                if bool(row.name) != bool(row.volumes.strip()): fail(path+".volumes", "Named fields require volumes; global fields have none")
                volumes = {name.strip() for name in row.volumes.split(',') if name.strip()}
                if volumes & explicit_field_volumes: fail(path+".volumes", "A volume cannot have multiple explicit local fields")
                explicit_field_volumes.update(volumes)
                if not any((row.magnetic, row.electric, row.magnetic_map, row.electric_map)): fail(path, "A field vector or map is required")
                for kind, units in (("magnetic", ("T", "tesla", "mT", "uT", "G", "gauss", "kG")), ("electric", ("V/m", "kV/m", "MV/m", "V/cm", "kV/cm", "MV/cm", "V/mm", "kV/mm"))):
                    v = getattr(row,kind)
                    if v and getattr(row,kind+"_map"): fail(path+"."+kind, "A uniform field and its map are mutually exclusive")
                    if v and (vector(v,True) is None or _vector_unit(v) not in units): fail(path+"."+kind, "A finite field vector with supported units is required")
                for key in ("min_step", "delta_chord", "delta_one_step", "delta_intersection"):
                    if not _positive(getattr(row,key), "length"): fail(path+"."+key, "A finite positive length is required")
    identities = set()
    active_rules = [r for r in model.bias_rules if r.enabled]
    if model.enable_biasing_physics and not active_rules: fail("physics.bias_rules", "Biasing requires an enabled process rule")
    if active_rules and not model.enable_biasing_physics: fail("physics.bias_rules", "Enabled process rules require the biasing hook")
    for index,row in enumerate(model.bias_rules):
        path = f"physics.bias_rules[{index}]"
        errors.extend(_safe_values(row,path,issues))
        # IniReader normalizes section names, even though the process VALUE
        # must retain case for real wrapped-process matching.
        identity = (row.particle.lower(),row.process.lower())
        if identity in identities: fail(path, "Duplicate particle and process rule")
        identities.add(identity)
        if not _name(row.particle) or not _name(row.process): fail(path, "Particle and process names are required")
        if not row.volumes.strip(): fail(path+".volumes", "A value is required")
        factor, weight = number(row.factor), number(row.min_weight)
        if factor is None or factor <= 0: fail(path+".factor", "A finite positive value is required")
        if weight is None or weight < 0: fail(path+".min_weight", "A finite nonnegative value is required")
        if not re.fullmatch(r"-1|\d+",row.max_interactions) or len(row.max_interactions) > 10 or int(row.max_interactions) > 2147483647: fail(path+".max_interactions", "Use -1 or a supported nonnegative integer")
        if row.only_primary and row.apply_to_secondaries: fail(path, "Primary-only and secondary application conflict")
    return errors


def physics_sections(model) -> str:
    values = {"default_cut": model.default_cut, "biasing": model.enable_biasing_physics, "verbose": "1"}
    if model.mode == "reference":
        values.update(reference=model.reference_list)
        if model.extra_modules: values["extra_modules"] = ", ".join(model.extra_modules)
        if model.replace_modules: values["replace_modules"] = ", ".join(model.replace_modules)
    else:
        values.update(reference="", modules=", ".join(model.manual_modules))
        # Explicit empty reference is required to select manual mode in C++.
    text = section("physics",values)
    if model.mode == "manual": text += "\nreference = "
    blocks = [text]
    if model.particle_cuts: blocks.append(section("physics.cuts",model.particle_cuts))
    blocks.extend(section("physics.region."+row.name,region_values(row)) for row in model.regions)
    blocks.extend(section("field"+("."+row.name if row.name else ""),{k:v for k,v in asdict(row).items() if k != "name"}) for row in model.fields)
    blocks.append(section("biasing", {"enabled": model.enable_biasing_physics}))
    blocks.extend(section("biasing.xs."+row.particle+"."+row.process,asdict(row)) for row in model.bias_rules)
    return "\n\n".join(blocks)


def hydrate_extensions(source, physics) -> None:
    """JSON constructors preserve all drafts; never run validation on restore."""
    for owner,key,cls in ((source,"gps_sources",GPSDefinition),(physics,"regions",RegionDefinition),
                          (physics,"fields",FieldDefinition),(physics,"bias_rules",BiasRuleDefinition)):
        setattr(owner,key,[cls(**row) if isinstance(row,dict) else row for row in getattr(owner,key)])
