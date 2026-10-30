#include "Output/OutputManager.hh"

#include "Output/AnalysisOutput.hh"
#include "Config/InputProvenance.hh"
#include "Scoring/HistoryStatistics.hh"
#include "Scoring/NumericChecks.hh"
#include "Scoring/ScoringMeshExport.hh"
#include "Utils/FileUtils.hh"
#include "Utils/StringUtils.hh"

#include <cmath>
#include <iomanip>
#include <random>
#include <limits>
#include <algorithm>
#include <cstdlib>
#include <exception>
#include <filesystem>
#include <sstream>
#include <stdexcept>

namespace {

std::string TestOutputFault()
{
#ifdef _WIN32
    char* value = nullptr;
    std::size_t length = 0;
    if (_dupenv_s(&value, &length, "G4USIM_TEST_OUTPUT_FAULT") != 0) return {};
    const std::string result = value ? value : "";
    std::free(value);
    return result;
#else
    const char* value = std::getenv("G4USIM_TEST_OUTPUT_FAULT");
    return value ? value : "";
#endif
}

}  // namespace

OutputManager::GeneratedFileRegistry::GeneratedFileRegistry()
{
    // Independent OS-backed entropy: never consume or reseed the Geant4 engine.
    std::random_device entropy;
    std::uniform_int_distribution<unsigned> byte(0, 255);
    const char* hex = "0123456789abcdef";
    executionId.reserve(32);
    for (int i = 0; i < 16; ++i) {
        const auto value = byte(entropy);
        executionId += hex[value >> 4]; executionId += hex[value & 15];
    }
}

OutputManager::~OutputManager() noexcept
{
    try {
        Close();
    } catch (...) {
    }
}

std::unique_ptr<OutputManager> OutputManager::CloneForThread(int threadId) const
{
    auto clone = std::make_unique<OutputManager>();
    clone->outputDir_ = outputDir_;
    clone->outputDirLocked_ = outputDirLocked_;
    clone->threadId_ = threadId;
    clone->runId_ = runId_;
    clone->threadSuffixEnabled_ = threadSuffixEnabled_;
    clone->format_ = format_;
    clone->formatExplicit_ = formatExplicit_;
    clone->autoFormatSelector_ = autoFormatSelector_;
    clone->runSummary_ = runSummary_;
    clone->generatedFiles_ = generatedFiles_;
    clone->effectiveState_ = effectiveState_->Clone();
    return clone;
}

void OutputManager::SetOutputDir(const std::string& outputDir)
{
    if (outputDirLocked_) {
        throw std::runtime_error("Output directory is locked by an explicit CLI option");
    }
    // Test-only: fail inside the manager setter (rather than in the
    // Messenger) to check that SimulationManager keeps its prior state.
    if (TestOutputFault() == "manager_set_dir" &&
        outputDir.find("__g4usim_inject_manager_set_dir__") != std::string::npos) {
        throw std::runtime_error("Injected OutputManager::SetOutputDir failure");
    }
    outputDir_ = outputDir.empty() ? "output" : outputDir;
}

void OutputManager::SetOutputDirLocked(bool locked)
{
    outputDirLocked_ = locked;
}

bool OutputManager::IsOutputDirLocked() const
{
    return outputDirLocked_;
}

const std::string& OutputManager::GetOutputDir() const
{
    return outputDir_;
}

void OutputManager::SetThreadId(int threadId)
{
    threadId_ = threadId;
}

int OutputManager::GetThreadId() const
{
    return threadId_;
}

void OutputManager::SetRunId(int runId)
{
    if (runId < 0) throw std::runtime_error("OutputManager run ID must be nonnegative");
    if (runId_ == runId) return;
    Close();
    // Test-only: a failure during run transition must be attributed to the
    // attempted run, without discarding the previous run's completed files.
    if (runId == 1 && threadId_ == 0 && TestOutputFault() == "begin_set_run_id_t0") {
        throw std::runtime_error("Injected failure during OutputManager::SetRunId");
    }
    hitWriter_.reset();
    eventEdepWriter_.reset();
    histograms1D_.clear();
    runId_ = runId;
}

