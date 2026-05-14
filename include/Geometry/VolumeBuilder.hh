#pragma once

#include "G4RotationMatrix.hh"

#include <memory>
#include <string>
#include <vector>

class G4LogicalVolume;
class G4VPhysicalVolume;
class G4VSolid;
class G4VisAttributes;
class GeometryRegistry;
class MaterialManager;
class VolumeNode;

class VolumeBuilder {
public:
    VolumeBuilder();
    ~VolumeBuilder();

    void SetMaterialManager(MaterialManager* materialManager);
    void SetRegistry(GeometryRegistry* registry);

    void SetCheckOverlaps(bool enable);
    bool GetCheckOverlaps() const;

    void SetDefaultWorldMaterial(const std::string& materialName);
    const std::string& GetDefaultWorldMaterial() const;

    void Clear();

    G4VPhysicalVolume* BuildWorld(const VolumeNode& rootNode);
    G4LogicalVolume* BuildLogicalVolume(const VolumeNode& node);
    G4VPhysicalVolume* BuildVolume(const VolumeNode& node, G4LogicalVolume* motherLogical);

    G4VSolid* CreateSolid(const VolumeNode& node);
    G4VSolid* CreateBoxSolid(const VolumeNode& node);
    G4VSolid* CreateTubsSolid(const VolumeNode& node);
    G4VSolid* CreateSphereSolid(const VolumeNode& node);
    G4VSolid* CreateOrbSolid(const VolumeNode& node);
    G4VSolid* CreateConeSolid(const VolumeNode& node);
    G4VSolid* CreateTrdSolid(const VolumeNode& node);
    G4VSolid* CreateTrapSolid(const VolumeNode& node);

    G4RotationMatrix* CreateRotation(const VolumeNode& node);

    void CreateRegion(const VolumeNode& node, G4LogicalVolume* logicalVolume);
    void ApplyVisualAttributes(const VolumeNode& node, G4LogicalVolume* logicalVolume);

    GeometryRegistry* GetRegistry();
    const GeometryRegistry* GetRegistry() const;

private:
    void EnsureReady(const std::string& action) const;
    void BuildChildren(const VolumeNode& parentNode, G4LogicalVolume* motherLogical);

    MaterialManager* materialManager_ = nullptr;
    GeometryRegistry* registry_ = nullptr;
    bool checkOverlaps_ = true;
    std::string defaultWorldMaterial_ = "G4_AIR";

    // Geant4 placements keep rotation pointers; keep them alive for the builder lifetime.
    std::vector<std::unique_ptr<G4RotationMatrix>> rotations_;

    // Logical volumes do not take ownership of vis attributes in all Geant4 versions.
    std::vector<std::unique_ptr<G4VisAttributes>> visualAttributes_;
};
