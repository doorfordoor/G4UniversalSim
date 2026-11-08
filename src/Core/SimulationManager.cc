#include "Core/SimulationManager.hh"
#include "Core/ConfigurationCoordinator.hh"

#include "Actions/ActionInitialization.hh"
#include "Config/ConfigManager.hh"
#include "Config/EffectiveConfig.hh"
#include "Config/InputProvenance.hh"
#include "Core/AppMessenger.hh"
#include "Detector/DetectorConstruction.hh"
#include "Geometry/GeometryManager.hh"
#include "Geometry/GeometryMessenger.hh"
#include "Hits/SensitiveDetector.hh"
#include "Materials/MaterialManager.hh"
#include "Materials/MaterialMessenger.hh"
#include "Output/AnalysisOutput.hh"
#include "Output/OutputManager.hh"
#include "Output/OutputMessenger.hh"
#include "Output/RunSummary.hh"
#include "Physics/PhysicsFactory.hh"
#include "Physics/PhysicsList.hh"
#include "Physics/PhysicsManager.hh"
#include "Physics/PhysicsMessenger.hh"
#include "Source/PrimaryGeneratorAction.hh"
#include "Source/SourceManager.hh"
#include "Source/SourceMessenger.hh"
#include "Biasing/BiasingManager.hh"
#include "Biasing/BiasingMessenger.hh"
#include "Scoring/ScoringMessenger.hh"
#include "ParallelWorld/ParallelWorldConfig.hh"
#include "ParallelWorld/ScoringParallelWorld.hh"
#include "Scoring/ScoringManager.hh"
#include "Scoring/ScoringMeshConfig.hh"
#include "Scoring/ThreadLocalScoringContext.hh"
#include "Utils/FileUtils.hh"
#include "Utils/StringUtils.hh"

#include "BuildInfo.hh"
#include "G4Box.hh"
#include "G4LogicalVolume.hh"
#include "G4ParallelWorldPhysics.hh"
#include "G4RunManager.hh"
#include "G4SystemOfUnits.hh"
#include "G4ThreeVector.hh"
#include "G4VSolid.hh"
#include "G4VPhysicalVolume.hh"
#include "G4Version.hh"
#include "G4StateManager.hh"
#include "G4ScoringManager.hh"
#include "G4ScoringManager.hh"
#ifdef G4MULTITHREADED
#include "G4MTRunManager.hh"
#endif
#include "Randomize.hh"

#include <cmath>
#include <iostream>
#include <algorithm>
#include <chrono>
#include <cstdlib>
#include <ctime>
#include <sstream>
#include <map>
#include <sstream>
#include <stdexcept>
#include <vector>

namespace {

effective_config::Value OutputProvenance(const std::string& executionId)
{
    using effective_config::Value;
    Value::Array inputs;
    for (const auto& item : input_provenance::Snapshot()) {
        inputs.emplace_back(Value::Object{
            {"sequence", static_cast<std::int64_t>(item.sequence)},
            {"path", item.path}, {"kind", item.kind}, {"role", item.role},
            {"capture_method", item.capture_method}, {"status", item.status},
            {"sha256", item.sha256 ? Value(*item.sha256) : Value()},
            {"size_bytes", item.size_bytes ? Value(static_cast<std::int64_t>(*item.size_bytes)) : Value()},
            {"reason", item.reason}});
    }
    return Value::Object{
        {"schema", "g4usim_provenance_v1"}, {"execution_id", executionId},
        {"build", Value::Object{
            {"git_commit", G4USIM_GIT_COMMIT}, {"git_source_state", G4USIM_GIT_SOURCE_STATE},
            {"git_state_scope", "cpp_build_inputs"},
            {"source_fingerprint", G4USIM_SOURCE_FINGERPRINT},
            {"compiler_id", G4USIM_COMPILER_ID}, {"compiler_version", G4USIM_COMPILER_VERSION},
            {"configuration", G4USIM_BUILD_CONFIGURATION}, {"geant4_version", G4Version}}},
        {"input_coverage", "project_readers_observed"},
        {"input_observation", "bytes_read_not_semantic_acceptance"},
        {"input_exclusions", Value::Array{
            "Geant4 internal datasets and external physics-table reads are not byte-captured",
            "Native command input IO outside the project readers is not comprehensively observed; known references are marked unobserved"}},
        {"inputs", std::move(inputs)}};
}

std::string BoolText(bool value)
{
    return value ? "true" : "false";
}

std::string UtcTimestamp()
{
    const std::time_t now = std::time(nullptr);
    std::tm utc{};
#ifdef _WIN32
    gmtime_s(&utc, &now);
#else
    gmtime_r(&now, &utc);
#endif
    char buffer[32]{};
    std::strftime(buffer, sizeof(buffer), "%Y-%m-%dT%H:%M:%SZ", &utc);
    return buffer;
}

std::string TestOutputFault()
{
#ifdef _WIN32
    char* value = nullptr;
    std::size_t length = 0;
    if (_dupenv_s(&value, &length, "G4USIM_TEST_OUTPUT_FAULT") != 0) return {};
    const std::string result = value ? value : "";
    std::free(value);
    return result;
#else
    const char* value = std::getenv("G4USIM_TEST_OUTPUT_FAULT");
    return value ? value : "";
#endif
}

std::string FirstCommandToken(const std::string& command)
{
    const std::string trimmed = StringUtils::Trim(command);
    const std::size_t separator = trimmed.find_first_of(" \t\r\n");
    return StringUtils::ToLower(trimmed.substr(0, separator));
}

std::map<std::string, std::vector<std::string>> BuildBiasParticleProcessMap(
    const BiasingManager* biasingManager)
{
    std::map<std::string, std::vector<std::string>> values;
    if (!biasingManager) return values;
    for (const std::string& particle : biasingManager->GetBiasedParticles()) {
        if (!StringUtils::Trim(particle).empty()) {
            values[particle] = biasingManager->GetBiasedProcesses(particle);
        }
    }
    return values;
}

std::vector<std::string> FilterOutGenericBiasingModules(const std::vector<std::string>& modules)
{
    std::vector<std::string> filtered;
    for (const auto& module : modules) {
        try {
            if (PhysicsFactory::Classify(module) == PhysicsCategory::Biasing) continue;
            if (PhysicsFactory::NormalizeOptionName(module) == "MicroElecPhysics") continue;
        } catch (...) {
        }
        filtered.push_back(module);
    }
    return filtered;
}

}  // namespace

SimulationManager::SimulationManager()
{
    BuildManagers();
}

SimulationManager::~SimulationManager() = default;

SimulationContext& SimulationManager::GetContext()
{
    return context_;
}

const SimulationContext& SimulationManager::GetContext() const
{
    return context_;
}

void SimulationManager::SetCommandLineOverrides(const SimulationCommandLineOverrides& overrides)
{
    if (commandLineOverridesSet_ || configLoaded_ || configured_ || initialized_) {
        throw std::runtime_error(
            "SimulationManager::SetCommandLineOverrides must be called exactly once before configuration"
        );
    }
    commandLineOverridesSet_ = true;
    commandLineOverrides_ = overrides;

    if (overrides.mainConfig) {
        context_.SetMainConfig(*overrides.mainConfig);
        configLoaded_ = false;
        configured_ = false;
        initialized_ = false;
    }
    if (overrides.outputDir) context_.SetOutputDir(*overrides.outputDir);
    if (overrides.runName) context_.SetRunName(*overrides.runName);
    if (overrides.macroFile) context_.SetMacroFile(*overrides.macroFile);
    if (overrides.numThreads) context_.SetNumThreads(*overrides.numThreads);
    if (overrides.seed) context_.SetSeed(*overrides.seed);
    if (overrides.interactive) context_.SetInteractive(*overrides.interactive);
    if (overrides.dryRun) context_.SetDryRun(*overrides.dryRun);
    if (overrides.checkOverlaps) context_.SetCheckOverlaps(*overrides.checkOverlaps);
}

void SimulationManager::SetMainConfig(const std::string& filename)
{
    // Changing the main INI after Configure() would invalidate the effective
    // configuration while leaving already-configured managers in place.
    if (configured_ || initialized_) {
        throw std::runtime_error(
            "Main config cannot be changed after configuration; start a new process with --config <file>"
        );
    }
    if (commandLineOverrides_.mainConfig) {
        WarnIgnoredCommandLineOverride("main config");
        return;
    }
    context_.SetMainConfig(filename);
    configLoaded_ = false;
    configured_ = false;
    initialized_ = false;
}

void SimulationManager::SetOutputDir(const std::string& outputDir)
{
    // Worker outputs are cloned from the selected directory. After Geant4
    // initialization, changing only the master would split CSVs and summary.
    if (G4StateManager::GetStateManager()->GetCurrentState() != G4State_PreInit) {
        throw std::runtime_error(
            "Output directory cannot be changed after Geant4 initialization; "
            "set it before /run/initialize or start a new process with --output <dir>"
        );
    }
    if (commandLineOverrides_.outputDir) {
        WarnIgnoredCommandLineOverride("output directory");
        return;
    }
    // Do not change the effective context or its origin unless the runtime
    // output manager accepts the new directory. Messenger failures may have
    // an ApplyCommand() status of zero when reported as JustWarning.
    const std::string normalizedDir = outputDir.empty() ? "output" : outputDir;
    if (outputManager_) {
        outputManager_->SetOutputDir(normalizedDir);
    }
    context_.SetOutputDir(normalizedDir);
    MarkRuntimeValueOrigin("output_dir");
}

void SimulationManager::SetNumThreads(int n)
{
    // G4MTRunManager rejects thread-count changes once workers are initialized.
    // Refuse before changing our configuration/origin snapshot, so the summary
    // cannot claim a thread count which the Geant4 kernel ignored.
    if (G4StateManager::GetStateManager()->GetCurrentState() != G4State_PreInit) {
        throw std::runtime_error(
            "Thread count cannot be changed after Geant4 initialization; restart with --threads <n> "
            "or set /AIHL/app/setNumThreads before /run/initialize"
        );
    }
    if (commandLineOverrides_.numThreads) {
        WarnIgnoredCommandLineOverride("thread count");
        return;
    }
    context_.SetNumThreads(n);
    MarkRuntimeValueOrigin("threads");
#ifdef G4MULTITHREADED
    if (auto* runManager = dynamic_cast<G4MTRunManager*>(G4RunManager::GetRunManager())) {
        runManager->SetNumberOfThreads(n);
    }
#endif
}