int OutputManager::GetRunId() const
{
    return runId_;
}

OutputManager::Format OutputManager::ParseFormat(const std::string& value)
{
    const std::string normalized = StringUtils::ToLower(StringUtils::Trim(value));
    if (normalized == "csv") return Format::Csv;
    if (normalized == "root") return Format::Root;
    if (normalized == "both" || normalized == "csv+root" || normalized == "root+csv") return Format::Both;
    if (normalized == "auto") return Format::Auto;
    throw std::runtime_error("Unknown output format '" + value + "'; expected csv, root, both or auto");
}

const char* OutputManager::FormatName(Format format)
{
    switch (format) {
    case Format::Csv: return "csv";
    case Format::Root: return "root";
    case Format::Both: return "both";
    case Format::Auto: return "auto";
    }
    return "csv";
}

void OutputManager::SetFormat(Format format)
{
    if (HasOpenFiles() || AnalysisOutput::IsOpen()) {
        throw std::runtime_error("Output format cannot change while output files are open");
    }
    if (format != Format::Csv && format != Format::Root && format != Format::Both && format != Format::Auto)
        throw std::invalid_argument("Unsupported output format enum");
    if (format == Format::Auto) {
        if (!autoFormatSelector_) throw std::runtime_error("Auto output format requires an explicit scoring selector");
        (void)autoFormatSelector_(); // Validate before publishing the new request.
    }
    format_ = format;
    formatExplicit_ = true;
}

OutputManager::Format OutputManager::GetRequestedFormat() const
{
    return format_;
}

void OutputManager::SetAutoFormatSelector(std::function<bool()> selector)
{
    if (HasOpenFiles() || AnalysisOutput::IsOpen())
        throw std::runtime_error("Auto format selector cannot change while output files are open");
    if (format_ == Format::Auto) {
        if (!selector) throw std::runtime_error("Cannot remove the selector of an active auto format request");
        (void)selector();
    }
    autoFormatSelector_ = std::move(selector);
}

OutputManager::Format OutputManager::GetFormat() const
{
    if (format_ != Format::Auto) return format_;
    if (!autoFormatSelector_) throw std::runtime_error("Auto output format requires an explicit scoring selector");
    return autoFormatSelector_() ? Format::Root : Format::Csv;
}

std::string OutputManager::FormatSelectionReason() const
{
    if (format_ == Format::Auto) return GetFormat() == Format::Root
        ? "auto_enabled_scoring_with_hits_or_event_edep"
        : "auto_no_enabled_hit_or_event_edep_output";
    return !formatExplicit_ ? "default_csv" : std::string("explicit_") + FormatName(format_);
}

bool OutputManager::WritesCsv() const
{
    const auto actual = GetFormat();
    return actual == Format::Csv || actual == Format::Both;
}

bool OutputManager::WritesRoot() const
{
    const auto actual = GetFormat();
    return actual == Format::Root || actual == Format::Both;
}

std::string OutputManager::RootFilename() const
{
    return runId_ > 0 ? "g4usim_r" + std::to_string(runId_) + ".root" : "g4usim.root";
}

std::string OutputManager::RootFilePath() const
{
    return MakeOutputPath(RootFilename());
}

void OutputManager::WriteRunMetadataJson()
{
    const std::string filename = MakeOutputPath("run_metadata.json");
    // A repeated finalization may replace a previously completed file. Drop
    // that registration before touching it; only a successful new close can
    // publish the replacement as generated output.
    const std::string absolute = FileUtils::AbsolutePath(filename);
    {
        std::lock_guard<std::mutex> guard(generatedFiles_->mutex);
        auto& files = generatedFiles_->files;
        files.erase(std::remove_if(files.begin(), files.end(), [&](const ArtifactEvidence& file) {
            return file.path == absolute;
        }), files.end());
    }
    try {
        runSummary_.WriteJson(filename);
    } catch (const RunSummary::MetadataWriteError& error) {
        RecordOutputFailure(error.stage, error.what());
        throw;
    } catch (const std::exception& error) {
        RecordOutputFailure("run_metadata_write", error.what());
        throw;
    }
    RegisterGeneratedFile(filename, ArtifactScope::Process);
}

