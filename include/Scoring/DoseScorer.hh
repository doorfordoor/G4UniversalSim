#pragma once

#include "Scoring/ScorerBase.hh"

class DoseScorer : public ScorerBase {
public:
    explicit DoseScorer(const std::string& name = "dose");
    ~DoseScorer() override;

    void ScoreHit(const HitRecord& hit) override;
    void Write(OutputManager& output) override;
    void Reset() override;
};
