#include "Actions/RunAction.hh"

#include "Actions/WorkerRunContext.hh"
#include "Biasing/BiasingManager.hh"
#include "G4Exception.hh"
#include "G4Run.hh"
#include "G4RunManager.hh"
#include "G4ios.hh"
#include "Output/OutputManager.hh"
#include "Output/RunSummary.hh"
#include "Scoring/ScoringManager.hh"
#include "Scoring/ThreadLocalScoringContext.hh"

#include <stdexcept>
#include <utility>

RunAction::RunAction(ScoringManager* scoringManager,
                     OutputManager* outputManager,
                     Role role,
                     BiasingManager* biasingManager)
    : scoringManager_(scoringManager),
      outputManager_(outputManager),
      biasingManager_(biasingManager),
      role_(role)
{
}

RunAction::RunAction(std::shared_ptr<WorkerRunContext> context, Role role, BiasingManager* biasingManager)
    : context_(std::move(context)),
      biasingManager_(biasingManager),
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

    if (role_ != Role::Worker && biasingManager_ && biasingManager_->IsEnabled()) {
        try {
            biasingManager_->ValidateActiveProcessRules();
        } catch (const std::exception& error) {
            G4Exception("RunAction::BeginOfRunAction", "AIHLBiasingTarget001", RunMustBeAborted, error.what());
            return;
        }
    }

    const int runID = run->GetRunID();
    if (verboseLevel_ > 0) {
        G4cout << "[RunAction] Begin run " << runID << G4endl;
    }

    OutputManager* outputManager = ActiveOutputManager();
    ScoringManager* scoringManager = ActiveScoringManager();

    const char* stage = "run_begin_set_run_id";
    try {
        if (outputManager) {
            outputManager->SetRunId(runID);
            stage = "run_begin_summary";
            outputManager->GetRunSummary().Set("run_id_begin", runID);
            stage = "run_begin_initialize";
            outputManager->Initialize();
        }
        if (role_ != Role::Master && scoringManager) {
            stage = "scoring_begin_run";
            scoringManager->BeginRun(runID);
        }
    } catch (const std::exception& error) {
        if (outputManager) outputManager->RecordOutputFailure(stage, error.what(), runID);
        G4cerr << "[OutputFailure] " << stage << ": " << error.what() << G4endl;
        if (auto* runManager = G4RunManager::GetRunManager()) runManager->AbortRun(true);
        return;
    } catch (...) {
        if (outputManager) outputManager->RecordOutputFailure(stage, "unknown exception", runID);
        G4cerr << "[OutputFailure] " << stage << ": unknown exception" << G4endl;
        if (auto* runManager = G4RunManager::GetRunManager()) runManager->AbortRun(true);
        return;
    }

    if (!outputManager && verboseLevel_ > 0) {
        G4cout << "[RunAction] OutputManager is null; output initialization skipped." << G4endl;
    }

    if (outputManager && (role_ == Role::Master || !scoringManager) && verboseLevel_ > 0) {
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

    // Geant4 worker callbacks must not let an output exception escape into the
    // worker event loop: the shared registry lets the master reject beamOn.
    const auto attempt = [outputManager](const char* stage, const auto& operation) {
        try {
            operation();
        } catch (const std::exception& error) {
            if (outputManager) outputManager->RecordOutputFailure(stage, error.what());
            G4cerr << "[OutputFailure] " << stage << ": " << error.what() << G4endl;
        } catch (...) {
            if (outputManager) outputManager->RecordOutputFailure(stage, "unknown exception");
            G4cerr << "[OutputFailure] " << stage << ": unknown exception" << G4endl;
        }
    };

    if (role_ != Role::Master && scoringManager) {
        attempt("scoring_end_run", [&]() { scoringManager->EndRun(runID); });
        if (!outputManager || !outputManager->HasOutputFailure()) {
            attempt("scoring_write_all", [&]() { scoringManager->WriteAll(); });
        }
    }

    if (outputManager) {
        outputManager->GetRunSummary().Set("run_id_end", runID);
        if (role_ != Role::Worker) {
            outputManager->RecordRun(
                runID,
                run->GetNumberOfEventToBeProcessed(),
                run->GetNumberOfEvent());
        }
        if (role_ != Role::Master) {
            if (!outputManager->HasOutputFailure()) {
                attempt("histograms_write", [&]() { outputManager->WriteAllHistograms(); });
            }
        }
        if (!outputManager->HasOutputFailure()) {
            attempt("run_flush", [&]() { outputManager->Flush(); });
        }
        if (role_ == Role::Worker) {
            attempt("worker_close", [&]() { outputManager->Close(); });
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
