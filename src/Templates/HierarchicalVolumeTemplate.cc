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
    diagnostics_ = config.GetDiagnostics();
    auto root=config.BuildTree();
    inputReader_=config.GetInputReader();inputs_=config.GetInputs();
    return root;
}

void HierarchicalVolumeTemplate::ValidateConfig(const ConfigManager&) const
{
}
