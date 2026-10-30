#include "Core/SimulationManager.hh"
#include "Config/ConfigManager.hh"
#include "Config/EffectiveRuntime.hh"
#include "Config/EffectiveReceiptView.hh"
#include "Geometry/GeometryManager.hh"
#include "Materials/MaterialManager.hh"
#include "Source/SourceManager.hh"
#include "Physics/PhysicsManager.hh"
#include "Scoring/ScoringManager.hh"
#include "Scoring/ScoringMeshConfig.hh"
#include "Biasing/BiasingManager.hh"
#include "Output/OutputManager.hh"
#include "Output/RunSummary.hh"
#include "Utils/FileUtils.hh"
#include "Utils/StringUtils.hh"
#include "G4VModularPhysicsList.hh"
#include <algorithm>
#include <atomic>
#include <chrono>
#include <cstdio>
#ifdef _WIN32
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>
#endif
#include <filesystem>
#include <fstream>
#include <set>
#include <sstream>
#include <stdexcept>

namespace {
using namespace effective_config;
std::string Token(const std::string& command) {
    std::istringstream input(command);std::string token;input>>token;
    return StringUtils::ToLower(token);
}
void Append(Value::Array& destination, const Value& value) {
    if (const auto* array = std::get_if<Value::Array>(&value.data)) destination.insert(destination.end(), array->begin(), array->end());
}
bool IsReadOnlyCommand(const std::string& token) {
    static const std::set<std::string> commands{
        "/aihl/source/print","/aihl/physics/print","/aihl/physics/listavailablereferences",
        "/aihl/physics/listavailableemreferences","/aihl/physics/dumpprocesses",
        "/aihl/geometry/print","/aihl/geometry/printtree","/aihl/geometry/listuservolumes",
        "/aihl/geometry/exportmesh","/aihl/geometry/exportgdml","/aihl/material/print","/aihl/material/list",
        "/aihl/biasing/print","/aihl/biasing/validate","/aihl/biasing/xs/printrules",
        "/aihl/scoring/print","/aihl/output/print","/aihl/app/print",
        "/gps/list","/gps/source/list","/gps/source/show","/score/list","/random/showenginestatus"};
    return commands.count(token)!=0;
}

void AddOrigin(Field& field, Origin origin, Value requested, bool requestedKnown = true) {
    for (auto& old : field.origins) if (old.disposition == "accepted") old.disposition = "shadowed";
    field.origins.push_back(std::move(origin)); field.requested = std::move(requested); field.requested_known = requestedKnown;
}
}

