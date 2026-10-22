#include "Geometry/GeometryManager.hh"

#include "Geometry/GeometryUtils.hh"
#include "Materials/MaterialManager.hh"
#include "Templates/GeometryTemplate.hh"
#include "Templates/TemplateFactory.hh"
#include "Utils/FileUtils.hh"
#include "Utils/StringUtils.hh"

#include "G4VPhysicalVolume.hh"
#include "G4ios.hh"

#include "Geometry/GdmlIO.hh"
#include "Utils/G4NameUtils.hh"
#include "G4LogicalVolume.hh"
#include "G4LogicalVolumeStore.hh"
#include "G4ProductionCuts.hh"
#include "G4Region.hh"
#include "G4RegionStore.hh"
#include "G4UserLimits.hh"
#include "Physics/PhysicsManager.hh"

#include <cfloat>

#include <algorithm>
#include <functional>
#include <set>
#include <stdexcept>

namespace {

void CollectRegions(const VolumeNode& node, std::set<std::string>& regions)
{
    if (!node.regionName.empty()) regions.insert(node.regionName);
    for (const VolumeNode& child : node.children) CollectRegions(child, regions);
}

bool Close(double a, double b)
{
    return std::abs(a - b) <= 1e-9 * std::max({1.0, std::abs(a), std::abs(b)});
}

// Same rules as VolumeBuilder::PlaceReplica, checked before any Geant4
// geometry object is created.
void ValidateReplicaAgainstMother(const VolumeNode& mother, const VolumeNode& replica)
{
    const PlacementSpec& spec = replica.placement;
    const std::string prefix = "Geometry volume '" + replica.name + "' placement=replica in mother '" + mother.name + "': ";
    if (mother.children.size() != 1) {
        throw std::runtime_error(prefix + "the mother must contain only the replica (Geant4 requirement); "
                                 "move other daughters into a separate mother volume");
    }
    if (mother.HasBooleanOperations() || replica.HasBooleanOperations()) {
        throw std::runtime_error(prefix + "boolean solids cannot be replicated; use placement=parameterised");
    }
    const double total = spec.replicaWidth * spec.replicaCount;
    if (spec.replicaAxis == "phi") {
        if (mother.shape != VolumeShape::Tubs || replica.shape != VolumeShape::Tubs ||
            mother.parameters.size() != 5 || replica.parameters.size() != 5) {
            throw std::runtime_error(prefix + "replica_axis=phi needs a tubs mother and a tubs replica");
        }
        const auto& m = mother.parameters;
        const auto& r = replica.parameters;
        if (!Close(total, m[4])) throw std::runtime_error(prefix + "replica_count * replica_width must equal the mother's deltaPhi");
        if (!Close(r[0], m[0]) || !Close(r[1], m[1]) || !Close(r[2], m[2]) || !Close(r[4], spec.replicaWidth)) {
            throw std::runtime_error(prefix + "the replica tubs must have the mother's radii and halfZ and deltaPhi = replica_width");
        }
        if (!Close(r[3], -0.5 * spec.replicaWidth)) {
            throw std::runtime_error(prefix + "the replica tubs must start at phi = -replica_width/2 (centred on phi = 0)");
        }
        if (spec.hasReplicaOffset && !Close(spec.replicaOffset, m[3])) {
            throw std::runtime_error(prefix + "replica_offset must equal the mother's startPhi");
        }
        return;
    }
    if (mother.shape != VolumeShape::Box || replica.shape != VolumeShape::Box) {
        throw std::runtime_error(prefix + "replica_axis=" + spec.replicaAxis + " needs a box mother and a box replica");
    }
    const double motherSize[3] = {mother.size.x, mother.size.y, mother.size.z};
    const double sliceSize[3] = {replica.size.x, replica.size.y, replica.size.z};
    const int index = spec.replicaAxis == "x" ? 0 : (spec.replicaAxis == "y" ? 1 : 2);
    if (!Close(total, motherSize[index])) {
        throw std::runtime_error(prefix + "replica_count * replica_width must equal the mother's full length along " + spec.replicaAxis);
    }
    for (int k = 0; k < 3; ++k) {
        const double expected = k == index ? spec.replicaWidth : motherSize[k];
        if (!Close(sliceSize[k], expected)) {
            throw std::runtime_error(prefix + "the replica box must have the mother's size except replica_width along " +
                                     spec.replicaAxis);
        }
    }
}

void ValidateNodeRecursive(const VolumeNode& node, bool isRoot)
{
    GeometryUtils::ValidateVolumeName(node.name);
    if (node.placementType == PlacementType::Assembly) {
        throw std::runtime_error(
            "Geometry volume '" + node.name + "' requests placement=assembly, but this capability is not"
            " supported. Use placement=normal with explicit child volumes or placement=parameterised."
        );
    }
    if (node.placementType == PlacementType::Replica && node.placement.replicaCount < 1) {
        throw std::runtime_error("Geometry volume '" + node.name + "' placement=replica has no replica_count");
    }
    if (node.placementType == PlacementType::Parameterised && node.placement.copies.empty()) {
        throw std::runtime_error("Geometry volume '" + node.name + "' placement=parameterised has no copies");
    }
    if (!isRoot && node.parentName.empty()) {
        throw std::runtime_error("Non-world volume '" + node.name + "' has empty parentName");
    }
    if (node.shape == VolumeShape::Unknown) {
        throw std::runtime_error("Volume '" + node.name + "' has unsupported shape '" + node.shapeName + "'");
    }
    if (!(isRoot && node.materialName.empty())) {
        if (StringUtils::Trim(node.materialName).empty()) {
            throw std::runtime_error("Volume '" + node.name + "' is missing materialName");
        }
    }
    if (node.shape == VolumeShape::Box) GeometryUtils::ValidateBoxSize(node.size);
    if (node.shape == VolumeShape::Tubs && node.parameters.size() >= 5) {
        GeometryUtils::ValidateTubsParameters(node.parameters[0], node.parameters[1], node.parameters[2], node.parameters[3], node.parameters[4]);
    }
    if (node.hasProductionCuts) {
        const auto check = [&](double value, const std::string& name) {
            if (value == 0.0 || value < -1.0) {
                throw std::runtime_error("Volume '" + node.name + "' has invalid production cut '" + name + "'");
            }
        };
        check(node.productionCuts.gamma, "gamma");
        check(node.productionCuts.electron, "e-");
        check(node.productionCuts.positron, "e+");
        check(node.productionCuts.proton, "proton");
    }
    for (const BooleanSolidOperation& op : node.booleanOperations) {
        const std::string opName = op.name.empty() ? "<unnamed>" : op.name;
        if (op.operation == BooleanOperation::None) {
            throw std::runtime_error("Volume '" + node.name + "' has boolean operation '" + opName + "' with operation=none");
        }
        if (op.tool.shape == VolumeShape::Unknown) {
            throw std::runtime_error("Volume '" + node.name + "' has boolean operation '" + opName + "' with unsupported tool shape");
        }
        if (op.tool.shape == VolumeShape::Box) GeometryUtils::ValidateBoxSize(op.tool.size);
        if (op.tool.shape == VolumeShape::Tubs) {
            if (op.tool.parameters.size() < 5) {
                throw std::runtime_error("Volume '" + node.name + "' boolean operation '" + opName + "' requires 5 tubs parameters");
            }
            GeometryUtils::ValidateTubsParameters(
                op.tool.parameters[0],
                op.tool.parameters[1],
                op.tool.parameters[2],
                op.tool.parameters[3],
                op.tool.parameters[4]
            );
        }
    }
    for (const VolumeNode& child : node.children) {
        if (child.placementType == PlacementType::Replica) ValidateReplicaAgainstMother(node, child);
        if (child.placementType == PlacementType::Parameterised && node.children.size() != 1) {
            throw std::runtime_error("Geometry volume '" + child.name + "' placement=parameterised in mother '" + node.name +
                                     "': the mother must contain only the parameterised volume (Geant4 requirement); "
                                     "put it in its own container volume");
        }
        ValidateNodeRecursive(child, false);
    }
}

std::string NormalizeVolumeKey(const std::string& name)
{
    return StringUtils::ToLower(StringUtils::Trim(name));
}

std::string UserVolumeContext(const std::string& functionName, const VolumeNode& node)
{
    return functionName + " volume='" + node.name
        + "' parent='" + node.parentName
        + "' shape='" + GeometryUtils::ShapeToString(node.shape)
        + "' material='" + node.materialName + "': ";
}

}  // namespace

