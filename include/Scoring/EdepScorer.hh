#pragma once

#include "Output/Histogram1D.hh"
#include "Scoring/ScorerBase.hh"

#include <map>
#include <string>

class EdepScorer : public ScorerBase {
public:
    explicit EdepScorer(const std::string& name = "edep");
    ~EdepScorer() override;

    void BeginRun(int runID) override;
    void EndRun(int runID) override;

    void BeginEvent(int eventID) override;
    void EndEvent(int eventID) override;

    void ScoreHit(const HitRecord& hit) override;
    void Write(OutputManager& output) override;
    void Reset() override;

    void EnableRawHistogram(bool enable);
    bool IsRawHistogramEnabled() const;

    void EnableWeightedHistogram(bool enable);
    bool IsWeightedHistogramEnabled() const;

    void ConfigureRawHistogram(int bins, double min, double max);
    void ConfigureWeightedHistogram(int bins, double min, double max);

    void EnableVolumeSummary(bool enable);
    bool IsVolumeSummaryEnabled() const;

    void EnableParticleSummary(bool enable);
    bool IsParticleSummaryEnabled() const;

    double GetCurrentEventRawEdep() const;
    double GetCurrentEventWeightedEdep() const;

    double GetRunRawEdep() const;
    double GetRunWeightedEdep() const;

private:
    static std::string SummaryKey(const std::string& value);
    static std::string ToString(double value);
    void WriteSummaryCsv(OutputManager& output,
                         const std::string& baseFilename,
                         const std::map<std::string, double>& raw,
                         const std::map<std::string, double>& weighted) const;

    int currentRunID_ = -1;
    int currentEventID_ = -1;

    double currentEventRawEdep_ = 0.0;
    double currentEventWeightedEdep_ = 0.0;

    double runRawEdep_ = 0.0;
    double runWeightedEdep_ = 0.0;

    bool rawHistogramEnabled_ = true;
    bool weightedHistogramEnabled_ = true;
    bool volumeSummaryEnabled_ = true;
    bool particleSummaryEnabled_ = true;

    Histogram1D rawEdepHist_;
    Histogram1D weightedEdepHist_;

    std::map<std::string, double> volumeRawEdep_;
    std::map<std::string, double> volumeWeightedEdep_;
    std::map<std::string, double> particleRawEdep_;
    std::map<std::string, double> particleWeightedEdep_;
};