void OutputManager::FillScoringMeshesRoot(int runId, long long threadEvents)
{
    if (!WritesRoot() || !ScoringMeshExport::HasMeshes()) return;
    for (const auto& c : ScoringMeshExport::CollectCells()) {
        AnalysisOutput::FillMeshCell(runId, threadId_, c.mesh, c.quantity, c.unit, c.i0, c.i1, c.i2,
                                     c.sum, c.sumSquares, c.entries, threadEvents);
    }
}

void OutputManager::WriteScoringMeshesCsv(int runId, long long events)
{
    if (!ScoringMeshExport::HasMeshes()) return;
    ScoringMeshExport::RecordInSummary(runSummary_);
    // This is the master publication boundary for every format. Worker ROOT
    // rows can be finite while merging their moments overflows on the master.
    const auto cells = ScoringMeshExport::CollectCells();
    if (!WritesCsv()) return;
    Initialize();
    const std::string filename = MakeOutputPath(
        runId > 0 ? "scoring_mesh_r" + std::to_string(runId) + ".csv" : "scoring_mesh.csv");
    CsvWriter writer(filename);
    writer.WriteHeader({"runID", "mesh", "quantity", "unit", "i0", "i1", "i2", "sum", "sum_sq",
                        "entries", "n_events", "rel_error", "uncertainty_estimator", "uncertainty_status"});
    for (const auto& c : cells) {
        writer.WriteRow({std::to_string(runId), c.mesh, c.quantity, c.unit, std::to_string(c.i0),
                         std::to_string(c.i1), std::to_string(c.i2), ToString(c.sum), ToString(c.sumSquares),
                         std::to_string(c.entries), std::to_string(events),
                         ToString(ScoringMeshExport::RelativeError(c.sum, c.sumSquares, events)),
                         "uncorrected_event_moments_v1", HistoryStatistics::UncertaintyStatus(events, c.sum)});
    }
    writer.Close();
    RegisterGeneratedFile(filename, ArtifactScope::Run, runId);
}

void OutputManager::WriteScorerStatisticsCsv(int runId, long long events, double wallSeconds)
{
    const auto entries = HistoryStatistics::Take(runId);
    if (entries.empty()) return;
    Initialize();
    const std::string filename = MakeOutputPath(
        runId > 0 ? "scorer_statistics_r" + std::to_string(runId) + ".csv" : "scorer_statistics.csv");
    CsvWriter writer(filename);
    writer.WriteHeader({"runID", "scorer", "quantity", "key", "name", "unit", "estimator", "n_events",
                        "entries", "value", "mean_per_event", "std_error", "rel_error", "fom_per_s",
                        "run_wall_time_s", "sum", "sum_sq", "uncertainty_estimator", "uncertainty_status"});
    for (const auto& item : entries) {
        const auto& [scorer, quantity, key] = item.first;
        const HistoryStatistics::Entry& e = item.second;
        double value = 0.0;
        double relError = 0.0;
        std::string mean;
        std::string sum;
        std::string sumSq;
        if (e.ratio) {
            value = e.denSum != 0.0 ? e.sum / e.denSum : 0.0;
            relError = HistoryStatistics::RatioRelativeError(e.sum, e.sumSq, e.denSum, e.denSumSq, e.crossSum);
        } else {
            value = e.sum;
            relError = HistoryStatistics::RelativeError(e.sum, e.sumSq, events);
            mean = ToString(events > 0 ? e.sum / static_cast<double>(events) : 0.0);
            sum = ToString(e.sum);
            sumSq = ToString(e.sumSq);
        }
        ScoringNumeric::Finite(value, "published statistics value");
        const double standardError = ScoringNumeric::Multiply(relError, std::abs(value), "published standard error");
        writer.WriteRow({std::to_string(runId), scorer, quantity, key, e.name, e.unit,
                         e.ratio ? "ratio" : "total", std::to_string(events), std::to_string(e.entries),
                         ToString(value), mean, ToString(standardError), ToString(relError),
                         ToString(HistoryStatistics::FigureOfMerit(relError, wallSeconds)),
                         ToString(wallSeconds), sum, sumSq,
                         e.ratio ? "uncorrected_delta_ratio_v1" : "uncorrected_event_moments_v1",
                         HistoryStatistics::UncertaintyStatus(events, e.sum, e.ratio, e.denSum)});
    }
    writer.Close();
    RegisterGeneratedFile(filename, ArtifactScope::Run, runId);
}

