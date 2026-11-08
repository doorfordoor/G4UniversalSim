#include "Actions/WorkerRunContext.hh"

#include "Output/OutputManager.hh"
#include "Scoring/ScoringManager.hh"

OutputManager* WorkerRunContext::GetOutputManager() const
{
    return sequentialOutput ? sequentialOutput : output.get();
}

ScoringManager* WorkerRunContext::GetScoringManager() const
{
    return scoring.get();
}
