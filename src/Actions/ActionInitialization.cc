#include "Actions/ActionInitialization.hh"

#include "Actions/EventAction.hh"
#include "Actions/RunAction.hh"
#include "Actions/SteppingAction.hh"
#include "Actions/TrackingAction.hh"
#include "Source/PrimaryGeneratorAction.hh"

#include <stdexcept>

ActionInitialization::ActionInitialization(SourceManager* sourceManager,
                                           ScoringManager* scoringManager,
                                           OutputManager* outputManager)
    : sourceManager_(sourceManager),
      scoringManager_(scoringManager),
      outputManager_(outputManager)
{
}

ActionInitialization::~ActionInitialization() = default;

void ActionInitialization::BuildForMaster() const
{
    auto* runAction = new RunAction(scoringManager_, outputManager_);
    runAction->SetVerboseLevel(verboseLevel_);
    SetUserAction(runAction);
}

void ActionInitialization::Build() const
{
    if (!sourceManager_) {
        throw std::runtime_error(
            "ActionInitialization::Build failed: SourceManager is null");
    }

    SetUserAction(new PrimaryGeneratorAction(sourceManager_));

    auto* runAction = new RunAction(scoringManager_, outputManager_);
    runAction->SetVerboseLevel(verboseLevel_);
    SetUserAction(runAction);

    auto* eventAction = new EventAction(scoringManager_);
    eventAction->SetVerboseLevel(verboseLevel_);
    SetUserAction(eventAction);

    auto* steppingAction = new SteppingAction(scoringManager_);
    steppingAction->SetVerboseLevel(verboseLevel_);
    SetUserAction(steppingAction);

    auto* trackingAction = new TrackingAction();
    trackingAction->SetVerboseLevel(verboseLevel_);
    SetUserAction(trackingAction);
}

void ActionInitialization::SetVerboseLevel(int level)
{
    if (level < 0) {
        throw std::runtime_error(
            "ActionInitialization::SetVerboseLevel failed: level must be >= 0");
    }
    verboseLevel_ = level;
}

int ActionInitialization::GetVerboseLevel() const
{
    return verboseLevel_;
}
