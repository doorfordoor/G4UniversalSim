#pragma once

#include "G4Timer.hh"
#include "G4UserRunAction.hh"

#include <memory>

class G4Run;
class OutputManager;
class ScoringManager;
class BiasingManager;
class SourceManager;
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
              Role role = Role::Sequential,
              BiasingManager* biasingManager = nullptr);
    explicit RunAction(std::shared_ptr<WorkerRunContext> context,
                       Role role = Role::Worker,
                       BiasingManager* biasingManager = nullptr);
    ~RunAction() override;

    void BeginOfRunAction(const G4Run* run) override;
    void EndOfRunAction(const G4Run* run) override;

    void SetScoringManager(ScoringManager* scoringManager);
    ScoringManager* GetScoringManager();

    void SetOutputManager(OutputManager* outputManager);
    OutputManager* GetOutputManager();

    // Master/sequential: source settings that need the built geometry are
    // applied at the start of each run (SourceManager::PrepareForRun).
    void SetSourceManager(SourceManager* sourceManager);

    void SetVerboseLevel(int level);
    int GetVerboseLevel() const;

private:
    ScoringManager* ActiveScoringManager() const;
    OutputManager* ActiveOutputManager() const;

    std::shared_ptr<WorkerRunContext> context_;
    ScoringManager* scoringManager_ = nullptr; // non-owning
    OutputManager* outputManager_ = nullptr;   // non-owning
    BiasingManager* biasingManager_ = nullptr; // non-owning
    SourceManager* sourceManager_ = nullptr;   // non-owning
    Role role_ = Role::Sequential;
    int verboseLevel_ = 0;
    G4Timer runTimer_;  // master/sequential wall time of the current run (FOM)
};