GeometryManager::GeometryManager()
{
    volumeBuilder_.SetRegistry(&registry_);
    volumeBuilder_.SetCheckOverlaps(checkOverlaps_);
    volumeBuilder_.SetDefaultWorldMaterial(defaultWorldMaterial_);
}

GeometryManager::~GeometryManager() = default;

void GeometryManager::SetMaterialManager(MaterialManager* materialManager)
{
    materialManager_ = materialManager;
    volumeBuilder_.SetMaterialManager(materialManager);
}

MaterialManager* GeometryManager::GetMaterialManager() const
{
    return materialManager_;
}

void GeometryManager::SetTemplate(const std::string& templateName)
{
    const std::string value = StringUtils::Trim(templateName);
    if (value.empty()) throw std::runtime_error("Geometry template name must not be empty");
    if (StringUtils::ToLower(value) == "gdml" && !GdmlIO::Available()) {
        throw std::runtime_error(
            "Geometry capability 'GDML' is not available in this build (Geant4 without GDML/XercesC). "
            "Use a supported geometry template and regular volume definitions instead."
        );
    }
    (void)TemplateFactory::Create(value); // Validate early and keep creation deferred to LoadGeometryConfig.
    templateName_ = value;
    MarkDirty();
}

const std::string& GeometryManager::GetTemplateName() const
{
    return templateName_;
}