std::vector<effective_config::Field> SimulationManager::ExportStartupFields() const
{
    using namespace effective_config;
    std::vector<Field> fields;
    const auto add = [&](const char* key, Value value, std::initializer_list<std::pair<const char*,const char*>> aliases,
                         const std::optional<Value>& cli = std::nullopt) {
        Field field; field.path = FieldPath("run", key); field.resolved = value;
        field.requested_known = false; field.evidence_level = EvidenceLevel::ManagerAccepted;
        field.evidence_source = "SimulationContext accepted startup settings";
        field.reason = "Configured value; kernel execution is recorded separately";
        Origin initial; initial.kind = "default"; field.origins.push_back(initial);
        // Compatibility readers choose the first applicable alias; duplicates of
        // that alias retain source order and the last declaration wins.
        std::string winnerSection, winnerKey; std::size_t winnerLine = 0;
        const auto declarations = startupEffective_.reader.GetDeclarations();
        for (const auto& alias : aliases) {
            for (const auto& d : declarations) if (d.normalizedSection == alias.first && d.normalizedKey == alias.second) {
                if ((std::string(key) == "name") && StringUtils::Trim(d.value).empty()) continue;
                winnerSection = d.normalizedSection; winnerKey = d.normalizedKey; winnerLine = d.lineNumber;
            }
            if (winnerLine) break;
        }
        for (const auto& d : declarations) {
            bool relevant = false;
            for (const auto& a : aliases) relevant = relevant || (d.normalizedSection == a.first && d.normalizedKey == a.second);
            if (!relevant) continue;
            Origin origin; origin.kind = "main_ini"; origin.file = startupEffective_.reader.GetFilename();
            origin.section = d.originalSection; origin.key = d.originalKey; origin.alias = d.originalKey;
            origin.line = d.lineNumber; origin.raw = d.value; origin.input_sha256 = startupEffective_.reader.GetInputSha256();
            origin.disposition = d.lineNumber == winnerLine ? "accepted" : "shadowed";
            field.origins.push_back(origin);
            if (origin.disposition == "accepted") { field.requested = d.value; field.requested_known = true; field.origins.front().disposition = "shadowed"; }
        }
        if (cli) { Origin origin; origin.kind = "cli"; origin.key = key; origin.raw = cli->ToJson(); AddOrigin(field, origin, *cli); }
        for (const auto& old : startupEffective_.fields) if (old.path == field.path) {
            field.origins = old.origins; field.requested = old.requested; field.requested_known = old.requested_known;
            field.application_status = old.application_status; field.reason = old.reason;
            field.configuration_generation = old.configuration_generation;
        }
        fields.push_back(std::move(field));
    };
    const auto optional = [](const auto& value) -> std::optional<Value> { return value ? std::optional<Value>(Value(*value)) : std::nullopt; };
    add("name", context_.GetRunName(), {{"run","name"},{"run","run_name"},{"run","runname"}}, optional(commandLineOverrides_.runName));
    add("threads", context_.GetNumThreads(), {{"run","threads"}}, optional(commandLineOverrides_.numThreads));
    // Preserve the v1 string seed representation: unsigned long is platform dependent.
    add("seed", context_.HasSeed() ? Value(std::to_string(context_.GetSeed())) : Value(),
        {{"run","seed"},{"run","randomseed"},{"general","seed"},{"general","randomseed"}},
        commandLineOverrides_.seed ? std::optional<Value>(std::to_string(*commandLineOverrides_.seed)) : std::nullopt);
    add("macro", context_.GetMacroFile(), {{"run","macro"}}, optional(commandLineOverrides_.macroFile));
    add("main_config", context_.GetMainConfig(), {}, optional(commandLineOverrides_.mainConfig));
    add("interactive", context_.IsInteractive(), {{"run","interactive"}}, optional(commandLineOverrides_.interactive));
    add("dry_run", context_.IsDryRun(), {{"run","dry_run"},{"run","dryrun"}}, optional(commandLineOverrides_.dryRun));
    add("verbose", context_.GetVerboseLevel(), {{"run","verbose"},{"general","verbose"}});
    auto format = startupEffective_.Make(FieldPath("configuration", "main_ini_schema_version"),
                                         1, "", "general", {"schema_version"});
    format.evidence_source = "ConfigManager input format validation";
    format.reason = startupEffective_.reader.HasKey("general", "schema_version")
        ? "Explicit main INI format accepted; this is not a kernel simulation setting"
        : "Version absent: legacy main INI format 1 retained; no explicit version request";
    fields.push_back(std::move(format));
    for (const auto& mode : moduleModes_) {
        auto policy=startupEffective_.Make(FieldPath("modules", mode.first),mode.second,"","modules",{mode.first.c_str()});
        const bool explicitMode=startupEffective_.reader.HasKey("modules",mode.first);
        policy.reason=explicitMode ? "Explicit module policy; enabled records accepted consumer state, not kernel application" :
            "Mode absent: legacy consumer defaults retained; this is not an explicit auto request";
        fields.push_back(policy);
        const bool enabled=mode.first=="scoring" ? scoringManager_->IsEnabled() || !scoringMeshCommands_.empty() :
            mode.first=="biasing" ? biasingManager_->IsEnabled() : mode.first=="field" ? !fieldConfig_.Empty() : scoringManager_->GetTrajectorySettings().events>0;
        Field state;state.path=ObjectFieldPath("modules",mode.first,"enabled");state.requested_known=false;
        state.resolved=enabled;state.evidence_level=EvidenceLevel::ManagerAccepted;state.origins=policy.origins;
        for(auto& origin:state.origins)if(origin.disposition=="accepted")origin.disposition="derived";
        state.reason=policy.reason;fields.push_back(std::move(state));
    }
    return fields;
}

