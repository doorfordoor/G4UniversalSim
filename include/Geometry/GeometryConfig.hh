#pragma once

#include "Geometry/VolumeNode.hh"
#include "Config/IniReader.hh"

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

    struct BooleanSectionId {
        std::string targetVolumeName;
        int index = -1;
    };

    static std::string Normalize(const std::string& name);
    static bool IsCutKey(const std::string& key);
    static bool IsKnownKey(const std::string& key);
    static bool IsBooleanSectionName(const std::string& sectionName);
    static BooleanSectionId ParseBooleanSectionName(const std::string& sectionName);
    static std::runtime_error Error(
        const std::string& filename,
        const std::string& section,
        const std::string& volume,
        const std::string& key,
        const std::string& message
    );
    std::runtime_error FieldError(
        const std::string& section,
        const std::string& volume,
        const std::string& key,
        const std::string& message,
        const std::string& suggestion = ""
    ) const;
    const IniFieldInfo* FindField(const std::string& section, const std::string& key) const;
    void ValidateCutFields() const;
    void ValidateShapeContract(
        const std::string& section,
        const std::string& volume,
        VolumeShape shape,
        const Vec3& size,
        const std::vector<double>& parameters,
        const std::map<std::string, std::string>& properties,
        bool booleanTool
    ) const;
    void ValidateCopyNumber(const std::string& section, const std::string& volume) const;

    VolumeNode ParseVolumeSection(
        const std::string& sectionName,
        const Section& values
    ) const;
    BooleanSolidOperation ParseBooleanSection(
        const std::string& sectionName,
        const Section& values,
        const std::string& targetName,
        int index
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
    std::vector<IniFieldInfo> sourceFields_;
};