void SimulationManager::SetSeed(unsigned long seed)
{
    // Re-seeding after initialisation would only touch the master engine: worker engines are
    // already created with the configured seed, so the run would be neither reproducible nor
    // described by the summary's configured_seed.
    if (G4StateManager::GetStateManager()->GetCurrentState() != G4State_PreInit) {
        throw std::runtime_error(
            "Random seed cannot be changed after Geant4 initialization; restart with --seed <n> "
            "or set /AIHL/app/setSeed before /run/initialize"
        );
    }
    if (commandLineOverrides_.seed) {
        WarnIgnoredCommandLineOverride("random seed");
        return;
    }
    context_.SetSeed(seed);
    MarkRuntimeValueOrigin("seed");
    CLHEP::HepRandom::setTheSeed(static_cast<long>(seed));
}

void SimulationManager::SetMacroFile(const std::string& filename)
{
    if (commandLineOverrides_.macroFile) {
        WarnIgnoredCommandLineOverride("macro file");
        return;
    }
    context_.SetMacroFile(filename);
    MarkRuntimeValueOrigin("macro_file");
}

void SimulationManager::SetInteractive(bool interactive)
{
    if (commandLineOverrides_.interactive) {
        WarnIgnoredCommandLineOverride("interactive mode");
        return;
    }
    context_.SetInteractive(interactive);
}

void SimulationManager::SetVerboseLevel(int level)
{
    context_.SetVerboseLevel(level);
}

void SimulationManager::SetCheckOverlaps(bool enable)
{
    if (commandLineOverrides_.checkOverlaps) {
        WarnIgnoredCommandLineOverride("geometry overlap checking");
        return;
    }
    context_.SetCheckOverlaps(enable);
    MarkRuntimeValueOrigin("check_overlaps");
    if (geometryManager_) geometryManager_->SetCheckOverlaps(enable);
}

void SimulationManager::SetDryRun(bool enable)
{
    if (commandLineOverrides_.dryRun) {
        WarnIgnoredCommandLineOverride("dry-run mode");
        return;
    }
    context_.SetDryRun(enable);
}

void SimulationManager::SetRunName(const std::string& name)
{
    if (commandLineOverrides_.runName) {
        WarnIgnoredCommandLineOverride("run name");
        return;
    }
    context_.SetRunName(name);
    MarkRuntimeValueOrigin("run_name");
}

void SimulationManager::LoadConfig()
{
    EnsureConfigManager();
    if (context_.GetMainConfig().empty()) {
        configLoaded_ = false;
        configured_ = false;
        return;
    }
    if (!FileUtils::IsFile(context_.GetMainConfig())) {
        throw std::runtime_error("Main config file does not exist: '" + context_.GetMainConfig() + "'");
    }

    configManager_->LoadMainConfig(context_.GetMainConfig());
    configLoaded_ = true;
    configWarningsReported_ = false;
    configured_ = false;
    initialized_ = false;
}

void SimulationManager::Initialize()
{
    BuildManagers();
    if (!context_.GetMainConfig().empty() && !configLoaded_) {
        LoadConfig();
    }
    if (!configured_) {
        Configure();
    }

    ConfigureOutputManager();
    outputManager_->Initialize();
    initialized_ = true;
    WriteBaseRunSummary();
}

void SimulationManager::BeginRuntimeTracking()
{
    initialSeed_ = context_.HasSeed()
        ? std::optional<unsigned long>(context_.GetSeed())
        : std::nullopt;
    macroSeedModified_ = false;
    runtimeTrackingStarted_ = true;
}

bool SimulationManager::NoteMacroCommand(const std::string& command) const
{
    const std::string token = FirstCommandToken(command);
    return token == "/aihl/app/setseed" ||
           token == "/random/setseeds" ||
           token == "/random/resetenginefrom";
}

void SimulationManager::ConfirmMacroCommandSuccess(bool seedStateChanged)
{
    if (seedStateChanged) macroSeedModified_ = true;
}

void SimulationManager::MarkRuntimeValueOrigin(const std::string& field)
{
    effectiveValueOrigins_[field] = ValueOrigin{"runtime_unattributed", "", "", "", 0};
}

void SimulationManager::RecordSuccessfulMacroCommand(const std::string& command,
                                                       const std::string& file,
                                                       int line, const std::string& inputSha256)
{
    effective_config::Origin receipt;
    receipt.kind = file.empty() ? "interactive" : "macro";
    receipt.file = file; receipt.line = static_cast<std::uint64_t>(std::max(0, line));
    receipt.raw = command; receipt.input_sha256 = inputSha256;
    ConfirmEffectiveCommand(command, receipt);
    // The command is recorded only after ApplyCommand and the corresponding
    // Messenger failure checks succeed. Never attribute an attempted command.
    const std::string token = FirstCommandToken(command);
    // These native paths bypass project readers. Record a reference, never a
    // final-path hash pretending to describe bytes actually read by Geant4.
    // The physics-table command only schedules a possible future retrieval.
    if (token == "/gps/hist/file" || token == "/run/particle/retrievephysicstable") {
        const auto separator = command.find_first_of(" \t");
        const auto argument = separator == std::string::npos ? std::string() :
            StringUtils::Trim(command.substr(separator + 1));
        if (token != "/run/particle/retrievephysicstable" || StringUtils::ToLower(argument) != "off") {
            input_provenance::MarkUnobserved(argument.empty() ? "(native default directory)" : argument,
                "Successful native command reference; consumed bytes and later retrieval are unobserved: " + token,
                "native_command", token, "command_reference_not_read");
        }
    }
    std::string field;
    if (token == "/aihl/app/setoutputdir" || token == "/aihl/output/setdir") field = "output_dir";
    else if (token == "/aihl/app/setnumthreads") field = "threads";
    else if (token == "/aihl/app/setseed") field = "seed";
    else if (token == "/aihl/app/setcheckoverlaps" || token == "/aihl/geometry/checkoverlaps") field = "check_overlaps";
    else if (token == "/aihl/geometry/settemplate") field = "geometry_template";
    else if (token == "/aihl/geometry/loadconfig" || token == "/aihl/geometry/clear") field = "geometry_config";
    else if (token == "/aihl/geometry/setdefaultworldmaterial") field = "geometry_default_world_material";
    else if (token == "/aihl/source/particle" || token == "/aihl/source/preset" ||
             token == "/aihl/source/reset") field = "source_particle";
    else if (token == "/aihl/physics/setreferencelist" ||
             token == "/aihl/physics/clearreferencelist" ||
             token == "/aihl/physics/setbasereferencelist") field = "physics_reference";
    else if (token == "/aihl/physics/setem" && physicsManager_ &&
             physicsManager_->HasReferenceList()) field = "physics_reference";
    if (token == "/aihl/source/energy" || token == "/aihl/source/preset" ||
        token == "/aihl/source/reset") {
        effectiveValueOrigins_["source_energy"] = ValueOrigin{"macro", file, "", token, line};
    }
    if (field.empty()) return;
    const bool locked = (field == "output_dir" && commandLineOverrides_.outputDir) ||
                        (field == "threads" && commandLineOverrides_.numThreads) ||
                        (field == "seed" && commandLineOverrides_.seed) ||
                        (field == "check_overlaps" && commandLineOverrides_.checkOverlaps);
    if (!locked) effectiveValueOrigins_[field] = ValueOrigin{"macro", file, "", token, line};
}

void SimulationManager::CaptureConfiguredValueOrigins()
{
    const auto fields = configLoaded_ ? configManager_->GetFields() : std::vector<IniFieldInfo>{};
    const auto select = [this, &fields](const std::string& name, bool cli,
                                       std::initializer_list<std::pair<std::string, std::string>> keys,
                                       bool nonempty = false) {
        ValueOrigin origin;
        if (cli) {
            origin.kind = "cli";
        } else if (configLoaded_) {
            for (const auto& key : keys) {
                if (!configManager_->HasKey(key.first, key.second)) continue;
                if (nonempty && StringUtils::Trim(configManager_->GetString(key.first, key.second)).empty()) continue;
                origin.kind = "main_ini";
                origin.file = configManager_->GetMainConfigPath();
                origin.section = key.first;
                origin.key = key.second;
                for (const auto& item : fields) {
                    if (StringUtils::ToLower(item.section) == StringUtils::ToLower(key.first) &&
                        StringUtils::ToLower(item.key) == StringUtils::ToLower(key.second)) {
                        origin.section = item.originalSection;
                        origin.key = item.originalKey;
                        origin.line = static_cast<int>(item.lineNumber);
                        break;
                    }
                }
                break;
            }
        }
        effectiveValueOrigins_[name] = origin;
    };
    select("output_dir", commandLineOverrides_.outputDir.has_value(),
           {{"output", "dir"}, {"output", "outputDir"}}, true);
    select("run_name", commandLineOverrides_.runName.has_value(),
           {{"run", "name"}, {"run", "run_name"}, {"run", "runName"}}, true);
    select("threads", commandLineOverrides_.numThreads.has_value(), {{"run", "threads"}});
    select("seed", commandLineOverrides_.seed.has_value(),
           {{"run", "seed"}, {"run", "randomSeed"}, {"general", "seed"}, {"general", "randomSeed"}});
    select("macro_file", commandLineOverrides_.macroFile.has_value(), {{"run", "macro"}});
    select("check_overlaps", commandLineOverrides_.checkOverlaps.has_value(),
           {{"geometry", "check_overlaps"}, {"geometry", "checkOverlaps"},
            {"run", "check_overlaps"}, {"run", "checkOverlaps"}});
    select("geometry_template", false, {{"geometry", "template"}, {"geometry", "templateName"}}, true);
    select("geometry_config", false, {{"geometry", "config"}, {"geometry", "configFile"}}, true);
    select("geometry_default_world_material", false,
           {{"geometry", "default_world_material"}, {"geometry", "defaultWorldMaterial"}}, true);
    // A preset supplies a particle unless an explicit, nonempty particle key overrides it.
    select("source_particle", false, {{"source", "particle"}, {"source", "preset"}}, true);
    // ApplyPreset assigns its default energy before any explicit [source]/energy override.
    select("source_energy", false, {{"source", "energy"}, {"source", "preset"}}, true);
    select("physics_reference", false, {{"physics", "reference"}});
    // In reference mode the explicit EM option selects the final reference suffix.
    if (physicsManager_ && physicsManager_->HasReferenceList() && configLoaded_ &&
        configManager_->HasKey("physics", "em") &&
        !StringUtils::Trim(configManager_->GetString("physics", "em")).empty()) {
        select("physics_reference", false, {{"physics", "em"}}, true);
    }
}

void SimulationManager::SetExecutedMacroPath(const std::string& path)
{
    executedMacroPath_ = path;
}

