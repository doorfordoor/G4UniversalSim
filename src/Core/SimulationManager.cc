#include "Core/SimulationManager.hh"

#include "Config/ConfigManager.hh"
#include "Biasing/BiasingManager.hh"
#include "Geometry/GeometryManager.hh"
#include "Materials/MaterialManager.hh"
#include "Output/OutputManager.hh"
#include "Output/RunSummary.hh"
#include "Physics/PhysicsManager.hh"
#include "Scoring/ScoringManager.hh"
#include "Source/SourceManager.hh"
#include "Utils/FileUtils.hh"

#include <iostream>
#include <stdexcept>

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

void SimulationManager::SetMainConfig(const std::string& filename)
{
    context_.SetMainConfig(filename);
    configLoaded_ = false;
    configured_ = false;
    initialized_ = false;
}

void SimulationManager::SetOutputDir(const std::string& outputDir)
{
    context_.SetOutputDir(outputDir);
    if (outputManager_) {
        outputManager_->SetOutputDir(context_.GetOutputDir());
    }
}

void SimulationManager::SetNumThreads(int n)
{
    context_.SetNumThreads(n);
}

void SimulationManager::SetSeed(unsigned long seed)
{
    context_.SetSeed(seed);
}

void SimulationManager::SetMacroFile(const std::string& filename)
{
    context_.SetMacroFile(filename);
}

void SimulationManager::SetInteractive(bool interactive)
{
    context_.SetInteractive(interactive);
}

void SimulationManager::SetVerboseLevel(int level)
{
    context_.SetVerboseLevel(level);
}

void SimulationManager::SetCheckOverlaps(bool enable)
{
    context_.SetCheckOverlaps(enable);
}

void SimulationManager::LoadConfig()
{
    if (context_.GetMainConfig().empty()) {
        throw std::runtime_error("SimulationManager::LoadConfig requires a main config path");
    }
    if (!FileUtils::IsFile(context_.GetMainConfig())) {
        throw std::runtime_error(
            "Main config file does not exist: '" + context_.GetMainConfig() + "'"
        );
    }

    EnsureConfigManager();
    configManager_->LoadMainConfig(context_.GetMainConfig());
    configLoaded_ = true;
    configured_ = false;
    initialized_ = false;
}

void SimulationManager::Initialize()
{
    if (!configLoaded_) {
        LoadConfig();
    }
    if (!configured_) {
        Configure();
    }

    BuildManagers();
    ConfigureOutputManager();
    outputManager_->Initialize();
    WriteBaseRunSummary();

    initialized_ = true;
}

void SimulationManager::Configure()
{
    if (!configLoaded_) {
        LoadConfig();
    }

    const int threads = configManager_->GetInt("run", "threads", context_.GetNumThreads());
    context_.SetNumThreads(threads);

    if (configManager_->HasKey("run", "seed")) {
        const int seed = configManager_->GetInt("run", "seed");
        if (seed < 0) {
            throw std::runtime_error("Invalid config value run/seed: seed must be >= 0");
        }
        context_.SetSeed(static_cast<unsigned long>(seed));
    }

    context_.SetInteractive(
        configManager_->GetBool("run", "interactive", context_.IsInteractive())
    );
    context_.SetMacroFile(
        configManager_->GetString("run", "macro", context_.GetMacroFile())
    );
    context_.SetVerboseLevel(
        configManager_->GetInt("run", "verbose", context_.GetVerboseLevel())
    );
    context_.SetCheckOverlaps(
        configManager_->GetBool("run", "check_overlaps", context_.GetCheckOverlaps())
    );
    context_.SetRunName(
        configManager_->GetString("run", "run_name", context_.GetRunName())
    );
    context_.SetOutputDir(
        configManager_->GetString("output", "dir", context_.GetOutputDir())
    );

    configured_ = true;
    initialized_ = false;
}

void SimulationManager::BuildManagers()
{
    EnsureConfigManager();
    EnsureOutputManager();

    // Material/Geometry/Physics/Source/Biasing/Scoring managers are not
    // constructed here yet because their modules are implemented later.
}

void SimulationManager::PrintSummary() const
{
    std::cout << "G4UniversalSim Simulation Summary\n";
    std::cout << "  main_config     : " << context_.GetMainConfig() << '\n';
    std::cout << "  output_dir      : " << context_.GetOutputDir() << '\n';
    std::cout << "  run_name        : " << context_.GetRunName() << '\n';
    std::cout << "  num_threads     : " << context_.GetNumThreads() << '\n';
    std::cout << "  seed            : "
              << (context_.HasSeed() ? std::to_string(context_.GetSeed()) : "(unset)") << '\n';
    std::cout << "  macro_file      : " << context_.GetMacroFile() << '\n';
    std::cout << "  interactive     : " << (context_.IsInteractive() ? "true" : "false") << '\n';
    std::cout << "  verbose_level   : " << context_.GetVerboseLevel() << '\n';
    std::cout << "  check_overlaps  : " << (context_.GetCheckOverlaps() ? "true" : "false") << '\n';
    std::cout << "  dry_run         : " << (context_.IsDryRun() ? "true" : "false") << '\n';
    std::cout << "  config_loaded   : " << (configLoaded_ ? "true" : "false") << '\n';
    std::cout << "  configured      : " << (configured_ ? "true" : "false") << '\n';
    std::cout << "  initialized     : " << (initialized_ ? "true" : "false") << '\n';
}

bool SimulationManager::IsConfigured() const
{
    return configured_;
}

bool SimulationManager::IsInitialized() const
{
    return initialized_;
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
    if (!configManager_) {
        configManager_ = std::make_unique<ConfigManager>();
    }
}

void SimulationManager::EnsureOutputManager()
{
    if (!outputManager_) {
        outputManager_ = std::make_unique<OutputManager>();
    }
}

void SimulationManager::ConfigureOutputManager()
{
    EnsureOutputManager();
    outputManager_->SetOutputDir(context_.GetOutputDir());
    outputManager_->SetThreadId(0);
    outputManager_->EnableThreadSuffix(true);
}

void SimulationManager::WriteBaseRunSummary()
{
    EnsureOutputManager();
    RunSummary& summary = outputManager_->GetRunSummary();
    summary.Set("run_name", context_.GetRunName());
    summary.Set("main_config", context_.GetMainConfig());
    summary.Set("output_dir", context_.GetOutputDir());
    summary.Set("num_threads", context_.GetNumThreads());
    summary.Set("seed", context_.HasSeed() ? std::to_string(context_.GetSeed()) : "");
    summary.Set("macro_file", context_.GetMacroFile());
    summary.SetBool("interactive", context_.IsInteractive());
    summary.Set("verbose_level", context_.GetVerboseLevel());
    summary.SetBool("check_overlaps", context_.GetCheckOverlaps());
    summary.SetBool("dry_run", context_.IsDryRun());
    summary.AddMessage("Core initialization completed");
    outputManager_->WriteRunSummary();
}
