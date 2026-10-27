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
    // Roadmap A7: fields are built per thread in ConstructSDandField.
    void SetFieldConfig(const FieldConfig* fieldConfig);

private:
    GeometryManager* geometryManager_ = nullptr;
    std::unique_ptr<DetectorMessenger> detectorMessenger_;
    G4VPhysicalVolume* worldVolume_ = nullptr;
    bool sensitiveDetectorEnabled_ = true;
    std::string sensitiveDetectorName_ = "AIHLParticleSD";
    int verboseLevel_ = 1;
    SensitiveDetectorFactory sensitiveDetectorFactory_;
    GeometryPostBuildCallback postBuildCallback_;
    const FieldConfig* fieldConfig_ = nullptr;  // not owned
};