bool SimulationManager::FinalizeRunSummary(const std::string& status,
                                            int exitCode,
                                            const std::string& macroStatus,
                                            const std::string& failureFile,
                                            int failureLine,
                                            const std::string& failureCommand,
                                            int failureCode,
                                            bool failureCodeAvailable)
{
    EnsureOutputManager();
    if (!initialized_) {
        WriteBaseRunSummary();
    }

    const auto finalizeOutput = [this](const char* stage, const auto& action) {
        try {
            action();
        } catch (const std::exception& error) {
            outputManager_->RecordOutputFailure(stage, error.what());
        } catch (...) {
            outputManager_->RecordOutputFailure(stage, "unknown exception");
        }
    };

    // Only test processes opt into these deterministic main-thread failures.
    // Production output still uses the real Flush/Close operations below.
    const std::string injectedFault = TestOutputFault();
    finalizeOutput("final_flush", [this, &injectedFault]() {
        outputManager_->Flush();
        if (injectedFault == "final_flush_master") {
            std::cerr << "[TestOutputFault] final_flush_master triggered\n";
            throw std::runtime_error("Injected main-thread final flush failure");
        }
    });
    finalizeOutput("final_close", [this, &injectedFault]() {
        outputManager_->Close();
        if (injectedFault == "final_close_master") {
            std::cerr << "[TestOutputFault] final_close_master triggered\n";
            throw std::runtime_error("Injected main-thread final close failure");
        }
    });
    // Contract D receipts must be recorded before the finalization snapshot is
    // written, and both the finalization write and the artifact evidence
    // collection below must observe the same completion boundary: a file that
    // run_summary.txt lists can never be missing from run_metadata.json.
    if (parallelWorldConfig_ && parallelWorldConfig_->enabled()) {
        const bool receiptsOutputFailed = outputManager_->HasOutputFailure();
        for (const auto& run : outputManager_->GetRunSummary().GetRuns()) {
            if (receiptsOutputFailed || run.completedEvents <= 0 ||
                run.completedEvents != run.plannedEvents) {
                continue;
            }
            effective_config::Value::Array files;
            try {
                for (const auto& artifact : outputManager_->CollectRunArtifacts(run.runId, false)) {
                    if (!artifact.sha256 || artifact.path.empty() ||
                        artifact.integrity_status != "hashed") {
                        continue;
                    }
                    files.emplace_back(effective_config::Value::Object{
                        {"path", artifact.path}, {"sha256", *artifact.sha256}});
                }
            } catch (const std::exception& error) {
                outputManager_->RecordOutputFailure("parallel_world_run_evidence",
                                                    error.what(), run.runId);
                continue;
            }
            if (files.empty()) continue;  // no completed output => no success receipt
            effective_config::Value::Object outputSha256;
            outputSha256.emplace("files", effective_config::Value(std::move(files)));
            outputSha256.emplace("completed_events",
                                 static_cast<std::int64_t>(run.completedEvents));
            parallelWorldConfig_->RecordRunValidated(run.runId, run.completedEvents,
                                                    parallelWorldConfig_->volumeCount(),
                                                    outputSha256);
        }
    }
    if (configured_) {
        finalizeOutput("effective_config_finalization", [this]() { WriteEffectiveFinalization(); });
    }
    RunSummary& summary = outputManager_->GetRunSummary();
    const auto& runs = summary.GetRuns();
    std::int64_t plannedEvents = 0;
    std::int64_t completedEvents = 0;
    bool incompleteRun = false;
    for (const auto& run : runs) {
        plannedEvents += run.plannedEvents;
        completedEvents += run.completedEvents;
        incompleteRun = incompleteRun || run.completedEvents != run.plannedEvents;
    }

    auto workerEvidence = biasingManager_ ? biasingManager_->GetWorkerEvidence()
                                         : std::vector<BiasingManager::WorkerEvidence>{};
    // These two injections test the receipt coverage gate, not transport.
    if (injectedFault == "biasing_missing_worker_receipt" && !workerEvidence.empty())
        workerEvidence.erase(workerEvidence.begin());
    if (injectedFault == "biasing_missing_end_receipt" && !workerEvidence.empty())
        workerEvidence.front().endRunCompleted = false;
    auto* actualRunManager = G4RunManager::GetRunManager();
    const int executionThreads = actualRunManager ? std::max(1, actualRunManager->GetNumberOfThreads()) : 0;
    std::map<std::pair<int, int>, bool> expectedWorkers;
    if (biasingManager_ && biasingManager_->IsEnabled()) {
        for (const auto& run : runs)
            for (int worker = 0; worker < executionThreads; ++worker)
                expectedWorkers[{run.runId, worker}] = false;
    }
    bool workerCoverageComplete = !expectedWorkers.empty() && workerEvidence.size() == expectedWorkers.size();
    bool workersValidated = workerCoverageComplete;
    for (const auto& evidence : workerEvidence) {
        const auto found = expectedWorkers.find({evidence.runId, evidence.threadId});
        if (found == expectedWorkers.end() || found->second || !evidence.endRunCompleted)
            workerCoverageComplete = false;
        else found->second = true;
        workersValidated = workersValidated && evidence.tlsVerified && evidence.operators > 0 &&
                           evidence.matchedRules > 0 && evidence.failure.empty();
    }
    for (const auto& expected : expectedWorkers) workerCoverageComplete = workerCoverageComplete && expected.second;
    workersValidated = workersValidated && workerCoverageComplete;
    if (biasingManager_ && biasingManager_->IsEnabled() && !runs.empty() && !workersValidated)
        outputManager_->RecordOutputFailure("biasing_worker_evidence",
            "Incomplete or failed execution-thread biasing receipts (run/thread/EndRun coverage)");

    // One streaming pass over closed ordinary artifacts. A registered file
    // disappearing is a failure, not permission to silently shorten the list.
    auto artifacts = outputManager_->CollectArtifactEvidence(true, true);
    summary.SetProvenance(OutputProvenance(outputManager_->GetExecutionId()));
    summary.Set("execution_id", outputManager_->GetExecutionId());
    summary.Set("output_provenance_schema", "g4usim_provenance_v1");
    std::string finalStatus = status;
    const bool outputFailed = outputManager_->HasOutputFailure();
    const auto outputFailure = outputManager_->GetOutputFailure();
    if (outputFailed) finalStatus = "failed";
    if (status == "completed" && incompleteRun) {
        if (!outputFailed) finalStatus = "aborted";
    }
    summary.Set("status", finalStatus);
    summary.Set("program_exit_code", outputFailed ? EXIT_FAILURE : exitCode);
    summary.Set("output_failure_status", outputFailed ? "failed" : "none");
    summary.Set("output_failure_run_id", outputFailed ? std::to_string(outputFailure.runId) : "not_applicable");
    summary.Set("output_failure_thread_id", outputFailed ? std::to_string(outputFailure.threadId) : "not_applicable");
    summary.Set("output_failure_stage", outputFailed ? outputFailure.stage : "not_applicable");
    summary.Set("output_failure_message", outputFailed ? outputFailure.message : "not_applicable");
    summary.Set("summary_generated_at", UtcTimestamp());
    summary.Set("macro_execution_status", macroStatus);
    summary.Set("macro_failure_phase",
                macroStatus == "preflight_failed" ? "preflight" :
                (macroStatus == "failed" ? "execution" : ""));
    summary.SetPath("actual_macro_file", executedMacroPath_.empty() ? "unknown" : executedMacroPath_);
    summary.SetPath("macro_failure_file", failureFile);
    summary.Set("macro_failure_line", failureLine);
    summary.Set("macro_failure_command", failureCommand);
    summary.Set("macro_failure_code", failureCode);
    summary.SetBool("macro_failure_code_available",
                    macroStatus == "failed" && failureCodeAvailable);
    summary.Set("planned_event_count", plannedEvents);
    summary.Set("actual_completed_event_count", completedEvents);
    summary.Set("run_count", static_cast<int>(runs.size()));
    summary.SetBool("simulation_executed", !runs.empty());
    summary.SetBool("biasing_operators_attached", biasingManager_ && biasingManager_->AreOperatorsAttached());
    summary.Set("biasing_attached_operator_count", static_cast<int>(biasingManager_ ? biasingManager_->GetAttachedOperatorCount() : 0));
    summary.Set("biasing_matched_process_rule_count", static_cast<int>(biasingManager_ ? biasingManager_->GetMatchedProcessRuleCount() : 0));
    summary.Set("biasing_process_match_status", !biasingManager_ || !biasingManager_->IsEnabled() ? "not_applicable" :
                (biasingManager_->GetMatchedProcessRuleCount() > 0 ? "validated" : "not_validated"));
    summary.Set("biasing_effect_observed", "unknown");
    summary.Set("biasing_attachment_scope", "master_geometry");
    summary.Set("biasing_worker_evidence_count", static_cast<int>(workerEvidence.size()));
    summary.Set("biasing_expected_worker_evidence_count", static_cast<int>(expectedWorkers.size()));
    summary.SetBool("biasing_worker_coverage_complete", workerCoverageComplete);
    for (std::size_t i = 0; i < workerEvidence.size(); ++i) {
        const auto& evidence = workerEvidence[i];
        const std::string prefix = "biasing_worker_" + std::to_string(i) + "_";
        summary.Set(prefix + "run_id", evidence.runId);
        summary.Set(prefix + "thread_id", evidence.threadId);
        summary.Set(prefix + "operators", std::to_string(evidence.operators));
        summary.Set(prefix + "matched_rules", std::to_string(evidence.matchedRules));
        summary.SetBool(prefix + "tls_verified", evidence.tlsVerified);
        summary.SetBool(prefix + "end_run_completed", evidence.endRunCompleted);
        summary.Set(prefix + "proposals", std::to_string(evidence.proposals));
        summary.Set(prefix + "applied_callbacks", std::to_string(evidence.applied));
        summary.Set(prefix + "failure", evidence.failure.empty() ? "none" : evidence.failure);
    }
    summary.Set("biasing_worker_validation_status", runs.empty() || !biasingManager_ || !biasingManager_->IsEnabled() ? "not_observed" :
                (workersValidated ? "validated" : "failed"));
    summary.SetPath("actual_output_dir", outputManager_->GetOutputDir());
    summary.Set("output_format", OutputManager::FormatName(outputManager_->GetFormat()));
    summary.Set("output_format_requested", OutputManager::FormatName(outputManager_->GetRequestedFormat()));
    summary.Set("output_format_selection_reason", outputManager_->FormatSelectionReason());
    summary.Set("scoring_mesh_ini_command_count", static_cast<int>(scoringMeshCommands_.size()));
    summary.Set("output_root_schema_version",
                outputManager_->WritesRoot() ? std::to_string(AnalysisOutput::kRootSchemaVersion) : "not_applicable");
    summary.Set("geant4_version", G4Version);
    summary.Set("source_fingerprint", G4USIM_SOURCE_FINGERPRINT);
    summary.Set("build_git_commit", G4USIM_GIT_COMMIT);
    summary.Set("build_git_source_state", G4USIM_GIT_SOURCE_STATE);
    summary.Set("initial_seed", initialSeed_ ? std::to_string(*initialSeed_) : "unset");
    summary.Set("configured_seed", context_.HasSeed() ? std::to_string(context_.GetSeed()) : "unset");
    summary.Set("initial_engine_seed", "unknown");
    summary.SetBool("macro_seed_modified", macroSeedModified_);

    if (parallelWorldConfig_ && parallelWorldConfig_->enabled()) {
        summary.SetBool("parallel_world_enabled", true);
        summary.Set("parallel_world_name", parallelWorldConfig_->name());
        summary.SetPath("parallel_world_geometry_config", parallelWorldConfig_->geometryConfigFile());
        summary.Set("parallel_world_geometry_sha256", parallelWorldConfig_->geometrySha256());
        summary.Set("parallel_world_volume_count", parallelWorldConfig_->volumeCount());
        if (parallelWorldConfig_->materialsResolved()) {
            // RunSummary::Set(double) keeps 12 significant digits; the default
            // std::to_string would print a small positive mass as 0.
            summary.Set("parallel_world_total_mass_kg", parallelWorldConfig_->totalMassKg());
        } else {
            summary.Set("parallel_world_total_mass_kg", "unknown");
        }
        summary.Set("parallel_world_physics_constructor", "G4ParallelWorldPhysics");
        summary.Set("parallel_world_process", "G4ParallelWorldProcess");
        summary.Set("parallel_world_step_source", "ghost_step");
        summary.Set("parallel_world_dose_normalization", "declared_material_reference_mass");
    }

    // Capture the current Manager values at the execution boundary.  These
    // are not a claim that every setting was applied to an initialized G4
    // object, and they deliberately do not fabricate per-field provenance.
    WriteFinalConfigSnapshot(macroStatus);

    if (runs.empty()) {
        summary.Set("actual_threads", status == "dry_run" ? "not_executed" : "unknown");
    } else if (auto* runManager = G4RunManager::GetRunManager()) {
        summary.Set("actual_threads", runManager->GetNumberOfThreads());
    } else {
        summary.Set("actual_threads", "unknown");
    }

    std::vector<std::string> generated = outputManager_->GetGeneratedFiles();
    generated.push_back(FileUtils::AbsolutePath(outputManager_->MakeOutputPath("run_summary.txt")));
    generated.push_back(FileUtils::AbsolutePath(outputManager_->MakeOutputPath("run_metadata.json")));
    std::sort(generated.begin(), generated.end());
    generated.erase(std::unique(generated.begin(), generated.end()), generated.end());
    summary.SetGeneratedFiles(generated);
    summary.Set("generated_file_count", static_cast<int>(generated.size()));
    for (const std::string& path : generated) {
        if (FileUtils::Filename(path).rfind("spectrum_", 0) == 0) {
            summary.Set("spectrum_csv_schema_version", 1);
            break;
        }
    }
    summary.Set("summary_write_status", "completed");

    outputManager_->WriteRunSummary();
    OutputManager::ArtifactEvidence textArtifact;
    textArtifact.path = FileUtils::AbsolutePath(outputManager_->MakeOutputPath("run_summary.txt"));
    textArtifact.execution_id = outputManager_->GetExecutionId();
    try {
        const auto digest = input_provenance::HashFile(textArtifact.path);
        textArtifact.sha256 = digest.sha256;
        textArtifact.size_bytes = digest.size_bytes;
        textArtifact.integrity_status = "hashed";
    } catch (const std::exception& error) {
        textArtifact.integrity_status = "unavailable";
        textArtifact.reason = error.what();
        outputManager_->RecordOutputFailure("artifact_integrity", error.what());
        const auto failure = outputManager_->GetOutputFailure();
        summary.Set("status", "failed");
        summary.Set("program_exit_code", EXIT_FAILURE);
        summary.Set("output_failure_status", "failed");
        summary.Set("output_failure_run_id", std::to_string(failure.runId));
        summary.Set("output_failure_thread_id", std::to_string(failure.threadId));
        summary.Set("output_failure_stage", failure.stage);
        summary.Set("output_failure_message", failure.message);
        outputManager_->WriteRunSummary();
    }
    artifacts.push_back(std::move(textArtifact));
    std::sort(artifacts.begin(), artifacts.end(), [](const auto& a, const auto& b) { return a.path < b.path; });
    summary.SetArtifactEvidence(artifacts);
    // Metadata may fail after the first text summary was closed. Latch its
    // precise cause, then correct the still-writable text artifact instead of
    // leaving status=completed/exit=0 behind. This is not an atomic two-file
    // transaction; a failed or partial JSON file is not a generated artifact.
    try {
        outputManager_->WriteRunMetadataJson();
    } catch (const std::exception& error) {
        outputManager_->RecordOutputFailure("run_metadata_write", error.what());
        const auto failure = outputManager_->GetOutputFailure();
        summary.Set("status", "failed");
        summary.Set("program_exit_code", EXIT_FAILURE);
        summary.Set("output_failure_status", "failed");
        summary.Set("output_failure_run_id", std::to_string(failure.runId));
        summary.Set("output_failure_thread_id", std::to_string(failure.threadId));
        summary.Set("output_failure_stage", failure.stage);
        summary.Set("output_failure_message", failure.message);
        // Use only completed registrations here. In particular, an existing
        // directory or a partially written metadata file must not be listed.
        generated = outputManager_->GetGeneratedFiles();
        const auto metadata = FileUtils::AbsolutePath(outputManager_->MakeOutputPath("run_metadata.json"));
        generated.erase(std::remove(generated.begin(), generated.end(), metadata), generated.end());
        summary.SetGeneratedFiles(generated);
        summary.Set("generated_file_count", static_cast<int>(generated.size()));
        for (const std::string& path : generated) {
            if (FileUtils::Filename(path).rfind("spectrum_", 0) == 0) {
                summary.Set("spectrum_csv_schema_version", 1);
                break;
            }
        }
        // summary_write_status describes successful text-summary completion,
        // not metadata success. If this corrective write fails it throws and
        // the existing summary-failure path remains authoritative.
        outputManager_->WriteRunSummary(); // preserve the real text-summary failure path
        return false;
    }
    return !outputManager_->HasOutputFailure();
}

