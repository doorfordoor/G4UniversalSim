#include "Core/SimulationManager.hh"

#include "Actions/ActionInitialization.hh"
#include "Config/ConfigManager.hh"
#include "Core/AppMessenger.hh"
#include "Detector/DetectorConstruction.hh"
#include "Geometry/GeometryManager.hh"
#include "Geometry/GeometryMessenger.hh"
#include "Hits/SensitiveDetector.hh"
#include "Materials/MaterialManager.hh"
#include "Materials/MaterialMessenger.hh"
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
#include "Scoring/ScoringManager.hh"
#include "Scoring/ThreadLocalScoringContext.hh"
#include "Utils/FileUtils.hh"
#include "Utils/StringUtils.hh"

#include "G4RunManager.hh"
#include "G4StateManager.hh"
#include "G4SystemOfUnits.hh"
#ifdef G4MULTITHREADED
#include "G4MTRunManager.hh"
#endif
#include "Randomize.hh"

#include <iostream>
#include <algorithm>
#include <chrono>
#include <cstdlib>
#include <ctime>
#include <map>
#include <sstream>
#include <stdexcept>
#include <vector>

namespace {

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

bool HasNonEmptyKey(const ConfigManager& config, const std::string& section, const std::string& key)
{
    return config.HasKey(section, key) && !StringUtils::Trim(config.GetString(section, key, "")).empty();
}

bool HasNonEmptyKeyCompat(const ConfigManager& config,
                          const std::string& section,
                          const std::vector<std::string>& keys)
{
    for (const auto& key : keys) {
        if (HasNonEmptyKey(config, section, key)) return true;
    }
    return false;
}

std::string GetStringCompat(const ConfigManager& config,
                            const std::string& section,
                            const std::vector<std::string>& keys,
                            const std::string& defaultValue = "")
{
    for (const auto& key : keys) {
        if (HasNonEmptyKey(config, section, key)) {
            return config.GetString(section, key);
        }
    }
    return defaultValue;
}

bool HasKeyCompat(const ConfigManager& config,
                  const std::string& section,
                  const std::vector<std::string>& keys)
{
    for (const auto& key : keys) {
        if (config.HasKey(section, key)) return true;
    }
    return false;
}

int GetIntCompat(const ConfigManager& config,
                 const std::string& section,
                 const std::vector<std::string>& keys,
                 int defaultValue)
{
    for (const auto& key : keys) {
        if (config.HasKey(section, key)) return config.GetInt(section, key);
    }
    return defaultValue;
}

bool GetBoolCompat(const ConfigManager& config,
                   const std::string& section,
                   const std::vector<std::string>& keys,
                   bool defaultValue)
{
    for (const auto& key : keys) {
        if (config.HasKey(section, key)) return config.GetBool(section, key);
    }
    return defaultValue;
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
                                                       int line)
{
    // The command is recorded only after ApplyCommand and the corresponding
    // Messenger failure checks succeed. Never attribute an attempted command.
    const std::string token = FirstCommandToken(command);
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
            throw std::runtime_error("Injected main-thread final flush failure");
        }
    });
    finalizeOutput("final_close", [this, &injectedFault]() {
        outputManager_->Close();
        if (injectedFault == "final_close_master") {
            throw std::runtime_error("Injected main-thread final close failure");
        }
    });

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
    summary.Set("biasing_matched_process_rule_count", static_cast<int>(biasingManager_ ? biasingManager_->GetMatchedProcessRuleCount() : 0));
    summary.Set("biasing_process_match_status", !biasingManager_ || !biasingManager_->IsEnabled() ? "not_applicable" :
                (biasingManager_->GetMatchedProcessRuleCount() > 0 ? "validated" : "not_validated"));
    summary.Set("biasing_effect_observed", "unknown");
    summary.SetPath("actual_output_dir", outputManager_->GetOutputDir());
    summary.Set("initial_seed", initialSeed_ ? std::to_string(*initialSeed_) : "unset");
    summary.Set("configured_seed", context_.HasSeed() ? std::to_string(context_.GetSeed()) : "unset");
    summary.Set("initial_engine_seed", "unknown");
    summary.SetBool("macro_seed_modified", macroSeedModified_);

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
    std::sort(generated.begin(), generated.end());
    generated.erase(std::unique(generated.begin(), generated.end()), generated.end());
    summary.SetGeneratedFiles(generated);
    summary.Set("generated_file_count", static_cast<int>(generated.size()));
    summary.Set("summary_write_status", "completed");

    outputManager_->WriteRunSummary();
    return !outputFailed;
}

