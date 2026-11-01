"""J2 own smoke: structured controls, writer, JSON drafts and F5 core replay.

Does not build/run Geant4 or claim native visual/physical acceptance.
"""
from __future__ import annotations

from copy import deepcopy
import configparser
import json
from dataclasses import replace
import os
from pathlib import Path
import sys
import tempfile
from uuid import uuid4

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

from PySide6.QtWidgets import QApplication
from g4usim_gui.core.run_editor_model import (
    GPSDefinition, RegionDefinition, FieldDefinition, BiasRuleDefinition,
    validate_gps, source_values,
)
from g4usim_gui.core.config_schema import quantity
from g4usim_gui.core.project import G4USimProject, project_from_dict, project_to_dict, save_project, load_project
from g4usim_gui.core.edit_snapshot import WorkspaceSnapshot, snapshot_to_json, snapshot_from_json
from g4usim_gui.core.edit_transactions import EditSession
from g4usim_gui.editors.source_physics_scoring_model import (
    SourceEditableModel, PhysicsEditableModel, ScoringEditableModel,
    validate_source_model, validate_physics_model,
)
from g4usim_gui.models.package_model import RunPackage, GeometrySettings
from g4usim_gui.models.run_model import RunSettings
from g4usim_gui.writers.main_ini_writer import build_main_ini_text
from g4usim_gui.widgets.config.j2_run_editors import J2RunEditors, FIELD_LABELS
from g4usim_gui.widgets.config_builder_page import ConfigBuilderPage


def write(source,physics=None):
    physics = physics or PhysicsEditableModel()
    scoring = ScoringEditableModel()
    package = RunPackage(**{key: "<package>/"+key for key in RunPackage.__dataclass_fields__})
    text = build_main_ini_text(package=package,run=RunSettings(),geometry=GeometrySettings(),
        source=source.to_settings(),physics=physics.to_settings(),scoring=scoring.to_settings(),
        source_model=source,physics_model=physics,scoring_model=scoring)
    parser = configparser.ConfigParser(interpolation=None,strict=True)
    parser.read_string(text)
    return parser,text