void SimulationManager::InitializeEffectiveConfig()
{
    startupEffective_.reader = configManager_->GetMainReader();
    startupEffective_.Accept(startupEffective_.reader, ExportStartupFields());
    outputManager_->AcceptEffectiveConfig(configManager_->GetMainReader());
    geometryManager_->AcceptEffectiveConfig(configManager_->GetMainReader());
    // CLI values are applied after the INI consumer, but their provenance must
    // retain the earlier declarations rather than attributing the final value to INI.
    if (commandLineOverrides_.outputDir) {
        Origin origin; origin.kind = "cli"; origin.key = "output";
        outputManager_->ConfirmEffectiveConfigMutation("/AIHL/output/setDir " + *commandLineOverrides_.outputDir, origin);
    }
    if (commandLineOverrides_.checkOverlaps) {
        Origin origin; origin.kind = "cli"; origin.key = "check_overlaps";
        geometryManager_->ConfirmEffectiveConfigMutation(std::string("/AIHL/geometry/checkOverlaps ") + (*commandLineOverrides_.checkOverlaps ? "true" : "false"), origin);
    }
    RefreshEffectiveConfig();
    configuredEffective_ = EffectiveSnapshot("configure", std::nullopt);
}

void SimulationManager::RefreshEffectiveConfig() const
{
    using namespace effective_config;
    std::vector<Field> fields = ExportStartupFields();
    const auto add = [&](std::vector<Field> values) { fields.insert(fields.end(), values.begin(), values.end()); };
    add(outputManager_->ExportEffectiveConfigFields()); add(geometryManager_->ExportEffectiveConfigFields());
    add(materialManager_->ExportEffectiveConfigFields()); add(sourceManager_->ExportEffectiveConfigFields());
    add(physicsManager_->ExportEffectiveConfigFields()); add(fieldConfig_.ExportEffectiveConfigFields());
    add(scoringManager_->ExportEffectiveConfigFields()); add(ScoringMeshConfig::ExportEffectiveConfigFields());
    add(biasingManager_->ExportEffectiveConfigFields());
    std::set<std::string> paths; for (const auto& field : fields) paths.insert(field.path);
    std::vector<std::string> removed;
    const auto previous = effectiveRegistry_.Capture("configure");
    for (const auto& old : previous.Fields()) if (!paths.count(old.first)) removed.push_back(old.first);
    effectiveRegistry_.Commit(std::move(fields), removed);
}

void SimulationManager::SetEffectiveMacroInputs(const std::vector<std::pair<std::string,std::string>>& inputs)
{
    std::lock_guard<std::mutex> lock(effectiveMutex_);
    effectiveMacroInputs_.clear();
    for (const auto& input : inputs) effectiveMacroInputs_.emplace_back(Value::Object{{"path",input.first},{"sha256",input.second},{"kind","macro_preflight"}});
    if(configuredEffective_) {
        auto metadata=configuredEffective_->Metadata();
        metadata["macro_inputs"]=effectiveMacroInputs_;
        configuredEffective_=configuredEffective_->WithMetadata(std::move(metadata));
    }
}

void SimulationManager::ConfirmEffectiveCommand(const std::string& command, const effective_config::Origin& origin)
{
    if (!configured_) return;
    std::lock_guard<std::mutex> lock(effectiveMutex_);
    const auto token = Token(command);
    const bool query=IsReadOnlyCommand(token);
    if (!query) {
        if (token.rfind("/aihl/source/",0)==0 || token.rfind("/gps/",0)==0) sourceManager_->ConfirmEffectiveConfigMutation(command,origin);
        if (token.rfind("/aihl/physics/",0)==0) physicsManager_->ConfirmEffectiveConfigMutation(command,origin);
        if (token.rfind("/aihl/geometry/",0)==0) geometryManager_->ConfirmEffectiveConfigMutation(command,origin);
        if (token.rfind("/aihl/material/",0)==0) materialManager_->ConfirmEffectiveConfigMutation(command,origin);
        if (token.rfind("/aihl/biasing/",0)==0) biasingManager_->ConfirmEffectiveConfigMutation(command,origin);
        if (token.rfind("/aihl/scoring/",0)==0) scoringManager_->ConfirmEffectiveConfigMutation(command,origin);
        outputManager_->ConfirmEffectiveConfigMutation(command,origin);
        if (token.rfind("/score/",0)==0) ScoringMeshConfig::ConfirmEffectiveConfigMutation(command,origin);
        const std::map<std::string,std::string> targets{{"setnumthreads","threads"},{"setseed","seed"},{"setmacro","macro"},
            {"setinteractive","interactive"},{"setverbose","verbose"},{"setdryrun","dry_run"},{"setrunname","name"}};
        const auto last = token.substr(token.find_last_of('/')+1);
        auto fields = ExportStartupFields(); bool touched = false;
        for (auto& field : fields) {
            const auto found = targets.find(last);
            if (token.rfind("/aihl/app/",0)==0 && found != targets.end() && field.path == FieldPath("run",found->second)) {
                AddOrigin(field,origin,command); touched = true;
            } else if (token.rfind("/random/",0)==0 && field.path=="/run/seed") {
                AddOrigin(field,origin,command); field.application_status=ApplicationStatus::Unknown;
                field.reason="Native random command accepted; configured seed is not the engine checkpoint"; touched=true;
            }
        }
        if(touched) startupEffective_.Accept(startupEffective_.reader,std::move(fields));
    }
    RefreshEffectiveConfig();
    effectiveCommands_.emplace_back(Value::Object{{"command",command},{"file",origin.file},{"line",static_cast<std::int64_t>(origin.line)},
        {"input_sha256",origin.input_sha256},{"kind",origin.kind},{"revision",static_cast<std::int64_t>(effectiveRegistry_.Revision())}});
}

