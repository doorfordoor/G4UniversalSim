#include "ParallelWorld/ScoringParallelWorld.hh"

#include "ParallelWorld/ParallelScoringDetector.hh"
#include "ParallelWorld/ParallelWorldConfig.hh"

#include "Output/OutputManager.hh"
#include "Scoring/ThreadLocalScoringContext.hh"

#include "G4Box.hh"
#include "G4LogicalVolume.hh"
#include "G4Material.hh"
#include "G4PVPlacement.hh"
#include "G4SDManager.hh"
#include "G4SystemOfUnits.hh"
#include "G4ThreeVector.hh"
#include "G4VPhysicalVolume.hh"

#include <map>
#include <stdexcept>
#include <string>

namespace parallel_world {

ScoringParallelWorld::ScoringParallelWorld(std::shared_ptr<const ParallelWorldConfig> config)
    : G4VUserParallelWorld(config ? config->name() : std::string("ScoringWorld")), config_(std::move(config))
{
}

void ScoringParallelWorld::Construct()
{
    if (!config_ || !config_->enabled()) {
        throw std::runtime_error("ScoringParallelWorld::Construct called for a disabled parallel world");
    }
    G4VPhysicalVolume* world = GetWorld();
    if (world == nullptr) {
        throw std::runtime_error("ScoringParallelWorld::Construct failed: Geant4 returned no ghost world for '" +
                                 config_->name() + "'");
    }
    G4LogicalVolume* worldLogical = world->GetLogicalVolume();
    if (worldLogical == nullptr) {
        throw std::runtime_error("ScoringParallelWorld::Construct failed: ghost world has no logical volume");
    }
    const G4Material* worldMaterial = config_->worldMaterial();
    if (worldMaterial == nullptr) {
        worldMaterial = G4Material::GetMaterial("G4_Galactic", false);
    }
    if (worldMaterial == nullptr) {
        throw std::runtime_error(
            "ScoringParallelWorld::Construct failed: G4_Galactic is not defined; the ghost world needs a vacuum "
            "material");
    }
    worldLogical->SetMaterial(const_cast<G4Material*>(worldMaterial));

    volumeLogicals_.clear();
    volumePlacements_.clear();
    envelopeLogicals_.clear();
    envelopePlacements_.clear();
    envelopeCells_.clear();

    // Internal navigation envelopes: one real box per declared grid with
    // exactly the declared grid bounds. Without it, a track that runs exactly
    // along an internal shared face of the cells is never limited by Geant4,
    // so no ghost step ever enters the grid (H3-4 grid fix r3). The envelope is
    // not a scoring volume: it is not in config volumes, not counted in
    // volume_count and it never feeds ScoreParallelHit.
    std::map<std::string, std::size_t> envelopeIndexByName;
    for (const auto& envelope : config_->envelopes()) {
        const G4Material* material =
            envelope.materialObject != nullptr ? envelope.materialObject : worldMaterial;
        if (material == nullptr) {
            throw std::runtime_error("ScoringParallelWorld::Construct failed: unknown material for "
                                     "navigation envelope '" + envelope.name + "'");
        }
        auto* solid = new G4Box(envelope.name + "_envelope_box",
                                envelope.sizeMm[0] * 0.5 * mm,
                                envelope.sizeMm[1] * 0.5 * mm,
                                envelope.sizeMm[2] * 0.5 * mm);
        auto* logical = new G4LogicalVolume(solid, const_cast<G4Material*>(material),
                                            envelope.name + "_envelope");
        auto* placement = new G4PVPlacement(nullptr,
                                            G4ThreeVector(envelope.centreMm[0] * mm,
                                                          envelope.centreMm[1] * mm,
                                                          envelope.centreMm[2] * mm),
                                            logical, envelope.name, worldLogical, false, 0);
        envelopeIndexByName[envelope.name] = envelopeLogicals_.size();
        envelopeLogicals_.push_back(logical);
        envelopePlacements_.push_back(placement);
        envelopeCells_.emplace_back();
    }

    for (const auto& volume : config_->volumes()) {
        auto* solid = new G4Box(volume.name + "_box", volume.sizeMm[0] * 0.5 * mm,
                                volume.sizeMm[1] * 0.5 * mm, volume.sizeMm[2] * 0.5 * mm);
        const G4Material* material = volume.materialObject != nullptr
                                         ? volume.materialObject
                                         : G4Material::GetMaterial(volume.material, false);
        if (material == nullptr) {
            delete solid;
            throw std::runtime_error("ScoringParallelWorld::Construct failed: unknown material '" +
                                     volume.material + "' for parallel volume '" + volume.name + "'");
        }
        auto* logical = new G4LogicalVolume(solid, const_cast<G4Material*>(material), volume.name);
        // Global size, position and material of every cell are unchanged. Grid
        // cells are placed inside the real envelope with a relative transform,
        // so the composed global centre is exactly the declared one.
        G4LogicalVolume* mother = worldLogical;
        G4ThreeVector position(volume.centreMm[0] * mm, volume.centreMm[1] * mm,
                               volume.centreMm[2] * mm);
        std::vector<G4VPhysicalVolume*>* envelopeCells = nullptr;
        if (!volume.envelope.empty()) {
            const auto found = envelopeIndexByName.find(volume.envelope);
            if (found == envelopeIndexByName.end()) {
                delete logical;
                throw std::runtime_error("ScoringParallelWorld::Construct failed: grid cell '" +
                                         volume.name + "' references unknown envelope '" +
                                         volume.envelope + "'");
            }
            const auto index = found->second;
            const auto& envelope = config_->envelopes()[index];
            mother = envelopeLogicals_[index];
            position -= G4ThreeVector(envelope.centreMm[0] * mm, envelope.centreMm[1] * mm,
                                      envelope.centreMm[2] * mm);
            envelopeCells = &envelopeCells_[index];
        }
        auto* placement = new G4PVPlacement(nullptr, position, logical, volume.name, mother, false, 0);
        volumeLogicals_.push_back(logical);
        volumePlacements_.push_back(placement);
        if (envelopeCells != nullptr) envelopeCells->push_back(placement);
    }
}

void ScoringParallelWorld::ConstructSD()
{
    if (!config_ || !config_->enabled()) return;
    G4VPhysicalVolume* world = GetWorld();
    if (world == nullptr || world->GetLogicalVolume() == nullptr) {
        throw std::runtime_error(
            "ScoringParallelWorld::ConstructSD failed: ghost world is missing; Construct() did not run");
    }
    const std::string detectorName = "ParallelScoringSD_" + config_->name();
    G4SDManager* sdManager = G4SDManager::GetSDMpointer();
    if (sdManager == nullptr) {
        throw std::runtime_error("ScoringParallelWorld::ConstructSD failed: G4SDManager is null");
    }
    // G4SDManager is per-thread: each worker creates its own detector instance.
    G4VSensitiveDetector* detector = sdManager->FindSensitiveDetector(detectorName, false);
    if (detector == nullptr) {
        detector = new ParallelScoringDetector(detectorName, config_.get(), outputManager_);
        sdManager->AddNewDetector(detector);
    }
    for (const auto* placement : volumePlacements_) {
        G4LogicalVolume* logical = placement ? placement->GetLogicalVolume() : nullptr;
        if (logical == nullptr) {
            throw std::runtime_error("ScoringParallelWorld::ConstructSD failed: ghost placement has no logical "
                                     "volume");
        }
        logical->SetSensitiveDetector(detector);
    }
    // Geant4 chooses the SD from the ghost pre-step-point volume.  A step whose
    // pre-point is located on the world root (e.g. a track running along a
    // shared face/edge of grid cells) is silently not distributed to any leaf
    // SD.  The root detector resolves the owning cell from the ghost step
    // coordinates against the real constructed boxes; steps outside every
    // configured volume are skipped there instead of being attributed.
    const std::string rootDetectorName = "ParallelScoringWorldSD_" + config_->name();
    G4VSensitiveDetector* rootDetector = sdManager->FindSensitiveDetector(rootDetectorName, false);
    if (rootDetector == nullptr) {
        rootDetector = new ParallelScoringDetector(rootDetectorName, config_.get(), outputManager_,
                                                   ParallelScoringDetector::Scope::WorldRoot, &volumePlacements_,
                                                   world);
        sdManager->AddNewDetector(rootDetector);
    }
    G4LogicalVolume* worldLogical = world->GetLogicalVolume();
    worldLogical->SetSensitiveDetector(rootDetector);
    // Grid envelopes: a step whose ghost pre-point is located on the real
    // grid-envelope surface is restored to its real cell owner by the
    // envelope detector; steps outside every cell are skipped there.
    std::vector<G4VSensitiveDetector*> envelopeDetectors;
    for (std::size_t index = 0; index < envelopeLogicals_.size(); ++index) {
        const std::string envelopeDetectorName = "ParallelScoringEnvelopeSD_" + config_->name() +
                                                  "_" + std::to_string(index);
        G4VSensitiveDetector* envelopeDetector =
            sdManager->FindSensitiveDetector(envelopeDetectorName, false);
        if (envelopeDetector == nullptr) {
            envelopeDetector = new ParallelScoringDetector(
                envelopeDetectorName, config_.get(), outputManager_,
                ParallelScoringDetector::Scope::Envelope, &volumePlacements_, world,
                envelopePlacements_[index]);
            sdManager->AddNewDetector(envelopeDetector);
        }
        envelopeLogicals_[index]->SetSensitiveDetector(envelopeDetector);
        envelopeDetectors.push_back(envelopeDetector);
    }
    // Contract I: a per-thread SD binding failure is latched into the shared
    // output-failure registry so the run cannot silently continue and finish with
    // status 0. The thread-local ScoringManager is bound later (ActionInitialization
    // Build), so the TLS check itself happens in ProcessHits, not here.
    const auto latch = [this](const std::string& message) {
        if (outputManager_ != nullptr) outputManager_->RecordOutputFailure("parallel_world_sd", message);
        throw std::runtime_error("ScoringParallelWorld::ConstructSD failed: " + message);
    };
    for (const auto* placement : volumePlacements_) {
        G4LogicalVolume* logical = placement ? placement->GetLogicalVolume() : nullptr;
        if (logical != nullptr && logical->GetSensitiveDetector() != detector) {
            latch("ghost logical volume '" + logical->GetName() +
                  "' did not keep the thread-local parallel sensitive detector binding");
        }
    }
    if (worldLogical->GetSensitiveDetector() != rootDetector) {
        latch("the ghost world root did not keep the thread-local parallel root detector binding");
    }
    for (std::size_t index = 0; index < envelopeLogicals_.size(); ++index) {
        G4LogicalVolume* logical = envelopeLogicals_[index];
        if (logical != nullptr && logical->GetSensitiveDetector() != envelopeDetectors[index]) {
            latch("grid envelope '" + logical->GetName() +
                  "' did not keep the thread-local parallel envelope detector binding");
        }
    }
}

G4LogicalVolume* ScoringParallelWorld::FindLogicalVolume(const std::string& name) const
{
    for (std::size_t index = 0; index < volumeLogicals_.size(); ++index) {
        if (volumeLogicals_[index] != nullptr && volumeLogicals_[index]->GetName() == name) {
            return volumeLogicals_[index];
        }
    }
    return nullptr;
}

G4VPhysicalVolume* ScoringParallelWorld::FindPlacement(const std::string& name) const
{
    for (auto* placement : volumePlacements_) {
        if (placement != nullptr && placement->GetName() == name) return placement;
    }
    return nullptr;
}

}  // namespace parallel_world
