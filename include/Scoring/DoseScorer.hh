#pragma once

#include "Scoring/HistoryStatistics.hh"
#include "Scoring/ScorerBase.hh"

#include <map>
#include <string>

class DoseScorer : public ScorerBase {
public:
    explicit DoseScorer(const std::string& name = "dose");
    ~DoseScorer() override;

    void BeginRun(int runID) override;
    void EndEvent(int eventID) override;
    void ScoreHit(const HitRecord& hit) override;
    void Write(OutputManager& output) override;
    void Reset() override;

private:
    struct VolumeDose {
        std::string name;
        double mass = 0.0;
        HistoryTally rawEdep;       // Geant4 energy units
        HistoryTally weightedEdep;
    };
    int runID_ = -1;
    long long events_ = 0;
    std::map<std::string, VolumeDose> volumes_;
    HistoryTallySet touched_;
};