void SimulationManager::Configure()
{
    BuildManagers();

    if (!context_.GetMainConfig().empty() && !configLoaded_) {
        LoadConfig();
    }

    if (configLoaded_) {
        configuration::ConfigureLoadedInputs(*configManager_, context_, {
            *materialManager_, *geometryManager_, *physicsManager_, *sourceManager_, *scoringManager_, *biasingManager_, *outputManager_,
            fieldConfig_, materialsFile_, geometryTemplate_, geometryConfigFile_, defaultWorldMaterial_, scoringMeshCommands_, parallelWorldConfig_
        });
    }

    outputManager_->SetOutputDir(context_.GetOutputDir());
    geometryManager_->SetCheckOverlaps(context_.GetCheckOverlaps());
    geometryManager_->SetMaterialManager(materialManager_.get());
    ApplyCommandLineOverrides();
    ApplyModuleModes();
    CaptureConfiguredValueOrigins();
    ReportConfigWarnings();

    initialized_ = false;
    InitializeEffectiveConfig();
    configured_ = true;
}

void SimulationManager::ReportConfigWarnings()
{
    if (!configLoaded_ || configWarningsReported_) return;

    const auto warnings = configManager_->GetUnconsumedWarnings();
    const auto duplicates = configManager_->GetDuplicateWarnings();
    RunSummary& summary = outputManager_->GetRunSummary();
    summary.Set("config_warning_count", static_cast<int>(warnings.size()));
    summary.Set("config_duplicate_count", static_cast<int>(duplicates.size()));
    const auto& geometryWarnings = geometryManager_->GetConfigDiagnostics();
    summary.Set("geometry_config_warning_count", static_cast<int>(geometryWarnings.size()));
    for (const auto& warning : warnings) {
        std::ostringstream message;
        message << "[ConfigWarning] unconsumed field " << warning.filename << ":"
                << warning.lineNumber << " [" << warning.section << "]";
        if (warning.key.empty()) {
            message << " unknown section";
        } else {
            message << "/" << warning.key << " = " << warning.value;
        }
        if (!warning.suggestion.empty()) {
            message << "; did you mean '" << warning.suggestion << "'?";
        }
        const std::string text = message.str();
        std::cerr << text << '\n';
        summary.AddWarning(text);
    }
    for (const auto& duplicate : duplicates) {
        std::ostringstream message;
        message << "[ConfigWarning] duplicate declaration " << duplicate.filename << ":"
                << duplicate.lineNumber << " [" << duplicate.section << "]";
        if (duplicate.key.empty()) {
            message << " repeated section header";
        } else {
            message << "/" << duplicate.key << " = " << duplicate.value;
        }
        message << "; " << duplicate.suggestion;
        const std::string text = message.str();
        std::cerr << text << '\n';
        summary.AddWarning(text);
    }
    for (const auto& warning : geometryWarnings) {
        const std::string text = warning.FormatWarning();
        std::cerr << text << '\n';
        summary.AddWarning(text);
    }
    configWarningsReported_ = true;
}

void SimulationManager::BuildManagers()
{
    EnsureConfigManager();
    EnsureOutputManager();
    EnsureMaterialManager();
    EnsureGeometryManager();
    EnsurePhysicsManager();
    EnsureSourceManager();
    EnsureBiasingManager();
    EnsureScoringManager();

    geometryManager_->SetMaterialManager(materialManager_.get());
    geometryManager_->SetCheckOverlaps(context_.GetCheckOverlaps());
    physicsManager_->SetBiasingManager(biasingManager_.get());
    geometryManager_->SetPhysicsManager(physicsManager_.get());
    outputManager_->SetOutputDir(context_.GetOutputDir());
    scoringManager_->SetOutputManager(outputManager_.get());

    if (!appMessenger_) {
        appMessenger_ = std::make_unique<AppMessenger>(this);
    }
    if (!outputMessenger_) {
        outputMessenger_ = std::make_unique<OutputMessenger>(
            outputManager_.get(),
            [this](const std::string& outputDir) { SetOutputDir(outputDir); });
    }
    if (!materialMessenger_) {
        materialMessenger_ = std::make_unique<MaterialMessenger>(materialManager_.get());
    }
    if (!geometryMessenger_) {
        geometryMessenger_ = std::make_unique<GeometryMessenger>(geometryManager_.get());
    }
    if (!physicsMessenger_) {
        physicsMessenger_ = std::make_unique<PhysicsMessenger>(physicsManager_.get());
    }
    if (!sourceMessenger_) {
        sourceMessenger_ = std::make_unique<SourceMessenger>(sourceManager_.get());
    }
    if (!biasingMessenger_) {
        biasingMessenger_ = std::make_unique<BiasingMessenger>(biasingManager_.get());
    }
    if (!scoringMessenger_) {
        scoringMessenger_ = std::make_unique<ScoringMessenger>(scoringManager_.get());
    }
}