void SimulationManager::Configure()
{
    BuildManagers();

    if (!context_.GetMainConfig().empty() && !configLoaded_) {
        LoadConfig();
    }

    if (configLoaded_) {
        const int threads = configManager_->GetInt("run", "threads", context_.GetNumThreads());
        context_.SetNumThreads(threads);

        if (HasKeyCompat(*configManager_, "run", {"seed", "randomSeed"}) ||
            HasKeyCompat(*configManager_, "general", {"seed", "randomSeed"})) {
            const int seed = HasKeyCompat(*configManager_, "run", {"seed", "randomSeed"})
                ? GetIntCompat(*configManager_, "run", {"seed", "randomSeed"}, 0)
                : GetIntCompat(*configManager_, "general", {"seed", "randomSeed"}, 0);
            if (seed < 0) throw std::runtime_error("Invalid config value run/seed: seed must be >= 0");
            context_.SetSeed(static_cast<unsigned long>(seed));
        }

        context_.SetInteractive(configManager_->GetBool("run", "interactive", context_.IsInteractive()));
        context_.SetMacroFile(configManager_->GetString("run", "macro", context_.GetMacroFile()));
        context_.SetDryRun(GetBoolCompat(*configManager_, "run", {"dry_run", "dryRun"}, context_.IsDryRun()));
        context_.SetVerboseLevel(HasKeyCompat(*configManager_, "run", {"verbose"})
            ? configManager_->GetInt("run", "verbose", context_.GetVerboseLevel())
            : configManager_->GetInt("general", "verbose", context_.GetVerboseLevel()));
        context_.SetCheckOverlaps(GetBoolCompat(*configManager_, "run", {"check_overlaps", "checkOverlaps"}, context_.GetCheckOverlaps()));
        context_.SetRunName(GetStringCompat(*configManager_, "run", {"name", "run_name", "runName"}, context_.GetRunName()));
        context_.SetOutputDir(GetStringCompat(*configManager_, "output", {"dir", "outputDir"}, context_.GetOutputDir()));

        if (HasNonEmptyKeyCompat(*configManager_, "materials", {"file", "materialFile", "config", "configFile"})) {
            materialsFile_ = GetStringCompat(*configManager_, "materials", {"file", "materialFile", "config", "configFile"});
            if (!FileUtils::IsFile(materialsFile_)) {
                throw std::runtime_error("Materials config file does not exist: '" + materialsFile_ + "'");
            }
            materialManager_->LoadMaterials(materialsFile_);
        }

        if (HasNonEmptyKeyCompat(*configManager_, "geometry", {"template", "templateName"})) {
            geometryTemplate_ = GetStringCompat(*configManager_, "geometry", {"template", "templateName"});
            geometryManager_->SetTemplate(geometryTemplate_);
        }

        if (HasKeyCompat(*configManager_, "geometry", {"check_overlaps", "checkOverlaps"})) {
            context_.SetCheckOverlaps(GetBoolCompat(*configManager_, "geometry", {"check_overlaps", "checkOverlaps"}, context_.GetCheckOverlaps()));
        }

        if (HasNonEmptyKeyCompat(*configManager_, "geometry", {"default_world_material", "defaultWorldMaterial"})) {
            defaultWorldMaterial_ = GetStringCompat(*configManager_, "geometry", {"default_world_material", "defaultWorldMaterial"});
            geometryManager_->SetDefaultWorldMaterial(defaultWorldMaterial_);
        }

        if (HasNonEmptyKeyCompat(*configManager_, "geometry", {"config", "configFile"})) {
            geometryConfigFile_ = GetStringCompat(*configManager_, "geometry", {"config", "configFile"});
            if (!FileUtils::IsFile(geometryConfigFile_)) {
                throw std::runtime_error("Geometry config file does not exist: '" + geometryConfigFile_ + "'");
            }
            geometryManager_->LoadGeometryConfig(geometryConfigFile_);
        }

        physicsManager_->SetBiasingManager(biasingManager_.get());
        physicsManager_->LoadFromConfig(*configManager_);
        sourceManager_->LoadFromConfig(*configManager_);
        scoringManager_->LoadFromConfig(*configManager_);
        biasingManager_->LoadFromConfig(*configManager_);
        if (biasingManager_->IsEnabled()) {
            physicsManager_->EnableBiasingPhysics(true);
        }

        // These aliases are intentionally accepted for compatibility.  A canonical
        // spelling may win, but a shadowed legacy spelling is still a consumed field.
        for (const auto& alias : {"seed", "randomSeed", "dry_run", "dryRun",
                                  "check_overlaps", "checkOverlaps", "name",
                                  "run_name", "runName"}) {
            configManager_->MarkKeyConsumed("run", alias);
        }
        for (const auto& alias : {"seed", "randomSeed", "verbose"}) {
            configManager_->MarkKeyConsumed("general", alias);
        }
        for (const auto& alias : {"dir", "outputDir"}) {
            configManager_->MarkKeyConsumed("output", alias);
        }
        for (const auto& alias : {"file", "materialFile", "config", "configFile"}) {
            configManager_->MarkKeyConsumed("materials", alias);
            configManager_->MarkKeyConsumed("geometry", alias);
        }
        for (const auto& alias : {"template", "templateName", "check_overlaps",
                                  "checkOverlaps", "default_world_material",
                                  "defaultWorldMaterial"}) {
            configManager_->MarkKeyConsumed("geometry", alias);
        }
    }

    outputManager_->SetOutputDir(context_.GetOutputDir());
    geometryManager_->SetCheckOverlaps(context_.GetCheckOverlaps());
    geometryManager_->SetMaterialManager(materialManager_.get());
    ApplyCommandLineOverrides();
    CaptureConfiguredValueOrigins();
    ReportConfigWarnings();

    configured_ = true;
    initialized_ = false;
}

