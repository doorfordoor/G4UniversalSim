#include "Templates/ShieldingTemplate.hh"

#include "Config/ConfigManager.hh"
#include "Geometry/GeometryUtils.hh"
#include "Utils/StringUtils.hh"
#include "Utils/UnitParser.hh"

#include <stdexcept>

namespace {

std::pair<double, double> ParseArea(const std::string& text)
{
    const auto parts = StringUtils::Split(text, ',', true);
    if (parts.size() != 2) throw std::runtime_error("shielding area expects two lengths: '" + text + "'");
    return {UnitParser::ParseLength(parts[0]), UnitParser::ParseLength(parts[1])};
}

}  // namespace

std::string ShieldingTemplate::Name() const
{
    return "shielding";
}

VolumeNode ShieldingTemplate::BuildNodes(const ConfigManager& config) const
{
    ValidateConfig(config);

    VolumeNode world("world");
    world.shape = VolumeShape::Box;
    world.shapeName = "box";
    world.size = GeometryUtils::ParseVec3(config.GetString("world", "size"));
    world.materialName = config.GetString("world", "material");
    world.ValidateBasic();

    const std::string axis = StringUtils::ToLower(config.GetString("shielding", "axis", "z"));
    if (axis != "z") throw std::runtime_error("shielding currently supports axis=z only");
    const auto area = ParseArea(config.GetString("shielding", "area"));
    const double gap = config.HasKey("shielding", "gap") ? UnitParser::ParseLength(config.GetString("shielding", "gap")) : 0.0;
    double edge = UnitParser::ParseLength(config.GetString("shielding", "start"));

    for (const std::string& rawName : config.GetVector("shielding", "layers")) {
        const std::string name = StringUtils::Trim(rawName);
        const std::string section = "shield." + name;
        const double thickness = UnitParser::ParseLength(config.GetString(section, "thickness"));
        VolumeNode shield(name);
        shield.parentName = world.name;
        shield.shape = VolumeShape::Box;
        shield.shapeName = "box";
        shield.size = {area.first, area.second, thickness};
        shield.position = {0.0, 0.0, edge + 0.5 * thickness};
        shield.materialName = config.GetString(section, "material");
        shield.bias = config.GetBool(section, "bias", false);
        shield.sensitive = config.GetBool(section, "sensitive", false);
        shield.regionName = config.GetString(section, "region", "");
        shield.ValidateBasic();
        world.AddChild(shield);
        edge += thickness + gap;
    }

    if (config.HasSection("detector")) {
        VolumeNode detector("Detector");
        detector.parentName = world.name;
        detector.shape = VolumeShape::Box;
        detector.shapeName = "box";
        detector.size = GeometryUtils::ParseVec3(config.GetString("detector", "size"));
        detector.position = GeometryUtils::ParseVec3(config.GetString("detector", "position"));
        detector.materialName = config.GetString("detector", "material");
        detector.sensitive = config.GetBool("detector", "sensitive", true);
        detector.regionName = config.GetString("detector", "region", "");
        detector.ValidateBasic();
        world.AddChild(detector);
    }

    return world;
}

VolumeNode ShieldingTemplate::BuildNodesFromFile(const std::string& filename) const
{
    return GeometryTemplate::BuildNodesFromFile(filename);
}

void ShieldingTemplate::ValidateConfig(const ConfigManager& config) const
{
    if (!config.HasKey("world", "size")) throw std::runtime_error("shielding missing [world]/size");
    if (!config.HasKey("world", "material")) throw std::runtime_error("shielding missing [world]/material");
    for (const auto& key : {"area", "start", "layers"}) {
        if (!config.HasKey("shielding", key)) throw std::runtime_error(std::string("shielding missing [shielding]/") + key);
    }
    for (const std::string& rawName : config.GetVector("shielding", "layers")) {
        const std::string section = "shield." + StringUtils::Trim(rawName);
        if (!config.HasKey(section, "thickness")) throw std::runtime_error("shielding missing " + section + "/thickness");
        if (!config.HasKey(section, "material")) throw std::runtime_error("shielding missing " + section + "/material");
    }
}
