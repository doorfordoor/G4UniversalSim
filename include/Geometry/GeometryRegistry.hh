#pragma once

#include <map>
#include <set>
#include <string>
#include <vector>

class G4LogicalVolume;
class G4VPhysicalVolume;

class GeometryRegistry {
public:
    GeometryRegistry() = default;

    void Clear();

    void RegisterLogicalVolume(const std::string& name, G4LogicalVolume* lv);
    void TrackImportedLogicalVolume(G4LogicalVolume* logical);
    void RegisterPhysicalVolume(const std::string& name, G4VPhysicalVolume* pv);

    bool HasLogicalVolume(const std::string& name) const;
    bool HasPhysicalVolume(const std::string& name) const;

    G4LogicalVolume* GetLogicalVolume(const std::string& name) const;
    G4VPhysicalVolume* GetPhysicalVolume(const std::string& name) const;

    void MarkSensitiveVolume(const std::string& name);
    // GDML identities must not pass through the INI case-insensitive name map.
    void MarkSensitiveLogicalVolume(G4LogicalVolume* logical);
    void MarkBiasVolume(const std::string& name);

    bool IsSensitiveVolume(const std::string& name) const;
    bool IsBiasVolume(const std::string& name) const;

    std::vector<std::string> GetLogicalVolumeNames() const;
    std::vector<std::string> GetPhysicalVolumeNames() const;
    std::vector<std::string> GetSensitiveVolumeNames() const;
    std::vector<std::string> GetBiasVolumeNames() const;

    std::vector<G4LogicalVolume*> GetSensitiveLogicalVolumes() const;
    std::vector<G4LogicalVolume*> GetBiasLogicalVolumes() const;

    void RegisterRegionName(const std::string& volumeName, const std::string& regionName);
    bool HasRegionName(const std::string& volumeName) const;
    std::string GetRegionName(const std::string& volumeName) const;

    void PrintSummary() const;

private:
    static std::string Normalize(const std::string& name);
    static void ValidateName(const std::string& name, const std::string& action);

    std::map<std::string, G4LogicalVolume*> logicalVolumes_;
    std::map<std::string, G4LogicalVolume*> importedLogicalVolumes_;
    std::set<std::string> ambiguousImportedLogicalNames_;
    std::map<std::string, G4VPhysicalVolume*> physicalVolumes_;
    std::set<std::string> sensitiveVolumes_;
    std::vector<G4LogicalVolume*> sensitiveLogicalVolumes_;
    std::set<std::string> biasVolumes_;
    std::map<std::string, std::string> regionNames_;
};
