#include "Scoring/DoseScorer.hh"

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
    volumes_.clear();
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
    volume.rawEdep += hit.edep;
    volume.weightedEdep += hit.edep * hit.weight;
    if (!std::isfinite(volume.rawEdep) || !std::isfinite(volume.weightedEdep)) {
        throw std::runtime_error("DoseScorer accumulated nonfinite energy deposition");
    }
}

void DoseScorer::Write(OutputManager& output)
{
    CsvWriter writer(output.MakeOutputPath(output.MakeThreadFilename("dose_volume_summary.csv")));
    writer.WriteHeader({"runID", "volume_path", "volume_name", "mass_kg", "raw_edep_MeV",
                        "weighted_edep_MeV", "raw_dose_Gy", "weighted_dose_Gy"});
    for (const auto& item : volumes_) {
        const auto& v = item.second;
        const double massKg = v.mass / kg;
        writer.WriteRow({std::to_string(runID_), item.first, v.name, Number(massKg),
                         Number(v.rawEdep / MeV), Number(v.weightedEdep / MeV),
                         Number((v.rawEdep / joule) / massKg),
                         Number((v.weightedEdep / joule) / massKg)});
    }
    writer.Close();
    output.RegisterGeneratedFile(writer.GetFilename());
}

void DoseScorer::Reset()
{
    runID_ = -1;
    volumes_.clear();
}
