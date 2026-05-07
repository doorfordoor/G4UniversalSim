#include "Geometry/VolumeBuilder.hh"

#include "Geometry/GeometryRegistry.hh"
#include "Geometry/GeometryUtils.hh"
#include "Geometry/VolumeNode.hh"
#include "Materials/MaterialManager.hh"
#include "Utils/G4NameUtils.hh"
#include "Utils/StringUtils.hh"

#include "G4Box.hh"
#include "G4Colour.hh"
#include "G4Cons.hh"
#include "G4Exception.hh"
#include "G4LogicalVolume.hh"
#include "G4Material.hh"
#include "G4Orb.hh"
#include "G4PVPlacement.hh"
#include "G4ProductionCuts.hh"
#include "G4Region.hh"
#include "G4RegionStore.hh"
#include "G4RotationMatrix.hh"
#include "G4Sphere.hh"
#include "G4ThreeVector.hh"
#include "G4Tubs.hh"
#include "G4VPhysicalVolume.hh"
#include "G4VisAttributes.hh"
#include "G4ios.hh"

#include <cmath>
#include <memory>
#include <stdexcept>

namespace {

constexpr double kZeroTolerance = 1.0e-12;

int ReadCopyNumber(const VolumeNode& node)
{
    if (!node.HasProperty("copyNo")) return 0;
    try {
        return std::stoi(node.GetProperty("copyNo"));
    } catch (...) {
        throw std::runtime_error("Volume '" + node.name + "' has invalid copyNo property: '" + node.GetProperty("copyNo") + "'");
    }
}

G4Colour ParseColour(const std::string& text)
{
    const std::string value = StringUtils::ToLower(StringUtils::Trim(text));
    if (value.empty() || value == "white") return G4Colour(1.0, 1.0, 1.0);
    if (value == "black") return G4Colour(0.0, 0.0, 0.0);
    if (value == "red") return G4Colour(1.0, 0.0, 0.0);
    if (value == "green") return G4Colour(0.0, 1.0, 0.0);
    if (value == "blue") return G4Colour(0.0, 0.0, 1.0);
    if (value == "yellow") return G4Colour(1.0, 1.0, 0.0);
    if (value == "cyan") return G4Colour(0.0, 1.0, 1.0);
    if (value == "magenta") return G4Colour(1.0, 0.0, 1.0);
    if (value == "gray" || value == "grey") return G4Colour(0.5, 0.5, 0.5);

    G4Exception(
        "VolumeBuilder::ApplyVisualAttributes",
        "AIHLGeometryVis001",
        JustWarning,
        ("Unknown visual color '" + text + "', using gray").c_str()
    );
    return G4Colour(0.5, 0.5, 0.5);
}

void ValidatePositive(double value, const std::string& label, const VolumeNode& node)
{
    if (value <= 0.0) {
        throw std::runtime_error("Volume '" + node.name + "' has non-positive " + label);
    }
}

}  // namespace

VolumeBuilder::VolumeBuilder() = default;
VolumeBuilder::~VolumeBuilder() = default;

void VolumeBuilder::SetMaterialManager(MaterialManager* materialManager)
{
    materialManager_ = materialManager;
}

void VolumeBuilder::SetRegistry(GeometryRegistry* registry)
{
    registry_ = registry;
}

void VolumeBuilder::SetCheckOverlaps(bool enable)
{
    checkOverlaps_ = enable;
}

bool VolumeBuilder::GetCheckOverlaps() const
{
    return checkOverlaps_;
}

void VolumeBuilder::SetDefaultWorldMaterial(const std::string& materialName)
{
    const std::string value = StringUtils::Trim(materialName);
    if (value.empty()) throw std::runtime_error("Default world material must not be empty");
    defaultWorldMaterial_ = value;
}

const std::string& VolumeBuilder::GetDefaultWorldMaterial() const
{
    return defaultWorldMaterial_;
}

void VolumeBuilder::Clear()
{
    rotations_.clear();
    visualAttributes_.clear();
}

