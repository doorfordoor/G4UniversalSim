#include "Core/SimulationManager.hh"

#include "Actions/ActionInitialization.hh"
#include "Config/ConfigManager.hh"
#include "Detector/DetectorConstruction.hh"
#include "Geometry/GeometryManager.hh"
#include "Geometry/GeometryMessenger.hh"
#include "Hits/SensitiveDetector.hh"
#include "Materials/MaterialManager.hh"
#include "Materials/MaterialMessenger.hh"
#include "Output/OutputManager.hh"
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
#include "Utils/FileUtils.hh"
#include "Utils/StringUtils.hh"

#include <iostream>
#include <map>
#include <stdexcept>
#include <vector>

namespace {

std::string BoolText(bool value)
{
    return value ? "true" : "false";
}

bool HasNonEmptyKey(const ConfigManager& config, const std::string& section, const std::string& key)
{
    return config.HasKey(section, key) && !StringUtils::Trim(config.GetString(section, key, "")).empty();
}

std::map<std::string, std::vector<std::string>> BuildBiasParticleProcessMap(
    const BiasingManager* biasingManager)
{
    std::map<std::string, std::vector<std::string>> values;
    if (!biasingManager) return values;
    for (const XSBiasRule& rule : biasingManager->GetEnabledXSBiasRules()) {
        if (!StringUtils::Trim(rule.particleName).empty()) {
            values[rule.particleName] = rule.processNames;
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
    if (outputManager_) outputManager_->SetOutputDir(context_.GetOutputDir());
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
    if (geometryManager_) geometryManager_->SetCheckOverlaps(enable);
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

void SimulationManager::Configure()
{
    BuildManagers();

    if (!context_.GetMainConfig().empty() && !configLoaded_) {
        LoadConfig();
    }

    if (configLoaded_) {
        const int threads = configManager_->GetInt("run", "threads", context_.GetNumThreads());
        context_.SetNumThreads(threads);

        if (configManager_->HasKey("run", "seed")) {
            const int seed = configManager_->GetInt("run", "seed");
            if (seed < 0) throw std::runtime_error("Invalid config value run/seed: seed must be >= 0");
            context_.SetSeed(static_cast<unsigned long>(seed));
        }

        context_.SetInteractive(configManager_->GetBool("run", "interactive", context_.IsInteractive()));
        context_.SetMacroFile(configManager_->GetString("run", "macro", context_.GetMacroFile()));
        context_.SetVerboseLevel(configManager_->GetInt("run", "verbose", context_.GetVerboseLevel()));
        context_.SetCheckOverlaps(configManager_->GetBool("run", "check_overlaps", context_.GetCheckOverlaps()));
        context_.SetRunName(configManager_->GetString("run", "run_name", context_.GetRunName()));
        context_.SetOutputDir(configManager_->GetString("output", "dir", context_.GetOutputDir()));

        if (HasNonEmptyKey(*configManager_, "materials", "file")) {
            materialsFile_ = configManager_->GetString("materials", "file");
            if (!FileUtils::IsFile(materialsFile_)) {
                throw std::runtime_error("Materials config file does not exist: '" + materialsFile_ + "'");
            }
            materialManager_->LoadMaterials(materialsFile_);
        }

        if (HasNonEmptyKey(*configManager_, "geometry", "template")) {
            geometryTemplate_ = configManager_->GetString("geometry", "template");
            geometryManager_->SetTemplate(geometryTemplate_);
        }

        if (configManager_->HasKey("geometry", "check_overlaps")) {
            context_.SetCheckOverlaps(configManager_->GetBool("geometry", "check_overlaps", context_.GetCheckOverlaps()));
        }

        if (HasNonEmptyKey(*configManager_, "geometry", "default_world_material")) {
            defaultWorldMaterial_ = configManager_->GetString("geometry", "default_world_material");
            geometryManager_->SetDefaultWorldMaterial(defaultWorldMaterial_);
        }

        if (HasNonEmptyKey(*configManager_, "geometry", "config")) {
            geometryConfigFile_ = configManager_->GetString("geometry", "config");
            if (!FileUtils::IsFile(geometryConfigFile_)) {
                throw std::runtime_error("Geometry config file does not exist: '" + geometryConfigFile_ + "'");
            }
            geometryManager_->LoadGeometryConfig(geometryConfigFile_);
        }

        biasingManager_->LoadFromConfig(*configManager_);
        physicsManager_->SetBiasingManager(biasingManager_.get());
        physicsManager_->LoadFromConfig(*configManager_);
        if (biasingManager_->IsEnabled()) {
            physicsManager_->EnableBiasingPhysics(true);
        }
        sourceManager_->LoadFromConfig(*configManager_);
        scoringManager_->LoadFromConfig(*configManager_);
    }

    outputManager_->SetOutputDir(context_.GetOutputDir());
    geometryManager_->SetCheckOverlaps(context_.GetCheckOverlaps());
    geometryManager_->SetMaterialManager(materialManager_.get());

    configured_ = true;
    initialized_ = false;
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
    std::cout << "  source_manager    : " << (sourceManager_ ? "created" : "null") << '\n';
    std::cout << "  source_configured : " << (sourceManager_ ? BoolText(sourceManager_->IsConfigured()) : "false") << '\n';
    std::cout << "  source_particle   : " << (sourceManager_ ? sourceManager_->GetParticleName() : "") << '\n';
    std::cout << "  source_energy     : " << (sourceManager_ ? sourceManager_->GetMonoEnergy() : 0.0) << '\n';
    std::cout << "  source_preset     : " << (sourceManager_ ? sourceManager_->GetPresetName() : "") << '\n';
    std::cout << "  biasing_manager   : " << (biasingManager_ ? "created" : "null") << '\n';
    std::cout << "  biasing_enabled   : " << (biasingManager_ ? BoolText(biasingManager_->IsEnabled()) : "false") << '\n';
    std::cout << "  biasing_xs_rules  : " << (biasingManager_ ? biasingManager_->GetXSBiasRules().size() : 0) << '\n';
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
        outputManager_.get());
}

std::function<G4VSensitiveDetector*()> SimulationManager::CreateSensitiveDetectorFactory() const
{
    if (!scoringManager_) {
        throw std::runtime_error("SimulationManager::CreateSensitiveDetectorFactory failed: ScoringManager is null");
    }

    return [this]() -> G4VSensitiveDetector* {
        return new SensitiveDetector("AIHLParticleSD", scoringManager_.get());
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
    if (scoringManager_) scoringManager_->SetOutputManager(outputManager_.get());
}

void SimulationManager::WriteBaseRunSummary()
{
    EnsureOutputManager();
    RunSummary& summary = outputManager_->GetRunSummary();
    summary.Set("run_name", context_.GetRunName());
    summary.Set("main_config", context_.GetMainConfig());
    summary.Set("output_dir", context_.GetOutputDir());
    summary.Set("num_threads", context_.GetNumThreads());
    summary.Set("seed", context_.HasSeed() ? std::to_string(context_.GetSeed()) : "unset");
    summary.Set("macro_file", context_.GetMacroFile());
    summary.SetBool("interactive", context_.IsInteractive());
    summary.Set("verbose_level", context_.GetVerboseLevel());
    summary.SetBool("check_overlaps", context_.GetCheckOverlaps());
    summary.SetBool("dry_run", context_.IsDryRun());
    summary.Set("materials_file", materialsFile_);
    summary.Set("geometry_template", geometryTemplate_);
    summary.Set("geometry_config", geometryConfigFile_);
    summary.Set("physics_mode", physicsManager_ ? (physicsManager_->HasReferenceList() ? "reference" : "manual") : "");
    summary.Set("physics_reference", physicsManager_ ? physicsManager_->GetReferenceList() : "");
    summary.Set("physics_extra_modules", physicsManager_ ? StringUtils::Join(physicsManager_->GetExtraModules(), ",") : "");
    summary.Set("physics_em", physicsManager_ ? physicsManager_->GetEMOption() : "");
    summary.Set("physics_modules", physicsManager_ ? StringUtils::Join(physicsManager_->GetPhysicsModules(), ",") : "");
    summary.Set("physics_default_cut", physicsManager_ ? physicsManager_->GetDefaultCut() : 0.0);
    summary.SetBool("physics_biasing_enabled", physicsManager_ ? physicsManager_->IsBiasingPhysicsEnabled() : false);
    summary.SetBool("source_configured", sourceManager_ ? sourceManager_->IsConfigured() : false);
    summary.Set("source_particle", sourceManager_ ? sourceManager_->GetParticleName() : "");
    summary.Set("source_energy", sourceManager_ ? sourceManager_->GetMonoEnergy() : 0.0);
    summary.Set("source_preset", sourceManager_ ? sourceManager_->GetPresetName() : "");
    summary.SetBool("biasing_enabled", biasingManager_ ? biasingManager_->IsEnabled() : false);
    summary.Set("biasing_xs_rule_count", static_cast<int>(biasingManager_ ? biasingManager_->GetXSBiasRules().size() : 0));
    summary.SetBool("biasing_operators_attached", biasingManager_ ? biasingManager_->AreOperatorsAttached() : false);
    summary.Set("biasing_attached_operator_count", static_cast<int>(biasingManager_ ? biasingManager_->GetAttachedOperatorCount() : 0));
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
    outputManager_->WriteRunSummary();
}
