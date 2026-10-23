#include "Actions/SteppingAction.hh"

#include "Actions/WorkerRunContext.hh"
#include "G4ParticleDefinition.hh"
#include "G4Step.hh"
#include "G4StepPoint.hh"
#include "G4SystemOfUnits.hh"
#include "G4ThreeVector.hh"
#include "G4Track.hh"
#include "G4VPhysicalVolume.hh"
#include "G4VProcess.hh"
#include "Output/OutputRecord.hh"
#include "Scoring/ScoringManager.hh"
#include "Scoring/DoseContext.hh"
#include "Utils/StringUtils.hh"

#include <algorithm>
#include <stdexcept>
#include <utility>

SteppingAction::SteppingAction(ScoringManager* scoringManager)
    : scoringManager_(scoringManager)
{
}

SteppingAction::SteppingAction(std::shared_ptr<WorkerRunContext> context)
    : context_(std::move(context))
{
}

SteppingAction::~SteppingAction() = default;

void SteppingAction::UserSteppingAction(const G4Step* step)
{
    if (!step) return;

    auto* track = step->GetTrack();
    if (!track) return;

    const auto* pre = step->GetPreStepPoint();
    const auto* post = step->GetPostStepPoint();
    std::string volumeName;
    if (pre && pre->GetPhysicalVolume()) {
        volumeName = pre->GetPhysicalVolume()->GetName();
    }

    ScoringManager* scoringManager = ActiveScoringManager();
    if (scoringManager && scoringManager->RecordsTrajectories()) {
        scoringManager->RecordTrajectoryStep(step);
    }

    if (!volumeName.empty() && IsKillVolume(volumeName)) {
        track->SetTrackStatus(fStopAndKill);
        return;
    }

    // Phase space: a step that ends on a boundary into the volume carries the
    // entry state at its post-step point (before anything happens inside).
    const G4VPhysicalVolume* next = post ? post->GetPhysicalVolume() : nullptr;
    if (scoringManager && scoringManager->IsPhaseSpaceEnabled() && post && next &&
        post->GetStepStatus() == fGeomBoundary && next->GetName() == scoringManager->GetPhaseSpaceVolume()) {
        const G4ParticleDefinition* definition = track->GetParticleDefinition();
        const std::string particle = definition ? definition->GetParticleName() : "";
        if (scoringManager->AcceptsPhaseSpaceParticle(particle)) {
            PhaseSpaceParticle entry;
            entry.trackID = track->GetTrackID();
            entry.parentID = track->GetParentID();
            entry.particle = particle;
            entry.pdg = definition ? definition->GetPDGEncoding() : 0;
            const G4ThreeVector position = post->GetPosition();
            const G4ThreeVector direction = post->GetMomentumDirection();
            entry.x = position.x();
            entry.y = position.y();
            entry.z = position.z();
            entry.u = direction.x();
            entry.v = direction.y();
            entry.w = direction.z();
            entry.kineticEnergy = post->GetKineticEnergy();
            entry.time = post->GetGlobalTime();
            entry.weight = post->GetWeight();
            scoringManager->RecordPhaseSpace(entry);
            if (scoringManager->KillsPhaseSpaceParticles()) {
                track->SetTrackStatus(fStopAndKill);
                return;
            }
        }
    }

    if (!stepScoringEnabled_ || !scoringManager) {
        return;
    }

    // Step scoring is a convenience fallback for non-SD studies. Keep it off by
    // default because the future SensitiveDetector path will produce canonical
    // HitRecord objects and double counting would be easy.
    HitRecord hit;
    hit.eventID = -1;
    hit.trackID = track->GetTrackID();
    hit.parentID = track->GetParentID();
    hit.particleName = track->GetParticleDefinition()
        ? track->GetParticleDefinition()->GetParticleName()
        : "";
    hit.edep = step->GetTotalEnergyDeposit();
    hit.ndep = step->GetNonIonizingEnergyDeposit();
    hit.stepLength = step->GetStepLength();
    if (pre) {
        const auto p = pre->GetPosition();
        hit.x0 = p.x();
        hit.y0 = p.y();
        hit.z0 = p.z();
        hit.kineticEnergy = pre->GetKineticEnergy();
        hit.weight = pre->GetWeight();
    }
    if (post) {
        const auto p = post->GetPosition();
        hit.x1 = p.x();
        hit.y1 = p.y();
        hit.z1 = p.z();
        if (post->GetProcessDefinedStep()) {
            hit.processName = post->GetProcessDefinedStep()->GetProcessName();
        }
    }
    const auto mom = track->GetMomentum();
    hit.px = mom.x();
    hit.py = mom.y();
    hit.pz = mom.z();
    hit.volumeName = volumeName;

    if (scoringManager->IsDoseScoringEnabled() || scoringManager->IsFluenceScoringEnabled() ||
        scoringManager->IsDisplacementScoringEnabled()) {
        PopulateDoseContext(step, hit);
    }

    scoringManager->ScoreHit(hit);
}

void SteppingAction::SetScoringManager(ScoringManager* scoringManager)
{
    scoringManager_ = scoringManager;
}

ScoringManager* SteppingAction::GetScoringManager()
{
    return ActiveScoringManager();
}

void SteppingAction::SetVerboseLevel(int level)
{
    if (level < 0) {
        throw std::runtime_error("SteppingAction::SetVerboseLevel failed: level must be >= 0");
    }
    verboseLevel_ = level;
}

int SteppingAction::GetVerboseLevel() const
{
    return verboseLevel_;
}

void SteppingAction::EnableStepScoring(bool enable)
{
    stepScoringEnabled_ = enable;
}

bool SteppingAction::IsStepScoringEnabled() const
{
    return stepScoringEnabled_;
}

void SteppingAction::AddKillVolume(const std::string& volumeName)
{
    const auto name = StringUtils::Trim(volumeName);
    if (name.empty()) {
        throw std::runtime_error("SteppingAction::AddKillVolume failed: volumeName is empty");
    }
    if (!IsKillVolume(name)) {
        killVolumes_.push_back(name);
    }
}

void SteppingAction::ClearKillVolumes()
{
    killVolumes_.clear();
}

bool SteppingAction::IsKillVolume(const std::string& volumeName) const
{
    const auto name = StringUtils::Trim(volumeName);
    return std::find(killVolumes_.begin(), killVolumes_.end(), name) != killVolumes_.end();
}

ScoringManager* SteppingAction::ActiveScoringManager() const
{
    return context_ ? context_->GetScoringManager() : scoringManager_;
}
