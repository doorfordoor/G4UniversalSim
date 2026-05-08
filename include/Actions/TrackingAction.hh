#pragma once

#include "G4UserTrackingAction.hh"

class G4Track;

class TrackingAction : public G4UserTrackingAction {
public:
    TrackingAction();
    ~TrackingAction() override;

    void PreUserTrackingAction(const G4Track* track) override;
    void PostUserTrackingAction(const G4Track* track) override;

    void SetVerboseLevel(int level);
    int GetVerboseLevel() const;

    void EnableTrackLogging(bool enable);
    bool IsTrackLoggingEnabled() const;

private:
    int verboseLevel_ = 0;
    bool trackLoggingEnabled_ = false;
};