void SimulationManager::PrintSummary() const
{
    std::cout << "G4UniversalSim Simulation Summary\n";
    std::cout << "  main_config       : " << context_.GetMainConfig() << '\n';
    std::cout << "  output_dir        : " << context_.GetOutputDir() << '\n';
    std::cout << "  run_name          : " << context_.GetRunName() << '\n';
    std::cout << "  num_threads       : " << context_.GetNumThreads() << '\n';
    std::cout << "  seed              : " << (context_.HasSeed() ? std::to_string(context_.GetSeed()) : "(unset)") << '\n';
    std::cout << "  macro_file        : " << context_.GetMacroFile() << '\n';
    std::cout << "  interactive       : " << BoolText(context_.IsInteractive()) << '\n';
    std::cout << "  verbose_level     : " << context_.GetVerboseLevel() << '\n';
    std::cout << "  check_overlaps    : " << BoolText(context_.GetCheckOverlaps()) << '\n';
    std::cout << "  dry_run           : " << BoolText(context_.IsDryRun()) << '\n';
    std::cout << "  material_manager  : " << (materialManager_ ? "created" : "null") << '\n';
    std::cout << "  geometry_manager  : " << (geometryManager_ ? "created" : "null") << '\n';
    std::cout << "  physics_manager   : " << (physicsManager_ ? "created" : "null") << '\n';
    std::cout << "  physics_mode      : " << (physicsManager_ ? (physicsManager_->HasReferenceList() ? "reference" : "manual") : "") << '\n';
    std::cout << "  physics_reference : " << (physicsManager_ ? physicsManager_->GetReferenceList() : "") << '\n';
    std::cout << "  physics_extra     : " << (physicsManager_ ? StringUtils::Join(physicsManager_->GetExtraModules(), ", ") : "") << '\n';
    std::cout << "  physics_em        : " << (physicsManager_ ? physicsManager_->GetEMOption() : "") << '\n';
    std::cout << "  physics_modules   : " << (physicsManager_ ? StringUtils::Join(physicsManager_->GetPhysicsModules(), ", ") : "") << '\n';
    std::cout << "  physics_cut       : " << (physicsManager_ ? physicsManager_->GetDefaultCut() : 0.0) << '\n';
    std::cout << "  physics_biasing   : " << (physicsManager_ ? BoolText(physicsManager_->IsBiasingPhysicsEnabled()) : "false") << '\n';
    std::cout << "  microelec         : " << (physicsManager_ ? BoolText(physicsManager_->IsMicroElecEnabled()) : "false") << '\n';
    std::cout << "  microelec_region  : " << (physicsManager_ ? physicsManager_->GetMicroElecRegion() : "") << '\n';
    std::cout << "  electron_capture  : " << (physicsManager_ ? BoolText(physicsManager_->IsElectronCaptureEnabled()) : "false") << '\n';
    std::cout << "  ecap_threshold    : " << (physicsManager_ ? physicsManager_->GetElectronCaptureThreshold() : 0.0) << '\n';
    std::cout << "  source_manager    : " << (sourceManager_ ? "created" : "null") << '\n';
    std::cout << "  source_configured : " << (sourceManager_ ? BoolText(sourceManager_->IsConfigured()) : "false") << '\n';
    std::cout << "  source_particle   : " << (sourceManager_ ? sourceManager_->GetParticleName() : "") << '\n';
    std::cout << "  source_energy     : " << (sourceManager_ ? sourceManager_->GetMonoEnergy() : 0.0) << '\n';
    std::cout << "  source_preset     : " << (sourceManager_ ? sourceManager_->GetPresetName() : "") << '\n';
    std::cout << "  biasing_manager   : " << (biasingManager_ ? "created" : "null") << '\n';
    std::cout << "  biasing_enabled   : " << (biasingManager_ ? BoolText(biasingManager_->IsEnabled()) : "false") << '\n';
    std::cout << "  biasing_process_rules: " << (biasingManager_ ? biasingManager_->GetEnabledXSProcessBiasRules().size() : 0) << '\n';
    std::cout << "  biasing_legacy_rules : " << (biasingManager_ ? biasingManager_->GetXSBiasRules().size() : 0) << '\n';
    std::cout << "  biasing_attached  : " << (biasingManager_ ? BoolText(biasingManager_->AreOperatorsAttached()) : "false") << '\n';
    std::cout << "  biasing_operators : " << (biasingManager_ ? biasingManager_->GetAttachedOperatorCount() : 0) << '\n';
    std::cout << "  scoring_manager   : " << (scoringManager_ ? "created" : "null") << '\n';
    std::cout << "  scoring_enabled   : " << (scoringManager_ ? BoolText(scoringManager_->IsEnabled()) : "false") << '\n';
    std::cout << "  scoring_hits      : " << (scoringManager_ ? BoolText(scoringManager_->IsHitOutputEnabled()) : "false") << '\n';
    std::cout << "  scoring_event_edep: " << (scoringManager_ ? BoolText(scoringManager_->IsEventEdepOutputEnabled()) : "false") << '\n';
    std::cout << "  scoring_edep      : " << (scoringManager_ ? BoolText(scoringManager_->IsEdepScoringEnabled()) : "false") << '\n';
    std::cout << "  scoring_let       : " << (scoringManager_ ? BoolText(scoringManager_->IsLETScoringEnabled()) : "false") << '\n';
    std::cout << "  scoring_dose      : " << (scoringManager_ ? BoolText(scoringManager_->IsDoseScoringEnabled()) : "false") << '\n';
    std::cout << "  scoring_fluence   : " << (scoringManager_ ? BoolText(scoringManager_->IsFluenceScoringEnabled()) : "false") << '\n';
    std::cout << "  scoring_auto      : " << (scoringManager_ ? BoolText(scoringManager_->IsAutoCreateDefaultScorersEnabled()) : "false") << '\n';
    std::cout << "  scoring_scorers   : " << (scoringManager_ ? scoringManager_->GetScorerNames().size() : 0) << '\n';
    std::cout << "  geometry_template : " << geometryTemplate_ << '\n';
    std::cout << "  geometry_config   : " << geometryConfigFile_ << '\n';
    std::cout << "  config_loaded     : " << BoolText(configLoaded_) << '\n';
    std::cout << "  configured        : " << BoolText(configured_) << '\n';
    std::cout << "  initialized       : " << BoolText(initialized_) << '\n';
}

bool SimulationManager::IsConfigured() const
{
    return configured_;
}

const std::string& SimulationManager::GetMaterialsConfigFile() const
{
    return materialsFile_;
}

bool SimulationManager::IsInitialized() const
{
    return initialized_;
}

std::unique_ptr<DetectorConstruction> SimulationManager::CreateDetectorConstruction() const
{
    if (!geometryManager_) {
        throw std::runtime_error("SimulationManager::CreateDetectorConstruction failed: GeometryManager is null");
    }
    auto detector = std::make_unique<DetectorConstruction>(geometryManager_.get());
    detector->SetFieldConfig(&fieldConfig_);
    detector->SetSensitiveDetectorFactory(CreateSensitiveDetectorFactory());
    detector->SetGeometryPostBuildCallback(CreateGeometryPostBuildCallback());
    detector->SetThreadBiasingCallback([this](const GeometryRegistry& registry) {
        if (biasingManager_) biasingManager_->ConstructThreadOperators(registry);
    });
    if (parallelWorldConfig_ && parallelWorldConfig_->enabled()) {
        detector->SetParallelWorldOutputManager(outputManager_.get());
        detector->SetParallelWorldConfig(parallelWorldConfig_);
    }
    return detector;
}

std::unique_ptr<G4VModularPhysicsList> SimulationManager::CreatePhysicsList() const
{
    if (!physicsManager_) {
        throw std::runtime_error("SimulationManager::CreatePhysicsList failed: PhysicsManager is null");
    }

    if (physicsManager_->HasReferenceList()) {
        auto list = PhysicsFactory::CreateReferencePhysicsList(physicsManager_->GetReferenceList());
        PhysicsFactory::RegisterExtraModules(
            list.get(),
            FilterOutGenericBiasingModules(physicsManager_->GetExtraModules()));

        if (physicsManager_->IsMicroElecEnabled() ||
            physicsManager_->HasExtraModule("microelec")) {
            auto microElec = PhysicsFactory::CreateMicroElecPhysics(*physicsManager_);
            list->RegisterPhysics(microElec.release());
        }

        const auto* biasing = physicsManager_->GetBiasingManager();
        const bool needsBiasing = physicsManager_->IsBiasingPhysicsEnabled() ||
            (biasing && biasing->IsEnabled());
        if (needsBiasing) {
            const auto particleProcesses = BuildBiasParticleProcessMap(biasing);
            if (particleProcesses.empty()) {
                std::cout << "[SimulationManager] Biasing physics requested but no biased particles are configured; generic biasing physics is not registered." << '\n';
            } else {
                PhysicsFactory::RegisterGenericBiasingPhysics(list.get(), particleProcesses);
            }
        }

        if (parallelWorldConfig_ && parallelWorldConfig_->enabled()) {
            list->RegisterPhysics(new G4ParallelWorldPhysics(parallelWorldConfig_->name(), false));
        }

        PhysicsFactory::ApplyRegionAndDecaySettings(list.get(), *physicsManager_);
        PhysicsFactory::ApplyCuts(
            list.get(),
            physicsManager_->GetDefaultCut(),
            physicsManager_->GetParticleCuts());
        return list;
    }

    auto list = std::make_unique<PhysicsList>(physicsManager_.get());
    list->ConfigureNow();
    PhysicsFactory::ApplyRegionAndDecaySettings(list.get(), *physicsManager_);
    if (parallelWorldConfig_ && parallelWorldConfig_->enabled()) {
        list->RegisterPhysics(new G4ParallelWorldPhysics(parallelWorldConfig_->name(), false));
    }
    return list;
}

