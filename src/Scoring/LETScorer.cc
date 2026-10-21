#include "Scoring/LETScorer.hh"

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

std::string JoinParticles(const std::set<std::string>& particles)
{
    if (particles.empty()) return "all_charged";
    std::string text;
    for (const auto& name : particles) text += (text.empty() ? "" : " ") + name;
    return text;
}
}  // namespace

LETScorer::LETScorer(const std::string& name)
    : ScorerBase(name)
{
}

LETScorer::~LETScorer() = default;

void LETScorer::BeginRun(int runID)
{
    runID_ = runID;
    volumes_.clear();
}

void LETScorer::ScoreHit(const HitRecord& hit)
{
    // LETstep <= 0 marks neutral particles or steps without a stopping power.
    if (!(hit.LETstep > 0.0) || !(hit.stepLength > 0.0)) return;
    if (!particles_.empty() && particles_.count(hit.particleName) == 0) return;
    if (hit.doseVolumePath.empty()) {
        throw std::runtime_error("LETScorer requires a sensitive touchable path for " + hit.volumeName);
    }
    if (!std::isfinite(hit.LETstep) || !std::isfinite(hit.stepLength) || !std::isfinite(hit.weight)) {
        throw std::runtime_error("LETScorer rejects nonfinite stopping power, step length or weight");
    }
    const double s = hit.LETstep / (MeV / mm);
    const double l = hit.stepLength / mm;
    auto& volume = volumes_[hit.doseVolumePath];
    if (volume.name.empty()) volume.name = hit.volumeName;
    ++volume.steps;
    volume.sumWL += hit.weight * l;
    volume.sumWSL += hit.weight * s * l;
    volume.sumWS2L += hit.weight * s * s * l;
}

void LETScorer::Write(OutputManager& output)
{
    const std::string particles = JoinParticles(particles_);
    struct Row {
        const std::string* path;
        const VolumeLET* v;
        double letT;
        double letD;
    };
    std::vector<Row> rows;
    for (const auto& item : volumes_) {
        const auto& v = item.second;
        const double letT = v.sumWL > 0.0 ? v.sumWSL / v.sumWL : 0.0;
        const double letD = v.sumWSL > 0.0 ? v.sumWS2L / v.sumWSL : 0.0;
        if (!std::isfinite(letT) || !std::isfinite(letD)) {
            throw std::runtime_error("LETScorer refuses nonfinite output for touchable " + item.first);
        }
        rows.push_back({&item.first, &v, letT, letD});
    }
    if (output.WritesRoot()) {
        for (const Row& r : rows) {
            AnalysisOutput::FillLET(runID_, output.GetThreadId(), *r.path, r.v->name, particles, r.v->steps,
                                    r.v->sumWL, r.v->sumWSL, r.v->sumWS2L, r.letT, r.letD);
        }
    }
    if (!output.WritesCsv()) return;
    CsvWriter writer(output.MakeOutputPath(output.MakeThreadFilename("let_volume_summary.csv")));
    writer.WriteHeader({"runID", "volume_path", "volume_name", "particles", "steps", "sum_wl_mm",
                        "sum_wSl_MeV", "sum_wS2l_MeV2_per_mm", "let_t_keV_per_um", "let_d_keV_per_um"});
    for (const Row& r : rows) {
        writer.WriteRow({std::to_string(runID_), *r.path, r.v->name, particles, std::to_string(r.v->steps),
                         Number(r.v->sumWL), Number(r.v->sumWSL), Number(r.v->sumWS2L),
                         Number(r.letT), Number(r.letD)});
    }
    writer.Close();
    output.RegisterGeneratedFile(writer.GetFilename());
}

void LETScorer::Reset()
{
    runID_ = -1;
    volumes_.clear();
}

void LETScorer::SetParticles(const std::set<std::string>& particles)
{
    particles_ = particles;
}

const std::set<std::string>& LETScorer::GetParticles() const
{
    return particles_;
}
