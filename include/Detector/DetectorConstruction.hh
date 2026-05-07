#pragma once

#include "G4VUserDetectorConstruction.hh"

#include <functional>
#include <string>

class G4VPhysicalVolume;
class G4VSensitiveDetector;
class GeometryManager;
class GeometryRegistry;

class DetectorConstruction : public G4VUserDetectorConstruction {
public:
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

    void SetSensitiveDetectorFactory(std::function<G4VSensitiveDetector*()> factory);

private:
    GeometryManager* geometryManager_ = nullptr;
    G4VPhysicalVolume* worldVolume_ = nullptr;
    bool sensitiveDetectorEnabled_ = true;
    std::string sensitiveDetectorName_ = "AIHLParticleSD";
    int verboseLevel_ = 1;
    std::function<G4VSensitiveDetector*()> sensitiveDetectorFactory_;
};
