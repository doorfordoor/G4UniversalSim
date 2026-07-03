#include "Scoring/ThreadLocalScoringContext.hh"

namespace {

thread_local ScoringManager* currentThreadScoringManager = nullptr;

}

namespace AIHL {

void SetCurrentThreadScoringManager(ScoringManager* scoringManager)
{
    currentThreadScoringManager = scoringManager;
}

ScoringManager* GetCurrentThreadScoringManager()
{
    return currentThreadScoringManager;
}

}  // namespace AIHL
