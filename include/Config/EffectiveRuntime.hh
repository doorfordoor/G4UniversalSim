#pragma once
#include "Config/EffectiveConfigSupport.hh"
#include "G4RunManager.hh"
#include "G4Run.hh"
#include "G4Threading.hh"
namespace effective_config {
inline Value Receipt(const std::string& path,Value observed,const std::string& stage,
                     const std::string& source,const std::string& level="kernel_constructed",
                     const std::string& status="applied",const std::string& reason="") {
 auto* manager=G4RunManager::GetRunManager();const auto* run=manager?manager->GetCurrentRun():nullptr;
 return Value::Object{{"path",path},{"stage",stage},{"run_id",run?Value(run->GetRunID()):Value()},
  {"thread_id",G4Threading::G4GetThreadId()}, {"role",G4Threading::IsWorkerThread()?"worker":(G4Threading::IsMultithreadedApplication()?"master":"sequential")},
  {"application_status",status},{"evidence_level",level},{"observed",std::move(observed)},{"evidence_source",source},{"reason",reason}};
}
}
