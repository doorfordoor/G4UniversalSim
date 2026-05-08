#include "Hits/TrackInformation.hh"

#include "G4ParticleDefinition.hh"
#include "G4Track.hh"
#include "G4ios.hh"

TrackInformation::TrackInformation() = default;

TrackInformation::TrackInformation(const G4Track* track)
{
    if (!track) return;

    originalTrackID_ = track->GetTrackID();
    parentID_ = track->GetParentID();
    isPrimary_ = (parentID_ == 0);
    ancestorTrackID_ = isPrimary_ ? originalTrackID_ : parentID_;

    const G4ParticleDefinition* particle = track->GetDefinition();
    if (particle) {
        primaryParticleName_ = particle->GetParticleName();
    }
}

TrackInformation::~TrackInformation() = default;

void TrackInformation::Print() const
{
    G4cout << "[TrackInformation] event=" << eventID_
           << " originalTrackID=" << originalTrackID_
           << " ancestorTrackID=" << ancestorTrackID_
           << " parentID=" << parentID_
           << " isPrimary=" << (isPrimary_ ? "true" : "false")
           << " primaryParticle=" << primaryParticleName_
           << G4endl;
}

void TrackInformation::SetEventID(int id) { eventID_ = id; }
int TrackInformation::GetEventID() const { return eventID_; }

void TrackInformation::SetOriginalTrackID(int id) { originalTrackID_ = id; }
int TrackInformation::GetOriginalTrackID() const { return originalTrackID_; }

void TrackInformation::SetAncestorTrackID(int id) { ancestorTrackID_ = id; }
int TrackInformation::GetAncestorTrackID() const { return ancestorTrackID_; }

void TrackInformation::SetParentID(int id) { parentID_ = id; }
int TrackInformation::GetParentID() const { return parentID_; }

void TrackInformation::SetIsPrimary(bool value) { isPrimary_ = value; }
bool TrackInformation::IsPrimary() const { return isPrimary_; }

void TrackInformation::SetPrimaryParticleName(const G4String& name) { primaryParticleName_ = name; }
const G4String& TrackInformation::GetPrimaryParticleName() const { return primaryParticleName_; }
