#pragma once
// Execution-thread-owned stores for the supported H4 mass-geometry domain.
#include "G4GeometryCellImportance.hh"
#include "G4GeometryCellWeight.hh"
#include "G4LogicalVolume.hh"
#include "G4VIStore.hh"
#include "G4VPhysicalVolume.hh"
#include "G4VWeightWindowStore.hh"
#include <stdexcept>

namespace biasing_detail {
template<class Interface, class Cells>
class MassGeometryStore : public Interface {
public:
    explicit MassGeometryStore(const G4VPhysicalVolume& world) : world_(world) {}
    MassGeometryStore(const MassGeometryStore&) = delete;
    MassGeometryStore& operator=(const MassGeometryStore&) = delete;

    const G4VPhysicalVolume& GetWorldVolume() const override { return world_; }
    G4bool IsKnown(const G4GeometryCell& cell) const override
    {
        return InWorld(cell) && cells_.find(cell) != cells_.end();
    }
protected:
    void Insert(const G4GeometryCell& cell, const typename Cells::mapped_type& value)
    {
        if (!InWorld(cell) || !cells_.emplace(cell, value).second)
            throw std::runtime_error("H4 sampling cell outside tracking world or already registered");
    }
    Cells cells_;
private:
    bool InWorld(const G4GeometryCell& cell) const
    {
        const auto* volume = &cell.GetPhysicalVolume();
        return volume == &world_ || world_.GetLogicalVolume()->IsAncestor(volume);
    }
    const G4VPhysicalVolume& world_;
};

class ImportanceStore final : public MassGeometryStore<G4VIStore, G4GeometryCellImportance> {
public:
    using MassGeometryStore::MassGeometryStore;
    void AddImportanceGeometryCell(G4double importance, const G4VPhysicalVolume& volume, G4int copy)
    {
        Insert(G4GeometryCell(volume, copy), importance);
    }
    G4double GetImportance(const G4GeometryCell& cell) const override { return cells_.at(cell); }
};

class OwnedWeightWindowStore : public MassGeometryStore<G4VWeightWindowStore, G4GeometryCellWeight> {
public:
    using MassGeometryStore::MassGeometryStore;
    void AddUpperEboundLowerWeightPairs(const G4GeometryCell& cell,
                                        const G4UpperEnergyToLowerWeightMap& weights)
    {
        Insert(cell, weights);
    }
    G4double GetLowerWeight(const G4GeometryCell& cell, G4double energy) const override
    {
        const auto& weights = cells_.at(cell);
        const auto bound = weights.upper_bound(energy);
        if (bound == weights.end()) throw std::out_of_range("H4 sampling energy has no upper bound");
        return bound->second;
    }
};
} // namespace biasing_detail
