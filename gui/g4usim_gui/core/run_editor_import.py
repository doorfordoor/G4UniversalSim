"""Closed CURRENT main.ini adapter for source/physics/field/process-bias edits.

This is not a macro interpreter or a historical runtime receipt. Unsupported
input refuses publication and carries its complete captured text and locations.
"""
from __future__ import annotations

from dataclasses import dataclass, fields
from pathlib import Path
import re

from g4usim_gui.core.config_migration import digest
from g4usim_gui.core.config_schema import quantity, TRUE, FALSE
from g4usim_gui.core.i18n import ui_format, ui_text
from g4usim_gui.core.run_editor_model import (
    GPSDefinition, RegionDefinition, FieldDefinition, BiasRuleDefinition,
    source_values, canonical_module, MODULES,
)
from g4usim_gui.parsers.ini_light_parser import parse_ini_light_text


@dataclass(frozen=True)
class ImportIssue:
    section: str
    key: str
    value: str
    line: int
    reason: str


class RunEditorImportError(ValueError):
    def __init__(self,path,text,issues):
        self.source_path, self.raw_text = str(path),text
        self.sha256 = digest(text.encode("utf-8"))
        self.issues = tuple(issues)
        first = self.issues[0]
        super().__init__(ui_format("Current INI import blocked: {path}:{line} [{section}]/{key}: {reason}",
            path=self.source_path,line=first.line,section=first.section,key=first.key,reason=ui_text(first.reason)))


@dataclass
class RunEditorImport:
    source: object
    physics: object
    source_path: str
    raw_text: str
    sha256: str
    notes: tuple[str,...] = ()


# Non-editor sections remain owned by their existing package adapters. Unknown
# sections/keys cannot pass through this allowlist and be silently dropped.
OTHER_KEYS = {
    "general": {"schema_version"},
    "run": {"name","threads","seed","interactive","verbose","check_overlaps","dry_run"},
    "output": {"dir","trajectories"}, "materials": {"file"},
    "geometry": {"template","config","check_overlaps","default_world_material"},
    "scoring": {"enabled","hits","event_edep","edep","let","dose","fluence","auto_create_default_scorers","verbose"},
    "scoring.edep": {"raw_histogram","weighted_histogram","bins","min","max","volume_summary","particle_summary"},
}


def _length(value):
    """Decode C++ comma/per-component vs whitespace/shared-unit semantics."""
    if "," in value:
        parts=value.split(",")
    else:
        tokens=value.split()
        if len(tokens)==3: parts=tokens
        elif len(tokens)==4: parts=[x+" "+tokens[3] for x in tokens[:3]]
        elif len(tokens)==6: parts=[" ".join(tokens[i:i+2]) for i in (0,2,4)]
        else: return value
    numbers=[quantity(part,"length") for part in parts]
    if len(numbers)!=3 or any(x is None for x in numbers): return value
    return ",".join(format(x,".17g") for x in numbers)+" mm"


def _direction(value):
    axes={"+x":"1,0,0","-x":"-1,0,0","+y":"0,1,0","-y":"0,-1,0","+z":"0,0,1","-z":"0,0,-1"}
    return axes.get(value,",".join(value.split()) if "," not in value else value)