def main():
    app = QApplication.instance() or QApplication([])
    base = GPSDefinition()
    translations=json.loads((Path(__file__).resolve().parents[1]/"g4usim_gui/core/j2_run_editors_i18n.json").read_text(encoding="utf-8"))
    for key in FIELD_LABELS.values():
        assert key in translations and translations[key]
    machine_issues=[]
    validate_gps(replace(base,energy="unfinished"),"source.gps_sources[3]",issues=machine_issues)
    assert ("source.gps_sources[3].energy","Energy is outside the supported range") in machine_issues
    # The actual writer must distinguish selected intensity vs simultaneous
    # emission and omit all legacy [source] fields in named mode.
    source = SourceEditableModel(gps_sources=[base,replace(base,editor_id=uuid4().hex,name="shell",intensity="3",position_type="surface",shape="sphere")],multiple_vertex=True)
    ini,text = write(source)
    assert set(ini["source"]) == {"multiple_vertex"}
    assert ini["source"].getboolean("multiple_vertex")
    assert ini["source.shell"]["position_type"] == "surface"
    assert ini["source.shell"]["shape"] == "sphere"
    assert ini["source.shell"]["intensity"] == "3"
    assert "position" not in ini["source.shell"]
    assert "halfx" not in ini["source.shell"]
    assert "preset" not in ini["source.shell"]
    assert "editor_id" not in ini["source.shell"]
    source.multiple_vertex=False
    assert not write(source)[0]["source"].getboolean("multiple_vertex")
    for position,shapes in (("point",("circle",)),("plane",("circle","annulus","ellipse","rectangle","square")),
                            ("surface",("sphere",)),("volume",("sphere","cylinder","box","ellipsoid")),("beam",("circle","ellipse"))):
        for shape in shapes:
            row = replace(base,position_type=position,shape=shape)
            assert not validate_gps(row), (position,shape,validate_gps(row))
            parsed,_ = write(SourceEditableModel(gps_sources=[row]))
            assert parsed["source.beam"]["position_type"] == position
    for energy in ("mono","gauss","uniform","power","exp","histogram","points"):
        row=replace(base,energy_type=energy,spectrum_file="spectrum.csv")
        assert not validate_gps(row), validate_gps(row)
        parsed,_=write(SourceEditableModel(gps_sources=[row]))
        assert parsed["source.beam"]["energy_type"] == energy
        assert ("energy" in parsed["source.beam"]) == (energy in ("mono","gauss"))
    for angular in ("fixed","isotropic","cone","cos","beam1d","beam2d","focused"):
        row=replace(base,angular=angular)
        assert not validate_gps(row), validate_gps(row)
        parsed,_=write(SourceEditableModel(gps_sources=[row]))
        assert parsed["source.beam"]["angular"] == ("isotropic" if angular=="cone" else angular)
        assert ("direction" in parsed["source.beam"]) == (angular not in ("isotropic","focused"))
    # Independent per-component decoding mirrors the backend comma parser:
    # a shared input cm unit must affect x/y too, not only the final component.
    row=replace(base,center="1,2,3 cm",angular="focused",focus="-2,3,4 m")
    parsed,_=write(SourceEditableModel(gps_sources=[row]))
    assert [quantity(x,"length") for x in parsed["source.beam"]["position"].split(',')]==[10,20,30]
    assert [quantity(x,"length") for x in parsed["source.beam"]["focus"].split(',')]==[-2000,3000,4000]
    assert row.center=="1,2,3 cm"
    assert not validate_gps(replace(base,position_type="plane",rot1="1e200,0,0",rot2="1,1,0"))
    assert validate_gps(replace(base,position_type="plane",rot1="1e200,0,0",rot2="2e200,0,0"))
    assert validate_gps(replace(base,center="1e308,0,0 m"))
    ion=replace(base,particle="ion",ion_z="27",ion_a="60",ion_charge="0",energy="0 keV")
    parsed,_=write(SourceEditableModel(gps_sources=[ion]))
    assert parsed["source.beam"]["ion"] == "27 60 0 0keV"
    # Invalid scalar/vector/identity/conflict cases must fail the writer, not
    # merely report a warning while emitting a runnable-looking configuration.
    for row in (replace(base,intensity="nan"),replace(base,energy="1e999 MeV"),replace(base,center="0,0,nan mm"),
                replace(base,direction="0,0,0"),replace(base,name="a.b"),replace(base,particle="p\n[run]"),
                replace(base,position_type="surface",shape="box"),replace(base,position_type="plane",shape="annulus",inner_radius="2 mm"),
                replace(base,confine="World"),replace(base,angular="cone",max_theta="200 deg"),
                replace(base,particle="ion",ion_z="2",ion_a="1"),replace(base,rot2="2,0,0",position_type="plane")):
        assert validate_gps(row), row
        try: write(SourceEditableModel(gps_sources=[row]))
        except ValueError: pass
        else: assert False, row
    duplicate = SourceEditableModel(gps_sources=[base,replace(base,name="BEAM")])
    assert validate_source_model(duplicate).errors
    physics = PhysicsEditableModel(replace_modules=["G4EmStandardPhysics_option4"],
        regions=[RegionDefinition(name="Target",volumes="target",electron="0.1 mm",max_step="0.01 mm",max_track_length="1 cm",max_time="1 ns",min_kinetic_energy="1 keV")],
        fields=[FieldDefinition(),FieldDefinition(name="local",volumes="target",magnetic="",electric="0,0,1 kV/cm")],
        enable_biasing_physics=True,bias_rules=[BiasRuleDefinition(volumes="target")],particle_cuts={"gamma":"0.1 mm"})
    assert not validate_physics_model(physics).errors, physics.errors
    ini,_=write(source,physics)
    assert ini["physics"]["replace_modules"] == "G4EmStandardPhysics_option4"
    assert ini["physics.region.Target"]["e-"] == "0.1 mm"
    assert ini["field.local"]["electric"] == "0,0,1 kV/cm"
    assert ini["biasing.xs.proton.hIoni"]["process"] == "hIoni"
    assert ini["biasing"].getboolean("enabled")
    assert ini["physics.cuts"]["gamma"] == "0.1 mm"
    manual=PhysicsEditableModel(mode="manual",manual_modules=["G4EmStandardPhysics_option4","G4DecayPhysics"])
    ini,_=write(SourceEditableModel(),manual)
    assert ini["physics"]["reference"] == ""
    assert "G4DecayPhysics" in ini["physics"]["modules"]
    alias_manual=PhysicsEditableModel(mode="manual",manual_modules=["em4","decay"])
    assert not validate_physics_model(alias_manual).errors
    assert write(SourceEditableModel(),alias_manual)[0]["physics"]["modules"]=="em4, decay"
    for bad in (PhysicsEditableModel(mode="manual"),PhysicsEditableModel(extra_modules=["G4EmStandardPhysics_option4"]),
                PhysicsEditableModel(manual_modules=["G4DecayPhysics"]),PhysicsEditableModel(replace_modules=["MicroElecPhysics"]),
                PhysicsEditableModel(replace_modules=["G4RadioactiveDecayPhysics"]),
                PhysicsEditableModel(extra_modules=["G4DecayPhysics"]),
                PhysicsEditableModel(replace_modules=["G4EmStandardPhysics","G4EmLivermorePhysics"]),
                PhysicsEditableModel(fields=[FieldDefinition(magnetic_map="map.csv")]),
                PhysicsEditableModel(fields=[FieldDefinition(name="local")]),
                PhysicsEditableModel(fields=[FieldDefinition(magnetic="0,0,nan T")]),
                PhysicsEditableModel(enable_biasing_physics=True,bias_rules=[BiasRuleDefinition(volumes="target"),BiasRuleDefinition(process="HIONI",volumes="target")]),
                PhysicsEditableModel(regions=[RegionDefinition(max_step="0 mm")]),
                PhysicsEditableModel(enable_biasing_physics=True),
                PhysicsEditableModel(enable_biasing_physics=True,bias_rules=[BiasRuleDefinition(volumes="target",apply_to_secondaries=True)])):
        assert validate_physics_model(bad).errors, bad
    replay=SourceEditableModel(phase_space_file="a.csv,b.csv",phase_space_recycle=True)
    ini,_=write(replay)
    assert set(ini["source"]) == {"phase_space_file","phase_space_recycle"}
    assert ini["source"].getboolean("phase_space_recycle")
    assert validate_source_model(replace(replay,gps_sources=[base])).errors
    assert validate_source_model(SourceEditableModel(phase_space_recycle=True)).errors
    # JSON, exact invalid draft persistence, legacy defaults, complete F5 codec.
    project=G4USimProject(sourceEditor=source,physicsEditor=physics)
    with tempfile.TemporaryDirectory(prefix="j2-editors-") as directory:
        path=Path(directory)/"project.json"
        save_project(project,path)
        restored=load_project(path)
        assert project_to_dict(restored)==project_to_dict(project)
        assert isinstance(restored.physicsEditor.fields[0],FieldDefinition)
        assert isinstance(restored.sourceEditor.gps_sources[0],GPSDefinition)
    restored=project_from_dict({"version":1,"sourceSettings":{"particle":"gamma"}})
    assert not restored.sourceEditor.gps_sources
    assert restored.sourceEditor.particle=="gamma"
    invalid=deepcopy(project)
    invalid.sourceEditor.gps_sources[0].energy="unfinished "
    invalid.physicsEditor.bias_rules[0].factor="nonsense "
    decoded=snapshot_from_json(snapshot_to_json(WorkspaceSnapshot(invalid)))
    assert decoded.project.sourceEditor.gps_sources[0].energy=="unfinished "
    assert decoded.project.physicsEditor.bias_rules[0].factor=="nonsense "
    session=EditSession(WorkspaceSnapshot(project))
    session.replace("J2 draft",WorkspaceSnapshot(invalid))
    assert session.current().project.sourceEditor.gps_sources[0].energy=="unfinished "
    session.undo()
    assert session.current().project.sourceEditor.gps_sources[0].energy=="10 MeV"
    session.redo()
    assert session.current().project.physicsEditor.bias_rules[0].factor=="nonsense "
    bad_json=project_to_dict(project)
    bad_json["sourceEditor"]["gps_sources"][0]["unexpected"]=1
    try: project_from_dict(bad_json)
    except ValueError: pass
    else: assert False, "unknown nested fields must be rejected"
    # Actual Qt list+detail edits retain per-row drafts and projection purity.
    editor=J2RunEditors()
    events=[]
    editor.changed.connect(lambda:events.append(True))
    editor.set_models(source,physics)
    assert not events
    gps=editor.row_editors["gps_sources"]
    gps.list.setCurrentRow(0)
    gps.controls["energy"].setText("unfinished ")
    gps.controls["energy"].textEdited.emit("unfinished ")
    assert len(events)==1
    gps.list.setCurrentRow(1)
    gps.list.setCurrentRow(0)
    assert gps.controls["energy"].text()=="unfinished "
    assert len(events)==1
    editor.collect_into(source,physics)
    assert source.gps_sources[0].energy=="unfinished "
    gps._structure("Duplicate")
    assert len(gps.rows)==3
    assert len({row.name.lower() for row in gps.rows})==3
    assert len({row.editor_id for row in gps.rows})==3
    gps._structure("Remove")
    assert len(gps.rows)==2
    before_ids=[row.editor_id for row in gps.rows]
    gps.list.setCurrentRow(0)
    gps._structure("Move down")
    assert [row.editor_id for row in gps.rows]==list(reversed(before_ids))
    gps.controls["name"].setText("renamed")
    gps.controls["name"].textEdited.emit("renamed")
    assert gps.rows[1].editor_id==before_ids[0]
    editor.collect_into(source,physics)
    replayed=project_from_dict(project_to_dict(G4USimProject(sourceEditor=source)))
    assert [row.editor_id for row in replayed.sourceEditor.gps_sources]==list(reversed(before_ids))
    assert replayed.sourceEditor.gps_sources[1].name=="renamed"
    # Selection/projection cannot imply runtime application or trigger a run.
    assert "not observed" in editor.observation.text()
    editor.close()
    # Exercise real page adoption/signals rather than only the isolated widget.
    page=ConfigBuilderPage()
    page_source=SourceEditableModel(gps_sources=[GPSDefinition(name="first"),GPSDefinition(name="second")])
    page.set_from_project(G4USimProject(sourceEditor=page_source),reload_sources=False)
    page_gps=page.j2_run_editors.row_editors["gps_sources"]
    notifications=[]
    page.settingsChanged.connect(lambda:notifications.append(True))
    page_gps.list.setCurrentRow(0)
    page_gps.controls["energy"].setText("31 MeV")
    page_gps.controls["energy"].textEdited.emit("31 MeV")
    page_gps.list.setCurrentRow(1)
    page_gps.controls["energy"].setText("33 MeV")
    page_gps.controls["energy"].textEdited.emit("33 MeV")
    assert [row.energy for row in page.source_editor.gps_sources]==["31 MeV","33 MeV"]
    assert len(notifications)==2
    page.source_energy.setText("44 MeV")
    page.source_energy.textEdited.emit("44 MeV")
    assert [row.energy for row in page.source_editor.gps_sources]==["31 MeV","33 MeV"]
    assert page.source_editor.energy=="44 MeV"
    assert "[source.first]" in page.generated_main_ini_raw.toPlainText()
    assert "energy = 31 MeV" in page.generated_main_ini_raw.toPlainText()
    page._backend_timer.stop()
    page.close()
    app.processEvents()
    print("J2 run editors smoke passed (model/writer/JSON/F5 core/Qt; backend and native UI not exercised)")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
