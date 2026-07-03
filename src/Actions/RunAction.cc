#include "Actions/RunAction.hh"

#include "Actions/WorkerRunContext.hh"
#include "G4Run.hh"
#include "G4ios.hh"
#include "Output/OutputManager.hh"
#include "Output/RunSummary.hh"
#include "Scoring/ScoringManager.hh"
#include "Scoring/ThreadLocalScoringContext.hh"

#include <stdexcept>
#include <utility>

RunAction::RunAction(ScoringManager* scoringManager,
                     OutputManager* outputManager,
                     Role role)
    : scoringManager_(scoringManager),
      outputManager_(outputManager),
      role_(role)
{
}

RunAction::RunAction(std::shared_ptr<WorkerRunContext> context, Role role)
    : context_(std::move(context)),
      role_(role)
{
}

RunAction::~RunAction()
{
    if (context_ && context_->GetScoringManager() &&
        AIHL::GetCurrentThreadScoringManager() == context_->GetScoringManager()) {
        AIHL::SetCurrentThreadScoringManager(nullptr);
    }
}

void RunAction::BeginOfRunAction(const G4Run* run)
{
    if (!run) {
        throw std::runtime_error("RunAction::BeginOfRunAction failed: G4Run is null");
    }

    const int runID = run->GetRunID();
    if (verboseLevel_ > 0) {
        G4cout << "[RunAction] Begin run " << runID << G4endl;
    }

    OutputManager* outputManager = ActiveOutputManager();
    ScoringManager* scoringManager = ActiveScoringManager();

    if (outputManager) {
        outputManager->Initialize();
        outputManager->GetRunSummary().Set("run_id_begin", runID);
    } else if (verboseLevel_ > 0) {
        G4cout << "[RunAction] OutputManager is null; output initialization skipped." << G4endl;
    }

    if (role_ != Role::Master && scoringManager) {
        scoringManager->BeginRun(runID);
    } else if (verboseLevel_ > 0) {
        G4cout << "[RunAction] ScoringManager BeginRun skipped for master or null manager." << G4endl;
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

    OutputManager* outputManager = ActiveOutputManager();
    ScoringManager* scoringManager = ActiveScoringManager();

    if (role_ != Role::Master && scoringManager) {
        scoringManager->EndRun(runID);
        scoringManager->WriteAll();
    }

    if (outputManager) {
        outputManager->GetRunSummary().Set("run_id_end", runID);
        if (role_ != Role::Master) {
            outputManager->WriteAllHistograms();
        }
        if (role_ != Role::Worker) {
            outputManager->WriteRunSummary();
        }
        outputManager->Flush();
        if (role_ == Role::Worker) {
            outputManager->Close();
        }
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
    return ActiveScoringManager();
}

void RunAction::SetOutputManager(OutputManager* outputManager)
{
    outputManager_ = outputManager;
}

OutputManager* RunAction::GetOutputManager()
{
    return ActiveOutputManager();
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

ScoringManager* RunAction::ActiveScoringManager() const
{
    return context_ ? context_->GetScoringManager() : scoringManager_;
}

OutputManager* RunAction::ActiveOutputManager() const
{
    return context_ ? context_->GetOutputManager() : outputManager_;
}
