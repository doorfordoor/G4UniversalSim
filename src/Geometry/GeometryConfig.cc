#include "Geometry/GeometryConfig.hh"

#include "Config/ConfigManager.hh"
#include "Geometry/GeometryUtils.hh"
#include "Utils/FileUtils.hh"
#include "Utils/StringUtils.hh"
#include "Utils/UnitParser.hh"

#include <fstream>
#include <functional>
#include <iostream>
#include <sstream>
#include <stdexcept>

namespace {

bool IsKnownBooleanKey(const std::string& key)
{
    static const std::set<std::string> keys = {
        "name", "operation", "shape", "size", "parameters", "position", "rotation"
    };
    return keys.count(key) > 0;
}

bool IsForbiddenBooleanKey(const std::string& key)
{
    static const std::set<std::string> keys = {
        "material", "sensitive", "bias", "region", "parent", "placement", "copyno", "copyNo"
    };
    const std::string lower = StringUtils::ToLower(StringUtils::Trim(key));
    return keys.count(lower) > 0
        || StringUtils::StartsWith(lower, "cut.")
        || StringUtils::StartsWith(lower, "vis.");
}

}  // namespace

void GeometryConfig::Load(const std::string& filename)
{
    Clear();
    if (!FileUtils::IsFile(filename)) {
        throw std::runtime_error("Geometry config file does not exist: '" + filename + "'");
    }
    filename_ = filename;

    std::ifstream input(filename);
    if (!input) throw std::runtime_error("Failed to open geometry config file: '" + filename + "'");

    std::map<std::string, Section> sections;
    std::string currentSection;
    std::string line;
    std::size_t lineNumber = 0;
    while (std::getline(input, line)) {
        ++lineNumber;
        const std::string clean = StringUtils::Trim(StringUtils::RemoveComment(line));
        if (clean.empty()) continue;

        if (clean.front() == '[') {
            if (clean.back() != ']') {
                throw std::runtime_error(
                    "Geometry ini parse error in '" + filename + "' line "
                    + std::to_string(lineNumber) + ": missing closing ']'"
                );
            }
            currentSection = StringUtils::Trim(clean.substr(1, clean.size() - 2));
            if (currentSection.empty()) {
                throw std::runtime_error(
                    "Geometry ini parse error in '" + filename + "' line "
                    + std::to_string(lineNumber) + ": empty section"
                );
            }
            sections[currentSection];
            continue;
        }

        if (currentSection.empty()) {
            throw std::runtime_error(
                "Geometry ini parse error in '" + filename + "' line "
                + std::to_string(lineNumber) + ": key outside section"
            );
        }
        const auto pos = clean.find('=');
        if (pos == std::string::npos) {
            throw std::runtime_error(
                "Geometry ini parse error in '" + filename + "' line "
                + std::to_string(lineNumber) + ": expected key=value"
            );
        }
        const std::string key = StringUtils::ToLower(StringUtils::Trim(clean.substr(0, pos)));
        const std::string value = StringUtils::Trim(clean.substr(pos + 1));
        sections[currentSection][key] = value;
    }

    std::map<std::string, std::map<int, BooleanSolidOperation>> pendingBooleanOps;
    std::map<std::string, std::string> pendingBooleanTargets;

    for (const auto& section : sections) {
        const std::string lower = StringUtils::ToLower(section.first);
        if (IsBooleanSectionName(section.first)) {
            const BooleanSectionId id = ParseBooleanSectionName(section.first);
            const std::string targetKey = Normalize(id.targetVolumeName);
            auto& opsByIndex = pendingBooleanOps[targetKey];
            if (opsByIndex.count(id.index)) {
                throw Error(filename_, section.first, id.targetVolumeName, "index", "duplicate boolean operation index " + std::to_string(id.index));
            }
            pendingBooleanTargets[targetKey] = id.targetVolumeName;
            opsByIndex[id.index] = ParseBooleanSection(section.first, section.second, id.targetVolumeName, id.index);
            continue;
        }
        if (lower == "world" || StringUtils::StartsWith(lower, "volume.")) {
            AddVolume(ParseVolumeSection(section.first, section.second));
        }
    }

    for (const auto& pending : pendingBooleanOps) {
        const std::string& targetKey = pending.first;
        const auto targetIt = pendingBooleanTargets.find(targetKey);
        const std::string targetName = targetIt == pendingBooleanTargets.end() ? targetKey : targetIt->second;
        if (!HasVolume(targetName)) {
            throw Error(filename_, "", targetName, "boolean", "target volume for boolean operations does not exist");
        }

        const auto& opsByIndex = pending.second;
        int expected = 0;
        for (const auto& item : opsByIndex) {
            if (item.first != expected) {
                throw Error(
                    filename_,
                    "volume." + targetName + ".boolean." + std::to_string(item.first),
                    targetName,
                    "index",
                    "boolean operation indices must be contiguous starting at 0"
                );
            }
            ++expected;
        }

        VolumeNode& target = GetVolumeMutable(targetName);
        for (const auto& item : opsByIndex) target.booleanOperations.push_back(item.second);
    }
    Validate();
}

