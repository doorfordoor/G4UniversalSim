#pragma once

#include "G4VUserActionInitialization.hh"

class OutputManager;
class ScoringManager;
class SourceManager;

class ActionInitialization : public G4VUserActionInitialization {
public:
    ActionInitialization(SourceManager* sourceManager,
                         ScoringManager* scoringManager,
                         OutputManager* outputManager);
    ~ActionInitialization() override;

    void BuildForMaster() const override;
    void Build() const override;

    void SetVerboseLevel(int level);
    int GetVerboseLevel() const;

private:
    SourceManager* sourceManager_ = nullptr;   // non-owning
    ScoringManager* scoringManager_ = nullptr; // non-owning
    OutputManager* outputManager_ = nullptr;   // non-owning
    int verboseLevel_ = 0;
};