effective_config::Snapshot SimulationManager::EffectiveSnapshot(const std::string& stage, std::optional<std::int64_t> runId,
    ScoringManager* scoring, OutputManager* output) const
{
    using namespace effective_config;
    auto snapshot = effectiveRegistry_.Capture(stage,runId);
    Value::Array evidence;
    Append(evidence, sourceManager_->ExportEffectiveConfigEvidence()); Append(evidence, physicsManager_->ExportEffectiveConfigEvidence());
    Append(evidence, fieldConfig_.ExportEffectiveConfigEvidence()); Append(evidence, geometryManager_->ExportEffectiveConfigEvidence());
    Append(evidence, materialManager_->ExportEffectiveConfigEvidence()); Append(evidence, biasingManager_->ExportEffectiveConfigEvidence());
    Append(evidence, ScoringMeshConfig::ExportEffectiveConfigEvidence());
    Append(evidence, (scoring ? scoring : scoringManager_.get())->ExportEffectiveConfigEvidence());
    Append(evidence, (output ? output : outputManager_.get())->ExportEffectiveConfigEvidence());
    const int thread = G4Threading::G4GetThreadId();
    std::optional<std::int64_t> receiptRun=runId;
    if(!receiptRun && stage=="finalization") {
        const auto& runs=outputManager_->GetRunSummary().GetRuns();
        if(!runs.empty())receiptRun=runs.back().runId;
    }
    RuntimeView runtime;
    if(stage!="configure")runtime=ReduceRuntimeReceipts(snapshot,evidence,thread,receiptRun);
    snapshot=snapshot.WithApplicationEvidence(runtime.annotations);
    Value::Array scoped=std::move(runtime.evidence);
    Value::Array inputs=effectiveMacroInputs_;
    if (!configManager_->GetMainReader().GetFilename().empty()) inputs.emplace_back(Value::Object{
        {"kind","main_ini"},{"path",configManager_->GetMainReader().GetFilename()},{"sha256",configManager_->GetMainReader().GetInputSha256()}});
    std::set<std::string> seen;
    for (const auto& pair : snapshot.Fields()) for (const auto& origin : pair.second.origins) {
        if(origin.file.empty() || origin.input_sha256.empty())continue;
        const std::string identity=Value(Value::Array{origin.file,origin.input_sha256}).ToJson();
        if(seen.insert(identity).second)inputs.emplace_back(Value::Object{{"path",origin.file},{"sha256",origin.input_sha256},{"kind",origin.kind}});
    }
    return snapshot.WithMetadata({{"scope","consumer_configuration_with_separate_application_evidence"},
        {"origin_chain_coverage","consumer_recorded"},{"input_hash_coverage","accepted_parser_bytes"},
        {"macro_execution_status",stage=="configure" ? "not_executed" : "see_run_summary"},
        {"thread_id",stage=="configure" ? Value() : Value(thread)},
        {"role",stage=="configure" ? "configuration" : (G4Threading::IsWorkerThread()?"worker":(G4Threading::IsMultithreadedApplication()?"master":"sequential"))},
        {"inputs",std::move(inputs)},{"evidence",std::move(scoped)},{"accepted_commands",effectiveCommands_},
        {"coverage",Value::Object{{"consumers",Value::Array{"startup","legacy_source","named_and_phase_space_source","geometry","materials","physics","scoring_and_mesh","field","biasing","output_and_trajectories","commands"}},
            {"application","Only value-matched, scoped runtime receipts; absent evidence remains unproven"}}},
        {"execution_performed",stage=="run_begin" || !outputManager_->GetRunSummary().GetRuns().empty()},
        {"thread_finalizations",effectiveThreadFinals_},
        {"limitations",Value::Array{"Snapshot evidence does not establish simulation success or physical validation", "Configured seed is not a complete random-engine checkpoint"}}});
}

