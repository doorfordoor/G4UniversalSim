#pragma once

#include "Output/OutputRecord.hh"
#include "Scoring/ScorerBase.hh"

#include <memory>
#include <string>
#include <vector>

class ConfigManager;
class EdepScorer;
class OutputManager;

class ScoringManager {
public:
    ScoringManager();
    ~ScoringManager();

    void SetOutputManager(OutputManager* outputManager);
    OutputManager* GetOutputManager();
    const OutputManager* GetOutputManager() const;

    void Enable(bool enable);
    bool IsEnabled() const;

    void EnableHitOutput(bool enable);
    bool IsHitOutputEnabled() const;

    void EnableEventEdepOutput(bool enable);
    bool IsEventEdepOutputEnabled() const;

    void EnableEdepScoring(bool enable);
    bool IsEdepScoringEnabled() const;

    void EnableLETScoring(bool enable);
    bool IsLETScoringEnabled() const;

    void EnableDoseScoring(bool enable);
    bool IsDoseScoringEnabled() const;

    void EnableFluenceScoring(bool enable);
    bool IsFluenceScoringEnabled() const;

    void SetAutoCreateDefaultScorers(bool enable);
    bool IsAutoCreateDefaultScorersEnabled() const;

    void ConfigureEdepHistogram(int bins, double min, double max);
    void ConfigureWeightedEdepHistogram(int bins, double min, double max);

    void SetVerboseLevel(int level);
    int GetVerboseLevel() const;

    void Clear();

    void RegisterScorer(std::unique_ptr<ScorerBase> scorer);
    void EnsureDefaultScorers();

    bool HasScorer(const std::string& name) const;
    ScorerBase* GetScorer(const std::string& name);
    const ScorerBase* GetScorer(const std::string& name) const;
    std::vector<std::string> GetScorerNames() const;

    void BeginRun(int runID);
    void EndRun(int runID);

    void BeginEvent(int eventID);
    void EndEvent(int eventID);

    void ScoreHit(const HitRecord& hit);

    double GetCurrentEventRawEdep() const;
    double GetCurrentEventWeightedEdep() const;
    int GetCurrentEventID() const;

    void WriteAll();

    void LoadFromConfig(const ConfigManager& config);
    void PrintSummary() const;

private:
    struct HistogramConfig {
        int bins = 200;
        double min = 0.0;
        double max = 10.0;
        bool configured = false;
    };

    static std::string NormalizeName(const std::string& name);
    std::vector<ScorerBase*> EnabledScorers();
    std::vector<const ScorerBase*> EnabledScorers() const;

    EdepScorer* GetEdepScorer();
    const EdepScorer* GetEdepScorer() const;
    void ApplyEdepSettings(EdepScorer& scorer) const;
    void SetScorerEnabledIfExists(const std::string& name, bool enable);

    OutputManager* outputManager_ = nullptr;
    bool enabled_ = true;
    bool hitOutputEnabled_ = true;
    bool eventEdepOutputEnabled_ = true;
    bool edepScoringEnabled_ = true;
    bool letScoringEnabled_ = false;
    bool doseScoringEnabled_ = false;
    bool fluenceScoringEnabled_ = false;
    bool autoCreateDefaultScorers_ = true;

    bool edepRawHistogramEnabled_ = true;
    bool edepWeightedHistogramEnabled_ = true;
    bool edepVolumeSummaryEnabled_ = true;
    bool edepParticleSummaryEnabled_ = true;
    HistogramConfig rawEdepHistogram_;
    HistogramConfig weightedEdepHistogram_;

    int verboseLevel_ = 0;
    int currentRunID_ = -1;
    int currentEventID_ = -1;
    double currentEventRawEdep_ = 0.0;
    double currentEventWeightedEdep_ = 0.0;
    std::vector<std::unique_ptr<ScorerBase>> scorers_;
};
