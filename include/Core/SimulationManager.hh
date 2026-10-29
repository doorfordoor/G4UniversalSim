#pragma once

#include "Core/SimulationContext.hh"

#include <functional>
#include <map>
#include "Field/FieldConfig.hh"

#include <memory>
#include <optional>
#include <string>
#include <vector>

struct SimulationCommandLineOverrides {
    std::optional<std::string> mainConfig;
    std::optional<std::string> outputDir;
    std::optional<std::string> runName;
    std::optional<std::string> macroFile;
    std::optional<int> numThreads;
    std::optional<unsigned long> seed;
    std::optional<bool> interactive;
    std::optional<bool> dryRun;
    std::optional<bool> checkOverlaps;
};

class ConfigManager;
class ActionInitialization;
class AppMessenger;
class OutputManager;
class OutputMessenger;
class MaterialManager;
class MaterialMessenger;
class GeometryManager;
class GeometryMessenger;
class GeometryRegistry;
class DetectorConstruction;
class G4VSensitiveDetector;
class PhysicsManager;
class PhysicsMessenger;
class PhysicsList;
class G4VModularPhysicsList;
class SourceManager;
class SourceMessenger;
class PrimaryGeneratorAction;
class BiasingManager;
class BiasingMessenger;
class ScoringManager;
class ScoringMessenger;

class SimulationManager {
public:
    SimulationManager();
    ~SimulationManager();

    SimulationContext& GetContext();
    const SimulationContext& GetContext() const;
    const std::string& GetMaterialsConfigFile() const;

    void SetCommandLineOverrides(const SimulationCommandLineOverrides& overrides);
    void SetMainConfig(const std::string& filename);
    void SetOutputDir(const std::string& outputDir);
    void SetNumThreads(int n);
    void SetSeed(unsigned long seed);
    void SetMacroFile(const std::string& filename);
    void SetInteractive(bool interactive);
    void SetVerboseLevel(int level);
    void SetCheckOverlaps(bool enable);
    void SetDryRun(bool enable);
    void SetRunName(const std::string& name);

    void LoadConfig();
    void Initialize();
    void BeginRuntimeTracking();
    bool NoteMacroCommand(const std::string& command) const;
    void ConfirmMacroCommandSuccess(bool seedStateChanged);
    void RecordSuccessfulMacroCommand(const std::string& command,
                                      const std::string& file,
                                      int line);
    void SetExecutedMacroPath(const std::string& path);
    bool FinalizeRunSummary(const std::string& status,
                            int exitCode,
                            const std::string& macroStatus,
                            const std::string& failureFile = {},
                            int failureLine = 0,
                            const std::string& failureCommand = {},
                            int failureCode = 0,
                            bool failureCodeAvailable = false);
    void Configure();
    void BuildManagers();
    void PrintSummary() const;
    // Read-only configured Manager subset; no kernel/application claim.
    std::string ExportEffectiveConfigJson() const;

    bool IsConfigured() const;
    bool IsInitialized() const;

    std::unique_ptr<DetectorConstruction> CreateDetectorConstruction() const;
    std::unique_ptr<G4VModularPhysicsList> CreatePhysicsList() const;
    std::unique_ptr<PrimaryGeneratorAction> CreatePrimaryGeneratorAction() const;
    std::unique_ptr<ActionInitialization> CreateActionInitialization() const;
    std::function<G4VSensitiveDetector*(const std::string&)> CreateSensitiveDetectorFactory() const;
    std::function<void(const GeometryRegistry&)> CreateGeometryPostBuildCallback() const;
    void InitializeSourceAfterPhysicsListRegistered();
    void ValidateBiasingProcessTargets();
    void EnableInteractivePhysicsGuard();
    std::size_t GetInteractivePhysicsFailureCount() const;
    std::string GetLastInteractivePhysicsFailure() const;

    ConfigManager* GetConfigManager();
    OutputManager* GetOutputManager();

    const ConfigManager* GetConfigManager() const;
    const OutputManager* GetOutputManager() const;
    // /score/ commands generated from [scoring.mesh.*] INI sections; main applies
    // them after G4ScoringManager is created and before user macros.
    const std::vector<std::string>& GetScoringMeshCommands() const { return scoringMeshCommands_; }

    MaterialManager* GetMaterialManager();
    GeometryManager* GetGeometryManager();
    PhysicsManager* GetPhysicsManager();
    SourceManager* GetSourceManager();
    BiasingManager* GetBiasingManager();
    ScoringManager* GetScoringManager();

    const MaterialManager* GetMaterialManager() const;
    const GeometryManager* GetGeometryManager() const;
    const PhysicsManager* GetPhysicsManager() const;
    const SourceManager* GetSourceManager() const;
    const BiasingManager* GetBiasingManager() const;
    const ScoringManager* GetScoringManager() const;

private:
    void EnsureConfigManager();
    void EnsureOutputManager();
    void EnsureMaterialManager();
    void EnsureGeometryManager();
    void EnsurePhysicsManager();
    void EnsureSourceManager();
    void EnsureBiasingManager();
    void EnsureScoringManager();
    void ConfigureOutputManager();
    void ApplyCommandLineOverrides();
    void WarnIgnoredCommandLineOverride(const std::string& name) const;
    void ReportConfigWarnings();
    void WriteBaseRunSummary();
    void WriteFinalConfigSnapshot(const std::string& macroStatus);
    void CaptureConfiguredValueOrigins();
    void MarkRuntimeValueOrigin(const std::string& field);

    struct ValueOrigin {
        std::string kind = "default";
        std::string file;
        std::string section;
        std::string key;
        int line = 0;
    };

    SimulationContext context_;
    std::unique_ptr<ConfigManager> configManager_;
    std::unique_ptr<OutputManager> outputManager_;
    std::unique_ptr<MaterialManager> materialManager_;
    std::unique_ptr<GeometryManager> geometryManager_;
    std::unique_ptr<AppMessenger> appMessenger_;
    std::unique_ptr<OutputMessenger> outputMessenger_;
    std::unique_ptr<MaterialMessenger> materialMessenger_;
    std::unique_ptr<GeometryMessenger> geometryMessenger_;
    std::unique_ptr<PhysicsMessenger> physicsMessenger_;
    std::unique_ptr<SourceMessenger> sourceMessenger_;
    std::unique_ptr<BiasingMessenger> biasingMessenger_;
    std::unique_ptr<ScoringMessenger> scoringMessenger_;

    // These managers are intentionally reserved for later modules.
    std::unique_ptr<PhysicsManager> physicsManager_;
    FieldConfig fieldConfig_;
    std::unique_ptr<SourceManager> sourceManager_;
    std::unique_ptr<BiasingManager> biasingManager_;
    std::unique_ptr<ScoringManager> scoringManager_;

    std::string materialsFile_;
    std::vector<std::string> scoringMeshCommands_;
    std::string geometryTemplate_ = "simple_box";
    std::string geometryConfigFile_;
    std::string defaultWorldMaterial_ = "G4_AIR";
    SimulationCommandLineOverrides commandLineOverrides_;
    bool commandLineOverridesSet_ = false;

    bool configLoaded_ = false;
    bool configWarningsReported_ = false;
    bool configured_ = false;
    bool initialized_ = false;
    std::optional<unsigned long> initialSeed_;
    bool macroSeedModified_ = false;
    bool runtimeTrackingStarted_ = false;
    std::string executedMacroPath_;
    std::map<std::string, ValueOrigin> effectiveValueOrigins_;
};
