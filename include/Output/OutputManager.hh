#pragma once

#include "Output/CsvWriter.hh"
#include "Output/Histogram1D.hh"
#include "Output/OutputRecord.hh"
#include "Output/RunSummary.hh"

#include <map>
#include <memory>
#include <mutex>
#include <string>
#include <vector>

class OutputManager {
public:
    // Which data files a run produces. CSV keeps the per-thread v3 files;
    // ROOT writes one merged g4usim[_rN].root per run via G4AnalysisManager.
    enum class Format {
        Csv,
        Root,
        Both
    };
    static Format ParseFormat(const std::string& value);
    static const char* FormatName(Format format);

    struct OutputFailure {
        int runId = -1;
        int threadId = -1;
        std::string stage;
        std::string message;
    };
    OutputManager() = default;
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
    bool WritesCsv() const;
    bool WritesRoot() const;
    // ROOT file for the current run: g4usim.root (run 0) or g4usim_rN.root.
    std::string RootFilename() const;
    std::string RootFilePath() const;
    void WriteRunMetadataJson();
    // Master/sequential: merged /score/ mesh results of this run to CSV and the summary.
    void WriteScoringMeshesCsv(int runId, long long events);
    // Worker/sequential: this thread's partial mesh results to the ROOT "mesh" ntuple.
    void FillScoringMeshesRoot(int runId, long long threadEvents);

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
    void ValidateOutputTargetDirectories(int runId, int threadCount) const;

    void Initialize();

    void OpenHitFile();
    void OpenEventEdepFile();

    void WriteHit(const HitRecord& record);
    void WriteEventEdep(const EventEdepRecord& record);

    void WriteHitRow(const std::vector<std::string>& values);
    void WriteEventEdepRow(const std::vector<std::string>& values);

    void AddHistogram1D(const Histogram1D& hist);
    Histogram1D& GetHistogram1D(const std::string& name);
    const Histogram1D& GetHistogram1D(const std::string& name) const;
    bool HasHistogram1D(const std::string& name) const;
    void WriteHistogram1D(const std::string& name);
    void WriteAllHistograms();

    RunSummary& GetRunSummary();
    const RunSummary& GetRunSummary() const;
    void WriteRunSummary();
    void RecordRun(int runId, std::int64_t plannedEvents, std::int64_t completedEvents);
    void RegisterGeneratedFile(const std::string& filename);
    std::vector<std::string> GetGeneratedFiles() const;
    void RecordOutputFailure(const std::string& stage, const std::string& message,
                             int attemptedRunId = -1);
    bool HasOutputFailure() const;
    OutputFailure GetOutputFailure() const;
    // Messenger command failures are separate from worker/file write failures.
    std::size_t GetCommandFailureCount() const;
    const std::string& GetLastCommandFailure() const;
    void RecordCommandFailure(const std::string& message);

    void Flush();
    void Close();

private:
    struct GeneratedFileRegistry {
        std::mutex mutex;
        std::vector<std::string> files;
        bool hasFailure = false;
        OutputFailure firstFailure;
    };

    static std::vector<std::string> HitHeader();
    static std::vector<std::string> EventEdepHeader();
    static std::string ToString(double value);

    std::string outputDir_ = "output";
    bool outputDirLocked_ = false;
    int threadId_ = 0;
    int runId_ = -1;
    bool threadSuffixEnabled_ = true;
    Format format_ = Format::Csv;
    // True once Initialize() has created the output directory; current file-open state is HasOpenFiles().
    bool initialized_ = false;
    // Shared by master and worker clones. Only finalized output files enter the manifest.
    std::shared_ptr<GeneratedFileRegistry> generatedFiles_ = std::make_shared<GeneratedFileRegistry>();
    std::unique_ptr<CsvWriter> hitWriter_;
    std::unique_ptr<CsvWriter> eventEdepWriter_;
    std::map<std::string, Histogram1D> histograms1D_;
    RunSummary runSummary_;
    std::size_t commandFailureCount_ = 0;
    std::string lastCommandFailure_;
};
