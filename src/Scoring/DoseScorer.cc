#include "Scoring/DoseScorer.hh"

DoseScorer::DoseScorer(const std::string& name)
    : ScorerBase(name)
{
}

DoseScorer::~DoseScorer() = default;

void DoseScorer::ScoreHit(const HitRecord&)
{
    // Dose requires volume mass or material/geometry information. This first
    // scoring implementation intentionally keeps the class as a registerable
    // no-op until that data contract is introduced.
}

void DoseScorer::Write(OutputManager&)
{
}

void DoseScorer::Reset()
{
}
