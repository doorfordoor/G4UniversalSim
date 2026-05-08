#include "Detector/DetectorConstruction.hh"

#include "Geometry/GeometryManager.hh"
#include "Geometry/GeometryRegistry.hh"

#include "G4Exception.hh"
#include "G4LogicalVolume.hh"
#include "G4SDManager.hh"
#include "G4VPhysicalVolume.hh"
#include "G4VSensitiveDetector.hh"
#include "G4ios.hh"

#include <stdexcept>
#include <utility>
#include <vector>

DetectorConstruction::DetectorConstruction(GeometryManager* geometryManager)
    : geometryManager_(geometryManager)
{
}

DetectorConstruction::~DetectorConstruction() = default;

G4VPhysicalVolume* DetectorConstruction::Construct()
{
    if (!geometryManager_) {
        throw std::runtime_error("DetectorConstruction::Construct failed: GeometryManager is null");
    }
    if (geometryManager_->IsDirty() && verboseLevel_ > 0) {
        G4cout << "[DetectorConstruction] GeometryManager is dirty; rebuilding world from current geometry state." << G4endl;
    }

    worldVolume_ = geometryManager_->BuildWorld();
    if (!worldVolume_) {
        throw std::runtime_error("DetectorConstruction::Construct failed: GeometryManager::BuildWorld returned null");
    }

    if (postBuildCallback_) {
        postBuildCallback_(geometryManager_->GetRegistry());
    }

    if (verboseLevel_ > 0) {
        G4cout << "[DetectorConstruction] World volume constructed." << G4endl;
        PrintRegistrySummary();
    }
    return worldVolume_;
}

void DetectorConstruction::ConstructSDandField()
{
    if (!sensitiveDetectorEnabled_) {
        if (verboseLevel_ > 0) G4cout << "[DetectorConstruction] Sensitive detector binding is disabled." << G4endl;
        return;
    }
    if (!geometryManager_) {
        throw std::runtime_error("DetectorConstruction::ConstructSDandField failed: GeometryManager is null");
    }

    GeometryRegistry& registry = geometryManager_->GetRegistry();
    const std::vector<G4LogicalVolume*> sensitiveLVs = registry.GetSensitiveLogicalVolumes();
    if (sensitiveLVs.empty()) {
        G4Exception(
            "DetectorConstruction::ConstructSDandField",
            "AIHLDetectorSD001",
            JustWarning,
            "No sensitive logical volumes are registered."
        );
        return;
    }

    if (!sensitiveDetectorFactory_) {
        G4Exception(
            "DetectorConstruction::ConstructSDandField",
            "AIHLDetectorSD002",
            JustWarning,
            "SensitiveDetector factory is not set. Sensitive volumes are registered but no SD is attached."
        );
        return;
    }

    G4SDManager* sdManager = G4SDManager::GetSDMpointer();
    if (!sdManager) {
        throw std::runtime_error("DetectorConstruction::ConstructSDandField failed: G4SDManager is null");
    }

    G4VSensitiveDetector* sd = sdManager->FindSensitiveDetector(sensitiveDetectorName_, false);
    if (!sd) {
        sd = sensitiveDetectorFactory_();
        if (!sd) {
            throw std::runtime_error("DetectorConstruction::ConstructSDandField failed: sensitiveDetectorFactory returned null");
        }
        sdManager->AddNewDetector(sd);
    } else if (verboseLevel_ > 0) {
        G4cout << "[DetectorConstruction] Reusing existing sensitive detector '"
               << sensitiveDetectorName_ << "'." << G4endl;
    }

    for (G4LogicalVolume* logicalVolume : sensitiveLVs) {
        if (logicalVolume) logicalVolume->SetSensitiveDetector(sd);
    }

    if (verboseLevel_ > 0) {
        G4cout << "[DetectorConstruction] Attached sensitive detector '" << sensitiveDetectorName_
               << "' to " << sensitiveLVs.size() << " logical volume(s)." << G4endl;
    }
}

void DetectorConstruction::SetGeometryManager(GeometryManager* geometryManager)
{
    geometryManager_ = geometryManager;
    worldVolume_ = nullptr;
}

GeometryManager* DetectorConstruction::GetGeometryManager() const
{
    return geometryManager_;
}

GeometryRegistry* DetectorConstruction::GetGeometryRegistry()
{
    if (!geometryManager_) return nullptr;
    return &geometryManager_->GetRegistry();
}

const GeometryRegistry* DetectorConstruction::GetGeometryRegistry() const
{
    if (!geometryManager_) return nullptr;
    return &geometryManager_->GetRegistry();
}

G4VPhysicalVolume* DetectorConstruction::GetWorldVolume() const
{
    return worldVolume_;
}

void DetectorConstruction::SetSensitiveDetectorEnabled(bool enable)
{
    sensitiveDetectorEnabled_ = enable;
}

bool DetectorConstruction::IsSensitiveDetectorEnabled() const
{
    return sensitiveDetectorEnabled_;
}

void DetectorConstruction::SetSensitiveDetectorName(const std::string& name)
{
    if (name.empty()) throw std::runtime_error("DetectorConstruction::SetSensitiveDetectorName failed: name is empty");
    sensitiveDetectorName_ = name;
}

const std::string& DetectorConstruction::GetSensitiveDetectorName() const
{
    return sensitiveDetectorName_;
}

void DetectorConstruction::SetVerboseLevel(int level)
{
    if (level < 0) throw std::runtime_error("DetectorConstruction::SetVerboseLevel failed: level must be >= 0");
    verboseLevel_ = level;
}

int DetectorConstruction::GetVerboseLevel() const
{
    return verboseLevel_;
}

void DetectorConstruction::PrintRegistrySummary() const
{
    const GeometryRegistry* registry = GetGeometryRegistry();
    if (!registry) {
        G4Exception(
            "DetectorConstruction::PrintRegistrySummary",
            "AIHLDetectorRegistry001",
            JustWarning,
            "GeometryRegistry is unavailable because GeometryManager is null."
        );
        return;
    }
    registry->PrintSummary();
}

void DetectorConstruction::PrintSensitiveVolumes() const
{
    const GeometryRegistry* registry = GetGeometryRegistry();
    if (!registry) {
        G4Exception("DetectorConstruction::PrintSensitiveVolumes", "AIHLDetectorRegistry002", JustWarning, "GeometryRegistry is unavailable.");
        return;
    }
    const auto names = registry->GetSensitiveVolumeNames();
    G4cout << "[DetectorConstruction] sensitive volumes: " << names.size() << G4endl;
    for (const std::string& name : names) G4cout << "  - " << name << G4endl;
}

void DetectorConstruction::PrintBiasVolumes() const
{
    const GeometryRegistry* registry = GetGeometryRegistry();
    if (!registry) {
        G4Exception("DetectorConstruction::PrintBiasVolumes", "AIHLDetectorRegistry003", JustWarning, "GeometryRegistry is unavailable.");
        return;
    }
    const auto names = registry->GetBiasVolumeNames();
    G4cout << "[DetectorConstruction] bias volumes: " << names.size() << G4endl;
    for (const std::string& name : names) G4cout << "  - " << name << G4endl;
}

void DetectorConstruction::SetSensitiveDetectorFactory(std::function<G4VSensitiveDetector*()> factory)
{
    sensitiveDetectorFactory_ = std::move(factory);
}

void DetectorConstruction::SetGeometryPostBuildCallback(GeometryPostBuildCallback callback)
{
    postBuildCallback_ = std::move(callback);
}
