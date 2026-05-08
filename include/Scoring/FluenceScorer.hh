#pragma once

#include "Scoring/ScorerBase.hh"

class FluenceScorer : public ScorerBase {
public:
    explicit FluenceScorer(const std::string& name = "fluence");
    ~FluenceScorer() override;

    void ScoreHit(const HitRecord& hit) override;
    void Write(OutputManager& output) override;
    void Reset() override;
};
