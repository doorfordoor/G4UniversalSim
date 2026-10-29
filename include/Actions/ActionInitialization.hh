#pragma once

#include "G4VUserActionInitialization.hh"
#include "Actions/RunAction.hh"

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
    void SetEffectiveCallbacks(RunAction::EffectiveCallback begin, RunAction::EffectiveCallback end) {
        effectiveBegin_ = std::move(begin); effectiveEnd_ = std::move(end);
    }

private:
    SourceManager* sourceManager_ = nullptr;   // non-owning
    ScoringManager* masterScoringManager_ = nullptr; // non-owning
    OutputManager* masterOutputManager_ = nullptr;   // non-owning
    BiasingManager* biasingManager_ = nullptr; // non-owning
    int verboseLevel_ = 0;
    RunAction::EffectiveCallback effectiveBegin_, effectiveEnd_;
};
