#pragma once

#include "Output/Histogram1D.hh"
#include "Scoring/ScorerBase.hh"

class LETScorer : public ScorerBase {
public:
    explicit LETScorer(const std::string& name = "let");
    ~LETScorer() override;

    void ScoreHit(const HitRecord& hit) override;
    void Write(OutputManager& output) override;
    void Reset() override;

    void EnableHistogram(bool enable);
    bool IsHistogramEnabled() const;
    void ConfigureHistogram(int bins, double min, double max);

private:
    bool histogramEnabled_ = false;
    Histogram1D letHist_;
};
