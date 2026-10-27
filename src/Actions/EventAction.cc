#include "Actions/EventAction.hh"
#include "Actions/RunProgress.hh"

#include "Actions/WorkerRunContext.hh"
#include "G4Event.hh"
#include "G4Run.hh"
#include "G4RunManager.hh"
#include "G4ios.hh"
#include "Scoring/ScoringManager.hh"

#include <stdexcept>
#include <utility>

EventAction::EventAction(ScoringManager* scoringManager)
    : scoringManager_(scoringManager)
{
}

EventAction::EventAction(std::shared_ptr<WorkerRunContext> context)
    : context_(std::move(context))
{
}

EventAction::~EventAction() = default;

void EventAction::BeginOfEventAction(const G4Event* event)
{
    if (!event) {
        throw std::runtime_error("EventAction::BeginOfEventAction failed: G4Event is null");
    }

    const int eventID = event->GetEventID();
    if (verboseLevel_ > 1) {
        G4cout << "[EventAction] Begin event " << eventID << G4endl;
    }
    if (ScoringManager* scoringManager = ActiveScoringManager()) {
        scoringManager->BeginEvent(eventID);
    }
}

void EventAction::EndOfEventAction(const G4Event* event)
{
    if (!event) {
        throw std::runtime_error("EventAction::EndOfEventAction failed: G4Event is null");
    }

    const int eventID = event->GetEventID();
    if (ScoringManager* scoringManager = ActiveScoringManager()) {
        scoringManager->EndEvent(eventID);
    }
    if (auto* manager = G4RunManager::GetRunManager()) {
        if (const auto* run = manager->GetCurrentRun()) {
            RunProgress::EventCompleted(run->GetRunID(), event->IsAborted());
        }
    }
    if (verboseLevel_ > 1) {
        G4cout << "[EventAction] End event " << eventID << G4endl;
    }
}

void EventAction::SetScoringManager(ScoringManager* scoringManager)
{
    scoringManager_ = scoringManager;
}

ScoringManager* EventAction::GetScoringManager()
{
    return ActiveScoringManager();
}

void EventAction::SetVerboseLevel(int level)
{
    if (level < 0) {
        throw std::runtime_error("EventAction::SetVerboseLevel failed: level must be >= 0");
    }
    verboseLevel_ = level;
}

int EventAction::GetVerboseLevel() const
{
    return verboseLevel_;
}

ScoringManager* EventAction::ActiveScoringManager() const
{
    return context_ ? context_->GetScoringManager() : scoringManager_;
}
