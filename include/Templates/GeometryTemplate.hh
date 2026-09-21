#pragma once

#include "Geometry/VolumeNode.hh"
#include "Geometry/GeometryConfigDiagnostic.hh"

#include <string>

class ConfigManager;
class GeometryConfig;

class GeometryTemplate {
public:
    virtual ~GeometryTemplate() = default;

    virtual std::string Name() const = 0;

    virtual VolumeNode BuildNodes(const ConfigManager& config) const = 0;

    virtual VolumeNode BuildNodesFromFile(const std::string& filename) const;

    virtual VolumeNode BuildNodes(const GeometryConfig& geometryConfig) const;

    virtual void ValidateConfig(const ConfigManager& config) const;

    const std::vector<GeometryConfigDiagnostic>& GetDiagnostics() const;

protected:
    mutable std::vector<GeometryConfigDiagnostic> diagnostics_;
};