void OutputManager::EnableThreadSuffix(bool enable)
{
    threadSuffixEnabled_ = enable;
}

bool OutputManager::IsThreadSuffixEnabled() const
{
    return threadSuffixEnabled_;
}

bool OutputManager::IsInitialized() const
{
    return initialized_;
}

bool OutputManager::IsHitFileOpen() const
{
    return hitWriter_ && hitWriter_->IsOpen();
}

bool OutputManager::IsEventEdepFileOpen() const
{
    return eventEdepWriter_ && eventEdepWriter_->IsOpen();
}

bool OutputManager::HasOpenFiles() const
{
    return IsHitFileOpen() || IsEventEdepFileOpen();
}

std::string OutputManager::GetHitFilename() const
{
    return hitWriter_ ? hitWriter_->GetFilename() : "";
}

std::string OutputManager::GetEventEdepFilename() const
{
    return eventEdepWriter_ ? eventEdepWriter_->GetFilename() : "";
}

std::string OutputManager::MakeOutputPath(const std::string& filename) const
{
    return FileUtils::JoinPath(outputDir_, filename);
}

std::string OutputManager::MakeThreadFilename(const std::string& baseName) const
{
    if (!threadSuffixEnabled_ && runId_ <= 0) {
        return baseName;
    }

    const std::string suffix = (threadSuffixEnabled_ ? "_t" + std::to_string(threadId_) : "")
        + (runId_ > 0 ? "_r" + std::to_string(runId_) : "");
    const std::string extension = FileUtils::Extension(baseName);
    if (extension.empty()) {
        return baseName + suffix;
    }

    const std::string parent = FileUtils::ParentPath(baseName);
    const std::string filename = FileUtils::Filename(baseName);
    const std::string stem = filename.substr(0, filename.size() - extension.size());
    const std::string named = stem + suffix + extension;
    return parent.empty() ? named : FileUtils::JoinPath(parent, named);
}