void SimulationManager::ReportConfigWarnings()
{
    if (!configLoaded_ || configWarningsReported_) return;

    const auto warnings = configManager_->GetUnconsumedWarnings();
    RunSummary& summary = outputManager_->GetRunSummary();
    summary.Set("config_warning_count", static_cast<int>(warnings.size()));
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
    detector->SetSensitiveDetectorFactory(CreateSensitiveDetectorFactory());
    detector->SetGeometryPostBuildCallback(CreateGeometryPostBuildCallback());
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

        PhysicsFactory::ApplyCuts(
            list.get(),
            physicsManager_->GetDefaultCut(),
            physicsManager_->GetParticleCuts());
        return list;
    }

    return std::make_unique<PhysicsList>(physicsManager_.get());
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
    return std::make_unique<ActionInitialization>(
        sourceManager_.get(),
        scoringManager_.get(),
        outputManager_.get(),
        biasingManager_.get());
}

std::function<G4VSensitiveDetector*()> SimulationManager::CreateSensitiveDetectorFactory() const
{
    if (!scoringManager_) {
        throw std::runtime_error("SimulationManager::CreateSensitiveDetectorFactory failed: ScoringManager is null");
    }

    return [this]() -> G4VSensitiveDetector* {
        ScoringManager* threadScoringManager = AIHL::GetCurrentThreadScoringManager();
        return new SensitiveDetector(
            "AIHLParticleSD",
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

void SimulationManager::ValidateBiasingProcessTargets()
{
    if (biasingManager_ && biasingManager_->IsEnabled()) {
        biasingManager_->ValidateActiveProcessRules();
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
    if (!outputManager_) outputManager_ = std::make_unique<OutputManager>();
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
    summary.SetBool("effective_biasing_enabled", biasingManager_ && biasingManager_->IsEnabled());
}
