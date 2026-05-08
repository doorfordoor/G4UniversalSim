#include "Actions/TrackingAction.hh"

#include "G4ParticleDefinition.hh"
#include "G4Track.hh"
#include "G4ios.hh"

#include <stdexcept>

TrackingAction::TrackingAction() = default;

TrackingAction::~TrackingAction() = default;

void TrackingAction::PreUserTrackingAction(const G4Track* track)
{
    if (!track) return;
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