void OutputManager::ValidateOutputTargetDirectories(int runId, int threadCount) const
{
    if (runId < 0 || threadCount < 1) {
        throw std::runtime_error("Invalid run ID or thread count for output target validation");
    }
    const std::filesystem::path directory(outputDir_);
    std::error_code error;
    const bool directoryExists = std::filesystem::exists(directory, error);
    if (error) throw std::filesystem::filesystem_error("Cannot inspect output directory", directory, error);
    if (directoryExists && std::filesystem::is_regular_file(directory, error)) {
        throw std::runtime_error("Output directory is an existing file: " + directory.string());
    }
    if (error) throw std::filesystem::filesystem_error("Cannot inspect output directory", directory, error);
    for (int thread = 0; thread < threadCount; ++thread) {
        OutputManager candidate;
        candidate.outputDir_ = outputDir_;
        // ActionInitialization::Build() always enables the suffix on worker
        // outputs, even when an earlier UI command disabled it on the master.
        candidate.threadSuffixEnabled_ = true;
        candidate.threadId_ = thread;
        candidate.runId_ = runId;
        if (thread == 0 && WritesRoot()) {
            candidate.format_ = format_;
            const std::filesystem::path rootPath(candidate.RootFilePath());
            error.clear();
            const bool rootExists = std::filesystem::exists(rootPath, error);
            if (error) throw std::filesystem::filesystem_error("Cannot inspect output ROOT target", rootPath, error);
            if (rootExists && std::filesystem::is_directory(rootPath, error)) {
                throw std::runtime_error("Output ROOT target is an existing directory: " + rootPath.string());
            }
        }
        if (!WritesCsv()) continue;
        for (const char* name : {"hits.csv", "event_edep.csv", "hist_edep_raw.csv",
                                 "hist_edep_weighted.csv", "edep_volume_summary.csv",
                                 "edep_particle_summary.csv", "dose_volume_summary.csv",
                                 "fluence_volume_summary.csv", "let_volume_summary.csv",
                                 "displacement_volume_summary.csv"}) {
            const std::filesystem::path path(candidate.MakeOutputPath(candidate.MakeThreadFilename(name)));
            error.clear();
            const bool exists = std::filesystem::exists(path, error);
            if (error) throw std::filesystem::filesystem_error("Cannot inspect output CSV target", path, error);
            if (exists && std::filesystem::is_directory(path, error)) {
                throw std::runtime_error("Output CSV target is an existing directory: " + path.string());
            }
            if (error) throw std::filesystem::filesystem_error("Cannot inspect output CSV target", path, error);
        }
    }
}

void OutputManager::Initialize()
{
    FileUtils::CreateDirectories(outputDir_);
    initialized_ = true;
}

void OutputManager::OpenHitFile()
{
    Initialize();
    hitWriter_ = std::make_unique<CsvWriter>(MakeOutputPath(MakeThreadFilename("hits.csv")));
    hitWriter_->WriteHeader(HitHeader());
    RecordEffectiveConfigState("writer_open");
}

void OutputManager::OpenEventEdepFile()
{
    Initialize();
    eventEdepWriter_ =
        std::make_unique<CsvWriter>(MakeOutputPath(MakeThreadFilename("event_edep.csv")));
    eventEdepWriter_->WriteHeader(EventEdepHeader());
    RecordEffectiveConfigState("writer_open");
}

void OutputManager::WriteHit(const HitRecord& record)
{
    for (double value : {record.edep, record.ndep, record.stepLength, record.x0, record.y0,
                         record.z0, record.x1, record.y1, record.z1, record.px, record.py,
                         record.pz, record.kineticEnergy, record.weight}) {
        ScoringNumeric::Finite(value, "published hit");
    }
    if (WritesRoot()) AnalysisOutput::FillHit(record, threadId_);
    if (!WritesCsv()) return;
    if (!hitWriter_ || !hitWriter_->IsOpen()) {
        OpenHitFile();
    }

    WriteHitRow({
        std::to_string(record.runID),
        std::to_string(record.eventID),
        std::to_string(record.trackID),
        std::to_string(record.parentID),
        record.particleName,
        ToString(record.edep),
        ToString(record.ndep),
        ToString(record.stepLength),
        ToString(record.x0),
        ToString(record.y0),
        ToString(record.z0),
        ToString(record.x1),
        ToString(record.y1),
        ToString(record.z1),
        ToString(record.px),
        ToString(record.py),
        ToString(record.pz),
        ToString(record.kineticEnergy),
        record.processName,
        record.volumeName,
        ToString(record.weight)
    });
}

void OutputManager::WriteEventEdep(const EventEdepRecord& record)
{
    ScoringNumeric::Finite(record.rawEdep, "published event raw Edep");
    ScoringNumeric::Finite(record.weightedEdep, "published event weighted Edep");
    if (WritesRoot()) AnalysisOutput::FillEvent(record, threadId_);
    if (!WritesCsv()) return;
    if (!eventEdepWriter_ || !eventEdepWriter_->IsOpen()) {
        OpenEventEdepFile();
    }

    WriteEventEdepRow({
        std::to_string(record.runID),
        std::to_string(record.eventID),
        ToString(record.rawEdep),
        ToString(record.weightedEdep)
    });
}

