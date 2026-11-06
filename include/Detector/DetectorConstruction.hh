#pragma once

#include "G4VUserDetectorConstruction.hh"

#include <functional>
#include <memory>
#include <string>

class DetectorMessenger;
class FieldConfig;
class G4VPhysicalVolume;
class G4VSensitiveDetector;
class GeometryManager;
class GeometryRegistry;
class OutputManager;

namespace parallel_world {
class ParallelWorldConfig;
class ScoringParallelWorld;
}

class DetectorConstruction : public G4VUserDetectorConstruction {
public:
    using GeometryPostBuildCallback = std::function<void(const GeometryRegistry&)>;
    // The factory must create the sensitive detector with the name passed in (the configured
    // sensitiveDetectorName_), otherwise the SD registered with G4SDManager and the name this
    // class looks up differ: re-initialisation would register a second SD and the configured
    // name would never be found.
    using SensitiveDetectorFactory = std::function<G4VSensitiveDetector*(const std::string&)>;

    explicit DetectorConstruction(GeometryManager* geometryManager);
    ~DetectorConstruction() override;

    G4VPhysicalVolume* Construct() override;
    void ConstructSDandField() override;

    void SetGeometryManager(GeometryManager* geometryManager);
    GeometryManager* GetGeometryManager() const;

    GeometryRegistry* GetGeometryRegistry();
    const GeometryRegistry* GetGeometryRegistry() const;

    G4VPhysicalVolume* GetWorldVolume() const;

    void SetSensitiveDetectorEnabled(bool enable);
    bool IsSensitiveDetectorEnabled() const;

    void SetSensitiveDetectorName(const std::string& name);
    const std::string& GetSensitiveDetectorName() const;

    void SetVerboseLevel(int level);
    int GetVerboseLevel() const;

    void PrintRegistrySummary() const;
    void PrintSensitiveVolumes() const;
    void PrintBiasVolumes() const;

    void SetSensitiveDetectorFactory(SensitiveDetectorFactory factory);
    void SetGeometryPostBuildCallback(GeometryPostBuildCallback callback);
    void SetThreadBiasingCallback(GeometryPostBuildCallback callback);
    // Roadmap A7: fields are built per thread in ConstructSDandField.
    void SetFieldConfig(const FieldConfig* fieldConfig);

    // Roadmap H3: optional parallel scoring world. The construction object keeps
    // a shared reference for the lifetime of the run. The parallel world object
    // is created and registered here (before CreateDetectorConstruction returns),
    // not from inside Construct(), and Geant4 builds it during initialization.
    void SetParallelWorldConfig(std::shared_ptr<const parallel_world::ParallelWorldConfig> config);
    // Not owned. Set before SetParallelWorldConfig so per-thread SD binding
    // failures can be latched into the shared output-failure registry.
    void SetParallelWorldOutputManager(OutputManager* outputManager);
    const std::shared_ptr<const parallel_world::ParallelWorldConfig>& GetParallelWorldConfig() const;
    // Kernel-side ghost world registered during Construct(); null when disabled.
    parallel_world::ScoringParallelWorld* GetScoringParallelWorld() const;

private:
    GeometryManager* geometryManager_ = nullptr;
    std::unique_ptr<DetectorMessenger> detectorMessenger_;
    G4VPhysicalVolume* worldVolume_ = nullptr;
    bool sensitiveDetectorEnabled_ = true;
    std::string sensitiveDetectorName_ = "AIHLParticleSD";
    int verboseLevel_ = 1;
    SensitiveDetectorFactory sensitiveDetectorFactory_;
    GeometryPostBuildCallback postBuildCallback_;
    GeometryPostBuildCallback threadBiasingCallback_;
    const FieldConfig* fieldConfig_ = nullptr;  // not owned
    std::shared_ptr<const parallel_world::ParallelWorldConfig> parallelWorldConfig_;  // may be null
    parallel_world::ScoringParallelWorld* scoringParallelWorld_ = nullptr;  // owned by Geant4
    bool parallelWorldRegistered_ = false;
    OutputManager* parallelWorldOutputManager_ = nullptr;  // not owned
};
