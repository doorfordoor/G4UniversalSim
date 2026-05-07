#include "Templates/SimpleBoxTemplate.hh"

#include "Config/ConfigManager.hh"
#include "Geometry/GeometryUtils.hh"
#include "Utils/StringUtils.hh"

#include <stdexcept>

namespace {

void ApplyCutsAndVisual(const ConfigManager& config, const std::string& section, VolumeNode& node)
{
    std::map<std::string, std::string> cuts;
    for (const std::string& key : {"cut.gamma", "cut.e-", "cut.e+", "cut.proton"}) {
        if (config.HasKey(section, key)) cuts[key] = config.GetString(section, key);
    }
    if (!cuts.empty()) {
        node.productionCuts = GeometryUtils::ParseProductionCuts(cuts);
        node.hasProductionCuts = true;
    }
}

void ApplyVisual(const ConfigManager& config, const std::string& section, VolumeNode& node)
{
    if (!config.HasSection(section)) return;
    if (config.HasKey(section, "color")) node.visual.color = config.GetString(section, "color");
    if (config.HasKey(section, "alpha")) node.visual.alpha = config.GetDouble(section, "alpha");
    if (config.HasKey(section, "visible")) node.visual.visible = config.GetBool(section, "visible");
    if (config.HasKey(section, "wireframe")) node.visual.wireframe = config.GetBool(section, "wireframe");
}

}  // namespace

std::string SimpleBoxTemplate::Name() const
{
    return "simple_box";
}

VolumeNode SimpleBoxTemplate::BuildNodes(const ConfigManager& config) const
{
    ValidateConfig(config);

    VolumeNode world("world");
    world.shape = VolumeShape::Box;
    world.shapeName = "box";
    world.size = GeometryUtils::ParseVec3(config.GetString("world", "size"));
    world.materialName = config.GetString("world", "material");
    ApplyVisual(config, "visual.world", world);
    world.ValidateBasic();

    VolumeNode target(config.GetString("target", "name", "Target"));
    target.parentName = world.name;
    target.shapeName = config.GetString("target", "shape", "box");
    target.shape = GeometryUtils::ParseShape(target.shapeName);
    target.size = GeometryUtils::ParseVec3(config.GetString("target", "size"));
    target.materialName = config.GetString("target", "material");
    target.position = GeometryUtils::ParseVec3(config.GetString("target", "position", "0 mm, 0 mm, 0 mm"));
    target.rotation = GeometryUtils::ParseRotation3(config.GetString("target", "rotation", "0 deg, 0 deg, 0 deg"));
    target.sensitive = config.GetBool("target", "sensitive", true);
    target.bias = config.GetBool("target", "bias", false);
    target.regionName = config.GetString("target", "region", "");
    ApplyCutsAndVisual(config, "target", target);
    ApplyVisual(config, "visual.target", target);
    target.ValidateBasic();

    world.AddChild(target);
    return world;
}

VolumeNode SimpleBoxTemplate::BuildNodesFromFile(const std::string& filename) const
{
    return GeometryTemplate::BuildNodesFromFile(filename);
}

void SimpleBoxTemplate::ValidateConfig(const ConfigManager& config) const
{
    if (!config.HasKey("world", "size")) throw std::runtime_error("simple_box missing [world]/size");
    if (!config.HasKey("world", "material")) throw std::runtime_error("simple_box missing [world]/material");
    if (!config.HasKey("target", "size")) throw std::runtime_error("simple_box missing [target]/size");
    if (!config.HasKey("target", "material")) throw std::runtime_error("simple_box missing [target]/material");
}
