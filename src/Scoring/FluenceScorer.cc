#include "Scoring/FluenceScorer.hh"

FluenceScorer::FluenceScorer(const std::string& name)
    : ScorerBase(name)
{
}

FluenceScorer::~FluenceScorer() = default;

void FluenceScorer::ScoreHit(const HitRecord&)
{
    // Fluence needs a clear surface/area or track-length scoring definition.
    // This first implementation keeps the scorer as a registerable no-op.
}

void FluenceScorer::Write(OutputManager&)
{
}

void FluenceScorer::Reset()
{
}
