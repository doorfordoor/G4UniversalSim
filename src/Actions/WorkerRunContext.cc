#include "Actions/WorkerRunContext.hh"

#include "Output/OutputManager.hh"
#include "Scoring/ScoringManager.hh"

OutputManager* WorkerRunContext::GetOutputManager() const
{
    return output.get();
}

ScoringManager* WorkerRunContext::GetScoringManager() const
{
    return scoring.get();
}
