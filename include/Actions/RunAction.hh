#pragma once

#include "G4UserRunAction.hh"

class G4Run;
class OutputManager;
class ScoringManager;

class RunAction : public G4UserRunAction {
public:
    RunAction(ScoringManager* scoringManager = nullptr,
              OutputManager* outputManager = nullptr);
    ~RunAction() override;

    void BeginOfRunAction(const G4Run* run) override;
    void EndOfRunAction(const G4Run* run) override;

    void SetScoringManager(ScoringManager* scoringManager);
    ScoringManager* GetScoringManager();

    void SetOutputManager(OutputManager* outputManager);
    OutputManager* GetOutputManager();

    void SetVerboseLevel(int level);
    int GetVerboseLevel() const;

private:
    ScoringManager* scoringManager_ = nullptr; // non-owning
    OutputManager* outputManager_ = nullptr;   // non-owning
    int verboseLevel_ = 0;
};