void GeometryConfig::LoadFromConfigManager(const ConfigManager& config)
{
    const std::string filename = config.GetString("geometry", "config");
    Load(filename);
}

void GeometryConfig::Clear()
{
    filename_.clear();
    flatVolumes_.clear();
    indexByName_.clear();
}

bool GeometryConfig::HasVolume(const std::string& name) const
{
    return indexByName_.find(Normalize(name)) != indexByName_.end();
}

const VolumeNode& GeometryConfig::GetVolume(const std::string& name) const
{
    const auto it = indexByName_.find(Normalize(name));
    if (it == indexByName_.end()) throw std::runtime_error("Geometry volume not found: '" + name + "'");
    return flatVolumes_[it->second];
}

VolumeNode& GeometryConfig::GetVolumeMutable(const std::string& name)
{
    const auto it = indexByName_.find(Normalize(name));
    if (it == indexByName_.end()) throw std::runtime_error("Geometry volume not found: '" + name + "'");
    return flatVolumes_[it->second];
}

std::vector<std::string> GeometryConfig::GetVolumeNames() const
{
    std::vector<std::string> names;
    for (const auto& volume : flatVolumes_) names.push_back(volume.name);
    return names;
}

std::vector<std::string> GeometryConfig::GetSensitiveVolumeNames() const
{
    std::vector<std::string> names;
    for (const auto& volume : flatVolumes_) if (volume.sensitive) names.push_back(volume.name);
    return names;
}

std::vector<std::string> GeometryConfig::GetBiasVolumeNames() const
{
    std::vector<std::string> names;
    for (const auto& volume : flatVolumes_) if (volume.bias) names.push_back(volume.name);
    return names;
}

std::vector<std::string> GeometryConfig::GetRegionNames() const
{
    std::set<std::string> unique;
    for (const auto& volume : flatVolumes_) if (!volume.regionName.empty()) unique.insert(volume.regionName);
    return {unique.begin(), unique.end()};
}

const std::vector<VolumeNode>& GeometryConfig::GetFlatVolumes() const
{
    return flatVolumes_;
}

VolumeNode GeometryConfig::BuildTree() const
{
    Validate();

    const VolumeNode* world = nullptr;
    for (const auto& volume : flatVolumes_) {
        if (volume.IsWorld()) {
            if (world) throw std::runtime_error("Geometry has multiple world volumes");
            world = &volume;
        }
    }
    if (!world) throw std::runtime_error("Geometry has no world volume");

    std::function<VolumeNode(const VolumeNode&)> cloneWithChildren = [&](const VolumeNode& parent) {
        VolumeNode node = parent;
        node.children.clear();
        for (const auto& child : flatVolumes_) {
            if (Normalize(child.parentName) == Normalize(parent.name)) {
                node.children.push_back(cloneWithChildren(child));
            }
        }
        return node;
    };

    return cloneWithChildren(*world);
}

