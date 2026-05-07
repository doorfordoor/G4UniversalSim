#pragma once

#include "Templates/GeometryTemplate.hh"

class GDMLTemplate : public GeometryTemplate {
public:
    std::string Name() const override;
    VolumeNode BuildNodes(const ConfigManager& config) const override;
    VolumeNode BuildNodesFromFile(const std::string& filename) const override;
    void ValidateConfig(const ConfigManager& config) const override;
};
