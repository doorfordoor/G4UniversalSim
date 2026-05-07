#include "Geometry/GeometryManager.hh"

#include "Geometry/GeometryUtils.hh"
#include "Materials/MaterialManager.hh"
#include "Templates/GeometryTemplate.hh"
#include "Templates/TemplateFactory.hh"
#include "Utils/FileUtils.hh"
#include "Utils/StringUtils.hh"

#include "G4VPhysicalVolume.hh"
#include "G4ios.hh"

#include <algorithm>
#include <set>
#include <stdexcept>

namespace {

void CollectRegions(const VolumeNode& node, std::set<std::string>& regions)
{
    if (!node.regionName.empty()) regions.insert(node.regionName);
    for (const VolumeNode& child : node.children) CollectRegions(child, regions);
}

void ValidateNodeRecursive(const VolumeNode& node, bool isRoot)
{
    GeometryUtils::ValidateVolumeName(node.name);
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
    for (const VolumeNode& child : node.children) ValidateNodeRecursive(child, false);
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

    auto geometryTemplate = TemplateFactory::Create(templateName_);
    VolumeNode root = geometryTemplate->BuildNodesFromFile(filename);
    ValidateRootNode(root);
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

void GeometryManager::SetCheckOverlaps(bool enable)
{
    checkOverlaps_ = enable;
    volumeBuilder_.SetCheckOverlaps(enable);
    MarkDirty();
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
    registry_.Clear();
    volumeBuilder_.Clear();
    volumeBuilder_.SetMaterialManager(materialManager_);
    volumeBuilder_.SetRegistry(&registry_);
    volumeBuilder_.SetCheckOverlaps(checkOverlaps_);
    volumeBuilder_.SetDefaultWorldMaterial(defaultWorldMaterial_);

    G4VPhysicalVolume* world = volumeBuilder_.BuildWorld(*rootNode_);
    if (!world) throw std::runtime_error("GeometryManager BuildWorld returned null world physical volume");
    ClearDirty();
    return world;
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
    G4cout << G4endl;
    for (const VolumeNode& child : node.children) PrintTreeNode(child, depth + 1);
}

void GeometryManager::PrintReinitializeHint() const
{
    G4cout << "[GeometryManager] Geometry tree was modified. Use /run/reinitializeGeometry before the next run if the run manager was already initialized." << G4endl;
}
