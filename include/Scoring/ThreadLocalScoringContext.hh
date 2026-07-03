#pragma once

class ScoringManager;

namespace AIHL {

void SetCurrentThreadScoringManager(ScoringManager* scoringManager);
ScoringManager* GetCurrentThreadScoringManager();

}  // namespace AIHL
