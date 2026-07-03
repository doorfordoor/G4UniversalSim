#pragma once

#include "G4UserSteppingAction.hh"

#include <memory>
#include <string>
#include <vector>

class G4Step;
class ScoringManager;
struct WorkerRunContext;

class SteppingAction : public G4UserSteppingAction {
public:
    explicit SteppingAction(ScoringManager* scoringManager = nullptr);
    explicit SteppingAction(std::shared_ptr<WorkerRunContext> context);
    ~SteppingAction() override;

    void UserSteppingAction(const G4Step* step) override;

    void SetScoringManager(ScoringManager* scoringManager);
    ScoringManager* GetScoringManager();

    void SetVerboseLevel(int level);
    int GetVerboseLevel() const;

    void EnableStepScoring(bool enable);
    bool IsStepScoringEnabled() const;

    void AddKillVolume(const std::string& volumeName);
    void ClearKillVolumes();
    bool IsKillVolume(const std::string& volumeName) const;

private:
    ScoringManager* ActiveScoringManager() const;

    std::shared_ptr<WorkerRunContext> context_;
    ScoringManager* scoringManager_ = nullptr; // non-owning
    int verboseLevel_ = 0;
    bool stepScoringEnabled_ = false;
    std::vector<std::string> killVolumes_;
};