void GeometryConfig::AddVolume(const VolumeNode& node)
{
    const std::string key = Normalize(node.name);
    if (key.empty()) throw std::runtime_error("Cannot add geometry volume with empty name");
    if (indexByName_.find(key) != indexByName_.end()) {
        throw std::runtime_error("Duplicate geometry volume name: '" + node.name + "'");
    }
    indexByName_[key] = flatVolumes_.size();
    flatVolumes_.push_back(node);
}

void GeometryConfig::Validate() const
{
    int worldCount = 0;
    for (const VolumeNode& volume : flatVolumes_) {
        volume.ValidateBasic();
        if (volume.IsWorld()) {
            ++worldCount;
        } else if (!HasVolume(volume.parentName)) {
            throw Error(filename_, "", volume.name, "parent", "parent volume does not exist: '" + volume.parentName + "'");
        }
        if (volume.hasProductionCuts && volume.regionName.empty()) {
            // Allowed: builder may choose to create a volume-specific region later.
        }
        if (volume.sensitive && volume.bias) {
            // Allowed intentionally: scoring and biasing can both be requested for the same logical volume.
        }
    }
    if (worldCount == 0) throw std::runtime_error("Geometry config has no world volume: '" + filename_ + "'");
    if (worldCount > 1) throw std::runtime_error("Geometry config has multiple world volumes: '" + filename_ + "'");
    ValidateNoCycles();
}

const std::string& GeometryConfig::GetFilename() const
{
    return filename_;
}

std::string GeometryConfig::Normalize(const std::string& name)
{
    return StringUtils::ToLower(StringUtils::Trim(name));
}

bool GeometryConfig::IsCutKey(const std::string& key)
{
    return StringUtils::StartsWith(key, "cut.");
}

bool GeometryConfig::IsKnownKey(const std::string& key)
{
    static const std::set<std::string> keys = {
        "name", "parent", "shape", "size", "parameters", "material", "position", "rotation",
        "sensitive", "bias", "region", "placement", "copyNo", "copyno", "vis.color", "vis.alpha",
        "vis.visible", "vis.wireframe"
    };
    return keys.count(key) || IsCutKey(key);
}

bool GeometryConfig::IsBooleanSectionName(const std::string& sectionName)
{
    const std::string lower = StringUtils::ToLower(StringUtils::Trim(sectionName));
    return StringUtils::StartsWith(lower, "volume.") && lower.find(".boolean.") != std::string::npos;
}

GeometryConfig::BooleanSectionId GeometryConfig::ParseBooleanSectionName(const std::string& sectionName)
{
    const std::string value = StringUtils::Trim(sectionName);
    const std::string lower = StringUtils::ToLower(value);
    const std::string prefix = "volume.";
    const std::string marker = ".boolean.";
    if (!StringUtils::StartsWith(lower, prefix)) {
        throw std::runtime_error("Invalid boolean section name '" + sectionName + "': expected volume.<target>.boolean.<index>");
    }
    const std::size_t markerPos = lower.find(marker);
    if (markerPos == std::string::npos) {
        throw std::runtime_error("Invalid boolean section name '" + sectionName + "': expected volume.<target>.boolean.<index>");
    }

    const std::size_t targetBegin = prefix.size();
    const std::string target = StringUtils::Trim(value.substr(targetBegin, markerPos - targetBegin));
    const std::string indexText = StringUtils::Trim(value.substr(markerPos + marker.size()));
    if (target.empty() || indexText.empty()) {
        throw std::runtime_error("Invalid boolean section name '" + sectionName + "': target and index must not be empty");
    }
    if (indexText.find('.') != std::string::npos) {
        throw std::runtime_error("Invalid boolean section name '" + sectionName + "': boolean index must be a non-negative integer");
    }

    std::size_t consumed = 0;
    int index = -1;
    try {
        index = std::stoi(indexText, &consumed);
    } catch (...) {
        throw std::runtime_error("Invalid boolean section name '" + sectionName + "': boolean index must be a non-negative integer");
    }
    if (consumed != indexText.size() || index < 0) {
        throw std::runtime_error("Invalid boolean section name '" + sectionName + "': boolean index must be a non-negative integer");
    }

    return {target, index};
}

