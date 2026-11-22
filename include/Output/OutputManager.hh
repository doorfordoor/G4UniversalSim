#pragma once

#include "Output/CsvWriter.hh"
#include "Config/EffectiveConfigSupport.hh"
#include "Output/Histogram1D.hh"
#include "Output/NamedHistogram2D.hh"
#include "Output/NamedEventNtuple.hh"
#include "Output/OutputRecord.hh"
#include "Output/RunSummary.hh"

#include <functional>
#include <map>
#include <memory>
#include <mutex>
#include <set>
#include <string>
#include <vector>

class GeometryRegistry;

class OutputManager {
public:
    // Which data files a run produces. CSV keeps the per-thread v3 files;
    // ROOT writes one merged g4usim[_rN].root per run via G4AnalysisManager.
    enum class Format {
        Csv,
        Root,
        Both,
        Auto
    };
    static Format ParseFormat(const std::string& value);
    static const char* FormatName(Format format);

    struct OutputFailure {
        int runId = -1;
        int threadId = -1;
        std::string stage;
        std::string message;
    };
    using ArtifactScope = RunSummary::ArtifactScope;
    using ArtifactEvidence = RunSummary::ArtifactEvidence;
    OutputManager() = default;
    void AcceptEffectiveConfig(const IniReader& reader);
    std::vector<effective_config::Field> ExportEffectiveConfigFields() const;
    effective_config::Value ExportEffectiveConfigEvidence() const;
    void ConfirmEffectiveConfigMutation(const std::string&, effective_config::Origin);
    void RecordEffectiveConfigState(const std::string& stage) const;
    ~OutputManager() noexcept;

    std::unique_ptr<OutputManager> CloneForThread(int threadId) const;

    void SetOutputDir(const std::string& outputDir);
    void SetOutputDirLocked(bool locked);
    bool IsOutputDirLocked() const;
    const std::string& GetOutputDir() const;

    void SetThreadId(int threadId);
    int GetThreadId() const;
    void SetRunId(int runId);
    int GetRunId() const;

    void SetFormat(Format format);
    Format GetFormat() const;
    Format GetRequestedFormat() const;
    // Root binds immutable scoring configuration; clones only read it.
    void SetAutoFormatSelector(std::function<bool()> selector);
    std::string FormatSelectionReason() const;
    bool WritesCsv() const;
    bool WritesRoot() const;
    // ROOT file for the current run: g4usim.root (run 0) or g4usim_rN.root.
    std::string RootFilename() const;
    std::string RootFilePath() const;
    void WriteRunMetadataJson();
    // Master/sequential: merged /score/ mesh results of this run to CSV and the summary.
    void WriteScoringMeshesCsv(int runId, long long events);
    void WriteVoxelRoiMass(int runId, const GeometryRegistry& geometry);
    // Worker/sequential: this thread's partial mesh results to the ROOT "mesh" ntuple.
    void FillScoringMeshesRoot(int runId, long long threadEvents);
    // Master/sequential: merged per-event statistics of the built-in scorers
    // (edep, dose, fluence, LET) to scorer_statistics[_rR].csv, for every output
    // format. events = events of the run, wallSeconds = run wall time (for FOM).
    void WriteScorerStatisticsCsv(int runId, long long events, double wallSeconds);

    void EnableThreadSuffix(bool enable);
    bool IsThreadSuffixEnabled() const;

    bool IsInitialized() const;
    bool IsHitFileOpen() const;
    bool IsEventEdepFileOpen() const;
    bool HasOpenFiles() const;
    std::string GetHitFilename() const;
    std::string GetEventEdepFilename() const;

    std::string MakeOutputPath(const std::string& filename) const;
    std::string MakeThreadFilename(const std::string& baseName) const;
    void ValidateOutputTargetDirectories(int runId, int threadCount,
                                         bool opticalPhotonCounts = false,
                                         bool opticalBoundaryObservations = false,
                                         bool activationObservations = false, bool voxelScoring = false) const;

    void Initialize();

    void SetHitVolumePathEnabled(bool value) { hitVolumePathEnabled_ = value; }
    void OpenHitFile();
    void OpenEventEdepFile();

    void WriteHit(const HitRecord& record);
    void WriteEventEdep(const EventEdepRecord& record);
    void WriteOpticalPhotonCounts(const OpticalPhotonCountRecord& record);
    void WriteVoxelEvent(int eventId, const std::map<std::pair<std::string, int>, VoxelEdepRecord>& cells);
    void FinishVoxelShard(int runId, const std::set<int>& events);
    void PublishVoxelRun(int runId, int expectedWorkers, int completedEvents);
    void WriteActivationObservations(const std::vector<ActivationObservationRecord>& records, int schemaVersion);
    void WriteOpticalBoundarySteps(const std::vector<OpticalBoundaryStepRecord>& records);

    void WriteHitRow(const std::vector<std::string>& values);
    void WriteEventEdepRow(const std::vector<std::string>& values);

    void WriteEventNtuples(const std::vector<NamedEventNtuple>& definitions, const EventEdepRecord& event);
    void FinishEventNtuples(const std::vector<NamedEventNtuple>& definitions, int completed);
    void PublishEventNtuples(const std::vector<NamedEventNtuple>& definitions, int workers, int completed);
    template<class Histogram> void FinishNamedHistograms(const std::vector<Histogram>& histograms, int completedEvents);
    template<class Histogram> void PublishNamedHistograms(const std::vector<Histogram>& definitions, int workers, int completedEvents);
    void AddHistogram1D(const Histogram1D& hist);
    Histogram1D& GetHistogram1D(const std::string& name);
    const Histogram1D& GetHistogram1D(const std::string& name) const;
    bool HasHistogram1D(const std::string& name) const;
    void WriteHistogram1D(const std::string& name);
    void WriteAllHistograms();

