#!/usr/bin/env python3
"""Compile and exercise the standalone C++17 model without Geant4."""
import json
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
        found = next((shutil.which(name) for name in ("g++", "clang++", "cl")
                      if shutil.which(name)), None)
        assert found, "C++17 compiler required (set CXX or configure PATH)"
        compiler = [found]
    source = r'''
#include "Config/EffectiveConfig.hh"
#include <iostream>
#include <limits>
#include <stdexcept>
using namespace effective_config;
int main() {
 Registry registry;
 Field a; a.path=ObjectFieldPath("source", "A/~B", "energy");
 a.requested="2 keV"; a.resolved=0.002; a.unit="MeV";
 a.origins.push_back({"default"});
 a.origins.push_back({"main_ini", "input.ini", 4, "source", "energy", "2 keV"});
 a.evidence_level=EvidenceLevel::ManagerAccepted;
 a.reason="Manager accepted; kernel not initialized";
 auto require=[](bool ok) { if (!ok) throw std::runtime_error("model invariant failed"); };
 require(registry.Commit({a})==1);
 const auto old=registry.Capture("configure");
 const auto oldJson=old.ToJson();
 a.requested="caller mutation"; a.origins[1].raw="caller mutation";
 require(old.ToJson()==oldJson && registry.Capture("configure").ToJson()==oldJson);
 auto reject=[&](Field bad) {
   bool rejected=false;
   try { registry.Commit({bad}); } catch(const std::exception&) { rejected=true; }
   require(rejected && registry.Revision()==1 && registry.Capture("configure").ToJson()==oldJson);
 };
 Field bad=a; bad.resolved=Value::Array{Value::Object{{"nested", std::numeric_limits<double>::infinity()}}}; reject(bad);
 bad=a; bad.resolved=Value::Object{{"nested", Value::Array{std::numeric_limits<double>::quiet_NaN()}}}; reject(bad);
 bad=a; bad.resolved=std::numeric_limits<double>::quiet_NaN(); reject(bad);
 bad=a; bad.path="/source/bad~2key"; reject(bad);
 bad=a; bad.path="/source/objects/A/extra/energy"; reject(bad);
 bad=a; bad.application_status=ApplicationStatus::Applied; reject(bad);
 bad=a; bad.applied_revision=2; reject(bad);
 bool duplicate=false;
 try {registry.Commit({a,a});} catch(const std::exception&) {duplicate=true;}
 require(duplicate && registry.Revision()==1);
 a.application_status=ApplicationStatus::Applied;
 a.evidence_level=EvidenceLevel::ThreadApplied; a.evidence_source="worker clone test fixture";
 require(registry.Commit({a})==2);
 require(old.ToJson()==oldJson && old.Revision()==1);
 Field z; z.path=FieldPath("app","flags");
 z.requested=Value::Array{true, Value(), std::int64_t(9007199254740993LL), 1.0};
 z.resolved=Value::Object{{"z", "quote\" slash\\ newline\n control\x01"}, {"a",false}};
 z.application_status=ApplicationStatus::Unknown; z.reason="external command unobservable";
 registry.Commit({z});
 bool missingRun=false;
 try {registry.Capture("run_begin");} catch(const std::exception&) {missingRun=true;}
 require(missingRun);
 const auto runJson=registry.Capture("run_begin",0).ToJson();
 z.requested_known=false; z.resolved_known=false;
 registry.Commit({z});
 // Module replacement removes mode-specific fields without touching neighbors.
 Registry replacement;
 Field first; first.path=FieldPath("source", "particle");first.resolved="proton";
 Field neighbor;neighbor.path=FieldPath("source_extra", "particle");neighbor.resolved="gamma";
 require(replacement.Commit({first,neighbor})==1);
 require(replacement.Commit({first})==1);
 require(replacement.Commit({})==1);
 const auto beforeReplace=replacement.Capture("configure");
 Field named;named.path=ObjectFieldPath("source","A/~B","intensity");named.resolved=1.0;
 require(replacement.ReplaceModule("source",{named})==2);
 require(replacement.Capture("configure").Fields().count(first.path)==0);
 require(replacement.Capture("configure").Fields().count(neighbor.path)==1);
 require(beforeReplace.Fields().count(first.path)==1);
 require(replacement.ReplaceModule("source",{named})==2);
 auto rejectTransaction=[&](auto operation) {
   const auto saved=replacement.Capture("configure").ToJson();bool rejected=false;
   try {operation();}catch(const std::exception&){rejected=true;}
   require(rejected && replacement.Revision()==2 && replacement.Capture("configure").ToJson()==saved);
 };
 rejectTransaction([&](){replacement.Commit({named},{named.path});});
 rejectTransaction([&](){replacement.Commit({}, {neighbor.path,neighbor.path});});
 rejectTransaction([&](){replacement.ReplaceModule("source",{neighbor});});
 Field invalid=named;invalid.resolved=std::numeric_limits<double>::infinity();
 rejectTransaction([&](){replacement.Commit({invalid},{neighbor.path});});
 require(replacement.ReplaceModule("source",{})==3);
 require(replacement.ReplaceModule("source",{})==3);
 require(replacement.Commit({}, {neighbor.path})==4);
 require(replacement.Commit({}, {neighbor.path})==4);
 require(replacement.Capture("configure").Fields().empty());
 // Idempotent runtime evidence preserves its original applied revision.
 require(registry.Commit({a})==4);
 require(registry.Capture("run_begin",1).Revision()==4);
 // Runtime receipts annotate immutable views without mutating configuration history.
 Field applied=old.Fields().begin()->second;
 applied.application_status=ApplicationStatus::Applied;
 applied.evidence_level=EvidenceLevel::ThreadApplied;
 applied.evidence_source="independent runtime readback fixture";
 const auto observed=old.WithApplicationEvidence({applied}).WithMetadata({{"thread_id",0}});
 require(observed.Revision()==old.Revision() && old.ToJson()==oldJson);
 require(observed.Fields().begin()->second.applied_revision==1);
 require(registry.Revision()==4);
 auto rejectEvidence=[&](Field receipt){bool rejected=false;try{old.WithApplicationEvidence({receipt});}catch(const std::exception&){rejected=true;}require(rejected && old.ToJson()==oldJson);};
 Field stale=applied;stale.revision=2;rejectEvidence(stale);
 Field mismatch=applied;mismatch.resolved=0.003;rejectEvidence(mismatch);
 Field managerOnly=applied;managerOnly.evidence_level=EvidenceLevel::ManagerAccepted;rejectEvidence(managerOnly);
 Field staleApplication=applied;staleApplication.applied_revision=2;rejectEvidence(staleApplication);
 Field absent=applied;absent.path="/source/absent";rejectEvidence(absent);
 bool duplicateEvidence=false;try{old.WithApplicationEvidence({applied,applied});}catch(const std::exception&){duplicateEvidence=true;}require(duplicateEvidence);
 bool reserved=false;try{old.WithMetadata({{"fields",Value::Array{}}});}catch(const std::exception&){reserved=true;}require(reserved);
 bool nonfiniteMetadata=false;try{old.WithMetadata({{"inputs",std::numeric_limits<double>::infinity()}});}catch(const std::exception&){nonfiniteMetadata=true;}require(nonfiniteMetadata);
 std::cout << oldJson << '\n' << runJson << '\n' << registry.Capture("finalization").ToJson() << '\n';
}
'''
    with tempfile.TemporaryDirectory(prefix="g4usim-effective-model-") as temp:
        folder = Path(temp)
        test = folder / "model.cc"
        test.write_text(source, encoding="utf-8")
        exe = folder / ("model.exe" if os.name == "nt" else "model")
        inputs = [str(test), str(root / "src/Config/EffectiveConfig.cc")]
        if Path(compiler[0]).stem.lower() in ("cl", "clang-cl"):
            args = compiler + ["/nologo", "/std:c++17", "/EHsc", "/I" + str(root / "include")]
            args += inputs + ["/Fe:" + str(exe)]
        else:
            args = compiler + ["-std=c++17", "-Wall", "-Wextra", "-pedantic", "-I", str(root / "include")]
            args += inputs + ["-o", str(exe)]
        built = subprocess.run(args, cwd=folder, capture_output=True, text=True, timeout=120)
        assert built.returncode == 0, built.stdout + built.stderr
        ran = subprocess.run([str(exe)], cwd=folder, capture_output=True, text=True, timeout=30)
        assert ran.returncode == 0, ran.stdout + ran.stderr
        old, new, final = [json.loads(line) for line in ran.stdout.splitlines()]
        assert old["revision"] == 1 and new["revision"] == 3
        assert old["fields"][0]["path"] == "/source/objects/A~1~0B/energy"
        assert old["fields"][0]["application_status"] == "not_applied"
        assert old["fields"][0]["evidence_level"] == "manager_accepted"
        assert len(old["fields"][0]["origins"]) == 2
        assert old["fields"][0]["origins"][1]["line"] == 4
        assert new["run_id"] == 0 and new["stage"] == "run_begin"
        assert [field["path"] for field in new["fields"]] == sorted(field["path"] for field in new["fields"])
        flags, energy = new["fields"]
        assert flags["requested"] == [True, None, 9007199254740993, 1.0]
        assert isinstance(flags["requested"][3], float)
        assert flags["resolved"]["z"] == 'quote" slash\\ newline\n control\x01'
        assert energy["applied_revision"] == 2 and energy["revision"] == 2
        assert energy["application_status"] == "applied" and energy["evidence_level"] == "thread_applied"
        assert final["revision"] == 4 and final["stage"] == "finalization"
        assert "requested" not in final["fields"][0] and "resolved" not in final["fields"][0]
    print("EffectiveConfig standalone model passed")


if __name__ == "__main__":
    main()
