#pragma once

#include "G4String.hh"
#include "G4VUserTrackInformation.hh"

class G4Track;

class TrackInformation : public G4VUserTrackInformation {
public:
    TrackInformation();
    explicit TrackInformation(const G4Track* track);
    ~TrackInformation() override;

    void Print() const override;

    void SetEventID(int id);
    int GetEventID() const;

    void SetOriginalTrackID(int id);
    int GetOriginalTrackID() const;

    void SetAncestorTrackID(int id);
    int GetAncestorTrackID() const;

    void SetParentID(int id);
    int GetParentID() const;

    void SetIsPrimary(bool value);
    bool IsPrimary() const;

    void SetPrimaryParticleName(const G4String& name);
    const G4String& GetPrimaryParticleName() const;

private:
    int eventID_ = -1;
    int originalTrackID_ = -1;
    int ancestorTrackID_ = -1;
    int parentID_ = -1;
    bool isPrimary_ = false;
    G4String primaryParticleName_;
};