    RunSummary& GetRunSummary();
    const RunSummary& GetRunSummary() const;
    void WriteRunSummary();
#ifdef G4USIM_H6_ENGINEERING
    void WriteEngineeringWaterEvent(int runId,int eventId,const std::string& bytes);
#endif
private:
    void WriteEventArtifact(int runId,int eventId,const std::string& bytes,const std::string& prefix);
public:
    void WriteNativeClockEvent(int runId, int eventId, const std::string& bytes);
    void RecordRun(int runId, std::int64_t plannedEvents, std::int64_t completedEvents);
    const std::string& GetExecutionId() const;
    void RegisterGeneratedFile(const std::string& filename);
    void RegisterGeneratedFile(const std::string& filename, ArtifactScope scope,
                               std::optional<int> runId = std::nullopt,
                               std::optional<int> threadId = std::nullopt);
    // Missing/failed reads remain unavailable entries and latch artifact_integrity.
    // HashFile never adds an input observation. Metadata alone excludes itself.
    std::vector<ArtifactEvidence> CollectArtifactEvidence(bool includeMetadataSelf = false, bool excludeSummary = false);
    // Per-run subset of the same registry, hashed after that run's files closed.
    // Does not modify the process-wide F1 registry or the summary.
    std::vector<ArtifactEvidence> CollectRunArtifacts(int runId, bool includeMetadataSelf = false);
    std::vector<std::string> GetGeneratedFiles() const;
    void RecordOutputFailure(const std::string& stage, const std::string& message,
                             int attemptedRunId = -1);
    // Construction has no run association, even if a clone inherited the
    // master's already-started run ID. Preserve the explicit unknown (-1).
    void RecordStartupFailure(const std::string& stage, const std::string& message);
    bool HasOutputFailure() const;
    OutputFailure GetOutputFailure() const;
    // Messenger command failures are separate from worker/file write failures.
    std::size_t GetCommandFailureCount() const;
    const std::string& GetLastCommandFailure() const;
    void RecordCommandFailure(const std::string& message);

    void Flush();
    void Close();

private:
    struct EventNtupleWriter {
        std::unique_ptr<CsvWriter> csv;
        int lastEvent = -1;
        int rows = 0;
    };
    std::map<std::string, EventNtupleWriter> ntupleWriters_;
    EventNtupleWriter& OpenEventNtuple(const NamedEventNtuple& definition);
    std::string EventNtupleFilename(const NamedEventNtuple& definition, bool merged) const;
    struct VoxelShard {
        std::vector<int> events;
        std::string path;  // Empty only for a worker with no completed event.
    };
    template<class Histogram> void WriteNamedHistogram(const Histogram& histogram, bool merged);
    struct GeneratedFileRegistry {
        GeneratedFileRegistry();
        std::mutex mutex;
        std::string executionId;
        std::vector<ArtifactEvidence> files;
        std::map<int, std::map<int, std::vector<Histogram1D>>> histogramShards;
        std::map<int, std::map<int, std::vector<NamedHistogram2D>>> histogram2DShards;
        auto& Shards(const std::vector<Histogram1D>&) { return histogramShards; }
        auto& Shards(const std::vector<NamedHistogram2D>&) { return histogram2DShards; }
        std::map<int, std::map<std::string, std::map<int, EventNtupleShard>>> ntupleShards;
        std::map<int, std::map<int, VoxelShard>> voxelShards;
        bool hasFailure = false;
        OutputFailure firstFailure;
    };

    void FinalizeArtifactEvidence(std::vector<ArtifactEvidence>& evidence);

    std::vector<std::string> HitHeader() const;
    static std::vector<std::string> EventEdepHeader();
    static std::string ToString(double value);

    std::shared_ptr<effective_config::ConsumerState> effectiveState_ = std::make_shared<effective_config::ConsumerState>();
    std::string outputDir_ = "output";
    bool outputDirLocked_ = false;
    bool hitVolumePathEnabled_ = false;
    int threadId_ = 0;
    int runId_ = -1;
    bool threadSuffixEnabled_ = true;
    Format format_ = Format::Csv; // requested policy; GetFormat returns its resolution
    bool formatExplicit_ = false;
    std::function<bool()> autoFormatSelector_;
    // True once Initialize() has created the output directory; current file-open state is HasOpenFiles().
    bool initialized_ = false;
    // Shared by master and worker clones. Only finalized output files enter the manifest.
    std::shared_ptr<GeneratedFileRegistry> generatedFiles_ = std::make_shared<GeneratedFileRegistry>();
    std::unique_ptr<CsvWriter> hitWriter_;
    std::unique_ptr<CsvWriter> eventEdepWriter_;
    std::unique_ptr<CsvWriter> opticalPhotonCountsWriter_;
    std::unique_ptr<CsvWriter> opticalBoundaryStepsWriter_;
    std::unique_ptr<CsvWriter> activationObservationsWriter_;
    std::unique_ptr<CsvWriter> voxelEdepWriter_;
    std::map<std::string, Histogram1D> histograms1D_;
    RunSummary runSummary_;
    std::size_t commandFailureCount_ = 0;
    std::string lastCommandFailure_;
};