G4VPhysicalVolume* VolumeBuilder::BuildWorld(const VolumeNode& rootNode)
{
    EnsureReady("build world");
    if (!rootNode.IsWorld()) {
        throw std::runtime_error("BuildWorld requires a world root node, got volume '" + rootNode.name + "' with parent '" + rootNode.parentName + "'");
    }

    G4LogicalVolume* worldLogical = BuildLogicalVolume(rootNode);
    G4VPhysicalVolume* worldPhysical = new G4PVPlacement(
        nullptr,
        G4ThreeVector(),
        worldLogical,
        G4NameUtils::PhysicalName(rootNode.name),
        nullptr,
        false,
        0,
        checkOverlaps_
    );
    if (!worldPhysical) throw std::runtime_error("Failed to create world physical volume for '" + rootNode.name + "'");

    registry_->RegisterPhysicalVolume(rootNode.name, worldPhysical);
    BuildChildren(rootNode, worldLogical);
    return worldPhysical;
}

G4LogicalVolume* VolumeBuilder::BuildLogicalVolume(const VolumeNode& node)
{
    EnsureReady("build logical volume");

    G4VSolid* solid = CreateSolid(node);
    if (!solid) throw std::runtime_error("Failed to create solid for volume '" + node.name + "'");

    std::string materialName = StringUtils::Trim(node.materialName);
    if (node.IsWorld() && materialName.empty()) materialName = defaultWorldMaterial_;
    if (materialName.empty()) {
        throw std::runtime_error("Volume '" + node.name + "' is missing materialName");
    }

    G4Material* material = nullptr;
    try {
        material = materialManager_->GetMaterial(materialName);
    } catch (const std::exception& e) {
        throw std::runtime_error("Failed to get material '" + materialName + "' for volume '" + node.name + "': " + e.what());
    }
    if (!material) {
        throw std::runtime_error("MaterialManager returned null material '" + materialName + "' for volume '" + node.name + "'");
    }

    G4LogicalVolume* logical = new G4LogicalVolume(solid, material, G4NameUtils::LogicalName(node.name));
    if (!logical) throw std::runtime_error("Failed to create logical volume for '" + node.name + "'");

    registry_->RegisterLogicalVolume(node.name, logical);
    if (node.sensitive) registry_->MarkSensitiveVolume(node.name);
    if (node.bias) registry_->MarkBiasVolume(node.name);
    CreateRegion(node, logical);
    ApplyVisualAttributes(node, logical);
    return logical;
}

G4VPhysicalVolume* VolumeBuilder::BuildVolume(const VolumeNode& node, G4LogicalVolume* motherLogical)
{
    EnsureReady("build physical volume");
    if (!motherLogical) throw std::runtime_error("Cannot build volume '" + node.name + "' with null mother logical volume");
    if (node.IsWorld()) throw std::runtime_error("BuildVolume cannot place world volume '" + node.name + "'");

    G4LogicalVolume* logical = BuildLogicalVolume(node);
    G4RotationMatrix* rotation = CreateRotation(node);
    const G4ThreeVector position(node.position.x, node.position.y, node.position.z);
    const int copyNo = ReadCopyNumber(node);

    G4VPhysicalVolume* physical = new G4PVPlacement(
        rotation,
        position,
        logical,
        G4NameUtils::PhysicalName(node.name),
        motherLogical,
        false,
        copyNo,
        checkOverlaps_
    );
    if (!physical) throw std::runtime_error("Failed to create physical volume for '" + node.name + "'");

    registry_->RegisterPhysicalVolume(node.name, physical);
    BuildChildren(node, logical);
    return physical;
}

