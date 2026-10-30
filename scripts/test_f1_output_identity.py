"""F1 artifact registry/serialization component and real backend identity regression."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]

HARNESS = r'''
#include "Output/OutputManager.hh"
#include "Output/AnalysisOutput.hh"
#include "Scoring/ScoringMeshExport.hh"
#include "Config/InputProvenance.hh"
#include <filesystem>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <cstdlib>
using effective_config::Value;
// Runtime-only readback is outside this no-Geant4 registry/serializer component.
void OutputManager::RecordEffectiveConfigState(const std::string&) const {}
namespace AnalysisOutput {
bool IsOpen(){return false;}
void FillHit(const HitRecord&,int){}
void FillEvent(const EventEdepRecord&,int){}
void FillMeshCell(int,int,const std::string&,const std::string&,const std::string&,int,int,int,double,double,int,long long){}
}
namespace ScoringMeshExport {
bool HasMeshes(){return false;}
std::vector<Cell> CollectCells(){return {};}
double RelativeError(double,double,long long){return 0;}
void RecordInSummary(RunSummary&){}
}
void require(bool ok,const char* what){if(!ok)throw std::runtime_error(what);}
void fault(const std::string& text){
#ifdef _WIN32
 _putenv_s("G4USIM_TEST_OUTPUT_FAULT",text.c_str());
#else
 setenv("G4USIM_TEST_OUTPUT_FAULT",text.c_str(),1);
#endif
}
Value provenance(const std::string& id){
 Value::Array inputs;
 for(const auto& input:input_provenance::Snapshot())inputs.emplace_back(Value::Object{
  {"sequence",static_cast<std::int64_t>(input.sequence)},{"path",input.path},{"kind",input.kind},
  {"role",input.role},{"capture_method",input.capture_method},{"status",input.status},
  {"sha256",input.sha256?Value(*input.sha256):Value()},
  {"size_bytes",input.size_bytes?Value(static_cast<std::int64_t>(*input.size_bytes)):Value()},{"reason",input.reason}});
 return Value::Object{{"schema","g4usim_provenance_v1"},{"execution_id",id},
  {"build",Value::Object{{"git_commit","unknown"},{"git_source_state","unknown"},{"source_fingerprint",std::string(64,'a')},
   {"compiler_id","component"},{"compiler_version","unknown"},{"configuration","component"},{"geant4_version","not_linked"}}},
  {"input_coverage","project_readers_observed"},{"input_observation","bytes_read_not_semantic_acceptance"},
  {"input_exclusions",Value::Array{"geant4_internal_datasets","unobserved_native_command_inputs"}},{"inputs",inputs}};
}
void publish(OutputManager& output){
 auto& summary=output.GetRunSummary();summary.Set("status","completed");
 summary.SetProvenance(provenance(output.GetExecutionId()));
 auto evidence=output.CollectArtifactEvidence(true,true);
 std::vector<std::string> files;for(const auto& item:evidence)files.push_back(item.path);
 files.push_back(output.MakeOutputPath("run_summary.txt"));summary.SetGeneratedFiles(files);
 output.WriteRunSummary();
 RunSummary::ArtifactEvidence text;text.path=output.MakeOutputPath("run_summary.txt");
 text.execution_id=output.GetExecutionId();const auto digest=input_provenance::HashFile(text.path);
 text.sha256=digest.sha256;text.size_bytes=digest.size_bytes;text.integrity_status="hashed";
 evidence.push_back(text);summary.SetArtifactEvidence(evidence);output.WriteRunMetadataJson();
}
int main(int argc,char** argv){
 require(argc==2,"output directory required");std::filesystem::path base=std::filesystem::u8path(argv[1]);
 std::filesystem::create_directories(base);fault("");
 auto input=base/"input.ini";{std::ofstream f(input,std::ios::binary);f<<"[input]\r\nx=1\r\n";}
 input_provenance::ReadFile(input.u8string());
 input_provenance::MarkUnobserved("native_input","No project reader for this command");
 const auto observations=input_provenance::Snapshot().size();
 OutputManager output;output.SetOutputDir((base/"normal").u8string());std::filesystem::create_directories(base/"normal");
 const auto id=output.GetExecutionId();auto worker=output.CloneForThread(3);
 require(id==worker->GetExecutionId(),"clone must share process identity");
 worker->SetRunId(0);output.RecordRun(0,2,2);
 const auto artifact=base/"normal"/"worker.bin";{std::ofstream f(artifact,std::ios::binary);f.write("abc\0\r\n",6);}
 worker->RegisterGeneratedFile(artifact.u8string(),OutputManager::ArtifactScope::Thread,0,3);
 const auto runfile=base/"normal"/"run.bin";{std::ofstream f(runfile,std::ios::binary);f<<"run bytes";}
 output.RegisterGeneratedFile(runfile.u8string(),OutputManager::ArtifactScope::Run,0);
 publish(output);publish(output); // repeated finalization must not duplicate or hash old summary bytes
 require(input_provenance::Snapshot().size()==observations,"output hashing must not enter input ledger");
 const auto valid=output.CollectArtifactEvidence(true);
 require(valid.size()==4,"manifest includes normal/run/text/self");
 for(const auto& file:valid)require(file.execution_id==id,"all artifacts share execution");
 auto bad=provenance(id);std::get<Value::Object>(bad.data)["schema"]="future";
 bool rejected=false;try{output.GetRunSummary().SetProvenance(bad);}catch(const std::exception&){rejected=true;}
 require(rejected,"unknown protocol must be rejected atomically");
 for(const bool gap:{false,true}) {
  bad=provenance(id);auto& rows=std::get<Value::Array>(std::get<Value::Object>(bad.data).at("inputs").data);
  auto& row=std::get<Value::Object>(rows.back().data);
  if(gap)row["sequence"]=4;else row["path"]="";
  rejected=false;try{output.GetRunSummary().SetProvenance(bad);}catch(const std::exception&){rejected=true;}
  require(rejected,"empty unknown paths and observation sequence gaps must be rejected");
 }
 output.WriteRunMetadataJson();
 auto duplicate=valid;duplicate.push_back(valid.front());rejected=false;
 try{output.GetRunSummary().SetArtifactEvidence(duplicate);}catch(const std::exception&){rejected=true;}
 require(rejected,"duplicate artifact must be rejected");
 auto wrong=valid;wrong.front().scope=RunSummary::ArtifactScope::Thread;wrong.front().thread_id.reset();rejected=false;
 try{output.GetRunSummary().SetArtifactEvidence(wrong);}catch(const std::exception&){rejected=true;}
 require(rejected,"thread scope must carry real nonnegative identity");
 for(const bool prior:{false,true}){
  OutputManager missing;missing.SetOutputDir((base/(prior?"prior":"missing")).u8string());
  std::filesystem::create_directories(std::filesystem::u8path(missing.GetOutputDir()));
  const auto path=std::filesystem::u8path(missing.MakeOutputPath("gone.bin"));
  {std::ofstream f(path);f<<"closed";}missing.RegisterGeneratedFile(path.u8string(),OutputManager::ArtifactScope::Process);
  std::filesystem::remove(path);if(prior)missing.RecordOutputFailure("earlier_failure","first cause");
  const auto evidence=missing.CollectArtifactEvidence();
  require(evidence.size()==1 && evidence[0].integrity_status=="unavailable" && !evidence[0].sha256 && !evidence[0].size_bytes,"missing file stays unavailable");
  require(missing.GetGeneratedFiles().size()==1,"missing registration must not vanish");
  require(missing.GetOutputFailure().stage==(prior?"earlier_failure":"artifact_integrity"),"first failure remains authoritative");
  auto& summary=missing.GetRunSummary();summary.SetProvenance(provenance(missing.GetExecutionId()));
  summary.Set("status","failed");missing.WriteRunSummary();
  summary.SetArtifactEvidence(missing.CollectArtifactEvidence(true));missing.WriteRunMetadataJson();
 }
 for(const auto token:{"metadata_write_master","metadata_close_master"}){
  OutputManager failed;failed.SetOutputDir((base/token).u8string());
  auto& summary=failed.GetRunSummary();summary.SetProvenance(provenance(failed.GetExecutionId()));failed.WriteRunSummary();
  summary.SetArtifactEvidence(failed.CollectArtifactEvidence(true));fault(token);bool threw=false;
  try{failed.WriteRunMetadataJson();}catch(const std::exception&){threw=true;}fault("");
  require(threw,"metadata fault must propagate");
  require(failed.GetOutputFailure().stage==(std::string(token)=="metadata_write_master"?"run_metadata_write":"run_metadata_close"),"metadata stage retained");
  for(const auto& file:failed.GetGeneratedFiles())require(std::filesystem::u8path(file).filename()!="run_metadata.json","failed metadata not registered");
 }
 std::cout<<id<<"\n";
}
'''


def component():
    configured = os.environ.get("CXX")
    compiler = shlex.split(configured, posix=os.name != "nt") if configured else []
    if not compiler:
        found = next((shutil.which(name) for name in ("g++", "clang++", "cl") if shutil.which(name)), None)
        assert found, "C++17 compiler required (set CXX or initialize compiler PATH)"
        compiler = [found]
    with tempfile.TemporaryDirectory(prefix="g4usim-f1-output-component-") as temporary:
        folder = Path(temporary)
        # CsvWriter includes this header for its Geant4-only worker fault gate.
        # This component does not define G4MULTITHREADED or test that runtime gate.
        (folder / "G4Threading.hh").write_text("#pragma once\n", encoding="utf-8")
        source = folder / "component.cc"
        source.write_text(HARNESS, encoding="utf-8")
        executable = folder / ("component.exe" if os.name == "nt" else "component")
        files = [source] + [ROOT / f"src/{name}.cc" for name in (
            "Output/OutputManager", "Output/RunSummary", "Output/CsvWriter", "Output/Histogram1D",
            "Utils/FileUtils", "Utils/StringUtils", "Config/EffectiveConfig", "Config/IniReader",
            "Config/InputProvenance", "Scoring/HistoryStatistics")]
        if Path(compiler[0]).stem.lower() in ("cl", "clang-cl"):
            args = compiler + ["/nologo", "/std:c++17", "/utf-8", "/EHsc", "/I" + str(folder), "/I" + str(ROOT / "include")]
            args += [str(path) for path in files] + ["/Fe:" + str(executable)]
        else:
            args = compiler + ["-std=c++17", "-Wall", "-Wextra", "-pedantic", "-pthread", "-I", str(folder), "-I", str(ROOT / "include")]
            args += [str(path) for path in files] + ["-o", str(executable)]
        built = subprocess.run(args, cwd=folder, capture_output=True, text=True, timeout=180)
        assert built.returncode == 0, built.stdout + built.stderr
        identifiers = []
        for label in ("one", "two"):
            output = folder / label
            run = subprocess.run([str(executable), str(output)], capture_output=True, text=True, timeout=40)
            assert run.returncode == 0, run.stdout + run.stderr
            identifier = run.stdout.strip()
            assert re.fullmatch(r"[0-9a-f]{32}", identifier), identifier
            identifiers.append(identifier)
            metadata = json.loads((output / "normal/run_metadata.json").read_text(encoding="utf-8"))
            assert metadata["provenance"]["execution_id"] == identifier
            verify(metadata, output / "normal", expected_runs={0})
            for failure in ("missing", "prior"):
                failed = json.loads((output / failure / "run_metadata.json").read_text(encoding="utf-8"))
                unavailable = [x for x in failed["generated_files"] if x["integrity_status"] == "unavailable"]
                assert len(unavailable) == 1 and Path(unavailable[0]["path"]).name == "gone.bin"
                assert unavailable[0]["sha256"] is None and unavailable[0]["size_bytes"] is None
                assert unavailable[0]["reason"] and failed["values"]["status"] == "failed"
        assert len(set(identifiers)) == 2, identifiers
    print("PASS: F1 registry/serializer component; shared execution, exact bytes, unavailable, self exclusion, first failure")


def verify(metadata, directory, expected_runs, *, allow_unavailable=False):
    assert metadata["schema"] == "run_metadata_json_v1"
    provenance = metadata["provenance"]
    assert provenance["schema"] == "g4usim_provenance_v1"
    assert re.fullmatch(r"[0-9a-f]{32}", provenance["execution_id"])
    assert provenance["input_coverage"] == "project_readers_observed"
    assert provenance["input_observation"] == "bytes_read_not_semantic_acceptance"
    assert len(provenance["input_exclusions"]) >= 2
    sequences = [x["sequence"] for x in provenance["inputs"]]
    assert sequences == list(range(1, len(sequences) + 1))
    assert all(type(item["path"]) is str and item["path"] for item in provenance["inputs"])
    paths = set()
    for artifact in metadata["generated_files"]:
        name = Path(artifact["path"]).name
        assert artifact["path"] not in paths
        paths.add(artifact["path"])
        assert artifact["execution_id"] == provenance["execution_id"]
        scope = artifact["scope"]
        assert scope in ("process", "run", "thread")
        if scope == "process":
            assert artifact["run_id"] is None and artifact["thread_id"] is None
        else:
            assert type(artifact["run_id"]) is int and artifact["run_id"] in expected_runs
            if scope == "run":
                assert artifact["thread_id"] is None
            else:
                assert type(artifact["thread_id"]) is int and artifact["thread_id"] >= 0
        if artifact["integrity_status"] == "unavailable":
            assert allow_unavailable and name != "run_metadata.json", artifact
            assert artifact["sha256"] is None and artifact["size_bytes"] is None and artifact["reason"]
            continue
        if name == "run_metadata.json":
            assert scope == "process" and artifact["integrity_status"] == "self_reference_excluded"
            assert artifact["sha256"] is None and artifact["size_bytes"] is None
        else:
            data = (directory / name).read_bytes()
            assert artifact["integrity_status"] == "hashed"
            assert type(artifact["size_bytes"]) is int and artifact["size_bytes"] == len(data)
            assert artifact["sha256"] == hashlib.sha256(data).hexdigest(), artifact
            if name == "run_summary.txt":
                assert scope == "process"
            if artifact["schema"] == "g4usim_effective_config_v1":
                snapshot = json.loads(data)
                if snapshot.get("run_id") is None:
                    assert scope == "process"
                elif snapshot.get("thread_id", -1) >= 0:
                    assert scope == "thread" and artifact["thread_id"] == snapshot["thread_id"]
                else:
                    assert scope == "run"


def backend(executable):
    assert executable and executable.is_file(), "Set G4USIM_EXE or --executable to the new F1 build"
    identifiers = set()
    with tempfile.TemporaryDirectory(prefix="g4usim-f1-output-backend-") as temporary:
        work = Path(temporary)
        for fmt in ("csv", "root", "both"):
            for threads in (1, 2, 4):
                label = f"{fmt}-{threads}"
                output = work / label
                ini = work / (label + ".ini")
                text = (f"[run]\nthreads={threads}\nseed=819\n[output]\nformat={fmt}\n"
                        f"[geometry]\ntemplate=simple_box\nconfig={(ROOT / 'config/geometry/simple_box.ini').as_posix()}\n"
                        "[physics]\nreference=\nmodules=G4EmStandardPhysics_option4\n"
                        "[source]\nparticle=proton\nenergy=1 MeV\nposition_type=point\nposition=0,0,-10 mm\ndirection=+z\n")
                ini.write_text(text, encoding="utf-8")
                accepted = ini.read_bytes()
                macro = work / (label + ".mac")
                macro.write_text("/run/initialize\n/run/beamOn 2\n/run/beamOn 3\n", encoding="utf-8")
                process = subprocess.run([str(executable), "--config", str(ini), "--macro", str(macro), "--output", str(output)],
                                         cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
                assert process.returncode == 0, process.stdout[-3000:] + process.stderr
                metadata = json.loads((output / "run_metadata.json").read_text(encoding="utf-8"))
                assert metadata["values"]["status"] == "completed"
                assert {r["run_id"] for r in metadata["runs"]} == {0, 1}
                verify(metadata, output, expected_runs={0, 1})
                identifier = metadata["provenance"]["execution_id"]
                assert identifier not in identifiers
                identifiers.add(identifier)
                observations = [x for x in metadata["provenance"]["inputs"] if Path(x["path"]) == ini]
                assert observations and all(x["sha256"] == hashlib.sha256(accepted).hexdigest() and x["size_bytes"] == len(accepted) for x in observations)
                before = metadata["provenance"]["inputs"]
                ini.unlink()
                assert json.loads((output / "run_metadata.json").read_text(encoding="utf-8"))["provenance"]["inputs"] == before
                print("PASS F1 output", label)
        # No-run and dry-run publish configuration identity without invented runs.
        for label, flags in (("no-run", []), ("dry-run", ["--dry-run"])):
            output = work / label
            ini = work / (label + ".ini")
            ini.write_text(text, encoding="utf-8")
            macro = work / (label + ".mac")
            macro.write_text("/control/echo F1_NO_RUN\n", encoding="utf-8")
            process = subprocess.run([str(executable), "--config", str(ini), "--macro", str(macro),
                                      "--output", str(output), *flags], cwd=ROOT, capture_output=True,
                                     text=True, encoding="utf-8", errors="replace", timeout=120)
            assert process.returncode == 0, process.stdout[-3000:] + process.stderr
            metadata = json.loads((output / "run_metadata.json").read_text(encoding="utf-8"))
            assert metadata["runs"] == []
            verify(metadata, output, expected_runs=set())
            assert not list(output.glob("effective_config_run_*.json"))
        # BeginRun failures are real attempted runs, not permission to fabricate
        # associations or lose their manifest to a secondary serializer error.
        for threads in (1, 2):
            for fault_token, stage in (("begin_scoring_t0", "scoring_begin_run"),
                                       ("begin_set_run_id_t0", "run_begin_set_run_id"),
                                       ("artifact_hash_master", "artifact_integrity")):
                label = f"failure-{threads}-{fault_token}"
                output = work / label
                ini = work / (label + ".ini")
                ini.write_text(text.replace("threads=4", f"threads={threads}").replace("format=both", "format=csv"), encoding="utf-8")
                macro = work / (label + ".mac")
                macro.write_text("/run/initialize\n/run/beamOn 2\n/run/beamOn 3\n/control/echo F1_AFTER_RUNS\n", encoding="utf-8")
                environment = os.environ.copy()
                environment["G4USIM_TEST_OUTPUT_FAULT"] = fault_token
                process = subprocess.run([str(executable), "--config", str(ini), "--macro", str(macro), "--output", str(output)],
                                         cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace",
                                         timeout=120, env=environment)
                assert process.returncode != 0, process.stdout[-3000:] + process.stderr
                facts = dict(line.split(" = ", 1) for line in (output / "run_summary.txt").read_text(encoding="utf-8").splitlines() if " = " in line)
                assert facts["status"] == "failed" and facts["output_failure_stage"] == stage, facts
                metadata_path = output / "run_metadata.json"
                assert metadata_path.is_file(), (fault_token, process.stderr)
                metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
                assert metadata["values"]["status"] == "failed"
                assert metadata["values"]["output_failure_stage"] == stage
                actual_runs = {r["run_id"] for r in metadata["runs"]}
                assert 0 in actual_runs, metadata["runs"]
                verify(metadata, output, expected_runs=actual_runs, allow_unavailable=fault_token == "artifact_hash_master")
    print("PASS: real F1 formats/workers/two runs, identity/hash/scope, no-run/dry-run and BeginRun failures")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--component", action="store_true")
    parser.add_argument("--executable", default=os.environ.get("G4USIM_EXE"))
    args = parser.parse_args()
    if args.component:
        component()
    else:
        backend(Path(args.executable) if args.executable else None)

if __name__ == "__main__":
    main()
