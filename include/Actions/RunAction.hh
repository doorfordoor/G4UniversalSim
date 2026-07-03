#pragma once

#include "G4UserRunAction.hh"

#include <memory>

class G4Run;
class OutputManager;
class ScoringManager;
struct WorkerRunContext;

class RunAction : public G4UserRunAction {
public:
    enum class Role {
        Sequential,
        Master,
        Worker
    };

    RunAction(ScoringManager* scoringManager = nullptr,
              OutputManager* outputManager = nullptr,
              Role role = Role::Sequential);
    explicit RunAction(std::shared_ptr<WorkerRunContext> context,
                       Role role = Role::Worker);
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
    ScoringManager* ActiveScoringManager() const;
    OutputManager* ActiveOutputManager() const;

    std::shared_ptr<WorkerRunContext> context_;
    ScoringManager* scoringManager_ = nullptr; // non-owning
    OutputManager* outputManager_ = nullptr;   // non-owning
    Role role_ = Role::Sequential;
    int verboseLevel_ = 0;
};
