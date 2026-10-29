#include "G4SystemOfUnits.hh"
#include "Geometry/VolumeBuilder.hh"

#include "Geometry/GeometryRegistry.hh"
#include "Geometry/GeometryUtils.hh"
#include "Geometry/StlReader.hh"
#include "Geometry/VolumeNode.hh"
#include "Materials/MaterialManager.hh"
#include "Utils/G4NameUtils.hh"
#include "Utils/StringUtils.hh"
#include "Utils/UnitParser.hh"

#include "G4Box.hh"
#include "G4Colour.hh"
#include "G4Cons.hh"
#include "G4Ellipsoid.hh"
#include "G4EllipticalTube.hh"
#include "G4Hype.hh"
#include "G4Exception.hh"
#include "G4IntersectionSolid.hh"
#include "G4LogicalVolume.hh"
#include "G4Material.hh"
#include "G4Orb.hh"
#include "G4PVParameterised.hh"
#include "G4PVReplica.hh"
#include "G4Para.hh"
#include "G4Polycone.hh"
#include "G4Polyhedra.hh"
#include "G4VPVParameterisation.hh"
#include "G4PVPlacement.hh"
#include "G4ProductionCuts.hh"
#include "G4Region.hh"
#include "G4RegionStore.hh"
#include "G4RotationMatrix.hh"
#include "G4Sphere.hh"
#include "G4TessellatedSolid.hh"
#include "G4Torus.hh"
#include "G4TriangularFacet.hh"
#include "G4SubtractionSolid.hh"
#include "G4ThreeVector.hh"
#include "G4Transform3D.hh"
#include "G4Trap.hh"
#include "G4Trd.hh"
#include "G4Tubs.hh"
#include "G4UnionSolid.hh"
#include "G4VPhysicalVolume.hh"
#include "G4VisAttributes.hh"
#include "G4ios.hh"

#include <cmath>
#include <memory>
#include <stdexcept>

namespace {

constexpr double kZeroTolerance = 1.0e-12;

// One position, rotation and (optional) material per copy number.
class CopyTableParameterisation : public G4VPVParameterisation {
public:
    struct Copy {
        G4ThreeVector translation;
        G4RotationMatrix* rotation = nullptr;  // owned by rotations_
        G4Material* material = nullptr;        // nullptr = logical volume material
    };

    CopyTableParameterisation(std::vector<Copy> copies, std::vector<std::unique_ptr<G4RotationMatrix>> rotations)
        : copies_(std::move(copies)), rotations_(std::move(rotations))
    {
    }

    void ComputeTransformation(const G4int copyNo, G4VPhysicalVolume* physical) const override
    {
        const Copy& copy = copies_.at(static_cast<std::size_t>(copyNo));
        physical->SetTranslation(copy.translation);
        physical->SetRotation(copy.rotation);
    }

    G4Material* ComputeMaterial(const G4int copyNo, G4VPhysicalVolume* physical,
                                const G4VTouchable* touchable) override
    {
        const Copy& copy = copies_.at(static_cast<std::size_t>(copyNo));
        return copy.material ? copy.material : G4VPVParameterisation::ComputeMaterial(copyNo, physical, touchable);
    }