std::runtime_error GeometryConfig::Error(
    const std::string& filename,
    const std::string& section,
    const std::string& volume,
    const std::string& key,
    const std::string& message
)
{
    return std::runtime_error(
        "Geometry config error in file '" + filename + "', section '" + section
        + "', volume '" + volume + "', key '" + key + "': " + message
    );
}

VolumeNode GeometryConfig::ParseVolumeSection(
    const std::string& sectionName,
    const Section& values
) const
{
    const std::string sectionLower = StringUtils::ToLower(sectionName);
    const bool isWorld = sectionLower == "world";
    const std::string sectionVolumeName =
        isWorld ? "world" : sectionName.substr(std::string("volume.").size());

    VolumeNode node(values.count("name") ? values.at("name") : sectionVolumeName);
    if (!isWorld) {
        if (!values.count("parent")) throw Error(filename_, sectionName, node.name, "parent", "missing parent");
        node.parentName = values.at("parent");
    }

    if (!values.count("shape")) throw Error(filename_, sectionName, node.name, "shape", "missing shape");
    node.shapeName = values.at("shape");
    node.shape = GeometryUtils::ParseShape(node.shapeName);
    if (node.shape == VolumeShape::Unknown) {
        throw Error(filename_, sectionName, node.name, "shape", "unsupported shape '" + node.shapeName + "'");
    }

    if (!values.count("material")) throw Error(filename_, sectionName, node.name, "material", "missing material");
    node.materialName = values.at("material");

    if (values.count("position")) node.position = GeometryUtils::ParseVec3(values.at("position"));
    if (values.count("rotation")) node.rotation = GeometryUtils::ParseRotation3(values.at("rotation"));
    if (values.count("placement")) node.placementType = GeometryUtils::ParsePlacementType(values.at("placement"));

    if (node.shape == VolumeShape::Box) {
        if (!values.count("size")) throw Error(filename_, sectionName, node.name, "size", "box requires size");
        node.size = GeometryUtils::ParseVec3(values.at("size"));
    }
    if (node.shape == VolumeShape::Tubs) {
        if (!values.count("parameters")) throw Error(filename_, sectionName, node.name, "parameters", "tubs requires parameters");
        node.parameters = GeometryUtils::ParseParameterList(values.at("parameters"));
    } else if (values.count("parameters")) {
        node.parameters = GeometryUtils::ParseParameterList(values.at("parameters"));
    }

    if (values.count("sensitive")) node.sensitive = StringUtils::ToBool(values.at("sensitive"));
    if (values.count("bias")) node.bias = StringUtils::ToBool(values.at("bias"));
    if (values.count("region")) node.regionName = values.at("region");
    if (values.count("copyno")) node.userProperties["copyNo"] = values.at("copyno");

    std::map<std::string, std::string> cutValues;
    for (const auto& item : values) {
        if (IsCutKey(item.first)) cutValues[item.first] = item.second;
    }
    if (!cutValues.empty()) {
        node.productionCuts = GeometryUtils::ParseProductionCuts(cutValues);
        node.hasProductionCuts = true;
    }

    if (values.count("vis.color")) node.visual.color = values.at("vis.color");
    if (values.count("vis.alpha")) node.visual.alpha = UnitParser::ParseDouble(values.at("vis.alpha"));
    if (values.count("vis.visible")) node.visual.visible = StringUtils::ToBool(values.at("vis.visible"));
    if (values.count("vis.wireframe")) node.visual.wireframe = StringUtils::ToBool(values.at("vis.wireframe"));

    for (const auto& item : values) {
        if (!IsKnownKey(item.first)) node.userProperties[item.first] = item.second;
    }

    return node;
}