void GeometryManager::LoadGeometryConfig(const std::string& filename)
{
    if (!FileUtils::Exists(filename)) {
        throw std::runtime_error("Geometry config file does not exist: '" + filename + "'");
    }

    VolumeBuilder::ResetCreatedGeometryObjectCount();
    configDiagnostics_.clear();
    auto geometryTemplate = TemplateFactory::Create(templateName_);
    VolumeNode root;
    try {
        root = geometryTemplate->BuildNodesFromFile(filename);
        configDiagnostics_ = geometryTemplate->GetDiagnostics();
        ValidateRootNode(root);
    } catch (const std::exception& error) {
        if (configDiagnostics_.empty()) configDiagnostics_ = geometryTemplate->GetDiagnostics();
        throw std::runtime_error(
            std::string(error.what()) + "; created_geometry_object_count="
            + std::to_string(VolumeBuilder::GetCreatedGeometryObjectCount())
        );
    }
    templateRootNode_ = std::make_unique<VolumeNode>(root);
    rootNode_ = std::make_unique<VolumeNode>(root);
    if (!preserveUserVolumesOnLoad_) {
        userAddedVolumes_.clear();
    } else {
        ApplyUserAddedVolumes();
    }
    geometryConfigFile_ = filename;
    MarkDirty();
}

const std::string& GeometryManager::GetGeometryConfigFile() const
{
    return geometryConfigFile_;
}

const std::vector<GeometryConfigDiagnostic>& GeometryManager::GetConfigDiagnostics() const
{
    return configDiagnostics_;
}

void GeometryManager::SetCheckOverlaps(bool enable)
{
    if (checkOverlapsLocked_) {
        G4cout << "[GeometryManager] Ignoring check-overlaps change because an explicit CLI option is active.\n";
        return;
    }
    checkOverlaps_ = enable;
    volumeBuilder_.SetCheckOverlaps(enable);
    MarkDirty();
}

void GeometryManager::SetCheckOverlapsLocked(bool locked)
{
    checkOverlapsLocked_ = locked;
}

bool GeometryManager::IsCheckOverlapsLocked() const
{
    return checkOverlapsLocked_;
}

bool GeometryManager::GetCheckOverlaps() const
{
    return checkOverlaps_;
}

void GeometryManager::SetDefaultWorldMaterial(const std::string& materialName)
{
    const std::string value = StringUtils::Trim(materialName);
    if (value.empty()) throw std::runtime_error("Default world material must not be empty");
    defaultWorldMaterial_ = value;
    volumeBuilder_.SetDefaultWorldMaterial(value);
    MarkDirty();
}

const std::string& GeometryManager::GetDefaultWorldMaterial() const
{
    return defaultWorldMaterial_;
}

void GeometryManager::SetRootNode(const VolumeNode& rootNode)
{
    ValidateRootNode(rootNode);
    templateRootNode_ = std::make_unique<VolumeNode>(rootNode);
    rootNode_ = std::make_unique<VolumeNode>(rootNode);
    if (preserveUserVolumesOnLoad_) ApplyUserAddedVolumes();
    MarkDirty();
}

