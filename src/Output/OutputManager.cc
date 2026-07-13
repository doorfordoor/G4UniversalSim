#include "Output/OutputManager.hh"

#include "Utils/FileUtils.hh"
#include "Utils/StringUtils.hh"

#include <iomanip>
#include <algorithm>
#include <filesystem>
#include <sstream>
#include <stdexcept>

namespace {

std::vector<std::string> ListRegularFiles(const std::string& directory)
{
    std::vector<std::string> files;
    std::error_code error;
    if (!std::filesystem::is_directory(directory, error)) return files;

    for (const auto& entry : std::filesystem::recursive_directory_iterator(directory, error)) {
        if (error) break;
        if (!entry.is_regular_file(error)) continue;
        files.push_back(std::filesystem::absolute(entry.path(), error).lexically_normal().string());
        if (error) break;
    }
    std::sort(files.begin(), files.end());
    return files;
}

}  // namespace

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
    clone->threadSuffixEnabled_ = threadSuffixEnabled_;
    clone->runSummary_ = runSummary_;
    clone->outputDirectoriesUsed_ = outputDirectoriesUsed_;
    clone->baselineFiles_ = baselineFiles_;
    clone->baselineFileTimes_ = baselineFileTimes_;
    clone->writtenFiles_ = writtenFiles_;
    return clone;
}

void OutputManager::SetOutputDir(const std::string& outputDir)
{
    if (outputDirLocked_) {
        throw std::runtime_error("Output directory is locked by an explicit CLI option");
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
    if (!threadSuffixEnabled_) {
        return baseName;
    }

    const std::string suffix = "_t" + std::to_string(threadId_);
    const std::string extension = FileUtils::Extension(baseName);
    if (extension.empty()) {
        return baseName + suffix;
    }

    const std::string parent = FileUtils::ParentPath(baseName);
    const std::string filename = FileUtils::Filename(baseName);
    const std::string stem = filename.substr(0, filename.size() - extension.size());
    const std::string threaded = stem + suffix + extension;
    return parent.empty() ? threaded : FileUtils::JoinPath(parent, threaded);
}

void OutputManager::Initialize()
{
    FileUtils::CreateDirectories(outputDir_);
    const std::string absoluteDir = FileUtils::AbsolutePath(outputDir_);
    if (std::find(outputDirectoriesUsed_.begin(), outputDirectoriesUsed_.end(), absoluteDir) ==
        outputDirectoriesUsed_.end()) {
        outputDirectoriesUsed_.push_back(absoluteDir);
        const auto files = ListRegularFiles(absoluteDir);
        baselineFiles_.insert(baselineFiles_.end(), files.begin(), files.end());
        for (const auto& file : files) {
            std::error_code error;
            const auto time = std::filesystem::last_write_time(file, error);
            if (!error) baselineFileTimes_[file] = time;
        }
    }
    initialized_ = true;
}

void OutputManager::OpenHitFile()
{
    Initialize();
    hitWriter_ = std::make_unique<CsvWriter>(MakeOutputPath(MakeThreadFilename("hits.csv")));
    hitWriter_->WriteHeader(HitHeader());
    RegisterGeneratedFile(hitWriter_->GetFilename());
}

void OutputManager::OpenEventEdepFile()
{
    Initialize();
    eventEdepWriter_ =
        std::make_unique<CsvWriter>(MakeOutputPath(MakeThreadFilename("event_edep.csv")));
    eventEdepWriter_->WriteHeader(EventEdepHeader());
    RegisterGeneratedFile(eventEdepWriter_->GetFilename());
}

void OutputManager::WriteHit(const HitRecord& record)
{
    if (!hitWriter_ || !hitWriter_->IsOpen()) {
        OpenHitFile();
    }

    WriteHitRow({
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
        ToString(record.weight),
        ToString(record.LETcalc),
        ToString(record.LETstep)
    });
}

void OutputManager::WriteEventEdep(const EventEdepRecord& record)
{
    if (!eventEdepWriter_ || !eventEdepWriter_->IsOpen()) {
        OpenEventEdepFile();
    }

    WriteEventEdepRow({
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
    const Histogram1D& hist = GetHistogram1D(name);
    const std::string safeName = StringUtils::Trim(name).empty() ? "unnamed" : name;
    const std::string filename = MakeOutputPath(MakeThreadFilename("hist_" + safeName + ".csv"));
    hist.WriteCSV(filename);
    RegisterGeneratedFile(filename);
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
    runSummary_.WriteText(MakeOutputPath("run_summary.txt"));
}

void OutputManager::RecordRun(int runId, std::int64_t plannedEvents, std::int64_t completedEvents)
{
    runSummary_.AddRun(runId, plannedEvents, completedEvents);
}

void OutputManager::RegisterGeneratedFile(const std::string& filename)
{
    const std::string absolute = FileUtils::AbsolutePath(filename);
    if (std::find(writtenFiles_.begin(), writtenFiles_.end(), absolute) == writtenFiles_.end()) {
        writtenFiles_.push_back(absolute);
    }
}

std::vector<std::string> OutputManager::GetGeneratedFiles() const
{
    std::vector<std::string> generated;
    for (const auto& directory : outputDirectoriesUsed_) {
        for (const auto& file : ListRegularFiles(directory)) {
            std::error_code error;
            const auto currentTime = std::filesystem::last_write_time(file, error);
            const auto baselineIt = baselineFileTimes_.find(file);
            if (baselineIt == baselineFileTimes_.end() ||
                (baselineIt->second != currentTime && !error)) {
                generated.push_back(file);
            }
        }
    }
    for (const auto& file : writtenFiles_) {
        if (FileUtils::IsFile(file)) generated.push_back(file);
    }
    std::sort(generated.begin(), generated.end());
    generated.erase(std::unique(generated.begin(), generated.end()), generated.end());
    return generated;
}

void OutputManager::Flush()
{
    if (hitWriter_) {
        hitWriter_->Flush();
    }
    if (eventEdepWriter_) {
        eventEdepWriter_->Flush();
    }
}

void OutputManager::Close()
{
    if (hitWriter_) {
        hitWriter_->Close();
    }
    if (eventEdepWriter_) {
        eventEdepWriter_->Close();
    }
}

std::vector<std::string> OutputManager::HitHeader()
{
    return {
        "eventID", "trackID", "parentID", "particle", "edep", "ndep", "stepLength",
        "x0", "y0", "z0", "x1", "y1", "z1", "px", "py", "pz", "kineticEnergy",
        "process", "volume", "weight", "LETcalc", "LETstep"
    };
}

std::vector<std::string> OutputManager::EventEdepHeader()
{
    return {"eventID", "raw_edep", "weighted_edep"};
}

std::string OutputManager::ToString(double value)
{
    std::ostringstream oss;
    oss << std::setprecision(12) << value;
    return oss.str();
}
