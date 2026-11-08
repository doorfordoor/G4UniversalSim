#include "Actions/PhaseSpaceStackingAction.hh"
#include "Actions/WorkerRunContext.hh"
#include "Source/PhaseSpaceReplayState.hh"
#include "Output/OutputManager.hh"
#include "Scoring/ScoringManager.hh"
#include "G4StackManager.hh"
#include "G4RunManager.hh"
#include "G4Run.hh"
#include "G4Track.hh"
#include <stdexcept>
#include <utility>
PhaseSpaceStackingAction::PhaseSpaceStackingAction(std::shared_ptr<WorkerRunContext> c):context_(std::move(c)) {
    if(!context_ || !context_->GetOutputManager())throw std::runtime_error("PhaseSpaceStackingAction missing output context");
}
PhaseSpaceStackingAction::~PhaseSpaceStackingAction()=default;
G4ClassificationOfNewTrack PhaseSpaceStackingAction::ClassifyNewTrack(const G4Track* track) {
    auto* output=context_->GetOutputManager();
    const auto abort=[] {
        if(auto* run=G4RunManager::GetRunManager()) {
            if(run->GetCurrentRun())run->AbortRun(false);
        }
    };
    if(output->HasOutputFailure()){abort();return fKill;} // blocks all remaining primaries, not only marked ones
    try {
        if(!stackManager || !track)throw std::runtime_error("PhaseSpace stacking SDK wiring missing");
        const auto classification=stackManager->GetDefaultClassification();
        phase_space_replay::RestoreBeforeTracking(*const_cast<G4Track*>(track));
        return classification;
    } catch(const std::exception& e) {
        auto* rm=G4RunManager::GetRunManager();
        output->RecordOutputFailure("phase_space_restore_first_track",e.what(),rm&&rm->GetCurrentRun()?rm->GetCurrentRun()->GetRunID():-1);
    } catch(...) {
        auto* rm=G4RunManager::GetRunManager();
        output->RecordOutputFailure("phase_space_restore_first_track","unknown exception",rm&&rm->GetCurrentRun()?rm->GetCurrentRun()->GetRunID():-1);
    }
    abort();return fKill;
}
