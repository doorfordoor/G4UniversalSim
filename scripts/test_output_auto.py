"""Explicit auto format: standalone manager/consumer model and real backend matrix."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import tempfile
from test_f1_output_identity import HARNESS as IDENTITY_HARNESS, verify

ROOT = Path(__file__).resolve().parents[1]
PREFIX = IDENTITY_HARNESS.split("void require", 1)[0].replace(
    "void OutputManager::RecordEffectiveConfigState(const std::string&) const {}", "")
PREFIX = PREFIX.replace("bool IsOpen(){return false;}", "bool analysisOpen=false;bool IsOpen(){return analysisOpen;}")
SOURCE = PREFIX + r"""
#include <thread>
#include <vector>
void require(bool ok,const char* message){if(!ok)throw std::runtime_error(message);}
effective_config::Field field(const OutputManager& output){
 for(const auto& f:output.ExportEffectiveConfigFields())if(f.path=="/output/format")return f;
 throw std::runtime_error("format field missing");
}
int main(int argc,char** argv){
 using Format=OutputManager::Format;using effective_config::Origin;
 require(argc==2,"component output path required");
 OutputManager output;
 require(output.GetRequestedFormat()==Format::Csv && output.GetFormat()==Format::Csv,"omitted policy stays CSV");
 require(output.FormatSelectionReason()=="default_csv","default reason must remain explicit");
 bool refused=false;try{output.SetFormat(Format::Auto);}catch(const std::exception&){refused=true;}
 require(refused && output.GetRequestedFormat()==Format::Csv,"no-selector auto must reject atomically");
 for(const auto& token:{"csv+root","root+csv","both"})require(OutputManager::ParseFormat(token)==Format::Both,"aliases preserve both");
 require(OutputManager::ParseFormat(" AUTO ")==Format::Auto,"explicit auto parser");
 bool enabled=false,hits=true,events=true;
 output.SetAutoFormatSelector([&](){return enabled && (hits || events);});
 output.SetFormat(Format::Auto);
 for(int mask=0;mask<8;++mask){
  enabled=(mask&4)!=0;hits=(mask&2)!=0;events=(mask&1)!=0;
  const bool selected=enabled && (hits || events);
  require(output.GetFormat()==(selected?Format::Root:Format::Csv),"final enabled/hits/event truth table");
  require(output.WritesRoot()==selected && output.WritesCsv()!=selected,"writer gates must use resolved format");
  require(enabled==((mask&4)!=0) && hits==((mask&2)!=0) && events==((mask&1)!=0),"selection cannot change flags");
 }
 enabled=true;hits=true;events=false;
 for(const int count:{1,2,4}){
  std::vector<std::unique_ptr<OutputManager>> clones;std::vector<int> answers(count);
  for(int i=0;i<count;++i)clones.push_back(output.CloneForThread(i));
  std::vector<std::thread> readers;
  for(int i=0;i<count;++i)readers.emplace_back([&,i](){answers[i]=clones[i]->GetRequestedFormat()==Format::Auto && clones[i]->GetFormat()==Format::Root;});
  for(auto& reader:readers)reader.join();for(auto answer:answers)require(answer==1,"clones share read-only final selector");
 }
 IniReader input;input.LoadBytes("component.ini","[output]\nformat=auto\n");output.AcceptEffectiveConfig(input);
 auto initial=field(output);require(initial.requested.ToJson()=="\"auto\"" && initial.resolved.ToJson()=="\"root\"","typed requested versus resolved");
 Origin origin;origin.kind="macro";origin.file="commands.mac";origin.line=1;
 output.SetFormat(Format::Root);output.ConfirmEffectiveConfigMutation("/AIHL/output/setFormat root",origin);
 auto explicitRoot=field(output);require(explicitRoot.requested.ToJson()=="\"root\"" && explicitRoot.origins.back().kind=="macro","same-resolution setFormat must record successful source");
 output.SetFormat(Format::Auto);output.ConfirmEffectiveConfigMutation("/AIHL/output/setFormat auto",origin);
 const auto before=field(output);enabled=false;
 output.ConfirmEffectiveConfigMutation("/AIHL/scoring/enable false",origin);
 const auto derived=field(output);
 require(derived.requested.ToJson()=="\"auto\"" && derived.resolved.ToJson()=="\"csv\"","dependency changes resolution, not policy request");
 require(derived.configuration_generation>before.configuration_generation && derived.origins.back().kind=="derived" && derived.origins.back().raw=="/AIHL/scoring/enable false","accepted dependency provenance");
 require(derived.origins.back().disposition=="derived","dependency is not an explicit format override");
 events=false;output.ConfirmEffectiveConfigMutation("/AIHL/scoring/eventEdep false",origin);
 require(field(output).configuration_generation==derived.configuration_generation,"irrelevant dependency change is not output transaction");
 const auto unchanged=field(output).requested.ToJson();
 refused=false;try{output.SetAutoFormatSelector({});}catch(const std::exception&){refused=true;}
 require(refused && field(output).requested.ToJson()==unchanged,"selector removal rejects active auto atomically");
 output.SetOutputDir(argv[1]);output.SetRunId(0);output.OpenEventEdepFile();
 refused=false;try{output.SetFormat(Format::Both);}catch(const std::exception&){refused=true;}
 require(refused && output.GetRequestedFormat()==Format::Auto,"open CSV rejects format changes");
 refused=false;try{output.SetAutoFormatSelector([](){return true;});}catch(const std::exception&){refused=true;}
 require(refused && output.GetFormat()==Format::Csv,"open CSV rejects selector change");output.Close();
 AnalysisOutput::analysisOpen=true;refused=false;
 try{output.SetFormat(Format::Root);}catch(const std::exception&){refused=true;}
 AnalysisOutput::analysisOpen=false;require(refused && output.GetRequestedFormat()==Format::Auto,"open ROOT rejects changes");
 for(const auto token:{"csv","root","both"}){
  output.SetFormat(OutputManager::ParseFormat(token));require(std::string(OutputManager::FormatName(output.GetFormat()))==token,"explicit modes do not consult auto");
 }
 std::cout<<"PASS: explicit auto manager/consumer component\n";
}
"""


def component():
    configured = os.environ.get("CXX")
    compiler = shlex.split(configured, posix=os.name != "nt") if configured else []
    if not compiler:
        found = next((shutil.which(name) for name in ("g++", "clang++", "cl") if shutil.which(name)), None)
        assert found, "C++17 compiler required (set CXX or initialize compiler PATH)"
        compiler = [found]
    with tempfile.TemporaryDirectory(prefix="g4usim-output-auto-model-") as temporary:
        folder = Path(temporary)
        # Deliberate no-Geant4 receipt stand-ins; backend mode tests real state gates.
        (folder / "G4Run.hh").write_text("#pragma once\nclass G4Run{public:int GetRunID()const{return 0;}};\n")
        (folder / "G4RunManager.hh").write_text('#pragma once\n#include "G4Run.hh"\nclass G4RunManager{public:static G4RunManager* GetRunManager(){return nullptr;}const G4Run* GetCurrentRun()const{return nullptr;}};\n')
        (folder / "G4Threading.hh").write_text("#pragma once\nnamespace G4Threading{inline int G4GetThreadId(){return -2;}inline bool IsWorkerThread(){return false;}inline bool IsMultithreadedApplication(){return false;}}\n")
        source = folder / "auto.cc"
        source.write_text(SOURCE, encoding="utf-8")
        executable = folder / ("auto.exe" if os.name == "nt" else "auto")
        files = [source] + [ROOT / f"src/{name}.cc" for name in (
            "Output/OutputManager", "Output/EffectiveOutput", "Output/RunSummary", "Output/CsvWriter", "Output/Histogram1D",
            "Utils/FileUtils", "Utils/StringUtils", "Config/EffectiveConfig", "Config/IniReader", "Config/ConfigValue",
            "Config/InputProvenance", "Scoring/HistoryStatistics")]
        if Path(compiler[0]).stem.lower() in ("cl", "clang-cl"):
            args = compiler + ["/nologo", "/std:c++17", "/utf-8", "/EHsc", "/I" + str(folder), "/I" + str(ROOT / "include")]
            args += [str(path) for path in files] + ["/Fe:" + str(executable)]
        else:
            args = compiler + ["-std=c++17", "-pthread", "-Wall", "-Wextra", "-pedantic", "-I", str(folder), "-I", str(ROOT / "include")]
            args += [str(path) for path in files] + ["-o", str(executable)]
        built = subprocess.run(args, cwd=folder, capture_output=True, text=True, timeout=180)
        assert built.returncode == 0, built.stdout + built.stderr
        run = subprocess.run([str(executable), str(folder / "output")], capture_output=True, text=True, timeout=30)
        assert run.returncode == 0, run.stdout + run.stderr
        assert "PASS: explicit auto" in run.stdout
    print("PASS: auto component (no kernel runtime claim)")


def backend(executable):
    assert executable and executable.is_file(), "Set G4USIM_EXE or --executable to the rebuilt auto candidate"
    with tempfile.TemporaryDirectory(prefix="g4usim-output-auto-") as temporary:
        work = Path(temporary)
        geometry = work / "geometry.ini"
        geometry.write_text("[world]\nshape=box\nsize=100 mm,100 mm,100 mm\nmaterial=G4_Galactic\n[volume.Det]\nparent=world\nshape=box\nsize=10 mm,10 mm,10 mm\nmaterial=G4_Si\nsensitive=true\n", encoding="utf-8")
        def run(name, mode, flags, expected, *, threads=1, before="", failure=False, requested=None, module=None, interactive=False):
            output = work / name
            config = work / (name + ".ini")
            config.write_text(f"[run]\nthreads={threads}\nseed=731\n[output]\n" + (f"format={mode}\n" if mode is not None else "") +
                f"[geometry]\ntemplate=hierarchical\nconfig={geometry.as_posix()}\n[physics]\nreference=\nmodules=G4EmStandardPhysics_option4\n" +
                "[source]\nparticle=gamma\nenergy=1 MeV\nposition_type=point\nposition=0,0,-20 mm\ndirection=+z\n[scoring]\n" +
                "".join(f"{key}={str(value).lower()}\n" for key, value in flags.items()) + f"edep={str(flags['enabled'] if module else True).lower()}\n" + (f"[modules]\nscoring={module}\n" if module else ""), encoding="utf-8")
            macro = work / (name + ".mac")
            commands = before if failure else before + "/run/initialize\n/run/beamOn 2\n/run/beamOn 3\n"
            macro.write_text(commands, encoding="utf-8")
            args = [str(executable), "--config", str(config), "--output", str(output)]
            args += ["--ui", "--ui-session", "csh"] if interactive else ["--macro", str(macro)]
            process = subprocess.run(args, input=commands + "exit\n" if interactive else None,
                                     cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
            assert (process.returncode != 0) == failure, process.stdout[-3000:] + process.stderr
            metadata = json.loads((output / "run_metadata.json").read_text(encoding="utf-8"))
            values = metadata["values"]
            assert values["status"] == ("failed" if failure else "completed"), values
            assert values["output_format"] == expected, values
            policy = requested if requested is not None else {"csv+root": "both", "root+csv": "both"}.get(mode, mode or "csv")
            assert values["output_format_requested"] == policy, values
            if policy == "auto":
                reason = "auto_enabled_scoring_with_hits_or_event_edep" if expected == "root" else "auto_no_enabled_hit_or_event_edep_output"
                assert values["output_format_selection_reason"] == reason, values
            elif mode is None and not before:
                assert values["output_format_selection_reason"] == "default_csv", values
            else:
                assert values["output_format_selection_reason"] == "explicit_" + policy, values
            # INI format is parsed before scoring; configure must still capture
            # the final flags, not an intermediate auto decision cached earlier.
            configure = json.loads((output / "effective_config_configure.json").read_text(encoding="utf-8"))
            configured = next(f for f in configure["fields"] if f["path"] == "/output/format")
            initial_actual = ("root" if flags["enabled"] and module != "off" and (flags["hits"] or flags["event_edep"]) else "csv") if mode == "auto" else {"csv+root": "both", "root+csv": "both"}.get(mode, mode or "csv")
            assert configured["resolved"] == initial_actual, configured
            if mode is not None:
                assert configured["requested"] == mode, configured
            else:
                assert "requested" not in configured, configured
            final = json.loads((output / "effective_config_finalization.json").read_text(encoding="utf-8"))
            fields = {field["path"]: field for field in final["fields"]}
            field = fields["/output/format"]
            assert field["resolved"] == expected, field
            if mode is not None or before:
                expected_request = policy if before else mode
                assert field["requested"] == expected_request, field
            else:
                assert "requested" not in field, field
            if failure:
                assert "AUTO_REJECT_CONTINUED" not in process.stdout
                configure = json.loads((output / "effective_config_configure.json").read_text(encoding="utf-8"))
                original = next(f for f in configure["fields"] if f["path"] == "/output/format")
                assert field["origins"] == original["origins"], (original, field)
                assert field["configuration_generation"] == original["configuration_generation"]
                assert metadata["runs"] == []
                verify(metadata, output, set())
            else:
                assert {r["run_id"] for r in metadata["runs"]} == {0, 1}
                verify(metadata, output, {0, 1})
                worker_snapshots = []
                for path in output.glob("effective_config_run_*.json"):
                    snapshot = json.loads(path.read_text(encoding="utf-8"))
                    projected = next(f for f in snapshot["fields"] if f["path"] == "/output/format")
                    assert projected["resolved"] == expected, (path, projected, field)
                    assert projected.get("requested") == field.get("requested"), (path, projected, field)
                    if snapshot.get("thread_id", -1) >= 0:
                        worker_snapshots.append(snapshot)
                assert {s["thread_id"] for s in worker_snapshots} == set(range(threads)), worker_snapshots
                assert {(s["run_id"], s["thread_id"]) for s in worker_snapshots} == {(r, t) for r in (0, 1) for t in range(threads)}, worker_snapshots
                roots = sorted(output.glob("g4usim*.root"))
                assert len(roots) == (2 if expected in ("root", "both") else 0), roots
                assert bool(list(output.glob("hist_edep_raw_t*.csv"))) == (expected in ("csv", "both") and flags["enabled"] and module != "off")
            return field, fields
        aggregate = {"enabled": True, "hits": False, "event_edep": False}
        hit = {"enabled": True, "hits": True, "event_edep": False}
        event = {"enabled": True, "hits": False, "event_edep": True}
        residual = {"enabled": False, "hits": True, "event_edep": True}
        run("omitted", None, hit, "csv")
        for mode in ("csv", "root", "both", "csv+root", "root+csv"):
            run("explicit-" + mode.replace("+", "-"), mode, aggregate, {"csv+root": "both", "root+csv": "both"}.get(mode, mode))
        for threads in (1, 2, 4):
            for label, flags, expected in (("aggregate", aggregate, "csv"), ("hits", hit, "root"), ("events", event, "root"), ("disabled-residual", residual, "csv")):
                field, fields = run(f"auto-{label}-{threads}", "auto", flags, expected, threads=threads)
                for key, value in flags.items():
                    assert fields["/scoring/" + key]["resolved"] == value, fields
        for module, flags, expected in (("off", {"enabled": False, "hits": False, "event_edep": False}, "csv"), ("auto", hit, "root"), ("auto", {"enabled": False, "hits": False, "event_edep": False}, "csv"), ("auto", aggregate, "csv")):
            run("module-" + module + "-" + expected + "-" + str(flags["enabled"]) + "-" + str(flags["hits"]), "auto", flags, expected, module=module)
        # Keep the rejected legacy/module conflicts as explicit negative coverage.
        for module in ("off", "auto"):
            config = work / ("module-" + module + "-conflict.ini")
            template = (work / "omitted.ini").read_text(encoding="utf-8")
            config.write_text(template.replace("enabled=true", "enabled=false") + f"[modules]\nscoring={module}\n", encoding="utf-8")
            rejected_output = work / ("module-" + module + "-conflict-output")
            rejected = subprocess.run([str(executable), "--config", str(config), "--output", str(rejected_output)], cwd=ROOT,
                                      capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30)
            diagnostic = rejected.stdout + rejected.stderr
            assert rejected.returncode != 0 and f"[modules]/scoring = {module} conflicts" in diagnostic, diagnostic
            assert not list(rejected_output.glob("effective_config_run_*.json")), rejected_output
        field, _ = run("csh-auto-dependency", "csv", aggregate, "root", before="/AIHL/output/setFormat auto\n/AIHL/scoring/hits true\n", requested="auto", interactive=True)
        assert any(o["kind"] == "interactive" and "setFormat auto" in o["raw"] for o in field["origins"]), field
        assert field["origins"][-1]["kind"] == "derived" and "scoring/hits true" in field["origins"][-1]["raw"], field
        field, fields = run("ini-auto-dependency", "auto", aggregate, "root", before="/AIHL/scoring/hits true\n", requested="auto")
        assert any(o["kind"] == "main_ini" and o["raw"] == "auto" and o["disposition"] == "accepted" for o in field["origins"]), field
        assert field["origins"][-1]["kind"] == "derived", field
        assert fields["/scoring/hits"]["resolved"] is True and fields["/scoring/event_edep"]["resolved"] is False
        field, _ = run("format-before-scoring", "csv", aggregate, "root", before="/AIHL/output/setFormat auto\n/AIHL/scoring/hits true\n", requested="auto")
        assert any(o["kind"] == "macro" and "setFormat auto" in o["raw"] for o in field["origins"]), field
        assert field["origins"][-1]["kind"] == "derived" and "scoring/hits true" in field["origins"][-1]["raw"], field
        field, _ = run("scoring-before-format", "auto", hit, "csv", before="/AIHL/scoring/hits false\n/AIHL/output/setFormat auto\n", requested="auto")
        assert field["origins"][-1]["kind"] == "macro" and "setFormat auto" in field["origins"][-1]["raw"], field
        field, _ = run("explicit-overrides-auto", "auto", hit, "csv", before="/AIHL/output/setFormat csv\n", requested="csv")
        assert field["origins"][-1]["kind"] == "macro" and "setFormat csv" in field["origins"][-1]["raw"], field
        run("reject-format-after-init", "csv", aggregate, "csv", before="/run/initialize\n/AIHL/output/setFormat auto\n/control/echo AUTO_REJECT_CONTINUED\n/run/beamOn 1\n", failure=True)
        run("reject-scoring-after-init", "auto", aggregate, "csv", before="/run/initialize\n/AIHL/scoring/hits true\n/control/echo AUTO_REJECT_CONTINUED\n/run/beamOn 1\n", failure=True)
    print("PASS: explicit auto/default/aliases, final scoring, source order, state rejection, workers and multi-run files")


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