std::string SimulationManager::ExportEffectiveConfigJson() const
{
    std::lock_guard<std::mutex> lock(effectiveMutex_);
    if (!configuredEffective_) throw std::logic_error("EffectiveConfig export requires successful Configure");
    // Inspection occurs before macro execution; add the parsed preflight inputs.
    return configuredEffective_->ToJson();
}

void SimulationManager::WriteEffectiveSnapshot(const effective_config::Snapshot& snapshot, const std::string& filename,
    OutputManager* output, std::optional<int> runId, std::optional<int> threadId) const
{
    if (!output) throw std::runtime_error("EffectiveConfig output manager unavailable");
    std::filesystem::path temporary;
    std::FILE* stream=nullptr;
    const char* failureStage="effective_config_serialize";
    try {
        const std::string bytes=snapshot.ToJson()+"\n";
        const auto path=std::filesystem::u8path(output->MakeOutputPath(filename));
        failureStage="effective_config_open";
        std::filesystem::create_directories(path.parent_path());
        static std::atomic<unsigned long long> sequence{0};
        for(unsigned attempt=0;attempt<32 && !stream;++attempt) {
            temporary=path;
            temporary+=std::filesystem::u8path(".tmp-"+std::to_string(std::chrono::steady_clock::now().time_since_epoch().count())+"-"+std::to_string(++sequence));
#ifdef _WIN32
            stream=_wfopen(temporary.c_str(),L"wbx");
#else
            stream=std::fopen(temporary.c_str(),"wbx");
#endif
        }
        if(!stream)throw std::runtime_error("Cannot create exclusive EffectiveConfig temporary file: "+path.u8string());
        failureStage="effective_config_write";
        if(std::fwrite(bytes.data(),1,bytes.size(),stream)!=bytes.size() || std::fflush(stream)!=0)
            throw std::runtime_error("Cannot write EffectiveConfig snapshot: "+path.u8string());
        failureStage="effective_config_close";
        const int closed=std::fclose(stream);stream=nullptr;
        if(closed!=0)throw std::runtime_error("Cannot close EffectiveConfig snapshot: "+path.u8string());
        failureStage="effective_config_publish";
#ifdef _WIN32
        if(!MoveFileExW(temporary.c_str(),path.c_str(),MOVEFILE_REPLACE_EXISTING|MOVEFILE_WRITE_THROUGH))
            throw std::runtime_error("Cannot atomically publish EffectiveConfig snapshot: "+path.u8string());
#else
        std::filesystem::rename(temporary,path);
#endif
        temporary.clear();
        failureStage="effective_config_register";
        const auto scope = !runId ? OutputManager::ArtifactScope::Process :
            (threadId && *threadId >= 0 ? OutputManager::ArtifactScope::Thread : OutputManager::ArtifactScope::Run);
        output->RegisterGeneratedFile(path.u8string(), scope, runId,
            scope == OutputManager::ArtifactScope::Thread ? threadId : std::nullopt);
    } catch(const std::exception& error) {
        if(stream)std::fclose(stream);
        if(!temporary.empty()){std::error_code ignored;std::filesystem::remove(temporary,ignored);}
        output->RecordOutputFailure(failureStage,error.what());
        throw;
    } catch(...) {
        if(stream)std::fclose(stream);
        if(!temporary.empty()){std::error_code ignored;std::filesystem::remove(temporary,ignored);}
        output->RecordOutputFailure(failureStage,"Unknown EffectiveConfig snapshot failure");
        throw;
    }
}

