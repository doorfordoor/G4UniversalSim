#pragma once

#include "Geometry/GeometryTypes.hh"

#include <map>
#include <string>
#include <vector>

class VolumeNode {
public:
    VolumeNode();
    explicit VolumeNode(const std::string& name);

    std::string name;
    std::string parentName;
    VolumeShape shape = VolumeShape::Unknown;
    std::string shapeName;
    std::string materialName;
    Vec3 size;
    Vec3 position;
    Rotation3 rotation;
    std::vector<double> parameters;
    bool sensitive = false;
    bool bias = false;
    std::string regionName;
    ProductionCut productionCuts;
    bool hasProductionCuts = false;
    PlacementType placementType = PlacementType::Normal;
    VisualAttributes visual;
    std::vector<VolumeNode> children;
    std::map<std::string, std::string> userProperties;

    bool IsWorld() const;
    bool HasParent() const;
    bool HasRegion() const;
    bool IsSensitive() const;
    bool IsBiasVolume() const;

    void AddChild(const VolumeNode& child);
    bool HasChildren() const;

    std::vector<VolumeNode*> GetChildrenMutable();
    std::vector<const VolumeNode*> GetChildren() const;

    void SetProperty(const std::string& key, const std::string& value);
    bool HasProperty(const std::string& key) const;
    std::string GetProperty(const std::string& key, const std::string& defaultValue = "") const;

    std::string ShapeAsString() const;
    std::string ToString() const;
    void ValidateBasic() const;
};