std::unique_ptr<PrimaryGeneratorAction> SimulationManager::CreatePrimaryGeneratorAction() const
{
    if (!sourceManager_) {
        throw std::runtime_error("SimulationManager::CreatePrimaryGeneratorAction failed: SourceManager is null");
    }
    return std::make_unique<PrimaryGeneratorAction>(sourceManager_.get());
}

std::unique_ptr<ActionInitialization> SimulationManager::CreateActionInitialization() const
{
    if (!sourceManager_) {
        throw std::runtime_error("SimulationManager::CreateActionInitialization failed: SourceManager is null");
    }
    auto actions = std::make_unique<ActionInitialization>(
        sourceManager_.get(),
        scoringManager_.get(),
        outputManager_.get(),
        biasingManager_.get());
    actions->SetEffectiveCallbacks(
        [this](int run, ScoringManager* scoring, OutputManager* output) { CaptureEffectiveRunBegin(run, scoring, output); },
        [this](int run, ScoringManager* scoring, OutputManager* output) { CaptureEffectiveThreadFinalization(run, scoring, output); });
    return actions;
}

std::function<G4VSensitiveDetector*(const std::string&)> SimulationManager::CreateSensitiveDetectorFactory() const
{
    if (!scoringManager_) {
        throw std::runtime_error("SimulationManager::CreateSensitiveDetectorFactory failed: ScoringManager is null");
    }

    return [this](const std::string& name) -> G4VSensitiveDetector* {
        ScoringManager* threadScoringManager = AIHL::GetCurrentThreadScoringManager();
        return new SensitiveDetector(
            name,
            threadScoringManager ? threadScoringManager : scoringManager_.get());
    };
}

std::function<void(const GeometryRegistry&)> SimulationManager::CreateGeometryPostBuildCallback() const
{
    return [this](const GeometryRegistry& registry) {
        if (biasingManager_ && biasingManager_->IsEnabled()) {
            biasingManager_->AttachOperators(registry);
        }
    };
}

void SimulationManager::InitializeSourceAfterPhysicsListRegistered()
{
    if (sourceManager_) {
        sourceManager_->InitializeAfterPhysicsListRegistered();
    }
}

const parallel_world::ParallelWorldConfig* SimulationManager::GetParallelWorldConfig() const
{
    return parallelWorldConfig_.get();
}

void SimulationManager::RefreshParallelWorldForCurrentGeometry()
{
    if (!parallelWorldConfig_ || !parallelWorldConfig_->enabled()) return;
    parallelWorldConfig_->RebindToCurrentGeometry(*geometryManager_, *materialManager_);
    RefreshEffectiveConfig();
}

void SimulationManager::ValidateParallelWorldDependencies()
{
    if (!parallelWorldConfig_ || !parallelWorldConfig_->enabled()) return;
    EnsureOutputManager();
    // Contract E: a batch macro, csh session or the controlled session can change
    // the dependent modules after Configure(). Re-check the live dependency state
    // before the kernel is initialized and before BeamOn, not only at Configure time.
    const G4ScoringManager* scoringManager = G4ScoringManager::GetScoringManager();
    const bool nativeMesh = scoringManager != nullptr && scoringManager->GetNumberOfMesh() > 0;
    const auto dependencyProblems = parallelWorldConfig_->ValidateDependencies(
        *scoringManager_, *outputManager_, biasingManager_ && biasingManager_->IsEnabled(),
        !fieldConfig_.Empty(), nativeMesh);
    if (!dependencyProblems.empty()) {
        outputManager_->RecordOutputFailure("parallel_world_config", dependencyProblems.front());
        throw std::runtime_error("[parallel_world] " + dependencyProblems.front());
    }
}

void SimulationManager::ValidateParallelWorldForRun()
{
    if (!parallelWorldConfig_ || !parallelWorldConfig_->enabled()) return;
    ValidateParallelWorldDependencies();
    const auto fail = [this](const std::string& stage, const std::string& message) {
        outputManager_->RecordOutputFailure(stage, message);
        throw std::runtime_error("[parallel_world] " + message);
    };
    // A PreInit /AIHL/geometry/loadConfig can replace the mass-world tree after
    // Configure(). Bind the material proof to the tree the kernel has just
    // built before accepting the run; an unrepeatable proof degrades to
    // `unknown` and the effective-configuration view is refreshed in place.
    try {
        RefreshParallelWorldForCurrentGeometry();
    } catch (const std::exception& error) {
        fail("parallel_world_config", error.what());
    }
    auto* runManager = G4RunManager::GetRunManager();
    if (runManager == nullptr) fail("parallel_world_geometry", "no G4RunManager is active");
    const auto* detector = dynamic_cast<const DetectorConstruction*>(runManager->GetUserDetectorConstruction());
    if (detector == nullptr) {
        fail("parallel_world_geometry", "the user detector construction is not a DetectorConstruction");
    }
    auto* world = detector->GetScoringParallelWorld();
    if (world == nullptr) {
        fail("parallel_world_geometry",
             "the parallel scoring world was not registered with Geant4; /run/initialize did not build it");
    }
    G4VPhysicalVolume* ghost = world->GhostWorld();
    if (ghost == nullptr || ghost->GetLogicalVolume() == nullptr ||
        ghost->GetLogicalVolume()->GetSolid() == nullptr) {
        fail("parallel_world_geometry", "the ghost world has no solid");
    }
    const G4VSolid* worldSolid = ghost->GetLogicalVolume()->GetSolid();

    // Internal navigation envelopes (one per declared grid): the envelope is not
    // a scoring volume, but the kernel must have built it as a real daughter of
    // the ghost world and every grid cell must be its direct daughter at exactly
    // the declared global centre. Otherwise the restored owner would come from
    // an invented hierarchy.
    {
        const auto& envelopes = parallelWorldConfig_->envelopes();
        const auto& envelopePlacements = world->EnvelopePlacements();
        if (envelopePlacements.size() != envelopes.size()) {
            fail("parallel_world_geometry",
                 "the kernel built " + std::to_string(envelopePlacements.size()) +
                     " navigation envelopes but the configuration declares " +
                     std::to_string(envelopes.size()));
        }
        for (std::size_t index = 0; index < envelopes.size(); ++index) {
            const auto& envelope = envelopes[index];
            G4VPhysicalVolume* placement = envelopePlacements[index];
            if (placement == nullptr || placement->GetLogicalVolume() == nullptr ||
                placement->GetLogicalVolume()->GetSolid() == nullptr) {
                fail("parallel_world_geometry", "navigation envelope '" + envelope.name + "' has no solid");
            }
            if (placement->GetMotherLogical() != ghost->GetLogicalVolume()) {
                fail("parallel_world_geometry",
                     "navigation envelope '" + envelope.name + "' is not a direct daughter of the ghost world");
            }
            if (placement->GetCopyNo() != 0) {
                fail("parallel_world_geometry", "navigation envelope '" + envelope.name + "' has a non-zero copy number");
            }
            if (!placement->GetObjectRotationValue().isIdentity()) {
                fail("parallel_world_geometry", "navigation envelope '" + envelope.name + "' is rotated");
            }
            auto* envelopeBox = dynamic_cast<G4Box*>(placement->GetLogicalVolume()->GetSolid());
            if (envelopeBox == nullptr) {
                fail("parallel_world_geometry", "navigation envelope '" + envelope.name + "' is not a box");
            }
            const double envelopeSizes[3] = {2.0 * envelopeBox->GetXHalfLength() / mm,
                                             2.0 * envelopeBox->GetYHalfLength() / mm,
                                             2.0 * envelopeBox->GetZHalfLength() / mm};
            for (int axis = 0; axis < 3; ++axis) {
                const double expected = envelope.sizeMm[axis];
                const double scale = std::max(std::fabs(expected), 1.0);
                if (std::fabs(envelopeSizes[axis] - expected) / scale > 1e-12) {
                    std::ostringstream message;
                    message << "navigation envelope '" << envelope.name << "' has size "
                            << envelopeSizes[axis] << " mm on axis " << axis
                            << " but the grid declares " << expected << " mm";
                    fail("parallel_world_geometry", message.str());
                }
            }
            for (const std::size_t cellIndex : envelope.volumeIndices) {
                if (cellIndex >= parallelWorldConfig_->volumes().size()) {
                    fail("parallel_world_geometry",
                         "navigation envelope '" + envelope.name + "' references an unknown cell index");
                }
                const auto& cell = parallelWorldConfig_->volumes()[cellIndex];
                G4VPhysicalVolume* cellPlacement = world->FindPlacement(cell.name);
                if (cellPlacement == nullptr) {
                    fail("parallel_world_geometry",
                         "grid cell '" + cell.name + "' does not exist in the kernel geometry");
                }
                if (cellPlacement->GetMotherLogical() != placement->GetLogicalVolume()) {
                    fail("parallel_world_geometry",
                         "grid cell '" + cell.name + "' is not a direct daughter of its navigation envelope '" +
                             envelope.name + "'");
                }
                if (cellPlacement->GetCopyNo() != 0) {
                    fail("parallel_world_geometry", "grid cell '" + cell.name + "' has a non-zero copy number");
                }
                if (!cellPlacement->GetObjectRotationValue().isIdentity()) {
                    fail("parallel_world_geometry", "grid cell '" + cell.name + "' is rotated");
                }
                const G4ThreeVector composed =
                    placement->GetObjectTranslation() + cellPlacement->GetObjectTranslation();
                for (int axis = 0; axis < 3; ++axis) {
                    const double actualMm =
                        (axis == 0 ? composed.x() : (axis == 1 ? composed.y() : composed.z())) / mm;
                    const double expected = cell.centreMm[axis];
                    const double scale = std::max(std::fabs(expected), 1.0);
                    if (std::fabs(actualMm - expected) / scale > 1e-12) {
                        std::ostringstream message;
                        message << "grid cell '" << cell.name << "' has global centre " << actualMm
                                << " mm on axis " << axis << " but the grid declares " << expected << " mm";
                        fail("parallel_world_geometry", message.str());
                    }
                }
            }
        }
    }
    parallel_world::KernelObservation observation;
    observation.worldName = parallelWorldConfig_->name();
    double totalMassKg = 0.0;
    double maxRelativeDeviation = 0.0;
    for (const auto& spec : parallelWorldConfig_->volumes()) {
        G4LogicalVolume* logical = world->FindLogicalVolume(spec.name);
        if (logical == nullptr) {
            fail("parallel_world_geometry",
                 "ghost volume '" + spec.name + "' does not exist in the kernel geometry");
        }
        auto* box = dynamic_cast<G4Box*>(logical->GetSolid());
        if (box == nullptr) {
            fail("parallel_world_geometry", "ghost volume '" + spec.name + "' is not a box");
        }
        const double actualSizes[3] = {2.0 * box->GetXHalfLength() / mm,
                                       2.0 * box->GetYHalfLength() / mm,
                                       2.0 * box->GetZHalfLength() / mm};
        for (int axis = 0; axis < 3; ++axis) {
            const double expected = spec.sizeMm[axis];
            const double scale = std::max(expected, 1.0);
            if (std::fabs(actualSizes[axis] - expected) / scale > 1e-12) {
                std::ostringstream message;
                message << "ghost volume '" << spec.name << "' has size " << actualSizes[axis]
                        << " mm on axis " << axis << " but the configuration declares " << expected << " mm";
                fail("parallel_world_geometry", message.str());
            }
        }
        const double actualMassKg = logical->GetMass(true, false) / kg;
        const double reference = spec.referenceMassKg;
        if (!(reference > 0.0) || !std::isfinite(actualMassKg)) {
            fail("parallel_world_geometry", "ghost volume '" + spec.name + "' has no usable reference mass");
        }
        const double relative = std::fabs(actualMassKg - reference) / reference;
        if (relative > 1e-12) {
            std::ostringstream message;
            message << "ghost volume '" << spec.name << "' mass " << actualMassKg
                    << " kg differs from the configured reference " << reference << " kg (relative "
                    << relative << ")";
            fail("parallel_world_geometry", message.str());
        }
        maxRelativeDeviation = std::max(maxRelativeDeviation, relative);
        totalMassKg += actualMassKg;
        ++observation.volumeCount;
        for (int sx = -1; sx <= 1; ++sx) {
            for (int sy = -1; sy <= 1; ++sy) {
                for (int sz = -1; sz <= 1; ++sz) {
                    const G4ThreeVector point(
                        (spec.centreMm[0] + 0.5 * sx * spec.sizeMm[0]) * mm,
                        (spec.centreMm[1] + 0.5 * sy * spec.sizeMm[1]) * mm,
                        (spec.centreMm[2] + 0.5 * sz * spec.sizeMm[2]) * mm);
                    if (worldSolid->Inside(point) == kOutside) {
                        fail("parallel_world_geometry", "ghost volume '" + spec.name +
                             "' is not fully inside the ghost world solid");
                    }
                }
            }
        }
    }
    observation.totalMassKg = totalMassKg;
    observation.maxRelativeMassDeviation = maxRelativeDeviation;
    parallelWorldConfig_->RecordKernelConstruction(-1, observation,
                                                   parallelWorldConfig_->geometrySha256());
}

