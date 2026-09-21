#include "Templates/GeometryTemplate.hh"

#include "Config/ConfigManager.hh"
#include "Geometry/GeometryConfig.hh"
#include "Utils/FileUtils.hh"

#include <stdexcept>

VolumeNode GeometryTemplate::BuildNodesFromFile(const std::string& filename) const
{
    if (!FileUtils::IsFile(filename)) {
        throw std::runtime_error("Template '" + Name() + "' config file does not exist: '" + filename + "'");
    }

    ConfigManager config;
    config.LoadMainConfig(filename);
    diagnostics_.clear();
    try {
        ValidateConfig(config);
        CollectGeometryConfigDiagnostics(
            config.GetMainConfigPath(), config.GetFields(), config.GetSectionInfo(), Name(), diagnostics_
        );
        return BuildNodes(config);
    } catch (const std::exception& error) {
        throw std::runtime_error(
            "Template '" + Name() + "' failed to build geometry from file '"
            + filename + "': " + error.what()
        );
    }
}

const std::vector<GeometryConfigDiagnostic>& GeometryTemplate::GetDiagnostics() const
{
    return diagnostics_;
}

VolumeNode GeometryTemplate::BuildNodes(const GeometryConfig& geometryConfig) const
{
    return geometryConfig.BuildTree();
}

void GeometryTemplate::ValidateConfig(const ConfigManager&) const
{
}
