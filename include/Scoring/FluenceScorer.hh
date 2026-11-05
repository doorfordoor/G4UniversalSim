#pragma once

#include "Scoring/HistoryStatistics.hh"
#include "Scoring/ScorerBase.hh"
#include "Scoring/VolumeFilter.hh"
#include "Scoring/VolumeSpectrum.hh"

#include <map>
#include <memory>
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

    // Roadmap H2-2: optional per-step filter and kinetic-energy spectrum.
    void SetFilter(std::unique_ptr<VolumeFilter> filter);
    void SetSpectrum(std::unique_ptr<VolumeSpectrum> spectrum);
    const VolumeFilter* GetFilter() const { return filter_.get(); }
    const VolumeSpectrum* GetSpectrum() const { return spectrum_.get(); }
    long long GetFilterAcceptedSteps() const { return filterAccepted_; }
    long long GetFilterRejectedSteps() const { return filterRejected_; }

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
    std::unique_ptr<VolumeFilter> filter_;
    std::unique_ptr<VolumeSpectrum> spectrum_;
    long long filterAccepted_ = 0;
    long long filterRejected_ = 0;
};