const VolumeNode& GeometryManager::GetRootNode() const
{
    if (!rootNode_) throw std::runtime_error("Geometry root node is not set");
    return *rootNode_;
}

bool GeometryManager::HasRootNode() const
{
    return static_cast<bool>(rootNode_);
}

void GeometryManager::AddVolume(const VolumeNode& node)
{
    if (!rootNode_) throw std::runtime_error("GeometryManager::AddVolume failed: rootNode_ is not set");
    ValidateUserVolume(node);
    if (!FindNode(*rootNode_, node.parentName)) {
        throw std::runtime_error(UserVolumeContext("GeometryManager::AddVolume", node) + "parent volume does not exist in current tree");
    }
    if (TreeContainsName(*rootNode_, node.name)) {
        throw std::runtime_error(UserVolumeContext("GeometryManager::AddVolume", node) + "volume name already exists in current tree");
    }
    if (HasUserAddedVolume(node.name)) {
        throw std::runtime_error(UserVolumeContext("GeometryManager::AddVolume", node) + "volume name already exists in user-added volumes");
    }

    userAddedVolumes_.push_back(node);
    AppendChildToParent(*rootNode_, node);
    MarkDirty();
    PrintReinitializeHint();
}

void GeometryManager::AddBoxVolume(
    const std::string& name,
    const std::string& parentName,
    const std::string& materialName,
    const Vec3& size,
    const Vec3& position,
    const Rotation3& rotation,
    bool sensitive,
    bool bias,
    const std::string& regionName
)
{
    VolumeNode node(name);
    node.parentName = parentName;
    node.materialName = materialName;
    node.shape = VolumeShape::Box;
    node.shapeName = "box";
    node.size = size;
    node.position = position;
    node.rotation = rotation;
    node.sensitive = sensitive;
    node.bias = bias;
    node.regionName = regionName;
    AddVolume(node);
}

void GeometryManager::AddTubsVolume(
    const std::string& name,
    const std::string& parentName,
    const std::string& materialName,
    double rMin,
    double rMax,
    double halfZ,
    double startPhi,
    double deltaPhi,
    const Vec3& position,
    const Rotation3& rotation,
    bool sensitive,
    bool bias,
    const std::string& regionName
)
{
    VolumeNode node(name);
    node.parentName = parentName;
    node.materialName = materialName;
    node.shape = VolumeShape::Tubs;
    node.shapeName = "tubs";
    node.parameters = {rMin, rMax, halfZ, startPhi, deltaPhi};
    node.position = position;
    node.rotation = rotation;
    node.sensitive = sensitive;
    node.bias = bias;
    node.regionName = regionName;
    AddVolume(node);
}

bool GeometryManager::RemoveUserVolume(const std::string& name)
{
    const std::string key = NormalizeVolumeKey(name);
    const auto it = std::find_if(userAddedVolumes_.begin(), userAddedVolumes_.end(), [&](const VolumeNode& node) {
        return NormalizeVolumeKey(node.name) == key;
    });
    if (it == userAddedVolumes_.end()) {
        G4cout << "[GeometryManager] RemoveUserVolume: '" << name << "' is not a user-added volume." << G4endl;
        return false;
    }

    const std::string removedName = it->name;
    userAddedVolumes_.erase(it);
    if (rootNode_) RemoveNodeFromTree(*rootNode_, removedName);
    MarkDirty();
    PrintReinitializeHint();
    return true;
}

void GeometryManager::ClearUserAddedVolumes()
{
    const std::vector<std::string> names = GetUserAddedVolumeNames();
    userAddedVolumes_.clear();
    if (templateRootNode_) {
        rootNode_ = std::make_unique<VolumeNode>(*templateRootNode_);
    } else if (rootNode_) {
        // No template copy exists; remove the recorded user subtrees from the current tree.
        for (const std::string& name : names) RemoveNodeFromTree(*rootNode_, name);
        ValidateRootNode(*rootNode_);
    }
    MarkDirty();
    PrintReinitializeHint();
}

std::vector<VolumeNode> GeometryManager::GetUserAddedVolumes() const
{
    return userAddedVolumes_;
}

std::vector<std::string> GeometryManager::GetUserAddedVolumeNames() const
{
    std::vector<std::string> names;
    names.reserve(userAddedVolumes_.size());
    for (const VolumeNode& node : userAddedVolumes_) names.push_back(node.name);
    return names;
}

