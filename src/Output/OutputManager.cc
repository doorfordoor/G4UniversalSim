#include <array>
#include <type_traits>
#include "Output/OutputManager.hh"

#include "Output/AnalysisOutput.hh"
#include "G4SystemOfUnits.hh"
#include "G4Box.hh"
#include "G4LogicalVolume.hh"
#include "G4Material.hh"
#include "G4PhantomParameterisation.hh"
#include "G4VPhysicalVolume.hh"
#include "Geometry/GeometryRegistry.hh"
#include "Geometry/VoxelGridDescriptor.hh"
#include "Config/InputProvenance.hh"
#include "Scoring/HistoryStatistics.hh"
#include "Scoring/NumericChecks.hh"
#include "Scoring/ScoringMeshExport.hh"
#include "Utils/FileUtils.hh"
#include "Utils/StringUtils.hh"

#include <cfenv>
#include <charconv>
#include <cmath>
#include <cstdio>
#include <iomanip>
#include <random>
#include <limits>
#include <locale>
#include <algorithm>
#include <cstdlib>
#include <exception>
#include <filesystem>
#include <sstream>
#include <stdexcept>

#ifdef _WIN32
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>
#endif

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
    opticalPhotonCountsWriter_.reset();
    opticalBoundaryStepsWriter_.reset();
    activationObservationsWriter_.reset();
    voxelEdepWriter_.reset();
    ntupleWriters_.clear();
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

