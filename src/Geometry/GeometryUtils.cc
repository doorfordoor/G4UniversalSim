#include "Geometry/GeometryUtils.hh"

#include "Utils/G4NameUtils.hh"
#include "Utils/StringUtils.hh"
#include "Utils/UnitParser.hh"

#include <stdexcept>

namespace {

std::vector<std::string> SplitVectorText(const std::string& text)
{
    if (text.find(',') != std::string::npos) {
        return StringUtils::Split(text, ',', true);
    }

    const auto tokens = StringUtils::SplitWhitespace(text);
    if (tokens.size() == 3 || tokens.size() == 5) return tokens;
    if (tokens.size() == 6) {
        return {tokens[0] + " " + tokens[1], tokens[2] + " " + tokens[3], tokens[4] + " " + tokens[5]};
    }
    if (tokens.size() == 10) {
        return {
            tokens[0] + " " + tokens[1], tokens[2] + " " + tokens[3],
            tokens[4] + " " + tokens[5], tokens[6] + " " + tokens[7],
            tokens[8] + " " + tokens[9]
        };
    }
    return tokens;
}

double ParseMaybeLength(const std::string& text, bool parseAsLength)
{
    return parseAsLength ? UnitParser::ParseLength(text) : UnitParser::ParseDouble(text);
}

}  // namespace

namespace GeometryUtils {

VolumeShape ParseShape(const std::string& text)
{
    const std::string value = StringUtils::ToLower(StringUtils::Trim(text));
    if (value == "box" || value == "cube") return VolumeShape::Box;
    if (value == "tubs" || value == "tube" || value == "cylinder") return VolumeShape::Tubs;
    if (value == "sphere") return VolumeShape::Sphere;
    if (value == "orb") return VolumeShape::Orb;
    if (value == "cone" || value == "cons") return VolumeShape::Cone;
    if (value == "trd" || value == "trapezoid") return VolumeShape::Trd;
    if (value == "trap") return VolumeShape::Trap;
    return VolumeShape::Unknown;
}

std::string ShapeToString(VolumeShape shape)
{
    switch (shape) {
        case VolumeShape::Box: return "box";
        case VolumeShape::Tubs: return "tubs";
        case VolumeShape::Sphere: return "sphere";
        case VolumeShape::Orb: return "orb";
        case VolumeShape::Cone: return "cone";
        case VolumeShape::Trd: return "trd";
        case VolumeShape::Trap: return "trap";
        default: return "unknown";
    }
}

PlacementType ParsePlacementType(const std::string& text)
{
    const std::string value = StringUtils::ToLower(StringUtils::Trim(text));
    if (value.empty() || value == "normal") return PlacementType::Normal;
    if (value == "replica") return PlacementType::Replica;
    if (value == "parameterised" || value == "parameterized") return PlacementType::Parameterised;
    if (value == "assembly") return PlacementType::Assembly;
    throw std::runtime_error("Unsupported placement type: '" + text + "'");
}

std::string PlacementTypeToString(PlacementType type)
{
    switch (type) {
        case PlacementType::Normal: return "normal";
        case PlacementType::Replica: return "replica";
        case PlacementType::Parameterised: return "parameterised";
        case PlacementType::Assembly: return "assembly";
    }
    return "normal";
}

Vec3 ParseVec3(const std::string& text, bool parseAsLength)
{
    const auto parts = SplitVectorText(text);
    if (parts.size() != 3) throw std::runtime_error("Expected Vec3 with 3 values: '" + text + "'");
    return {
        ParseMaybeLength(parts[0], parseAsLength),
        ParseMaybeLength(parts[1], parseAsLength),
        ParseMaybeLength(parts[2], parseAsLength)
    };
}

Rotation3 ParseRotation3(const std::string& text)
{
    const auto parts = SplitVectorText(text);
    if (parts.size() != 3) throw std::runtime_error("Expected Rotation3 with 3 values: '" + text + "'");
    return {
        UnitParser::ParseAngle(parts[0]),
        UnitParser::ParseAngle(parts[1]),
        UnitParser::ParseAngle(parts[2])
    };
}

std::vector<double> ParseParameterList(const std::string& text, bool parseWithUnits)
{
    const auto parts = SplitVectorText(text);
    std::vector<double> values;
    values.reserve(parts.size());
    for (const std::string& part : parts) {
        values.push_back(parseWithUnits ? UnitParser::ParseDoubleWithUnit(part) : UnitParser::ParseDouble(part));
    }
    return values;
}

ProductionCut ParseProductionCuts(const std::map<std::string, std::string>& values)
{
    ProductionCut cuts;
    const auto read = [&](const std::string& key, double& target) {
        const auto it = values.find(key);
        if (it != values.end() && !StringUtils::Trim(it->second).empty()) {
            target = UnitParser::ParseLength(it->second);
            if (target <= 0.0) throw std::runtime_error("Production cut '" + key + "' must be > 0");
        }
    };
    read("cut.gamma", cuts.gamma);
    read("cut.e-", cuts.electron);
    read("cut.e+", cuts.positron);
    read("cut.proton", cuts.proton);
    return cuts;
}

bool IsValidVolumeName(const std::string& name)
{
    return !StringUtils::Trim(name).empty();
}

std::string NormalizeVolumeName(const std::string& name)
{
    return G4NameUtils::SanitizeName(StringUtils::Trim(name));
}

void ValidateVolumeName(const std::string& name)
{
    if (!IsValidVolumeName(name)) throw std::runtime_error("Volume name must not be empty");
}

void ValidateBoxSize(const Vec3& size)
{
    if (size.x <= 0.0 || size.y <= 0.0 || size.z <= 0.0) {
        throw std::runtime_error("Box size must be positive in x/y/z");
    }
}

void ValidateTubsParameters(double rMin, double rMax, double halfZ, double, double deltaPhi)
{
    if (rMin < 0.0) throw std::runtime_error("Tubs rMin must be >= 0");
    if (rMax <= rMin) throw std::runtime_error("Tubs rMax must be > rMin");
    if (halfZ <= 0.0) throw std::runtime_error("Tubs halfZ must be > 0");
    if (deltaPhi <= 0.0) throw std::runtime_error("Tubs deltaPhi must be > 0");
}

std::string MakePath(const std::string& parentPath, const std::string& childName)
{
    const std::string child = NormalizeVolumeName(childName);
    if (parentPath.empty() || parentPath == "/") return "/" + child;
    return parentPath + "/" + child;
}

}  // namespace GeometryUtils
