#include "Geometry/GeometryRegistry.hh"

#include "Utils/StringUtils.hh"

#include "G4ios.hh"

#include <stdexcept>

void GeometryRegistry::Clear()
{
    logicalVolumes_.clear();
    physicalVolumes_.clear();
    sensitiveVolumes_.clear();
    biasVolumes_.clear();
    regionNames_.clear();
}

void GeometryRegistry::RegisterLogicalVolume(const std::string& name, G4LogicalVolume* lv)
{
    ValidateName(name, "register logical volume");
    if (!lv) throw std::runtime_error("Cannot register null G4LogicalVolume for '" + name + "'");
    logicalVolumes_[Normalize(name)] = lv; // Last registration wins to support geometry reinitialization.
}

void GeometryRegistry::RegisterPhysicalVolume(const std::string& name, G4VPhysicalVolume* pv)
{
    ValidateName(name, "register physical volume");
    if (!pv) throw std::runtime_error("Cannot register null G4VPhysicalVolume for '" + name + "'");
    physicalVolumes_[Normalize(name)] = pv; // Last registration wins to support geometry reinitialization.
}

bool GeometryRegistry::HasLogicalVolume(const std::string& name) const
{
    return logicalVolumes_.find(Normalize(name)) != logicalVolumes_.end();
}

bool GeometryRegistry::HasPhysicalVolume(const std::string& name) const
{
    return physicalVolumes_.find(Normalize(name)) != physicalVolumes_.end();
}

G4LogicalVolume* GeometryRegistry::GetLogicalVolume(const std::string& name) const
{
    const auto it = logicalVolumes_.find(Normalize(name));
    if (it == logicalVolumes_.end()) throw std::runtime_error("Logical volume not found: '" + name + "'");
    return it->second;
}

G4VPhysicalVolume* GeometryRegistry::GetPhysicalVolume(const std::string& name) const
{
    const auto it = physicalVolumes_.find(Normalize(name));
    if (it == physicalVolumes_.end()) throw std::runtime_error("Physical volume not found: '" + name + "'");
    return it->second;
}

void GeometryRegistry::MarkSensitiveVolume(const std::string& name)
{
    ValidateName(name, "mark sensitive volume");
    sensitiveVolumes_.insert(Normalize(name));
}

void GeometryRegistry::MarkBiasVolume(const std::string& name)
{
    ValidateName(name, "mark bias volume");
    biasVolumes_.insert(Normalize(name));
}

bool GeometryRegistry::IsSensitiveVolume(const std::string& name) const
{
    return sensitiveVolumes_.find(Normalize(name)) != sensitiveVolumes_.end();
}

bool GeometryRegistry::IsBiasVolume(const std::string& name) const
{
    return biasVolumes_.find(Normalize(name)) != biasVolumes_.end();
}

std::vector<std::string> GeometryRegistry::GetLogicalVolumeNames() const
{
    std::vector<std::string> names;
    for (const auto& item : logicalVolumes_) names.push_back(item.first);
    return names;
}

std::vector<std::string> GeometryRegistry::GetPhysicalVolumeNames() const
{
    std::vector<std::string> names;
    for (const auto& item : physicalVolumes_) names.push_back(item.first);
    return names;
}

std::vector<std::string> GeometryRegistry::GetSensitiveVolumeNames() const
{
    return {sensitiveVolumes_.begin(), sensitiveVolumes_.end()};
}

std::vector<std::string> GeometryRegistry::GetBiasVolumeNames() const
{
    return {biasVolumes_.begin(), biasVolumes_.end()};
}

std::vector<G4LogicalVolume*> GeometryRegistry::GetSensitiveLogicalVolumes() const
{
    std::vector<G4LogicalVolume*> result;
    for (const std::string& name : sensitiveVolumes_) {
        const auto it = logicalVolumes_.find(name);
        if (it != logicalVolumes_.end()) result.push_back(it->second);
    }
    return result;
}

std::vector<G4LogicalVolume*> GeometryRegistry::GetBiasLogicalVolumes() const
{
    std::vector<G4LogicalVolume*> result;
    for (const std::string& name : biasVolumes_) {
        const auto it = logicalVolumes_.find(name);
        if (it != logicalVolumes_.end()) result.push_back(it->second);
    }
    return result;
}

void GeometryRegistry::RegisterRegionName(const std::string& volumeName, const std::string& regionName)
{
    ValidateName(volumeName, "register region name");
    if (StringUtils::Trim(regionName).empty()) {
        throw std::runtime_error("Cannot register empty region name for volume '" + volumeName + "'");
    }
    regionNames_[Normalize(volumeName)] = regionName;
}

bool GeometryRegistry::HasRegionName(const std::string& volumeName) const
{
    return regionNames_.find(Normalize(volumeName)) != regionNames_.end();
}

std::string GeometryRegistry::GetRegionName(const std::string& volumeName) const
{
    const auto it = regionNames_.find(Normalize(volumeName));
    if (it == regionNames_.end()) throw std::runtime_error("Region name not found for volume '" + volumeName + "'");
    return it->second;
}

void GeometryRegistry::PrintSummary() const
{
    G4cout << "[GeometryRegistry] logical=" << logicalVolumes_.size()
           << ", physical=" << physicalVolumes_.size()
           << ", sensitive=" << sensitiveVolumes_.size()
           << ", bias=" << biasVolumes_.size()
           << ", regions=" << regionNames_.size() << G4endl;
}

std::string GeometryRegistry::Normalize(const std::string& name)
{
    return StringUtils::ToLower(StringUtils::Trim(name));
}

void GeometryRegistry::ValidateName(const std::string& name, const std::string& action)
{
    if (StringUtils::Trim(name).empty()) {
        throw std::runtime_error("Cannot " + action + " with empty volume name");
    }
}