void OutputManager::WriteHitRow(const std::vector<std::string>& values)
{
    if (!hitWriter_ || !hitWriter_->IsOpen()) {
        OpenHitFile();
    }
    hitWriter_->WriteRow(values);
}

void OutputManager::WriteEventEdepRow(const std::vector<std::string>& values)
{
    if (!eventEdepWriter_ || !eventEdepWriter_->IsOpen()) {
        OpenEventEdepFile();
    }
    eventEdepWriter_->WriteRow(values);
}

void OutputManager::AddHistogram1D(const Histogram1D& hist)
{
    if (hist.GetName().empty()) {
        throw std::runtime_error("Cannot add Histogram1D with empty name");
    }
    histograms1D_[hist.GetName()] = hist;
}

Histogram1D& OutputManager::GetHistogram1D(const std::string& name)
{
    const auto it = histograms1D_.find(name);
    if (it == histograms1D_.end()) {
        throw std::runtime_error("Histogram1D not found: '" + name + "'");
    }
    return it->second;
}

const Histogram1D& OutputManager::GetHistogram1D(const std::string& name) const
{
    const auto it = histograms1D_.find(name);
    if (it == histograms1D_.end()) {
        throw std::runtime_error("Histogram1D not found: '" + name + "'");
    }
    return it->second;
}

bool OutputManager::HasHistogram1D(const std::string& name) const
{
    return histograms1D_.find(name) != histograms1D_.end();
}

void OutputManager::WriteHistogram1D(const std::string& name)
{
    // ROOT histograms are filled per event by ScoringManager; this is the CSV path.
    if (!WritesCsv()) return;
    const Histogram1D& hist = GetHistogram1D(name);
    const std::string safeName = StringUtils::Trim(name).empty() ? "unnamed" : name;
    const std::string filename = MakeOutputPath(MakeThreadFilename("hist_" + safeName + ".csv"));
    const std::string axisUnit = name == "edep_raw" || name == "edep_weighted" ? "MeV" : "";
    hist.WriteCSV(filename, axisUnit);
    RegisterGeneratedFile(filename, ArtifactScope::Thread, runId_, threadId_);
}

void OutputManager::WriteAllHistograms()
{
    for (const auto& item : histograms1D_) {
        WriteHistogram1D(item.first);
    }
}

RunSummary& OutputManager::GetRunSummary()
{
    return runSummary_;
}

const RunSummary& OutputManager::GetRunSummary() const
{
    return runSummary_;
}

void OutputManager::WriteRunSummary()
{
    const std::string filename = MakeOutputPath("run_summary.txt");
    const std::string absolute = FileUtils::AbsolutePath(filename);
    {
        std::lock_guard<std::mutex> guard(generatedFiles_->mutex);
        auto& files = generatedFiles_->files;
        files.erase(std::remove_if(files.begin(), files.end(), [&](const ArtifactEvidence& file) {
            return file.path == absolute;
        }), files.end());
    }
    runSummary_.WriteText(filename);
    RegisterGeneratedFile(filename, ArtifactScope::Process);
}

void OutputManager::RecordRun(int runId, std::int64_t plannedEvents, std::int64_t completedEvents)
{
    runSummary_.AddRun(runId, plannedEvents, completedEvents);
}

const std::string& OutputManager::GetExecutionId() const
{
    return generatedFiles_->executionId;
}

void OutputManager::RegisterGeneratedFile(const std::string& filename)
{
    if (runId_ < 0) RegisterGeneratedFile(filename, ArtifactScope::Process);
    else if (threadId_ < 0) RegisterGeneratedFile(filename, ArtifactScope::Run, runId_);
    else RegisterGeneratedFile(filename, ArtifactScope::Thread, runId_, threadId_);
}

