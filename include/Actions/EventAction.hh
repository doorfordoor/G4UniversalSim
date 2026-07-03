#pragma once

#include "G4UserEventAction.hh"

#include <memory>

class G4Event;
class ScoringManager;
struct WorkerRunContext;

class EventAction : public G4UserEventAction {
public:
    explicit EventAction(ScoringManager* scoringManager = nullptr);
    explicit EventAction(std::shared_ptr<WorkerRunContext> context);
    ~EventAction() override;

    void BeginOfEventAction(const G4Event* event) override;
    void EndOfEventAction(const G4Event* event) override;

    void SetScoringManager(ScoringManager* scoringManager);
    ScoringManager* GetScoringManager();

    void SetVerboseLevel(int level);
    int GetVerboseLevel() const;

private:
    ScoringManager* ActiveScoringManager() const;

    std::shared_ptr<WorkerRunContext> context_;
    ScoringManager* scoringManager_ = nullptr; // non-owning
    int verboseLevel_ = 0;
};