BooleanSolidOperation GeometryConfig::ParseBooleanSection(
    const std::string& sectionName,
    const Section& values,
    const std::string& targetName,
    int index
) const
{
    BooleanSolidOperation op;
    op.name = values.count("name") && !StringUtils::Trim(values.at("name")).empty()
        ? values.at("name")
        : targetName + "_bool_" + std::to_string(index);

    if (!values.count("operation")) throw Error(filename_, sectionName, targetName, "operation", "missing boolean operation");
    op.operation = GeometryUtils::ParseBooleanOperation(values.at("operation"));
    if (op.operation == BooleanOperation::None) {
        throw Error(filename_, sectionName, targetName, "operation", "boolean operation must be union, subtraction, or intersection");
    }

    if (!values.count("shape")) throw Error(filename_, sectionName, targetName, "shape", "missing boolean tool shape");
    op.tool.shapeName = values.at("shape");
    op.tool.shape = GeometryUtils::ParseShape(op.tool.shapeName);
    if (op.tool.shape == VolumeShape::Unknown) {
        throw Error(filename_, sectionName, targetName, "shape", "unsupported boolean tool shape '" + op.tool.shapeName + "'");
    }

    if (values.count("position")) op.tool.position = GeometryUtils::ParseVec3(values.at("position"));
    if (values.count("rotation")) op.tool.rotation = GeometryUtils::ParseRotation3(values.at("rotation"));

    if (op.tool.shape == VolumeShape::Box) {
        if (!values.count("size")) throw Error(filename_, sectionName, targetName, "size", "box boolean tool requires size");
        op.tool.size = GeometryUtils::ParseVec3(values.at("size"));
    }
    if (op.tool.shape == VolumeShape::Tubs) {
        if (!values.count("parameters")) {
            throw Error(filename_, sectionName, targetName, "parameters", "tubs boolean tool requires parameters");
        }
        op.tool.parameters = GeometryUtils::ParseParameterList(values.at("parameters"));
    } else if (values.count("parameters")) {
        op.tool.parameters = GeometryUtils::ParseParameterList(values.at("parameters"));
    }

    for (const auto& item : values) {
        if (IsForbiddenBooleanKey(item.first)) {
            std::cerr << "[GeometryConfig] warning: boolean section '" << sectionName
                      << "' ignores volume-only key '" << item.first << "'." << std::endl;
            continue;
        }
        if (!IsKnownBooleanKey(item.first)) op.tool.properties[item.first] = item.second;
    }

    return op;
}

void GeometryConfig::ValidateNoCycles() const
{
    std::set<std::string> visiting;
    std::set<std::string> visited;
    for (const VolumeNode& volume : flatVolumes_) {
        if (HasCycleFrom(Normalize(volume.name), visiting, visited)) {
            throw std::runtime_error("Geometry parent cycle detected at volume '" + volume.name + "'");
        }
    }
}

bool GeometryConfig::HasCycleFrom(
    const std::string& name,
    std::set<std::string>& visiting,
    std::set<std::string>& visited
) const
{
    if (visited.count(name)) return false;
    if (visiting.count(name)) return true;
    visiting.insert(name);

    const auto it = indexByName_.find(name);
    if (it != indexByName_.end()) {
        const VolumeNode& node = flatVolumes_[it->second];
        if (!node.parentName.empty()) {
            const std::string parent = Normalize(node.parentName);
            if (HasCycleFrom(parent, visiting, visited)) return true;
        }
    }

    visiting.erase(name);
    visited.insert(name);
    return false;
}
