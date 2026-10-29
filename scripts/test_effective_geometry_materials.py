#!/usr/bin/env python3
"""2C geometry/material real parser and optional backend projection regression."""
import hashlib
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import tempfile


def main():
    root = Path(__file__).resolve().parents[1]
    configured = os.environ.get("CXX")
    compiler = shlex.split(configured, posix=os.name != "nt") if configured else []
    if not compiler:
        found = next((shutil.which(name) for name in ("g++", "clang++", "cl") if shutil.which(name)), None)
        assert found, "C++17 compiler required (set CXX or configure PATH)"
        compiler = [found]
    source = r'''
#include "Materials/MaterialIniReader.hh"
#include "Geometry/StlReader.hh"
#include "Config/InputProvenance.hh"
#include <fstream>
#include <sstream>
#include <stdexcept>
int main(){
 auto require=[](bool value){if(!value)throw std::runtime_error("geometry/material input invariant failed");};
 const std::string bytes="[element.C]\r\nsymbol=C\r\nz=6\r\na=12 g/mole\r\n[material.Coating]\r\ndensity=1 g/cm3\r\ndensity=2 g/cm3\r\ncomponents=C:1\r\n";
 {std::ofstream out("material.ini",std::ios::binary);out<<bytes;}
 MaterialIniReader reader;reader.Load("material.ini");
 require(reader.GetInputReader().GetInputSha256()==input_provenance::Sha256(bytes));
 require(reader.GetInputReader().GetDeclarations().size()==6);
 require(reader.GetInputReader().GetDuplicates().size()==1);
 require(reader.GetMaterialDefinition("Coating").densityText=="2 g/cm3");
 {std::ofstream out("material.ini",std::ios::binary);out<<"[material.Bad]\ndensity=nan\ncomponents=C:1\n";}
 bool failed=false;try{reader.Load("material.ini");}catch(const std::exception&){failed=true;}
 require(failed && reader.HasMaterial("Coating") && !reader.HasMaterial("Bad"));
 require(reader.GetInputReader().GetInputSha256()==input_provenance::Sha256(bytes));
 std::ostringstream stl;stl<<"solid tetra\n";
 const double vertices[4][3]={{0,0,0},{1,0,0},{0,1,0},{0,0,1}};
 const int faces[4][3]={{0,2,1},{0,1,3},{0,3,2},{1,2,3}};
 for(const auto& face:faces){stl<<"facet normal 0 0 0\nouter loop\n";for(int i:face)stl<<"vertex "<<vertices[i][0]<<" "<<vertices[i][1]<<" "<<vertices[i][2]<<"\n";stl<<"endloop\nendfacet\n";}stl<<"endsolid tetra\n";
 {std::ofstream out("mesh.stl",std::ios::binary);out<<stl.str();}
 const auto mesh=StlReader::Read("mesh.stl",1);
 require(mesh.inputSha256==input_provenance::Sha256(stl.str()) && mesh.inputPath=="mesh.stl" && !mesh.binary);
 require(mesh.triangles.size()==4 && mesh.volume>0 && mesh.lengthUnit==1);
}
'''
    with tempfile.TemporaryDirectory(prefix="g4usim-input-provenance-") as temp:
        folder = Path(temp)
        test = folder / "input.cc"
        test.write_text(source, encoding="utf-8")
        exe = folder / ("input.exe" if os.name == "nt" else "input")
        inputs = [str(test)] + [str(root / f"src/{name}.cc") for name in
                  ("Config/IniReader", "Config/InputProvenance", "Materials/MaterialIniReader", "Materials/MaterialCommandParser", "Geometry/StlReader", "Utils/CommandParser", "Utils/StringUtils")]
        if Path(compiler[0]).stem.lower() in ("cl", "clang-cl"):
            args = compiler + ["/nologo", "/std:c++17", "/utf-8", "/EHsc", "/I" + str(root / "include")]
            args += inputs + ["/Fe:" + str(exe)]
        else:
            args = compiler + ["-std=c++17", "-Wall", "-Wextra", "-pedantic", "-I", str(root / "include")]
            args += inputs + ["-o", str(exe)]
        include = os.environ.get("GEANT4_INCLUDE_DIR")
        assert include and Path(include, "G4SystemOfUnits.hh").is_file(), "set GEANT4_INCLUDE_DIR for independent parser compilation"
        args += [("/I" if Path(compiler[0]).stem.lower() in ("cl", "clang-cl") else "-I") + include]
        built = subprocess.run(args, cwd=folder, capture_output=True, text=True, timeout=120)
        assert built.returncode == 0, built.stdout + built.stderr
        ran = subprocess.run([str(exe)], cwd=folder, capture_output=True, text=True, timeout=30)
        assert ran.returncode == 0, ran.stdout + ran.stderr

    print("Geometry/material exact-input standalone regression passed")


