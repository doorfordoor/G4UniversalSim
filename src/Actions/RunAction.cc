#include "Actions/RunAction.hh"
#include "Actions/RunProgress.hh"

#include "Actions/WorkerRunContext.hh"
#include "Biasing/BiasingManager.hh"
#include "G4Exception.hh"
#include "G4Run.hh"
#include "G4RunManager.hh"
#include "G4Threading.hh"
#include "G4ios.hh"
#include "Output/AnalysisOutput.hh"
#include "Output/OutputManager.hh"
#include "Output/RunSummary.hh"
#include "Scoring/HistoryStatistics.hh"
#include "Scoring/ScoringManager.hh"
#include "Scoring/ThreadLocalScoringContext.hh"
#include "Source/SourceManager.hh"

#include <algorithm>
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

    if (role_ != Role::Worker) {
        RunProgress::Begin(run->GetRunID(), run->GetNumberOfEventToBeProcessed());
    }

    if (role_ != Role::Worker && biasingManager_ && biasingManager_->IsEnabled()) {
        try {
            biasingManager_->ValidateActiveProcessRules();
        } catch (const std::exception& error) {
            G4Exception("RunAction::BeginOfRunAction", "AIHLBiasingTarget001", RunMustBeAborted, error.what());
            return;
        }
    }

    if (role_ != Role::Worker && sourceManager_) {
        try {
            sourceManager_->PrepareForRun(run->GetNumberOfEventToBeProcessed());
        } catch (const std::exception& error) {
            // Recorded in the shared failure registry so batch and interactive
            // sessions end with a failed summary and a non-zero exit code.
            if (OutputManager* output = ActiveOutputManager()) {
                output->RecordOutputFailure("source_prepare_run", error.what(), run->GetRunID());
            }
            G4cerr << "[SourceFailure] " << error.what() << G4endl;
            if (auto* runManager = G4RunManager::GetRunManager()) runManager->AbortRun(true);
            return;
        }
    }

    const int runID = run->GetRunID();
    if (verboseLevel_ > 0) {
        G4cout << "[RunAction] Begin run " << runID << G4endl;
    }
    if (role_ != Role::Worker) runTimer_.Start();

    OutputManager* outputManager = ActiveOutputManager();
    ScoringManager* scoringManager = ActiveScoringManager();

    const char* stage = "run_begin_validate_targets";
    try {
        if (role_ != Role::Master && biasingManager_ && biasingManager_->IsEnabled()) {
            stage = "biasing_thread_begin";
            biasingManager_->BeginThreadRun(runID);
        }
        stage = "run_begin_validate_targets";
        // The interactive UI invokes beamOn without passing through main.cc's
        // batch macro guard. Check the master/sequential output targets before
        // any worker begins writing event data.
        if (outputManager && role_ != Role::Worker) {
            auto* runManager = G4RunManager::GetRunManager();
            const int threads = runManager ? std::max(1, runManager->GetNumberOfThreads()) : 1;
            outputManager->ValidateOutputTargetDirectories(runID, threads);
        }
        stage = "run_begin_set_run_id";
        if (outputManager) {
            outputManager->SetRunId(runID);
            stage = "run_begin_summary";
            outputManager->GetRunSummary().Set("run_id_begin", runID);
            stage = "run_begin_initialize";
            outputManager->Initialize();
            if (outputManager->WritesRoot()) {
                // Master and workers each open the same logical file; Geant4
                // merges worker histograms/ntuples into the master's file.
                stage = "run_begin_root_open";
                AnalysisOutput::H1Binning raw;
                AnalysisOutput::H1Binning weighted;
                if (scoringManager) {
                    const auto r = scoringManager->GetEdepHistogramBinning(false);
                    const auto w = scoringManager->GetEdepHistogramBinning(true);
                    raw = {r.bins, r.min, r.max};
                    weighted = {w.bins, w.min, w.max};
                }
                AnalysisOutput::BeginRun(outputManager->RootFilePath(), raw, weighted);
            }
        }
        if (role_ != Role::Master && scoringManager) {
            stage = "scoring_begin_run";
            scoringManager->BeginRun(runID);
            scoringManager->RecordEffectiveConfigApplied(runID, G4Threading::G4GetThreadId());
        }
        stage = "effective_config_run_begin";
        if (effectiveBegin_) effectiveBegin_(runID, role_ == Role::Master ? nullptr : scoringManager, outputManager);
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

    if (role_ != Role::Master && biasingManager_ && biasingManager_->IsEnabled()) {
        attempt("biasing_thread_end", [&]() { biasingManager_->EndThreadRun(runID); });
    }

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
        // Geant4 merges worker scoring meshes into the master before the
        // master's EndOfRunAction, so meshes are exported once, here.
        // Workers still hold their own partial mesh values here; in MT the
        // master owns no ntuples, so ROOT rows come from workers (per thread)
        // and the merged CSV comes from the master.
        if (!outputManager->HasOutputFailure()) {
            if (role_ != Role::Master) {
                attempt("scoring_mesh_root", [&]() {
                    outputManager->FillScoringMeshesRoot(runID, run->GetNumberOfEvent());
                });
            }
            if (role_ != Role::Worker) {
                attempt("scoring_mesh_csv", [&]() {
                    outputManager->WriteScoringMeshesCsv(runID, run->GetNumberOfEvent());
                });
            }
        }
        // Workers submitted their per-event statistics in WriteAll(); Geant4
        // finishes every worker run before this master callback.
        if (role_ != Role::Worker) {
            runTimer_.Stop();
            if (!outputManager->HasOutputFailure()) {
                attempt("scorer_statistics_csv", [&]() {
                    outputManager->WriteScorerStatisticsCsv(runID, run->GetNumberOfEvent(),
                                                            runTimer_.GetRealElapsed());
                });
            }
            HistoryStatistics::Take(runID);  // drop partial results of a failed run
        }
        // Always close an open ROOT file, even after a failure, so the master
        // can finish merging. Workers end before the master in Geant4 MT.
        attempt("root_write_close", [&]() {
            if (AnalysisOutput::EndRun() && role_ != Role::Worker) {
                outputManager->RegisterGeneratedFile(outputManager->RootFilePath(),
                                                     OutputManager::ArtifactScope::Run, runID);
            }
        });
        if (role_ == Role::Worker) {
            attempt("worker_close", [&]() { outputManager->Close(); });
        }
    } else if (verboseLevel_ > 0) {
        G4cout << "[RunAction] OutputManager is null; final output skipped." << G4endl;
    }
    attempt("effective_config_thread_finalization", [&]() {
        if (effectiveEnd_) effectiveEnd_(runID, role_ == Role::Master ? nullptr : scoringManager, outputManager);
    });
    if (role_ != Role::Worker) {
        RunProgress::End(runID, run->GetNumberOfEventToBeProcessed(), run->GetNumberOfEvent(),
                         outputManager && outputManager->HasOutputFailure());
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

void RunAction::SetSourceManager(SourceManager* sourceManager)
{
    sourceManager_ = sourceManager;
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
