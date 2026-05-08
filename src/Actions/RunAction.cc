#include "Actions/RunAction.hh"

#include "G4Run.hh"
#include "G4ios.hh"
#include "Output/OutputManager.hh"
#include "Output/RunSummary.hh"
#include "Scoring/ScoringManager.hh"

#include <stdexcept>

RunAction::RunAction(ScoringManager* scoringManager, OutputManager* outputManager)
    : scoringManager_(scoringManager),
      outputManager_(outputManager)
{
}

RunAction::~RunAction() = default;

void RunAction::BeginOfRunAction(const G4Run* run)
{
    if (!run) {
        throw std::runtime_error("RunAction::BeginOfRunAction failed: G4Run is null");
    }

    const int runID = run->GetRunID();
    if (verboseLevel_ > 0) {
        G4cout << "[RunAction] Begin run " << runID << G4endl;
    }

    if (outputManager_) {
        outputManager_->Initialize();
        outputManager_->GetRunSummary().Set("run_id_begin", runID);
    } else if (verboseLevel_ > 0) {
        G4cout << "[RunAction] OutputManager is null; output initialization skipped." << G4endl;
    }

    if (scoringManager_) {
        scoringManager_->BeginRun(runID);
    } else if (verboseLevel_ > 0) {
        G4cout << "[RunAction] ScoringManager is null; BeginRun skipped." << G4endl;
    }
}

void RunAction::EndOfRunAction(const G4Run* run)
{
    if (!run) {
        throw std::runtime_error("RunAction::EndOfRunAction failed: G4Run is null");
    }

    const int runID = run->GetRunID();
    if (verboseLevel_ > 0) {
        G4cout << "[RunAction] End run " << runID << G4endl;
    }

    if (scoringManager_) {
        scoringManager_->EndRun(runID);
        scoringManager_->WriteAll();
    }

    if (outputManager_) {
        outputManager_->GetRunSummary().Set("run_id_end", runID);
        outputManager_->WriteAllHistograms();
        outputManager_->WriteRunSummary();
        outputManager_->Flush();
    } else if (verboseLevel_ > 0) {
        G4cout << "[RunAction] OutputManager is null; final output skipped." << G4endl;
    }
}

void RunAction::SetScoringManager(ScoringManager* scoringManager)
{
    scoringManager_ = scoringManager;
}

ScoringManager* RunAction::GetScoringManager()
{
    return scoringManager_;
}

void RunAction::SetOutputManager(OutputManager* outputManager)
{
    outputManager_ = outputManager;
}

OutputManager* RunAction::GetOutputManager()
{
    return outputManager_;
}

void RunAction::SetVerboseLevel(int level)
{
    if (level < 0) {
        throw std::runtime_error("RunAction::SetVerboseLevel failed: level must be >= 0");
    }
    verboseLevel_ = level;
}

int RunAction::GetVerboseLevel() const
{
    return verboseLevel_;
}