void SimulationManager::CaptureEffectiveRunBegin(int runId, ScoringManager* scoring, OutputManager* output) const
{
    std::lock_guard<std::mutex> lock(effectiveMutex_);
    sourceManager_->ObserveEffectiveRunSource();
    ScoringMeshConfig::ObserveEffectiveConfigMeshes();
    if (const auto* manager=G4RunManager::GetRunManager()) {
        if (const auto* list=dynamic_cast<const G4VModularPhysicsList*>(manager->GetUserPhysicsList()))
            physicsManager_->ObserveEffectiveConfigPhysics(*list,"physics_process");
    }
    output->RecordEffectiveConfigState("run_begin");
    if(configuredEffective_ && !effectiveConfigureWritten_.count(output->GetOutputDir())) {
        WriteEffectiveSnapshot(*configuredEffective_,"effective_config_configure.json",output);
        effectiveConfigureWritten_.insert(output->GetOutputDir());
    }
    const int thread=G4Threading::G4GetThreadId();
    WriteEffectiveSnapshot(EffectiveSnapshot("run_begin",runId,scoring,output),
        "effective_config_run_"+std::to_string(runId)+"_t"+std::to_string(thread)+".json",output,runId,thread);
}

void SimulationManager::CaptureEffectiveThreadFinalization(int runId, ScoringManager* scoring, OutputManager* output) const
{
    std::lock_guard<std::mutex> lock(effectiveMutex_);
    output->RecordEffectiveConfigState("finalization");
    auto snapshot=EffectiveSnapshot("finalization",runId,scoring,output);
    const std::string name="effective_config_final_r"+std::to_string(runId)+"_t"+std::to_string(G4Threading::G4GetThreadId())+".json";
    WriteEffectiveSnapshot(snapshot,name,output,runId,G4Threading::G4GetThreadId());
    effectiveThreadFinals_.emplace_back(Value::Object{{"file",output->MakeOutputPath(name)},{"run_id",runId},
        {"thread_id",G4Threading::G4GetThreadId()},{"revision",static_cast<std::int64_t>(snapshot.Revision())}});
}

void SimulationManager::WriteEffectiveFinalization()
{
    std::lock_guard<std::mutex> lock(effectiveMutex_);
    outputManager_->RecordEffectiveConfigState("finalization");
    if(configuredEffective_ && !effectiveConfigureWritten_.count(outputManager_->GetOutputDir())) {
        WriteEffectiveSnapshot(*configuredEffective_,"effective_config_configure.json",outputManager_.get());
        effectiveConfigureWritten_.insert(outputManager_->GetOutputDir());
    }
    auto snapshot=EffectiveSnapshot("finalization",std::nullopt);
    // Keep thread snapshots independently scoped; the process final snapshot
    // never promotes one worker's observation to an all-worker assertion.
    WriteEffectiveSnapshot(snapshot,"effective_config_finalization.json",outputManager_.get());
}

