#pragma once

#include "G4VUserParallelWorld.hh"

#include <memory>
#include <string>
#include <vector>

class G4LogicalVolume;
class G4VPhysicalVolume;
class OutputManager;

namespace parallel_world {

class ParallelWorldConfig;

// Builds the ghost scoring world declared by [parallel_world]:
// a world the same size as the mass world (Geant4 copies the mass-world solid
// when GetWorld() is called), filled with G4_Galactic, one box per configured
// volume, and one internal navigation envelope per declared grid whose cells
// are real daughters. The envelope is not a scoring volume.
//
// Construct() runs once on the master thread; ConstructSD() runs once per
// worker thread and attaches a fresh ParallelScoringDetector to each ghost
// logical volume of that thread. No mutable scoring state is shared.
class ScoringParallelWorld : public G4VUserParallelWorld {
public:
    explicit ScoringParallelWorld(std::shared_ptr<const ParallelWorldConfig> config);

    void Construct() override;
    void ConstructSD() override;

    // Not owned; used to latch per-thread SD binding failures into the run
    // summary/exit status. Set before Geant4 constructs the parallel SDs.
    void SetOutputManager(OutputManager* outputManager) { outputManager_ = outputManager; }

    const std::vector<G4LogicalVolume*>& VolumeLogicals() const { return volumeLogicals_; }
    const std::vector<G4VPhysicalVolume*>& VolumePlacements() const { return volumePlacements_; }
    // Internal navigation envelopes (one per declared grid, in config order);
    // they are never scored and never counted as scoring volumes.
    const std::vector<G4LogicalVolume*>& EnvelopeLogicals() const { return envelopeLogicals_; }
    const std::vector<G4VPhysicalVolume*>& EnvelopePlacements() const { return envelopePlacements_; }
    // The kernel-owned ghost world root; valid after Construct().
    G4VPhysicalVolume* GhostWorld() { return GetWorld(); }
    G4LogicalVolume* FindLogicalVolume(const std::string& name) const;
    G4VPhysicalVolume* FindPlacement(const std::string& name) const;

private:
    std::shared_ptr<const ParallelWorldConfig> config_;
    OutputManager* outputManager_ = nullptr;  // not owned
    std::vector<G4LogicalVolume*> volumeLogicals_;
    std::vector<G4VPhysicalVolume*> volumePlacements_;
    std::vector<G4LogicalVolume*> envelopeLogicals_;
    std::vector<G4VPhysicalVolume*> envelopePlacements_;
    std::vector<std::vector<G4VPhysicalVolume*>> envelopeCells_;
};

}  // namespace parallel_world