    std::size_t Size() const { return copies_.size(); }

private:
    std::vector<Copy> copies_;
    std::vector<std::unique_ptr<G4RotationMatrix>> rotations_;
};

// Several Geant4 solids cache GetCubicVolume() lazily in a member; the first
// concurrent calls from worker threads (dose mass, fluence volume) can read a
// partial sum. Fill the cache once on the master while building.
G4VSolid* PrecomputeVolume(G4VSolid* solid)
{
    if (solid) (void)solid->GetCubicVolume();
    return solid;
}

bool Close(double a, double b)
{
    return std::abs(a - b) <= 1e-9 * std::max({1.0, std::abs(a), std::abs(b)});
}

int ReadCopyNumber(const VolumeNode& node)
{
    const std::string rawCopyNoText = node.HasProperty("copyNo")
        ? node.GetProperty("copyNo")
        : node.GetProperty("copyno");
    const std::string copyNoText = StringUtils::Trim(rawCopyNoText);
    if (StringUtils::Trim(copyNoText).empty()) return 0;
    try {
        std::size_t consumed = 0;
        const int copyNo = std::stoi(copyNoText, &consumed);
        if (consumed != StringUtils::Trim(copyNoText).size()) {
            throw std::runtime_error("trailing text");
        }
        return copyNo;
    } catch (...) {
        throw std::runtime_error("Volume '" + node.name + "' has invalid copyNo property: '" + copyNoText + "'");
    }
}

std::string RequireProperty(const VolumeNode& node, const std::string& key)
{
    const std::string value = node.GetProperty(key);
    if (StringUtils::Trim(value).empty()) {
        throw std::runtime_error("Volume '" + node.name + "' is missing required key '" + key + "'");
    }
    return value;
}

double ReadLengthProperty(const VolumeNode& node, const std::string& key)
{
    double value = 0.0;
    try {
        value = UnitParser::ParseLength(RequireProperty(node, key));
    } catch (const std::exception& e) {
        throw std::runtime_error("Volume '" + node.name + "' has invalid length key '" + key + "': " + e.what());
    }
    if (value <= 0.0) {
        throw std::runtime_error("Volume '" + node.name + "' length key '" + key + "' must be > 0");
    }
    return value;
}

double ReadAngleProperty(const VolumeNode& node, const std::string& key)
{
    try {
        return UnitParser::ParseAngle(RequireProperty(node, key));
    } catch (const std::exception& e) {
        throw std::runtime_error("Volume '" + node.name + "' has invalid angle key '" + key + "': " + e.what());
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
    if (value == "aqua") return G4Colour(0.0, 1.0, 1.0);
    if (value == "magenta") return G4Colour(1.0, 0.0, 1.0);
    if (value == "gray" || value == "grey") return G4Colour(0.5, 0.5, 0.5);
    if (value == "darkgray") return G4Colour(0.25, 0.25, 0.25);
    if (value == "lime") return G4Colour(0.0, 1.0, 0.0);
    if (value == "brown") return G4Colour(0.6, 0.3, 0.1);

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

std::string BooleanToolContext(
    const std::string& ownerVolumeName,
    std::size_t booleanIndex,
    const BooleanOperand& operand
)
{
    return "Boolean tool creation failed for volume '" + ownerVolumeName
        + "', operation #" + std::to_string(booleanIndex)
        + ": shape=" + GeometryUtils::ShapeToString(operand.shape) + " ";
}

}  // namespace

std::atomic<std::size_t> VolumeBuilder::createdGeometryObjectCount_{0};

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
    inputEvidence_.clear();
    rotations_.clear();
    visualAttributes_.clear();
}

void VolumeBuilder::ResetCreatedGeometryObjectCount()
{
    createdGeometryObjectCount_.store(0);
}

std::size_t VolumeBuilder::GetCreatedGeometryObjectCount()
{
    return createdGeometryObjectCount_.load();
}

void VolumeBuilder::RecordCreatedGeometryObject()
{
    createdGeometryObjectCount_.fetch_add(1);
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
    RecordCreatedGeometryObject();
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
    RecordCreatedGeometryObject();
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
    if (node.placementType == PlacementType::Replica || node.placementType == PlacementType::Parameterised) {
        G4VPhysicalVolume* placed = node.placementType == PlacementType::Replica
            ? PlaceReplica(node, logical, motherLogical)
            : PlaceParameterised(node, logical, motherLogical);
        RecordCreatedGeometryObject();
        registry_->RegisterPhysicalVolume(node.name, placed);
        BuildChildren(node, logical);
        return placed;
    }
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
    RecordCreatedGeometryObject();
    if (!physical) throw std::runtime_error("Failed to create physical volume for '" + node.name + "'");

    registry_->RegisterPhysicalVolume(node.name, physical);
    BuildChildren(node, logical);
    return physical;
}

G4VSolid* VolumeBuilder::CreateSolid(const VolumeNode& node)
{
    G4VSolid* baseSolid = CreatePrimitiveSolid(node);
    if (!node.HasBooleanOperations()) return baseSolid;
    return ApplyBooleanOperations(node, baseSolid);
}

G4VSolid* VolumeBuilder::CreatePrimitiveSolid(const VolumeNode& node)
{
    if (node.HasProperty("gdml_file") || node.GetProperty("template") == "gdml_placeholder" || node.GetProperty("source") == "gdml") {
        throw std::runtime_error("GDML geometry is read by GeometryManager (template = gdml), not built per volume: '" + node.name + "'");
    }

    switch (node.shape) {
        case VolumeShape::Box: return CreateBoxSolid(node);
        case VolumeShape::Tubs: return CreateTubsSolid(node);
        case VolumeShape::Sphere: return CreateSphereSolid(node);
        case VolumeShape::Orb: return CreateOrbSolid(node);
        case VolumeShape::Cone: return CreateConeSolid(node);
        case VolumeShape::Trd: return CreateTrdSolid(node);
        case VolumeShape::Trap: return CreateTrapSolid(node);
        case VolumeShape::Ellipsoid: return PrecomputeVolume(CreateEllipsoidSolid(node));
        case VolumeShape::EllipticalTube: return PrecomputeVolume(CreateEllipticalTubeSolid(node));
        case VolumeShape::Torus: return PrecomputeVolume(CreateTorusSolid(node));
        case VolumeShape::Para: return PrecomputeVolume(CreateParaSolid(node));
        case VolumeShape::Hype: return PrecomputeVolume(CreateHypeSolid(node));
        case VolumeShape::Polycone: return PrecomputeVolume(CreatePolyconeSolid(node, false));
        case VolumeShape::Polyhedra: return PrecomputeVolume(CreatePolyconeSolid(node, true));
        case VolumeShape::Tessellated: return PrecomputeVolume(CreateTessellatedSolid(node));
        default:
            throw std::runtime_error(
                "Unsupported shape for volume '" + node.name + "': shapeName='" + node.shapeName
                + "', parsed='" + GeometryUtils::ShapeToString(node.shape) + "'"
            );
    }
}

G4VSolid* VolumeBuilder::CreatePrimitiveSolidFromOperand(
    const std::string& ownerVolumeName,
    std::size_t booleanIndex,
    const BooleanOperand& operand
)
{
    VolumeNode toolNode(ownerVolumeName + "_bool_" + std::to_string(booleanIndex) + "_tool");
    toolNode.shape = operand.shape;
    toolNode.shapeName = operand.shapeName;
    toolNode.size = operand.size;
    toolNode.parameters = operand.parameters;
    for (const auto& item : operand.properties) toolNode.SetProperty(item.first, item.second);

    try {
        switch (toolNode.shape) {
            case VolumeShape::Box:
                if (toolNode.size.x <= 0.0 || toolNode.size.y <= 0.0 || toolNode.size.z <= 0.0) {
                    throw std::runtime_error("box requires positive size x,y,z");
                }
                return CreateBoxSolid(toolNode);
            case VolumeShape::Tubs:
                if (toolNode.parameters.size() < 5) {
                    throw std::runtime_error("tubs requires 5 parameters: rMin,rMax,halfZ,startPhi,deltaPhi");
                }
                return CreateTubsSolid(toolNode);
            case VolumeShape::Sphere:
                if (toolNode.parameters.size() < 6) {
                    throw std::runtime_error("sphere requires 6 parameters: rMin,rMax,startPhi,deltaPhi,startTheta,deltaTheta");
                }
                return CreateSphereSolid(toolNode);
            case VolumeShape::Orb:
                if (toolNode.parameters.empty() && toolNode.size.x <= 0.0) {
                    throw std::runtime_error("orb requires parameters=radius or positive size.x shorthand");
                }
                return CreateOrbSolid(toolNode);
            case VolumeShape::Cone:
                if (toolNode.parameters.size() < 7) {
                    throw std::runtime_error("cone requires 7 parameters: rMin1,rMax1,rMin2,rMax2,halfZ,startPhi,deltaPhi");
                }
                return CreateConeSolid(toolNode);
            case VolumeShape::Trd:
                return CreateTrdSolid(toolNode);
            case VolumeShape::Trap:
                return CreateTrapSolid(toolNode);
            default:
                throw std::runtime_error("unsupported or missing boolean tool shape");
        }
    } catch (const std::exception& e) {
        throw std::runtime_error(BooleanToolContext(ownerVolumeName, booleanIndex, operand) + e.what());
    }
}

G4VSolid* VolumeBuilder::ApplyBooleanOperations(const VolumeNode& node, G4VSolid* baseSolid)
{
    if (!baseSolid) throw std::runtime_error("Cannot apply boolean operations to null base solid for volume '" + node.name + "'");

    if (node.booleanOperations.size() > 8) {
        G4Exception(
            "VolumeBuilder::ApplyBooleanOperations",
            "AIHLGeometryBoolean001",
            JustWarning,
            ("Volume '" + node.name + "' has " + std::to_string(node.booleanOperations.size())
             + " sequential boolean operations. Many sequential boolean operations may slow Geant4 navigation.").c_str()
        );
    }

    bool hasUnionOrIntersection = false;
    bool hasIntersection = false;
    for (const auto& op : node.booleanOperations) {
        hasUnionOrIntersection = hasUnionOrIntersection
            || op.operation == BooleanOperation::Union
            || op.operation == BooleanOperation::Intersection;
        hasIntersection = hasIntersection || op.operation == BooleanOperation::Intersection;
    }
    if (hasUnionOrIntersection) {
        G4Exception(
            "VolumeBuilder::ApplyBooleanOperations",
            "AIHLGeometryBoolean002",
            JustWarning,
            ("Volume '" + node.name + "' uses union/intersection boolean operations. "
             "Union/intersection boolean operations can make geometry interpretation and navigation more complex. "
             "Validate the geometry visually and with overlap checks.").c_str()
        );
    }
    if (hasIntersection) {
        G4Exception(
            "VolumeBuilder::ApplyBooleanOperations",
            "AIHLGeometryBoolean003",
            JustWarning,
            ("Volume '" + node.name + "' uses an intersection boolean operation. "
             "If the intersection region is empty or extremely small, initialization may succeed but tracking results may be meaningless.").c_str()
        );
    }

    G4VSolid* current = baseSolid;
    for (std::size_t i = 0; i < node.booleanOperations.size(); ++i) {
        const BooleanSolidOperation& op = node.booleanOperations[i];
        if (op.operation != BooleanOperation::Subtraction
            && op.operation != BooleanOperation::Union
            && op.operation != BooleanOperation::Intersection) {
            throw std::runtime_error(
                "Invalid boolean operation '" + GeometryUtils::BooleanOperationToString(op.operation)
                + "' for volume '" + node.name + "' at operation #" + std::to_string(i)
            );
        }

        G4VSolid* tool = CreatePrimitiveSolidFromOperand(node.name, i, op.tool);
        const G4Transform3D transform = MakeBooleanToolTransform(op.tool);
        const std::string operationText = GeometryUtils::BooleanOperationToString(op.operation);

        const std::string operationName = StringUtils::Trim(op.name).empty()
            ? node.name + "_bool_" + std::to_string(i) + "_" + operationText
            : node.name + "_bool_" + std::to_string(i) + "_" + op.name + "_" + operationText;

        G4cout << "[VolumeBuilder] Applying boolean " << operationText << ": volume=" << node.name
               << " index=" << i
               << " toolShape=" << GeometryUtils::ShapeToString(op.tool.shape)
               << " toolPosition=(" << op.tool.position.x << "," << op.tool.position.y << "," << op.tool.position.z << ")"
               << " toolRotation=(" << op.tool.rotation.x << "," << op.tool.rotation.y << "," << op.tool.rotation.z << ")"
               << G4endl;
        if (i == 0) {
            G4cout << "[VolumeBuilder] Boolean tool solids should slightly penetrate the base solid instead of sharing exactly coplanar boundaries." << G4endl;
        }

        const G4String solidName = G4NameUtils::SolidName(operationName);
        switch (op.operation) {
            case BooleanOperation::Subtraction:
                current = new G4SubtractionSolid(solidName, current, tool, transform);
                RecordCreatedGeometryObject();
                break;
            case BooleanOperation::Union:
                current = new G4UnionSolid(solidName, current, tool, transform);
                RecordCreatedGeometryObject();
                break;
            case BooleanOperation::Intersection:
                current = new G4IntersectionSolid(solidName, current, tool, transform);
                RecordCreatedGeometryObject();
                break;
            default:
                throw std::runtime_error(
                    "Invalid boolean operation '" + GeometryUtils::BooleanOperationToString(op.operation)
                    + "' for volume '" + node.name + "' at operation #" + std::to_string(i)
                );
        }
    }
    return current;
}

G4Transform3D VolumeBuilder::MakeBooleanToolTransform(const BooleanOperand& operand)
{
    G4RotationMatrix rotation;
    rotation.rotateX(operand.rotation.x);
    rotation.rotateY(operand.rotation.y);
    rotation.rotateZ(operand.rotation.z);
    const G4ThreeVector translation(operand.position.x, operand.position.y, operand.position.z);
    return G4Transform3D(rotation, translation);
}

G4VSolid* VolumeBuilder::CreateBoxSolid(const VolumeNode& node)
{
    GeometryUtils::ValidateBoxSize(node.size);
    auto* solid = new G4Box(
        G4NameUtils::SolidName(node.name),
        node.size.x * 0.5,
        node.size.y * 0.5,
        node.size.z * 0.5
    );
    RecordCreatedGeometryObject();
    return solid;
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
    auto* solid = new G4Tubs(G4NameUtils::SolidName(node.name), rMin, rMax, halfZ, startPhi, deltaPhi);
    RecordCreatedGeometryObject();
    return solid;
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
    auto* solid = new G4Sphere(G4NameUtils::SolidName(node.name), rMin, rMax, startPhi, deltaPhi, startTheta, deltaTheta);
    RecordCreatedGeometryObject();
    return solid;
}

G4VSolid* VolumeBuilder::CreateOrbSolid(const VolumeNode& node)
{
    const double radius = !node.parameters.empty() ? node.parameters[0] : node.size.x * 0.5;
    ValidatePositive(radius, "orb radius", node);
    auto* solid = new G4Orb(G4NameUtils::SolidName(node.name), radius);
    RecordCreatedGeometryObject();
    return solid;
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
    auto* solid = new G4Cons(G4NameUtils::SolidName(node.name), rMin1, rMax1, rMin2, rMax2, halfZ, startPhi, deltaPhi);
    RecordCreatedGeometryObject();
    return solid;
}

G4VSolid* VolumeBuilder::CreateTrdSolid(const VolumeNode& node)
{
    const double dx1 = ReadLengthProperty(node, "dx1");
    const double dx2 = ReadLengthProperty(node, "dx2");
    const double dy1 = ReadLengthProperty(node, "dy1");
    const double dy2 = ReadLengthProperty(node, "dy2");
    const double dz = ReadLengthProperty(node, "dz");
    auto* solid = new G4Trd(G4NameUtils::SolidName(node.name), dx1, dx2, dy1, dy2, dz);
    RecordCreatedGeometryObject();
    return solid;
}

G4VSolid* VolumeBuilder::CreateTrapSolid(const VolumeNode& node)
{
    const double dz = ReadLengthProperty(node, "dz");
    const double theta = ReadAngleProperty(node, "theta");
    const double phi = ReadAngleProperty(node, "phi");
    const double dy1 = ReadLengthProperty(node, "dy1");
    const double dx1 = ReadLengthProperty(node, "dx1");
    const double dx2 = ReadLengthProperty(node, "dx2");
    const double alpha1 = ReadAngleProperty(node, "alpha1");
    const double dy2 = ReadLengthProperty(node, "dy2");
    const double dx3 = ReadLengthProperty(node, "dx3");
    const double dx4 = ReadLengthProperty(node, "dx4");
    const double alpha2 = ReadAngleProperty(node, "alpha2");
    auto* solid = new G4Trap(
        G4NameUtils::SolidName(node.name),
        dz,
        theta,
        phi,
        dy1,
        dx1,
        dx2,
        alpha1,
        dy2,
        dx3,
        dx4,
        alpha2
    );
    RecordCreatedGeometryObject();
    return solid;
}

G4VSolid* VolumeBuilder::CreateEllipsoidSolid(const VolumeNode& node)
{
    const auto& p = node.parameters;
    if (p.size() != 3 && p.size() != 5) throw std::runtime_error("Volume '" + node.name + "' ellipsoid needs 3 or 5 parameters");
    auto* solid = new G4Ellipsoid(G4NameUtils::SolidName(node.name), p[0], p[1], p[2],
                                  p.size() == 5 ? p[3] : 0.0, p.size() == 5 ? p[4] : 0.0);
    RecordCreatedGeometryObject();
    return solid;
}

G4VSolid* VolumeBuilder::CreateEllipticalTubeSolid(const VolumeNode& node)
{
    const auto& p = node.parameters;
    if (p.size() != 3) throw std::runtime_error("Volume '" + node.name + "' eltube needs 3 parameters");
    auto* solid = new G4EllipticalTube(G4NameUtils::SolidName(node.name), p[0], p[1], p[2]);
    RecordCreatedGeometryObject();
    return solid;
}

G4VSolid* VolumeBuilder::CreateTorusSolid(const VolumeNode& node)
{
    const auto& p = node.parameters;
    if (p.size() != 5) throw std::runtime_error("Volume '" + node.name + "' torus needs 5 parameters");
    auto* solid = new G4Torus(G4NameUtils::SolidName(node.name), p[0], p[1], p[2], p[3], p[4]);
    RecordCreatedGeometryObject();
    return solid;
}

G4VSolid* VolumeBuilder::CreateParaSolid(const VolumeNode& node)
{
    const auto& p = node.parameters;
    if (p.size() != 6) throw std::runtime_error("Volume '" + node.name + "' para needs 6 parameters");
    auto* solid = new G4Para(G4NameUtils::SolidName(node.name), p[0], p[1], p[2], p[3], p[4], p[5]);
    RecordCreatedGeometryObject();
    return solid;
}

G4VSolid* VolumeBuilder::CreateHypeSolid(const VolumeNode& node)
{
    const auto& p = node.parameters;
    if (p.size() != 5) throw std::runtime_error("Volume '" + node.name + "' hype needs 5 parameters");
    auto* solid = new G4Hype(G4NameUtils::SolidName(node.name), p[0], p[1], p[2], p[3], p[4]);
    RecordCreatedGeometryObject();
    return solid;
}

G4VSolid* VolumeBuilder::CreatePolyconeSolid(const VolumeNode& node, bool polyhedra)
{
    const auto z = GeometryUtils::ParseParameterList(node.GetProperty("z_planes"));
    const auto rInner = GeometryUtils::ParseParameterList(node.GetProperty("r_inner"));
    const auto rOuter = GeometryUtils::ParseParameterList(node.GetProperty("r_outer"));
    if (z.size() < 2 || rInner.size() != z.size() || rOuter.size() != z.size()) {
        throw std::runtime_error("Volume '" + node.name + "' needs matching z_planes, r_inner and r_outer lists");
    }
    const auto& p = node.parameters;
    G4VSolid* solid = nullptr;
    if (polyhedra) {
        solid = new G4Polyhedra(G4NameUtils::SolidName(node.name), p[0], p[1], static_cast<G4int>(p[2]),
                                static_cast<G4int>(z.size()), z.data(), rInner.data(), rOuter.data());
    } else {
        solid = new G4Polycone(G4NameUtils::SolidName(node.name), p[0], p[1],
                               static_cast<G4int>(z.size()), z.data(), rInner.data(), rOuter.data());
    }
    RecordCreatedGeometryObject();
    return solid;
}

G4VSolid* VolumeBuilder::CreateTessellatedSolid(const VolumeNode& node)
{
    const std::string path = node.HasProperty("file.resolved") ? node.GetProperty("file.resolved") : node.GetProperty("file");
    const std::string unitText = StringUtils::Trim(node.GetProperty("file_unit", "mm"));
    const StlMesh mesh = StlReader::Read(path, UnitParser::ParseLength("1 " + unitText));
    auto* solid = new G4TessellatedSolid(G4NameUtils::SolidName(node.name));
    RecordCreatedGeometryObject();
    auto vertex = [&](int index) {
        const auto& v = mesh.vertices[static_cast<std::size_t>(index)];
        return G4ThreeVector(v[0], v[1], v[2]);
    };
    for (const auto& tri : mesh.triangles) {
        auto* facet = new G4TriangularFacet(vertex(tri[0]), vertex(tri[1]), vertex(tri[2]), ABSOLUTE);
        if (!facet->IsDefined() || !solid->AddFacet(facet)) {
            throw std::runtime_error("Volume '" + node.name + "' STL '" + path + "' has a facet Geant4 cannot use "
                                     "(degenerate or too small)");
        }
    }
    solid->SetSolidClosed(true);
    inputEvidence_.emplace_back(effective_config::Value::Object{{"object",node.name},{"path",mesh.inputPath},
      {"sha256",mesh.inputSha256},{"length_unit_internal",mesh.lengthUnit},{"format",mesh.binary?"binary_stl":"ascii_stl"},
      {"triangles",static_cast<std::int64_t>(mesh.triangles.size())},{"volume_mm3",mesh.volume/(mm*mm*mm)}});
    return solid;
}

G4VPhysicalVolume* VolumeBuilder::PlaceReplica(const VolumeNode& node, G4LogicalVolume* logical,
                                               G4LogicalVolume* motherLogical)
{
    const PlacementSpec& spec = node.placement;
    const std::string prefix = "Volume '" + node.name + "' placement=replica: ";
    if (motherLogical->GetNoDaughters() != 0) {
        throw std::runtime_error(prefix + "the mother must contain only the replica (Geant4 requirement); "
                                 "move other daughters into a separate mother volume");
    }
    const double total = spec.replicaWidth * spec.replicaCount;
    EAxis axis = kXAxis;
    double offset = 0.0;
    if (spec.replicaAxis == "phi") {
        const auto* mother = dynamic_cast<const G4Tubs*>(motherLogical->GetSolid());
        const auto* slice = dynamic_cast<const G4Tubs*>(logical->GetSolid());
        if (!mother || !slice) throw std::runtime_error(prefix + "replica_axis=phi needs a tubs mother and a tubs replica");
        if (!Close(total, mother->GetDeltaPhiAngle())) {
            throw std::runtime_error(prefix + "replica_count * replica_width must equal the mother's deltaPhi");
        }
        if (!Close(slice->GetInnerRadius(), mother->GetInnerRadius()) || !Close(slice->GetOuterRadius(), mother->GetOuterRadius()) ||
            !Close(slice->GetZHalfLength(), mother->GetZHalfLength()) || !Close(slice->GetDeltaPhiAngle(), spec.replicaWidth)) {
            throw std::runtime_error(prefix + "the replica tubs must have the mother's radii and halfZ and deltaPhi = replica_width");
        }
        // Geant4 rotates copy i to the centre of [offset + i*w, offset + (i+1)*w],
        // so the slice must be centred on phi = 0.
        if (!Close(slice->GetStartPhiAngle(), -0.5 * spec.replicaWidth)) {
            throw std::runtime_error(prefix + "the replica tubs must start at phi = -replica_width/2 (centred on phi = 0)");
        }
        offset = spec.hasReplicaOffset ? spec.replicaOffset : mother->GetStartPhiAngle();
        if (!Close(offset, mother->GetStartPhiAngle())) {
            throw std::runtime_error(prefix + "replica_offset must equal the mother's startPhi");
        }
        axis = kPhi;
    } else {
        const auto* mother = dynamic_cast<const G4Box*>(motherLogical->GetSolid());
        const auto* slice = dynamic_cast<const G4Box*>(logical->GetSolid());
        if (!mother || !slice) throw std::runtime_error(prefix + "replica_axis=" + spec.replicaAxis + " needs a box mother and a box replica");
        const double motherHalf[3] = {mother->GetXHalfLength(), mother->GetYHalfLength(), mother->GetZHalfLength()};
        const double sliceHalf[3] = {slice->GetXHalfLength(), slice->GetYHalfLength(), slice->GetZHalfLength()};
        const int index = spec.replicaAxis == "x" ? 0 : (spec.replicaAxis == "y" ? 1 : 2);
        if (!Close(total, 2.0 * motherHalf[index])) {
            throw std::runtime_error(prefix + "replica_count * replica_width must equal the mother's full length along " +
                                     spec.replicaAxis);
        }
        for (int k = 0; k < 3; ++k) {
            const double expected = k == index ? 0.5 * spec.replicaWidth : motherHalf[k];
            if (!Close(sliceHalf[k], expected)) {
                throw std::runtime_error(prefix + "the replica box must have the mother's size except replica_width along " +
                                         spec.replicaAxis);
            }
        }
        axis = index == 0 ? kXAxis : (index == 1 ? kYAxis : kZAxis);
    }
    return new G4PVReplica(G4NameUtils::PhysicalName(node.name), logical, motherLogical, axis,
                           spec.replicaCount, spec.replicaWidth, offset);
}

G4VPhysicalVolume* VolumeBuilder::PlaceParameterised(const VolumeNode& node, G4LogicalVolume* logical,
                                                     G4LogicalVolume* motherLogical)
{
    if (motherLogical->GetNoDaughters() != 0) {
        throw std::runtime_error("Volume '" + node.name + "' placement=parameterised: the mother must contain only "
                                 "the parameterised volume (Geant4 requirement)");
    }
    std::vector<CopyTableParameterisation::Copy> copies;
    std::vector<std::unique_ptr<G4RotationMatrix>> rotations;
    for (const ParameterisedCopy& source : node.placement.copies) {
        CopyTableParameterisation::Copy copy;
        copy.translation = G4ThreeVector(source.position.x, source.position.y, source.position.z);
        if (std::abs(source.rotation.x) > kZeroTolerance || std::abs(source.rotation.y) > kZeroTolerance ||
            std::abs(source.rotation.z) > kZeroTolerance) {
            auto rotation = std::make_unique<G4RotationMatrix>();
            rotation->rotateX(source.rotation.x);
            rotation->rotateY(source.rotation.y);
            rotation->rotateZ(source.rotation.z);
            copy.rotation = rotation.get();
            rotations.push_back(std::move(rotation));
        }
        if (!StringUtils::Trim(source.material).empty()) {
            try {
                copy.material = materialManager_->GetMaterial(StringUtils::Trim(source.material));
            } catch (const std::exception& error) {
                throw std::runtime_error("Volume '" + node.name + "' parameterised copy material '" + source.material +
                                         "': " + error.what());
            }
        }
        copies.push_back(copy);
    }
    auto parameterisation = std::make_unique<CopyTableParameterisation>(std::move(copies), std::move(rotations));
    const auto count = static_cast<G4int>(parameterisation->Size());
    auto* placed = new G4PVParameterised(G4NameUtils::PhysicalName(node.name), logical, motherLogical, kUndefined,
                                         count, parameterisation.get(), checkOverlaps_);
    parameterisations_.push_back(std::move(parameterisation));
    return placed;
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
    if (!region) {
        region = new G4Region(regionName);
        RecordCreatedGeometryObject();
    }
    region->AddRootLogicalVolume(logicalVolume);
    registry_->RegisterRegionName(node.name, regionName);

    if (!node.hasProductionCuts) return;

    auto* cuts = new G4ProductionCuts();
    RecordCreatedGeometryObject();
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
