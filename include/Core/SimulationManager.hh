#pragma once

#include "Core/SimulationContext.hh"

#include <memory>
#include <string>

class ConfigManager;
class OutputManager;
class MaterialManager;
class MaterialMessenger;
class GeometryManager;
class GeometryMessenger;
class DetectorConstruction;
class PhysicsManager;
class SourceManager;
class BiasingManager;
class ScoringManager;

class SimulationManager {
public:
    SimulationManager();
    ~SimulationManager();

    SimulationContext& GetContext();
    const SimulationContext& GetContext() const;

    void SetMainConfig(const std::string& filename);
    void SetOutputDir(const std::string& outputDir);
    void SetNumThreads(int n);
    void SetSeed(unsigned long seed);
    void SetMacroFile(const std::string& filename);
    void SetInteractive(bool interactive);
    void SetVerboseLevel(int level);
    void SetCheckOverlaps(bool enable);

    void LoadConfig();
    void Initialize();
    void Configure();
    void BuildManagers();
    void PrintSummary() const;

    bool IsConfigured() const;
    bool IsInitialized() const;

    std::unique_ptr<DetectorConstruction> CreateDetectorConstruction() const;

    ConfigManager* GetConfigManager();
    OutputManager* GetOutputManager();

    const ConfigManager* GetConfigManager() const;
    const OutputManager* GetOutputManager() const;

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
    void ConfigureOutputManager();
    void WriteBaseRunSummary();

    SimulationContext context_;
    std::unique_ptr<ConfigManager> configManager_;
    std::unique_ptr<OutputManager> outputManager_;
    std::unique_ptr<MaterialManager> materialManager_;
    std::unique_ptr<GeometryManager> geometryManager_;
    std::unique_ptr<MaterialMessenger> materialMessenger_;
    std::unique_ptr<GeometryMessenger> geometryMessenger_;

    // These managers are intentionally reserved for later modules.
    std::unique_ptr<PhysicsManager> physicsManager_;
    std::unique_ptr<SourceManager> sourceManager_;
    std::unique_ptr<BiasingManager> biasingManager_;
    std::unique_ptr<ScoringManager> scoringManager_;

    std::string materialsFile_;
    std::string geometryTemplate_ = "simple_box";
    std::string geometryConfigFile_;
    std::string defaultWorldMaterial_ = "G4_AIR";

    bool configLoaded_ = false;
    bool configured_ = false;
    bool initialized_ = false;
};
