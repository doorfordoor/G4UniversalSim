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
    volumes_.clear();
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
    const double rawLength = volume.rawLength + hit.stepLength;
    const double weightedLength = volume.weightedLength + hit.stepLength * hit.weight;
    if (!std::isfinite(rawLength) || !std::isfinite(weightedLength)) {
        throw std::runtime_error("FluenceScorer accumulated nonfinite track length");
    }
    volume.rawLength = rawLength;
    volume.weightedLength = weightedLength;
}

void FluenceScorer::Write(OutputManager& output)
{
    struct Row {
        const std::string* path;
        const std::string* name;
        double volumeMm3, rawLengthMm, weightedLengthMm, rawFluence, weightedFluence;
    };
    std::vector<Row> rows;
    for (const auto& item : volumes_) {
        const auto& v = item.second;
        const double volumeMm3 = v.volume / (mm * mm * mm);
        const double rawLengthMm = v.rawLength / mm;
        const double weightedLengthMm = v.weightedLength / mm;
        const double rawFluence = rawLengthMm / volumeMm3;
        const double weightedFluence = weightedLengthMm / volumeMm3;
        if (!std::isfinite(volumeMm3) || volumeMm3 <= 0.0 ||
            !std::isfinite(rawLengthMm) || !std::isfinite(weightedLengthMm) ||
            !std::isfinite(rawFluence) || !std::isfinite(weightedFluence)) {
            throw std::runtime_error("FluenceScorer refuses nonfinite/invalid output for touchable " + item.first);
        }
        rows.push_back({&item.first, &v.name, volumeMm3, rawLengthMm, weightedLengthMm, rawFluence, weightedFluence});
    }
    if (output.WritesRoot()) {
        for (const Row& r : rows) {
            AnalysisOutput::FillFluence(runID_, output.GetThreadId(), *r.path, *r.name, r.volumeMm3,
                                        r.rawLengthMm, r.weightedLengthMm, r.rawFluence, r.weightedFluence);
        }
    }
    if (!output.WritesCsv()) return;
    CsvWriter writer(output.MakeOutputPath(output.MakeThreadFilename("fluence_volume_summary.csv")));
    writer.WriteHeader({"runID", "volume_path", "volume_name", "volume_mm3", "raw_track_length_mm",
                        "weighted_track_length_mm", "raw_fluence_mm-2", "weighted_fluence_mm-2"});
    for (const auto& item : volumes_) {
        const auto& v = item.second;
        const double volumeMm3 = v.volume / (mm * mm * mm);
        const double rawLengthMm = v.rawLength / mm;
        const double weightedLengthMm = v.weightedLength / mm;
        const double rawFluence = rawLengthMm / volumeMm3;
        const double weightedFluence = weightedLengthMm / volumeMm3;
        if (!std::isfinite(volumeMm3) || volumeMm3 <= 0.0 ||
            !std::isfinite(rawLengthMm) || !std::isfinite(weightedLengthMm) ||
            !std::isfinite(rawFluence) || !std::isfinite(weightedFluence)) {
            throw std::runtime_error("FluenceScorer refuses nonfinite/invalid output for touchable " + item.first);
        }
        writer.WriteRow({std::to_string(runID_), item.first, v.name, Number(volumeMm3),
                         Number(rawLengthMm), Number(weightedLengthMm),
                         Number(rawFluence), Number(weightedFluence)});
    }
    writer.Close();
    output.RegisterGeneratedFile(writer.GetFilename());
}

void FluenceScorer::Reset()
{
    runID_ = -1;
    volumes_.clear();
}
