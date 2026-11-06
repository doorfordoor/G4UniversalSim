#pragma once

#include "G4VSensitiveDetector.hh"

#include <string>
#include <vector>

class G4HCofThisEvent;
class G4Step;
class G4VPhysicalVolume;
class OutputManager;
class ScoringManager;

namespace parallel_world {

class ParallelWorldConfig;
struct VolumeSpec;

// Sensitive detectors for the parallel scoring world.
//
// Scope::Leaf is attached to every configured ghost scoring volume (box or grid
// cell).  Geant4 chooses the SD from the ghost pre-step-point volume, so leaf
// steps keep the original path: pre-point volume -> configuration lookup ->
// score.
//
// Scope::WorldRoot is attached to the ghost world root volume and
// Scope::Envelope to each grid's real navigation envelope.  Geant4 delivers a
// step to the sensitive detector of its ghost pre-step-point volume, so a step
// whose pre-point is located on the root/envelope (the track can run along a
// shared face/edge/corner of adjacent cells) is resolved here against the real
// constructed G4Box placements.  The resolution uses the real world -> parent
// -> placement transform; steps outside every configured cell (vacuum / gap /
// outer-face exit) are skipped instead of dumping world quantities into a
// scoring box.
class ParallelScoringDetector : public G4VSensitiveDetector {
public:
    enum class Scope { Leaf, WorldRoot, Envelope };

    // config/outputManager are not owned. placements/world are the real ghost
    // physical volumes built by ScoringParallelWorld::Construct() (same objects
    // in every worker thread); they are only used by Scope::WorldRoot.
    ParallelScoringDetector(const std::string& name, const ParallelWorldConfig* config,
                            OutputManager* outputManager,
                            Scope scope = Scope::Leaf,
                            const std::vector<G4VPhysicalVolume*>* placements = nullptr,
                            G4VPhysicalVolume* world = nullptr,
                            G4VPhysicalVolume* parent = nullptr);

    G4bool ProcessHits(G4Step* step, G4TouchableHistory* history) override;

    // Contract H3-4 R-RUNTIME: with hits CSV output enabled on a real worker,
    // the legacy hits file must exist with its header even when no mass hit is
    // produced.  Scope::WorldRoot opens that real per-thread writer through the
    // live thread-local ScoringManager/OutputManager so the regular Close()
    // path flushes and registers it.  No ghost step is ever written to hits.
    void Initialize(G4HCofThisEvent* hitCollection) override;

    // Latch the contract-H3 failure used when ProcessHits runs without a
    // thread-local ScoringManager.  Exposed so the component check can drive
    // the exact production path without constructing a Geant4 transport step.
    static void ReportMissingThreadManager(OutputManager* outputManager);

private:
    G4bool ProcessLeafStep(G4Step* step, ScoringManager* manager);
    G4bool ProcessWorldRootStep(G4Step* step, ScoringManager* manager);

    enum class OwnerResolution { Owner, Skip, Failure };
    // Resolve the unique owning cell for a step whose ghost pre-point is the
    // world root.  Owner -> spec/volumePath filled; Skip -> the whole step is
    // outside every configured scoring volume (vacuum or a gap); Failure -> the
    // step physically crosses a scoring volume boundary without a unique owner
    // (must not be silently dropped).
    OwnerResolution ResolveOwnerStep(const G4Step& step, const VolumeSpec*& spec,
                                     std::string& volumePath) const;

    const ParallelWorldConfig* config_ = nullptr;   // owned by DetectorConstruction
    OutputManager* outputManager_ = nullptr;        // not owned; used to latch failures
    Scope scope_ = Scope::Leaf;
    const std::vector<G4VPhysicalVolume*>* placements_ = nullptr;  // not owned
    G4VPhysicalVolume* world_ = nullptr;                            // not owned
    G4VPhysicalVolume* parent_ = nullptr;  // not owned; the envelope for Scope::Envelope
};

}  // namespace parallel_world
