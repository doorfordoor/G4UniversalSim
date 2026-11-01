"""CURRENT package import, advanced preview and F5 interaction contract smoke."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import os
from pathlib import Path
import re
import sys
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM","offscreen")
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PySide6.QtWidgets import QApplication
from g4usim_gui.core.run_editor_import import parse_run_editor_ini,RunEditorImportError
from g4usim_gui.core.run_editor_model import GPSDefinition,RegionDefinition,FieldDefinition,BiasRuleDefinition
from g4usim_gui.core.project import G4USimProject
from g4usim_gui.core.project_snapshot import load_snapshot
from g4usim_gui.editors.source_physics_scoring_model import SourceEditableModel,PhysicsEditableModel,ScoringEditableModel
from g4usim_gui.editors.geometry_editor_model import GeometryDocument,HierarchicalVolumeRow,BooleanOperationRow,geometry_document_from_summary
from g4usim_gui.editors.material_editor_model import material_document_from_summary
from g4usim_gui.models.package_model import GeometrySettings,PathSettings
from g4usim_gui.models.run_model import RunSettings
from g4usim_gui.parsers.geometry_parser import parse_geometry
from g4usim_gui.parsers.materials_parser import parse_materials
from g4usim_gui.preview3d.source_builder import build_preview_source
from g4usim_gui.preview3d.scene_builder import build_preview_scene
from g4usim_gui.widgets.config.j2_run_editors import J2RunEditors
from g4usim_gui.widgets.config_builder_page import ConfigBuilderPage
from g4usim_gui.writers.package_writer import create_run_package
from smoke_j2_run_editors import write


def main():
    app=QApplication.instance() or QApplication([])
    source=SourceEditableModel(gps_sources=[GPSDefinition(name="first"),GPSDefinition(name="second",position_type="surface",shape="sphere")],multiple_vertex=True)
    physics=PhysicsEditableModel(replace_modules=["option4"],regions=[RegionDefinition(name="Target",electron="0.1 mm",max_step="0.01 mm")],
        fields=[FieldDefinition(name="local",volumes="Target")],enable_biasing_physics=True,bias_rules=[BiasRuleDefinition(volumes="Target")])
    _,text=write(source,physics)
    imported=parse_run_editor_ini(text,source_path="captured/main.ini",previous_source=source)
    assert [r.editor_id for r in imported.source.gps_sources]==[r.editor_id for r in source.gps_sources]
    assert imported.source.multiple_vertex
    assert imported.source.gps_sources[1].position_type=="surface"
    assert imported.physics.regions[0].electron=="0.1 mm"
    assert imported.physics.bias_rules[0].process=="hIoni"
    assert imported.physics.replace_modules==["option4"]
    assert imported.raw_text==text
    prefix="[source]\npreset=proton_beam\n"
    suffix="\n[physics]\nreference=FTFP_BERT\n"
    duplicate=parse_run_editor_ini(prefix+"energy=1\nEnergy=2\nenergy=3 MeV"+suffix,source_path="current.ini")
    assert duplicate.source.energy=="3 MeV"
    default_bias=parse_run_editor_ini(prefix+suffix+"biasing=true\n[biasing]\nenabled=true\n[biasing.xs.proton.hIoni]\nvolumes=Target\n",source_path="current.ini")
    assert default_bias.physics.bias_rules[0].factor=="1"
    cone=parse_run_editor_ini(prefix+"angular=isotropic\nmin_theta=0 deg\ndirection=0,0,1"+suffix,source_path="current.ini")
    assert cone.source.gps_sources[0].max_theta=="180 deg"
    plane=parse_run_editor_ini(prefix+"position_type=plane"+suffix,source_path="current.ini")
    assert plane.source.position=="0,0,-1 mm"
    assert plane.source.radius=="1 mm"
    _,old_plane=write(SourceEditableModel(position_mode="plane",position_type="plane",source_shape="circle",radius="2 mm"))
    assert parse_run_editor_ini(old_plane,source_path="current.ini").source.radius=="2 mm"
    # Every supported distribution emitted by the editor must be importable.
    for angular in ("fixed","isotropic","cone","cos","beam1d","beam2d","focused"):
        row=GPSDefinition(angular=angular)
        _,sample=write(SourceEditableModel(gps_sources=[row]))
        restored=parse_run_editor_ini(sample,source_path="current.ini")
        assert restored.source.gps_sources[0].angular==angular
    for energy in ("mono","gauss","uniform","power","exp","histogram","points"):
        _,sample=write(SourceEditableModel(gps_sources=[GPSDefinition(energy_type=energy,spectrum_file="spectrum.csv")]))
        assert parse_run_editor_ini(sample,source_path="current.ini").source.gps_sources[0].energy_type==energy
    for mode,shapes in (("plane",("circle","rectangle","ellipse","annulus","square")),("volume",("sphere","cylinder","box","ellipsoid")),("beam",("circle","ellipse"))):
        for shape in shapes:
            _,sample=write(SourceEditableModel(gps_sources=[GPSDefinition(position_type=mode,shape=shape)]))
            row=parse_run_editor_ini(sample,source_path="current.ini").source.gps_sources[0]
            assert (row.position_type,row.shape)==(mode,shape)
    for bad in (text+"\n[unknown.future]\nvalue=secret-draft\n",text.replace("energy = 10 MeV","future_energy = 10 MeV",1),
                text.replace("schema_version = 1","schema_version = 999",1),
                text.replace("energy = 10 MeV\n","",1),
                text+"\n[physics.region.Unknown]\nfuture_limit=3 mm\n"):
        try: parse_run_editor_ini(bad,source_path="original/current.ini")
        except RunEditorImportError as exc:
            assert exc.raw_text==bad
            assert exc.source_path=="original/current.ini"
            assert exc.issues
            assert len(exc.sha256)==64
        else: assert False,"unknown input must refuse publication"
    _,legacy=write(SourceEditableModel(energy="7 MeV"))
    assert parse_run_editor_ini(legacy.replace("7 MeV","99 MeV"),source_path="current.ini").source.energy=="99 MeV"
    _,manual=write(SourceEditableModel(),PhysicsEditableModel(mode="manual",manual_modules=["em4","decay"]))
    assert parse_run_editor_ini(manual,source_path="current.ini").physics.mode=="manual"
    implicit=parse_run_editor_ini("[source]\npreset=proton_beam\n[physics]\ndefault_cut=1 mm\n",source_path="current.ini")
    assert implicit.physics.mode=="manual"
    assert implicit.physics.manual_modules==["G4EmStandardPhysics_option4","G4DecayPhysics"]
    replay="[source]\nphase_space_file=a.csv,b.csv\nphase_space_recycle=true\n[physics]\nreference=FTFP_BERT\n"
    assert parse_run_editor_ini(replay,source_path="current.ini").source.phase_space_file=="a.csv,b.csv"
    # Advanced mode must not fall back to the unrelated legacy position/energy.
    for advanced in (source,SourceEditableModel(phase_space_file="a.csv,b.csv")):
        warnings=[]
        preview=build_preview_source(advanced,warnings,[])
        assert not preview.glyphs and not preview.preview_rays
        assert not preview.generated and preview.position_mm is None
        assert warnings and "hidden" in warnings[0]
    ordinary=build_preview_source(SourceEditableModel(),[],[])
    assert ordinary.glyphs and ordinary.generated
    # Interaction API carries legal machine tokens, never redundant raw drafts.
    editor=J2RunEditors()
    editor.set_models(source,physics)
    events=[]
    editor.changed.connect(lambda:events.append(True))
    assert editor.interaction_controls()==editor.editable_controls()
    for key in editor.interaction_controls():
        assert re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.:/-]{0,159}",key),key
    assert "j2.cuts.positron" in editor.interaction_controls()
    assert "j2.gps_sources.editor_id" not in editor.interaction_controls()
    source.is_dirty=physics.is_dirty=False
    editor.collect_into(source,physics)
    assert not source.is_dirty and not physics.is_dirty
    gps=editor.row_editors["gps_sources"]
    gps.list.setCurrentRow(1)
    gps.controls["energy"].setText("unfinished ")
    editor.collect_into(source,physics)
    assert source.gps_sources[1].energy=="unfinished "
    assert source.gps_sources[0].energy=="10 MeV"
    assert source.is_dirty and not physics.is_dirty
    selection=editor.selection_state()
    selection["j2.tabs"]=2
    before=len(events)
    editor.restore_selection(selection)
    assert editor.selection_state()==selection
    assert len(events)==before
    page=ConfigBuilderPage()
    page.set_from_project(G4USimProject(sourceEditor=source,physicsEditor=physics),reload_sources=False)
    assert not page.source_energy.isEnabled()
    assert "Named GPS" in page.source_status_label.text()
    assert "simultaneous" in page.source_status_label.text()
    page._backend_timer.stop()
    page.close()
    editor.close()
    # Boolean results remain backend-only; named tool parameters are validated,
    # and unsupported tools carry a concrete not_drawn reason.
    geometry=GeometryDocument(mode="hierarchical",volumes=[HierarchicalVolumeRow(name="world",shape="box",size="10 cm,10 cm,10 cm",material="G4_AIR"),
        HierarchicalVolumeRow(name="Target",parent="world",shape="box",size="1 cm,1 cm,1 cm",material="G4_WATER")],
        boolean_ops=[BooleanOperationRow(target_volume="Target",index=0,operation="subtract",tool_shape="trd",shape_properties={"dx1":"1 mm","dx2":"2 mm","dy1":"3 mm","dy2":"4 mm","dz":"5 mm"})])
    scene=build_preview_scene(geometry,SourceEditableModel())
    tool=next(v for v in scene.volumes if v.role=="boolean_tool")
    assert tool.parameters_mm==(1,2,3,4,5)
    assert "backend" in tool.not_drawn
    geometry.boolean_ops[0].tool_shape="trap"
    geometry.boolean_ops[0].shape_properties={}
    tool=next(v for v in build_preview_scene(geometry,SourceEditableModel()).volumes if v.role=="boolean_tool")
    assert "needs" in tool.not_drawn
    # Real package: historical JSON says 7 MeV, CURRENT main says 99 MeV.
    # Snapshot-recorded disabled geometry/material drafts are never substituted
    # for the actual package files that are now accepted.
    with tempfile.TemporaryDirectory(prefix="j2-current-") as temporary:
        root=Path(temporary)
        materials=root/"material.ini"
        materials.write_text("[material.Mix]\nmode=mass_fraction\ndensity=2 g/cm3\ncomponents=Si:1\n",encoding="utf-8")
        geom=root/"geometry.ini"
        stl=root/"tetra.stl"
        vertices=((0,0,0),(1,0,0),(0,1,0),(0,0,1))
        facets=[]
        for face in ((0,2,1),(0,1,3),(0,3,2),(1,2,3)):
            facets.append("facet normal 0 0 0\nouter loop\n"+"\n".join("vertex "+" ".join(map(str,vertices[index])) for index in face)+"\nendloop\nendfacet")
        stl.write_text("solid tetra\n"+"\n".join(facets)+"\nendsolid tetra\n",encoding="utf-8")
        geom.write_text("[global]\nversion=2\n[world]\nshape=box\nsize=10 cm,10 cm,10 cm\nmaterial=G4_AIR\n[volume.Target]\nparent=world\nshape=tessellated\nfile=tetra.stl\nmaterial=Mix\nsensitive=true\n",encoding="utf-8")
        material_document=material_document_from_summary(parse_materials(materials))
        geometry_document=geometry_document_from_summary(parse_geometry(geom,"hierarchical"),"hierarchical")
        src=SourceEditableModel(energy="7 MeV")
        phy=PhysicsEditableModel()
        score=ScoringEditableModel()
        package,_=create_run_package(project=G4USimProject(),paths=PathSettings(executable=sys.executable,workspace_root=str(root),runs_root=str(root/"runs"),materials_config=str(materials),geometry_config=str(geom)),
            run=RunSettings(),geometry=GeometrySettings(template="hierarchical",config_path=str(geom)),source=src.to_settings(),physics=phy.to_settings(),scoring=score.to_settings(),
            material_document=material_document,geometry_document=geometry_document,source_model=src,physics_model=phy,scoring_model=score)
        main_path=Path(package.main_ini_path)
        main_path.write_text(main_path.read_text(encoding="utf-8").replace("7 MeV","99 MeV"),encoding="utf-8")
        stl.unlink()
        geom.unlink()
        materials.unlink()
        loaded=load_snapshot(package.project_snapshot_path)
        assert loaded.project.sourceEditor.energy=="99 MeV"
        assert any(item.role=="main_ini_path" for item in loaded.inputs)
        target=next(row for row in loaded.project.geometryEditor.volumes if row.name=="Target")
        restored_stl=target.shape_properties.get("file",target.preview_properties.get("file",""))
        assert restored_stl and Path(restored_stl).is_file()
        assert Path(restored_stl).is_relative_to(Path(package.package_dir))
        # A second package uses multiple replay files and a field map. The
        # accepted CURRENT copies remain usable after originals are deleted.
        replay_a=root/"a.csv"; replay_b=root/"b.csv"; field_map=root/"field.csv"
        for path in (replay_a,replay_b,field_map): path.write_bytes(b"captured resource bytes\n")
        replay_source=SourceEditableModel(phase_space_file=str(replay_a)+","+str(replay_b),phase_space_recycle=True)
        replay_physics=PhysicsEditableModel(fields=[FieldDefinition(magnetic="",magnetic_map=str(field_map))])
        replay_package,_=create_run_package(project=G4USimProject(),paths=PathSettings(executable=sys.executable,workspace_root=str(root),runs_root=str(root/"runs"),
                materials_config=package.materials_ini_path,geometry_config=package.geometry_ini_path),run=RunSettings(run_name="resources"),
            geometry=GeometrySettings(template="hierarchical",config_path=package.geometry_ini_path),source=replay_source.to_settings(),physics=replay_physics.to_settings(),scoring=score.to_settings(),
            material_document=loaded.project.materialEditor,geometry_document=loaded.project.geometryEditor,source_model=replay_source,physics_model=replay_physics,scoring_model=score)
        for path in (replay_a,replay_b,field_map): path.unlink()
        replay_loaded=load_snapshot(replay_package.project_snapshot_path)
        assert len(replay_loaded.project.sourceEditor.phase_space_file.split(','))==2
        for path in replay_loaded.project.sourceEditor.phase_space_file.split(','):
            assert Path(path).is_file() and Path(path).is_relative_to(Path(replay_package.package_dir))
        assert Path(replay_loaded.project.physicsEditor.fields[0].magnetic_map).is_file()
        assert sum(item.role=="phase_space" for item in replay_loaded.inputs)==2
        # Package path checks follow the same final physical declarations as
        # IniReader, including exact-key and case-variant repetitions.
        valid_current=main_path.read_text(encoding="utf-8")
        geometry_line="config = "+package.geometry_ini_path
        repeated=valid_current.replace(geometry_line,"config = wrong.ini\nConfig = wrong2.ini\n"+geometry_line)
        main_path.write_text(repeated,encoding="utf-8")
        assert load_snapshot(package.project_snapshot_path).project.sourceEditor.energy=="99 MeV"
        mismatched=valid_current.replace(geometry_line,geometry_line+"\nConfig = wrong2.ini\nconfig = outside.ini")
        main_path.write_text(mismatched,encoding="utf-8")
        try: load_snapshot(package.project_snapshot_path)
        except RunEditorImportError as exc:
            assert exc.issues[0].value=="outside.ini"
        else: assert False,"last declared target must be checked"
        main_path.write_text(valid_current,encoding="utf-8")
        captured=main_path.read_text(encoding="utf-8")+"\n[future]\nunknown=keep-me\n"
        main_path.write_text(captured,encoding="utf-8")
        captured_bytes=main_path.read_bytes()
        try: load_snapshot(package.project_snapshot_path)
        except RunEditorImportError as exc:
            assert exc.raw_text==captured_bytes.decode("utf-8")
            assert "keep-me" in exc.raw_text
        else: assert False,"CURRENT unknown package input must block"
    app.processEvents()
    print("J2 CURRENT import/preview/interaction smoke passed")
    return 0


if __name__=="__main__": raise SystemExit(main())
