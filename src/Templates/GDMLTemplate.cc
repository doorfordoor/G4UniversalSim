#include "Templates/GDMLTemplate.hh"

#include "Config/ConfigManager.hh"
#include "Geometry/GeometryUtils.hh"

#include <stdexcept>

std::string GDMLTemplate::Name() const
{
    return "gdml";
}

VolumeNode GDMLTemplate::BuildNodes(const ConfigManager& config) const
{
    ValidateConfig(config);

    VolumeNode world(config.GetString("gdml", "world_name", "world"));
    world.shape = VolumeShape::Box;
    world.shapeName = "gdml_placeholder";
    world.materialName = "G4_AIR";
    world.size = {1.0, 1.0, 1.0};
    world.userProperties["gdml_file"] = config.GetString("gdml", "file");
    world.userProperties["gdml_world_name"] = config.GetString("gdml", "world_name", world.name);
    world.userProperties["template"] = "gdml_placeholder";

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
    if (!config.HasKey("gdml", "file")) throw std::runtime_error("gdml template missing [gdml]/file");
}