def backend():
    import json
    executable = Path(os.environ["G4USIM_EXE"])
    assert executable.is_file(), executable
    with tempfile.TemporaryDirectory(prefix="g4usim-2c-geom-material-") as temp:
        work=Path(temp)
        material=work/"materials.ini"
        material.write_text("[element.C]\nsymbol=C\nz=6\na=12 g/mole\n[material.Coating]\ndensity=1 g/cm3\ndensity=2 g/cm3\ncomponents=C:1\n",encoding="utf-8")
        copies=work/"copies.csv";copies.write_text("x_mm,y_mm,z_mm\n-20,0,0\n20,0,0\n",encoding="utf-8")
        geometry=work/"geometry.ini"
        geometry.write_text("[world]\nshape=box\nsize=100 mm,100 mm,100 mm\nmaterial=G4_Galactic\n[volume.A/~B]\nparent=world\nshape=box\nsize=2 mm,3 mm,4 mm\nmaterial=G4_AIR\nmaterial=Coating\nplacement=parameterised\ncopies_file="+copies.as_posix()+"\n",encoding="utf-8")
        main_ini=work/"main.ini"
        main_ini.write_text("[materials]\nconfig="+material.as_posix()+"\n[geometry]\ntemplate=hierarchical\nconfig="+geometry.as_posix()+"\ncheck_overlaps=false\n",encoding="utf-8")
        target=work/"snapshot.json"
        process=subprocess.run([str(executable),"--config",str(main_ini),"--dump-effective-config",str(target)],cwd=work,capture_output=True,text=True,timeout=90)
        assert process.returncode==0,process.stdout+process.stderr
        document=json.loads(target.read_text());fields={f["path"]:f for f in document["fields"]}
        density=fields["/materials/objects/material:Coating/density"]
        assert density["resolved"]==2 and density["unit"]=="g/cm3"
        declarations=[o for o in density["origins"] if o["key"]=="density"]
        assert [o["raw"] for o in declarations]==["1 g/cm3","2 g/cm3"]
        assert declarations[0]["disposition"]=="shadowed" and declarations[1]["disposition"]=="accepted"
        assert all(o["input_sha256"]==hashlib.sha256(material.read_bytes()).hexdigest() for o in declarations)
        assert fields["/geometry/objects/A~1~0B/size"]["resolved"]==[2,3,4]
        assert len(fields["/geometry/objects/A~1~0B/copies"]["resolved"])==2
        inputs=fields["/geometry/input_files"]["resolved"]
        assert {r["sha256"] for r in inputs}=={hashlib.sha256(p.read_bytes()).hexdigest() for p in (geometry,copies)}
        assert fields["/geometry/objects/A~1~0B/shape"]["application_status"]=="not_applied"
        assert not (work/"output").exists()
    print("Geometry/material backend projection passed")


if __name__ == "__main__":
    import sys
    backend() if "--backend" in sys.argv else main()
