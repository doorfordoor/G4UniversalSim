#pragma once

#include "Geometry/GeometryRegistry.hh"
#include "Geometry/VolumeBuilder.hh"
#include "Geometry/VolumeNode.hh"

#include <memory>
#include <string>
#include <vector>

class G4VPhysicalVolume;
class MaterialManager;

class GeometryManager {
public:
    GeometryManager();
    ~GeometryManager();

    void SetMaterialManager(MaterialManager* materialManager);
    MaterialManager* GetMaterialManager() const;

    void SetTemplate(const std::string& templateName);
    const std::string& GetTemplateName() const;

    void LoadGeometryConfig(const std::string& filename);
    const std::string& GetGeometryConfigFile() const;

    void SetCheckOverlaps(bool enable);
    bool GetCheckOverlaps() const;

    void SetDefaultWorldMaterial(const std::string& materialName);
    const std::string& GetDefaultWorldMaterial() const;

    void SetRootNode(const VolumeNode& rootNode);
    const VolumeNode& GetRootNode() const;
    bool HasRootNode() const;

    void AddVolume(const VolumeNode& node);
    void AddBoxVolume(
        const std::string& name,
        const std::string& parentName,
        const std::string& materialName,
        const Vec3& size,
        const Vec3& position,
        const Rotation3& rotation,
        bool sensitive,
        bool bias,
        const std::string& regionName
    );
    void AddTubsVolume(
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
    );
    bool RemoveUserVolume(const std::string& name);
    void ClearUserAddedVolumes();
    std::vector<VolumeNode> GetUserAddedVolumes() const;
    std::vector<std::string> GetUserAddedVolumeNames() const;
    void SetPreserveUserVolumesOnLoad(bool preserve);
    bool GetPreserveUserVolumesOnLoad() const;
    void ApplyUserAddedVolumes();
    bool HasVolumeInCurrentTree(const std::string& name) const;
    bool HasUserAddedVolume(const std::string& name) const;
    void PrintUserAddedVolumes() const;

    void MarkDirty();
    void ClearDirty();
    bool IsDirty() const;

    G4VPhysicalVolume* BuildWorld();

    GeometryRegistry& GetRegistry();
    const GeometryRegistry& GetRegistry() const;

    VolumeBuilder& GetVolumeBuilder();
    const VolumeBuilder& GetVolumeBuilder() const;

    std::vector<std::string> GetSensitiveVolumeNames() const;
    std::vector<std::string> GetBiasVolumeNames() const;
    std::vector<std::string> GetRegionNames() const;

    void PrintSummary() const;
    void PrintTree() const;

    void Clear();

private:
    void ValidateRootNode(const VolumeNode& rootNode) const;
    void ValidateUserVolume(const VolumeNode& node) const;
    VolumeNode* FindNodeMutable(VolumeNode& root, const std::string& name);
    const VolumeNode* FindNode(const VolumeNode& root, const std::string& name) const;
    bool TreeContainsName(const VolumeNode& root, const std::string& name) const;
    void AppendChildToParent(VolumeNode& root, const VolumeNode& child);
    bool RemoveNodeFromTree(VolumeNode& root, const std::string& name);
    void PrintTreeNode(const VolumeNode& node, int depth) const;
    void PrintReinitializeHint() const;

    MaterialManager* materialManager_ = nullptr;
    GeometryRegistry registry_;
    VolumeBuilder volumeBuilder_;
    std::string templateName_ = "simple_box";
    std::string geometryConfigFile_;
    std::unique_ptr<VolumeNode> templateRootNode_;
    std::unique_ptr<VolumeNode> rootNode_;
    std::vector<VolumeNode> userAddedVolumes_;
    bool preserveUserVolumesOnLoad_ = true;
    bool dirty_ = true;
    bool checkOverlaps_ = true;
    std::string defaultWorldMaterial_ = "G4_AIR";
};