void SimulationManager::ApplyModuleModes()
{
    moduleModes_.clear();
    const auto& reader=configManager_->GetMainReader();
    for(const auto& field:reader.GetFields()) if(field.normalizedSection=="modules") {
        if(field.normalizedKey!="scoring" && field.normalizedKey!="biasing" && field.normalizedKey!="field" && field.normalizedKey!="trajectories")
            throw std::runtime_error(reader.GetFilename()+":"+std::to_string(field.lineNumber)+": unsupported optional module '"+field.originalKey+"'; geometry/source/physics are required");
    }
    const auto has=[&](const char* section,const char* key){return configLoaded_ && configManager_->HasKey(section,key);};
    const auto explicitTrue=[&](const char* section,const char* key){return has(section,key) && configManager_->GetBool(section,key,false);};
    const auto explicitFalse=[&](const char* section,const char* key){return has(section,key) && !configManager_->GetBool(section,key,true);};
    const auto hasFields=[&](const std::string& section){
        for(const auto& field:reader.GetFields())if(field.normalizedSection==section)return true;
        return false;
    };
    bool scorerDemand=false;
    for(const char* key:{"enabled","hits","event_edep","edep","let","dose","fluence","displacement"})
        scorerDemand=scorerDemand || explicitTrue("scoring",key);
    // Tuning an active scorer is an explicit dependency; ignored sub-sections
    // without [scoring], and settings for explicitly disabled scorers, are not.
    if(configLoaded_ && configManager_->HasSection("scoring")) {
        scorerDemand=scorerDemand || (scoringManager_->IsEdepScoringEnabled() && hasFields("scoring.edep")) ||
            (scoringManager_->IsLETScoringEnabled() && hasFields("scoring.let")) ||
            (scoringManager_->IsDisplacementScoringEnabled() && hasFields("scoring.displacement"));
    }
    const bool meshDemand=!scoringMeshCommands_.empty();
    const bool biasRules=!biasingManager_->GetEnabledXSProcessBiasRules().empty();
    const bool wrapperDemand=explicitTrue("physics","biasing");
    for(const char* name:{"scoring","biasing","field","trajectories"}) {
        const bool explicitMode=has("modules",name);
        const auto mode=StringUtils::ToLower(StringUtils::Trim(explicitMode ? configManager_->GetString("modules",name) : "auto"));
        if(mode!="off" && mode!="auto" && mode!="on")throw std::runtime_error(std::string("[modules]/")+name+" must be off, auto or on");
        moduleModes_[name]=mode;
        // Absence preserves all legacy defaults, including default SD scoring.
        if(!explicitMode)continue;
        const std::string module=name;
        const bool demand=module=="scoring" ? scorerDemand || meshDemand : module=="biasing" ? biasRules :
            module=="field" ? !fieldConfig_.Empty() : scoringManager_->GetTrajectorySettings().events>0;
        const bool incomplete=module=="biasing" && !biasRules && (explicitTrue("biasing","enabled") || wrapperDemand);
        const bool blocked=(module=="scoring" && scorerDemand && explicitFalse("scoring","enabled")) ||
            (module=="biasing" && demand && (explicitFalse("biasing","enabled") ||
                explicitFalse("physics","biasing")));
        if(mode=="off" && (demand || incomplete))
            throw std::runtime_error("[modules]/"+module+" = off conflicts with an explicit active request; remove the request or select auto/on");
        if(mode!="off" && blocked)
            throw std::runtime_error("[modules]/"+module+" = "+mode+" conflicts with an explicit disabled legacy switch");
        if(mode!="off" && incomplete)
            throw std::runtime_error("[modules]/biasing requires complete enabled particle/process rules; an empty hook or physics wrapper is not a rule");
        if(mode=="on" && !demand)
            throw std::runtime_error("[modules]/"+module+" = on requires an explicitly configured active module; no settings or physics are invented");
        const bool enabled=mode!="off" && demand;
        Origin origin;origin.kind="module_policy";origin.section="modules";origin.key=module;origin.raw=mode;origin.disposition="derived";
        origin.file=reader.GetFilename();origin.input_sha256=reader.GetInputSha256();
        for(const auto& d:reader.GetFields())if(d.normalizedSection=="modules" && d.normalizedKey==module)origin.line=d.lineNumber;
        if(module=="scoring") {
            // Mesh-only demand does not turn on the independent sensitive-volume gate.
            if(!enabled || !scorerDemand)scoringManager_->SuppressModule(false,origin);
        } else if(module=="trajectories") {
            if(!enabled)scoringManager_->SuppressModule(true,origin);
        } else if(module=="field")fieldConfig_.SetModuleEnabled(enabled);
        else {
            biasingManager_->Enable(enabled);
            biasingManager_->ConfirmEffectiveConfigDerived("[modules]/biasing = "+mode,origin);
            physicsManager_->EnableBiasingPhysics(enabled);
            physicsManager_->ConfirmEffectiveConfigMutation(std::string("/AIHL/physics/enableBiasing ")+(enabled?"true":"false"),origin);
        }
    }
    if(biasingManager_->IsEnabled()) {
        Origin derived;derived.kind="derived";derived.raw="Enabled biasing rules require wrapped physics";derived.disposition="derived";
        physicsManager_->ConfirmEffectiveConfigMutation("/AIHL/physics/enableBiasing true",derived);
    }
}

void SimulationManager::ValidateEffectiveModuleCommand(const std::string& command) const
{
    const auto token=Token(command);
    if(IsReadOnlyCommand(token))return;
    for(const auto& mode:moduleModes_) if(mode.second=="off") {
        bool conflict=mode.first=="scoring" && (token.rfind("/aihl/scoring/",0)==0 || token.rfind("/score/",0)==0);
        conflict=conflict || (mode.first=="biasing" && (token.rfind("/aihl/biasing/",0)==0 || token.find("/aihl/physics/enablebiasing")==0));
        if(conflict)throw std::runtime_error("Command conflicts with [modules]/"+mode.first+" = off; edit the startup configuration and use a new process");
    }
}
