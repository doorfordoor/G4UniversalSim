#pragma once

#include "Scoring/HistoryStatistics.hh"
#include "Scoring/ScorerBase.hh"
#include "Scoring/VolumeFilter.hh"
#include "Scoring/VolumeSpectrum.hh"

#include <map>
#include <memory>
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

    // Roadmap H2-2: optional per-step filter and kinetic-energy spectrum.
    void SetFilter(std::unique_ptr<VolumeFilter> filter);
    void SetSpectrum(std::unique_ptr<VolumeSpectrum> spectrum);
    const VolumeFilter* GetFilter() const { return filter_.get(); }
    const VolumeSpectrum* GetSpectrum() const { return spectrum_.get(); }
    long long GetFilterAcceptedSteps() const { return filterAccepted_; }
    long long GetFilterRejectedSteps() const { return filterRejected_; }

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
    std::unique_ptr<VolumeFilter> filter_;
    std::unique_ptr<VolumeSpectrum> spectrum_;
    long long filterAccepted_ = 0;
    long long filterRejected_ = 0;
};
