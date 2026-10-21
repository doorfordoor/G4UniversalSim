#include "Scoring/DoseScorer.hh"

#include "Output/AnalysisOutput.hh"
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
}

DoseScorer::DoseScorer(const std::string& name)
    : ScorerBase(name)
{
}

DoseScorer::~DoseScorer() = default;

void DoseScorer::BeginRun(int runID)
{
    runID_ = runID;
    events_ = 0;
    touched_.Clear();
    volumes_.clear();
}

void DoseScorer::EndEvent(int)
{
    ++events_;
    touched_.EndEvent();
}

void DoseScorer::ScoreHit(const HitRecord& hit)
{
    if (hit.edep == 0.0) return;
    if (hit.doseVolumePath.empty() || !std::isfinite(hit.doseMass) || hit.doseMass <= 0.0) {
        throw std::runtime_error("DoseScorer requires a positive Geant4 physical-volume mass and touchable path for " + hit.volumeName);
    }
    if (!std::isfinite(hit.edep) || !std::isfinite(hit.weight)) {
        throw std::runtime_error("DoseScorer rejects nonfinite energy deposition or track weight");
    }
    auto& volume = volumes_[hit.doseVolumePath];
    if (volume.mass == 0.0) {
        volume.mass = hit.doseMass;
        volume.name = hit.volumeName;
    } else if (std::abs(volume.mass - hit.doseMass) > 1e-9 * volume.mass) {
        throw std::runtime_error("DoseScorer detected changing mass for touchable " + hit.doseVolumePath);
    }
    touched_.Add(volume.rawEdep, hit.edep);
    touched_.Add(volume.weightedEdep, hit.edep * hit.weight);
    if (!std::isfinite(volume.rawEdep.event) || !std::isfinite(volume.weightedEdep.event)) {
        throw std::runtime_error("DoseScorer accumulated nonfinite energy deposition");
    }
}

void DoseScorer::Write(OutputManager& output)
{
    const double mev2 = MeV * MeV;
    for (const auto& item : volumes_) {
        const auto& v = item.second;
        // Dose per event = edep / mass with a fixed mass, so sums scale exactly.
        const double gyPerEdep = 1.0 / joule / (v.mass / kg);
        for (const auto* tally : {&v.rawEdep, &v.weightedEdep}) {
            HistoryStatistics::Entry entry;
            entry.name = v.name;
            entry.unit = "Gy";
            entry.sum = tally->sum * gyPerEdep;
            entry.sumSq = tally->sumSq * gyPerEdep * gyPerEdep;
            entry.entries = tally->entries;
            HistoryStatistics::Submit(runID_, "dose", tally == &v.rawEdep ? "raw_dose" : "weighted_dose",
                                      item.first, entry);
        }
    }
    if (output.WritesRoot()) {
        for (const auto& item : volumes_) {
            const auto& v = item.second;
            const double massKg = v.mass / kg;
            AnalysisOutput::FillDose(runID_, output.GetThreadId(), item.first, v.name, massKg,
                                     v.rawEdep.sum / MeV, v.weightedEdep.sum / MeV,
                                     (v.rawEdep.sum / joule) / massKg, (v.weightedEdep.sum / joule) / massKg,
                                     v.rawEdep.sumSq / mev2, v.weightedEdep.sumSq / mev2, events_);
        }
    }
    if (!output.WritesCsv()) return;
    CsvWriter writer(output.MakeOutputPath(output.MakeThreadFilename("dose_volume_summary.csv")));
    writer.WriteHeader({"runID", "volume_path", "volume_name", "mass_kg", "raw_edep_MeV",
                        "weighted_edep_MeV", "raw_dose_Gy", "weighted_dose_Gy",
                        "raw_edep_sum_sq_MeV2", "weighted_edep_sum_sq_MeV2", "n_events"});
    for (const auto& item : volumes_) {
        const auto& v = item.second;
        const double massKg = v.mass / kg;
        writer.WriteRow({std::to_string(runID_), item.first, v.name, Number(massKg),
                         Number(v.rawEdep.sum / MeV), Number(v.weightedEdep.sum / MeV),
                         Number((v.rawEdep.sum / joule) / massKg),
                         Number((v.weightedEdep.sum / joule) / massKg),
                         Number(v.rawEdep.sumSq / mev2), Number(v.weightedEdep.sumSq / mev2),
                         std::to_string(events_)});
    }
    writer.Close();
    output.RegisterGeneratedFile(writer.GetFilename());
}

void DoseScorer::Reset()
{
    runID_ = -1;
    events_ = 0;
    touched_.Clear();
    volumes_.clear();
}
