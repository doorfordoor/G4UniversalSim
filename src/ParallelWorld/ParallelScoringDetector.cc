#include "ParallelWorld/ParallelScoringDetector.hh"

#include "ParallelWorld/ParallelWorldConfig.hh"

#include "Hits/ParticleHit.hh"
#include "Output/OutputManager.hh"
#include "Output/OutputRecord.hh"
#include "Scoring/ScoringManager.hh"
#include "Scoring/ThreadLocalScoringContext.hh"

#include "G4Box.hh"
#include "G4Event.hh"
#include "G4GeometryTolerance.hh"
#include "G4LogicalVolume.hh"
#include "G4RotationMatrix.hh"
#include "G4RunManager.hh"
#include "G4Step.hh"
#include "G4StepPoint.hh"
#include "G4SystemOfUnits.hh"
#include "G4ThreeVector.hh"
#include "G4TouchableHistory.hh"
#include "G4Transform3D.hh"
#include "G4VPhysicalVolume.hh"

#include <algorithm>
#include <cmath>
#include <iostream>
#include <memory>
#include <string>
#include <vector>

namespace parallel_world {
namespace {

void LatchFailure(OutputManager* output, const std::string& message)
{
    std::cerr << "[ParallelScoringDetector] " << message << '\n';
    if (output != nullptr) output->RecordOutputFailure("parallel_world_scoring", message);
}

double SurfaceTolerance()
{
    return G4GeometryTolerance::GetInstance()->GetSurfaceTolerance();
}

// Real composed transform of a placement inside its physical parent. Grid
// cells are children of the grid envelope, so the parent transform must be
// composed exactly as Geant4 composed it; no local coordinate is ever
// treated as a global one (H3-4 grid fix r3).
G4Transform3D ComposedTransform(const G4VPhysicalVolume& parent, const G4VPhysicalVolume& placement)
{
    const G4Transform3D parentTransform(parent.GetObjectRotationValue(), parent.GetObjectTranslation());
    const G4Transform3D placementTransform(placement.GetObjectRotationValue(),
                                           placement.GetObjectTranslation());
    return parentTransform * placementTransform;
}

G4ThreeVector LocalPoint(const G4Transform3D& transform, const G4ThreeVector& global)
{
    return transform.inverse().getRotation() * (global - transform.getTranslation());
}

G4ThreeVector LocalDirection(const G4Transform3D& transform, const G4ThreeVector& direction)
{
    return transform.inverse().getRotation() * direction;
}

bool InsideClosedBox(const G4ThreeVector& local, const G4Box& box, double tolerance)
{
    return std::fabs(local.x()) <= box.GetXHalfLength() + tolerance &&
           std::fabs(local.y()) <= box.GetYHalfLength() + tolerance &&
           std::fabs(local.z()) <= box.GetZHalfLength() + tolerance;
}

}  // namespace

ParallelScoringDetector::ParallelScoringDetector(const std::string& name, const ParallelWorldConfig* config,
                                                 OutputManager* outputManager, Scope scope,
                                                 const std::vector<G4VPhysicalVolume*>* placements,
                                                 G4VPhysicalVolume* world,
                                                 G4VPhysicalVolume* parent)
    : G4VSensitiveDetector(name),
      config_(config),
      outputManager_(outputManager),
      scope_(scope),
      placements_(placements),
      world_(world),
      parent_(parent)
{
}

void ParallelScoringDetector::Initialize(G4HCofThisEvent*)
{
    // Contract H3-4 R-RUNTIME: the legacy hits CSV must exist (header only,
    // zero data rows) when hits output is enabled on a real worker, even when no
    // mass hit is produced.  Only the ghost world root owns this duty: with the
    // parallel scoring world enabled the mass layer is insensitive, so without
    // it the per-thread writer would never be opened and Close() could not
    // register the file.  The parallel world never writes ghost rows to hits;
    // this opens the real thread-local writer only.
    if (scope_ != Scope::WorldRoot) return;
    ScoringManager* manager = AIHL::GetCurrentThreadScoringManager();
    if (manager == nullptr) {
        // A real parallel step reports the missing thread-local manager; an
        // event without steps must not fabricate a failure here.
        return;
    }
    if (!manager->IsEnabled() || !manager->IsHitOutputEnabled()) return;
    OutputManager* output = manager->GetOutputManager();
    if (output == nullptr || !output->WritesCsv() || output->IsHitFileOpen()) return;
    try {
        output->OpenHitFile();
    } catch (const std::exception& error) {
        manager->ReportScoringFailure("parallel_world_hits", error.what());
    } catch (...) {
        manager->ReportScoringFailure("parallel_world_hits",
                                      "unknown exception while opening the hits file");
    }
}

void ParallelScoringDetector::ReportMissingThreadManager(OutputManager* outputManager)
{
    LatchFailure(outputManager,
                 "no thread-local ScoringManager is bound; the parallel scoring step cannot be attributed");
}

G4bool ParallelScoringDetector::ProcessHits(G4Step* step, G4TouchableHistory* history)
{
    ScoringManager* manager = AIHL::GetCurrentThreadScoringManager();
    if (manager == nullptr) {
        // Contract H3: never fall back to the master manager from a worker. The
        // failure must be propagated to the shared latch and end with a non-zero
        // run status instead of a stderr-only abort.
        ReportMissingThreadManager(outputManager_);
        if (auto* runManager = G4RunManager::GetRunManager()) runManager->AbortRun(true);
        return true;
    }
    if (step == nullptr) {
        manager->ReportScoringFailure("parallel_world_scoring", "parallel SD received a null step");
        return true;
    }
    if (scope_ == Scope::WorldRoot || scope_ == Scope::Envelope) {
        return ProcessWorldRootStep(step, manager);
    }
    return ProcessLeafStep(step, manager);
}

G4bool ParallelScoringDetector::ProcessLeafStep(G4Step* step, ScoringManager* manager)
{
    const auto pre = step->GetPreStepPoint();
    const auto post = step->GetPostStepPoint();
    const auto touchable = pre ? pre->GetTouchableHandle() : G4TouchableHandle();
    if (!touchable || !touchable->GetVolume()) {
        manager->ReportScoringFailure("parallel_world_scoring",
                                      "parallel SD step has no ghost physical volume");
        return true;
    }
    const std::string volumeName = touchable->GetVolume()->GetName();
    const VolumeSpec* spec = config_ ? config_->FindVolume(volumeName) : nullptr;
    if (spec == nullptr) {
        manager->ReportScoringFailure("parallel_world_scoring",
                                      "parallel SD step entered an unconfigured volume '" + volumeName + "'");
        return true;
    }
    if (touchable->GetCopyNumber(0) != 0) {
        manager->ReportScoringFailure(
            "parallel_world_scoring",
            "parallel SD step entered volume '" + volumeName + "' with copy number " +
                std::to_string(touchable->GetCopyNumber(0)) + "; named box/grid cells require copy number 0");
        return true;
    }

    int eventID = -1;
    if (auto* runManager = G4RunManager::GetRunManager()) {
        if (const auto* event = runManager->GetCurrentEvent()) eventID = event->GetEventID();
    }

    HitRecord record;
    try {
        std::unique_ptr<ParticleHit> particle(ParticleHit::FromStep(step, eventID));
        record = particle->ToHitRecord();
    } catch (const std::exception& error) {
        manager->ReportScoringFailure("parallel_world_scoring", error.what());
        return true;
    } catch (...) {
        manager->ReportScoringFailure("parallel_world_scoring", "unknown exception while building the score");
        return true;
    }

    // Contract H3 (H): the ghost step supplies the transport quantities; the
    // score's normalization comes from the declared reference mass/volume and
    // the path from the ghost touchable history. The mass-world dose context is
    // never populated here.
    std::string volumePath;
    for (int depth = touchable->GetHistoryDepth(); depth >= 0; --depth) {
        const G4VPhysicalVolume* volume = touchable->GetVolume(depth);
        volumePath += "/";
        volumePath += volume != nullptr ? volume->GetName() : std::string("unknown");
        volumePath += "#";
        volumePath += std::to_string(touchable->GetCopyNumber(depth));
    }
    record.processName = "parallel_world_step";
    record.volumeName = spec->name;
    record.doseVolumePath = volumePath;
    record.doseMass = spec->referenceMassKg * kg;
    record.fluenceVolume = spec->volumeMm3 * mm * mm * mm;
    const double preKinetic = pre != nullptr ? pre->GetKineticEnergy() : record.kineticEnergy;
    const double postKinetic = post != nullptr ? post->GetKineticEnergy() : record.kineticEnergy;
    record.meanKineticEnergy = 0.5 * (preKinetic + postKinetic);

    manager->ScoreParallelHit(record);
    return true;
}

ParallelScoringDetector::OwnerResolution ParallelScoringDetector::ResolveOwnerStep(
    const G4Step& step, const VolumeSpec*& spec, std::string& volumePath) const
{
    spec = nullptr;
    volumePath.clear();
    if (config_ == nullptr || placements_ == nullptr || world_ == nullptr) return OwnerResolution::Failure;
    const auto& volumes = config_->volumes();
    if (placements_->size() != volumes.size()) return OwnerResolution::Failure;
    if (world_->GetLogicalVolume() == nullptr) return OwnerResolution::Failure;

    // Which real physical volume was the step located on? Scope::WorldRoot is
    // attached to the ghost world; Scope::Envelope to one grid's real envelope.
    // The detected parent is the actual PV, never an assumed plane.
    const G4VPhysicalVolume* parent = world_;
    if (scope_ == Scope::Envelope) {
        parent = parent_;
        if (parent == nullptr || parent->GetLogicalVolume() == nullptr) return OwnerResolution::Failure;
        if (parent->GetMotherLogical() != world_->GetLogicalVolume()) return OwnerResolution::Failure;
    }
    const G4LogicalVolume* parentLogical = parent->GetLogicalVolume();

    const auto* pre = step.GetPreStepPoint();
    if (pre == nullptr) return OwnerResolution::Failure;
    const G4ThreeVector prePosition = pre->GetPosition();
    const G4ThreeVector direction = pre->GetMomentumDirection();
    const double tolerance = SurfaceTolerance();

    // Frozen H3-4 semantics: a step belongs to the cell of its pre-step point.
    // This detector only sees steps whose pre-point Geant4 located on the
    // root/envelope; that point is either on the boundary of one or more real
    // scoring boxes (the defect this fixes) or in vacuum outside every box
    // (legitimately skipped). No whole-segment must-fit-one-box rule is added:
    // leaf steps keep their original pre-point attribution, and a step starting
    // inside a real cell is never re-attributed to its post cell.
    std::vector<std::size_t> candidates;
    std::vector<G4Transform3D> transforms;
    for (std::size_t index = 0; index < volumes.size(); ++index) {
        const VolumeSpec& volume = volumes[index];
        // Cheap declared-box prefilter: the ghost scoring world builds exactly
        // these axis-aligned boxes.  The real decision below still uses the
        // constructed G4Box and its real composed transform.
        bool near = true;
        for (int axis = 0; axis < 3; ++axis) {
            const double half = volume.sizeMm[axis] * 0.5;
            const double low = volume.centreMm[axis] - half - tolerance;
            const double high = volume.centreMm[axis] + half + tolerance;
            const double value = axis == 0 ? prePosition.x() : (axis == 1 ? prePosition.y() : prePosition.z());
            if (value < low || value > high) {
                near = false;
                break;
            }
        }
        if (!near) continue;

        const G4VPhysicalVolume* placement = (*placements_)[index];
        if (placement == nullptr || placement->GetLogicalVolume() == nullptr) return OwnerResolution::Failure;
        if (placement->GetName() != volume.name) return OwnerResolution::Failure;  // order must match the config
        // The placement must be a direct daughter of the physical volume this
        // detector is attached to, otherwise it belongs to another scope.
        if (placement->GetMotherLogical() != parentLogical) continue;
        const auto* box = dynamic_cast<const G4Box*>(placement->GetLogicalVolume()->GetSolid());
        if (box == nullptr) return OwnerResolution::Failure;  // the ghost scoring world only builds boxes
        const G4Transform3D transform = ComposedTransform(*parent, *placement);
        const G4ThreeVector local = LocalPoint(transform, prePosition);
        if (InsideClosedBox(local, *box, tolerance)) {
            candidates.push_back(index);
            transforms.push_back(transform);
        }
    }

    // A pre-point exactly on a closed box face is not enough to own the step.
    // Classify every candidate from the real local coordinates and the local
    // direction - no synthetic probe distance: a fixed advance cannot represent
    // boxes thinner than that advance (grid fix r2, 2e-7 mm cells).  Strictly
    // interior pre-points own the step directly; surface points use the face
    // normal sign to tell entering, exiting and shared-boundary glide apart.
    const double direction_epsilon = 1.0e-12;
    std::vector<std::size_t> entering;
    std::vector<std::size_t> glide;
    std::vector<G4Transform3D> enteringTransforms;
    std::vector<G4Transform3D> glideTransforms;
    for (std::size_t candidate = 0; candidate < candidates.size(); ++candidate) {
        const std::size_t index = candidates[candidate];
        const G4VPhysicalVolume* placement = (*placements_)[index];
        if (placement == nullptr || placement->GetLogicalVolume() == nullptr) return OwnerResolution::Failure;
        const auto* box = dynamic_cast<const G4Box*>(placement->GetLogicalVolume()->GetSolid());
        if (box == nullptr) return OwnerResolution::Failure;
        const G4Transform3D& transform = transforms[candidate];
        const G4ThreeVector local = LocalPoint(transform, prePosition);
        const G4ThreeVector localDirection = LocalDirection(transform, direction);
        const double half[3] = {box->GetXHalfLength(), box->GetYHalfLength(), box->GetZHalfLength()};
        const double point[3] = {local.x(), local.y(), local.z()};
        const double stepDirection[3] = {localDirection.x(), localDirection.y(), localDirection.z()};

        bool boundary = false;
        bool inside = true;
        for (int axis = 0; axis < 3; ++axis) {
            if (std::fabs(point[axis]) > half[axis] + tolerance) {
                inside = false;
                break;
            }
            if (std::fabs(point[axis]) >= half[axis] - tolerance) boundary = true;
        }
        if (!inside) continue;  // defensive: candidates were closed-box filtered
        if (!boundary) {
            entering.push_back(index);
            enteringTransforms.push_back(transform);
            continue;
        }

        // The pre-point lies on at least one face.  For each such face compare
        // the local direction with its inward normal: positive means the step
        // enters the box, negative means it leaves, zero means it runs exactly
        // along the boundary (a shared face/edge or a surface glide).
        bool inwardSeen = false;
        bool outwardSeen = false;
        for (int axis = 0; axis < 3; ++axis) {
            if (std::fabs(point[axis]) < half[axis] - tolerance) continue;
            const double side = point[axis] >= 0.0 ? 1.0 : -1.0;
            const double inward = -side * stepDirection[axis];
            if (inward > direction_epsilon) {
                inwardSeen = true;
            } else if (inward < -direction_epsilon) {
                outwardSeen = true;
            }
        }
        if (!outwardSeen && inwardSeen) {
            entering.push_back(index);  // enters through a face, edge or corner
            enteringTransforms.push_back(transform);
        } else if (!outwardSeen) {
            glide.push_back(index);  // runs exactly along the boundary
            glideTransforms.push_back(transform);
        }
        // outwardSeen: this box is left by the step and can never be the owner.
    }

    std::size_t owner = volumes.size();
    G4Transform3D ownerTransform;
    if (!entering.empty()) {
        // Box interiors are disjoint, so an entering owner is unique; the
        // lexicographic rule is only a deterministic safety net.
        std::size_t slot = 0;
        owner = entering.front();
        for (std::size_t candidate = 0; candidate < entering.size(); ++candidate) {
            if (volumes[entering[candidate]].name < volumes[owner].name) {
                owner = entering[candidate];
                slot = candidate;
            }
        }
        ownerTransform = enteringTransforms[slot];
    } else if (glide.size() >= 2) {
        // A shared face/edge/corner between real cells: the step runs exactly
        // along a boundary and is attributed once by a deterministic rule.
        std::size_t slot = 0;
        owner = glide.front();
        for (std::size_t candidate = 0; candidate < glide.size(); ++candidate) {
            if (volumes[glide[candidate]].name < volumes[owner].name) {
                owner = glide[candidate];
                slot = candidate;
            }
        }
        ownerTransform = glideTransforms[slot];
    } else {
        // An outer-surface glide (single closed-box candidate), an outward
        // exit into vacuum, or a point in a gap/external region: nothing is
        // scored, so the following vacuum length is not target fluence.
        return OwnerResolution::Skip;
    }

    const G4VPhysicalVolume* placement = (*placements_)[owner];
    if (placement == nullptr || placement->GetLogicalVolume() == nullptr) return OwnerResolution::Failure;
    if (placement->GetMotherLogical() != parentLogical) return OwnerResolution::Failure;
    if (placement->GetCopyNo() != 0) return OwnerResolution::Failure;
    (void)ownerTransform;

    // The reported path references the real ghost physical volumes only: the
    // world root, the real grid envelope (when used) and the real cell, each
    // with its actual copy number.
    spec = &volumes[owner];
    volumePath = "/";
    volumePath += world_->GetName();
    volumePath += "#";
    volumePath += std::to_string(world_->GetCopyNo());
    volumePath += "/";
    if (scope_ == Scope::Envelope && parent_ != nullptr) {
        volumePath += parent_->GetName();
        volumePath += "#";
        volumePath += std::to_string(parent_->GetCopyNo());
        volumePath += "/";
    }
    volumePath += placement->GetName();
    volumePath += "#";
    volumePath += std::to_string(placement->GetCopyNo());
    return OwnerResolution::Owner;
}

G4bool ParallelScoringDetector::ProcessWorldRootStep(G4Step* step, ScoringManager* manager)
{
    const auto* pre = step->GetPreStepPoint();
    const auto* post = step->GetPostStepPoint();
    if (pre == nullptr || post == nullptr) {
        manager->ReportScoringFailure("parallel_world_scoring", "parallel SD step has no step points");
        return true;
    }
    const double length = step->GetStepLength();
    const double edep = step->GetTotalEnergyDeposit();
    if (length <= 0.0 && edep <= 0.0) {
        // Zero-length relocation/boundary marks carry no score (fluence also
        // needs a positive track length).
        return true;
    }

    const VolumeSpec* spec = nullptr;
    std::string volumePath;
    const OwnerResolution resolution = ResolveOwnerStep(*step, spec, volumePath);
    if (resolution == OwnerResolution::Skip) return true;
    if (resolution == OwnerResolution::Failure) {
        if (auto* runManager = G4RunManager::GetRunManager()) runManager->AbortRun(true);
        return true;
    }

    int eventID = -1;
    if (auto* runManager = G4RunManager::GetRunManager()) {
        if (const auto* event = runManager->GetCurrentEvent()) eventID = event->GetEventID();
    }

    HitRecord record;
    try {
        std::unique_ptr<ParticleHit> particle(ParticleHit::FromStep(step, eventID));
        record = particle->ToHitRecord();
    } catch (const std::exception& error) {
        manager->ReportScoringFailure("parallel_world_scoring", error.what());
        return true;
    } catch (...) {
        manager->ReportScoringFailure("parallel_world_scoring", "unknown exception while building the score");
        return true;
    }

    record.processName = "parallel_world_step";
    record.volumeName = spec->name;
    record.doseVolumePath = volumePath;
    record.doseMass = spec->referenceMassKg * kg;
    record.fluenceVolume = spec->volumeMm3 * mm * mm * mm;
    const double preKinetic = pre->GetKineticEnergy();
    const double postKinetic = post->GetKineticEnergy();
    record.meanKineticEnergy = 0.5 * (preKinetic + postKinetic);

    manager->ScoreParallelHit(record);
    return true;
}

}  // namespace parallel_world
