#include "Templates/ArrayTemplate.hh"

#include "Config/ConfigManager.hh"
#include "Geometry/GeometryUtils.hh"
#include "Utils/StringUtils.hh"
#include "Utils/UnitParser.hh"

#include <stdexcept>

namespace {

struct Counts3 { int x = 0; int y = 0; int z = 0; };

Counts3 ParseCounts(const std::string& text)
{
    const auto parts = StringUtils::Split(text, ',', true);
    if (parts.size() != 3) throw std::runtime_error("array counts expects 3 integers: '" + text + "'");
    Counts3 c{std::stoi(StringUtils::Trim(parts[0])), std::stoi(StringUtils::Trim(parts[1])), std::stoi(StringUtils::Trim(parts[2]))};
    if (c.x <= 0 || c.y <= 0 || c.z <= 0) throw std::runtime_error("array counts must be positive: '" + text + "'");
    return c;
}

}  // namespace

std::string ArrayTemplate::Name() const
{
    return "array";
}

VolumeNode ArrayTemplate::BuildNodes(const ConfigManager& config) const
{
    ValidateConfig(config);

    VolumeNode world("world");
    world.shape = VolumeShape::Box;
    world.shapeName = "box";
    world.size = GeometryUtils::ParseVec3(config.GetString("world", "size"));
    world.materialName = config.GetString("world", "material");
    world.ValidateBasic();

    const std::string base = config.GetString("array", "name", "PixelArray");
    const Counts3 counts = ParseCounts(config.GetString("array", "counts"));
    const Vec3 elementSize = GeometryUtils::ParseVec3(config.GetString("array", "element_size"));
    const Vec3 pitch = GeometryUtils::ParseVec3(config.GetString("array", "pitch"));
    if (pitch.x < elementSize.x || pitch.y < elementSize.y || (counts.z > 1 && pitch.z < elementSize.z)) {
        throw std::runtime_error("array pitch must be >= element_size on active axes");
    }
    const Vec3 center = GeometryUtils::ParseVec3(config.GetString("array", "center", "0 mm, 0 mm, 0 mm"));

    for (int i = 0; i < counts.x; ++i) {
        for (int j = 0; j < counts.y; ++j) {
            for (int k = 0; k < counts.z; ++k) {
                VolumeNode pixel(base + "_" + std::to_string(i) + "_" + std::to_string(j) + "_" + std::to_string(k));
                pixel.parentName = world.name;
                pixel.shapeName = config.GetString("array", "shape", "box");
                pixel.shape = GeometryUtils::ParseShape(pixel.shapeName);
                pixel.size = elementSize;
                pixel.materialName = config.GetString("array", "material");
                pixel.position = {
                    center.x + (static_cast<double>(i) - 0.5 * (counts.x - 1)) * pitch.x,
                    center.y + (static_cast<double>(j) - 0.5 * (counts.y - 1)) * pitch.y,
                    center.z + (static_cast<double>(k) - 0.5 * (counts.z - 1)) * pitch.z
                };
                pixel.sensitive = config.GetBool("array", "sensitive", true);
                pixel.bias = config.GetBool("array", "bias", false);
                pixel.regionName = config.GetString("array", "region", "");
                pixel.ValidateBasic();
                world.AddChild(pixel);
            }
        }
    }

    return world;
}

VolumeNode ArrayTemplate::BuildNodesFromFile(const std::string& filename) const
{
    return GeometryTemplate::BuildNodesFromFile(filename);
}

void ArrayTemplate::ValidateConfig(const ConfigManager& config) const
{
    for (const auto& key : {"size", "material"}) {
        if (!config.HasKey("world", key)) throw std::runtime_error(std::string("array missing [world]/") + key);
    }
    for (const auto& key : {"material", "element_size", "counts", "pitch"}) {
        if (!config.HasKey("array", key)) throw std::runtime_error(std::string("array missing [array]/") + key);
    }
}