G4VSolid* VolumeBuilder::CreateSolid(const VolumeNode& node)
{
    if (node.HasProperty("gdml_file") || node.GetProperty("template") == "gdml_placeholder" || node.GetProperty("source") == "gdml") {
        throw std::runtime_error("GDML geometry import is not implemented in VolumeBuilder yet for volume '" + node.name + "'");
    }

    switch (node.shape) {
        case VolumeShape::Box: return CreateBoxSolid(node);
        case VolumeShape::Tubs: return CreateTubsSolid(node);
        case VolumeShape::Sphere: return CreateSphereSolid(node);
        case VolumeShape::Orb: return CreateOrbSolid(node);
        case VolumeShape::Cone: return CreateConeSolid(node);
        default:
            throw std::runtime_error(
                "Unsupported shape for volume '" + node.name + "': shapeName='" + node.shapeName
                + "', parsed='" + GeometryUtils::ShapeToString(node.shape) + "'"
            );
    }
}

G4VSolid* VolumeBuilder::CreateBoxSolid(const VolumeNode& node)
{
    GeometryUtils::ValidateBoxSize(node.size);
    return new G4Box(
        G4NameUtils::SolidName(node.name),
        node.size.x * 0.5,
        node.size.y * 0.5,
        node.size.z * 0.5
    );
}

G4VSolid* VolumeBuilder::CreateTubsSolid(const VolumeNode& node)
{
    double rMin = 0.0;
    double rMax = 0.0;
    double halfZ = 0.0;
    double startPhi = 0.0;
    double deltaPhi = 0.0;

    if (node.parameters.size() >= 5) {
        rMin = node.parameters[0];
        rMax = node.parameters[1];
        halfZ = node.parameters[2];
        startPhi = node.parameters[3];
        deltaPhi = node.parameters[4];
    } else if (node.size.x > 0.0 && node.size.y > 0.0 && node.size.z > 0.0) {
        rMin = 0.0;
        rMax = node.size.x * 0.5;
        halfZ = node.size.z * 0.5;
        startPhi = 0.0;
        deltaPhi = CLHEP::twopi;
    } else {
        throw std::runtime_error("Volume '" + node.name + "' requires 5 tubs parameters or positive size shorthand");
    }

    GeometryUtils::ValidateTubsParameters(rMin, rMax, halfZ, startPhi, deltaPhi);
    return new G4Tubs(G4NameUtils::SolidName(node.name), rMin, rMax, halfZ, startPhi, deltaPhi);
}

G4VSolid* VolumeBuilder::CreateSphereSolid(const VolumeNode& node)
{
    if (node.parameters.size() < 6) {
        throw std::runtime_error("Volume '" + node.name + "' requires 6 sphere parameters: rMin,rMax,startPhi,deltaPhi,startTheta,deltaTheta");
    }
    const double rMin = node.parameters[0];
    const double rMax = node.parameters[1];
    const double startPhi = node.parameters[2];
    const double deltaPhi = node.parameters[3];
    const double startTheta = node.parameters[4];
    const double deltaTheta = node.parameters[5];
    if (rMin < 0.0 || rMax <= rMin) throw std::runtime_error("Volume '" + node.name + "' has invalid sphere radii");
    ValidatePositive(deltaPhi, "sphere deltaPhi", node);
    ValidatePositive(deltaTheta, "sphere deltaTheta", node);
    return new G4Sphere(G4NameUtils::SolidName(node.name), rMin, rMax, startPhi, deltaPhi, startTheta, deltaTheta);
}

G4VSolid* VolumeBuilder::CreateOrbSolid(const VolumeNode& node)
{
    const double radius = !node.parameters.empty() ? node.parameters[0] : node.size.x * 0.5;
    ValidatePositive(radius, "orb radius", node);
    return new G4Orb(G4NameUtils::SolidName(node.name), radius);
}

G4VSolid* VolumeBuilder::CreateConeSolid(const VolumeNode& node)
{
    if (node.parameters.size() < 7) {
        throw std::runtime_error("Volume '" + node.name + "' requires 7 cone parameters: rMin1,rMax1,rMin2,rMax2,halfZ,startPhi,deltaPhi");
    }
    const double rMin1 = node.parameters[0];
    const double rMax1 = node.parameters[1];
    const double rMin2 = node.parameters[2];
    const double rMax2 = node.parameters[3];
    const double halfZ = node.parameters[4];
    const double startPhi = node.parameters[5];
    const double deltaPhi = node.parameters[6];
    if (rMin1 < 0.0 || rMin2 < 0.0 || rMax1 <= rMin1 || rMax2 <= rMin2) {
        throw std::runtime_error("Volume '" + node.name + "' has invalid cone radii");
    }
    ValidatePositive(halfZ, "cone halfZ", node);
    ValidatePositive(deltaPhi, "cone deltaPhi", node);
    return new G4Cons(G4NameUtils::SolidName(node.name), rMin1, rMax1, rMin2, rMax2, halfZ, startPhi, deltaPhi);
}