void GeometryManager::SetPreserveUserVolumesOnLoad(bool preserve)
{
    if (preserveUserVolumesOnLoad_ == preserve) return;
    preserveUserVolumesOnLoad_ = preserve;
    if (!preserve) {
        userAddedVolumes_.clear();
        if (templateRootNode_) rootNode_ = std::make_unique<VolumeNode>(*templateRootNode_);
        MarkDirty();
        PrintReinitializeHint();
    } else if (rootNode_) {
        ApplyUserAddedVolumes();
    }
}

bool GeometryManager::GetPreserveUserVolumesOnLoad() const
{
    return preserveUserVolumesOnLoad_;
}

void GeometryManager::ApplyUserAddedVolumes()
{
    if (!rootNode_) throw std::runtime_error("GeometryManager::ApplyUserAddedVolumes failed: rootNode_ is not set");
    if (userAddedVolumes_.empty()) return;

    for (const VolumeNode& node : userAddedVolumes_) {
        ValidateUserVolume(node);
        if (TreeContainsName(*rootNode_, node.name)) {
            throw std::runtime_error(UserVolumeContext("GeometryManager::ApplyUserAddedVolumes", node) + "volume name already exists in current tree");
        }
        AppendChildToParent(*rootNode_, node);
    }
    MarkDirty();
}

bool GeometryManager::HasVolumeInCurrentTree(const std::string& name) const
{
    return rootNode_ && TreeContainsName(*rootNode_, name);
}

bool GeometryManager::HasUserAddedVolume(const std::string& name) const
{
    const std::string key = NormalizeVolumeKey(name);
    return std::any_of(userAddedVolumes_.begin(), userAddedVolumes_.end(), [&](const VolumeNode& node) {
        return NormalizeVolumeKey(node.name) == key;
    });
}

void GeometryManager::PrintUserAddedVolumes() const
{
    G4cout << "[GeometryManager] user-added volumes: " << userAddedVolumes_.size() << G4endl;
    for (const VolumeNode& node : userAddedVolumes_) {
        G4cout << "  - " << node.name
               << " parent=" << node.parentName
               << " shape=" << node.ShapeAsString()
               << " material=" << node.materialName
               << " sensitive=" << (node.sensitive ? "true" : "false")
               << " bias=" << (node.bias ? "true" : "false")
               << " region=" << (node.regionName.empty() ? "<none>" : node.regionName)
               << G4endl;
    }
}

void GeometryManager::MarkDirty()
{
    dirty_ = true;
}

void GeometryManager::ClearDirty()
{
    dirty_ = false;
}

bool GeometryManager::IsDirty() const
{
    return dirty_;
}

G4VPhysicalVolume* GeometryManager::BuildWorld()
{
    if (!materialManager_) throw std::runtime_error("GeometryManager cannot build world: MaterialManager is null");
    if (!rootNode_) throw std::runtime_error("GeometryManager cannot build world: root node is not set");

    ValidateRootNode(*rootNode_);
    VolumeBuilder::ResetCreatedGeometryObjectCount();
    registry_.Clear();
    volumeBuilder_.Clear();
    volumeBuilder_.SetMaterialManager(materialManager_);
    volumeBuilder_.SetRegistry(&registry_);
    volumeBuilder_.SetCheckOverlaps(checkOverlaps_);
    volumeBuilder_.SetDefaultWorldMaterial(defaultWorldMaterial_);

    if (rootNode_->GetProperty("template") == "gdml") {
        G4VPhysicalVolume* world = BuildGdmlWorld(*rootNode_);
        ApplyRegionPhysics();
        ClearDirty();
        return world;
    }

    G4VPhysicalVolume* world = volumeBuilder_.BuildWorld(*rootNode_);
    if (!world) throw std::runtime_error("GeometryManager BuildWorld returned null world physical volume");
    ApplyRegionPhysics();
    ClearDirty();
    return world;
}

void GeometryManager::SetPhysicsManager(const PhysicsManager* physicsManager)
{
    physicsManager_ = physicsManager;
}

