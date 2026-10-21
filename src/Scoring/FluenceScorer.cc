#include "Scoring/FluenceScorer.hh"

#include "Output/AnalysisOutput.hh"
#include "Output/CsvWriter.hh"
#include "Output/OutputManager.hh"
#include "G4SystemOfUnits.hh"

#include <cmath>
#include <iomanip>
#include <sstream>
#include <stdexcept>
#include <vector>

namespace {
std::string Number(double value)
{
    std::ostringstream stream;
    stream << std::setprecision(12) << value;
    return stream.str();
}
}

FluenceScorer::FluenceScorer(const std::string& name)
    : ScorerBase(name)
{
}

FluenceScorer::~FluenceScorer() = default;

void FluenceScorer::BeginRun(int runID)
{
    runID_ = runID;
    events_ = 0;
    touched_.Clear();
    volumes_.clear();
}

void FluenceScorer::EndEvent(int)
{
    ++events_;
    touched_.EndEvent();
}

void FluenceScorer::ScoreHit(const HitRecord& hit)
{
    if (!std::isfinite(hit.stepLength) || !std::isfinite(hit.weight) || hit.stepLength < 0.0) {
        throw std::runtime_error("FluenceScorer rejects nonfinite/negative step length or nonfinite weight");
    }
    if (hit.stepLength == 0.0) return;
    if (hit.doseVolumePath.empty() || !std::isfinite(hit.fluenceVolume) || hit.fluenceVolume <= 0.0) {
        throw std::runtime_error("FluenceScorer requires a positive daughter-free sensitive solid volume and touchable path for " + hit.volumeName);
    }
    auto& volume = volumes_[hit.doseVolumePath];
    if (volume.volume == 0.0) {
        volume.name = hit.volumeName;
        volume.volume = hit.fluenceVolume;
    } else if (std::abs(volume.volume - hit.fluenceVolume) > 1e-9 * volume.volume) {
        throw std::runtime_error("FluenceScorer detected changing volume for touchable " + hit.doseVolumePath);
    }
    const double weightedStep = hit.stepLength * hit.weight;
    if (!std::isfinite(volume.rawLength.event + hit.stepLength) ||
        !std::isfinite(volume.weightedLength.event + weightedStep)) {
        throw std::runtime_error("FluenceScorer accumulated nonfinite track length");
    }
    touched_.Add(volume.rawLength, hit.stepLength);
    touched_.Add(volume.weightedLength, weightedStep);
}

void FluenceScorer::Write(OutputManager& output)
{
    struct Row {
        const std::string* path;
        const std::string* name;
        double volumeMm3, rawLengthMm, weightedLengthMm, rawFluence, weightedFluence;
        double rawLengthSumSqMm2, weightedLengthSumSqMm2;
    };
    std::vector<Row> rows;
    for (const auto& item : volumes_) {
        const auto& v = item.second;
        const double volumeMm3 = v.volume / (mm * mm * mm);
        const double rawLengthMm = v.rawLength.sum / mm;
        const double weightedLengthMm = v.weightedLength.sum / mm;
        const double rawFluence = rawLengthMm / volumeMm3;
        const double weightedFluence = weightedLengthMm / volumeMm3;
        const double rawSumSq = v.rawLength.sumSq / (mm * mm);
        const double weightedSumSq = v.weightedLength.sumSq / (mm * mm);
        if (!std::isfinite(volumeMm3) || volumeMm3 <= 0.0 ||
            !std::isfinite(rawLengthMm) || !std::isfinite(weightedLengthMm) ||
            !std::isfinite(rawFluence) || !std::isfinite(weightedFluence) ||
            !std::isfinite(rawSumSq) || !std::isfinite(weightedSumSq)) {
            throw std::runtime_error("FluenceScorer refuses nonfinite/invalid output for touchable " + item.first);
        }
        rows.push_back({&item.first, &v.name, volumeMm3, rawLengthMm, weightedLengthMm, rawFluence, weightedFluence,
                        rawSumSq, weightedSumSq});
    }
    for (const Row& r : rows) {
        const auto& v = volumes_.at(*r.path);
        const double inverseVolume = 1.0 / r.volumeMm3;
        for (const bool weighted : {false, true}) {
            HistoryStatistics::Entry entry;
            entry.name = *r.name;
            entry.unit = "mm-2";
            entry.sum = (weighted ? r.weightedLengthMm : r.rawLengthMm) * inverseVolume;
            entry.sumSq = (weighted ? r.weightedLengthSumSqMm2 : r.rawLengthSumSqMm2) * inverseVolume * inverseVolume;
            entry.entries = weighted ? v.weightedLength.entries : v.rawLength.entries;
            HistoryStatistics::Submit(runID_, "fluence", weighted ? "weighted_fluence" : "raw_fluence", *r.path, entry);
        }
    }
    if (output.WritesRoot()) {
        for (const Row& r : rows) {
            AnalysisOutput::FillFluence(runID_, output.GetThreadId(), *r.path, *r.name, r.volumeMm3,
                                        r.rawLengthMm, r.weightedLengthMm, r.rawFluence, r.weightedFluence,
                                        r.rawLengthSumSqMm2, r.weightedLengthSumSqMm2, events_);
        }
    }
    if (!output.WritesCsv()) return;
    CsvWriter writer(output.MakeOutputPath(output.MakeThreadFilename("fluence_volume_summary.csv")));
    writer.WriteHeader({"runID", "volume_path", "volume_name", "volume_mm3", "raw_track_length_mm",
                        "weighted_track_length_mm", "raw_fluence_mm-2", "weighted_fluence_mm-2",
                        "raw_track_length_sum_sq_mm2", "weighted_track_length_sum_sq_mm2", "n_events"});
    for (const Row& r : rows) {
        writer.WriteRow({std::to_string(runID_), *r.path, *r.name, Number(r.volumeMm3),
                         Number(r.rawLengthMm), Number(r.weightedLengthMm),
                         Number(r.rawFluence), Number(r.weightedFluence),
                         Number(r.rawLengthSumSqMm2), Number(r.weightedLengthSumSqMm2),
                         std::to_string(events_)});
    }
    writer.Close();
    output.RegisterGeneratedFile(writer.GetFilename());
}

void FluenceScorer::Reset()
{
    runID_ = -1;
    events_ = 0;
    touched_.Clear();
    volumes_.clear();
}
