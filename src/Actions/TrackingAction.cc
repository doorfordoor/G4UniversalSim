#include "Actions/TrackingAction.hh"
#include "Actions/WorkerRunContext.hh"
#include "Scoring/ScoringManager.hh"

#include "G4ParticleDefinition.hh"
#include "G4Track.hh"
#include "G4ios.hh"

#include <stdexcept>
#include <utility>

TrackingAction::TrackingAction(std::shared_ptr<WorkerRunContext> context)
    : context_(std::move(context))
{
}

TrackingAction::~TrackingAction() = default;

void TrackingAction::ClearPendingActivationBirths() const noexcept
{
    if (context_) {
        if (auto* scoring = context_->GetScoringManager()) scoring->ClearPendingActivationBirths();
    }
}

void TrackingAction::PreUserTrackingAction(const G4Track* track)
{
    if (!track) return;
    // Native stacking resolves the previous parent's births before the next track starts.
    // Drop any unclassified identities before the allocator can reuse their addresses.
    ClearPendingActivationBirths();
    if (!trackLoggingEnabled_ || verboseLevel_ <= 0) return;

    const auto* particle = track->GetParticleDefinition();
    G4cout << "[TrackingAction] Pre trackID=" << track->GetTrackID()
           << " parentID=" << track->GetParentID()
           << " particle=" << (particle ? particle->GetParticleName() : "<unknown>")
           << " kineticEnergy=" << track->GetKineticEnergy()
           << " weight=" << track->GetWeight()
           << G4endl;
}

void TrackingAction::PostUserTrackingAction(const G4Track* track)
{
    if (!track) return;
    // In this branch G4EventManager deletes the secondaries without invoking stacking.
    if (track->GetTrackStatus() == fKillTrackAndSecondaries) ClearPendingActivationBirths();
    if (!trackLoggingEnabled_ || verboseLevel_ <= 0) return;

    const auto* particle = track->GetParticleDefinition();
    G4cout << "[TrackingAction] Post trackID=" << track->GetTrackID()
           << " parentID=" << track->GetParentID()
           << " particle=" << (particle ? particle->GetParticleName() : "<unknown>")
           << " kineticEnergy=" << track->GetKineticEnergy()
           << " weight=" << track->GetWeight()
           << G4endl;
}

void TrackingAction::SetVerboseLevel(int level)
{
    if (level < 0) {
        throw std::runtime_error("TrackingAction::SetVerboseLevel failed: level must be >= 0");
    }
    verboseLevel_ = level;
}

int TrackingAction::GetVerboseLevel() const
{
    return verboseLevel_;
}

void TrackingAction::EnableTrackLogging(bool enable)
{
    trackLoggingEnabled_ = enable;
}

bool TrackingAction::IsTrackLoggingEnabled() const
{
    return trackLoggingEnabled_;
}