void GeometryManager::ApplyRegionPhysics()
{
    if (!physicsManager_) return;
    for (const auto& item : physicsManager_->GetRegionPhysics()) {
        const std::string& name = item.first;
        const RegionPhysicsSettings& settings = item.second;
        const std::string context = "[physics.region." + name + "]: ";
        G4Region* region = G4RegionStore::GetInstance()->GetRegion(name, false);
        if (!region && settings.volumes.empty()) {
            std::string available;
            for (const G4Region* existing : *G4RegionStore::GetInstance()) {
                available += (available.empty() ? "" : ", ") + std::string(existing->GetName());
            }
            throw std::runtime_error(context + "region '" + name + "' does not exist in the geometry; set region = " + name +
                                     " on a geometry volume or list its logical volumes in volumes = ... "
                                     "(existing regions: " + available + ")");
        }
        const bool created = region == nullptr;
        if (created) region = new G4Region(name);
        for (const std::string& volume : settings.volumes) {
            G4LogicalVolume* logical = G4LogicalVolumeStore::GetInstance()->GetVolume(volume, false);
            if (!logical) logical = G4LogicalVolumeStore::GetInstance()->GetVolume(volume + "_LV", false);
            if (!logical) throw std::runtime_error(context + "volumes names unknown logical volume '" + volume + "'");
            if (logical->GetRegion() && logical->IsRootRegion() && logical->GetRegion() != region) {
                throw std::runtime_error(context + "logical volume '" + volume + "' is already the root of region '" +
                                         std::string(logical->GetRegion()->GetName()) + "'");
            }
            region->AddRootLogicalVolume(logical);
        }
        if (!settings.cuts.empty()) {
            if (!created && region->GetProductionCuts()) {
                throw std::runtime_error(context + "region '" + name + "' already has production cuts from geometry "
                                         "volume cut.* fields; set the cuts in one place only");
            }
            auto* cuts = new G4ProductionCuts();
            cuts->SetProductionCut(physicsManager_->GetDefaultCut());
            for (const auto& cut : settings.cuts) cuts->SetProductionCut(cut.second, cut.first);
            region->SetProductionCuts(cuts);
        }
        if (settings.HasUserLimits()) {
            region->SetUserLimits(new G4UserLimits(
                settings.maxStep > 0.0 ? settings.maxStep : DBL_MAX,
                settings.maxTrackLength > 0.0 ? settings.maxTrackLength : DBL_MAX,
                settings.maxTime > 0.0 ? settings.maxTime : DBL_MAX,
                settings.minKineticEnergy));
        }
    }
}

bool GeometryManager::HasConfiguredVolume(const std::string& name) const
{
    if (!rootNode_ || rootNode_->GetProperty("template") == "gdml") return true;
    const std::function<bool(const VolumeNode&)> visit = [&](const VolumeNode& node) {
        if (node.name == name || G4NameUtils::LogicalName(node.name) == name) return true;
        for (const VolumeNode& child : node.children) {
            if (visit(child)) return true;
        }
        return false;
    };
    return visit(*rootNode_);
}

void GeometryManager::ValidateRegionPhysicsNames() const
{
    if (!physicsManager_ || !rootNode_ || rootNode_->GetProperty("template") == "gdml") return;
    const std::vector<std::string> regions = GetRegionNames();
    for (const auto& item : physicsManager_->GetRegionPhysics()) {
        if (!item.second.volumes.empty()) continue;
        if (std::find(regions.begin(), regions.end(), item.first) != regions.end()) continue;
        std::string available;
        for (const std::string& region : regions) available += (available.empty() ? "" : ", ") + region;
        throw std::runtime_error("[physics.region." + item.first + "]: region '" + item.first +
                                 "' does not exist in the geometry; set region = " + item.first +
                                 " on a geometry volume or list its logical volumes in volumes = ... "
                                 "(geometry regions: " + (available.empty() ? std::string("none") : available) + ")");
    }
}

