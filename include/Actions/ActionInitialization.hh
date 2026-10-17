#pragma once

#include "G4VUserActionInitialization.hh"

class OutputManager;
class ScoringManager;
class SourceManager;
class BiasingManager;

class ActionInitialization : public G4VUserActionInitialization {
public:
    ActionInitialization(SourceManager* sourceManager,
                         ScoringManager* scoringManager,
                         OutputManager* outputManager,
                         BiasingManager* biasingManager = nullptr);
    ~ActionInitialization() override;

    void BuildForMaster() const override;
    void Build() const override;

    void SetVerboseLevel(int level);
    int GetVerboseLevel() const;

private:
    SourceManager* sourceManager_ = nullptr;   // non-owning
    ScoringManager* masterScoringManager_ = nullptr; // non-owning
    OutputManager* masterOutputManager_ = nullptr;   // non-owning
    BiasingManager* biasingManager_ = nullptr; // non-owning
    int verboseLevel_ = 0;
};
