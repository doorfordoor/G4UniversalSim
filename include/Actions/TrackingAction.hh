#pragma once

#include "G4UserTrackingAction.hh"
#include <memory>

class G4Track;
struct WorkerRunContext;

class TrackingAction : public G4UserTrackingAction {
public:
    explicit TrackingAction(std::shared_ptr<WorkerRunContext> context = {});
    ~TrackingAction() override;

    void PreUserTrackingAction(const G4Track* track) override;
    void PostUserTrackingAction(const G4Track* track) override;

    void SetVerboseLevel(int level);
    int GetVerboseLevel() const;

    void EnableTrackLogging(bool enable);
    bool IsTrackLoggingEnabled() const;

private:
    std::shared_ptr<WorkerRunContext> context_;
    void ClearPendingActivationBirths() const noexcept;
    int verboseLevel_ = 0;
    bool trackLoggingEnabled_ = false;
};