G4VPhysicalVolume* GeometryManager::BuildGdmlWorld(const VolumeNode& root)
{
    const std::string file = root.GetProperty("gdml_file");
    const GdmlIO::ImportResult imported = GdmlIO::Read(file, root.GetProperty("gdml_validate") == "true", checkOverlaps_);
    registry_.RegisterPhysicalVolume(imported.world->GetName(), imported.world);
    std::string available;
    for (G4LogicalVolume* logical : *G4LogicalVolumeStore::GetInstance()) {
        available += (available.empty() ? "" : ", ") + std::string(logical->GetName());
    }
    const auto mark = [&](const std::string& key, bool sensitive) {
        for (const std::string& part : StringUtils::Split(root.GetProperty(key), ',')) {
            const std::string name = StringUtils::Trim(part);
            if (name.empty()) continue;
            G4LogicalVolume* logical = G4LogicalVolumeStore::GetInstance()->GetVolume(name, false);
            if (!logical) {
                throw std::runtime_error("[gdml]/" + key + " names logical volume '" + name + "' which is not in '" +
                                         file + "'; available logical volumes: " + available);
            }
            if (!registry_.HasLogicalVolume(name)) registry_.RegisterLogicalVolume(name, logical);
            if (sensitive) registry_.MarkSensitiveVolume(name);
            else registry_.MarkBiasVolume(name);
        }
    };
    mark("sensitive_volumes", true);
    mark("bias_volumes", false);
    for (G4LogicalVolume* logical : imported.auxSensitive) {
        const std::string name = logical->GetName();
        if (!registry_.HasLogicalVolume(name)) registry_.RegisterLogicalVolume(name, logical);
        registry_.MarkSensitiveVolume(name);
    }
    return imported.world;
}

GeometryRegistry& GeometryManager::GetRegistry()
{
    return registry_;
}

const GeometryRegistry& GeometryManager::GetRegistry() const
{
    return registry_;
}

VolumeBuilder& GeometryManager::GetVolumeBuilder()
{
    return volumeBuilder_;
}

const VolumeBuilder& GeometryManager::GetVolumeBuilder() const
{
    return volumeBuilder_;
}

std::vector<std::string> GeometryManager::GetSensitiveVolumeNames() const
{
    return registry_.GetSensitiveVolumeNames();
}

std::vector<std::string> GeometryManager::GetBiasVolumeNames() const
{
    return registry_.GetBiasVolumeNames();
}

std::vector<std::string> GeometryManager::GetRegionNames() const
{
    std::set<std::string> regions;
    if (rootNode_) CollectRegions(*rootNode_, regions);
    return {regions.begin(), regions.end()};
}

void GeometryManager::PrintSummary() const
{
    G4cout << "[GeometryManager] template=" << templateName_
           << ", config=" << (geometryConfigFile_.empty() ? "<none>" : geometryConfigFile_)
           << ", hasRoot=" << (rootNode_ ? "true" : "false")
           << ", dirty=" << (dirty_ ? "true" : "false")
           << ", checkOverlaps=" << (checkOverlaps_ ? "true" : "false")
           << ", defaultWorldMaterial=" << defaultWorldMaterial_
           << ", userAddedVolumes=" << userAddedVolumes_.size()
           << ", preserveUserVolumesOnLoad=" << (preserveUserVolumesOnLoad_ ? "true" : "false")
           << G4endl;
    registry_.PrintSummary();
}

void GeometryManager::PrintTree() const
{
    if (!rootNode_) {
        G4cout << "[GeometryManager] No root node is loaded." << G4endl;
        return;
    }
    PrintTreeNode(*rootNode_, 0);
}

void GeometryManager::Clear()
{
    geometryConfigFile_.clear();
    configDiagnostics_.clear();
    templateRootNode_.reset();
    rootNode_.reset();
    userAddedVolumes_.clear();
    registry_.Clear();
    volumeBuilder_.Clear();
    MarkDirty();
}

void GeometryManager::ValidateRootNode(const VolumeNode& rootNode) const
{
    if (!rootNode.IsWorld()) {
        throw std::runtime_error("Geometry root node must be world-like with empty parentName, got '" + rootNode.name + "'");
    }
    ValidateNodeRecursive(rootNode, true);
}

