#!/usr/bin/env python3
"""E7 registry component/static checks; --backend needs a fresh G4USIM_EXE.

The component compiles production SolidRegistry.cc with instrumented factory
and solid doubles to check dispatch/cache policy without Geant4. It does not
construct real solids. Backend mode checks real volumes/masses and A5 negatives.
"""
from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
# Independent dispatch expectation, including two modes of the shared factory.
FACTORIES = {
    "Box": "CreateBoxSolid", "Tubs": "CreateTubsSolid", "Sphere": "CreateSphereSolid",
    "Orb": "CreateOrbSolid", "Cone": "CreateConeSolid", "Trd": "CreateTrdSolid",
    "Trap": "CreateTrapSolid", "Ellipsoid": "CreateEllipsoidSolid",
    "EllipticalTube": "CreateEllipticalTubeSolid", "Torus": "CreateTorusSolid",
    "Para": "CreateParaSolid", "Hype": "CreateHypeSolid", "Polycone": "CreatePolyconeSolid",
    "Polyhedra": "CreatePolyconeSolid", "Tessellated": "CreateTessellatedSolid",
}
LEGACY = {"box", "tubs", "sphere", "orb", "cone", "trd", "trap"}
COUNTS = {"box": [], "tubs": [5], "sphere": [6], "orb": [1], "cone": [7], "trd": [], "trap": [],
          "ellipsoid": [3, 5], "eltube": [3], "torus": [5], "para": [6], "hype": [5],
          "polycone": [2], "polyhedra": [3], "tessellated": []}


