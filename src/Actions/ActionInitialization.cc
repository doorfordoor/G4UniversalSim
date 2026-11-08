#include "Actions/ActionInitialization.hh"

#include "Actions/EventAction.hh"
#include "Actions/RunAction.hh"
#include "Actions/SteppingAction.hh"
#include "Actions/TrackingAction.hh"
#include "Actions/PhaseSpaceStackingAction.hh"
#include "Actions/WorkerRunContext.hh"
#include "Output/OutputManager.hh"
#include "Scoring/ScoringManager.hh"
#include "Scoring/ThreadLocalScoringContext.hh"
#include "Source/PrimaryGeneratorAction.hh"

#ifdef G4MULTITHREADED
#include "G4Threading.hh"
#endif

#include <memory>
#include <stdexcept>

namespace {

int CurrentThreadIdOrZero()
{
#ifdef G4MULTITHREADED
    const int threadId = G4Threading::G4GetThreadId();
    return threadId < 0 ? 0 : threadId;
#else
    return 0;
#endif
}

RunAction::Role CurrentRunActionRole()
{
#ifdef G4MULTITHREADED
    return G4Threading::G4GetThreadId() < 0
        ? RunAction::Role::Sequential
        : RunAction::Role::Worker;
#else
    return RunAction::Role::Sequential;
#endif
}

}  // namespace

ActionInitialization::ActionInitialization(SourceManager* sourceManager,
                                           ScoringManager* scoringManager,
                                           OutputManager* outputManager,
                                           BiasingManager* biasingManager)
    : sourceManager_(sourceManager),
      masterScoringManager_(scoringManager),
      masterOutputManager_(outputManager),
      biasingManager_(biasingManager)
{
}

ActionInitialization::~ActionInitialization() = default;

void ActionInitialization::BuildForMaster() const
{
    auto* runAction = new RunAction(
        masterScoringManager_,
        masterOutputManager_,
        RunAction::Role::Master,
        biasingManager_);
    runAction->SetSourceManager(sourceManager_);
    runAction->SetEffectiveCallbacks(effectiveBegin_, effectiveEnd_);
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

    auto context = std::make_shared<WorkerRunContext>();
    const int threadId = CurrentThreadIdOrZero();
    const auto role = CurrentRunActionRole();
    if (role == RunAction::Role::Sequential && masterOutputManager_) {
        context->sequentialOutput = masterOutputManager_;
    } else if (masterOutputManager_) {
        context->output = masterOutputManager_->CloneForThread(threadId);
    } else {
        context->output = std::make_unique<OutputManager>();
        context->output->SetThreadId(threadId);
    }
    auto* output = context->GetOutputManager();
    output->SetThreadId(threadId);
    output->EnableThreadSuffix(true);

    // Publish TLS only after the complete local scorer set has been rebuilt.
    // A failed worker must still install its actions and reach the kernel's
    // normal synchronization/cleanup path; exceptions cannot escape Build.
    AIHL::SetCurrentThreadScoringManager(nullptr);
    try {
        if (masterScoringManager_) {
            context->scoring = masterScoringManager_->CloneForThread(
                output,
                threadId);
        } else {
            context->scoring = std::make_unique<ScoringManager>();
            context->scoring->SetOutputManager(output);
        }
    } catch (const std::exception& error) {
        output->RecordStartupFailure("scoring_factory_build", error.what());
    } catch (...) {
        output->RecordStartupFailure("scoring_factory_build", "unknown exception");
    }
    AIHL::SetCurrentThreadScoringManager(context->scoring.get());

    auto* runAction = new RunAction(context, role, biasingManager_);
    runAction->SetEffectiveCallbacks(effectiveBegin_, effectiveEnd_);
    if (role != RunAction::Role::Worker) runAction->SetSourceManager(sourceManager_);
    runAction->SetVerboseLevel(verboseLevel_);
    SetUserAction(runAction);

    auto* eventAction = new EventAction(context);
    eventAction->SetVerboseLevel(verboseLevel_);
    SetUserAction(eventAction);

    auto* steppingAction = new SteppingAction(context);
    steppingAction->SetVerboseLevel(verboseLevel_);
    SetUserAction(steppingAction);

    auto* trackingAction = new TrackingAction();
    trackingAction->SetVerboseLevel(verboseLevel_);
    SetUserAction(trackingAction);
    SetUserAction(new PhaseSpaceStackingAction(context));
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