void SimulationManager::ValidateBiasingProcessTargets()
{
    if (biasingManager_ && biasingManager_->IsEnabled()) {
        biasingManager_->ValidateActiveProcessRules();
    }
}

void SimulationManager::ValidateScoringVolumeConfigsBeforeRun()
{
    // Legacy LET and phase-space selectors also need the initialized particle
    // table. Absence of H2 filters/spectra must not bypass their pre-run check.
    if (!scoringManager_) {
        return;
    }
    try {
        scoringManager_->ValidateVolumeConfigsForRun();
    } catch (const std::exception& error) {
        const std::string message = error.what();
        const bool particleFailure =
            message.find("unknown Geant4 particle") != std::string::npos;
        if (outputManager_) {
            outputManager_->RecordOutputFailure(
                particleFailure ? "scoring_filter_particle" : "scoring_volume_config",
                message, 0);
        }
        throw;
    }
}

ConfigManager* SimulationManager::GetConfigManager()
{
    return configManager_.get();
}

OutputManager* SimulationManager::GetOutputManager()
{
    return outputManager_.get();
}

const ConfigManager* SimulationManager::GetConfigManager() const
{
    return configManager_.get();
}

const OutputManager* SimulationManager::GetOutputManager() const
{
    return outputManager_.get();
}

MaterialManager* SimulationManager::GetMaterialManager()
{
    return materialManager_.get();
}

GeometryManager* SimulationManager::GetGeometryManager()
{
    return geometryManager_.get();
}

PhysicsManager* SimulationManager::GetPhysicsManager()
{
    return physicsManager_.get();
}

void SimulationManager::EnableInteractivePhysicsGuard()
{
    if (physicsMessenger_) physicsMessenger_->SetInteractiveSessionMode(true);
}

std::size_t SimulationManager::GetInteractivePhysicsFailureCount() const
{
    return physicsMessenger_ ? physicsMessenger_->GetInteractiveCommandFailureCount() : 0;
}

std::string SimulationManager::GetLastInteractivePhysicsFailure() const
{
    return physicsMessenger_ ? physicsMessenger_->GetLastInteractiveCommandFailure() : "";
}

SourceManager* SimulationManager::GetSourceManager()
{
    return sourceManager_.get();
}

BiasingManager* SimulationManager::GetBiasingManager()
{
    return biasingManager_.get();
}

ScoringManager* SimulationManager::GetScoringManager()
{
    return scoringManager_.get();
}

const MaterialManager* SimulationManager::GetMaterialManager() const
{
    return materialManager_.get();
}

const GeometryManager* SimulationManager::GetGeometryManager() const
{
    return geometryManager_.get();
}

const PhysicsManager* SimulationManager::GetPhysicsManager() const
{
    return physicsManager_.get();
}

const SourceManager* SimulationManager::GetSourceManager() const
{
    return sourceManager_.get();
}

const BiasingManager* SimulationManager::GetBiasingManager() const
{
    return biasingManager_.get();
}

const ScoringManager* SimulationManager::GetScoringManager() const
{
    return scoringManager_.get();
}

void SimulationManager::EnsureConfigManager()
{
    if (!configManager_) configManager_ = std::make_unique<ConfigManager>();
}

void SimulationManager::EnsureOutputManager()
{
    if (!outputManager_) {
        outputManager_ = std::make_unique<OutputManager>();
        // Format selection only observes final scoring flags. The selector is
        // shared by workers, whose configuration is frozen before Initialize.
        outputManager_->SetAutoFormatSelector([this]() {
            return scoringManager_ && scoringManager_->IsEnabled() &&
                (scoringManager_->IsHitOutputEnabled() || scoringManager_->IsEventEdepOutputEnabled());
        });
    }
}

void SimulationManager::EnsureMaterialManager()
{
    if (!materialManager_) materialManager_ = std::make_unique<MaterialManager>();
}

void SimulationManager::EnsureGeometryManager()
{
    if (!geometryManager_) geometryManager_ = std::make_unique<GeometryManager>();
}

void SimulationManager::EnsurePhysicsManager()
{
    if (!physicsManager_) physicsManager_ = std::make_unique<PhysicsManager>();
}

void SimulationManager::EnsureSourceManager()
{
    if (!sourceManager_) sourceManager_ = std::make_unique<SourceManager>();
}

void SimulationManager::EnsureBiasingManager()
{
    if (!biasingManager_) biasingManager_ = std::make_unique<BiasingManager>();
}

void SimulationManager::EnsureScoringManager()
{
    if (!scoringManager_) scoringManager_ = std::make_unique<ScoringManager>();
}

void SimulationManager::ConfigureOutputManager()
{
    EnsureOutputManager();
    outputManager_->SetOutputDir(context_.GetOutputDir());
    outputManager_->SetThreadId(0);
    outputManager_->EnableThreadSuffix(true);
    outputManager_->SetOutputDirLocked(commandLineOverrides_.outputDir.has_value());
    if (scoringManager_) scoringManager_->SetOutputManager(outputManager_.get());
}

void SimulationManager::ApplyCommandLineOverrides()
{
    if (commandLineOverrides_.mainConfig) context_.SetMainConfig(*commandLineOverrides_.mainConfig);
    if (commandLineOverrides_.outputDir) {
        context_.SetOutputDir(*commandLineOverrides_.outputDir);
        outputManager_->SetOutputDir(*commandLineOverrides_.outputDir);
    }
    if (commandLineOverrides_.runName) context_.SetRunName(*commandLineOverrides_.runName);
    if (commandLineOverrides_.macroFile) context_.SetMacroFile(*commandLineOverrides_.macroFile);
    if (commandLineOverrides_.numThreads) context_.SetNumThreads(*commandLineOverrides_.numThreads);
    if (commandLineOverrides_.seed) context_.SetSeed(*commandLineOverrides_.seed);
    if (commandLineOverrides_.interactive) context_.SetInteractive(*commandLineOverrides_.interactive);
    if (commandLineOverrides_.dryRun) context_.SetDryRun(*commandLineOverrides_.dryRun);
    if (commandLineOverrides_.checkOverlaps) {
        context_.SetCheckOverlaps(*commandLineOverrides_.checkOverlaps);
        geometryManager_->SetCheckOverlaps(*commandLineOverrides_.checkOverlaps);
        geometryManager_->SetCheckOverlapsLocked(true);
    }
}

void SimulationManager::WarnIgnoredCommandLineOverride(const std::string& name) const
{
    std::cerr << "[SimulationManager] Ignoring runtime change to " << name
              << " because an explicit CLI option has higher priority.\n";
}