def component() -> dict:
    configured = os.environ.get("CXX")
    compiler = shlex.split(configured, posix=os.name != "nt") if configured else []
    if not compiler:
        found = next((shutil.which(c) for c in ("g++", "clang++", "cl") if shutil.which(c)), None)
        assert found, "C++17 compiler required (set CXX or configure PATH)"
        compiler = [found]
    with tempfile.TemporaryDirectory(prefix="g4usim-solid-registry-") as temp:
        folder = Path(temp)
        (folder / "Geometry").mkdir()
        (folder / "G4VSolid.hh").write_text('''#pragma once
class G4VSolid { public: int volumeCalls=0; virtual ~G4VSolid()=default;
virtual double GetCubicVolume() { ++volumeCalls; return 123.0; } };
''', encoding="utf-8")
        (folder / "Geometry/VolumeNode.hh").write_text('''#pragma once
#include "Geometry/GeometryTypes.hh"
class VolumeNode { public: std::string name="probe", shapeName="unknown";
VolumeShape shape=VolumeShape::Unknown; Vec3 size; std::vector<double> parameters; };
''', encoding="utf-8")
        methods = []
        for shape, method in FACTORIES.items():
            if shape in ("Polycone", "Polyhedra"):
                continue
            methods.append(f"G4VSolid* {method}(const VolumeNode& n) {{ return Record(n, VolumeShape::{shape}); }}")
        methods.append("""G4VSolid* CreatePolyconeSolid(const VolumeNode& n, bool polyhedra) {
return Record(n, polyhedra ? VolumeShape::Polyhedra : VolumeShape::Polycone); }""")
        (folder / "Geometry/VolumeBuilder.hh").write_text('''#pragma once
#include "Geometry/VolumeNode.hh"
#include "G4VSolid.hh"
#include <stdexcept>
class VolumeBuilder { public:
G4VSolid solid; const VolumeNode* observed=nullptr;
VolumeShape observedShape=VolumeShape::Unknown; int calls=0; bool fail=false, nullResult=false;
G4VSolid* Record(const VolumeNode& n, VolumeShape s) {
++calls; observed=&n; observedShape=s;
if(fail) throw std::runtime_error("factory_failure");
return nullResult ? nullptr : &solid;
}
''' + "\n".join(methods) + "\n};\n", encoding="utf-8")
        harness = folder / "registry_test.cc"
        harness.write_text(r'''
#include "Geometry/SolidRegistry.hh"
#include "Geometry/VolumeBuilder.hh"
#include <iostream>
#include <stdexcept>
using V=effective_config::Value;
using C=SolidRegistry::Context;
int main() {
 V::Array observations;
 for(const auto& e:SolidRegistry::Entries()) {
  VolumeNode n; n.shape=e.shape; n.size={20,30,40}; n.parameters={0,1,2,3,4,5,6};
  VolumeBuilder b;
  auto* s=SolidRegistry::Create(b,n);
  auto description=SolidRegistry::Describe(); // must not invoke constructors/cache
  observations.emplace_back(V::Object{{"name",e.name},{"factory_matches",b.observedShape==e.shape},
   {"same_node",b.observed==&n},{"calls",b.calls},{"same_solid",s==&b.solid},
   {"cache_calls",b.solid.volumeCalls},{"find_shape",SolidRegistry::Find(e.shape)==&e},
   {"supports_volume",SolidRegistry::Supports(e.shape)},
   {"supports_tool",SolidRegistry::Supports(e.shape,C::BooleanTool)}});
 }
 V::Array tools;
 for(const auto& e:SolidRegistry::Entries()) {
  VolumeNode n; n.shape=e.shape; n.size={20,30,40}; n.parameters={0,1,2,3,4,5,6};
  VolumeBuilder b; std::string error;
  try { SolidRegistry::Create(b,n,C::BooleanTool); }
  catch(const std::exception& ex) { error=ex.what(); }
  tools.emplace_back(V::Object{{"name",e.name},{"error",error},{"calls",b.calls},
   {"cache_calls",b.solid.volumeCalls},{"factory_matches",b.observedShape==e.shape}});
 }
 V::Array invalid;
 for(auto shape:{VolumeShape::Box,VolumeShape::Tubs,VolumeShape::Sphere,VolumeShape::Orb,VolumeShape::Cone,
                 VolumeShape::Unknown,static_cast<VolumeShape>(999)}) {
  VolumeNode n; n.shape=shape; VolumeBuilder b; std::string error;
  try { SolidRegistry::Create(b,n,C::BooleanTool); } catch(const std::exception& ex) { error=ex.what(); }
  invalid.emplace_back(V::Object{{"error",error},{"calls",b.calls}});
 }
 VolumeNode unknown; VolumeBuilder b; std::string unknownError;
 try { SolidRegistry::Create(b,unknown); } catch(const std::exception& ex) { unknownError=ex.what(); }
 VolumeNode a5; a5.shape=VolumeShape::Ellipsoid;
 VolumeBuilder failing; failing.fail=true; std::string factoryError;
 try { SolidRegistry::Create(failing,a5); } catch(const std::exception& ex) { factoryError=ex.what(); }
 VolumeBuilder nullBuilder; nullBuilder.nullResult=true;
 bool nullPreserved=SolidRegistry::Create(nullBuilder,a5)==nullptr;
 V::Array aliases;
 for(const auto& e:SolidRegistry::Entries()) {
  for(const auto& alias:e.aliases) aliases.emplace_back(V::Object{{"alias",alias},
   {"match",SolidRegistry::Find(" \t"+alias+"\r\n")==&e}});
  std::string upper=e.name;
  for(char& c:upper) if(c>='a' && c<='z') c-=32;
  aliases.emplace_back(V::Object{{"alias",upper},{"match",SolidRegistry::Find(upper)==&e}});
 }
 V result=V::Object{{"metadata",SolidRegistry::Describe()},{"observations",observations},
  {"tools",tools},{"invalid",invalid},{"aliases",aliases},{"unknown_error",unknownError},
  {"unknown_lookup",SolidRegistry::Find("unknown")==nullptr && SolidRegistry::Find("")==nullptr &&
    SolidRegistry::Find("G4Box")==nullptr && SolidRegistry::Find(static_cast<VolumeShape>(999))==nullptr &&
    !SolidRegistry::Supports(VolumeShape::Unknown)},
  {"factory_error",factoryError},{"failed_cache_calls",failing.solid.volumeCalls},
  {"null_preserved",nullPreserved},{"null_cache_calls",nullBuilder.solid.volumeCalls}};
 std::cout<<result.ToJson()<<'\n';
}
''', encoding="utf-8")
        inputs = [str(harness), str(ROOT / "src/Geometry/SolidRegistry.cc"),
                  str(ROOT / "src/Config/EffectiveConfig.cc")]
        exe = folder / ("registry.exe" if os.name == "nt" else "registry")
        if Path(compiler[0]).stem.lower() in ("cl", "clang-cl"):
            command = compiler + ["/nologo", "/std:c++17", "/EHsc", "/I" + str(folder),
                                  "/I" + str(ROOT / "include"), *inputs, "/Fe:" + str(exe)]
        else:
            command = compiler + ["-std=c++17", "-Wall", "-Wextra", "-pedantic", "-I", str(folder),
                                  "-I", str(ROOT / "include"), *inputs, "-o", str(exe)]
        built = subprocess.run(command, cwd=folder, capture_output=True, text=True, timeout=120)
        assert built.returncode == 0, built.stdout + built.stderr
        ran = subprocess.run([str(exe)], cwd=folder, capture_output=True, text=True, timeout=30)
        assert ran.returncode == 0, ran.stdout + ran.stderr
        result = json.loads(ran.stdout)
    metadata = result["metadata"]
    solids = metadata["solids"]
    assert metadata["schema"] == "g4usim_solid_registry_v1"
    assert metadata["internal_units"] == {"length": "mm", "angle": "rad"}
    assert {s["name"] for s in solids} == set(COUNTS)
    assert len(solids) == len(COUNTS)
    # Compare production parser/canonical names/aliases to detect metadata drift.
    utils = (ROOT / "src/Geometry/GeometryUtils.cc").read_text(encoding="utf-8")
    parse_body = utils.split("VolumeShape ParseShape(", 1)[1].split("std::string ShapeToString", 1)[0]
    parsed_aliases = {}
    for condition, shape in re.findall(r'if \((.*?)\) return VolumeShape::(\w+);', parse_body):
        parsed_aliases[shape] = re.findall(r'value == "([^"]+)"', condition)
    canonical = dict(re.findall(r'case VolumeShape::(\w+): return "([^"]+)";',
                               utils.split("std::string ShapeToString", 1)[1].split("PlacementType ParsePlacementType", 1)[0]))
    assert set(parsed_aliases) == set(FACTORIES)
    for shape, accepted in parsed_aliases.items():
        entry = next(s for s in solids if s["name"] == canonical[shape])
        assert set([entry["name"], *entry["aliases"]]) == set(accepted), shape
        assert entry["parameter_counts"] == COUNTS[entry["name"]]
        assert entry["boolean_tool"] == (entry["name"] in LEGACY)
        assert entry["experimental"] == (entry["name"] not in LEGACY)
        assert entry["precompute_volume"] == (entry["name"] not in LEGACY)
        assert entry["uses_size"] == (entry["name"] == "box")
    by_name = {s["name"]: s for s in solids}
    assert [f["dimension"] for f in by_name["hype"]["parameters"]] == ["length", "length", "angle", "angle", "length"]
    assert [f["dimension"] for f in by_name["polyhedra"]["parameters"]] == ["angle", "angle", "integer"]
    assert [f["name"] for f in by_name["trap"]["properties"]] == ["dz", "theta", "phi", "dy1", "dx1", "dx2", "alpha1", "dy2", "dx3", "dx4", "alpha2"]
    assert by_name["tessellated"]["properties"][-1] == {"name": "file_unit", "dimension": "length_unit", "required": False, "default": "mm"}
    assert [f["required"] for f in by_name["ellipsoid"]["parameters"]] == [True, True, True, False, False]
    for observation in result["observations"]:
        assert observation["factory_matches"] and observation["same_node"] and observation["same_solid"]
        assert observation["calls"] == 1
        assert observation["cache_calls"] == (0 if observation["name"] in LEGACY else 1)
        assert observation["find_shape"] and observation["supports_volume"]
        assert observation["supports_tool"] == (observation["name"] in LEGACY)
    for tool in result["tools"]:
        assert tool["cache_calls"] == 0
        if tool["name"] in LEGACY:
            assert tool["calls"] == 1 and tool["error"] == "" and tool["factory_matches"]
        else:
            assert tool["calls"] == 0 and tool["error"] == "unsupported or missing boolean tool shape"
    expected_errors = [
        "box requires positive size x,y,z",
        "tubs requires 5 parameters: rMin,rMax,halfZ,startPhi,deltaPhi",
        "sphere requires 6 parameters: rMin,rMax,startPhi,deltaPhi,startTheta,deltaTheta",
        "orb requires parameters=radius or positive size.x shorthand",
        "cone requires 7 parameters: rMin1,rMax1,rMin2,rMax2,halfZ,startPhi,deltaPhi",
        "unsupported or missing boolean tool shape", "unsupported or missing boolean tool shape",
    ]
    assert len(result["invalid"]) == len(expected_errors)
    for invalid, error in zip(result["invalid"], expected_errors):
        assert invalid["calls"] == 0 and invalid["error"] == error
    for alias in result["aliases"]:
        assert alias["match"], alias
    assert result["unknown_lookup"]
    assert result["unknown_error"] == "Unsupported shape for volume 'probe': shapeName='unknown', parsed='unknown'"
    assert result["factory_error"] == "factory_failure" and result["failed_cache_calls"] == 0
    assert result["null_preserved"] and result["null_cache_calls"] == 0
    builder = (ROOT / "src/Geometry/VolumeBuilder.cc").read_text(encoding="utf-8")
    assert "return SolidRegistry::Create(*this, node);" in builder
    assert "SolidRegistry::Create(*this, toolNode, SolidRegistry::Context::BooleanTool)" in builder
    assert "PrecomputeVolume(" not in builder
    assert "GDML geometry is read by GeometryManager" in builder
    assert "BooleanToolContext(ownerVolumeName, booleanIndex, operand) + e.what()" in builder
    print("solid_registry: production C++ component dispatch, cache/rejection policy and parser metadata parity PASS")
    return metadata


