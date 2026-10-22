#include "Templates/GDMLTemplate.hh"

#include "Config/ConfigManager.hh"
#include "Geometry/GdmlIO.hh"
#include "Geometry/GeometryUtils.hh"
#include "Utils/StringUtils.hh"

#include <filesystem>
#include <stdexcept>

namespace {

std::string ResolveGdmlPath(const ConfigManager& config)
{
    std::filesystem::path file = std::filesystem::u8path(StringUtils::Trim(config.GetString("gdml", "file")));
    if (file.is_relative()) {
        const std::string base = config.GetMainConfigPath();
        if (!base.empty()) file = std::filesystem::u8path(base).parent_path() / file;
    }
    return file.u8string();
}

}  // namespace

std::string GDMLTemplate::Name() const
{
    return "gdml";
}

// The node tree only carries the import request; GeometryManager::BuildWorld
// reads the file with G4GDMLParser when Geant4 constructs the geometry.
VolumeNode GDMLTemplate::BuildNodes(const ConfigManager& config) const
{
    ValidateConfig(config);

    VolumeNode world(config.GetString("gdml", "world_name", "world"));
    world.shape = VolumeShape::Box;
    world.shapeName = "gdml_placeholder";
    world.materialName = "G4_AIR";
    world.size = {1.0, 1.0, 1.0};
    world.userProperties["gdml_file"] = ResolveGdmlPath(config);
    world.userProperties["gdml_validate"] = config.GetBool("gdml", "validate", false) ? "true" : "false";
    world.userProperties["template"] = "gdml";

    if (config.HasKey("gdml", "sensitive_volumes")) {
        world.userProperties["sensitive_volumes"] = config.GetString("gdml", "sensitive_volumes");
    }
    if (config.HasKey("gdml", "bias_volumes")) {
        world.userProperties["bias_volumes"] = config.GetString("gdml", "bias_volumes");
    }
    return world;
}

VolumeNode GDMLTemplate::BuildNodesFromFile(const std::string& filename) const
{
    return GeometryTemplate::BuildNodesFromFile(filename);
}

void GDMLTemplate::ValidateConfig(const ConfigManager& config) const
{
    if (!GdmlIO::Available()) {
        throw std::runtime_error(
            "Geometry capability 'GDML' is not available in this build (Geant4 without GDML/XercesC). "
            "Use a supported geometry template and regular volume definitions instead, or rebuild "
            "Geant4 with GEANT4_USE_GDML=ON."
        );
    }
    if (!config.HasKey("gdml", "file") || StringUtils::Trim(config.GetString("gdml", "file")).empty()) {
        throw std::runtime_error("GDML geometry requires [gdml]/file = <model.gdml>");
    }
    const std::string path = ResolveGdmlPath(config);
    if (!std::filesystem::is_regular_file(std::filesystem::u8path(path))) {
        throw std::runtime_error("GDML file does not exist: '" + path + "'");
    }
    (void)config.GetBool("gdml", "validate", false);
}
