#pragma once

#include <array>
#include <map>
#include <memory>
#include <set>
#include <string>
#include <vector>

class G4LogicalVolume;
class G4VPhysicalVolume;
class G4PhantomParameterisation;
struct VoxelGridDescriptor;

struct VoxelScoringBinding {
    std::string gridId;
    const G4VPhysicalVolume* container = nullptr;
    const G4PhantomParameterisation* parameterisation = nullptr;
    std::array<int, 3> shape{};
    std::shared_ptr<const VoxelGridDescriptor> descriptor;
    std::array<double, 3> worldCentre{};
};

class GeometryRegistry {
public:
    GeometryRegistry() = default;

    void Clear();

    void RegisterLogicalVolume(const std::string& name, G4LogicalVolume* lv);
    void TrackImportedLogicalVolume(G4LogicalVolume* logical);
    void RegisterPhysicalVolume(const std::string& name, G4VPhysicalVolume* pv);

    void RegisterVoxelScoring(G4VPhysicalVolume* leaf, VoxelScoringBinding binding);
    const VoxelScoringBinding* FindVoxelScoring(const G4VPhysicalVolume* leaf) const;
    bool HasVoxelScoring() const { return !voxelScoring_.empty(); }
    const auto& GetVoxelScoringBindings() const { return voxelScoring_; }
    void SetVoxelGeometryInput(const std::string& path, const std::string& sha);
    void SetVoxelWorldCentre(const G4VPhysicalVolume* leaf, std::array<double, 3> centre);
    const std::string& GetVoxelGeometryPath() const { return voxelGeometryPath_; }
    const std::string& GetVoxelGeometrySha() const { return voxelGeometrySha_; }

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
    std::map<const G4VPhysicalVolume*, VoxelScoringBinding> voxelScoring_;
    std::string voxelGeometryPath_;
    std::string voxelGeometrySha_;
    std::set<std::string> sensitiveVolumes_;
    std::vector<G4LogicalVolume*> sensitiveLogicalVolumes_;
    std::set<std::string> biasVolumes_;
    std::map<std::string, std::string> regionNames_;
};
