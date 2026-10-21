#pragma once

#include "Scoring/ScorerBase.hh"

#include <map>
#include <string>

class DoseScorer : public ScorerBase {
public:
    explicit DoseScorer(const std::string& name = "dose");
    ~DoseScorer() override;

    void BeginRun(int runID) override;
    void ScoreHit(const HitRecord& hit) override;
    void Write(OutputManager& output) override;
    void Reset() override;

private:
    struct VolumeDose {
        std::string name;
        double mass = 0.0;
        double rawEdep = 0.0;
        double weightedEdep = 0.0;
    };
    int runID_ = -1;
    std::map<std::string, VolumeDose> volumes_;
};