void GeometryManager::ValidateUserVolume(const VolumeNode& node) const
{
    const std::string prefix = UserVolumeContext("GeometryManager::ValidateUserVolume", node);
    if (StringUtils::Trim(node.name).empty()) throw std::runtime_error(prefix + "name must not be empty");
    if (StringUtils::Trim(node.parentName).empty()) throw std::runtime_error(prefix + "parentName must not be empty");
    if (node.shape == VolumeShape::Unknown) throw std::runtime_error(prefix + "shape must not be unknown");
    if (StringUtils::Trim(node.materialName).empty()) throw std::runtime_error(prefix + "materialName must not be empty");
    if (node.placementType != PlacementType::Normal) {
        throw std::runtime_error(
            prefix + "placement=" + GeometryUtils::PlacementTypeToString(node.placementType)
            + " is not supported; use placement=normal with explicit child volumes"
        );
    }

    if (node.shape == VolumeShape::Box) {
        try {
            GeometryUtils::ValidateBoxSize(node.size);
        } catch (const std::exception& e) {
            throw std::runtime_error(prefix + e.what());
        }
    }
    if (node.shape == VolumeShape::Tubs) {
        if (node.parameters.size() < 5) throw std::runtime_error(prefix + "tubs requires parameters rMin,rMax,halfZ,startPhi,deltaPhi");
        try {
            GeometryUtils::ValidateTubsParameters(node.parameters[0], node.parameters[1], node.parameters[2], node.parameters[3], node.parameters[4]);
        } catch (const std::exception& e) {
            throw std::runtime_error(prefix + e.what());
        }
    }
    if (node.hasProductionCuts) {
        const auto check = [&](double value, const std::string& label) {
            if (value == 0.0 || value < -1.0) throw std::runtime_error(prefix + "invalid production cut " + label);
        };
        check(node.productionCuts.gamma, "gamma");
        check(node.productionCuts.electron, "e-");
        check(node.productionCuts.positron, "e+");
        check(node.productionCuts.proton, "proton");
    }
}

VolumeNode* GeometryManager::FindNodeMutable(VolumeNode& root, const std::string& name)
{
    if (NormalizeVolumeKey(root.name) == NormalizeVolumeKey(name)) return &root;
    for (VolumeNode& child : root.children) {
        if (VolumeNode* found = FindNodeMutable(child, name)) return found;
    }
    return nullptr;
}

const VolumeNode* GeometryManager::FindNode(const VolumeNode& root, const std::string& name) const
{
    if (NormalizeVolumeKey(root.name) == NormalizeVolumeKey(name)) return &root;
    for (const VolumeNode& child : root.children) {
        if (const VolumeNode* found = FindNode(child, name)) return found;
    }
    return nullptr;
}

bool GeometryManager::TreeContainsName(const VolumeNode& root, const std::string& name) const
{
    return FindNode(root, name) != nullptr;
}

void GeometryManager::AppendChildToParent(VolumeNode& root, const VolumeNode& child)
{
    VolumeNode* parent = FindNodeMutable(root, child.parentName);
    if (!parent) {
        throw std::runtime_error(UserVolumeContext("GeometryManager::AppendChildToParent", child) + "parent volume does not exist");
    }
    parent->AddChild(child);
}

bool GeometryManager::RemoveNodeFromTree(VolumeNode& root, const std::string& name)
{
    const std::string key = NormalizeVolumeKey(name);
    auto& children = root.children;
    const auto it = std::find_if(children.begin(), children.end(), [&](const VolumeNode& child) {
        return NormalizeVolumeKey(child.name) == key;
    });
    if (it != children.end()) {
        children.erase(it); // First version removes the whole child subtree.
        return true;
    }
    for (VolumeNode& child : children) {
        if (RemoveNodeFromTree(child, name)) return true;
    }
    return false;
}

void GeometryManager::PrintTreeNode(const VolumeNode& node, int depth) const
{
    for (int i = 0; i < depth; ++i) G4cout << "  ";
    G4cout << "- " << node.name
           << " shape=" << node.ShapeAsString()
           << " material=" << (node.materialName.empty() ? "<default>" : node.materialName);
    if (node.sensitive) G4cout << " sensitive";
    if (node.bias) G4cout << " bias";
    if (!node.regionName.empty()) G4cout << " region=" << node.regionName;
    if (node.HasBooleanOperations()) G4cout << " booleanOps=" << node.booleanOperations.size();
    if (!node.userProperties.empty()) {
        G4cout << " properties={";
        bool first = true;
        for (const auto& item : node.userProperties) {
            if (!first) G4cout << ", ";
            G4cout << item.first << "=" << item.second;
            first = false;
        }
        G4cout << "}";
    }
    G4cout << G4endl;
    for (const VolumeNode& child : node.children) PrintTreeNode(child, depth + 1);
}

void GeometryManager::PrintReinitializeHint() const
{
    G4cout << "[GeometryManager] Geometry tree was modified. Use /run/reinitializeGeometry before the next run if the run manager was already initialized." << G4endl;
}
