#pragma once

#include "Geometry/VolumeNode.hh"

#include <map>
#include <set>
#include <stdexcept>
#include <string>
#include <vector>

class ConfigManager;

class GeometryConfig {
public:
    GeometryConfig() = default;

    void Load(const std::string& filename);
    void LoadFromConfigManager(const ConfigManager& config);
    void Clear();

    bool HasVolume(const std::string& name) const;
    const VolumeNode& GetVolume(const std::string& name) const;
    VolumeNode& GetVolumeMutable(const std::string& name);

    std::vector<std::string> GetVolumeNames() const;
    std::vector<std::string> GetSensitiveVolumeNames() const;
    std::vector<std::string> GetBiasVolumeNames() const;
    std::vector<std::string> GetRegionNames() const;

    const std::vector<VolumeNode>& GetFlatVolumes() const;
    VolumeNode BuildTree() const;
    void AddVolume(const VolumeNode& node);
    void Validate() const;
    const std::string& GetFilename() const;

private:
    using Section = std::map<std::string, std::string>;

    static std::string Normalize(const std::string& name);
    static bool IsCutKey(const std::string& key);
    static bool IsKnownKey(const std::string& key);
    static std::runtime_error Error(
        const std::string& filename,
        const std::string& section,
        const std::string& volume,
        const std::string& key,
        const std::string& message
    );

    VolumeNode ParseVolumeSection(
        const std::string& sectionName,
        const Section& values
    ) const;

    void ValidateNoCycles() const;
    bool HasCycleFrom(
        const std::string& name,
        std::set<std::string>& visiting,
        std::set<std::string>& visited
    ) const;

    std::string filename_;
    std::vector<VolumeNode> flatVolumes_;
    std::map<std::string, std::size_t> indexByName_;
};