void OutputManager::RegisterGeneratedFile(const std::string& filename, ArtifactScope scope,
                                          std::optional<int> runId, std::optional<int> threadId)
{
    if (filename.empty()) throw std::invalid_argument("Generated artifact path cannot be empty");
    if (scope != ArtifactScope::Process && scope != ArtifactScope::Run && scope != ArtifactScope::Thread)
        throw std::invalid_argument("Unknown generated artifact scope");
    if ((scope == ArtifactScope::Process && (runId || threadId)) ||
        (scope == ArtifactScope::Run && (!runId || *runId < 0 || threadId)) ||
        (scope == ArtifactScope::Thread && (!runId || *runId < 0 || !threadId || *threadId < 0)))
        throw std::invalid_argument("Generated artifact scope requires explicit valid run/thread identity");
    const std::string absolute = FileUtils::AbsolutePath(filename);
    bool conflict = false;
    {
        std::lock_guard<std::mutex> guard(generatedFiles_->mutex);
        const auto found = std::find_if(generatedFiles_->files.begin(), generatedFiles_->files.end(),
            [&](const ArtifactEvidence& file) { return file.path == absolute; });
        if (found == generatedFiles_->files.end()) {
            ArtifactEvidence file;
            file.path = absolute; file.execution_id = GetExecutionId(); file.scope = scope;
            file.run_id = runId; file.thread_id = threadId;
            generatedFiles_->files.push_back(std::move(file));
        } else conflict = found->scope != scope || found->run_id != runId || found->thread_id != threadId;
    }
    if (conflict) {
        const auto message = "Conflicting explicit scope for generated artifact: '" + absolute + "'";
        RecordOutputFailure("artifact_integrity", message, runId.value_or(-1));
        throw std::runtime_error(message);
    }
}

std::vector<std::string> OutputManager::GetGeneratedFiles() const
{
    std::vector<std::string> generated;
    {
        std::lock_guard<std::mutex> guard(generatedFiles_->mutex);
        for (const auto& file : generatedFiles_->files) generated.push_back(file.path);
    }
    // A vanished registered artifact is a failure, never silently erased.
    std::sort(generated.begin(), generated.end());
    return generated;
}

std::vector<OutputManager::ArtifactEvidence> OutputManager::CollectArtifactEvidence(bool includeMetadataSelf, bool excludeSummary)
{
    std::vector<ArtifactEvidence> evidence;
    {
        std::lock_guard<std::mutex> guard(generatedFiles_->mutex);
        evidence = generatedFiles_->files;
    }
    const auto metadata = FileUtils::AbsolutePath(MakeOutputPath("run_metadata.json"));
    if (excludeSummary) {
        // An explicit finalization bridge will rewrite and independently hash
        // this process summary. Do not carry its previous bytes into that pass.
        const auto summary = FileUtils::AbsolutePath(MakeOutputPath("run_summary.txt"));
        evidence.erase(std::remove_if(evidence.begin(), evidence.end(), [&](const ArtifactEvidence& file) {
            return file.path == summary;
        }), evidence.end());
    }
    if (includeMetadataSelf && std::none_of(evidence.begin(), evidence.end(),
            [&](const ArtifactEvidence& file) { return file.path == metadata; })) {
        ArtifactEvidence self; self.path = metadata; self.execution_id = GetExecutionId();
        evidence.push_back(std::move(self));
    }
    for (auto& file : evidence) {
        file.sha256.reset(); file.size_bytes.reset(); file.reason.clear();
        if (file.path == metadata) {
            file.scope = ArtifactScope::Process; file.run_id.reset(); file.thread_id.reset();
            file.integrity_status = "self_reference_excluded";
            file.reason = "Metadata cannot contain its own byte hash or size";
            continue;
        }
        try {
            if (TestOutputFault() == "artifact_hash_master")
                throw std::runtime_error("Injected artifact hash read failure");
            const auto digest = input_provenance::HashFile(file.path);
            if (digest.size_bytes > static_cast<std::uint64_t>(std::numeric_limits<std::int64_t>::max()))
                throw std::runtime_error("Artifact byte size exceeds metadata integer range");
            file.sha256 = digest.sha256; file.size_bytes = digest.size_bytes;
            file.integrity_status = "hashed";
        } catch (const std::exception& error) {
            file.integrity_status = "unavailable"; file.reason = error.what();
            // Preserve the first output failure, including any earlier worker cause.
            RecordOutputFailure("artifact_integrity", "Artifact '" + file.path + "': " + error.what(),
                                file.run_id.value_or(-1));
        }
    }
    std::sort(evidence.begin(), evidence.end(), [](const ArtifactEvidence& a, const ArtifactEvidence& b) {
        return a.path < b.path;
    });
    return evidence;
}