G4RotationMatrix* VolumeBuilder::CreateRotation(const VolumeNode& node)
{
    if (std::abs(node.rotation.x) < kZeroTolerance
        && std::abs(node.rotation.y) < kZeroTolerance
        && std::abs(node.rotation.z) < kZeroTolerance) {
        return nullptr;
    }

    auto rotation = std::make_unique<G4RotationMatrix>();
    rotation->rotateX(node.rotation.x);
    rotation->rotateY(node.rotation.y);
    rotation->rotateZ(node.rotation.z);
    G4RotationMatrix* raw = rotation.get();
    rotations_.push_back(std::move(rotation));
    return raw;
}

void VolumeBuilder::CreateRegion(const VolumeNode& node, G4LogicalVolume* logicalVolume)
{
    if (!logicalVolume || node.regionName.empty()) return;
    const std::string regionName = StringUtils::Trim(node.regionName);
    if (regionName.empty()) {
        throw std::runtime_error("Volume '" + node.name + "' has empty regionName");
    }

    G4Region* region = G4RegionStore::GetInstance()->GetRegion(regionName, false);
    if (!region) region = new G4Region(regionName);
    region->AddRootLogicalVolume(logicalVolume);
    registry_->RegisterRegionName(node.name, regionName);

    if (!node.hasProductionCuts) return;

    auto* cuts = new G4ProductionCuts();
    const auto setCut = [&](double value, const char* particleName) {
        if (value < 0.0) return;
        if (value <= 0.0) {
            throw std::runtime_error(
                "Volume '" + node.name + "' has invalid production cut for " + std::string(particleName)
                + " in region '" + regionName + "'"
            );
        }
        cuts->SetProductionCut(value, particleName);
    };
    setCut(node.productionCuts.gamma, "gamma");
    setCut(node.productionCuts.electron, "e-");
    setCut(node.productionCuts.positron, "e+");
    setCut(node.productionCuts.proton, "proton");
    region->SetProductionCuts(cuts);
}

void VolumeBuilder::ApplyVisualAttributes(const VolumeNode& node, G4LogicalVolume* logicalVolume)
{
    if (!logicalVolume) return;

    auto vis = std::make_unique<G4VisAttributes>();
    vis->SetVisibility(node.visual.visible);
    if (!node.visual.visible) {
        logicalVolume->SetVisAttributes(vis.get());
        visualAttributes_.push_back(std::move(vis));
        return;
    }

    G4Colour colour = ParseColour(node.visual.color);
    colour.SetAlpha(node.visual.alpha);
    vis->SetColour(colour);
    if (node.visual.wireframe) vis->SetForceWireframe(true);
    logicalVolume->SetVisAttributes(vis.get());
    visualAttributes_.push_back(std::move(vis));
}

GeometryRegistry* VolumeBuilder::GetRegistry()
{
    return registry_;
}

const GeometryRegistry* VolumeBuilder::GetRegistry() const
{
    return registry_;
}

void VolumeBuilder::EnsureReady(const std::string& action) const
{
    if (!materialManager_) throw std::runtime_error("VolumeBuilder cannot " + action + ": MaterialManager is null");
    if (!registry_) throw std::runtime_error("VolumeBuilder cannot " + action + ": GeometryRegistry is null");
}

void VolumeBuilder::BuildChildren(const VolumeNode& parentNode, G4LogicalVolume* motherLogical)
{
    for (const VolumeNode& child : parentNode.children) {
        BuildVolume(child, motherLogical);
    }
}
