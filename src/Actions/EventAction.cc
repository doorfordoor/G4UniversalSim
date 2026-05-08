#include "Actions/EventAction.hh"

#include "G4Event.hh"
#include "G4ios.hh"
#include "Scoring/ScoringManager.hh"

#include <stdexcept>

EventAction::EventAction(ScoringManager* scoringManager)
    : scoringManager_(scoringManager)
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
    if (scoringManager_) {
        scoringManager_->BeginEvent(eventID);
    }
}

void EventAction::EndOfEventAction(const G4Event* event)
{
    if (!event) {
        throw std::runtime_error("EventAction::EndOfEventAction failed: G4Event is null");
    }

    const int eventID = event->GetEventID();
    if (scoringManager_) {
        scoringManager_->EndEvent(eventID);
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
    return scoringManager_;
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
