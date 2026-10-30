#include "Config/ConfigSchemaTable.hh"
#include "Geometry/GeometryConfig.hh"

#include "Config/ConfigManager.hh"
#include "Geometry/GeometryUtils.hh"
#include "Geometry/GeometryConfigDiagnostic.hh"
#include "Geometry/StlReader.hh"
#include "G4SystemOfUnits.hh"
#include "Utils/FileUtils.hh"
#include "Utils/StringUtils.hh"
#include "Utils/UnitParser.hh"

#include <cmath>
#include <filesystem>
#include <fstream>
#include <functional>
#include <iostream>
#include <limits>
#include <sstream>
#include <stdexcept>

namespace {

bool IsKnownBooleanKey(const std::string& key)
{
    return ConfigSchema::HasKey("geometry_hierarchical_ini", "volume.<name>.boolean.<index>", key);
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

bool IsShapeProperty(const std::string& key)
{
    static const std::set<std::string> keys = {
        "dx1", "dx2", "dx3", "dx4", "dy1", "dy2", "dz",
        "theta", "phi", "alpha1", "alpha2",
        // roadmap A5: polycone/polyhedra planes and tessellated STL input
        "z_planes", "r_inner", "r_outer", "file", "file_unit"
    };
    return keys.count(StringUtils::ToLower(StringUtils::Trim(key))) > 0;
}

bool IsPlacementKey(const std::string& key)
{
    static const std::set<std::string> keys = {
        "replica_axis", "replica_count", "replica_width", "replica_offset",
        "copies_file", "copies", "copy_step"
    };
    return keys.count(StringUtils::ToLower(StringUtils::Trim(key))) > 0;
}

std::string ResolveNextTo(const std::string& baseFile, const std::string& path)
{
    std::filesystem::path file = std::filesystem::u8path(StringUtils::Trim(path));
    if (file.is_relative()) file = std::filesystem::u8path(baseFile).parent_path() / file;
    return file.u8string();
}

int ParseCount(const std::string& text)
{
    const std::string trimmed = StringUtils::Trim(text);
    std::size_t consumed = 0;
    const long long value = std::stoll(trimmed, &consumed);
    if (consumed != trimmed.size() || value < 1 || value > 1000000) throw std::runtime_error("expected an integer in 1..1000000");
    return static_cast<int>(value);
}

}  // namespace

void GeometryConfig::Load(const std::string& filename)
{
    const auto input=input_provenance::ReadFile(filename, "geometry_ini", "geometry_parse");
    GeometryConfig candidate;
    candidate.LoadBytes(filename,input.bytes);
    *this=std::move(candidate);
}
void GeometryConfig::LoadBytes(const std::string& filename,const std::string& bytes)
{
    filename_=filename;
    sourceReader_.LoadBytes(filename,bytes);
    inputs_.push_back({filename,{},sourceReader_.GetInputSha256()});
    std::istringstream input(bytes);
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

    sourceFields_ = sourceReader_.GetFields();
    sourceSections_ = sourceReader_.GetSectionInfo();
    diagnostics_.clear();
    CollectGeometryConfigDiagnostics(filename_, sourceFields_, sourceSections_, "hierarchical", diagnostics_, &bytes);
    ValidateCutFields();

    for (const auto& section : sections) {
        const std::string lower = StringUtils::ToLower(section.first);
        if (IsBooleanSectionName(section.first)) {
            BooleanSectionId id;
            try {
                id = ParseBooleanSectionName(section.first);
            } catch (const std::exception&) {
                // The diagnostic collector reports malformed boolean sections as
                // unknown_section; preserve the legacy warning-only behavior.
                continue;
            }
            const std::string targetKey = Normalize(id.targetVolumeName);
            auto& opsByIndex = pendingBooleanOps[targetKey];
            if (opsByIndex.count(id.index)) {
                throw Error(filename_, section.first, id.targetVolumeName, "index", "duplicate boolean operation index " + std::to_string(id.index));
            }
            pendingBooleanTargets[targetKey] = id.targetVolumeName;
            opsByIndex[id.index] = ParseBooleanSection(section.first, section.second, id.targetVolumeName, id.index);
            continue;
        }
        if (lower == "world" || (StringUtils::StartsWith(lower, "volume.") && lower != "volume.")) {
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
    sourceReader_.Clear();inputs_.clear();
    filename_.clear();
    flatVolumes_.clear();
    indexByName_.clear();
    sourceFields_.clear();
    sourceSections_.clear();
    diagnostics_.clear();
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
            throw std::runtime_error(
                "Geometry volume '" + volume.name + "' has production cuts but no non-empty region"
            );
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

const std::vector<GeometryConfigDiagnostic>& GeometryConfig::GetDiagnostics() const
{
    return diagnostics_;
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
    // Metadata stays in userProperties, including a literally named <name> key.
    return (key != "metadata.<name>" && ConfigSchema::HasKey("geometry_hierarchical_ini", "volume.<name>", key)) || IsCutKey(key);
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

const IniFieldInfo* GeometryConfig::FindField(const std::string& section, const std::string& key) const
{
    const std::string sectionKey = Normalize(section);
    const std::string fieldKey = Normalize(key);
    for (const auto& field : sourceFields_) {
        if (Normalize(field.section) == sectionKey && Normalize(field.key) == fieldKey) return &field;
    }
    return nullptr;
}

std::runtime_error GeometryConfig::FieldError(
    const std::string& section,
    const std::string& volume,
    const std::string& key,
    const std::string& message,
    const std::string& suggestion
) const
{
    const IniFieldInfo* field = FindField(section, key);
    std::ostringstream text;
    text << "Geometry config error in file '" << filename_ << "'";
    if (field) text << ", line " << field->lineNumber;
    text << ", section '[" << section << "]', volume '" << volume << "', key '"
         << (field ? field->key : key) << "', value '" << (field ? field->value : "<missing>")
         << "': " << message;
    if (!suggestion.empty()) text << " " << suggestion;
    return std::runtime_error(text.str());
}

void GeometryConfig::ValidateCutFields() const
{
    static const std::set<std::string> allowed = {
        "cut.gamma", "cut.e-", "cut.e+", "cut.proton"
    };
    for (const auto& field : sourceFields_) {
        const std::string key = Normalize(field.key);
        if (!StringUtils::StartsWith(key, "cut.")) continue;
        const std::string section = Normalize(field.section);
        const bool ordinaryVolume = section == "world" || StringUtils::StartsWith(section, "volume.");
        const bool booleanTool = section.find(".boolean.") != std::string::npos;
        if (!allowed.count(key)) {
            const std::string suggestion = (key == "cut.electron" || key == "cut.electron-")
                ? "Use 'cut.e-' instead."
                : "Use one of cut.gamma, cut.e-, cut.e+, or cut.proton.";
            throw FieldError(field.section, "", field.key, "unknown production cut key.", suggestion);
        }
        if (!ordinaryVolume || booleanTool) {
            throw FieldError(
                field.section,
                "",
                field.key,
                "production cuts are only valid on ordinary geometry volumes.",
                "Move the cut to [world] or [volume.<name>] and set a non-empty region."
            );
        }
        const IniFieldInfo* region = FindField(field.section, "region");
        if (!region || StringUtils::Trim(region->value).empty()) {
            throw FieldError(
                field.section,
                "",
                field.key,
                "production cut requires a non-empty region in the same section.",
                "Add 'region = <RegionName>' to this section."
            );
        }
        try {
            if (UnitParser::ParseLength(field.value) <= 0.0) {
                throw FieldError(field.section, "", field.key, "production cut must be > 0.");
            }
        } catch (const std::runtime_error& error) {
            const std::string message = error.what();
            if (message.find("Geometry config error") != std::string::npos) throw;
            throw FieldError(field.section, "", field.key, "invalid production cut value: " + message);
        }
    }
}

void GeometryConfig::ValidateCopyNumber(const std::string& section, const std::string& volume) const
{
    const IniFieldInfo* field = FindField(section, "copyno");
    if (!field) return;
    const std::string text = StringUtils::Trim(field->value);
    try {
        std::size_t consumed = 0;
        const long long value = std::stoll(text, &consumed);
        if (consumed != text.size()
            || value < std::numeric_limits<int>::min()
            || value > std::numeric_limits<int>::max()) {
            throw std::runtime_error("out of range");
        }
    } catch (...) {
        throw FieldError(
            section,
            volume,
            field->key,
            "copyNo must be a signed 32-bit integer.",
            "Use an integer from -2147483648 to 2147483647."
        );
    }
}

void GeometryConfig::ValidateShapeContract(
    const std::string& section,
    const std::string& volume,
    VolumeShape shape,
    const Vec3& size,
    const std::vector<double>& parameters,
    const std::map<std::string, std::string>& properties,
    bool booleanTool
) const
{
    const auto fail = [&](const std::string& key, const std::string& message, const std::string& suggestion = "") {
        throw FieldError(section, volume, key, message, suggestion);
    };
    const auto exactParameters = [&](std::size_t count, const std::string& label) {
        if (parameters.size() != count) {
            fail("parameters", label + " requires exactly " + std::to_string(count) + " parameters; got "
                + std::to_string(parameters.size()) + ".");
        }
    };
    const auto positiveProperty = [&](const std::string& key) {
        const auto it = properties.find(key);
        if (it == properties.end() || StringUtils::Trim(it->second).empty()) {
            fail(key, "shape requires this length field.");
        }
        double value = 0.0;
        try {
            value = UnitParser::ParseLength(it->second);
        } catch (const std::exception& error) {
            fail(key, std::string("invalid positive length: ") + error.what());
        }
        if (value <= 0.0) fail(key, "shape length must be > 0.");
    };
    const auto angleProperty = [&](const std::string& key) {
        const auto it = properties.find(key);
        if (it == properties.end() || StringUtils::Trim(it->second).empty()) fail(key, "shape requires this angle field.");
        try {
            (void)UnitParser::ParseAngle(it->second);
        } catch (const std::exception& error) {
            fail(key, std::string("invalid angle: ") + error.what());
        }
    };

    std::set<std::string> allowedProperties;
    if (shape == VolumeShape::Trd) {
        allowedProperties = {"dx1", "dx2", "dy1", "dy2", "dz"};
    } else if (shape == VolumeShape::Trap) {
        allowedProperties = {
            "dz", "theta", "phi", "dy1", "dx1", "dx2", "alpha1",
            "dy2", "dx3", "dx4", "alpha2"
        };
    } else if (shape == VolumeShape::Polycone || shape == VolumeShape::Polyhedra) {
        allowedProperties = {"z_planes", "r_inner", "r_outer"};
    } else if (shape == VolumeShape::Tessellated) {
        allowedProperties = {"file", "file_unit"};
    }
    const bool a5Shape = shape == VolumeShape::Ellipsoid || shape == VolumeShape::EllipticalTube
        || shape == VolumeShape::Torus || shape == VolumeShape::Para || shape == VolumeShape::Hype
        || shape == VolumeShape::Polycone || shape == VolumeShape::Polyhedra || shape == VolumeShape::Tessellated;
    if (booleanTool && a5Shape) {
        fail("shape", "shape=" + GeometryUtils::ShapeToString(shape) + " is not supported as a boolean tool.",
             "Use box, tubs, sphere, orb, cone, trd or trap as the boolean tool.");
    }
    for (const auto& item : properties) {
        if (IsShapeProperty(item.first) && !allowedProperties.count(Normalize(item.first))) {
            fail(
                item.first,
                "shape-specific field is not valid for shape=" + GeometryUtils::ShapeToString(shape) + ".",
                "Remove the field or select the matching trd/trap shape."
            );
        }
    }

    if (shape == VolumeShape::Box) {
        if (FindField(section, "parameters")) fail("parameters", "box does not accept parameters; use size with exactly three positive lengths.");
        try { GeometryUtils::ValidateBoxSize(size); }
        catch (const std::exception& error) { fail("size", error.what()); }
        return;
    }
    if (FindField(section, "size")) {
        fail("size", "this shape does not accept size shorthand.", "Use the documented parameters or shape-specific fields.");
    }
    try {
        if (shape == VolumeShape::Tubs) {
            exactParameters(5, "tubs");
            GeometryUtils::ValidateTubsParameters(parameters[0], parameters[1], parameters[2], parameters[3], parameters[4]);
        } else if (shape == VolumeShape::Sphere) {
            exactParameters(6, "sphere");
            if (parameters[0] < 0.0 || parameters[1] <= parameters[0]
                || parameters[3] <= 0.0 || parameters[5] <= 0.0) {
                fail("parameters", "sphere radii and angular spans are invalid.");
            }
        } else if (shape == VolumeShape::Orb) {
            exactParameters(1, "orb");
            if (parameters[0] <= 0.0) fail("parameters", "orb radius must be > 0.");
        } else if (shape == VolumeShape::Cone) {
            exactParameters(7, "cone");
            if (parameters[0] < 0.0 || parameters[2] < 0.0
                || parameters[1] <= parameters[0] || parameters[3] <= parameters[2]
                || parameters[4] <= 0.0 || parameters[6] <= 0.0) {
                fail("parameters", "cone radii, halfZ, or deltaPhi are invalid.");
            }
        } else if (shape == VolumeShape::Trd) {
            if (FindField(section, "parameters")) fail("parameters", "trd uses dx1, dx2, dy1, dy2, and dz fields, not parameters.");
            for (const auto& key : {"dx1", "dx2", "dy1", "dy2", "dz"}) positiveProperty(key);
        } else if (shape == VolumeShape::Trap) {
            if (FindField(section, "parameters")) fail("parameters", "trap uses explicit shape-specific fields, not parameters.");
            for (const auto& key : {"dz", "dy1", "dx1", "dx2", "dy2", "dx3", "dx4"}) positiveProperty(key);
            for (const auto& key : {"theta", "phi", "alpha1", "alpha2"}) angleProperty(key);
        } else if (shape == VolumeShape::Ellipsoid) {
            if (parameters.size() != 3 && parameters.size() != 5) {
                fail("parameters", "ellipsoid requires 3 parameters (ax,by,cz) or 5 (ax,by,cz,zBottomCut,zTopCut).");
            }
            if (parameters[0] <= 0.0 || parameters[1] <= 0.0 || parameters[2] <= 0.0) fail("parameters", "ellipsoid semi-axes must be > 0.");
            if (parameters.size() == 5 && !(parameters[3] < parameters[4])) fail("parameters", "ellipsoid requires zBottomCut < zTopCut.");
        } else if (shape == VolumeShape::EllipticalTube) {
            exactParameters(3, "eltube");
            if (parameters[0] <= 0.0 || parameters[1] <= 0.0 || parameters[2] <= 0.0) fail("parameters", "eltube half-lengths dx,dy,dz must be > 0.");
        } else if (shape == VolumeShape::Torus) {
            exactParameters(5, "torus");
            if (parameters[0] < 0.0 || parameters[1] <= parameters[0] || parameters[2] < parameters[1] || parameters[4] <= 0.0) {
                fail("parameters", "torus requires 0 <= rMin < rMax <= rTor and deltaPhi > 0.");
            }
        } else if (shape == VolumeShape::Para) {
            exactParameters(6, "para");
            if (parameters[0] <= 0.0 || parameters[1] <= 0.0 || parameters[2] <= 0.0) fail("parameters", "para half-lengths dx,dy,dz must be > 0.");
        } else if (shape == VolumeShape::Hype) {
            exactParameters(5, "hype");
            if (parameters[0] < 0.0 || parameters[1] <= parameters[0] || parameters[4] <= 0.0) {
                fail("parameters", "hype requires 0 <= innerRadius < outerRadius and halfZ > 0.");
            }
        } else if (shape == VolumeShape::Polycone || shape == VolumeShape::Polyhedra) {
            const bool polyhedra = shape == VolumeShape::Polyhedra;
            exactParameters(polyhedra ? 3 : 2, polyhedra ? "polyhedra (startPhi,deltaPhi,numSide)" : "polycone (startPhi,deltaPhi)");
            if (parameters[1] <= 0.0) fail("parameters", "deltaPhi must be > 0.");
            if (polyhedra && (parameters[2] < 3.0 || parameters[2] != std::floor(parameters[2]))) {
                fail("parameters", "polyhedra numSide must be an integer >= 3.");
            }
            std::vector<std::vector<double>> lists;
            for (const char* key : {"z_planes", "r_inner", "r_outer"}) {
                const auto it = properties.find(key);
                if (it == properties.end()) fail(key, "shape requires this list of lengths.");
                try { lists.push_back(GeometryUtils::ParseParameterList(it->second)); }
                catch (const std::exception& error) { fail(key, error.what()); }
            }
            if (lists[0].size() < 2 || lists[1].size() != lists[0].size() || lists[2].size() != lists[0].size()) {
                fail("z_planes", "z_planes, r_inner and r_outer need the same number (>= 2) of entries.");
            }
            for (std::size_t i = 0; i < lists[0].size(); ++i) {
                if (i > 0 && lists[0][i] < lists[0][i - 1]) fail("z_planes", "z_planes must be non-decreasing.");
                if (lists[1][i] < 0.0 || lists[2][i] < lists[1][i]) fail("r_outer", "every plane needs 0 <= r_inner <= r_outer.");
            }
        } else if (shape == VolumeShape::Tessellated) {
            if (FindField(section, "parameters")) fail("parameters", "tessellated uses file (STL) and optional file_unit, not parameters.");
            const auto file = properties.find("file");
            if (file == properties.end() || StringUtils::Trim(file->second).empty()) fail("file", "tessellated requires file = <mesh.stl>.");
            double unit = CLHEP::mm;
            const auto unitText = properties.find("file_unit");
            if (unitText != properties.end()) {
                try { unit = UnitParser::ParseLength("1 " + StringUtils::Trim(unitText->second)); }
                catch (const std::exception& error) { fail("file_unit", error.what(), "Use a length unit such as mm, cm or m."); }
            }
            try { (void)StlReader::Read(ResolveNextTo(filename_, file->second), unit, "geometry_validation"); }
            catch (const std::exception& error) { fail("file", error.what()); }
        }
    } catch (const std::runtime_error&) {
        throw;
    } catch (const std::exception& error) {
        fail(shape == VolumeShape::Trd || shape == VolumeShape::Trap ? "shape" : "parameters", error.what());
    }

    (void)booleanTool;
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
        throw FieldError(sectionName, node.name, "shape", "unsupported shape '" + node.shapeName + "'");
    }

    if (!values.count("material")) throw Error(filename_, sectionName, node.name, "material", "missing material");
    node.materialName = values.at("material");

    if (values.count("position")) {
        try { node.position = GeometryUtils::ParseVec3(values.at("position")); }
        catch (const std::exception& error) { throw FieldError(sectionName, node.name, "position", error.what()); }
    }
    if (values.count("rotation")) {
        try { node.rotation = GeometryUtils::ParseRotation3(values.at("rotation")); }
        catch (const std::exception& error) { throw FieldError(sectionName, node.name, "rotation", error.what()); }
    }
    if (values.count("placement")) {
        try {
            node.placementType = GeometryUtils::ParsePlacementType(values.at("placement"));
        } catch (const std::exception& error) {
            throw FieldError(sectionName, node.name, "placement", error.what(), "Use placement=normal, replica or parameterised.");
        }
        if (node.placementType == PlacementType::Assembly) {
            throw FieldError(
                sectionName,
                node.name,
                "placement",
                "geometry capability 'placement=assembly' is not supported.",
                "Use placement=normal with explicit child volumes, or placement=parameterised for repeated copies."
            );
        }
    }
    ParsePlacement(sectionName, node, values);

    if (node.shape == VolumeShape::Box) {
        if (!values.count("size")) throw Error(filename_, sectionName, node.name, "size", "box requires size");
        try { node.size = GeometryUtils::ParseVec3(values.at("size")); }
        catch (const std::exception& error) { throw FieldError(sectionName, node.name, "size", error.what()); }
    }
    if (node.shape == VolumeShape::Tubs) {
        if (!values.count("parameters")) throw Error(filename_, sectionName, node.name, "parameters", "tubs requires parameters");
        try { node.parameters = GeometryUtils::ParseParameterList(values.at("parameters")); }
        catch (const std::exception& error) { throw FieldError(sectionName, node.name, "parameters", error.what()); }
    } else if (values.count("parameters")) {
        try { node.parameters = GeometryUtils::ParseParameterList(values.at("parameters")); }
        catch (const std::exception& error) { throw FieldError(sectionName, node.name, "parameters", error.what()); }
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
        if (IsShapeProperty(item.first)) node.userProperties[item.first] = item.second;
        if (!IsKnownKey(item.first)) node.userProperties[item.first] = item.second;
    }
    if (node.shape == VolumeShape::Tessellated && values.count("file")) {
        node.userProperties["file.resolved"] = ResolveNextTo(filename_, values.at("file"));
    }

    ValidateCopyNumber(sectionName, node.name);
    ValidateShapeContract(
        sectionName, node.name, node.shape, node.size, node.parameters, node.userProperties, false
    );

    return node;
}

void GeometryConfig::ParsePlacement(const std::string& sectionName, VolumeNode& node, const Section& values) const
{
    const auto fail = [&](const std::string& key, const std::string& message, const std::string& suggestion = "") {
        throw FieldError(sectionName, node.name, key, message, suggestion);
    };
    const bool replica = node.placementType == PlacementType::Replica;
    const bool parameterised = node.placementType == PlacementType::Parameterised;
    for (const auto& item : values) {
        const std::string key = Normalize(item.first);
        if (!IsPlacementKey(key)) continue;
        const bool replicaKey = StringUtils::StartsWith(key, "replica_");
        if ((replicaKey && !replica) || (!replicaKey && !parameterised)) {
            fail(item.first, "is only valid with placement=" + std::string(replicaKey ? "replica" : "parameterised") + ".");
        }
    }
    if (replica) {
        if (values.count("position") || values.count("rotation") || values.count("copyno") || values.count("copyNo")) {
            fail("placement", "placement=replica takes its position from the mother; remove position, rotation and copyNo.");
        }
        if (!values.count("replica_axis") || !values.count("replica_count") || !values.count("replica_width")) {
            fail("placement", "placement=replica requires replica_axis, replica_count and replica_width.");
        }
        auto& spec = node.placement;
        spec.replicaAxis = Normalize(values.at("replica_axis"));
        if (spec.replicaAxis != "x" && spec.replicaAxis != "y" && spec.replicaAxis != "z" && spec.replicaAxis != "phi") {
            fail("replica_axis", "must be x, y, z (box mother) or phi (tubs mother).");
        }
        try { spec.replicaCount = ParseCount(values.at("replica_count")); }
        catch (const std::exception& error) { fail("replica_count", error.what()); }
        const bool angular = spec.replicaAxis == "phi";
        try {
            spec.replicaWidth = angular ? UnitParser::ParseAngle(values.at("replica_width"))
                                        : UnitParser::ParseLength(values.at("replica_width"));
            if (values.count("replica_offset")) {
                spec.hasReplicaOffset = true;
                spec.replicaOffset = angular ? UnitParser::ParseAngle(values.at("replica_offset"))
                                             : UnitParser::ParseLength(values.at("replica_offset"));
            }
        } catch (const std::exception& error) {
            fail("replica_width", error.what(), angular ? "Use an angle such as '30 deg'." : "Use a length such as '2 mm'.");
        }
        if (!(spec.replicaWidth > 0.0)) fail("replica_width", "must be > 0.");
        if (!angular && values.count("replica_offset") && spec.replicaOffset != 0.0) {
            fail("replica_offset", "Geant4 requires offset 0 for cartesian replicas; remove replica_offset.");
        }
    }
    if (parameterised) {
        const bool table = values.count("copies_file") > 0;
        const bool linear = values.count("copies") > 0 || values.count("copy_step") > 0;
        if (table == linear) {
            fail("placement", "placement=parameterised requires either copies_file or copies + copy_step.");
        }
        auto& copies = node.placement.copies;
        if (linear) {
            if (!values.count("copies") || !values.count("copy_step")) fail("copies", "copies and copy_step must be given together.");
            int count = 0;
            try { count = ParseCount(values.at("copies")); }
            catch (const std::exception& error) { fail("copies", error.what()); }
            Vec3 step;
            try { step = GeometryUtils::ParseVec3(values.at("copy_step")); }
            catch (const std::exception& error) { fail("copy_step", error.what()); }
            for (int i = 0; i < count; ++i) {
                ParameterisedCopy copy;
                copy.position = {node.position.x + i * step.x, node.position.y + i * step.y, node.position.z + i * step.z};
                copy.rotation = node.rotation;
                copies.push_back(copy);
            }
        } else {
            if (values.count("position") || values.count("rotation")) {
                fail("copies_file", "copies_file defines every copy's position and rotation; remove position and rotation.");
            }
            const std::string path = ResolveNextTo(filename_, values.at("copies_file"));
            const auto acceptedInput=input_provenance::ReadFile(path, "copies_table", "parameterised_copies_parse");
            std::istringstream input(acceptedInput.bytes);
            inputs_.push_back({path,{},acceptedInput.sha256});
            std::string line;
            std::vector<std::string> header;
            int lineNumber = 0;
            while (std::getline(input, line)) {
                ++lineNumber;
                const std::string clean = StringUtils::Trim(StringUtils::RemoveComment(line));
                if (clean.empty()) continue;
                std::vector<std::string> cells;
                for (const auto& cell : StringUtils::Split(clean, ',')) cells.push_back(Normalize(cell));
                if (header.empty()) {
                    header = cells;
                    const std::vector<std::string> base{"x_mm", "y_mm", "z_mm"};
                    const bool ok = header.size() >= 3 && std::equal(base.begin(), base.end(), header.begin()) &&
                        (header.size() == 3 || header.size() == 4 || header.size() == 6 || header.size() == 7) &&
                        (header.size() < 6 || (header[3] == "rot_x_deg" && header[4] == "rot_y_deg" && header[5] == "rot_z_deg")) &&
                        (header.size() != 4 || header[3] == "material") && (header.size() != 7 || header[6] == "material");
                    if (!ok) {
                        fail("copies_file", "'" + path + "' header must be x_mm,y_mm,z_mm[,rot_x_deg,rot_y_deg,rot_z_deg][,material].");
                    }
                    continue;
                }
                if (cells.size() != header.size()) {
                    fail("copies_file", "'" + path + "' line " + std::to_string(lineNumber) + " has the wrong number of columns.");
                }
                std::vector<std::string> raw;
                for (const auto& cell : StringUtils::Split(clean, ',')) raw.push_back(StringUtils::Trim(cell));
                ParameterisedCopy copy;
                try {
                    copy.position = {UnitParser::ParseDouble(raw[0]) * CLHEP::mm, UnitParser::ParseDouble(raw[1]) * CLHEP::mm,
                                     UnitParser::ParseDouble(raw[2]) * CLHEP::mm};
                    if (header.size() >= 6) {
                        copy.rotation = {UnitParser::ParseDouble(raw[3]) * CLHEP::deg, UnitParser::ParseDouble(raw[4]) * CLHEP::deg,
                                         UnitParser::ParseDouble(raw[5]) * CLHEP::deg};
                    }
                } catch (const std::exception& error) {
                    fail("copies_file", "'" + path + "' line " + std::to_string(lineNumber) + ": " + error.what());
                }
                if (header.back() == "material") copy.material = raw.back();
                copies.push_back(copy);
            }
            if (copies.empty()) fail("copies_file", "'" + path + "' contains no copies.");
        }
    }
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
        throw FieldError(sectionName, targetName, "shape", "unsupported boolean tool shape '" + op.tool.shapeName + "'");
    }

    if (values.count("position")) {
        try { op.tool.position = GeometryUtils::ParseVec3(values.at("position")); }
        catch (const std::exception& error) { throw FieldError(sectionName, targetName, "position", error.what()); }
    }
    if (values.count("rotation")) {
        try { op.tool.rotation = GeometryUtils::ParseRotation3(values.at("rotation")); }
        catch (const std::exception& error) { throw FieldError(sectionName, targetName, "rotation", error.what()); }
    }

    if (op.tool.shape == VolumeShape::Box) {
        if (!values.count("size")) throw Error(filename_, sectionName, targetName, "size", "box boolean tool requires size");
        try { op.tool.size = GeometryUtils::ParseVec3(values.at("size")); }
        catch (const std::exception& error) { throw FieldError(sectionName, targetName, "size", error.what()); }
    }
    if (op.tool.shape == VolumeShape::Tubs) {
        if (!values.count("parameters")) {
            throw Error(filename_, sectionName, targetName, "parameters", "tubs boolean tool requires parameters");
        }
        try { op.tool.parameters = GeometryUtils::ParseParameterList(values.at("parameters")); }
        catch (const std::exception& error) { throw FieldError(sectionName, targetName, "parameters", error.what()); }
    } else if (values.count("parameters")) {
        try { op.tool.parameters = GeometryUtils::ParseParameterList(values.at("parameters")); }
        catch (const std::exception& error) { throw FieldError(sectionName, targetName, "parameters", error.what()); }
    }

    for (const auto& item : values) {
        if (IsForbiddenBooleanKey(item.first)) {
            continue;
        }
        if (!IsKnownBooleanKey(item.first)) op.tool.properties[item.first] = item.second;
    }

    ValidateShapeContract(
        sectionName, targetName, op.tool.shape, op.tool.size, op.tool.parameters, op.tool.properties, true
    );

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
