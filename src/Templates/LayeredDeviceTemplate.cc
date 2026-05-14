#include "Templates/LayeredDeviceTemplate.hh"

#include "Config/ConfigManager.hh"
#include "Geometry/GeometryUtils.hh"
#include "Utils/StringUtils.hh"
#include "Utils/UnitParser.hh"

#include <set>
#include <stdexcept>

namespace {

std::pair<double, double> ParseXY(const std::string& text)
{
    const auto parts = text.find(',') != std::string::npos
        ? StringUtils::Split(text, ',', true)
        : StringUtils::SplitWhitespace(text);
    if (parts.size() != 2 && parts.size() != 4) {
        throw std::runtime_error("layered_device xy expects two lengths: '" + text + "'");
    }
    if (parts.size() == 2) return {UnitParser::ParseLength(parts[0]), UnitParser::ParseLength(parts[1])};
    return {UnitParser::ParseLength(parts[0] + " " + parts[1]), UnitParser::ParseLength(parts[2] + " " + parts[3])};
}

void ApplyCuts(const ConfigManager& config, const std::string& section, VolumeNode& node)
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
    if (config.HasKey(section, "vis.color")) node.visual.color = config.GetString(section, "vis.color");
    if (config.HasKey(section, "vis.alpha")) node.visual.alpha = config.GetDouble(section, "vis.alpha");
    if (config.HasKey(section, "vis.visible")) node.visual.visible = config.GetBool(section, "vis.visible");
    if (config.HasKey(section, "vis.wireframe")) node.visual.wireframe = config.GetBool(section, "vis.wireframe");
}

bool IsKnownLayerKey(const std::string& key)
{
    static const std::set<std::string> keys = {
        "thickness", "xy", "material", "position", "rotation", "sensitive", "bias", "region",
        "cut.gamma", "cut.e-", "cut.e+", "cut.proton",
        "vis.color", "vis.alpha", "vis.visible", "vis.wireframe",
        "copyno"
    };
    return keys.count(StringUtils::ToLower(StringUtils::Trim(key))) > 0;
}

std::string ValidateCopyNo(const std::string& text, const std::string& section)
{
    const std::string trimmed = StringUtils::Trim(text);
    try {
        std::size_t consumed = 0;
        (void)std::stoi(trimmed, &consumed);
        if (consumed != trimmed.size()) throw std::runtime_error("trailing text");
    } catch (...) {
        throw std::runtime_error("layered_device " + section + "/copyNo must be an integer, got '" + text + "'");
    }
    return trimmed;
}

void ApplyUserProperties(const ConfigManager& config, const std::string& section, VolumeNode& node)
{
    if (config.HasKey(section, "copyNo")) {
        node.userProperties["copyNo"] = ValidateCopyNo(config.GetString(section, "copyNo"), section);
    }

    for (const std::string& key : config.GetKeys(section)) {
        if (!IsKnownLayerKey(key)) {
            node.userProperties[key] = config.GetString(section, key);
        }
    }
}

}  // namespace

std::string LayeredDeviceTemplate::Name() const
{
    return "layered_device";
}

VolumeNode LayeredDeviceTemplate::BuildNodes(const ConfigManager& config) const
{
    ValidateConfig(config);

    VolumeNode world("world");
    world.shape = VolumeShape::Box;
    world.shapeName = "box";
    world.size = GeometryUtils::ParseVec3(config.GetString("world", "size"));
    world.materialName = config.GetString("world", "material");
    world.ValidateBasic();

    const auto names = config.GetVector("layers", "names");
    const bool autoStack = config.GetBool("layers", "auto_stack", true);
    const std::string axis = StringUtils::ToLower(config.GetString("layers", "axis", "z"));
    if (axis != "z") throw std::runtime_error("layered_device currently supports axis=z only");
    const double gap = config.HasKey("layers", "gap") ? UnitParser::ParseLength(config.GetString("layers", "gap")) : 0.0;

    std::vector<double> thicknesses;
    thicknesses.reserve(names.size());
    double total = gap * static_cast<double>(names.size() > 0 ? names.size() - 1 : 0);
    for (const std::string& rawName : names) {
        const std::string layerName = StringUtils::Trim(rawName);
        const std::string section = "layer." + layerName;
        const double thickness = UnitParser::ParseLength(config.GetString(section, "thickness"));
        if (thickness <= 0.0) throw std::runtime_error("layered_device layer '" + layerName + "' thickness must be > 0");
        thicknesses.push_back(thickness);
        total += thickness;
    }

    double edge = config.HasKey("layers", "z_start")
        ? UnitParser::ParseLength(config.GetString("layers", "z_start"))
        : -0.5 * total;

    for (std::size_t i = 0; i < names.size(); ++i) {
        const std::string layerName = StringUtils::Trim(names[i]);
        const std::string section = "layer." + layerName;
        const auto xy = ParseXY(config.GetString(section, "xy"));
        VolumeNode layer(layerName);
        layer.parentName = world.name;
        layer.shape = VolumeShape::Box;
        layer.shapeName = "box";
        layer.size = {xy.first, xy.second, thicknesses[i]};
        layer.materialName = config.GetString(section, "material");
        if (autoStack) {
            layer.position = {0.0, 0.0, edge + 0.5 * thicknesses[i]};
            edge += thicknesses[i] + gap;
        } else {
            layer.position = GeometryUtils::ParseVec3(config.GetString(section, "position"));
        }
        layer.rotation = GeometryUtils::ParseRotation3(config.GetString(section, "rotation", "0 deg, 0 deg, 0 deg"));
        layer.sensitive = config.GetBool(section, "sensitive", false);
        layer.bias = config.GetBool(section, "bias", false);
        layer.regionName = config.GetString(section, "region", "");
        ApplyCuts(config, section, layer);
        ApplyVisual(config, section, layer);
        ApplyUserProperties(config, section, layer);
        layer.ValidateBasic();
        world.AddChild(layer);
    }

    return world;
}

VolumeNode LayeredDeviceTemplate::BuildNodesFromFile(const std::string& filename) const
{
    return GeometryTemplate::BuildNodesFromFile(filename);
}

void LayeredDeviceTemplate::ValidateConfig(const ConfigManager& config) const
{
    if (!config.HasKey("world", "size")) throw std::runtime_error("layered_device missing [world]/size");
    if (!config.HasKey("world", "material")) throw std::runtime_error("layered_device missing [world]/material");
    const int count = config.GetInt("layers", "count");
    const auto names = config.GetVector("layers", "names");
    if (count <= 0) throw std::runtime_error("layered_device [layers]/count must be > 0");
    if (static_cast<int>(names.size()) != count) {
        throw std::runtime_error("layered_device [layers]/count does not match names size");
    }
    for (const std::string& rawName : names) {
        const std::string section = "layer." + StringUtils::Trim(rawName);
        if (!config.HasKey(section, "thickness")) throw std::runtime_error("layered_device missing " + section + "/thickness");
        if (!config.HasKey(section, "xy")) throw std::runtime_error("layered_device missing " + section + "/xy");
        if (!config.HasKey(section, "material")) throw std::runtime_error("layered_device missing " + section + "/material");
    }
}