def backend(metadata: dict) -> None:
    from run_m0_tests import workspace_source_fingerprint
    from test_run_summary import read_summary
    import test_geometry_a5 as a5
    supplied = os.environ.get("G4USIM_EXE")
    assert supplied, "--backend requires G4USIM_EXE (no hard-coded build path)"
    exe = Path(supplied).resolve()
    result = subprocess.run([str(exe), "--capabilities"], cwd=exe.parent, capture_output=True,
                            text=True, encoding="utf-8", errors="replace", timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    capabilities = json.loads(result.stdout)
    assert capabilities.get("source_fingerprint") == workspace_source_fingerprint(), "rebuild backend for current worktree"
    assert capabilities.get("solid_registry") == metadata, "main-agent integration must expose SolidRegistry::Describe()"
    a5.EXE = exe
    with tempfile.TemporaryDirectory(prefix="g4usim-solid-registry-backend-") as temp:
        runner = a5.Runner(Path(temp))
        a5.solids_case(runner)
        cases = {
            "Box": ("shape=box\nsize=20 mm,40 mm,60 mm", 20*40*60),
            "Tubs": ("shape=tubs\nparameters=0 mm,10 mm,20 mm,0 deg,360 deg", math.pi*100*40),
            "Sphere": ("shape=sphere\nparameters=0 mm,10 mm,0 deg,360 deg,0 deg,180 deg", 4/3*math.pi*1000),
            "Orb": ("shape=orb\nparameters=10 mm", 4/3*math.pi*1000),
            "Cone": ("shape=cone\nparameters=0 mm,10 mm,0 mm,20 mm,30 mm,0 deg,360 deg", math.pi*60/3*(100+200+400)),
            "Trd": ("shape=trd\ndx1=10 mm\ndx2=10 mm\ndy1=20 mm\ndy2=20 mm\ndz=30 mm", 8*10*20*30),
            "Trap": ("shape=trap\ndz=30 mm\ntheta=0 deg\nphi=0 deg\ndy1=20 mm\ndx1=10 mm\ndx2=10 mm\nalpha1=0 deg\ndy2=20 mm\ndx3=10 mm\ndx4=10 mm\nalpha2=0 deg", 8*10*20*30),
        }
        geometry, sources = "[global]\nversion=2\n" + a5.WORLD, ""
        for index, (name, (body, _)) in enumerate(cases.items()):
            x = -400 + index*120
            geometry += a5.volume(name, f"{body}\nposition={x} mm,0 mm,0 mm")
            sources += (f"[source.s{name}]\nparticle=proton\nenergy=10 MeV\nposition_type=point\n"
                        f"position={x} mm,0 mm,0 mm\nangular=isotropic\n")
        output, _ = runner.run(geometry, sources, 400)
        facts, _ = read_summary(output)
        assert facts["status"] == "completed", facts
        assert facts["summary_write_status"] == "completed", facts
        assert facts["macro_execution_status"] == "completed", facts
        assert facts["output_failure_status"] == "none", facts
        assert int(facts["run_count"]) == 1, facts
        assert int(facts["planned_event_count"]) == 400, facts
        assert int(facts["actual_completed_event_count"]) == 400, facts
        assert int(facts["actual_threads"]) == 2, facts
        fluence = a5.by_volume(output, "fluence_volume_summary", "raw_track_length_mm")
        dose = a5.by_volume(output, "dose_volume_summary", "raw_edep_MeV")
        for name, (_, expected) in cases.items():
            key = next(k for k in fluence if f"/{name}_PV#0" in k)
            assert abs(fluence[key]["volume_mm3"] / expected - 1) < 2e-3, name
            assert abs(dose[key]["mass_kg"] / (expected*1e-6) - 1) < 2e-3, name
        # Named dimensions remain parser inputs after they become schema-known.
        # Both tools here are rectangular, with independent analytic volumes.
        for name in ("Trd", "Trap"):
            body, removed_volume = cases[name]
            base = "[global]\nversion=2\n" + a5.WORLD + a5.volume("OperandTarget", "shape=box\nsize=100 mm,100 mm,100 mm")
            tool = f"\n[volume.OperandTarget.boolean.0]\noperation=subtraction\n{body}\n"
            source = "[source]\nparticle=proton\nenergy=10 MeV\nposition_type=point\nposition=40 mm,0 mm,0 mm\nisotropic=true\n"
            boolean_output, _ = runner.run(base + tool, source, 8)
            boolean_facts, _ = read_summary(boolean_output)
            assert boolean_facts["status"] == "completed", (name, boolean_facts)
            assert int(boolean_facts["actual_completed_event_count"]) == 8, name
            volumes = a5.by_volume(boolean_output, "fluence_volume_summary", "raw_track_length_mm")
            target = next(value for key, value in volumes.items() if "/OperandTarget_PV#0" in key)
            # G4BooleanSolid estimates cubic volume statistically, unlike primitives.
            assert abs(target["volume_mm3"] / (100**3 - removed_volume) - 1) < .02, (name, target)
            for invalid, expected_error in (
                    (tool.replace("dx1=10 mm\n", ""), "shape requires this length field"),
                    (tool + "material=G4_WATER\n", "ignored_boolean_key")):
                failed, log = runner.run(base + invalid, source, 1, expect_ok=False)
                # Configuration rejection can precede summary context creation.
                assert expected_error in log, (name, log[-2000:])
                assert not list(failed.glob("fluence_volume_summary*.csv")), name
        a5.failure_cases(runner)
    print("solid_registry: fresh real-backend capabilities, primitive analytic volumes/masses, A5 negatives PASS")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", action="store_true")
    parser.add_argument("--metadata-output", type=Path, help="optional component metadata evidence JSON")
    args = parser.parse_args()
    metadata = component()
    if args.metadata_output:
        args.metadata_output.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.backend:
        backend(metadata)


if __name__ == "__main__":
    main()
