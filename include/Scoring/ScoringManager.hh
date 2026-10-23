#pragma once

#include "Output/OutputRecord.hh"
#include "Scoring/PhaseSpace.hh"
#include "Scoring/ScorerBase.hh"
#include "Scoring/TrajectoryRecorder.hh"

#include <map>
#include <memory>
#include <set>
#include <string>
#include <vector>

class ConfigManager;
class G4Step;
class CsvWriter;
class EdepScorer;
class NielTable;
class OutputManager;

class ScoringManager {
public:
    ScoringManager();
    ~ScoringManager();

    std::unique_ptr<ScoringManager> CloneForThread(OutputManager* outputManager,
                                                   int threadId) const;

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
    // Particles included in LET averages; empty = all charged particles.
    void SetLETParticles(const std::set<std::string>& particles);
    const std::set<std::string>& GetLETParticles() const;

    void EnableDoseScoring(bool enable);
    bool IsDoseScoringEnabled() const;

    void EnableFluenceScoring(bool enable);
    bool IsFluenceScoringEnabled() const;

    // Displacement damage dose from NIEL tables ([scoring] displacement,
    // [scoring.displacement] <particle> = <table.csv>), roadmap B2.
    void EnableDisplacementScoring(bool enable);
    bool IsDisplacementScoringEnabled() const;
    void SetNielTables(const std::map<std::string, std::shared_ptr<const NielTable>>& tables);
    const std::map<std::string, std::shared_ptr<const NielTable>>& GetNielTables() const;

    void SetAutoCreateDefaultScorers(bool enable);
    bool IsAutoCreateDefaultScorersEnabled() const;

    void ConfigureEdepHistogram(int bins, double min, double max);
    void ConfigureWeightedEdepHistogram(int bins, double min, double max);
    struct EdepHistogramBinning {
        int bins = 200;
        double min = 0.0;
        double max = 10.0;
    };
    EdepHistogramBinning GetEdepHistogramBinning(bool weighted) const;

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
    // Accumulate a zero-deposition step for fluence only, without hits or Edep.
    void ScoreFluenceStep(const HitRecord& hit);
    // Record failures before a transport step can be converted to HitRecord.
    void ReportFluenceTransportFailure(const std::string& message);
    // Charged step without energy deposit: LET track-length contribution only.
    void ScoreLETStep(const HitRecord& hit);
    // Step without energy deposit (e.g. neutrons): displacement damage only.
    void ScoreDisplacementStep(const HitRecord& hit);

    double GetCurrentEventRawEdep() const;
    double GetCurrentEventWeightedEdep() const;
    int GetCurrentEventID() const;

    void WriteAll();

    void LoadFromConfig(const ConfigManager& config);
    void PrintSummary() const;

    // Phase-space recording ([phase_space] in the main INI): particles entering
    // the named physical volume are written to phase_space_tN[_rR].csv.
    // Trajectories of the first N events ([output] trajectories, roadmap H1).
    const TrajectorySettings& GetTrajectorySettings() const;
    bool RecordsTrajectories() const;      // the current event is recorded
    void RecordTrajectoryStep(const G4Step* step);

    bool IsPhaseSpaceEnabled() const;
    const std::string& GetPhaseSpaceVolume() const;
    bool AcceptsPhaseSpaceParticle(const std::string& particle) const;
    bool KillsPhaseSpaceParticles() const;
    // Worker: fills runID/eventID and writes one row; failures abort the run.
    void RecordPhaseSpace(PhaseSpaceParticle particle);

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
    void BeginPhaseSpaceRun();
    void EndPhaseSpaceRun();

    OutputManager* outputManager_ = nullptr;
    bool enabled_ = true;
    bool hitOutputEnabled_ = true;
    bool eventEdepOutputEnabled_ = true;
    bool edepScoringEnabled_ = true;
    bool letScoringEnabled_ = false;
    bool doseScoringEnabled_ = false;
    bool fluenceScoringEnabled_ = false;
    bool displacementScoringEnabled_ = false;
    std::map<std::string, std::shared_ptr<const NielTable>> nielTables_;
    std::set<std::string> letParticles_;
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

    TrajectoryRecorder trajectories_;       // [output] trajectories (roadmap H1)
    std::string phaseSpaceVolume_;          // empty = disabled
    std::set<std::string> phaseSpaceParticles_;  // empty = all
    bool phaseSpaceKill_ = false;
    std::unique_ptr<CsvWriter> phaseSpaceWriter_;
};