void SimulationManager::WriteBaseRunSummary()
{
    EnsureOutputManager();
    RunSummary& summary = outputManager_->GetRunSummary();
    summary.Set("run_summary_schema_version", 1);
    summary.Set("run_name", context_.GetRunName());
    summary.Set("output_csv_schema_version", 3);
    summary.SetPath("main_config", context_.GetMainConfig());
    summary.SetPath("output_dir", context_.GetOutputDir());
    summary.Set("num_threads", context_.GetNumThreads());
    summary.Set("seed", context_.HasSeed() ? std::to_string(context_.GetSeed()) : "unset");
    summary.SetPath("macro_file", context_.GetMacroFile());
    summary.SetPath("planned_output_dir", context_.GetOutputDir());
    summary.Set("planned_num_threads", context_.GetNumThreads());
    summary.Set("planned_seed", context_.HasSeed() ? std::to_string(context_.GetSeed()) : "unset");
    summary.SetPath("planned_macro_file", context_.GetMacroFile());
    summary.SetBool("interactive", context_.IsInteractive());
    summary.Set("verbose_level", context_.GetVerboseLevel());
    summary.SetBool("check_overlaps", context_.GetCheckOverlaps());
    summary.SetBool("dry_run", context_.IsDryRun());
    if (!summary.Has("config_warning_count")) summary.Set("config_warning_count", 0);
    if (!summary.Has("config_duplicate_count")) summary.Set("config_duplicate_count", 0);
    if (!summary.Has("geometry_config_warning_count")) summary.Set("geometry_config_warning_count", 0);
    summary.SetPath("materials_file", materialsFile_);
    summary.Set("geometry_template", geometryTemplate_);
    summary.SetPath("geometry_config", geometryConfigFile_);
    summary.Set("physics_mode", physicsManager_ ? (physicsManager_->HasReferenceList() ? "reference" : "manual") : "");
    summary.Set("physics_reference", physicsManager_ ? physicsManager_->GetReferenceList() : "");
    summary.Set("physics_extra_modules", physicsManager_ ? StringUtils::Join(physicsManager_->GetExtraModules(), ",") : "");
    summary.Set("physics_em", physicsManager_ ? physicsManager_->GetEMOption() : "");
    summary.Set("physics_modules", physicsManager_ ? StringUtils::Join(physicsManager_->GetPhysicsModules(), ",") : "");
    summary.Set("physics_default_cut", physicsManager_ ? physicsManager_->GetDefaultCut() : 0.0);
    summary.SetBool("physics_biasing_enabled", physicsManager_ ? physicsManager_->IsBiasingPhysicsEnabled() : false);
    summary.SetBool("physics_microelec_enabled", physicsManager_ ? physicsManager_->IsMicroElecEnabled() : false);
    summary.Set("physics_microelec_region", physicsManager_ ? physicsManager_->GetMicroElecRegion() : "");
    summary.SetBool("physics_electron_capture_enabled", physicsManager_ ? physicsManager_->IsElectronCaptureEnabled() : false);
    summary.Set("physics_electron_capture_threshold", physicsManager_ ? physicsManager_->GetElectronCaptureThreshold() : 0.0);
    summary.SetBool("source_configured", sourceManager_ ? sourceManager_->IsConfigured() : false);
    summary.Set("source_particle", sourceManager_ ? sourceManager_->GetParticleName() : "");
    summary.Set("source_energy", sourceManager_ ? sourceManager_->GetMonoEnergy() : 0.0);
    summary.Set("source_preset", sourceManager_ ? sourceManager_->GetPresetName() : "");
    if (sourceManager_) {
        const auto& sources = sourceManager_->GetSources();
        summary.Set("field_count", static_cast<int>(fieldConfig_.GetFields().size()));
        for (std::size_t index = 0; index < fieldConfig_.GetFields().size(); ++index) {
            summary.Set("field_" + std::to_string(index) + "_spec", fieldConfig_.GetFields()[index].Describe());
        }
        summary.Set("source_count", static_cast<int>(sources.size()));
        summary.SetBool("source_phase_space", sourceManager_->UsesPhaseSpace());
        if (sourceManager_->UsesPhaseSpace()) {
            std::string files;
            for (const auto& file : sourceManager_->GetPhaseSpaceFiles()) files += (files.empty() ? "" : ",") + file;
            summary.Set("source_phase_space_files", files);
            summary.Set("source_phase_space_histories", static_cast<std::int64_t>(sourceManager_->GetPhaseSpaceHistoryCount()));
            summary.Set("source_phase_space_particles", static_cast<std::int64_t>(sourceManager_->GetPhaseSpaceParticleCount()));
            summary.SetBool("source_phase_space_recycle", sourceManager_->IsPhaseSpaceRecycled());
        }
        for (std::size_t index = 0; index < sources.size(); ++index) {
            summary.Set("source_" + std::to_string(index) + "_spec", sources[index].Describe());
        }
    }
    summary.SetBool("biasing_enabled", biasingManager_ ? biasingManager_->IsEnabled() : false);
    summary.Set("biasing_xs_rule_count", static_cast<int>(biasingManager_ ? biasingManager_->GetEnabledXSProcessBiasRules().size() : 0));
    summary.Set("biasing_legacy_xs_rule_count", static_cast<int>(biasingManager_ ? biasingManager_->GetXSBiasRules().size() : 0));
    summary.SetBool("biasing_operators_attached", biasingManager_ ? biasingManager_->AreOperatorsAttached() : false);
    summary.Set("biasing_attached_operator_count", static_cast<int>(biasingManager_ ? biasingManager_->GetAttachedOperatorCount() : 0));
    summary.Set("biasing_matched_process_rule_count", static_cast<int>(biasingManager_ ? biasingManager_->GetMatchedProcessRuleCount() : 0));
    summary.Set("biasing_process_match_status", !biasingManager_ || !biasingManager_->IsEnabled() ? "not_applicable" :
                (biasingManager_->GetMatchedProcessRuleCount() > 0 ? "validated" : "not_validated"));
    summary.Set("biasing_effect_observed", "unknown");
    summary.SetBool("scoring_enabled", scoringManager_ ? scoringManager_->IsEnabled() : false);
    summary.SetBool("scoring_hits_enabled", scoringManager_ ? scoringManager_->IsHitOutputEnabled() : false);
    summary.SetBool("scoring_event_edep_enabled", scoringManager_ ? scoringManager_->IsEventEdepOutputEnabled() : false);
    summary.SetBool("scoring_edep_enabled", scoringManager_ ? scoringManager_->IsEdepScoringEnabled() : false);
    summary.SetBool("scoring_let_enabled", scoringManager_ ? scoringManager_->IsLETScoringEnabled() : false);
    {
        std::string particles;
        if (scoringManager_) {
            for (const auto& name : scoringManager_->GetLETParticles()) particles += (particles.empty() ? "" : ",") + name;
        }
        summary.Set("scoring_let_particles", particles.empty() ? "all_charged" : particles);
    }
    summary.SetBool("scoring_dose_enabled", scoringManager_ ? scoringManager_->IsDoseScoringEnabled() : false);
    summary.SetBool("scoring_fluence_enabled", scoringManager_ ? scoringManager_->IsFluenceScoringEnabled() : false);
    summary.SetBool("scoring_auto_create_default_scorers", scoringManager_ ? scoringManager_->IsAutoCreateDefaultScorersEnabled() : false);
    summary.Set("scoring_scorer_count", static_cast<int>(scoringManager_ ? scoringManager_->GetScorerNames().size() : 0));
    summary.SetBool("initialized", initialized_);
    summary.AddMessage("Core initialization completed");
}

void SimulationManager::WriteFinalConfigSnapshot(const std::string& macroStatus)
{
    RunSummary& summary = outputManager_->GetRunSummary();
    summary.Set("effective_config_snapshot_version", 1);
    summary.Set("effective_config_snapshot_stage", "finalization");
    summary.Set("effective_config_snapshot_scope", "manager_state_subset");
    summary.Set("effective_config_macro_execution_status", macroStatus);
    summary.Set("effective_config_source_coverage", "startup_geometry_source_and_physics_reference");
    summary.Set("effective_config_geant4_applied", "unknown");
    for (const auto& entry : effectiveValueOrigins_) {
        const std::string prefix = "effective_" + entry.first + "_origin_";
        summary.Set(prefix + "kind", entry.second.kind);
        summary.SetPath(prefix + "file", entry.second.file.empty() ? "not_applicable" : entry.second.file);
        summary.Set(prefix + "line", entry.second.line);
        summary.Set(prefix + "section", entry.second.section.empty() ? "not_applicable" : entry.second.section);
        summary.Set(prefix + "key", entry.second.key.empty() ? "not_applicable" : entry.second.key);
    }

    // Read the live owners rather than the pre-macro planned_* fields.
    summary.SetPath("effective_output_dir", outputManager_->GetOutputDir());
    summary.Set("effective_run_name", context_.GetRunName());
    summary.Set("effective_requested_threads", context_.GetNumThreads());
    summary.Set("effective_configured_seed",
                context_.HasSeed() ? std::to_string(context_.GetSeed()) : "unset");
    summary.SetBool("effective_check_overlaps",
                    geometryManager_ ? geometryManager_->GetCheckOverlaps() : context_.GetCheckOverlaps());
    summary.SetPath("effective_macro_file", context_.GetMacroFile());
    summary.Set("effective_geometry_template",
                geometryManager_ ? geometryManager_->GetTemplateName() : "unknown");
    summary.SetPath("effective_geometry_config",
                    geometryManager_ ? geometryManager_->GetGeometryConfigFile() : "unknown");
    summary.Set("effective_geometry_default_world_material",
                geometryManager_ ? geometryManager_->GetDefaultWorldMaterial() : "unknown");
    // Material loads are additive and macro commands can also edit definitions.
    // Only name a single effective file when it is the sole known file source.
    if (materialManager_) {
        const auto& files = materialManager_->GetLoadedConfigFiles();
        summary.Set("effective_materials_loaded_file_count", static_cast<int>(files.size()));
        for (std::size_t index = 0; index < files.size(); ++index) {
            summary.SetPath("effective_materials_loaded_file_" + std::to_string(index), files[index]);
        }
        std::string sourceStatus = "no_file_loaded";
        if (materialManager_->HasIncompleteConfigLoad()) sourceStatus = "incomplete_load";
        else if (materialManager_->HasNonFileConfigMutations()) sourceStatus = "non_file_mutation";
        else if (files.size() > 1) sourceStatus = "multiple_files";
        else if (files.size() == 1) sourceStatus = "single_file";
        summary.Set("effective_materials_source_status", sourceStatus);
        summary.SetPath("effective_materials_file",
                        sourceStatus == "single_file" ? files.front() : "unknown");
    } else {
        summary.Set("effective_materials_loaded_file_count", 0);
        summary.Set("effective_materials_source_status", "manager_unavailable");
        summary.SetPath("effective_materials_file", "unknown");
    }
    summary.Set("effective_physics_reference",
                physicsManager_ ? physicsManager_->GetReferenceList() : "unknown");
    summary.Set("effective_source_particle",
                sourceManager_ ? sourceManager_->GetParticleName() : "unknown");
    summary.Set("effective_source_energy_MeV",
                sourceManager_ ? sourceManager_->GetMonoEnergy() / CLHEP::MeV : 0.0);
    summary.SetBool("effective_scoring_enabled", scoringManager_ && scoringManager_->IsEnabled());
    // The legacy scoring_* keys were captured before batch macro execution.
    // Preserve them as an initialization snapshot, and expose the final
    // manager setting separately (without asserting Geant4 kernel application).
    summary.SetBool("effective_scoring_event_edep_enabled",
                    scoringManager_ && scoringManager_->IsEventEdepOutputEnabled());
    summary.SetBool("effective_biasing_enabled", biasingManager_ && biasingManager_->IsEnabled());
}
