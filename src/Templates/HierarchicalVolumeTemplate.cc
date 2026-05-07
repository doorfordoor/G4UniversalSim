#include "Templates/HierarchicalVolumeTemplate.hh"

#include "Geometry/GeometryConfig.hh"

std::string HierarchicalVolumeTemplate::Name() const
{
    return "hierarchical";
}

VolumeNode HierarchicalVolumeTemplate::BuildNodes(const ConfigManager&) const
{
    throw std::runtime_error("hierarchical template requires BuildNodesFromFile so GeometryConfig can parse [volume.*] sections");
}

VolumeNode HierarchicalVolumeTemplate::BuildNodesFromFile(const std::string& filename) const
{
    GeometryConfig config;
    config.Load(filename);
    return config.BuildTree();
}

void HierarchicalVolumeTemplate::ValidateConfig(const ConfigManager&) const
{
}
