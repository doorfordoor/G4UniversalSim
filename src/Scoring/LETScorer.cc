#include "Scoring/LETScorer.hh"

#include "Output/OutputManager.hh"

LETScorer::LETScorer(const std::string& name)
    : ScorerBase(name),
      letHist_("let", 200, 0.0, 10.0)
{
}

LETScorer::~LETScorer() = default;

void LETScorer::ScoreHit(const HitRecord& hit)
{
    if (histogramEnabled_ && hit.LETcalc > 0.0) {
        letHist_.Fill(hit.LETcalc, hit.weight);
    }
}

void LETScorer::Write(OutputManager& output)
{
    if (!histogramEnabled_) return;
    output.AddHistogram1D(letHist_);
    output.WriteHistogram1D(letHist_.GetName());
}

void LETScorer::Reset()
{
    letHist_.Reset();
}

void LETScorer::EnableHistogram(bool enable)
{
    histogramEnabled_ = enable;
}

bool LETScorer::IsHistogramEnabled() const
{
    return histogramEnabled_;
}

void LETScorer::ConfigureHistogram(int bins, double min, double max)
{
    letHist_.Configure("let", bins, min, max);
}
