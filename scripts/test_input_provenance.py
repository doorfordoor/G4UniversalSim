#!/usr/bin/env python3
"""Independent C++17 exact-byte hashing and atomic INI provenance regression."""
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
#include "Config/InputProvenance.hh"
#include "Config/IniReader.hh"
#include <filesystem>
#include <fstream>
#include <iostream>
#include <stdexcept>
using namespace input_provenance;
int main() {
 auto require=[](bool ok){if(!ok)throw std::runtime_error("input invariant failed");};
 require(Sha256("")=="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855");
 require(Sha256("abc")=="ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad");
 require(Sha256(std::string(1000000,'a'))=="cdc76e5c9914fb9281a1c7e284d73e67f1809a48a497200e046d39ccc7112cd0");
 for(int n: {1,55,56,63,64,65,119,120,127,128,129}) {
  std::string bytes;for(int i=0;i<n;++i)bytes+=static_cast<char>(i%256);
  std::cout<<n<<" "<<Sha256(bytes)<<"\n";
 }
 const auto path=std::filesystem::u8path(u8"配置.ini");
 const std::string bytes="[Source]\r\nEnergy = 1 keV\r\n[source]\r\nenergy = 2 keV # accepted\r\n";
 {std::ofstream f(path,std::ios::binary);f<<bytes;}
 auto input=ReadFile(path.u8string());require(input.bytes==bytes && input.sha256==Sha256(bytes));
 IniReader ini;ini.Load(path.u8string());require(ini.GetInputSha256()==input.sha256);
 require(ini.GetString("SOURCE","ENERGY")=="2 keV");
 auto declarations=ini.GetDeclarations();require(declarations.size()==2);
 require(declarations[0].value=="1 keV" && declarations[1].value=="2 keV");
 require(declarations[0].lineNumber==2 && declarations[1].lineNumber==4);
 require(declarations[0].originalSection=="Source" && declarations[1].originalSection=="source");
 require(declarations[1].rawLine=="energy = 2 keV # accepted\r");
 require(!declarations[0].consumed && declarations[1].consumed);
 require(ini.GetFields().size()==1 && ini.GetFields()[0].consumed);
 auto sections=ini.GetSectionDeclarations();require(sections.size()==2 && sections[0].lineNumber==1 && sections[1].lineNumber==3);
 require(ini.GetDuplicates().size()==2);
 // Hash and parsed values describe accepted bytes even if the file changes later.
 {std::ofstream f(path,std::ios::binary);f<<"[broken\n";}
 require(ini.GetInputSha256()==Sha256(bytes) && ini.GetString("source","energy")=="2 keV");
 for(const auto& bad: {path.u8string(), std::string("missing.ini"), std::string(".")}) {
  bool rejected=false;try{ini.Load(bad);}catch(const std::exception&){rejected=true;}
  require(rejected && ini.GetFilename()==path.u8string() && ini.GetInputSha256()==input.sha256);
  require(ini.GetFields().size()==1 && ini.GetFields()[0].consumed && ini.GetDeclarations().size()==2 && ini.GetDuplicates().size()==2);
 }
 {std::ofstream f(path,std::ios::binary);f<<"[new]\nx=3\n";}
 ini.Load(path.u8string());require(!ini.HasSection("source") && ini.GetDeclarations().size()==1 && ini.GetDuplicates().empty());
 require(ini.GetInputSha256()==Sha256("[new]\nx=3\n"));
 ini.LoadBytes("virtual.ini","[memory]\nx=4\n");require(ini.GetFilename()=="virtual.ini" && ini.GetInputSha256()==Sha256("[memory]\nx=4\n"));
 bool malformed=false;try{ini.LoadBytes("bad.ini","[broken\n");}catch(const std::exception&){malformed=true;}
 require(malformed && ini.GetFilename()=="virtual.ini" && ini.GetString("memory","x")=="4");
 ini.Clear();require(ini.GetInputSha256().empty() && ini.GetDeclarations().empty() && ini.GetSectionDeclarations().empty());
}
'''
    with tempfile.TemporaryDirectory(prefix="g4usim-input-provenance-") as temp:
        folder = Path(temp)
        test = folder / "input.cc"
        test.write_text(source, encoding="utf-8")
        exe = folder / ("input.exe" if os.name == "nt" else "input")
        inputs = [str(test)] + [str(root / f"src/{name}.cc") for name in
                  ("Config/IniReader", "Config/InputProvenance", "Utils/StringUtils")]
        if Path(compiler[0]).stem.lower() in ("cl", "clang-cl"):
            args = compiler + ["/nologo", "/std:c++17", "/utf-8", "/EHsc", "/I" + str(root / "include")]
            args += inputs + ["/Fe:" + str(exe)]
        else:
            args = compiler + ["-std=c++17", "-Wall", "-Wextra", "-pedantic", "-I", str(root / "include")]
            args += inputs + ["-o", str(exe)]
        built = subprocess.run(args, cwd=folder, capture_output=True, text=True, timeout=120)
        assert built.returncode == 0, built.stdout + built.stderr
        ran = subprocess.run([str(exe)], cwd=folder, capture_output=True, text=True, timeout=30)
        assert ran.returncode == 0, ran.stdout + ran.stderr
        for line in ran.stdout.splitlines():
            n, digest = line.split()
            assert digest == hashlib.sha256(bytes(i % 256 for i in range(int(n)))).hexdigest(), line
        assert len(ran.stdout.splitlines()) == 11
    print("Input provenance standalone regression passed")


if __name__ == "__main__":
    main()
