#pragma once

#include "Scoring/ScorerBase.hh"

#include <map>
#include <string>

class FluenceScorer : public ScorerBase {
public:
    explicit FluenceScorer(const std::string& name = "fluence");
    ~FluenceScorer() override;

    void BeginRun(int runID) override;
    void ScoreHit(const HitRecord& hit) override;
    void Write(OutputManager& output) override;
    void Reset() override;

private:
    struct VolumeData {
        std::string name;
        double volume = 0.0;
        double rawLength = 0.0;
        double weightedLength = 0.0;
    };
    int runID_ = -1;
    std::map<std::string, VolumeData> volumes_;
};
