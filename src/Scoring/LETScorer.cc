#include "Scoring/LETScorer.hh"
#include "Scoring/NumericChecks.hh"

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
    events_ = 0;
    touched_.clear();
    volumes_.clear();
}

void LETScorer::EndEvent(int)
{
    ++events_;
    for (VolumeLET* v : touched_) {
        VolumeLET next = *v;
        next.sumWL = ScoringNumeric::Add(v->sumWL, v->eventWL, "LET WL sum");
        next.sumWSL = ScoringNumeric::Add(v->sumWSL, v->eventWSL, "LET WSL sum");
        next.sumWS2L = ScoringNumeric::Add(v->sumWS2L, v->eventWS2L, "LET WS2L sum");
        const auto moment = [](double sum, double a, double b) {
            return ScoringNumeric::Add(sum, ScoringNumeric::Multiply(a, b, "LET event moment"), "LET moment sum");
        };
        next.sumSqWL = moment(v->sumSqWL, v->eventWL, v->eventWL);
        next.sumSqWSL = moment(v->sumSqWSL, v->eventWSL, v->eventWSL);
        next.sumSqWS2L = moment(v->sumSqWS2L, v->eventWS2L, v->eventWS2L);
        next.sumWLxWSL = moment(v->sumWLxWSL, v->eventWL, v->eventWSL);
        next.sumWSLxWS2L = moment(v->sumWSLxWS2L, v->eventWSL, v->eventWS2L);
        next.entries = ScoringNumeric::AddCount(v->entries, 1, "LET entries");
        next.eventWL = next.eventWSL = next.eventWS2L = 0.0;
        next.pending = false;
        *v = std::move(next);
    }
    touched_.clear();
}

void LETScorer::ScoreHit(const HitRecord& hit)
{
    // LETstep <= 0 marks neutral particles or steps without a stopping power.
    if (!ScoringNumeric::PositiveLETStep(hit.LETstep, hit.stepLength, hit.weight)) return;
    if (!particles_.empty() && particles_.count(hit.particleName) == 0) return;
    if (hit.doseVolumePath.empty()) {
        throw std::runtime_error("LETScorer requires a sensitive touchable path for " + hit.volumeName);
    }
    const double s = hit.LETstep / (MeV / mm);
    const double l = hit.stepLength / mm;
    auto& volume = volumes_[hit.doseVolumePath];
    const double wl = ScoringNumeric::Multiply(hit.weight, l, "LET weighted length");
    const double wsl = ScoringNumeric::Multiply(wl, s, "LET weighted stopping power");
    const double ws2l = ScoringNumeric::Multiply(wsl, s, "LET weighted squared stopping power");
    const double nextWL = ScoringNumeric::Add(volume.eventWL, wl, "LET event WL");
    const double nextWSL = ScoringNumeric::Add(volume.eventWSL, wsl, "LET event WSL");
    const double nextWS2L = ScoringNumeric::Add(volume.eventWS2L, ws2l, "LET event WS2L");
    if (volume.name.empty()) volume.name = hit.volumeName;
    if (!volume.pending) {
        volume.pending = true;
        touched_.push_back(&volume);
    }
    ++volume.steps;
    volume.eventWL = nextWL;
    volume.eventWSL = nextWSL;
    volume.eventWS2L = nextWS2L;
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
    for (const Row& r : rows) {
        const VolumeLET& v = *r.v;
        HistoryStatistics::Entry letT;
        letT.name = v.name;
        letT.unit = "keV/um";
        letT.ratio = true;
        letT.entries = v.entries;
        HistoryStatistics::Entry letD = letT;
        letT.sum = v.sumWSL;
        letT.sumSq = v.sumSqWSL;
        letT.denSum = v.sumWL;
        letT.denSumSq = v.sumSqWL;
        letT.crossSum = v.sumWLxWSL;
        letD.sum = v.sumWS2L;
        letD.sumSq = v.sumSqWS2L;
        letD.denSum = v.sumWSL;
        letD.denSumSq = v.sumSqWSL;
        letD.crossSum = v.sumWSLxWS2L;
        HistoryStatistics::Submit(runID_, "let", "let_t", *r.path, letT);
        HistoryStatistics::Submit(runID_, "let", "let_d", *r.path, letD);
    }
    if (output.WritesRoot()) {
        for (const Row& r : rows) {
            AnalysisOutput::FillLET(runID_, output.GetThreadId(), *r.path, r.v->name, particles, r.v->steps,
                                    r.v->sumWL, r.v->sumWSL, r.v->sumWS2L, r.letT, r.letD,
                                    r.v->sumSqWL, r.v->sumSqWSL, r.v->sumSqWS2L, r.v->sumWLxWSL,
                                    r.v->sumWSLxWS2L, events_);
        }
    }
    if (!output.WritesCsv()) return;
    CsvWriter writer(output.MakeOutputPath(output.MakeThreadFilename("let_volume_summary.csv")));
    writer.WriteHeader({"runID", "volume_path", "volume_name", "particles", "steps", "sum_wl_mm",
                        "sum_wSl_MeV", "sum_wS2l_MeV2_per_mm", "let_t_keV_per_um", "let_d_keV_per_um",
                        "sum_sq_wl_mm2", "sum_sq_wSl_MeV2", "sum_sq_wS2l_MeV4_per_mm2",
                        "sum_wl_x_wSl_MeV_mm", "sum_wSl_x_wS2l_MeV3_per_mm", "n_events"});
    for (const Row& r : rows) {
        writer.WriteRow({std::to_string(runID_), *r.path, r.v->name, particles, std::to_string(r.v->steps),
                         Number(r.v->sumWL), Number(r.v->sumWSL), Number(r.v->sumWS2L),
                         Number(r.letT), Number(r.letD), Number(r.v->sumSqWL), Number(r.v->sumSqWSL),
                         Number(r.v->sumSqWS2L), Number(r.v->sumWLxWSL), Number(r.v->sumWSLxWS2L),
                         std::to_string(events_)});
    }
    writer.Close();
    output.RegisterGeneratedFile(writer.GetFilename(), OutputManager::ArtifactScope::Thread,
                                 output.GetRunId(), output.GetThreadId());
}

void LETScorer::Reset()
{
    runID_ = -1;
    events_ = 0;
    touched_.clear();
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