def parse_run_editor_ini(text: str, *, source_path: str | Path, previous_source=None) -> RunEditorImport:
    from g4usim_gui.editors.source_physics_scoring_model import SourceEditableModel,PhysicsEditableModel
    doc=parse_ini_light_text(text,source_path=source_path)
    issues=[ImportIssue("","","",0,error) for error in doc.errors]
    sections={}
    originals={}
    lines={}
    notes=[]
    for section in doc.sections:
        normalized=section.name.lower()
        if normalized in sections: notes.append(ui_format("Duplicate section retained with backend last-value semantics: {section}",section=section.name))
        values=sections.setdefault(normalized,{})
        originals[normalized]=section.name
        lines[(normalized,"")]=section.line_no
        # IniLightDocument retains the final value per *case-sensitive* key.
        # Replay those values in their final physical declaration order before
        # applying the backend's case-insensitive key identity.
        for key,value in sorted(section.values.items(),key=lambda item:section.key_lines[item[0]]):
            token=key.lower()
            if token in values: notes.append(ui_format("Duplicate field retained with backend last-value semantics: {section}/{key}",section=section.name,key=key))
            values[token]=value
            lines[(normalized,token)]=section.key_lines[key]

    def fail(section,key,reason):
        issues.append(ImportIssue(originals.get(section,section),key,sections.get(section,{}).get(key,""),lines.get((section,key),0),reason))

    def closed(section,allowed):
        for key in sections[section]:
            if key not in allowed: fail(section,key,"unsupported or unrepresentable field")

    def boolean(section,key,default=False):
        value=sections[section].get(key,"true" if default else "false").lower()
        if value not in TRUE|FALSE:
            fail(section,key,"invalid boolean")
            return default
        return value in TRUE

    source=SourceEditableModel()
    physics=PhysicsEditableModel()
    named=[section for section in sections if section.startswith("source.")]
    global_values=sections.get("source",{})
    if not named and "source" not in sections: fail("source","","an explicit source is required for editable import")
    if named and "source" in sections: closed("source",{"verbose","multiple_vertex"})
    if "multiple_vertex" in global_values:
        source.multiple_vertex=boolean("source","multiple_vertex")
        if not named: fail("source","multiple_vertex","requires named sources")
    if "phase_space_file" in global_values:
        closed("source",{"phase_space_file","phase_space_recycle","verbose"})
        source.phase_space_file=global_values["phase_space_file"]
        source.phase_space_recycle=boolean("source","phase_space_recycle")
        if named: fail("source","phase_space_file","phase-space replay conflicts with named sources")
        if not all(x.strip() for x in source.phase_space_file.split(",")): fail("source","phase_space_file","empty replay path")
    else:
        ids={row.name.lower():row.editor_id for row in getattr(previous_source,"gps_sources",[])}
        for section in named or (["source"] if "source" in sections else []):
            values=sections[section]
            row=GPSDefinition(name=originals[section][7:] if section!="source" else "source")
            if row.name.lower() in ids: row.editor_id=ids[row.name.lower()]
            preset=values.get("preset","").lower()
            if "preset" in values and not preset: fail(section,"preset","explicit source preset is empty")
            if preset:
                if preset in ("neutron_beam","gamma_beam","isotropic_neutron"):
                    row.particle="gamma" if preset=="gamma_beam" else "neutron"
                    row.energy="1 MeV"
                    if preset=="isotropic_neutron": row.center="0,0,0 mm"; row.angular="isotropic"
                elif preset=="plane_proton_beam": row.position_type="plane"
                elif preset not in ("proton_beam","mono_proton"): fail(section,"preset","unsupported preset")
            elif section!="source":
                for key,valid in (("particle","particle" in values),("energy","energy" in values or "energy_type" in values),
                                  ("position","position" in values or "position_type" in values),
                                  ("direction",values.get("position_type","").lower()=="plane" or any(k in values for k in ("direction","angular","isotropic")))):
                    if not valid: fail(section,key,"named source is missing an explicit required value")
            for f in fields(row):
                if f.name in values and f.name not in ("name","editor_id","center","direction","rot1","rot2","focus"):
                    setattr(row,f.name,values[f.name])
            for key in ("energy_type","position_type","shape","angular"):
                setattr(row,key,getattr(row,key).lower())
            if "position" in values: row.center=_length(values["position"])
            if "center" in values: row.center=_length(values["center"])
            elif "position_type" in values and row.position_type!="point":
                row.center="0,0,-1 mm" if row.position_type=="plane" else "0,0,0 mm"
            if "focus" in values: row.focus=_length(values["focus"])
            for key in ("direction","rot1","rot2"):
                if key in values: setattr(row,key,_direction(values[key]))
            if "isotropic" in values:
                if "angular" in values: fail(section,"isotropic","angular and isotropic selectors conflict")
                isotropic=boolean(section,"isotropic")
                if isotropic: row.angular="isotropic"
                elif row.angular=="isotropic" and "direction" not in values: fail(section,"isotropic","disabling an isotropic preset requires direction")
                elif not isotropic and "angular" not in values: row.angular="fixed"
                if isotropic and "direction" in values: fail(section,"direction","isotropic source conflicts with explicit direction")
            if row.angular=="isotropic" and any(key in values for key in ("min_theta","max_theta")):
                row.angular="cone"
                if "max_theta" not in values: row.max_theta="180 deg"
            if row.angular=="cos" and "max_theta" not in values: row.max_theta="90 deg"
            if "ion" in values:
                tokens=values["ion"].split()
                if not 2<=len(tokens)<=4: fail(section,"ion","ion requires Z A [charge [excitation]]")
                else:
                    row.ion_z,row.ion_a=tokens[:2]
                    row.ion_charge=tokens[2] if len(tokens)>2 else tokens[0]
                    row.ion_excitation=tokens[3] if len(tokens)>3 else "0 keV"
            active=source_values(row)
            # Never repair an incomplete declared distribution using the GUI's
            # convenient defaults. Only a recognized backend preset supplies
            # missing legacy particle/mono/position/angular state.
            required=set()
            if not preset: required.add("particle")
            if not preset or "energy_type" in values:
                required.update(key for key in ("energy","energy_sigma","energy_min","energy_max","alpha","ezero","spectrum_file") if key in active)
            if values.get("position_type","").lower()=="point": required.add("position")
            if "position_type" in values and row.position_type!="point":
                required.update(key for key in ("shape","radius","inner_radius","halfx","halfy","halfz","beam_sigma","beam_sigma_x","beam_sigma_y") if key in active)
                if row.position_type in ("plane","beam") and "shape" not in values: required.discard("shape")
                if row.position_type=="plane" and row.shape=="circle": required.discard("radius")
            if "rot1" in values or "rot2" in values: required.update(("rot1","rot2"))
            if row.angular in ("fixed","cos","cone","beam1d","beam2d") and row.position_type!="plane" and preset not in ("proton_beam","mono_proton","neutron_beam","gamma_beam","plane_proton_beam"):
                required.add("direction")
            if row.angular in ("beam1d","beam2d"):
                required.update(key for key in ("angular_sigma","angular_sigma_x","angular_sigma_y") if key in active)
            if row.angular=="focused": required.add("focus")
            for key in required:
                if key not in values: fail(section,key,"declared distribution is missing a required value")
            allowed=set(source_values(row))|{"preset","isotropic","verbose"}
            if section=="source": allowed.discard("intensity")
            # UI-only names/ion subfields never count as accepted INI keys.
            closed(section,allowed)
            for key in ("verbose",):
                if key in values and values[key] not in ("0","1"): fail(section,key,"nondefault verbosity is not editable")
            if row.particle=="ion" and "ion" not in values: fail(section,"ion","particle=ion requires explicit ion values")
            if row.angular=="focused" and "focus" not in values: fail(section,"focus","focused source requires focus")
            # Standard legacy inputs retain their original single-source editor.
            legacy=(section=="source" and row.energy_type=="mono" and row.particle!="ion" and row.position_type in ("point","plane")
                    and (row.position_type=="point" or row.shape in ("circle","rectangle")) and row.angular in ("fixed","isotropic")
                    and not any(key in values for key in ("rot1","rot2","confine")))
            if legacy:
                source.preset=preset or "proton_beam"
                source.particle,source.energy=row.particle,row.energy
                source.position_mode=source.position_type=row.position_type
                source.position=row.center
                source.direction=row.direction
                source.source_shape="point" if row.position_type=="point" else row.shape
                source.radius,source.halfx,source.halfy=row.radius,row.halfx,row.halfy
                source.angular_mode=row.angular
            else: source.gps_sources.append(row)

    if "physics" not in sections: fail("physics","","an explicit physics section is required for editable import")
    for section in sorted(sections,key=lambda key:key!="physics"):
        values=sections[section]
        if section=="source" or section.startswith("source."): continue
        if section=="physics":
            closed(section,{"reference","default_cut","biasing","verbose","modules","extra_modules","replace_modules","em","list"})
            # PhysicsManager starts in manual mode with option4 EM + decay;
            # absence is not the GUI's reference-list default.
            reference=values.get("reference","")
            physics.mode="reference" if reference else "manual"
            physics.reference_list=reference
            physics.default_cut=values.get("default_cut",physics.default_cut)
            physics.enable_biasing_physics=boolean(section,"biasing")
            split=lambda key:[item.strip() for item in values.get(key,"").split(",") if item.strip()]
            physics.replace_modules=split("replace_modules")
            if physics.mode=="reference":
                physics.extra_modules=split("modules")+split("extra_modules")
                if values.get("em") or values.get("list"): fail(section,"em","reference EM override requires an explicit editable suffix or replacement")
            else:
                physics.manual_modules=(split("modules") if "modules" in values else ["G4DecayPhysics"])+split("extra_modules")
                selector=values.get("em",values.get("list",""))
                if "em" in values and "list" in values: fail(section,"list","legacy list selector is shadowed by explicit em")
                if selector:
                    if "em" in values and MODULES.get(canonical_module(selector))!="em": fail(section,"em","explicit em selector requires an EM constructor")
                    physics.manual_modules.insert(0,selector)
                unique=[]
                seen=set()
                for item in physics.manual_modules:
                    token=canonical_module(item) or item
                    if token not in seen: unique.append(item); seen.add(token)
                physics.manual_modules=unique
                if not any(MODULES.get(canonical_module(item))=="em" for item in unique):
                    physics.manual_modules.insert(0,"G4EmStandardPhysics_option4")
            if values.get("verbose","1")!="1": fail(section,"verbose","nondefault verbosity is not editable")
        elif section=="physics.cuts":
            closed(section,{"gamma","e-","e+","proton"})
            physics.particle_cuts=dict(values)
        elif section.startswith("physics.region."):
            row=RegionDefinition(name=originals[section][15:])
            mapping={"e-":"electron","e+":"positron"}
            closed(section,({f.name for f in fields(row)}-{"name","electron","positron"})|{"e-","e+"})
            for key,value in values.items():
                if hasattr(row,mapping.get(key,key)): setattr(row,mapping.get(key,key),value)
            physics.regions.append(row)
        elif section=="field" or section.startswith("field."):
            row=FieldDefinition(name="" if section=="field" else originals[section][6:],magnetic="")
            closed(section,{f.name for f in fields(row)}-{"name"})
            for key,value in values.items():
                if hasattr(row,key): setattr(row,key,value)
            physics.fields.append(row)
        elif section=="biasing":
            closed(section,{"enabled"})
            if boolean(section,"enabled") != physics.enable_biasing_physics: fail(section,"enabled","biasing module and physics hook must agree")
        elif section.startswith("biasing.xs."):
            parts=originals[section].split(".")
            if len(parts)!=4: fail(section,"","expected biasing.xs.particle.Process"); continue
            row=BiasRuleDefinition(particle=parts[2],process=parts[3],factor="1")
            closed(section,{f.name for f in fields(row)})
            for key,value in values.items():
                if hasattr(row,key): setattr(row,key,boolean(section,key) if type(getattr(row,key)) is bool else value)
            physics.bias_rules.append(row)
        elif section.startswith("scoring.filter."):
            scorer = section.split(".", 2)[2]
            if scorer not in {"dose", "fluence", "let", "displacement"}:
                fail(section, "", "unknown volume filter scorer")
            else:
                closed(section, {"particles", "energy_min", "energy_max"})
        elif section.startswith("scoring.spectrum."):
            scorer = section.split(".", 2)[2]
            if scorer not in {"dose", "fluence", "displacement"}:
                fail(section, "", "unknown kinetic-energy spectrum scorer")
            else:
                closed(section, {"bins", "min", "max"})
        elif section in OTHER_KEYS:
            closed(section,OTHER_KEYS[section])
            if section=="general" and values.get("schema_version","1")!="1":
                fail(section,"schema_version","unsupported main INI schema version")
        else: fail(section,"","unsupported section must remain in its source file")
    if physics.enable_biasing_physics and "biasing" not in sections:
        fail("biasing","enabled","biasing module and physics hook must agree")
    if issues: raise RunEditorImportError(source_path,text,issues)
    source.is_dirty=physics.is_dirty=False
    return RunEditorImport(source,physics,str(source_path),text,digest(text.encode("utf-8")),tuple(notes))


def load_run_editor_ini(path: str | Path, *, previous_source=None) -> RunEditorImport:
    source=Path(path)
    return parse_run_editor_ini(source.read_bytes().decode("utf-8"),source_path=source,previous_source=previous_source)
