#pragma once

#include "Geometry/VolumeNode.hh"

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
};
