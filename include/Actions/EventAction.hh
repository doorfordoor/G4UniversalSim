#pragma once

#include "G4UserEventAction.hh"

class G4Event;
class ScoringManager;

class EventAction : public G4UserEventAction {
public:
    explicit EventAction(ScoringManager* scoringManager = nullptr);
    ~EventAction() override;

    void BeginOfEventAction(const G4Event* event) override;
    void EndOfEventAction(const G4Event* event) override;

    void SetScoringManager(ScoringManager* scoringManager);
    ScoringManager* GetScoringManager();

    void SetVerboseLevel(int level);
    int GetVerboseLevel() const;

private:
    ScoringManager* scoringManager_ = nullptr; // non-owning
    int verboseLevel_ = 0;
};
