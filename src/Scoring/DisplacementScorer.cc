#include "Scoring/DisplacementScorer.hh"
#include "Scoring/NumericChecks.hh"

#include "Output/CsvWriter.hh"
#include "Output/OutputManager.hh"
#include "G4SystemOfUnits.hh"

#include <cmath>
#include <iomanip>
#include <sstream>
#include <stdexcept>

namespace {
std::string Number(double value)
{
    std::ostringstream stream;
    stream << std::setprecision(12) << value;
    return stream.str();
}

constexpr double kMm2PerCm2 = 100.0;
}

DisplacementScorer::DisplacementScorer(const std::string& name)
    : ScorerBase(name)
{
}

DisplacementScorer::~DisplacementScorer() = default;

void DisplacementScorer::SetTables(const TableMap& tables)
{
    tables_ = tables;
}

void DisplacementScorer::BeginRun(int runID)
{
    runID_ = runID;
    events_ = 0;
    touched_.Clear();
    volumes_.clear();
}

void DisplacementScorer::EndEvent(int)
{
    ++events_;
    touched_.EndEvent();
}

void DisplacementScorer::ScoreHit(const HitRecord& hit)
{
    const auto table = tables_.find(hit.particleName);
    if (table == tables_.end()) return;
    if (!std::isfinite(hit.stepLength) || !std::isfinite(hit.weight) || hit.stepLength < 0.0 ||
        !std::isfinite(hit.meanKineticEnergy)) {
        throw std::runtime_error("DisplacementScorer rejects nonfinite/negative step length, weight or energy");
    }
    if (hit.stepLength == 0.0) return;
    if (hit.doseVolumePath.empty() || !std::isfinite(hit.fluenceVolume) || hit.fluenceVolume <= 0.0) {
        throw std::runtime_error("DisplacementScorer requires a positive daughter-free sensitive solid volume and "
                                 "touchable path for " + hit.volumeName);
    }
    auto& volume = volumes_[hit.doseVolumePath];
    if (volume.volume == 0.0) {
        volume.name = hit.volumeName;
        volume.volume = hit.fluenceVolume;
    } else if (std::abs(volume.volume - hit.fluenceVolume) > 1e-9 * volume.volume) {
        throw std::runtime_error("DisplacementScorer detected changing volume for touchable " + hit.doseVolumePath);
    }
    auto& particle = volume.particles[hit.particleName];
    const double lengthMm = ScoringNumeric::Multiply(hit.weight, hit.stepLength / mm, "DDD weighted length");
    double niel = 0.0;
    if (!table->second->Evaluate(hit.meanKineticEnergy, niel)) {
        particle.outOfRangeLength = ScoringNumeric::Add(particle.outOfRangeLength, lengthMm, "DDD out-of-range length");
        return;
    }
    particle.trackLength = ScoringNumeric::Add(particle.trackLength, lengthMm, "DDD track length");
    const double ddd = lengthMm * niel * kMm2PerCm2 / (volume.volume / (mm * mm * mm));
    if (!std::isfinite(ddd)) throw std::runtime_error("DisplacementScorer accumulated nonfinite DDD");
    if (ddd > 0.0) {
        touched_.Add(particle.ddd, ddd);
        touched_.Add(volume.total, ddd);
    }
}

void DisplacementScorer::Write(OutputManager& output)
{
    for (const auto& item : volumes_) {
        const auto& v = item.second;
        HistoryStatistics::Entry total;
        total.name = v.name;
        total.unit = "MeV/g";
        total.sum = v.total.sum;
        total.sumSq = v.total.sumSq;
        total.entries = v.total.entries;
        HistoryStatistics::Submit(runID_, "displacement", "ddd_total", item.first, total);
        for (const auto& p : v.particles) {
            HistoryStatistics::Entry entry = total;
            entry.sum = p.second.ddd.sum;
            entry.sumSq = p.second.ddd.sumSq;
            entry.entries = p.second.ddd.entries;
            HistoryStatistics::Submit(runID_, "displacement", "ddd_" + p.first, item.first, entry);
        }
    }
    if (!output.WritesCsv()) return;
    CsvWriter writer(output.MakeOutputPath(output.MakeThreadFilename("displacement_volume_summary.csv")));
    writer.WriteHeader({"runID", "volume_path", "volume_name", "particle", "niel_table", "volume_mm3",
                        "track_length_mm", "out_of_range_track_length_mm", "ddd_MeV_g", "ddd_sum_sq_MeV2_g2",
                        "n_events"});
    for (const auto& item : volumes_) {
        const auto& v = item.second;
        for (const auto& p : v.particles) {
            writer.WriteRow({std::to_string(runID_), item.first, v.name, p.first, tables_.at(p.first)->GetFile(),
                             Number(v.volume / (mm * mm * mm)), Number(p.second.trackLength),
                             Number(p.second.outOfRangeLength), Number(p.second.ddd.sum),
                             Number(p.second.ddd.sumSq), std::to_string(events_)});
        }
    }
    writer.Close();
    output.RegisterGeneratedFile(writer.GetFilename());
}

void DisplacementScorer::Reset()
{
    runID_ = -1;
    events_ = 0;
    touched_.Clear();
    volumes_.clear();
}
