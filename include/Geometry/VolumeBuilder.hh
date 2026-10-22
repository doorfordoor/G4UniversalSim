#pragma once

#include "Geometry/GeometryTypes.hh"

#include "G4RotationMatrix.hh"
#include "G4Transform3D.hh"

#include <memory>
#include <atomic>
#include <cstddef>
#include <string>
#include <vector>

class G4LogicalVolume;
class G4VPVParameterisation;
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
    G4VSolid* CreatePrimitiveSolid(const VolumeNode& node);
    G4VSolid* CreatePrimitiveSolidFromOperand(
        const std::string& ownerVolumeName,
        std::size_t booleanIndex,
        const BooleanOperand& operand
    );
    G4VSolid* ApplyBooleanOperations(const VolumeNode& node, G4VSolid* baseSolid);
    G4Transform3D MakeBooleanToolTransform(const BooleanOperand& operand);

    G4VSolid* CreateBoxSolid(const VolumeNode& node);
    G4VSolid* CreateTubsSolid(const VolumeNode& node);
    G4VSolid* CreateSphereSolid(const VolumeNode& node);
    G4VSolid* CreateOrbSolid(const VolumeNode& node);
    G4VSolid* CreateConeSolid(const VolumeNode& node);
    G4VSolid* CreateTrdSolid(const VolumeNode& node);
    G4VSolid* CreateTrapSolid(const VolumeNode& node);
    // roadmap A5
    G4VSolid* CreateEllipsoidSolid(const VolumeNode& node);
    G4VSolid* CreateEllipticalTubeSolid(const VolumeNode& node);
    G4VSolid* CreateTorusSolid(const VolumeNode& node);
    G4VSolid* CreateParaSolid(const VolumeNode& node);
    G4VSolid* CreateHypeSolid(const VolumeNode& node);
    G4VSolid* CreatePolyconeSolid(const VolumeNode& node, bool polyhedra);
    G4VSolid* CreateTessellatedSolid(const VolumeNode& node);

    G4RotationMatrix* CreateRotation(const VolumeNode& node);

    void CreateRegion(const VolumeNode& node, G4LogicalVolume* logicalVolume);
    void ApplyVisualAttributes(const VolumeNode& node, G4LogicalVolume* logicalVolume);

    GeometryRegistry* GetRegistry();
    const GeometryRegistry* GetRegistry() const;

    static void ResetCreatedGeometryObjectCount();
    static std::size_t GetCreatedGeometryObjectCount();

private:
    void EnsureReady(const std::string& action) const;
    void BuildChildren(const VolumeNode& parentNode, G4LogicalVolume* motherLogical);
    G4VPhysicalVolume* PlaceReplica(const VolumeNode& node, G4LogicalVolume* logical, G4LogicalVolume* motherLogical);
    G4VPhysicalVolume* PlaceParameterised(const VolumeNode& node, G4LogicalVolume* logical, G4LogicalVolume* motherLogical);

    MaterialManager* materialManager_ = nullptr;
    GeometryRegistry* registry_ = nullptr;
    bool checkOverlaps_ = true;
    std::string defaultWorldMaterial_ = "G4_AIR";

    // Geant4 placements keep rotation pointers; keep them alive for the builder lifetime.
    std::vector<std::unique_ptr<G4RotationMatrix>> rotations_;

    // Logical volumes do not take ownership of vis attributes in all Geant4 versions.
    std::vector<std::unique_ptr<G4VisAttributes>> visualAttributes_;

    // G4PVParameterised does not own its parameterisation.
    std::vector<std::unique_ptr<G4VPVParameterisation>> parameterisations_;

    static void RecordCreatedGeometryObject();
    static std::atomic<std::size_t> createdGeometryObjectCount_;
};