void OutputManager::RecordOutputFailure(const std::string& stage, const std::string& message,
                                        int attemptedRunId)
{
    std::lock_guard<std::mutex> guard(generatedFiles_->mutex);
    if (!generatedFiles_->hasFailure) {
        generatedFiles_->firstFailure = {
            attemptedRunId >= 0 ? attemptedRunId : runId_, threadId_, stage, message};
        generatedFiles_->hasFailure = true;
    }
}

bool OutputManager::HasOutputFailure() const
{
    std::lock_guard<std::mutex> guard(generatedFiles_->mutex);
    return generatedFiles_->hasFailure;
}

std::size_t OutputManager::GetCommandFailureCount() const
{
    return commandFailureCount_;
}

const std::string& OutputManager::GetLastCommandFailure() const
{
    return lastCommandFailure_;
}

void OutputManager::RecordCommandFailure(const std::string& message)
{
    ++commandFailureCount_;
    lastCommandFailure_ = message;
}

OutputManager::OutputFailure OutputManager::GetOutputFailure() const
{
    std::lock_guard<std::mutex> guard(generatedFiles_->mutex);
    return generatedFiles_->firstFailure;
}

void OutputManager::Flush()
{
    std::exception_ptr firstError;
    const auto flushWriter = [&firstError](const std::unique_ptr<CsvWriter>& writer) {
        if (!writer) return;
        try {
            writer->Flush();
        } catch (...) {
            if (!firstError) firstError = std::current_exception();
        }
    };
    flushWriter(hitWriter_);
    flushWriter(eventEdepWriter_);
    if (firstError) std::rethrow_exception(firstError);
}

void OutputManager::Close()
{
    std::exception_ptr firstError;
    const auto closeWriter = [this, &firstError](const std::unique_ptr<CsvWriter>& writer) {
        if (!writer || !writer->IsOpen()) return;
        try {
            writer->Close();
            RegisterGeneratedFile(writer->GetFilename(), ArtifactScope::Thread, runId_, threadId_);
        } catch (...) {
            if (!firstError) firstError = std::current_exception();
        }
    };
    closeWriter(hitWriter_);
    closeWriter(eventEdepWriter_);
    if (firstError) std::rethrow_exception(firstError);
}

std::vector<std::string> OutputManager::HitHeader()
{
    return {
        "runID", "eventID", "trackID", "parentID", "particle", "edep_MeV", "ndep_MeV", "stepLength_mm",
        "x0_mm", "y0_mm", "z0_mm", "x1_mm", "y1_mm", "z1_mm", "px", "py", "pz", "kineticEnergy_MeV",
        "process", "volume", "weight"
    };
}

std::vector<std::string> OutputManager::EventEdepHeader()
{
    return {"runID", "eventID", "raw_edep_MeV", "weighted_edep_MeV"};
}

std::string OutputManager::ToString(double value)
{
    std::ostringstream oss;
    oss << std::setprecision(12) << value;
    return oss.str();
}