void OutputManager::WriteVoxelRoiMass(int runId, const GeometryRegistry& geometry)
{
    if (!WritesCsv() || runId < 0 || runId != runId_) {
        throw std::runtime_error("voxel ROI mass requires an active CSV master run");
    }
    const auto& bindings = geometry.GetVoxelScoringBindings();
    std::map<std::string, const std::map<const G4VPhysicalVolume*, VoxelScoringBinding>::value_type*> sorted;
    for (const auto& binding : bindings) {
        if (!sorted.emplace(binding.second.gridId, &binding).second) {
            throw std::runtime_error("duplicate grid in voxel ROI mass output");
        }
    }
    const auto filename = MakeOutputPath(runId > 0 ? "voxel_roi_mass_r" + std::to_string(runId) + ".csv"
                                                   : "voxel_roi_mass.csv");
    CsvWriter writer(filename);
    writer.WriteHeader(StringUtils::Split(kVoxelRoiMassCsvHeader, ','));
    const auto number = [](double value) {
        if (!std::isfinite(value)) throw std::runtime_error("nonfinite voxel ROI mass output");
        std::ostringstream stream;
        stream.imbue(std::locale::classic());
        stream << std::setprecision(std::numeric_limits<double>::max_digits10) << value;
        return stream.str();
    };
    for (const auto& [id, entry] : sorted) {
        const auto& [leaf, binding] = *entry;
        const auto& native = *binding.parameterisation;
        const auto& grid = *binding.descriptor;
        const auto& descriptor = grid.inputs.at(0);
        const auto& labels = grid.inputs.at(1);
        auto* solid = dynamic_cast<G4Box*>(leaf->GetLogicalVolume()->GetSolid());
        if (!solid || leaf->GetRegularStructureId() != 1 || native.SkipEqualMaterials()
            || native.GetNoVoxelsX() != static_cast<std::size_t>(binding.shape[0])
            || native.GetNoVoxelsY() != static_cast<std::size_t>(binding.shape[1])
            || native.GetNoVoxelsZ() != static_cast<std::size_t>(binding.shape[2])) {
            throw std::runtime_error("voxel ROI mass disagrees with the actual regular geometry");
        }
        const auto volume = solid->GetCubicVolume();
        if (!std::isfinite(volume) || volume <= 0) throw std::runtime_error("invalid voxel cell volume");
        const auto position = binding.container->GetObjectTranslation();
        const auto& shape = binding.shape;
        const std::vector<std::string> common{
            GetExecutionId(), std::to_string(runId), id, std::to_string(shape[0]), std::to_string(shape[1]),
            std::to_string(shape[2]), number(2 * native.GetVoxelHalfX() / mm),
            number(2 * native.GetVoxelHalfY() / mm), number(2 * native.GetVoxelHalfZ() / mm),
            number(position.x() / mm), number(position.y() / mm), number(position.z() / mm),
            number((binding.worldCentre[0] - native.GetVoxelHalfX() * shape[0]) / mm),
            number((binding.worldCentre[1] - native.GetVoxelHalfY() * shape[1]) / mm),
            number((binding.worldCentre[2] - native.GetVoxelHalfZ() * shape[2]) / mm),
            number(volume / (mm * mm * mm)), geometry.GetVoxelGeometryPath(), geometry.GetVoxelGeometrySha(),
            descriptor.path, descriptor.sha256, labels.path, labels.sha256, std::to_string(grid.rois.size())};
        auto gridRow = common;
        gridRow.insert(gridRow.end(), {"grid", "", "", "", "", "", "", "", "", "", "", ""});
        writer.WriteRow(gridRow);
        for (const auto& [roi, indices] : grid.rois) {
            const auto& input = grid.inputs.at(grid.roiInputIndices.at(roi));
            auto declaration = common;
            declaration.insert(declaration.end(), {"roi", roi, input.path, input.sha256,
                std::to_string(indices.size()), "", "", "", "", "", "", ""});
            writer.WriteRow(declaration);
            for (const auto cell : indices) {
                const auto* material = native.GetMaterial(cell);
                const auto density = material->GetDensity();
                const auto mass = density * volume;
                if (!std::isfinite(mass) || mass <= 0) throw std::runtime_error("invalid voxel ROI member mass");
                auto row = common;
                row.insert(row.end(), {"member", roi, input.path, input.sha256, "", std::to_string(cell),
                    std::to_string(cell % shape[0]), std::to_string(cell / shape[0] % shape[1]),
                    std::to_string(cell / (shape[0] * shape[1])), material->GetName(),
                    number(density / (g / cm3)), number(mass / g)});
                writer.WriteRow(row);
            }
        }
    }
    if (TestOutputFault() == "voxel_roi_before_close") {
        throw std::runtime_error("Injected voxel ROI mass write failure before close");
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
    const bool ntupleOpen = std::any_of(ntupleWriters_.begin(), ntupleWriters_.end(), [](const auto& entry) {
        return entry.second.csv && entry.second.csv->IsOpen();
    });
    return ntupleOpen || IsHitFileOpen() || IsEventEdepFileOpen() ||
           (opticalPhotonCountsWriter_ && opticalPhotonCountsWriter_->IsOpen()) ||
           (opticalBoundaryStepsWriter_ && opticalBoundaryStepsWriter_->IsOpen()) ||
           (activationObservationsWriter_ && activationObservationsWriter_->IsOpen());
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

void OutputManager::ValidateOutputTargetDirectories(int runId, int threadCount,
                                                    bool opticalPhotonCounts,
                                                    bool opticalBoundaryObservations,
                                                    bool activationObservations, bool voxelScoring) const
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
        const auto validateCsv = [&](const char* name) {
            const std::filesystem::path path(candidate.MakeOutputPath(candidate.MakeThreadFilename(name)));
            error.clear();
            const bool exists = std::filesystem::exists(path, error);
            if (error) throw std::filesystem::filesystem_error("Cannot inspect output CSV target", path, error);
            if (exists && std::filesystem::is_directory(path, error)) {
                throw std::runtime_error("Output CSV target is an existing directory: " + path.string());
            }
            if (error) throw std::filesystem::filesystem_error("Cannot inspect output CSV target", path, error);
        };
        if (opticalPhotonCounts) validateCsv("optical_photon_counts.csv");
        if (opticalBoundaryObservations) validateCsv("optical_boundary_steps.csv");
        if (activationObservations) validateCsv("activation_observations.csv");
        if (voxelScoring) {
            validateCsv("voxel_edep.csv");
            const auto massName = runId > 0 ? "voxel_roi_mass_r" + std::to_string(runId) + ".csv"
                                            : "voxel_roi_mass.csv";
            const auto massPath = std::filesystem::u8path(MakeOutputPath(massName));
            const bool isDirectory = std::filesystem::is_directory(massPath, error);
            if (error && error != std::errc::no_such_file_or_directory)
                throw std::filesystem::filesystem_error("Cannot inspect voxel ROI mass target", massPath, error);
            if (isDirectory) throw std::runtime_error("Voxel ROI mass target is an existing directory: " + massPath.string());
            error.clear();
        }
        if (!WritesCsv()) continue;
        for (const char* name : {"hits.csv", "event_edep.csv", "hist_edep_raw.csv",
                                 "hist_edep_weighted.csv", "edep_volume_summary.csv",
                                 "edep_particle_summary.csv", "dose_volume_summary.csv",
                                 "fluence_volume_summary.csv", "let_volume_summary.csv",
                                 "displacement_volume_summary.csv"}) {
            validateCsv(name);
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
    if (hitVolumePathEnabled_ && record.doseVolumePath.empty())
        throw std::runtime_error("hit_volume_path: missing pre-step physical touchable path");
    if (WritesRoot()) AnalysisOutput::FillHit(record, threadId_);
    if (!WritesCsv()) return;
    if (!hitWriter_ || !hitWriter_->IsOpen()) {
        OpenHitFile();
    }

    // Match the published 12-significant-digit hit format. Keep stream
    // conversion when the caller selected a different locale or rounding mode.
    const bool useChars = std::locale() == std::locale::classic() &&
                          std::fegetround() == FE_TONEAREST;
    const auto number = [useChars](double value) {
        if (useChars) {
            char buffer[64];
            const auto result = std::to_chars(buffer, buffer + sizeof(buffer), value,
                                              std::chars_format::general, 12);
            if (result.ec == std::errc{}) return std::string(buffer, result.ptr);
        }
        return ToString(value);
    };

    std::vector<std::string> values = {
        std::to_string(record.runID),
        std::to_string(record.eventID),
        std::to_string(record.trackID),
        std::to_string(record.parentID),
        record.particleName,
        number(record.edep),
        number(record.ndep),
        number(record.stepLength),
        number(record.x0),
        number(record.y0),
        number(record.z0),
        number(record.x1),
        number(record.y1),
        number(record.z1),
        number(record.px),
        number(record.py),
        number(record.pz),
        number(record.kineticEnergy),
        record.processName,
        record.volumeName,
        number(record.weight)
    };
    if (hitVolumePathEnabled_) values.push_back(record.doseVolumePath);
    WriteHitRow(values);
}

void OutputManager::WriteOpticalPhotonCounts(const OpticalPhotonCountRecord& record)
{
    // This diagnostic is CSV even when the primary output format is ROOT.
    if (!opticalPhotonCountsWriter_ || !opticalPhotonCountsWriter_->IsOpen()) {
        auto writer = std::make_unique<CsvWriter>(
            MakeOutputPath(MakeThreadFilename("optical_photon_counts.csv")));
        writer->WriteHeader({"runID", "eventID", "scintillation_generated",
                             "cerenkov_generated", "other_optical_generated"});
        opticalPhotonCountsWriter_ = std::move(writer);
    }
    opticalPhotonCountsWriter_->WriteRow({
        std::to_string(record.runID), std::to_string(record.eventID),
        std::to_string(record.scintillation), std::to_string(record.cerenkov),
        std::to_string(record.other)
    });
}

void OutputManager::WriteVoxelEvent(int eventId, const std::map<std::pair<std::string, int>, VoxelEdepRecord>& cells)
{
    if (!WritesCsv() || runId_ < 0 || threadId_ < 0 || eventId < 0) {
        throw std::runtime_error("voxel event requires an active CSV worker output");
    }
    if (!voxelEdepWriter_) {
        auto writer = std::make_unique<CsvWriter>(MakeOutputPath(MakeThreadFilename("voxel_edep.csv")));
        writer->WriteHeader(StringUtils::Split(kVoxelEdepCsvHeader, ','));
        voxelEdepWriter_ = std::move(writer);
    }
    const auto number = [](double value) {
        std::ostringstream stream;
        stream.imbue(std::locale::classic());
        stream << std::setprecision(std::numeric_limits<double>::max_digits10) << value;
        return stream.str();
    };
    const auto execution = GetExecutionId();
    const auto run = std::to_string(runId_);
    const auto event = std::to_string(eventId);
    const auto worker = std::to_string(threadId_);
    for (const auto& [key, cell] : cells) {
        voxelEdepWriter_->WriteRow({execution, run, event, worker, "cell", key.first, std::to_string(key.second),
            std::to_string(cell.index[0]), std::to_string(cell.index[1]), std::to_string(cell.index[2]),
            cell.material, std::to_string(cell.steps), number(cell.rawEdep / MeV), number(cell.weightedEdep / MeV)});
    }
    // Fault control executes after rows were submitted but before the event closure.
    if (!cells.empty() && threadId_ == 0 && TestOutputFault() == "voxel_after_cells_t0") {
        throw std::runtime_error("Injected voxel write failure before event closure");
    }
    voxelEdepWriter_->WriteRow({execution, run, event, worker, "event_complete", "", "", "", "", "", "",
                               "", "", ""});
}

void OutputManager::FinishVoxelShard(int runId, const std::set<int>& events)
{
    if (runId < 0 || runId != runId_ || threadId_ < 0
        || (events.empty() == static_cast<bool>(voxelEdepWriter_))) {
        throw std::runtime_error("invalid voxel worker shard identity or writer coverage");
    }
    VoxelShard shard;
    shard.events.assign(events.begin(), events.end());
    if (voxelEdepWriter_) {
        voxelEdepWriter_->Close();
        shard.path = voxelEdepWriter_->GetFilename();
        voxelEdepWriter_.reset();
    }
    std::lock_guard<std::mutex> guard(generatedFiles_->mutex);
    if (!generatedFiles_->voxelShards[runId].emplace(threadId_, std::move(shard)).second) {
        throw std::runtime_error("duplicate voxel worker shard");
    }
}

void OutputManager::PublishVoxelRun(int runId, int expectedWorkers, int completedEvents)
{
    if (runId < 0 || runId != runId_ || expectedWorkers <= 0 || completedEvents < 0) {
        throw std::runtime_error("invalid master voxel run coverage identity");
    }
    std::map<int, VoxelShard> shards;
    {
        std::lock_guard<std::mutex> guard(generatedFiles_->mutex);
        const auto found = generatedFiles_->voxelShards.find(runId);
        if (found != generatedFiles_->voxelShards.end()) {
            shards = std::move(found->second);
            generatedFiles_->voxelShards.erase(found);
        }
    }
    if (shards.size() != static_cast<std::size_t>(expectedWorkers)) {
        throw std::runtime_error("voxel run is missing an actual worker completion receipt");
    }
    std::vector<bool> seen(completedEvents);
    std::size_t count = 0;
    std::string workerCounts;
    for (const auto& [worker, shard] : shards) {
        if (worker < 0 || worker >= expectedWorkers) throw std::runtime_error("voxel run has unexpected worker ID");
        for (int event : shard.events) {
            if (event < 0 || event >= completedEvents || seen[event]) {
                throw std::runtime_error("voxel run has duplicate or out-of-range event ID");
            }
            seen[event] = true;
            ++count;
        }
        if (!workerCounts.empty()) workerCounts += ',';
        workerCounts += std::to_string(worker) + ':' + std::to_string(shard.events.size());
    }
    if (count != seen.size()) throw std::runtime_error("voxel run has gaps in the completed event IDs");
    for (const auto& [worker, shard] : shards) {
        if (!shard.path.empty()) RegisterGeneratedFile(shard.path, ArtifactScope::Thread, runId, worker);
    }
    runSummary_.Set("voxel_worker_event_counts_r" + std::to_string(runId), workerCounts);
}

void OutputManager::WriteActivationObservations(const std::vector<ActivationObservationRecord>& records,
                                                int schemaVersion)
{
    if (records.empty()) return;
    if (!activationObservationsWriter_ || !activationObservationsWriter_->IsOpen()) {
        auto writer = std::make_unique<CsvWriter>(
            MakeOutputPath(MakeThreadFilename("activation_observations.csv")));
        std::string header = kActivationObservationCsvHeader;
        if (schemaVersion >= 2) header += kActivationObservationCsvV2Columns;
        if (schemaVersion >= 3) header += kActivationObservationCsvV3Columns;
        writer->WriteHeader(StringUtils::Split(header, ','));
        activationObservationsWriter_ = std::move(writer);
    }
    const auto number = [](double value) {
        std::ostringstream stream;
        stream.imbue(std::locale::classic());
        stream << std::setprecision(std::numeric_limits<double>::max_digits10) << value;
        return stream.str();
    };
    const auto optionalNumber = [&](const std::optional<double>& value) {
        return value ? number(*value) : std::string{};
    };
    const auto optionalInt = [](const std::optional<int>& value) {
        return value ? std::to_string(*value) : std::string{};
    };
    for (const auto& row : records) {
        std::vector<std::string> fields{
            std::to_string(row.runID), std::to_string(row.eventID),
            std::to_string(row.trackID), std::to_string(row.parentID), std::to_string(row.stepID),
            row.kind, row.process, row.particle, std::to_string(row.atomicNumber),
            std::to_string(row.massNumber), std::to_string(row.isomer), number(row.excitationKeV),
            number(row.timeSeconds), number(row.weight), number(row.positionMm[0]),
            number(row.positionMm[1]), number(row.positionMm[2]), std::to_string(row.originStepID),
            std::to_string(row.secondaryOrdinal)
        };
        if (schemaVersion >= 2) {
            fields.insert(fields.end(), {
                optionalInt(row.creatorModelID), row.creatorModelName, optionalNumber(row.properTimeSeconds),
                optionalNumber(row.preGlobalTimeSeconds), optionalNumber(row.preProperTimeSeconds),
                optionalNumber(row.preKineticEnergyKeV), optionalNumber(row.kineticEnergyKeV),
                row.postStepStatus, row.postTrackStatus, row.secondaryCreatorRelation,
                optionalInt(row.stepSecondaryCount), optionalInt(row.stepExcludedSecondaryCount)
            });
        }
        if (schemaVersion >= 3) {
            fields.insert(fields.end(), {
                row.endpointTransport, row.preMassTouchable, row.postMassTouchable, row.trackNextMassTouchable,
                row.postTouchableMatchesNext ? (*row.postTouchableMatchesNext ? "true" : "false") : "",
                optionalInt(row.generatedPrimaryNeutrons), optionalNumber(row.generatedPrimaryNeutronWeight),
                optionalInt(row.unknownPrimaryDefinitions), optionalInt(row.captureCreatorMatches),
                optionalNumber(row.capturePreWeight), row.captureTargetObservation, row.captureModel,
                optionalInt(row.captureTargetNucleusZ), optionalInt(row.captureTargetNucleusA),
                optionalInt(row.captureTargetIsotopeZ), optionalInt(row.captureTargetIsotopeA)
            });
        }
        activationObservationsWriter_->WriteRow(fields);
    }
}

void OutputManager::WriteOpticalBoundarySteps(const std::vector<OpticalBoundaryStepRecord>& records)
{
    if (records.empty()) return;
    if (!opticalBoundaryStepsWriter_ || !opticalBoundaryStepsWriter_->IsOpen()) {
        auto writer = std::make_unique<CsvWriter>(
            MakeOutputPath(MakeThreadFilename("optical_boundary_steps.csv")));
        writer->WriteHeader(StringUtils::Split(kOpticalBoundaryStepCsvHeader, ','));
        opticalBoundaryStepsWriter_ = std::move(writer);
    }
    const auto number = [](double value) {
        std::ostringstream stream;
        stream.imbue(std::locale::classic());
        stream << std::setprecision(std::numeric_limits<double>::max_digits10) << value;
        return stream.str();
    };
    for (const auto& record : records) {
        std::vector<std::string> row{
            std::to_string(record.runID), std::to_string(record.eventID),
            std::to_string(record.trackID), std::to_string(record.parentID),
            std::to_string(record.stepID), record.preVolumePath, record.postCandidateVolumePath,
            record.preMaterial, record.postCandidateMaterial
        };
        row.reserve(29);
        const auto append = [&](const std::array<double, 3>& vector) {
            for (double component : vector) row.push_back(number(component));
        };
        append(record.positionMm);
        row.push_back(number(record.stepLengthMm));
        row.push_back(number(record.preEnergyMeV));
        row.push_back(number(record.postEnergyMeV));
        append(record.preDirection);
        append(record.postDirection);
        append(record.prePolarization);
        append(record.postPolarization);
        row.push_back(std::to_string(record.nativeStatusCode));
        row.push_back(record.nativeStatus);
        opticalBoundaryStepsWriter_->WriteRow(row);
    }
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

std::string OutputManager::EventNtupleFilename(const NamedEventNtuple& definition, bool merged) const
{
    return MakeOutputPath("ntuple_" + definition.name + "_r" + std::to_string(runId_) +
                          (merged ? "" : "_t" + std::to_string(threadId_)) + ".csv");
}

OutputManager::EventNtupleWriter& OutputManager::OpenEventNtuple(const NamedEventNtuple& definition)
{
    auto& state = ntupleWriters_[definition.name];
    if (!state.csv) {
        state.csv = std::make_unique<CsvWriter>(EventNtupleFilename(definition, false));
        state.csv->WriteHeader(definition.Header());
    }
    return state;
}

void OutputManager::WriteEventNtuples(const std::vector<NamedEventNtuple>& definitions, const EventEdepRecord& event)
{
    if (event.runID != runId_ || event.eventID < 0 || threadId_ < 0)
        throw std::runtime_error("event ntuple has invalid event identity");
    const auto number = [](double value) {
        ScoringNumeric::Finite(value, "event ntuple energy");
        std::ostringstream output;
        output.imbue(std::locale::classic());
        output << std::setprecision(std::numeric_limits<double>::max_digits10) << value;
        return output.str();
    };
    const auto raw = number(event.rawEdep / MeV);
    const auto weighted = number(event.weightedEdep / MeV);
    for (const auto& definition : definitions) {
        auto& state = OpenEventNtuple(definition);
        if (state.rows == std::numeric_limits<int>::max() || state.lastEvent >= event.eventID) throw std::runtime_error("event ntuple unordered worker key");
        std::vector<std::string> row{std::to_string(runId_), std::to_string(event.eventID), std::to_string(threadId_)};
        for (const auto& column : definition.columns)
            row.push_back(column == "raw_edep_MeV" ? raw : weighted);
        state.csv->WriteRow(row);
        ++state.rows;
        state.lastEvent = event.eventID;
    }
}

void OutputManager::FinishEventNtuples(const std::vector<NamedEventNtuple>& definitions, int completed)
{
    for (const auto& definition : definitions) {
        auto& state = OpenEventNtuple(definition);  // An idle worker contributes its header and zero rows.
        if (state.rows != completed) throw std::runtime_error("event ntuple worker count mismatch");
        if (TestOutputFault() == "named_ntuple_worker_before_close")
            throw std::runtime_error("injected event ntuple worker close failure");
        const auto path = state.csv->GetFilename();
        state.csv->Close();
        const auto digest = input_provenance::HashFile(path);
        {
            std::lock_guard<std::mutex> lock(generatedFiles_->mutex);
            auto& workers = generatedFiles_->ntupleShards[runId_][definition.name];
            if (!workers.emplace(threadId_, EventNtupleShard{path, digest.sha256, completed}).second)
                throw std::runtime_error("duplicate event ntuple worker");
        }
        RegisterGeneratedFile(path, ArtifactScope::Thread, runId_, threadId_);
    }
    ntupleWriters_.clear();
}

void OutputManager::PublishEventNtuples(const std::vector<NamedEventNtuple>& definitions, int workers, int completed)
{
    std::map<std::string, std::map<int, EventNtupleShard>> all;
    {
        std::lock_guard<std::mutex> lock(generatedFiles_->mutex);
        const auto run = generatedFiles_->ntupleShards.find(runId_);
        if (run == generatedFiles_->ntupleShards.end()) throw std::runtime_error("missing event ntuple run");
        all.swap(run->second);
        generatedFiles_->ntupleShards.erase(run);
    }
    if (all.size() != definitions.size()) throw std::runtime_error("event ntuple declaration coverage mismatch");
    for (const auto& definition : definitions) {
        const auto& shards = all.at(definition.name);
        if (shards.size() != static_cast<std::size_t>(workers) || shards.begin()->first != 0 ||
            shards.rbegin()->first != workers - 1) throw std::runtime_error("event ntuple worker coverage mismatch");
        const auto path = EventNtupleFilename(definition, true);
        CsvWriter output(path);
        MergeEventNtuple(definition, shards, runId_, completed, output);
        if (TestOutputFault() == "named_ntuple_merge_before_close")
            throw std::runtime_error("injected event ntuple merge close failure");
        output.Close();
        RegisterGeneratedFile(path, ArtifactScope::Run, runId_);
    }
}

template<class Histogram>
void OutputManager::WriteNamedHistogram(const Histogram& hist, bool merged)
{
    const std::string worker = merged ? "" : std::to_string(threadId_);
    constexpr bool twoDimensional = std::is_same_v<Histogram, NamedHistogram2D>;
    const std::string kind = twoDimensional ? "h2" : "h1";
    const auto filename = MakeOutputPath(kind + "_" + hist.GetName() + "_r" + std::to_string(runId_) +
                                         (merged ? "" : "_t" + worker) + ".csv");
    CsvWriter writer(filename);
    writer.WriteHeader(StringUtils::Split(twoDimensional ? kNamedH2CsvHeader : kNamedH1CsvHeader, ','));
    const auto number = [](double v) {
        std::ostringstream s;
        s.imbue(std::locale::classic());
        s << std::setprecision(std::numeric_limits<double>::max_digits10) << v;
        return s.str();
    };
    if constexpr (twoDimensional) {
        const auto axisFields = [&](const EqualHistogramAxis& axis, int i) {
            const std::string index = i < 0 ? "underflow" : i == axis.bins ? "overflow" : std::to_string(i);
            return std::array<std::string, 3>{index, i < 0 ? "" : number(axis.Edge(i)),
                                             i == axis.bins ? "" : number(axis.Edge(i + 1))};
        };
        const auto entries = number(hist.GetEntries());
        for (int x = -1; x <= hist.X().bins; ++x) {
            const auto xFields = axisFields(hist.X(), x);
            for (int y = -1; y <= hist.Y().bins; ++y) {
                const auto yFields = axisFields(hist.Y(), y);
                writer.WriteRow({"1","event_edep_raw","event_edep_weighted","MeV","MeV",hist.GetName(),
                    std::to_string(runId_),worker,merged ? "run" : "thread",
                    xFields[0],xFields[1],xFields[2],yFields[0],yFields[1],yFields[2],
                    number(hist.Cell(x,y)),entries,entries});
            }
        }
    } else {
        const auto row = [&](const std::string& index, const std::string& low, const std::string& high, double count) {
            writer.WriteRow({"1",hist.GetName(),"event_edep_raw","MeV",std::to_string(runId_),worker,
                merged ? "run" : "thread",index,low,high,number(count),number(hist.GetEntries()),number(hist.GetSumWeight())});
        };
        std::string lower = number(hist.GetMin());
        row("underflow", "", lower, hist.GetUnderflow());
        for (int i = 0; i < hist.GetBins(); ++i) {
            const auto upper = number(hist.EqualBinEdge(i + 1));
            row(std::to_string(i), lower, upper, hist.GetBinContent(i));
            lower = upper;
        }
        row("overflow", lower, "", hist.GetOverflow());
    }
    if (TestOutputFault() == "named_" + kind + (merged ? "_merge_before_close" : "_worker_before_close"))
        throw std::runtime_error("injected named histogram close failure");
    writer.Close();
    if (merged) RegisterGeneratedFile(filename, ArtifactScope::Run, runId_);
    else RegisterGeneratedFile(filename, ArtifactScope::Thread, runId_, threadId_);
}

template<class Histogram>
void OutputManager::FinishNamedHistograms(const std::vector<Histogram>& histograms, int completedEvents)
{
    for (const auto& hist : histograms) {
        if (hist.GetEntries() != completedEvents) throw std::runtime_error("named histogram worker count mismatch");
        WriteNamedHistogram(hist, false);
    }
    std::lock_guard<std::mutex> lock(generatedFiles_->mutex);
    if (!generatedFiles_->Shards(histograms)[runId_].emplace(threadId_, histograms).second)
        throw std::runtime_error("duplicate named histogram worker");
}

template<class Histogram>
void OutputManager::PublishNamedHistograms(const std::vector<Histogram>& definitions, int workers, int completedEvents)
{
    std::map<int, std::vector<Histogram>> shards;
    {
        std::lock_guard<std::mutex> lock(generatedFiles_->mutex);
        auto& registry = generatedFiles_->Shards(definitions);
        auto it = registry.find(runId_);
        if (it == registry.end()) throw std::runtime_error("missing named histogram workers");
        shards.swap(it->second);
        registry.erase(it);
    }
    if (shards.size() != static_cast<std::size_t>(workers)) throw std::runtime_error("named histogram worker coverage mismatch");
    auto merged = definitions;
    for (auto& histogram : merged) histogram.Reset();
    for (const auto& shard : shards) {
        if (shard.second.size() != merged.size()) throw std::runtime_error("named histogram declaration mismatch");
        for (std::size_t i = 0; i < merged.size(); ++i) merged[i].Merge(shard.second[i]);
    }
    for (const auto& hist : merged) {
        if (hist.GetEntries() != completedEvents) throw std::runtime_error("named histogram merged count mismatch");
        WriteNamedHistogram(hist, true);
    }
}

template void OutputManager::FinishNamedHistograms(const std::vector<Histogram1D>&, int);
template void OutputManager::PublishNamedHistograms(const std::vector<Histogram1D>&, int, int);
template void OutputManager::FinishNamedHistograms(const std::vector<NamedHistogram2D>&, int);
template void OutputManager::PublishNamedHistograms(const std::vector<NamedHistogram2D>&, int, int);

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

void OutputManager::WriteNativeClockEvent(int runId,int eventId,const std::string& bytes)
{
    WriteEventArtifact(runId,eventId,bytes,"native_at_rest_e");
}
#ifdef G4USIM_H6_ENGINEERING
void OutputManager::WriteEngineeringWaterEvent(int runId,int eventId,const std::string& bytes)
{
    WriteEventArtifact(runId,eventId,bytes,"water_collision_e");
}
#endif
void OutputManager::WriteEventArtifact(int runId, int eventId, const std::string& bytes,const std::string& prefix)
{
    if (runId < 0 || runId != runId_ || eventId < 0 || bytes.empty()) {
        throw std::invalid_argument("Invalid native clock output identity");
    }
    const auto name = MakeOutputPath(MakeThreadFilename(
        prefix + std::to_string(eventId) + ".json"));
    const auto target = std::filesystem::u8path(name);
    auto temporary = target;
    temporary += ".tmp-" + GetExecutionId();
#ifdef _WIN32
    std::FILE* stream = _wfopen(temporary.c_str(), L"wbx");
#else
    std::FILE* stream = std::fopen(temporary.c_str(), "wbx");
#endif
    if (!stream) {
        throw std::runtime_error("Cannot create native clock temporary file: " + name);
    }
    try {
        const auto fault = TestOutputFault();
        const auto size = fault == "native_clock_short_write" ? bytes.size() / 2 : bytes.size();
        if (std::fwrite(bytes.data(), 1, size, stream) != bytes.size() || std::fflush(stream) != 0) {
            throw std::runtime_error("Cannot write native clock event: " + name);
        }
        const int closed = std::fclose(stream);
        stream = nullptr;
        if (closed != 0 || fault == "native_clock_close") {
            throw std::runtime_error("Cannot close native clock event: " + name);
        }
        // Publish without replacing an older event file, even if another process
        // creates it between staging and publication.
#ifdef _WIN32
        if (!MoveFileExW(temporary.c_str(), target.c_str(), MOVEFILE_WRITE_THROUGH)) {
            throw std::runtime_error("Cannot publish native clock event: " + name);
        }
#else
        std::filesystem::create_hard_link(temporary, target);
        std::filesystem::remove(temporary);
#endif
        RegisterGeneratedFile(name);
    } catch (...) {
        if (stream) std::fclose(stream);
        std::error_code ignored;
        std::filesystem::remove(temporary, ignored);
        throw;
    }
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
    FinalizeArtifactEvidence(evidence);
    return evidence;
}

std::vector<OutputManager::ArtifactEvidence> OutputManager::CollectRunArtifacts(int runId, bool includeMetadataSelf)
{
    std::vector<ArtifactEvidence> evidence;
    {
        std::lock_guard<std::mutex> guard(generatedFiles_->mutex);
        for (const auto& file : generatedFiles_->files) {
            if (file.scope == ArtifactScope::Process) continue;
            if (!file.run_id.has_value() || *file.run_id != runId) continue;
            evidence.push_back(file);
        }
    }
    const auto metadata = FileUtils::AbsolutePath(MakeOutputPath("run_metadata.json"));
    if (includeMetadataSelf && std::none_of(evidence.begin(), evidence.end(),
            [&](const ArtifactEvidence& file) { return file.path == metadata; })) {
        ArtifactEvidence self; self.path = metadata; self.execution_id = GetExecutionId();
        evidence.push_back(std::move(self));
    }
    FinalizeArtifactEvidence(evidence);
    return evidence;
}

void OutputManager::FinalizeArtifactEvidence(std::vector<ArtifactEvidence>& evidence)
{
    const auto metadata = FileUtils::AbsolutePath(MakeOutputPath("run_metadata.json"));
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

void OutputManager::RecordStartupFailure(const std::string& stage, const std::string& message)
{
    std::lock_guard<std::mutex> guard(generatedFiles_->mutex);
    if (!generatedFiles_->hasFailure) {
        generatedFiles_->firstFailure = {-1, threadId_, stage, message};
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
    flushWriter(opticalPhotonCountsWriter_);
    flushWriter(opticalBoundaryStepsWriter_);
    flushWriter(activationObservationsWriter_);
    flushWriter(voxelEdepWriter_);
    for (const auto& entry : ntupleWriters_) flushWriter(entry.second.csv);
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
    closeWriter(opticalPhotonCountsWriter_);
    closeWriter(opticalBoundaryStepsWriter_);
    closeWriter(activationObservationsWriter_);
    for (const auto& entry : ntupleWriters_) {
        // Only FinishEventNtuples can register a complete worker shard.
        try {
            if (entry.second.csv && entry.second.csv->IsOpen()) entry.second.csv->Close();
        } catch (...) {
            if (!firstError) firstError = std::current_exception();
        }
    }
    if (voxelEdepWriter_ && voxelEdepWriter_->IsOpen()) {
        try {
            // An unsubmitted stream may be from a failed worker. No publication here.
            voxelEdepWriter_->Close();
        } catch (...) {
            if (!firstError) firstError = std::current_exception();
        }
    }
    if (firstError) std::rethrow_exception(firstError);
}

std::vector<std::string> OutputManager::HitHeader() const
{
    std::vector<std::string> columns = {
        "runID", "eventID", "trackID", "parentID", "particle", "edep_MeV", "ndep_MeV", "stepLength_mm",
        "x0_mm", "y0_mm", "z0_mm", "x1_mm", "y1_mm", "z1_mm", "px", "py", "pz", "kineticEnergy_MeV",
        "process", "volume", "weight"
    };
    if (hitVolumePathEnabled_) columns.emplace_back("volume_path");
    return columns;
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
