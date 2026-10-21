#pragma once

#include "Scoring/HistoryStatistics.hh"
#include "Scoring/ScorerBase.hh"

#include <map>
#include <string>

class FluenceScorer : public ScorerBase {
public:
    explicit FluenceScorer(const std::string& name = "fluence");
    ~FluenceScorer() override;

    void BeginRun(int runID) override;
    void EndEvent(int eventID) override;
    void ScoreHit(const HitRecord& hit) override;
    void Write(OutputManager& output) override;
    void Reset() override;

private:
    struct VolumeData {
        std::string name;
        double volume = 0.0;
        HistoryTally rawLength;       // Geant4 length units
        HistoryTally weightedLength;
    };
    int runID_ = -1;
    long long events_ = 0;
    std::map<std::string, VolumeData> volumes_;
    HistoryTallySet touched_;
};
