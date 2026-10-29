#!/usr/bin/env python3
"""Independent C++17 consumer provenance, same-value mutation and clone regression."""
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
#include "Config/EffectiveConfigSupport.hh"
#include <stdexcept>
using namespace effective_config;
int main(){
 auto require=[](bool ok){if(!ok)throw std::runtime_error("consumer invariant failed");};
 IniReader ini;ini.LoadBytes("accepted.ini","[source]\nenergy=1 MeV\nenergy=2 MeV\n");
 ConsumerState state;state.reader=ini;
 auto field=state.Make("/source/energy",2.0,"MeV","source",{"energy"});
 require(field.requested_known && field.origins.size()==3);
 require(field.origins[1].disposition=="shadowed" && field.origins[2].disposition=="accepted");
 require(field.origins[2].input_sha256==ini.GetInputSha256());
 auto implicit=state.Make("/source/verbose",0,"","source",{"verbose"});require(!implicit.requested_known);
 state.Accept(ini,{field,implicit});
 auto clone=state.Clone();Origin origin;origin.kind="macro";origin.file="macro.mac";origin.line=7;
 clone->Confirm({field,implicit},"/AIHL/source/energy 2 MeV",origin,false,{"/source/energy"});
 require(clone->fields[0].origins.size()==4 && state.fields[0].origins.size()==3);
 require(clone->fields[1].origins.size()==1);
 // A fresh projection still contains INI request=2 even after energy=3.
 // An unrelated next command must preserve the accepted request, not restore INI.
 auto consecutive=state.Clone();auto changedEnergy=field;changedEnergy.resolved=3.0;
 consecutive->Confirm({changedEnergy,implicit},"/AIHL/source/energy 3 MeV",origin,false,{"/source/energy"});
 const auto acceptedRequest=consecutive->fields[0].requested.ToJson();
 auto replayEnergy=state.Make("/source/energy",3.0,"MeV","source",{"energy"});
 auto changedVerbose=implicit;changedVerbose.resolved=1;
 consecutive->Confirm({replayEnergy,changedVerbose},"/AIHL/source/verbose 1",origin,false,{"/source/verbose"});
 require(consecutive->fields[0].requested.ToJson()==acceptedRequest && consecutive->fields[0].requested_known);
 require(consecutive->fields[0].origins.back().raw=="/AIHL/source/energy 3 MeV");
 require(consecutive->fields[1].origins.back().raw=="/AIHL/source/verbose 1");
 auto unknown=state.Clone();auto speculative=implicit;speculative.requested="invented by rebuild";speculative.requested_known=true;
 unknown->Confirm({field,speculative},"/AIHL/source/energy 2 MeV",origin,false,{"/source/energy"});
 require(!unknown->fields[1].requested_known);
 clone->Confirm(clone->fields,"/gps/ene/mono 9 MeV",origin,true);
 require(clone->fields[0].application_status==ApplicationStatus::Unknown);
 require(state.fields[0].application_status==ApplicationStatus::NotApplied);
 state.Record(Value::Object{{"path","/source/energy"},{"observed",2.0}});
 auto receipts=std::get<Value::Array>(state.Evidence().data);require(receipts.size()==1);
 auto receipt=std::get<Value::Object>(receipts[0].data);
 require(std::get<std::int64_t>(receipt.at("configuration_generation").data)==1);
 require(std::get<std::string>(receipt.at("resolved_sha256").data)==input_provenance::Sha256(field.resolved.ToJson()));
 require(std::get<Value::Array>(clone->Evidence().data).empty());
}
'''
    with tempfile.TemporaryDirectory(prefix="g4usim-input-provenance-") as temp:
        folder = Path(temp)
        test = folder / "input.cc"
        test.write_text(source, encoding="utf-8")
        exe = folder / ("input.exe" if os.name == "nt" else "input")
        inputs = [str(test)] + [str(root / f"src/{name}.cc") for name in
                  ("Config/IniReader", "Config/InputProvenance", "Config/EffectiveConfig", "Utils/StringUtils")]
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

    print("Consumer state standalone regression passed")


if __name__ == "__main__":
    main()
